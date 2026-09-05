"""The lint engine: structural checks L1-L5 and the DEV-specific C1 and C5.

    python -m knowledge.lint [--vault DIR] [--dev-root DIR] [--json]

Exit 0 clean, 1 findings, 3 refused (HALT.flag). Lint writes nothing.

WHAT EACH CHECK CATCHES (WIKI_SCHEMA.md section 7):
  L1  a page without parseable frontmatter, without `type`, or with a field
      that breaks the OKF v0.2 shapes (actor strings, ISO instants, sources
      without `resource`, dev: entries without file/pattern).
  L2  index.md or log.md off the reserved format; an index entry whose path
      does not exist; a page missing from the index; log dates not newest
      first.
  L3  an orphan: a page no other page links to (index.md does not count -
      it lists everything, so it would make the check vacuous).
  L4  `stale_after` in the past on a page that is not `deprecated`.
  L5  a `sources[].resource` that names a local path (file:// or a plain
      path) which no longer exists - the federated raw layer moved or was
      purged.
  C1  copied-state drift: a `dev.asserts` pattern no longer matches its
      file, or a `dev.parameters` value no longer equals what the owning
      file says. The Round 94 header defect, made mechanical.
  C5  a page edited inside its own `dev.window` (file mtime between start
      and end): a registration amended in the window.

C2-C4 and C6 (expired tokens, cross-desk conflicts, unhedged tax, the LLM
contradiction pass) are Phase 2-3 and are not in this file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import DEV_ROOT, EXIT_FINDINGS, EXIT_HALT, EXIT_OK, OWNED_FILES, VAULT, halted
from .frontmatter import parse_iso8601, validate
from .pages import Document, load_documents, parse_index, parse_log


@dataclass
class Finding:
    code: str        # L1..L5, C1, C5
    severity: str    # "error" | "warning"
    path: str        # vault-relative, or the file the check concerned
    message: str

    def line(self) -> str:
        return f"[{self.code}] {self.severity.upper():7} {self.path}: {self.message}"


def _rel(path: Path, vault: Path) -> str:
    try:
        return path.resolve().relative_to(vault.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _local_path(resource: str, dev_root: Path) -> Path | None:
    """A filesystem path for file:// URIs and plain paths; None for git:/http(s)."""
    if resource.startswith("file://"):
        parsed = urlparse(resource)
        raw = unquote(parsed.path)
        # file:///c:/x -> /c:/x on Windows; strip the leading slash before a drive letter
        if re.match(r"^/[A-Za-z]:", raw):
            raw = raw[1:]
        return Path(raw)
    if "://" in resource or resource.startswith("git:"):
        return None
    p = Path(resource)
    return p if p.is_absolute() else dev_root / p


# ---------------------------------------------------------------- checks

def check_l1(docs: list[Document], vault: Path) -> list[Finding]:
    out: list[Finding] = []
    for d in docs:
        rel = _rel(d.path, vault)
        if d.meta is None:
            out.append(Finding("L1", "error", rel, d.error or "no frontmatter"))
            continue
        for issue in validate(d.meta):
            out.append(Finding("L1", "error", rel, issue))
    return out


def check_l2(docs: list[Document], vault: Path) -> list[Finding]:
    out: list[Finding] = []
    index = vault / "index.md"
    if not index.exists():
        out.append(Finding("L2", "warning", "index.md", "missing (run the seed or write_index)"))
    else:
        entries, errors = parse_index(index.read_text(encoding="utf-8"))
        out += [Finding("L2", "error", "index.md", e) for e in errors]
        listed = {e.path for e in entries}
        for e in entries:
            if not (vault / e.path).exists():
                out.append(Finding("L2", "error", "index.md", f"entry path does not exist: {e.path}"))
        for d in docs:
            if d.meta is not None and _rel(d.path, vault) not in listed:
                out.append(Finding("L2", "warning", _rel(d.path, vault), "page not listed in index.md"))
    log = vault / "log.md"
    if log.exists():
        _, errors = parse_log(log.read_text(encoding="utf-8"))
        out += [Finding("L2", "error", "log.md", e) for e in errors]
    return out


def check_l3(docs: list[Document], vault: Path) -> list[Finding]:
    """Orphans. A page is linked if any OTHER page's links name its path, stem or title."""
    out: list[Finding] = []
    for d in docs:
        if d.meta is None:
            continue
        rel = _rel(d.path, vault)
        names = {rel, d.path.stem, d.path.name}
        title = d.meta.get("title")
        if isinstance(title, str) and title:
            names.add(title)
        linked = False
        for other in docs:
            if other is d:
                continue
            for target in other.links:
                t = target.strip()
                if t in names or t.endswith("/" + d.path.name) or t.endswith("/" + d.path.stem):
                    linked = True
                    break
            if linked:
                break
        if not linked:
            out.append(Finding("L3", "warning", rel, "orphan: no inbound link from another page"))
    return out


def check_l4(docs: list[Document], vault: Path, now: datetime) -> list[Finding]:
    out: list[Finding] = []
    for d in docs:
        if d.meta is None or "stale_after" not in d.meta:
            continue
        try:
            stale = parse_iso8601(d.meta["stale_after"])
        except ValueError:
            continue  # L1 reports the malformed value
        if stale < now and d.meta.get("status") != "deprecated":
            out.append(Finding("L4", "warning", _rel(d.path, vault),
                               f"stale_after {d.meta['stale_after']} has passed; review or deprecate"))
    return out


def check_l5(docs: list[Document], vault: Path, dev_root: Path) -> list[Finding]:
    out: list[Finding] = []
    for d in docs:
        if d.meta is None or not isinstance(d.meta.get("sources"), list):
            continue
        for i, s in enumerate(d.meta["sources"]):
            if not isinstance(s, dict) or not isinstance(s.get("resource"), str):
                continue
            p = _local_path(s["resource"], dev_root)
            if p is not None and not p.exists():
                out.append(Finding("L5", "error", _rel(d.path, vault),
                                   f"sources[{i}].resource not on disk: {s['resource']}"))
    return out


def _norm_number(s: str) -> str:
    return s.strip().replace(",", "").replace("$", "").replace(" ", "")


def check_c1(docs: list[Document], vault: Path, dev_root: Path) -> list[Finding]:
    out: list[Finding] = []
    cache: dict[Path, str | None] = {}

    def read(rel_file: str) -> str | None:
        p = Path(rel_file)
        p = p if p.is_absolute() else dev_root / p
        if p not in cache:
            cache[p] = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
        return cache[p]

    for d in docs:
        if d.meta is None or not isinstance(d.meta.get("dev"), dict):
            continue
        rel = _rel(d.path, vault)
        dev = d.meta["dev"]
        for i, a in enumerate(dev.get("asserts") or []):
            if not isinstance(a, dict) or not isinstance(a.get("file"), str) or not isinstance(a.get("pattern"), str):
                continue
            text = read(a["file"])
            if text is None:
                out.append(Finding("C1", "error", rel, f"dev.asserts[{i}]: file missing: {a['file']}"))
                continue
            try:
                ok = re.search(a["pattern"], text, re.M) is not None
            except re.error:
                continue  # L1 reports the bad regex
            if not ok:
                claim = a.get("claim") or a["pattern"]
                out.append(Finding("C1", "error", rel,
                                   f"dev.asserts[{i}] drift: {a['file']} no longer matches /{a['pattern']}/ ({claim})"))
        for i, p in enumerate(dev.get("parameters") or []):
            if not isinstance(p, dict) or not isinstance(p.get("file"), str) or not isinstance(p.get("pattern"), str):
                continue
            text = read(p["file"])
            if text is None:
                out.append(Finding("C1", "error", rel, f"dev.parameters[{i}]: file missing: {p['file']}"))
                continue
            try:
                m = re.search(p["pattern"], text, re.M)
            except re.error:
                continue
            if m is None:
                out.append(Finding("C1", "error", rel,
                                   f"dev.parameters[{i}] {p.get('name')}: pattern not found in {p['file']}"))
                continue
            found = m.group(1) if m.groups() else m.group(0)
            if _norm_number(str(found)) != _norm_number(str(p.get("value"))):
                out.append(Finding("C1", "error", rel,
                                   f"dev.parameters[{i}] {p.get('name')} drift: page says {p.get('value')!r}, "
                                   f"{p['file']} says {found!r}"))
    return out


def check_c5(docs: list[Document], vault: Path) -> list[Finding]:
    out: list[Finding] = []
    for d in docs:
        if d.meta is None or not isinstance(d.meta.get("dev"), dict):
            continue
        w = d.meta["dev"].get("window")
        if not isinstance(w, dict) or "start" not in w or "end" not in w:
            continue
        try:
            start, end = parse_iso8601(w["start"]), parse_iso8601(w["end"])
        except ValueError:
            continue
        mtime = datetime.fromtimestamp(d.path.stat().st_mtime, tz=timezone.utc)
        if start <= mtime <= end:
            out.append(Finding("C5", "error", _rel(d.path, vault),
                               f"edited inside its registration window ({w['start']} .. {w['end']}); "
                               f"modified {mtime.strftime('%Y-%m-%dT%H:%M:%SZ')}"))
    return out


def lint_vault(vault: Path, dev_root: Path, now: datetime | None = None) -> list[Finding]:
    now = now or datetime.now(timezone.utc)
    docs = load_documents(vault)
    findings: list[Finding] = []
    findings += check_l1(docs, vault)
    findings += check_l2(docs, vault)
    findings += check_l3(docs, vault)
    findings += check_l4(docs, vault, now)
    findings += check_l5(docs, vault, dev_root)
    findings += check_c1(docs, vault, dev_root)
    findings += check_c5(docs, vault)
    order = {"error": 0, "warning": 1}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.code, f.path))
    return findings


def summarize(findings: list[Finding], pages: int) -> dict:
    return {
        "pages": pages,
        "findings": len(findings),
        "errors": sum(1 for f in findings if f.severity == "error"),
        "warnings": sum(1 for f in findings if f.severity == "warning"),
        "by_code": {c: sum(1 for f in findings if f.code == c) for c in sorted({f.code for f in findings})},
    }


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.lint", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - lint refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT

    findings = lint_vault(args.vault, args.dev_root)
    pages = sum(1 for _ in load_documents(args.vault))
    summary = summarize(findings, pages)
    if args.json:
        print(json.dumps({"summary": summary, "findings": [asdict(f) for f in findings]}, indent=2), file=out)
    else:
        for f in findings:
            print(f.line(), file=out)
        print(f"lint: {pages} page(s) · {summary['errors']} error(s) · {summary['warnings']} warning(s)"
              + (" · CLEAN" if not findings else ""), file=out)
    return EXIT_FINDINGS if findings else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
