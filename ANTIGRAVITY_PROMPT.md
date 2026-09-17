# ANTIGRAVITY_PROMPT.md - the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting. Written by Antigravity, read by Claude Code; the operator
carries it between the two.

**Before answering a handoff, confirm it is new.** A re-pasted or truncated `HANDOFF_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- ANTIGRAVITY_PROMPT.md` and its mtime: if nothing changed, there is
nothing new to rule on.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** The `State`
line below is an assertion about repository state that the auditor cannot verify from here and the
implementer can. Write what was measured and when - not "clean", and not a PID table standing in
for stream liveness.

---

## Section 94: Secret Remediation Ratified (Option A), Arbitrage Agent Retirement Confirmed, Phase 0 Bar Stratification, 4-Week Strategic Priority (2026-09-16 21:00 EDT / 2026-09-17 01:00Z)

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-16 21:00 EDT / 2026-09-17 01:00Z (Wednesday evening post-drill)  
**Re**: Comprehensive audit rulings on Section 94 handoff: credential remediation protocol, ratification of dontshare.py untracking, formal retirement of Funding_Arbitrage_Agent, Phase 0 bar stratification for live paper trading, and strategic roadmap for the 4-week inter-drill window.

### 1. Secret Remediation & Git Remote Protocol (§1): OPTION (a) RATIFIED
- **Forensic Verification**:
  - `743496b:BOTS/Phemex/Phem_key.py`: Confirmed active string `key = '59fcd1fc...'` and `secret = 'fcunlq55...'`.
  - `743496b:Polymarket/Polymarket_Moondev/poly_whale_monitor.py`: Confirmed fallback `'moongroup_31a630c54125eab9'`.
  - `HEAD:BOTS/HYPERLIQUID/key_file.py`: Confirmed public EVM wallet address `0xD78A1bF07F211f11B08Cc48C4F51D3BE9d2CeeA8`.
- **Ruling on Remedy**: **OPTION (a) RATIFIED**.
  - Rewriting git history (Option b) breaks the cryptographic SHA-1 hashes of all 171+ historical commits cited across vault wiki pages, L5 provenance entries, and `HOMEWORK.md`. It is disproportionate and structurally destructive.
  - The standard cryptographic and operational remedy is **immediate credential rotation and revocation at the issuer**. The operator must rotate/revoke keys at Phemex and Moon Dev. Once revoked, the strings in git history become inert dead text.
  - Pushing to a strictly **private** authenticated remote (GitHub private or self-hosted bare git) with revoked credentials in history is safe and standard practice.
  - **Wallet Address (`key_file.py`)**: The `0xD78A...` string is an on-chain public address, not a private key. However, linking this address to an external GitHub account is an **operator privacy decision**. If desired, replace `key_file.py` with an environment variable lookup `os.getenv("HL_ACCOUNT_ADDRESS")` in working tree before setting up the remote.

### 2. Untracking `dontshare.py` & `.gitignore` Negation (§2): RATIFIED
- Commit `c0ff089` untracking `BOTS/HYPERLIQUID/dontshare.py` with `git rm --cached` and adding `.gitignore` rules (`dontshare.py`, `**/.env`, `!**/.env.example`) is **RATIFIED in full**.
- Leaving an empty tracked file that is intended to hold secrets is an extreme hazard under `git add -A`. Removing it from the index permanently defuses the trap.

### 3. Retirement of `Funding_Arbitrage_Agent` (§3): RATIFIED
- **Audit Findings Verified**:
  - `execution_manager.py:161`: `_place_single_live_leg` sleeps 0.5s and unconditionally returns `status='FILLED'`.
  - `execution_manager.py:173`: `_handle_leg_imbalance` calls `_place_single_live_leg` for unwinds, faking the emergency unwind too.
  - `execution_manager.py:54`: `get_account_balance` returns `paper_balance_usd` in both dry-run and live modes.
  - `execution_manager.py:200`: `close_arbitrage_position` live branch merely flips `pos.is_closed = True` without sending any orders.
  - Structural dependency on Binance perps is legally and operationally barred in New Jersey.
- **Retirement Protocol Ratified**:
  - "Retire" means disabled + documented, never deleted.
  - Mark `AGENTS/Funding_Arbitrage_Agent` as superseded in `COMMANDS.txt`.
  - Set `status: disabled` with triage rationale in `Dexter/registry.yaml`.
  - Retain code directory intact for architectural post-mortem and golden-testing reference.

### 4. Operator Goal & Harvester Phase 1 Parallelization (§4): RATIFIED
- **Zero Real Funds Active**: Operator's confirmation that only **live paper trading** is active validates that $0.00 tax liability is correct, and unmodelled funding income is an execution gate rather than an accrued liability.
- **Phase 1 Parallelization Approved**:
  - Phase 1 (`api/exchange_client.py`, info client, signed request construction, and offline JSON fixture tests) involves **zero live DB interaction and zero live execution**. It may proceed in parallel with `DEFECT-COL-001`.
  - **The Strict Gate**: Phase 2 (wiring the live chain into `market_collector.py`) and live socket streaming remain strictly gated behind the deployment and verification of `DEFECT-COL-001`.

### 5. Phase 0 Bar Stratification (§5): RATIFIED
- To prevent deadlocking development when real money is not on the table, the Phase 0 bar is **stratified into two distinct tiers**:
  1. **Phase 0A (Live Paper Deployment Bar)**:
     - $\ge 10$ closed paper positions
     - $\ge 5$ distinct coins
     - Top position share of total PnL $< 65\%$
     - Positive net PnL after taker fee simulation.
     - *Purpose*: Unlocks wiring real testnet/paper execution in the collector.
  2. **Phase 0B (Real Capital / Mainnet Deployment Bar)**:
     - Maintains the original conservative institutional bar: $\ge 20$ closed positions, $\ge 10$ distinct coins, top position $< 50\%$ PnL, median net APR $\ge 20\%$ sustained over a 30-day window.

### 6. Strategic Roadmap for the 4-Week Inter-Drill Window (§6)
- **Candidate Selected**: **Systemic Fail-Fast Hardening via Queue Execution (Synthesis of Candidates 1 & 4)**.
- **Defense Against Alternatives**:
  - *Against Candidate 2 (Phase 1-2 Paper first)*: Building a paper harvester on top of a collector that is suffering 393 lock errors a day creates synthetic unobservable bugs. The data layer must be sound before trading logic is added.
  - *Against Candidate 3 (Track B DEX arb)*: MEV on Base DEXes is an unvalidated exploratory hypothesis; diverting core engineering from HyperLiquid to Base before Desk 1 is hardened violates focus.
  - *Why Synthesis 1 + 4 Wins*: The queue items (DEFECT-COL-001, DEFECT-EXP-001, Drill Tooling Hardening, S92 Ground-Truth Gate) ARE the exact embodiments of the silent-failure class. Fixing them systematically with strict fail-fast contracts (raising errors on empty slices, zero-lock tolerance, assert-not-silent) cures the infrastructure completely, paving the runway for Track A Phase 1-2 to proceed cleanly.

### Standing State & Queue Priority
- Queue order: (1) DEFECT-COL-001 -> (2) DEFECT-EXP-001 -> (3) Drill Tooling Hardening -> (4) DEFECT-LINT-001 -> (5) TradingView MCP Integration -> (6) Harvester Phase 1 -> (7) S92 Ground-Truth Upgrades.
