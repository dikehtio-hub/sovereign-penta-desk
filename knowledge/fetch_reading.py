"""Reading intake, network half: every link in raw/inbox/ -> an immutable text snapshot in raw/fetched/.

    python -m knowledge.fetch_reading [--inbox DIR] [--refetch] [--timeout 30] [--max-chars 400000]
                                      [--dry-run] [--no-compile]

THE ONE MODULE IN THIS PACKAGE THAT OPENS A SOCKET. Every other command reads files that already exist
(WIKI_SCHEMA.md s.9); that stays true because this module does the network half ALONE and writes plain
snapshots, and ``knowledge.ingest.reading`` compiles them offline afterwards. The split keeps the
socket in one named place that a reviewer can audit in a single read, rather than inside an adapter.

WHAT IT FETCHES, AND FROM WHERE. Only URLs the operator typed into the inbox, only with GET, no
credentials, no API keys, nothing metered:
    youtube  title from the public oEmbed endpoint; transcript via youtube_transcript_api (captions
             YouTube already serves to the player), rendered with [mm:ss] markers every minute
    arxiv    the abstract page, then the PDF's text (pypdf)
    github   a repository's README (public API, raw media type) or a single file via raw.githubusercontent
    pdf      the file's text (pypdf)
    web      the page's readable text (bs4: <article>/<main> preferred, chrome stripped)
    clip     a clipped article already in the inbox: its own text, no network at all

WHAT IT REFUSES. HALT.flag (exit 3). A snapshot that already exists is never rewritten without
``--refetch``: a source's text is raw-layer truth and a silent re-fetch would move it under every page
that cites its sha256. A failure writes ``<stem>.failed.txt`` with the reason and is retried on the next
run; a later success removes it. Exit 1 when any fetch failed this run, so a scheduled caller notices.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from . import EXIT_FINDINGS, EXIT_OK, GENERATED_BY
from .pages import assert_owned, iso, now_utc, write_owned_text
from .reading import (INBOX_DIR, InboxItem, failure_path, parse_inbox, render_snapshot, sha256_text,
                      snapshot_path)

USER_AGENT = "Mozilla/5.0 (knowledge.fetch_reading; operator reading inbox)"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_CHARS = 400_000
THIN_TEXT_CHARS = 400
BLOCK_TAGS = ["p", "div", "li", "ul", "ol", "dl", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table",
              "section", "article", "main", "pre", "blockquote", "figcaption", "hr"]
PROCESS = "process:knowledge.fetch_reading"


class FetchError(Exception):
    """A source that could not be turned into text; the message is recorded in the failure marker."""


@dataclass
class Fetched:
    title: str | None
    text: str
    fetcher: str
    author: str | None = None
    warning: str | None = None


@dataclass
class FetchReport:
    fetched: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------- transports (injectable)

def http_get(url: str, timeout: float = DEFAULT_TIMEOUT, headers: dict | None = None):
    import requests  # imported here so the package imports without it and tests never reach it
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    return requests.get(url, timeout=timeout, headers=h)


def youtube_transcript(video_id: str) -> list[tuple[float, str]]:
    """(start seconds, text) snippets. English first; otherwise the first transcript YouTube lists."""
    from youtube_transcript_api import YouTubeTranscriptApi
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except Exception as first:  # noqa: BLE001 - the library raises a family of classes; the message is what matters
        try:
            fetched = next(iter(api.list(video_id))).fetch()
        except Exception:  # noqa: BLE001
            reason = (str(first).strip().splitlines() or [type(first).__name__])[0]
            raise FetchError(f"no transcript ({type(first).__name__}): {reason[:200]}") from None
    return [(float(s.start), str(s.text)) for s in fetched]


# ---------------------------------------------------------------- extraction

def _clean_lines(text: str) -> str:
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


def html_to_text(html: str) -> tuple[str | None, str | None, str]:
    """(title, author, readable text). Prefers <article>, then <main>, then <body>; strips page chrome."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    def meta(*names: str) -> str | None:
        for n in names:
            tag = soup.find("meta", attrs={"name": n}) or soup.find("meta", attrs={"property": n})
            if tag and tag.get("content", "").strip():
                return tag["content"].strip()
        return None

    title = meta("citation_title", "og:title", "twitter:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    author = meta("citation_author", "author", "article:author")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    # Newlines come from BLOCK elements only. get_text("\n") put every inline link and citation marker on a
    # line of its own ("see\nMean reversion (disambiguation)\n." on the first live Wikipedia fetch), which a
    # reader has to re-join by eye. Inline elements now join their sentence; cells get a space.
    for br in root.find_all("br"):
        br.replace_with("\n")
    for tag in root.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    for cell in root.find_all(["td", "th"]):
        cell.insert_after(" ")
    return title, author, _clean_lines(root.get_text(""))


def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return _clean_lines("\n\n".join((page.extract_text() or "") for page in reader.pages))


def _stamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def render_transcript(snippets: list[tuple[float, str]], every_s: int = 60) -> str:
    """Paragraphs of caption text, each opened by a [mm:ss] marker, one per `every_s` seconds of video."""
    paras: list[str] = []
    current: list[str] = []
    next_mark = 0.0
    for start, text in snippets:
        if start >= next_mark:
            if current:
                paras.append(" ".join(current))
            current = [f"[{_stamp(start)}]"]
            next_mark = (int(start // every_s) + 1) * every_s
        current.append(re.sub(r"\s+", " ", text).strip())
    if current:
        paras.append(" ".join(current))
    return "\n\n".join(paras)


def _ok(resp, url: str):
    if getattr(resp, "status_code", 200) >= 400:
        raise FetchError(f"HTTP {resp.status_code} for {url}")
    return resp


# ---------------------------------------------------------------- per kind

def fetch_item(item: InboxItem, *, get: Callable = http_get, transcript: Callable = youtube_transcript,
               timeout: float = DEFAULT_TIMEOUT) -> Fetched:
    if item.kind == "clip" or item.clip_text is not None:
        if not (item.clip_text or "").strip():
            raise FetchError("clipped file has a source URL but no body text")
        return Fetched(item.clip_title, item.clip_text, "clip")

    if item.kind == "youtube":
        title = author = None
        try:
            r = get("https://www.youtube.com/oembed?" + urlencode({"format": "json", "url": item.canonical}), timeout=timeout)
            if getattr(r, "status_code", 200) < 400:
                data = r.json()
                title, author = data.get("title"), data.get("author_name")
        except Exception:  # noqa: BLE001 - a missing title is not a failed source
            pass
        snippets = transcript(item.key)
        if not snippets:
            raise FetchError("transcript is empty")
        return Fetched(title, render_transcript(snippets), "youtube_transcript_api", author)

    if item.kind == "arxiv":
        abs_resp = _ok(get(item.canonical, timeout=timeout), item.canonical)
        title, author, abstract = html_to_text(abs_resp.text)
        text, warning = f"ABSTRACT PAGE\n\n{abstract}", None
        pdf_url = f"https://arxiv.org/pdf/{item.key}"
        try:
            text += "\n\nFULL TEXT (PDF)\n\n" + pdf_to_text(_ok(get(pdf_url, timeout=timeout), pdf_url).content)
        except Exception as e:  # noqa: BLE001 - the abstract alone is still a usable source
            warning = f"PDF text unavailable ({type(e).__name__}); abstract page only"
        return Fetched(title, text, "arxiv+pypdf", author, warning)

    if item.kind == "github":
        owner_repo, _, blob = item.key.partition("/blob/")
        if blob:
            raw = f"https://raw.githubusercontent.com/{owner_repo}/{blob}"
            return Fetched(f"{owner_repo}: {blob.split('/', 1)[-1]}", _ok(get(raw, timeout=timeout), raw).text, "github-raw")
        api = f"https://api.github.com/repos/{owner_repo}/readme"
        resp = _ok(get(api, timeout=timeout, headers={"Accept": "application/vnd.github.raw"}), api)
        return Fetched(f"{owner_repo} (README)", resp.text, "github-readme")

    resp = _ok(get(item.url, timeout=timeout), item.url)
    ctype = (getattr(resp, "headers", {}) or {}).get("content-type", "").lower()
    content = getattr(resp, "content", b"") or b""
    if item.kind == "pdf" or "pdf" in ctype or content[:4] == b"%PDF":
        return Fetched(None, pdf_to_text(content), "pypdf")
    title, author, text = html_to_text(resp.text)
    warning = None
    if len(text) < THIN_TEXT_CHARS:
        warning = (f"thin text ({len(text)} chars): the page probably renders with JavaScript or sits behind a "
                   "login - clip it into raw/inbox/ with a browser clipper instead")
    return Fetched(title, text, "requests+bs4", author, warning)


# ---------------------------------------------------------------- run

def run_fetch(vault: Path, *, inbox: Path | None = None, refetch: bool = False, timeout: float = DEFAULT_TIMEOUT,
              max_chars: int = DEFAULT_MAX_CHARS, dry_run: bool = False, get: Callable = http_get,
              transcript: Callable = youtube_transcript, now: datetime | None = None, out=None) -> FetchReport:
    out = out or sys.stdout
    inbox = inbox or (vault / INBOX_DIR)
    report = FetchReport()
    for item in parse_inbox(inbox):
        snap, fail = snapshot_path(vault, item.stem), failure_path(vault, item.stem)
        if snap.is_file() and not refetch:
            report.skipped.append(item.stem)
            print(f"[SKIP]  {item.stem}  already fetched ({item.url})", file=out)
            continue
        if dry_run:
            print(f"[WOULD] {item.stem}  {item.kind}  {item.url}", file=out)
            continue
        at = iso(now or now_utc())
        try:
            got = fetch_item(item, get=get, transcript=transcript, timeout=timeout)
        except Exception as e:  # noqa: BLE001 - every failure becomes a recorded, retryable marker
            reason = str(e) if isinstance(e, FetchError) else f"{type(e).__name__}: {e}"
            reason = (reason.strip().splitlines() or ["unknown error"])[0][:300]
            write_owned_text(fail, render_snapshot({"url": item.url, "canonical": item.canonical, "kind": item.kind,
                                                    "status": "failed", "attempted_at": at, "error": reason}), vault)
            report.failed.append((item.stem, reason))
            print(f"[FAIL]  {item.stem}  {reason}", file=out)
            continue
        text = got.text.strip("\n")   # normalised before hashing, so read_snapshot returns exactly what was hashed
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + f"\n\n[truncated by knowledge.fetch_reading at {max_chars:,} characters]"
        headers = {"url": item.url, "canonical": item.canonical, "kind": item.kind, "status": "ok",
                   "title": got.title, "author": got.author, "fetched_at": at, "fetcher": got.fetcher,
                   "chars": len(text), "sha256": sha256_text(text), "truncated": "yes" if truncated else None,
                   "warning": got.warning}
        write_owned_text(snap, render_snapshot(headers, text), vault)
        if fail.is_file():
            assert_owned(fail, vault)
            fail.unlink()
        report.fetched.append(item.stem)
        print(f"[FETCH] {item.stem}  {item.kind}  {len(text):,} chars  {got.title or item.url}", file=out)
        if got.warning:
            print(f"        warning: {got.warning}", file=out)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    from .ingest import add_common_args, at_from, guard
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.fetch_reading", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--inbox", type=Path, default=None, help=f"default <vault>/{INBOX_DIR}")
    ap.add_argument("--refetch", action="store_true", help="rewrite snapshots that already exist")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched; no network, no writes")
    ap.add_argument("--no-compile", action="store_true", help="skip knowledge.ingest.reading afterwards")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    report = run_fetch(args.vault, inbox=args.inbox, refetch=args.refetch, timeout=args.timeout,
                       max_chars=args.max_chars, dry_run=args.dry_run, now=at_from(args), out=out)
    print(f"fetched {len(report.fetched)}, skipped {len(report.skipped)}, failed {len(report.failed)}", file=out)
    if not args.dry_run and not args.no_compile:
        from .ingest.reading import ingest_reading
        rep = ingest_reading(args.vault, args.dev_root, inbox=args.inbox, at=at_from(args), by=GENERATED_BY)
        print(f"compiled {rep.sources} source page(s), {len(rep.written)} written, {rep.pending} awaiting review "
              f"-> wiki/concepts/strategy_family_search.md", file=out)
    return EXIT_FINDINGS if report.failed else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
