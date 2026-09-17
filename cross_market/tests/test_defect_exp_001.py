"""
DEFECT-EXP-001: the cross-market exporter must survive the retention sweep.

`load_questions` listed the drop folder with `glob()` and then called `.stat()`
on every entry to build a sort key. The Polymarket watcher's `prune_stamped_drops`
deletes 192 h-old drops on its own 300 s cycle, so a file could vanish between the
listing and the stat. The resulting FileNotFoundError propagated out of the
exporter's `while True:` - which catches only KeyboardInterrupt - and killed the
process. It happened three times in ten days (2026-09-14 06:28, 2026-09-14 21:20,
2026-09-16 03:55), each needing a human to restart it.

Two fixes, tested here:
  1. _safe_mtime: a file that disappears mid-listing sorts first and is skipped,
     instead of raising.
  2. _current_drops: read the newest drop per family instead of all of them,
     which is what "one row per market, newest wins" actually needs. The live
     folder held 3,857 files / 5.5 GB, all parsed EVERY 15 s cycle, which is why
     the loop ran at ~54 s and why the stat pass was wide enough to lose the race.
"""
import json
import tempfile
import unittest
from pathlib import Path

from cross_market.interfaces.obsidian_exporter import (_current_drops, _safe_mtime,
                                                        load_questions)


def _q(token: str, price: float) -> dict:
    return {"token_id": token, "question": f"Q{token}", "yes_price": price, "no_price": 1.0 - price}


def _write(path: Path, rows: list) -> Path:
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


class TestSafeMtime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_sorts_first_instead_of_raising(self):
        gone = self.dir / "never_existed.json"
        self.assertEqual(_safe_mtime(gone), -1.0)

    def test_real_file_returns_its_mtime(self):
        p = _write(self.dir / "polymarket_macro.json", [_q("t1", 0.5)])
        self.assertGreater(_safe_mtime(p), 0.0)

    def test_load_questions_survives_a_drop_deleted_mid_listing(self):
        """The exact race: glob() lists the file, the watcher prunes it, stat() runs.

        Against the unguarded sort key this raises FileNotFoundError - which is
        precisely what killed the exporter three times.
        """
        _write(self.dir / "polymarket_macro.json", [_q("live", 0.42)])
        doomed = _write(self.dir / "polymarket_macro_20260101T000000_000000Z.json", [_q("old", 0.1)])

        real_glob = Path.glob

        def glob_then_prune(self_path, pattern):
            listed = list(real_glob(self_path, pattern))
            if doomed.exists():
                doomed.unlink()                     # the watcher's sweep, mid-listing
            return iter(listed)

        Path.glob = glob_then_prune
        try:
            rows = load_questions(self.dir)         # must not raise
        finally:
            Path.glob = real_glob
        self.assertEqual([r["token_id"] for r in rows], ["live"])


class TestCurrentDropsOnly(unittest.TestCase):
    """Fix 2: the newest drop per family, not the whole 5.5 GB folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_canonical_file_alone_still_loads(self):
        """Pins the behaviour test_polymarket_fetcher depends on."""
        _write(self.dir / "polymarket_sports.json", [_q("a", 0.5), _q("b", 0.25)])
        rows = load_questions(self.dir)
        self.assertEqual(sorted(r["token_id"] for r in rows), ["a", "b"])

    def test_canonical_beats_older_stamped_copies(self):
        _write(self.dir / "polymarket_macro_20260101T000000_000000Z.json", [_q("a", 0.10)])
        _write(self.dir / "polymarket_macro_20260102T000000_000000Z.json", [_q("a", 0.20)])
        _write(self.dir / "polymarket_macro.json", [_q("a", 0.99)])
        rows = load_questions(self.dir)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["yes_price"], 0.99)

    def test_newest_stamp_wins_when_there_is_no_canonical(self):
        _write(self.dir / "polymarket_macro_20260101T000000_000000Z.json", [_q("a", 0.10)])
        _write(self.dir / "polymarket_macro_20260103T000000_000000Z.json", [_q("a", 0.30)])
        _write(self.dir / "polymarket_macro_20260102T000000_000000Z.json", [_q("a", 0.20)])
        rows = load_questions(self.dir)
        self.assertEqual(rows[0]["yes_price"], 0.30)

    def test_families_do_not_shadow_each_other(self):
        """macro and sports are separate files; both must survive the narrowing."""
        _write(self.dir / "polymarket_macro.json", [_q("m1", 0.5)])
        _write(self.dir / "polymarket_sports.json", [_q("s1", 0.6)])
        rows = load_questions(self.dir)
        self.assertEqual(sorted(r["token_id"] for r in rows), ["m1", "s1"])

    def test_old_stamps_are_not_read_at_all(self):
        """The performance claim, asserted rather than assumed: an unparseable
        ancient stamp would raise if it were still being read, and it is not."""
        (self.dir / "polymarket_macro_20250101T000000_000000Z.json").write_text(
            "{{{ not json at all", encoding="utf-8")
        _write(self.dir / "polymarket_macro.json", [_q("m1", 0.5)])
        rows = load_questions(self.dir)
        self.assertEqual([r["token_id"] for r in rows], ["m1"])

    def test_a_delisted_token_leaves_when_it_leaves_the_newest_drop(self):
        """Behaviour change, deliberate: this aligns the exporter with lint C2,
        which already treats 'not in the newest drops' as resolved or delisted."""
        _write(self.dir / "polymarket_macro_20260101T000000_000000Z.json", [_q("gone", 0.5), _q("stays", 0.5)])
        _write(self.dir / "polymarket_macro.json", [_q("stays", 0.7)])
        rows = load_questions(self.dir)
        self.assertEqual([r["token_id"] for r in rows], ["stays"])

    def test_only_one_file_per_family_is_opened(self):
        """The performance claim, measured rather than asserted. 200 stamped drops
        plus a canonical one: the old code opened all 201, this opens 1."""
        for i in range(200):
            _write(self.dir / f"polymarket_macro_202601{i // 24 + 1:02d}T{i % 24:02d}0000_000000Z.json",
                   [_q("a", 0.01 * i)])
        _write(self.dir / "polymarket_macro.json", [_q("a", 0.99)])

        opened = []
        real_read = Path.read_text

        def counting_read(self_path, *a, **kw):
            opened.append(self_path.name)
            return real_read(self_path, *a, **kw)

        Path.read_text = counting_read
        try:
            rows = load_questions(self.dir)
        finally:
            Path.read_text = real_read

        self.assertEqual(len(opened), 1, f"opened {len(opened)} files, expected 1: {opened[:5]}")
        self.assertEqual(opened, ["polymarket_macro.json"])
        self.assertEqual(rows[0]["yes_price"], 0.99)

    def test_current_drops_picks_one_path_per_family(self):
        _write(self.dir / "polymarket_macro.json", [_q("m", 0.5)])
        _write(self.dir / "polymarket_macro_20260101T000000_000000Z.json", [_q("m", 0.1)])
        _write(self.dir / "polymarket_sports_20260101T000000_000000Z.json", [_q("s", 0.2)])
        _write(self.dir / "polymarket_sports_20260202T000000_000000Z.json", [_q("s", 0.3)])
        names = sorted(p.name for p in _current_drops(self.dir))
        self.assertEqual(names, ["polymarket_macro.json",
                                 "polymarket_sports_20260202T000000_000000Z.json"])

    def test_unstamped_legacy_drop_counts_as_sports(self):
        """Round 52 single-tag runs wrote polymarket_<stamp>.json with no family."""
        _write(self.dir / "polymarket_20260101T000000_000000Z.json", [_q("legacy", 0.4)])
        rows = load_questions(self.dir)
        self.assertEqual([r["token_id"] for r in rows], ["legacy"])

    def test_unreadable_current_drop_yields_nothing_rather_than_raising(self):
        (self.dir / "polymarket_macro.json").write_text("not json", encoding="utf-8")
        self.assertEqual(load_questions(self.dir), [])

    def test_missing_directory_is_empty(self):
        self.assertEqual(load_questions(self.dir / "nope"), [])


if __name__ == "__main__":
    unittest.main()
