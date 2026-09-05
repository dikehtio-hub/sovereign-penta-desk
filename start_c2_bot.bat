@echo off
title Penta-Desk C2 Bot Launcher (detached)
cd /d "%~dp0"
:: Item 10 Phase 1 (Round 85): the Telegram C2 bot, detached under pythonw, log in cross_market\data\c2_bot.log.
:: Fail-closed: without TELEGRAM_BOT_TOKEN and C2_ADMIN_IDS (user-level env vars) the bot refuses to start -
:: the log will say so. The token is never on this command line and never printed.
:: The pythonw lookup sits OUTSIDE the if-block; the block holds no bare parentheses (Round 73 traps).
for /f "delims=" %%P in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%P"
if not exist "%PYW%" set "PYW=pythonw"
python -m cross_market.interfaces.c2_bot --status
if errorlevel 3 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PYW%' -ArgumentList '-m','cross_market.interfaces.c2_bot','--interval','25','--log-file','cross_market\data\c2_bot.log' -WorkingDirectory '%CD%'"
    echo ✓ C2 bot launched DETACHED, no window. Log: cross_market\data\c2_bot.log
) else (
    echo ✓ C2 bot already running - kept. Holder shown above.
)
