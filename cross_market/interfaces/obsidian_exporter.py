"""
Cross-market arbitrage -> Obsidian. Writes `<vault>/Cross_Market_Arb.md`.

Every matched Polymarket / sportsbook pair, priced through the asymmetric tax
engine, with BOTH characterisations on the line - because Round 29 ruled IRC
1234A capital the default and kept the wagering reading available, and that is
only useful if the operator can see what the adverse reading costs at the moment
of deciding.

Two reference hurdles are printed at the top so a row can be read against them
without a calculator: 16.75% (capital reading, no relief capacity - the realistic
case) and 23.93% (the Polymarket leg read as wagering). Per-pair hurdles are
computed live from the pair's own shape and shown beside each row; the reference
figures are the round-27 headline numbers, not a substitute for them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Sports_Desk.interfaces.obsidian_exporter import (HUB_NOTE, fmt_usd, resolve_vault,
                                                      write_note_if_changed)
from cross_market.hud import _adverse_hurdle, scan_cross_market
from cross_market.hybrid_arb import MIN_CAPITAL
from cross_market.matcher import DEFAULT_DB_PATH

CROSS_MARKET_ARB_NOTE = "Cross_Market_Arb"
DEFAULT_QUESTIONS_DIR = (Path(__file__).resolve().parents[2]
                         / "Sports_Desk" / "data" / "polymarket_drops")

# Round 27 headline hurdles, NJ resident, composite 32.37%.
HURDLE_CAPITAL_NO_CAPACITY = 0.1675
HURDLE_WAGERING = 0.2393

# What a pair is priced on when the bankroll is $0 or gated. The verdict does
# not depend on capital (the hurdle is a property of shape and tax), so a nominal
# figure gives the same yes/no; only the dollar stakes are notional.
NOMINAL_CAPITAL = 1_000.0


def load_questions(drop_dir: Path = DEFAULT_QUESTIONS_DIR) -> List[Dict[str, Any]]:
    """
    Polymarket questions from dropped JSON files. Never the network.

    ONE ROW PER MARKET, THE NEWEST WINS. A folder that has been polled into holds
    the same market in several files at prices that are no longer offered;
    pricing each copy would show a pair three times at three stale prices.
    Files are read oldest-first and keyed by token id (question text when there
    is none), so the most recently written quote is the one that survives.
    """
    drop_dir = Path(drop_dir)
    if not drop_dir.exists():
        return []
    found: Dict[str, Dict[str, Any]] = {}
    paths = sorted(drop_dir.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for row in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(row, dict):
                continue
            key = str(row.get("token_id") or row.get("question") or id(row))
            found[key] = row
    return list(found.values())


def collect(hook: Any, questions: List[Dict[str, Any]],
            db_path: Path = DEFAULT_DB_PATH,
            capital: Optional[float] = None) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {"questions": len(questions), "rows": [],
                                "capital": None, "capital_note": "", "error": ""}
    if capital is None:
        try:
            capital = float(hook.get_safe_bankroll()) if hook is not None else 0.0
        except Exception:                                       # noqa: BLE001
            capital = 0.0
    if capital < MIN_CAPITAL:
        snapshot["capital_note"] = ("bankroll is %s - pairs priced on a nominal %s; "
                                    "verdicts are unaffected, stakes are notional"
                                    % (fmt_usd(capital), fmt_usd(NOMINAL_CAPITAL)))
        capital = NOMINAL_CAPITAL
    snapshot["capital"] = capital
    if not questions or hook is None:
        return snapshot
    try:
        results, pairs = scan_cross_market(hook, questions, db_path=db_path,
                                           capital=capital)
    except Exception as exc:                                    # noqa: BLE001
        snapshot["error"] = "%s: %s" % (type(exc).__name__, exc)
        return snapshot
    for result, pair in zip(results, pairs):
        adverse = _adverse_hurdle(result)
        snapshot["rows"].append({
            "pair": "%s / %s" % (result.leg_a.selection, result.leg_b.selection),
            "token_id": result.leg_a.token_id,
            "limit_price": result.leg_a.limit_price,
            "book": result.leg_b.venue,
            "book_selection": result.leg_b.selection,
            "book_odds": result.leg_b.decimal_odds,
            "gross_arb": result.gross_arb,
            "worst_pct": result.worst_after_tax_pct,
            "hurdle_capital": result.breakeven_gross_arb,
            "hurdle_wagering": adverse,
            "viable": result.viable,
            "stake_a": result.stake_a, "stake_b": result.stake_b,
            "rationale": pair.target.rationale if getattr(pair, "target", None) else "",
        })
    snapshot["rows"].sort(key=lambda r: (not r["viable"], -(r["worst_pct"] or 0.0)))
    return snapshot


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else "%+.2f%%" % (float(value) * 100.0)


def render(snapshot: Dict[str, Any], synced_at: str, vault_path: Path) -> str:
    rows = snapshot.get("rows") or []
    viable = [r for r in rows if r["viable"]]
    lines: List[str] = [
        "---", "title: Cross-Market Arbitrage - Polymarket vs Sportsbook",
        "tags:", "  - monarch", "  - cross-market", "  - arbitrage", "  - tax-asymmetry",
        'last_synced: "%s"' % synced_at, "---", "",
        "# ⚖️ Cross-Market Arbitrage - Polymarket vs Sportsbook", "",
        "> [!INFO] **Desk Snapshot**",
        "> - **Questions loaded**: `%d`" % int(snapshot.get("questions", 0)),
        "> - **Matched pairs**: `%d`  •  **Clearing after tax**: **`%d`**" % (len(rows), len(viable)),
        "> - **Pricing capital**: `%s`%s" % (fmt_usd(float(snapshot.get("capital") or 0.0)),
                                             ("  _(%s)_" % snapshot["capital_note"])
                                             if snapshot.get("capital_note") else ""),
        "> - **Reference hurdles**: capital reading, no capacity **`%.2f%%`** • "
        "wagering reading **`%.2f%%`**" % (HURDLE_CAPITAL_NO_CAPACITY * 100.0, HURDLE_WAGERING * 100.0),
        "> - **Last Synchronized**: `%s`" % synced_at, "",
        "> **Cockpit Navigation**: [[%s|👑 Master Hub]] • [[Sports_Desk|🏈 Sports Desk]] "
        "• [[Polymarket_Monarch|🌐 Polymarket]] • [[HyperLiquid_Monarch|🏛 HyperLiquid]]" % HUB_NOTE,
        "", "---", "",
        "> [!NOTE] **Why the bar is so high**",
        "> Each leg's loss is deductible only against a class of income the other leg does not",
        "> produce. When the sportsbook leg loses, the winner is a capital gain - NJ 54A:5-1(g)",
        "> has no gambling winnings to net against. When the Polymarket leg loses, the winner is",
        "> ordinary income - IRC 1211(b) caps the offset at $3,000. Real cross-book arbs pay 1-3%.",
        "", "---", "", "## 📋 Matched Pairs", ""]

    if snapshot.get("error"):
        lines.append("_Scan failed: %s._" % snapshot["error"])
    elif not rows:
        lines.append("_No matched cross-market pairs. This is the normal state: a pair needs the "
                     "same fixture, market and line quoted on both venues at once, and "
                     "unmatched markets are dropped rather than approximated._")
    else:
        lines += ["| Verdict | Pair | Book arb | Worst after-tax | Hurdle (1234A) | Hurdle (165(d)) | Leg A | Leg B |",
                  "| :---: | :--- | ---: | ---: | ---: | ---: | :--- | :--- |"]
        for r in rows:
            flag_cap = "" if r["hurdle_capital"] is None or r["gross_arb"] >= r["hurdle_capital"] else " ⛔"
            flag_wag = "" if r["hurdle_wagering"] is None or r["gross_arb"] >= r["hurdle_wagering"] else " ⛔"
            lines.append("| %s | %s | `%s` | **`%s`** | `%s`%s | `%s`%s | `%s` @ %.4f (%s) | %s %s @ %.4f (%s) |" % (
                "✅ CLEARS" if r["viable"] else "❌ REJECT", r["pair"],
                _pct(r["gross_arb"]), _pct(r["worst_pct"]),
                _pct(r["hurdle_capital"]), flag_cap, _pct(r["hurdle_wagering"]), flag_wag,
                r["token_id"] or "?", float(r["limit_price"] or 0.0), fmt_usd(r["stake_a"]),
                r["book"], r["book_selection"], r["book_odds"], fmt_usd(r["stake_b"])))
        lines += ["", "_⛔ marks a book arb below that reading's hurdle. A pair that clears 1234A but "
                  "not 165(d) is a position whose verdict depends on a question the IRS has not "
                  "answered._"]

    lines += ["", "---", "", "- Sports DB: `%s`" % DEFAULT_DB_PATH,
              "- Vault: `%s`" % vault_path, "",
              "*Generated by `cross_market.interfaces.obsidian_exporter`.*"]
    return "\n".join(lines)


def default_hook() -> Any:
    try:
        from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
        return get_hook()
    except Exception:                                           # noqa: BLE001
        return None


def export_cross_market_arb(vault: Optional[str] = None, hook: Any = None,
                            questions: Optional[List[Dict[str, Any]]] = None,
                            db_path: Path = DEFAULT_DB_PATH,
                            questions_dir: Path = DEFAULT_QUESTIONS_DIR,
                            capital: Optional[float] = None,
                            now: Optional[datetime] = None) -> Tuple[Path, bool]:
    vault_path = resolve_vault(vault)
    now = now or datetime.now(timezone.utc)
    synced_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    hook = hook if hook is not None else default_hook()
    questions = questions if questions is not None else load_questions(questions_dir)
    snapshot = collect(hook, questions, db_path=db_path, capital=capital)
    return write_note_if_changed(vault_path / ("%s.md" % CROSS_MARKET_ARB_NOTE),
                                 render(snapshot, synced_at, vault_path))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-Market Arb -> Obsidian exporter")
    parser.add_argument("--vault", type=str, default=None)
    parser.add_argument("--db", type=Path, default=None, help="sports_market.db path")
    parser.add_argument("--questions", type=Path, default=None, help="Polymarket JSON drop dir")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=15.0)
    args = parser.parse_args(argv)
    db_path = Path(args.db or DEFAULT_DB_PATH)
    qdir = Path(args.questions or DEFAULT_QUESTIONS_DIR)

    if not args.watch:
        path, changed = export_cross_market_arb(args.vault, db_path=db_path, questions_dir=qdir)
        print("[OK] %s %s" % (path, "written" if changed else "unchanged"))
        return 0
    print("[SYNC] Cross-Market Arb -> %s every %gs. Ctrl-C to stop."
          % (resolve_vault(args.vault), args.interval))
    try:
        while True:
            path, changed = export_cross_market_arb(args.vault, db_path=db_path, questions_dir=qdir)
            print("[%s] %s %s" % (datetime.now().strftime("%H:%M:%S"), path.name,
                                  "written" if changed else "unchanged"))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[STOP] Cross-Market Arb exporter stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
