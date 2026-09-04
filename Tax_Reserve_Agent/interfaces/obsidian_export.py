"""
Obsidian Vault Exporter.
Writes a daily Markdown card into the user's Obsidian Vault.
"""
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from ..config import load_config

def export_summary_to_obsidian(summary: Dict[str, Any], vault_path_override: str = "") -> Optional[Path]:
    config = load_config()
    vault_str = vault_path_override or config.get("output", {}).get("obsidian_vault_path", "")
    if not vault_str:
        return None
        
    vault_dir = Path(vault_str)
    if not vault_dir.exists():
        return None
        
    taxes_dir = vault_dir / "Trading_Taxes"
    taxes_dir.mkdir(parents=True, exist_ok=True)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    file_path = taxes_dir / f"Tax_Reserve_{today_str}.md"
    
    breakdown = summary.get("breakdown_by_asset", {})
    breakdown_md = ""
    for asset, data in breakdown.items():
        asset_title = asset.replace("_", " ").title()
        breakdown_md += f"- **{asset_title}:** Net: `${data['net_pnl']:,.2f}` (Gains: `+${data['gross_gains']:,.2f}` | Losses: `-${abs(data['gross_losses']):,.2f}`)\n"

    strat_cfgs = config.get("bot_integration", {}).get("strategies", {})
    safe_bankroll = summary.get("safe_deployable_bankroll", 0.0)
    strat_md = ""
    for s_name, s_pct in sorted(strat_cfgs.items()):
        alloc_usd = safe_bankroll * float(s_pct)
        strat_md += f"- **`{s_name}`:** `{s_pct*100:.0f}%` (${alloc_usd:,.2f})\n"
        
    ord_income = summary.get("ordinary_income", 0.0)
    ord_expense = summary.get("ordinary_expense", 0.0)
    net_ord = summary.get("net_ordinary_income", 0.0)

    # The escrow is three separate liabilities added together. Showing only the
    # total makes it impossible to tell a funding-heavy quarter from a
    # capital-gains one, and it was a silently missing ordinary component that
    # let the bankroll overstate itself in the first place.
    esc_st = summary.get("escrow_short_term", 0.0)
    esc_lt = summary.get("escrow_long_term", 0.0)
    esc_ord = summary.get("escrow_ordinary", 0.0)
    esc_fut = summary.get("escrow_futures", 0.0)
    esc_gambling = summary.get("escrow_gambling", 0.0)
    fut_rate = summary.get("futures_rate", 0.0)

    # Wagering gets its own section rather than a line in the escrow list: the
    # number that matters is not the escrow, it is the gap between what was
    # banked and what is taxable. Nothing else in this report has that property.
    gambling_md = ""
    if esc_gambling > 0 or summary.get("gambling_gains", 0.0) > 0 or summary.get("gambling_losses", 0.0) != 0:
        treatment = summary.get("gambling_treatment", "casual_standard_deduction")
        disallowed = summary.get("gambling_loss_disallowed", 0.0)
        surplus = summary.get("gambling_w2g_surplus", 0.0)
        gambling_md = f"""
### 🎲 Gambling & Sports Wagering (IRC §61 & §165(d))
- **Treatment:** `{treatment}`
- **Gross Winnings:** `+${summary.get('gambling_gains', 0.0):,.2f}`
- **Gross Losses:** `-${abs(summary.get('gambling_losses', 0.0)):,.2f}`
- **Net Cash P&L:** `${summary.get('gambling_net', 0.0):,.2f}`
- **Federal Taxable Base:** `${summary.get('gambling_federal_taxable_base', 0.0):,.2f}`
- **State Taxable Base:** `${summary.get('gambling_state_taxable_base', 0.0):,.2f}`
- **Losses disallowed under §165(d):** `${disallowed:,.2f}`
- **Federal / State / Buffer:** `${summary.get('gambling_federal_tax', 0.0):,.2f}` / `${summary.get('gambling_state_tax', 0.0):,.2f}` / `${summary.get('gambling_safety_buffer_tax', 0.0):,.2f}`
- **W-2G withheld / credited:** `${summary.get('gambling_w2g_withheld', 0.0):,.2f}` / `${summary.get('gambling_w2g_credit_applied', 0.0):,.2f}`
- **🛡️ Gambling Escrow:** `${esc_gambling:,.2f}`
"""
        if surplus > 0:
            gambling_md += (
                f"\n> [!info] `${surplus:,.2f}` was overwithheld at the book. "
                f"That is a refund receivable against your return, **not** released "
                f"escrow - state tax and buffer are still owed in cash.\n"
            )
        for warning in summary.get("gambling_warnings", []):
            gambling_md += f"\n> [!warning] {warning}\n"

    content = f"""# 🏦 Tax Escrow & Safe Bankroll Report ({today_str})

> Generated automatically by Tax Reserve Agent. 
> Last updated: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

---

### 📊 Portfolio & Bankroll Summary
- **Total Liquid Balance:** `${summary['liquid_cash_balance']:,.2f}`
- **🛡️ Tax Escrow (DO NOT SPEND):** `${summary['tax_escrow_reserve']:,.2f}`
- **🚀 Safe Deployable Bankroll:** **`${summary['safe_deployable_bankroll']:,.2f}`**
- **Escrow Ratio:** `{summary['reserve_ratio_pct']:.1f}%`

**Escrow composition**
- Short-term capital gains: `${esc_st:,.2f}`
- Long-term capital gains: `${esc_lt:,.2f}`
- CME futures (IRC §1256, 60/40 @ `{fut_rate*100:.1f}%`): `${esc_fut:,.2f}`
- Ordinary income (IRC §61): `${esc_ord:,.2f}`
- Gambling / wagering (IRC §165(d)): `${esc_gambling:,.2f}`

---

### 📈 Realized Capital Gains (Tax Year {summary['tax_year']})
- **Net Capital Gains:** `${summary.get('net_capital_gains_excl_gambling', summary['net_capital_gains']):,.2f}`
- **Gross Gains:** `+${summary.get('capital_gross_gains', summary['total_gross_gains']):,.2f}`
- **Gross Losses:** `-${abs(summary.get('capital_gross_losses', summary['total_gross_losses'])):,.2f}`
- **Composite Tax Rate:** `{summary['effective_tax_rate']*100:.1f}%`

### 💰 Ordinary Income (IRC §61 - Funding Yields / Staking)
- **Net Ordinary Income:** `${net_ord:,.2f}`
- **Gross Income:** `+${ord_income:,.2f}`
- **Gross Expense:** `-${abs(ord_expense):,.2f}`

{gambling_md}
### 📂 Asset Breakdown
{breakdown_md if breakdown_md else "- *No closed trades yet.*"}

---

### 🎯 Strategy Capital Buckets (Allocations off Safe Bankroll)
{strat_md if strat_md else "- *No strategy buckets configured.*"}

---
*Note: This is an internal managerial estimate to prevent bankroll over-allocation across all 4 desks.*
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return file_path
