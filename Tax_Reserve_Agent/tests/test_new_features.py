"""
Unit tests for the CTF chain ingestor, the CSV drop-folder watcher, and the
Monarch bankroll hook.

Everything here is offline and deterministic: CTF logs are synthesised as ABI
blobs and fed to the decoder, the subgraph/RPC clients are never constructed, and
the market resolver runs with `offline=True` so symbols fall back to their
on-chain form. No network, no fixtures that rot.
"""
import contextlib
import csv
import sys
import hashlib
import json
import math
import importlib.util
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

from Tax_Reserve_Agent.database.db import get_connection, get_meta, init_db, set_meta
from Tax_Reserve_Agent.engine.lot_engine import (
    ACCOUNTING_METHOD_KEY,
    FIFO,
    HIFO,
    lot_ordering,
    normalise_method,
    process_batch,
    rebuild_lots,
)
from Tax_Reserve_Agent.engine.loss_harvester import (
    LossHarvester,
    PolymarketMarkSource,
    load_marks,
)
from Tax_Reserve_Agent.engine.tax_calculator import calculate_tax_summary
from Tax_Reserve_Agent.interfaces.cli import (
    render_hud,
    render_strategy_table,
    run_health_check,
)
from Tax_Reserve_Agent.interfaces.tax_calendar import (
    build_calendar,
    next_business_day,
    quarter_bounds,
)
from Tax_Reserve_Agent.ingestors.csv_watcher import CSVWatcher, ClassificationError, classify_csv
from Tax_Reserve_Agent.ingestors.keccak import event_topic, keccak256, sha3_256
from Tax_Reserve_Agent.ingestors.market_resolution import (
    MarketResolutionSync,
    gamma_payout_ratios,
    parse_gamma_timestamp,
)
from Tax_Reserve_Agent.ingestors.polymarket import (
    CTF_TOPICS,
    FeeSchedule,
    PolymarketFeeSource,
    PolymarketIngestor,
    PolymarketMarketResolver,
    DEFAULT_POLYGON_RPC_ENDPOINTS,
    REORG_SAFETY_BLOCKS,
    PolygonRPCClient,
    PolymarketDataAPIClient,
    RPCError,
    CTFDecodeError,
    CTFEventDecoder,
    PolymarketChainIngestor,
    canonical_symbol,
    index_set_to_outcomes,
)
from Tax_Reserve_Agent.interfaces.monarch_hook import (
    CATEGORY_WINDOW,
    DEFAULT_PAYOFF_BASIS,
    MIN_CATEGORY_TRADES,
    MAX_PAYOFF_RATIO,
    MAX_SIZING_PCT,
    MIN_SIZING_PCT,
    MonarchBankrollHook,
    categorise,
    StrategyAllocationError,
    normalise_allocations,
    strategy_tag,
    tag_strategy,
    kelly_fraction_for,
    kelly_from_payoff_ratio,
    wilson_lower_bound,
)
from Tax_Reserve_Agent.ingestors.spot import SpotIngestor

TEST_CONFIG = {
    "tax_rates": {
        "short_term_capital_gains": 0.28,
        "state_tax_rate": 0.05,
        "safety_buffer_pct": 0.02,   # composite 35%
        "long_term_capital_gains": 0.15,
    },
    "portfolio": {"default_cash_balance_usdc": 10000.0, "tax_year": 2026},
}

WALLET = "0x" + "ab" * 20
CONDITION_ID = "0x" + "11" * 32
USDC = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"


def _word(value: int) -> str:
    return hex(value)[2:].rjust(64, "0")


def _make_split_log(amount_usdc: float = 100.0, legs=(1, 2), block: int = 1,
                    log_index: int = 0, event: str = "PositionSplit") -> dict:
    """Builds a real ABI-encoded PositionSplit/PositionsMerge log."""
    raw = int(round(amount_usdc * 1_000_000))
    tail = _word(len(legs)) + "".join(_word(leg) for leg in legs)
    return {
        "address": "0x4d97dcd97ec945f40cf65f87097ace5ea0476045",
        "topics": [CTF_TOPICS[event], "0x" + WALLET[2:].rjust(64, "0"), "0x" + _word(0), CONDITION_ID],
        # heads: collateralToken, offset(0x60) to partition, amount
        "data": "0x" + _word(int(USDC, 16)) + _word(0x60) + _word(raw) + tail,
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
        "transactionHash": "0x" + f"{block:02x}" * 32,
    }


def _make_redemption_log(payout_usdc: float = 100.0, legs=(2,), block: int = 3,
                         log_index: int = 0) -> dict:
    raw = int(round(payout_usdc * 1_000_000))
    tail = _word(len(legs)) + "".join(_word(leg) for leg in legs)
    return {
        "address": "0x4d97dcd97ec945f40cf65f87097ace5ea0476045",
        "topics": [CTF_TOPICS["PayoutRedemption"], "0x" + WALLET[2:].rjust(64, "0"),
                   "0x" + USDC[2:].rjust(64, "0"), "0x" + _word(0)],
        # heads: conditionId, offset(0x60) to indexSets, payout
        "data": "0x" + CONDITION_ID[2:] + _word(0x60) + _word(raw) + tail,
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
        "transactionHash": "0x" + f"{block:02x}" * 32,
    }


TIMESTAMPS = {1: "2026-01-05 10:00:00", 2: "2026-01-06 10:00:00", 3: "2026-02-01 10:00:00"}


class TestKeccak(unittest.TestCase):
    def test_known_answer_vectors(self):
        """Keccak-256, not SHA3-256 - the two differ only in a padding byte."""
        self.assertEqual(keccak256(b"").hex(),
                         "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(keccak256(b"abc").hex(),
                         "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45")

    def test_multi_block_matches_hashlib_sha3(self):
        """
        Pins the sponge against a known-good implementation across block
        boundaries.

        The two functions differ ONLY in the domain byte (0x01 vs 0x06) and share
        the permutation, the absorb loop and the padding path, so agreeing with
        `hashlib.sha3_256` at 0x06 is real evidence the 0x01 path is right. This
        replaces a check that only asserted the digest was 32 bytes long - which
        every broken implementation also satisfies, including one that ignores
        every byte after the first block.
        """
        sizes = [0, 1, 55, 134, 135, 136, 137, 271, 272, 273, 500, 1000, 4096]
        for size in sizes:
            data = bytes((i * 37 + 11) % 256 for i in range(size))
            self.assertEqual(sha3_256(data), hashlib.sha3_256(data).digest(),
                             f"sponge diverges from SHA3-256 at {size} bytes")

    def test_multi_block_keccak_known_answer_vectors(self):
        """
        Hardcoded multi-block Keccak-256 digests, to back up the SHA-3 cross-check
        with direct constants.

        PROVENANCE - these were not produced by the implementation under test,
        which would be circular. Each was generated on 2026-09-02 by TWO
        independent C implementations, pycryptodome 3.23.0
        (`Crypto.Hash.keccak`) and `eth_hash.auto`, and both agreed with each
        other before being written down here. Neither library is a runtime
        dependency; they were dev-time oracles only, and nothing in the package
        imports them.

        Inputs are chosen to span the 136-byte rate: 200 bytes is 2 blocks,
        430 is 4, 1024 is 8. A sponge that dropped everything after the first
        block would pass a length assertion and fail every line below.
        """
        vectors = [
            (b"a" * 200,
             "96ea54061def936c4be90b518992fdc6f12f535068a256229aca54267b4d084d"),
            (b"The quick brown fox jumps over the lazy dog" * 10,
             "e22d86321209c346393e4c8700a079b1a10ffa9fba9c3d367314ace1c7c195a9"),
            (bytes(range(256)) * 4,
             "5902e53903be0d0f9656bdbd5b9f0d8c2d815f865645d629eef77f5185f6cd7f"),
        ]
        for data, expected in vectors:
            self.assertEqual(keccak256(data).hex(), expected,
                             f"Keccak-256 wrong for a {len(data)}-byte input "
                             f"({len(data) // 136 + 1} rate blocks)")

    def test_keccak_is_not_sha3(self):
        """The padding byte is the whole difference; conflating them yields topics that match nothing."""
        self.assertNotEqual(keccak256(b"abc"), hashlib.sha3_256(b"abc").digest())

    def test_rate_boundary_padding(self):
        """
        135 bytes is the one case where the domain byte and the 0x80 terminator
        land on the same byte and have to be merged rather than written twice.
        """
        for size in (134, 135, 136, 271, 272):
            data = bytes(range(size % 256)) * (size // max(1, size % 256) or 1)
            data = (data * size)[:size]
            self.assertEqual(sha3_256(data), hashlib.sha3_256(data).digest())

    def test_erc20_transfer_topic(self):
        self.assertEqual(event_topic("Transfer(address,address,uint256)"),
                         "0x" + "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef")


class TestCTFDecoder(unittest.TestCase):
    def test_decodes_position_split(self):
        event = CTFEventDecoder.decode_log(_make_split_log(100.0, legs=(1, 2)))
        self.assertEqual(event["event"], "PositionSplit")
        self.assertEqual(event["stakeholder"], WALLET.lower())
        self.assertEqual(event["condition_id"], CONDITION_ID)
        self.assertEqual(event["index_sets"], [1, 2])
        self.assertEqual(event["amount"], 100_000_000)

    def test_decodes_payout_redemption(self):
        event = CTFEventDecoder.decode_log(_make_redemption_log(250.0, legs=(2,)))
        self.assertEqual(event["event"], "PayoutRedemption")
        self.assertEqual(event["payout"], 250_000_000)
        self.assertEqual(event["index_sets"], [2])

    def test_ignores_unrelated_logs(self):
        self.assertIsNone(CTFEventDecoder.decode_log(
            {"topics": [event_topic("Transfer(address,address,uint256)")], "data": "0x"}))

    def test_rejects_truncated_data(self):
        broken = _make_split_log()
        broken["data"] = broken["data"][:100]
        with self.assertRaises(CTFDecodeError):
            CTFEventDecoder.decode_log(broken)

    def test_batch_sorts_by_chain_order(self):
        logs = [_make_split_log(block=5, log_index=9), _make_split_log(block=5, log_index=1),
                _make_split_log(block=2, log_index=7)]
        events = CTFEventDecoder.decode_logs(logs)
        self.assertEqual([(e["block_number"], e["log_index"]) for e in events],
                         [(2, 7), (5, 1), (5, 9)])

    def test_index_set_bitmask(self):
        self.assertEqual(index_set_to_outcomes(1), [0])
        self.assertEqual(index_set_to_outcomes(2), [1])
        self.assertEqual(index_set_to_outcomes(3), [0, 1])
        self.assertEqual(index_set_to_outcomes(5), [0, 2])


class TestChainIngestor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        self.ingestor = PolymarketChainIngestor(offline=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_split_allocates_basis_equally(self):
        events = CTFEventDecoder.decode_logs([_make_split_log(100.0, legs=(1, 2))])
        rows = self.ingestor.events_to_transactions(events, TIMESTAMPS)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["side"] == "BUY" and r["quantity"] == 100.0 for r in rows))
        self.assertEqual([r["price"] for r in rows], [0.5, 0.5])
        # The $1 set price is conserved: no basis invented, none destroyed.
        self.assertAlmostEqual(sum(r["total_value"] for r in rows), 100.0)

    def test_custom_basis_allocation_is_normalised(self):
        ingestor = PolymarketChainIngestor(offline=True, basis_allocation=[3.0, 1.0])
        rows = ingestor.events_to_transactions(
            CTFEventDecoder.decode_logs([_make_split_log(100.0, legs=(1, 2))]), TIMESTAMPS)
        self.assertEqual([r["price"] for r in rows], [0.75, 0.25])
        self.assertAlmostEqual(sum(r["total_value"] for r in rows), 100.0)

    def test_split_then_merge_nets_to_zero(self):
        """A round trip with no trading in between must realise exactly $0 of gain."""
        events = CTFEventDecoder.decode_logs([
            _make_split_log(100.0, legs=(1, 2), block=1),
            _make_split_log(100.0, legs=(1, 2), block=2, event="PositionsMerge"),
        ])
        process_batch(self.ingestor.events_to_transactions(events, TIMESTAMPS), db_path=self.db_path)
        summary = calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)
        self.assertAlmostEqual(summary["net_capital_gains"], 0.0)
        self.assertAlmostEqual(summary["tax_escrow_reserve"], 0.0)

    def test_split_then_winning_redemption(self):
        """100 shares taken on at $0.50 basis, redeemed at $1.00 -> +$50 gain."""
        events = CTFEventDecoder.decode_logs([
            _make_split_log(100.0, legs=(1, 2), block=1),
            _make_redemption_log(100.0, legs=(2,), block=3),
        ])
        rows = self.ingestor.events_to_transactions(events, TIMESTAMPS, {CONDITION_ID: [0.0, 1.0]})
        process_batch(rows, db_path=self.db_path)
        summary = calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)
        self.assertAlmostEqual(summary["net_capital_gains"], 50.0)
        self.assertAlmostEqual(summary["tax_escrow_reserve"], 17.5)

    def test_redemption_share_count_uses_payout_ratio(self):
        """A 50-cent partial resolution means the payout bought twice as many shares."""
        events = CTFEventDecoder.decode_logs([_make_redemption_log(100.0, legs=(2,), block=3)])
        rows = self.ingestor.events_to_transactions(events, TIMESTAMPS, {CONDITION_ID: [0.0, 0.5]})
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["quantity"], 200.0)
        self.assertAlmostEqual(rows[0]["price"], 0.5)

    def test_redemption_without_ratios_is_flagged(self):
        rows = self.ingestor.events_to_transactions(
            CTFEventDecoder.decode_logs([_make_redemption_log(100.0, legs=(2,), block=3)]), TIMESTAMPS)
        self.assertAlmostEqual(rows[0]["price"], 1.0)
        self.assertIn("NEEDS-REVIEW", rows[0]["notes"])

    def test_losing_leg_writeoff_closes_open_lots(self):
        """The loser is never redeemed on chain, so its loss has to be booked explicitly."""
        events = CTFEventDecoder.decode_logs([
            _make_split_log(100.0, legs=(1, 2), block=1),
            _make_redemption_log(100.0, legs=(2,), block=3),
        ])
        process_batch(self.ingestor.events_to_transactions(
            events, TIMESTAMPS, {CONDITION_ID: [0.0, 1.0]}), db_path=self.db_path)

        loser = canonical_symbol(condition_id=CONDITION_ID, index_set=1)
        writeoffs = PolymarketChainIngestor.build_loser_writeoffs(
            [loser], "2026-02-01 10:00:00", db_path=self.db_path)
        self.assertEqual(len(writeoffs), 1)
        self.assertAlmostEqual(writeoffs[0]["quantity"], 100.0)
        self.assertEqual(writeoffs[0]["price"], 0.0)

        process_batch(writeoffs, db_path=self.db_path)
        summary = calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)
        # +$50 on the winner, -$50 on the loser: splitting and holding both is a wash.
        self.assertAlmostEqual(summary["net_capital_gains"], 0.0)
        self.assertAlmostEqual(summary["total_gross_losses"], -50.0)

    def test_log_index_keeps_same_block_fills_distinct(self):
        """
        Two splits of the same market in one transaction must produce two rows.
        Bare tx hashes would collide on the ledger's UNIQUE key and lose one.
        """
        log_a = _make_split_log(100.0, legs=(1, 2), block=1, log_index=0)
        log_b = _make_split_log(50.0, legs=(1, 2), block=1, log_index=4)
        rows = self.ingestor.events_to_transactions(
            CTFEventDecoder.decode_logs([log_a, log_b]), TIMESTAMPS)
        self.assertEqual(len(set(r["tx_hash"] for r in rows)), 4)
        process_batch(rows, db_path=self.db_path)

        loser = canonical_symbol(condition_id=CONDITION_ID, index_set=1)
        open_lots = PolymarketChainIngestor.build_loser_writeoffs(
            [loser], "2026-03-01 10:00:00", db_path=self.db_path)
        self.assertAlmostEqual(open_lots[0]["quantity"], 150.0)  # both splits survived

    def test_event_without_block_timestamp_is_skipped(self):
        rows = self.ingestor.events_to_transactions(
            CTFEventDecoder.decode_logs([_make_split_log(block=99)]), TIMESTAMPS)
        self.assertEqual(rows, [])

    def test_clob_fill_buy_and_sell(self):
        buy = self.ingestor.fill_to_transaction({
            "id": "0xfill1", "timestamp": "1767610800", "transactionHash": "0x" + "aa" * 32,
            "maker": WALLET, "makerAssetId": "0", "takerAssetId": "123456789",
            "makerAmountFilled": "40000000", "takerAmountFilled": "100000000", "fee": "0",
        })
        self.assertEqual(buy["side"], "BUY")
        self.assertAlmostEqual(buy["quantity"], 100.0)
        self.assertAlmostEqual(buy["price"], 0.40)

        sell = self.ingestor.fill_to_transaction({
            "id": "0xfill2", "timestamp": "1767610800", "transactionHash": "0x" + "bb" * 32,
            "maker": WALLET, "makerAssetId": "123456789", "takerAssetId": "0",
            "makerAmountFilled": "100000000", "takerAmountFilled": "95000000", "fee": "1000000",
        })
        self.assertEqual(sell["side"], "SELL")
        self.assertAlmostEqual(sell["price"], 0.95)
        self.assertAlmostEqual(sell["fee"], 1.0)

    def test_token_for_token_fill_is_skipped(self):
        """Neither leg is collateral, so there is no USD basis to record."""
        self.assertIsNone(self.ingestor.fill_to_transaction({
            "id": "0xfill3", "timestamp": "1767610800", "makerAssetId": "111", "takerAssetId": "222",
            "makerAmountFilled": "1000000", "takerAmountFilled": "1000000",
        }))


class TestCSVWatcher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_path = root / "test_tax.db"
        init_db(self.db_path)
        self.imports = root / "imports"
        self.imports.mkdir()
        self.watcher = CSVWatcher(imports_dir=self.imports, db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, name, header, rows):
        path = self.imports / name
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def _summary(self):
        return calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)

    def test_classifies_by_filename_header_and_side(self):
        self.assertEqual(classify_csv(Path("spot_kraken.csv"), [{"side": "BUY"}])[0], "spot")
        self.assertEqual(classify_csv(Path("deribit_options.csv"), [{"side": "BUY"}])[0], "options")
        self.assertEqual(classify_csv(Path("polymarket_2026.csv"), [{"side": "BUY"}])[0], "polymarket")
        self.assertEqual(classify_csv(Path("export.csv"), [{"side": "OPTION_EXPIRE"}])[0], "options")
        self.assertEqual(classify_csv(Path("export.csv"), [{"side": "REDEEM"}])[0], "polymarket")
        self.assertEqual(classify_csv(Path("export.csv"), [{"source": "spot", "side": "BUY"}])[0], "spot")

    def test_ambiguous_file_is_rejected_not_guessed(self):
        """Silently filing options under crypto spot is invisible and permanent."""
        with self.assertRaises(ClassificationError):
            classify_csv(Path("export.csv"), [{"side": "BUY", "symbol": "XYZ"}])

    def test_ingests_all_three_sources(self):
        self._write("spot_kraken.csv", ["timestamp", "symbol", "side", "quantity", "price"],
                    [["2026-01-01 10:00:00", "ETH/USDC", "BUY", 1, 2000],
                     ["2026-01-15 10:00:00", "ETH/USDC", "SELL", 1, 3000]])
        self._write("polymarket_export.csv", ["timestamp", "symbol", "side", "quantity", "price"],
                    [["2026-01-10 12:00:00", "MARKET_A_YES", "BUY", 1000, 0.40],
                     ["2026-01-20 12:00:00", "MARKET_A_YES", "REDEEM", 1000, 1.00]])
        self._write("deribit_options.csv", ["timestamp", "symbol", "side", "quantity", "price"],
                    [["2026-01-05 10:00:00", "ETH-3500-CALL", "OPTION_BUY", 1, 400],
                     ["2026-01-30 10:00:00", "ETH-3500-CALL", "OPTION_EXPIRE", 1, 0]])

        results = self.watcher.scan_once(require_stable=False)
        self.assertTrue(all(r["status"] == "ok" for r in results))
        # +1000 spot, +600 polymarket, -400 options
        self.assertAlmostEqual(self._summary()["net_capital_gains"], 1200.0)
        self.assertEqual(len(list(self.imports.glob("*.csv"))), 0)

    def test_processed_files_are_archived_and_failures_quarantined(self):
        self._write("spot_ok.csv", ["timestamp", "symbol", "side", "quantity", "price"],
                    [["2026-01-01 10:00:00", "ETH/USDC", "BUY", 1, 2000]])
        self._write("mystery.csv", ["timestamp", "symbol", "side", "quantity", "price"],
                    [["2026-01-01 10:00:00", "XYZ", "BUY", 1, 1]])
        self.watcher.scan_once(require_stable=False)
        self.assertEqual(len(list((self.imports / "processed").glob("*.csv"))), 1)
        self.assertEqual(len(list((self.imports / "failed").glob("*.csv"))), 1)

    def test_reimport_is_idempotent(self):
        """The same export dropped repeatedly must not multiply realised gains."""
        for _ in range(3):
            self._write("spot_kraken.csv", ["timestamp", "symbol", "side", "quantity", "price"],
                        [["2026-01-01 10:00:00", "ETH/USDC", "BUY", 1, 2000],
                         ["2026-01-15 10:00:00", "ETH/USDC", "SELL", 1, 3000]])
            self.watcher.scan_once(require_stable=False)
            self.assertAlmostEqual(self._summary()["net_capital_gains"], 1000.0)

    def test_partially_written_file_waits_a_cycle(self):
        self._write("spot_kraken.csv", ["timestamp", "symbol", "side", "quantity", "price"],
                    [["2026-01-01 10:00:00", "ETH/USDC", "BUY", 1, 2000]])
        self.assertEqual(self.watcher.scan_once(), [])            # first sighting: defer
        self.assertEqual(len(self.watcher.scan_once()), 1)        # unchanged: ingest

    def test_empty_and_headerless_files_fail_cleanly(self):
        (self.imports / "spot_empty.csv").write_text("timestamp,symbol,side,quantity,price\n", encoding="utf-8")
        results = self.watcher.scan_once(require_stable=False)
        self.assertEqual(results[0]["status"], "failed")
        self.assertIn("no data rows", results[0]["reason"])


class TestMonarchHook(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        # +$1,000 realised -> $350 escrow at the 35% composite rate.
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 3000.0, "2026-01-15 10:00:00"),
        ], db_path=self.db_path)
        self.hook = MonarchBankrollHook(tax_year=2026, db_path=self.db_path,
                                        config=TEST_CONFIG, max_position_pct=0.05)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_safe_bankroll_excludes_escrow(self):
        self.assertAlmostEqual(self.hook.get_tax_escrow(), 350.0)
        self.assertAlmostEqual(self.hook.get_safe_bankroll(), 9650.0)
        self.assertAlmostEqual(self.hook.max_position_size(), 482.5)

    def test_order_within_limits_is_approved_unchanged(self):
        decision = self.hook.check_order(300.0)
        self.assertTrue(decision.approved)
        self.assertAlmostEqual(decision.approved_notional, 300.0)

    def test_oversized_order_is_clamped_not_rejected(self):
        decision = self.hook.check_order(5000.0)
        self.assertTrue(decision.approved)
        self.assertAlmostEqual(decision.approved_notional, 482.5)
        self.assertIn("per-order cap", decision.reason)

    def test_live_cash_overrides_static_config(self):
        """The config balance is stale the moment anything trades."""
        self.assertAlmostEqual(self.hook.get_safe_bankroll(live_cash=5000.0), 4650.0)

    def test_escrow_exceeding_cash_rejects_everything(self):
        decision = self.hook.check_order(100.0, live_cash=200.0)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.approved_notional, 0.0)
        self.assertIn("no risk capital", decision.reason)

    def test_already_deployed_capital_reduces_headroom(self):
        """A burst of orders inside one cache window can't all claim the same dollars."""
        decision = self.hook.check_order(400.0, already_deployed=9600.0)
        self.assertTrue(decision.approved)
        self.assertAlmostEqual(decision.approved_notional, 50.0)
        decision = self.hook.check_order(400.0, already_deployed=9650.0)
        self.assertFalse(decision.approved)

    def test_sub_minimum_order_is_rejected(self):
        self.assertFalse(self.hook.check_order(0.25).approved)

    def test_non_positive_notional_is_rejected(self):
        self.assertFalse(self.hook.check_order(0.0).approved)
        self.assertFalse(self.hook.check_order(-100.0).approved)

    def test_unreadable_ledger_fails_closed(self):
        """An accounting outage must not fail-open into unlimited sizing."""
        broken = MonarchBankrollHook(tax_year=2026, config=TEST_CONFIG,
                                     db_path=Path(self.temp_dir.name) / "missing" / "nope.db")
        decision = broken.check_order(100.0)
        self.assertFalse(decision.approved)
        self.assertTrue(decision.stale)
        self.assertEqual(decision.approved_notional, 0.0)

    def test_snapshot_is_cached_until_refreshed(self):
        first = self.hook.snapshot()
        self.assertIs(self.hook.snapshot(), first)
        self.assertIsNot(self.hook.refresh(), first)

    def test_size_order_returns_the_clamped_number(self):
        self.assertAlmostEqual(self.hook.size_order(5000.0), 482.5)
        self.assertEqual(self.hook.size_order(0.10), 0.0)


# ============================================================================
# ROUND 2: reorg horizon, market resolution sync, Monarch gate
# ============================================================================

class _FakeRPC:
    """Stands in for PolygonRPCClient: no sockets, fully scripted answers."""

    def __init__(self, head=1_000_000, finalized=None, ratios=None):
        self.head = head
        self.finalized = finalized
        self.ratios = ratios or {}
        self.ratio_calls = []

    def block_number(self):
        return self.head

    def finalized_block_number(self):
        return self.finalized

    def safe_block_number(self, confirmations=REORG_SAFETY_BLOCKS):
        return PolygonRPCClient.safe_block_number(self, confirmations)

    def get_payout_ratios(self, condition_id, contract=None):
        self.ratio_calls.append(condition_id)
        return self.ratios.get(condition_id, [])


class _FakeResolver:
    """Market metadata and resolution state from a dict instead of the Gamma API."""

    def __init__(self, markets=None):
        self.markets = markets or {}
        self._cache = {}
        self.state_calls = []
        for condition_id, market in self.markets.items():
            self._cache[condition_id] = {
                "slug": market.get("slug", ""),
                "question": market.get("question", ""),
                "outcomes": market.get("outcomes", []),
                "token_ids": market.get("token_ids", []),
                "condition_id": condition_id,
            }

    def fetch_market_state(self, condition_id):
        self.state_calls.append(condition_id)
        return self.markets.get(condition_id)

    def by_condition(self, condition_id):
        return self._cache.get(condition_id)

    def resolve_symbol(self, symbol, max_split_attempts=4):
        """Offline stand-in: only what was explicitly remembered, never a Gamma call."""
        entry = self._cache.get(f"symbol:{symbol}")
        return dict(entry) if entry else None

    def remember_symbol(self, symbol, condition_id, slug="", token_id=""):
        self._cache[f"symbol:{symbol}"] = {"condition_id": str(condition_id).lower(),
                                           "slug": slug, "token_id": token_id}

    def save(self):
        pass


class TestReorgSafeHorizon(unittest.TestCase):
    """
    A reorged log that has been through the FIFO engine has already minted tax
    lots and realized_pnl rows, and nothing ever retracts them.
    """

    def test_falls_back_to_head_minus_confirmations(self):
        self.assertEqual(_FakeRPC(head=1000, finalized=None).safe_block_number(64), 936)

    def test_optimistic_finalized_tag_does_not_override_the_floor(self):
        """
        SUPERSEDES an earlier test that asserted `finalized` always wins. Probing
        real nodes on 2026-09-02 showed publicnode and drpc report finalized at
        head-4 and head-3, which is not Polygon finality - so trusting the tag
        synced to within 4 blocks of the tip and voided the guard. The horizon is
        now the more conservative of the two. See
        TestReorgHorizonAgainstRealNodeBehaviour for the measured cases.
        """
        self.assertEqual(_FakeRPC(head=1000, finalized=940).safe_block_number(64), 936)

    def test_conservative_finalized_tag_is_honoured(self):
        self.assertEqual(_FakeRPC(head=1000, finalized=800).safe_block_number(64), 800)

    def test_never_returns_a_negative_block(self):
        self.assertEqual(_FakeRPC(head=10, finalized=None).safe_block_number(64), 0)

    def test_default_confirmations_is_64(self):
        self.assertEqual(REORG_SAFETY_BLOCKS, 64)

    def test_open_ended_sync_stops_at_the_safe_head(self):
        ingestor = PolymarketChainIngestor(offline=True, rpc=_FakeRPC(head=1000))
        self.assertEqual(ingestor.block_ceiling(None), 936)

    def test_explicit_to_block_is_capped_at_the_safe_head(self):
        """Asking for the unfinalised tip is an oversight, not an instruction."""
        ingestor = PolymarketChainIngestor(offline=True, rpc=_FakeRPC(head=1000))
        self.assertEqual(ingestor.block_ceiling(999), 936)

    def test_explicit_to_block_below_the_horizon_is_honoured(self):
        ingestor = PolymarketChainIngestor(offline=True, rpc=_FakeRPC(head=1000))
        self.assertEqual(ingestor.block_ceiling(500), 500)

    def test_confirmations_are_configurable(self):
        ingestor = PolymarketChainIngestor(offline=True, rpc=_FakeRPC(head=1000), confirmations=200)
        self.assertEqual(ingestor.block_ceiling(None), 800)


class TestMarketResolutionSync(unittest.TestCase):
    SLUG = "will-fed-cut-rates"
    RESOLVED_MARKET = {
        "slug": SLUG, "conditionId": CONDITION_ID, "closed": True,
        "outcomes": ["Yes", "No"], "outcomePrices": '["0", "1"]',
        "closedTime": "2026-03-01T18:00:00Z",
    }

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        self.yes = canonical_symbol(slug=self.SLUG, outcome="Yes")
        self.no = canonical_symbol(slug=self.SLUG, outcome="No")
        # Split $100: 100 shares of each leg at $0.50 basis.
        process_batch([
            {"source": "polymarket", "tx_hash": "split#0#1", "timestamp": "2026-01-05 10:00:00",
             "asset_class": "prediction_market", "symbol": self.yes, "side": "BUY",
             "quantity": 100.0, "price": 0.5, "fee": 0.0, "total_value": 50.0, "notes": ""},
            {"source": "polymarket", "tx_hash": "split#0#2", "timestamp": "2026-01-05 10:00:00",
             "asset_class": "prediction_market", "symbol": self.no, "side": "BUY",
             "quantity": 100.0, "price": 0.5, "fee": 0.0, "total_value": 50.0, "notes": ""},
        ], db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _sync(self, markets=None, ratios=None, rpc=True, **kwargs):
        return MarketResolutionSync(
            db_path=self.db_path,
            resolver=_FakeResolver(markets if markets is not None else {CONDITION_ID: self.RESOLVED_MARKET}),
            rpc=_FakeRPC(ratios=ratios if ratios is not None else {CONDITION_ID: [0.0, 1.0]}) if rpc else None,
            **kwargs)

    def _summary(self):
        return calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)

    def test_finds_open_prediction_positions(self):
        self.assertEqual(self._sync().open_positions(), {self.yes: 100.0, self.no: 100.0})

    def test_maps_symbols_back_to_conditions(self):
        """
        SUPERSEDES a version asserting `(condition_id, outcome_index)` tuples. The
        index is no longer carried here - a cached entry can be stale and a trade
        row's own `outcomeIndex` is garbage on ~6% of rows, and picking the wrong
        leg settles a winner as worthless. It is derived in `plan()` from Gamma's
        authoritative outcome order instead.
        """
        index = self._sync().symbol_to_condition()
        self.assertEqual(index[self.yes], CONDITION_ID)
        self.assertEqual(index[self.no], CONDITION_ID)
        # The on-chain fallback naming resolves to the same condition.
        self.assertEqual(index[canonical_symbol(condition_id=CONDITION_ID, index_set=2)],
                         CONDITION_ID)

    def test_outcome_index_comes_from_the_market_outcome_order(self):
        market = {"slug": self.SLUG, "outcomes": ["Yes", "No"]}
        self.assertEqual(
            MarketResolutionSync.outcome_index_for_symbol(self.yes, market, CONDITION_ID), 0)
        self.assertEqual(
            MarketResolutionSync.outcome_index_for_symbol(self.no, market, CONDITION_ID), 1)
        self.assertIsNone(
            MarketResolutionSync.outcome_index_for_symbol("UNRELATED", market, CONDITION_ID))

    def test_data_api_fills_record_their_condition_for_later_settlement(self):
        """
        REGRESSION: the Data API builds symbols from a trade row without asking
        Gamma, which left the metadata cache empty - so `resolve-markets` mapped
        NOTHING and reported every open position as "no condition id on record".
        """
        resolver = PolymarketMarketResolver(
            cache_path=Path(self.temp_dir.name) / "cache.json", offline=True)
        ingestor = PolymarketChainIngestor(offline=True, resolver=resolver)
        ingestor.data_api_trade_to_transaction({
            "transactionHash": "0xaa", "asset": "1", "side": "BUY", "size": 10.0, "price": 0.5,
            "timestamp": 1600000000, "slug": self.SLUG, "outcome": "Yes",
            "conditionId": CONDITION_ID, "outcomeIndex": 999,
        })
        self.assertEqual(resolver._cache[f"symbol:{self.yes}"]["condition_id"],
                         CONDITION_ID.lower())

    def test_settles_both_legs_together_for_a_net_wash(self):
        """
        Split-and-hold to resolution is a wash. Booking the loser alone would
        invent a $50 loss, lower the escrow, and leave the reserve short.
        """
        syncer = self._sync()
        plan = syncer.plan()
        self.assertEqual(len(plan.settlements), 2)
        self.assertEqual(syncer.apply(plan), 2)
        summary = self._summary()
        self.assertAlmostEqual(summary["net_capital_gains"], 0.0)
        self.assertAlmostEqual(summary["total_gross_gains"], 50.0)
        self.assertAlmostEqual(summary["total_gross_losses"], -50.0)

    def test_settlement_is_dated_to_resolution_not_today(self):
        """The settlement date picks the tax year."""
        rows = self._sync().plan().settlements
        self.assertTrue(all(r["timestamp"] == "2026-03-01 18:00:00" for r in rows))

    def test_payout_ratios_come_from_chain(self):
        rows = {r["symbol"]: r["price"] for r in self._sync().plan().settlements}
        self.assertEqual(rows[self.yes], 0.0)
        self.assertEqual(rows[self.no], 1.0)

    def test_open_market_is_skipped(self):
        market = dict(self.RESOLVED_MARKET, closed=False)
        plan = self._sync(markets={CONDITION_ID: market}).plan()
        self.assertEqual(plan.settlements, [])
        self.assertIn("still open", plan.skipped[0][1])

    def test_closed_but_unresolved_is_skipped_without_trust_gamma(self):
        """Gamma `closed` means trading stopped, not that payouts were reported."""
        plan = self._sync(ratios={CONDITION_ID: []}).plan()
        self.assertEqual(plan.settlements, [])
        self.assertIn("no payouts yet", plan.skipped[0][1])

    def test_trust_gamma_falls_back_to_outcome_prices(self):
        plan = self._sync(ratios={CONDITION_ID: []}, trust_gamma=True).plan()
        self.assertEqual(len(plan.settlements), 2)
        self.assertEqual(plan.resolved_conditions[0]["verified_by"], "gamma")

    def test_no_rpc_without_trust_gamma_refuses_to_settle(self):
        plan = self._sync(rpc=False).plan()
        self.assertEqual(plan.settlements, [])
        self.assertIn("no Polygon RPC", plan.skipped[0][1])

    def test_unmappable_symbol_is_reported_not_guessed(self):
        process_batch([{"source": "polymarket", "tx_hash": "manual_x", "timestamp": "2026-01-05 10:00:00",
                        "asset_class": "prediction_market", "symbol": "HAND_ENTERED_YES", "side": "BUY",
                        "quantity": 10.0, "price": 0.5, "fee": 0.0, "total_value": 5.0, "notes": ""}],
                      db_path=self.db_path)
        plan = self._sync().plan()
        self.assertIn("HAND_ENTERED_YES", [subject for subject, _ in plan.skipped])

    def test_missing_resolution_date_is_skipped_unless_as_of_given(self):
        market = {k: v for k, v in self.RESOLVED_MARKET.items() if k != "closedTime"}
        syncer = self._sync(markets={CONDITION_ID: market})
        self.assertEqual(syncer.plan().settlements, [])
        rows = syncer.plan(as_of="2026-04-01 00:00:00").settlements
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["timestamp"] == "2026-04-01 00:00:00" for r in rows))

    def test_losers_only_leaves_the_winner_open(self):
        plan = self._sync(losers_only=True).plan()
        self.assertEqual([r["symbol"] for r in plan.settlements], [self.yes])
        self.assertEqual(plan.settlements[0]["price"], 0.0)

    def test_applying_twice_is_idempotent(self):
        syncer = self._sync()
        syncer.apply(syncer.plan())
        first = self._summary()["net_capital_gains"]
        syncer.apply(syncer.plan())   # lots are closed now; the second plan is empty
        self.assertAlmostEqual(self._summary()["net_capital_gains"], first)

    def test_gamma_price_vector_validation(self):
        """
        SUPERSEDES an earlier version that accepted `["0.5","0.5"]` as a 50/50
        payout. Measuring 300 real closed markets showed Gamma publishes the LAST
        TRADE, not the settlement - so a fractional vector is indistinguishable
        from a market that merely stopped trading at that mid, and accepting one
        books a fabricated settlement. See TestGammaPayoutValidation.
        """
        self.assertEqual(gamma_payout_ratios({"outcomePrices": '["0","1"]'}), [0.0, 1.0])
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["0.5","0.5"]'}))
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["0.62","0.41"]'}))
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": "[]"}))
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["nonsense"]'}))

    def test_gamma_timestamp_formats(self):
        self.assertEqual(parse_gamma_timestamp("2026-03-01T18:00:00Z"), "2026-03-01 18:00:00")
        self.assertEqual(parse_gamma_timestamp("2026-03-01"), "2026-03-01 00:00:00")
        self.assertIsNone(parse_gamma_timestamp(""))
        self.assertIsNone(parse_gamma_timestamp("not a date"))

    def test_plan_renders_without_raising(self):
        self.assertIn("MARKET RESOLUTION PLAN", self._sync().plan().render())


class TestMonarchTaxGate(unittest.TestCase):
    """
    Exercises the Monarch shim by loading it from its own path - Monarch is not
    an importable package, and the test must not depend on it becoming one.
    """

    GATE_PATH = Path(__file__).resolve().parents[2] / "Polymarket" / "Polymarket_Monarch" / "tax_gate.py"

    @classmethod
    def setUpClass(cls):
        if not cls.GATE_PATH.exists():
            raise unittest.SkipTest(f"Monarch shim not found at {cls.GATE_PATH}")
        spec = importlib.util.spec_from_file_location("monarch_tax_gate", cls.GATE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 3000.0, "2026-01-15 10:00:00"),
        ], db_path=self.db_path)   # +$1,000 -> $350 escrow -> $9,650 safe
        hook = MonarchBankrollHook(tax_year=2026, db_path=self.db_path,
                                   config=TEST_CONFIG, max_position_pct=0.05)
        self.gate = self.mod.TaxGate(hook=hook)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_size_within_limits_passes_through(self):
        sized = self.gate.clamp_shares(100.0, cost_per_share=1.0)
        self.assertTrue(sized.gated)
        self.assertAlmostEqual(sized.approved_shares, 100.0)
        self.assertFalse(sized.clamped)

    def test_oversized_request_is_clamped(self):
        sized = self.gate.clamp_shares(5000.0, cost_per_share=1.0)
        self.assertTrue(sized.clamped)
        self.assertAlmostEqual(sized.approved_shares, 482.5)   # 5% of $9,650

    def test_cost_per_share_converts_shares_to_notional(self):
        """A dutch book set costs the summed ask, not $1 per leg."""
        sized = self.gate.clamp_shares(5000.0, cost_per_share=0.50)
        self.assertAlmostEqual(sized.approved_shares, 965.0)   # $482.50 / $0.50

    def test_unavailable_agent_fails_open_but_says_so(self):
        gate = self.mod.TaxGate(hook=None, enabled=False)
        sized = gate.clamp_shares(5000.0)
        self.assertFalse(sized.gated)
        self.assertAlmostEqual(sized.approved_shares, 5000.0)
        self.assertIn("UNGATED", gate.status_line())

    def test_unreadable_ledger_is_reported_as_ungated(self):
        broken = MonarchBankrollHook(tax_year=2026, config=TEST_CONFIG,
                                     db_path=Path(self.temp_dir.name) / "missing" / "nope.db")
        gate = self.mod.TaxGate(hook=broken)
        self.assertFalse(gate.available)
        self.assertIn("UNGATED", gate.status_line())

    def test_zero_cost_per_share_is_not_clamped(self):
        sized = self.gate.clamp_shares(100.0, cost_per_share=0.0)
        self.assertFalse(sized.gated)
        self.assertAlmostEqual(sized.approved_shares, 100.0)

    def test_blocked_when_escrow_exceeds_cash(self):
        gate = self.mod.TaxGate(hook=MonarchBankrollHook(
            tax_year=2026, db_path=self.db_path, config=TEST_CONFIG), live_cash=100.0)
        sized = gate.clamp_shares(100.0)
        self.assertTrue(sized.blocked)
        self.assertEqual(sized.approved_shares, 0.0)

    def test_status_line_reports_escrow(self):
        line = self.gate.status_line()
        self.assertIn("9,650.00", line)
        self.assertIn("350.00", line)


class TestMonarchWiring(unittest.TestCase):
    """
    Source-level checks that the Monarch tools actually route sizing through the
    gate. Importing dutched_arb here would drag in rich, requests and Monarch's
    whole module graph, so the wiring is verified by inspection.
    """

    MONARCH = Path(__file__).resolve().parents[2] / "Polymarket" / "Polymarket_Monarch"

    def setUp(self):
        if not (self.MONARCH / "dutched_arb.py").exists():
            self.skipTest("Polymarket_Monarch not present")

    def test_dutched_arb_gates_its_share_sizing(self):
        source = (self.MONARCH / "dutched_arb.py").read_text(encoding="utf-8")
        self.assertIn("from tax_gate import", source)
        self.assertIn("def gate_shares(", source)
        self.assertIn("sizing = gate_shares(shares, gate, cost_per_share=max_ask_sum)", source)
        # Depth must be priced against the CLAMPED size, never the requested one.
        self.assertIn("price_with_depth(h, tradeable_shares)", source)
        self.assertIn("add_tax_arguments(parser)", source)

    def test_dashboard_shows_the_status_line(self):
        source = (self.MONARCH / "terminal_dashboard.py").read_text(encoding="utf-8")
        self.assertIn("from tax_gate import TaxGate", source)
        self.assertIn("TAX_GATE.status_line()", source)
        self.assertIn('Layout(name="header", size=5)', source)


# ============================================================================
# ROUND 3: WAL concurrency, HIFO, loss harvesting, quarterly calendar
# ============================================================================

class TestConcurrency(unittest.TestCase):
    """
    The agent is no longer one process: the CSV watcher polls in one, a Monarch
    scanner reads through the bankroll hook in another, chain-sync writes in a
    third. Under the default rollback journal a reader blocks a writer outright.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_wal_and_busy_timeout_are_set(self):
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
        finally:
            conn.close()

    def test_synchronous_stays_full(self):
        """
        NORMAL is the usual WAL companion and is deliberately NOT set: it can lose
        the most recent commits on a power cut, and this is a tax ledger written a
        few times a day, so the speed is worth nothing.
        """
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 2)  # FULL
        finally:
            conn.close()

    def test_open_reader_does_not_block_a_writer(self):
        """The exact failure WAL exists to prevent: 'database is locked'."""
        reader = get_connection(self.db_path)
        try:
            reader.execute("BEGIN")
            reader.execute("SELECT COUNT(*) FROM transactions").fetchone()
            process_batch([
                SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            ], db_path=self.db_path)
        finally:
            reader.rollback()
            reader.close()
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"], 1)
        finally:
            conn.close()

    def test_meta_roundtrip_and_default(self):
        set_meta("probe", "value", db_path=self.db_path)
        self.assertEqual(get_meta("probe", db_path=self.db_path), "value")
        self.assertEqual(get_meta("absent", "fallback", db_path=self.db_path), "fallback")


class TestAccountingMethods(unittest.TestCase):
    """Three ETH lots at $1k / $3k / $2k, then one sale at $2,500."""

    LOTS = [
        SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 1000.0, "2026-01-01 10:00:00"),
        SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 3000.0, "2026-01-02 10:00:00"),
        SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-03 10:00:00"),
        SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 2500.0, "2026-06-01 10:00:00"),
    ]

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _net(self):
        return calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)["net_capital_gains"]

    def test_fifo_consumes_the_oldest_lot(self):
        process_batch(self.LOTS, db_path=self.db_path, method="FIFO")
        self.assertAlmostEqual(self._net(), 1500.0)   # sold against the $1,000 lot

    def test_hifo_consumes_the_most_expensive_lot(self):
        process_batch(self.LOTS, db_path=self.db_path, method="HIFO")
        self.assertAlmostEqual(self._net(), -500.0)   # sold against the $3,000 lot

    def test_hifo_leaves_the_cheap_lots_open(self):
        """
        The cost of HIFO: spending the expensive basis first leaves the cheap old
        lots open, deferring gain rather than removing it.
        """
        process_batch(self.LOTS, db_path=self.db_path, method="HIFO")
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT unit_cost_basis FROM tax_lots WHERE is_closed = 0 "
                                "ORDER BY unit_cost_basis").fetchall()
        finally:
            conn.close()
        self.assertEqual([r["unit_cost_basis"] for r in rows], [1000.0, 2000.0])

    def test_method_ordering_clauses(self):
        self.assertIn("acquired_at ASC", lot_ordering(FIFO))
        self.assertIn("unit_cost_basis DESC", lot_ordering(HIFO))
        # Both end in a fixed tie-break so a rebuild reproduces the original match.
        self.assertTrue(lot_ordering(FIFO).endswith("id ASC"))
        self.assertTrue(lot_ordering(HIFO).endswith("id ASC"))

    def test_unknown_method_falls_back_to_fifo(self):
        self.assertEqual(normalise_method("LIFO"), FIFO)
        self.assertEqual(normalise_method(None), FIFO)
        self.assertEqual(normalise_method("hifo"), HIFO)

    def test_ledger_records_the_method_it_was_built_with(self):
        process_batch(self.LOTS, db_path=self.db_path, method="HIFO")
        self.assertEqual(get_meta(ACCOUNTING_METHOD_KEY, db_path=self.db_path), "HIFO")

    def test_rebuild_switches_method_and_is_reversible(self):
        process_batch(self.LOTS, db_path=self.db_path, method="FIFO")
        self.assertAlmostEqual(self._net(), 1500.0)
        stats = rebuild_lots(db_path=self.db_path, method="HIFO")
        self.assertEqual(stats["transactions"], 4)
        self.assertAlmostEqual(self._net(), -500.0)
        rebuild_lots(db_path=self.db_path, method="FIFO")
        self.assertAlmostEqual(self._net(), 1500.0)

    def test_rebuild_is_idempotent(self):
        process_batch(self.LOTS, db_path=self.db_path, method="FIFO")
        first = rebuild_lots(db_path=self.db_path, method="FIFO")
        second = rebuild_lots(db_path=self.db_path, method="FIFO")
        self.assertEqual(first["realized_rows_after"], second["realized_rows_after"])
        self.assertAlmostEqual(self._net(), 1500.0)

    def test_rebuild_does_not_duplicate_transactions(self):
        """
        The replay path must not go back through the INSERT: that path early-returns
        on the UNIQUE constraint, so every replayed row would be a silent no-op.
        """
        process_batch(self.LOTS, db_path=self.db_path, method="FIFO")
        rebuild_lots(db_path=self.db_path, method="FIFO")
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"], 4)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM realized_pnl").fetchone()["n"], 1)
        finally:
            conn.close()

    def test_summary_flags_a_method_mismatch(self):
        """Editing config.yaml without rebuilding blends two methods in one ledger."""
        process_batch(self.LOTS, db_path=self.db_path, method="HIFO")
        config = dict(TEST_CONFIG, accounting={"method": "FIFO"})
        summary = calculate_tax_summary(2026, db_path=self.db_path, config=config)
        self.assertTrue(summary["method_mismatch"])
        self.assertEqual(summary["accounting_method"], "HIFO")
        self.assertEqual(summary["configured_method"], "FIFO")
        self.assertIn("rebuild", render_hud(summary))

    def test_matching_method_raises_no_flag(self):
        process_batch(self.LOTS, db_path=self.db_path, method="FIFO")
        config = dict(TEST_CONFIG, accounting={"method": "FIFO"})
        self.assertFalse(calculate_tax_summary(2026, db_path=self.db_path,
                                               config=config)["method_mismatch"])


class TestLossHarvester(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "test_tax.db"
        init_db(self.db_path)
        process_batch([
            # +$2,000 short-term realised
            SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 4000.0, "2026-02-01 10:00:00"),
            # open and underwater
            SpotIngestor.create_trade("SOL/USDC", "BUY", 100.0, 200.0, "2026-03-01 10:00:00"),
            # open and up
            SpotIngestor.create_trade("BTC/USDC", "BUY", 1.0, 50000.0, "2026-03-01 10:00:00"),
            # open, no mark anywhere
            SpotIngestor.create_trade("DOGE/USDC", "BUY", 1000.0, 1.0, "2026-04-01 10:00:00"),
        ], db_path=self.db_path, method="FIFO")
        self.marks = self._write_marks({"SOL/USDC": 120.0, "BTC/USDC": 60000.0})

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_marks(self, prices):
        path = self.root / "marks.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["symbol", "price"])
            for symbol, price in prices.items():
                writer.writerow([symbol, price])
        return path

    def _report(self, **kwargs):
        return LossHarvester(db_path=self.db_path, config=TEST_CONFIG,
                             marks_path=self.marks, **kwargs).analyze(
            2026, as_of="2026-09-02 12:00:00")

    def test_finds_only_underwater_marked_lots(self):
        report = self._report()
        self.assertEqual([c.symbol for c in report.candidates], ["SOL/USDC"])
        self.assertAlmostEqual(report.candidates[0].unrealised_loss, -8000.0)

    def test_positions_that_are_up_are_not_candidates(self):
        report = self._report()
        self.assertNotIn("BTC/USDC", [c.symbol for c in report.candidates])
        self.assertAlmostEqual(report.unrealised_gains, 10000.0)

    def test_unmarked_positions_are_excluded_not_guessed(self):
        """A made-up mark produces a made-up loss someone might trade on."""
        report = self._report()
        self.assertEqual([u["symbol"] for u in report.unmarked], ["DOGE/USDC"])
        self.assertNotIn("DOGE/USDC", [c.symbol for c in report.candidates])

    def test_benefit_follows_the_netting_order(self):
        """
        $8,000 of ST loss against $2,000 of ST gain: $2,000 offsets the gain,
        $3,000 goes against ordinary income, $3,000 carries forward at zero value.
        """
        report = self._report()
        self.assertAlmostEqual(report.total_loss, 8000.0)
        self.assertAlmostEqual(report.offsettable_loss, 2000.0)
        self.assertAlmostEqual(report.ordinary_offset, 3000.0)
        self.assertAlmostEqual(report.carryforward_loss, 3000.0)
        self.assertAlmostEqual(report.estimated_tax_saving, 5000.0 * 0.35)

    def test_carryforward_is_valued_at_zero(self):
        """
        Naive tools model loss * rate and overstate a harvest into a flat year by
        an order of magnitude - exactly when someone is tempted to do it.
        """
        harvester = LossHarvester(db_path=self.db_path, config=TEST_CONFIG, marks_path=self.marks)
        benefit = harvester.estimate_benefit(short_term_loss=50000.0, long_term_loss=0.0,
                                             realised_short=0.0, realised_long=0.0)
        self.assertAlmostEqual(benefit["ordinary_offset"], 3000.0)
        self.assertAlmostEqual(benefit["carryforward_loss"], 47000.0)
        self.assertAlmostEqual(benefit["estimated_tax_saving"], 3000.0 * 0.35)

    def test_same_term_netting_before_crossover(self):
        harvester = LossHarvester(db_path=self.db_path, config=TEST_CONFIG, marks_path=self.marks)
        # $1,000 LT loss with $1,000 LT gain available: netted at the LT rate (0.20).
        benefit = harvester.estimate_benefit(0.0, 1000.0, realised_short=5000.0, realised_long=1000.0)
        self.assertAlmostEqual(benefit["offsettable_loss"], 1000.0)
        self.assertAlmostEqual(benefit["estimated_tax_saving"], 1000.0 * 0.20)

    def test_crossover_uses_the_other_term_rate(self):
        harvester = LossHarvester(db_path=self.db_path, config=TEST_CONFIG, marks_path=self.marks)
        # LT loss with no LT gain crosses over to kill a ST gain, saving the ST rate.
        benefit = harvester.estimate_benefit(0.0, 1000.0, realised_short=5000.0, realised_long=0.0)
        self.assertAlmostEqual(benefit["estimated_tax_saving"], 1000.0 * 0.35)

    def test_injected_price_source_beats_the_marks_file(self):
        report = self._report(price_source=lambda symbol, asset_class:
                              50.0 if symbol == "SOL/USDC" else None)
        candidate = next(c for c in report.candidates if c.symbol == "SOL/USDC")
        self.assertAlmostEqual(candidate.mark, 50.0)
        self.assertAlmostEqual(candidate.unrealised_loss, -15000.0)

    def test_long_term_classification(self):
        report = LossHarvester(db_path=self.db_path, config=TEST_CONFIG,
                               marks_path=self.marks).analyze(2026, as_of="2027-06-01 12:00:00")
        self.assertEqual(report.candidates[0].term, "LONG_TERM")

    def test_missing_marks_file_is_not_an_error(self):
        self.assertEqual(load_marks(self.root / "nope.csv"), {})

    def test_unparseable_mark_is_skipped(self):
        path = self.root / "bad.csv"
        path.write_text("symbol,price\nETH/USDC,not-a-number\nSOL/USDC,120\n", encoding="utf-8")
        self.assertEqual(load_marks(path), {"SOL/USDC": 120.0})

    def test_harvest_lowers_the_projected_escrow(self):
        report = self._report()
        self.assertAlmostEqual(report.escrow_before, 700.0)
        self.assertLess(report.escrow_after, report.escrow_before)

    def test_report_renders_and_serialises(self):
        report = self._report()
        self.assertIn("TAX-LOSS HARVESTING SCAN", report.render())
        self.assertIn("Wash-sale", report.render())
        self.assertIsInstance(report.to_dict()["candidates"], list)


class TestTaxCalendar(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _gain_on(self, close_date, buy_price=1000.0, sell_price=2000.0, symbol="ETH/USDC"):
        process_batch([
            SpotIngestor.create_trade(symbol, "BUY", 1.0, buy_price, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade(symbol, "SELL", 1.0, sell_price, close_date),
        ], db_path=self.db_path, method="FIFO")

    def test_periods_are_irs_periods_not_even_quarters(self):
        """Q2 is two months and Q4 is four. Even quarters get every deadline wrong."""
        bounds = quarter_bounds(2026)
        self.assertEqual([(b["start"].isoformat(), b["end"].isoformat()) for b in bounds], [
            ("2026-01-01", "2026-03-31"),
            ("2026-04-01", "2026-05-31"),
            ("2026-06-01", "2026-08-31"),
            ("2026-09-01", "2026-12-31"),
        ])

    def test_q4_is_due_in_the_following_year(self):
        self.assertEqual(quarter_bounds(2026)[3]["due"].year, 2027)

    def test_weekend_deadlines_roll_to_monday(self):
        # 2027-01-15 is a Friday; 2028-01-15 is a Saturday -> Monday the 17th.
        self.assertEqual(quarter_bounds(2026)[3]["due"], date(2027, 1, 15))
        self.assertEqual(quarter_bounds(2027)[3]["due"], date(2028, 1, 17))

    def test_next_business_day(self):
        self.assertEqual(next_business_day(date(2026, 4, 15)), date(2026, 4, 15))  # Wednesday
        self.assertEqual(next_business_day(date(2026, 4, 18)), date(2026, 4, 20))  # Sat -> Mon
        self.assertEqual(next_business_day(date(2026, 4, 19)), date(2026, 4, 20))  # Sun -> Mon

    def test_a_june_1_gain_lands_in_q3_not_q2(self):
        """
        The whole point of the asymmetric periods: May 31 and June 1 are three
        months apart in deadline terms.
        """
        self._gain_on("2026-06-01 10:00:00")
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 9, 2))
        by_label = {q.label: q for q in calendar.quarters}
        self.assertAlmostEqual(by_label["Q2"].net_gain, 0.0)
        self.assertAlmostEqual(by_label["Q3"].net_gain, 1000.0)

    def test_a_may_31_gain_lands_in_q2(self):
        self._gain_on("2026-05-31 23:59:59")
        by_label = {q.label: q for q in build_calendar(
            2026, db_path=self.db_path, config=TEST_CONFIG, today=date(2026, 9, 2)).quarters}
        self.assertAlmostEqual(by_label["Q2"].net_gain, 1000.0)
        self.assertAlmostEqual(by_label["Q3"].net_gain, 0.0)

    def test_tax_due_and_cumulative(self):
        self._gain_on("2026-02-01 10:00:00")
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 9, 2))
        self.assertAlmostEqual(calendar.quarters[0].tax_due, 350.0)      # $1,000 at 35%
        self.assertAlmostEqual(calendar.total_tax_due, 350.0)
        self.assertAlmostEqual(calendar.quarters[3].cumulative_tax_due, 350.0)

    def test_statuses_track_the_date(self):
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 9, 2))
        statuses = {q.label: q.status for q in calendar.quarters}
        self.assertIn(statuses["Q1"], ("CLOSED", "CLOSED_UNPAID"))
        self.assertEqual(statuses["Q3"], "UPCOMING")      # period ended, deadline Sep 15
        self.assertEqual(statuses["Q4"], "IN_PROGRESS")   # period is running

    def test_past_due_tax_is_marked_releasable(self):
        self._gain_on("2026-02-01 10:00:00")
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 9, 2))
        self.assertEqual(calendar.quarters[0].status, "CLOSED_UNPAID")
        self.assertAlmostEqual(calendar.escrow_releasable, 350.0)
        self.assertAlmostEqual(calendar.escrow_reserved, 0.0)
        self.assertAlmostEqual(calendar.shortfall, 0.0)

    def test_gain_before_its_deadline_is_reserved_not_releasable(self):
        self._gain_on("2026-02-01 10:00:00")
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 3, 1))   # before Apr 15
        self.assertAlmostEqual(calendar.escrow_releasable, 0.0)
        self.assertAlmostEqual(calendar.escrow_reserved, 350.0)

    def test_a_losing_quarter_does_not_refund_an_earlier_one(self):
        """
        Each period is priced on its own gains. A Q3 loss reduces the ANNUAL
        liability (which the escrow already reflects) but does not cancel tax
        that fell due in April.
        """
        self._gain_on("2026-02-01 10:00:00", symbol="ETH/USDC")
        self._gain_on("2026-07-01 10:00:00", buy_price=5000.0, sell_price=1000.0, symbol="SOL/USDC")
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 9, 2))
        by_label = {q.label: q for q in calendar.quarters}
        self.assertAlmostEqual(by_label["Q1"].tax_due, 350.0)
        self.assertAlmostEqual(by_label["Q3"].net_gain, -4000.0)
        self.assertAlmostEqual(by_label["Q3"].tax_due, 0.0)

    def test_shortfall_when_escrow_does_not_cover_what_is_due(self):
        self._gain_on("2026-02-01 10:00:00")
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 9, 2))
        calendar.escrow_held = 100.0     # simulate a raided escrow
        recomputed = max(0.0, calendar.quarters[0].tax_due - calendar.escrow_held)
        self.assertAlmostEqual(recomputed, 250.0)

    def test_calendar_renders_and_serialises(self):
        calendar = build_calendar(2026, db_path=self.db_path, config=TEST_CONFIG,
                                  today=date(2026, 9, 2))
        self.assertIn("QUARTERLY ESTIMATED TAX SCHEDULE", calendar.render())
        self.assertEqual(len(calendar.to_dict()["quarters"]), 4)


# ============================================================================
# ROUND 4: RPC endpoint failover, live-verified reorg horizon, Data API fills
# ============================================================================

class _ScriptedRPC(PolygonRPCClient):
    """A real PolygonRPCClient with only the wire replaced, so failover logic runs."""

    def __init__(self, responses, **kwargs):
        super().__init__(**kwargs)
        self.responses = responses      # endpoint -> payload, or an Exception to raise
        self.attempts = []
        self.max_retries = 1            # keep the tests fast
        self.min_interval_s = 0.0

    def _post(self, payload):
        errors = []
        start = self.endpoints.index(self.rpc_url) if self.rpc_url in self.endpoints else 0
        for endpoint in self.endpoints[start:] + self.endpoints[:start]:
            self.attempts.append(endpoint)
            outcome = self.responses.get(endpoint)
            if isinstance(outcome, Exception):
                errors.append(f"{endpoint}: {outcome}")
                continue
            self.rpc_url = endpoint
            return outcome
        raise RPCError("every Polygon RPC endpoint failed -> " + " | ".join(errors))


class TestRPCEndpointFailover(unittest.TestCase):
    """
    The single hardcoded default (polygon-rpc.com) started answering 401 and took
    the whole sync down. A list plus failover is the fix; one URL swapped for
    another would just reset the clock on the same failure.
    """

    ALIVE = "https://polygon-bor-rpc.publicnode.com"
    DEAD = "https://polygon-rpc.com"

    def test_defaults_are_a_nonempty_ordered_list(self):
        self.assertGreaterEqual(len(DEFAULT_POLYGON_RPC_ENDPOINTS), 2)
        self.assertNotIn(self.DEAD, DEFAULT_POLYGON_RPC_ENDPOINTS)

    def test_configured_endpoint_is_tried_first(self):
        client = PolygonRPCClient(rpc_url=self.ALIVE)
        self.assertEqual(client.endpoints[0], self.ALIVE)

    def test_defaults_are_appended_as_fallbacks(self):
        client = PolygonRPCClient(rpc_url=self.DEAD)
        self.assertEqual(client.endpoints[0], self.DEAD)
        self.assertIn(DEFAULT_POLYGON_RPC_ENDPOINTS[0], client.endpoints)

    def test_fallback_can_be_disabled_to_pin_a_private_node(self):
        client = PolygonRPCClient(rpc_url="https://my-private-node.internal", allow_fallback=False)
        self.assertEqual(client.endpoints, ["https://my-private-node.internal"])

    def test_dead_endpoint_fails_over_and_pins_the_working_one(self):
        client = _ScriptedRPC(
            {self.DEAD: RuntimeError("HTTP Error 401: Unauthorized"),
             DEFAULT_POLYGON_RPC_ENDPOINTS[0]: {"jsonrpc": "2.0", "id": 1, "result": "0x64"}},
            rpc_url=self.DEAD)
        self.assertEqual(client.block_number(), 100)
        self.assertEqual(client.rpc_url, DEFAULT_POLYGON_RPC_ENDPOINTS[0])

    def test_all_endpoints_dead_raises_with_every_reason(self):
        client = _ScriptedRPC({e: RuntimeError("dead") for e in DEFAULT_POLYGON_RPC_ENDPOINTS})
        with self.assertRaises(RPCError) as ctx:
            client.block_number()
        self.assertIn("every Polygon RPC endpoint failed", str(ctx.exception))

    def test_http_200_carrying_a_jsonrpc_error_is_still_an_error(self):
        """Ankr answers 200 with an auth error in the body; the status code lies."""
        client = _ScriptedRPC({DEFAULT_POLYGON_RPC_ENDPOINTS[0]: {
            "jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Unauthorized"}}})
        with self.assertRaises(RPCError):
            client.block_number()


class TestReorgHorizonAgainstRealNodeBehaviour(unittest.TestCase):
    """
    Measured live 2026-09-02 at one chain head: publicnode reported
    finalized = head-4, drpc head-3, 1rpc head-500. A 3-4 block lag is not
    Polygon finality (Heimdall milestones run every ~16-32 blocks), so those
    nodes alias the tag near the tip. Preferring `finalized` therefore synced to
    within 4 blocks of head and voided the reorg guard entirely.
    """

    def _client(self, head, finalized):
        client = PolygonRPCClient(allow_fallback=False, rpc_url="https://x")
        client.block_number = lambda: head
        client.finalized_block_number = lambda: finalized
        return client

    def test_optimistic_finalized_tag_is_floored_at_confirmations(self):
        self.assertEqual(self._client(1_000_000, 999_996).safe_block_number(64), 999_936)

    def test_conservative_finalized_tag_is_honoured(self):
        self.assertEqual(self._client(1_000_000, 999_500).safe_block_number(64), 999_500)

    def test_absent_finalized_tag_uses_the_floor(self):
        self.assertEqual(self._client(1_000_000, None).safe_block_number(64), 999_936)

    def test_never_nearer_the_tip_than_confirmations(self):
        for finalized in (None, 999_999, 999_996, 999_500, 0):
            safe = self._client(1_000_000, finalized).safe_block_number(64)
            self.assertLessEqual(safe, 1_000_000 - 64)

    def test_shallow_chain_never_goes_negative(self):
        self.assertEqual(self._client(10, 9).safe_block_number(64), 0)


class TestDataAPIFills(unittest.TestCase):
    """
    Field names and quirks below were read off live Data API responses on
    2026-09-02, not guessed from documentation.
    """

    TRADE = {
        "proxyWallet": "0xc69bd5567b40ef4d11922eaa57e1f9be1c642076",
        "side": "BUY",
        "asset": "85508226579776661565412759095989699451960697255598383218224975352414916440360",
        "conditionId": "0x64c97524cd04b6cb6357cf3973f406eacfea79dde139120c914991894aef3b00",
        "size": 25.0,
        "price": 0.32,
        "timestamp": 1788363463,
        "title": "Will Shakhtar Donetsk win the 2026-27 UCL?",
        "slug": "will-shakhtar-donetsk-win",
        "outcome": "Yes",
        "outcomeIndex": 999,
        "transactionHash": "0xfd03ee9fefaa1111111111111111111111111111111111111111111111111111",
    }

    def setUp(self):
        self.ingestor = PolymarketChainIngestor(offline=True)

    def test_parses_a_real_trade_row(self):
        row = self.ingestor.data_api_trade_to_transaction(self.TRADE)
        self.assertEqual(row["side"], "BUY")
        self.assertEqual(row["symbol"], "WILL-SHAKHTAR-DONETSK-WIN-YES")
        self.assertAlmostEqual(row["quantity"], 25.0)
        self.assertAlmostEqual(row["price"], 0.32)
        self.assertAlmostEqual(row["total_value"], 8.0)
        self.assertEqual(row["asset_class"], "prediction_market")

    def test_size_and_price_are_decimals_not_base_units(self):
        """The chain path deals in 6-decimal base units; this endpoint does not."""
        row = self.ingestor.data_api_trade_to_transaction(self.TRADE)
        self.assertAlmostEqual(row["quantity"], 25.0)      # not 25e-6

    def test_timestamp_is_converted_from_unix(self):
        row = self.ingestor.data_api_trade_to_transaction(self.TRADE)
        self.assertEqual(row["timestamp"], "2026-09-02 15:37:43")

    def test_outcome_index_sentinel_is_ignored(self):
        """
        outcomeIndex was 999 on 32 of 500 live rows. Keying on it would mislabel
        roughly one position in fifteen; the outcome STRING is always populated.
        """
        row = self.ingestor.data_api_trade_to_transaction(dict(self.TRADE, outcomeIndex=999))
        self.assertTrue(row["symbol"].endswith("-YES"))
        flipped = self.ingestor.data_api_trade_to_transaction(dict(self.TRADE, outcome="No"))
        self.assertTrue(flipped["symbol"].endswith("-NO"))

    def test_symbol_matches_the_on_chain_path_for_the_same_position(self):
        """
        The whole point of one symbol authority: a CLOB buy and a CTF redemption
        must close against each other in FIFO rather than leaving an orphan lot.
        """
        row = self.ingestor.data_api_trade_to_transaction(self.TRADE)
        self.assertEqual(row["symbol"], canonical_symbol(slug="will-shakhtar-donetsk-win",
                                                         outcome="Yes"))

    def test_fee_is_zero_because_the_endpoint_reports_none(self):
        row = self.ingestor.data_api_trade_to_transaction(self.TRADE)
        self.assertEqual(row["fee"], 0.0)
        self.assertIn("fees not reported", row["notes"])

    def test_two_markets_in_one_transaction_stay_distinct(self):
        other = dict(self.TRADE, asset="123456789", slug="other-market", outcome="Yes")
        rows = self.ingestor.data_api_trades_to_transactions([self.TRADE, other])
        self.assertEqual(len({r["tx_hash"] for r in rows}), 2)

    def test_same_trade_twice_produces_one_identical_key(self):
        """Re-syncing must be a no-op; the ledger dedupes on this key."""
        rows = self.ingestor.data_api_trades_to_transactions([self.TRADE, dict(self.TRADE)])
        self.assertEqual(len({r["tx_hash"] for r in rows}), 1)

    def test_unusable_rows_are_skipped(self):
        for bad in ({"side": "MERGE"}, dict(self.TRADE, size=0),
                    dict(self.TRADE, timestamp=0), dict(self.TRADE, size="x")):
            self.assertIsNone(self.ingestor.data_api_trade_to_transaction(bad))

    def test_falls_back_to_condition_id_when_metadata_is_missing(self):
        bare = dict(self.TRADE, slug="", outcome="", asset="")
        row = self.ingestor.data_api_trade_to_transaction(bare)
        self.assertTrue(row["symbol"].startswith("CTF-"))

    def test_batch_survives_a_malformed_row(self):
        rows = self.ingestor.data_api_trades_to_transactions(
            [self.TRADE, {"side": "BUY", "size": None}, dict(self.TRADE, asset="999")])
        self.assertEqual(len(rows), 2)

    def test_parsed_rows_run_through_the_fifo_engine(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "test_tax.db"
        init_db(db_path)
        sell = dict(self.TRADE, side="SELL", price=0.50,
                    transactionHash="0xaa" + "11" * 31)
        rows = self.ingestor.data_api_trades_to_transactions([self.TRADE, sell])
        process_batch(rows, db_path=db_path)
        summary = calculate_tax_summary(2026, db_path=db_path, config=TEST_CONFIG)
        self.assertAlmostEqual(summary["net_capital_gains"], 25.0 * (0.50 - 0.32))

    def test_subgraph_is_not_built_unless_explicitly_configured(self):
        """The public Goldsky endpoint 404s; it must not be the default path."""
        self.assertIsNone(PolymarketChainIngestor(offline=True).subgraph)
        self.assertIsNone(PolymarketChainIngestor(offline=True, subgraph_url=None).subgraph)


class TestLogSpanCap(unittest.TestCase):
    """
    Public nodes cap `eth_getLogs` at an undocumented block span (publicnode
    rejects >10,000) and only say so by erroring, so the span is found by halving.

    REGRESSION: the first version of the caching remembered the span of any
    SUCCESSFUL call. The last chunk of a range is often a single block, so the
    cache latched onto 1 and every later query crawled the chain block by block -
    a live sync that had taken seconds ran past four minutes. The cap is only
    meaningful when the node REJECTS a span.
    """

    def _client(self, reject_above=None):
        client = PolygonRPCClient(allow_fallback=False, rpc_url="https://x")
        client.min_interval_s = 0.0
        calls = []

        def fake_call(method, params):
            span = int(params[0]["toBlock"], 16) - int(params[0]["fromBlock"], 16) + 1
            calls.append(span)
            if reject_above is not None and span > reject_above:
                raise RPCError(f"exceed maximum block range: {reject_above}")
            return []

        client.call = fake_call
        return client, calls

    def test_successful_span_is_never_cached(self):
        """A short final chunk must not become the ceiling for every later query."""
        client, _ = self._client()
        client.get_logs("0xctf", ["0xtopic"], 0, 100_001)   # last chunk is 1 block
        self.assertIsNone(client._max_log_span)

    def test_rejected_span_is_cached_and_reused(self):
        client, calls = self._client(reject_above=10_000)
        client.get_logs("0xctf", ["0xtopic"], 0, 19_999)
        self.assertEqual(client._max_log_span, 10_000)
        first_query_calls = len(calls)

        calls.clear()
        client.get_logs("0xctf", ["0xother"], 0, 19_999)
        # Second query starts at the learned cap, so it wastes no rejected call.
        self.assertNotIn(20_000, calls)
        self.assertLess(len(calls), first_query_calls)

    def test_every_block_is_still_covered_after_narrowing(self):
        """Halving must not skip or double-count a range."""
        client, calls = self._client(reject_above=10_000)
        client.get_logs("0xctf", ["0xtopic"], 1_000, 25_999)
        self.assertEqual(sum(s for s in calls if s <= 10_000), 25_000)

    def test_a_node_that_rejects_everything_still_raises(self):
        client, _ = self._client(reject_above=0)
        with self.assertRaises(RPCError):
            client.get_logs("0xctf", ["0xtopic"], 0, 10)


# ============================================================================
# ROUND 5: paging race, proxy-wallet detection
# ============================================================================

class _PagedDataAPI(PolymarketDataAPIClient):
    """Data API client with the wire replaced by a scripted list of pages."""

    def __init__(self, pages, **kwargs):
        super().__init__(**kwargs)
        self.pages = pages
        self.requested = []
        self.min_interval_s = 0.0

    def _get(self, path):
        self.requested.append(path)
        index = len(self.requested) - 1
        return self.pages[index] if index < len(self.pages) else []


def _trade(tx, asset="123", side="BUY", size=1.0, price=0.5, ts=1788363463):
    return {"transactionHash": tx, "asset": asset, "side": side, "size": size,
            "price": price, "timestamp": ts, "slug": "market", "outcome": "Yes",
            "conditionId": "0x" + "11" * 32}


class TestDataAPIPagingRace(unittest.TestCase):
    """
    Offset paging races a live feed. The feed is newest-first, so a trade landing
    mid-walk pushes older rows to a HIGHER offset and the next page re-serves rows
    the previous one already returned. Measured live: a 2,000-trade walk repeated
    15 rows across page boundaries.
    """

    def test_trade_key_identity(self):
        base = _trade("0xAB")
        self.assertEqual(PolymarketDataAPIClient.trade_key(base),
                         PolymarketDataAPIClient.trade_key(_trade("0xab")))
        self.assertNotEqual(PolymarketDataAPIClient.trade_key(base),
                            PolymarketDataAPIClient.trade_key(_trade("0xab", side="SELL")))
        self.assertNotEqual(PolymarketDataAPIClient.trade_key(base),
                            PolymarketDataAPIClient.trade_key(_trade("0xab", asset="999")))

    def test_rows_repeated_across_a_page_boundary_are_deduplicated(self):
        page1 = [_trade(f"0x{i:04x}") for i in range(4)]
        # Two new trades arrive mid-walk, so page 2 re-serves the last two of page 1.
        page2 = page1[2:] + [_trade(f"0x{i:04x}") for i in range(4, 6)]
        client = _PagedDataAPI([page1, page2], page_size=4)
        trades = client.fetch_trades("0xwallet")
        self.assertEqual(len(trades), 6)
        self.assertEqual(len({PolymarketDataAPIClient.trade_key(t) for t in trades}), 6)

    def test_a_fully_repeated_page_adds_nothing(self):
        page = [_trade(f"0x{i:04x}") for i in range(4)]
        client = _PagedDataAPI([page, list(page), []], page_size=4)
        self.assertEqual(len(client.fetch_trades("0xwallet")), 4)

    def test_walk_stops_on_a_short_page(self):
        client = _PagedDataAPI([[_trade("0x01"), _trade("0x02")]], page_size=4)
        client.fetch_trades("0xwallet")
        self.assertEqual(len(client.requested), 1)

    def test_offsets_advance_by_page_size(self):
        pages = [[_trade(f"0x{i:04x}") for i in range(4)], []]
        client = _PagedDataAPI(pages, page_size=4)
        client.fetch_trades("0xwallet")
        self.assertIn("offset=0", client.requested[0])
        self.assertIn("offset=4", client.requested[1])

    def test_deduplication_survives_into_ledger_rows(self):
        page1 = [_trade(f"0x{i:04x}") for i in range(4)]
        page2 = page1[3:] + [_trade("0x00ff")]
        client = _PagedDataAPI([page1, page2], page_size=4)
        ingestor = PolymarketChainIngestor(offline=True)
        rows = ingestor.data_api_trades_to_transactions(client.fetch_trades("0xwallet"))
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({r["tx_hash"] for r in rows}), 5)

    def test_timestamp_filter_still_applies_after_dedup(self):
        page = [_trade("0x01", ts=1000), _trade("0x02", ts=5000)]
        client = _PagedDataAPI([page], page_size=4)
        self.assertEqual(len(client.fetch_trades("0xwallet", from_timestamp=2000)), 1)


class TestProxyWalletDetection(unittest.TestCase):
    """
    Polymarket routes orders through a Gnosis Safe PROXY. `/trades?user=` matches
    only that proxy, while the CTF contract logs against whichever address called
    it -- so configuring the EOA yields on-chain rows and ZERO fills, and cost
    basis gets built from redemptions with no purchases behind them.
    """

    def test_chain_rows_without_fills_warns_about_the_proxy(self):
        message = PolymarketChainIngestor.warn_if_probably_not_a_proxy_wallet("0x" + "ab" * 20, 12, 0)
        self.assertIsNotNone(message)
        self.assertIn("PROXY", message)
        self.assertIn("ZERO CLOB fills", message)

    def test_nothing_at_all_is_a_softer_note(self):
        message = PolymarketChainIngestor.warn_if_probably_not_a_proxy_wallet("0x" + "ab" * 20, 0, 0)
        self.assertIn("[INFO]", message)
        self.assertIn("PROXY", message)

    def test_fills_present_is_silent(self):
        self.assertIsNone(
            PolymarketChainIngestor.warn_if_probably_not_a_proxy_wallet("0x" + "ab" * 20, 5, 5))

    def test_fills_without_chain_rows_is_silent(self):
        """A pure CLOB trader who never split or redeemed is perfectly normal."""
        self.assertIsNone(
            PolymarketChainIngestor.warn_if_probably_not_a_proxy_wallet("0x" + "ab" * 20, 0, 9))


# ============================================================================
# ROUND 6: Gamma closed filter, page-cap warning, fee capitalisation
# ============================================================================

class TestGammaClosedFilter(unittest.TestCase):
    """
    Gamma defaults to `closed=false` and does not say so, so a lookup by
    `condition_ids` or `clob_token_ids` returns NOTHING for a market that has
    resolved. Verified live 2026-09-02 against
    will-joe-biden-get-coronavirus-before-the-election:
        condition_ids=0xe3b4...              -> 0 rows
        condition_ids=0xe3b4...&closed=true  -> 1 row

    This broke `resolve-markets` completely - every resolved condition came back
    as "no Gamma record", so nothing was ever settled - and 16 unit tests passed
    over it because they drive a fake resolver.
    """

    def _resolver(self, responses):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        resolver = PolymarketMarketResolver(cache_path=Path(temp_dir.name) / "cache.json")
        resolver.requested = []

        def fake_request(params):
            resolver.requested.append(params)
            return responses.get(params, [])

        resolver._request = fake_request
        return resolver

    MARKET = {"conditionId": "0xabc", "slug": "resolved-market", "closed": True,
              "outcomes": ["Yes", "No"], "outcomePrices": '["0", "1"]'}

    def test_empty_result_is_retried_with_closed_true(self):
        resolver = self._resolver({"condition_ids=0xabc&closed=true": [self.MARKET]})
        self.assertEqual(resolver._fetch("condition_ids=0xabc"), [self.MARKET])
        self.assertEqual(resolver.requested,
                         ["condition_ids=0xabc", "condition_ids=0xabc&closed=true"])

    def test_open_market_answers_on_the_first_request(self):
        """An open market must not pay for a second round trip."""
        resolver = self._resolver({"condition_ids=0xabc": [self.MARKET]})
        self.assertEqual(resolver._fetch("condition_ids=0xabc"), [self.MARKET])
        self.assertEqual(len(resolver.requested), 1)

    def test_explicit_closed_param_is_not_retried(self):
        resolver = self._resolver({})
        resolver._fetch("condition_ids=0xabc&closed=false")
        self.assertEqual(len(resolver.requested), 1)

    def test_resolved_market_reaches_fetch_market_state(self):
        """The end-to-end path resolve-markets depends on."""
        resolver = self._resolver({"condition_ids=0xabc&closed=true": [self.MARKET]})
        self.assertIsNotNone(resolver.fetch_market_state("0xabc"))

    def test_token_lookup_also_retries(self):
        market = dict(self.MARKET, clobTokenIds='["777"]')
        resolver = self._resolver({"clob_token_ids=777&closed=true": [market]})
        self.assertIsNotNone(resolver.by_token("777"))


class TestGammaPayoutValidation(unittest.TestCase):
    """
    Gamma publishes the LAST TRADE, not the settlement. Measured across 300 closed
    markets on 2026-09-02: a resolved winner reads 0.9999989 and the loser
    1.01e-06, while on-chain `payoutNumerators` returns a clean [0.0, 1.0].

    So "the vector sums to 1.0" is not a test for resolution - a market that
    merely stopped trading at a final mid of [0.97, 0.03] sums to 1.0 too, and
    accepting it would book a fabricated 97%/3% settlement as a payout.
    """

    def test_last_trade_prices_are_snapped_to_the_real_payout(self):
        self.assertEqual(gamma_payout_ratios({"outcomePrices": '["0.0000010", "0.9999989"]'}),
                         [0.0, 1.0])

    def test_clean_binary_resolution(self):
        self.assertEqual(gamma_payout_ratios({"outcomePrices": '["0", "1"]'}), [0.0, 1.0])

    def test_a_final_mid_price_is_refused(self):
        """The dangerous case: sums to 1.0 but is not a resolution."""
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["0.97", "0.03"]'}))
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["0.62", "0.38"]'}))

    def test_void_or_unsettled_is_refused(self):
        """15% of closed markets carry an all-zero vector."""
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["0", "0"]'}))

    def test_fractional_resolution_is_refused_not_guessed(self):
        """
        A genuine 50/50 scalar settlement is indistinguishable from a final mid in
        this field, so --trust-gamma skips it. The on-chain path handles it exactly.
        """
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["0.5", "0.5"]'}))

    def test_multiple_winners_refused(self):
        self.assertIsNone(gamma_payout_ratios({"outcomePrices": '["1", "1"]'}))

    def test_malformed_input_refused(self):
        for raw in ("[]", '["nonsense"]', None, "not json"):
            self.assertIsNone(gamma_payout_ratios({"outcomePrices": raw}))


class TestPageCapWarning(unittest.TestCase):
    """
    A full final page means there is more history the walk never reached. Silence
    hands a high-volume wallet a ledger missing its oldest trades, which removes
    cost basis and reads as higher gains.
    """

    def _client(self, pages, max_pages):
        client = PolymarketDataAPIClient(page_size=2, max_pages=max_pages)
        client.min_interval_s = 0.0
        client._get = lambda path, _p=iter(pages): next(_p, [])
        return client

    def test_warns_when_stopped_by_the_page_cap(self):
        full = [_trade("0x01"), _trade("0x02")]
        client = self._client([full, [_trade("0x03"), _trade("0x04")]], max_pages=2)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            client.fetch_trades("0xwallet")
        self.assertIn("HISTORY IS TRUNCATED", out.getvalue())

    def test_silent_when_the_walk_completes(self):
        client = self._client([[_trade("0x01"), _trade("0x02")], [_trade("0x03")]], max_pages=5)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            client.fetch_trades("0xwallet")
        self.assertNotIn("TRUNCATED", out.getvalue())

    def test_silent_on_an_empty_wallet(self):
        client = self._client([[]], max_pages=5)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            client.fetch_trades("0xwallet")
        self.assertNotIn("TRUNCATED", out.getvalue())


class TestFeeCapitalisation(unittest.TestCase):
    """
    Pins behaviour that ALREADY EXISTS in the lot engine, so it cannot silently
    regress: basis + fee on acquisition, proceeds - fee on disposal.

    Note this lives in `lot_engine`, not `tax_calculator` - the calculator only
    aggregates finished `realized_pnl` rows, so applying fees there again would
    double-count them.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _realized(self):
        conn = get_connection(self.db_path)
        try:
            return conn.execute("SELECT cost_basis, proceeds, net_gain_loss FROM realized_pnl").fetchall()
        finally:
            conn.close()

    def test_buy_fee_is_capitalised_into_basis(self):
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 10.0, 100.0, "2026-01-01 10:00:00", fee=25.0),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 10.0, 110.0, "2026-06-01 10:00:00", fee=0.0),
        ], db_path=self.db_path)
        row = self._realized()[0]
        self.assertAlmostEqual(row["cost_basis"], 1025.0)   # 10*100 + 25

    def test_sell_fee_is_deducted_from_proceeds(self):
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 10.0, 100.0, "2026-01-01 10:00:00", fee=0.0),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 10.0, 110.0, "2026-06-01 10:00:00", fee=25.0),
        ], db_path=self.db_path)
        row = self._realized()[0]
        self.assertAlmostEqual(row["proceeds"], 1075.0)     # 10*110 - 25

    def test_round_trip_fees_reduce_the_taxable_gain(self):
        """The whole point: on a 1-4% edge, fees are most of the profit."""
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 10.0, 100.0, "2026-01-01 10:00:00", fee=25.0),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 10.0, 110.0, "2026-06-01 10:00:00", fee=25.0),
        ], db_path=self.db_path)
        row = self._realized()[0]
        self.assertAlmostEqual(row["cost_basis"], 1025.0)
        self.assertAlmostEqual(row["proceeds"], 1075.0)
        self.assertAlmostEqual(row["net_gain_loss"], 50.0)   # gross 100, less 50 of fees

    def test_sell_fee_is_prorated_across_matched_lots(self):
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 5.0, 100.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "BUY", 5.0, 100.0, "2026-01-02 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 10.0, 110.0, "2026-06-01 10:00:00", fee=30.0),
        ], db_path=self.db_path)
        rows = self._realized()
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(sum(r["proceeds"] for r in rows), 1100.0 - 30.0)

    def test_tax_calculator_does_not_reapply_fees(self):
        """Fees are the lot engine's job; applying them again would double-count."""
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 10.0, 100.0, "2026-01-01 10:00:00", fee=25.0),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 10.0, 110.0, "2026-06-01 10:00:00", fee=25.0),
        ], db_path=self.db_path)
        summary = calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)
        self.assertAlmostEqual(summary["net_capital_gains"], 50.0)
        self.assertAlmostEqual(summary["tax_escrow_reserve"], 17.5)   # 50 * 35%


class TestPolymarketFeeEstimate(unittest.TestCase):
    """
    The Data API reports no fee on any row, so Polymarket basis is gross of fees
    unless a rate is configured. Off by default: a guessed number in a tax ledger
    is the same mistake as a guessed market price.
    """

    TRADE = {"transactionHash": "0xaa", "asset": "1", "side": "BUY", "size": 100.0,
             "price": 0.40, "timestamp": 1788363463, "slug": "m", "outcome": "Yes",
             "conditionId": "0x" + "11" * 32}

    def test_default_is_gross_of_fees_and_says_so(self):
        row = PolymarketChainIngestor(offline=True).data_api_trade_to_transaction(self.TRADE)
        self.assertEqual(row["fee"], 0.0)
        self.assertIn("GROSS of fees", row["notes"])

    def test_configured_rate_books_a_labelled_estimate(self):
        ingestor = PolymarketChainIngestor(offline=True, polymarket_fee_rate=0.02)
        row = ingestor.data_api_trade_to_transaction(self.TRADE)
        self.assertAlmostEqual(row["fee"], 100.0 * 0.40 * 0.02)
        self.assertIn("ESTIMATED", row["notes"])

    def test_estimated_fee_flows_into_cost_basis(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "test_tax.db"
        init_db(db_path)
        ingestor = PolymarketChainIngestor(offline=True, polymarket_fee_rate=0.02)
        sell = dict(self.TRADE, side="SELL", price=0.50, transactionHash="0xbb")
        process_batch(ingestor.data_api_trades_to_transactions([self.TRADE, sell]), db_path=db_path)
        conn = get_connection(db_path)
        try:
            row = conn.execute("SELECT cost_basis, proceeds FROM realized_pnl").fetchone()
        finally:
            conn.close()
        self.assertAlmostEqual(row["cost_basis"], 40.0 + 0.80)    # basis + estimated buy fee
        self.assertAlmostEqual(row["proceeds"], 50.0 - 1.00)      # proceeds - estimated sell fee

    def test_negative_rate_is_clamped(self):
        self.assertEqual(PolymarketChainIngestor(offline=True, polymarket_fee_rate=-1).polymarket_fee_rate, 0.0)


# ============================================================================
# ROUND 6b: cold-cache symbol resolution
# ============================================================================

class TestColdCacheSymbolResolution(unittest.TestCase):
    """
    `harvest --live-marks` and `resolve-markets` both used to read
    `resolver._cache` and nothing else. On a cold cache - fresh checkout, a ledger
    built from CSV imports, a cleared cache file - every position came back
    unmarked or unresolvable. Nothing errored; the reports were silently empty.
    """

    MARKET = {
        "conditionId": "0xfeed", "slug": "will-fed-cut-rates", "closed": True,
        "outcomes": '["Yes", "No"]', "clobTokenIds": '["tokenYES", "tokenNO"]',
        "outcomePrices": '["0", "1"]',
    }

    def _resolver(self, responses):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        resolver = PolymarketMarketResolver(cache_path=Path(temp_dir.name) / "cache.json")
        resolver.requested = []

        def fake_request(params):
            resolver.requested.append(params)
            return responses.get(params, [])

        resolver._request = fake_request
        return resolver

    def test_slug_symbol_resolves_from_an_empty_cache(self):
        resolver = self._resolver({"slug=will-fed-cut-rates": [self.MARKET]})
        self.assertEqual(len(resolver._cache), 0)
        resolved = resolver.resolve_symbol("WILL-FED-CUT-RATES-YES")
        self.assertEqual(resolved["condition_id"], "0xfeed")
        self.assertEqual(resolved["outcome_index"], 0)
        self.assertEqual(resolved["token_id"], "tokenYES")

    def test_second_outcome_maps_to_the_second_slot(self):
        resolver = self._resolver({"slug=will-fed-cut-rates": [self.MARKET]})
        resolved = resolver.resolve_symbol("WILL-FED-CUT-RATES-NO")
        self.assertEqual(resolved["outcome_index"], 1)
        self.assertEqual(resolved["token_id"], "tokenNO")

    def test_split_point_is_searched_right_to_left(self):
        """The slug contains hyphens, so where the outcome starts is ambiguous."""
        market = dict(self.MARKET, slug="who-wins", outcomes='["Donald Trump", "Someone Else"]',
                      clobTokenIds='["tokDT", "tokSE"]')
        resolver = self._resolver({"slug=who-wins": [market]})
        resolved = resolver.resolve_symbol("WHO-WINS-DONALD-TRUMP")
        self.assertEqual(resolved["outcome_index"], 0)
        self.assertEqual(resolved["token_id"], "tokDT")

    def test_resolution_is_cached_so_it_costs_one_lookup(self):
        resolver = self._resolver({"slug=will-fed-cut-rates": [self.MARKET]})
        resolver.resolve_symbol("WILL-FED-CUT-RATES-YES")
        before = len(resolver.requested)
        resolver.resolve_symbol("WILL-FED-CUT-RATES-YES")
        self.assertEqual(len(resolver.requested), before)

    def test_remembered_link_short_circuits_the_network(self):
        resolver = self._resolver({})
        resolver.remember_symbol("SOME-MARKET-YES", "0xabc", "some-market", "tok1")
        resolved = resolver.resolve_symbol("SOME-MARKET-YES")
        self.assertEqual(resolved["condition_id"], "0xabc")
        self.assertEqual(resolved["token_id"], "tok1")
        self.assertEqual(resolver.requested, [])

    def test_unknown_symbol_returns_none_rather_than_guessing(self):
        resolver = self._resolver({})
        self.assertIsNone(resolver.resolve_symbol("NOT-A-REAL-MARKET-YES"))

    def test_split_attempts_are_capped(self):
        resolver = self._resolver({})
        resolver.resolve_symbol("A-B-C-D-E-F-G-H-YES", max_split_attempts=3)
        self.assertLessEqual(len(resolver.requested), 3 * 2)   # each may retry with closed=true

    def test_ctf_symbol_yields_its_outcome_index_without_any_lookup(self):
        """
        The index set is fully encoded in the symbol, so the outcome comes back
        for free - and CTF-form symbols are exactly the ones Gamma cannot help with.
        """
        resolver = self._resolver({})
        resolved = resolver.resolve_symbol("CTF-ABCDEF0123-2")
        self.assertEqual(resolved["outcome_index"], 1)   # index set 2 -> slot 1
        self.assertEqual(resolver.requested, [])

    def test_ctf_symbol_cannot_recover_a_full_condition_id(self):
        """
        `canonical_symbol()` truncates the condition id to 10 of 64 hex chars.
        40 bits of a 256-bit id cannot be reversed, so it is reported empty rather
        than matched to a plausible-looking market.
        """
        resolver = self._resolver({})
        resolved = resolver.resolve_symbol("CTF-ABCDEF0123-2")
        self.assertEqual(resolved["condition_id"], "")
        self.assertEqual(resolved["condition_prefix"], "abcdef0123")

    def test_ctf_prefix_matches_a_condition_already_known(self):
        resolver = self._resolver({})
        resolver._store({"conditionId": "0xabcdef0123456789", "slug": "m",
                         "outcomes": '["Yes","No"]', "clobTokenIds": '["t0","t1"]'})
        resolved = resolver.resolve_symbol("CTF-ABCDEF0123-2")
        self.assertEqual(resolved["condition_id"], "0xabcdef0123456789")
        self.assertEqual(resolved["token_id"], "t1")

    def test_live_marks_find_a_token_on_a_cold_cache(self):
        """REGRESSION: harvest --live-marks silently priced nothing on a fresh run."""
        resolver = self._resolver({"slug=will-fed-cut-rates": [self.MARKET]})
        source = PolymarketMarkSource(resolver=resolver)
        self.assertEqual(source._token_for_symbol("WILL-FED-CUT-RATES-YES"), "tokenYES")

    def test_ctf_chain_rows_record_their_condition_link(self):
        """A wallet that only splits and redeems never produces a CLOB fill."""
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        resolver = PolymarketMarketResolver(
            cache_path=Path(temp_dir.name) / "cache.json", offline=True)
        ingestor = PolymarketChainIngestor(offline=True, resolver=resolver)
        events = CTFEventDecoder.decode_logs([_make_split_log(100.0, legs=(1, 2))])
        rows = ingestor.events_to_transactions(events, TIMESTAMPS)
        for row in rows:
            self.assertEqual(resolver._cache[f"symbol:{row['symbol']}"]["condition_id"],
                             CONDITION_ID.lower())


# ============================================================================
# ROUND 7: negative cache, legacy CTF recovery, category edge sizing
# ============================================================================

class TestNegativeCache(unittest.TestCase):
    """
    A symbol that resolves nowhere costs up to `max_split_attempts` Gamma calls
    every run. Remembering the failure avoids that - but ONLY for the process.
    """

    def _resolver(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        resolver = PolymarketMarketResolver(cache_path=Path(temp_dir.name) / "cache.json")
        resolver.requested = []
        resolver._request = lambda params: (resolver.requested.append(params) or [])
        return resolver

    def test_second_lookup_of_an_unresolvable_symbol_is_free(self):
        resolver = self._resolver()
        resolver.resolve_symbol("NOT-A-MARKET-YES")
        first = len(resolver.requested)
        self.assertGreater(first, 0)
        resolver.resolve_symbol("NOT-A-MARKET-YES")
        self.assertEqual(len(resolver.requested), first)

    def test_negative_results_are_never_written_to_disk(self):
        """
        A Gamma outage is transient. Persisting a negative would permanently
        blacklist a perfectly good market, surfacing weeks later as a position that
        silently refuses to resolve.
        """
        resolver = self._resolver()
        resolver.resolve_symbol("NOT-A-MARKET-YES")
        resolver.save()
        with open(resolver.cache_path, encoding="utf-8") as f:
            written = json.load(f)
        self.assertNotIn("negative:NOT-A-MARKET-YES", written)
        self.assertFalse(any("NOT-A-MARKET" in key for key in written))
        self.assertIn("NOT-A-MARKET-YES", resolver._unresolvable)

    def test_a_fresh_resolver_retries(self):
        """The blacklist dies with the process, so a transient outage self-heals."""
        first = self._resolver()
        first.resolve_symbol("NOT-A-MARKET-YES")
        second = self._resolver()
        second.resolve_symbol("NOT-A-MARKET-YES")
        self.assertGreater(len(second.requested), 0)

    def test_ctf_symbols_are_not_blacklisted(self):
        """Their condition id can still be recovered from chain later."""
        resolver = self._resolver()
        resolver.resolve_symbol("CTF-ABCDEF0123-2")
        self.assertNotIn("CTF-ABCDEF0123-2", resolver._unresolvable)


class TestLegacyCTFRecovery(unittest.TestCase):
    """
    The briefed approach - read the condition id out of `transactions.notes` -
    could not work: notes carried only the first 12 hex characters, exactly like
    the symbol carries 10. Both are prefixes of the same 64-character id. What
    does work is re-reading the original log from chain via the transaction hash.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        self.symbol = canonical_symbol(condition_id=CONDITION_ID, index_set=1)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed(self, tx_hash, notes):
        process_batch([{"source": "polymarket", "tx_hash": tx_hash,
                        "timestamp": "2026-01-05 10:00:00", "asset_class": "prediction_market",
                        "symbol": self.symbol, "side": "BUY", "quantity": 100.0, "price": 0.5,
                        "fee": 0.0, "total_value": 50.0, "notes": notes}], db_path=self.db_path)

    def test_recovers_from_a_note_carrying_the_full_id(self):
        """Rows written from Round 7 on carry the id in full."""
        self._seed("0xaa#0#1", f"CTF SplitPosition | condition {CONDITION_ID}")
        syncer = MarketResolutionSync(db_path=self.db_path, resolver=_FakeResolver())
        self.assertEqual(syncer.recover_condition_id(self.symbol), CONDITION_ID.lower())

    def test_a_truncated_note_alone_recovers_nothing(self):
        """Both prefixes come from the same string; combining them adds no bits."""
        self._seed("nochain", f"condition {CONDITION_ID[:14]}...")
        syncer = MarketResolutionSync(db_path=self.db_path, resolver=_FakeResolver())
        self.assertIsNone(syncer.recover_condition_id(self.symbol))

    def test_recovers_by_re_reading_the_log_from_chain(self):
        self._seed("0xdeadbeef#0#1", "condition 0x1111111111...")
        log = _make_split_log(100.0, legs=(1, 2), block=1, log_index=0)

        class _ReceiptRPC(_FakeRPC):
            def call(self, method, params):
                return {"logs": [log]} if method == "eth_getTransactionReceipt" else None

        syncer = MarketResolutionSync(db_path=self.db_path, resolver=_FakeResolver(),
                                      rpc=_ReceiptRPC())
        self.assertEqual(syncer.recover_condition_id(self.symbol), CONDITION_ID)

    def test_prefix_mismatch_is_refused(self):
        """A 40-bit prefix has real collision risk; a wrong market is worse than none."""
        self._seed("0xaa#0#1", "condition 0x" + "ff" * 32)
        syncer = MarketResolutionSync(db_path=self.db_path, resolver=_FakeResolver())
        self.assertIsNone(syncer.recover_condition_id(self.symbol))

    def test_non_ctf_symbol_returns_none(self):
        syncer = MarketResolutionSync(db_path=self.db_path, resolver=_FakeResolver())
        self.assertIsNone(syncer.recover_condition_id("WILL-FED-CUT-RATES-YES"))


class TestCategoryEdgeSizing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed(self, prefix, wins, total, entry=0.40):
        rows = []
        for i in range(total):
            symbol = f"{prefix}-{i}-YES"
            rows += [
                {"source": "polymarket", "tx_hash": f"b{prefix}{i}", "timestamp": "2026-01-01 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "BUY",
                 "quantity": 100.0, "price": entry, "fee": 0.0, "total_value": 100 * entry, "notes": ""},
                {"source": "polymarket", "tx_hash": f"s{prefix}{i}", "timestamp": "2026-02-01 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "SELL",
                 "quantity": 100.0, "price": 0.95 if i < wins else 0.02, "fee": 0.0,
                 "total_value": 0.0, "notes": ""},
            ]
        process_batch(rows, db_path=self.db_path)

    def _hook(self, **kwargs):
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path, config=TEST_CONFIG,
                                   max_position_pct=0.05, **kwargs)

    def test_categorisation(self):
        self.assertEqual(categorise("BITCOIN-UP-OR-DOWN-SEPT-2-YES"), "crypto-intraday")
        self.assertEqual(categorise("WILL-FED-CUT-RATES-YES"), "macro")
        self.assertEqual(categorise("WILL-TRUMP-WIN-THE-2028-ELECTION-YES"), "politics")
        self.assertEqual(categorise("SOMETHING-ARBITRARY"), "uncategorised")

    def test_wilson_beats_the_naive_shrinkage_at_small_n(self):
        """
        `p_hat - sqrt(p_hat(1-p_hat)/N)` is ZERO-width at p_hat 0 or 1, so three
        wins from three trades reads as certainty and sizes at the maximum.
        """
        naive_3_of_3 = 1.0 - math.sqrt(1.0 * 0.0 / 3)
        self.assertEqual(naive_3_of_3, 1.0)
        self.assertLess(wilson_lower_bound(3, 3), 0.80)
        self.assertGreater(wilson_lower_bound(3, 3), 0.70)

    def test_wilson_converges_on_the_naive_answer_at_large_n(self):
        naive = 0.70 - math.sqrt(0.70 * 0.30 / 100)
        self.assertAlmostEqual(wilson_lower_bound(70, 100), naive, places=2)

    def test_wilson_of_no_trials_is_zero(self):
        self.assertEqual(wilson_lower_bound(0, 0), 0.0)

    def test_kelly_is_zero_when_price_equals_probability(self):
        self.assertAlmostEqual(kelly_fraction_for(0.40, 0.40), 0.0)

    def test_kelly_is_negative_when_the_market_is_against_you(self):
        self.assertLess(kelly_fraction_for(0.30, 0.60), 0.0)

    def test_kelly_grows_with_edge(self):
        self.assertLess(kelly_fraction_for(0.50, 0.40), kelly_fraction_for(0.70, 0.40))

    def test_category_stats_measure_win_rate_and_entry(self):
        self._seed("WILL-FED-CUT-RATES", wins=14, total=20, entry=0.40)
        stats = self._hook().category_stats()
        self.assertIn("macro", stats)
        self.assertEqual(stats["macro"].trades, 20)
        self.assertEqual(stats["macro"].wins, 14)
        self.assertAlmostEqual(stats["macro"].win_rate, 0.70)
        self.assertAlmostEqual(stats["macro"].avg_entry_price, 0.40, places=4)

    def test_sizing_is_clamped_to_the_one_to_eight_percent_band(self):
        self._seed("WILL-FED-CUT-RATES", wins=20, total=20, entry=0.10)
        edge = self._hook().category_stats()["macro"]
        self.assertLessEqual(edge.sizing_pct, MAX_SIZING_PCT)
        self.assertGreaterEqual(edge.sizing_pct, MIN_SIZING_PCT)

    def test_a_losing_category_sizes_to_zero(self):
        """
        SUPERSEDES a version asserting the 1% floor. Under magnitude-adjusted
        Kelly a negative-expectancy category sizes to ZERO - the floor applies to
        positive-expectancy categories, not to books that lose money.
        """
        self._seed("WILL-FED-CUT-RATES", wins=2, total=20, entry=0.40)
        self.assertEqual(self._hook().category_stats()["macro"].sizing_pct, 0.0)

    def test_unmeasured_category_uses_the_flat_cap_not_the_floor(self):
        """
        An unmeasured category is not evidence of a bad edge. Dropping every new
        market to 1% would make the sizer a ratchet that only shrinks into what
        has already been traded.
        """
        edge = self._hook().category_edge("politics")
        self.assertEqual(edge.basis, "default")
        self.assertAlmostEqual(edge.sizing_pct, 0.05)

    def test_price_overrides_the_historical_entry(self):
        self._seed("WILL-FED-CUT-RATES", wins=14, total=20, entry=0.40)
        hook = self._hook()
        cheap = hook.category_edge("macro", price=0.20)
        rich = hook.category_edge("macro", price=0.85)
        self.assertGreater(cheap.sizing_pct, rich.sizing_pct)

    def test_check_order_honours_the_category(self):
        self._seed("WILL-FED-CUT-RATES", wins=14, total=20, entry=0.40)
        hook = self._hook()
        flat = hook.check_order(50_000.0)
        expensive = hook.check_order(50_000.0, category="macro", price=0.90)
        self.assertLess(expensive.approved_notional, flat.approved_notional)
        self.assertEqual(expensive.detail["sizing_basis"], "empirical")

    def test_empirical_sizing_only_tightens_by_default(self):
        """A statistic from your own history does not get to raise a limit you set."""
        self._seed("WILL-FED-CUT-RATES", wins=30, total=40, entry=0.40)
        hook = self._hook()
        self.assertGreater(hook.category_edge("macro").sizing_pct, 0.05)
        self.assertAlmostEqual(hook.check_order(50_000.0, category="macro").detail["sizing_pct"], 0.05)

    def test_upsize_flag_opts_into_the_full_band(self):
        self._seed("WILL-FED-CUT-RATES", wins=30, total=40, entry=0.40)
        hook = self._hook(allow_empirical_upsize=True)
        self.assertGreater(hook.check_order(50_000.0, category="macro").detail["sizing_pct"], 0.05)

    def test_open_positions_are_excluded_from_the_win_rate(self):
        """Counting them lets a book full of losers-in-waiting read as perfect."""
        self._seed("WILL-FED-CUT-RATES", wins=5, total=10, entry=0.40)
        process_batch([{"source": "polymarket", "tx_hash": "open1",
                        "timestamp": "2026-03-01 10:00:00", "asset_class": "prediction_market",
                        "symbol": "WILL-FED-CUT-RATES-OPEN-YES", "side": "BUY", "quantity": 100.0,
                        "price": 0.4, "fee": 0.0, "total_value": 40.0, "notes": ""}],
                      db_path=self.db_path)
        self.assertEqual(self._hook().category_stats()["macro"].trades, 10)

    def test_category_report_renders(self):
        self._seed("WILL-FED-CUT-RATES", wins=14, total=20)
        self.assertIn("macro", self._hook().category_report())

    def test_no_history_reports_cleanly(self):
        self.assertIn("No closed", self._hook().category_report())


class TestMultiOutcomeSettlement(unittest.TestCase):
    """
    7% of closed markets carry 3-7 outcomes, and some resolve FRACTIONALLY
    (verified live: how-many-charges-will-derek-chauvin-be-convicted-of pays
    1/3 on every leg).
    """

    SLUG = "three-way-market"
    CID = "0x" + "22" * 32

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        self.symbols = [canonical_symbol(slug=self.SLUG, outcome=o) for o in ("A", "B", "C")]

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed(self, price):
        process_batch([{"source": "polymarket", "tx_hash": f"b#{i}",
                        "timestamp": "2026-01-05 10:00:00", "asset_class": "prediction_market",
                        "symbol": symbol, "side": "BUY", "quantity": 300.0, "price": price,
                        "fee": 0.0, "total_value": 300 * price, "notes": ""}
                       for i, symbol in enumerate(self.symbols)], db_path=self.db_path)

    def _sync(self, ratios):
        market = {"slug": self.SLUG, "conditionId": self.CID, "closed": True,
                  "outcomes": ["A", "B", "C"], "outcomePrices": '["0","1","0"]',
                  "closedTime": "2026-03-01T18:00:00Z"}
        return MarketResolutionSync(db_path=self.db_path,
                                    resolver=_FakeResolver({self.CID: market}),
                                    rpc=_FakeRPC(ratios={self.CID: ratios}))

    def test_winner_take_all_across_three_outcomes(self):
        self._seed(1 / 3)
        syncer = self._sync([0.0, 1.0, 0.0])
        plan = syncer.plan()
        self.assertEqual(len(plan.settlements), 3)
        prices = {r["symbol"]: r["price"] for r in plan.settlements}
        self.assertEqual(prices[self.symbols[1]], 1.0)
        self.assertEqual(prices[self.symbols[0]], 0.0)
        syncer.apply(plan)
        summary = calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)
        self.assertAlmostEqual(summary["net_capital_gains"], 0.0, places=6)

    def test_fractional_three_way_resolution(self):
        """The chain path handles what --trust-gamma refuses."""
        self._seed(1 / 3)
        third = 1 / 3
        syncer = self._sync([third, third, third])
        plan = syncer.plan()
        self.assertEqual(len(plan.settlements), 3)
        self.assertTrue(all(abs(r["price"] - third) < 1e-9 for r in plan.settlements))
        syncer.apply(plan)
        summary = calculate_tax_summary(2026, db_path=self.db_path, config=TEST_CONFIG)
        self.assertAlmostEqual(summary["net_capital_gains"], 0.0, places=6)

    def test_winner_beyond_the_second_slot(self):
        self._seed(1 / 3)
        plan = self._sync([0.0, 0.0, 1.0]).plan()
        prices = {r["symbol"]: r["price"] for r in plan.settlements}
        self.assertEqual(prices[self.symbols[2]], 1.0)

    def test_combinatorial_index_set_is_skipped_not_mis_settled(self):
        """
        A position spanning several outcome slots has no single outcome name, so
        it keeps the raw CTF form and cannot be matched to one payout. Skipping is
        correct; picking one of its legs would be a fabricated settlement.
        """
        combo = canonical_symbol(condition_id=self.CID, index_set=3)
        process_batch([{"source": "polymarket", "tx_hash": "combo",
                        "timestamp": "2026-01-05 10:00:00", "asset_class": "prediction_market",
                        "symbol": combo, "side": "BUY", "quantity": 100.0, "price": 0.5,
                        "fee": 0.0, "total_value": 50.0, "notes": ""}], db_path=self.db_path)
        plan = self._sync([0.0, 1.0, 0.0]).plan()
        self.assertNotIn(combo, [r["symbol"] for r in plan.settlements])
        self.assertIn(combo, [subject for subject, _ in plan.skipped])


# ============================================================================
# ROUND 8: magnitude-adjusted Kelly, rolling window, break-even threshold
# ============================================================================

class TestMagnitudeAdjustedKelly(unittest.TestCase):
    """
    Win rate alone is not an edge. A book winning 60% at +0.05 and losing 40% at
    -0.40 has a good-looking win rate and loses money; sizing on the win count
    would grow it.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed(self, specs, prefix="WILL-FED-CUT-RATES", month=1):
        rows = []
        for i, (entry, exit_price) in enumerate(specs):
            symbol = f"{prefix}-{i}-YES"
            rows += [
                {"source": "polymarket", "tx_hash": f"b{prefix}{i}",
                 "timestamp": f"2026-{month:02d}-{(i % 28) + 1:02d} 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "BUY",
                 "quantity": 100.0, "price": entry, "fee": 0.0,
                 "total_value": 100 * entry, "notes": ""},
                {"source": "polymarket", "tx_hash": f"s{prefix}{i}",
                 "timestamp": f"2026-{month + 1:02d}-{(i % 28) + 1:02d} 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "SELL",
                 "quantity": 100.0, "price": exit_price, "fee": 0.0,
                 "total_value": 100 * exit_price, "notes": ""},
            ]
        process_batch(rows, db_path=self.db_path)

    def _hook(self, **kwargs):
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path, config=TEST_CONFIG,
                                   max_position_pct=0.05, **kwargs)

    def test_kelly_from_payoff_ratio_matches_the_standard_form(self):
        # (p(b+1) - 1)/b is p - (1-p)/b
        for p, b in [(0.6, 2.0), (0.55, 1.5), (0.8, 0.5)]:
            self.assertAlmostEqual(kelly_from_payoff_ratio(p, b), p - (1 - p) / b)

    def test_negative_expectancy_returns_zero_not_a_small_positive(self):
        self.assertEqual(kelly_from_payoff_ratio(0.60, 0.125), 0.0)
        self.assertEqual(kelly_from_payoff_ratio(0.30, 1.0), 0.0)

    def test_zero_or_negative_payoff_ratio_is_zero(self):
        self.assertEqual(kelly_from_payoff_ratio(0.9, 0.0), 0.0)
        self.assertEqual(kelly_from_payoff_ratio(0.9, -1.0), 0.0)

    def test_a_high_win_rate_losing_book_sizes_to_zero(self):
        """12 wins at +0.05, 8 losses at -0.40: 60% win rate, -$260 P&L."""
        self._seed([(0.50, 0.55)] * 12 + [(0.50, 0.10)] * 8)
        edge = self._hook().category_stats()["macro"]
        self.assertAlmostEqual(edge.win_rate, 0.60)
        self.assertLess(edge.net_pnl, 0)
        self.assertLess(edge.expectancy, 0)
        self.assertEqual(edge.sizing_pct, 0.0)

    def test_that_book_is_rejected_outright(self):
        self._seed([(0.50, 0.55)] * 12 + [(0.50, 0.10)] * 8)
        decision = self._hook().check_order(1000.0, category="macro")
        self.assertFalse(decision.approved)
        self.assertIn("negative expectancy", decision.reason)

    def test_same_win_rate_with_real_payoff_sizes_up(self):
        """Identical 60% win rate, profitable magnitudes - the sizer must separate them."""
        self._seed([(0.40, 0.95)] * 12 + [(0.40, 0.20)] * 8)
        edge = self._hook().category_stats()["macro"]
        self.assertAlmostEqual(edge.win_rate, 0.60)
        self.assertGreater(edge.net_pnl, 0)
        self.assertGreater(edge.expectancy, 0)
        self.assertGreater(edge.sizing_pct, 0.0)

    def test_payoff_ratio_is_per_dollar_risked(self):
        self._seed([(0.50, 1.00)] * 10 + [(0.50, 0.25)] * 10)
        edge = self._hook().category_stats()["macro"]
        self.assertAlmostEqual(edge.avg_win_return, 1.0, places=6)    # +0.50 on 0.50
        self.assertAlmostEqual(edge.avg_loss_return, 0.5, places=6)   # -0.25 on 0.50
        self.assertAlmostEqual(edge.payoff_ratio, 2.0, places=6)

    def test_a_category_with_no_losses_has_its_ratio_capped(self):
        """An unbounded b would size at the ceiling off a lucky streak."""
        self._seed([(0.40, 0.95)] * 5)
        self.assertEqual(self._hook().category_stats()["macro"].payoff_ratio, MAX_PAYOFF_RATIO)

    def test_priced_order_uses_the_tighter_of_the_two_payoff_ratios(self):
        """
        A 10c share offers b = 9, but a book that habitually exits at 15c has never
        captured that. Sizing on the theoretical payoff bets on a return the
        operator does not actually take.
        """
        self._seed([(0.10, 0.15)] * 12 + [(0.10, 0.02)] * 8)
        hook = self._hook()
        historical = hook.category_stats()["macro"].payoff_ratio
        priced = hook.category_edge("macro", price=0.10)
        self.assertLess(priced.payoff_ratio, (1 - 0.10) / 0.10)
        self.assertAlmostEqual(priced.payoff_ratio, min((1 - 0.10) / 0.10, historical))

    def test_an_expensive_share_caps_the_ratio_regardless_of_history(self):
        self._seed([(0.40, 0.95)] * 18 + [(0.40, 0.20)] * 2)
        priced = self._hook().category_edge("macro", price=0.90)
        self.assertAlmostEqual(priced.payoff_ratio, (1 - 0.90) / 0.90, places=6)


class TestCategoryRollingWindow(unittest.TestCase):
    """
    Without a window, a category that worked in a past regime keeps its size:
    60 old wins drown out 20 recent losses and the sizer stays loud while the edge
    decays.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        rows = []
        for i in range(60):        # older wins
            rows += self._pair(f"OLD{i}", "2026-01-05", "2026-02-05", 0.40, 0.95)
        for i in range(20):        # recent losses
            rows += self._pair(f"NEW{i}", "2026-06-01", "2026-07-01", 0.40, 0.05)
        process_batch(rows, db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _pair(tag, bought, sold, entry, exit_price):
        symbol = f"WILL-FED-CUT-RATES-{tag}-YES"
        return [
            {"source": "polymarket", "tx_hash": f"b{tag}", "timestamp": f"{bought} 10:00:00",
             "asset_class": "prediction_market", "symbol": symbol, "side": "BUY",
             "quantity": 100.0, "price": entry, "fee": 0.0, "total_value": 100 * entry, "notes": ""},
            {"source": "polymarket", "tx_hash": f"s{tag}", "timestamp": f"{sold} 10:00:00",
             "asset_class": "prediction_market", "symbol": symbol, "side": "SELL",
             "quantity": 100.0, "price": exit_price, "fee": 0.0,
             "total_value": 100 * exit_price, "notes": ""},
        ]

    def _edge(self, window):
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path, config=TEST_CONFIG,
                                   max_position_pct=0.05,
                                   category_window=window).category_stats()["macro"]

    def test_window_caps_the_sample(self):
        self.assertEqual(self._edge(40).trades, 40)

    def test_window_keeps_the_most_recent_trades(self):
        """All 20 recent losses must be inside a 40-trade window."""
        self.assertEqual(self._edge(40).wins, 20)

    def test_recent_losses_shrink_the_size(self):
        self.assertLess(self._edge(40).sizing_pct, self._edge(200).sizing_pct)

    def test_a_wide_window_is_dominated_by_stale_wins(self):
        self.assertEqual(self._edge(200).trades, 80)
        self.assertEqual(self._edge(200).wins, 60)

    def test_default_window_is_forty(self):
        self.assertEqual(CATEGORY_WINDOW, 40)


class TestBreakevenThreshold(unittest.TestCase):
    """
    Under gross-of-fees accounting the tax lands on the GROSS gain while fees come
    out of pocket unrecorded, so break-even is fee/(1-tax), not fee.
    """

    def _hook(self, ledger_fee=0.0, assumed=0.02):
        config = dict(TEST_CONFIG,
                      chain={"polymarket_fee_rate": ledger_fee},
                      bot_integration={"assumed_round_trip_fee": assumed})
        return MonarchBankrollHook(tax_year=2026, config=config)

    def test_two_percent_round_trip_at_thirty_five_percent_tax(self):
        self.assertAlmostEqual(self._hook().breakeven_gross_edge(), 0.02 / 0.65, places=6)
        self.assertAlmostEqual(self._hook().breakeven_gross_edge() * 100, 3.08, places=2)

    def test_the_gap_above_the_raw_fee_is_the_cost_of_not_recording_fees(self):
        breakeven = self._hook().breakeven_gross_edge()
        self.assertGreater(breakeven, 0.02)
        self.assertAlmostEqual(breakeven - 0.02, 0.0108, places=4)

    def test_explicit_rate_overrides_config(self):
        self.assertAlmostEqual(self._hook().breakeven_gross_edge(0.03), 0.03 / 0.65, places=6)

    def test_a_measured_ledger_fee_wins_over_the_assumption(self):
        self.assertAlmostEqual(self._hook(ledger_fee=0.005).breakeven_gross_edge(),
                               0.01 / 0.65, places=6)

    def test_zero_fees_means_zero_threshold(self):
        self.assertEqual(self._hook(assumed=0.0).breakeven_gross_edge(), 0.0)

    def test_the_filter_defaults_on_even_though_the_ledger_rate_is_zero(self):
        """
        The ledger stays measurement-only, but the SCANNER threshold is a decision
        aid that is never written down - so it may assume a realistic fee, and
        leaving it inert would remove the protection exactly when it matters.
        """
        self.assertGreater(self._hook(ledger_fee=0.0).breakeven_gross_edge(), 0.03)


# ============================================================================
# ROUND 9: minimum-N gate, payoff basis, strategy tag, scanner wiring
# ============================================================================

class TestMinimumSampleGate(unittest.TestCase):
    """
    Wilson shrinks a small sample hard, but shrinking is not abstaining: three
    observations still produce a number, and that number moves real money.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed(self, count):
        rows = []
        for i in range(count):
            symbol = f"WILL-FED-CUT-RATES-{i}-YES"
            rows += [
                {"source": "polymarket", "tx_hash": f"b{i}", "timestamp": "2026-01-01 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "BUY",
                 "quantity": 100.0, "price": 0.40, "fee": 0.0, "total_value": 40.0, "notes": ""},
                {"source": "polymarket", "tx_hash": f"s{i}", "timestamp": "2026-02-01 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "SELL",
                 "quantity": 100.0, "price": 0.95, "fee": 0.0, "total_value": 95.0, "notes": ""},
            ]
        process_batch(rows, db_path=self.db_path)

    def _hook(self, **kwargs):
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path, config=TEST_CONFIG,
                                   max_position_pct=0.05, **kwargs)

    def test_below_the_gate_the_flat_percentage_applies(self):
        self._seed(4)
        edge = self._hook().category_edge("macro")
        self.assertEqual(edge.basis, "default")
        self.assertAlmostEqual(edge.sizing_pct, 0.05)

    def test_at_the_gate_the_empirical_sizer_engages(self):
        self._seed(5)
        self.assertEqual(self._hook().category_edge("macro").basis, "empirical")

    def test_the_observed_count_is_still_reported_below_the_gate(self):
        """Reported as unmeasured, not as absent."""
        self._seed(3)
        self.assertEqual(self._hook().category_edge("macro").trades, 3)

    def test_the_gate_is_configurable(self):
        self._seed(6)
        self.assertEqual(self._hook(min_category_trades=10).category_edge("macro").basis, "default")

    def test_default_gate_is_five(self):
        self.assertEqual(MIN_CATEGORY_TRADES, 5)


class TestPayoffBasis(unittest.TestCase):
    """
    `p_wilson` is measured from CLOSED trades - an exit-behaviour statistic. Pairing
    it with the hold-to-resolution payoff (1-q)/q mixes two populations: most of
    those trades never collected the full $1.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        # A scalping book: wins small (0.10 -> 0.15), loses small (0.10 -> 0.02).
        rows = []
        for i in range(20):
            symbol = f"WILL-FED-CUT-RATES-{i}-YES"
            exit_price = 0.15 if i < 14 else 0.02
            rows += [
                {"source": "polymarket", "tx_hash": f"b{i}", "timestamp": "2026-01-01 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "BUY",
                 "quantity": 100.0, "price": 0.10, "fee": 0.0, "total_value": 10.0, "notes": ""},
                {"source": "polymarket", "tx_hash": f"s{i}", "timestamp": "2026-02-01 10:00:00",
                 "asset_class": "prediction_market", "symbol": symbol, "side": "SELL",
                 "quantity": 100.0, "price": exit_price, "fee": 0.0,
                 "total_value": 100 * exit_price, "notes": ""},
            ]
        process_batch(rows, db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _edge(self, basis, price=0.10):
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path, config=TEST_CONFIG,
                                   max_position_pct=0.05,
                                   payoff_basis=basis).category_edge("macro", price=price)

    def test_price_basis_uses_the_contract_payoff(self):
        self.assertAlmostEqual(self._edge("price").payoff_ratio, (1 - 0.10) / 0.10, places=6)

    def test_realized_basis_uses_what_the_book_actually_captured(self):
        realized = self._edge("realized").payoff_ratio
        self.assertLess(realized, (1 - 0.10) / 0.10)
        self.assertGreater(realized, 0.0)

    def test_conservative_is_the_minimum_of_the_two(self):
        self.assertAlmostEqual(self._edge("conservative").payoff_ratio,
                               min(self._edge("price").payoff_ratio,
                                   self._edge("realized").payoff_ratio))

    def test_price_basis_sizes_a_scalper_larger(self):
        """The overstatement the consistency argument predicts."""
        self.assertGreater(self._edge("price").sizing_pct, self._edge("realized").sizing_pct)

    def test_an_expensive_order_caps_every_basis(self):
        for basis in ("price", "conservative"):
            self.assertAlmostEqual(self._edge(basis, price=0.90).payoff_ratio,
                                   (1 - 0.90) / 0.90, places=6)

    def test_default_basis_is_conservative(self):
        self.assertEqual(DEFAULT_PAYOFF_BASIS, "conservative")


class TestStrategyTag(unittest.TestCase):
    """A tag so future modular strategies can be attributed without a schema change."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 3000.0, "2026-01-15 10:00:00"),
        ], db_path=self.db_path)
        self.hook = MonarchBankrollHook(tax_year=2026, db_path=self.db_path,
                                        config=TEST_CONFIG, max_position_pct=0.05)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_tag(self):
        self.assertEqual(self.hook.check_order(100.0).strategy, "default")

    def test_tag_round_trips(self):
        self.assertEqual(self.hook.check_order(100.0, strategy="dutched_arb").strategy,
                         "dutched_arb")

    def test_tag_survives_a_rejection(self):
        decision = self.hook.check_order(0.0, strategy="consensus_copy")
        self.assertFalse(decision.approved)
        self.assertEqual(decision.strategy, "consensus_copy")

    def test_tag_is_serialised(self):
        self.assertEqual(self.hook.check_order(100.0, strategy="x").to_dict()["strategy"], "x")

    def test_size_order_accepts_the_tag(self):
        self.assertGreater(self.hook.size_order(100.0, strategy="dutched_arb"), 0)

    def test_already_deployed_still_works_alongside_the_new_parameters(self):
        """
        The briefed signature dropped `already_deployed`. It is load-bearing - it
        is what stops a burst of orders inside one cache window each claiming the
        same dollars - so it was kept.
        """
        decision = self.hook.check_order(400.0, already_deployed=9_650.0, strategy="x")
        self.assertFalse(decision.approved)


class TestScannerBreakevenWiring(unittest.TestCase):
    """
    Source-level checks that both Monarch scanners actually filter on the
    after-tax threshold. Importing them would drag in rich, requests and the whole
    module graph.
    """

    MONARCH = Path(__file__).resolve().parents[2] / "Polymarket" / "Polymarket_Monarch"

    def setUp(self):
        if not (self.MONARCH / "consensus_scanner.py").exists():
            self.skipTest("Polymarket_Monarch not present")

    def test_dutched_arb_filters_on_the_threshold(self):
        source = (self.MONARCH / "dutched_arb.py").read_text(encoding="utf-8")
        self.assertIn("min_edge", source)
        self.assertIn("below_threshold", source)
        self.assertIn("breakeven_gross_edge", source)

    def test_consensus_scanner_filters_on_the_threshold(self):
        source = (self.MONARCH / "consensus_scanner.py").read_text(encoding="utf-8")
        self.assertIn("MIN_AFTER_TAX_EDGE = 0.0308", source)
        self.assertIn("def expected_edge(", source)
        self.assertIn("skipped_below_breakeven", source)
        self.assertIn("breakeven_gross_edge", source)

    def test_consensus_scanner_tags_its_strategy(self):
        source = (self.MONARCH / "consensus_scanner.py").read_text(encoding="utf-8")
        self.assertIn('strategy="consensus_copy"', source)

    def test_tax_gate_passes_the_strategy_through(self):
        source = (self.MONARCH / "tax_gate.py").read_text(encoding="utf-8")
        self.assertIn("strategy=strategy", source)


# ============================================================================
# ROUND 10: survivorship shrinkage, category on copies, fail-safe break-even
# ============================================================================

class TestPayoffBasisAlias(unittest.TestCase):
    def test_min_is_an_alias_for_conservative(self):
        """The backtest reports under 'min'; the config should read the same way."""
        hook = MonarchBankrollHook(config=TEST_CONFIG, payoff_basis="min")
        self.assertEqual(hook.payoff_basis, "conservative")

    def test_explicit_bases_are_untouched(self):
        for basis in ("price", "realized", "conservative"):
            self.assertEqual(MonarchBankrollHook(config=TEST_CONFIG,
                                                 payoff_basis=basis).payoff_basis, basis)


class TestConsensusScannerWiring(unittest.TestCase):
    """
    Source-level checks. Importing consensus_scanner pulls in rich, requests and
    the whole Monarch module graph.
    """

    MONARCH = Path(__file__).resolve().parents[2] / "Polymarket" / "Polymarket_Monarch"

    def setUp(self):
        if not (self.MONARCH / "consensus_scanner.py").exists():
            self.skipTest("Polymarket_Monarch not present")
        self.source = (self.MONARCH / "consensus_scanner.py").read_text(encoding="utf-8")

    def test_sharp_win_rate_is_shrunk_before_the_edge(self):
        self.assertIn("def shrunk_win_rate(", self.source)
        self.assertIn("wilson_lower_bound", self.source)
        self.assertIn("aggregate_closed", self.source)

    def test_edge_uses_the_shrunk_rate_not_the_raw_one(self):
        self.assertIn("p = ConsensusPaperBook.shrunk_win_rate(", self.source)

    def test_copies_derive_a_category(self):
        self.assertIn("categorise(", self.source)
        self.assertIn("category=category", self.source)

    def test_break_even_falls_back_rather_than_disabling(self):
        gate_source = (self.MONARCH / "tax_gate.py").read_text(encoding="utf-8")
        self.assertIn("FALLBACK_AFTER_TAX_EDGE = 0.0308", gate_source)
        self.assertIn("default: float = FALLBACK_AFTER_TAX_EDGE", gate_source)

    def test_dutched_arb_no_longer_fails_open(self):
        source = (self.MONARCH / "dutched_arb.py").read_text(encoding="utf-8")
        self.assertNotIn("gate.breakeven_gross_edge(0.0)", source)


class TestSurvivorshipShrinkage(unittest.TestCase):
    """
    Loads the scanner's shrinkage maths directly, without importing the module.
    The roster selects wallets FOR having won, so the raw rate is an artefact.
    """

    def _shrink(self, win_rate_pct, closed):
        # Mirrors ConsensusPaperBook.shrunk_win_rate.
        if not win_rate_pct or win_rate_pct <= 0:
            return 0.0
        n = int(closed or 0) or 10
        p_hat = min(max(win_rate_pct / 100.0, 0.0), 1.0)
        return wilson_lower_bound(int(round(p_hat * n)), n)

    def test_a_small_sample_is_shrunk_hard(self):
        self.assertLess(self._shrink(70.0, 12), 0.60)

    def test_a_large_sample_barely_moves(self):
        self.assertGreater(self._shrink(70.0, 300), 0.66)

    def test_shrinkage_flips_a_marginal_signal_to_rejected(self):
        """70% over 12 positions at a 0.60 ask: 16.7% raw edge, negative shrunk."""
        ask = 0.60
        raw_edge = (0.70 - ask) / ask
        shrunk_edge = (self._shrink(70.0, 12) - ask) / ask
        self.assertGreater(raw_edge, 0.0308)
        self.assertLess(shrunk_edge, 0.0308)

    def test_a_genuinely_strong_signal_still_clears(self):
        self.assertGreater((self._shrink(85.0, 150) - 0.60) / 0.60, 0.0308)


# ============================================================================
# PHASE 3 (task 1): strategy capital buckets
# ============================================================================

class TestAllocationNormalisation(unittest.TestCase):
    def test_a_clean_set_passes_through(self):
        self.assertEqual(normalise_allocations({"a": 0.5, "b": 0.3, "sandbox": 0.2}),
                         {"a": 0.5, "b": 0.3, "sandbox": 0.2})

    def test_over_commitment_raises(self):
        """
        SUPERSEDES a version asserting proportional down-scaling. Scaling silently
        produces buckets nobody asked for and hides the typo that caused them, so
        an impossible capital plan is now a hard failure.
        """
        with self.assertRaises(StrategyAllocationError) as ctx:
            normalise_allocations({"a": 0.8, "b": 0.5})
        self.assertIn("130%", str(ctx.exception))

    def test_exactly_one_hundred_percent_is_accepted(self):
        self.assertEqual(sum(normalise_allocations({"a": 0.5, "b": 0.5}).values()), 1.0)

    def test_floating_point_slack_is_tolerated(self):
        """0.1 + 0.2 + 0.7 does not sum to exactly 1.0 in binary."""
        self.assertEqual(len(normalise_allocations({"a": 0.1, "b": 0.2, "c": 0.7})), 3)

    def test_under_commitment_is_left_alone(self):
        """The shortfall is unallocated reserve, not a rounding error to absorb."""
        self.assertEqual(normalise_allocations({"a": 0.3}), {"a": 0.3})

    def test_junk_entries_are_dropped(self):
        self.assertEqual(normalise_allocations({"a": "x", "b": -1, "c": 0.4}), {"c": 0.4})

    def test_empty_disables_bucketing(self):
        self.assertEqual(normalise_allocations(None), {})
        self.assertEqual(normalise_allocations({}), {})


class TestStrategyBuckets(unittest.TestCase):
    ALLOCATIONS = {"dutched_arb": 0.50, "consensus_copy": 0.30, "sandbox": 0.20}

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 3000.0, "2026-01-15 10:00:00"),
        ], db_path=self.db_path)   # +$1,000 -> $350 escrow -> $9,650 safe

    def tearDown(self):
        self.temp_dir.cleanup()

    def _hook(self, allocations=None):
        config = dict(TEST_CONFIG)
        if allocations is not None:
            config["bot_integration"] = {"strategies": allocations}
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path, config=config,
                                   max_position_pct=0.05)

    def test_no_allocations_leaves_behaviour_unchanged(self):
        hook = self._hook()
        budget = hook.strategy_budget("anything", 9650.0)
        self.assertFalse(budget.enforced)
        self.assertAlmostEqual(budget.budget, 9650.0)
        self.assertAlmostEqual(hook.check_order(50_000.0, strategy="x").approved_notional, 482.5)

    def test_each_bucket_gets_its_share(self):
        hook = self._hook(self.ALLOCATIONS)
        self.assertAlmostEqual(hook.strategy_budget("dutched_arb", 9650.0).budget, 4825.0)
        self.assertAlmostEqual(hook.strategy_budget("consensus_copy", 9650.0).budget, 2895.0)
        self.assertAlmostEqual(hook.strategy_budget("sandbox", 9650.0).budget, 1930.0)

    def test_the_per_order_cap_is_a_fraction_of_the_bucket(self):
        """5% of the sandbox, not 5% of the book - otherwise quarantine is cosmetic."""
        hook = self._hook(self.ALLOCATIONS)
        self.assertAlmostEqual(hook.check_order(50_000.0, strategy="sandbox").approved_notional,
                               1930.0 * 0.05)

    def test_an_unknown_strategy_is_quarantined_into_the_sandbox(self):
        hook = self._hook(self.ALLOCATIONS)
        budget = hook.strategy_budget("brand_new_thing", 9650.0)
        self.assertTrue(budget.quarantined)
        self.assertAlmostEqual(budget.budget, 1930.0)

    def test_the_default_tag_is_quarantined_too(self):
        """Under an enforced regime, unclassified traffic is exactly what sandboxing is for."""
        self.assertTrue(self._hook(self.ALLOCATIONS).strategy_budget("default", 9650.0).quarantined)

    def test_without_a_sandbox_an_unknown_strategy_is_rejected(self):
        hook = self._hook({"dutched_arb": 1.0})
        decision = hook.check_order(1000.0, strategy="unknown")
        self.assertFalse(decision.approved)
        self.assertIn("no capital allocation", decision.reason)

    def test_deployed_capital_exhausts_only_its_own_bucket(self):
        hook = self._hook(self.ALLOCATIONS)
        exhausted = hook.check_order(50_000.0, strategy="dutched_arb", already_deployed=4825.0)
        self.assertFalse(exhausted.approved)
        fresh = hook.check_order(50_000.0, strategy="consensus_copy")
        self.assertTrue(fresh.approved)

    def test_partial_deployment_limits_to_what_remains(self):
        hook = self._hook(self.ALLOCATIONS)
        decision = hook.check_order(50_000.0, strategy="dutched_arb", already_deployed=4730.0)
        self.assertAlmostEqual(decision.approved_notional, 95.0)

    def test_the_decision_carries_the_budget(self):
        decision = self._hook(self.ALLOCATIONS).check_order(100.0, strategy="dutched_arb")
        self.assertAlmostEqual(decision.strategy_budget, 4825.0)
        self.assertAlmostEqual(decision.strategy_remaining, 4825.0)

    def test_an_over_committed_config_refuses_to_construct(self):
        """A bot must not start against a capital plan that cannot be honoured."""
        with self.assertRaises(StrategyAllocationError):
            self._hook({"a": 0.8, "b": 0.6})

    def test_reason_names_the_bucket_not_the_whole_bankroll(self):
        reason = self._hook(self.ALLOCATIONS).check_order(50_000.0, strategy="sandbox").reason
        self.assertIn("sandbox bucket", reason)
        self.assertIn("1,930.00", reason)

    def test_report_renders_and_flags_a_missing_sandbox(self):
        self.assertIn("dutched_arb", self._hook(self.ALLOCATIONS).strategy_report())
        self.assertIn("no `sandbox` bucket", self._hook({"dutched_arb": 1.0}).strategy_report())

    def test_report_shows_unallocated_reserve(self):
        self.assertIn("unallocated reserve", self._hook({"dutched_arb": 0.4}).strategy_report())


# ============================================================================
# PHASE 3 tasks 2 & 3: strategy attribution and the base interface
# ============================================================================

class TestStrategyTagging(unittest.TestCase):
    """
    The schema is FROZEN, so attribution rides in `transactions.notes`. The tag
    terminator is what keeps `sandbox` from matching `sandbox_v2`.
    """

    def test_tag_format(self):
        self.assertEqual(strategy_tag("sandbox"), "strategy:sandbox;")

    def test_a_prefix_name_does_not_match_a_longer_one(self):
        """Without the ';' terminator, sandbox_v2's exposure would pool into sandbox."""
        self.assertNotIn(strategy_tag("sandbox"), f"note {strategy_tag('sandbox_v2')}")

    def test_tagging_prepends_and_keeps_the_original_note(self):
        tx = {"notes": "Crypto spot trade"}
        tag_strategy(tx, "dutched_arb")
        self.assertEqual(tx["notes"], "strategy:dutched_arb; Crypto spot trade")

    def test_tagging_is_idempotent(self):
        tx = {"notes": "x"}
        tag_strategy(tx, "a")
        tag_strategy(tx, "a")
        self.assertEqual(tx["notes"].count("strategy:a;"), 1)

    def test_no_strategy_leaves_the_note_untouched(self):
        tx = {"notes": "unchanged"}
        self.assertEqual(tag_strategy(tx, None)["notes"], "unchanged")

    def test_ingestors_accept_a_strategy(self):
        spot = SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0,
                                         "2026-01-01 10:00:00", strategy="dutched_arb")
        self.assertIn("strategy:dutched_arb;", spot["notes"])
        poly = PolymarketIngestor.create_manual_trade("M", "BUY", 10, 0.5,
                                                      "2026-01-01 10:00:00", strategy="sandbox")
        self.assertIn("strategy:sandbox;", poly["notes"])

    def test_untagged_ingestion_is_unchanged(self):
        self.assertNotIn("strategy:",
                         SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0,
                                                   "2026-01-01 10:00:00")["notes"])


class TestStrategyExposure(unittest.TestCase):
    """
    Ledger-measured exposure is what makes a bucket a real ceiling rather than a
    per-order cap - it holds even when the caller passes 0.
    """

    ALLOCATIONS = {"dutched_arb": 0.50, "consensus_copy": 0.30, "sandbox": 0.20}

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        process_batch([
            SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 3000.0, "2026-01-15 10:00:00"),
        ], db_path=self.db_path)   # +$1,000 -> $350 escrow -> $9,650 safe

    def tearDown(self):
        self.temp_dir.cleanup()

    def _hook(self, allocations=None):
        config = dict(TEST_CONFIG)
        if allocations is not None:
            config["bot_integration"] = {"strategies": allocations}
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path, config=config,
                                   max_position_pct=0.05)

    def _open(self, strategy, cost):
        process_batch([SpotIngestor.create_trade(
            f"POS-{strategy}-{cost}", "BUY", 1.0, cost, "2026-03-01 10:00:00",
            strategy=strategy)], db_path=self.db_path)

    def test_untagged_lots_contribute_nothing(self):
        self.assertEqual(self._hook().get_strategy_open_exposure("dutched_arb"), 0.0)

    def test_exposure_sums_open_cost_basis(self):
        self._open("dutched_arb", 500.0)
        self._open("dutched_arb", 250.0)
        self.assertAlmostEqual(self._hook().get_strategy_open_exposure("dutched_arb"), 750.0)

    def test_exposure_is_isolated_per_strategy(self):
        self._open("dutched_arb", 500.0)
        self._open("sandbox", 100.0)
        hook = self._hook()
        self.assertAlmostEqual(hook.get_strategy_open_exposure("dutched_arb"), 500.0)
        self.assertAlmostEqual(hook.get_strategy_open_exposure("sandbox"), 100.0)

    def test_a_prefix_named_strategy_does_not_leak(self):
        self._open("sandbox_v2", 400.0)
        self.assertEqual(self._hook().get_strategy_open_exposure("sandbox"), 0.0)

    def test_closed_lots_stop_counting(self):
        self._open("dutched_arb", 500.0)
        hook = self._hook()
        self.assertAlmostEqual(hook.get_strategy_open_exposure("dutched_arb"), 500.0)
        process_batch([SpotIngestor.create_trade("POS-dutched_arb-500.0", "SELL", 1.0,
                                                 600.0, "2026-04-01 10:00:00")],
                      db_path=self.db_path)
        self.assertAlmostEqual(self._hook().get_strategy_open_exposure("dutched_arb"), 0.0)

    def test_a_caller_passing_zero_still_gets_the_ceiling(self):
        """The whole point: bucket limits must not depend on caller bookkeeping."""
        self._open("sandbox", 1900.0)   # sandbox budget is 20% of 9650 = 1930
        decision = self._hook(self.ALLOCATIONS).check_order(5000.0, strategy="sandbox",
                                                            already_deployed=0.0)
        self.assertAlmostEqual(decision.detail["measured_exposure"], 1900.0)
        self.assertLessEqual(decision.approved_notional, 30.0)

    def test_an_exhausted_bucket_rejects(self):
        self._open("sandbox", 1930.0)
        decision = self._hook(self.ALLOCATIONS).check_order(500.0, strategy="sandbox")
        self.assertFalse(decision.approved)

    def test_an_explicit_figure_still_wins(self):
        self._open("sandbox", 1900.0)
        decision = self._hook(self.ALLOCATIONS).check_order(500.0, strategy="sandbox",
                                                            already_deployed=10.0)
        self.assertAlmostEqual(decision.detail["measured_exposure"], 10.0)

    def test_no_bucketing_means_no_ledger_lookup(self):
        self._open("dutched_arb", 5000.0)
        decision = self._hook().check_order(50_000.0, strategy="dutched_arb")
        self.assertAlmostEqual(decision.detail["measured_exposure"], 0.0)

    def test_strategy_stats_attributes_realised_pnl(self):
        process_batch([
            SpotIngestor.create_trade("WIN", "BUY", 1.0, 100.0, "2026-03-01 10:00:00",
                                      strategy="dutched_arb"),
            SpotIngestor.create_trade("WIN", "SELL", 1.0, 150.0, "2026-04-01 10:00:00",
                                      strategy="dutched_arb"),
        ], db_path=self.db_path)
        stats = self._hook(self.ALLOCATIONS).strategy_stats()
        self.assertEqual(stats["dutched_arb"]["closed"], 1)
        self.assertAlmostEqual(stats["dutched_arb"]["pnl"], 50.0)
        self.assertAlmostEqual(stats["dutched_arb"]["win_rate"], 100.0)

    def test_strategy_table_renders(self):
        hook = self._hook(self.ALLOCATIONS)
        safe = hook.get_safe_bankroll()
        budgets = {n: hook.strategy_budget(n, safe) for n in hook.strategy_allocations}
        table = render_strategy_table(hook.strategy_stats(), budgets, safe)
        self.assertIn("STRATEGY CAPITAL", table)
        self.assertIn("dutched_arb", table)


class TestBaseStrategyInterface(unittest.TestCase):
    """
    Loaded from its own path - Monarch is not an importable package, and these
    tests must not require it to become one.
    """

    MONARCH = Path(__file__).resolve().parents[2] / "Polymarket" / "Polymarket_Monarch"

    @classmethod
    def setUpClass(cls):
        base = cls.MONARCH / "strategies" / "base.py"
        if not base.exists():
            raise unittest.SkipTest("Monarch strategies package not present")
        if str(cls.MONARCH) not in sys.path:
            sys.path.insert(0, str(cls.MONARCH))
        spec = importlib.util.spec_from_file_location("monarch_strategy_base", base)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _demo(self, **kwargs):
        mod = self.mod

        class Demo(mod.BaseStrategy):
            name = "dutched_arb"

            def scan(self):
                return [mod.Opportunity("good", 0.30, 0.06).as_dict(),
                        mod.Opportunity("marginal", 0.30, 0.025).as_dict()]

            def evaluate_opportunity(self, opportunity, hook):
                return hook.check_order(opportunity.get("_notional", 100.0),
                                        price=opportunity["price"], strategy=self.name)

        return Demo(**kwargs)

    def test_it_is_abstract(self):
        with self.assertRaises(TypeError):
            self.mod.BaseStrategy()

    def test_min_edge_defaults_to_the_after_tax_breakeven(self):
        """Never zero: a strategy defaulting to 0 surfaces after-tax losers."""
        # fee/(1-t) at the Round 26k composite: 0.02 / 0.69 = 2.899%. It was
        # 3.077% while the composite double-counted state at 0.35, so this
        # threshold moved DOWN when the rates were unbundled - the hurdle was
        # never 3.08%, the rate behind it was wrong.
        self.assertGreater(self._demo().min_edge, 0.028)

    def test_the_hurdle_filters_scan_results(self):
        strategy = self._demo()
        self.assertEqual(len(strategy.scan()), 2)
        self.assertEqual([o["market"] for o in strategy.opportunities()], ["good"])

    def test_an_override_is_honoured(self):
        self.assertAlmostEqual(self._demo(min_edge=0.10).min_edge, 0.10)

    def test_validate_flags_a_below_breakeven_override(self):
        problems = self._demo(min_edge=0.01).validate()
        self.assertTrue(any("BELOW the after-tax break-even" in p for p in problems))

    def test_validate_flags_a_missing_name(self):
        strategy = self._demo()
        strategy.name = "unnamed_strategy"
        self.assertTrue(any("no `name`" in p for p in strategy.validate()))

    def test_validate_flags_a_non_positive_notional(self):
        self.assertTrue(any("positive" in p for p in self._demo(default_notional=0).validate()))

    def test_a_clean_strategy_validates(self):
        self.assertEqual(self._demo().validate(), [])

    def test_opportunity_shape(self):
        row = self.mod.Opportunity("m", 0.4, 0.05, category="macro").as_dict()
        self.assertEqual(row["market"], "m")
        self.assertEqual(row["category"], "macro")
        self.assertIn("detail", row)

    def test_clears_hurdle_handles_junk(self):
        strategy = self._demo()
        self.assertFalse(strategy.clears_hurdle({"edge": "not a number"}))
        self.assertFalse(strategy.clears_hurdle({}))


# ============================================================================
# PHASE 4: live fee detection, execution receipts, health check
# ============================================================================

class TestFeeSchedule(unittest.TestCase):
    """
    Fee terms measured live across 300 open markets on 2026-09-03: politics 4%,
    sports 3%, economics 5%, crypto 7%; 295 of 300 had `feesEnabled: true`.
    """

    def test_fee_scales_with_distance_from_the_extremes(self):
        """Default curve is 2p(1-p): 2.00% politics at 50c, symmetric about it."""
        schedule = FeeSchedule(rate=0.04, exponent=1)
        self.assertAlmostEqual(schedule.one_way_fee(0.50), 0.02)
        self.assertAlmostEqual(schedule.one_way_fee(0.10), 0.04 * 2 * 0.10 * 0.90)
        self.assertAlmostEqual(schedule.one_way_fee(0.10), schedule.one_way_fee(0.90))

    def test_both_curves_agree_at_fifty_cents_and_nowhere_else(self):
        """
        This is why the stated anchors could not tell them apart. In the tails
        `product` charges up to 2x what `min` does.
        """
        product = FeeSchedule(rate=0.04, curve="product")
        minimum = FeeSchedule(rate=0.04, curve="min")
        self.assertAlmostEqual(product.one_way_fee(0.50), minimum.one_way_fee(0.50))
        self.assertGreater(product.one_way_fee(0.10), minimum.one_way_fee(0.10))
        self.assertAlmostEqual(product.one_way_fee(0.10) / minimum.one_way_fee(0.10), 1.8)

    def test_the_stated_anchor_points(self):
        self.assertAlmostEqual(FeeSchedule(rate=0.04).one_way_fee(0.50), 0.0200)
        self.assertAlmostEqual(FeeSchedule(rate=0.07).one_way_fee(0.50), 0.0350)

    def test_round_trip_charges_both_legs_by_default(self):
        self.assertAlmostEqual(FeeSchedule(rate=0.04).round_trip_fee(0.50), 0.04)

    def test_holding_to_resolution_charges_one_leg(self):
        """Redemption runs through the CTF contract, not the exchange."""
        schedule = FeeSchedule(rate=0.04)
        self.assertAlmostEqual(schedule.round_trip_fee(0.50, holds_to_resolution=True), 0.02)
        self.assertAlmostEqual(schedule.round_trip_fee(0.50, holds_to_resolution=True),
                               schedule.round_trip_fee(0.50) / 2)

    def test_a_politics_dutch_book_at_a_coin_flip_needs_exactly_308bp(self):
        """The flat constant we used for rounds was right for precisely this case."""
        fee = FeeSchedule(rate=0.04).round_trip_fee(0.50, holds_to_resolution=True)
        self.assertAlmostEqual(fee / 0.65, 0.0308, places=4)

    def test_a_disabled_schedule_is_free(self):
        self.assertEqual(FeeSchedule(rate=0.04, fees_enabled=False).one_way_fee(0.5), 0.0)

    def test_the_rebate_is_not_applied(self):
        """Conditional on maker behaviour we do not model; applying it would shrink
        the hurdle, which is the wrong direction to be wrong in."""
        self.assertAlmostEqual(FeeSchedule(rate=0.04, rebate_rate=0.25).one_way_fee(0.5), 0.02)

    def test_a_crypto_scalp_at_a_coin_flip_dwarfs_the_flat_assumption(self):
        """7% rate at p=0.5, sold out -> 7% round trip -> a 10.77% hurdle, not 3.08%."""
        self.assertAlmostEqual(FeeSchedule(rate=0.07).round_trip_fee(0.50), 0.07)
        self.assertAlmostEqual(FeeSchedule(rate=0.07).round_trip_fee(0.50) / 0.65, 0.1077, places=4)

    def test_prices_are_clamped(self):
        for price in (-1.0, 0.0, 1.0, 2.0):
            self.assertGreaterEqual(FeeSchedule(rate=0.04).one_way_fee(price), 0.0)


class TestFeeSource(unittest.TestCase):
    """Network replaced; only the parsing and caching logic is exercised."""

    POLITICS = [{"feesEnabled": True, "feeType": "politics_fees",
                 "feeSchedule": {"rate": 0.04, "exponent": 1, "takerOnly": True,
                                 "rebateRate": 0.25}}]

    def _source(self, payload, ttl=3600.0):
        source = PolymarketFeeSource(ttl_s=ttl)
        source.calls = []

        def fake_get(url):
            source.calls.append(url)
            return payload

        source._get_json = fake_get
        return source

    def test_parses_a_live_schedule(self):
        schedule = self._source(self.POLITICS).fee_schedule("tok")
        self.assertEqual(schedule.rate, 0.04)
        self.assertEqual(schedule.fee_type, "politics_fees")
        self.assertEqual(schedule.source, "gamma")

    def test_zero_fee_market_is_recognised(self):
        payload = [{"feesEnabled": False, "feeType": "none"}]
        schedule = self._source(payload).fee_schedule("tok")
        self.assertEqual(schedule.source, "disabled")
        self.assertEqual(schedule.round_trip_fee(0.5), 0.0)

    def test_enabled_but_unpublished_is_unavailable_not_free(self):
        """A missing number is not a free market."""
        payload = [{"feesEnabled": True, "feeType": "x", "feeSchedule": {}}]
        self.assertEqual(self._source(payload).fee_schedule("tok").source, "unavailable")

    def test_unknown_token_is_unavailable(self):
        self.assertEqual(self._source([]).fee_schedule("tok").source, "unavailable")

    def test_round_trip_returns_none_when_unknown(self):
        """None must stay distinct from 0.0 - one falls back, the other removes the hurdle."""
        self.assertIsNone(self._source([]).round_trip_fee("tok", 0.5))
        self.assertEqual(self._source([{"feesEnabled": False}]).round_trip_fee("tok", 0.5), 0.0)

    def test_results_are_cached(self):
        source = self._source(self.POLITICS)
        source.fee_schedule("tok")
        source.fee_schedule("tok")
        self.assertEqual(len(source.calls), 1)

    def test_the_cache_expires(self):
        source = self._source(self.POLITICS, ttl=-1.0)
        source.fee_schedule("tok")
        source.fee_schedule("tok")
        self.assertEqual(len(source.calls), 2)

    def test_offline_never_touches_the_network(self):
        source = PolymarketFeeSource(offline=True)
        source._get_json = lambda url: self.fail("offline source made a request")
        self.assertEqual(source.fee_schedule("tok").source, "unavailable")

    def test_an_empty_token_is_rejected(self):
        self.assertEqual(PolymarketFeeSource().fee_schedule("").source, "unavailable")


class TestLiveFeeHurdle(unittest.TestCase):
    def _hook(self, round_trip):
        hook = MonarchBankrollHook(config=dict(
            TEST_CONFIG, bot_integration={"assumed_round_trip_fee": 0.02}))
        hook.fetch_clob_fee_rate = (
            lambda token_id, price=0.5, holds_to_resolution=False: round_trip)
        return hook

    def test_a_live_fee_overrides_the_assumption(self):
        self.assertAlmostEqual(self._hook(0.07).breakeven_gross_edge(token_id="t", price=0.5),
                               0.07 / 0.65, places=6)

    def test_an_unknown_fee_falls_back_to_the_assumption(self):
        self.assertAlmostEqual(self._hook(None).breakeven_gross_edge(token_id="t"),
                               0.02 / 0.65, places=6)

    def test_a_genuinely_zero_fee_market_has_no_hurdle(self):
        self.assertEqual(self._hook(0.0).breakeven_gross_edge(token_id="t"), 0.0)

    def test_no_token_uses_the_assumption(self):
        self.assertAlmostEqual(self._hook(0.07).breakeven_gross_edge(), 0.02 / 0.65, places=6)

    def test_an_explicit_rate_still_wins(self):
        self.assertAlmostEqual(self._hook(0.07).breakeven_gross_edge(0.01, token_id="t"),
                               0.01 / 0.65, places=6)


class TestExecutionReceipts(unittest.TestCase):
    """
    A fill that reaches the ledger untagged counts against no bucket and quietly
    loosens every ceiling. The receipt is written at execution, the only moment
    the strategy is known for certain.
    """

    MONARCH = Path(__file__).resolve().parents[2] / "Polymarket" / "Polymarket_Monarch"

    @classmethod
    def setUpClass(cls):
        base = cls.MONARCH / "strategies" / "base.py"
        if not base.exists():
            raise unittest.SkipTest("Monarch strategies package not present")
        if str(cls.MONARCH) not in sys.path:
            sys.path.insert(0, str(cls.MONARCH))
        spec = importlib.util.spec_from_file_location("monarch_strategy_base_r13", base)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.imports = Path(self.temp_dir.name) / "imports"
        mod = self.mod

        class Demo(mod.BaseStrategy):
            name = "dutched_arb"

            def scan(self):
                return []

            def evaluate_opportunity(self, opportunity, hook):
                return None

        self.strategy = Demo()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, **kwargs):
        return self.strategy.log_execution_receipt(
            market="WILL-FED-CUT-RATES-YES", token_id="tok123", size=100.0, price=0.42,
            imports_dir=self.imports, timestamp="2026-03-01 12:00:00", **kwargs)

    def test_a_receipt_is_written(self):
        path = self._write()
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

    def test_the_strategy_tag_is_in_the_notes_column(self):
        with self._write().open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["notes"], "strategy:dutched_arb;")

    def test_the_filename_lets_the_watcher_classify_it(self):
        """`polymarket` in the name means the watcher does not have to guess."""
        self.assertIn("polymarket", self._write().name)

    def test_each_receipt_gets_its_own_file(self):
        """The watcher MOVES a file once ingested; appending would race that move."""
        first, second = self._write(), self._write()
        self.assertNotEqual(first, second)

    def test_the_receipt_round_trips_through_the_watcher_into_the_ledger(self):
        temp_db = Path(self.temp_dir.name) / "test_tax.db"
        init_db(temp_db)
        self._write()
        CSVWatcher(imports_dir=self.imports, db_path=temp_db).scan_once(require_stable=False)
        hook = MonarchBankrollHook(tax_year=2026, db_path=temp_db, config=TEST_CONFIG)
        self.assertAlmostEqual(hook.get_strategy_open_exposure("dutched_arb"), 42.0)

    def test_an_unwritable_directory_does_not_raise(self):
        """Bookkeeping must not take down an execution path."""
        self.assertIsNone(self.strategy.log_execution_receipt(
            market="M", token_id="t", size=1.0, price=0.5,
            imports_dir=self._blocked_dir()))

    def _blocked_dir(self) -> Path:
        """
        A path that genuinely cannot be created: a FILE sits where a directory
        would need to be. The earlier version used a made-up absolute path, which
        Windows happily created - the test passed for the wrong reason.
        """
        blocker = Path(self.temp_dir.name) / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        return blocker / "sub"


class TestHealthCheck(unittest.TestCase):
    class _Edge:
        def __init__(self, expectancy, trades):
            self.expectancy = expectancy
            self.trades = trades

    HEALTHY = {"reserve_ratio_pct": 5.0, "tax_escrow_reserve": 500.0,
               "liquid_cash_balance": 10000.0, "safe_deployable_bankroll": 9500.0}

    def test_healthy_returns_zero(self):
        code, report = run_health_check(self.HEALTHY, {"macro": self._Edge(0.4, 30)})
        self.assertEqual(code, 0)
        self.assertIn("HEALTHY", report)

    def test_an_inverted_category_needs_review(self):
        code, report = run_health_check(self.HEALTHY, {"macro": self._Edge(-0.2, 30)})
        self.assertEqual(code, 1)
        self.assertIn("INVERTED", report)

    def test_a_high_escrow_ratio_needs_review(self):
        summary = dict(self.HEALTHY, reserve_ratio_pct=18.0)
        code, report = run_health_check(summary, {})
        self.assertEqual(code, 1)
        self.assertIn("above the 15% review threshold", report)

    def test_the_threshold_boundary_is_not_an_alert(self):
        self.assertEqual(run_health_check(dict(self.HEALTHY, reserve_ratio_pct=15.0), {})[0], 0)

    def test_an_unmeasured_category_is_not_a_failure(self):
        """Absence of evidence is not an inverted edge; alerting trains people to ignore this."""
        self.assertEqual(run_health_check(self.HEALTHY, {"new": self._Edge(0.0, 0)})[0], 0)

    def test_both_problems_are_reported_together(self):
        code, report = run_health_check(dict(self.HEALTHY, reserve_ratio_pct=20.0),
                                        {"macro": self._Edge(-0.1, 30)})
        self.assertEqual(code, 1)
        self.assertIn("INVERTED", report)
        self.assertIn("review threshold", report)


# ============================================================================
# FINAL LOCK: resolution-hold fee, tag back-fill race
# ============================================================================

class TestResolutionHoldHurdle(unittest.TestCase):
    def _hook(self, one_way):
        hook = MonarchBankrollHook(config=dict(
            TEST_CONFIG, bot_integration={"assumed_round_trip_fee": 0.02}))
        hook.fetch_clob_fee_rate = (
            lambda token_id, price=0.5, holds_to_resolution=False:
            one_way if holds_to_resolution else one_way * 2)
        return hook

    def test_holding_halves_the_hurdle(self):
        hook = self._hook(0.02)
        sold = hook.breakeven_gross_edge(token_id="t", price=0.5)
        held = hook.breakeven_gross_edge(token_id="t", price=0.5, holds_to_resolution=True)
        self.assertAlmostEqual(held, sold / 2)

    def test_a_dutch_book_clears_an_edge_a_scalp_cannot(self):
        """
        The practical consequence: at a 4% politics rate and 50c, a 4% edge is a
        loser if you sell out and a winner if you redeem.
        """
        hook = self._hook(0.02)
        self.assertLess(hook.breakeven_gross_edge(token_id="t", price=0.5,
                                                  holds_to_resolution=True), 0.04)
        self.assertGreater(hook.breakeven_gross_edge(token_id="t", price=0.5), 0.04)

    def test_the_default_is_the_conservative_two_leg_charge(self):
        hook = self._hook(0.02)
        self.assertAlmostEqual(hook.breakeven_gross_edge(token_id="t", price=0.5),
                               hook.breakeven_gross_edge(token_id="t", price=0.5,
                                                         holds_to_resolution=False))


class TestStrategyTagBackfill(unittest.TestCase):
    """
    An execution receipt and the Data API sync describe the same fill. The ledger
    dedupes with ON CONFLICT IGNORE, so whichever lands second is discarded - and
    if that is the receipt, the strategy tag goes with it and the position counts
    against no capital bucket.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "test_tax.db"
        init_db(self.db_path)
        self.imports = self.root / "imports"
        self.imports.mkdir()
        self.watcher = CSVWatcher(imports_dir=self.imports, db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    LEDGER_KEY = "0xabc#85508226579776661565"

    def _untagged_row(self):
        """What the Data API sync writes: same fill, no strategy attribution."""
        process_batch([{
            "source": "polymarket", "tx_hash": self.LEDGER_KEY,
            "timestamp": "2026-03-01 12:00:00", "asset_class": "prediction_market",
            "symbol": "WILL-FED-CUT-RATES-YES", "side": "BUY", "quantity": 100.0,
            "price": 0.42, "fee": 0.0, "total_value": 42.0,
            "notes": "Polymarket CLOB fill (data API)",
        }], db_path=self.db_path)

    def _receipt(self, strategy="dutched_arb"):
        path = self.imports / f"fills_polymarket_{strategy}.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "symbol", "side", "quantity", "price",
                             "fee", "tx_hash", "source", "notes"])
            writer.writerow(["2026-03-01 12:00:00", "WILL-FED-CUT-RATES-YES", "BUY",
                             "100.0", "0.42", "0", self.LEDGER_KEY, "polymarket",
                             f"strategy:{strategy};"])
        return path

    def _notes(self):
        conn = get_connection(self.db_path)
        try:
            return [r["notes"] for r in
                    conn.execute("SELECT notes FROM transactions").fetchall()]
        finally:
            conn.close()

    def _exposure(self, strategy="dutched_arb"):
        return MonarchBankrollHook(tax_year=2026, db_path=self.db_path,
                                   config=TEST_CONFIG).get_strategy_open_exposure(strategy)

    def test_the_race_without_the_fix_would_lose_the_tag(self):
        """The insert really is discarded - the back-fill is what saves the tag."""
        self._untagged_row()
        self._receipt()
        self.watcher.scan_once(require_stable=False)
        self.assertEqual(len(self._notes()), 1, "the fill must not be double-counted")

    def test_the_tag_is_attached_to_the_row_that_won(self):
        self._untagged_row()
        self.assertEqual(self._exposure(), 0.0)
        self._receipt()
        self.watcher.scan_once(require_stable=False)
        self.assertAlmostEqual(self._exposure(), 42.0)

    def test_the_fill_is_not_double_counted(self):
        """Re-inserting would double cost basis; only the note may change."""
        self._untagged_row()
        self._receipt()
        self.watcher.scan_once(require_stable=False)
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT COUNT(*) AS n FROM tax_lots").fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(rows, 1)

    def test_an_already_tagged_row_is_not_re_tagged(self):
        """A later strategy must not be able to steal an earlier one's trade."""
        self._receipt("dutched_arb")
        self.watcher.scan_once(require_stable=False)
        self._receipt("sandbox")
        self.watcher.scan_once(require_stable=False)
        notes = " ".join(self._notes())
        self.assertIn("strategy:dutched_arb;", notes)
        self.assertNotIn("strategy:sandbox;", notes)
        self.assertAlmostEqual(self._exposure("sandbox"), 0.0)

    def test_a_different_symbol_on_the_same_hash_is_not_tagged(self):
        """
        One Polygon transaction can carry several markets. Keying the back-fill on
        tx_hash alone would stamp one strategy's tag onto another's position.
        """
        process_batch([{
            "source": "polymarket", "tx_hash": self.LEDGER_KEY,
            "timestamp": "2026-03-01 12:00:00", "asset_class": "prediction_market",
            "symbol": "SOME-OTHER-MARKET-YES", "side": "BUY", "quantity": 50.0,
            "price": 0.20, "fee": 0.0, "total_value": 10.0, "notes": "other market",
        }], db_path=self.db_path)
        self._receipt()
        self.watcher.scan_once(require_stable=False)
        conn = get_connection(self.db_path)
        try:
            other = conn.execute(
                "SELECT notes FROM transactions WHERE symbol = 'SOME-OTHER-MARKET-YES'"
            ).fetchone()["notes"]
        finally:
            conn.close()
        self.assertNotIn("strategy:", other)

    def test_backfill_is_a_no_op_without_tags(self):
        self._untagged_row()
        self.assertEqual(self.watcher.backfill_strategy_tags(
            [{"source": "polymarket", "tx_hash": self.LEDGER_KEY, "notes": "no tag here",
              "symbol": "WILL-FED-CUT-RATES-YES", "side": "BUY"}]), 0)

    def test_a_receipt_arriving_first_still_works(self):
        """The ordinary path: no race, tag lands with the insert."""
        self._receipt()
        self.watcher.scan_once(require_stable=False)
        self.assertAlmostEqual(self._exposure(), 42.0)


if __name__ == "__main__":
    unittest.main()
