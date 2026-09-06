"""The lint engine: structural checks L1-L9 and the DEV-specific C1, C2, C3, C5.

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
  L5  a cited source that is no longer there: a `sources[].resource`
      naming a local path that does not exist, or (Round 106) a git
      provenance reference - `sources[].resource: git:<sha>` or a
      `dev.citations` entry - naming a commit this repository does not
      contain. The git half is SKIPPED, not passed, outside a repository.
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
  L6  typed relations (Round 100): a `supersedes` target must exist and be
      deprecated, and chains must be acyclic; `contradicts` needs a
      `resolved_by` relation to an existing Ruling page; `measured_by` must
      name an Experiment page; `enforced_in` must name a file in the repo.
  L7  staleness policy (Round 100): a Ruling (180 d) or Concept (90 d) page
      without `stale_after` is a warning unless it is machine-maintained.
  L9  a wikilink whose only target is a file git IGNORES (Round 108). The
      page lints clean here and fails L8 on a fresh clone, where the file
      does not exist. Skipped outside a repository, like L5's git half.
  L8  a dangling outbound wikilink (Round 105): `[[target]]` naming a page
      that does not exist. The mirror of L3, which catches the page nothing
      links to. Links inside code fences and code spans are not links, so
      the constitution can document the syntax without tripping the check.

C4 (unhedged tax liability) and C6 (the LLM contradiction pass) are Phase 3.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import DEV_ROOT, EXIT_FINDINGS, EXIT_HALT, EXIT_OK, VAULT, halted
from .frontmatter import parse_iso8601, validate
from .pages import (Document, iter_index_files, load_documents, parse_index, parse_log,
                    wikilink_targets)

DEFAULT_DROPS = Path("Sports_Desk") / "data" / "polymarket_drops"


@dataclass
class Finding:
    code: str        # L1..L9, C1, C2, C3, C5
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
    # Round 109: a `#fragment` names a SECTION of the file, not a different file. A digest citing
    # `AGENTS.md#round-109-findings` is citing AGENTS.md; resolving the whole string as a path would
    # report a missing file that is sitting right there. extract_links already strips anchors for
    # markdown links, so this brings sources into line with them.
    p = Path(resource.split("#", 1)[0])
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


GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def is_git_repo(dev_root: Path) -> bool:
    try:
        r = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=str(dev_root),
                           capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def commit_exists(sha: str, dev_root: Path) -> bool:
    """Whether `sha` names a commit object in this repository. Read-only; never fetches."""
    if not GIT_SHA_RE.match(sha):
        return False
    try:
        r = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=str(dev_root),
                           capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def git_citations(meta: dict[str, Any]) -> list[tuple[str, str]]:
    """Every git provenance reference on a page, as (where, sha).

    Two spellings, both already in use: a `sources[].resource` of the form `git:<sha>` (which
    seed.py has written on every ruling that cites a commit since Round 96), and an explicit
    `dev.citations` list for pages that reference a commit without calling it a source.
    """
    out: list[tuple[str, str]] = []
    for i, s in enumerate(meta.get("sources") or []):
        if isinstance(s, dict) and isinstance(s.get("resource"), str) and s["resource"].startswith("git:"):
            out.append((f"sources[{i}].resource", s["resource"][4:].strip()))
    dev = meta.get("dev")
    if isinstance(dev, dict):
        for i, c in enumerate(dev.get("citations") or []):
            if isinstance(c, str):
                out.append((f"dev.citations[{i}]", c.strip()))
            elif isinstance(c, dict) and isinstance(c.get("commit"), str):
                out.append((f"dev.citations[{i}].commit", c["commit"].strip()))
    return out


def check_l5(docs: list[Document], vault: Path, dev_root: Path) -> list[Finding]:
    """L5: a cited source that is no longer there.

    Round 106 (backlog B19/B20) widens this from local paths to GIT PROVENANCE. A ruling that says
    "implemented in commit da48cf3" is making a checkable claim, and an unresolvable hash means
    either the commit was rewritten out of history or the number was typed from memory - the same
    class of failure as a `sources[].resource` naming a file that has been deleted, which is why it
    belongs here rather than in a rule of its own.

    THE CHECK IS SKIPPED, NOT PASSED, WHEN IT CANNOT RUN. Outside a git repository (a test fixture,
    an exported copy of the vault) `git cat-file` cannot answer, and reporting "valid" would be a
    lie while reporting "missing" would be a false alarm. Verification is only attempted when
    `dev_root` is actually a repository. Nothing here writes, fetches or touches the network.
    """
    out: list[Finding] = []
    repo = is_git_repo(dev_root)
    for d in docs:
        if d.meta is None:
            continue
        rel = _rel(d.path, vault)
        if isinstance(d.meta.get("sources"), list):
            for i, s in enumerate(d.meta["sources"]):
                if not isinstance(s, dict) or not isinstance(s.get("resource"), str):
                    continue
                p = _local_path(s["resource"], dev_root)
                if p is not None and not p.exists():
                    out.append(Finding("L5", "error", rel,
                                       f"sources[{i}].resource not on disk: {s['resource']}"))
        if not repo:
            continue
        for where, sha in git_citations(d.meta):
            if not GIT_SHA_RE.match(sha):
                out.append(Finding("L5", "error", rel,
                                   f"{where}: {sha!r} is not a commit hash"))
            elif not commit_exists(sha, dev_root):
                out.append(Finding("L5", "error", rel,
                                   f"{where}: commit {sha} is not in this repository"))
    return out


def link_namespace(docs: list[Document], vault: Path) -> set[str]:
    """Every name a [[wikilink]] may legitimately resolve to.

    Obsidian resolves a wikilink by FILENAME, not by title, so a page's title is deliberately NOT
    in here: letting a title resolve would quietly pass a link that Obsidian itself renders broken.
    Frontmatter `aliases` are honoured because Obsidian honours them.
    """
    names: set[str] = set()
    for d in docs:
        rel = _rel(d.path, vault)
        names |= {rel, rel[:-3] if rel.endswith(".md") else rel, d.path.stem, d.path.name}
        aliases = (d.meta or {}).get("aliases")
        if isinstance(aliases, str):
            names.add(aliases)
        elif isinstance(aliases, list):
            names |= {a for a in aliases if isinstance(a, str)}
    # EVERY note in the vault, not only the ones this package owns. A reader opens the vault in
    # Obsidian, which resolves against all of it: the desks link the exporter-owned Monarch_Hub,
    # and each CRM whale page links its exporter-owned Whales/<address> note. Those are real,
    # resolvable links; scoping the namespace to owned documents would report 183 false ones.
    # Tooling folders (`_views`, `_templates`) and dot-folders are not linkable content.
    for f in vault.rglob("*.md"):
        parts = f.relative_to(vault).parts
        if any(part.startswith(".") or part.startswith("_") for part in parts):
            continue
        rel = f.relative_to(vault).as_posix()
        names |= {rel, rel[:-3], f.stem, f.name}
    return {n for n in names if n}


def check_l8(docs: list[Document], vault: Path) -> list[Finding]:
    """L8 (Round 105, Ruling R104-4): an outbound wikilink naming a page that does not exist.

    L3 catches the opposite failure - a page nothing links TO. Nothing caught a link pointing at
    nothing, and in Round 104 a guessed page stem produced a broken link that linted perfectly
    clean; it was found by reading the rendered page, which is not a control.

    An error, not a warning: unlike an orphan, a dangling link is never a transitional state that
    resolves itself. It is either a typo or a page renamed out from under a reference.
    """
    names = link_namespace(docs, vault)
    out: list[Finding] = []
    for d in docs:
        if d.meta is None:
            continue
        rel = _rel(d.path, vault)
        for target in sorted(wikilink_targets(d.body)):
            if target in names or target.split("/")[-1] in names:
                continue
            out.append(Finding("L8", "error", rel, f"dangling wikilink: [[{target}]] resolves to no page"))
    return out


def _repo_rel(path: Path, dev_root: Path) -> str:
    """`path` as git would name it: relative to the repository root, forward slashes."""
    try:
        return path.resolve().relative_to(dev_root.resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix().replace("\\", "/")


def ignored_under(root: Path, dev_root: Path) -> set[str]:
    """Every git-ignored file under `root`, repo-relative, in ONE call.

    WHY NOT `git check-ignore`, WHICH IS THE OBVIOUS TOOL. Three ways it failed here, each found
    against the real vault and none of which announces itself:

      * on argv it blows the Windows command-line limit outright (WinError 206 at 519 paths);
      * `--stdin` SILENTLY TRUNCATES: at 568 paths the tail was dropped and git reported nothing
        ignored, with an empty stderr and a clean exit;
      * and even inside a 100-path batch it emitted only the FIRST match - so all three ignored
        dashboards went in and exactly one came back.

    A linter that answers "all clear" because it never saw the question is worse than no linter, so
    the question is asked the other way round: `ls-files --others --ignored --exclude-standard`
    enumerates what git ignores, completely, in a single call with no per-path plumbing to get
    wrong. The caller intersects.
    """
    # git speaks REPO-RELATIVE paths and knows nothing about our absolute ones; a comparison across
    # the two silently matches nothing, which for a linter reads as "all clear".
    spec = _repo_rel(root, dev_root)
    try:
        r = subprocess.run(["git", "ls-files", "--others", "--ignored", "--exclude-standard",
                            "--", spec], cwd=str(dev_root),
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {ln.strip().replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip()}


def check_l9(docs: list[Document], vault: Path, dev_root: Path) -> list[Finding]:
    """L9 (Round 108, Ruling R107-1.D): a wikilink whose only target is a git-ignored file.

    The mirror of the hole Round 107 opened. Untracking the three volatile dashboards was safe
    BECAUSE they had no inbound links - a fact verified by hand, once, and then not enforced by
    anything. A page committed tomorrow linking an ignored file would lint CLEAN here and fail L8
    on a FRESH CLONE, where the file does not exist. That is the worst shape of bug: invisible to
    the person who introduced it, and only reproducible somewhere else.

    Skipped outside a git repository, like L5's provenance half: `git check-ignore` cannot answer
    there, and a guess in either direction is worse than silence.
    """
    if not is_git_repo(dev_root):
        return []
    # every name a link may resolve to -> the file it resolves to
    resolved: dict[str, Path] = {}
    for f in vault.rglob("*.md"):
        parts = f.relative_to(vault).parts
        if any(p.startswith(".") or p.startswith("_") for p in parts):
            continue
        rel = f.relative_to(vault).as_posix()
        for name in (rel, rel[:-3], f.stem, f.name):
            resolved.setdefault(name, f)

    linked: dict[Path, list[tuple[str, str]]] = {}
    for d in docs:
        if d.meta is None:
            continue
        page = _rel(d.path, vault)
        for target in sorted(wikilink_targets(d.body)):
            f = resolved.get(target) or resolved.get(target.split("/")[-1])
            if f is not None:
                linked.setdefault(f, []).append((page, target))

    ignored = ignored_under(vault, dev_root)
    out: list[Finding] = []
    for f, refs in sorted(linked.items()):
        if _repo_rel(f, dev_root) not in ignored:
            continue
        rel = f.relative_to(vault).as_posix()
        for page, target in refs:
            out.append(Finding("L9", "error", page,
                               f"[[{target}]] targets git-ignored file '{rel}'; fresh clones will fail L8"))
    return out


RULE_FIELDS = ("label", "condition", "market", "outcome", "neg_risk")


def rules_from_raw(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """The registration JSON's rules in the shape the page stores them.

    ONE function, imported by the compiler, so the page and the check cannot disagree about what
    "the same rules" means. Two independent transcriptions of the same mapping would drift exactly
    the way this check exists to catch.
    """
    out = []
    for r in raw.get("rules") or []:
        if isinstance(r, dict):
            out.append({"label": r.get("label"),
                        "condition": f"{r.get('field')} {r.get('op')} {r.get('value')}".strip(),
                        "market": str(r.get("market", "")),
                        "outcome": r.get("outcome_if_true"),
                        "neg_risk": bool(r.get("neg_risk", False))})
    return out


def check_rules_drift(meta: dict[str, Any], rel: str, dev_root: Path) -> list[Finding]:
    """C1 over `dev.rules` (Round 109, Ruling R108-1.E).

    Round 108 copied the registration's rules into the page's frontmatter so the drill card could
    show whole token ids without parsing a rendered table. That created a SECOND COPY of the one
    thing in this repository that must never quietly change - the pre-registered mapping from a Fed
    decision to a market - and nothing checked the two agreed. This does.

    A token id that drifts here is not a formatting bug: it is the card telling an operator to trade
    a different market than the one that was registered before the data was seen.
    """
    dev = meta.get("dev") or {}
    if dev.get("kind") != "sniper_rules" or not dev.get("registration"):
        return []
    src = dev_root / str(dev["registration"])
    if not src.is_file():
        return [Finding("C1", "error", rel, f"dev.registration missing on disk: {dev['registration']}")]
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [Finding("C1", "error", rel, f"dev.registration unreadable ({e.__class__.__name__}): {dev['registration']}")]
    want, have = rules_from_raw(raw), [dict(r) for r in (dev.get("rules") or []) if isinstance(r, dict)]
    if len(want) != len(have):
        return [Finding("C1", "error", rel,
                        f"dev.rules drift: page has {len(have)} rule(s), {dev['registration']} has {len(want)}")]
    out = []
    for i, (w, h) in enumerate(zip(want, have)):
        for field in RULE_FIELDS:
            if w.get(field) != h.get(field):
                out.append(Finding("C1", "error", rel,
                                   f"dev.rules[{i}].{field} drift: page says {h.get(field)!r}, "
                                   f"{dev['registration']} says {w.get(field)!r}"))
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
        out += check_rules_drift(d.meta, rel, dev_root)
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


def _relations(d: Document) -> list[dict]:
    dev = _dev(d)
    rels = dev.get("relations") if dev else None
    return [r for r in rels if isinstance(r, dict) and isinstance(r.get("target"), str)] if isinstance(rels, list) else []


def check_l6(docs: list[Document], vault: Path, dev_root: Path) -> list[Finding]:
    """Typed relations (Round 100, B11). Targets are page stems (or repo paths for enforced_in)."""
    out: list[Finding] = []
    by_stem: dict[str, Document] = {d.path.stem: d for d in docs if d.meta is not None}
    supersedes: dict[str, list[str]] = {}
    for d in docs:
        rels = _relations(d)
        if not rels:
            continue
        rel = _rel(d.path, vault)
        resolvers = [r["target"] for r in rels if r.get("type") == "resolved_by"]
        for r in rels:
            t, target = r.get("type"), r["target"].strip()
            tgt = by_stem.get(target)
            if t == "supersedes":
                supersedes.setdefault(d.path.stem, []).append(target)
                if tgt is None:
                    out.append(Finding("L6", "error", rel, f"supersedes target not found: {target}"))
                elif (tgt.meta or {}).get("status") != "deprecated":
                    out.append(Finding("L6", "warning", rel, f"supersedes {target}, which is not `deprecated`"))
            elif t == "contradicts":
                if tgt is None:
                    out.append(Finding("L6", "error", rel, f"contradicts target not found: {target}"))
                ok = any((by_stem.get(x) or Document(Path(x), None, "")).meta and (by_stem[x].meta or {}).get("type") == "Ruling"
                         for x in resolvers if x in by_stem)
                if not ok:
                    out.append(Finding("L6", "error", rel, f"contradicts {target} without a `resolved_by` relation to an existing Ruling page"))
            elif t == "resolved_by":
                if tgt is None or (tgt.meta or {}).get("type") != "Ruling":
                    out.append(Finding("L6", "error", rel, f"resolved_by target is not an existing Ruling page: {target}"))
            elif t == "measured_by":
                if tgt is None or (tgt.meta or {}).get("type") != "Experiment":
                    out.append(Finding("L6", "error", rel, f"measured_by target is not an existing Experiment page: {target}"))
            elif t == "enforced_in":
                p = Path(target)
                if not (p if p.is_absolute() else dev_root / p).is_file():
                    out.append(Finding("L6", "error", rel, f"enforced_in target is not a file in the repository: {target}"))
            elif t == "depends_on":
                if tgt is None:
                    out.append(Finding("L6", "warning", rel, f"depends_on target not found: {target}"))
    # supersedes chains must be acyclic
    def reaches(start: str, node: str, seen: set[str]) -> bool:
        for nxt in supersedes.get(node, []):
            if nxt == start or (nxt not in seen and reaches(start, nxt, seen | {nxt})):
                return True
        return False
    for stem in supersedes:
        if reaches(stem, stem, {stem}):
            d = by_stem.get(stem)
            out.append(Finding("L6", "error", _rel(d.path, vault) if d else stem, f"supersedes chain is cyclic through {stem}"))
    return out


def check_l7(docs: list[Document], vault: Path) -> list[Finding]:
    """Staleness policy (Round 100, B14): a policed type must carry stale_after unless machine-maintained."""
    from .pages import STALENESS_DAYS, is_machine_maintained
    out: list[Finding] = []
    for d in docs:
        if d.meta is None or d.constitution:
            continue
        t = d.meta.get("type")
        if t in STALENESS_DAYS and "stale_after" not in d.meta and not is_machine_maintained(d.meta) \
                and d.meta.get("status") != "deprecated":
            out.append(Finding("L7", "warning", _rel(d.path, vault),
                               f"{t} page without stale_after (policy: {STALENESS_DAYS[t]} d)"))
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
    findings += check_l6(docs, vault, dev_root)
    findings += check_l7(docs, vault)
    findings += check_l8(docs, vault)
    findings += check_l9(docs, vault, dev_root)
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
        from .pages import load_pages, write_index
        write_index(vault, load_pages(vault))  # Ruling 98-5: fix-safe may also regenerate the root index
        append_log(vault, "Lint", f"--fix-safe deprecated {len(changed)} Market page(s) whose token left the newest drops: "
                   + ", ".join(f"[[{Path(p).stem}]]" for p in changed) + "; [index](index.md) rebuilt.", when=now)
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
