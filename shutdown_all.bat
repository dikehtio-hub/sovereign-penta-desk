@echo off
title Monarch - Clean Shutdown (telemetry + ecosystem + collector, then register the gap)
chcp 65001 >nul
setlocal EnableDelayedExpansion

rem ======================================================================
rem  shutdown_all.bat  -  the mirror of resume_all.bat.
rem
rem  resume_all brings up THREE layers; stop_all_ecosystem_sync.bat only
rem  ever stopped layer 3. The HL collector -- the process writing to an
rem  8.5 GB SQLite database -- had no clean stop at all. This closes that.
rem
rem  Layers, torn down in REVERSE of resume order:
rem    3. Telemetry: the 5 per-desk Obsidian exporters
rem    2. Data ecosystem: Polymarket watcher + cross-market exporter
rem    1. HL price collector + supervisor   (graceful, then WAL checkpoint)
rem
rem  WHY GRACEFUL MATTERS LESS THAN YOU THINK, AND STILL MATTERS:
rem  the database is journal_mode=WAL with synchronous=FULL, so a hard
rem  power-off is RECOVERABLE -- SQLite replays the WAL on next open. The
rem  database is not at risk. What a clean stop buys is (a) checkpointing
rem  the pending WAL into the main file instead of leaving it to replay,
rem  and (b) not severing a write mid-row.
rem
rem  HOW THE COLLECTOR IS STOPPED. The supervisor runs detached under
rem  pythonw: no console, no window. That rules out every signal path on
rem  Windows -- CTRL_BREAK_EVENT needs a shared console group, taskkill
rem  without /F delivers WM_CLOSE to a window that does not exist, and
rem  os.kill() for anything but the CTRL_* events maps onto
rem  TerminateProcess. So run_collector_service.py gained a --stop flag
rem  that drops a sentinel file the supervise loop polls once a second.
rem  It reports "graceful": true/false so you can tell a cooperative stop
rem  from a forced one.
rem
rem  SAFE to run whether things are up or down. Every step is gated.
rem  Prints the gap interval at the end -- register it with:
rem      python -m knowledge.ingest.data_gaps   (after editing data_gaps.json)
rem ======================================================================

set "ROOT=%~dp0"
set "HLDIR=%ROOT%HyperLiquid\HL_Monarch"

for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().ToString(\"yyyy-MM-ddTHH:mm:ssZ\")"') do set "GAP_START=%%i"

echo ======================================================================
echo  SHUTDOWN ALL - Monarch pipeline
echo  gap starts: %GAP_START%
echo ======================================================================
echo.

rem ---------------------------------------------------------------- 3 ---
echo [3/3] Telemetry exporters (5 per-desk Obsidian watchers)...
call "%ROOT%stop_all_ecosystem_sync.bat" >nul 2>&1
echo       stopped.
echo.

rem ---------------------------------------------------------------- 2 ---
echo [2/3] Data ecosystem (Polymarket watcher + cross-market exporter)...
taskkill /FI "WINDOWTITLE eq Polymarket Watcher*" /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Cross-Market*" /T >nul 2>&1
echo       stop signalled.
echo.

rem ---------------------------------------------------------------- 1 ---
echo [1/3] HL collector + supervisor (cooperative stop, then checkpoint)...
pushd "%HLDIR%"

rem run_collector_service.py --stop drops a sentinel the supervise loop polls
rem once a second, waits for the process to go, and only forces if it is still
rem there after --stop-timeout. It checkpoints the WAL either way and reports
rem "graceful": true/false so you can tell which happened.
rem
rem A supervisor started BEFORE the sentinel existed cannot see it and will take
rem the forced path -- that is expected once, and clears on the next resume_all.
"%ROOT%quant_trading_lab\venv\Scripts\python.exe" run_collector_service.py --stop --stop-timeout 30
if errorlevel 3 echo       (nothing was running)
popd
echo.

rem ------------------------------------------------------------ verify ---
echo ======================================================================
echo  VERIFY
echo ======================================================================
powershell -NoProfile -Command "$n=(Get-Process python,pythonw -ErrorAction SilentlyContinue | Measure-Object).Count; Write-Host ('  python/pythonw still running : ' + $n + '  (0 = fully down)')"
git -C "%ROOT%qtl_autoresearch" status --short > "%TEMP%\_ar_status.txt" 2>&1
for %%A in ("%TEMP%\_ar_status.txt") do set "ARSZ=%%~zA"
if "!ARSZ!"=="0" (echo   autoresearch worktree        : CLEAN) else (echo   autoresearch worktree        : UNCOMMITTED CHANGES - see git status)
for /f %%i in ('git -C "%ROOT%quant_trading_lab" rev-parse --short master') do set "LABM=%%i"
echo   lab master fence             : !LABM!   ^(must be 33ebe81^)
echo.

rem --------------------------------------------------------------- gap ---
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().ToString(\"yyyy-MM-ddTHH:mm:ssZ\")"') do set "GAP_MARK=%%i"
echo ======================================================================
echo  REGISTER THE GAP  (knowledge/data_gaps.json, then knowledge.ingest.data_gaps)
echo ======================================================================
echo   start_utc : %GAP_START%
echo   end_utc   : ^<fill in when resume_all.bat runs^>
echo.
echo   Streams that stop recording: HL asset_snapshots / trades /
echo   liquidation_events / cascade_excursions, and Polymarket drops.
echo   L12 lint warns if an evaluation window overlaps an unregistered gap.
echo.
echo   Machine may now be powered off.
echo ======================================================================
timeout /t 5 >nul
endlocal
