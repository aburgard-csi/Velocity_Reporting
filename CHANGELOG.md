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

### 2026-08-28 — responder counts now agree across slides

The same mailing reported different responder counts on different slides: Wellworth
1549's Jun 2026 drop read 1,077 on the mailing slides and 1,026 on Program Reach,
Depth of Engagement, Ranking and Sustained.

Cause: those four counted a HISTORICAL mailing's responders through the CURRENT
eligibility snapshot (`<latest> Elig`), which drops anyone who responded and has since
closed or gone ineligible — 51 accounts on Wellworth. Slides 18/19 already used the
personal cohort for exactly this reason (2026-08-27); the rest now match.

Affects every ARS deck. Reach, depth and ranking figures rise.

### 2026-08-28 — sustained rate measured after the response month

Sustained compared the extract's trailing 3 months against the ask, for every mailing.
For a recent mailing that window includes months from before the customer responded, so
it reported attrition that had not happened.

A response is recorded in the month AFTER the offer — Wellworth confirms it: 44% of the
Jun 2026 responders cleared their ask in June, 100% in July. The window now starts at
mailing+2. A mailing with no month after its response month reads 100% by definition and
is drawn grey with the caption saying attrition cannot appear yet.

### 2026-08-28 — before/after is mean only, split by offer

The median twin (slide 19) is replaced by the same mean, split into Non-User and
Threshold respondents. The two offers ask for different behaviour and pooling them hid
which one moved. Grouping keys on `<mon> Mail`, as mail_summary does.

A Non-User's baseline is near zero, so its percentage change is meaningless (Wellworth
computes +9,018% off $13); below a $25 baseline the narrative states dollars instead.

### 2026-08-28 — Stat Code fallback in the shared status classifier

`classify_status` only ever read `Stat Desc`. 1549 Wellworth populates `Stat Code`
(O/C/X) and leaves `Stat Desc` BLANK on every non-open account, so 18,274 of 50,218 rows
classified as "Other". `oddd_optimize.STAT_CODE_MAP` now maps O/A -> Open, C -> Closed,
X -> Charged Off (Aaron-confirmed); the description still wins when it carries text.

Affects the account-status mix on any client whose core fills the code, not the label.

### 2026-08-28 — take-rate-by-branch table showed months twice

`set_table` trimmed surplus template ROWS but not COLUMNS, so a client with fewer
activity months than the template's eleven kept the reference client's remaining
columns. Wellworth's table carried a second Apr/May/Jun and a second Cards/Elig/Take%
block from Union Financial. Columns are now trimmed to the data and the width
re-spread. The table also fills the slide (10 branches, was a fixed 6).

### 2026-08-28 — stale month captions

A dozen template captions carried the reference client's month and no swap ever reached
them, so a Jul 2026 extract shipped "Monthly debit spend (June 2026)", "opt-in status as
of June 2026" and "Jul 2023 - Jun 2026 (36 months)" on a client with five months of data.
Point-in-time phrases and series spans are now derived. `validate_deck` FAILs any dated
caption still byte-identical to the template's, scoped to the template's own reporting
month so a genuinely fixed window (the Kaplan-Meier cohort) is not flagged.

### 2026-08-28 — ICS branch goals pro-rated

Branch goals in the VIP export are ANNUAL, but a program that started partway through the
year has not had a year to hit them. Wellworth began in May; its Main branch read 24
against a 204 annual goal (12%), which reports the calendar rather than the branch. The
goal is now pro-rated to the months the program has run — Main reads 24 of 68 (35%), and
the top-8 total moves from 14% to 41%. Falls back to the annual goal when the run length
cannot be derived.

### 2026-08-28 — Reg E "no election" wording, and the ICS branch selection line

"No election means the customer was never asked" asserted something the data cannot
show, and put it on the branch. No election means only that we do not hold their
decision — they may well have been asked. Now reads "no election means the customer
hasn't given us one" (the exact phrase "didn't give us their decision" measures 12.30in
against 12.10in of box and wraps onto the tiles).

The selection line was removed from ICS "Results by Branch – Year to Date": with the
callouts and the pro-rating note it ran to ~20in of text in a 9.68in box, wrapped, and
its box overlapped the table above and the logo band below. Selection, branch counts and
the pro-rating basis are all in the notes.

### 2026-08-28 — combined deck split the ARS section at a fixed index

`assemble_combined` kept "the first 30 slides" ahead of the ICS section. That is only
right while the ARS deck is exactly 47 slides. Adding Excluded Accounts and Reg E by
Branch made it 49, and the boundary cut two slides early: "Reg E Opt-In by Account
Vintage" and "ARS Key Takeaways" were pushed AFTER the ICS section. The boundary now
resolves by TITLE ("ARS Key Takeaways") — CLAUDE.md: never by index. It printed a note
about the count mismatch and carried on regardless; it now states where the section ends.

Also: the combined agenda described the ICS section as "Referral trend, account value,
ROI & financial results" even for a referrals-only build that contains none of those.
Detected from the slides actually copied, not from a flag.

### 2026-08-28 — Reg E by Branch is new accounts, not the whole book

The table was built on every open personal card holder — a view dominated by decades of
legacy elections that says nothing about how branches are asking today. It now uses the
same trailing-12-month cohort and >=15 threshold as the new-account chart beside it, and
reconciles to `rege_new_pct`. The heading states the window ACTUALLY used: an extract
carrying fewer than twelve activity months yields a shorter one (Wellworth's is
Mar-Jul 2026), and "Last 12 Months" over five would be false.

### 2026-08-28 — referrals-only ICS agenda listed absent sections

The section divider correctly dropped to "Referrals", but the agenda still listed
Performance of ICS Accounts, ICS Revenue & Revenue Detail, ICS Financial Summary and
Comparisons — four sections a referrals-only build deliberately OMITS. Wellworth 1549
shipped that way. Rows are now removed, not blanked, for the same reason
`assemble_combined` removes them: an empty numbered row reads as a section that failed
to render. A full workbook-driven build still lists all eight.

### 2026-08-28 — client logo on the Agenda slide (ARS + ICS)

Placed in the right-hand third, which is empty: the agenda's own text reaches at most
8.80in (measured against the bundled TTFs at the 16pt floor), so a logo from 9.30in
clears it. Sourced from `Inputs/Logos/<clientid>.png` via `rpe_env.client_logo`, cropped
to its ink by `trim_logo` and fitted by `fit_box`. Absent logo = slide built without it.

`trim_logo` also re-encodes any file python-pptx cannot embed: 1539.png is really a
WEBP, which PIL opens happily and `add_picture` then refuses outright. MRPC has no
agenda slide, so it is unchanged.

### New slides — Excluded Accounts (ARS), Reg E Opt-In by Branch (ARS)

Excluded Accounts follows Product Mix: the eligibility waterfall (status -> product code
-> debit card, each account counted once) plus the per-client excluded product codes,
derived as those with no eligible account. $0 balance and address quality are reported as
observations, NOT exclusions — neither predicts the `Elig` flag.

Reg E Opt-In by Branch is the table companion to the two Reg E branch charts, carrying
opted-in / opted-out / no-election per branch.


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
