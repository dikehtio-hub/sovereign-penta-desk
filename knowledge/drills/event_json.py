"""Write the drill's event.json from ONE human-supplied number, correctly, under time pressure.

    python -m knowledge.drills.event_json --bps 0            # the statement said: no change
    python -m knowledge.drills.event_json --bps 25           # hike 25 bps
    python -m knowledge.drills.event_json --bps -25 --force  # overwrite an existing file (a correction)

Round 121 (operator-permissioned; Antigravity section 3.1 item 2). At 14:00 on 2026-09-16 the operator reads
the Federal Reserve statement and must write ./event.json in the shape the survival curve and the pages
gate on. The DECISION - the number - stays human and is the only argument. Everything else (kind, source,
confidence 0.995, observed_at) is written the same way every time, so a slipped quote or a missing field
cannot be what goes wrong two minutes after the print. Refuses to overwrite an existing event.json unless
--force, and prints the exact file it wrote. It never fetches anything and never decides the number.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import DEV_ROOT, EXIT_FINDINGS, EXIT_OK

DEFAULT_PATH = Path("event.json")                      # the drill card's step 1: "write ./event.json" at the repo root
SOURCE = "federalreserve.gov statement"
CONFIDENCE = 0.995                                     # only ever from the statement itself; nothing automated may decide
KIND = "fed_rate"


def build_event(bps: int, *, source: str = SOURCE, observed_at: datetime | None = None) -> dict:
    observed_at = observed_at or datetime.now(timezone.utc)
    return {"kind": KIND, "payload": {"change_bps": int(bps)}, "source": source, "confidence": CONFIDENCE,
            "observed_at": observed_at.isoformat().replace("+00:00", "Z")}


def write_event(path: Path, event: dict, *, force: bool = False) -> bool:
    """Write the file; False (and no write) when it exists and force is not set."""
    if path.exists() and not force:
        return False
    path.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.drills.event_json", description=__doc__.split("\n\n")[0])
    ap.add_argument("--bps", type=int, required=True, help="the rate change in basis points, read off the statement (0 = hold)")
    ap.add_argument("--source", default=SOURCE, help=f"default: {SOURCE!r}")
    ap.add_argument("--out", type=Path, default=DEV_ROOT / DEFAULT_PATH)
    ap.add_argument("--force", action="store_true", help="overwrite an existing event.json (a correction)")
    ap.add_argument("--observed-at", default=None, help="ISO instant (default: now, UTC)")
    a = ap.parse_args(argv)
    observed = datetime.fromisoformat(a.observed_at.replace("Z", "+00:00")).astimezone(timezone.utc) if a.observed_at else None
    event = build_event(a.bps, source=a.source, observed_at=observed)
    if not write_event(a.out, event, force=a.force):
        print(f"[REFUSE] {a.out} exists; re-run with --force if this is a correction (exit {EXIT_FINDINGS})", file=out)
        return EXIT_FINDINGS
    print(f"[WRITE] {a.out}", file=out)
    print(json.dumps(event, indent=2), file=out)
    print(f"change_bps={event['payload']['change_bps']}  -> next: the survival curve, per the drill card", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
