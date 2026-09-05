@echo off
title Polymarket Watcher Launcher (detached)
cd /d "%~dp0"
:: Round 73 review: the watcher feeds Item 18's 24 h series; a closed console must not break it.
:: Detached under pythonw, output in Sports_Desk\data\polymarket_watcher.log, one watcher per folder - pid lock.
:: No bare parentheses inside the if-block below: an unescaped ) in an echo closes the block early.
:: The pythonw lookup sits OUTSIDE the if-block: cmd expands %PYW% when it parses the whole block,
:: before `set` has run inside it, so Start-Process would get an empty -FilePath (rc 255).
for /f "delims=" %%P in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%P"
if not exist "%PYW%" set "PYW=pythonw"
python -m cross_market.ingestors.polymarket_fetcher --status
if errorlevel 3 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PYW%' -ArgumentList '-m','cross_market.ingestors.polymarket_fetcher','--live','--watch','--interval','300','--tags','sports,crypto,fed-rates','--keywords','\"fed,rate cut,bitcoin,btc\"','--log-file','Sports_Desk\data\polymarket_watcher.log' -WorkingDirectory '%CD%'"
    echo ✓ Polymarket watcher launched DETACHED, no window. Log: Sports_Desk\data\polymarket_watcher.log
) else (
    echo ✓ Polymarket watcher already running - kept. Holder shown above.
)
