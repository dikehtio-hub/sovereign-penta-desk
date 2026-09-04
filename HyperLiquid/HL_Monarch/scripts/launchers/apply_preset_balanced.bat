@echo off
title Monarch - Apply Balanced Preset
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo ⚖️ Applying Balanced Risk Preset ($10k Notional, 2 Slots, 25%% Floor)...
echo ======================================================================
python -m config.dynamic_config --preset balanced
timeout /t 2 >nul
