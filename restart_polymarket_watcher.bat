@echo off
title Polymarket Watcher Restart (Directive 79-2)
cd /d "%~dp0"
:: Round 79 (Directive 79-2): stop the live watcher, then the guarded launcher starts a fresh one running
:: the code on disk (e.g. Round 76 tags). Done inside 60 minutes the stamped series stays continuous.
:: No if-blocks here on purpose (see start_polymarket_watcher.bat for the two cmd traps).
::
:: Round 104 (Ruling R103-F1): WAIT FOR THE LOCK BEFORE ASKING. On 2026-09-05 this script reported
:: "[STATUS] watcher STOPPED - no lock" and exited 3 on a COMPLETELY SUCCESSFUL restart: it called
:: --status about two seconds after a detached Start-Process, before the new pythonw had taken its pid
:: lock. Anything treating that exit code as failure - a human, a task chain - would wrongly conclude
:: the restart broke. The loop below polls --status for up to 10 s and stops at the first success, so
:: the exit code now reports the restart rather than the race.
python -m cross_market.ingestors.polymarket_fetcher --stop
call "%~dp0start_polymarket_watcher.bat"
echo Waiting up to 10s for the new watcher to take the pid lock...
for /L %%i in (1,1,10) do (
    python -m cross_market.ingestors.polymarket_fetcher --status >nul 2>&1
    if not errorlevel 3 goto :locked
    timeout /t 1 /nobreak >nul
)
:locked
python -m cross_market.ingestors.polymarket_fetcher --status
echo Verify above: a NEW pid holds the lock; after the next poll the tags line should read carries tags.
