@echo off
title Monarch - Apply Aggressive Preset
chcp 65001 >nul
cd /d "%~dp0..\.."

echo ======================================================================
echo ⚔️ Applying Aggressive Risk Preset ($25k Notional, 4 Slots, 18%% Floor)...
echo ======================================================================
python -m config.dynamic_config --preset aggressive
timeout /t 2 >nul 2>&1
