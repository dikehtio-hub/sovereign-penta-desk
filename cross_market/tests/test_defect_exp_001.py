"""
DEFECT-EXP-001: the cross-market exporter must survive the retention sweep.

`load_questions` listed the drop folder with `glob()` and then called `.stat()`
on every entry to build a sort key. The Polymarket watcher's `prune_stamped_drops`
deletes 192 h-old drops on its own 300 s cycle, so a file could vanish between the
listing and the stat. The resulting FileNotFoundError propagated out of the
exporter's `while True:` - which catches only KeyboardInterrupt - and killed the
process. It happened three times in ten days (2026-09-14 06:28, 2026-09-14 21:20,
2026-09-16 03:55), each needing a human to restart it.

Commit 1 of 2. _safe_mtime: a file that disappears mid-listing sorts first and
is skipped by the read below, instead of raising. Commit 2 removes the need to
stat the whole folder at all.
"""
import json
import tempfile
import unittest
from pathlib import Path

from cross_market.interfaces.obsidian_exporter import _safe_mtime, load_questions


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


if __name__ == "__main__":
    unittest.main()
