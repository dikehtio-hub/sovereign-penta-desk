@echo off
title HL_Monarch - Stop Collector Daemon
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 👑 Stopping HL_Monarch Ingestion Collector Daemon...
echo ======================================================================
rem Round 119 (2026-09-06): the supervisor is stopped FIRST, or it relaunches the collector the moment
rem the collector dies. And the pids are read with delayed expansion: inside a parenthesised block
rem cmd expands %VAR% when the block is PARSED, before set /p runs, so the original script ran
rem "taskkill /PID  /F /T" with an EMPTY pid, printed "Terminating PID ...", deleted the pid files and
rem reported success while both processes kept running (found live during the Round 119 restart).
setlocal EnableDelayedExpansion
set "SPID="
set "PID="
if exist "data\collector_service.pid" set /p SPID=<"data\collector_service.pid"
if exist "data\collector.pid" set /p PID=<"data\collector.pid"
if defined SPID (
    echo Terminating Service Supervisor PID !SPID!...
    taskkill /PID !SPID! /F /T >nul 2>&1
    if errorlevel 1 echo   ^(taskkill reported no such process^)
    del /f /q "data\collector_service.pid" >nul 2>&1
)
if defined PID (
    echo Terminating Collector PID !PID!...
    taskkill /PID !PID! /F /T >nul 2>&1
    if errorlevel 1 echo   ^(taskkill reported no such process^)
    del /f /q "data\collector.pid" >nul 2>&1
)
if not defined SPID if not defined PID echo   ^(no pid files: nothing to stop^)
endlocal
echo ✓ Stop sequence finished - verify with: tasklist /FI "PID eq <pid>"
timeout /t 2 >nul 2>&1
