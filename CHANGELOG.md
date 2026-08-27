# Changelog

Behavior changes to the deck pipelines. The point of this file is that a
reversal like the 2026-08-20 one below should be findable without reading an
80KB source file.

Record anything that changes a number on a client-facing slide, changes where a
number is sourced from, or changes what a slide claims. Refactors and layout
tweaks don't need an entry.

Format: newest first, dated, with the reason — not just the change.

---

## Unreleased

### Pending — tier response rate denominators

`NU 5+` and `Threshold Met` on the ARS Mailing Response Summary divide by total
accounts mailed instead of by each offer group's own mailed count. They are
shares of the whole file, not response rates, and they sum exactly to the
overall response rate — which is the tell.

The fix, agreed 2026-08-26: each offer group is rated against its own mailed
base. NU responders over NU recipients; TH responders over TH-10 through TH-25
recipients combined; overall responders over total offers sent. The three no
longer sum, because the denominators differ.

The ODD already carries what's needed. `<mon> Mail` holds the offer strategy per
account (`NU`, `TH-10`, `TH-15`, `TH-20`, `TH-25`) — `metrics_gen.OFFER_GOAL`
maps exactly those five values, and the dot-plot code already reads it that way.
`mail_summary` simply never split on it.

Grouping keys on what was mailed (`<mon> Mail`), not on how the account
responded (`<mon> Resp`). Those should agree, but if they ever don't, keying on
the response tier puts a responder in a group whose denominator doesn't contain
them, and the rate can exceed 100%.

Touches `metrics_gen.mail_summary`, the six-value row unpack in
`build_ars_gen.py`, the slide-12 subtitle, and the stale comment block described
in the 2026-08-20 entry.

Affects: all nine 2026.08 ARS decks. None had been sent when this was found.

CoastLife 1705 v3 was patched by hand on 2026-08-26 as a stopgap, sourcing the
rates from the workbook rather than the ODD. It is superseded once the generator
is fixed and CoastLife is regenerated. Do not treat v3 as the reference.

---

## 2026-08-20

### Mailing response moved from the workbook to the ODD

Slide 12 read tier response percentages out of the workbook while slide 14
computed the latest mailer from the ODD, and the two disagreed on the same drop
— 16.3% vs 10.7% on Wellworth 1549. Both now use one definition: offers sent =
personal accounts carrying a `<mon> Mail` value; responders = those whose
`<mon> Resp` reached a goal tier.

The rationale recorded in `build_ars_gen.py` states the workbook's denominator
is not the mailed population. That reasoning does not hold for every client —
CoastLife's workbook denominators reconstruct the mailed population exactly
(2,015 NU + 2,756 TH = 4,771 offers sent, Jun 2026). Wellworth has a single
mailing and no lift matrix, so it was a thin case to generalize from.

Single-sourcing to the ODD was still correct. The denominator was the separate
bug, unfixed here, and carried forward into every deck built after this date.

**Update the comment block in `build_ars_gen.py` when the Unreleased fix lands.**
It currently argues for behavior we are changing.

### Other fixes the same day

- Title-slide and PTD-pill months were never swapped; every 2026.08 ARS deck
  shipped the template's "July 2026" and "PTD · June 2026".
- Business take-rate branch chart had no bar cap while sharing the personal
  chart's geometry — 19 bars on 1549, 37 on 1075, x labels unreadable.
- The 2:1 profitability sentence was a template literal, so a client below the
  threshold shipped "0.2 : 1 is well above the 2 : 1 threshold".
- Mailing Response Summary carried the reference client's rows below a short
  client's data; `set_table(trim=True)` now drops them.

---

## 2026-07-25

- Slide resolution moved from indices to titles (`SB()`), which raises instead
  of silently no-opping. Index access is how the Appendix swaps went stale.
- Swap gate added: any find-string matching nothing fails the build. A miss
  would ship the reference client's numbers.
