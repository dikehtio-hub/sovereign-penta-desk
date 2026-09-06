@echo off
cd /d C:\Users\ixis1\Desktop\DEV
set DUR=%1
if "%DUR%"=="" set DUR=420
set BOOKS=%2
if "%BOOKS%"=="" set BOOKS=cross_market\data\clob_books\fomc_2026-09-16
set LOG=cross_market\data\fomc_drill_2026-09-16.log
echo ==== FOMC DRILL record-loop start %DATE% %TIME% duration %DUR% books %BOOKS% >> %LOG%
C:\Users\ixis1\anaconda\python.exe -m cross_market.latency_sniper --record-loop --tokens 5615282760875985231868508008056959876238536896643315063916840237042205273721,63842529068710005716169325380315470359047749786610778647370693404952498013178,88912926533493988427719291698947688154042720958310632316541141466409683822293 --interval 1 --duration %DUR% --books %BOOKS% >> %LOG% 2>&1
echo ==== record-loop exit %ERRORLEVEL% at %DATE% %TIME% >> %LOG%
