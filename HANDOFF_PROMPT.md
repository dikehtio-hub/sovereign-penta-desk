# HANDOFF_PROMPT.md — the prompt currently owed to Antigravity

**This file holds ONE prompt: the handoff to send next.** When it is answered and a new one is
written, the old one moves to `HANDOFF_ARCHIVE.md` (newest last) rather than being appended below.
The handoff letter and the cross-check request are ONE block, one copy-paste — never two.

---

HANDOFF — CLAUDE CODE TO ANTIGRAVITY (clock 04:15Z 09-22 / 09-22 00:15 EDT)
Subject: Section 105 executed. Pipeline stopped for the house move at 03:44:21Z on the operator's word,
         first real run of shutdown_dev_penta.ps1 -Execute clean. Backup done as three verified zips in
         Google Drive (2.95 GB) instead of a 14.2 GB mirror - the substitution and why, below. Push to a
         private remote deferred to the new home. One arithmetic note on s4, one protocol note on clocks.

=== 1. SECTION 105 RULINGS - ACCEPTED, WITH TWO NOTES ===
s1 file-watched relay and the authority invariant: accepted verbatim. Protocol note: Section 105 was on
disk at 22:16 EDT (mtime) under a header stamped 22:35 EDT; my 02:25Z handoff header was likewise ahead
of wall time. Under the file relay the MTIME is the freshness stamp, headers are labels.
s2 gen-1 scripts untouched tonight; WP4 on refactor/unify-lifecycle-scripts accepted as specified.
s3 backup mandate: executed with a substitution (s3 below). s3.3 push: deferred - `gh` is not
installed, the operator has no repo yet, and Section 105's invariant makes a push an operator action.
Pre-flight done for it: [WORLD-CHECK] the only committed revision of dontshare.py (743496b) is 0 bytes;
no 0x+64hex / PEM / sk- string in any code file across all 273 commits on master and
feat/collector-hardening; largest blob 52.4 MB (under GitHub's 100 MB limit); credential.helper=manager.
s4 arithmetic: the hurdle text says "measured", the figure uses passive BTC +4.99 % - the s2500-table
value that charges BTC 20 bps. At the measured 0.2 bps passive BTC is ~+5.37 %, Delta ~ -8.95 %,
failing by ~12.95, not 12.57. Same species as 13.8/13.5. Verdict unchanged.

=== 2. THE SHUTDOWN, AS RUN ===
[WORLD-CHECK] P4 read 03:43Z (script sha e99ad136..., day coverage 540/540): primary median dAPR
+1.895 % n=248; BTC +17.03 / ETH +9.74 / SOL +1.79 -> NULL NOT CONFIRMED under ratified and amended
sets, as at 16:03Z. Cohort SANDWICH with the partial evening-after (17:00-03:43Z, 82 % of the window)
= +0.38 % n=27 - the shape the null predicts, but PARTIAL, script marks it n/a, recorded as such. The
06:03Z sleeper was cancelled before the stop.
[WORLD-CHECK] shutdown_dev_penta.ps1 -Execute, first real run, watched, dry run first (PLAN 10):
collector --stop graceful=true forced=false waited 3.5 s checkpointed=true wal 0->0; watcher and
cross-market exporter terminated by --stop; 5 telemetry + worker gone; VERIFY 0; exit 0; 28 s.
Independent command-line sweep = 0. DB quick_check ok, -wal 0 bytes. Antigravity's extension and the
6 TradingView MCP processes untouched, as designed. GAP STARTS 2026-09-22T03:44:21Z.

=== 3. THE BACKUP - WHAT EXISTS AND WHY IT IS NOT THE MIRROR ===
The operator installed Google Drive for desktop (no external media exists) and, while the pipeline was
still live, added DEV as a mirrored computer folder. [WORLD-CHECK] Drive log: mirror_local generating
1-4 upload events per second from the live writes; a mirror of a live WAL database is a torn copy, and
a reader on that file is the DEFECT-COL-001 risk. I asked for a pause; the click that followed removed
the folder from sync (Drive's mirror_sqlite.db: root_config empty, mirror_item 0 rows; 5,800+ queued
items dropped as "root not currently syncing"). No local file was touched. Rather than re-add a two-way
mirror that would have to be unlinked before resume, the copy was made ONCE, after the daemons stopped:
  DEV_backup_2026-09-22.zip  251,394,982 B  sha256 d55e2346...bd0b7  - 14,686 files: all code, every
     .git (DEV, quant_trading_lab and its two worktrees), vault, HOMEWORK/AGENTS, handoff archives,
     tonight's uncommitted work, every small DB. Excludes only the two rolling 8-day stores and venvs.
  hyperliquid_data_snapshot_2026-09-22.zip  2,066,522,304 B  sha256 11eaad2e...3789  - VACUUM INTO
     snapshot (5.20 GB clean, quick_check ok, 17,826,766 asset_snapshots rows), zipped.
  polymarket_drops_2026-09-22.zip  636,457,715 B  sha256 32b1e756...1442  - 2,980 JSON drops.
All three in G:\My Drive\DEV_backup_2026-09-22\ with .sha256 files; each verified against its hash
after the copy. [WORLD-CHECK] Drive's metadata store at 04:10:12Z: all three carry cloud IDs (1L6HNHWev8..., 124sSMDga9..., 1LX333ABg0...), sizes byte-exact, pending operations 0. 2.95 GB in the cloud.
Sizing fact for the record: 97 % of the 14.22 GB folder is the two 192-hour windows; on resume the
collector prunes everything older than 192 h from that moment, so their shelf life is days. The
irreplaceable set is ~250 MB.

=== STATE ===
Pipeline DOWN since 03:44:21Z, 0 daemons, laptop to be powered off for the move. DEV master 157e5e9 =
cd5bfac + the catch-up set, committed on the operator's "commit it" (116 paths, +14,927/-393); lab master
6e23e8f. Remote: origin = https://github.com/dikehtio-hub/sovereign-penta-desk.git registered, repo created
empty by the operator, PUSHED BY THE OPERATOR from the terminal (the app's permission classifier withholds
publication from me): [WORLD-CHECK] git ls-remote origin -> master 157e5e9, feat/collector-hardening 70bd232;
local master tracks origin/master. Also off-machine: git bundle (--all, verified) in
G:\My Drive\DEV_backup_2026-09-22\records_final\, beside the final AGENTS.md and handoff files; the essential
zip predates the commit (03:47Z). Uncommitted after this edit: AGENTS.md and HANDOFF_PROMPT.md only. Nothing launched. Nothing deleted except the
temporary 5.2 GB snapshot file the zip replaced. Left in place for the operator: Desktop\DEV_backup_
2026-09-22.zip and Desktop\DEV_data_2026-09-22\ (local copies of the same zips) and DEV\.tmp.driveupload
(Drive's abandoned staging folder, ~2,000 entries) - both are safe to delete, neither was mine to delete.

=== NEXT SESSION OPENS WITH ===
(1) confirm no folder is listed under Drive preferences -> Folders from your computer (none should be);
(2) optional Windows 11 25H2 while the pipeline is down; (3) resume_all.bat; (4) register the gap
(start 2026-09-22T03:44:21Z) in data_gaps.json + python -m knowledge.ingest.data_gaps; (5) s3.3 DONE - both branches
on GitHub; from now on `git push` at the end of a session keeps it current; (6) WP4 on its branch; (7) nights 1-5 restart
from the first full night after resume. Your Opening Sheet, rule (0) first, for whatever comes next.
