@echo off
REM ============================================================================
REM  HL_MONARCH - Launch the collector service DETACHED in the background.
REM
REM  Returns your terminal immediately and leaves no console window open. The
REM  service keeps running after you close this window, which is what 99%+
REM  snapshot coverage needs - everything downstream (funding backtester,
REM  squeeze percentiles, precedence validator) is only as good as the
REM  continuity of asset_snapshots.
REM
REM  Usage:
REM     launch_service_background.bat            start detached
REM     launch_service_background.bat status     running? + snapshot coverage
REM     launch_service_background.bat stop       stop the background service
REM     launch_service_background.bat log        tail the structured JSON log
REM
REM  Liveness comes from the supervisor's own PID lockfile
REM  (data\collector_service.pid), queried through `run_collector_service.py
REM  --status`. Earlier versions matched process command lines, which was wrong
REM  in both directions: a stale wmic parse reported a phantom process, and a
REM  looser PowerShell match treated any command merely NAMING the script (a
REM  linter or test run) as a running service.
REM ============================================================================
setlocal
chcp 65001 > nul
cd /d "%~dp0HL_Monarch"

set "LOGFILE=data\collector_service.jsonl"
set "PIDFILE=data\collector_service.pid"

if /I "%~1"=="status" goto :status
if /I "%~1"=="stop"   goto :stop
if /I "%~1"=="log"    goto :log

REM ---------------------------------------------------------------- start ----
python run_collector_service.py --status 2>nul | findstr /C:"\"running\": true" >nul
if not errorlevel 1 (
    echo [!] Service is already running.
    echo     Stop it first:  launch_service_background.bat stop
    goto :end
)

if not exist "data" mkdir "data"

echo Launching HL_Monarch collector service in the background...

REM pythonw.exe runs with no console window at all. Resolve it from the
REM interpreter actually in use rather than from PATH: `where pythonw.exe` finds
REM Windows Store App Execution Alias stubs first, which fail with
REM "Access is denied" instead of running anything.
set "PYW="
for /f "delims=" %%I in ('python -c "import sys,os;p=os.path.join(os.path.dirname(sys.executable),'pythonw.exe');print(p if os.path.exists(p) else '')" 2^>nul') do set "PYW=%%I"

if defined PYW (
    start "" /B "%PYW%" run_collector_service.py --quiet
) else (
    REM No pythonw beside the interpreter: fall back to a minimised console.
    start "HL_Monarch Collector Service" /MIN python.exe run_collector_service.py --quiet
)

REM Confirm from the lockfile rather than assuming the spawn worked.
powershell -NoProfile -Command "Start-Sleep -Seconds 4" >nul
python run_collector_service.py --status 2>nul | findstr /C:"\"running\": true" >nul
if errorlevel 1 (
    echo   [!] Service did not start.
    echo       Run run_monarch_collector_service.bat to see the error.
) else (
    echo   Confirmed running.
)

echo.
echo   This window can be closed safely; the service keeps running.
echo   Structured log : HL_Monarch\%LOGFILE%
echo   Check progress : launch_service_background.bat status
echo   Stop it        : launch_service_background.bat stop
echo.
goto :end

REM --------------------------------------------------------------- status ----
:status
echo === HL_Monarch Collector Service ===
python run_collector_service.py --status
echo.
echo   Coverage needs to approach 99%% before the backtester, squeeze
echo   percentiles and precedence validator mean anything.
goto :end

REM ----------------------------------------------------------------- stop ----
:stop
echo Stopping HL_Monarch collector service...
if not exist "%PIDFILE%" (
    echo   No lockfile - supervisor does not appear to be running.
    goto :stop_orphans
)
set /p SVCPID=<"%PIDFILE%"
echo   terminating supervisor PID %SVCPID%
REM /T also kills the collector child, so stopping the supervisor cannot orphan
REM a collector that would keep writing to the database.
"%SystemRoot%\System32\taskkill.exe" /F /T /PID %SVCPID% >nul 2>&1
del "%PIDFILE%" >nul 2>&1

:stop_orphans
powershell -NoProfile -Command "$o = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py collector*' }); if ($o.Count -eq 0) { Write-Host '  No orphaned collectors.' } else { $o | ForEach-Object { Write-Host ('  terminating orphaned collector PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }"
echo   Stopped.
goto :end

REM ------------------------------------------------------------------ log ----
:log
if not exist "%LOGFILE%" (
    echo No log file yet at HL_Monarch\%LOGFILE%
    echo Start the service first: launch_service_background.bat
    goto :end
)
echo === Last 20 service events ===
powershell -NoProfile -Command "Get-Content '%LOGFILE%' -Tail 20"
goto :end

:end
endlocal
