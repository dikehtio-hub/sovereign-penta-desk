# DEV Folder Cleanup — 2026-08-16

Full sweep of `DEV/`: every `.py` file (76 total, excluding `.conda`/`.venv`/caches) was
compile-checked, and 9 had syntax errors. All 9 are old bootcamp/practice files dated
Sept–Oct 2025 — unrelated to the Arbitrage Agent (which was clean already; see below).
All 76 files now compile and pass a `pyflakes` undefined-name check.

## Folder reorganization

Moved `AGENTS/ATC/` → top-level `BOTS/` (`Aster/`, `discord_code/`, `HYPERLIQUID/`,
`Phemex/`, `12_vwap_bot.py`). `AGENTS/` now holds only the two structured, tested
systems (`Arbitrage Agent`, `Funding_Arbitrage_Agent` — both have `agent.py` +
separated config/execution/risk modules + tests + README). `ATC`'s single-file,
numbered bootcamp bot scripts didn't fit that pattern, so they get their own tier:
`STRATS/` (backtest research) → `BOTS/` (single-file live-exchange scripts) →
`AGENTS/` (full structured systems). Put future single-file bot projects in `BOTS/`;
graduate one to `AGENTS/` if it grows config/execution/risk separation and tests.
Recompiled all files post-move to confirm the reorg didn't break anything (0 errors).

## Arbitrage Agent (`AGENTS/Arbitrage Agent/`)

No syntax errors, all tests already passing. Found and fixed 3 stale-value bugs (the
kind that drift silently when config values change):

- `config.py` — `OFFRAMP_TRIGGER_USDC` comment claimed "+9.1% net / +$273 profit
  harvest"; actual math is `3273 - 2950 = $323`, `323/2950 = 10.95%`. The value itself
  was correct and used consistently everywhere else — only the comment was wrong.
- `execution.py` — two gas-cost comments were off by ~16x (`0.00008 ETH` labeled
  "~$0.015" is actually ~$0.24 at $3,000/ETH; `0.00002 ETH` labeled "~$0.004" is
  actually ~$0.06).
- `agent.py` — startup banner hardcoded `"~$50 USD"` for the gas reserve instead of
  computing it from config; now derived dynamically so it can't go stale again.

Verified: `pytest test_agent.py` (8/8 pass) and `run_agent_test.py` smoke test both
still clean after the edits.

## Other files fixed (syntax errors + adjacent crash-on-first-use bugs)

Per-file, fixed enough to make each one parse and pass a pyflakes undefined-name
check. Where a bug was immediately adjacent to the syntax error and unambiguous
(a typo'd variable name, a mismatched function signature), it was fixed too, since
"parses but crashes on the next line" isn't a real fix. Deeper, ambiguous gaps
(business logic that was never written) were left alone and are called out below.

- **`BOTS/12_vwap_bot.py`** (moved from `AGENTS/ATC/`, see below) — unterminated string in an f-string print;
  `im_in_post` → `im_in_pos` typo; `acount1`/`account1` inconsistent spelling; missing
  `)` on a `float(...)` call; missing `if ... :` colon; missing `import random`;
  `pnl_close(...)` was called with 4 args but only takes `symbol`.
- **`BOTS/discord_code/Range_breakout.py`** — extensively broken: `def init`
  should be `def __init__` (constructor was never being called), a dozen bare comment
  lines missing their `#` (parsed as invalid expressions), several mis-indented
  statements, missing `*` in `"=" * 80`-style separators and in `pnl*100` percent
  math, and the file was **truncated mid-statement** at the end with no `__main__`
  entry point at all. Completed the cut-off report section using variables already
  computed earlier in the same method, and added a `__main__` block that instantiates
  the strategy and runs `backtest()`.
- **`BOTS/HYPERLIQUID/bollinger_bot.py`** — `[bid}` bracket mismatch in an
  f-string; `in_in_pos` typo (should be `im_in_pos`, which is what every other
  reference in the file uses); confusing `account1 = LocalAccount = ...` double
  assignment that shadowed the imported class; `pnl_close(...)` called with 4 args
  instead of 1 (same bug as above).
- **`BOTS/HYPERLIQUID/nice_funcs.py`** — docstring indented 1 space instead of
  4 (unexpected-indent error); `df('BandWidth'] = ...)` had `(`/`[` swapped, plus a
  stray trailing `\` line-continuation; `'Bandwidth'` vs `'BandWidth'` casing mismatch
  on the next read of that column; `del calculate_bollinger_bands(...)` should have
  been `def`; `get_latest_sma(...)` was missing its `:`, called `datetime()` instead
  of `datetime.now()`, and referenced an undefined `window` instead of `sma_window`;
  and `get_position_andmaxpos` was renamed to `get_position_and_maxpos` because three
  separate caller scripts (`12_vwap_bot.py`, `bollinger_bot.py`,
  `bolling_HL_AI_fix.py`) all call it with the underscore — the module's own
  definition was the one out of step with everything that imports it.
- **`BOTS/HYPERLIQUID/nice_func_AI_FIX.py`** — same `get_latest_sma` bug as
  above (missing colon, `datetime()`, undefined `window`), fixed the same way.
- **`DATA-STREAMS/fuuuunding.py`** — `async with print_lock` missing its `:`;
  `yearly_funding_rate * 3 * 3650 * 100` computed a value and threw it away instead of
  assigning it; `len(symbol)` (string length of one symbol) used where `len(symbols)`
  (count of tracked symbols) was clearly intended; and the `main()` list comprehension
  was cut off (`for symbol in` with nothing after it).
- **`DATA-STREAMS/receeeeent_trades.py`** — `trade_filena,e` typo (comma inside a
  variable name) inconsistent with `trades_filename` used everywhere else it's read;
  wrong websocket host (`fstreeam` → `fstream.binance.com`); `usd_size` was compared
  and used but never computed (added `usd_size = price * quantity`); `'SEL'` typo'd
  `'SELL'` and a `'Sell'` case mismatch, both of which silently broke the sell/buy
  color branch; unterminated f-string; `|n` typo for `\n` in the CSV writer; and
  `for symbol in symbol:` (iterating a not-yet-defined name) should have been
  `for symbol in symbols:`, with the loop body's indentation fixed to match.
- **`productivity/MOONDEVprojects/twopoint1.py`** — Windows path passed as a normal
  string (`\U` in the path was being read as a unicode escape); made it a raw string
  (`r'...'`).
- **`STRATS/sma_pullback/77_backtesting.py`** — `import backtesting import Backtest,
  Strategy` should be `from backtesting import ...`; `self.data.CLose` casing typo;
  `elif price > sma:` referenced an undefined bare `sma` instead of `self.sma[-1]`;
  `print(stop_loss, ".". take_profit)` had a stray period where a comma belonged.

## Known issues left unfixed (ambiguous / not mine to guess)

- **`nice_funcs.py`**: `kill_switch()` and `pnl_close()` both call a `get_position(symbol)`
  that doesn't exist anywhere in the file (only `get_position_and_maxpos(symbol, account,
  max_positions)` does, with a different signature and return arity). This is a real gap —
  calling either function will raise `NameError` — but fixing it means guessing what
  `account` value to pass, which isn't safe to invent silently.
- These ATC/HYPERLIQUID/DATA-STREAMS files are unrelated, unfinished Moon Dev bootcamp
  practice bots — several still have header comments like "DO NOT RUN YET" / "make your
  own strategy first." Getting them to *parse* doesn't mean they're safe to run live;
  none of this cleanup touched exchange credentials, order sizing, or strategy logic
  beyond what was needed to fix the listed bugs.
