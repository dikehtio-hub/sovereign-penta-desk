"""The lint engine: structural checks L1-L5 and the DEV-specific C1, C2, C3, C5.

    python -m knowledge.lint [--vault DIR] [--dev-root DIR] [--drops DIR] [--json]

Exit 0 clean, 1 findings, 3 refused (HALT.flag). Lint writes nothing.

WHAT EACH CHECK CATCHES (WIKI_SCHEMA.md section 7):
  L1  a page without parseable frontmatter, without `type`, or with a field
      that breaks the OKF v0.2 shapes. The constitution is in scope.
  L2  index.md or log.md off the reserved format; an index entry whose path
      does not exist; a page missing from the root index; log dates not
      newest first. Every index.md under the owned folders (raw/index.md)
      is format-checked and its paths resolved relative to its own folder.
  L3  an orphan: a page no other page links to. index.md does not count,
      and the constitution is exempt (Round 97 ruling 5).
  L4  `stale_after` in the past on a page that is not `deprecated`.
  L5  a `sources[].resource` that names a local path which no longer exists.
  C1  copied-state drift: a `dev.asserts` pattern no longer matches its
      file; a `dev.parameters` value no longer equals what the owning file
      says (compared as floats when both sides parse, else as normalised
      strings - Round 97 ruling 2); a `dev.requires_files` entry is gone.
  C2  expired market tokens: a `dev.token_id` or `dev.tokens[]` entry on a
      non-deprecated page that is absent from the newest macro and sports
      drops (resolved, delisted, or never listed).
  C3  cross-desk parameter conflicts: the same `dev.parameters[].name`
      declared with different values on two or more pages.
  C5  a page edited inside its own `dev.window`: `generated.at` inside the
      window is an error (the agent stamped it there); only the file mtime
      inside the window is a warning (a checkout can do that) - ruling 3.

C4 (unhedged tax liability) and C6 (the LLM contradiction pass) are Phase 3.
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

from . import DEV_ROOT, EXIT_FINDINGS, EXIT_HALT, EXIT_OK, VAULT, halted
from .frontmatter import parse_iso8601, validate
from .pages import Document, iter_index_files, load_documents, parse_index, parse_log

DEFAULT_DROPS = Path("Sports_Desk") / "data" / "polymarket_drops"


@dataclass
class Finding:
    code: str        # L1..L5, C1, C2, C3, C5
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
        if re.match(r"^/[A-Za-z]:", raw):
            raw = raw[1:]
        return Path(raw)
    if "://" in resource or resource.startswith("git:"):
        return None
    p = Path(resource)
    return p if p.is_absolute() else dev_root / p


def _norm(s: object) -> str:
    return str(s).strip().replace(",", "").replace("$", "").replace(" ", "")


def values_equal(a: object, b: object) -> bool:
    """Ruling 2: compare as floats when both sides parse, else as normalised strings."""
    na, nb = _norm(a), _norm(b)
    try:
        return float(na) == float(nb)
    except ValueError:
        return na == nb


def _dev(d: Document) -> dict | None:
    if d.meta is None:
        return None
    dev = d.meta.get("dev")
    return dev if isinstance(dev, dict) else None


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


def _check_index_file(index: Path, base: Path, vault: Path) -> tuple[list[Finding], set[str]]:
    out: list[Finding] = []
    rel = _rel(index, vault)
    entries, errors = parse_index(index.read_text(encoding="utf-8"))
    out += [Finding("L2", "error", rel, e) for e in errors]
    for e in entries:
        if not (base / e.path).exists():
            out.append(Finding("L2", "error", rel, f"entry path does not exist: {e.path}"))
    return out, {e.path for e in entries}


def check_l2(docs: list[Document], vault: Path) -> list[Finding]:
    out: list[Finding] = []
    index = vault / "index.md"
    if not index.exists():
        out.append(Finding("L2", "warning", "index.md", "missing (run the seed or write_index)"))
    else:
        findings, listed = _check_index_file(index, vault, vault)
        out += findings
        for d in docs:
            if d.meta is not None and not d.constitution and _rel(d.path, vault) not in listed:
                out.append(Finding("L2", "warning", _rel(d.path, vault), "page not listed in index.md"))
    for sub in iter_index_files(vault):
        findings, _ = _check_index_file(sub, sub.parent, vault)
        out += findings
    log = vault / "log.md"
    if log.exists():
        _, errors = parse_log(log.read_text(encoding="utf-8"))
        out += [Finding("L2", "error", "log.md", e) for e in errors]
    return out


def check_l3(docs: list[Document], vault: Path) -> list[Finding]:
    """Orphans. A page is linked if any OTHER page's links name its path, stem or title."""
    out: list[Finding] = []
    for d in docs:
        if d.meta is None or d.constitution:
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
            continue
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
        dev = _dev(d)
        if dev is None:
            continue
        rel = _rel(d.path, vault)
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
                continue
            if not ok:
                claim = a.get("claim") or a["pattern"]
                out.append(Finding("C1", "error", rel,
                                   f"dev.asserts[{i}] drift: {a['file']} no longer matches /{a['pattern']}/ ({claim})"))
        for i, p in enumerate(dev.get("parameters") or []):
            if not isinstance(p, dict) or not isinstance(p.get("file"), str):
                continue
            text = read(p["file"])
            if text is None:
                out.append(Finding("C1", "error", rel, f"dev.parameters[{i}]: file missing: {p['file']}"))
                continue
            if isinstance(p.get("json_path"), str):
                # a JSON source is addressed by dotted path, because the same key can occur in several
                # blocks (lead_lag_tier2b.meta.json has readiness.min_points 200 AND bars.min_points 60)
                try:
                    node = json.loads(text)
                    for part in p["json_path"].split("."):
                        node = node[int(part)] if isinstance(node, list) else node[part]
                except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
                    out.append(Finding("C1", "error", rel,
                                       f"dev.parameters[{i}] {p.get('name')}: json_path {p['json_path']} not found in {p['file']}"))
                    continue
                found: object = node
            elif isinstance(p.get("pattern"), str):
                try:
                    m = re.search(p["pattern"], text, re.M)
                except re.error:
                    continue
                if m is None:
                    out.append(Finding("C1", "error", rel,
                                       f"dev.parameters[{i}] {p.get('name')}: pattern not found in {p['file']}"))
                    continue
                found = m.group(1) if m.groups() else m.group(0)
            else:
                continue
            if not values_equal(found, p.get("value")):
                out.append(Finding("C1", "error", rel,
                                   f"dev.parameters[{i}] {p.get('name')} drift: page says {p.get('value')!r}, "
                                   f"{p['file']} says {found!r}"))
        for i, f in enumerate(dev.get("requires_files") or []):
            if isinstance(f, str) and read(f) is None:
                out.append(Finding("C1", "error", rel, f"dev.requires_files[{i}] missing: {f}"))
    return out


def newest_drop(drops: Path, prefix: str) -> Path | None:
    """The newest stamped drop for a prefix, else the canonical file, else None."""
    stamped = sorted(drops.glob(f"{prefix}_*.json"))
    if stamped:
        return stamped[-1]
    canonical = drops / f"{prefix}.json"
    return canonical if canonical.is_file() else None


_newest = newest_drop


def load_live_tokens(drops: Path) -> tuple[set[str], list[str]]:
    """Token ids in the newest macro and sports drops, plus the files they came from."""
    tokens: set[str] = set()
    used: list[str] = []
    for prefix in ("polymarket_macro", "polymarket_sports"):
        f = _newest(drops, prefix)
        if f is None:
            continue
        try:
            records = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(records, list):
            for r in records:
                if isinstance(r, dict) and r.get("token_id"):
                    tokens.add(str(r["token_id"]))
            used.append(f.name)
    return tokens, used


def page_tokens(dev: dict) -> list[str]:
    out: list[str] = []
    if isinstance(dev.get("token_id"), str):
        out.append(dev["token_id"])
    for t in dev.get("tokens") or []:
        if isinstance(t, str):
            out.append(t)
    return out


def check_c2(docs: list[Document], vault: Path, drops: Path | None) -> list[Finding]:
    out: list[Finding] = []
    bearing = [(d, page_tokens(_dev(d) or {})) for d in docs
               if _dev(d) is not None and d.meta.get("status") != "deprecated"]
    bearing = [(d, t) for d, t in bearing if t]
    if not bearing:
        return out
    if drops is None or not drops.is_dir():
        out.append(Finding("C2", "warning", "(drops)",
                           f"drops folder not found ({drops}); {len(bearing)} token-bearing page(s) unchecked"))
        return out
    live, used = load_live_tokens(drops)
    if not live:
        out.append(Finding("C2", "warning", "(drops)", f"no drop records under {drops}; token expiry unchecked"))
        return out
    for d, toks in bearing:
        for t in toks:
            if t not in live:
                out.append(Finding("C2", "warning", _rel(d.path, vault),
                                   f"token {t[:12]}... not in the newest drops ({', '.join(used)}): resolved, delisted or never listed"))
    return out


def check_c3(docs: list[Document], vault: Path) -> list[Finding]:
    seen: dict[str, list[tuple[object, str]]] = {}
    for d in docs:
        dev = _dev(d)
        if dev is None:
            continue
        for p in dev.get("parameters") or []:
            if isinstance(p, dict) and isinstance(p.get("name"), str) and "value" in p:
                seen.setdefault(p["name"], []).append((p["value"], _rel(d.path, vault)))
    out: list[Finding] = []
    for name, entries in sorted(seen.items()):
        if len(entries) < 2:
            continue
        first = entries[0][0]
        if any(not values_equal(v, first) for v, _ in entries[1:]):
            detail = "; ".join(f"{path} says {v!r}" for v, path in entries)
            out.append(Finding("C3", "error", entries[0][1], f"parameter {name!r} conflicts across pages: {detail}"))
    return out


def check_c5(docs: list[Document], vault: Path) -> list[Finding]:
    out: list[Finding] = []
    for d in docs:
        dev = _dev(d)
        if dev is None:
            continue
        w = dev.get("window")
        if not isinstance(w, dict) or "start" not in w or "end" not in w:
            continue
        try:
            start, end = parse_iso8601(w["start"]), parse_iso8601(w["end"])
        except ValueError:
            continue
        rel = _rel(d.path, vault)
        gen_at = None
        gen = d.meta.get("generated") if d.meta else None
        if isinstance(gen, dict) and "at" in gen:
            try:
                gen_at = parse_iso8601(gen["at"])
            except ValueError:
                gen_at = None
        mtime = datetime.fromtimestamp(d.path.stat().st_mtime, tz=timezone.utc)
        if gen_at is not None and start <= gen_at <= end:
            out.append(Finding("C5", "error", rel,
                               f"generated.at {gen['at']} is inside its registration window ({w['start']} .. {w['end']})"))
        elif start <= mtime <= end:
            out.append(Finding("C5", "warning", rel,
                               f"file mtime {mtime.strftime('%Y-%m-%dT%H:%M:%SZ')} is inside its registration window "
                               f"({w['start']} .. {w['end']}) but generated.at is not: a checkout, or an edit"))
    return out


def lint_vault(vault: Path, dev_root: Path, now: datetime | None = None,
               drops: Path | None = None) -> list[Finding]:
    now = now or datetime.now(timezone.utc)
    if drops is None:
        drops = dev_root / DEFAULT_DROPS
    docs = load_documents(vault)
    findings: list[Finding] = []
    findings += check_l1(docs, vault)
    findings += check_l2(docs, vault)
    findings += check_l3(docs, vault)
    findings += check_l4(docs, vault, now)
    findings += check_l5(docs, vault, dev_root)
    findings += check_c1(docs, vault, dev_root)
    findings += check_c2(docs, vault, drops)
    findings += check_c3(docs, vault)
    findings += check_c5(docs, vault)
    order = {"error": 0, "warning": 1}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.code, f.path))
    return findings


def apply_fix_safe(findings: list[Finding], vault: Path, now: datetime | None = None) -> list[str]:
    """The only writes lint may make (WIKI_SCHEMA.md s.7): deprecate a Market page whose token left
    the drops (C2). index.md is untouched (status is not an index column); one log bullet records it."""
    from .pages import append_log, iso, load_page, write_page  # local import keeps lint importable by pages' users

    now = now or datetime.now(timezone.utc)
    changed: list[str] = []
    for f in findings:
        if f.code != "C2" or f.path.startswith("("):
            continue
        page = load_page(vault / f.path)
        if page is None or page.type != "Market" or page.meta.get("status") == "deprecated":
            continue
        page.meta["status"] = "deprecated"
        dev = page.meta.setdefault("dev", {})
        dev["deprecated"] = {"at": iso(now), "reason": f.message}
        write_page(page, vault, now=now)
        changed.append(f.path)
    if changed:
        append_log(vault, "Lint", f"--fix-safe deprecated {len(changed)} Market page(s) whose token left the newest drops: "
                   + ", ".join(f"[[{Path(p).stem}]]" for p in changed), when=now)
    return changed


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
    ap.add_argument("--drops", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_DROPS.as_posix()}")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix-safe", action="store_true",
                    help="apply the only permitted fixes: deprecate Market pages whose token left the drops (C2)")
    args = ap.parse_args(argv)

    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - lint refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT

    findings = lint_vault(args.vault, args.dev_root, drops=args.drops)
    if args.fix_safe:
        changed = apply_fix_safe(findings, args.vault)
        if changed:
            print(f"[FIX-SAFE] deprecated {len(changed)} Market page(s): {', '.join(changed)}", file=out)
            findings = lint_vault(args.vault, args.dev_root, drops=args.drops)
    pages = sum(1 for d in load_documents(args.vault) if not d.constitution)
    summary = summarize(findings, pages)
    if args.json:
        print(json.dumps({"summary": summary, "findings": [asdict(f) for f in findings]}, indent=2), file=out)
    else:
        for f in findings:
            print(f.line(), file=out)
        print(f"lint: {pages} page(s) + constitution · {summary['errors']} error(s) · {summary['warnings']} warning(s)"
              + (" · CLEAN" if not findings else ""), file=out)
    return EXIT_FINDINGS if findings else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
