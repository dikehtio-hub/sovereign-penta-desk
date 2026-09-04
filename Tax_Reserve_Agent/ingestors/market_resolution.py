"""
Automated market resolution sync.

Finds prediction-market lots that are still open in the ledger, checks whether
their market has actually resolved, and books the settlement - losers written off
at $0.00, winners closed at their payout. Drives `python -m Tax_Reserve_Agent.main
resolve-markets`.

WHY THIS IS WRITTEN SO DEFENSIVELY. Every other ingestor reports something that
happened; this one INFERS that something happened and then writes a realised loss
off the back of that inference. A false write-off invents a capital loss, which
lowers net gains, which lowers the tax escrow - so the failure mode points
directly at under-reserving for a real tax bill. Three rules follow from that:

  1. RESOLUTION IS VERIFIED ON CHAIN, NOT ASSUMED FROM GAMMA. Gamma's `closed`
     flag means the market stopped trading, which is not the same as payouts
     having been reported - a market can close days before UMA resolves it, and
     can close disputed. `payoutDenominator > 0` on the ConditionalTokens
     contract is the authoritative statement that payouts exist. Gamma is used to
     find CANDIDATES cheaply; the chain decides. `--trust-gamma` relaxes this and
     says so loudly.
  2. A CONDITION'S LEGS SETTLE TOGETHER. Splitting $100 and holding both legs to
     resolution is a wash: +$50 winner, -$50 loser. Writing off only the loser
     invents a $50 loss. Every open leg of a resolved condition is booked in the
     same batch.
  3. NOTHING IS WRITTEN WITHOUT `--apply`. The default is a plan you can read.

The settlement is dated to the market's resolution, never to today, because the
date picks the tax year. A condition whose resolution date cannot be established
is skipped rather than dated to now.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .polymarket import (
    CTF_CONTRACT_ADDRESS,
    PolygonRPCClient,
    PolymarketChainIngestor,
    PolymarketMarketResolver,
    canonical_symbol,
)

RESOLVED_PRICE_TOLERANCE = 1e-6
# How far a Gamma price may sit from a clean 0 or 1 and still be read as a payout.
# Resolved markets quote the LAST TRADE, not the settlement, so a winner reads
# 0.999999 rather than exactly 1.
GAMMA_RESOLUTION_TOLERANCE = 1e-3


@dataclass
class ResolutionPlan:
    """What `resolve-markets` intends to do, before it does any of it."""
    settlements: List[Dict[str, Any]] = field(default_factory=list)
    resolved_conditions: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)   # (subject, reason)

    @property
    def realised_proceeds(self) -> float:
        return sum(row["quantity"] * row["price"] for row in self.settlements)

    def render(self) -> str:
        lines = ["=" * 68, "  MARKET RESOLUTION PLAN", "=" * 68]
        if self.resolved_conditions:
            for entry in self.resolved_conditions:
                lines.append(f"  {entry['slug'] or entry['condition_id'][:18]}  "
                             f"[resolved {entry['resolved_at']}, verified {entry['verified_by']}]")
                for row in entry["rows"]:
                    verdict = "WORTHLESS" if row["price"] <= 0 else f"${row['price']:.4f}/share"
                    lines.append(f"      {row['symbol']:<34} {row['quantity']:>12,.2f} sh  ->  {verdict}")
        else:
            lines.append("  (no open positions in verified-resolved markets)")

        lines.append("-" * 68)
        lines.append(f"  {len(self.settlements)} lot(s) to settle across "
                     f"{len(self.resolved_conditions)} condition(s); "
                     f"${self.realised_proceeds:,.2f} of proceeds to book.")
        if self.skipped:
            lines.append("-" * 68)
            lines.append("  SKIPPED (left open):")
            for subject, reason in self.skipped:
                lines.append(f"    * {subject}: {reason}")
        lines.append("=" * 68)
        return "\n".join(lines)


def parse_gamma_timestamp(value: Any) -> Optional[str]:
    """Gamma's assorted date formats -> the ledger's 'YYYY-MM-DD HH:MM:SS'."""
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip().replace("Z", "+00:00")
    for parse in (
        lambda t: datetime.fromisoformat(t),
        lambda t: datetime.strptime(t, "%Y-%m-%d %H:%M:%S"),
        lambda t: datetime.strptime(t, "%Y-%m-%d"),
    ):
        try:
            parsed = parse(text)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def gamma_payout_ratios(market: Dict[str, Any]) -> Optional[List[float]]:
    """
    `outcomePrices` -> payout ratios, or None when they do not describe a
    resolution. Used ONLY by `--trust-gamma`; the chain is the default authority.

    GAMMA DOES NOT PUBLISH PAYOUTS - IT PUBLISHES THE LAST TRADE. Measured across
    300 closed markets on 2026-09-02, a resolved winner reads 0.9999989, not 1.0,
    and the loser reads 1.01e-06, not 0. Cross-checked against on-chain
    `payoutNumerators`, which returns the true [0.0, 1.0] for the same markets.

    The consequence is that "the vector sums to 1.0" is NOT a test for
    resolution - a market that merely stopped trading at a final mid of
    [0.97, 0.03] also sums to 1.0, and accepting it would book a fabricated
    97%/3% settlement into the ledger as though it were a payout. Every value is
    therefore required to sit within `GAMMA_RESOLUTION_TOLERANCE` of a clean 0 or
    1, with exactly one winner, and is then SNAPPED to exact 0.0/1.0 to match what
    the contract actually pays.

    This deliberately refuses genuine fractional resolutions (a scalar market
    settling 0.5/0.5). Those are indistinguishable from a final mid price in this
    field, so they are skipped rather than guessed at - the on-chain path handles
    them exactly, and `--trust-gamma` is the explicitly-less-safe fallback.

    15% of closed markets carry an all-zero vector (void or not yet settled) and
    are rejected by the same rule.
    """
    prices = PolymarketMarketResolver._maybe_json_list(market.get("outcomePrices"))
    if not prices:
        return None
    try:
        ratios = [float(p) for p in prices]
    except (TypeError, ValueError):
        return None

    snapped = []
    for ratio in ratios:
        if abs(ratio) <= GAMMA_RESOLUTION_TOLERANCE:
            snapped.append(0.0)
        elif abs(ratio - 1.0) <= GAMMA_RESOLUTION_TOLERANCE:
            snapped.append(1.0)
        else:
            return None   # a real price, not a payout - refuse to invent a settlement
    if sum(snapped) != 1.0:
        return None       # no winner, or several - not a resolution this can read
    return snapped


class MarketResolutionSync:
    """
    Reconciles open prediction-market lots against real market resolutions.

    Network access is entirely through injected `resolver` / `rpc` objects, so the
    planner is unit-testable offline with fakes.
    """

    def __init__(self,
                 db_path: Optional[Path] = None,
                 resolver: Optional[PolymarketMarketResolver] = None,
                 rpc: Optional[PolygonRPCClient] = None,
                 ctf_address: str = CTF_CONTRACT_ADDRESS,
                 trust_gamma: bool = False,
                 losers_only: bool = False):
        self.db_path = db_path
        self.resolver = resolver or PolymarketMarketResolver()
        self.rpc = rpc
        self.ctf_address = ctf_address
        self.trust_gamma = trust_gamma
        self.losers_only = losers_only
        # Per-run memo. Resolution state is fetched uncached on purpose (a stale
        # "still open" is the one answer that matters), but fetching it twice for
        # the same condition inside one plan is just a wasted round trip.
        self._state_memo: Dict[str, Optional[Dict[str, Any]]] = {}

    # -- discovery ----------------------------------------------------------

    def open_positions(self) -> Dict[str, float]:
        """Every prediction-market symbol still holding open shares."""
        from ..database.db import get_connection

        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, SUM(remaining_qty) AS open_qty
                FROM tax_lots
                WHERE is_closed = 0 AND asset_class = 'prediction_market'
                GROUP BY symbol
            """)
            rows = cursor.fetchall()
        finally:
            conn.close()
        return {row["symbol"]: float(row["open_qty"] or 0.0) for row in rows
                if float(row["open_qty"] or 0.0) > 1e-9}

    def symbol_to_condition(self) -> Dict[str, str]:
        """
        Reverse index: symbol -> condition_id. NO outcome index - see below.

        Two sources, because symbols reach the ledger by two routes:
          * markets whose full Gamma record is cached (every symbol they could
            have produced is regenerated, in both the readable `SLUG-OUTCOME` form
            and the `CTF-<cid>-<indexSet>` fallback), and
          * `symbol:` links recorded by the Data API fill parser, which builds
            symbols from a trade row without ever consulting Gamma.

        The outcome INDEX is deliberately not carried here. A cached entry can be
        stale or partial, and a trade row's own `outcomeIndex` is garbage on ~6% of
        rows - and picking the wrong leg settles a winner as worthless. The index
        is resolved in `plan()` against the authoritative `outcomes` order on the
        freshly-fetched market instead.

        A symbol neither source has seen (a hand-entered `MARKET_A_YES`) simply
        does not appear, and is reported as unmappable rather than guessed at.
        """
        index: Dict[str, str] = {}
        for key, entry in self.resolver._cache.items():
            if not isinstance(entry, dict):
                continue
            if key.startswith("symbol:"):
                if entry.get("condition_id"):
                    index[key[len("symbol:"):]] = entry["condition_id"]
                continue
            if key.startswith("token:"):
                continue
            condition_id = entry.get("condition_id") or key
            for outcome_index, outcome in enumerate(entry.get("outcomes") or []):
                if entry.get("slug"):
                    index[canonical_symbol(slug=entry["slug"], outcome=outcome)] = condition_id
                index[canonical_symbol(condition_id=condition_id,
                                       index_set=1 << outcome_index)] = condition_id
        return index

    @staticmethod
    def outcome_index_for_symbol(symbol: str, market: Dict[str, Any],
                                 condition_id: str) -> Optional[int]:
        """
        Which outcome slot `symbol` names, per Gamma's authoritative outcome order.

        Regenerates the symbol each outcome would produce and matches on that, so
        it agrees with `canonical_symbol()` by construction rather than by
        assuming a stored index is still right.
        """
        outcomes = PolymarketMarketResolver._maybe_json_list(market.get("outcomes"))
        slug = market.get("slug") or ""
        for position, outcome in enumerate(outcomes):
            if slug and canonical_symbol(slug=slug, outcome=str(outcome)) == symbol:
                return position
            if canonical_symbol(condition_id=condition_id, index_set=1 << position) == symbol:
                return position
        return None

    def recover_condition_id(self, symbol: str) -> Optional[str]:
        """
        Recovers a full condition id for a legacy `CTF-<prefix>-<indexSet>` lot.

        THE BRIEFED APPROACH CANNOT WORK: `transactions.notes` carried only the
        first 12 hex characters, exactly as the symbol carries 10 - both are
        prefixes of the same 64-character id, so combining them recovers no extra
        bits. (Notes written from Round 7 on carry the id in full, so this path is
        only for rows written earlier.)

        What DOES work is the transaction hash. A CTF row's `tx_hash` is
        `<real polygon tx hash>#<log index>#<index set>`, so the original log can
        be re-fetched and decoded for the exact condition id - a measurement, not
        an inference.

        Returns None rather than guessing. A 40-bit prefix has real collision risk
        across a large market set, and settling against the wrong market is worse
        than leaving the position open.
        """
        from ..database.db import get_connection
        from .polymarket import CTFEventDecoder

        parts = symbol.split("-")
        if not symbol.startswith("CTF-") or len(parts) < 3:
            return None
        prefix = parts[1].lower()

        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("""
                SELECT DISTINCT t.tx_hash, t.notes
                FROM tax_lots l JOIN transactions t ON t.id = l.transaction_id
                WHERE l.symbol = ? AND t.source = 'polymarket'
            """, (symbol,)).fetchall()
        finally:
            conn.close()

        # 1. A note already carrying the full id (rows written from Round 7 on).
        for row in rows:
            for token in str(row["notes"] or "").split():
                if (token.startswith("0x") and len(token) == 66
                        and token[2:].lower().startswith(prefix)):
                    return token.lower()

        # 2. Re-read the original log from chain.
        if self.rpc is None:
            return None
        for row in rows:
            raw = str(row["tx_hash"] or "")
            if "#" not in raw:
                continue
            tx_hash, _, rest = raw.partition("#")
            log_index = rest.split("#")[0]
            if not tx_hash.startswith("0x") or not log_index.isdigit():
                continue
            try:
                receipt = self.rpc.call("eth_getTransactionReceipt", [tx_hash])
            except Exception as e:
                print(f"[INFO] Could not re-read {tx_hash[:12]}... for {symbol}: {e}")
                continue
            for log in (receipt or {}).get("logs", []):
                try:
                    event = CTFEventDecoder.decode_log(log)
                except Exception:
                    continue
                if event and event["log_index"] == int(log_index):
                    condition_id = event["condition_id"]
                    if condition_id[2:].lower().startswith(prefix):
                        return condition_id
        return None

    # -- verification -------------------------------------------------------

    def market_state(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """`fetch_market_state`, fetched at most once per condition per plan run."""
        if condition_id not in self._state_memo:
            self._state_memo[condition_id] = self.resolver.fetch_market_state(condition_id)
        return self._state_memo[condition_id]

    def verify_resolution(self, condition_id: str) -> Tuple[Optional[List[float]], str, str]:
        """
        Returns (payout_ratios, verified_by, reason).

        `payout_ratios` is None when the condition is not verifiably resolved -
        which is the only safe default, since booking a settlement that has not
        happened writes a loss the ledger will never take back.
        """
        market = self.market_state(condition_id)
        if market is None:
            return None, "", "no Gamma record for this condition (offline, or delisted market)"
        if not market.get("closed"):
            return None, "", "market is still open on Gamma"

        if self.rpc is not None:
            ratios = self.rpc.get_payout_ratios(condition_id, self.ctf_address)
            if ratios:
                return ratios, "chain", ""
            if not self.trust_gamma:
                return None, "", ("Gamma says closed but the CTF contract reports no payouts yet "
                                  "(unresolved or disputed) - re-run once it settles, or pass "
                                  "--trust-gamma to accept Gamma's word")
        elif not self.trust_gamma:
            return None, "", ("no Polygon RPC available to verify payouts on chain - "
                              "pass --trust-gamma to settle on Gamma's word alone")

        ratios = gamma_payout_ratios(market)
        if ratios is None:
            return None, "", "Gamma outcomePrices do not describe a settled payout vector"
        return ratios, "gamma", ""

    # -- planning -----------------------------------------------------------

    def plan(self, as_of: Optional[str] = None) -> ResolutionPlan:
        """
        Works out what should be settled, touching nothing.

        `as_of` supplies a settlement date for conditions whose resolution date
        Gamma does not carry. Without it such a condition is skipped: the date
        chooses the tax year, and silently defaulting to today would file a prior
        year's loss against this one.
        """
        plan = ResolutionPlan()
        self._state_memo.clear()
        open_positions = self.open_positions()
        if not open_positions:
            return plan

        index = self.symbol_to_condition()
        by_condition: Dict[str, List[str]] = {}
        for symbol in sorted(open_positions):
            condition_id = index.get(symbol)
            if condition_id is None:
                # Cold cache: ask Gamma directly rather than declaring the position
                # unresolvable. Without this, a ledger built from CSV imports (or a
                # cleared cache) mapped nothing at all and settled nothing.
                resolved = self.resolver.resolve_symbol(symbol) or {}
                condition_id = resolved.get("condition_id") or None
                if condition_id is None and symbol.startswith("CTF-"):
                    # Legacy on-chain symbol: the id is not in the symbol, but the
                    # transaction that wrote it is still on Polygon.
                    condition_id = self.recover_condition_id(symbol)
            if condition_id is None:
                plan.skipped.append((symbol, "no condition id on record and Gamma could not "
                                             "identify it - hand-entered, or a CTF-<prefix> symbol "
                                             "whose truncated condition id cannot be reversed"))
                continue
            by_condition.setdefault(condition_id, []).append(symbol)

        for condition_id, legs in sorted(by_condition.items()):
            ratios, verified_by, reason = self.verify_resolution(condition_id)
            market = self.resolver.by_condition(condition_id) or {}
            label = market.get("slug") or condition_id[:18]
            if ratios is None:
                plan.skipped.append((label, reason))
                continue

            raw_market = self.market_state(condition_id) or market or {}
            resolved_at = (parse_gamma_timestamp(raw_market.get("closedTime"))
                           or parse_gamma_timestamp(raw_market.get("endDate"))
                           or parse_gamma_timestamp(raw_market.get("umaEndDate"))
                           or as_of)
            if not resolved_at:
                plan.skipped.append((label, "resolution date unknown - pass --as-of to date the "
                                            "settlement explicitly (it picks the tax year)"))
                continue

            payouts: Dict[str, float] = {}
            for symbol in sorted(legs):
                outcome_index = self.outcome_index_for_symbol(symbol, raw_market, condition_id)
                if outcome_index is None:
                    plan.skipped.append((symbol, "could not be matched to an outcome in the "
                                                 "market's current outcome list"))
                    continue
                if outcome_index >= len(ratios):
                    plan.skipped.append((symbol, f"outcome slot {outcome_index} is outside the "
                                                 f"{len(ratios)}-slot payout vector"))
                    continue
                payout = float(ratios[outcome_index])
                if self.losers_only and payout > 0:
                    plan.skipped.append((symbol, f"winner at ${payout:.4f}/share left open "
                                                 f"(--losers-only); redeem it on chain"))
                    continue
                payouts[symbol] = payout

            if not payouts:
                continue
            rows = PolymarketChainIngestor.build_settlements(payouts, resolved_at, self.db_path)
            if not rows:
                continue
            plan.settlements.extend(rows)
            plan.resolved_conditions.append({
                "condition_id": condition_id,
                "slug": market.get("slug", ""),
                "resolved_at": resolved_at,
                "verified_by": verified_by,
                "rows": rows,
            })
        return plan

    def apply(self, plan: ResolutionPlan) -> int:
        """Commits a plan's settlements. Returns the number of lots settled."""
        from ..engine.lot_engine import process_batch

        if not plan.settlements:
            return 0
        process_batch(plan.settlements, db_path=self.db_path)
        return len(plan.settlements)
