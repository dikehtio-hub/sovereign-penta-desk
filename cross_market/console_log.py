"""
Console tee for detached loops (Round 73 review).

The supervisor already runs under pythonw with its output in a file; the
Polymarket watcher and the Cross-Market Arb exporter ran in console windows,
which is one closed window away from a broken 24 h series. `tee_stdout(path)`
sends every print to the console (when there is one) AND to an append-only,
line-buffered file - and under pythonw, where sys.stdout is None, to the file
alone. Never raises: a logging problem must not take a loop down.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional


class Tee:
    def __init__(self, *streams: Any):
        self.streams = [s for s in streams if s is not None]

    def write(self, text: str) -> int:
        for stream in self.streams:
            try:
                stream.write(text)
            except Exception:                               # noqa: BLE001
                continue
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:                               # noqa: BLE001
                continue

    def isatty(self) -> bool:
        return False


def tee_stdout(path: Path, also_stderr: bool = True) -> Optional[Path]:
    """Route stdout (and stderr) to `path` as well as the console; returns the path, or None on failure."""
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = open(target, "a", buffering=1, encoding="utf-8", errors="replace")
    except Exception:                                       # noqa: BLE001
        return None
    sys.stdout = Tee(sys.stdout, handle) if sys.stdout is not None else handle
    if also_stderr:
        sys.stderr = Tee(sys.stderr, handle) if sys.stderr is not None else handle
    return target
