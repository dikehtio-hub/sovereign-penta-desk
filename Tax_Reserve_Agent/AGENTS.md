# Tax Reserve Agent — Agent Handoff

## OPERATOR PROFILE (2026-09-03) - READ BEFORE TOUCHING RATES

Travelling x-ray technologist on contract. Tax home: Union, NJ 07083. Works and
lives across multiple states on assignment.

Three consequences the config now encodes:

- **NJ marginal rate 6.37%**, not the old 0.05 placeholder. NJ Gross Income Tax
  is graduated: 5.525% to $75,000, then 6.37% to $500,000. Gambling winnings
  stack on wages, so the marginal dollar on a travel contract lands at 6.37%.
- **NJ NETS GAMBLING LOSSES AS A CATEGORY - no Schedule A required.** This is
  independent of the federal election, and the code used to conflate them; see
  the bug below.
- **`professional_schedule_c` IS NOT AVAILABLE.** Groetzinger needs gambling
  pursued full time as a livelihood. Someone working travel healthcare contracts
  cannot meet it. Realistic modes are casual_standard_deduction (almost certainly)
  or casual_itemized.

NOT MODELLED: multi-state sourcing. NJ taxes residents on income earned anywhere
and credits tax paid elsewhere, so the effective rate per dollar is roughly
max(NJ, work-state) - higher in NY, lower in PA. Betting while physically in
another state can source those winnings there. A single `state_tax_rate` is the
right approximation for a NJ resident and is not a substitute for a return.

## ROUND 26L (2026-09-03) - STATE NETTING IS NOT THE FEDERAL ELECTION

**A REAL BUG, FOUND FROM THE OPERATOR PROFILE.** `state_allows_loss_deduction`
was consulted in the itemised, session and professional branches but NOT in the
standard-deduction branch, where the state base was hardcoded to gross winnings -
as though the federal standard deduction bound the state too.

For a New Jersey resident on $80,000 won / $79,000 lost that over-stated state
tax by **$5,032**. The state base should have been $1,000, not $80,000.

- The state base is now computed ONCE, centrally, from the state's own rule, in
  every treatment.
- **`state_loss_deduction_pct`** is separate from the federal one and defaults to
  1.0. OBBBA 70114 amended IRC 165(d) only; no state adopted it, so NJ nets at
  100% while the federal deduction is haircut to 90%.
- The federal trap is untouched: a standard-deduction filer is still taxed on the
  full gross federally. Only the state leg changed.

## ROUND 26k (2026-09-03) - RATES UNBUNDLED, SESSION NETTING, THREE BRIDGES

521 agent tests + 652 master + 23 bridge tests pass.

- **THE STATE DOUBLE-COUNT IS GONE.** `tax_rates` now holds one thing per line:
  `federal_ordinary_rate 0.24`, `state_tax_rate 0.05`, `safety_buffer_pct 0.02`,
  and `short_term_capital_gains 0.24` (short-term gains ARE ordinary income).
  Composite 0.31, not 0.35.
- **EVERY PUBLISHED FIGURE FROM ROUNDS 26f-26j WAS COMPUTED AT THE WRONG RATE**
  and is restated here. The hurdle was never 21.21%:

        single even-money, delta=0   21.21%  ->  18.34%
        symmetric 2-way arb, delta=0 26.92%  ->  22.46%
        arb, delta=0.90               2.69%  ->   2.25%
        Polymarket fee break-even     3.08%  ->   2.90%
        $150 of winnings, escrow     $52.50  ->  $46.50

  The direction is uniform: every hurdle was too STRICT and every escrow too
  HIGH, because state was charged twice. The W-2G credit ceiling moves the other
  way - capped at 24% now instead of 28%, so it credits LESS.
- **`session_netting_itemizes`.** Session netting is a MEASUREMENT convention,
  not a deduction mode. A session-netter who itemises deducts losing sessions on
  Schedule A; one on the standard deduction does not. `tax_calculator` now
  measures losing sessions as well as winning ones. Defaults false - the stricter
  reading, since allowing the deduction lowers the reserve.

## ROUND 26j (2026-09-03) - AUDIT OF EARLIER DECISIONS

Three things from earlier rounds that interacted badly as the system grew.

- **THE COMPOSITE RATE COUNTS STATE TWICE, and it now drives everything.**
  `tax_rates.short_term_capital_gains: 0.28` is documented in config.yaml as
  "24% Federal + 4% State composite", and `state_tax_rate: 0.05` is then ADDED.
  Since Round 26 that composite has been the fallback federal leg for gambling,
  so: the W-2G credit ceiling is too GENEROUS (capped at a federal+state number)
  and every hurdle is too STRICT (computed at the inflated 35%). NOT fixable from
  code - it needs the operator's real marginal rates. Now surfaced as a gambling
  warning whenever `gambling.federal_ordinary_rate` is unset, instead of being
  inherited silently.
- **The term-classification rule is now VERSIONED.** Round 26c replaced
  `holding_days >= 365` with the calendar test, but `realized_pnl` is derived and
  nothing rewrites it in place - a ledger built earlier keeps terms computed the
  old way, and the old way marked exact-anniversary trades LONG_TERM when they are
  legally SHORT, which UNDER-states the reserve. `TERM_RULE_KEY` in `agent_meta`
  is compared on every read; `term_rule_stale` and a HUD banner say to rebuild.
  Same pattern as the accounting-method mismatch that was already there.
- **`session_netting` forces delta = 0 regardless of itemisation - FLAGGED, NOT
  CHANGED.** Session netting is a MEASUREMENT convention, not a deduction mode: a
  session-netter who also itemises can deduct losing sessions on Schedule A.
  Changing it would LOWER the reserve, which this ledger does not do on its own
  initiative. Antigravity to rule.

## ROUND 26i (2026-09-03) - N-WAY ARB HURDLE + FREE-BET EFFECTIVE STAKE

- **`after_tax_arbitrage_hurdle` generalised to N legs and made delta-aware**:
  `R = [1 - t*s_min - t*delta*(1 - s_min)] / (1 - t)` with
  `s_min = (1/O_max)/booksum`. Contains the symmetric two-leg formula exactly and
  zeroes the worst branch for 2-, 3- and 4-way markets at every delta.
- **W-2G effective stake is the CASH side where there is one.** A $75 cash + $25
  bonus ticket is measured against the $75 actually risked; a wholly promotional
  ticket falls back to the promo amount; only a ticket with no stake on either
  side has an unbounded multiplier.

## ROUND 26h (2026-09-03) - W-2G + THE ARBITRAGE TAX TRAP

508 agent tests pass (was 485). 597 on the master six-module suite.

- **Form W-2G is wired; the config keys are no longer dead.** `assess_w2g()` in
  `gambling_tax.py` applies both statutory tests, which are CONJUNCTIVE and that
  is the whole point: Reg. 1.6041-10 needs proceeds of $600 AND 300x the wager,
  IRC 3402(q) needs proceeds over $5,000 AND the same 300:1. A $1,000 winner at
  2:1 clears every dollar threshold and triggers NOTHING. Measured on PROCEEDS
  (received minus staked), not payout.
- Assessed at ingestion, where the wager and payout are both in hand, and tagged
  `w2g_reportable:true` / `w2g_withholding_predicted:X`.
- **Predicted withholding is credited through the SAME federal-capped path as
  recorded withholding**, not subtracted from the total escrow as specified.
  A book that withheld and a book that MUST withhold cannot produce different
  escrows for the same wager, and 3402(q) withholding is federal income tax - it
  cannot pay a state or this ledger's safety buffer. Counted once: a ticket with
  a recorded tag is never also predicted.
- **The arbitrage tax trap** - `after_tax_arbitrage_hurdle()` and a hard gate in
  `check_order(arbitrage_edge=...)`. At 35%: delta 0 -> 26.92%, delta 0.90 ->
  2.69%, delta 1.0 -> 0.00%. Real cross-book arbitrage is 1-3%, so under a
  standard deduction EVERY ONE OF THEM is an after-tax loss of roughly 14%.
- **AN ARBITRAGE IS NOT RISKLESS AFTER TAX.** The two legs are taxed
  asymmetrically - one books a taxable win, the other a non-deductible loss - so
  a position riskless in dollars has two different after-tax outcomes whenever
  the stakes are unequal and losses are not fully deductible. Passing both legs
  prices the WORST branch: a 1.05/25.00 arb needs 51.68%, not 26.92%.

## ROUND 26g (2026-09-03) - ARBITRATION FIXES

- **`BOOK_STAKE_IS_CASH` is now NORMALISED THROUGH `canonical_book` at import**,
  and gained espnbet + thescore. It is compared against canonicalised names, so a
  raw spelling would silently never match - `espn_bet` canonicalises to `espnbet`,
  and `kambi` is dead weight regardless (a B2B platform, not a consumer brand
  that appears in an export). Normalising removes that whole class of inert entry.
- Staleness, `is_live` and CLV guardrails are in `Sports_Desk` - see its AGENTS.md.

## ROUND 26f (2026-09-03) - THE HURDLE BECOMES A GATE

485 agent tests pass (was 470). 532 across the required four-module command.

- **`check_order` now enforces the after-tax hurdle** for `WAGERING_CATEGORIES`.
  Caller supplies `expected_edge` and `decimal_odds`; a sub-hurdle wager is
  REJECTED, and what survives is sized by `after_tax_kelly_fraction`, which can
  only tighten the flat cap. Before this a $500 wager with a 5% edge was approved
  at $375 against a 24.29% hurdle - the gate had no parameter for the edge.
- **f* is zero exactly at the tax hurdle** (verified to 1e-12), so the gate and
  the sizer are the same inequality. The gate additionally charges the execution
  fee, which creates a middle band where Kelly is positive and the order is still
  refused - documented and tested, not an inconsistency.
- **FAIL-CLOSED on a missing edge.** The fee-only fallback passes a 3% edge that
  carries a 21%+ hurdle, so it is the wrong check, not a weaker one.
- **`BOOK_STAKE_IS_CASH`** - books whose `stake` column is the cash side even
  without a separate cash column (betrivers, sugarhouse, kambi, twinspires,
  barstool). Everywhere else `stake >= promo` is still read as the TOTAL. NOTE
  adding a book to that set RAISES its basis and LOWERS its taxable winnings, so
  it needs a real export behind it.

## ROUND 26e (2026-09-03) - STAKE-COLUMN AMBIGUITY

470 agent tests pass (was 467).

- **`stake` means two different things and the code assumed one of them.** Some
  exports print it as the CASH side beside a separate bonus column; others print
  it as the TOTAL of which the bonus is a part. `wager = max(cash, wager) + promo`
  read a total as a cash side, so `Stake: 100, Free Bet Stake: 25` booked $100 of
  basis instead of $75 and left $25 of winnings untaxed.
- Resolution order, in `_rows_from_record`:
    1. an explicit CASH COLUMN present (any value, `0.00` included) -> total is
       cash + promo. Presence is the signal, not a positive value.
    2. no cash column and stake == 0 -> wholly promotional.
    3. stake < promo -> a total cannot be smaller than its own part, so the
       stake is the cash side; total is stake + promo.
    4. stake >= promo -> GENUINELY AMBIGUOUS. Read as the TOTAL, which gives the
       lower basis and the higher taxable winnings, and tagged
       `stake_basis:assumed_total_not_cash` so the row can be reconciled.
- NOTE the proposed fix keyed on `cash_stake > 0`, which regressed BOTH wholly
  promotional shapes (DraftKings `Stake: 0.00`, FanDuel `Cash Wager: 0.00`) into
  a promo-exceeds-total error and dropped the rows - reintroducing the exact leak
  Round 26d closed. Both are pinned by tests now.

## ROUND 26d (2026-09-03) - PROMO LEAK + AFTER-TAX HURDLE

467 agent tests pass (was 458).

- **Free/bonus bets were STILL being dropped** (Antigravity's find, and correct).
  The promo detection added in 26c matched on WORDS, but the two biggest books
  signal it with a NUMBER in a second column: FanDuel writes
  `Cash Wager: 0.00, Bonus Wager: 25.00`, DraftKings `Stake: 0.00,
  Free Bet Stake: 50.00`. Neither row contains "bonus" as a value anywhere, so
  both were refused as a missing stake column and their winnings never reached
  the ledger. `PROMO_AMOUNT_COLUMNS` / `CASH_STAKE_COLUMNS` now read the numbers.
- **`promo` became a PORTION, not a flag.** Books allow a $75 cash + $25 bonus
  ticket, where only the cash half is basis. `promo_stake=` carries the
  promotional part; `promo=True` still means wholly promotional.
- **`monarch_hook.after_tax_edge_hurdle()`** - IRC 165(d) applied to SIZING, not
  just to escrow. See `Sports_Desk/AGENTS.md` for the formula and the numbers.
  The headline: under a casual standard deduction, an even-money wager needs a
  21.21% gross edge to break even after tax. `breakeven_gross_edge` now takes
  `category="sports"` and adds it; every other category is untouched.
  `gambling_loss_deductibility()` reads the SAME config the escrow uses - if the
  hurdle and the escrow ever disagree on d, the bot sizes for a tax the ledger is
  not holding cash for.

## ROUND 26c (2026-09-03) - ANTIGRAVITY CROSS-CHECK, ROUND 2

458 agent tests pass (was 437). Antigravity reproduced three more defects; all
three fixed, and the first uncovered a fourth in the frozen core.

- **`parse_iso_date` took only two timestamp shapes.** A bare date
  (`2026-01-10`), microseconds and a space-separated offset all raised - and
  `sortable_timestamp` catches that and sorts the row to `datetime.max`, pushing
  an OPENING lot to the end of the batch. Its settlement then found no lot,
  booked the full payout at zero basis, and stranded the stake open forever. Now
  runs `fromisoformat` with a strptime ladder behind it. Bare epoch seconds are
  still REFUSED: `1767013200` is an equally plausible quantity or ticket id.
- **LONG_TERM used `holding_days >= 365`.** IRC 1222(3) with Rev. Rul. 66-7 needs
  MORE THAN one year counting from the day after acquisition, so an exact
  one-year hold is short-term. Antigravity proposed `> 365`; that fixes the
  common year and BREAKS the leap year - 2024-01-01 to 2025-01-01 is 366 days
  and still exactly one year. No day count is right in both, because one year is
  a calendar span. Now `is_long_term()`, calendar-based, shared with
  `loss_harvester` (which had the same bug at line 376). Only ever moves a
  boundary trade LONG -> SHORT, which RAISES the reserve.
- **W-2G deduped structurally in `tax_calculator`**, keyed on (book, ticket), on
  top of the ingestor fix. The calculator sums a free-text tag across rows and a
  multi-leg settlement is two rows for one ticket; trusting the writer is how the
  tag landed on both legs in the first place.
- **Free / promo / bonus bets now import.** A zero stake was refused outright,
  which DROPPED the taxable winnings entirely - the same failure mode as the
  orphan settlement. `promo=True` (or a promo/free_bet/bet_type column) gives a
  ZERO cost basis: you did not buy the wager, so everything it returns is IRC 61
  income. A zero stake WITHOUT the flag is still refused, because a free bet and
  a missing stake column are identical in a CSV.
- **A parlay printed one row per leg booked one lot per leg.** A 4-leg $100
  parlay booked $400 of basis and understated winnings by $300. `load_from_csv`
  now collapses repeats on (source, tx_hash, side) - the key already encodes
  book + ticket + role, so a genuine two-row placement/settlement log is
  untouched. First row wins, which also keeps the symbol stable.
- **Bookmaker names canonicalised.** `DK` and `DraftKings` were two lot families,
  so a settlement from one export never matched a placement from the other and
  hit the zero-basis orphan path. NOTE: `canonical_book` changes `source`, which
  is part of the ledger UNIQUE key - rebuild rather than merge if a ledger ever
  holds both spellings.

## ROUND 26b (2026-09-03) - ANTIGRAVITY CROSS-CHECK FIXES

Antigravity independently reviewed Round 26 and reproduced three defects. All
three fixed, plus a fourth the first fix uncovered. 445 agent tests pass.

- **Timestamp ordering (Antigravity defect 1).** `process_batch` sorted
  `str(timestamp)`. A space is 0x20 and `T` is 0x54, so
  `"2026-01-10 16:30:00"` sorted BEFORE `"2026-01-10T13:00:00Z"` - a 13:00
  placement arrived after its own 16:30 settlement. The settlement found no lot,
  booked the full $2,500 payout as winnings instead of $1,500, and stranded the
  $1,000 stake open forever. Now ordered on parsed datetimes via
  `ledger_ordering_key`, with settlements sorting after placements at an equal
  timestamp - scoped to wager sides only, so a same-second spot sell-then-rebuy
  keeps its existing basis. `rebuild_lots` sorts in Python with the SAME key; it
  used a SQL `ORDER BY timestamp` string sort, so a rebuild could have produced
  different lots from the import that created them.
- **Offset-aware/naive crash (found by fixing the above).** Once settlements
  started matching, `apply_to_lots` hit `TypeError: can't subtract offset-naive
  and offset-aware datetimes` on the holding period. Latent since long before
  the wagering module - string comparison hid it by never matching. `as_naive_utc`
  now normalises for the subtraction only; `tax_year` still comes from the
  timestamp as written, so a New Year's Eve row keeps its local tax year.
- **W-2G double-count (Antigravity defect 2).** `withholding` passed through
  `**kwargs` tagged BOTH legs of a dead heat / partial void, and the calculator
  sums the tag per row: one $1,200 W-2G credited as $2,400, reserve $1,200 light.
  Now attached to the paying leg only.
- **Odds sniffing (Antigravity defect 3, fixed DIFFERENTLY than proposed).**
  Antigravity proposed sniffing on the decimal point. That trades a 60x error on
  genuine decimal longshots for a 60x error on American prices written as floats
  (`150.0`) - which is the more common export shape, and would then fire the
  payout cross-check on every row. Instead: a SIGN is decisive (`-110.0`,
  `+150.0` are American - decimal odds are never signed), a bare integer >= 100
  stays American by convention, and a bare `150.0` is REFUSED. `_safe_quote`
  catches the refusal, warns, and still records the wager, so no tax figure is at
  risk. `gambling.default_odds_format` and the CSV `odds_format` column are the
  one-line escape hatches.

## ROUND 26 (2026-09-03, Claude Code) - SPORTS GAMBLING TAX MODULE

445 agent tests pass (was 379) + 904 HL_Monarch, all offline:

```
python -m unittest Tax_Reserve_Agent.tests.test_sports_tax Tax_Reserve_Agent.tests.test_new_features
```

Antigravity drafted Item 1 (sports gambling escrow under IRC 61/165(d)); Claude
Code audited and reworked it. THE CORE LEDGER IS NO LONGER FROZEN - `lot_engine`
and `tax_calculator` both changed. What changed and why:

- **Ticket-scoped lot symbols.** The draft keyed a wager's symbol on
  `book:sport:selection`, so two tickets on the same selection shared a lot and
  the FIFO matcher settled one against the other's stake. A $20 loser and a $500
  winner on CHIEFS -3.5 booked as +$935/-$500 instead of +$455/-$20. Symbols now
  carry the ticket id (`DK:NFL:CHIEFS_-3.5#T1`), which makes the collision
  structurally impossible rather than merely unlikely.
- **Unmatched settlements no longer vanish.** A closing row with no open lot fell
  off the end of the matcher and booked nothing - a settled-only sportsbook
  export (books offer exactly that download) silently dropped every dollar of
  winnings and produced a $0 escrow. Wager sides now book at zero cost basis and
  warn. Scoped to `BET_*` only; the frozen Polymarket/options paths are untouched.
- **`BET_CASHOUT` added.** A partial cashout booked as `BET_LOSS` recorded the
  whole stake as lost: cashing $100 out at $60 is a $40 loss, not $100.
- **W-2G credit is federal-only.** The draft netted federal withholding against a
  composite rate that includes state tax and the safety buffer - crediting the
  bettor with money the state never received, and moving the reserve DOWN on an
  assumption. Credit is now capped at the federal legs; overwithholding is
  reported as `gambling_w2g_surplus` (a refund receivable) instead of silently
  absorbed. See `gambling.w2g_credit_scope` to restore the old behaviour.
- **OBBBA 70114 (the 2026 90% loss haircut) implemented.** Absent from the draft
  and material: break even at $100k in / $100k out and $10,000 of phantom taxable
  income now exists. Config-driven and dated - `loss_deduction_pct: 1.0` restores
  pre-2026 behaviour in one line if the FAIR BET Act repeal lands.
- **Statutory SE tax** (92.35% factor, SS wage-base cap, 164(f) half deduction)
  replaces a flat 15.3% on net profit; 165(d) now also caps a professional's
  losses AND expenses at winnings.
- **Session netting groups by day AND book** (AM 2008-011 describes one
  establishment), not by date alone.
- **`engine/gambling_tax.py` is new** - the statute as pure arithmetic, no
  SQLite, unit-tested on numbers. **`engine/odds.py` is new** - American /
  decimal / fractional normalisation plus a payout-vs-odds consistency check.
  `implied_probability` there is the seam Item 2 (no-vig engine) attaches to.

## PREVIOUSLY FROZEN FOR Q1 LIVE DEPLOYMENT (2026-09-03)

Milestone `v1.1-q1-live`. 612 tests passed (375 agent + 237 Monarch), all offline.
Core ledger (`lot_engine.py`, `tax_calculator.py`, `db.py`) had been frozen since
Round 8. Every transport verified against live endpoints.

Read "Decisions worth re-litigating" and "Next / open questions" before changing
anything: several defaults look conservative by accident and are not.

## Status

Local-first tax escrow + safe bankroll accountant. Deterministic, no paid APIs, no
LLM calls at runtime. Architecture, SQLite layer, FIFO engine and the first two
tests are Antigravity's; the CTF chain ingestor, CSV watcher and Monarch hook are
Claude Code's (2026-09-02).

375 tests pass, all offline:

```
python -m unittest Tax_Reserve_Agent.tests.test_agent Tax_Reserve_Agent.tests.test_new_features
```

| File | Role |
|---|---|
| `database/db.py` | SQLite schema: `transactions`, `tax_lots`, `realized_pnl` |
| `engine/lot_engine.py` | FIFO lot matching, realised P&L |
| `engine/tax_calculator.py` | Escrow sizing, safe bankroll |
| `engine/gambling_tax.py` | IRC 61/165(d)/1402 + OBBBA 70114 rules (pure, no DB) |
| `engine/odds.py` | Odds normalisation + payout consistency check |
| `ingestors/sports_betting.py` | Wagers, settlements, sportsbook CSV exports |
| `ingestors/keccak.py` | Pure-Python Keccak-256 (derives CTF event topics; no web3 dep) |
| `ingestors/polymarket.py` | REST path + `PolymarketChainIngestor` (CTF logs, CLOB subgraph) |
| `ingestors/csv_watcher.py` | `data/imports/` drop-folder ingestion |
| `ingestors/market_resolution.py` | `resolve-markets`: settles lots in markets that resolved |
| `engine/loss_harvester.py` | `harvest`: underwater lots ranked by real tax saved |
| `interfaces/tax_calendar.py` | `calendar`: IRS estimated-tax periods and escrow release |
| `interfaces/monarch_hook.py` | order gate, per-category Kelly sizing, strategy capital buckets |
| `interfaces/monarch_hook.py` | Order-sizing gate for the Polymarket Monarch bot |

## What changed (2026-09-02, Claude Code)

- **`engine/lot_engine.py` — duplicate-transaction bug fixed.** `INSERT OR IGNORE`
  leaves `cursor.lastrowid` holding the *previous* successful insert's id, so the
  `if not tx_id` duplicate check never fired and a re-imported transaction was
  replayed through the lot engine — minting a second tax lot and a second
  `realized_pnl` row. Re-dropping one CSV export doubled the year's gains
  (verified: 1200 → 2200). Now keyed on `cursor.rowcount == 0` with an early
  return. This is the only pre-existing file whose logic changed.
- **`ingestors/polymarket.py`** — appended the on-chain layer: `CTFEventDecoder`
  (pure ABI decode of `PositionSplit` / `PositionsMerge` / `PayoutRedemption`),
  `PolygonRPCClient` (chunk-halving `eth_getLogs`, batched block timestamps,
  `payoutNumerators` reads), `PolymarketSubgraphClient` (paginated CLOB fills),
  `PolymarketMarketResolver` (Gamma metadata + disk cache), and
  `PolymarketChainIngestor`. The original `PolymarketIngestor` is untouched.
- **`ingestors/csv_watcher.py`, `interfaces/monarch_hook.py`** — new, per the brief.
- **`main.py`** — new commands `chain-sync`, `import`, `watch`, `bankroll`.
- **`config.yaml` / `config.py`** — new `chain`, `imports`, `bot_integration` sections.
- **`tests/test_new_features.py`** — 38 offline tests (synthesised ABI log blobs,
  temp DBs, no network).

## Gambling module - decisions worth re-litigating

- **`loss_deduction_pct: 0.90` is defaulted ON for 2026.** OBBBA 70114 amended
  165(d) for tax years beginning after 2025. It has been the target of repeal
  bills. If it was repealed, set it to `1.0` - one line, and the escrow drops.
  Nothing in this repo can verify current law; check before filing.
- **`seca.social_security_wage_base: 184500` is an ESTIMATE.** Confirm each
  January. It only binds a professional netting six figures.
- **`federal_ordinary_rate` is blank by default**, so the federal leg falls back
  to `tax_rates.short_term_capital_gains` - which config.yaml documents as
  ALREADY blending federal and state. That overstates the federal leg and so
  over-credits W-2G withholding. Setting your true marginal rate makes the
  credit exact; leaving it blank is the looser reading.
- **Orphan settlements book at ZERO cost basis.** The stake is not deducted, so
  the base is overstated - deliberately, since the alternative was losing the
  income entirely. Import the placement rows and the figure corrects itself.
- **Winnings are measured per-wager, not per-session, by default.** Proceeds net
  of that wager's own stake (the Reg. 1.6041-10 / W-2G measure). `session_netting`
  is available but is a different reading, and it reserves less.
- **A parlay with a voided leg is assumed to be repriced by the book** and
  settled once at the new payout - which needs no special handling.
  `create_partial_void_settlement` exists for books that instead refund pro rata.
- **No brackets, no AGI phase-outs, no standard-deduction amount.** This sizes an
  escrow at flat marginal rates; it is not a tax preparer.

## Decisions worth re-litigating before trusting the numbers

- **Split basis is allocated equally** ($0.50/$0.50 binary), not by market price
  at split time — a price oracle for a moment that may have no trade is not
  deterministic. Override via `config.yaml -> chain.split_basis_allocation`.
- **Merges and redemptions are written as `SELL`, not `MERGE`/`REDEEM`.** The FIFO
  engine only closes lots for a fixed set of sides; a `MERGE` side would be
  recorded and then silently skipped by the lot matcher. Provenance is in `notes`
  and the on-chain `tx_hash`.
- **`tx_hash` is written as `<hash>#<logIndex>#<indexSet>`.** The ledger's UNIQUE
  key is `(source, tx_hash, symbol, side)` and one Polygon tx routinely holds
  several fills of the same market and side. Bare hashes would collide and drop
  all but the first.
- **Losing outcomes emit no chain event.** Their loss is realised by
  `resolve-markets`, not by the log sync. Until that runs the escrow is
  overstated (safe direction, still wrong).
- **`resolve-markets` settles a condition’s legs together, and defaults to a dry
  run.** Writing off only the losing leg of a split-and-hold invents a loss that
  never happened, which lowers the escrow and leaves the reserve SHORT — the one
  direction of error that costs real money. `--losers-only` forces the narrow
  behaviour if it is ever wanted; `--trust-gamma` drops the on-chain payout
  verification and warns.
- **A redemption with no readable payout ratio** falls back to $1.00/share and
  tags the note `NEEDS-REVIEW` rather than presenting the assumption as measured.

## What changed (2026-09-02, Claude Code — Round 2)

Antigravity audited Round 1 (ABI decoder, topic derivation, the `rowcount` fix and
the hook suite all verified). Round 2 closed the three gaps that audit left open.

- **Monarch now calls the hook.** New `Polymarket/Polymarket_Monarch/tax_gate.py`
  is the single coupling point (path bootstrap, import guard, `TaxGate`,
  `add_tax_arguments`). `dutched_arb.py` clamps `--shares` through it *before*
  walking the book — depth pricing a size the bankroll cannot fund produces an
  executable share count and a profit figure for a trade that was never
  placeable. `terminal_dashboard.py` carries the escrow line in its header
  (header `size` 4 -> 5).
  The shim fails OPEN and says UNGATED, unlike the hook itself which fails
  closed — Monarch places no orders, so refusing to scan because an accounting
  DB is missing would be absurd. Anything that actually sends an order must use
  `MonarchBankrollHook.check_order()` directly and honour its rejection.
- **Reorg horizon.** `PolygonRPCClient.safe_block_number()` prefers the
  `finalized` tag, else head minus `REORG_SAFETY_BLOCKS` (64).
  `block_ceiling()` caps an explicit `--to-block` at that horizon rather than
  honouring it. Configurable via `chain.confirmations`.
- **`resolve-markets`.** New `ingestors/market_resolution.py` with
  `MarketResolutionSync`; `build_loser_writeoffs()` is now a thin wrapper over a
  general `build_settlements()`.

## What changed (2026-09-02, Claude Code - Round 3)

Antigravity's V2 roadmap, all four items.

- **WAL + `busy_timeout=5000`** in `database/db.py`, plus a new `agent_meta`
  table and `set_meta()` / `get_meta()`. `synchronous` deliberately left at FULL
  (see below). WAL is applied once per db path, and a filesystem that refuses it
  warns instead of failing.
- **HIFO** alongside FIFO via `accounting.method`. Required splitting the lot
  matcher out of `process_transaction()` into `apply_to_lots()` so the new
  `rebuild_lots()` can replay the ledger - the insert path early-returns on the
  UNIQUE constraint, so a replay through it would have been a silent no-op on
  every row. `lot_ordering()` is the whole method: both orderings end in
  `id ASC` so a rebuild reproduces the original match on ties.
- **`engine/loss_harvester.py`** - `harvest`. Marks come from `data/marks.csv` or
  an injected price source; unmarked positions are excluded, never guessed.
- **`interfaces/tax_calendar.py`** - `calendar`. IRS estimated-tax periods
  (Q2 is two months, Q4 is four and due in January), weekend rollover, and the
  escrow split into past-due versus still-reserved.
- **`main.py`** - `harvest`, `calendar`, `rebuild` (+ `--method`, `--marks`,
  `--live-marks`). **`interfaces/cli.py`** - HUD prints the method and warns on drift.
- **`tests/test_new_features.py`** - +41 tests (113 in file, 115 total).

## Decisions worth re-litigating (Round 3)

- **`synchronous=FULL` kept.** The standard WAL recipe pairs it with NORMAL for
  speed, at the cost of possibly losing the last commits on a power cut. This
  ledger is written a few times a day; the speed is worth nothing and the
  durability is worth a lot. Do not "optimise" without a reason.
- **A method switch is surfaced, never auto-corrected.** `calculate_tax_summary()`
  returns `method_mismatch` and the HUD prints it, but nothing rebuilds behind
  your back - a silent re-match would change every historical number in the
  ledger without anyone asking for it.
- **Carried-forward losses are valued at ZERO** in the harvest estimate. They are
  worth something in a future year and nothing this April; conflating the two is
  what makes naive harvest tools overstate a flat-year harvest by 10x.
- **A losing quarter does not refund an earlier one.** Each estimated-tax period
  is priced on its own gains, clamped at zero. The annual netting is already
  reflected in the escrow figure; letting a Q3 loss cancel tax that fell due in
  April would understate what is owed right now.
- **Harvest marks are never invented.** An unmarked position is excluded from
  every total and listed separately.

## What changed (2026-09-02, Claude Code - Round 4: LIVE ENDPOINT FIXES)

Antigravity probed the live endpoints and found two dead transports. Both
confirmed independently, and probing turned up three more problems that only
appear against real infrastructure.

- **Polygon RPC was a single hardcoded URL that started 401ing.** Replaced with
  an ORDERED LIST plus failover (`DEFAULT_POLYGON_RPC_ENDPOINTS`), because
  swapping one hardcoded URL for another just resets the clock on the same
  failure. Measured 2026-09-02: publicnode 200/46ms, drpc 200/79ms,
  1rpc 200/165ms, polygon-rpc.com 401, ankr 200-with-an-error-body,
  **llamarpc does not resolve** (it was one of the two suggested replacements -
  do not use it). `allow_fallback=False` pins a private node.
- **REORG GUARD WAS SILENTLY VOID.** `safe_block_number()` preferred the node's
  `finalized` tag. Live, publicnode reports finalized = head-4 and drpc head-3 -
  not Polygon finality, since Heimdall milestones run every ~16-32 blocks - so
  the sync would have read to within 4 blocks of the tip. 1rpc reports head-500.
  Now takes the MINIMUM of `finalized` and head-minus-confirmations, so the
  64-block floor always holds and a genuinely stricter node is still honoured.
  This bug survived both a design review and an audit because it was only ever
  exercised against a fake RPC.
- **Goldsky subgraph 404s.** CLOB fills now come from the Polymarket Data API
  (`PolymarketDataAPIClient`), which is a better source anyway: rows carry
  `slug`, `outcome` and `conditionId`, so fills name themselves through
  `canonical_symbol()` with no Gamma round trip and no dependence on a warm
  metadata cache. `PolymarketSubgraphClient` is kept but is now opt-in - it is
  only constructed when `chain.orderbook_subgraph_url` is set.
- **Keccak test was hollow.** `test_multi_block_input` only asserted the digest
  was 32 bytes, which every broken implementation also satisfies. The sponge is
  now factored out with the domain byte as a parameter, and the test pins it
  against `hashlib.sha3_256` across 13 sizes spanning 31 rate blocks - the
  permutation, absorb loop and padding are shared, so agreement at 0x06 is real
  evidence for the 0x01 path.
- **`eth_getLogs` span cap is learned once**, not rediscovered per topic
  (publicnode caps at 10,000 and only says so by erroring).

### Three things measured on the Data API that changed the parser

1. **Fills are PRE-AGGREGATED** - zero `(transactionHash, asset, side)`
   collisions across 500 live rows, so no log-index disambiguator is needed.
2. **`outcomeIndex` is unreliable** - the sentinel 999 on 32 of 500 rows (6.4%).
   The `outcome` STRING is used instead; anything keyed on the index would
   mislabel one position in fifteen.
3. **There is no `fee` field on any row.** Fees are booked as 0.00, so cost basis
   is gross of Polymarket fees. That over-states gains and therefore the escrow -
   the safe direction, but an approximation, not a measurement.

### Live end-to-end, first time

`sync_wallet()` against a real Polymarket wallet: RPC failover picked publicnode,
safe head lagged the tip by exactly 64, the Round 1 chunk-halving absorbed the
undocumented 10k cap, and 85 transactions came back with unique keys and readable
symbols. 100 live Data API trades parsed to 100 ledger rows, ran through the FIFO
engine, and re-imported idempotently.

### Self-inflicted regression, caught and fixed

The span-cap cache first remembered the span of any SUCCESSFUL call. The last
chunk of a range is often one block, so it latched onto 1 and later queries
crawled the chain block by block - a seconds-long sync ran past four minutes.
Only a REJECTION tells you the node's cap. `TestLogSpanCap` pins this.

## What changed (2026-09-02, Claude Code - Round 5)

Antigravity's live-probe patch list. Item 1 was already done in Round 4; the other
three are new.

- **RPC endpoints** - already an ordered list with failover from Round 4; verified
  no dead endpoint is referenced anywhere outside explanatory comments, and
  re-probed all three live. Order kept as publicnode -> drpc -> 1rpc rather than
  the suggested publicnode -> 1rpc -> drpc, because drpc measured consistently
  faster (73-79ms vs 147-165ms) and is the better first fallback.
- **Data API paging race fixed.** `fetch_trades()` now keys every row on
  `transactionHash|asset|side` and de-duplicates across pages, reporting the
  count. The feed is newest-first, so a trade landing mid-walk pushes older rows
  to a higher offset and the next page re-serves them - Antigravity measured 15
  repeats in a 2,000-trade walk. Worth noting the drift can only OVERLAP, never
  gap: rows shift down because entries are inserted at the head and trades are
  never deleted, so nothing slips past a boundary unseen. Duplicates are the whole
  failure mode and de-duplication is the whole fix.
- **Proxy-wallet detection.** `warn_if_probably_not_a_proxy_wallet()` fires when a
  wallet yields on-chain CTF rows but ZERO CLOB fills - the signature of an EOA
  configured instead of the Gnosis Safe proxy that `/trades?user=` matches. That
  combination silently builds cost basis from redemptions with no purchases behind
  them. Fills-without-chain-rows stays silent: a pure CLOB trader who never split
  or redeemed is perfectly normal.
- **Multi-block Keccak KAT added.** Three hardcoded digests at 200 / 430 / 1024
  bytes (2 / 4 / 8 rate blocks). PROVENANCE MATTERS HERE: they were NOT produced
  by the implementation under test, which would be circular. Each was generated by
  two independent C implementations - pycryptodome 3.23.0 and `eth_hash.auto` -
  which agreed with each other first. Neither is a runtime dependency; nothing in
  the package imports them. This sits alongside, not instead of, the
  `hashlib.sha3_256` sponge cross-check.

### Live re-verification

1,586 trades pulled across 8 pages from a real wallet: zero duplicate keys in the
output, 1,586 unique ledger rows. That also lifts the evidence for Data API fill
pre-aggregation from 500 rows to 1,586 with no `tx+asset+side` collision.

## What changed (2026-09-02, Claude Code - Round 6)

Antigravity sent three patches. Two were real; the third was already implemented,
and adding it where proposed would have double-counted. Running the fixes
end-to-end then exposed two further bugs no unit test could have caught.

- **GAMMA DEFAULTS TO `closed=false` AND DOES NOT SAY SO.** A lookup by
  `condition_ids` or `clob_token_ids` returned ZERO rows for any resolved market.
  `resolve-markets` was therefore completely non-functional - every resolved
  condition read as "no Gamma record" and nothing was ever settled - while all 16
  of its unit tests passed, because they drive a fake resolver. The same
  fake-only blind spot that hid the reorg bug. `_fetch()` now retries an empty
  result with `&closed=true`; open markets still answer on the first request.
- **`max_pages` truncation now warns.** A full final page means unreached history;
  silence handed a high-volume wallet a ledger missing its oldest trades, which
  removes cost basis and reads as higher gains.
- **Fee capitalisation was ALREADY CORRECT** in `lot_engine.py` - basis + fee on
  acquisition, proceeds - fee (pro-rated across matched lots) on disposal, proven
  empirically. It was NOT added to `tax_calculator.py` as proposed: that module
  only aggregates finished `realized_pnl` rows, so applying fees there again would
  double-count them. Pinned instead with five regression tests.
  The real gap behind the concern is that the Data API reports no fee at all, so
  Polymarket basis is gross of fees. Added an OPT-IN `chain.polymarket_fee_rate`
  (default 0 = off) that books a clearly-labelled ESTIMATE - a guessed number in a
  tax ledger is the same mistake as a guessed market price.

### Two more bugs, found only by running it

- **Gamma publishes the LAST TRADE, not the payout.** Across 300 closed markets a
  resolved winner reads 0.9999989 and the loser 1.01e-06, while on-chain
  `payoutNumerators` returns [0.0, 1.0]. So "sums to 1.0" was never a test for
  resolution - a market that merely stopped trading at a final mid of
  [0.97, 0.03] sums to 1.0 too, and `--trust-gamma` would have booked a fabricated
  97%/3% settlement. `gamma_payout_ratios()` now requires every value within 1e-3
  of a clean 0 or 1 with exactly one winner, and snaps to exact 0.0/1.0. 19 of 300
  markets the loose rule accepted are now correctly refused; the three
  cross-checked against chain match exactly.
- **The Data API path never populated the metadata cache.** It builds symbols from
  a trade row without asking Gamma, so after a `chain-sync` the cache was empty and
  `resolve-markets` could not map a single position back to its condition. Fills
  now record a `symbol:` -> condition link. The outcome INDEX is deliberately not
  stored with it (a row's `outcomeIndex` is the sentinel 999 on ~6% of rows, and
  picking the wrong leg settles a winner as worthless) - it is derived at
  settlement time from Gamma's authoritative `outcomes` order via
  `outcome_index_for_symbol()`.

### `resolve-markets` verified end-to-end, first time

Against `will-kim-kardashian-and-kanye-west-divorce-before-jan-1-2021`:
chain-verified payouts, correct winner (NO), resolution dated 2021-01-02, booked
into tax year 2021, split-and-hold settling to exactly $0.00 net.

## What changed (2026-09-02, Claude Code - Round 6b: cold cache)

Antigravity's follow-up repeated three patches already delivered in Round 6
(Gamma `closed=true` retry, `max_pages` warning, fee capitalisation) and added one
genuinely new finding - the one raised in the Round 6 cross-check prompt.

- **COLD-CACHE BLINDSPOT.** `loss_harvester._token_for_symbol()` and
  `market_resolution.symbol_to_condition()` both read `resolver._cache` and
  nothing else. On a fresh checkout, a CSV-built ledger, or a cleared cache file
  that cache is EMPTY, so `harvest --live-marks` priced nothing and
  `resolve-markets` mapped nothing. Neither errored - the reports were silently
  blank, which is the worst failure shape available.
- **New `PolymarketMarketResolver.resolve_symbol()`**, three routes cheapest
  first: a recorded `symbol:` link (free, carries the CLOB token id); a
  `CTF-<prefix>-<indexSet>` symbol (the index set is fully encoded, so the outcome
  index needs no lookup); or an on-demand Gamma `?slug=` lookup, trying split
  points right-to-left because the slug itself contains hyphens.
- **`remember_symbol()` now stores the token id** and is called from the CTF
  split/merge/redemption paths as well as the Data API parser - a wallet that only
  splits and redeems never produces a CLOB fill and would otherwise stay
  unresolvable.

### One part of the brief was not implementable as written

"Parse `condition_id` directly from the `CTF-<cid>-<indexSet>` symbol" cannot be
done: `canonical_symbol()` truncates the condition id to **10 of 64 hex
characters**, and 40 bits of a 256-bit id are not reversible. What IS recoverable
is the index set, so the outcome index comes back free. The condition id is
matched against conditions already known and otherwise reported empty rather than
guessed - settling against a plausible-looking wrong market is far worse than
skipping. Recording the link at write time (now on every path) stops the situation
arising for anything synced from here on.

### Verified live on a cold cache

`resolve_symbol` mapped a symbol to the right condition, outcome slot and token
from zero cache entries; `resolve-markets` settled a CSV-style ledger 2 settled /
0 skipped; `harvest --live-marks` returned a real CLOB midpoint (0.0455) for an
active market, having previously returned None for everything.

## What changed (2026-09-02, Claude Code - Round 7)

Antigravity's strategy proofs arrived (escrow gating is over-Kelly protection; a
2% round trip on a 3% edge is a 105% effective tax rate; category sizing on
shrunk win rates). Four implementation items, three of which needed correcting.

- **Negative cache is SESSION-SCOPED, not written to `_cache`.** The brief said
  `self._cache[f"negative:{symbol}"] = True`, but `_cache` is persisted by
  `save()` - so one Gamma outage would permanently blacklist a real market, and
  the symptom would appear weeks later as a position that silently refuses to
  resolve. It lives in an in-memory `_unresolvable` set instead, costing one
  wasted lookup per process and self-healing on restart.
- **Legacy CTF recovery does NOT read `transactions.notes`** as briefed: notes
  carried only 12 hex characters, exactly as the symbol carries 10 - both
  prefixes of the same string, so combining them recovers no extra bits. What
  works is re-reading the original log from chain via the row's real transaction
  hash and log index (`recover_condition_id()`). Notes now also carry the FULL
  condition id, so the problem does not recur.
- **Category sizing uses a WILSON LOWER BOUND, not `p - sqrt(p(1-p)/N)`.** The
  briefed shrinkage term is ZERO when p is 0 or 1, so three wins from three trades
  returns 1.0 - full certainty from three observations - and sizes at the maximum,
  which is the exact opposite of conservative and fires hardest at small N. Wilson
  returns 0.75 there and converges on the naive answer once the sample is real
  (70/100: 0.6524 vs 0.6542), so it costs nothing where the naive form was safe.
- **Kelly needs a price.** `f* = (p - q) / (1 - q)` for a share bought at q paying
  $1. `check_order(category=..., price=...)` uses the order's own price; without
  one it falls back to the category's historical average entry.
- **Empirical sizing only TIGHTENS by default.** `max_position_pct` is a limit a
  human set; a win rate estimated from that human's own trades is
  survivorship-prone and noisy, and letting it raise the ceiling means the sizer
  bids hardest right after a hot streak - the over-Kelly failure the escrow gate
  exists to prevent. `bot_integration.allow_empirical_upsize` opts into the full
  1-8% band.
- **`categorise()` matches whole tokens, not substrings.** Found by its own test:
  "SOM**ETH**ING" matched crypto, "AB**SOL**UTELY" would too. A mis-categorised
  symbol is sized off another market type's win rate, silently.

### Item 4: multi-outcome settlement, investigated on live data

7% of closed markets (28 of 400) carry 3-7 outcomes, so this is not a corner case.
Verified end-to-end:

- **Winner-take-all across 3 outcomes**: settles correctly, net exactly 0.0000 for
  a full set bought at 1/3 each.
- **Genuine FRACTIONAL resolution**: `how-many-charges-will-derek-chauvin-be-convicted-of`
  pays 1/3 on every leg on chain. The chain path settles it exactly; Gamma returns
  a vector `gamma_payout_ratios` correctly refuses, so `--trust-gamma` skips it
  rather than fabricating a winner. The safety ordering works.
- **Combinatorial index sets** (a position spanning several slots, e.g. index set
  3) keep the raw `CTF-` form, cannot be matched to one outcome, and are SKIPPED -
  never mis-settled onto one of their legs.
- Negative-risk EVENTS decompose into one binary sub-market per outcome, each with
  its own condition id, so they settle through the ordinary binary path.

## What changed (2026-09-02, Claude Code - Round 8: final polish)

Core tax engine FROZEN per Antigravity sign-off. Three sizing items plus the
break-even filter.

- **Magnitude-adjusted Kelly.** `f* = max(0, (p(b+1) - 1)/b)` with
  `b = R+ / R-` measured per dollar of basis actually risked. This closes the hole
  raised in the Round 7 cross-check: a book winning 60% at +0.05 and losing 40% at
  -0.40 has a fine win rate and loses money, and the old win-rate-only sizer would
  have GROWN it. It now sizes to zero and `check_order` rejects it outright.
  Verified: same 60% win rate, profitable magnitudes -> 7.6%; losing magnitudes ->
  0.0% and rejected.
- **Payoff ratio is capped** at 10 when a category has no losses yet - an unbounded
  b would size at the ceiling off a lucky streak.
- **A priced order takes the TIGHTER of two payoff ratios**: what the order could
  pay held to resolution, `(1-q)/q`, and what the category has historically paid.
  They differ because traders exit early - a 10c share offers b=9, but a book that
  habitually takes profit at 15c has never captured it, and sizing on the
  theoretical payoff bets on a return the operator does not actually take.
- **Rolling window, 40 most recent completed trades per category.** Verified: with
  60 old wins then 20 recent losses, a 40-trade window sizes at 1.4% while an
  unbounded one sizes at 8.0% - the stale-regime problem, measured.
- **Break-even filter in `dutched_arb.py` (`--min-edge`).** Under gross-of-fees
  accounting `after_tax = e(1-t) - f`, so break-even is `f/(1-t)`: 3.08% at a 2%
  round trip and a 35% rate, against 2.00% if fees were captured. THE 1.08pp GAP
  IS THE COST OF NOT RECORDING FEES - a third of the threshold. A 2.5% "arbitrage"
  clears its fees and still loses after tax, and that is exactly the trade the
  scanner would otherwise surface.

### VWAP was already correct

Item 3 asked for volume-weighting. `basis/qty` is sum-of-value over sum-of-quantity
- already VWAP. My own Round 7 cross-check prompt called it an arithmetic mean;
that was wrong about my own code. No change needed, now labelled in the report.

### Two fee numbers, deliberately

`chain.polymarket_fee_rate` writes into the LEDGER and stays 0 by default - a
guessed number in a tax record is the same mistake as a guessed market price.
`bot_integration.assumed_round_trip_fee` defaults to a real 2% and is used ONLY by
the break-even filter, which is a decision aid that is never written down. Tying
the filter to the ledger rate would have left it inert exactly when it matters. A
measured ledger rate overrides the assumption.

## What changed (2026-09-02, Claude Code - Round 9: Phase 2 sizing)

Three of the four sprint items had already shipped in Round 8 (magnitude Kelly,
rolling window, VWAP). Genuinely new: the minimum-sample gate, the strategy tag,
and the consensus_scanner break-even wiring.

- **Minimum-sample gate, N >= 5.** Below it the empirical sizer does not engage at
  all and the flat percentage applies. Wilson shrinks a small sample hard, but
  shrinking is not abstaining - three observations still produce a number that
  moves money. The observed count is still reported, so the category reads as
  unmeasured rather than absent.
- **`strategy` tag on `check_order()` / `size_order()` / `BankrollDecision`**,
  passed through `tax_gate.clamp_shares()`. `consensus_scanner` tags its copies
  `consensus_copy`.
- **`consensus_scanner` break-even filter.** It has no "spread", so the edge had
  to be defined: buying at `ask` returns $1 if the thesis lands, so the expected
  gross edge per dollar is `(p - ask) / ask`. New `expected_edge()` plus a
  `skipped_below_breakeven` counter, distinct from the existing priced-in guard -
  a signal can be perfectly fresh and still not clear 3.08%.
- **`payoff_basis` config** (`conservative` default | `price` | `realized`).

### The one place I did not follow the brief

Item 1 says "use the prospective order price q to define contract payoff
b = (1-q)/q". That is only half a pair. `p_wilson` is measured as *what fraction of
CLOSED trades were profitable* - an exit-behaviour statistic - and most of those
trades were exited early, never collecting the full $1. Pairing that p with the
hold-to-resolution payoff mixes two populations and OVERSTATES f* for anyone who
scalps; the self-consistent pair is (realised p, realised b).

The default stays `conservative` = min(price-implied, realised), which equals
`realised` except when an expensive order caps it lower - correct, since a 90c
share pays b = 0.11 regardless of history. The brief's exact behaviour is
`bot_integration.payoff_basis: "price"`, one config line away. Measured on a
scalping book (0.10 -> 0.15 wins), `price` sizes materially larger than `realized`,
which is the overstatement the argument predicts.

Also kept, against the briefed signature: **`already_deployed`**. The brief's
`check_order` signature drops it, but it is what stops a burst of orders inside one
cache window each claiming the same dollars. `strategy` was added alongside it
rather than in place of it.

### Frozen ledger untouched

`lot_engine.py`, `tax_calculator.py` and `db.py` were not modified this sprint.

## What changed (2026-09-02, Claude Code - Round 10: freeze)

- **Sharp win rates are Wilson-shrunk** in `consensus_scanner` before the edge is
  computed. The roster selects wallets FOR having won (`MIN_WIN_RATE = 60`,
  `MIN_REALIZED_PNL = $5,000`), so the raw rate is a survivorship artefact and
  using it made the filter too permissive - the wrong direction for something
  whose job is to reject. Signals now carry `aggregate_closed` so there is a
  sample size to shrink against. Measured: 70% over 12 closed positions at a 0.60
  ask goes from a 16.7% raw edge (clears) to NEGATIVE (rejected); 70% over 300
  barely moves.
- **Copied trades derive a category** via the same `categorise()` the bot orders
  use, so a copy is subject to the measured drawdown clamps rather than the flat cap.
- **Break-even is fail-SAFE, not fail-open.** `dutched_arb` previously passed
  `0.0` as the fallback, so an unreachable agent silently disabled the filter and
  surfaced sub-break-even "arbitrage". Both scanners now fall back to
  `FALLBACK_AFTER_TAX_EDGE = 0.0308` and say so on stdout.
- **`payoff_basis: "min"`** accepted as an alias for `conservative`, matching the
  name the backtest reports under.

### The backtest, reproduced and extended

`scratch/backtest_sizing.py` reproduces exactly (210 round-trips, `min` best at
22.88% DD / 0.0365 Calmar). Two things worth recording:

- **The harness does not model the shipped zero-clamp.** Its
  `min(0.05, max(0.01, 0.25*f))` floors a negative-expectancy category at 1%,
  while the implementation clamps it to 0. Re-running with the real behaviour:
  max DD **22.88% -> 10.74%**, Calmar **0.0365 -> 0.0797**, final $57,362 ->
  $59,992. `min` remains the best basis under both. So the shipped numbers are
  BETTER than the ones signed off, not worse.
- **That clamp refuses 98 of 210 trades (47%).** Worth knowing before live
  deployment: the sizer is not trimming those, it is declining them outright.
- The harness is one wallet fetched live, so it is not reproducible over time, and
  it models no fees or tax - it compares sizing in isolation.

## What changed (2026-09-03, Claude Code - Phase 3 task 1: capital buckets)

The Phase 3 sprint message arrived TRUNCATED mid-YAML - task 1 only, tasks 2+
unknown. Task 1 is delivered in full; the rest is outstanding.

- **`bot_integration.strategies`** ring-fences each strategy's slice of the SAFE
  bankroll. An empty block disables bucketing entirely and restores pre-Phase-3
  behaviour, so nothing existing changed until someone opts in.
- **Allocations above 100% are scaled down, not honoured.** A total of 130% does
  not mean 130% exists - it means every bucket is 30% larger than the operator
  believes. Below 100% is left alone: the shortfall is unallocated reserve.
- **The per-order cap is a fraction of the BUCKET, not the bankroll.** 5% of a 20%
  sandbox is 1% of the book. Sizing off the whole bankroll would make
  "quarantined" cosmetic.
- **An unrecognised strategy is QUARANTINED into `sandbox`, not given the
  default.** `default` counts as unrecognised under an enforced regime - it is the
  tag on every order that never named a strategy, precisely the unclassified
  traffic sandboxing exists for. With no `sandbox` bucket, an unknown strategy
  gets $0 and is rejected.
- **`already_deployed` is now per-strategy.** The caller still owns that state:
  this hook is read-only, and a second source of truth for live exposure would be
  worse than none.

## What changed (2026-09-03, Claude Code - Phase 3 tasks 2 & 3)

- **Over-allocation now HARD-FAILS** (`StrategyAllocationError`) instead of
  scaling down. It is its own exception type so callers can tell a
  misconfiguration from an outage - they need opposite handling.
- **AND THE SHIM NOW FAILS CLOSED ON IT.** `tax_gate` catches every construction
  error and degrades to UNGATED, which is right for an outage and catastrophic
  for a bad capital plan: a typo totalling 110% would have turned off ALL sizing
  protection. A `StrategyAllocationError` now sets `fatal_config_error` and
  `clamp_shares()` returns 0 shares. Outages still fail open, as designed.
- **Strategy attribution rides in `transactions.notes`** as `strategy:<name>;`,
  leaving the frozen schema alone. The trailing `;` is load-bearing: matching
  `%strategy:sandbox%` would also match `strategy:sandbox_v2` and pool a new
  strategy's exposure into the bucket it was quarantined from.
- **`get_strategy_open_exposure()` measures open cost basis from the ledger**, and
  `check_order()` folds it in when the caller passes 0. This closes the Phase 3
  task 1 hole: bucket ceilings no longer depend on caller bookkeeping.
- **`main strategies`** reports budget, open exposure, closed lots, realised P&L,
  win rate and Wilson expectancy per strategy, flagging any bucket over budget.
- **`strategies/base.py`** - `BaseStrategy` ABC and `Opportunity`. `min_edge`
  defaults to the after-tax break-even (never 0), `opportunities()` applies the
  hurdle centrally so a forgotten filter cannot become an unguarded path, and
  `validate()` warns when an override sits below break-even.

## What changed (2026-09-03, Claude Code - Phase 4)

### The brief's fee premise was inverted, and dangerously so

It said `/fee-rate` returns `{"base_fee": 0}` on standard event markets, so a 0%
fee should drop the hurdle to 0% and unlock "zero-fee event arbitrage". Probed
live on 2026-09-03:

- `/fee-rate` returns **`base_fee: 1000` for essentially every market** - 23 of 25
  live tokens, one 0, one 404. It is a CONSTANT, not a rate. Read as basis points
  it implies a 10% fee and a 30% hurdle that rejects everything.
- Gamma publishes the real terms. Across 300 open markets: politics 4% (237),
  sports 3% (31), economics 5% (14), finance 4% (7), crypto 7% (6), no schedule
  (5). **295 of 300 have `feesEnabled: true`.** Fee-free markets are the rare
  exception, and implementing the brief literally would have zeroed the hurdle on
  the markets charging the MOST.
- Fees are PRICE-DEPENDENT: `rate * min(p, 1-p)`. On a 7% crypto book the true
  hurdle is **10.77% at a coin flip** and 0.43% at 2c. The flat 3.08% was 3.5x too
  LOW at mid prices and several times too HIGH in the tails.

`PolymarketFeeSource` reads Gamma's `feeSchedule` with a 1h TTL cache;
`fetch_clob_fee_rate()` and `breakeven_gross_edge(token_id=, price=)` use it.
**None stays distinct from 0.0** throughout - "unknown" falls back to the
assumption, "zero" means genuinely free. Collapsing them would remove the hurdle
exactly when the fee data is missing.

### The attribution loop was broken, and the round-trip test caught it

`log_execution_receipt()` writes a tagged fill into `data/imports/`. But
`csv_watcher`'s loaders built their own `notes` and DISCARDED the file's - so a
receipt written with `strategy:dutched_arb;` reached the ledger untagged, counted
against no bucket, and silently loosened every ceiling. `_carry_notes()` now
preserves a `notes` or `strategy` column on all three loaders. This was invisible
to inspection and only surfaced because the test ran a receipt through the watcher
into the ledger and checked the exposure came back.

Receipts use a uuid4 suffix, not a millisecond clock: two fills in the same
millisecond are normal and a collision would overwrite a real receipt.

### `main health`

Exit 0/1 for cron. Fires on an inverted category expectancy (measured on the
40-trade window, so it catches a RECENT turn rather than waiting for a lifetime
average) or an escrow ratio above 15%. An unmeasured category is explicitly NOT a
failure - alerting on absence of evidence trains people to ignore the alert.

## What changed (2026-09-03, Claude Code - final lock)

- **`holds_to_resolution` on the fee model.** A contract carried to settlement is
  redeemed against the CTF contract, not sold through the exchange, so only the
  entry pays a taker fee. `dutched_arb` sets it; scalping strategies do not. The
  default stays the two-leg charge - an undeclared strategy is assumed to trade
  out, and over-stating the hurdle declines a marginal trade rather than taking a
  losing one. Consequence: at 4% politics and 50c, a 4% edge is a LOSER if sold
  out and a WINNER if redeemed.
- **Fee curve switched to `2p(1-p)`.** The sign-off named a `p(1-p)` curve while
  the implementation used `min(p, 1-p)`. Both give 2.00% politics and 3.50%
  crypto at 50c - which is exactly why the stated anchors could not tell them
  apart - but at 10c they differ by 1.8x. `product` is now the default because it
  is the named curve AND uniformly the more conservative; `min` remains available
  via `FeeSchedule(curve="min")`.
- **Execution receipts can carry the chain tx hash**, formatted as the Data API
  writes it (`<tx>#<asset[:24]>`). Without that the receipt and the synced row are
  DIFFERENT keys and the same fill is counted twice - doubling cost basis and
  realised gains. The briefed UPDATE only helps once the keys match.
- **`backfill_strategy_tags()`** attaches a tag to a row already in the ledger
  untagged. Matched on the FULL unique key, not `tx_hash` alone: one Polygon
  transaction can carry several markets, and keying on the hash would stamp one
  strategy's tag onto another's position.

## Fee model validated on chain (2026-09-03)

Antigravity ran the fill reconciliation; I decoded the same transaction
independently and confirm it. Polygon tx `0x904ac954...99b121`, CTFExchangeV2,
block 93120661:

| | rate |
|---|---|
| actual on-chain fee | **2.5240%** |
| `2p(1-p)` x 5% (shipped) | 2.4998% - **delta +2.42 bps** |
| `min(p,1-p)` x 5% (rejected) | 2.4760% - delta +4.80 bps |

The curve we shipped is twice as accurate as the one it replaced, so switching it
at the last lock was the right call. A residual remains: the implied exact rate is
5.048% against a published 5.000%, which is consistent with rounding in the fee
computation but is not zero, and nobody should quote this model to the basis point.

**A second assumption was validated in the same transaction, unclaimed.** It
carried three fills - two MAKER legs that paid exactly ZERO fee, and one taker leg
carrying the whole charge. That is direct on-chain evidence for `takerOnly: true`,
which had been an untested inference underneath the entire
`holds_to_resolution` split.

Note for whoever decodes this next: CTFExchangeV2 does NOT emit the standard
`OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)`.
Its fill event is topic0 `0xd543adfd...` with 4 topics and 7 data words, and
`logIndex` in a receipt is BLOCK-scoped, not transaction-scoped. Both cost me a
wrong turn.

## `init --force` (2026-09-03, pre-deployment)

The deployment sign-off instructed the operator to run `main init --force` to
clear the demo ledger. THAT COMMAND DID NOT EXIST - argparse rejected `--force`,
and plain `main init` printed "[SUCCESS] Database initialized." while deleting
nothing. An operator who dropped the flag would have got a success message that
reads exactly like a wipe, and started Q1 on $1,542 of fabricated gains.

A blocker believed fixed is worse than one known open, so the command now exists
and does what the instruction implied:

  `main init`          reports what is actually there and that NOTHING was
                       deleted; points at --force.
  `main init --force`  copies the ledger to `tax_ledger.<timestamp>.bak`, THEN
                       clears the three tables, and reports both.

Archived rather than deleted outright: the demo rows this exists to remove are
indistinguishable from real ones once gone. Implemented in `main.py`, not
`db.py`, so the frozen schema module is untouched.

The live ledger has now been cleared. First readings against the empty book:
escrow 0.0%, safe bankroll $10,000.00, no category edges, `health` exit 0.

## Next / open questions

- **`--trust-gamma` refuses genuine fractional resolutions.** A scalar market
  settling 0.5/0.5 is indistinguishable from a final mid price in `outcomePrices`,
  so it is skipped rather than guessed. The on-chain path handles it exactly.
- **Category sizing is fitted to the user's own history**, so survivorship bias
  remains: only trades that were actually taken are measured. The 40-trade rolling
  window handles regime decay; nothing handles selection effects.
- **The fee curve is now VALIDATED to 2.42 bps** against a real fill (see above),
  but the residual implies 5.048% where 5.000% is published. Confirmed in shape,
  not exact in constant.
- **The two-leg default is still unmeasured.** A strategy that EXITS AS A MAKER
  pays nothing on the way out - the same transaction shows maker legs at zero fee
  - so its true hurdle is the one-leg figure. We charge two unless
  `holds_to_resolution` is set, which over-states the hurdle for any
  liquidity-providing exit.
- **The rebate (0.20-0.25) is deliberately not applied.** It is conditional on
  maker behaviour we do not model, and applying it would shrink the hurdle.
- **`takerOnly: true` is now CONFIRMED on chain** (two maker legs at zero fee in
  the validation transaction). The round trip still assumes taker on both legs,
  which over-states the fee for a strategy that rests orders.
- **Exposure is only measured for lots TAGGED at ingestion.** Anything written
  before Phase 3 carries no `strategy:` tag and counts against no bucket, so on a
  historical ledger exposure is under-stated and ceilings are looser than they
  look. There is no backfill - the tag records intent at trade time, which cannot
  be reconstructed after the fact.
- **`already_deployed == 0` is the trigger for a ledger lookup**, so a caller who
  genuinely has zero deployed cannot say so without also opting into the
  measurement. That is the safe direction, but it is a slightly odd API.
- **Shrinkage does not remove selection bias, it only prices sample size.** The
  wallets are still on the roster because they won; a large sample of a selected
  population is still selected. Nothing here can fix that.
- **`consensus_scanner`'s edge still uses the sharps' AGGREGATE win rate as p.** That is
  their hit rate across every market they have ever traded, not their rate on this
  market type, and those wallets were SELECTED for having won. The resulting edge
  is an upper bound - the filter is directionally right but optimistic.
- **The rolling window is a hard cut, not a decay.** Trade 40 counts fully and
  trade 41 not at all. An EWMA would be smoother; the cut is simpler to reason
  about and to test.
- **`assumed_round_trip_fee` is still an assumption** (2%). It drives only the
  scanner threshold, never the ledger, but a wrong value moves which trades get
  surfaced. Measuring real Polymarket fees would retire it.
- **`chain.polymarket_fee_rate` is a flat guess when enabled.** Polymarket fees
  vary; one rate beats zero for low-edge strategies but is not a measurement.
- **Symbol-to-condition mapping depends on the metadata cache.** A position
  imported before its market was cached has no condition id on record and is
  reported as unmappable. Re-running `chain-sync` on that wallet repopulates the
  cache; nothing does it automatically.
- **`chain-sync` now verified end-to-end against a live wallet** (Round 4), but
  `config.yaml` still carries the `0x000...0` placeholder - it has never been run
  against YOUR wallet. Note `user=` matches the PROXY wallet, not the EOA you
  sign with; an empty sync for an address you know trades is that mismatch.
- **Polymarket fees are not captured anywhere.** The Data API omits them and the
  CTF logs do not carry them, so every Polymarket cost basis is gross of fees.
- **`max_pages` silently truncates a very large history.** `fetch_trades()` stops
  at 60 pages (30,000 trades at the default page size) without saying so. A
  wallet past that limit gets a quietly incomplete ledger - it should warn when it
  stops on the page cap rather than on a short page.
- **De-duplication masks the paging race rather than removing it.** It is the
  correct fix for overlap, but if Polymarket ever changed the feed ordering or
  started deleting rows, gaps would become possible and nothing would detect
  them. Timestamp-cursor paging would be immune; offset paging is not.
- **Wash-sale rules are not modelled anywhere.** Fine for crypto/prediction
  markets today; a change in treatment would need lot-level replay - which
  `rebuild_lots()` now makes tractable.
- **Federal holidays are not in the tax calendar.** Emancipation Day shifts the
  April deadline in some years. Weekend rollover is handled; holidays are not.
- **Safe-harbour rules are not modelled.** The calendar shows what the year's
  realised gains imply, not the minimum payment that avoids a penalty.
- **A `CTF-<prefix>-` symbol written before Round 6b has no recoverable condition
  id.** Its outcome index resolves, but the market does not, so `resolve-markets`
  skips it. Re-running `chain-sync` re-records the link.
- **`resolve_symbol`'s slug search costs up to `max_split_attempts` Gamma calls**
  for a multi-word outcome. Cheap once (results cache), but a large cold ledger
  pays it per distinct market.
