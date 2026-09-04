"""
Configuration loader for Tax Reserve Agent.
"""
from pathlib import Path
from typing import Any, Dict
import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"

DEFAULT_CONFIG: Dict[str, Any] = {
    # Unbundled as of Round 26k - see config.yaml for why the old composite was
    # wrong. Each rate is exactly one thing.
    "tax_rates": {
        "federal_ordinary_rate": 0.24,
        "state_tax_rate": 0.0637,   # NJ single, $75k-$500k band
        "safety_buffer_pct": 0.02,
        "short_term_capital_gains": 0.24,
        "long_term_capital_gains": 0.15,
    },
    "accounting": {
        "method": "FIFO",
    },
    # See config.yaml for what each of these means and why the defaults are
    # where they are. Duplicated here only so a missing config.yaml does not
    # silently drop to a looser tax treatment than the file would have given.
    "gambling": {
        "tax_treatment": "casual_standard_deduction",
        "federal_ordinary_rate": None,
        "state_ordinary_rate": None,
        "state_allows_loss_deduction": True,     # NJ nets losses as a category
        "state_loss_deduction_pct": 1.0,         # no state adopted the OBBBA haircut
        "loss_deduction_pct": 0.90,
        "loss_haircut_effective_year": 2026,
        "track_w2g_withholdings": True,
        "w2g_reporting_threshold_usd": 600.0,
        "w2g_odds_multiplier_threshold": 300.0,
        "w2g_mandatory_withholding_threshold_usd": 5000.0,
        "mandatory_withholding_rate": 0.24,
        "w2g_credit_scope": "federal",
        "session_grouping": "day_book",
        "session_netting_itemizes": False,
        "self_employment_tax_rate": 0.153,
        "use_statutory_seca": True,
        "seca": {
            "net_earnings_factor": 0.9235,
            "social_security_rate": 0.124,
            "medicare_rate": 0.029,
            "social_security_wage_base": 184500.0,
            "deduct_half_se_tax": True,
        },
        "default_odds_format": "",
        "odds_payout_tolerance_pct": 0.02,
    },
    "wallets": {
        "polygon_wallets": [],
        "solana_wallets": [],
        "evm_wallets": [],
    },
    "portfolio": {
        "default_cash_balance_usdc": 10000.0,
        "tax_year": 2026,
    },
    "output": {
        "obsidian_vault_path": "",
        "export_to_obsidian": False,
    },
    "chain": {
        "polygon_rpc_endpoints": [
            "https://polygon-bor-rpc.publicnode.com",
            "https://polygon.drpc.org",
            "https://1rpc.io/matic",
        ],
        "ctf_contract": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        "orderbook_subgraph_url": "",
        "start_block": 0,
        "confirmations": 64,
        "include_clob_fills": True,
        "polymarket_fee_rate": 0.0,
        "split_basis_allocation": [],
    },
    "imports": {
        "drop_folder": "data/imports",
        "poll_interval_seconds": 5,
        "archive_after_import": True,
    },
    "bot_integration": {
        "max_position_pct": 0.05,
        "min_order_usd": 1.00,
        "snapshot_cache_seconds": 60,
        "allow_empirical_upsize": False,
        "category_window": 40,
        "min_category_trades": 5,
        "payoff_basis": "conservative",
        "assumed_round_trip_fee": 0.02,
        "strategies": {
            "dutched_arb": 0.30,
            "consensus_copy": 0.20,
            "hl_basis_harvest": 0.25,
            "sports_betting": 0.15,
            "hl_liquidation_fade": 0.05,
            "sandbox": 0.10,
        },
    },
}

def load_config(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    if not config_path.exists():
        return DEFAULT_CONFIG
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else DEFAULT_CONFIG
    except Exception as e:
        print(f"[WARN] Failed to read {config_path}: {e}. Using defaults.")
        return DEFAULT_CONFIG

def federal_ordinary_rate(config: Dict[str, Any] = None) -> float:
    """
    The PURE federal ordinary rate, with a documented fallback.

    `tax_rates.federal_ordinary_rate` is the answer when it is set. Before Round
    26k it did not exist and callers used `short_term_capital_gains`, which was a
    federal+state blend - so the fallback is kept for an un-migrated config, and
    it is the wrong number by construction. `gambling_tax.resolve_rates` warns
    when it has to use it.
    """
    if config is None:
        config = load_config()
    rates = config.get("tax_rates", {}) or {}
    explicit = rates.get("federal_ordinary_rate")
    if explicit is not None:
        return float(explicit)
    return float(rates.get("short_term_capital_gains", 0.24))


def get_composite_tax_rate(config: Dict[str, Any] = None) -> float:
    """
    Federal + state + buffer. 0.24 + 0.05 + 0.02 = 0.31.

    Reads `short_term_capital_gains` as the ordinary leg because short-term gains
    ARE taxed as ordinary income, and the two are set equal in config.yaml. State
    is added exactly once, which was the whole point of the 26k unbundling.
    """
    if config is None:
        config = load_config()
    rates = config.get("tax_rates", {})
    st = rates.get("short_term_capital_gains", 0.24)
    state = rates.get("state_tax_rate", 0.05)
    buffer_ = rates.get("safety_buffer_pct", 0.02)
    return float(st + state + buffer_)
