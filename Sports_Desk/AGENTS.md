# Sports Desk - Agent Handoff

## Status

Items 2 and 3: fair-value engine + odds ingestion. 2026-09-03. Built jointly -
Antigravity drafted, Claude Code audited and merged, in the same session.
47 tests pass, all offline:

```
python -m unittest Sports_Desk.tests.test_fair_value Sports_Desk.tests.test_odds_watcher
```

| File | Role |
|---|---|
| `engine/fair_value.py` | Devigging. PURE - no I/O, no DB, no network. |
| `ingestors/odds_watcher.py` | drop-folder ingestion, staleness guard, edge pricing |
| `ingestors/results_watcher.py` | settled outcomes + rolling Brier calibration |
| `interfaces/cli_hotlist.py` | actionable-edge HUD, gated and dollar-sized |
| `engine/arbitrage.py` | cross-book arbitrage, priced after tax |
| `interfaces/monarch_shark.py` | `Monarch_Shark` betslip + execution CLV |
| `data/db.py` | `sports_market.db`: measurements, edges, import log |
| `tests/test_fair_value.py` | Analytic fixtures + regressions |
| `tests/test_odds_watcher.py` | Watcher mechanics, refusals, provenance |

Run the chain:

```
python -m Sports_Desk.ingestors.odds_watcher --once --hurdle-from-ledger
python -m Sports_Desk.ingestors.results_watcher --once
python -m Sports_Desk.interfaces.cli_hotlist --show-rejected
python -m Sports_Desk.interfaces.monarch_shark            # interactive betslip
python -m Sports_Desk.interfaces.monarch_shark --arb      # arbitrage only
python -m Sports_Desk.interfaces.monarch_shark --clv      # execution CLV
```

USE `--hurdle-from-ledger`, NOT `--hurdle`. The hurdle rises with the odds.

## The truth-teller question is now answered in code

`odds_watcher` devigs the SHARP book (Pinnacle / Circa / Bookmaker / Betcris, or
any row flagged `is_sharp`) and scores every retail quote against those fair
probabilities. Retail books are never devigged - you bet the offered price, not a
fair one, so the retail side is stored raw.

A market with NO sharp book is REFUSED, not priced off DraftKings. So is a market
where two sharp books both quote (the fair value would depend on row order), and
one where the sharp book quotes fewer than two legs.

**THE LINE IS PART OF THE MARKET KEY**, not an attribute of it. Markets group on
`(event_id, sport, market_type, line)`. Chiefs -3.5 and Chiefs -2.5 are different
bets with different fair prices; grouping them devigged one book against another
quoting a different number, and the phantom "edge" that fell out was the
half-point - largest exactly where line shopping looks most attractive. `line` was
also an odds alias, so a -3.5 handicap parsed as a price; it no longer is.

**SELECTION MEMBERSHIP IS ENFORCED ON A NORMALISED KEY** (case and whitespace
only). A retail selection outside the devigged sharp set has no fair price and is
skipped by name. Matching raw strings meant `Chiefs` and `chiefs ` were different
runners, which dropped every retail quote and looked like a market nobody quoted.

**STALENESS**: quotes are dropped when older than the sport threshold measured
against the NEWEST quote in the same market - relative, not wall-clock, so a file
imported the morning after a scrape is still valid if its quotes are
contemporaneous. A market that loses a sharp leg to staleness is unpriceable, not
priceable-with-fewer-legs. An export with no timestamps is passed through with a
note; nothing about it is verified.

## The hurdle is now a GATE, not a report (Round 26f)

`check_order(category="sports", expected_edge=..., decimal_odds=...)` rejects any
wager whose gross edge does not clear `breakeven_gross_edge`, and sizes what
survives by AFTER-TAX Kelly:

    w = (O-1)(1-t)        winnings, taxed
    l = 1 - t*delta       stake lost, relieved only by the deductible part
    f* = (p*w - q*l) / (w*l)

The numerator is exactly the after-tax EV, so **f* is zero precisely where the
gross edge equals the tax hurdle** - the gate and the sizer are the same
inequality read two ways, verified to 1e-12. Kelly can only ever TIGHTEN the flat
cap, never raise it.

An edge sorts into three bands, and the middle one is worth knowing about:

    edge < tax hurdle           f* < 0, rejected - an after-tax loss
    tax hurdle < edge < total   f* > 0 but STILL rejected: Kelly says the bet is
                                worth making, the execution fee says it is not
    edge > total hurdle         f* > 0, approved and Kelly-sized

**THE HURDLE IS A FUNCTION OF THE ODDS, NOT A CONSTANT** - 16.3% at 1.50 rising
to 49.7% at +1000, because the tax is charged on a bigger win while the loss still
relieves nothing. `OddsWatcher(after_tax_hurdle=...)` therefore takes a CALLABLE
`f(decimal_odds) -> hurdle`; `--hurdle-from-ledger` wires the real one. Passing a
flat number marked a +1600 dog with a 41.67% edge as tradeable when its true
hurdle was 52.20%, and made the edge table disagree with the order gate.

**FAIL-CLOSED**: a wagering order with no `expected_edge`/`decimal_odds` is
rejected outright. The fee-only fallback is not a weaker check, it is the wrong
one - it passes a 3% edge carrying a 21%+ hurdle. Non-wagering categories are
untouched.

## The after-tax hurdle (Item 3, in `monarch_hook`)

`MonarchBankrollHook.after_tax_edge_hurdle(decimal_odds)` prices what IRC 165(d)
does to a wager's viability. Stake 1 at odds O, tax t, loss-deductible fraction d:

    p_breakeven = (1 - t*d) / [ (O-1)(1-t) + (1 - t*d) ]
    hurdle      = p_breakeven * O - 1

At t = 35%, O = 2.00:  d=1.0 -> 0.00% | d=0.90 -> 2.62% | d=0.00 -> 21.21%.

THE 21.21% IS THE HEADLINE. Under a casual standard deduction a coin flip at
2.00 needs a TRUE win rate of 60.6% to break even after tax, and the hurdle grows
with the odds - a +1000 shot needs 46.67%. Every "3% edge" sports model is an
after-tax loser in that regime. Verified by Monte-Carlo (400k wagers at
p_breakeven return zero after tax) as well as algebraically.

`breakeven_gross_edge(category="sports", decimal_odds=...)` adds it to the
existing fee hurdle. Every other category is untouched: a capital loss nets
against a capital gain, so only `fee/(1-t)` applies there.

NOTE d = 0.90 for `professional_schedule_c`, not 1.0. OBBBA 70114 amended
165(d) itself, which binds professionals too, and `gambling_tax.py` already
applies the haircut in that branch. The hurdle MUST use the same d the escrow
reserves against, or the bot sizes for a tax the ledger is not holding cash for.

Depends on `Tax_Reserve_Agent/engine/odds.py` for `OddsQuote` / `parse_odds`.
That import is HARD, not wrapped in try/except: a silent fallback would let this
engine and the tax ledger disagree about what `-110` means.

## Decisions that are settled - do not relitigate without a reason

- **Shin everywhere.** Not Shin-for-narrow / Power-for-wide. Two markets devigged
  by different estimators are not comparable, and everything downstream compares
  them. Measured: Shin and Power differ by 0.0078 on a 4-way market, so routing
  by width silently shifts every fair value by that much at the boundary.
- **n=2 uses a closed form, and it is an EQUAL ABSOLUTE DEDUCTION**
  (`p_i = pi_i - (beta-1)/2`). This is Antigravity's find and it is correct:
  at n=2 Shin collapses exactly onto the additive method. Not obvious, since the
  general Shin correction is larger on longshots. Verified against an
  independently written bisection solver from 1.001/501.0 to a symmetric -110,
  agreeing to 2.3e-16.
- **Power is a cross-check oracle, never a production path.** Tolerance 0.03,
  CALIBRATED not guessed: well-formed markets (from -110/-110 to a 20-runner golf
  book) deviate at most 0.0102; a leg mistyped by 10x deviates 0.1070. A flag
  that fires on normal markets teaches the operator to ignore it.
- **Nothing is renormalised after solving.** Rescaling makes a failed solve
  indistinguishable from a good one - an early stop on 1.20/4.75 gives
  [0.9058, 0.0942] against a true [0.8114, 0.1886], 9.4 points out, and still
  sums to exactly 1.0. `converged` is load-bearing. Gate orders on `trustworthy`,
  which also requires the oracle to agree and no warnings.
- **A booksum below 1.0 raises `ArbitrageError`, never a price.** Pricing it
  anyway reports a positive edge on every side at once, which cannot be true and
  is the one thing a scanner most needs surfaced. The exception carries
  `.booksum` and `.edge_pct` so it is usable as a signal, and subclasses
  `DevigError` so existing catch sites still work.
- **A bare number is DECIMAL odds by contract here.** `100.0` is a legitimate
  outright price; the tax ledger's sniffer refuses it as ambiguous, but this
  module's signature settles it. American prices come in as strings (`"-110"`,
  `"+150"`), which are unambiguous because of the sign.

## The chain is now closed (Round 26g)

    odds CSV -> odds_watcher -> edge_opportunities
                                      |
    results CSV -> results_watcher -> settled_results -> Brier / skill score
                                      |
                                cli_hotlist -> monarch_hook.check_order
                                      |
                             ACTIONABLE BETS WITH DOLLAR SIZING

**`results_watcher`** settles outcomes and re-scores every book:

    brier = mean((forecast - outcome)^2)          lower is better
    skill = 1 - brier / baseline_brier            baseline = this sample's base rate

The skill score is what makes the Brier mean anything - forecasting a field of
heavy favourites scores well by saying nothing. A PUSH is recorded as `voided`
and excluded from every score: squaring a forecast against a non-outcome is a
category error, not a small one. The CLOSING measurement is the one scored, since
an early price measures how far the line moved rather than how good the book is.
Snapshots are only frozen past `MIN_FORECASTS_FOR_SNAPSHOT` (20) - below that a
Brier is noise wearing a decimal point.

**This is what should eventually replace the hardcoded `SHARP_BOOKS` list.**
Sharpness is a property you measure, not a name you recognise.

**`cli_hotlist`** ranks by APPROVED DOLLARS, not by edge - a 40% edge the gate
sizes to $12 deserves less attention than a 30% edge it sizes to $300. Six
exclusion reasons, each because the alternative looks tradeable and is not:
`settled`, `started`, `live`, `stale`, `untrusted` (oracle-divergent sharp
market), `rejected` (sub-hurdle). Under a casual standard deduction an EMPTY
hotlist is the normal, correct output, and the render says so - an operator who
does not know that will assume the pipeline is broken.

## One close per selection, enforced by the database (Round 26h)

`measure_clv` takes the LAST closing row it finds, so two competing closes never
errored - they silently picked a winner, and the CLV of every bet on that
selection depended on which file was imported second. A partial unique index on
`fair_odds_measurements (event_id, market_type, line, selection) WHERE
is_closing = 1` makes that unrepresentable.

The writer DEMOTES a prior close rather than colliding with it: books genuinely
re-close a market, and an IntegrityError on a legitimate update would be a worse
failure than the one this prevents. `_migrate` demotes pre-existing duplicates
before creating the index, so an older database upgrades instead of blocking.

Note the invariant is per LINE - a spread at -3.5 and one at -2.5 each keep their
own close.

## Cross-book arbitrage, and why it is usually a trap (Round 26i)

`engine/arbitrage.py` builds a SYNTHETIC market from the best price per outcome
across every book. A single book never arbs itself - its overround is its margin
- so the opportunity only exists across books.

It scans BOTH tables and has to: `edge_opportunities` holds one row per RETAIL
quote, so a selection only the sharp book priced has no row there. Scanning that
table alone found nothing on exactly the shape that matters - one side best at
the sharp book, the other best at a retail book.

**A 5.60% arb on $1,000, same position, two filers:**

    professional (delta 0.90)   hurdle  2.91%   worst branch  +1.75%  (+$17)
    casual standard deduction   hurdle 29.12%   worst branch -15.29%  (-$153)

The arb wins one leg and loses the other every time; under a standard deduction
the loss deducts nothing. Real cross-book arbs are 1-3%, so almost all of them
are reliable losses that look like free money.

The N-way hurdle prices the WORST branch - the longest-odds leg, because that is
the smallest stake and so the largest non-deductible loss:

    R = [ 1 - t*s_min - t*delta*(1 - s_min) ] / (1 - t),  s_min = (1/O_max)/booksum

Verified to zero the worst branch for 2-, 3- and 4-way markets at every delta,
and it contains the symmetric two-leg formula exactly.

## Monarch_Shark - the betslip (Round 26i)

The point at which a recommendation becomes a wager, and the only module that
records that money moved. It does NOT place bets with a book and does NOT write
to the tax ledger - `Tax_Reserve_Agent` is fed by the book's own export, because
the escrow must reserve against what the BOOK says happened.

`placed_bets` is what was TAKEN; `edge_opportunities` is what was OFFERED. The
gap is execution slippage, invisible unless both are kept.

Two refusals worth knowing about:
  * A stake above the approved size is REFUSED, not clamped. Silently halving
    what you typed is worse - you would place your number at the book and the
    ledger would disagree with reality.
  * A sub-hurdle arbitrage is refused WHOLESALE. Staking legs one at a time
    would let a rejected leg through as a naked bet, the opposite of riskless.

`execution_clv()` reports two things that can disagree, and both are needed:
`clv_prob_delta` (did the market come to you) and `beat_closing_price` (was the
price you took better than closing fair). A bet can win one and lose the other.

## The three operational bridges (Round 26k)

The chain now closes in both directions - the desk tells the ledger, and the
ledger's outcomes come back.

**A. TAX-LEDGER RECONCILIATION.** `check_sync()` lists placed bets older than
three days that the tax ledger has never seen; `--export-to-tax-agent` writes
them into `Tax_Reserve_Agent/data/imports/` as a CSV the existing ingestor reads.

IDEMPOTENCY DEPENDS ON THE BOOK'S TICKET ID, which `Monarch_Shark` now asks for
at stake time. The ingestor builds `tx_hash` as `{book}_{ticket}_bet`, so an
exported row WITH the ticket id collides with the book's own export later and is
ignored - one wager, one lot. A row WITHOUT one cannot collide, so importing both
would book the wager TWICE; those rows are still exported (leaving them out
under-states the escrow) but flagged in the notes and called out.

**B. OUTCOME SETTLEMENT.** `results_watcher` now joins `settled_results` onto
`placed_bets` and writes `outcome`, `realized_pnl`, `settled_at`. A push books
zero and is excluded from turnover and the win rate - a returned stake is not a
bet that was won or lost. `desk_performance()` reports realised P&L, ROI, win
rate against the model's own expected win rate, and average execution CLV.

**C. CORRELATED EVENT EXPOSURE.** One game gets one position's worth of risk,
however many legs it is sliced into. Chiefs ML and Chiefs -3.5 are close to the
same bet and the sizer treats them as independent.

The cap is scaled to the STRATEGY BUCKET, not the whole bankroll: 5% of the safe
bankroll is 6.7x looser than the per-order cap once bucketing is on, so it would
have taken about seven legs on one game before binding. Measured: four legs on
one game now stop at $375.00 exactly.

## Known limitations, deliberate

- **A market missing a leg cannot be detected.** It just looks like a market with
  less margin. Often caught incidentally (a 1X2 book less its draw falls to 0.77
  and trips the arb guard), but that is luck: a 4-way at 1.0889 less its longshot
  still sums to 1.0556, devigs cleanly, reports `trustworthy`, and is 1.7 EV
  points too generous. Only the CALLER knows how many outcomes an event has.
- **No opinion on which book to trust.** Devigging a soft book yields that book's
  opinion minus its margin, not a fair price. Pinnacle/Circa as the sharp
  reference is agreed but lives in the data layer, which is not built yet.
- **`kelly_fraction` is GROSS OF TAX and must not size a real order.** Under the
  ledger's default `casual_standard_deduction`, gambling losses do not offset
  winnings at all, so the after-tax growth rate it maximises is not the one the
  bettor experiences. Real sizing needs `monarch_hook`, where the bankroll and
  the tax treatment live.

## Next / open questions

1. **Nothing places an order yet.** The watcher records edges and whether they
   clear the hurdle; no path turns a cleared edge into a wager. Sizing needs
   `monarch_hook`'s bankroll and the `sports_betting` strategy bucket, and
   `fair_value.kelly_fraction` is GROSS OF TAX so it must not be wired straight
   through - see the warning on it.
2. **CLV is measured but nothing is calibrated against it.** `measure_clv()`
   compares entry fair probability to closing fair probability per
   (event, market, line, selection). Nothing yet aggregates it into a verdict on
   the model, and "entry" is the earliest measurement rather than a stake - when
   bets are recorded this should take a stake timestamp instead.
3. **Staleness thresholds are ENGINEERING ESTIMATES, not measurements.**
   `MAX_QUOTE_AGE_SECONDS` (30s in-play, 180s NBA, 300s NFL, 3600s golf, 600s
   default) has no line-history data behind it. Deliberately generous so the
   guard catches last night's quote without discarding a normal scrape.
4. **Cross-book arbitrage is NOT detected.** `ArbitrageError` fires only when ONE
   book's own booksum falls below 1.0. The arb that actually exists - Pinnacle
   quoting the dog at +120 while DraftKings quotes the favourite at -100 - is
   stored as two independent positive edges, and nothing says they are two sides
   of one riskless position. Worth noting the tax consequence: under a standard
   deduction even a real arb can be an after-tax loss, because the losing leg
   deducts nothing.
5. **`w2g_threshold_usd` and `mandatory_withholding_rate` are DEAD CONFIG KEYS.**
   Defined in `config.yaml` and `config.py`, read by nothing. Nothing predicts
   which wagers will trigger a W-2G and 24% withholding at the book, so a bettor
   gets no warning that a payout is about to arrive $2,388 short.
6. **`SHARP_BOOKS` is a static set.** Sharpness is an empirical property (do the
   book's closing lines predict outcomes?), not a name. Measuring it would need
   settled results, which nothing here ingests yet.
7. **The additive fee + tax hurdle is an approximation.** The two are not
   strictly separable: a commission changes the realised payout, which changes
   the tax leg. Exact treatment shrinks (O-1) instead. Adding them overstates the
   hurdle slightly, which is the safe direction.
