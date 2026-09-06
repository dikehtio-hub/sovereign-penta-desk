@echo off
cd /d C:\Users\ixis1\Desktop\DEV
set LOG=cross_market\data\maiden_protocol_2026-09-06.log
echo ==== RESTART at %DATE% %TIME% >> %LOG%
call restart_polymarket_watcher.bat >> %LOG% 2>&1
echo ==== restart exit %ERRORLEVEL% >> %LOG%
