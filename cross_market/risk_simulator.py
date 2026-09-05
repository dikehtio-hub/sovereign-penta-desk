"""
Item 19 - Multi-desk Monte Carlo risk-of-ruin simulator (Round 58, Directives 58-1 / 58-2).

One joint simulation of the trading bankroll across the desks that share it:

  Desk 1  HyperLiquid basis book   long spot / short perp, 1x per leg. The funding level starts
                                   at the book's measured mean and decays toward a long-run APR
                                   with a half-life (a para coin printing 2,900% APR at entry
                                   does not keep it); hourly AR(1) noise (std and persistence
                                   measured from hyperliquid_data.db) rides on top, so negative
                                   streaks happen. The short perp leg is marked with
                                   fat-tailed (Student-t) daily moves; an adverse move past
                                   1/leverage - maintenance before the next rebalance is a
                                   liquidation and costs a slice of the position's capital.
  Desk 2  Sports desk              quarter-Kelly wagers on fair-value edges: each wager draws a
                                   win probability from the desk's distribution, stakes the
                                   fractional Kelly of that edge at the offered odds (capped),
                                   and settles as a Bernoulli.
  Desk 3  Cross-market arb         Poisson arrivals of arbs of a fixed capital; a leg failure
                                   leaves a naked leg that loses a uniform slice, otherwise the
                                   gross arb return is banked.
  Desk 5  Tax reserve              at each quarter end the composite rate (federal short-term +
                                   state + buffer, NJ 32.37%) of the quarter's POSITIVE net gain
                                   is escrowed out of the trading bankroll.

Desk 4 (Quant Trading Lab) is outside this repo and outside the directive.

Paths are simulated day by day with numpy; only running equity, peak, drawdown and the ruin
flags are kept, never full paths, so 100,000 iterations over 365 days fit in memory. Every
input comes with a provenance label - "measured (<source>)" or "assumed" - and the report
prints them, because a risk number is only as honest as its inputs.

Ruin is reported two ways: HARD ruin (equity <= 0, as directed) and PRACTICAL ruin (a
drawdown of `ruin_fraction`, default 50%, from the starting equity) - a spot-backed basis
book plus quarter-Kelly wagers almost never reaches zero, and a probability that always
reads 0.000 would teach nothing.

The Kelly shrinkage is the single multiplier on every desk's sizing (basis capital per
position, sports Kelly fraction, arb capital) that maximises the median log growth of
terminal equity subject to practical ruin <= RUIN_TOLERANCE, chosen from SHRINKAGE_GRID
and reported with the whole grid.

Offline. Hermetic under a seed. `--assume-defaults` skips every live file.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

DEV_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PAPER_STATE = DEV_ROOT / "HyperLiquid" / "HL_Monarch" / "data" / "basis_paper_state.json"
DEFAULT_HL_DB = DEV_ROOT / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"
DEFAULT_SPORTS_DB = DEV_ROOT / "Sports_Desk" / "data" / "sports_market.db"
DEFAULT_VAULT = DEV_ROOT / "obsidian_vault"
RISK_NOTE = "Risk_Sentinel"
HOURS_PER_YEAR = 24 * 365
SHRINKAGE_GRID = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
RUIN_TOLERANCE = 0.05
DEFAULT_ITERATIONS = 100_000
DEFAULT_GRID_ITERATIONS = 20_000
MDD_SHORT_HORIZON_DAYS = 30


@dataclass
class RiskInputs:
    """Every knob of the joint simulation. Sizing knobs are what the shrinkage multiplies."""
    equity: float = 100_000.0
    horizon_days: int = 365
    # Desk 1 - HyperLiquid basis book
    basis_positions: int = 2
    basis_capital_per_position: float = 20_000.0    # both legs
    basis_funding_apr: float = 20.0                  # % - the book's CURRENT mean hourly funding, annualised
    basis_funding_long_run_apr: float = 25.0         # % - where funding settles (the harvester's entry gate)
    basis_funding_half_life_days: float = 7.0        # days for the excess over long-run to halve; 0 = constant
    basis_funding_hourly_std: float = 2.2e-5
    basis_funding_autocorr: float = 0.8              # hourly AR(1) persistence
    basis_daily_vol: float = 0.12
    basis_tail_df: float = 3.0                       # Student-t degrees of freedom for perp moves
    basis_leverage: float = 1.0
    basis_maintenance_margin: float = 0.05
    basis_rebalance_days: int = 1
    basis_liquidation_cost: float = 0.03             # of the position's capital, per liquidation
    # Desk 2 - Sports desk
    sports_bankroll_fraction: float = 0.10           # of equity, the sports bankroll
    sports_bets_per_day: int = 3
    sports_win_prob_mean: float = 0.535
    sports_win_prob_std: float = 0.03
    sports_decimal_odds: float = 1.95
    sports_kelly_fraction: float = 0.25              # quarter Kelly
    sports_max_stake_fraction: float = 0.02          # of the sports bankroll, per wager
    # Desk 3 - Cross-market arb
    arb_per_day: float = 1.0                         # Poisson rate
    arb_capital: float = 1_000.0
    arb_gross_return: float = 0.015
    arb_return_std: float = 0.005
    arb_leg_fail_prob: float = 0.05
    arb_desync_loss_max: float = 0.08                # uniform(0, max) of the arb capital
    # Desk 5 - Tax reserve
    tax_rate: float = 0.3237
    tax_quarter_days: int = 91
    # Systemic stress (Round 59, Directive 59-2): joint shock days. 0 = off.
    stress_correlation: float = 0.0                  # 0..1 - how hard the desks co-move on a shock day
    stress_day_prob: float = 0.02                    # probability a day is a systemic shock day (~7/yr)
    stress_vol_multiplier: float = 3.0               # perp vol on a shock day at correlation 1
    # Ruin
    ruin_fraction: float = 0.5
    provenance: Dict[str, str] = field(default_factory=dict)

    def scaled(self, multiplier: float) -> "RiskInputs":
        """The same book with every desk's sizing multiplied; risk parameters untouched."""
        return replace(self, basis_capital_per_position=self.basis_capital_per_position * multiplier,
                       sports_kelly_fraction=self.sports_kelly_fraction * multiplier,
                       arb_capital=self.arb_capital * multiplier, provenance=dict(self.provenance))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskInputs":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in (data or {}).items() if k in known}
        prov = dict(clean.pop("provenance", {}) or {})
        inputs = cls(**clean)
        inputs.provenance = prov
        return inputs


def _percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q)) if values.size else 0.0


def simulate(inputs: RiskInputs, iterations: int = DEFAULT_ITERATIONS, seed: int = 7) -> Dict[str, Any]:
    """
    Joint day-by-day simulation. Returns ruin probabilities (hard and practical, at
    30 days and at the horizon), max-drawdown VaR (95/99, 30d and horizon), terminal
    equity percentiles, median log growth, escrow, per-desk mean P&L, and the
    liquidation count per path. Deterministic for a given seed.
    """
    rng = np.random.default_rng(seed)
    n = max(1, int(iterations))
    horizon = max(1, int(inputs.horizon_days))
    short_h = min(MDD_SHORT_HORIZON_DAYS, horizon)
    start = float(inputs.equity)

    equity = np.full(n, start)
    peak = equity.copy()
    mdd = np.zeros(n)
    mdd_short = np.zeros(n)
    hard = np.zeros(n, dtype=bool)
    practical = np.zeros(n, dtype=bool)
    hard_short = np.zeros(n, dtype=bool)
    practical_short = np.zeros(n, dtype=bool)
    quarter = np.zeros(n)
    escrow = np.zeros(n)
    liquidations = np.zeros(n)
    desk = {"basis": np.zeros(n), "sports": np.zeros(n), "arb": np.zeros(n), "tax": np.zeros(n)}

    # Desk 1 constants
    positions = max(0, int(inputs.basis_positions))
    capital_basis = positions * float(inputs.basis_capital_per_position)
    short_notional = capital_basis / 2.0                            # the perp leg is half of each position
    mu_h = float(inputs.basis_funding_apr) / 100.0 / HOURS_PER_YEAR
    long_run_h = float(inputs.basis_funding_long_run_apr) / 100.0 / HOURS_PER_YEAR
    half_life = float(inputs.basis_funding_half_life_days)
    decay = 0.5 ** (1.0 / half_life) if half_life > 0 else 1.0
    level_h = mu_h                                                   # today's mean hourly funding
    rho = min(max(float(inputs.basis_funding_autocorr), 0.0), 0.999)
    sigma_h = max(float(inputs.basis_funding_hourly_std), 0.0)
    var24 = sigma_h ** 2 * (24 + 2 * sum((24 - k) * rho ** k for k in range(1, 24)))
    sd24 = math.sqrt(var24)
    df = float(inputs.basis_tail_df)
    daily_vol = max(float(inputs.basis_daily_vol), 0.0)
    tscale = daily_vol * math.sqrt((df - 2.0) / df) if df > 2.0 else daily_vol
    leverage = max(float(inputs.basis_leverage), 1e-9)
    liq_move = max(1.0 / leverage - float(inputs.basis_maintenance_margin), 0.0)
    rebalance = int(inputs.basis_rebalance_days)
    move = np.zeros(n)
    # Desk 2 constants
    b = max(float(inputs.sports_decimal_odds) - 1.0, 1e-9)
    bets = max(0, int(inputs.sports_bets_per_day))
    # Desk 3 constants
    arb_rate = max(float(inputs.arb_per_day), 0.0)
    # Systemic stress: the shock mask is drawn every day whatever the correlation, so a
    # zero-correlation run is bit-identical to an unstressed one under the same seed.
    corr = min(max(float(inputs.stress_correlation), 0.0), 1.0)
    shock_prob = min(max(float(inputs.stress_day_prob), 0.0), 1.0)
    vol_boost = 1.0 + corr * (max(float(inputs.stress_vol_multiplier), 1.0) - 1.0)
    shock_days = np.zeros(n)
    ruin_level = start * (1.0 - float(inputs.ruin_fraction))
    quarter_days = int(inputs.tax_quarter_days)

    for day in range(horizon):
        alive = equity > 0.0
        shock = rng.random(n) < shock_prob
        shock_days += shock
        hit = shock * corr                                               # 0 on calm days, corr on shock days
        # ---- Desk 1: funding income and fat-tailed perp moves against the short leg
        if positions > 0 and capital_basis > 0:
            # The level decays from the measured mean toward the long-run APR (a para coin can
            # print a four-digit APR for a day; it does not keep it), the AR(1) noise rides on top.
            # On a shock day funding compresses toward zero and flips negative at full correlation,
            # while the perp leg's vol is multiplied - the two things a squeeze does to a short.
            base_funding = rng.normal(24.0 * level_h, sd24, n)
            funding = short_notional * (base_funding * (1.0 - hit) - hit * 24.0 * abs(level_h))
            level_h = long_run_h + (level_h - long_run_h) * decay
            move = move + rng.standard_t(df, n) * tscale * np.where(shock, vol_boost, 1.0)
            liq = move >= liq_move
            cost = np.where(liq, capital_basis * float(inputs.basis_liquidation_cost), 0.0)
            liquidations += liq
            move = np.where(liq, 0.0, move)
            if rebalance > 0 and (day + 1) % rebalance == 0:
                move = np.zeros(n)
            pnl_basis = funding - cost
        else:
            pnl_basis = np.zeros(n)
        # ---- Desk 2: quarter-Kelly wagers on the desk's edge distribution
        pnl_sports = np.zeros(n)
        if bets > 0 and inputs.sports_bankroll_fraction > 0:
            bank = np.maximum(equity, 0.0) * float(inputs.sports_bankroll_fraction)
            for _ in range(bets):
                p = np.clip(rng.normal(inputs.sports_win_prob_mean, inputs.sports_win_prob_std, n), 0.05, 0.95)
                frac = np.clip(float(inputs.sports_kelly_fraction) * (p * b - (1.0 - p)) / b,
                               0.0, float(inputs.sports_max_stake_fraction))
                stake = frac * bank
                win = rng.random(n) < p
                pnl_sports += np.where(win, stake * b, -stake)
        # ---- Desk 3: Poisson arb arrivals, leg failures leave a naked leg
        pnl_arb = np.zeros(n)
        if arb_rate > 0 and inputs.arb_capital > 0:
            counts = rng.poisson(arb_rate, n)
            for m in range(int(counts.max())):
                active = counts > m
                fail = rng.random(n) < float(inputs.arb_leg_fail_prob) * (1.0 + hit)   # doubles at corr 1
                gross = rng.normal(inputs.arb_gross_return, inputs.arb_return_std, n) * float(inputs.arb_capital)
                loss = -rng.uniform(0.0, float(inputs.arb_desync_loss_max), n) * float(inputs.arb_capital)
                pnl_arb += np.where(active, np.where(fail, loss, gross), 0.0)
        day_pnl = (pnl_basis + pnl_sports + pnl_arb) * alive
        desk["basis"] += pnl_basis * alive
        desk["sports"] += pnl_sports * alive
        desk["arb"] += pnl_arb * alive
        equity = equity + day_pnl
        quarter += day_pnl
        # ---- Desk 5: quarterly escrow of the composite rate on positive net gains
        if quarter_days > 0 and (day + 1) % quarter_days == 0:
            tax = float(inputs.tax_rate) * np.maximum(quarter, 0.0) * alive
            equity = equity - tax
            escrow += tax
            desk["tax"] -= tax
            quarter = np.zeros(n)
        hard |= equity <= 0.0
        equity = np.maximum(equity, 0.0)
        practical |= equity <= ruin_level
        peak = np.maximum(peak, equity)
        dd = np.where(peak > 0, (peak - equity) / np.where(peak > 0, peak, 1.0), 1.0)
        mdd = np.maximum(mdd, dd)
        if day < short_h:
            mdd_short = np.maximum(mdd_short, dd)
            hard_short = hard.copy()
            practical_short = practical.copy()

    log_growth = np.log(np.maximum(equity, 1e-9) / start)
    return {
        "iterations": n, "horizon_days": horizon, "short_horizon_days": short_h, "seed": int(seed),
        "start_equity": start, "ruin_fraction": float(inputs.ruin_fraction),
        "ruin": {
            "hard_horizon": float(hard.mean()), "practical_horizon": float(practical.mean()),
            "hard_short": float(hard_short.mean()), "practical_short": float(practical_short.mean()),
        },
        "max_drawdown": {
            "var95_short": _percentile(mdd_short, 95), "var99_short": _percentile(mdd_short, 99),
            "var95_horizon": _percentile(mdd, 95), "var99_horizon": _percentile(mdd, 99),
            "median_horizon": _percentile(mdd, 50),
        },
        "terminal_equity": {
            "p05": _percentile(equity, 5), "p50": _percentile(equity, 50), "p95": _percentile(equity, 95),
            "mean": float(equity.mean()),
        },
        "median_log_growth": float(np.median(log_growth)),
        "escrow": {"median": _percentile(escrow, 50), "mean": float(escrow.mean())},
        "desk_mean_pnl": {k: float(v.mean()) for k, v in desk.items()},
        "liquidations_per_path": float(liquidations.mean()),
        "stress": {"correlation": corr, "day_prob": shock_prob, "vol_multiplier": float(inputs.stress_vol_multiplier),
                   "shock_days_per_path": float(shock_days.mean())},
    }


def stress_impact(inputs: RiskInputs, iterations: int = DEFAULT_ITERATIONS, seed: int = 7,
                  stressed: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Baseline (correlation 0) vs the stressed book, same paths and seed: what the joint
    shock days do to VaR99, practical ruin, the cash buffer and the desk P&Ls. None when
    stress is off.
    """
    if float(inputs.stress_correlation) <= 0.0:
        return None
    stressed = stressed or simulate(inputs, iterations=iterations, seed=seed)
    baseline = simulate(replace(inputs, stress_correlation=0.0, provenance=dict(inputs.provenance)),
                        iterations=iterations, seed=seed)

    def pick(res: Dict[str, Any]) -> Dict[str, float]:
        return {
            "var99_short": res["max_drawdown"]["var99_short"], "var99_horizon": res["max_drawdown"]["var99_horizon"],
            "var95_horizon": res["max_drawdown"]["var95_horizon"],
            "practical_ruin": res["ruin"]["practical_horizon"], "hard_ruin": res["ruin"]["hard_horizon"],
            "buffer_usd": res["start_equity"] * res["max_drawdown"]["var99_horizon"],
            "terminal_p50": res["terminal_equity"]["p50"], "basis_pnl": res["desk_mean_pnl"]["basis"],
            "arb_pnl": res["desk_mean_pnl"]["arb"], "liquidations_per_path": res["liquidations_per_path"],
        }

    b, st = pick(baseline), pick(stressed)
    return {"correlation": stressed["stress"]["correlation"], "day_prob": stressed["stress"]["day_prob"],
            "vol_multiplier": stressed["stress"]["vol_multiplier"],
            "shock_days_per_path": stressed["stress"]["shock_days_per_path"],
            "baseline": b, "stressed": st, "delta": {k: st[k] - b[k] for k in b}}


def allocation_fraction(inputs: RiskInputs) -> float:
    """Capital the desks would hold at once, as a fraction of equity: basis capital, sports bankroll, one arb."""
    if inputs.equity <= 0:
        return float("inf")
    deployed = (max(0, int(inputs.basis_positions)) * float(inputs.basis_capital_per_position)
                + float(inputs.sports_bankroll_fraction) * float(inputs.equity)
                + (float(inputs.arb_capital) if inputs.arb_per_day > 0 else 0.0))
    return deployed / float(inputs.equity)


def kelly_shrinkage(inputs: RiskInputs, iterations: int = DEFAULT_GRID_ITERATIONS, seed: int = 7,
                    grid: Sequence[float] = SHRINKAGE_GRID, tolerance: float = RUIN_TOLERANCE) -> Dict[str, Any]:
    """
    The sizing multiplier that maximises median log growth with practical ruin at the
    horizon <= tolerance AND the desks' capital fitting inside the equity (allocation
    <= 100%): a spot-backed basis book cannot be ruined in this model, so without the
    allocation bound the grid would always point at its top. When no multiplier is
    feasible, the one with the least ruin among those that fit, else the least ruin.
    """
    rows = []
    for multiplier in grid:
        scaled = inputs.scaled(float(multiplier))
        res = simulate(scaled, iterations=iterations, seed=seed)
        rows.append({
            "multiplier": float(multiplier),
            "median_log_growth": res["median_log_growth"],
            "practical_ruin": res["ruin"]["practical_horizon"],
            "hard_ruin": res["ruin"]["hard_horizon"],
            "var95_horizon": res["max_drawdown"]["var95_horizon"],
            "terminal_p50": res["terminal_equity"]["p50"],
            "allocation": allocation_fraction(scaled),
        })
    fits = [r for r in rows if r["allocation"] <= 1.0]
    feasible = [r for r in fits if r["practical_ruin"] <= tolerance]
    if feasible:
        best = max(feasible, key=lambda r: (r["median_log_growth"], -r["multiplier"]))
        top_fit = max(fits, key=lambda r: r["multiplier"])
        # When every multiplier that fits the equity is also inside the ruin tolerance and the
        # pick is the largest of them, ruin never bound: the answer is "risk is not the limit",
        # not "add leverage". Say which constraint decided.
        binding = "allocation" if (best["multiplier"] == top_fit["multiplier"]
                                   and all(r["practical_ruin"] <= tolerance for r in fits)) else "ruin"
    else:
        best = min(fits or rows, key=lambda r: (r["practical_ruin"], r["multiplier"]))
        binding = "none"
    return {"grid": rows, "recommended_multiplier": best["multiplier"], "feasible": bool(feasible),
            "binding": binding, "tolerance": float(tolerance), "iterations": int(iterations)}


BINDING_TEXT = {
    "allocation": "capital allocation - ruin never bound at any size that fits the equity, so the pick means "
                  "'risk is not the limit', not 'add leverage'",
    "ruin": "the practical-ruin tolerance",
    "none": "none satisfied - no multiplier that fits the equity stays inside the ruin tolerance",
}


# ------------------------------------------------------------------ live inputs

def _measure_funding_and_vol(hl_db: Path, coins: Sequence[str]):
    """(hourly funding mean, std, autocorr, daily vol, hours) from the snapshot DB for `coins`; None when thin."""
    con = sqlite3.connect("file:%s?mode=ro" % Path(hl_db).as_posix(), uri=True)
    try:
        means, stds, rhos, vols, hours = [], [], [], [], 0
        for coin in coins:
            rows = con.execute("SELECT timestamp, funding_rate, mark_px FROM asset_snapshots WHERE coin=? "
                               "ORDER BY timestamp", (coin,)).fetchall()
            hourly: Dict[int, tuple] = {}
            for ts, fr, px in rows:
                hourly.setdefault(int(ts) // 3_600_000, (fr, px))
            series = [hourly[k] for k in sorted(hourly)]
            if len(series) < 24:
                continue
            fr = np.array([float(v[0]) for v in series if v[0] is not None], dtype=float)
            px = np.array([float(v[1]) for v in series if v[1] is not None and float(v[1]) > 0], dtype=float)
            if fr.size >= 24:
                means.append(float(fr.mean()))
                stds.append(float(fr.std()))
                centred = fr - fr.mean()
                denom = float((centred ** 2).sum())
                rhos.append(float((centred[1:] * centred[:-1]).sum() / denom) if denom > 0 else 0.0)
            if px.size >= 24:
                rets = np.diff(np.log(px))
                vols.append(float(rets.std() * math.sqrt(24.0)))
            hours = max(hours, len(series))
        if not stds and not vols:
            return None
        return (float(np.mean(means)) if means else None, float(np.mean(stds)) if stds else None,
                float(np.clip(np.mean(rhos), 0.0, 0.99)) if rhos else None,
                float(np.mean(vols)) if vols else None, hours)
    finally:
        con.close()


def _measure_sports_edges(sports_db: Path):
    """(win-prob mean, std, mean decimal odds, rows) from edge_opportunities' positive-Kelly rows; None when empty."""
    con = sqlite3.connect("file:%s?mode=ro" % Path(sports_db).as_posix(), uri=True)
    try:
        rows = con.execute("SELECT sharp_fair_prob, retail_offered_odds FROM edge_opportunities "
                           "WHERE sharp_fair_prob IS NOT NULL AND retail_offered_odds IS NOT NULL").fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    kept = [(float(p), float(o)) for p, o in rows if 0.0 < float(p) < 1.0 and float(o) > 1.0
            and (float(p) * (float(o) - 1.0) - (1.0 - float(p))) > 0.0]
    if not kept:
        return None
    probs = np.array([p for p, _ in kept])
    odds = np.array([o for _, o in kept])
    return float(probs.mean()), float(probs.std()), float(odds.mean()), len(kept)


def _tax_rate_from_config() -> Optional[float]:
    try:
        from Tax_Reserve_Agent import config as tax_config
    except Exception:                                       # noqa: BLE001
        return None
    for name in dir(tax_config):
        value = getattr(tax_config, name)
        if isinstance(value, dict) and isinstance(value.get("tax_rates"), dict):
            rates = value["tax_rates"]
            try:
                return (float(rates.get("short_term_capital_gains", 0.24)) + float(rates.get("state_tax_rate", 0.0))
                        + float(rates.get("safety_buffer_pct", 0.0)))
            except (TypeError, ValueError):
                return None
    return None


def load_live_inputs(paper_state: Path = DEFAULT_PAPER_STATE, hl_db: Path = DEFAULT_HL_DB,
                     sports_db: Path = DEFAULT_SPORTS_DB, use_tax_config: bool = True) -> RiskInputs:
    """
    RiskInputs from the live files, every field labelled. Missing or thin sources fall
    back to the dataclass defaults, labelled "assumed". Never raises.
    """
    inputs = RiskInputs()
    prov: Dict[str, str] = {}
    coins: List[str] = []
    aprs: List[float] = []
    try:
        state = json.loads(Path(paper_state).read_text(encoding="utf-8"))
        positions = state.get("positions") or {}
        caps = [float(p.get("capital") or 0.0) for p in positions.values() if isinstance(p, dict)]
        aprs = [float(p.get("entry_funding_apr")) for p in positions.values()
                if isinstance(p, dict) and p.get("entry_funding_apr") is not None]
        coins = [str(p.get("coin") or k) for k, p in positions.items() if isinstance(p, dict)]
        inputs.equity = float(state.get("cash") or 0.0) + sum(caps)
        inputs.basis_positions = len(caps)
        source = "measured (%s)" % Path(paper_state).name
        prov.update(equity=source, basis_positions=source)
        if caps:
            inputs.basis_capital_per_position = float(np.mean(caps))
            prov["basis_capital_per_position"] = source
        if aprs:
            # The entry APR is what the book was opened at, not a year-long mean: a para coin can
            # print a four-digit APR for a day. It seeds the estimate and is replaced by the
            # snapshot DB's measured mean below whenever that exists.
            inputs.basis_funding_apr = float(np.mean(aprs))
            prov["basis_funding_apr"] = source + " entry APR %.1f%% (no DB history)" % float(np.mean(aprs))
    except Exception:                                       # noqa: BLE001 - no book: defaults
        prov.update(equity="assumed", basis_positions="assumed")
    measured = None
    try:
        measured = _measure_funding_and_vol(hl_db, coins or ["BTC"])
    except Exception:                                       # noqa: BLE001
        measured = None
    if measured:
        mean_h, std, rho, vol, hours = measured
        source = "measured (%s, %s, %dh)" % (Path(hl_db).name, ", ".join(coins or ["BTC"]), hours)
        if mean_h is not None:
            entry = " - book entry APR %.1f%%" % float(np.mean(aprs)) if aprs else ""
            inputs.basis_funding_apr = float(mean_h) * HOURS_PER_YEAR * 100.0
            prov["basis_funding_apr"] = source + entry
        if std is not None:
            inputs.basis_funding_hourly_std, prov["basis_funding_hourly_std"] = std, source
        if rho is not None:
            inputs.basis_funding_autocorr, prov["basis_funding_autocorr"] = rho, source
        if vol is not None:
            inputs.basis_daily_vol, prov["basis_daily_vol"] = vol, source
    for name in ("basis_funding_hourly_std", "basis_funding_autocorr", "basis_daily_vol"):
        prov.setdefault(name, "assumed")
    edges = None
    try:
        edges = _measure_sports_edges(sports_db)
    except Exception:                                       # noqa: BLE001
        edges = None
    if edges:
        pm, ps, odds, rows = edges
        source = "measured (%s edge_opportunities, %d positive-Kelly rows)" % (Path(sports_db).name, rows)
        inputs.sports_win_prob_mean, inputs.sports_win_prob_std, inputs.sports_decimal_odds = pm, ps, odds
        prov.update(sports_win_prob_mean=source, sports_win_prob_std=source, sports_decimal_odds=source)
    else:
        prov.update(sports_win_prob_mean="assumed", sports_win_prob_std="assumed", sports_decimal_odds="assumed")
    rate = _tax_rate_from_config() if use_tax_config else None
    if rate is not None:
        inputs.tax_rate, prov["tax_rate"] = rate, "measured (Tax_Reserve_Agent.config)"
    else:
        prov["tax_rate"] = "assumed"
    for name in ("basis_funding_long_run_apr", "basis_funding_half_life_days",
                 "stress_correlation", "stress_day_prob", "stress_vol_multiplier",
                 "sports_bankroll_fraction", "sports_bets_per_day", "sports_kelly_fraction",
                 "sports_max_stake_fraction", "arb_per_day", "arb_capital", "arb_gross_return",
                 "arb_leg_fail_prob", "arb_desync_loss_max", "basis_leverage", "basis_liquidation_cost",
                 "basis_rebalance_days", "basis_tail_df"):
        prov.setdefault(name, "assumed")
    inputs.provenance = prov
    return inputs


# ------------------------------------------------------------------ reports

def buffer_recommendation(result: Dict[str, Any], shrinkage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Cash to keep unallocated: the VaR99 horizon drawdown in dollars, plus the sizing multiplier."""
    start = float(result["start_equity"])
    var99 = float(result["max_drawdown"]["var99_horizon"])
    multiplier = float(shrinkage["recommended_multiplier"]) if shrinkage else 1.0
    return {"buffer_usd": start * var99, "buffer_fraction": var99, "sizing_multiplier": multiplier,
            "hold_back_fraction": max(0.0, 1.0 - multiplier)}


def format_stress(stress: Optional[Dict[str, Any]], horizon: int) -> List[str]:
    if not stress:
        return ["[RISK] systemic stress: off (--stress-correlation 0)"]
    b, st, d = stress["baseline"], stress["stressed"], stress["delta"]
    return [
        "[RISK] systemic stress: correlation %.2f, shock-day prob %.3f (%.1f days/path), vol x%.1f on shock days"
        % (stress["correlation"], stress["day_prob"], stress["shock_days_per_path"], stress["vol_multiplier"]),
        "[RISK]   VaR99 %dd baseline %.2f%% -> stressed %.2f%% (%+.2f pp); practical ruin %.4f -> %.4f"
        % (horizon, b["var99_horizon"] * 100, st["var99_horizon"] * 100, d["var99_horizon"] * 100,
           b["practical_ruin"], st["practical_ruin"]),
        "[RISK]   buffer $%s -> $%s (%+.0f); basis P&L %+.0f; arb P&L %+.0f; liquidations/path %.3f -> %.3f"
        % ("{:,.0f}".format(b["buffer_usd"]), "{:,.0f}".format(st["buffer_usd"]), d["buffer_usd"], d["basis_pnl"],
           d["arb_pnl"], b["liquidations_per_path"], st["liquidations_per_path"]),
    ]


def format_report(result: Dict[str, Any], inputs: RiskInputs, shrinkage: Optional[Dict[str, Any]] = None,
                  stress: Optional[Dict[str, Any]] = None) -> str:
    r, m, t = result["ruin"], result["max_drawdown"], result["terminal_equity"]
    short = result["short_horizon_days"]
    horizon = result["horizon_days"]
    buf = buffer_recommendation(result, shrinkage)
    lines = [
        "[RISK] Item 19 - %d paths x %dd, seed %d, start equity $%s" % (result["iterations"], horizon, result["seed"],
                                                                        "{:,.2f}".format(result["start_equity"])),
        "[RISK] ruin: hard (equity <= 0)  %dd %.4f | %dd %.4f" % (short, r["hard_short"], horizon, r["hard_horizon"]),
        "[RISK] ruin: practical (-%.0f%%)   %dd %.4f | %dd %.4f" % (result["ruin_fraction"] * 100, short,
                                                                    r["practical_short"], horizon, r["practical_horizon"]),
        "[RISK] max drawdown VaR: 95%% %dd %.2f%% | 99%% %dd %.2f%% | 95%% %dd %.2f%% | 99%% %dd %.2f%% (median %dd %.2f%%)"
        % (short, m["var95_short"] * 100, short, m["var99_short"] * 100, horizon, m["var95_horizon"] * 100,
           horizon, m["var99_horizon"] * 100, horizon, m["median_horizon"] * 100),
        "[RISK] terminal equity p05 $%s | p50 $%s | p95 $%s; median log growth %+.4f; escrow median $%s"
        % ("{:,.0f}".format(t["p05"]), "{:,.0f}".format(t["p50"]), "{:,.0f}".format(t["p95"]),
           result["median_log_growth"], "{:,.0f}".format(result["escrow"]["median"])),
        "[RISK] desk mean P&L: basis $%s | sports $%s | arb $%s | tax -$%s; liquidations/path %.3f"
        % ("{:,.0f}".format(result["desk_mean_pnl"]["basis"]), "{:,.0f}".format(result["desk_mean_pnl"]["sports"]),
           "{:,.0f}".format(result["desk_mean_pnl"]["arb"]), "{:,.0f}".format(-result["desk_mean_pnl"]["tax"]),
           result["liquidations_per_path"]),
    ]
    if shrinkage:
        lines.append("[RISK] Kelly shrinkage grid (practical ruin <= %.0f%%, %d paths each):"
                     % (shrinkage["tolerance"] * 100, shrinkage["iterations"]))
        for row in shrinkage["grid"]:
            mark = " <- recommended" if row["multiplier"] == shrinkage["recommended_multiplier"] else ""
            over = "" if row["allocation"] <= 1.0 else "  (over-allocated)"
            lines.append("[RISK]   x%.2f  growth %+.4f  practical ruin %.4f  hard %.4f  VaR95 %.2f%%  allocation %.0f%%%s%s"
                         % (row["multiplier"], row["median_log_growth"], row["practical_ruin"], row["hard_ruin"],
                            row["var95_horizon"] * 100, row["allocation"] * 100, over, mark))
        if not shrinkage["feasible"]:
            lines.append("[RISK]   no multiplier meets the ruin tolerance inside the equity - the least-ruin one is recommended")
        lines.append("[RISK]   binding constraint: %s" % BINDING_TEXT.get(shrinkage.get("binding"), "unknown"))
    lines.append("[RISK] buffer: keep $%s unallocated (VaR99 %dd drawdown = %.1f%% of equity); size every desk at x%.2f"
                 % ("{:,.0f}".format(buf["buffer_usd"]), horizon, buf["buffer_fraction"] * 100, buf["sizing_multiplier"]))
    lines.extend(format_stress(stress, horizon))
    measured = sorted(k for k, v in inputs.provenance.items() if v.startswith("measured"))
    assumed = sorted(k for k, v in inputs.provenance.items() if v == "assumed")
    lines.append("[RISK] inputs measured: %s" % (", ".join(measured) or "none"))
    lines.append("[RISK] inputs assumed:  %s" % (", ".join(assumed) or "none"))
    return "\n".join(lines)


def render_stress_section(stress: Optional[Dict[str, Any]], horizon: int) -> str:
    if not stress:
        return ("_Systemic stress is off_ (`--stress-correlation 0`). Turn it on to see joint shock days: perp vol "
                "spikes, funding compresses and flips, arb leg failures double, all on the same day.")
    b, st, d = stress["baseline"], stress["stressed"], stress["delta"]
    return (
        "Correlation `%.2f`, shock-day probability `%.3f` (`%.1f` days per path), perp vol `x%.1f` on shock days; "
        "sports wagers are unaffected (nothing links them to a crypto squeeze).\n\n"
        "| Metric | Baseline | Stressed | Δ |\n| :--- | :---: | :---: | :---: |\n"
        "| VaR99 max drawdown %dd | `%.2f%%` | `%.2f%%` | `%+.2f pp` |\n"
        "| VaR95 max drawdown %dd | `%.2f%%` | `%.2f%%` | `%+.2f pp` |\n"
        "| Practical ruin %dd | `%.2f%%` | `%.2f%%` | `%+.2f pp` |\n"
        "| Recommended cash buffer | `$%s` | `$%s` | `%+.0f` |\n"
        "| Basis desk P&L | `$%s` | `$%s` | `%+.0f` |\n"
        "| Arb desk P&L | `$%s` | `$%s` | `%+.0f` |\n"
        "| Liquidations per path | `%.3f` | `%.3f` | `%+.3f` |"
        % (stress["correlation"], stress["day_prob"], stress["shock_days_per_path"], stress["vol_multiplier"],
           horizon, b["var99_horizon"] * 100, st["var99_horizon"] * 100, d["var99_horizon"] * 100,
           horizon, b["var95_horizon"] * 100, st["var95_horizon"] * 100, d["var95_horizon"] * 100,
           horizon, b["practical_ruin"] * 100, st["practical_ruin"] * 100, d["practical_ruin"] * 100,
           "{:,.0f}".format(b["buffer_usd"]), "{:,.0f}".format(st["buffer_usd"]), d["buffer_usd"],
           "{:,.0f}".format(b["basis_pnl"]), "{:,.0f}".format(st["basis_pnl"]), d["basis_pnl"],
           "{:,.0f}".format(b["arb_pnl"]), "{:,.0f}".format(st["arb_pnl"]), d["arb_pnl"],
           b["liquidations_per_path"], st["liquidations_per_path"], d["liquidations_per_path"]))


def render_note(result: Dict[str, Any], inputs: RiskInputs, shrinkage: Optional[Dict[str, Any]],
                now: Optional[datetime] = None, stress: Optional[Dict[str, Any]] = None) -> str:
    """The Risk_Sentinel.md card."""
    now = now or datetime.now(timezone.utc)
    synced = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    r, m, t = result["ruin"], result["max_drawdown"], result["terminal_equity"]
    short, horizon = result["short_horizon_days"], result["horizon_days"]
    buf = buffer_recommendation(result, shrinkage)
    grid_rows = "\n".join(
        "| `x%.2f` | `%+.4f` | `%.2f%%` | `%.2f%%` | `%.1f%%` | `%.0f%%` | %s |"
        % (row["multiplier"], row["median_log_growth"], row["practical_ruin"] * 100, row["hard_ruin"] * 100,
           row["var95_horizon"] * 100, row["allocation"] * 100,
           "**recommended**" if row["multiplier"] == shrinkage["recommended_multiplier"]
           else ("over-allocated" if row["allocation"] > 1.0 else ""))
        for row in (shrinkage["grid"] if shrinkage else [])) or "| — | — | — | — | — | — | grid not run |"
    prov_rows = "\n".join("| `%s` | `%s` | %s |" % (k, _fmt_input(getattr(inputs, k, None)), v)
                          for k, v in sorted(inputs.provenance.items()))
    desk = result["desk_mean_pnl"]
    verdict = "SUCCESS" if r["practical_horizon"] <= RUIN_TOLERANCE else "WARNING"
    return f"""---
title: Risk Sentinel - Multi-Desk Monte Carlo
tags:
  - risk
  - monte-carlo
  - risk-of-ruin
  - cross-market
  - dashboard
last_synced: "{synced}"
---

# 🛡 Risk Sentinel - Multi-Desk Monte Carlo (Item 19)

> [!{verdict}] **Practical ruin (-{result['ruin_fraction'] * 100:.0f}%) over {horizon}d: `{r['practical_horizon'] * 100:.2f}%`** · hard ruin `{r['hard_horizon'] * 100:.3f}%`
> - **Last Synchronized**: `{synced}`
> - **Paths**: `{result['iterations']:,}` × `{horizon}` days, seed `{result['seed']}`, start equity `${result['start_equity']:,.2f}`
> - **Buffer**: keep `${buf['buffer_usd']:,.0f}` unallocated (VaR99 {horizon}d drawdown `{buf['buffer_fraction'] * 100:.1f}%`); size every desk at `x{buf['sizing_multiplier']:.2f}`
> - Shell twin: `python -m cross_market.risk_simulator --iterations {result['iterations']} --json`

> **Cockpit Navigation**: [[Monarch_Hub|👑 Master Hub]] • [[HyperLiquid_Monarch|🏛 HyperLiquid]] • [[Sports_Desk|🏈 Sports Desk]] • [[Cross_Market_Arb|⚖️ Cross-Market Arb]] • [[Cross_Market_Titans|🌐 Titans]] • [[Bot_Config|⚙️ Bot Config]]

---

## 📉 Ruin & Drawdown

| Metric | {short}d | {horizon}d |
| :--- | :---: | :---: |
| Hard ruin P(equity ≤ 0) | `{r['hard_short'] * 100:.3f}%` | `{r['hard_horizon'] * 100:.3f}%` |
| Practical ruin P(drawdown ≥ {result['ruin_fraction'] * 100:.0f}%) | `{r['practical_short'] * 100:.2f}%` | `{r['practical_horizon'] * 100:.2f}%` |
| Max drawdown VaR 95 | `{m['var95_short'] * 100:.2f}%` | `{m['var95_horizon'] * 100:.2f}%` |
| Max drawdown VaR 99 | `{m['var99_short'] * 100:.2f}%` | `{m['var99_horizon'] * 100:.2f}%` |
| Median max drawdown | — | `{m['median_horizon'] * 100:.2f}%` |

**Terminal equity** ({horizon}d): p05 `${t['p05']:,.0f}` · p50 `${t['p50']:,.0f}` · p95 `${t['p95']:,.0f}` · median log growth `{result['median_log_growth']:+.4f}` · escrow median `${result['escrow']['median']:,.0f}`

**Desk mean P&L** ({horizon}d): basis `${desk['basis']:,.0f}` · sports `${desk['sports']:,.0f}` · arb `${desk['arb']:,.0f}` · tax `-${-desk['tax']:,.0f}` · liquidations per path `{result['liquidations_per_path']:.3f}`

---

## 🎯 Cross-Desk Kelly Shrinkage

Multiplier on every desk's sizing (basis capital per position, sports Kelly fraction, arb capital); the recommendation maximises median log growth with practical ruin ≤ `{RUIN_TOLERANCE * 100:.0f}%` and the desks' capital fitting inside the equity (allocation ≤ 100%). Tax escrow leaves the trading bankroll and therefore counts as drawdown here.

| Multiplier | Median log growth | Practical ruin | Hard ruin | VaR95 {horizon}d | Allocation | |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
{grid_rows}

**Binding constraint**: {BINDING_TEXT.get(shrinkage.get("binding"), "grid not run") if shrinkage else "grid not run"}.

---

## ⚡ Systemic Stress

{render_stress_section(stress, horizon)}

---

## 🧾 Inputs & Provenance

Desk 4 (Quant Trading Lab) is outside this simulation. `assumed` inputs have no live history yet.

| Input | Value | Provenance |
| :--- | :---: | :--- |
{prov_rows}

---

## 🧭 Model Notes

1. **Basis**: the funding level starts at the book's measured mean and decays toward `basis_funding_long_run_apr` with half-life `basis_funding_half_life_days` (a para coin can print a four-digit APR for a day, not a year); hourly AR(1) noise (std and persistence from the snapshot DB) rides on top, so negative streaks occur. The short perp leg takes Student-t daily moves and is liquidated past `1/leverage - maintenance` before the next rebalance, costing a slice of the position's capital.
2. **Sports**: each wager draws a win probability, stakes the fractional Kelly of that edge at the offered odds (capped per wager), settles as a Bernoulli against a bankroll that is a fraction of equity.
3. **Arb**: Poisson arrivals; a leg failure leaves a naked leg losing a uniform slice, else the gross return is banked.
4. **Tax**: the composite rate of each quarter's positive net gain leaves the trading bankroll as escrow.
"""


def _fmt_input(value: Any) -> str:
    if isinstance(value, float):
        return ("%.6g" % value)
    return str(value)


def write_note(content: str, vault: Path = DEFAULT_VAULT):
    from cross_market.titan_correlator import write_note_if_changed
    return write_note_if_changed(Path(vault) / ("%s.md" % RISK_NOTE), content)


# ------------------------------------------------------------------ CLI

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Item 19 - multi-desk Monte Carlo risk-of-ruin simulator (offline)")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--horizon-days", type=int, default=None, help="default 365 (or the --inputs file's value)")
    parser.add_argument("--ruin-fraction", type=float, default=None, help="practical ruin drawdown (default 0.5)")
    parser.add_argument("--inputs", type=Path, default=None, help="JSON overriding any RiskInputs field")
    parser.add_argument("--assume-defaults", action="store_true", help="skip every live file (hermetic)")
    parser.add_argument("--paper-state", type=Path, default=DEFAULT_PAPER_STATE)
    parser.add_argument("--hl-db", type=Path, default=DEFAULT_HL_DB)
    parser.add_argument("--sports-db", type=Path, default=DEFAULT_SPORTS_DB)
    parser.add_argument("--grid-iterations", type=int, default=DEFAULT_GRID_ITERATIONS)
    parser.add_argument("--no-grid", action="store_true", help="skip the Kelly shrinkage grid")
    parser.add_argument("--stress-correlation", type=float, default=None,
                        help="Round 59: 0..1 joint shock days (perp vol spike, funding compresses/flips, arb leg "
                             "failures double); the report shows baseline vs stressed (default 0 = off)")
    parser.add_argument("--stress-day-prob", type=float, default=None, help="shock-day probability (default 0.02)")
    parser.add_argument("--stress-vol-multiplier", type=float, default=None, help="perp vol on a shock day (default 3)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--no-vault", action="store_true", help="do not write Risk_Sentinel.md")
    args = parser.parse_args(argv)

    if args.assume_defaults:
        inputs = RiskInputs()
        inputs.provenance = {f.name: "assumed" for f in fields(RiskInputs) if f.name != "provenance"}
    else:
        inputs = load_live_inputs(args.paper_state, args.hl_db, args.sports_db)
    if args.inputs:
        overrides = json.loads(Path(args.inputs).read_text(encoding="utf-8"))
        merged = inputs.to_dict()
        merged.update({k: v for k, v in overrides.items() if k != "provenance"})
        prov = dict(inputs.provenance)
        prov.update({k: "override (%s)" % Path(args.inputs).name for k in overrides if k != "provenance"})
        inputs = RiskInputs.from_dict(merged)
        inputs.provenance = prov
    if args.horizon_days is not None:
        inputs.horizon_days = int(args.horizon_days)
    if args.ruin_fraction is not None:
        inputs.ruin_fraction = float(args.ruin_fraction)
    for name, value in (("stress_correlation", args.stress_correlation), ("stress_day_prob", args.stress_day_prob),
                        ("stress_vol_multiplier", args.stress_vol_multiplier)):
        if value is not None:
            setattr(inputs, name, float(value))
            inputs.provenance[name] = "override (cli)"

    result = simulate(inputs, iterations=args.iterations, seed=args.seed)
    stress = stress_impact(inputs, iterations=args.iterations, seed=args.seed, stressed=result)
    shrinkage = None if args.no_grid else kelly_shrinkage(inputs, iterations=min(args.grid_iterations, args.iterations),
                                                          seed=args.seed)
    note_status = "not written (--no-vault)"
    if not args.no_vault:
        path, changed = write_note(render_note(result, inputs, shrinkage, stress=stress), args.vault)
        note_status = "%s %s" % (path, "written" if changed else "unchanged")
    if args.json:
        print(json.dumps({"result": result, "shrinkage": shrinkage, "buffer": buffer_recommendation(result, shrinkage),
                          "stress": stress, "inputs": inputs.to_dict(), "note": note_status}, indent=2))
    else:
        print(format_report(result, inputs, shrinkage, stress))
        print("[RISK] note: %s" % note_status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
