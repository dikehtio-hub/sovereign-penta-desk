@echo off
title Cross-Market Arb Exporter Launcher (detached)
cd /d "%~dp0"
:: Round 73 review: this loop refreshes Cross_Market_Arb.md, the Titans sentinel and risk cards, and
:: runs the Item 18 maiden regression by itself once the sentinel is READY - so it must outlive a window.
:: Detached under pythonw, output in cross_market\data\cross_market_exporter.log.
for /f "delims=" %%P in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%P"
if not exist "%PYW%" set "PYW=pythonw"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PYW%' -ArgumentList '-m','cross_market.interfaces.obsidian_exporter','--watch','--interval','15','--risk-stress','0.5','--log-file','cross_market\data\cross_market_exporter.log' -WorkingDirectory '%CD%'"
echo ✓ Cross-Market Arb exporter launched DETACHED, no window. Log: cross_market\data\cross_market_exporter.log
