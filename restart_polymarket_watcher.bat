@echo off
title Polymarket Watcher Restart (Directive 79-2)
cd /d "%~dp0"
:: Round 79 (Directive 79-2): stop the live watcher, then the guarded launcher starts a fresh one running
:: the code on disk (e.g. Round 76 tags). Done inside 60 minutes the stamped series stays continuous.
:: No if-blocks here on purpose (see start_polymarket_watcher.bat for the two cmd traps).
python -m cross_market.ingestors.polymarket_fetcher --stop
call "%~dp0start_polymarket_watcher.bat"
python -m cross_market.ingestors.polymarket_fetcher --status
echo Verify above: a NEW pid holds the lock; after the next poll the tags line should read carries tags.
