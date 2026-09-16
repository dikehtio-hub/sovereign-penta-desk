"""Reading intake, shared half: parse the inbox, name each source, read and write snapshots. No network.

The operator drops links (videos, articles, papers, repositories) into ``raw/inbox/``. Two commands
turn them into knowledge, and they are split on purpose:

    knowledge.fetch_reading     the ONE module in this package that opens a socket: public URL ->
                                an immutable text snapshot under raw/fetched/
    knowledge.ingest.reading    offline, like every other adapter: inbox + snapshots -> Source Summary
                                pages, the sources register and the strategy family search page

This module is what both share: the inbox grammar, URL classification, the stable page stem, and
the snapshot file format. Everything here is pure given its inputs.

WHY THE STEM IS A HASH. A title is unknown until the fetch and can change on a re-fetch; a YouTube id
is case-sensitive while Windows filenames are not, so two real videos can collide on disk. The stem
is ``source_<kind>_<sha256(canonical url)[:10]>``: stable across fetches, unique on this filesystem.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .frontmatter import try_parse

INBOX_DIR = "raw/inbox"
SNAPSHOT_DIR = "raw/fetched"
HEADER_END = "---"

KINDS = ("youtube", "arxiv", "github", "pdf", "web", "clip")

URL_RE = re.compile(r"https?://[^\s<>\[\]\"'`]+")
EXAMPLE_RE = re.compile(r"example.*delete me", re.I)
TRACKING_PARAM_RE = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|si|feature|pp)$", re.I)
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?$")
NOTE_SEP_RE = re.compile(r"^\s*(?:—|–|-{1,2}|:)\s*")


@dataclass
class InboxItem:
    url: str
    note: str
    file: str            # inbox-relative file name the item came from
    line: int
    kind: str
    canonical: str
    key: str             # video id, arXiv id, owner/repo[/blob path], or the canonical URL
    clip_text: str | None = None   # a clipped article carries its own text: no fetch needed
    clip_title: str | None = None

    @property
    def stem(self) -> str:
        return stem_for(self.kind, self.canonical)


def stem_for(kind: str, canonical: str) -> str:
    return f"source_{kind}_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:10]}"


def _clean_url(raw: str) -> str:
    url = raw.rstrip(".,;:!?*_")
    # a URL may legitimately contain parentheses (Wikipedia); only strip a closing one it did not open
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1]
    return url


def classify(url: str) -> tuple[str, str, str]:
    """(kind, canonical URL, key). Canonical drops fragments and tracking params so one source is one page."""
    p = urlparse(url)
    host = p.netloc.lower()
    bare = host[4:] if host.startswith("www.") else host
    parts = [x for x in p.path.split("/") if x]
    q = dict(parse_qsl(p.query))

    vid = None
    if bare in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        if parts[:1] == ["watch"]:
            vid = q.get("v")
        elif len(parts) >= 2 and parts[0] in ("shorts", "live", "embed"):
            vid = parts[1]
    elif bare == "youtu.be" and parts:
        vid = parts[0]
    if vid and YT_ID_RE.match(vid):
        return "youtube", f"https://www.youtube.com/watch?v={vid}", vid

    if bare.endswith("arxiv.org") and len(parts) >= 2 and parts[0] in ("abs", "pdf", "html"):
        aid = "/".join(parts[1:])
        aid = aid[:-4] if aid.endswith(".pdf") else aid
        m = ARXIV_ID_RE.match(aid)
        if m:
            return "arxiv", f"https://arxiv.org/abs/{m.group(1)}", m.group(1)

    if bare == "github.com" and len(parts) >= 2:
        owner, repo = parts[0], parts[1].removesuffix(".git")
        if len(parts) >= 5 and parts[2] == "blob":
            path = "/".join(parts[3:])
            return "github", f"https://github.com/{owner}/{repo}/blob/{path}", f"{owner}/{repo}/blob/{path}"
        return "github", f"https://github.com/{owner}/{repo}", f"{owner}/{repo}"

    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING_PARAM_RE.match(k)])
    path = p.path.rstrip("/") or ""
    canonical = urlunparse((p.scheme.lower(), host, path, "", query, ""))
    kind = "pdf" if path.lower().endswith(".pdf") else "web"
    return kind, canonical, canonical


def parse_inbox(inbox: Path) -> list[InboxItem]:
    """Every link in every ``*.md`` under the inbox, first occurrence wins, example lines skipped.

    A line may hold several URLs; the note is whatever text on the line is not a URL, with a leading
    separator (``—``, ``-``, ``:``) stripped. A file whose frontmatter names a ``source`` or ``url`` is
    a CLIPPED article (Obsidian Web Clipper writes ``source:``): it becomes one item carrying its own
    body as text, and the fetcher never touches the network for it.
    """
    items: dict[str, InboxItem] = {}
    if not inbox.is_dir():
        return []
    for path in sorted(inbox.rglob("*.md")):
        rel = path.relative_to(inbox).as_posix()
        text = path.read_text(encoding="utf-8")
        meta, body, _err = try_parse(text)
        clip_src = None
        if isinstance(meta, dict):
            for key in ("source", "url"):
                if isinstance(meta.get(key), str) and URL_RE.match(meta[key].strip()):
                    clip_src = meta[key].strip()
                    break
        if clip_src:
            kind_, canonical, _key = classify(_clean_url(clip_src))
            title = meta.get("title") if isinstance(meta.get("title"), str) else None
            item = InboxItem(clip_src, "", rel, 1, "clip", canonical, canonical, clip_text=body.strip(), clip_title=title)
            items.setdefault(item.stem, item)
            continue
        # line numbers count from the top of the file, frontmatter included, so an editor jump lands right
        all_lines = text.replace("\r\n", "\n").split("\n")
        lines = (body if meta is not None else text).replace("\r\n", "\n").split("\n")
        offset = max(0, len(all_lines) - len(lines))
        in_fence = False
        for n, line in enumerate(lines, 1):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence or EXAMPLE_RE.search(line):
                continue
            urls = [_clean_url(m.group(0)) for m in URL_RE.finditer(line)]
            if not urls:
                continue
            rest = line
            for u in urls:
                rest = rest.replace(u, " ")
            rest = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", rest)          # the bullet itself
            rest = re.sub(r"\[\s*\]\(\s*\)|[<>()\[\]]", " ", rest)        # debris of [text](url) / <url>
            note = NOTE_SEP_RE.sub("", re.sub(r"\s+", " ", rest).strip()).strip()
            for u in urls:
                kind, canonical, key = classify(u)
                item = InboxItem(u, note, rel, n + offset, kind, canonical, key)
                existing = items.get(item.stem)
                if existing is None:
                    items[item.stem] = item
                elif note and note not in existing.note:
                    existing.note = f"{existing.note} / {note}" if existing.note else note
    return list(items.values())


# ---------------------------------------------------------------- snapshots

def snapshot_path(vault: Path, stem: str) -> Path:
    return vault / SNAPSHOT_DIR / f"{stem}.txt"


def failure_path(vault: Path, stem: str) -> Path:
    return vault / SNAPSHOT_DIR / f"{stem}.failed.txt"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _one_line(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip()


def render_snapshot(headers: dict, text: str = "") -> str:
    """``key: value`` lines, a ``---`` line, then the text verbatim. Values are forced onto one line."""
    head = [f"{k}: {_one_line(v)}" for k, v in headers.items() if v not in (None, "")]
    return "\n".join(head + [HEADER_END, text]) + "\n"


def read_snapshot(path: Path) -> tuple[dict[str, str], str] | None:
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    head, sep, text = raw.partition(f"\n{HEADER_END}\n")
    if not sep:
        return None
    text = text[:-1] if text.endswith("\n") else text   # render_snapshot adds exactly one; the sha256 is of the text without it
    headers: dict[str, str] = {}
    for line in head.split("\n"):
        k, colon, v = line.partition(": ")
        if colon:
            headers[k.strip()] = v.strip()
    return headers, text
