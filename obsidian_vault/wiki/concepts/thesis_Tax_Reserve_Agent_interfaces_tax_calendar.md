---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/interfaces/tax_calendar.py'
description: "This is the detail the name hides and everyone gets wrong:\n\n Q1 Jan\
  \ 1 - Mar 31 (3 months) due Apr 15 Q2 Apr 1 - May 31 (2 months) due Jun 15 Q3 Jun\
  \ 1 - Aug 31 (3 months) due Sep 15 Q4 Sep 1 - Dec 31 (4 months) due Jan 15 of the\
  \ FOLLOWING year\n\n A trader who books a large gain on …"
tags:
- concept
- thesis
- desk-5
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: Tax_Reserve_Agent/interfaces/tax_calendar.py
  title: Tax_Reserve_Agent/interfaces/tax_calendar.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/interfaces/tax_calendar.py
  headings:
  - THE QUARTERS ARE NOT QUARTERS
  asserts:
  - file: Tax_Reserve_Agent/interfaces/tax_calendar.py
    pattern: THE\ QUARTERS\ ARE\ NOT\ QUARTERS
    claim: the docstring still carries the section 'THE QUARTERS ARE NOT QUARTERS'
  requires_files:
  - Tax_Reserve_Agent/interfaces/tax_calendar.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/interfaces/tax_calendar.py

> 1 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Quarters Are Not Quarters

This is the detail the name hides and everyone gets wrong:

 Q1 Jan 1 - Mar 31 (3 months) due Apr 15 Q2 Apr 1 - May 31 (2 months) due Jun 15 Q3 Jun 1 - Aug 31 (3 months) due Sep 15 Q4 Sep 1 - Dec 31 (4 months) due Jan 15 of the FOLLOWING year

 A trader who books a large gain on June 1 owes it in the Q3 payment, not Q2, and one who books it on May 31 owes it two weeks later. Splitting the year into even three-month blocks produces the right annual total and the wrong deadline on every one of them, which is precisely what triggers an underpayment penalty even when the year is paid in full.

 The gain is attributed to the period it was REALISED in, which is the annualised income installment method - the right one for lumpy trading income, where the even-quarters default would demand tax in April on a gain not made until November.

 Deadlines falling at a weekend roll to the following Monday. Federal holidays are NOT modelled: the one that matters in practice is Emancipation Day in DC, which pushes the April deadline to the 17th in some years. Treat a due date within a day or two of a weekend as needing a check against the IRS calendar.

 Not modelled either: the safe-harbour rules (paying 90% of this year, or 100% / 110% of last year's liability, avoids a penalty regardless of how the income actually fell). This schedule shows what the year's realised gains imply, which is the number you need to have set aside either way.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
