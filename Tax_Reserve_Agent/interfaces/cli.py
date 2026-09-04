"""
CLI Dashboard & Terminal HUD for Tax Reserve Agent.
"""
from typing import Dict, Any
from datetime import datetime

def _wrap(text: str, width: int) -> list:
    """Minimal greedy wrapper - `textwrap` is fine, but this HUD has no imports
    beyond the stdlib basics and one function is cheaper than one more import."""
    words, line, out = str(text).split(), "", []
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def render_hud(summary: Dict[str, Any]) -> str:
    """
    Renders an ASCII Heads-Up Display showing the Tax Escrow & Safe Bankroll.
    """
    lines = []
    lines.append("=" * 64)
    lines.append("          PORTFOLIO & TAX ESCROW RESERVE DASHBOARD")
    lines.append("=" * 64)
    lines.append(f"  Tax Year: {summary['tax_year']}                     Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"  Composite Tax Rate: {summary['effective_tax_rate']*100:.1f}%"
                 f"          Method: {summary.get('accounting_method', 'FIFO')}")
    if summary.get("method_mismatch"):
        lines.append(f"  [!] Lots were matched under {summary['accounting_method']} but config.yaml "
                     f"now says {summary['configured_method']}.")
        lines.append("      Numbers below blend two methods. Run `main rebuild` to re-match.")
    if summary.get("term_rule_stale"):
        lines.append("  [!] Capital terms were classified under an older rule "
                     f"({summary.get('term_rule')}).")
        lines.append("      LONG vs SHORT now uses a calendar test - a day count cannot")
        lines.append("      express 'more than one year' across a leap year. Boundary")
        lines.append("      trades may be marked LONG_TERM that are legally SHORT_TERM,")
        lines.append("      which UNDER-states the reserve. Run `main rebuild`.")
    lines.append("-" * 64)
    lines.append(f"  Total Liquid Cash / Capital:     ${summary['liquid_cash_balance']:>12,.2f}")
    lines.append("-" * 64)
    lines.append("  REALIZED P&L BREAKDOWN BY ASSET CLASS:")
    
    breakdown = summary.get("breakdown_by_asset", {})
    if not breakdown:
        lines.append("    (No closed trades recorded yet for this tax year)")
    else:
        for asset, data in breakdown.items():
            asset_label = asset.replace("_", " ").title()
            net_str = f"{'+$' if data['net_pnl'] >= 0 else '-$'}{abs(data['net_pnl']):,.2f}"
            lines.append(f"    * {asset_label:<24} {net_str:>14}  ({data['trade_count']} trades)")
            lines.append(f"        Gains: +${data['gross_gains']:,.2f} | Losses: -${abs(data['gross_losses']):,.2f}")
            
    lines.append("-" * 64)
    # `net_capital_gains` and `total_gross_*` include the wagering and 1256
    # buckets for backward compatibility. A line labelled CAPITAL GAINS must not,
    # so the card reads the capital-only mirrors where they exist.
    net_cap = summary.get("net_capital_gains_excl_gambling", summary["net_capital_gains"])
    gross_g = summary.get("capital_gross_gains", summary["total_gross_gains"])
    gross_l = summary.get("capital_gross_losses", summary["total_gross_losses"])
    net_str = f"{'+$' if net_cap >= 0 else '-$'}{abs(net_cap):,.2f}"
    lines.append(f"  NET REALIZED CAPITAL GAINS:      {net_str:>14}")
    lines.append(f"  Gross Gains:  +${gross_g:>10,.2f} | Gross Losses: -${abs(gross_l):>10,.2f}")

    if ("sports_bet" in breakdown or summary.get("gambling_gains", 0.0) > 0
            or summary.get("gambling_losses", 0.0) != 0):
        lines.append("-" * 64)
        lines.append("  GAMBLING & SPORTS WAGERING (IRC 61 & 165(d)):")
        treatment_label = summary.get("gambling_treatment", "casual_standard_deduction").replace("_", " ").title()
        lines.append(f"  Treatment: {treatment_label}")
        g_gains = summary.get("gambling_gains", 0.0)
        g_losses = summary.get("gambling_losses", 0.0)
        g_net = summary.get("gambling_net", 0.0)
        g_net_str = f"{'+$' if g_net >= 0 else '-$'}{abs(g_net):,.2f}"
        lines.append(f"  Gross Wins:   +${g_gains:>10,.2f} | Gross Losses: -${abs(g_losses):>10,.2f}")
        lines.append(f"  Net Cash P&L:  {g_net_str:>11} | Taxable Base: ${summary.get('gambling_federal_taxable_base', 0.0):>10,.2f}")

        # The gap between what was banked and what is taxed is the whole point of
        # this card. Naming the disallowed figure is the difference between an
        # operator who understands the escrow and one who thinks it is a bug.
        disallowed = summary.get("gambling_loss_disallowed", 0.0)
        if disallowed > 0:
            haircut = summary.get("gambling_loss_deduction_pct", 1.0)
            note = f" ({haircut*100:.0f}% cap)" if 0 < haircut < 1 else ""
            lines.append(f"  Losses DISALLOWED under 165(d): ${disallowed:>10,.2f}{note}")

        state_base = summary.get("gambling_state_taxable_base", 0.0)
        fed_base = summary.get("gambling_federal_taxable_base", 0.0)
        if abs(state_base - fed_base) > 0.005:
            lines.append(f"  State base differs: ${state_base:>10,.2f} "
                         f"(state disallows loss deduction)")
        lines.append(f"  Federal: ${summary.get('gambling_federal_tax', 0.0):>9,.2f} | "
                     f"State: ${summary.get('gambling_state_tax', 0.0):>8,.2f} | "
                     f"Buffer: ${summary.get('gambling_safety_buffer_tax', 0.0):>7,.2f}")
        se_tax = summary.get("gambling_self_employment_tax", 0.0)
        if se_tax > 0:
            lines.append(f"  Self-employment tax (IRC 1401): ${se_tax:>10,.2f}")

        credit = summary.get("gambling_w2g_credit_applied", 0.0)
        surplus = summary.get("gambling_w2g_surplus", 0.0)
        if credit > 0 or surplus > 0:
            lines.append(f"  W-2G Withheld: -${summary.get('gambling_w2g_withheld', 0.0):>10,.2f} "
                         f"(${credit:,.2f} credited)")
        if surplus > 0:
            lines.append(f"  [i] ${surplus:,.2f} OVERWITHHELD - a refund receivable, not "
                         f"released escrow.")
        sessions = summary.get("gambling_session_count", 0)
        if sessions:
            lines.append(f"  Winning sessions counted: {sessions}")
        lines.append(f"  Gambling Escrow: ${summary.get('escrow_gambling', 0.0):>10,.2f}")
        if summary.get("gambling_treatment") == "casual_standard_deduction" and abs(g_losses) > 0:
            lines.append("  [!] NOTE: Standard deduction active; $0 loss offset allowed under 165(d).")
        for warning in summary.get("gambling_warnings", [])[:3]:
            for chunk in _wrap(warning, 58):
                lines.append(f"      {chunk}")
    lines.append("-" * 64)
    lines.append(f"  >>> TAX ESCROW RESERVE (HOLD):   ${summary['tax_escrow_reserve']:>12,.2f}  [{summary['reserve_ratio_pct']:.1f}% of liquid]")
    lines.append(f"  >>> SAFE DEPLOYABLE BANKROLL:    ${summary['safe_deployable_bankroll']:>12,.2f}  <-- [TRUE RISK CAPITAL]")
    lines.append("=" * 64)
    
    if summary["tax_escrow_reserve"] > 0:
        lines.append("  [!] ACTION: Keep tax escrow in USDC/cash. Do not reinvest this portion.")
    else:
        lines.append("  [i] All liquid balance is safe to deploy (0 tax escrow owed).")
    lines.append("=" * 64)
    return "\n".join(lines)


def render_strategy_table(stats: Dict[str, Any], budgets: Dict[str, Any],
                          safe_bankroll: float) -> str:
    """
    Per-strategy capital and performance.

    Open exposure is measured from the ledger via the `strategy:<name>;` tag in
    `transactions.notes`, so it reflects what a strategy actually has at risk
    rather than what a caller claimed. Lots opened before tagging existed carry no
    tag and appear nowhere here - on a historical ledger the exposure column
    under-states reality.
    """
    lines = []
    lines.append("=" * 88)
    lines.append("          STRATEGY CAPITAL & ATTRIBUTION")
    lines.append("=" * 88)
    lines.append(f"  Safe bankroll: ${safe_bankroll:,.2f}")
    lines.append("-" * 88)
    lines.append(f"  {'STRATEGY':<18}{'BUDGET':>12}{'OPEN EXP':>12}{'CLOSED':>8}"
                 f"{'REALISED':>12}{'WIN %':>8}{'EXPECT':>9}")
    lines.append("-" * 88)

    for name in sorted(set(stats) | set(budgets)):
        row = stats.get(name, {})
        budget = budgets.get(name)
        budget_str = f"${budget.budget:,.2f}" if budget is not None else "-"
        exposure = float(row.get("open_exposure", 0.0))
        closed = int(row.get("closed", 0))
        pnl = float(row.get("pnl", 0.0))
        win = float(row.get("win_rate", 0.0))
        expectancy = float(row.get("expectancy", 0.0))
        over = "  <-- OVER BUDGET" if budget is not None and exposure > budget.budget else ""
        lines.append(f"  {name[:17]:<18}{budget_str:>12}{exposure:>12,.2f}{closed:>8}"
                     f"{pnl:>+12,.2f}{win:>7.1f}%{expectancy:>9.3f}{over}")

    lines.append("-" * 88)
    lines.append("  Expectancy is the Wilson lower bound on the win rate - the conservative")
    lines.append("  estimate the position sizer actually uses, not the raw rate.")
    lines.append("  Open exposure counts only lots tagged at ingestion; older lots are absent.")
    lines.append("=" * 88)
    return "\n".join(lines)


HEALTH_ESCROW_RATIO_LIMIT = 15.0     # percent of liquid cash


def run_health_check(summary: Dict[str, Any], category_stats: Dict[str, Any]) -> tuple:
    """
    Two questions worth waking someone up for, and nothing else.

    Returns `(exit_code, report)` - 0 healthy, 1 needs review - so a scheduler can
    branch on it without parsing text.

      1. HAS A CATEGORY'S EDGE INVERTED? Expectancy is measured on the 40-trade
         rolling window, so this fires when a category has RECENTLY turned, not
         when its lifetime average finally catches up. That is the point: by the
         time a lifetime figure inverts, the damage is done.
      2. IS THE ESCROW ABOVE 15% OF LIQUID CASH? A high ratio is not itself a
         problem - it means the year has been profitable - but it means a large
         share of the balance is spoken for, and sizing off the raw balance from
         here is how a good year funds a bad April.

    A category with no measured edge is NOT a failure. Absence of evidence is not
    an inverted edge, and alerting on it would train the operator to ignore this.
    """
    problems = []
    notes = []

    for name, edge in sorted(category_stats.items()):
        expectancy = float(getattr(edge, "expectancy", 0.0))
        trades = int(getattr(edge, "trades", 0))
        if trades <= 0:
            continue
        if expectancy <= 0:
            problems.append(f"category {name!r} expectancy has INVERTED "
                            f"({expectancy:+.3f} per $ risked over its last {trades} "
                            f"trades) - it is sized to zero and is losing money")
        else:
            notes.append(f"{name}: E={expectancy:+.3f} over {trades} trades")

    ratio = float(summary.get("reserve_ratio_pct", 0.0))
    if ratio > HEALTH_ESCROW_RATIO_LIMIT:
        problems.append(f"tax escrow is {ratio:.1f}% of liquid cash "
                        f"(${summary.get('tax_escrow_reserve', 0.0):,.2f} of "
                        f"${summary.get('liquid_cash_balance', 0.0):,.2f}), above the "
                        f"{HEALTH_ESCROW_RATIO_LIMIT:.0f}% review threshold - a large "
                        f"share of the balance is already owed")

    lines = ["=" * 72,
             "  HEALTH CHECK" + ("  -  NEEDS REVIEW" if problems else "  -  HEALTHY"),
             "=" * 72]
    if problems:
        for problem in problems:
            lines.append(f"  [!] {problem}")
    else:
        lines.append("  No inverted category edges; escrow ratio within threshold.")
    if notes:
        lines.append("-" * 72)
        for note in notes:
            lines.append(f"  [ok] {note}")
    lines.append("-" * 72)
    lines.append(f"  escrow {summary.get('reserve_ratio_pct', 0.0):.1f}% of liquid "
                 f"| safe bankroll ${summary.get('safe_deployable_bankroll', 0.0):,.2f}")
    lines.append("=" * 72)
    return (1 if problems else 0), "\n".join(lines)
