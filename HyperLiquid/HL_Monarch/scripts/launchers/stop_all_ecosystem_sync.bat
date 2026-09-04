@echo off
title Monarch Ecosystem - Stop All Telemetry Synchronizers
chcp 65001 >nul
cd /d "%~dp0..\..\.."
call stop_all_ecosystem_sync.bat
