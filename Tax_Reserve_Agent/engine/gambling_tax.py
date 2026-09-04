"""
Gambling tax rules (IRC 61, 165(d), 1402; OBBBA 70114).

Pulled out of `tax_calculator.py` so the statute lives in one readable place and
can be unit-tested on numbers alone, with no SQLite behind it. `tax_calculator`
does the querying; this module does the law.

FOUR THINGS THIS MODULE EXISTS TO GET RIGHT
-------------------------------------------

1. GROSS WINNINGS ARE NOT NET WINNINGS. IRC 61 taxes every winning wager. IRC
   165(d) makes losses a DEDUCTION, and a deduction is only worth something to
   someone who itemises. A bettor who wins $80,000 and loses $79,000 over a year
   and takes the standard deduction owes tax on $80,000. That is the single most
   expensive fact in this file and the default mode enforces it.

   "Winnings" here means proceeds from a wager NET OF THAT WAGER's own stake -
   the Reg. 1.6041-10 measure a W-2G reports, not the gross amount handed back.
   A $100 bet returning $250 is $150 of winnings, not $250.

2. THE 2026 90% HAIRCUT. OBBBA 70114 amended 165(d) for tax years beginning
   after 2025: the deduction is limited to 90% of losses, still capped at
   winnings. Break even at $100k in and $100k out and you now have $10,000 of
   phantom taxable income. This is CONFIGURABLE (`loss_deduction_pct`) and dated
   (`loss_haircut_effective_year`) precisely because it has been the subject of
   repeal attempts - set it to 1.0 for one line and pre-2026 behaviour returns.

3. A W-2G CREDIT IS FEDERAL AND ONLY FEDERAL. The 24% a sportsbook withholds is
   federal income tax. It does not pay state tax, and it certainly does not pay
   this agent's safety buffer. Netting it against a composite rate credits the
   bettor with money nobody sent to their state, and it moves the reserve DOWN -
   the one direction this ledger must never move on an assumption. Credit is
   therefore capped at the federal leg, and any excess is reported as a refund
   receivable rather than silently absorbed.

4. LOSSES CANNOT CREATE A REFUND. Under every mode the taxable base floors at
   zero and the escrow floors at zero. A losing year releases no escrow that
   another bucket is responsible for.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
-----------------------------------------
It does not compute a return. It sizes an ESCROW - money to keep in cash so April
is funded - using flat marginal rates from config. It has no brackets, no AGI
phase-outs, no standard-deduction amount, and no state apportionment. Those turn
a reserve estimator into a tax preparer, and getting them half-right is worse
than not having them.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

STANDARD_DEDUCTION = "casual_standard_deduction"
ITEMIZED = "casual_itemized"
PROFESSIONAL = "professional_schedule_c"
SESSION_NETTING = "session_netting"

TREATMENTS = (STANDARD_DEDUCTION, ITEMIZED, PROFESSIONAL, SESSION_NETTING)

# Credit scopes for Form W-2G withholding.
CREDIT_FEDERAL = "federal"   # correct, and the default
CREDIT_TOTAL = "total"       # Antigravity's original behaviour, kept as an opt-in

DEFAULT_LOSS_DEDUCTION_PCT = 0.90          # OBBBA 70114
DEFAULT_HAIRCUT_EFFECTIVE_YEAR = 2026

# FORM W-2G, Reg. 1.6041-10 and IRC 3402(q). Both tests are CONJUNCTIVE and both
# are measured on PROCEEDS FROM THE WAGER - the amount received MINUS the amount
# wagered - not on the gross payout. A $100 bet returning $700 is $600 of
# proceeds at a 6x multiplier: it clears the dollar test and fails the odds test,
# so no W-2G, which is why nearly every sports bet escapes reporting entirely.
DEFAULT_W2G_REPORTING_THRESHOLD = 600.0        # dollar test for a return
DEFAULT_W2G_MULTIPLIER_THRESHOLD = 300.0       # 300:1 on the wager
DEFAULT_W2G_WITHHOLDING_THRESHOLD = 5000.0     # dollar test for withholding
DEFAULT_MANDATORY_WITHHOLDING_RATE = 0.24      # IRC 3402(q) flat rate

# Self-employment tax, IRC 1401/1402. Only touched in professional mode.
DEFAULT_SECA = {
    "net_earnings_factor": 0.9235,          # 1402(a)(12)
    "social_security_rate": 0.124,
    "medicare_rate": 0.029,
    "social_security_wage_base": 184500.0,  # 2026 estimate - confirm each January
    "deduct_half_se_tax": True,             # 164(f)
}


@dataclass
class GamblingInputs:
    """Dollars measured from the ledger. No policy, no rates."""

    gross_winnings: float = 0.0          # sum of positive per-wager proceeds
    gross_losses: float = 0.0            # POSITIVE magnitude of losing stakes
    net_cash_pnl: float = 0.0            # winnings - losses, as actually banked
    session_winnings: float = 0.0        # sum of positive session nets
    session_losses: float = 0.0          # POSITIVE magnitude of negative session nets
    session_count: int = 0
    expenses: float = 0.0                # professional Schedule C expenses
    w2g_withheld: float = 0.0            # federal tax already paid at the book
    w2g_predicted: float = 0.0           # 3402(q) withholding the book MUST take
                                         # on a settled winner the import did not
                                         # record a withholding tag for


@dataclass
class GamblingRates:
    """Flat marginal rates, split so a federal credit can be applied federally."""

    federal_ordinary: float = 0.28
    state_ordinary: float = 0.05
    safety_buffer: float = 0.02
    self_employment: float = 0.153        # legacy flat rate, used only if seca is off
    federal_rate_is_composite: bool = False   # see `resolve_rates`

    @property
    def total(self) -> float:
        return self.federal_ordinary + self.state_ordinary + self.safety_buffer


@dataclass
class GamblingPolicy:
    """Everything the operator chose, resolved from `config.yaml -> gambling`."""

    treatment: str = STANDARD_DEDUCTION
    state_allows_loss_deduction: bool = True
    # The state's OWN haircut on gambling losses, which is not the federal one.
    # OBBBA 70114 amended IRC 165(d); it did not touch any state code. New Jersey,
    # for instance, nets gambling losses against gambling winnings at 100% within
    # the same year. Defaults to 1.0 - full netting - because applying the federal
    # 90% to a state that never adopted it over-reserves.
    state_loss_deduction_pct: float = 1.0
    track_w2g_withholdings: bool = True
    w2g_credit_scope: str = CREDIT_FEDERAL
    loss_deduction_pct: float = DEFAULT_LOSS_DEDUCTION_PCT
    loss_haircut_effective_year: int = DEFAULT_HAIRCUT_EFFECTIVE_YEAR
    session_netting_itemizes: bool = False
    use_statutory_seca: bool = True
    seca: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SECA))
    w2g_reporting_threshold: float = DEFAULT_W2G_REPORTING_THRESHOLD
    w2g_multiplier_threshold: float = DEFAULT_W2G_MULTIPLIER_THRESHOLD
    w2g_withholding_threshold: float = DEFAULT_W2G_WITHHOLDING_THRESHOLD
    mandatory_withholding_rate: float = DEFAULT_MANDATORY_WITHHOLDING_RATE


@dataclass
class GamblingResult:
    """
    The escrow and every intermediate the operator needs to check it.

    Every field is reported because the failure mode here is not a wrong total,
    it is a right-looking total nobody can reconcile against a 1040 in April.
    """

    treatment: str = STANDARD_DEDUCTION
    gross_winnings: float = 0.0
    gross_losses: float = 0.0
    net_cash_pnl: float = 0.0
    expenses: float = 0.0
    session_winnings: float = 0.0
    session_losses: float = 0.0
    session_count: int = 0

    loss_deduction_pct: float = 1.0
    loss_deduction_allowed: float = 0.0      # losses actually deductible federally
    loss_disallowed: float = 0.0             # losses that produce no deduction at all

    federal_taxable_base: float = 0.0
    state_taxable_base: float = 0.0

    federal_tax: float = 0.0
    state_tax: float = 0.0
    safety_buffer_tax: float = 0.0
    self_employment_tax: float = 0.0
    tax_gross: float = 0.0                   # before any withholding credit

    w2g_withheld: float = 0.0
    w2g_predicted: float = 0.0
    w2g_credit_applied: float = 0.0
    w2g_surplus: float = 0.0                 # overwithheld: a refund, not escrow

    escrow: float = 0.0
    warnings: list = field(default_factory=list)

    def as_summary_fields(self) -> Dict[str, Any]:
        """Flattened with the `gambling_` prefix the HUD and exporters read."""
        data = asdict(self)
        warnings = data.pop("warnings")
        escrow = data.pop("escrow")
        treatment = data.pop("treatment")
        out = {f"gambling_{k}": v for k, v in data.items()}
        out["escrow_gambling"] = escrow
        out["gambling_treatment"] = treatment
        out["gambling_warnings"] = warnings
        return out


def resolve_policy(gambling_cfg: Optional[Dict[str, Any]]) -> GamblingPolicy:
    """Reads `config.yaml -> gambling`, falling back to the conservative defaults."""
    cfg = gambling_cfg or {}
    treatment = str(cfg.get("tax_treatment", STANDARD_DEDUCTION)).strip().lower()
    if treatment not in TREATMENTS:
        print(f"[WARN] Unknown gambling.tax_treatment {treatment!r}; "
              f"falling back to {STANDARD_DEDUCTION} (no loss deduction).")
        treatment = STANDARD_DEDUCTION

    scope = str(cfg.get("w2g_credit_scope", CREDIT_FEDERAL)).strip().lower()
    if scope not in (CREDIT_FEDERAL, CREDIT_TOTAL):
        scope = CREDIT_FEDERAL

    seca = dict(DEFAULT_SECA)
    seca.update({k: float(v) for k, v in (cfg.get("seca") or {}).items()
                 if k != "deduct_half_se_tax"})
    seca["deduct_half_se_tax"] = bool((cfg.get("seca") or {}).get(
        "deduct_half_se_tax", DEFAULT_SECA["deduct_half_se_tax"]))

    return GamblingPolicy(
        treatment=treatment,
        state_allows_loss_deduction=bool(cfg.get("state_allows_loss_deduction", True)),
        state_loss_deduction_pct=float(cfg.get("state_loss_deduction_pct", 1.0)),
        track_w2g_withholdings=bool(cfg.get("track_w2g_withholdings", True)),
        w2g_credit_scope=scope,
        loss_deduction_pct=float(cfg.get("loss_deduction_pct", DEFAULT_LOSS_DEDUCTION_PCT)),
        loss_haircut_effective_year=int(cfg.get("loss_haircut_effective_year",
                                                DEFAULT_HAIRCUT_EFFECTIVE_YEAR)),
        session_netting_itemizes=bool(cfg.get("session_netting_itemizes", False)),
        use_statutory_seca=bool(cfg.get("use_statutory_seca", True)),
        seca=seca,
        # `w2g_threshold_usd` was the original spelling; read it as a fallback so
        # an existing config keeps working rather than silently reverting to the
        # default it happens to equal.
        w2g_reporting_threshold=float(
            cfg.get("w2g_reporting_threshold_usd",
                    cfg.get("w2g_threshold_usd", DEFAULT_W2G_REPORTING_THRESHOLD))),
        w2g_multiplier_threshold=float(
            cfg.get("w2g_odds_multiplier_threshold", DEFAULT_W2G_MULTIPLIER_THRESHOLD)),
        w2g_withholding_threshold=float(
            cfg.get("w2g_mandatory_withholding_threshold_usd",
                    DEFAULT_W2G_WITHHOLDING_THRESHOLD)),
        mandatory_withholding_rate=float(
            cfg.get("mandatory_withholding_rate", DEFAULT_MANDATORY_WITHHOLDING_RATE)),
    )


def resolve_rates(tax_rates: Optional[Dict[str, Any]],
                  gambling_cfg: Optional[Dict[str, Any]]) -> GamblingRates:
    """
    Splits the composite escrow rate into a federal leg and a state leg.

    `tax_rates.short_term_capital_gains` is documented in config.yaml as ALREADY
    being a federal+state composite, which makes it the wrong number to cap a
    federal withholding credit against - it overstates the federal leg and so
    over-credits. `gambling.federal_ordinary_rate` lets the operator state the
    true federal marginal rate; without it we fall back to the composite and say
    so, rather than inventing a split.
    """
    rates = tax_rates or {}
    cfg = gambling_cfg or {}
    # Most specific first: a gambling-only override, then the unbundled rate added
    # in Round 26k, then the pre-26k composite - which is the wrong number and
    # says so.
    explicit_federal = cfg.get("federal_ordinary_rate")
    if explicit_federal is None:
        explicit_federal = rates.get("federal_ordinary_rate")
    fallback_federal = float(rates.get("short_term_capital_gains", 0.24))
    return GamblingRates(
        federal_rate_is_composite=explicit_federal is None,
        federal_ordinary=float(explicit_federal if explicit_federal is not None
                               else fallback_federal),
        state_ordinary=float(cfg.get("state_ordinary_rate")
                             if cfg.get("state_ordinary_rate") is not None
                             else rates.get("state_tax_rate", 0.05)),
        safety_buffer=float(rates.get("safety_buffer_pct", 0.02)),
        self_employment=float(cfg.get("self_employment_tax_rate", 0.153)),
    )


@dataclass(frozen=True)
class W2GAssessment:
    """Whether one settled wager triggers a Form W-2G, and for how much."""

    profit: float               # proceeds from the wager: received minus staked
    wager: float
    multiplier: float           # profit / wager, the 300:1 test
    reportable: bool            # the book must issue a W-2G
    withholding_required: bool  # the book must withhold at source
    withholding: float          # dollars the payout will arrive short by

    def note(self) -> str:
        """Tag written into `transactions.notes` at ingestion."""
        parts = []
        if self.reportable:
            parts.append("w2g_reportable:true")
        if self.withholding_required:
            parts.append(f"w2g_withholding_predicted:{self.withholding:.2f}")
        return ";".join(parts)


def assess_w2g(profit: float, wager: float,
               policy: Optional[GamblingPolicy] = None,
               promo_stake: float = 0.0) -> W2GAssessment:
    """
    Applies both statutory tests to one settled wager.

    BOTH TESTS ARE CONJUNCTIVE, and that is the whole reason most sports betting
    never generates a W-2G. Reg. 1.6041-10 requires proceeds of $600 or more AND
    at least 300 times the wager; IRC 3402(q) requires withholding at 24% when
    proceeds exceed $5,000 AND the same 300:1 test is met. A $2,000 winner on a
    $1,000 bet clears the dollar test twice over and fails the odds test at 2:1,
    so nothing is reported and nothing is withheld.

    MEASURED ON PROCEEDS, NOT PAYOUT. "The amount of the proceeds from a wager"
    is what is received minus what was staked, so a $100 ticket returning $700 is
    $600 of proceeds at 6x - not $700 at 7x.

    THE EFFECTIVE STAKE IS THE CASH SIDE WHERE THERE IS ONE. A $75 cash + $25
    bonus ticket is measured against the $75 the bettor actually risked; a wholly
    promotional ticket falls back to the promo amount, which is what the book
    prints on the slip and reports against. Only a ticket with NO stake at all on
    either side has an unbounded multiplier - and then the dollar test alone
    decides, which is the conservative reading.

    That matters because dividing by the TOTAL would understate the multiplier on
    a part-promo ticket and could miss a W-2G the book will certainly issue.
    """
    policy = policy or GamblingPolicy()
    profit = float(profit)
    wager = float(wager)
    promo_stake = max(0.0, float(promo_stake or 0.0))
    if profit <= 0:
        return W2GAssessment(profit, wager, 0.0, False, False, 0.0)

    cash_stake = max(0.0, wager - promo_stake)
    effective_stake = cash_stake if cash_stake > 0 else promo_stake
    multiplier = (profit / effective_stake) if effective_stake > 0 else float("inf")
    odds_test = multiplier >= policy.w2g_multiplier_threshold
    reportable = odds_test and profit >= policy.w2g_reporting_threshold
    withholding_required = odds_test and profit > policy.w2g_withholding_threshold
    withholding = (profit * policy.mandatory_withholding_rate
                   if withholding_required else 0.0)
    return W2GAssessment(profit, wager, multiplier, reportable,
                         withholding_required, withholding)


def _statutory_seca(net_profit: float, seca: Dict[str, Any]) -> float:
    """
    IRC 1401/1402 self-employment tax.

    Three details a flat 15.3% gets wrong, all of them by a lot at real size:
    only 92.35% of net earnings is subject to it; the 12.4% Social Security leg
    stops at the wage base while the 2.9% Medicare leg never does. A professional
    netting $300k is not paying 15.3% on the lot.
    """
    if net_profit <= 0:
        return 0.0
    base = net_profit * float(seca.get("net_earnings_factor", 0.9235))
    wage_base = float(seca.get("social_security_wage_base", 184500.0))
    ss = min(base, wage_base) * float(seca.get("social_security_rate", 0.124))
    medicare = base * float(seca.get("medicare_rate", 0.029))
    return ss + medicare


def _deductible_losses(gross_losses: float, gross_winnings: float,
                       policy: GamblingPolicy, tax_year: int,
                       result: GamblingResult) -> float:
    """
    IRC 165(d) as amended by OBBBA 70114, in the only order that is correct:
    apply the percentage haircut FIRST, then cap at winnings.

    Doing it the other way round (cap, then haircut) is a different and smaller
    number whenever losses exceed winnings, and it is not what the statute says.
    """
    haircut = 1.0
    if tax_year >= policy.loss_haircut_effective_year:
        haircut = max(0.0, min(1.0, policy.loss_deduction_pct))
    result.loss_deduction_pct = haircut

    after_haircut = gross_losses * haircut
    allowed = min(after_haircut, max(0.0, gross_winnings))

    if haircut < 1.0 and gross_losses > 0:
        phantom = gross_losses - after_haircut
        result.warnings.append(
            f"OBBBA 70114: only {haircut * 100:.0f}% of ${gross_losses:,.2f} in losses is "
            f"deductible for {tax_year}, creating ${phantom:,.2f} of phantom taxable income. "
            f"Set gambling.loss_deduction_pct: 1.0 if this limit was repealed."
        )
    if gross_losses > 0 and allowed < gross_losses:
        result.warnings.append(
            f"${gross_losses - allowed:,.2f} of gambling losses produce NO deduction "
            f"(165(d) caps the deduction at winnings and it never carries forward)."
        )
    return allowed


def compute_gambling_tax(inputs: GamblingInputs, rates: GamblingRates,
                         policy: GamblingPolicy, tax_year: int) -> GamblingResult:
    """
    Sizes the gambling escrow. Pure: same inputs, same answer, no I/O.
    """
    winnings = max(0.0, float(inputs.gross_winnings))
    losses = abs(float(inputs.gross_losses))

    result = GamblingResult(
        treatment=policy.treatment,
        gross_winnings=winnings,
        gross_losses=losses,
        net_cash_pnl=float(inputs.net_cash_pnl),
        expenses=max(0.0, float(inputs.expenses)),
        session_winnings=max(0.0, float(inputs.session_winnings)),
        session_losses=abs(float(inputs.session_losses)),
        session_count=int(inputs.session_count),
        w2g_withheld=max(0.0, float(inputs.w2g_withheld)) if policy.track_w2g_withholdings else 0.0,
        w2g_predicted=max(0.0, float(inputs.w2g_predicted)) if policy.track_w2g_withholdings else 0.0,
    )

    # What the STATE measures. Set per branch, then netted centrally below - the
    # state's rule is its own and does not follow the federal election.
    state_winnings, state_losses = winnings, losses

    if policy.treatment == STANDARD_DEDUCTION:
        # THE FEDERAL TRAP. Every dollar won is federal income; not one dollar
        # lost is federally deductible.
        #
        # THE STATE IS A SEPARATE QUESTION and used to be answered wrongly here.
        # This branch hardcoded the state base to gross winnings, as though the
        # federal standard deduction bound the state too. It does not: New Jersey
        # nets gambling losses against gambling winnings in the same year as a
        # CATEGORY, with no itemisation requirement. On an $80,000-won /
        # $79,000-lost year that overstated NJ tax by about $5,000.
        result.loss_deduction_allowed = 0.0
        result.loss_disallowed = losses
        result.loss_deduction_pct = 0.0
        result.federal_taxable_base = winnings
        if losses > 0:
            result.warnings.append(
                f"Standard deduction: all ${losses:,.2f} of losses are disallowed under "
                f"165(d). Taxable base is gross winnings of ${winnings:,.2f}, not the "
                f"${result.net_cash_pnl:,.2f} actually banked."
            )

    elif policy.treatment == SESSION_NETTING:
        # IRS AM 2008-011. Netting happens WITHIN a session, so the winnings are
        # the sum of POSITIVE session nets rather than of individual wagers.
        #
        # WHETHER LOSING SESSIONS THEN COME OFF IS A SEPARATE QUESTION, and
        # conflating the two was wrong. Session netting is a MEASUREMENT
        # convention; the deduction still depends on whether the filer itemises.
        # A session-netter who itemises deducts losing sessions on Schedule A
        # (subject to the OBBBA haircut); one taking the standard deduction does
        # not. `session_netting_itemizes` says which, and defaults to false - the
        # stricter reading, because raising the deduction lowers the reserve.
        base = max(0.0, float(inputs.session_winnings))
        session_losses = abs(float(inputs.session_losses))
        if policy.session_netting_itemizes:
            allowed = _deductible_losses(session_losses, base, policy, tax_year, result)
            result.loss_deduction_allowed = allowed
            result.loss_disallowed = session_losses - allowed
            result.federal_taxable_base = max(0.0, base - allowed)
            state_winnings, state_losses = base, session_losses
            result.warnings.append(
                f"Session netting, ITEMISED: {result.session_count} winning session(s) "
                f"total ${base:,.2f}, against ${session_losses:,.2f} of losing sessions "
                f"deducted on Schedule A.")
        else:
            result.loss_deduction_allowed = 0.0
            result.loss_disallowed = max(session_losses, winnings - base)
            result.loss_deduction_pct = 0.0
            result.federal_taxable_base = base
            state_winnings, state_losses = base, session_losses
            result.warnings.append(
                f"Session netting aggregates {result.session_count} winning session(s) "
                f"into ${base:,.2f}. Losing sessions are NOT deducted - that needs "
                f"Schedule A. Set gambling.session_netting_itemizes: true if you itemise.")

    elif policy.treatment == ITEMIZED:
        allowed = _deductible_losses(losses, winnings, policy, tax_year, result)
        result.loss_deduction_allowed = allowed
        result.loss_disallowed = losses - allowed
        result.federal_taxable_base = max(0.0, winnings - allowed)
        if not policy.state_allows_loss_deduction and losses > 0:
            result.warnings.append(
                f"State disallows gambling losses: state tax is assessed on gross winnings "
                f"of ${winnings:,.2f}, not the federal base of "
                f"${result.federal_taxable_base:,.2f}."
            )

    elif policy.treatment == PROFESSIONAL:
        # Groetzinger: a full-time bettor is in a trade or business. TCJA (made
        # permanent by OBBBA) still applies 165(d) to a professional - losses AND
        # expenses together cannot exceed winnings, so a professional cannot
        # generate a business loss out of gambling either.
        allowed_losses = _deductible_losses(losses, winnings, policy, tax_year, result)
        room = max(0.0, winnings - allowed_losses)
        allowed_expenses = min(result.expenses, room)
        if allowed_expenses < result.expenses:
            result.warnings.append(
                f"${result.expenses - allowed_expenses:,.2f} of Schedule C expenses exceed "
                f"the 165(d) ceiling of winnings and are disallowed."
            )
        result.loss_deduction_allowed = allowed_losses
        result.loss_disallowed = losses - allowed_losses
        net_profit = max(0.0, winnings - allowed_losses - allowed_expenses)

        if policy.use_statutory_seca:
            result.self_employment_tax = _statutory_seca(net_profit, policy.seca)
            income_base = net_profit
            if policy.seca.get("deduct_half_se_tax", True):
                # 164(f): half the SE tax is an above-the-line deduction.
                income_base = max(0.0, net_profit - 0.5 * result.self_employment_tax)
        else:
            result.self_employment_tax = net_profit * rates.self_employment
            income_base = net_profit

        result.federal_taxable_base = income_base
        # A professional's net profit is already netted, so the state base is that
        # profit unless the state disallows the offset entirely.
        state_winnings = income_base if policy.state_allows_loss_deduction else winnings
        state_losses = 0.0

    if rates.federal_rate_is_composite and result.gross_winnings > 0:
        # THE RATE MUDDLE, SURFACED RATHER THAN SILENTLY INHERITED.
        # `tax_rates.short_term_capital_gains` is documented in config.yaml as
        # ALREADY blending federal and state ("24% Federal + 4% State"), and
        # `state_tax_rate` is then added on top - so state is counted twice in the
        # composite, and the federal leg used here is not a federal rate at all.
        #
        # Two consequences, in opposite directions: the W-2G credit ceiling is too
        # GENEROUS (it is capped at a federal+state number), and every hurdle is
        # too STRICT (computed at the inflated composite). Neither is fixable from
        # code - it needs the operator to state their real marginal rates.
        result.warnings.append(
            f"No unbundled federal rate is set, so the federal leg falls back to "
            f"tax_rates.short_term_capital_gains ({rates.federal_ordinary * 100:.0f}%). "
            f"Before Round 26k that field was a federal+STATE blend, so this "
            f"over-states the federal leg and state is then added again at "
            f"{rates.state_ordinary * 100:.0f}%. Set tax_rates.federal_ordinary_rate; "
            f"every hurdle and W-2G credit ceiling depends on it.")

    # THE STATE BASE, COMPUTED ONCE, FROM THE STATE'S OWN RULE. A state that
    # allows the offset nets losses against winnings at its own percentage
    # (usually 100% - the OBBBA haircut is federal and no state adopted it),
    # capped at winnings. A state that disallows it - IL, OH, CT and others -
    # taxes the GROSS, which is why their bettors owe state tax on a losing year.
    if policy.state_allows_loss_deduction:
        state_haircut = min(max(policy.state_loss_deduction_pct, 0.0), 1.0)
        state_allowed = min(state_losses * state_haircut, max(0.0, state_winnings))
        result.state_taxable_base = max(0.0, state_winnings - state_allowed)
    else:
        result.state_taxable_base = max(0.0, state_winnings)

    result.federal_tax = max(0.0, result.federal_taxable_base) * rates.federal_ordinary
    result.state_tax = max(0.0, result.state_taxable_base) * rates.state_ordinary
    result.safety_buffer_tax = max(0.0, result.federal_taxable_base) * rates.safety_buffer
    result.tax_gross = (result.federal_tax + result.state_tax
                        + result.safety_buffer_tax + result.self_employment_tax)

    # W-2G withholding is a FEDERAL prepayment. Cap the credit at the federal
    # legs it can actually pay (income tax + SE tax, both federal); report the
    # rest as the refund receivable it is instead of quietly shrinking escrow.
    # PREDICTED WITHHOLDING IS CREDITED THROUGH THE SAME FEDERAL-CAPPED PATH as
    # recorded withholding, not subtracted from the total. Treating the two
    # differently would mean a book that withheld and a book that must withhold
    # produce different escrows for the same wager, which cannot be right - and
    # the federal cap is there because 3402(q) withholding is FEDERAL income tax
    # and cannot pay a state or this ledger's safety buffer.
    withheld = result.w2g_withheld + result.w2g_predicted
    if policy.w2g_credit_scope == CREDIT_TOTAL:
        creditable = result.tax_gross
    else:
        creditable = result.federal_tax + result.self_employment_tax
    result.w2g_credit_applied = min(withheld, max(0.0, creditable))
    result.w2g_surplus = max(0.0, withheld - result.w2g_credit_applied)
    if result.w2g_predicted > 0:
        result.warnings.append(
            f"${result.w2g_predicted:,.2f} of IRC 3402(q) withholding is MANDATORY on "
            f"settled winners in this ledger but was not recorded by the import. The "
            f"payout arrived (or will arrive) short by that much - the escrow already "
            f"credits it, but your CASH did not include it.")
    if result.w2g_surplus > 0:
        result.warnings.append(
            f"${result.w2g_surplus:,.2f} withheld at the book exceeds the federal gambling "
            f"tax it can pay. It is a refund receivable against your total return, NOT a "
            f"release of escrow - state tax and buffer are still owed in cash."
        )

    result.escrow = max(0.0, result.tax_gross - result.w2g_credit_applied)
    return result
