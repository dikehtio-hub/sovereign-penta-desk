"""Pages, ownership and the two OKF reserved files.

OWNERSHIP IS THE SAFETY PROPERTY. ``write_page`` is the only writer in the
package and it refuses (WriteRefused) any target outside
``obsidian_vault/{wiki,crm,journal,raw}/`` and the three owned files
``WIKI_SCHEMA.md``, ``index.md``, ``log.md``. Dashboards, ``Whales/``,
``Wallets/``, ``Trading_Taxes/``, drop folders and databases are therefore
unreachable from this code by construction, not by convention.

RESERVED FILES (OKF v0.2 sections 8-9, adopted verbatim):

    index.md    # Section Heading
                * [Title](path) - description
    log.md      ## YYYY-MM-DD           (newest first)
                * **Action**: description with [links](path).

``log.md`` is append-only and machine-written; ``append_log`` is the only
thing that touches it.

WINDOWS. A page whose ``dev.window`` contains now is a registration inside
its own window; writing it is refused (the standing constraint, enforced
mechanically instead of by memory).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from . import OWNED_DIRS, OWNED_FILES, RESERVED_FILES, GENERATED_BY
from .frontmatter import FrontmatterError, parse_iso8601, serialize, try_parse, validate

# Page-type vocabulary (WIKI_SCHEMA.md section 4). Order here is index.md order.
PAGE_TYPES: tuple[str, ...] = (
    "Desk",
    "Item",
    "Ruling",
    "Experiment",
    "Event",
    "Reaction Profile",
    "Regime",
    "Market",
    "Concept",
    "Source Summary",
    "Attested Computation",
    "Entity/Whale",
    "Entity/Sharp Trader",
    "Entity/Titan",
    "Entity/Sportsbook",
    "Entity/Market Maker",
    "Entity/Official",
    "Contact",
    "Journal Entry",
    "Debrief",
    "Lint Report",
    "Blueprint",
)

TYPE_FOLDERS: dict[str, str] = {
    "Desk": "wiki/desks",
    "Item": "wiki/items",
    "Ruling": "wiki/rulings",
    "Experiment": "wiki/experiments",
    "Event": "wiki/events",
    "Reaction Profile": "wiki/profiles",
    "Regime": "wiki/regimes",
    "Market": "wiki/markets",
    "Concept": "wiki/concepts",
    "Source Summary": "wiki/sources",
    "Attested Computation": "wiki/computations",
    "Entity/Whale": "crm/whales",
    "Entity/Sharp Trader": "crm/sharps",
    "Entity/Titan": "crm/titans",
    "Entity/Sportsbook": "crm/books",
    "Entity/Market Maker": "crm/makers",
    "Entity/Official": "crm/officials",
    "Contact": "crm/contacts",
    "Journal Entry": "journal",
    "Debrief": "journal/debriefs",
    "Lint Report": "wiki/lint",
    "Blueprint": "wiki/concepts",
}


class WriteRefused(PermissionError):
    """A write outside the owned folders, or inside a registration window."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Page:
    path: Path
    meta: dict[str, Any]
    body: str = ""
    error: str | None = None  # set by load_documents when the frontmatter failed

    @property
    def type(self) -> str | None:
        t = self.meta.get("type") if self.meta else None
        return t if isinstance(t, str) else None

    @property
    def title(self) -> str:
        t = self.meta.get("title") if self.meta else None
        return t if isinstance(t, str) and t else self.path.stem

    @property
    def description(self) -> str:
        d = self.meta.get("description") if self.meta else None
        return d if isinstance(d, str) else ""

    def rel(self, vault: Path) -> str:
        return self.path.resolve().relative_to(vault.resolve()).as_posix()


@dataclass
class Document:
    """Anything load_documents found: a page, or an unparsable file with `error`."""
    path: Path
    meta: dict[str, Any] | None
    body: str
    error: str | None = None
    links: set[str] = field(default_factory=set)
    constitution: bool = False  # WIKI_SCHEMA.md: linted for L1/L4/L5/C1, exempt from L2-listing and L3


# ---------------------------------------------------------------- ownership

def owned_targets(vault: Path) -> list[Path]:
    v = vault.resolve()
    return [v / d for d in OWNED_DIRS] + [v / f for f in OWNED_FILES]


def is_owned(path: Path, vault: Path) -> bool:
    p = Path(path).resolve()
    for target in owned_targets(vault):
        if p == target:
            return True
        try:
            p.relative_to(target)
            return True
        except ValueError:
            continue
    return False


def assert_owned(path: Path, vault: Path) -> None:
    if not is_owned(path, vault):
        raise WriteRefused(
            f"refusing to write {path}: outside the owned set "
            f"{', '.join(OWNED_DIRS)}/ and {', '.join(OWNED_FILES)} under {vault}"
        )


def in_window(meta: dict[str, Any] | None, now: datetime) -> bool:
    if not meta:
        return False
    dev = meta.get("dev")
    if not isinstance(dev, dict):
        return False
    w = dev.get("window")
    if not isinstance(w, dict) or "start" not in w or "end" not in w:
        return False
    try:
        return parse_iso8601(w["start"]) <= now <= parse_iso8601(w["end"])
    except ValueError:
        return False


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_page(page: Page, vault: Path, now: datetime | None = None) -> Path:
    """Validate, check ownership and window, then write. The package's only page writer."""
    now = now or now_utc()
    issues = validate(page.meta)
    if issues:
        raise FrontmatterError(f"{page.path.name}: " + "; ".join(issues))
    assert_owned(page.path, vault)
    if page.path.name in RESERVED_FILES:
        raise WriteRefused(f"{page.path.name} is reserved; use write_index / append_log")
    if in_window(page.meta, now):
        raise WriteRefused(f"{page.path.name}: inside its own registration window; not amended")
    _write_text(page.path, serialize(page.meta, page.body))
    return page.path


def write_owned_text(path: Path, text: str, vault: Path) -> Path:
    """Write a non-page owned file (WIKI_SCHEMA.md) with the same ownership guard."""
    assert_owned(path, vault)
    _write_text(path, text if text.endswith("\n") else text + "\n")
    return path


# ---------------------------------------------------------------- loading

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MDLINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def extract_links(body: str) -> set[str]:
    """Targets of [[wikilinks]] and [text](path) links, anchors stripped."""
    out: set[str] = set()
    for m in WIKILINK_RE.finditer(body):
        # inside a Markdown table the alias pipe is escaped: [[page\|alias]]
        out.add(m.group(1).strip().rstrip("\\").strip())
    for m in MDLINK_RE.finditer(body):
        target = m.group(1).split("#", 1)[0]
        if target and "://" not in target:
            out.add(target)
    return out


def iter_page_files(vault: Path) -> Iterable[Path]:
    for d in OWNED_DIRS:
        root = vault / d
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            if p.name in RESERVED_FILES:
                continue
            if any(part.startswith("_") for part in p.relative_to(root).parts[:-1]):
                continue  # _views/, _templates/: tooling folders, not pages (Round 101)
            yield p


def load_documents(vault: Path, include_constitution: bool = True) -> list[Document]:
    docs: list[Document] = []
    for p in iter_page_files(vault):
        text = p.read_text(encoding="utf-8")
        meta, body, err = try_parse(text)
        docs.append(Document(path=p, meta=meta, body=body, error=err, links=extract_links(body)))
    schema = vault / "WIKI_SCHEMA.md"
    if include_constitution and schema.is_file():
        text = schema.read_text(encoding="utf-8")
        meta, body, err = try_parse(text)
        docs.append(Document(path=schema, meta=meta, body=body, error=err, links=extract_links(body), constitution=True))
    return docs


def load_pages(vault: Path) -> list[Page]:
    """Parsable wiki pages only (the constitution is not a page). Lint uses load_documents."""
    return [Page(d.path, d.meta, d.body) for d in load_documents(vault) if d.meta is not None and not d.constitution]


def load_page(path: Path) -> Page | None:
    """One page by path, or None when it does not exist or has no parseable frontmatter."""
    if not path.is_file():
        return None
    meta, body, err = try_parse(path.read_text(encoding="utf-8"))
    return None if meta is None else Page(path, meta, body)


def iter_index_files(vault: Path) -> Iterable[Path]:
    """Every index.md below the owned folders (OKF: an index may appear in any directory)."""
    for d in OWNED_DIRS:
        root = vault / d
        if root.is_dir():
            yield from sorted(root.rglob("index.md"))


# ---------------------------------------------------------------- index.md

INDEX_HEADING_RE = re.compile(r"^# (.+)$")
INDEX_LINE_RE = re.compile(r"^\* \[(?P<title>[^\]]+)\]\((?P<path>[^)\s]+)\) - (?P<desc>.+)$")


@dataclass
class IndexEntry:
    section: str
    title: str
    path: str
    description: str


def build_index(pages: Iterable[Page], vault: Path) -> str:
    groups: dict[str, list[Page]] = {}
    for p in pages:
        groups.setdefault(p.type or "Untyped", []).append(p)
    order = [t for t in PAGE_TYPES if t in groups] + sorted(t for t in groups if t not in PAGE_TYPES)
    out: list[str] = []
    for t in order:
        out.append(f"# {t}")
        for p in sorted(groups[t], key=lambda x: x.rel(vault)):
            desc = safe_title(p.description) or "(no description)"
            out.append(f"* [{safe_title(p.title)}]({p.rel(vault)}) - {desc}")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def parse_index(text: str) -> tuple[list[IndexEntry], list[str]]:
    entries: list[IndexEntry] = []
    errors: list[str] = []
    section = ""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0] == "---":
        errors.append("index.md must not carry frontmatter (OKF reserved file)")
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if line.startswith("> "):
            continue  # a note under a heading (raw/index.md lists streams that are not on this machine this way)
        h = INDEX_HEADING_RE.match(line)
        if h:
            section = h.group(1).strip()
            continue
        m = INDEX_LINE_RE.match(line)
        if m:
            if not section:
                errors.append(f"index.md:{n}: entry before any section heading")
            entries.append(IndexEntry(section, m.group("title"), m.group("path"), m.group("desc")))
            continue
        errors.append(f"index.md:{n}: not a section heading, a '> note', or a '* [Title](path) - description' line")
    return entries, errors


def write_index(vault: Path, pages: Iterable[Page] | None = None) -> Path:
    pages = list(pages) if pages is not None else load_pages(vault)
    target = vault / "index.md"
    assert_owned(target, vault)
    _write_text(target, build_index(pages, vault))
    return target


# ---------------------------------------------------------------- log.md

LOG_HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})$")
LOG_BULLET_RE = re.compile(r"^\* \*\*(?P<action>[A-Z][A-Za-z -]*)\*\*: (?P<text>.+)$")


@dataclass
class LogEntry:
    date: str
    action: str
    text: str


def parse_log(text: str) -> tuple[list[LogEntry], list[str]]:
    entries: list[LogEntry] = []
    errors: list[str] = []
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0] == "---":
        errors.append("log.md must not carry frontmatter (OKF reserved file)")
    date = ""
    seen_dates: list[str] = []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        h = LOG_HEADING_RE.match(line)
        if h:
            date = h.group(1)
            if seen_dates and date >= seen_dates[-1]:
                errors.append(f"log.md:{n}: dates must run newest first ({date} after {seen_dates[-1]})")
            seen_dates.append(date)
            continue
        m = LOG_BULLET_RE.match(line)
        if m:
            if not date:
                errors.append(f"log.md:{n}: bullet before any '## YYYY-MM-DD' heading")
            entries.append(LogEntry(date, m.group("action"), m.group("text")))
            continue
        errors.append(f"log.md:{n}: not a date heading or '* **Action**: text' bullet")
    return entries, errors


def append_log(vault: Path, action: str, text: str, when: datetime | None = None) -> Path:
    """Append one bullet under today's heading (created at the top if absent)."""
    when = when or now_utc()
    day = when.astimezone(timezone.utc).strftime("%Y-%m-%d")
    target = vault / "log.md"
    assert_owned(target, vault)
    existing = target.read_text(encoding="utf-8").replace("\r\n", "\n") if target.exists() else ""
    bullet = f"* **{action}**: {text}"
    lines = existing.split("\n") if existing else []
    heading = f"## {day}"
    if heading in lines:
        i = lines.index(heading) + 1
        while i < len(lines) and lines[i].startswith("* "):
            i += 1
        lines.insert(i, bullet)
    else:
        block = [heading, bullet, ""]
        lines = block + lines if lines else block
    out = "\n".join(lines).rstrip("\n") + "\n"
    _write_text(target, out)
    return target


# ---------------------------------------------------------------- constructors

# Round 100 (B14): per-type staleness policy in days. Absent = never stale (historical facts).
STALENESS_DAYS: dict[str, int] = {"Ruling": 180, "Concept": 90}


def default_stale_after(type_: str, at: datetime) -> str | None:
    days = STALENESS_DAYS.get(type_)
    return iso(at + timedelta(days=days)) if days else None


def is_machine_maintained(meta: dict[str, Any]) -> bool:
    """Registers and history pages are regenerated wholesale; the staleness policy does not apply to them."""
    dev = meta.get("dev") or {}
    return isinstance(dev, dict) and ("register_for" in dev or "history" in dev)


def safe_title(text: str) -> str:
    """A title that survives `* [Title](path) - desc` and `[[stem\\|Title]]`: no brackets, pipes or newlines."""
    return re.sub(r"\s+", " ", str(text).replace("[", "(").replace("]", ")").replace("|", "/")).strip()


def carry_human_fields(existing: Page | None, meta: dict[str, Any]) -> None:
    """Re-ingest never drops what a human or a ratification wrote: verified, stale_after, a status past
    draft, and dev.ratified_by (Round 99)."""
    if existing is None:
        return
    for key in ("verified", "stale_after"):
        if key in existing.meta:
            meta[key] = existing.meta[key]
    if existing.meta.get("status") not in (None, "draft"):
        meta["status"] = existing.meta["status"]
    old_dev = existing.meta.get("dev") or {}
    if isinstance(old_dev, dict) and "ratified_by" in old_dev:
        meta.setdefault("dev", {})["ratified_by"] = old_dev["ratified_by"]


def make_meta(
    type_: str,
    title: str,
    description: str,
    *,
    tags: list[str] | None = None,
    generated_by: str = GENERATED_BY,
    at: datetime | None = None,
    status: str = "draft",
    sources: list[dict[str, Any]] | None = None,
    dev: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """An ordered OKF v0.2 frontmatter mapping; `type` first, `dev` last."""
    meta: dict[str, Any] = {
        "type": type_,
        "title": title,
        "description": description,
        "tags": list(tags or []),
        "generated": {"by": generated_by, "at": iso(at or now_utc())},
        "status": status,
    }
    meta.update(extra)
    if sources:
        meta["sources"] = sources
    if dev:
        meta["dev"] = dev
    return meta


def page_path(vault: Path, type_: str, filename: str) -> Path:
    folder = TYPE_FOLDERS.get(type_)
    if folder is None:
        raise ValueError(f"no folder for page type {type_!r}")
    if not filename.endswith(".md"):
        filename += ".md"
    return vault / folder / filename
