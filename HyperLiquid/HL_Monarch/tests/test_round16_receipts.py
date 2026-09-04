"""
Round 16: execution receipts and the attribution loop.

A receipt is what places an HL fill in a capital bucket. Every test writes into a
tmp_path drop folder - never the real `Tax_Reserve_Agent/data/imports/`, which a
watcher would ingest into the live tax ledger.
"""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from execution.basis_harvester import BasisHarvester
from execution.paper_trader import PaperTrader
from execution.risk_manager import STRATEGY_BASIS_HARVEST, STRATEGY_LIQUIDATION_FADE

from Tax_Reserve_Agent.interfaces.receipts import (
    RECEIPT_COLUMNS,
    build_notes,
    log_execution_receipt,
    receipt_row,
)


def _rows(directory: Path):
    out = []
    for path in sorted(directory.glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            out.extend(list(csv.DictReader(handle)))
    return out


# ------------------------------------------------------------------ format

def test_notes_carry_a_terminated_strategy_tag():
    """The ';' is load-bearing: without it `sandbox` matches `sandbox_v2`."""
    assert build_notes("hl_basis_harvest") == "strategy:hl_basis_harvest;"
    assert "strategy:hl_basis;" not in build_notes("hl_basis_harvest")


def test_notes_carry_the_exit_reason():
    notes = build_notes(STRATEGY_LIQUIDATION_FADE, exit_reason="TAKE_PROFIT")
    assert "strategy:hl_liquidation_fade;" in notes
    assert "exit_reason:TAKE_PROFIT;" in notes


def test_receipt_columns_match_what_the_watcher_reads(tmp_path):
    path = log_execution_receipt("BTC", "BUY", 1.0, 60_000.0, "hl_basis_harvest",
                                 venue="hyperliquid", imports_dir=tmp_path)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        assert next(csv.reader(handle)) == RECEIPT_COLUMNS


def test_the_filename_lets_the_watcher_classify_without_guessing(tmp_path):
    path = log_execution_receipt("BTC", "BUY", 1.0, 60_000.0, STRATEGY_BASIS_HARVEST,
                                 venue="hyperliquid", imports_dir=tmp_path)
    assert path.name.startswith("fills_hyperliquid_hl_basis_harvest_")
    assert path.suffix == ".csv"


def test_each_receipt_gets_its_own_file(tmp_path):
    """The watcher MOVES a file once ingested; appending would race that move."""
    first = log_execution_receipt("BTC", "BUY", 1.0, 60_000.0, "s", imports_dir=tmp_path)
    second = log_execution_receipt("BTC", "BUY", 1.0, 60_000.0, "s", imports_dir=tmp_path)
    assert first != second
    assert len(list(tmp_path.glob("*.csv"))) == 2


def test_a_missing_directory_is_created(tmp_path):
    target = tmp_path / "does" / "not" / "exist"
    assert log_execution_receipt("BTC", "BUY", 1.0, 60_000.0, "s", imports_dir=target)


def test_an_unwritable_target_does_not_raise(tmp_path):
    """Bookkeeping must never take down an execution path."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where a directory needs to be", encoding="utf-8")
    assert log_execution_receipt("BTC", "BUY", 1.0, 60_000.0, "s",
                                 imports_dir=blocker / "sub") is None


def test_junk_numbers_are_refused_not_written(tmp_path):
    assert log_execution_receipt("BTC", "BUY", "nonsense", 1.0, "s", imports_dir=tmp_path) is None
    assert log_execution_receipt("BTC", "BUY", 0.0, 1.0, "s", imports_dir=tmp_path) is None
    assert list(tmp_path.glob("*.csv")) == []


# ------------------------------------------------------- paper trader fills

def test_receipts_are_off_by_default(tmp_path):
    """
    561 existing tests, every backtest and every research run share this class.
    Receipts write real CSVs into a folder a watcher ingests into the live ledger,
    so attribution has to be opted into where something is actually trading.
    """
    trader = PaperTrader(initial_balance_usd=100_000.0, receipts_dir=tmp_path)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0, strategy=STRATEGY_BASIS_HARVEST)
    assert list(tmp_path.glob("*.csv")) == []


def test_an_entry_fill_writes_a_receipt(tmp_path):
    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=tmp_path)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0,
                              strategy=STRATEGY_LIQUIDATION_FADE)
    rows = _rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTC"
    assert rows[0]["side"] == "BUY"
    assert float(rows[0]["quantity"]) == pytest.approx(1.0)
    assert float(rows[0]["price"]) == pytest.approx(60_000.0)
    assert "strategy:hl_liquidation_fade;" in rows[0]["notes"]


def test_an_exit_fill_writes_its_own_receipt_with_the_reason(tmp_path):
    """
    Entries and exits are separate receipts on purpose - the ledger runs its own
    FIFO matching, and netting them here would duplicate that logic elsewhere.
    """
    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=tmp_path)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0, strategy=STRATEGY_LIQUIDATION_FADE)
    trader.place_market_order("BTC", "A", 1.0, 61_000.0, strategy=STRATEGY_LIQUIDATION_FADE,
                              exit_reason="TAKE_PROFIT")
    rows = _rows(tmp_path)
    assert len(rows) == 2
    exit_row = next(r for r in rows if r["side"] == "SELL")
    assert "exit_reason:TAKE_PROFIT;" in exit_row["notes"]


@pytest.mark.parametrize("reason", ["TAKE_PROFIT", "STOP_LOSS", "TIME_STOP"])
def test_every_exit_reason_is_recorded(tmp_path, reason):
    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=tmp_path)
    trader.place_market_order("ETH", "B", 1.0, 3_000.0, strategy=STRATEGY_LIQUIDATION_FADE)
    trader.place_market_order("ETH", "A", 1.0, 3_100.0, strategy=STRATEGY_LIQUIDATION_FADE,
                              exit_reason=reason)
    assert any(f"exit_reason:{reason};" in r["notes"] for r in _rows(tmp_path))


def test_an_untagged_fill_is_not_written(tmp_path):
    """Better to write nothing than an unattributed row that loosens a ceiling."""
    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=tmp_path)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0)
    assert list(tmp_path.glob("*.csv")) == []


def test_a_default_strategy_covers_untagged_fills(tmp_path):
    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=tmp_path,
                         default_strategy=STRATEGY_BASIS_HARVEST)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0)
    assert "strategy:hl_basis_harvest;" in _rows(tmp_path)[0]["notes"]


def test_the_fee_and_venue_reach_the_receipt(tmp_path):
    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=tmp_path)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0, fee_pct=0.0005,
                              strategy=STRATEGY_BASIS_HARVEST)
    row = _rows(tmp_path)[0]
    assert float(row["fee"]) == pytest.approx(30.0)
    assert row["source"] == "hyperliquid"


def test_a_rejected_order_writes_nothing(tmp_path):
    trader = PaperTrader(100.0, receipts_enabled=True, receipts_dir=tmp_path)
    result = trader.place_market_order("BTC", "B", 100.0, 60_000.0,
                                       strategy=STRATEGY_BASIS_HARVEST)
    assert result["status"] == "REJECTED"
    assert list(tmp_path.glob("*.csv")) == []


def test_the_order_id_is_the_dedupe_key(tmp_path):
    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=tmp_path)
    fill = trader.place_market_order("BTC", "B", 1.0, 60_000.0,
                                     strategy=STRATEGY_BASIS_HARVEST)
    assert _rows(tmp_path)[0]["tx_hash"] == fill["order_id"]


# ------------------------------------------------------------ basis harvester

def test_basis_receipts_are_off_by_default(tmp_path):
    harvester = BasisHarvester(starting_cash=100_000.0, receipts_dir=tmp_path)
    assert harvester.receipts_enabled is False


def test_a_basis_close_writes_both_legs(tmp_path):
    """
    The brief only named paper_trader, but BasisHarvester never goes through it -
    hooking only the paper trader would have instrumented the RETIRED fade
    strategy and missed the live delta-neutral book.
    """
    harvester = BasisHarvester(starting_cash=100_000.0, receipts_enabled=True,
                               receipts_dir=tmp_path)
    written = harvester._emit_receipts(
        {"coin": "BTC", "notional_per_leg": 10_000.0, "spot_price": 60_000.0,
         "perp_price": 60_300.0, "funding_accrued": 12.34, "exit_fee": 4.0},
        opening=False, reason="MANUAL")
    assert len(written) == 2
    rows = _rows(tmp_path)
    assert {r["symbol"] for r in rows} == {"BTC-SPOT", "BTC-PERP"}
    assert {r["side"] for r in rows} == {"SELL", "BUY"}


def test_basis_legs_are_opposite_sides_on_entry(tmp_path):
    harvester = BasisHarvester(starting_cash=100_000.0, receipts_enabled=True,
                               receipts_dir=tmp_path)
    harvester._emit_receipts(
        {"coin": "ETH", "notional_per_leg": 5_000.0, "spot_price": 3_000.0,
         "perp_price": 3_010.0, "funding_accrued": 0.0, "entry_fee": 2.0},
        opening=True)
    rows = {r["symbol"]: r for r in _rows(tmp_path)}
    assert rows["ETH-SPOT"]["side"] == "BUY"      # long spot
    assert rows["ETH-PERP"]["side"] == "SELL"     # short perp


def test_funding_is_memoed_but_not_booked_as_capital(tmp_path):
    """
    Funding is periodic ORDINARY income; the ledger models capital gains only.
    Pushing it through the FIFO engine would misclassify it - wrong invisibly on
    the HUD and wrong on a filing.
    """
    harvester = BasisHarvester(starting_cash=100_000.0, receipts_enabled=True,
                               receipts_dir=tmp_path)
    harvester._emit_receipts(
        {"coin": "BTC", "notional_per_leg": 10_000.0, "spot_price": 60_000.0,
         "perp_price": 60_300.0, "funding_accrued": 42.5, "exit_fee": 4.0},
        opening=False, reason="MANUAL")
    rows = _rows(tmp_path)
    assert all("funding_accrued=42.5" in r["notes"] for r in rows)
    assert all("NOT booked as capital" in r["notes"] for r in rows)
    # The funding number must not appear as a tradeable quantity or price.
    assert all(float(r["quantity"]) != pytest.approx(42.5) for r in rows)


def test_a_zero_notional_basis_position_writes_nothing(tmp_path):
    harvester = BasisHarvester(starting_cash=100_000.0, receipts_enabled=True,
                               receipts_dir=tmp_path)
    assert harvester._emit_receipts(
        {"coin": "BTC", "notional_per_leg": 0.0, "spot_price": 60_000.0},
        opening=True) == []


def test_basis_receipts_carry_the_right_strategy_tag(tmp_path):
    harvester = BasisHarvester(starting_cash=100_000.0, receipts_enabled=True,
                               receipts_dir=tmp_path)
    harvester._emit_receipts(
        {"coin": "BTC", "notional_per_leg": 1_000.0, "spot_price": 60_000.0,
         "perp_price": 60_000.0, "funding_accrued": 0.0}, opening=True)
    assert all("strategy:hl_basis_harvest;" in r["notes"] for r in _rows(tmp_path))


# ------------------------------------------------- end-to-end into the ledger

def test_a_receipt_round_trips_into_the_tax_ledger(tmp_path):
    """
    The whole point of the loop: an HL fill must end up counting against its
    capital bucket. Anything less and the bucket is a per-order cap, not a ceiling.
    """
    from Tax_Reserve_Agent.database.db import init_db
    from Tax_Reserve_Agent.ingestors.csv_watcher import CSVWatcher
    from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

    db_path = tmp_path / "ledger.db"
    imports = tmp_path / "imports"
    imports.mkdir()
    init_db(db_path)

    trader = PaperTrader(100_000.0, receipts_enabled=True, receipts_dir=imports)
    trader.place_market_order("BTC", "B", 1.0, 60_000.0, strategy=STRATEGY_BASIS_HARVEST)

    CSVWatcher(imports_dir=imports, db_path=db_path).scan_once(require_stable=False)
    hook = MonarchBankrollHook(db_path=db_path, config={
        "tax_rates": {}, "portfolio": {"default_cash_balance_usdc": 100_000.0}})
    assert hook.get_strategy_open_exposure(STRATEGY_BASIS_HARVEST) == pytest.approx(60_000.0)
