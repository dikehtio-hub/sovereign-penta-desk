"""Seed the wiki from what the repo already records (Round 96, Phase 1).

    python -m knowledge.seed [--vault DIR] [--dev-root DIR] [--registry FILE]
                             [--force] [--dry-run] [--at ISO8601]

Compiles, read-only from its sources:
  * 20 Item pages from the Top 20 registry in MASTER_COMMAND_LIST.txt
    (the `[x] ITEM N: TITLE` blocks and their `- Key:` fields);
  * 5 Desk pages from the desk table this package carries (the Round 95
    audit), each listing the items and rulings that belong to it;
  * the Rulings catalogue R1-R6 plus R95 (Ratification R95-A..G). R2, R4
    and R6 have recorded text (commits 49f85f8, da48cf3, fe40a1a). R5 is
    referenced by cross_market/amm_rewards.py as the ruling that will record
    the pool rate and has not been issued. R1 and R3 have NO text anywhere
    in the repo or its history at ec98342; their pages say so, so the
    numbering has a home and lint can see the hole.
Then rebuilds index.md and appends one line to log.md.

Existing pages are skipped unless --force: a seed must never clobber a page
a human or a later ingest has improved. Every write goes through
pages.write_page (ownership + window guard). HALT.flag -> exit 3.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import DEV_ROOT, EXIT_HALT, EXIT_OK, GENERATED_BY, VAULT, halted
from .frontmatter import parse_iso8601
from .pages import Page, append_log, iso, load_pages, make_meta, now_utc, page_path, write_index, write_page

REGISTRY_NAME = "MASTER_COMMAND_LIST.txt"
REGISTRY_SOURCE_ID = "top20-registry"
ANTIGRAVITY = "antigravity/architect"   # canonical actor string for Antigravity (WIKI_SCHEMA.md s.2)

# ---------------------------------------------------------------- registry parsing

ITEM_HEADER_RE = re.compile(r"^\[( |x)\] ITEM (\d+): (.+?)\s*$")
TIER_RE = re.compile(r"^TIER (\d+): (.+?)\s*$")
FIELD_RE = re.compile(r"^  - ([A-Za-z][A-Za-z ]*?):\s*(.*)$")
SEPARATOR_RE = re.compile(r"^[-=]{10,}\s*$")


@dataclass
class ItemSpec:
    number: int
    title: str
    checked: bool
    tier: int = 0
    tier_name: str = ""
    fields: dict[str, list[str]] = field(default_factory=dict)

    def text(self, key: str) -> str:
        return "\n".join(self.fields.get(key, [])).strip()

    def lines(self, key: str) -> list[str]:
        return [l.strip() for l in self.fields.get(key, []) if l.strip()]


def parse_registry(text: str) -> list[ItemSpec]:
    items: list[ItemSpec] = []
    tier, tier_name = 0, ""
    cur: ItemSpec | None = None
    key: str | None = None
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        t = TIER_RE.match(line)
        if t:
            tier, tier_name = int(t.group(1)), t.group(2)
            cur, key = None, None
            continue
        h = ITEM_HEADER_RE.match(line)
        if h:
            cur = ItemSpec(int(h.group(2)), h.group(3), h.group(1) == "x", tier, tier_name)
            items.append(cur)
            key = None
            continue
        if cur is None:
            continue
        if not line.strip() or SEPARATOR_RE.match(line):
            continue
        f = FIELD_RE.match(line)
        if f:
            key = f.group(1).strip()
            cur.fields.setdefault(key, [])
            if f.group(2):
                cur.fields[key].append(f.group(2))
            continue
        if line.startswith("    ") and key is not None:
            cur.fields[key].append(line.strip())
            continue
        # a top-level line that is not a field: the registry block is over
        cur, key = None, None
    return items


ACRONYMS = {"UI", "CLV", "C2", "AMM", "CME", "IRC", "API", "L2", "HL", "PM", "DEX", "EV", "NQ", "ES", "GC",
            "CL", "BTC", "CLOB", "P&L", "PNL", "OI"}


def slugify(title: str, max_words: int = 6) -> str:
    """Registry titles are ALL CAPS, so every word is title-cased except known acronyms.

    Anything that is not a letter or digit is a separator: `->`, `&`, `/`, `(`, `:`
    would otherwise reach the filename (Item 18's title has `->`, invalid on Windows).
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", title)
    words = [w for w in re.split(r"\s+", cleaned) if w]
    words = [w if w.upper() in ACRONYMS else w.capitalize() for w in words][:max_words]
    slug = "_".join(words)
    if not re.fullmatch(r"[A-Za-z0-9_]+", slug):  # pragma: no cover - guarded by the regex above
        raise ValueError(f"slug has invalid characters: {slug!r}")
    return slug


# ---------------------------------------------------------------- desks

@dataclass(frozen=True)
class DeskSpec:
    number: int
    name: str
    slug: str
    description: str
    domain: str
    code_roots: tuple[str, ...]
    vault_notes: tuple[str, ...]
    raw_streams: tuple[str, ...]
    asserts: tuple[dict[str, str], ...] = ()
    parameters: tuple[dict[str, Any], ...] = ()


DESKS: tuple[DeskSpec, ...] = (
    DeskSpec(
        1, "HyperLiquid Monarch", "HyperLiquid_Monarch",
        "Perp DEX desk: delta-neutral funding harvester, whale cascade sweeper, L2 order-book sampler, "
        "liquidation engine and the collector that feeds a 4.9 GB snapshot warehouse.",
        "Hyperliquid perps and HIP-3 TradFi",
        ("HyperLiquid/HL_Monarch",),
        ("HyperLiquid_Monarch.md", "Trading_Terminal.md", "Bot_Control.md", "Bot_Config.md", "Whales/"),
        ("HyperLiquid/HL_Monarch/data/hyperliquid_data.db (13 tables)",
         "HyperLiquid/HL_Monarch/data/collector_service.jsonl",
         "HyperLiquid/HL_Monarch/data/experiments/*.meta.json"),
        asserts=({"file": "HyperLiquid/HL_Monarch/execution/basis_harvester.py", "pattern": r"class |def ",
                  "claim": "the basis harvester module is at its registered path"},),
    ),
    DeskSpec(
        2, "Sports Desk", "Sports_Desk",
        "Sportsbook desk: multi-book odds ingestion, Shin/Power devigging to fair value, after-tax edge hurdle, "
        "execution CLV, stale-quote guard and the Polymarket drop watcher that feeds Item 18.",
        "Sportsbooks and Polymarket sports questions",
        ("Sports_Desk",),
        ("Sports_Desk.md",),
        ("Sports_Desk/data/sports_market.db (8 tables)",
         "Sports_Desk/data/polymarket_drops/ (stamped macro + sports JSON)",
         "Sports_Desk/data/odds_drops/, results_drops/"),
        asserts=({"file": "Sports_Desk/engine/fair_value.py", "pattern": r"def ",
                  "claim": "the pure devigging engine is at its registered path"},),
        parameters=(
            {"name": "kelly_fraction", "value": 0.25, "file": "Sports_Desk/engine/fair_value.py",
             "pattern": r"def kelly_fraction\(fair_prob: float, offered_odds: float, fraction: float = ([0-9.]+)\)"},
            {"name": "fee_rate", "value": 0.0, "file": "cross_market/ingestors/polymarket_fetcher.py",
             "pattern": r"fee_rate: float = ([0-9.]+),"},
        ),
    ),
    DeskSpec(
        3, "Cross-Market Desk", "Cross_Market_Desk",
        "Cross-venue desk: Polymarket vs sportsbook dutching arb, Titan correlator and lead-lag research, "
        "latency sniper (paper), AMM rewards simulator (paper), risk-of-ruin simulator, C2 bot.",
        "Polymarket, Hyperliquid and sportsbooks together",
        ("cross_market", "Polymarket/Polymarket_Monarch"),
        ("Cross_Market_Arb.md", "Cross_Market_Titans.md", "Risk_Sentinel.md", "Polymarket_Monarch.md", "Wallets/"),
        ("cross_market/data/clob_books/ (CLOB stamps)",
         "cross_market/experiments/*.json (pre-registrations)",
         "cross_market/data/paper_receipts/",
         "cross_market/titan_identities_cache.json",
         "Polymarket/Polymarket_Monarch/data/polymarket_whales.db"),
        asserts=({"file": "cross_market/latency_sniper.py", "pattern": r"def record_loop",
                  "claim": "Ruling R2's recording loop exists"},),
        parameters=(
            {"name": "lead_lag_min_abs_corr", "value": 0.2,
             "file": "cross_market/experiments/lead_lag_tier2b.meta.json",
             "pattern": r'"min_abs_corr":\s*([0-9.]+)'},
            {"name": "lead_lag_latency_minutes_crypto", "value": 5.0,
             "file": "cross_market/experiments/lead_lag_tier2b.meta.json",
             "pattern": r'"latency_minutes_crypto":\s*([0-9.]+)'},
            {"name": "kelly_fraction", "value": 0.25, "file": "cross_market/latency_sniper.py",
             "pattern": r"^KELLY_FRACTION = ([0-9.]+)"},
            {"name": "confidence_floor", "value": 0.99, "file": "cross_market/latency_sniper.py",
             "pattern": r"^MIN_CONFIDENCE = ([0-9.]+)"},
            {"name": "fee_rate", "value": 0.0, "file": "cross_market/latency_sniper.py",
             "pattern": r"^\s+fee_rate: float = ([0-9.]+)$"},
        ),
    ),
    DeskSpec(
        4, "Quant Trading Lab", "Quant_Trading_Lab",
        "CME futures desk: nine strategy stacks, ICT session clocks, Risk Sentinel invariants, walk-forward "
        "and grid-search research over stitched continuous contracts; its own git repository.",
        "CME futures (/NQ /ES /GC /CL) and BTC perps",
        ("quant_trading_lab",),
        ("Quant_Trading_Lab.md",),
        ("quant_trading_lab/data/continuous/*.csv", "quant_trading_lab/state/runtime_state.json"),
        parameters=(
            {"name": "daily_drawdown_killswitch_usd", "value": "3,500.00",
             "file": "quant_trading_lab/CLAUDE.md",
             "pattern": r"Hard Daily Drawdown Killswitch: \$([0-9,\.]+)"},
            {"name": "single_trade_risk_pct", "value": 1.0,
             "file": "quant_trading_lab/CLAUDE.md",
             "pattern": r"Single Trade Risk Budget: ([0-9.]+)%"},
        ),
    ),
    DeskSpec(
        5, "Tax Reserve Agent", "Tax_Reserve_Agent",
        "The accountant every desk asks before sizing: lot engine, IRC 1256 60/40, IRC 165(d) gambling, "
        "NJ apportionment, tax escrow and the safe-bankroll gating hook.",
        "Tax escrow and bankroll gating across all desks",
        ("Tax_Reserve_Agent",),
        ("Trading_Taxes/",),
        ("Tax_Reserve_Agent/data/tax_ledger.db", "Tax_Reserve_Agent/data/imports/"),
        asserts=({"file": "Tax_Reserve_Agent/interfaces/monarch_hook.py", "pattern": r"class MonarchBankrollHook",
                  "claim": "the gating hook class exists"},),
        parameters=(
            {"name": "federal_ordinary_rate", "value": 0.24,
             "file": "Tax_Reserve_Agent/config.yaml", "pattern": r"^\s*federal_ordinary_rate:\s*([0-9.]+)"},
            {"name": "state_tax_rate_nj", "value": 0.0637,
             "file": "Tax_Reserve_Agent/config.yaml", "pattern": r"^\s*state_tax_rate:\s*([0-9.]+)"},
            {"name": "kelly_fraction", "value": 0.25, "file": "Tax_Reserve_Agent/interfaces/monarch_hook.py",
             "pattern": r"^KELLY_FRACTION = ([0-9.]+)"},
        ),
    ),
)
# `kelly_fraction` is declared on Desks 2, 3 and 5 on purpose: lint C3 checks the three files agree.

# Items whose registry block carries no Primary Code line.
ITEM_DESK_FALLBACK = {7: 2, 10: 3, 11: 4, 12: 3, 13: 3}

_PREFIX_TO_DESK = (
    ("HyperLiquid/", 1), ("Sports_Desk/", 2), ("cross_market/", 3), ("Polymarket/", 3),
    ("quant_trading_lab/", 4), ("Tax_Reserve_Agent/", 5),
)


def desk_for_item(item: ItemSpec) -> int:
    for line in item.lines("Primary Code"):
        for prefix, desk in _PREFIX_TO_DESK:
            if line.startswith(prefix):
                return desk
    return ITEM_DESK_FALLBACK.get(item.number, 3)


def desk_filename(d: DeskSpec) -> str:
    return f"Desk_{d.number:02d}_{d.slug}.md"


# Round 97 ruling 11: hand-curated slugs where six title words truncate awkwardly.
SLUG_OVERRIDES: dict[int, str] = {
    4: "Section_1256_Futures_Tax_60_40",
    19: "Multi_Desk_Monte_Carlo_Risk_Of_Ruin",
}


def item_filename(item: ItemSpec) -> str:
    return f"Item_{item.number:02d}_{SLUG_OVERRIDES.get(item.number) or slugify(item.title)}.md"


def registry_mtime(registry: Path) -> datetime:
    """Round 97 ruling 12: the default generated.at is the registry's mtime, so --force is byte-idempotent."""
    return datetime.fromtimestamp(registry.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)


# ---------------------------------------------------------------- rulings

@dataclass(frozen=True)
class RulingSpec:
    rid: str
    title: str
    description: str
    body: str
    desk: int
    items: tuple[int, ...]
    round: int | None
    commit: str | None
    ratified: bool                  # True -> verified by Antigravity
    asserts: tuple[dict[str, str], ...] = ()
    status: str = "stable"
    ratified_at: str | None = None  # the ratifying commit's instant (Round 97 ruling 6c), else the seed time


RULINGS: tuple[RulingSpec, ...] = (
    RulingSpec(
        "R1", "R1 - never issued (deprecated placeholder)",
        "Part of the R1-R6 numbering but never issued: no ruling text exists in AGENTS.md, COMMANDS.txt, any "
        "module docstring or any commit message. Confirmed by Antigravity in Round 97; kept so the numbering has a home.",
        "The R1-R6 numbering is used across Rounds 88-93 (R2, R4, R6 are cited by commit). A whole-word search "
        "of the handoff log, the command references, the module docstrings and `git log` at ec98342 found no "
        "definition of R1, and Antigravity confirmed in Round 97 that none was issued. This page is a deprecated "
        "historical placeholder: nothing cites it, and nothing should.",
        3, (12, 13), 97, None, False, status="deprecated",
    ),
    RulingSpec(
        "R2", "R2 - record the CLOB around a scheduled print",
        "One read-only GET per token per interval from T-2 to T+5 around a scheduled release, so the seconds "
        "a resting book survives after the print can be measured before anything is built on it.",
        "Implemented in Round 93 as `latency_sniper.record_loop()` and the CLI `--record-loop --tokens T[,..] "
        "--interval 1 --duration 420 [--books DIR]`: sleeps interval minus fetch time, stops at the duration, on "
        "HALT.flag (exit 3) or Ctrl-C; an HTTP 429 is counted and answered with a growing pause (5 s x n, max 30 s). "
        "The first drill is the 2026-09-16 FOMC statement (Windows task Monarch_FOMC_Drill, 13:58 EDT). Its stamps "
        "are the raw layer for the first Reaction Profile pages.",
        3, (12,), 93, "49f85f8", True,
        asserts=({"file": "cross_market/latency_sniper.py", "pattern": r"def record_loop",
                  "claim": "the recording loop exists"},),
        ratified_at="2026-09-05T18:13:11Z",
    ),
    RulingSpec(
        "R3", "R3 - never issued (deprecated placeholder)",
        "Part of the R1-R6 numbering but never issued: no ruling text exists anywhere in the repository. "
        "Confirmed by Antigravity in Round 97; kept so the numbering has a home.",
        "As for R1: the number is part of the series but no definition exists, and Antigravity confirmed in Round 97 "
        "that none was issued. Deprecated historical placeholder.",
        3, (12, 13), 97, None, False, status="deprecated",
    ),
    RulingSpec(
        "R4", "R4 - neg_risk books skip the NO side",
        "On a negative-risk Polymarket book only the winning outcome's YES asks are lifted; a NO outcome on a "
        "neg_risk book is deferred to Phase 2 and never traded by the sniper.",
        "Implemented in Round 88: `Book` carries `neg_risk` from the live stamp's field; `evaluate()` skips a NO "
        "outcome on a neg_risk book with the reason \"NO side deferred to Phase 2 (Ruling R4)\" and still lifts the "
        "winning outcome's YES asks. A standalone market's NO side is unchanged. The depth report and the survival "
        "curve inherit the rule. Enforced in code, not in prose.",
        3, (12,), 88, "da48cf3", True,
        asserts=({"file": "cross_market/latency_sniper.py", "pattern": r"neg_risk",
                  "claim": "the neg_risk field is read and acted on"},),
        ratified_at="2026-09-05T17:15:05Z",
    ),
    RulingSpec(
        "R5", "R5 - record the rewards pool rate (pending)",
        "The AMM rewards estimator treats the daily pool rate as an ASSUMED input until a ruling records it from "
        "live markets. That ruling has not been issued; the module names it as the one input left.",
        "`cross_market/amm_rewards.py` prints \"the pool rate is the only input left (Ruling R5)\" and refuses "
        "`--replay-books` without `--pool`. Item 13 Phase 2 (record rewards fields additively in the fetcher, "
        "post-maiden) is the prerequisite. This page turns `stable` when the ruling is issued and the recording "
        "exists.",
        3, (13,), None, None, False, status="draft",
        asserts=({"file": "cross_market/amm_rewards.py", "pattern": r"Ruling R5",
                  "claim": "the module still names R5 as the pending ruling"},),
    ),
    RulingSpec(
        "R6", "R6 - competitor Q is measured from recorded books",
        "The programme score of every resting level inside the rewards window is computed from a recorded CLOB "
        "stamp; competitor liquidity is a measurement, not an input. The pool rate stays the one input (R5).",
        "Implemented in Round 91: `amm_rewards.book_q()` scores each level per side (Q_min by the band rule); "
        "`replay_rewards()` runs it over a stamps folder and adds the share a hypothetical two-sided quote would earn. "
        "First measurement (Fed \"no change in Sept 2026\", one stamp at 16:59Z): Q_min 28,828 over 6 levels in the "
        "3-cent window; a 100-share quote at +/-1 cent earns a 0.09 % share. Retail-sized quoting on a heavily-made "
        "market is a rounding error of the pool, and the module says so rather than an APY.",
        3, (13,), 91, "fe40a1a", True,
        asserts=({"file": "cross_market/amm_rewards.py", "pattern": r"def book_q",
                  "claim": "book_q exists"},),
        ratified_at="2026-09-05T17:48:20Z",
    ),
    RulingSpec(
        "R95", "R95 - Ratification of the knowledge layer (R95-A to R95-G)",
        "Antigravity's seven rulings on the Round 95 blueprint: placement, constitution, OKF depth, verification "
        "actor, git tracking (deferred), journal debrief scope and module numbering.",
        "- **R95-A Placement**: wiki/, crm/, journal/, raw/ live INSIDE obsidian_vault/. Exporters keep exclusive "
        "ownership of the root dashboards, Whales/, Wallets/ and Trading_Taxes/. Raw desk databases stay federated "
        "in place.\n"
        "- **R95-B Constitution**: obsidian_vault/WIKI_SCHEMA.md is authoritative; AGENTS.md remains the handoff log.\n"
        "- **R95-C OKF depth**: adopt OKF v0.2 frontmatter and the reserved index.md / log.md formats. Attested "
        "Computation metadata stays declarative; no live attester daemon.\n"
        "- **R95-D Verification actor**: `verified.by` Antigravity is reserved for Antigravity-ratified Rulings, "
        "Directives and parameter pages.\n"
        "- **R95-E Git tracking**: DEFERRED to Phase 4; dashboards stay tracked to protect the Item 18 maiden-run "
        "marker block in Cross_Market_Titans.md.\n"
        "- **R95-F Journal debrief**: paper receipts only (paper:1); checks against the Tax Reserve Agent after-tax "
        "hurdle and Risk Sentinel drawdowns.\n"
        "- **R95-G Module 23**: the knowledge/ package is Master Module 23.",
        3, tuple(range(1, 21)), 96, "ea63111", True,
        ratified_at="2026-09-05T20:10:31Z",
    ),
)


def ruling_filename(r: RulingSpec) -> str:
    num = r.rid[1:]
    return f"Ruling_R{int(num):02d}.md" if int(num) < 10 else f"Ruling_R{num}.md"


# ---------------------------------------------------------------- page builders

def _existing(dev_root: Path, entries: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Only emit asserts/parameters whose file exists under dev_root (a test fixture has few)."""
    return [dict(e) for e in entries if (dev_root / e["file"]).is_file()]


def _registry_source(dev_root: Path, registry: Path) -> dict[str, Any]:
    try:
        rel = registry.resolve().relative_to(dev_root.resolve()).as_posix()
    except ValueError:
        rel = registry.as_posix()
    return {"id": REGISTRY_SOURCE_ID, "resource": rel,
            "title": "Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)",
            "author": "human:operator"}


def build_item_page(item: ItemSpec, desks: dict[int, DeskSpec], vault: Path, dev_root: Path,
                    registry: Path, at: datetime, by: str) -> Page:
    desk = desks[desk_for_item(item)]
    what = item.text("What It Does") or "(the registry block carries no description)"
    status_line = item.text("Status") or ("Deployed (registry checkbox [x])" if item.checked else "Roadmap")
    code = item.lines("Primary Code")
    db = item.text("Database")
    activate = item.lines("How to Activate")
    tests = item.lines("Test Command")
    desk_link = f"[[{desk_filename(desk)[:-3]}|Desk {desk.number}: {desk.name}]]"

    body = [f"# Item {item.number}: {item.title.title()}", "",
            f"> Tier {item.tier}: {item.tier_name.title()} · {'deployed' if item.checked else 'roadmap'} · {desk_link}", "",
            "## What it does", "", what, ""]
    if code or db:
        body += ["## Where it lives", ""]
        body += [f"- `{c}`" for c in code]
        if db:
            body.append(f"- database: `{db}`")
        body.append("")
    if activate:
        body += ["## How to activate", "", "```", *activate, "```", ""]
    if tests:
        body += ["## Test", "", "```", *tests, "```", ""]
    body += ["## Status", "", status_line, ""]
    if item.text("Added"):
        body += [f"Added: {item.text('Added')}", ""]
    rulings = [r for r in RULINGS if item.number in r.items and r.rid != "R95"]
    body += ["## Related", "", f"- {desk_link}"]
    body += [f"- [[{ruling_filename(r)[:-3]}|{r.title}]]" for r in rulings]
    body.append("")

    # Round 97 ruling 10: a file-exists check is `dev.requires_files`, not a "." regex.
    requires = [c for c in code if (dev_root / c).is_file()]
    dev: dict[str, Any] = {"desk": desk.number, "item": item.number, "tier": item.tier,
                           "registry_checked": item.checked}
    if requires:
        dev["requires_files"] = requires
    meta = make_meta(
        "Item", f"Item {item.number}: {item.title.title()}",
        (what.split(". ")[0].rstrip(".") + ".")[:300],
        tags=["item", f"desk-{desk.number}", f"tier-{item.tier}", "deployed" if item.checked else "roadmap"],
        generated_by=by, at=at, sources=[_registry_source(dev_root, registry)], dev=dev,
    )
    return Page(page_path(vault, "Item", item_filename(item)), meta, "\n".join(body))


def build_desk_page(d: DeskSpec, items: list[ItemSpec], vault: Path, dev_root: Path,
                    registry: Path, at: datetime, by: str) -> Page:
    mine = sorted((i for i in items if desk_for_item(i) == d.number), key=lambda i: i.number)
    rulings = [r for r in RULINGS if r.desk == d.number or r.rid == "R95"]
    body = [f"# Desk {d.number}: {d.name}", "", d.description, "", f"**Domain**: {d.domain}", "",
            "## Code roots", "", *[f"- `{c}`" for c in d.code_roots], "",
            "## Raw streams (federated, read-only)", "", *[f"- `{s}`" for s in d.raw_streams], "",
            "## Vault surface (exporter-owned, never written by the knowledge layer)", "",
            *[f"- `{n}`" for n in d.vault_notes], "",
            "## Items", ""]
    body += [f"- [[{item_filename(i)[:-3]}|Item {i.number}: {i.title.title()}]]"
             f" · {'deployed' if i.checked else 'roadmap'}" for i in mine] or ["- (none in the registry)"]
    body += ["", "## Rulings", ""]
    body += [f"- [[{ruling_filename(r)[:-3]}|{r.title}]]" for r in rulings]
    body += ["", "## Registers (machine-maintained)", "",
             "- [[experiments_register|Experiments register]]", "- [[rulings_register|Rulings register]]",
             "- [[computations_register|Computations register]]", "- [[events_register|Events register]]",
             "- [[markets_register|Markets register]]"]
    if d.number == 3:
        body += ["", "## Compiled pages (Phase 2 adapters)", "",
                 "- [[experiments_register|Experiments register]] - pre-registrations and verdicts",
                 "- [[btc_macro_regime|BTC macro regime]] - lead-lag classification history",
                 "- [[latency_decay|Latency decay across events]] - post-print depth survival per event"]
    body += ["", "## Other desks", ""]
    body += [f"- [[{desk_filename(o)[:-3]}|Desk {o.number}: {o.name}]]" for o in DESKS if o.number != d.number]
    body += ["", "## Related", "", "- [[Monarch_Hub|Monarch Hub]] (exporter-owned dashboard index)", ""]
    dev: dict[str, Any] = {"desk": d.number}
    a = _existing(dev_root, d.asserts)
    p = _existing(dev_root, d.parameters)
    if a:
        dev["asserts"] = a
    if p:
        dev["parameters"] = p
    meta = make_meta("Desk", f"Desk {d.number}: {d.name}", d.description,
                     tags=["desk", f"desk-{d.number}"], generated_by=by, at=at,
                     sources=[_registry_source(dev_root, registry),
                              {"id": "round-95-blueprint", "resource": "LLM_WIKI_BLUEPRINT.md",
                               "title": "Round 95 five-desk audit", "author": GENERATED_BY}],
                     dev=dev)
    return Page(page_path(vault, "Desk", desk_filename(d)), meta, "\n".join(body))


def build_ruling_page(r: RulingSpec, desks: dict[int, DeskSpec], items: list[ItemSpec], vault: Path,
                      dev_root: Path, at: datetime, by: str) -> Page:
    by_num = {i.number: i for i in items}
    desk = desks[r.desk]
    body = [f"# Ruling {r.title}", "", r.body, "", "## Applies to", "",
            f"- [[{desk_filename(desk)[:-3]}|Desk {desk.number}: {desk.name}]]"]
    for n in r.items:
        if n in by_num and r.rid != "R95":
            body.append(f"- [[{item_filename(by_num[n])[:-3]}|Item {n}: {by_num[n].title.title()}]]")
    if r.rid == "R95":
        body.append("- every desk page")
    body += ["", "## Provenance", ""]
    if r.round:
        body.append(f"- Round {r.round}" + (f", commit `{r.commit}`" if r.commit else ""))
    body.append("- ratified by Antigravity" if r.ratified else "- NOT ratified: no recorded text")
    body.append("")
    sources: list[dict[str, Any]] = [{"id": "agents-md", "resource": "AGENTS.md", "title": "DEV handoff log",
                                      "author": "human:operator"}]
    if r.commit:
        sources.append({"id": f"commit-{r.commit}", "resource": f"git:{r.commit}", "title": f"commit {r.commit}"})
    dev: dict[str, Any] = {"desk": r.desk, "ruling_id": r.rid}
    if r.round:
        dev["round"] = r.round
    a = _existing(dev_root, r.asserts)
    if a:
        dev["asserts"] = a
    extra: dict[str, Any] = {}
    if r.ratified:
        extra["verified"] = [{"by": ANTIGRAVITY, "at": r.ratified_at or iso(at)}]
    meta = make_meta("Ruling", r.title, r.description,
                     tags=["ruling", f"desk-{r.desk}", r.rid.lower()], generated_by=by, at=at,
                     status=r.status, sources=sources, dev=dev, **extra)
    return Page(page_path(vault, "Ruling", ruling_filename(r)), meta, "\n".join(body))


# ---------------------------------------------------------------- driver

@dataclass
class SeedReport:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    index: str | None = None
    log: str | None = None

    def summary(self) -> str:
        return (f"seed: {len(self.written)} page(s) written, {len(self.skipped)} skipped"
                + (f"; index -> {self.index}" if self.index else "")
                + (f"; log -> {self.log}" if self.log else ""))


def build_all(items: list[ItemSpec], vault: Path, dev_root: Path, registry: Path,
              at: datetime, by: str = GENERATED_BY) -> list[Page]:
    desks = {d.number: d for d in DESKS}
    pages = [build_desk_page(d, items, vault, dev_root, registry, at, by) for d in DESKS]
    pages += [build_item_page(i, desks, vault, dev_root, registry, at, by) for i in items]
    pages += [build_ruling_page(r, desks, items, vault, dev_root, at, by) for r in RULINGS]
    return pages


def seed(vault: Path, dev_root: Path, registry: Path, *, at: datetime | None = None,
         by: str = GENERATED_BY, force: bool = False, dry_run: bool = False) -> SeedReport:
    at = at or registry_mtime(registry)
    items = parse_registry(registry.read_text(encoding="utf-8"))
    report = SeedReport()
    for page in build_all(items, vault, dev_root, registry, at, by):
        rel = page.path.relative_to(vault).as_posix()
        if page.path.exists() and not force:
            report.skipped.append(rel)
            continue
        if not dry_run:
            write_page(page, vault, now=at)
        report.written.append(rel)
    if not dry_run:
        for d in ("wiki", "crm", "journal", "raw"):
            (vault / d).mkdir(parents=True, exist_ok=True)
        report.index = write_index(vault, load_pages(vault)).name
        n_items = sum(1 for _ in items)
        report.log = append_log(
            vault, "Seed",
            f"seed from the Top 20 registry (generated.at {iso(at)}): {len(report.written)} page(s) written, "
            f"{len(report.skipped)} kept ({len(DESKS)} desks, {n_items} items, {len(RULINGS)} rulings); "
            f"[index](index.md) rebuilt.", when=at).name
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.seed", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--registry", type=Path, default=None, help=f"default <dev-root>/{REGISTRY_NAME}")
    ap.add_argument("--force", action="store_true", help="rewrite pages that already exist")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--at", default=None, help="ISO 8601 instant for generated.at (default: the registry file's mtime)")
    args = ap.parse_args(argv)

    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - seed refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    registry = args.registry or (args.dev_root / REGISTRY_NAME)
    if not registry.is_file():
        print(f"[REFUSE] registry not found: {registry} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    at = parse_iso8601(args.at) if args.at else None
    report = seed(args.vault, args.dev_root, registry, at=at, force=args.force, dry_run=args.dry_run)
    for rel in report.written:
        print(("[DRY] " if args.dry_run else "[WRITE] ") + rel, file=out)
    for rel in report.skipped:
        print("[KEEP]  " + rel, file=out)
    print(report.summary(), file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
