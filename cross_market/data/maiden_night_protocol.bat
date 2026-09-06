@echo off
cd /d C:\Users\ixis1\Desktop\DEV
set LOG=cross_market\data\maiden_protocol_2026-09-06.log
echo ==== PROTOCOL at %DATE% %TIME% >> %LOG%
C:\Users\ixis1\anaconda\python.exe -m cross_market.maiden_protocol >> %LOG% 2>&1
echo ==== protocol exit %ERRORLEVEL% >> %LOG%
C:\Users\ixis1\anaconda\python.exe -m cross_market.ingestors.polymarket_fetcher --status >> %LOG% 2>&1
