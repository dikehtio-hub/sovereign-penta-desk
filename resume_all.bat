@echo off
title Monarch - Resume Full Data Pipeline (collector + ecosystem)
chcp 65001 >nul
setlocal EnableDelayedExpansion

rem ======================================================================
rem  resume_all.bat  (Round 122, built for the "shut down tonight, resume
rem  in the morning" case)  -  ONE command to bring the whole data pipeline
rem  back after a reboot.  It is SAFE to run whether things are up or down:
rem  every launch is gated on that daemon's own --status, so it never
rem  double-starts and never forgets the price collector (the Saturday
rem  09-06 failure was exactly that - the watcher came back, the collector
rem  did not, and BTC prices stopped for 9 hours).
rem
rem  It brings back, in order:
rem    1. the HL price collector + its supervisor   (run_collector_service.py)
rem    2. the ecosystem: Polymarket watcher, cross-market exporter, and the
rem       five Obsidian sync exporters               (start_all_ecosystem_sync.bat)
rem
rem  It writes nothing to the vault or the databases itself; it only starts
rem  the same processes the canonical launchers do.
rem ======================================================================

set "ROOT=%~dp0"
set "HLDIR=%ROOT%HyperLiquid\HL_Monarch"

echo ======================================================================
echo  RESUME ALL - Monarch data pipeline
echo ======================================================================

rem ---- 1. Price collector + supervisor ---------------------------------
echo.
echo [1/2] Price collector (run_collector_service.py)
pushd "%HLDIR%"
python run_collector_service.py --status | python -c "import sys,json;d=json.load(sys.stdin);sys.exit(0 if d.get('running') else 3)"
if errorlevel 3 (
    echo   collector is DOWN - launching...
    call "%HLDIR%\scripts\launchers\start_collector.bat"
) else (
    echo   collector already running - kept. No second supervisor started.
)
popd

rem ---- 2. Ecosystem (watcher + exporters) ------------------------------
rem The Polymarket watcher being up is our proxy for "ecosystem already
rem running": if it is up we SKIP the ecosystem launcher, because that
rem script starts the five Obsidian sync exporters unconditionally and we
rem do not want duplicates.  After a reboot the watcher is down, so it runs.
echo.
echo [2/2] Ecosystem (Polymarket watcher + exporters)
python -m cross_market.ingestors.polymarket_fetcher --status >nul 2>&1
if errorlevel 3 (
    echo   ecosystem watcher is DOWN - launching the full ecosystem...
    call "%ROOT%start_all_ecosystem_sync.bat"
) else (
    echo   ecosystem watcher already running - kept. Skipping to avoid duplicate exporters.
)

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

echo ----------------------------------------------------------------------
echo  Done.  If any line says DOWN, re-run this script or check
echo  HyperLiquid\HL_Monarch\data\collector.log.
echo ======================================================================
endlocal
