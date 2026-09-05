@echo off
title HL_Monarch - Collector Daemon Launcher
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 👑 Starting HL_Monarch Background Ingestion Collector Service...
echo ======================================================================
rem Round 53 (Ruling 53-1): DETACHED. pythonw has no console window, so closing a
rem terminal cannot take the supervisor - and its keep-awake hold - down with it.
rem Everything it prints goes to data\collector_service.jsonl and data\collector.log.
rem To watch it live:  type data\collector.log   |   python run_collector_service.py --status
for /f "delims=" %%P in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%P"
if not exist "%PYW%" set "PYW=pythonw"
rem Round 54: Start-Process (ShellExecute) instead of "start": the supervisor no longer inherits
rem the caller's stdout/stderr pipe, so a script or agent that captures this launcher's output
rem returns at once instead of blocking for as long as the service lives.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PYW%' -ArgumentList 'run_collector_service.py','--quiet' -WorkingDirectory '%CD%'"
echo ✓ Ingestion collector service launched DETACHED (no window). Logs: data\collector_service.jsonl, data\collector.log
timeout /t 3 >nul 2>&1
