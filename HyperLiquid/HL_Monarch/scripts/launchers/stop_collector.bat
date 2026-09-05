@echo off
title HL_Monarch - Stop Collector Daemon
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 👑 Stopping HL_Monarch Ingestion Collector Daemon...
echo ======================================================================
if exist "data\collector.pid" (
    set /p PID=<"data\collector.pid"
    echo Terminating PID %PID%...
    taskkill /PID %PID% /F /T >nul 2>&1
    del /f /q "data\collector.pid" >nul 2>&1
)
if exist "data\collector_service.pid" (
    set /p SPID=<"data\collector_service.pid"
    echo Terminating Service Supervisor PID %SPID%...
    taskkill /PID %SPID% /F /T >nul 2>&1
    del /f /q "data\collector_service.pid" >nul 2>&1
)
echo ✓ Collector daemon stopped.
timeout /t 2 >nul 2>&1
