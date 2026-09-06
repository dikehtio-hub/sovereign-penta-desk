"""Register pages: one machine-maintained Concept page per compiled type.

Every adapter writes pages that nothing else links to yet (a registration, a
computation, an event, a market). The register for that type lists them all,
so lint L3 never sees an orphan, and every Desk page links every register, so
the graph has one hop from a desk to anything compiled. Hand edits to a
register are overwritten on the next run; that is what "machine-maintained"
means in WIKI_SCHEMA.md s.4.
"""
from __future__ import annotations

from datetime import datetime

from . import GENERATED_BY
from .pages import Page, load_pages, make_meta, page_path, safe_title

# type -> (stem, title, description, columns shown after the page link)
SPECS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "Experiment": ("experiments_register", "Experiments register",
                   "Every Experiment page: pre-registrations (draft until a verdict lands), archived controls, and verdicts as measured.",
                   ("kind",)),
    "Ruling": ("rulings_register", "Rulings register",
               "Every Ruling page: the R-series, and every Directive, Ratification and numbered Ruling extracted from the handoff log.",
               ("kind", "round")),
    "Attested Computation": ("computations_register", "Computations register",
                             "Every shell twin and knowledge CLI filed as an OKF Attested Computation (declarative only, R95-C).",
                             ("runtime", "kind")),
    "Event": ("events_register", "Events register",
              "Every Event page: scheduled prints with their windows, tax deadlines, and recorded events.",
              ("kind", "release_utc")),
    "Market": ("markets_register", "Markets register",
               "Every Market page the wiki is bound to; lint C2 warns when a token leaves the drops and --fix-safe deprecates it.",
               ("family",)),
    # "Entity" is a prefix: every Entity/* type (titans, whales, sharp traders, sportsbooks, ...) lands in one CRM register.
    "Entity": ("crm_register", "CRM register",
               "Every counterparty page under crm/: titans (both venues), Hyperliquid whales, Polymarket sharps, sportsbooks. Judgement is human; evidence is appended.",
               ("type", "desk")),
    "Journal Entry": ("journal_register", "Journal register",
                      "Every trading-day journal page: paper executions, the calibration ledger, the debrief. Plan and Open sections are human.",
                      ("date", "receipts", "predictions_n")),
    "Digest": ("digests_register", "Digests register",
               "Every round of the sovereign work chain as its own page, compiled from AGENTS.md. The log stays the record; a digest loses to it wherever they disagree.",
               ("round", "date")),
    # "Thesis" selects Concept pages compiled from module docstrings (dev.kind == thesis).
    "Thesis": ("theses_register", "Theses register",
               "Every module thesis compiled from a desk docstring; each heading is pinned to its source so a silent deletion is a lint C1 finding.",
               ("module", "desk")),
}


def matches(page_type: str | None, type_: str, dev: dict | None = None) -> bool:
    if page_type is None:
        return False
    if type_ == "Entity":
        return page_type.startswith("Entity/")
    if type_ == "Thesis":
        return page_type == "Concept" and isinstance(dev, dict) and dev.get("kind") == "thesis"
    return page_type == type_

REGISTER_STEMS = tuple(spec[0] for spec in SPECS.values())


def register_stem(type_: str) -> str:
    return SPECS[type_][0]


def _cell(page: Page, col: str) -> str:
    dev = page.meta.get("dev") or {}
    v = page.meta.get(col, dev.get(col, "-"))
    return "-" if v in (None, "") else str(v)


def update_register(vault, type_: str, *, at: datetime, by: str = GENERATED_BY) -> Page:
    stem, title, description, cols = SPECS[type_]
    pages = sorted((p for p in load_pages(vault) if matches(p.type, type_, p.meta.get("dev"))), key=lambda p: p.path.name)
    head = "| Page | " + " | ".join(c.replace("_", " ") for c in cols) + " | Status | Generated |"
    sep = "|---|" + "---|" * len(cols) + "---|---|"
    lines = [f"# {title}", "", f"> {description}", "> Maintained by the knowledge layer; hand edits are overwritten.", "", head, sep]
    for p in pages:
        gen = (p.meta.get("generated") or {}).get("at", "")
        cells = " | ".join(_cell(p, c) for c in cols)
        lines.append(f"| [[{p.path.stem}\\|{safe_title(p.title)}]] | {cells} | {p.meta.get('status', 'stable')} | {gen} |")
    lines += ["", f"{len(pages)} page(s).", "", "## Related", "", "- [[WIKI_SCHEMA|Constitution]] s.4 (registers)", ""]
    meta = make_meta("Concept", title, f"{description} {len(pages)} page(s) today.",
                     tags=["concept", "register", type_.lower().replace(" ", "-").replace("/", "-")],
                     generated_by=by, at=at, status="draft",
                     dev={"register_for": type_, "count": len(pages), "pages": [p.path.stem for p in pages]})
    return Page(page_path(vault, "Concept", stem), meta, "\n".join(lines))
