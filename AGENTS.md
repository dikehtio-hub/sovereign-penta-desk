# DEV — Sovereign Penta-Desk Trading Ecosystem

Handoff log between Claude Code and Antigravity. Terse by design; git history has
the detail.

## Status

Round 55 complete: WATCHER PID LOCK, WATCHDOG GAVE UP BADGE. The Polymarket
watcher (--watch) takes a single-instance lock keyed to its drop folder
(<folder>/polymarket_watcher.pid, or --pid-file); dead / corrupt / not-a-
watcher pid files are swept, a live watcher makes the newcomer print
already_running and exit 0, orderly exits release (atexit + SIGINT/SIGTERM/
SIGBREAK). cross_market/ingestors/pid_lock.py mirrors the supervisor's
semantics without importing across trees, and its liveness probe never uses
os.kill(pid, 0). The read-only dashboard header shows a red WATCHDOG GAVE UP
badge (relaunch count, the launcher to run) while the Round 54 ceiling is
reached; it clears on service_back. The claim is an exclusive create, so two
starters that both saw a stale file cannot both run. Watcher restarted under
the lock and a second watcher proved to refuse. 8 new tests.

Round 54 complete: WATCHDOG CEILING + ABANDONMENT ALERT, USER-LEVEL WEBHOOK
FALLBACK, LAUNCHER DETACHMENT ROOT CAUSE FIXED. The dashboard watchdog gives
up after SERVICE_WATCHDOG_MAX_RELAUNCHES (3) relaunches that left the service
dead, logs service_abandoned and alerts once (own cooldown key); the service
coming back resets it. WebhookAlerter.user_env reads DISCORD_WEBHOOK_URL /
TELEGRAM_* from os.environ and then from the USER-level registry value, so a
process born before the variable existed still alerts (tests neutralise the
fallback via tests/conftest.py). start_collector.bat launches the supervisor
with PowerShell Start-Process: a caller that captures the launcher's output
returns at once instead of blocking for the service's lifetime. Service and
the multi-tag Polymarket watcher restarted with the variable exported; the
dashboard runs without it and alerts through the registry fallback (proved
from a fresh variable-less process). 2 new tests.

Round 53 complete: DETACHED SUPERVISOR, DASHBOARD WATCHDOG + ALERTS, TAG-FAMILY
DROPS, LIVE WATCHER WIRED. start_collector.bat now launches the supervisor
under pythonw (no console window to close; the logger skips its console
handler when there is none); a fresh supervisor removes stale pid files
before claiming the lock. A read-only dashboard whose service dies logs it,
alerts through WebhookAlerter, and issues the detached relaunch at most once
per 5 min; a status file older than 2h alerts once per episode. The
Polymarket watcher writes polymarket_sports.json and polymarket_macro.json
separately (stamped copies carry the family); start_all_ecosystem_sync.bat
starts it with --tags sports,crypto,fed-rates. The real drop dir now holds
LIVE sports + macro questions (one-shot). 5 new tests.

Round 52 complete: STAMPED POLYMARKET DROPS, MULTI-TAG WATCHER, LEAK FIX, VAULT
TRACKED. `--watch` now writes a stamped copy (`polymarket_<UTC stamp>Z.json`)
beside the canonical file on every price change and prunes copies older than
192h by the stamp in their name, so Item 18 gets its probability series.
`--tags sports,crypto,fed-rates` fetches several Gamma tags in one watcher
(non-sports by verified `tag_slug`, labelled by slug, narrowed by `--keywords`).
The unclosed read-only connection in find_market_probability is closed on the
no-table path. open_dashboard.bat (Antigravity's root launcher) and the five
new whale dossiers are tracked. 5 new tests. No collector code; no restart.

Round 51 complete: MEASURED MACRO SIGNALS & ITEM 18 LEAD-LAG (OFFLINE). The
Titan note's macro block is no longer three hard-coded narratives: Polymarket
probabilities are looked up in whale_trades and in drop files (keyword groups
for a Fed cut and a BTC $100k milestone), HyperLiquid flow is measured from
latest_snapshots/asset_snapshots (OI-weighted funding APR, total OI, 24h OI
change) and every signal carries measured/source; a missing input is
"[NO LIVE MARKET FOUND]" or "[UNMEASURED: reason]", never a number. New
`cross_market/lead_lag.py` (Item 18) finds the lag at which probability shifts
and perp returns line up, from timestamped drops and a READ-ONLY snapshot DB,
and refuses to name one on thin evidence. 11 new tests; master suite is 16
modules. No collector code changed; no restart.

Round 50 complete - MILESTONE. Titan correlator gains `--scan` / `--report` CLI
with a printed summary (its macro block is labelled as the static placeholder
it is); all five desk notes, the hub, the canvas and today's tax note were
regenerated from their exporters and checked against the live book; the
milestone log below records the round series and the day. 1 new test.

Round 49 complete: DASHBOARD LIFECYCLE LOG, 2-HOUR STATUS WINDOW, PERPDEXS
CHECK AT START-UP. The dashboard appends start / stop / frame_error / crash
(with traceback) to `data/dashboard.jsonl`, so the next unexplained death has
a cause. `read_collector_status` trusts the collector's status file for two
hours by default (COLLECTOR_STATUS_MAX_AGE_SECONDS), so a dead collector's
last write cannot keep a NOVEL DEX badge alive. `_check_perp_dexs()` runs on
the collector's start-up (before the loops) and hourly, so the status file
exists from minute 0. hyna's future as a MIXED dex with its own allow-list is
ratified ahead of time. 2 new tests, 1 extended.

Round 48 complete: MIXED-DEX CRYPTO ALLOW-LIST, NOVEL-DEX DASHBOARD BADGE,
CANDIDATE ROTATION LOG. `CRYPTO_DEXES = {main}`, `MIXED_DEXES = {para}`, and a
perp on a mixed dex is TradFi unless its base is on `MIXED_DEX_CRYPTO_ALLOWLIST`
(para: ANSEM, TOTAL2, BTCD, OTHERS) - para:NEWSTOCK is refused the day it lists.
The hourly cycle writes `data/collector_status.json`; the dashboard header shows
an amber `⚠ NOVEL DEX: ...` badge when it names a dex no settings set knows.
`_sample_pass` logs "Candidate set rotated: [prev] -> [new]" on change. 4 new
tests.

Round 47 complete: STRUCTURAL DEX FAIL-CLOSED, HOURLY DRIFT DETECTOR, ONE
CANDIDATE SLOT PER UNDERLYING. `CRYPTO_DEXES = {main, para}`; a perp on any dex
in neither CRYPTO_DEXES nor TRADFI_DEXES is refused as unclassified before
anyone has heard of the dex. The hourly cycle reads perpDexs and WARNS on any
name no settings set knows. `top_funding_candidates` keeps one slot per
`perp_base_symbol` (best-ranked listing wins) and skips bases already held.
hyna joins the deliberately-refused list so the detector stays quiet. 1 new
test, 2 extended.

Round 46 complete: vntl CLASSIFIED TRADFI, hyna DOCUMENTED MIXED, PRESET-AWARE
CONFIG FALLBACK. `TRADFI_DEXES` gains vntl (Ventuals: ANTHROPIC, OPENAI, SPACEX,
MAG7, SOY, WHEAT...), `UNCLASSIFIED_DEXES` shrinks to abcd, hyna is documented
as mixed crypto + GOLD/SILVER and stays unpolled. A corrupt Bot_Config field now
falls back to the ACTIVE PRESET's value (a "conservative" typo lands on $5k, not
the dataclass's $10k); custom/unknown presets and preset-less fields keep the
dataclass/settings default. Safety-flags-fail-armed ratified. 1 new test.

Round 45 complete: PER-FIELD CONFIG FALLBACK FOR EVERY FIELD & UNCLASSIFIED-DEX
FAIL-CLOSED. Every Bot_Config field now parses on its own through
`_config_number` / `_config_int` / `_config_flag`: a corrupt value warns and
takes that field's default while its neighbours load; the whole-file kill-switch
path fires only when the note cannot be read or yields no fields. The two safety
flags fail ARMED on a malformed value (deviation, see findings).
`UNCLASSIFIED_DEXES` (vntl, hyna, abcd) is documented as excluded from
ACTIVE_DEXES and `spot_symbol_candidates` returns [] for a perp on one, with no
runtime switch. 3 new tests.

Round 44 complete: TRADFI_DEXES GAINS mkts AND io; CONFIG CLAMP FLOOR $10k;
MALFORMED FIELDS FALL BACK WITH A WARNING. `TRADFI_DEXES` now covers xyz, km,
cash, flx, mkts (Markets By Kinetiq) and io (EntropyIO pre-IPO equities), all
verified against the live perpDexs payload. `spot_min_day_volume` clamps to
$10k minimum; a Bot_Config field that will not parse falls back to its settings
default with a logged warning instead of failing the whole reload. The
Penta-Desk header was already in place from Round 43. 1 new test, 1 extended.

Round 43 complete: DEX-LEVEL TRADFI QUARANTINE, CANONICAL DUPLICATE GUARD, ONE
VOLUME MAP PER CYCLE, VAULT FIX & HOT-RELOADED THRESHOLDS. `TRADFI_DEXES`
(xyz, km, cash, flx) quarantines whatever lists there; the symbol set covers
para: and main. `canonical_spot_base` makes ANSEM/UANSEM and FARTCOIN/UFART one
underlying for the duplicate guard, and the guard compares perp bases too. The
hourly cycle builds ONE engine whose volume map feeds the sweep, the scan and
the sampler cache. The Trading Terminal's closed-trades table read keys the
harvester never writes (every swept trade showed $0.00 / 0.0h) - fixed and the
vault refreshed. `allow_synthetic_tradfi_basis`, `spot_min_volume_notional_
multiple` and `spot_min_day_volume` are Bot_Config fields now. 6 new tests.

Round 42 complete: PERP-LEVEL TRADFI QUARANTINE, ILLIQUID-LEG SWEEP & 10x ADV
FLOOR. `ALLOW_SYNTHETIC_TRADFI_BASIS = False` with `SYNTHETIC_TRADFI_SYMBOLS`
(the ruled set plus every TradFi base observed live across the cash/flx/km/xyz/
para dexes): a quarantined perp has NO spot candidates - bare, wrapper or alias.
SPX -> UUUSPX ("Unit SPX6900", the memecoin). `BasisHarvester.sweep_illiquid_
exits` closes positions whose spot leg is under the floor or whose perp is
quarantined; hooked into the hourly accrual cycle and `basis --sweep-illiquid`
(refuses while a service collector is alive). The three dead-leg paper positions
were swept with the service stopped. Floor multiple 5x -> 10x ($100k at $10k).
3 new tests.

Round 41 complete: SYNTHETIC EQUITY QUARANTINE, DYNAMIC SPOT FLOOR, ILLIQUID-LEG
REPORTING & UNMAPPED-SPOT TELEMETRY. Tokenised equities (NVDAX, TSLAX, EQ*)
live in `SYNTHETIC_EQUITY_ALIASES` and are ignored while
`ALLOW_SYNTHETIC_EQUITY_BASIS = False`; the spot floor is
`effective_spot_min_volume() = max($50k, 5 x basis_notional_usd)`; the "U"
wrapper now outranks the bare name on ties and in no-volume calls; the paper
book tags positions whose spot leg is under the floor `[ILLIQUID SPOT]` (three
of five live); `python main.py basis --unmapped-spot` lists liquid spot tokens
no perp resolves to (13 live). 4 new tests.

Round 40 complete: SPOT ALIASES, LIQUIDITY-MAXIMISING HEDGE SELECTION & SPOT
DECIMALS FIX. `SPOT_SYMBOL_ALIASES` (hand-kept, verified against live
fullNames) lets `spot_symbol_for` see wrappers that are not "U" + name (UFART,
XMR1, NVDAX...); with `spot_volumes` it picks the MOST LIQUID of several hedges
(para:ANSEM -> UANSEM $928k/day, not ANSEM $1.5k); the spot leg's szDecimals
is now read for the spot symbol itself (every wrapped hedge came back None
before); SPOT_MIN_DAY_VOLUME raised to $50k (32 of 499 tokens). The paper
state's para:ANSEM spot leg was rewritten to UANSEM while the service was
stopped. 3 new tests.

Round 39 complete: SPOT LIQUIDITY GROUNDING & NET-APR CANDIDATE RANKING. A
spot TOKEN is no longer a spot MARKET: `get_spot_universe` keeps only tokens
whose best spot pair turned over >= SPOT_MIN_DAY_VOLUME ($10k) in 24h, read
from spotMetaAndAssetCtxs (46 of 499 tokens live). TSLA/AVGO spot did $0 while
their HIP-3 perps traded tens of millions; COIN/NVDA have a token and no pair.
Sampler candidates with a spread on record rank on net APR. 5 new tests.

Round 38 complete: SPOT-GROUNDED CANDIDATES, SPREAD CEILING & CONCENTRATION
GUARD. Funding candidates for the spread sampler are now decided by
`spot_symbol_for` against the live spot universe (the ':' prefix rule was wrong
both ways) and pre-filtered by the OI/volume floors; the basis spread ceiling
now reaches every costed row in the scan AND the harvester's own gate (para:AVGO
had entered at 35 bps against 25); one paper position per spot symbol
(para:AVGO + xyz:AVGO were both hedged with AVGO); the stalled-service threshold
is derived from REST_POLL_INTERVAL with a 45s floor; Bot_Config.md's preset label
is "custom" to match its 5 slots. 12 new tests.

Round 37 complete: STALLED-SERVICE DETECTION, CANDIDATE SPREAD SAMPLING & REPO
UNTRACKING. The dashboard header has a fifth state - a live service that has
written nothing for 45s shows STALLED in red; order book sampling now runs
held positions > top-5 positive-funding candidates > rotated > core, so a
spread exists before an entry instant; five more runtime/cache/backup files
are untracked and ignored. A latent Round 34 flake (same-second drop filenames
overwriting) is fixed. 5 new tests.

Round 36 complete: READ-ONLY DASHBOARD, POSITION-FIRST SAMPLING & REPO CLEANUP.
`main.py dashboard` no longer starts a collector while a service collector is
alive (Ruling 3.A) - it is a read-only viewer with a live header badge, and
falls back to standalone ingestion only when no service exists. Held basis
positions are sampled first. Runtime `.pid` / `.jsonl` files are untracked and
ignored; Antigravity's Trading Terminal note change is committed (4af4f51).
8 new tests.

Round 35 complete: SPREAD ALIGNMENT, L2 SPREAD SAMPLING & SUPERVISOR HARDENING.
Each spread leg is stored under its OWN signed handicap (Ruling 5.B) and the
cross-market sample now matches 7 of 7 questions; the collector that owns
maintenance samples top-of-book spreads for a bounded coin set into
`orderbook_snapshots` (Ruling 5.C), which joins the fail-closed set; the
supervisor holds the host awake (Ruling 5.A); a live PID counts as the service
only if its command line says "collector", and the dashboard's embedded
collector re-decides ownership every cycle. 21 new tests.

Round 34 complete: INCREMENTAL PERSISTENCE & DATA INGESTION. The pruner now
reduces raw rows to `basis_realised_windows` and `cascade_excursions` BEFORE
deleting them (never pruned; Ruling D's 720h standard is now reachable);
Polymarket sports questions flow into `Sports_Desk/data/polymarket_drops/`
(`Cross_Market_Arb.md` shows 6 matched pairs, 0 clearing); the odds fetcher
polls and drops only on price change; `Canvases/Sovereign_Penta_Cockpit.canvas`
renders all six notes around the tax reserve. **The collector was restarted** -
it had been pruning at 72h for 15 hours after Round 33 said 192 (see findings).
58 new tests.

Round 33 complete: DATA GROUNDING. Retention raised to 192h; the bankroll gate
now FAILS CLOSED on an empty ledger (config placeholder removed, DEPOSIT rows
are the measured balance); Sports_Desk has a real `sports_market.db` for the
first time; Obsidian is a penta-desk cockpit (Sports_Desk.md, Cross_Market_Arb.md,
hub regenerated). 62 new tests.

Round 31 complete: Targets D (exit hysteresis) and E (leverage policy) applied,
and **Item 14 built as a GATED, NON-TRADING module** - see findings. 38 new tests.

Round 29 before it: Item 8, the funding harvester's BUCKET GATE and after-tax
economics (`HL_Monarch/strategies/funding_harvester.py`). The delta-neutral
engine already existed and was left alone; what was missing was the layer
between it and the bankroll. 24 new tests.

Round 27 before it: Item 6, cross-market arbitrage (`cross_market/hybrid_arb.py`,
`matcher.py`, `hud.py`, `--cross-market` on Monarch_Shark). 52 new tests.

Round 26m before it. **The repository now has version history** — it had none
through ~12 rounds of work. Two commits: the baseline (`743496b`, 526 files) and
the reconcile alias (`5e188a5`).

Suites, all offline:

| suite | count |
|---|---|
| master + bridges + cross-market + exporters + ingestors (16 modules, incl. test_titan_correlator, test_lead_lag) | 823 OK |
| HL_Monarch (pytest) | 1083 passed |
| Tax_Reserve_Agent (5 modules) | 546 OK |

Tax config is **New Jersey resident** (Union, 07083): composite 32.37% =
24% federal + 6.37% NJ + 2% buffer, `casual_standard_deduction`.

## What changed

- **`.gitignore` written before the first commit, not after.** `Keys/` holds a
  *screenshot of a HyperLiquid API key*; two live `.env` files; `*.db` carries a
  real tax position. A committed secret survives deletion — it stays in every
  clone — so these never entered history.
- **`quant_trading_lab/` is excluded and that is deliberate.** It has its own
  git repo. Staged from the parent it becomes a bare gitlink: it *looks*
  version-controlled while tracking nothing. It versions itself; the outer repo
  stays out of its way.
- **Three secret-scan hits were checked, not assumed.** The `connection_id` and
  `r`/`s` values in `HyperLiquid/HL_Monarch/execution/wallet_manager.py` are
  EIP-712 test vectors sitting beside `"private_key": "0x" + "11" * 32`. The
  base64 hits in `MoonDev_Quant_Strats/.../chart_benchmark_*.html` are chart
  image data. All false positives.
- **`--reconcile` added as an alias of `--check-sync`** on `monarch_shark`, with
  a test — an argparse alias regresses silently.

## Round 55 findings

- **The lock is keyed to the drop folder, not the machine.** The harm is two
  watchers rewriting ONE folder's canonical files and doubling its stamped
  series; two watchers on two folders are legitimate. So the file lives at
  <folder>/polymarket_watcher.pid (override: --pid-file), inside a data dir
  git already ignores. Semantics copied from the supervisor, not imported
  (HL_Monarch is not a package from the DEV root): dead, corrupt or live-but-
  not-a-watcher pids are swept; a live watcher wins; psutil absent -> assume
  the holder. A newcomer prints `[LOCK] already_running: watcher pid N holds
  ...` and returns 0, as directed.
- **Cleanup is best effort, the sweep is the guarantee.** atexit plus
  SIGINT/SIGTERM/SIGBREAK handlers that release and raise SystemExit(128+n)
  cover Ctrl+C and orderly stops. A closed console window or a task-kill runs
  none of them on Windows; the next watcher's stale sweep handles that.
- **The liveness probe is tested for not killing.** pid_is_alive goes through
  OpenProcess + GetExitCodeProcess on Windows (os.kill(pid, 0) would
  TerminateProcess, the trap the supervisor documented in Round 36); the test
  spawns a sleeper, probes it, and asserts it is still running.
- **The claim is an exclusive create (O_EXCL), not sweep-then-write.** Two
  watchers starting within the same second both find the predecessor's stale
  file and both sweep it; with a plain write both would run. Now exactly one
  creates the file; the loser re-reads it and refuses the live winner (or
  reports -1 while the winner's pid is not readable yet, treated as running;
  a dead pid that reappears is swept on a retry). Observed live while proving
  the lock: my restart launched the "second" watcher before the first had
  claimed, the second claimed first and the FIRST refused - the lock held, my
  script's ordering was the bug. Two restart attempts were also lost to the
  tool: a heredoc-passed kill filter matched the calling shell's own command
  line (self-kill), and escaped newlines inside heredoc strings arrived
  unescaped. Patch scripts now go through files; kill filters match argv
  structure and exclude the caller's ancestors.
- **The badge needs no new state.** _header_status composes service badge,
  watchdog badge (from _service_abandoned / _watchdog_attempts set by the
  Round 54 watchdog) and the NOVEL DEX badge; service_back already resets the
  flag, so the badge clears with the episode.
- **Live**: watcher pid 29420 started 02:07:23Z holds polymarket_watcher.pid; a second watcher exited 0 with already_running in 0.1 s; 1 watcher(s) alive after. The restart adds one extra stamped point to the macro series
  (harmless). Lead-lag stays queued until >24h of stamps: earliest honest run
  after 2026-09-06T02:00Z.

## Round 54 findings

- **Ceiling semantics**: an attempt is a relaunch issued while the service is
  dead; it counts as failed when the service is still dead at the NEXT
  cooldown. So three relaunches get their full 300 s each, and only at the
  fourth due time does the watchdog log service_abandoned (relaunches,
  dead_for_s), alert through alert_service_abandoned (cooldown key
  abandoned:COLLECTOR, so the service-down alert of the same episode cannot
  swallow it) and go quiet. service_back resets the counter; a failed spawn
  consumes an attempt; max_attempts <= 0 restores Round 53's unlimited loop.
- **The Round 53 hang explanation was wrong and is corrected here.** Under a
  non-console stdin `timeout /t 3` exits at once ("Input redirection is not
  supported"), and every launcher already had `>nul`. The real cause was
  measured: `start "" pythonw ...` hands the caller's stdout/stderr pipe to the
  detached child, so any caller that captures the launcher's output waits for
  the child's whole life (12.3 s for a 12 s sleeper; forever for a supervisor).
  PowerShell Start-Process (ShellExecute, no handle inheritance) returned in
  0.4 s. start_collector.bat now uses it. The ratified `2>&1` sweep was applied
  to 13 launchers anyway; it is cosmetic.
- **The webhook was invisible to every running process.** DISCORD_WEBHOOK_URL
  is set at USER level (121 chars) but none of supervisor 31800, collector
  10180, dashboard 48792 or its shim saw it: a process keeps the environment
  it was born with, and all four predate the variable. Whale alerts, service
  alerts and the Round 53 watchdog alerts were all silent. Fix in two layers:
  user_env() falls back to HKCU\Environment (never raises; strips), and this
  round's restart exported the value into the supervisor, collector and
  watcher. The dashboard alive now was opened at 01:36:27Z by the Round 53
  PowerShell launcher call, which had been blocked since 00:59 on the old
  supervisor's inherited pipe and resumed the instant that supervisor was
  killed - a second, independent confirmation of the inheritance cause. It
  has no variable in its environment and alerts through the fallback, which
  a fresh variable-less process proved (discord_url found). tests/conftest.py
  (new) neutralises the fallback for every test so no suite posts to Discord.
- **The watchdog's relaunch path was fired once against the live service**
  (TerminalDashboard.relaunch_service(): cmd with CREATE_NO_WINDOW -> the bat
  -> powershell Start-Process -> pythonw). The spawned supervisor logged
  `already_running` holder_pid 46740 at 01:44:34Z and exited; one supervisor
  remained. So a watchdog firing while a live lock holder exists leaves
  exactly that ERROR line in collector_service.jsonl - it is the expected
  signature, not a fault. The new supervisor also logged its keep_awake hold.
- **Only HL_Monarch reads DISCORD_WEBHOOK_URL / TELEGRAM_***: no other desk
  has a reader, so no other suite can post to Discord from a shell that has
  the user-level variable. The fallback is read at alerter construction:
  rotating the webhook needs a restart of long-lived processes.
- **Lead-lag has no data yet.** One-shot fetcher runs do not stamp (stamping
  is a --watch feature), the drop dir held only the two family files, and no
  watcher process existed, so the ">24h of stamped macro drops" clock had not
  started. The multi-tag watcher was started in its own console this round;
  stamped polymarket_macro_<stamp>Z.json copies accumulate from now
  (every 300 s when prices change). Item 3 stays queued until >24h exist.

## Round 53 findings

- **pythonw is safe for the supervisor**: sys.stdout is None there, so
  build_logger now adds its console handler only when a console exists; the
  jsonl file handler is unchanged and the child's output goes to
  collector.log regardless. The bat resolves pythonw.exe beside whatever
  `python` resolves to (the WindowsApps shim's own pythonw is a different
  interpreter) and falls back to `pythonw` on PATH.
- **The watchdog is a pure method** (`service_watchdog(alive, now, relaunch,
  alerter, log, enabled, cooldown)`) so the whole state machine is tested
  without spawning anything: dead -> log + one alert + relaunch; still dead
  inside the cooldown -> nothing; cooldown passed -> relaunch again; back ->
  log with dead_for_s; standalone dashboards never relaunch. The relaunch
  itself runs the bat with CREATE_NO_WINDOW.
- **Alerts are no-ops until a webhook is configured** (DISCORD_WEBHOOK_URL or
  the Telegram pair); the events still land in dashboard.jsonl.
- **Family split only when several tags are requested**; the single-tag
  path keeps one canonical file and unprefixed stamps, so Round 34-52
  behaviour and tests stand. Empty families write no file until they have
  had content once.
- **Live activation**: the real drop dir now carries live sports (410) and
  macro (300) questions from a one-shot run; the WATCHER itself is an
  operator-session process in start_all_ecosystem_sync.bat (Ruling 50-3).
  Drop files are not tracked (data rules), so the live fetch did not dirty git.
- **The macro block measured 3 of 3 for the first time**: Fed cut PM 93%
  (polymarket_macro.json) against longs paying +7.5% APR with OI -0.6%/24h
  -> DIVERGENT (PM yes; perps not confirming); Bitcoin $100k PM 5% ->
  DIVERGENT (PM no; perps long); flow LONGS PAYING, OI FLAT OR SHRINKING.
  `--scan --resolve` seeded 1,685 Gamma identities into the cache, yet 0
  titans match: no HyperLiquid whale wallet in the DB resolves to a Polymarket
  sharp trader. The cache file was TRACKED (a9c547d) - untracked now so the
  ignore rule applies.
- **The launcher hangs its caller**: `cmd /c start_collector.bat` from a
  non-interactive shell blocked after starting the service (the bat's
  `timeout /t 3` waits on a console that is not there). Harmless when double-
  clicked; the dashboard watchdog runs it with CREATE_NO_WINDOW and does not
  wait. Trailing `timeout` calls in launchers are worth a `>nul 2>&1` or
  removal - noted, not changed.

## Round 52 findings

- **THIRD service death, found by the research pass, not by an alert.** The
  supervisor's last coverage report is 23:44:25 UTC (uptime 4506s); the next
  three never came. At 23:52:59 a dashboard started in STANDALONE mode from the
  new root open_dashboard.bat (dashboard.jsonl: mode standalone, service_pid
  8820 read from a stale pid file) and its embedded collector carried
  ingestion for 44 minutes (newest snapshot 00:36:36 UTC, accruals 52 -> 53,
  cash +$3.51). All three deaths today (20:43, ~22:00 dashboard, 23:44-23:52)
  coincide with someone operating console windows. Restored 00:4x UTC: stale
  pid files removed, standalone dashboard killed, service + read-only
  dashboard relaunched.
- **The service collector's log lines went to DEVNULL.** run_collector_service
  spawned the child with stdout=DEVNULL, so "Basis position opened",
  "Candidate set rotated", the perpDexs warning and every refusal reason
  existed only in a console nobody keeps open. The child now writes
  data/collector.log (append across restarts, rotated once to .1 past
  COLLECTOR_LOG_MAX_BYTES = 20 MB); the supervisor logs a child_log event
  with the path. Tested end to end with a real subprocess.
- **The morning checklist changes**: `tail data/collector.log` is now step 1b.
- cross_market/titan_identities_cache.json (written by --scan) is ignored.

- **The multi-tag watcher works live** (one-shot into a temp folder, NOT the
  real drop dir): 717 questions - sports 417 (MLB 276, NFL 117, NBA 24),
  crypto 203, fed-rates 97 - and among them a real "Will Bitcoin reach
  $100,000 in September?" at 5% and a $76k-$82k daily ladder. Pointing the
  real watcher at these tags would replace the SAMPLE drop the arb note has
  shown since Round 34 with live sports questions; that is Antigravity's call.
- **Gamma `tag_slug` is real**: /events?tag_slug=crypto pages exactly like
  tag_id, and /tags/slug/crypto resolves to id 21. Round 34's "?tag=sports is
  ignored" stands - the parameter name is tag_slug, not tag.
- **The ResourceWarning was mine** (Round 51's find_market_probability opened
  a connection and raised past its close when whale_trades was absent), not
  lead_lag.load_mark_series as the handoff guessed - tracemalloc placed it.
  Now try/finally. The three cross-market modules run clean under
  -W error::ResourceWarning.
- **Non-sports questions carry sport = the tag slug upper-cased** (CRYPTO,
  FED-RATES). The arb matcher never pairs them with a sportsbook fixture; the
  cross-market exporter will LIST them as unmatched if they land in the real
  drop dir. A separate canonical file per tag family would avoid that - not
  built, asked.
- Stamped copies and the exporter: load_questions dedups by token with the
  newest FILE (mtime) winning, and a stamped copy is written right after the
  canonical one with identical content, so "latest" is unaffected.

## Round 51 findings

- **Live macro block today: 1 measured, 2 unmeasured.** HyperLiquid flow across
  BTC/ETH/SOL: longs paying, OI-weighted funding +9.7% APR, OI $5.74B, -0.1%
  over 24h -> "LONGS PAYING, OI FLAT OR SHRINKING". Fed-cut and BTC-$100k
  markets: NO LIVE MARKET FOUND - polymarket_whales.db has no market table
  (whale_trades is empty; the other tables are wallets) and the only local drop
  is the sports sample. The tags are the truth; the old 88% / 64% were not.
- **Item 18 cannot measure anything on today's data**: 7 markets, 0 shifts.
  The Polymarket fetcher overwrites ONE drop file in place, so no probability
  time series exists on disk. The correlator is verified on planted lags
  (+10 and -15 minutes found exactly; noise -> "no measurable lead-lag"; two
  events -> refused). To measure for real, the fetcher must keep timestamped
  drops (polymarket_<stamp>.json, like the odds fetcher) - the exporter already
  dedups by token across files, so that is a fetcher-only change. Ruling asked.
- Co-positioning is now RULES, not narrative: CONVERGENT / DIVERGENT / NEUTRAL /
  UNMEASURED from (PM probability, weighted funding sign, OI change sign);
  strength from probability distance and OI change magnitude. All pinned.
- Safety: both tools read drops and a read-only sqlite URI; neither opens a
  socket or touches the harvester. The bankroll gate and quarantine sets are
  untouched.

## Round 50 closeout (session end, 2026-09-04 ~23:05 UTC)

Antigravity's independent audit, re-derived from basis_paper_state.json and
live spot contexts, not from Claude's summaries:
- Invariant: equity $100,310.41 - starting $100,000.00 - realised $310.41 =
  $0.000000. PASS.
- Every open hedge liquid at the $100k floor: UANSEM $898,154/day (8.98x),
  UXPL $1,291,837/day (12.92x). PASS.

Settled at closeout (no longer carrying):
- R44-Q2 polling mkts/io: NO - ~150 weight/min per dex against the 1,200
  ceiling, and their perps cannot be basis legs.
- R49-Q1 dashboard stop signal: KeyboardInterrupt vs unhandled exception in
  dashboard.jsonl is sufficient on Windows.
- R49-Q2 dual-mode status write: only the collector that OWNS maintenance
  writes collector_status.json (implemented at closeout: `_check_perp_dexs`
  checks `_owns_maintenance()`; an embedded collector a service has joined
  still warns, but leaves the file). Code on disk is newer than the running
  processes; the changed path is not exercised by a service collector or a
  read-only dashboard, so no restart was taken. The next restart picks it up.
- R48(b) sampler 6h refresh: kept as the cold-start fallback (0 weight warm).
- Macro placeholder labelling: RATIFIED.

Queued for Round 51 / next session:
- Measure the Titan note's macro block from real sources: Fed-cut and BTC
  milestone probabilities from Polymarket markets in polymarket_whales.db;
  equity/crypto bias from latest_snapshots funding and OI momentum.
- Item 18, lead-lag event correlator (offline research): event drops from
  Sports_Desk/data/polymarket_drops/ and cross_market/data/ against historical
  asset_snapshots. The titan-resolution module stays the production component.

Overnight policy: HL_Monarch collector + supervisor run 24/7 (keep-awake held);
Sports and Cross-Market desks stay static (their watchers are an operator
session workflow, start_all_ecosystem_sync.bat). Morning checklist: the
Round 50 handoff, section 5.

## Round 50 milestone log

THREE NUMBERING SERIES MEET HERE, and the log says which is which:
- HL_Monarch rounds 1-25 (to 2026-09-02) predate version control - the repo was
  initialised at "Round 26L" (743496b, 526 files, 2026-09-03). Their record is
  `HyperLiquid/HL_Monarch/AGENTS.md` and COMMANDS.txt, not git.
- The Tax Reserve Agent kept its own series (COMMANDS.txt "ROUND 15..36",
  2026-09-01..03: tax gate, HIFO, receipts, fee model validated on chain).
- The DEV series below is the one Antigravity and Claude Code have run since
  the penta-desk vault (Round 33). Rounds 34-50 were all on 2026-09-04.

| DEV round | commit | what it settled |
|---|---|---|
| 26L-31 | 743496b..027a3e1 | quad-desk baseline, sports desk, cross-market arb under asymmetric tax, harvester gated on the basis bucket |
| 33 | 5dbc12b | data grounding: 192h retention, fail-closed bankroll, real sports DB, penta-desk vault |
| 34 | 33111d7 | incremental measurement persistence (measure before prune), Polymarket ingestion, odds poller, cockpit canvas |
| 35 | 18b4989 | signed spread lines, L2 spread sampler, keep-awake, PID-reuse guard |
| 36 | a4b6c51 | read-only dashboard under a live service (one ingester), held positions sampled first |
| 37 | d80c937 | STALLED badge, candidate-first sampling, runtime files untracked |
| 38 | acff08d | spread ceiling on every costed row, one position per spot symbol, stall threshold from poll interval |
| 39 | a4f43b4 | spot universe = liquid pairs (spotMetaAndAssetCtxs), net-APR candidate ranking |
| 40 | 287b603 | alias table, most-liquid hedge, spot decimals fix, floor $50k, para:ANSEM -> UANSEM |
| 41 | 35b98ea | equity quarantine, floor scales with notional, [ILLIQUID SPOT] tags, --unmapped-spot |
| 42 | cfd137b | quarantine on the PERP, illiquid-leg sweep (3 dead legs closed, $60k freed), 10x ADV floor |
| 43 | 7068e40 | dex-level quarantine, canonical duplicate guard, one volume map per cycle, vault closed-trades fix |
| 44 | e7b2e54 | TRADFI_DEXES + mkts/io, config clamp floor, malformed-field fallback |
| 45 | 06c12d9 | per-field config fallback for every field (safety flags fail armed), unclassified dexes fail closed |
| 46 | 9e91818 | vntl TradFi, hyna mixed, abcd unclassified, preset-aware fallback |
| 47 | c84c150 | structural dex fail-closed, hourly drift detector, one candidate slot per underlying |
| 48 | 914c852 | mixed-dex crypto allow-list (para), NOVEL DEX dashboard badge, candidate rotation log |
| 49 | 2146012 | dashboard lifecycle log, 2h status window, perpDexs check at start-up |
| 50 | (this) | Titan CLI, five-desk vault regeneration, milestone log, command index |

THE DAY IN NUMBERS (2026-09-04): 17 rounds (34-50), 19 commits, 15 service
restarts, 2 unexplained dashboard deaths (now logged) and 1 unexplained
collector death (20:43, ~7.5 min lost). Tests 2,3xx -> 2,427. Paper book:
5 positions -> 2 after the sweep; cash $324 -> $60,310; every position's hedge
now verified liquid; invariant equity - starting == realised exact throughout.
UNCHANGED ALL DAY: FADE_STRATEGY_ENABLED False, WHALE_SWEEP_EXECUTION_ENABLED
False, the pre-registration bar, the live tax ledger at $0.00.

## Round 50 findings

- **`detect_macro_signals()` returns fixed narratives.** The Titan note's
  "Macro Co-Positioning" block (Fed cut 88%, BTC $100k 64%, /NQ divergence)
  is hard-coded, not measured. The new CLI report labels it STATIC
  PLACEHOLDERS; the vault note still renders it as before. Ruling asked.
- **The ruling described a different module** (lead-lag over event drops).
  What exists correlates HyperLiquid whale wallets with Polymarket sharp
  traders (EOA -> proxy, conviction score). The CLI was built for the module
  that exists; the lead-lag idea is recorded as an open item.
- Vault regeneration: HL `obsidian --once` rewrites HyperLiquid_Monarch.md,
  Trading_Terminal.md, the hub and the canvas; Sports_Desk.md and
  Cross_Market_Arb.md reported "unchanged" (no new drops since their last
  sync); Quant_Trading_Lab.md and Polymarket_Monarch.md (+41 trader notes)
  rewritten; today's Tax_Reserve note written by `Tax_Reserve_Agent.main
  export` (read-only: it computes the summary and writes the note).

## Round 49 findings

- **The dashboard's render loop swallowed every exception silently** - one
  bad frame slept a second and retried, forever, with nothing written. Now
  the first three frame errors are logged with tracebacks and counted; an
  exception that escapes the loop (Live itself failing) is logged as a crash
  and RE-RAISED, so the process still exits and main.py prints it; a clean
  exit logs stop with the frame-error count. The supervisor still does not
  manage the dashboard (Ruling 49-1: it is an optional viewer).
- **The 2h window is a default, not a hard rule**: read_collector_status(path,
  max_age_s=None) reads regardless of age; the dashboard uses the default.
- **Start-up check runs on the hl-l2 executor** after universe metadata sync
  and before the loops, so the first status file is written ~2s after start.
  If perpDexs fails at start, the hourly cycle retries; the previous file
  (if any) stands until then - and the 2h window expires it if the collector
  never comes back.
- Windows note: the collector's console cannot print the ⚠ glyph (cp1252);
  the dashboard reconfigures stdout to UTF-8 and Rich renders it. The
  rotation and drift log lines are ASCII on purpose.

## Round 48 findings

- **para verified live before inverting the rule**: 33 perps, four crypto
  (TOTAL2, OTHERS, BTCD, ANSEM), the rest equities (SMCI, RDDT, CRWD, MELI,
  SOFI, TTWO...), rates (2Y/10Y/30Y) and pre-IPO (ANTH). The allow-list of four
  is exactly the crypto set. is_mixed_dex_tradfi() is the new test, joined
  into is_synthetic_tradfi; the TradFi switch still opens it like the others.
- **The "dashboard status JSON payload" in the ruling did not exist** - the
  dashboard is a Rich terminal in its own read-only process. Built the channel:
  MarketCollector.write_collector_status(COLLECTOR_STATUS_PATH, {...}) from the
  hourly cycle (unclassified_dexs, dexes_listed, checked_at, pid), and
  ui.components.read_collector_status / novel_dex_badge on the dashboard side,
  composed into the header by TerminalDashboard._header_status. First write is
  one hour after a collector start; the file persists across restarts.
- **Rotation log lives in the collector's _sample_pass** (the sampler's
  function is pure); candidate_rotation_message() is the pure helper. The first
  pass after a start logs "[-] -> [...]" on purpose.
- The Round 47 dedup test needed para:BTC admitted; it now monkeypatches the
  allow-list for the fixture rather than weakening the rule.

## Round 47 findings

- **Fail-closed is now structural, not a list.** `is_unclassified_dex` is
  "dex not in CRYPTO_DEXES and not in TRADFI_DEXES". UNCLASSIFIED_DEXES no
  longer gates anything; it is the "known and deliberately refused" list the
  drift detector consults so abcd and hyna do not warn every hour. hyna was
  added to it for that reason (behaviour unchanged: refused either way).
- **hyna:HYPE no longer resolves** (Round 46 pinned it resolving). Under the
  structural rule a mixed dex that is not in CRYPTO_DEXES is refused whole;
  admitting hyna is a one-line settings edit once someone wants it polled.
- **Candidate dedup counts underlyings, not listings**: n=5 means five
  distinct bases. A held position's base is excluded from candidates outright
  (`exclude=held`) - it already has its spread series and a second listing
  could never be opened. A measured spread can flip which listing wins.
- Drift detector: `unclassified_dex_names(perpDexs names)`; the payload's
  first entry is null (the main dex) and is ignored. Live today: [] (all ten
  dexes are in some set).

## Round 46 findings

- **abcd is not an empty shell.** The ruling called it dormant with an empty
  asset list; the live meta for dex=abcd lists one perp, abcd:USA500. It stays
  in UNCLASSIFIED_DEXES as ruled (refused), and USA500 is in the symbol set, so
  it would be refused twice over if ever polled. Settings comment corrected.
- **Live universes verified before classifying**: vntl 15 perps, all pre-IPO
  equities, sector baskets or commodities; hyna 25 perps, crypto majors and
  memes plus GOLD and SILVER (mixed, exactly para's shape); neither is polled.
- **Preset-aware fallback reads active_preset FIRST**, then resolves each
  field's default from PRESETS[preset] when present, else the dataclass. A
  well-formed line under any preset is honoured as written - the preset only
  supplies fallbacks. Safety flags: malformed -> armed, absent -> the preset's
  False. Spot fields have no preset entry and keep the settings defaults.

## Round 45 findings

- **Safety flags fail armed, not off** (deviation from "fall back to the
  field's default"). `emergency_killswitch: maybe` or `pause_new_entries: 7`
  now reads as True with a warning; an ABSENT flag is still False, because
  absence is not corruption. A malformed safety value must stop trading, never
  enable it. The spot policy flag falls back to its default (False) as ruled.
- **Integers read through float**: `max_concurrent_positions: 3.0` is 3; "2.5"
  would be 2. Clamping is unchanged - `validate_and_clamp` still runs on the
  assembled config against BOUNDS, so per-field parsing and clamping are two
  passes, not one.
- **Unclassified dexes are refused with no switch**: `is_unclassified_dex`
  gates `spot_symbol_candidates` before the TradFi test, so the scan, the
  sampler and the resolver all see [] regardless of `allow_synthetic_tradfi`.
  Admission is a settings edit after a human looks at the dex.
- Ruling 45-3 named `sample_orderbooks()` / `_spot_universe_cache`; the real
  names are `_sample_pass` / `_spot_universe_cached`, and the cold-start path
  is already pinned by `test_the_spot_universe_is_cached_refreshed_and_never_
  guessed` (failed lookup -> zero candidates, retry, stale copy survives).

## Round 44 findings

- **Service found dead at 20:50 UTC.** Last DB write 20:43:49 (8 min after the
  Round 44 restart); supervisor log ends at its 20:35:18 coverage report with
  no shutdown or child-exit event; the dashboard died at the same moment; BOTH
  pid files still held the dead PIDs (so stop_collector.bat was not used - it
  deletes them). Signature of the console windows being closed or an external
  kill. Relaunched 20:51:21 (supervisor 10428, collector 51188). ~7.5 min lost.
  If the windows were closed deliberately, use stop_collector.bat instead; the
  supervisor cannot log or recover from a kill of itself.

- **perpDexs lists ten dexes**: xyz, flx, vntl (Ventuals), hyna (HyENA), km,
  abcd (ABCDEx), cash, para, mkts, io. Six are quarantined by name; para is
  mixed (symbol set); vntl, hyna and abcd are UNCLASSIFIED. None of mkts, io,
  vntl, hyna or abcd is in ACTIVE_DEXES, so nothing from them reaches the
  scan today - the dex quarantine on mkts/io is pre-emptive, and a future
  widening of ACTIVE_DEXES must classify the other three first.
- **Per-field fallback vs whole-reload failure.** Before this round a single
  unparseable number anywhere in Bot_Config raised inside reload(); get_config
  caught it and kept the last cached config silently. The three spot fields
  now fall back individually with a warning; the older fields still take the
  whole-reload path. Worth unifying - ruling asked.

## Round 43 findings

- **The vault had been wrong for every closed trade.** `generate_trading_
  terminal_note` read `realized_pnl` and `hold_duration_hours`; the harvester
  writes `net_pnl` and `hours_held`. No test covered the table. Now one does,
  and the three swept trades render +$4.09 / +$0.15 / -$7.28 with their hours
  and `ILLIQUID_SPOT_LEG` reasons.
- **canonical_spot_base is string logic with known edges.** Aliases map via the
  tables; a "U" prefix is stripped only when 3+ characters remain (UNI, UMA, UP
  stay themselves); USDC canonicalises to SDC, harmless for a quote asset. The
  harvester ALSO compares perp bases (`holds_spot(spot, coin=)`), which needs
  no table: para:AVGO and xyz:AVGO collide on AVGO whatever spot name resolved.
- **One engine per hourly cycle** (`FundingArbitrageEngine(client=rest_client)`)
  now serves the illiquid sweep, the scan (`scanner=`) and refreshes the
  sampler's universe + volume cache, so the 6h/1h divergence is gone and a pair
  that dies is swept within the hour.
- **Hot-reload boundary:** the three new Bot_Config fields take effect live
  through `_dynamic_value()` (a getattr on the cached config; the file is
  stat-ed per call). CODE changes still need a restart - this round restarted
  for the dex quarantine, the canonical guard and the unified volume map.
- Ruling 43-5 recorded in the harvester docstring: returns are right-tail
  heavy (one of five positions paid $322 of $350); report median and top share,
  hold the 25%/20% bar - baseline large-cap funding nets negative after drag.

## Round 42 findings

- **The TradFi perp list is much longer than the ruled set.** Live dexes carry
  cash:AMZN/INTC/KWEB/USA500/WTI, flx:COPPER/PALLADIUM/USA100, km:JPN225/
  USBOND/EUR/TENCENT, para:2Y/10Y/30Y and more. The ruled 21 symbols were kept
  as issued and extended with every TradFi base observed on 2026-09-04 (34
  more), labelled separately in settings. A hand-kept symbol set will drift as
  dexes list; a structural rule (dex metadata or an asset-class field) is the
  next question.
- **Sweep accounting, live:** capital returned $59,990.67 (HOOD $20,000.00,
  para:AVGO $19,995.58, xyz:AVGO $19,995.10), maker exit fees $6.00 (0.01% x
  notional x 2 legs x 3), cash $324.30 -> ~$60,309, realised $314.92 ->
  ~$308.92, invariant equity - starting == realised exact. Antigravity's
  estimate ($9.00 fees, $60,305.98) used a different fee assumption.
- **The sweep is a different KIND of exit.** Ruling 39-1 (spread is a cost, not
  a reason to leave) stands; a dead spot leg means the position was never
  delta-neutral. Fails closed on a missing/empty volume map.
- **Operational trap avoided:** the CLI sweep refuses while `collector.pid`
  names a live collector - the running harvester would overwrite the file on
  its next hourly save. The hourly cycle runs the same sweep from the sampler's
  cached volume map, so a future dead leg closes within the hour.

## Round 41 findings

- **Wrapper-first precedence applies everywhere, not only on volume ties**
  (deviation from the ruling's wording). A call without volumes is an all-ties
  call; two different orders would make the answer depend on whether volumes
  were supplied. para:ANSEM -> UANSEM even before volumes are known.
- **Live `--unmapped-spot` (floor $50k):** KNTQ $1.77M, XAUT0 $1.74M, FLOCK,
  DRV, SEDA, SPCXD, MUX, HSEI, HPL, UUUSPX, HFUN, KHYPE, LIQD. Most are assets
  with no perp. XAUT0 (gold) and UUUSPX (S&P) are commodity/index wrappers the
  xyz:GOLD / index perps could hedge with - the same 5-day-market question as
  the equity quarantine. Ruling asked; nothing added.
- **The quarantine covers aliases only.** A bare-named liquid equity token
  (none exists today: NVDA/TSLA bare tokens are dead Wagyu.xyz shells) would
  still resolve through the bare-name path. Noted, not built.
- `python main.py basis --harvest` now makes ONE spot-context request so dead
  legs are tagged; a failed lookup prints the book untagged. Live: xyz:HOOD
  ($402/day), para:AVGO and xyz:AVGO ($0/day) tagged; UANSEM and UXPL clean.
- Stablecoins (SPOT_NON_BASIS_TOKENS) are excluded from the telemetry so it
  reports missing aliases, not quote assets.

## Round 40 findings

- **Aliases verified before adoption** (live token list, 2026-09-04): UFART
  "Unit Fartcoin" $570k/day, HPENGU "Pudgy Penguins" $180k, XMR1 "XMR -
  Wagyu.xyz" $16M, FXMR "Freedom XMR" $10.7k, NVDAX "Wrapped NVIDIA xStock"
  $131k, TSLAX $0, FXRP $12k; EQNVDA/EQTSLA/IXRP/WXRP exist with no pair. The
  bare NVDA/TSLA tokens are "Wagyu.xyz" shells with no or dead pairs. Fuzzy
  fullName matching was ruled out: a wrong alias hedges one asset with another.
- **Decimals bug (Ruling 40-4).** `spot_sz_decimals` looked up the PERP base
  name in the spot table, so UBTC/UFART/UANSEM hedges all reported None and
  `matched_leg_size` sized off the perp leg alone. Fixed spot-first with an
  `is None` test - the suggested `or` would have treated 0 decimals (whole
  units) as missing.
- **`spot_volumes` in the sampler changes nothing about ranking** - it only
  decides which spot name would hedge; passed through for parity with the scan.
- Paper state: para:ANSEM `spot_symbol` ANSEM -> UANSEM, edited on disk between
  stop and start (the running harvester would have overwritten a live edit on
  its next hourly save). Sizing/decimals of the open position untouched.

## Round 39 findings

- **Four of the five paper positions are hedged on dead spot legs.** Live
  24h spot pair volume: ANSEM $1.5k, HOOD $402, AVGO $0 (both AVGO perps),
  UXPL $1.36M. Under the new rule xyz:HOOD, para:AVGO and xyz:AVGO resolve to
  no spot leg; para:ANSEM resolves to UANSEM (liquid) rather than the bare
  ANSEM it was booked against. Positions untouched per Ruling 39-1 (yield-only
  exits); no new entry can be classed spot-backed on those legs.
- **Two payload traps.** `universe[i].tokens` are token INDEX fields, not list
  positions (a positional parse raises IndexError); asset contexts are NOT
  aligned with the pair list (718 contexts for 326 pairs) and match by `coin`
  name. Both are pinned in tests. A failed lookup returns an empty universe
  and is not cached.
- **Alias gap in `spot_symbol_for` (open).** The U-prefix rule misses
  abbreviated wrappers: FARTCOIN's liquid spot is UFART ($570k/day), XMR's is
  XMR1/FXMR, NVDA has NVDAX. FARTCOIN is therefore spot-backed in fact and
  unmatched in code. Needs an alias table or a fullName match - ruling asked.
- **Net-APR ranking mixes measured and unmeasured on one scale** (deviation
  from the directive's "unmeasured behind measured"): an unmeasured coin ranks
  on gross, an upper bound that buys it one sample; ranking it behind five
  measured positives would never sample a new hot market before entry.
- Threshold note: a $10k leg into a $10k/day pair is the day's whole turnover;
  25 tokens survive at $100k. Ruling asked.

## Round 38 findings

- **The prefix rule was wrong both ways.** Live spot lookup: CHIP, PONS, XMR,
  FARTCOIN (four of Round 37's five candidates) have NO spot token; para:ANSEM
  (held against spot ANSEM) and xyz:TSLA (spot TSLA) were excluded. Candidates
  now go through `spot_symbol_for(coin, spot_universe)`, the same function the
  harvester's scan uses. The collector caches the universe (6h refresh); a
  FAILED lookup yields zero candidates, never the prefix guess; a stale copy
  outlives a failed refresh.
- **Two paper positions showed two missing gates.** `scan_basis_opportunities`
  costed rows on demand below the scanner's 8-row spread probe and judged them
  on the net bar alone: 77.9% gross at 35.05 bps amortised over 7 days still
  nets 41%, so para:AVGO entered against a 25 bps ceiling. The ceiling is now
  enforced on every costed row (reason `spread X.Xbps > Y.Ybps max`) and again
  in `BasisHarvester.open_position` - the last gate before capital moves must
  not rely on the caller. `can_open(spot_symbol=)` refuses a spot token already
  hedging an open position (para:AVGO + xyz:AVGO = $40k on AVGO). Refusals now
  carry a reason (`harvester.last_refusal`) and the accrual loop logs it.
- **The two existing over-ceiling / duplicate positions were NOT closed.** The
  guard is on entry; the paper book still holds them and the exits stay
  yield-driven (Ruling 34-B style: a gate change is not a reversal).
- **Stall threshold**: `STALLED_AFTER_SECONDS = max(45, (REST_POLL_INTERVAL + 2) x 4)`
  lives in settings (45s at the 8s poll; 88s at 20s); `ui/components` re-exports.
- Bot_Config.md: `active_preset: "custom"`, `max_concurrent_positions: 5` kept;
  the harvester report shows the cap in force ("Open n/5"), not the code's 2.

## Round 37 findings

- **Stalled is an ALIVE-service state.** The process probe cannot see a hung
  child or a dead socket; the newest row in latest_snapshots can. Built AFTER
  the snapshot fetch in the render path (the Round 36 order had the badge
  first), cached probe every 5s, badge rebuilt every frame. Stalled outranks
  the dual warning; a dead service is orphaned/standalone regardless of age.
- **Candidates before entries.** `top_funding_candidates` ranks POSITIVE
  funding on main-dex perps only - a HIP-3 perp has no spot leg to hedge, so
  its funding is not a candidate for the spot-backed harvester however high it
  prints. Ties break on the name. `_sample_pass` runs on the hl-l2 thread:
  latest_snapshots -> `_sample_coins` -> `sample_orderbooks`.
- **The ledger backup that was tracked held demo data** (8 option transactions
  from 2026-01-05, opt_buy_BTC-90K-CALL). Untracked and ignored; history keeps
  a demo file, not a real position. No rewrite needed.
- **A latent flake, found by the suite.** `write_drop`'s default filename had
  one-second resolution; two drops within a second overwrote each other. It
  surfaced as 1 file where a test expected 2. Microseconds now.
- Antigravity's own query: 13.2M rows, 82.2h span, 98.33% 60-minute continuity
  with one poller (Round 34 measured 78% with two).

## Round 36 findings

- **One ingester, measured.** With the dashboard's embedded collector polling
  beside the service, BTC had 119 snapshot rows per 10 minutes (two 8s pollers
  would give 150; the shortfall was throttling). Read-only dashboard beside the
  service: 59 rows per 10 minutes, the single-collector rate (8s sleep plus ~2s of request time gives ~60). The second
  900 weight/min is gone.
- **The header tells the truth in four states.** read_only (service alive),
  standalone (none at start), orphaned (started read-only, service since died:
  RED, "tables are going stale"), dual (started standalone, service since
  appeared: restart the dashboard). Re-checked every 5s from a file read and a
  process probe; nothing is spawned mid-run.
- **Sampling priority is positions > rotated > core**, via
  `MarketCollector._sample_coins`; the harvester is created lazily by the
  accrual loop, so a collector that has not accrued yet samples rotated/core.
- **Runtime files untracked.** `*.pid` and `*.jsonl` ignored; the three files the
  Round 26 baseline tracked are `git rm --cached`. `git status` is quiet apart
  from the vault notes the sync rewrites and the paper-state JSON.

## Round 35 findings

- **Ruling 5.B, as built.** `MarketQuote.line` is the selection's own handicap;
  the watcher keys a market by `market_line_key` = the UNSIGNED number, so both
  legs still devig together; `record_fair_value_measurement(lines=...)` stores
  one signed line per leg. A home-keyed file (Round 33's -3.5 / -3.5) still
  groups into one market but stores -3.5 on both legs, so it can never hedge a
  spread - the convention is "as the feed states each leg". RESULTS FILES MUST
  FOLLOW IT: `settle_placed_bets` joins on the `line` string, so a Ravens result
  is `+3.5`, not `-3.5`.
- **7 of 7 matched** on the real `sports_market.db` after re-dropping the sample:
  the Eagles -6.5 question hedges against Pinnacle Cowboys +6.5 at 1.909, book
  arb -2.33%, worst branch -8.78%. 0 clear the hurdle, as before.
- **The REST budget decides the sampler, not the wish list.** Context polling
  costs 6 dexes x 20 weight every 8s = 900 of the 960 weight/min the limiter
  allows. Sampling 24 coins every 120s costs 24/min. It runs ONLY in the
  collector that owns maintenance; the sampled spread is the PERP leg's and
  stands in for both legs of the drag formula.
- **The dashboard still ingests.** Its embedded collector yields maintenance and
  sampling now, but it still polls contexts and writes snapshots alongside the
  service: 727 snapshot rows per coin per hour where one collector at 8s would
  write ~450, and a second 900 weight/min against the same IP. That duplication
  is the most likely cause of the 429s behind the continuity gaps. Decision
  needed: the dashboard should read the database and not run a collector while
  the service is alive.
- **Keep-awake holds the IDLE timer only.** ES_CONTINUOUS|ES_SYSTEM_REQUIRED is
  set by the supervisor and released on exit; a user-chosen Sleep, a lid close,
  or a critical-battery shutdown still sleeps the host. `--allow-sleep` opts out.
- **Polymarket outcome 1 is priced off the mirrored bid** when that is worse than
  the posted price (1 - bestBid_0); basis recorded as `mirrored_bid`. Totals and
  spread outcomes are never rewritten as fixture questions.

## Round 34 findings

- **The Round 33 retention fix was not in effect on the machine.** Settings are
  read at import; the collector had been launched 2026-09-03 14:45, nine hours
  before `SNAPSHOT_RETENTION_HOURS` was edited, and the oldest snapshot was
  exactly 72.0h old 15 hours later. Its supervisor (`run_collector_service.py`)
  had died, leaving a bare child with **78% hour-continuity** over the retained
  window (12 of the last 24 hours had no rows for ANY coin). Restarted under the
  supervisor 2026-09-04 04:45 UTC, and again 05:20 UTC after the collector patch
  below. Ruling C's ~2026-09-08 for 168h of raw rows still holds; the first
  PERSISTED 168h windows (entry must carry a quote, window must complete) land
  ~2026-09-11, and Ruling D's 720h no earlier than ~2026-10-04.
- **A SECOND pruner: the dashboard.** `main.py dashboard` embeds a full
  `MarketCollector`, maintenance loop included. The dashboard launched 2026-09-03
  14:46 kept 72h in memory and pruned every five minutes AFTER the service was
  restarted with 192h - caught because rows older than 72.5h stayed at zero and
  the boundary moved at 05:02:34 UTC, a time no service pass could produce.
  The embedded collector now skips maintenance whenever `data/collector.pid`
  names a live process (`service_collector_alive`); the dashboard was restarted.
  Restart BOTH after any settings change.
- **What the persisted tables say after the first backfill** (6,670 windows,
  11,941 events + matched controls, 418s): entry-conditioned 24h, quote >= 20%:
  n=358 on 103 coins, median realised 25.7% vs 6.8% unconditional, **+18.9pp,
  coin-bootstrap P(median >= 20%) = 0.897**; >= 25%: +22.3pp, P 0.972; >= 40%:
  +28.6pp, P 1.000 - the Round 32 result reproduced from the summary tables.
  Cascade excursions, trade_sweep, 7,694 events on 31 coins: MFE/MAE 0.49 (5m)
  to 0.83 (60m) against a persisted control of ~1.05, cluster P(>= 1) 0.000-0.032
  - the fade retirement on 15x the sample. Regimes seen: VOL_MID|FUND_FLAT 18h,
  UNKNOWN 15h (BTC reference gaps); 168h hold: 0 windows until ~2026-09-11.
- **The machine sleeps, and the service does not survive it.** Windows entered
  sleep 2026-09-04 02:19 local (06:19 UTC) and resumed 11:12 local; on resume
  neither the supervisor nor its collector child existed, and the old dashboard
  was gone too (its 72h pruning stopped with it - oldest row is now 81h). The
  launcher was re-run 15:22 UTC and the dashboard restarted behind it so the
  service owns maintenance. A nightly nine-hour sleep caps continuity near 60%
  and puts an UNKNOWN regime across every gap; Ruling D's 720h cannot be met on
  a machine that sleeps. Decide: disable sleep for this box, or host the
  collector elsewhere.
- **The collector's one `hl-db` thread ran the snapshot poller, the buffer
  flusher AND maintenance.** A two-minute measurement pass queued behind it
  would have created the gaps the measurements are made from. Maintenance now
  has its own `hl-maint` thread; the per-pass budget is one grid instant per
  hold (~2 min across 440 coins for the 7-day scan, 0.25s per coin measured).
- **Fail closed on the measured tables.** If the persistence pass raises,
  `asset_snapshots` and `liquidation_events` are NOT pruned that cycle; the
  others prune as before. Tested by monkeypatching the pass to raise.
- **"No quote, no entry."** The first rule wrote 1,760 seven-day windows whose
  entry instant predated any row for the coin - entries nobody could have made.
  Deleted; a window is now recorded only if a funding quote was in force at the
  entry instant (one indexed lookup, asked first). Thin windows AFTER a real
  entry still record with a NULL rate, never a number.
- **`orderbook_snapshots` is empty and nothing writes it.** `net_apr_after_fees`
  is therefore NULL on every persisted window (`fee_basis = 'unmeasured'`); no
  default spread is substituted. The cost model that decides the 7-day hold has
  no measured spread anywhere in the repo.
- **Antigravity's Gamma URL does not filter.** `?tag=sports` returned a crypto IPO
  event and French politics; `tag_id=1` (the "Sports" tag per `/tags/slug/sports`)
  does. Fixture markets are team-vs-team, not yes/no, and are rewritten into two
  derived questions carrying `derived_from`. `takerBaseFee` has no documented
  unit and is NOT inferred into `fee_rate`.
- **Spread pairs never match, by convention conflict.** `odds_watcher` keys both
  spread legs under the home handicap (Round 33 fix); `matcher.hedge_leg_for`
  looks for the MIRRORED line on the opponent. The sample carries one spread
  question so the gap is visible: 7 questions loaded, 6 pairs matched. Needs a
  ruling on which convention wins before spreads can be hedged.
- A static odds source cannot fabricate line history: `--watch` fingerprints
  PRICES (not timestamps) and skips an unchanged poll. Brier scoring is fed by
  settled results (`results_watcher`), not by quotes - the poller does not
  touch it.
- The supervisor sends the collector's stdout to DEVNULL, so its maintenance
  log lines are invisible. `python main.py persist --status` and
  `measurement_watermarks.updated_at` are the evidence that passes run.

## Round 33 findings

- **Three of Antigravity's Round 33 rulings needed correction before building on
  them, all verified**: (1) Ruling B's cost-drag figures (3.13% / 21.90%) used
  `legs=1` for a two-leg spot-backed trade; correct values are **6.26% / 43.80%**
  - the conclusion (keep 7-day hold) is *strengthened*. (2) Ruling A's "unblocks
  7-day windows TODAY" is wrong: raising retention does not recreate pruned
  rows; snapshots spanned 69.1h, so a full 168h window first exists **~4.1 days
  after the change**. (3) Ruling D (720h across >=2 regimes) **cannot be met under
  Ruling A alone** - 192h retention can never hold 720h; incremental measurement
  persistence (option b) is required by D, not optional.
- **Target 2 path names were wrong** (`monarch_bankroll.py` does not exist; the
  hook is `interfaces/monarch_hook.py`). No `DEPOSIT` type existed in the ledger;
  one now does (`asset_class="cash"`, opens no lot, never summed into gains).
- **Precedence for liquid cash**: override (`--cash` / `--paper-bankroll`) >
  deposits (measured) > declared-in-config > **none = $0.00**. `config.yaml` now
  ships `default_cash_balance_usdc: null`. One HL test relied on the old
  placeholder and now declares its balance explicitly.
- **The odds watcher's own guard caught a defect in my sample**: I keyed the two
  spread legs under different lines (-3.5/+3.5), making two one-leg markets it
  correctly refused. Both legs now share one line key; 6/6 markets price.
- **`.gitignore` data rules were root-anchored** - `data/odds_drops/` never
  matched `Sports_Desk/data/odds_drops/`, and the first real drop showed up as
  untracked. All data rules now use `**/` prefixes; verified with `check-ignore`.
- The Sports exporter had a tz-aware `now` vs naive `placed_at` bug that silently
  disabled the >3-day un-exported warning; caught by the test that asked for the
  warning by name.

## Round 31 findings

- **Item 14 is the retired liquidation fade.** Same signal (liquidation
  clusters), same thesis (wick rebound), same mechanism (pre-positioned limits).
  It was measured and killed in Round 16: **MFE/MAE 0.513 vs a random-entry
  control of 1.092**, n=466, t=-10.52, MAE > MFE in 72.7% of events, 0/20,000
  bootstrap resamples non-negative. Below the control means *worse than random*.
  `config/settings.py` records: "no filter or geometry fixes a sign error" and
  "do not re-enable without a new pre-registered excursion result".
- **Forced liquidations are momentum drivers, not mean-reverting wicks.** The
  spec's "tight post-fill trailing stops" is the worst possible configuration
  against that - it converts adverse excursion from paper into realised loss,
  and is exactly what rounds 9-15 kept retrying.
- **A live pre-registration already exists**: `data/experiments/
  passive_fade_rebenchmark.meta.json`, status PASSIVE, reopening bar
  `P(ratio >= 1.25) > 0.90` under a **cluster** bootstrap, >=500 events, >=20
  coins, top coin <=20%. Building Item 14 as specified would have violated the
  project's own protocol.
- **The retirement is weaker than the headline**, and the registration says so:
  0.513 was substantially a two-microcap artifact (83% of events, HHI 0.360);
  broad-market effect was 0.849. Only the 30m horizon clears p<0.05. So: probably
  no edge, *not proven* across the broad market, under active re-measurement.
- **What I built instead**: `strategies/whale_sweeper.py` with cluster geometry,
  zone maths, the `hl_whale_sweep` bucket, and `EvidenceGate` holding execution
  shut until the pre-registered bar clears. Two independent locks; both must
  open. The path is wired and tested, not stubbed.

## Round 29 findings

- **Item 8 was ~90% already built.** `execution/basis_harvester.py` (delta-neutral,
  accrues at the CURRENT rate not the entry quote), `analytics/funding_arbitrage.py`
  (scan + spread amortisation), `BASIS_MIN_NET_APR = 20.0` already the *net* bar,
  and `hl_basis_harvest` already the bucket name in `risk_manager.py`.
- **The real gap: the harvester never asked the bankroll.** It imported
  `STRATEGY_BASIS_HARVEST` only to tag receipts and gated on its own paper cash;
  `market_collector.py` opened positions with no bucket check at all. Same defect
  as Monarch_Shark running 1.7x over its sports bucket. Now wired, and the live
  call site goes through it.
- **The quoted APR is double the return on capital.** Every APR in the system is
  per-*leg*; `capital_required()` is `notional x 2`. A position reporting 56%
  realised earns 28% on money committed. A gate asking for one leg's notional
  would authorise half what the position spends.
- **The honest restatement**: 20% quoted -> 10% on capital -> 6.8% after tax ->
  vs 3.7% for a T-bill after ITS tax (state-exempt, 31 USC 3124(a)). A three-point
  edge, not fifteen.
- The gate **fails closed**: an unreadable ledger rejects rather than waving
  through, and logs loudly so "gated off" is never mistaken for "no opportunities".

## Round 27 findings

- **Both deltas in the Round 27 spec were overstated.** `delta_state = 1.0` on
  the sportsbook leg reads as full relief; it is full relief *at the bare state
  rate*, an effective delta of 6.37/32.37 = **0.197**. And `delta = 1.0` on the
  Polymarket leg assumes capital gains exist to absorb the loss.
- **The structural reason**: each leg's loss is deductible only against a class
  of income the other leg does not produce. When the sportsbook leg loses the
  winner is a capital gain (nothing for NJ 54A:5-1(g) to net against); when the
  Polymarket leg loses the winner is ordinary income (IRC 1211(b) caps the
  offset at $3,000). Both reliefs are therefore *capacity*-dependent and default
  to zero.
- **Hurdles**: 8.83% with ample capacity, **16.75% with none**, 23.93% if the
  Polymarket leg is read as wagering. Real cross-book arbs pay 1-3%, so the
  engine's usual answer is REJECTED.
- Pinned against two closed forms: the known single-venue delta=0 hurdle
  (23.9317%, matches to 1e-6) and the trivially-zero fully-relieved case.

## Next / open questions

- `persist --status` will show `fees_measured` climbing from the next grid
  instant after a sampling pass; the first 7-day windows with a measured fee
  arrive with the first 168h windows (~2026-09-11).

- **Decision needed: the collector host sleeps.** Continuity was 78% before
  and a nightly sleep makes it worse; the service must be relaunched by hand
  after every resume (`start_collector.bat`). Either disable sleep on this
  machine or run the collector on one that stays up.
- **Ruling needed: spread line convention.** Store the selection's OWN handicap
  (away leg at +3.5) and group markets by |line|, or teach the matcher the
  home-keyed form. Until then no spread hedge can price.
- **Orderbook collection.** Nothing populates `orderbook_snapshots`; the cost
  drag on every basis decision rests on an assumed spread. Persisted windows
  will carry a measured `net_apr_after_fees` the moment it is written.
- `persist --status` daily. Ruling D precondition: 720h across >= 2 regime tags
  with >= 48h each; UNKNOWN never counts. First 168h persisted windows
  ~2026-09-11; first 24h walk-forward read `persist --hold 24` is available now.
- Polymarket live polling is the operator's call (network):
  `python -m cross_market.ingestors.polymarket_fetcher --live --watch`.

- **Incremental measurement persistence (option b)** is now *required* by Ruling
  D's 720h standard, not a follow-up. Design: persist per-event excursions and
  per-window realised funding as raw rows age out, so the analysis window is
  unbounded while storage stays flat.
- **7-day entry-conditioned re-run** once snapshots reach 168h (~2026-09-08).
  The 24h signal is validated (+17.7pp over control, coin-bootstrap 0.913-1.000);
  the 7-day hold the money is committed for is not.
- Run `python -m Tax_Reserve_Agent.main seed-bankroll --paper-bankroll <amt>`
  before any live desk starts, or every gate stays FAIL-CLOSED by design.

- **Is a Polymarket event contract capital or wagering?** Unsettled - the IRS has
  not ruled on retail-held CFTC-regulated binaries. IRC 1234A supports capital;
  a wagering characterisation collapses the leg into the same trap as the
  sportsbook and costs ~7 points of hurdle. `--prediction-as-wagering` prices it.
  This is the largest open legal question in the build.
- `matcher.TEAMS` is deliberately partial. An absent team produces NO MATCH,
  which is safe. Add teams on demand rather than loosening the matcher.

- **The drop path is `data/imports`, not `data/drop`.** Round 26m specified
  `Tax_Reserve_Agent/data/drop/`; that directory does not exist and nothing reads
  it. `config.yaml -> imports.drop_folder` and `csv_watcher.DEFAULT_IMPORTS_DIR`
  both resolve to `data/imports`. An export to `data/drop` would look like it
  worked and import nothing. A test now pins `TAX_DROP_DIR ==
  DEFAULT_IMPORTS_DIR` so they cannot drift.
- **No remote is configured.** Nothing is pushed anywhere. Before adding one,
  re-check `.gitignore` — the secrets argument only holds while the history is
  local.
- **The multi-state problem is not modelled.** A travelling contract worker
  resident in NJ owes roughly `max(NJ, work-state)` per dollar after the
  other-jurisdiction credit — higher in NY, lower in PA — and betting while
  physically in another state can source winnings there. The single 6.37% is the
  right approximation for a NJ resident; it is not a return.
- `professional_schedule_c` is permanently barred under *Groetzinger* while the
  x-ray contract work continues. Do not re-open it.
