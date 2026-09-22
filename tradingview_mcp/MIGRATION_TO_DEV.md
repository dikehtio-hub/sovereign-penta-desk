# MIGRATION_TO_DEV.md - moving tradingview_mcp into DEV after the FOMC drill

> ## EXECUTED 2026-09-20 ~19:44 EDT (Claude Code) — Model A (vendored) — DO NOT RE-RUN SECTION 3
>
> The project now lives at `C:\Users\ixis1\Desktop\DEV\tradingview_mcp`. Section 3's commands
> reference the old Desktop path and would fail or do damage if run again. Sections 0, 4, 5 and 6
> are kept as the record of what was done; Sections 0 and 5.0 describe the PRE-move state.
>
> **What was done:** all 5 Section 1 gates passed (drill over; freeze lifted by 6 post-drill commits
> `c0ff089`..`ccdfa5c`; DEV re-measured at 37 dirty; port 9222 free; Chrome closed). Nested `.git`
> dropped. venv deleted and rebuilt at the new path. Both MCP registrations repointed. DEV
> `.gitignore` block added (Section 4.3, with the date corrected to 09-20).
>
> **Three corrections to this plan, found while executing it:**
>
> 1. **Section 1's gate list was incomplete.** It was written before the user-scope registration of
>    2026-09-14 23:48 EDT, so it never anticipated that *running MCP servers* hold the venv open.
>    16 of them (8 stub+interpreter pairs, leaked one pair per session launch since 09-19 13:14) had
>    to be stopped before Windows would release the directory. Any future move must stop them first.
> 2. **Section 3.3's stated reason is wrong, its conclusion is right.** `pyvenv.cfg` does NOT embed
>    the project path — its `home` is `C:\Users\ixis1\anaconda`, so it is position-independent. The
>    paths that actually embed are the `activate` scripts, the `Scripts\*.exe` console wrappers, and
>    the editable install's `MAPPING` in `__editable___tradingview_mcp_0_1_0_finder.py`. Rebuilding
>    is still correct, just not for the reason given. The rebuild was done from a `pip freeze` of the
>    working venv rather than from `requirements.txt`, so versions were reproduced, not re-resolved.
> 3. **Section 0's deviation count is stale.** It records 63 insertions / 15 deletions; the actual
>    diff at move time was **79 / 15**. The deviations grew after 09-14. They were uncommitted, so
>    dropping `.git` would have made them indistinguishable from upstream code — they are now saved
>    as `local_deviations_vs_upstream_60f12fd.patch` (7,631 bytes) beside this file.
>
> **Verified after the move:** 16 tools build; `import tradingview_mcp` from a foreign cwd resolves to
> the DEV path; `tests/test_smoke.py` 3 passed; `mcp` 1.30.0 (the `<2` pin held); the Pine example
> decodes to 6247 chars with 🌙 intact (the cp1252 fix survived); `git add -n` stages 61 source files
> and zero secrets, venv or browser-profile files.
>
> **Still owed (Section 6.2/6.3, needs a browser — operator):** launch the dedicated Chrome and run
> `mount_pine.py`. The TradingView login is in `C:\Users\ixis1\.tradingview_mcp_chrome` (HOME) and was
> never moved, so no re-login is expected. **Claude Code must be restarted** before the `tv_*` tools
> reappear. Not committed — the operator did not ask for a commit.

**Written**: 2026-09-14 (Mon) by Claude Code, during the pre-drill code freeze.
**Do not execute before**: Wednesday 2026-09-16, after the 14:00 EDT FOMC drill concludes
and the operator lifts the DEV freeze (DEV locked at `fabeb97` + 51 dirty until then).

This project was deliberately built OUTSIDE `C:\Users\ixis1\Desktop\DEV` so nothing in the
frozen repo changed. This file is the checklist for bringing it in.

---

## 0. What exists today (standalone state)

| Item | Location | Notes |
|---|---|---|
| Project root | `C:\Users\ixis1\Desktop\tradingview_mcp` | clone of upstream `60f12fd` ("Give the chart real focus before driving it") |
| Virtualenv | `C:\Users\ixis1\Desktop\tradingview_mcp\venv` | base interpreter `C:\Users\ixis1\anaconda\python.exe` (3.13.5); nothing installed into Anaconda base |
| Config | `C:\Users\ixis1\Desktop\tradingview_mcp\.env` | copied from `.env.example`; `TV_MCP_CDP_PORT=9222` |
| Chrome profile | `C:\Users\ixis1\.tradingview_mcp_chrome` | HOME dir, not the project. Created on first launcher run. Holds the TradingView login. |
| Tool-call log | `C:\Users\ixis1\.tradingview_mcp_chrome\tool_calls.jsonl` | also in HOME, per `.env` default |
| CDP port | 9222 | audited free on 2026-09-14; dedicated Chrome 152.0.7977.84 listening since the operator's launch that evening |
| MCP registration (canonical) | `~/.claude.json`, user scope | added by the operator 2026-09-14 23:48 EDT; `claude mcp get tradingview` -> "User config", "Connected" from any cwd; holds the absolute Desktop venv path, must change at migration (section 5.2) |
| MCP registration (duplicate) | `C:\Users\ixis1\Desktop\tradingview_mcp\.mcp.json` | project scope, written by `claude mcp add --scope project` on 2026-09-14, same server name; inside this directory project scope shadows user scope and still shows "pending approval"; keep for option (i) in 5.1 or delete |
| Local approval | `C:\Users\ixis1\Desktop\tradingview_mcp\.claude\settings.local.json` | `enabledMcpjsonServers: ["tradingview"]`, gitignored; `claude mcp list` still reports "pending approval" until an interactive `claude` session opened in this directory accepts the server once |
| Editable install | venv site-packages -> this source tree | `pip install -e .` so `-m tradingview_mcp.server` imports from any cwd (measured: import failed from `%TEMP%` before, works after) |

**Local deviations from upstream (5 files, all intentional, all CRLF like the working copy; `git diff --stat` = 63 insertions, 15 deletions):**

1. `requirements.txt`: `mcp>=1.0.0` -> `mcp>=1.0.0,<2`. Unpinned, pip resolved `mcp` 2.2.0, which
   renamed `FastMCP` to `MCPServer` and removed `mcp.server.fastmcp`; `server.py` imports the old
   path and fails at import. Venv has `mcp` 1.30.0. Keep this pin until upstream migrates.
2. `.gitignore`: appended `venv/` (upstream does not ignore it).
3. `mount_pine.py:69`: `pine.read_text()` -> `pine.read_text(encoding="utf-8")`. This machine's
   locale encoding is cp1252 (`utf8_mode` 0, `PYTHONUTF8` unset), so the default decode turned the
   🌙 in the indicator title into 4 garbage characters (6275 chars vs 6247 correct). The garbled
   source still compile-checked as valid (a garbled string literal is legal Pine) and the legend
   check still passes ("Moon Dev" survives), so the only visible symptom would have been a
   corrupted title on the chart. The MCP server path is unaffected (code arrives over JSON).
4. `tradingview_mcp/tools/chart.py` `_current_chart_state`: added DOM fallbacks. On the live chart
   `document.title` is just `AAPL` (no " — " separator) and the URL carries no query, so
   `tv_get_current_symbol` returned `symbol=""`, `interval=""` with status ok. Now falls back to the
   header symbol button (`#header-toolbar-symbol-search` -> `AAPL`) and the main-series legend row
   (`intervalTitle` -> `1D`, `exchangeTitle` -> `NASDAQ`, `mainTitle` -> `Apple Inc`), and returns
   `exchange` / `description` as extra keys. The header interval bar is deliberately last: its
   `aria-checked` button said 15m while the legend and the daily candles said 1D.
   Addendum 2026-09-15 00:10 EDT: the legend row also has a compact display mode (`BATS:AAPL · 15`,
   no interval / exchange spans), seen after someone changed the chart at ~23:48. The row's full
   title text is now parsed (interval token and `EXCHANGE:SYMBOL`) before the header fallback;
   regexes unit-checked on `BATS:AAPL · 15`, `A Apple Inc 1D NASDAQ`, `CME_MINI:ES1! · 4h`,
   `BINANCE:1000PEPEUSDT.P 1W`, `NQ1! 60`. Live result: AAPL / 15 / BATS.
5. `tradingview_mcp/tools/indicators.py` `_read_legend`: `[data-name="legend-source-item"]` matches
   0 nodes on current TradingView (tv_selectors.py itself marks it dead since 2026-08-29), so
   `tv_list_indicators` and `tv_read_indicator_value` returned an empty legend against a chart
   showing Vol + MD RIBBON. Now reads the hashed-class legend (`[class*="sources-"] > [class*="study-"]`,
   values from `valueValue`), keeps the old selector as fallback, and adds an `args` list (the
   legend's input lines). NOT fixed, same dead selector but only in post-action verification:
   `tv_add_indicator` (L178), `tv_remove_indicator` (L220), `tv_remove_all_indicators` (L244).
   `pine.py` `_legend_titles` already carries its own V2 fallback.

Also added, not upstream files: `.mcp.json` (project-scope registration, absolute Desktop path),
`.claude/settings.local.json` (gitignored), the editable install (`tradingview_mcp.egg-info/`, ignored).

**Verified on 2026-09-14 (standalone):**
- `build_server()` constructs and lists all 16 `tv_*` tools.
- `tests/test_smoke.py`: 3 passed (pytest + pytest-asyncio installed into the venv; they are the
  pyproject `dev` extras, not in requirements.txt).
- `tv_validate_pine_script` on `examples/moon_dev_rainbow_ribbon_10_50.pine`, correctly decoded
  UTF-8 source (6247 chars) -> `valid=True`, 0 errors, 416 ms, no browser.
- Browser stages, run 2026-09-14 23:30 EDT against the operator's logged-in Chrome 152.0.7977.84 on 9222:
  `[x]` compile-check valid=True 422 ms `[x]` Monaco write ok (clear+paste, 121 lines, 4.7 s)
  `[x]` add to chart 12.3 s, no compile errors `[x]` editor panel closed `[x]` legend `['Vol', 'MD RIBBON']`
  `[x]` `moon_dev_chart.png` written, 131,503 bytes (AAPL 1D NASDAQ, five ribbon lines and the Moon Dev
  table visible, 🌙 rendered correctly) `[x]` `MOUNTED: True`, exit 0.
- MCP protocol health check (a stdio client spawning the server exactly as Claude Code does, once from the
  project cwd and once from `%TEMP%`): handshake 1.6-2.6 s, 16 tools discovered, none missing, none extra.
  Live calls after deviations 4-5: `tv_get_current_symbol` -> AAPL / 1D / NASDAQ / Apple Inc;
  `tv_list_indicators` -> Vol + MD RIBBON with args and values; `tv_read_indicator_value("RIBBON")` -> 12
  values; `("Vol")` -> 2 values; `("RSI")` -> clean "not on chart" error carrying the legend.
- `claude mcp get tradingview`: scope "Project config (shared via .mcp.json)", status "Pending approval"
  until an interactive session in this directory accepts it (operator action, see section 5.1).
- 2026-09-15 04:05Z and 04:08Z, re-proof from the DEV-rooted Claude Code session through the stdio
  client (that session has no native tv_* tools; it predates the registration): 16 tools; state
  AAPL / 15 / BATS after someone changed the chart at ~23:48 EDT from a DEV working directory,
  which left `DEV\moon_dev_chart.png` (80,404 bytes, untracked, NOT ignored by DEV's gitignore).
  On that screenshot the bars and the OHLC readout (O 334.79, C 333.08) were identical to the
  earlier 1D view while the UI said 15, so the interval claim deserves a human look at the window.

---

## 1. Pre-move gate (all must be true)

- [ ] It is after 14:00 EDT Wed 2026-09-16 and the drill is over.
- [ ] Operator has explicitly lifted the DEV code freeze (HOMEWORK.md / AGENTS.md says so).
- [ ] DEV working tree state has been re-measured (`git -C C:\Users\ixis1\Desktop\DEV status --short | wc -l`) and the operator is fine with adding to it. Consider committing or stashing the 51 pre-existing dirty files first so the migration is its own commit.
- [ ] Port 9222 re-audited: `netstat -ano | findstr :9222` returns nothing, OR only the dedicated Chrome you launched.
- [ ] The dedicated Chrome window is CLOSED (so no process holds files under the project while you move it - the profile is in HOME so this is just hygiene).

---

## 2. Decide the tracking model (pick one, record the choice in AGENTS.md)

DEV has two precedents for sub-projects:

| Model | Precedent in DEV | How DEV treats it |
|---|---|---|
| **A. Vendored (recommended)** | `MoonDev_Quant_Strats` (26 tracked files, no nested `.git`) | plain files committed to DEV master |
| B. Nested repo | `quant_trading_lab` (own `.git`, listed in DEV `.gitignore` line 97) | DEV ignores the whole dir; history lives in the nested repo |

The user's stated intent is "alongside MoonDev_Quant_Strats", so **A is the default**.
Upstream has only 3 commits; nothing of value is lost by dropping the nested history.
Record the upstream commit hash (`60f12fd`) in the vendored copy's `AGENTS.md` / this file so it can be diffed against upstream later.

---

## 3. Move steps (Model A, vendored)

Run in PowerShell. Every path is absolute on purpose.

```powershell
# 3.1 Move the directory (Desktop -> DEV). Same drive, so this is a rename, not a copy.
Move-Item -LiteralPath 'C:\Users\ixis1\Desktop\tradingview_mcp' -Destination 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp'

# 3.2 Drop the nested git metadata (Model A only). Keep the .gitattributes / .gitignore files.
Remove-Item -Recurse -Force 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\.git'

# 3.3 Delete the OLD venv. Its activate scripts and pyvenv.cfg embed the Desktop path; do not carry it.
Remove-Item -Recurse -Force 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv'

# 3.4 Recreate the venv at the new path from the same base interpreter, then reinstall.
& 'C:\Users\ixis1\anaconda\python.exe' -m venv 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv'
& 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv\Scripts\python.exe' -m pip install --upgrade pip
& 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv\Scripts\python.exe' -m pip install -r 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\requirements.txt'

# 3.4a Editable install, so `-m tradingview_mcp.server` imports from ANY cwd. Required: Claude Code's
#      .mcp.json entry has no cwd key, and without this the import fails from anywhere but the project root
#      (measured 2026-09-14). Creates tradingview_mcp.egg-info/ next to the package (ignored by *.egg-info/).
& 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv\Scripts\python.exe' -m pip install -e 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp'

# 3.4b (optional) test deps, so tests\test_smoke.py runs at the new path
& 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv\Scripts\python.exe' -m pip install "pytest>=8.0" "pytest-asyncio>=0.23"

# 3.5 Confirm the mcp pin held (must print 1.x, not 2.x).
& 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv\Scripts\python.exe' -c "import importlib.metadata as m; print(m.version('mcp'))"
```

`.env` moves with the directory (3.1). Nothing in it is path-dependent: the profile dir is
`~/.tradingview_mcp_chrome`, which resolves to HOME regardless of where the project lives.
**The Chrome profile and the TradingView login do not move and do not need to be redone.**

For Model B instead: skip 3.2, and add `tradingview_mcp/` to DEV `.gitignore` next to the
`quant_trading_lab/` block (line ~90-97) with a comment that it has its own repo.

---

## 4. gitignore rules

### 4.1 Already covered by DEV's root `.gitignore` (verified 2026-09-14, read-only)

| Pattern | DEV line | Covers |
|---|---|---|
| `.env` / `*.env` (with `!.env.example`) | 9-12 | `tradingview_mcp/.env` |
| `venv/` | 63 | `tradingview_mcp/venv/` |
| `*.jsonl` | 108 | any tool-call log that lands inside the tree |

### 4.2 The project's own `.gitignore` still applies after vendoring

Git honors nested `.gitignore` files, so `tradingview_mcp/.gitignore` keeps ignoring
`.env`, `__pycache__/`, `.tradingview_mcp_chrome/`, `*.jsonl`, `moon_dev_chart.png`,
`_debug_state.png`, and (added locally) `venv/`. Leave it in place.

### 4.3 Add to DEV root `.gitignore` anyway (belt and braces)

Append this block. The profile dir defaults to HOME, but if anyone ever sets
`TV_MCP_CHROME_PROFILE_DIR` to a project-relative path, a logged-in browser profile must
never reach a commit.

```gitignore
# tradingview_mcp (vendored from moondevonyt/Trading-View-MCP-for-AI-by-Moon-Dev @ 60f12fd, migrated 2026-09-16)
# Secrets, local venv, and the dedicated Chrome profile (a logged-in browser session) must never be committed.
tradingview_mcp/.env
tradingview_mcp/venv/
tradingview_mcp/.tradingview_mcp_chrome/
.tradingview_mcp_chrome/
tradingview_mcp/moon_dev_chart.png
tradingview_mcp/_debug_state.png
tradingview_mcp/.claude/settings.local.json
```

`tradingview_mcp/.mcp.json` is meant to be committed (it is the shared registration), but it holds an
absolute path, so fix the path (section 5.1) before the migration commit.

Then verify nothing sensitive is staged:

```powershell
git -C 'C:\Users\ixis1\Desktop\DEV' add -n tradingview_mcp | Select-String -Pattern '\.env$|venv|tradingview_mcp_chrome|\.jsonl'
# expected: no output
```

---

## 5. MCP config path updates

The server is stdio (`FastMCP.run()` default), so the client just needs the interpreter,
the module, and the working directory. Use the **venv interpreter by absolute path**: bare
`python` on this machine resolves to Anaconda base, which does not have `mcp` installed.

### 5.0 What exists now (2026-09-15 00:10 EDT): a USER-scope registration is canonical

The operator added the server at user scope on 2026-09-14 23:48 EDT (`~/.claude.json`);
`claude mcp get tradingview` reports "User config (available in all your projects)", "Connected",
from both the standalone directory and DEV. It carries the absolute Desktop venv path. At
migration, update it (section 5.2) with:

```powershell
claude mcp remove --scope user tradingview
claude mcp add --scope user tradingview -- 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp\venv\Scripts\python.exe' -m tradingview_mcp.server
```

and restart any open Claude Code session (MCP servers attach at session start; a session opened
before the registration does not see the tools until restarted). The project-scope `.mcp.json`
below is now a same-name duplicate: inside this directory project scope shadows user scope and
still shows "pending approval". Either delete it (`claude mcp remove --scope project tradingview`
run inside the directory, plus `.claude\settings.local.json`) or keep it for option (i).

### 5.1 Claude Code, project scope (optional alternative)

The registration already exists: `tradingview_mcp\.mcp.json`, written on 2026-09-14 by
`claude mcp add --scope project` (the CLI writes to its cwd, which is why it was run inside the
standalone directory and not DEV). Current content, with the pre-migration path:

```json
{
  "mcpServers": {
    "tradingview": {
      "type": "stdio",
      "command": "C:\\Users\\ixis1\\Desktop\\tradingview_mcp\\venv\\Scripts\\python.exe",
      "args": ["-m", "tradingview_mcp.server"],
      "env": {}
    }
  }
}
```

At migration, pick where Claude Code should see the server and edit `command` to the DEV path
`C:\\Users\\ixis1\\Desktop\\DEV\\tradingview_mcp\\venv\\Scripts\\python.exe`:

- (i) leave the file inside `DEV\tradingview_mcp` and open Claude Code there when using the tool; or
- (ii) merge the same block into a DEV-root `.mcp.json` (absent as of 2026-09-14; merge, never
  overwrite, if one appears) so sessions opened in DEV see it. The editable install (3.4a) is what
  makes (ii) work: the docs say a stdio server's working directory is the config's location, there is
  no documented `cwd` key, and without the editable install the import fails from any cwd but the
  package root.

Approval, per the Claude Code MCP docs and confirmed on 2026-09-14: `.mcp.json` servers need
approval, recorded through `enabledMcpjsonServers` in a settings file. The standalone directory
already has `.claude\settings.local.json` with `{"enabledMcpjsonServers": ["tradingview"]}`, but
that only takes effect after the workspace trust dialog has been accepted once, so `claude mcp list`
keeps saying "Pending approval" until an interactive `claude` session is opened in that directory
one time. Operator step, after the move: open `claude` inside the directory that holds `.mcp.json`,
accept the trust dialog, then `claude mcp list` should show the server connected. If the settings
file was not carried over, re-create it (gitignored) or accept the server in the dialog.

### 5.2 If it was registered at user scope during the standalone phase

`~/.claude.json` already has an `mcpServers` block for other servers. If a `tradingview`
entry was added there pointing at `C:\Users\ixis1\Desktop\tradingview_mcp\...`, it becomes a
dead path after the move. Either:

```powershell
claude mcp remove --scope user tradingview
```

and re-add at project scope (5.1), or edit the `command` / `cwd` strings in place.

### 5.3 Claude Desktop (Windows), if used

`%APPDATA%\Claude\claude_desktop_config.json`, same JSON shape as 5.1. Restart Claude Desktop.

---

## 6. Post-move verification (repeat the standalone checks at the new path)

```powershell
Set-Location 'C:\Users\ixis1\Desktop\DEV\tradingview_mcp'

# 6.1 Server builds, 16 tools
.\venv\Scripts\python.exe -c "import asyncio; from tradingview_mcp.server import build_server; print(len(asyncio.run(build_server().list_tools())), 'tools')"

# 6.2 Launch (or reuse) the dedicated Chrome; login should already persist from the HOME profile
.\venv\Scripts\python.exe -m tradingview_mcp.chrome_launcher

# 6.3 One-shot: headless compile -> Monaco write -> add to chart -> legend -> screenshot
.\venv\Scripts\python.exe mount_pine.py examples\moon_dev_rainbow_ribbon_10_50.pine
# expect: valid=True, status ok on write, no compile errors, legend contains "MD RIBBON", "MOUNTED: True", moon_dev_chart.png written

# 6.4 Ask Claude Code (from DEV): "what tradingview tools do you have?"  -> 16 tv_* tools
```

---

## 7. DEV bookkeeping after the move (per standing operator rules)

- [ ] `DEV\AGENTS.md`: add a round entry (source repo + hash, tracking model chosen, mcp<2 pin, verification results).
- [ ] `DEV\COMMANDS.txt`: add the launcher, mount_pine one-shot, and the MCP registration command (bots/agents inventory rule).
- [ ] `DEV\HOMEWORK.md`: remove the migration item; add "log into TradingView in the dedicated Chrome" only if the profile was lost.
- [ ] Antigravity cross-check prompt for the migration commit (standing rule).
- [ ] Commit: `feat(tradingview_mcp): vendor MoonDev TradingView MCP @ 60f12fd; pin mcp<2` (single commit, separate from the pre-existing dirty set).
- [ ] Delete this file's Section 3 old-path references once the move is done, or leave as history. Keep Sections 4-6.

---

## 8. Rollback

If anything in Section 3 fails midway: `Move-Item` back to `C:\Users\ixis1\Desktop\tradingview_mcp`,
recreate the venv there with the 3.4 commands using the Desktop path, and `git -C DEV checkout -- .gitignore`
if 4.3 was already applied. The Chrome profile in HOME is untouched by every step above.
