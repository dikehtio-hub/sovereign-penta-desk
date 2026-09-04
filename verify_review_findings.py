"""
Independent verification harness for the Round 18 architecture review.

Run this from C:\\Users\\ixis1\\Desktop\\DEV with the Anaconda python:

    python verify_review_findings.py

Every check prints PASS (the reviewer's claim reproduced) or FAIL (claim did not
reproduce - the reviewer was wrong, say so). Nothing here writes to a real vault,
a real database, or a real paper account: config and harvester checks run against
temp directories, and the vault checks are read-only.

The point is that a reviewer's claim you cannot reproduce is not a finding. Two of
the claims in the review were initially WRONG and were retracted after measurement
(see CHECK 5) - assume the same is possible for the rest.
"""

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time

DEV = pathlib.Path(__file__).resolve().parent
HL = DEV / "HyperLiquid" / "HL_Monarch"
PM = DEV / "Polymarket" / "Polymarket_Monarch"
QL = DEV / "quant_trading_lab"

results = []


def report(name, ok, detail=""):
    results.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        for line in str(detail).rstrip().splitlines():
            print(f"         {line}")


def header(n, title):
    print(f"\n{'=' * 72}\nCHECK {n}: {title}\n{'=' * 72}")


# --------------------------------------------------------------- 1. test suites

def check_suites():
    header(1, "Test suites - claimed 557 / 237 / 167")
    for label, cwd, exe in (
        ("HL_Monarch", HL, sys.executable),
        ("Polymarket_Monarch", PM, sys.executable),
        ("quant_trading_lab", QL, str(QL / "venv" / "Scripts" / "python.exe")),
    ):
        if not pathlib.Path(exe).exists() and label == "quant_trading_lab":
            report(f"{label} suite", False, "venv python not found")
            continue
        out = subprocess.run([exe, "-m", "pytest", "tests/", "-q"],
                             cwd=str(cwd), capture_output=True, text=True)
        tail = [l for l in out.stdout.strip().splitlines() if "passed" in l or "failed" in l]
        line = tail[-1] if tail else "(no summary line)"
        report(f"{label} suite", "failed" not in line and "passed" in line, line)


# ------------------------------------------------- 2. killswitch parse fail-open

def check_parser():
    header(2, "BLOCKER - which corruptions empty the config dict?")
    sys.path.insert(0, str(HL))
    from config.dynamic_config import parse_yaml_frontmatter as p

    cases = {
        "valid":              "---\nemergency_killswitch: true\n---\n",
        "leading blank line": "\n---\nemergency_killswitch: true\n---\n",
        "UTF-8 BOM":          "\ufeff---\nemergency_killswitch: true\n---\n",
        "closing fence lost": "---\nemergency_killswitch: true\n",
        "no frontmatter":     "# Config\nemergency_killswitch: true\n",
        "truncated mid-save": "---\nemergency_kills",
    }
    emptied = []
    for name, text in cases.items():
        d = p(text)
        if name == "valid":
            report("valid frontmatter parses", d.get("emergency_killswitch") is True)
            continue
        if not d:
            emptied.append(name)
    report("corruptions that empty the dict >= 5", len(emptied) >= 5,
           "emptied by: " + ", ".join(emptied))


# ------------------------------------------- 3. killswitch disarms end-to-end

def check_killswitch_disarms():
    header(3, "BLOCKER - killswitch disarms, and does not recover")
    sys.path.insert(0, str(HL))
    import config.dynamic_config as dc

    for label, corrupt in (
        ("leading blank line", "\n---\nemergency_killswitch: true\n---\n"),
        ("UTF-8 BOM",          "\ufeff---\nemergency_killswitch: true\n---\n"),
        ("closing fence lost", "---\nemergency_killswitch: true\n"),
    ):
        tmp = pathlib.Path(tempfile.mkdtemp())
        note = tmp / "Bot_Config.md"
        note.write_text("---\nemergency_killswitch: true\n---\n", encoding="utf-8")
        m = dc.DynamicConfigManager(vault_path=tmp)
        armed = m.get_config().emergency_killswitch
        time.sleep(0.05)
        note.write_text(corrupt, encoding="utf-8")
        after = m.get_config().emergency_killswitch
        retry = m.get_config().emergency_killswitch
        report(f"disarms on: {label}", armed and not after,
               f"armed={armed} after={after} retry={retry}"
               + ("  <-- stays disarmed" if not retry else ""))


# ------------------------------- 4. harvester trades through an armed killswitch

def check_harvester_bypass():
    header(4, "BLOCKER - basis harvester opens a position with killswitch ARMED")
    sys.path.insert(0, str(HL))
    import config.dynamic_config as dc
    from execution.basis_harvester import BasisHarvester

    tmp = pathlib.Path(tempfile.mkdtemp())
    note = tmp / "Bot_Config.md"
    note.write_text("---\nemergency_killswitch: true\n---\n", encoding="utf-8")
    dc.DynamicConfigManager._instance = None
    dc.DynamicConfigManager.get_instance(vault_path=tmp)

    opp = {"coin": "MON", "spot_symbol": "MON", "mark_px": 3.37, "funding_apr": 56.0,
           "net_apr": 56.0, "spread_bps": 0.4, "holding_days": 7.0,
           "is_spot_backed": True, "perp_sz_decimals": 0, "spot_sz_decimals": 2}

    blocked = BasisHarvester(100_000.0, str(tmp / "a.json")).open_position(opp) is None
    time.sleep(0.05)
    note.write_text("\n---\nemergency_killswitch: true\n---\n", encoding="utf-8")
    traded = BasisHarvester(100_000.0, str(tmp / "b.json")).open_position(opp)

    report("armed killswitch blocks", blocked)
    report("one blank line lets it TRADE", traded is not None,
           f"opened {traded['coin']} ${traded['notional_per_leg']:,.0f}/leg" if traded
           else "still blocked - claim did NOT reproduce")
    dc.DynamicConfigManager._instance = None


# ------------------------------------------------------- 5. dangling wikilinks

def check_links():
    header(5, "Dangling wikilinks - the reviewer's FIRST count of 30 was WRONG")
    print("  A naive basename-only matcher reports ~30 dangling links. Obsidian also")
    print("  resolves path-qualified [[Wallets/0x...]] links, so the real count is 0.")
    print("  This check exists to show how a bad matcher manufactures a finding.\n")
    for vault in (DEV / "obsidian_vault", HL / "obsidian_vault"):
        if not vault.is_dir():
            continue
        # Canvases are link targets too, and are addressed WITH their extension
        # ([[Canvases/X.canvas]]). Globbing only *.md made this checker report a
        # valid canvas link as dangling - the second false positive it produced,
        # after missing path-qualified links. A checker that invents findings is
        # worse than no checker.
        targets = list(vault.rglob("*.md")) + list(vault.rglob("*.canvas"))
        stems = {p.stem for p in targets} | {p.name for p in targets}
        rels = ({p.relative_to(vault).with_suffix("").as_posix() for p in targets}
                | {p.relative_to(vault).as_posix() for p in targets})
        naive, correct = set(), set()
        for p in vault.rglob("*.md"):
            body = p.read_text(encoding="utf-8", errors="replace")
            for m in re.findall(r"\[\[([^\]|#]+)", body):
                t = m.strip().lstrip("./")
                if t and t not in stems:
                    naive.add(t)
                if t and t not in stems and t not in rels:
                    correct.add(t)
        report(f"{vault.name} @ {vault.parent.name}: 0 real dangling links",
               len(correct) == 0,
               f"naive matcher: {len(naive)} | path-aware: {len(correct)}")


# ------------------------------------------------------ 6. vault fragmentation

def check_vaults():
    header(6, "Vault fragmentation - is the SHARED vault the live one?")
    rows = []
    for v in (DEV / "obsidian_vault", HL / "obsidian_vault", PM / "obsidian_vault"):
        if v.is_dir():
            notes = list(v.rglob("*.md"))
            newest = max((p.stat().st_mtime for p in notes), default=0)
            rows.append((v, len(notes), newest))
    for v, n, ts in rows:
        stamp = time.strftime("%m-%d %H:%M", time.localtime(ts))
        print(f"         {n:3d} notes  newest {stamp}  {v}")
    report("only one vault exists", len(rows) == 1,
           f"{len(rows)} vaults found - wikilinks do not resolve across roots")
    if len(rows) > 1:
        freshest = max(rows, key=lambda r: r[2])[0]
        report("the SHARED vault is the freshest", freshest == DEV / "obsidian_vault",
               f"freshest is {freshest}")


# ------------------------------------------------- 7. user-notes data loss path

def check_user_notes():
    header(7, "preserve_user_notes returns the DEFAULT template on read failure")
    sys.path.insert(0, str(HL))
    from analytics.obsidian_links import preserve_user_notes, USER_NOTES_HEADER

    tmp = pathlib.Path(tempfile.mkdtemp())
    note = tmp / "Whale.md"
    note.write_text(f"# Whale\n{USER_NOTES_HEADER}\nMY IRREPLACEABLE RESEARCH\n",
                    encoding="utf-8")
    kept = preserve_user_notes(note, "DEFAULT TEMPLATE")
    report("readable note preserves user research", "IRREPLACEABLE" in kept)

    # Simulate an externally re-encoded note (UTF-16 is what Windows tools emit).
    note.write_bytes("# Whale\n{}\nMY IRREPLACEABLE RESEARCH\n"
                     .format(USER_NOTES_HEADER).encode("utf-16"))
    lost = preserve_user_notes(note, "DEFAULT TEMPLATE")
    report("UTF-16 note LOSES user research", "IRREPLACEABLE" not in lost,
           f"returned: {lost.strip()[:60]!r}")


# ------------------------------------------------------- 8. dual-market sizing

def check_sizing():
    header(8, "Dual-market sizing - reviewer says this part is CORRECT")
    exe = QL / "venv" / "Scripts" / "python.exe"
    if not exe.exists():
        report("quant_lab venv present", False, "venv python missing")
        return
    code = (
        "import sys; sys.path.insert(0,'.')\n"
        "from engine.risk_sentinel import RiskSentinel\n"
        "rs=RiskSentinel()\n"
        "for s,e,st in (('NQ',25000.,24950.),('MNQ',25000.,24950.),"
        "('BTCUSDT',78000.,77220.),('ETHUSDT',2470.,2445.)):\n"
        "    print(s, rs.calculate_position_size(symbol=s,entry_price=e,stop_price=st))\n"
    )
    out = subprocess.run([str(exe), "-c", code], cwd=str(QL),
                         capture_output=True, text=True)
    sizes = dict(l.split() for l in out.stdout.strip().splitlines() if " " in l)
    report("futures and crypto both size without error", len(sizes) == 4, out.stdout.strip())
    if sizes:
        report("crypto sizes fractionally (respects lot_size)",
               "." in sizes.get("BTCUSDT", ""), f"BTCUSDT={sizes.get('BTCUSDT')}")
        report("ETHUSDT binds at its QUANTITY cap (drifts with price)",
               sizes.get("ETHUSDT") == "20.0", f"ETHUSDT={sizes.get('ETHUSDT')}")


# -------------------------------------------------------- 9. crypto cap drift

def check_cap_drift():
    header(9, "Crypto position caps are QUANTITY, so notional drifts with price")
    spec = QL / "config" / "asset_specs.json"
    if not spec.exists():
        report("asset_specs.json present", False)
        return
    data = json.loads(spec.read_text(encoding="utf-8"))
    crypto = [a for a in data["assets"] if a.get("asset_class") == "crypto_perpetual"]
    ok = all("margin_requirement_usd" not in a for a in crypto)
    for a in crypto:
        print(f"         {a['symbol']:9s} max_position_size={a.get('max_position_size')} "
              f"(quantity)  margin_requirement_usd={a.get('margin_requirement_usd', 'ABSENT')}")
    report("crypto specs carry no margin_requirement_usd", ok,
           "so any cross-asset exposure sum must special-case crypto")


def main():
    print(__doc__)
    for fn in (check_suites, check_parser, check_killswitch_disarms,
               check_harvester_bypass, check_links, check_vaults,
               check_user_notes, check_sizing, check_cap_drift):
        try:
            fn()
        except Exception as e:
            report(f"{fn.__name__} crashed", False, f"{type(e).__name__}: {e}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{'=' * 72}\n{passed}/{len(results)} checks reproduced the review's claims.")
    print("A FAIL means the reviewer was wrong about that item. Say so explicitly.")


if __name__ == "__main__":
    main()
