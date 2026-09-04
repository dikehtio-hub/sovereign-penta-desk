"""
SDK Hook for Trading Bots and Scripts.
Allows external scripts/bots to query safe bankroll sizing with 0 token overhead.
"""
from typing import Dict, Any, Optional
from pathlib import Path
from ..engine.tax_calculator import calculate_tax_summary

def get_safe_bankroll(tax_year: int = 2026, db_path: Optional[Path] = None) -> float:
    """Returns the exact dollar amount that is safe to risk/trade (excluding tax escrow)."""
    summary = calculate_tax_summary(tax_year=tax_year, db_path=db_path)
    return summary["safe_deployable_bankroll"]

def get_tax_escrow_reserve(tax_year: int = 2026, db_path: Optional[Path] = None) -> float:
    """Returns the dollar amount that must be set aside for tax liabilities."""
    summary = calculate_tax_summary(tax_year=tax_year, db_path=db_path)
    return summary["tax_escrow_reserve"]

def get_full_tax_summary(tax_year: int = 2026, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Returns complete tax metrics dictionary."""
    return calculate_tax_summary(tax_year=tax_year, db_path=db_path)
