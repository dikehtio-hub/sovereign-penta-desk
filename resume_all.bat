@echo off
title Monarch - Resume Full Data Pipeline (collector + data ecosystem + telemetry)
chcp 65001 >nul
setlocal EnableDelayedExpansion

rem ======================================================================
rem  resume_all.bat  -  ONE command to bring the whole pipeline back after
rem  a reboot (or after any component dies).  SAFE to run whether things are
rem  up or down: EVERY component is gated on its OWN liveness, so it never
rem  double-starts and never forgets the collector.
rem
rem  Round 123 (R123-1.A.4): the telemetry exporters are recovered by their
rem  own per-process liveness (knowledge.drills.telemetry_health --ensure),
rem  NOT by using "watcher up" as a proxy for "ecosystem up".  That proxy was
rem  the bug: the watcher stayed up while tax/sports telemetry died silently,
rem  and resume_all skipped them.  Each layer now stands on its own.
rem
rem  Layers, in order:
rem    1. HL price collector + supervisor   (run_collector_service.py --status)
rem    2. Data ecosystem: Polymarket watcher + cross-market exporter (each --status)
rem    3. Telemetry: the 5 per-desk Obsidian exporters (telemetry_health --ensure)
rem ======================================================================

set "ROOT=%~dp0"
set "HLDIR=%ROOT%HyperLiquid\HL_Monarch"

echo ======================================================================
echo  RESUME ALL - Monarch pipeline
echo ======================================================================

rem ---- 1. Price collector + supervisor ---------------------------------
echo.
echo [1/3] Price collector (run_collector_service.py)
pushd "%HLDIR%"
python run_collector_service.py --status | python -c "import sys,json;d=json.load(sys.stdin);sys.exit(0 if d.get('running') else 3)"
if errorlevel 3 (
    echo   collector is DOWN - launching...
    call "%HLDIR%\scripts\launchers\start_collector.bat"
) else (
    echo   collector already running - kept. No second supervisor started.
)
popd

rem ---- 2. Data ecosystem: watcher + cross-market exporter --------------
rem Each is checked on its OWN --status (exit 3 = stopped) and launched only if down.
echo.
echo [2/3] Data ecosystem (Polymarket watcher + cross-market exporter)
python -m cross_market.ingestors.polymarket_fetcher --status >nul 2>&1
if errorlevel 3 (
    echo   watcher is DOWN - launching...
    call "%ROOT%start_polymarket_watcher.bat"
) else (
    echo   watcher already running - kept.
)
python -m cross_market.interfaces.obsidian_exporter --status >nul 2>&1
if errorlevel 3 (
    echo   cross-market exporter is DOWN - launching...
    call "%ROOT%start_cross_market_exporter.bat"
) else (
    echo   cross-market exporter already running - kept.
)

rem ---- 3. Telemetry: the 5 per-desk Obsidian exporters -----------------
rem Per-exporter process liveness; launches only the dead ones, detached, no duplicates.
echo.
echo [3/3] Telemetry exporters (per-desk dashboards)
python -m knowledge.drills.telemetry_health --ensure

rem ---- verify ----------------------------------------------------------
echo.
echo Waiting 8s for detached processes to settle, then verifying...
timeout /t 8 >nul 2>&1
echo ----------------------------------------------------------------------
echo  HEALTH CHECK
echo ----------------------------------------------------------------------

pushd "%HLDIR%"
python run_collector_service.py --status | python -c "import sys,json;d=json.load(sys.stdin);print('  collector/supervisor : ' + ('RUNNING pid '+str(d.get('supervisor_pid')) if d.get('running') else 'DOWN'))"
popd

python -m cross_market.ingestors.polymarket_fetcher --status >nul 2>&1
if errorlevel 3 (echo   polymarket watcher   : DOWN) else (echo   polymarket watcher   : RUNNING)

python -m cross_market.interfaces.obsidian_exporter --status >nul 2>&1
if errorlevel 3 (echo   cross-market export  : DOWN) else (echo   cross-market export  : RUNNING)

echo   telemetry exporters  :
python -m knowledge.drills.telemetry_health

echo ----------------------------------------------------------------------
echo  Done.  If any line says DOWN, re-run this script or check
echo  HyperLiquid\HL_Monarch\data\collector.log.
echo ======================================================================
endlocal
