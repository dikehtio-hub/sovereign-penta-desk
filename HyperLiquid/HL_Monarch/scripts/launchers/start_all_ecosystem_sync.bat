@echo off
title Monarch Ecosystem - Master Tri-Market Telemetry Synchronizer
chcp 65001 >nul
cd /d "%~dp0..\..\.."
call start_all_ecosystem_sync.bat
