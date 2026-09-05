@echo off
title Monarch - Apply Conservative Preset
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo 🛡️ Applying Conservative Risk Preset ($5k Notional, 1 Slot, 35%% Floor)...
echo ======================================================================
python -m config.dynamic_config --preset conservative
timeout /t 2 >nul 2>&1
