---
type: Concept
title: 'Thesis: Sports_Desk/engine/fair_value.py'
description: 'Dividing each implied probability by the booksum (MULTIPLICATIVE) assumes
  margin is spread proportionally. It is not: books load disproportionately more margin
  onto longshots, because that is where the public bets. Multiplicative devigging
  therefore leaves a longshot''s fair proba…'
tags:
- concept
- thesis
- desk-2
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: Sports_Desk/engine/fair_value.py
  title: Sports_Desk/engine/fair_value.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Sports_Desk/engine/fair_value.py
  headings:
  - HOW THE SURPLUS IS STRIPPED IS THE ENTIRE QUESTION
  - SHIN (1992, 1993) IS THE ESTIMATOR, EVERYWHERE
  - POWER IS A CROSS-CHECK ORACLE, NOT AN ALTERNATIVE
  - NOTHING IS RENORMALISED AFTER SOLVING
  - WHAT THIS MODULE WILL NOT DO
  asserts:
  - file: Sports_Desk/engine/fair_value.py
    pattern: HOW\ THE\ SURPLUS\ IS\ STRIPPED\ IS\ THE\ ENTIRE\ QUESTION
    claim: the docstring still carries the section 'HOW THE SURPLUS IS STRIPPED IS
      THE ENTIRE QUESTION'
  - file: Sports_Desk/engine/fair_value.py
    pattern: SHIN\ \(1992,\ 1993\)\ IS\ THE\ ESTIMATOR,\ EVERYWHERE
    claim: the docstring still carries the section 'SHIN (1992, 1993) IS THE ESTIMATOR,
      EVERYWHERE'
  - file: Sports_Desk/engine/fair_value.py
    pattern: POWER\ IS\ A\ CROSS\-CHECK\ ORACLE,\ NOT\ AN\ ALTERNATIVE
    claim: the docstring still carries the section 'POWER IS A CROSS-CHECK ORACLE,
      NOT AN ALTERNATIVE'
  - file: Sports_Desk/engine/fair_value.py
    pattern: NOTHING\ IS\ RENORMALISED\ AFTER\ SOLVING
    claim: the docstring still carries the section 'NOTHING IS RENORMALISED AFTER
      SOLVING'
  - file: Sports_Desk/engine/fair_value.py
    pattern: WHAT\ THIS\ MODULE\ WILL\ NOT\ DO
    claim: the docstring still carries the section 'WHAT THIS MODULE WILL NOT DO'
  requires_files:
  - Sports_Desk/engine/fair_value.py
  desk: 2
---
# Thesis: Sports_Desk/engine/fair_value.py

> 5 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## How The Surplus Is Stripped Is The Entire Question

Dividing each implied probability by the booksum (MULTIPLICATIVE) assumes margin is spread proportionally. It is not: books load disproportionately more margin onto longshots, because that is where the public bets. Multiplicative devigging therefore leaves a longshot's fair probability too HIGH - manufacturing value exactly where the favourite-longshot bias says none exists.

## Shin (1992, 1993) Is The Estimator, Everywhere

It models the book as pricing against a proportion `z` of insider traders and solves for the z that makes the fair probabilities sum to one. Running a different estimator on wide markets than on narrow ones would be cheaper and is a trap: two markets devigged differently are not comparable, and everything downstream compares them. Measured on a 4-way market Shin and Power differ by 0.0078, so routing by market width shifts every fair value by that much at the boundary.

 n = 2 closed form, PROVEN exact (see `_shin_two_way`) - no iteration at all n >= 3 bisection on z in [0, 1)

## Power Is A Cross-Check Oracle, Not An Alternative

`p_i = pi_i ** k` solved for the normalising k is a different functional form of the same bias. The tolerance is CALIBRATED, not guessed: across well-formed markets from -110/-110 to a 20-runner golf book the two estimators differ by at most 0.0102, while a market with one leg mistyped by 10x differs by 0.1070. The 0.03 default sits in that gap. A flag that fires on normal markets teaches the operator to ignore it.

## Nothing Is Renormalised After Solving

Rescaling the output so it sums to one is tempting and it is a trap: it makes a FAILED solve indistinguishable from a good one. Stopping the bisection early on a 1.20/4.75 market gives [0.9058, 0.0942] against a true [0.8114, 0.1886] - a 9.4 percentage point error - and a rescale still leaves it summing to exactly 1.0, so nothing about the vector looks wrong. `converged` is load-bearing; callers must check it, and `trustworthy` bundles it with the oracle result for exactly that purpose.

 A BOOKSUM AT OR BELOW 1.0 IS A SIGNAL, NOT A PRICE. There is no margin to strip, every devigger would have to ADD some to normalise, and Shin's z goes negative. Pricing it anyway reports a POSITIVE edge on both sides of the market - the one result that cannot be true, and the one a scanner most needs to see. Hence `ArbitrageError`, which carries the booksum and the edge rather than just a message.

## What This Module Will Not Do

* No I/O. No database, no network, no file reads - pure arithmetic, so the maths is testable against analytic answers with nothing mocked. Persistence lives in `Sports_Desk/data/db.py`; ingestion is separate again. * No opinion on WHICH book to trust. Devigging a soft book yields that book's opinion minus its margin, not a fair price. Choosing a sharp reference (Pinnacle, Circa) is a data-layer decision. * No tax. `kelly_fraction` is GROSS of tax and must not size a real order on its own - see the warning on that function.

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[theses_register|Theses register]]
