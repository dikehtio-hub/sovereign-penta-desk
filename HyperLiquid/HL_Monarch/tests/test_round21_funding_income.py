"""
Tests for Round 21: Section 61 Ordinary Income Funding Bridge
"""
import pytest
from pathlib import Path
from execution.basis_harvester import BasisHarvester
from Tax_Reserve_Agent.database.db import get_connection, init_db
from Tax_Reserve_Agent.ingestors.csv_watcher import CSVWatcher
from Tax_Reserve_Agent.engine.tax_calculator import calculate_tax_summary


def test_basis_harvester_emits_funding_receipt(tmp_path: Path):
    harvester = BasisHarvester(
        starting_cash=20000.0,
        receipts_enabled=True,
        receipts_dir=tmp_path
    )
    opp = {
        "coin": "BTC",
        "spot_symbol": "BTC/USDC",
        "spread_bps": 5.0,
        "funding_apr": 35.0,
        "net_apr": 34.5,
        "holding_days": 10.0,
        "mark_px": 60000.0,
        "perp_sz_decimals": 4,
        "spot_sz_decimals": 4,
    }
    pos = harvester.open_position(opp, notional_per_leg=6000.0)
    assert pos is not None
    assert "BTC" in harvester.positions

    # Accrue 1h of positive funding (0.0001 = 0.01% per hour)
    rates = {"BTC": 0.0001}
    credited = harvester.accrue(rates, hours=1.0)
    assert credited["BTC"] == pytest.approx(0.60, abs=1e-4)  # $6000 * 0.0001 = $0.60

    # Verify receipt was written to drop folder
    csvs = list(tmp_path.glob("*.csv"))
    assert len(csvs) == 1
    content = csvs[0].read_text()
    assert "BTC-FUNDING" in content
    assert "INCOME" in content
    assert "strategy:hl_basis_harvest;" in content


def test_funding_receipt_ingestion_and_tax_calculation(tmp_path: Path):
    imports_dir = tmp_path / "imports"
    imports_dir.mkdir(parents=True)
    db_path = tmp_path / "tax_ledger.db"
    init_db(db_path)

    # 1. Generate funding receipt via harvester
    harvester = BasisHarvester(
        starting_cash=20000.0,
        receipts_enabled=True,
        receipts_dir=imports_dir
    )
    opp = {
        "coin": "ETH",
        "spot_symbol": "ETH/USDC",
        "spread_bps": 5.0,
        "funding_apr": 50.0,
        "net_apr": 49.5,
        "holding_days": 10.0,
        "mark_px": 3000.0,
        "perp_sz_decimals": 3,
        "spot_sz_decimals": 3,
    }
    pos = harvester.open_position(opp, notional_per_leg=3000.0)
    assert pos is not None
    harvester.accrue({"ETH": 0.0005}, hours=1.0)  # $3000 * 0.0005 = $1.50

    # 2. Process through CSVWatcher (two scans: first registers mtime, second ingests)
    watcher = CSVWatcher(imports_dir=imports_dir, db_path=db_path)
    watcher.scan_once()
    results = watcher.scan_once()
    assert len(results) == 1
    assert results[0]["status"] == "ok"

    # 3. Verify transactions table has the INCOME record
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT symbol, side, asset_class, total_value FROM transactions")
    txs = cur.fetchall()
    assert len(txs) == 1
    row = dict(txs[0])
    assert row["symbol"] == "ETH-FUNDING"
    assert row["side"] == "INCOME"
    assert row["asset_class"] == "crypto_perp_funding"
    assert row["total_value"] == pytest.approx(1.50, abs=1e-4)

    # 4. Invariant: tax_lots and realized_pnl MUST remain untouched (0 rows)
    cur.execute("SELECT count(*) as c FROM tax_lots")
    assert cur.fetchone()["c"] == 0
    cur.execute("SELECT count(*) as c FROM realized_pnl")
    assert cur.fetchone()["c"] == 0

    # 5. Ordinary income is reported, kept out of CAPITAL GAINS, and still escrowed.
    #
    # SUPERSEDED ASSERTION. This step previously required
    # `tax_escrow_reserve == 0.0`, which encoded a real defect as intended
    # behaviour. The Round 21 requirement is that funding income must not pollute
    # the CAPITAL GAINS computation - step 4 above is what proves that, and it
    # still passes: zero tax lots, zero realized_pnl, zero gross gains.
    #
    # Escrow is a different question. Funding is IRC 61 ordinary income and the
    # tax on it is really owed, so reserving nothing against it meant the agent
    # printed the income on the Obsidian card and simultaneously reported 100% of
    # it as safe to deploy. A basis harvester earning funding all year would have
    # been handed its entire tax bill as tradeable bankroll - the precise failure
    # this ledger exists to prevent.
    #
    # $1.50 of funding at the composite ordinary rate (0.35) = $0.525.
    # ROUND 33 RULING C: config.yaml no longer carries a placeholder balance, so a
    # ledger with income but no DEPOSIT row sizes to $0.00. This test is a
    # simulation and must DECLARE the balance it reasons about - which is what
    # every fixture was implicitly doing before, off a number nobody measured.
    from Tax_Reserve_Agent.config import load_config
    config = load_config()
    config.setdefault("portfolio", {})["default_cash_balance_usdc"] = 10_000.0
    summary = calculate_tax_summary(tax_year=2026, db_path=db_path, config=config)
    assert summary["ordinary_income"] == pytest.approx(1.50, abs=1e-4)
    assert summary["net_ordinary_income"] == pytest.approx(1.50, abs=1e-4)

    # Capital gains remain untouched by the funding accrual.
    assert summary["total_gross_gains"] == 0.0
    assert summary["escrow_short_term"] == 0.0
    assert summary["escrow_long_term"] == 0.0

    # ...but the ordinary tax IS reserved.
    expected = 1.50 * summary["effective_tax_rate"]
    assert summary["escrow_ordinary"] == pytest.approx(expected, abs=1e-6)
    assert summary["tax_escrow_reserve"] == pytest.approx(expected, abs=1e-6)
    assert summary["safe_deployable_bankroll"] == pytest.approx(
        summary["liquid_cash_balance"] - expected, abs=1e-6)
