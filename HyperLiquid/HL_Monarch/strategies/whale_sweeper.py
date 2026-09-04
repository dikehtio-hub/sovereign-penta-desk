"""
HL_Shark: whale cascade sweeper - cluster geometry, and the gate that holds it shut.

READ THIS BEFORE ENABLING ANYTHING HERE.

The strategy this module describes has already been built, traded on paper,
measured against a pre-registered bar, and RETIRED. It is not an untested idea.
`execution/strategies/liquidation_fade_strategy.py` traded exactly this thesis -
detect a forced-sell cascade, compute a rebound zone, rest a limit order in it -
and `config/settings.py` records why it stopped:

    MFE/MAE 0.513 against a random-entry control of 1.092
    n=466, 98% coverage, 30m horizon
    paired MFE-MAE per event: t = -10.52
    MAE exceeded MFE in 72.7% of events
    0 of 20,000 bootstrap resamples produced a non-negative mean

A ratio BELOW the random control means entering on this signal was worse than
entering at random. Forced liquidations are MOMENTUM drivers, not mean-reverting
wicks: price ran about twice as far against the fade as for it. Rounds 9 through
15 of execution refinement - better geometry, tighter stops, regime filters -
never moved the number, because no amount of execution work fixes a sign error.

TIGHT POST-FILL TRAILING STOPS MAKE THAT WORSE, NOT BETTER. Against a momentum
driver the fill arrives precisely because price is still travelling against you,
and a tight stop then converts the adverse excursion from paper into realised
loss. The retired strategy's own history is the evidence: it is the configuration
rounds 9-15 kept trying.

WHAT IS ACTUALLY OPEN, AND IT IS NARROWER THAN IT SOUNDS.
`data/experiments/passive_fade_rebenchmark.meta.json` records a live
pre-registration, and it is honest about the retirement's weakness: the 0.513
came from 15.2 hours in which two microcaps supplied 83% of all events
(HHI 0.360), and the broad-market effect was 0.849 - still sub-random, but far
less damning. Only the 30-minute horizon clears p<0.05 under a cluster bootstrap;
at 5m and 15m the retirement is NOT statistically significant.

So the honest position is: probably no edge, not proven across the broad market,
and under active re-measurement with execution DISABLED. The reopening bar was
set deliberately asymmetric - retiring took p=0.024 on a narrow sample, so coming
back costs more than leaving did:

    >= 500 events, >= 20 coins, no coin over 20% of the sample
    then P(ratio >= 1.25) > 0.90 under a CLUSTER bootstrap resampling coins

WHAT THIS MODULE THEREFORE DOES. Everything the sweeper needs except the part
that would violate the pre-registration: cluster identification, rebound-zone
geometry, order sizing, and the `hl_whale_sweep` bankroll bucket. Execution is
held behind `EvidenceGate`, which reads the live benchmark and refuses until the
bar is cleared. Nothing here is a placeholder - the day the measurement clears,
`WHALE_SWEEP_EXECUTION_ENABLED` flips and the path is already wired and tested.

The gate is the deliverable. A sweeper that trades a signal measured at half of
random is not a strategy, it is a way to pay fees faster.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from strategies.funding_harvester import BucketGate, GateDecision

STRATEGY_WHALE_SWEEP = "hl_whale_sweep"

# Mirrors FADE_STRATEGY_ENABLED. This flag alone does not open the path - the
# evidence gate below must ALSO pass - but flipping it without the measurement is
# the single mistake this module exists to make difficult.
WHALE_SWEEP_EXECUTION_ENABLED = False

EXPERIMENT_PATH = (Path(__file__).resolve().parents[1] / "data" / "experiments"
                   / "passive_fade_rebenchmark.meta.json")

# The pre-registered reopening bar. Duplicated from the experiment file as a
# fallback only; `EvidenceGate` prefers the file, so amending the registration
# amends the gate rather than leaving the two to drift apart.
REOPEN_RATIO = 1.25
REOPEN_CONFIDENCE = 0.90
REOPEN_MIN_EVENTS = 500
REOPEN_MIN_COINS = 20
REOPEN_MAX_COIN_SHARE = 0.20

# The retirement measurement, kept here so a caller reading a refusal does not
# have to go looking for why.
RETIREMENT_RATIO = 0.513
RETIREMENT_CONTROL = 1.092


class SweeperDisabled(RuntimeError):
    """Execution was attempted while the evidence gate is shut."""


# ---------------------------------------------------------------------------
# Cluster geometry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SweepZone:
    """A rebound zone: where an order WOULD rest, if the signal had an edge."""

    coin: str
    side: str                      # "BUY" below a long-liquidation cluster
    cluster_price: float
    cluster_notional: float
    mark_price: float
    entry_price: float
    stop_price: float
    take_profit: float
    distance_pct: float
    book_depth_usd: float = 0.0

    @property
    def reward_risk(self) -> float:
        risk = abs(self.entry_price - self.stop_price)
        return abs(self.take_profit - self.entry_price) / risk if risk else 0.0

    def as_record(self) -> Dict[str, Any]:
        return {"coin": self.coin, "side": self.side,
                "cluster_price": self.cluster_price,
                "cluster_notional": self.cluster_notional,
                "mark_price": self.mark_price, "entry_price": self.entry_price,
                "stop_price": self.stop_price, "take_profit": self.take_profit,
                "distance_pct": self.distance_pct,
                "book_depth_usd": self.book_depth_usd,
                "reward_risk": self.reward_risk}


def wick_rebound_zone(coin: str, cluster_price: float, mark_price: float,
                      cluster_notional: float = 0.0,
                      overshoot_pct: float = 0.35,
                      stop_pct: float = 0.60,
                      target_pct: float = 0.90,
                      book_depth_usd: float = 0.0) -> Optional[SweepZone]:
    """
    Where a rebound order would rest relative to a liquidation cluster.

    The geometry is the retired strategy's, reproduced faithfully rather than
    reinvented: rest BEYOND the cluster by `overshoot_pct`, because a cascade
    that stops exactly at the cluster never fills the order, and one that runs
    through it fills at a better price. Stop beyond that again; target back
    toward the mark.

    THE GEOMETRY WAS NEVER THE PROBLEM. Rounds 9 through 15 rebuilt exactly this
    calculation - offsets, ATR scaling, floors against the fee - and the MFE/MAE
    result did not move, because the signal's SIGN was wrong. This function is
    here to measure zones, not to redeem them, and a caller that finds a
    beautiful reward:risk here has learned nothing about whether to trade it.

    Returns None for a cluster on the wrong side of the mark: a long-liquidation
    cluster ABOVE the mark is not a cascade level, it is stale data.
    """
    if mark_price <= 0 or cluster_price <= 0:
        return None
    below = cluster_price < mark_price
    side = "BUY" if below else "SELL"
    direction = -1.0 if below else 1.0
    entry = cluster_price * (1.0 + direction * overshoot_pct / 100.0)
    stop = entry * (1.0 + direction * stop_pct / 100.0)
    target = entry * (1.0 - direction * target_pct / 100.0)
    if entry <= 0 or stop <= 0 or target <= 0:
        return None
    return SweepZone(
        coin=coin, side=side, cluster_price=float(cluster_price),
        cluster_notional=float(cluster_notional), mark_price=float(mark_price),
        entry_price=entry, stop_price=stop, take_profit=target,
        distance_pct=abs(entry - mark_price) / mark_price * 100.0,
        book_depth_usd=float(book_depth_usd))


def rank_clusters(clusters: Sequence[Dict[str, Any]], mark_price: float,
                  min_notional: float = 0.0,
                  max_distance_pct: float = 5.0) -> List[Dict[str, Any]]:
    """
    Clusters worth measuring, largest first.

    Distance is capped because a cluster 30% away is not a level the tape will
    reach today, and letting it rank on notional alone fills the report with
    zones nothing will ever touch.
    """
    out = []
    for cluster in clusters:
        price = float(cluster.get("price") or 0.0)
        notional = float(cluster.get("notional") or cluster.get("size_usd") or 0.0)
        if price <= 0 or mark_price <= 0 or notional < min_notional:
            continue
        distance = abs(price - mark_price) / mark_price * 100.0
        if distance > max_distance_pct:
            continue
        out.append({**cluster, "price": price, "notional": notional,
                    "distance_pct": distance})
    return sorted(out, key=lambda c: -c["notional"])


# ---------------------------------------------------------------------------
# The evidence gate
# ---------------------------------------------------------------------------

@dataclass
class EvidenceDecision:
    """Whether the pre-registered bar permits this strategy to trade at all."""

    eligible: bool
    status: str
    detail: str
    ratio: Optional[float] = None
    control: Optional[float] = None
    confidence: Optional[float] = None
    events: int = 0
    coins: int = 0
    top_coin_share: float = 0.0
    bar: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return "[%s] %s" % (self.status, self.detail)


class EvidenceGate:
    """
    Holds execution shut until the pre-registered reopening bar is cleared.

    IT FAILS CLOSED, AND THAT IS THE ENTIRE DESIGN. No benchmark, unreadable
    registration, thin sample, missing p-value - every one of them returns
    ineligible. The default state of a strategy measured at half of random is
    OFF, and anything the gate cannot verify leaves it off.
    """

    def __init__(self, experiment_path: Optional[Path] = None):
        self.experiment_path = Path(experiment_path or EXPERIMENT_PATH)
        self.registration: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            self.registration = json.loads(
                self.experiment_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.registration = {}

    @property
    def bar(self) -> Dict[str, Any]:
        """
        The reopening bar, preferring the registration file over the constants.

        Reading the file means amending the pre-registration amends the gate. A
        gate carrying its own private copy would let the two drift, and the
        version that mattered would be whichever one nobody was looking at.
        """
        requirements = self.registration.get("sample_requirements", {}) or {}
        return {
            "ratio": REOPEN_RATIO,
            "confidence": REOPEN_CONFIDENCE,
            "min_events": int(requirements.get("min_events", REOPEN_MIN_EVENTS)),
            "min_coins": int(requirements.get("min_coins", REOPEN_MIN_COINS)),
            "max_single_coin_share": float(
                requirements.get("max_single_coin_share", REOPEN_MAX_COIN_SHARE)),
        }

    def check(self, benchmark_result: Optional[Dict[str, Any]] = None
              ) -> EvidenceDecision:
        """Evaluate a `wick_benchmark.benchmark()` result against the bar."""
        bar = self.bar
        if not self.registration:
            return EvidenceDecision(
                False, "NO_REGISTRATION",
                "the pre-registration at %s could not be read; a strategy "
                "measured at %.3f against a %.3f control does not trade on an "
                "unverifiable bar" % (self.experiment_path.name,
                                      RETIREMENT_RATIO, RETIREMENT_CONTROL),
                bar=bar)
        if not benchmark_result:
            return EvidenceDecision(
                False, "NO_MEASUREMENT",
                "no excursion benchmark supplied; the retirement stands at "
                "%.3f vs a %.3f control until a new one replaces it"
                % (RETIREMENT_RATIO, RETIREMENT_CONTROL), bar=bar)

        usable = [(h, d) for h, d in sorted(
            (benchmark_result.get("horizons", {}) or {}).items())
            if (d.get("signal") or {}).get("ratio") is not None]
        if not usable:
            return EvidenceDecision(False, "NO_DATA",
                                    "nothing measurable in any horizon", bar=bar)

        horizon, data = usable[-1]
        signal = data.get("signal") or {}
        control = data.get("control") or {}
        events = int(signal.get("n") or 0)
        coins = int(data.get("coins_measured") or 0)
        share = float(data.get("top_coin_share") or 0.0)
        ratio = signal.get("ratio")
        confidence = data.get("cluster_p_ge_reopen")
        if confidence is None:
            confidence = data.get("cluster_p_ge_1")

        fails: List[str] = []
        if events < bar["min_events"]:
            fails.append("n=%d < %d" % (events, bar["min_events"]))
        if coins < bar["min_coins"]:
            fails.append("%d coins < %d" % (coins, bar["min_coins"]))
        if share > bar["max_single_coin_share"]:
            fails.append("top coin %.0f%% > %.0f%%"
                         % (share * 100.0, bar["max_single_coin_share"] * 100.0))
        if fails:
            return EvidenceDecision(
                False, "SAMPLE_TOO_NARROW",
                "%s (the retirement itself rested on a sample this narrow, which "
                "is why the bar exists)" % "; ".join(fails),
                ratio=ratio, control=control.get("ratio"), confidence=confidence,
                events=events, coins=coins, top_coin_share=share, bar=bar)

        if confidence is None:
            return EvidenceDecision(
                False, "NO_CLUSTER_BOOTSTRAP",
                "sample is broad enough but no cluster-bootstrapped confidence "
                "was reported. An EVENT-level bootstrap is invalid here - forward "
                "windows on the same coin overlap, and it reported 0/20,000 where "
                "resampling coins reported 0.024 on identical data",
                ratio=ratio, control=control.get("ratio"), events=events,
                coins=coins, top_coin_share=share, bar=bar)

        if float(confidence) <= bar["confidence"]:
            return EvidenceDecision(
                False, "BAR_NOT_CLEARED",
                "P(ratio >= %.2f) = %.3f, needs > %.2f at the %s horizon"
                % (bar["ratio"], float(confidence), bar["confidence"], horizon),
                ratio=ratio, control=control.get("ratio"),
                confidence=float(confidence), events=events, coins=coins,
                top_coin_share=share, bar=bar)

        return EvidenceDecision(
            True, "BAR_CLEARED",
            "P(ratio >= %.2f) = %.3f > %.2f on n=%d across %d coins at %s"
            % (bar["ratio"], float(confidence), bar["confidence"], events,
               coins, horizon),
            ratio=ratio, control=control.get("ratio"), confidence=float(confidence),
            events=events, coins=coins, top_coin_share=share, bar=bar)


# ---------------------------------------------------------------------------
# The sweeper
# ---------------------------------------------------------------------------

@dataclass
class SweepVerdict:
    """One zone, with both gates' answers and every reason it was refused."""

    coin: str
    zone: Optional[SweepZone]
    evidence: EvidenceDecision
    gate: Optional[GateDecision]
    tradeable: bool
    reasons: List[str] = field(default_factory=list)

    def as_record(self) -> Dict[str, Any]:
        return {"coin": self.coin, "tradeable": self.tradeable,
                "reasons": list(self.reasons),
                "zone": self.zone.as_record() if self.zone else None,
                "evidence": {"eligible": self.evidence.eligible,
                             "status": self.evidence.status,
                             "detail": self.evidence.detail},
                "gate": {"approved": self.gate.approved,
                         "approved_capital": self.gate.approved_capital}
                if self.gate else None}


class WhaleSweeper:
    """
    Measures cascade zones. Trades none of them until the evidence says so.

    Both gates must pass, and they are independent questions: `EvidenceGate` asks
    whether this signal has an edge at all, `BucketGate` asks whether the desk
    can fund it. A strategy can be perfectly funded and still have no business
    trading, which is exactly the situation here.
    """

    def __init__(self, hook: Any = None, gate: Optional[BucketGate] = None,
                 evidence: Optional[EvidenceGate] = None,
                 notional_usd: float = 1_000.0,
                 execution_enabled: bool = WHALE_SWEEP_EXECUTION_ENABLED):
        self.gate = gate if gate is not None else BucketGate(
            hook=hook, strategy=STRATEGY_WHALE_SWEEP)
        self.evidence = evidence if evidence is not None else EvidenceGate()
        self.notional_usd = float(notional_usd)
        self.execution_enabled = bool(execution_enabled)
        self.observed: List[Dict[str, Any]] = []

    def evaluate(self, coin: str, cluster_price: float, mark_price: float,
                 cluster_notional: float = 0.0, book_depth_usd: float = 0.0,
                 benchmark_result: Optional[Dict[str, Any]] = None
                 ) -> SweepVerdict:
        """Price one cluster and ask both gates."""
        zone = wick_rebound_zone(coin, cluster_price, mark_price,
                                 cluster_notional=cluster_notional,
                                 book_depth_usd=book_depth_usd)
        decision = self.evidence.check(benchmark_result)
        reasons: List[str] = []

        if zone is None:
            reasons.append("No usable rebound geometry for this cluster.")
        if not self.execution_enabled:
            reasons.append(
                "WHALE_SWEEP_EXECUTION_ENABLED is False. This thesis was traded, "
                "measured at MFE/MAE %.3f against a %.3f random-entry control, "
                "and retired. It is under passive re-measurement."
                % (RETIREMENT_RATIO, RETIREMENT_CONTROL))
        if not decision.eligible:
            reasons.append("Evidence gate %s: %s" % (decision.status, decision.detail))

        # The bankroll is asked LAST and only when the evidence permits, because
        # a bucket approval on a signal with no edge is not a partial success -
        # printing "approved" next to a retired strategy invites exactly the
        # misreading this module is built to prevent.
        gate_decision = None
        if not reasons:
            gate_decision = self.gate.check(self.notional_usd, perp_leverage=1.0)
            if not gate_decision.approved:
                reasons.append("Bucket %s: %s" % (STRATEGY_WHALE_SWEEP,
                                                  gate_decision.reason))

        return SweepVerdict(coin=coin, zone=zone, evidence=decision,
                            gate=gate_decision, tradeable=not reasons,
                            reasons=reasons)

    def observe(self, coin: str, cluster_price: float, mark_price: float,
                cluster_notional: float = 0.0, timestamp: Optional[float] = None
                ) -> Optional[SweepZone]:
        """
        Record a zone without trading it - the PASSIVE mode the registration names.

        This is how the re-benchmark accumulates its sample. The registration's
        status line is explicit: "sweeps accumulate with execution disabled", and
        that sample is the only route back to trading.
        """
        zone = wick_rebound_zone(coin, cluster_price, mark_price,
                                 cluster_notional=cluster_notional)
        if zone is not None:
            self.observed.append({"timestamp": timestamp, **zone.as_record()})
        return zone

    def scan(self, clusters: Sequence[Dict[str, Any]], mark_price: float,
             coin: str, benchmark_result: Optional[Dict[str, Any]] = None
             ) -> List[SweepVerdict]:
        return [self.evaluate(coin, c["price"], mark_price,
                              cluster_notional=c.get("notional", 0.0),
                              benchmark_result=benchmark_result)
                for c in rank_clusters(clusters, mark_price)]

    def place(self, verdict: SweepVerdict) -> Dict[str, Any]:
        """
        The execution path. Raises unless BOTH gates passed.

        It raises rather than returning None so a caller cannot ignore the
        refusal by not checking a return value - the same reason
        `RiskBreachException` exists for the order executor.
        """
        if not verdict.tradeable:
            raise SweeperDisabled("; ".join(verdict.reasons))
        zone = verdict.zone
        return {"coin": zone.coin, "side": zone.side,
                "limit_price": zone.entry_price, "stop_price": zone.stop_price,
                "take_profit": zone.take_profit,
                "notional_usd": verdict.gate.approved_capital,
                "strategy": STRATEGY_WHALE_SWEEP}


def format_status(sweeper: "WhaleSweeper",
                  benchmark_result: Optional[Dict[str, Any]] = None) -> str:
    """Why the sweeper is not trading, in the form an operator can act on."""
    decision = sweeper.evidence.check(benchmark_result)
    bar = decision.bar or sweeper.evidence.bar
    lines = ["", "HL_SHARK - WHALE CASCADE SWEEPER", "=" * 66,
             "  execution flag        %s"
             % ("ENABLED" if sweeper.execution_enabled else "DISABLED"),
             "  evidence gate         %s" % decision.status,
             "  %s" % decision.detail, "",
             "  RETIREMENT ON RECORD  MFE/MAE %.3f vs %.3f random-entry control"
             % (RETIREMENT_RATIO, RETIREMENT_CONTROL),
             "                        forced liquidations are MOMENTUM drivers;",
             "                        price ran ~2x further against the fade.", "",
             "  REOPENING BAR         >=%d events, >=%d coins, top coin <=%.0f%%,"
             % (bar["min_events"], bar["min_coins"],
                bar["max_single_coin_share"] * 100.0),
             "                        then P(ratio >= %.2f) > %.2f under a"
             % (bar["ratio"], bar["confidence"]),
             "                        CLUSTER bootstrap resampling coins.",
             "  observed zones        %d (passive)" % len(sweeper.observed),
             "=" * 66, ""]
    return "\n".join(lines)
