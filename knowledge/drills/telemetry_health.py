"""Round 123 (R123-1.A): process-liveness health for the five per-desk Obsidian telemetry exporters.

Why this is a separate module (Directive R123-1.A.2): the FOMC drill pre-flight
(``fomc_rehearsal --online``) is the execution gate for the September 16 rate-print drill - it
judges the latency sniper, CLOB depth, target tokens, NTP, and the three *execution* data daemons
(collector, watcher, cross-market exporter). The five telemetry exporters only render Markdown
dashboards for human viewing; a dead one must NEVER block the drill. So telemetry health lives here,
and ``resume_all.bat`` delegates recovery to ``--ensure``.

Why liveness, not mtime (Directive R123-1.A.3): the Quant-Lab, Sports and Tax exporters use
``write_note_if_changed`` (a sha256 guard against disk wear), so an idle desk's dashboard keeps its
old mtime for hours - a file-age check would cry stale every quiet night. Health here is whether the
exporter PROCESS is alive, read from the OS process table (psutil, else PowerShell), never from a file.

CLI:
  python -m knowledge.drills.telemetry_health            # --check: one line per exporter, exit 1 if any down
  python -m knowledge.drills.telemetry_health --json     # machine-readable liveness
  python -m knowledge.drills.telemetry_health --ensure   # launch every DOWN exporter detached, then report
  python -m knowledge.drills.telemetry_health --ensure --dry-run   # say what --ensure would launch, launch nothing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, Optional

# knowledge/drills/telemetry_health.py -> parents[2] is the DEV root
DEV = Path(__file__).resolve().parents[2]
VAULT = DEV / "obsidian_vault"


def _norm(s: str) -> str:
    """Slash-normalized AND lower-cased, so a mixed-case Windows path matches a lowercase posix signature.
    (Round 123 bug: `Tax_Reserve_Agent.obsidian_sync` in the real cmdline never matched a lowercased
    signature until this lowercased both sides - the matcher silently saw tax/sports as always-down.)
    Signatures in ``exporter_specs`` are written lowercase to pair with this."""
    return (s or "").replace("\\", "/").lower()


def _base_pythonw() -> str:
    """The windowless interpreter beside the one running this module (the desks' anaconda pythonw)."""
    cand = Path(sys.executable).with_name("pythonw.exe")
    return str(cand) if cand.exists() else sys.executable


def _venv_pythonw() -> str:
    """Quant-Lab runs in its own venv (Round 122 finding); fall back to the base interpreter if absent."""
    cand = DEV / "quant_trading_lab" / "venv" / "Scripts" / "pythonw.exe"
    return str(cand) if cand.exists() else _base_pythonw()


def exporter_specs() -> list[dict]:
    """The five telemetry exporters: a unique, slash-normalized cmdline SIGNATURE for liveness, and the
    exact launch spec (interpreter, argv, cwd) - the same commands ``start_all_ecosystem_sync.bat`` uses.
    The cross-market exporter is NOT here: it is an execution-pipeline daemon with its own ``--status``,
    guarded separately in ``resume_all.bat``.
    """
    v = str(VAULT)
    base, venv = _base_pythonw(), _venv_pythonw()
    return [
        {"name": "hyperliquid", "signature": "main.py obsidian",
         "interp": base, "cwd": DEV / "HyperLiquid" / "HL_Monarch",
         "args": ["main.py", "obsidian", "--watch", "--interval", "15", "--vault", v, "--throttle-seconds", "60"]},
        {"name": "polymarket", "signature": "obsidian_sync.py",
         "interp": base, "cwd": DEV / "Polymarket" / "Polymarket_Monarch",
         "args": ["obsidian_sync.py", "--watch", "--interval", "15", "--vault", v]},
        {"name": "tax", "signature": "tax_reserve_agent.obsidian_sync",
         "interp": base, "cwd": DEV,
         "args": ["-m", "Tax_Reserve_Agent.obsidian_sync", "--watch", "--interval", "15", "--vault", v]},
        {"name": "sports", "signature": "sports_desk.interfaces.obsidian_exporter",
         "interp": base, "cwd": DEV,
         "args": ["-m", "Sports_Desk.interfaces.obsidian_exporter", "--watch", "--interval", "15", "--vault", v]},
        {"name": "quantlab", "signature": "telemetry/obsidian_exporter",
         "interp": venv, "cwd": DEV / "quant_trading_lab",
         "args": ["telemetry/obsidian_exporter.py", "--interval", "15", "--vault", v]},
    ]


def list_python_cmdlines() -> list[str]:
    """Every running python/pythonw process command line, slash-normalized. psutil when present, else
    PowerShell's CIM. Returns [] rather than raising if neither works (a health probe must not crash)."""
    try:
        import psutil  # noqa: PLC0415
        out = []
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                nm = (p.info.get("name") or "").lower()
                if nm.startswith("python"):
                    out.append(_norm(" ".join(p.info.get("cmdline") or [])))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return out
    except Exception:  # noqa: BLE001 - fall back to the OS, never fail the probe
        pass
    try:
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" "
              "| ForEach-Object { $_.CommandLine }")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
        return [_norm(ln) for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001
        return []


def liveness(cmdlines: Optional[Iterable[str]] = None) -> list[dict]:
    """[{name, signature, running, up}] for each exporter. ``running`` counts matching processes
    (Quant-Lab legitimately shows 2: a parent and its reloader worker), ``up`` is running >= 1.
    ``cmdlines`` is injectable so tests need no real processes."""
    lines = [_norm(c) for c in (cmdlines if cmdlines is not None else list_python_cmdlines())]
    rows = []
    for spec in exporter_specs():
        sig = spec["signature"]
        n = sum(1 for c in lines if sig in c)
        rows.append({"name": spec["name"], "signature": sig, "running": n, "up": n >= 1})
    return rows


def _launch(spec: dict) -> Optional[int]:
    """Start one exporter fully detached, so it OUTLIVES the launching shell and any parent job object.

    On Windows this is ``Start-Process`` (ShellExecute): it breaks away from the caller's job the way the
    surviving daemons do. A plain ``subprocess.Popen`` with ``DETACHED_PROCESS`` is NOT enough - inside a
    kill-on-close job (an automation harness, some terminals) the child is reaped the instant the launcher
    exits, which looked exactly like an instant crash in testing. Returns the child pid, or None if the
    shell did not report one. Off Windows, a detached Popen (for test portability; tests inject a launcher).
    """
    if sys.platform == "win32":
        argl = ", ".join("'%s'" % str(a).replace("'", "''") for a in spec["args"])
        ps = ("(Start-Process -FilePath '%s' -WorkingDirectory '%s' -WindowStyle Hidden -PassThru "
              "-ArgumentList %s).Id" % (str(spec["interp"]).replace("'", "''"),
                                        str(spec["cwd"]).replace("'", "''"), argl))
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout or "Start-Process failed").strip()[:200])
        out = (r.stdout or "").strip().splitlines()
        return int(out[-1]) if out and out[-1].strip().isdigit() else None
    p = subprocess.Popen(
        [spec["interp"], *spec["args"]], cwd=str(spec["cwd"]),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, start_new_session=True,
    )
    return p.pid


def ensure(cmdlines: Optional[Iterable[str]] = None,
           launcher: Optional[Callable[[dict], int]] = None,
           dry_run: bool = False) -> list[dict]:
    """Launch every DOWN exporter (one launch each - liveness is re-read from ``cmdlines`` once, so a
    down exporter is started exactly once), keep the rest. ``launcher`` and ``cmdlines`` are injectable
    for tests; ``dry_run`` reports the plan without launching. Returns [{name, action, pid?}]."""
    launcher = launcher or _launch
    rows = liveness(cmdlines)
    specs = {s["name"]: s for s in exporter_specs()}
    out = []
    for row in rows:
        if row["up"]:
            out.append({"name": row["name"], "action": "kept", "running": row["running"]})
        elif dry_run:
            out.append({"name": row["name"], "action": "would-launch"})
        else:
            try:
                pid = launcher(specs[row["name"]])
                out.append({"name": row["name"], "action": "launched", "pid": pid})
            except Exception as exc:  # noqa: BLE001
                out.append({"name": row["name"], "action": "launch-failed", "error": str(exc)})
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Liveness health for the 5 per-desk telemetry exporters.")
    ap.add_argument("--ensure", action="store_true", help="launch every exporter that is DOWN, then report")
    ap.add_argument("--dry-run", action="store_true", help="with --ensure: report the plan, launch nothing")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.ensure:
        result = ensure(dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for r in result:
                extra = f" pid {r['pid']}" if r.get("pid") else ""
                print(f"[{r['action'].upper():>12}] {r['name']}{extra}")
        return 0

    rows = liveness()
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            tag = "UP  " if r["up"] else "DOWN"
            print(f"[{tag}] {r['name']:<12} ({r['running']} proc)")
        down = [r["name"] for r in rows if not r["up"]]
        print(f"{sum(r['up'] for r in rows)}/5 telemetry exporters up"
              + (f"; DOWN: {', '.join(down)} - run `--ensure` to recover" if down else " - all live"))
    return 0 if all(r["up"] for r in rows) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
