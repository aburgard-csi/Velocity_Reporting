# Changelog

Behavior changes to the deck pipelines. The point of this file is that a
reversal like the 2026-08-20 one below should be findable without reading an
80KB source file.

Record corrections and changes (Aaron, 2026-09-01): anything that changes a
number on a client-facing slide, changes where a number is sourced from, changes
what a slide claims, or changes what a slide RENDERS. A fix that moves no figure
still belongs here — the MRPC retention line below moved no figure and could not
be seen on any deck that carried it. Judging an entry by whether a number moved
is how a correction goes unrecorded.

Format: newest first, dated, with the reason — not just the change.

---

## Changes, newest first

This section was headed "Unreleased" until 2026-10-12, and nothing ever moved an entry out of it:
there is no release-tagging step. What is released is what `Tools\RPE\RELEASE.txt` names, and this
file travels with the code, so Sheila's change log page shows that stamp above these entries.

### 2026-10-28 — Transaction Intelligence cut: the ODD's shape is checked before any figure (stage g14-03)

Summary: before any chapter computes, the TI cut's build now runs v5's extract check on the client's ODD. It records the file's shape in `ti_pack.json` as `extract_*` figures and warns when that shape would quietly distort a figure elsewhere.

Before v5 added this check, any of these produced numbers that were wrong in ways no section could detect, because every figure computed over whatever arrived:
- a month missing inside the covered range, which reads as a month of zero activity;
- Swipes and Spend covering different months, so a per-swipe ratio divides one window by another;
- an account appearing twice, so every headcount counts it more than once;
- an anchor month absent from the series.

`ti/monthly_analysis/extract_check.py` is v5's at `a491b5c`, logic unchanged, and it runs first, as in v5's `metrics.py`. It never suppresses a section, it only reports. Its warnings sit in the build log beside the others, and no figure, slide or deck changes. The ARS deck is untouched.

### 2026-10-28 — Transaction Intelligence cut: one concept, one number, or no deck (stage g14-02)

Summary: the TI cut's build now runs v5's consistency audit. Wherever two slides quote the same figure differently, it records each disagreement in `ti_pack.json` and in the build log, and builds no deck until they agree.

v5 added this audit after the real 1585 deck disagreed with itself: the hero quoted 12.4% where the per-mailer table said 11.4% for the same wave, three slides gave three responder counts, and the P&L slide relabelled window revenue as cumulative. James's rule then: "fail safe if the numbers dont align". `ti/monthly_analysis/consistency.py` is v5's at `a491b5c`, logic unchanged. A rule fires only when both of the figures it compares are present, so a section that declined is never a violation. v5 passes its ODD and transaction figures as two dicts. The cut holds them in one, so `ti_build.main` passes that dict as both. Checked against the cut's real Sep26 packs for 1761 and 1776: no violations, so no deck that builds today is refused. One v5 test is not ported because it checks `run.py`'s card-spend reconciliation through v5's whole metrics harness, not this module. The ARS deck is untouched.

### 2026-10-28 — Transaction Intelligence cut: every table behind its slides as a CSV (stage g14-01)

Summary: the TI cut's build now writes v5's analyst tables: each tabular figure that names its columns becomes a CSV in `ti/tables/`, listed in `ti_pack.json`. A tabular figure that names no columns is listed in the build's warnings by name, never dropped silently.

James, 2026-10-27: "i just need to be able to back up the data." A figure on a slide has to be checkable against the rows behind it. v5 wrote these tables in `run.py` beside `metrics.json`. The cut had no equivalent, so its figures lived only inside `ti_pack.json`. `ti/monthly_analysis/tables.py` is v5's `tables.py` at `a491b5c`, logic unchanged: rows are written exactly as the figure holds them, nothing rounded or re-ordered, so a CSV cannot disagree with its slide. The files are UTF-8 with a BOM so Excel on Windows opens accented names cleanly. `ti_build.main` calls it after the figures and before the decks, as v5 does. A failure here is a warning and the build goes on. No figure, slide or deck changes. The ARS deck is untouched. The figures that are tables but declare no columns are named in the warning; declaring them is a follow-up.

### 2026-10-27 — ARS Companion deck: James's analysis slides get their own button in Sheila

Summary: Sheila has a new ARS Companion panel and button that builds a separate deck of James's analysis slides for an ARS client, filed in Outputs beside the Executive Review without changing it.

Aaron, 2026-10-27: "Build functionality in Sheila (a new button) to build a ARS Companion Deck with James's slides." The companion is built the way the Transaction Intelligence deck is: its own checks, its own button on the client page, the same build queue, and its own file name (`<id>-<yyyy.mm>-COMP-<Client> ARS Companion.pptx`) so it is never taken for the period's Executive Review and is never archived by an Executive Review build. It is the ARS deck built with every opt-in view switched on (James's views, the sustained-activity split, the debit spend slides), cut down to the slides those views added plus the cover, Questions & Discussion and Contact. The Executive Review, its template and its slide count are unchanged. VERSION is now 2.1.

### 2026-10-27 — Slide Review: CSMs vote keep, delete or appendix on any deck's slides

Summary: Sheila has a new Slide Review tab where a CSM votes Keep, Delete or Appendix on each slide of any deck in Outputs, and a Summary that counts the votes across clients.

Aaron, 2026-10-27: "an evaluation process for all of the decks so the CSM can vote whether to keep or delete a slide, or to add it to an appendix." **Review**: pick a client and one of their decks in Outputs for the cycle (Executive Review, Transaction Intelligence, ARS Companion), vote on each slide, add a comment; votes are saved as you click and can be changed. **Summary**: one row per slide across clients, most Delete votes first, with clients, voters and comments, filterable by deck family, with an Export CSV. A vote is its own small file under `Build Artifacts/slide_votes/` (so several CSMs voting at once never overwrite each other); the newest vote per voter and slide wins. A slide is matched by its title with the client's name and figures taken out, never by its number. A vote is checked against the deck as it is in Outputs now, so a rebuilt deck refuses a stale page's vote. `scripts/slide_votes.py`, `scripts/slide_review_ui.py`, `tests/test_slide_votes.py`.

### 2026-10-26 — Transaction Intelligence: three headlines that misstated their figures

Summary: Three Transaction Intelligence headlines were wrong, all found reviewing 1776 CoastHills CU's
deck. "How the leakage builds" said six categories carry $45.1M of the $22.9M that leaves: it summed in
payment apps, which the $22.9M does not count. It now sums leakage categories only: $21.6M of $22.9M. The
ICS summary said ICS "activates them -2 points faster": it now says "2 points fewer of them in month one".
And a store whose card descriptions start "WAL Wal-Mart" was grouped apart from Walmart as "WAL WAL" and
headlined as a faded merchant: it now groups with Walmart, so Flex Finance is the faded merchant and
Walmart's PIN dollars on "Where PIN gets pressed" rise from $14.5M to $17.2M. v5 has all three faults.
Rebuilt 1776's eight-chapter decks, both lenses: 156 slides, 0 FAIL.

`ti/deck/txn_leakage.py`: `how_the_leakage_builds` and `where_the_leakage_goes` keep only rows of kind
"leakage" (`fin_by_category` also carries the adjacency rows), and the count word follows the categories
drawn instead of a fixed "Six". `ti/deck/ics_slides.py`: the month-one gap is worded by its sign.
`ti/transaction_intelligence/merchant.py`: `_two_tokens` skips a word repeated straight after itself;
`loader.CACHE_VERSION` 6 -> 7, because the parquet cache stores `merchant_key` and an old cache would keep
the old key. The merchant tables now differ from v5's wherever a doubled prefix occurs. Tests:
`tests/test_ti_headline_fixes.py` (all four fail without the fixes).

### 2026-10-26 — Transaction Intelligence: the survival-by-tenure overlap is on the register

Summary: docs/migration/DUPLICATES.md gains row 28. The Transaction Intelligence deck's "Account retention
— survival by tenure" repeats the ARS deck's default "Account Retention — Survival by Tenure", and the two
disagree. For 1776 CoastHills CU the ARS deck says 94% of accounts are still open at 1 year and 81% at 3
years; the TI slide says 97.3% and 93.8%. The ARS deck's Kaplan-Meier leaves out accounts too young to
reach each mark; v5's method counts them as retained, which raises the 3-year figure. No slide or number
changes. The row's decision is pending, and the review page for keep/toss decisions pairs the two slides.

### 2026-10-26 — Transaction Intelligence: keep or toss any chapter or slide in one file

Summary: Which chapters and slides go in the Transaction Intelligence decks is now set in one file,
`build/ars_pipeline/ti/slides.json`: every chapter and every slide of the cut is listed by name as
"keep" or "toss". A tossed slide is left out of the deck; a tossed chapter loses its divider and agenda
row too. Everything starts as "keep", so no deck changes today. This is how the overlaps with the ARS
deck in docs/migration/DUPLICATES.md get settled (James and Aaron, 2026-10-26: "an easy way to
include/toss slides, especially those that conflict"): each decision is a reviewed change to this file.

`ti/selection.py` reads it (`TI_SLIDES` points at another file); `Deck.run` and the ICS chapter return
only the kept slides, by the fixed title each was drawn under (never the data-driven headline), and
`build_ti_gen.build` drops a tossed chapter before the agenda is laid out. A tossed slide gets no
stated page: leaving it out was a decision, not missing data. A key may use `*` for slides named per
offer ("Mailer * summary"); an unlisted slide is kept; any state other than keep or toss stops the
build. `tests/test_ti_selection.py` checks every key names a real chapter or slide and every slide the
cut draws is listed. 8 chapters, 138 slide entries.

### 2026-10-26 — Transaction Intelligence: the campaign hero and Revenue frames

Summary: The Campaign chapter gains James's v5 hero slide and Revenue frames. The hero's big number
is what the client has earned over the fees paid while a 2:1 guarantee balance is live, the
workbook's program profit otherwise, with the response trend and the response, gain and retention
tiles. Revenue frames sets the workbook's booked revenue and profit beside the
difference-in-differences gain per responder (and that gain as interchange), and says why the two
never tie. 1776, both lenses: both drawn, 0 FAIL ("The 2:1 guarantee holds: $561K earned over the
fees paid"). No ARS deck changes.

Both are lifted from v5's build like the rest of the chapter, after the per-offer summary and before
the Offer detail appendix, as in v5. One change, marked: the hero's tile icons go through the helper
bundle's `chart()` into the chapter's charts folder (v5 wrote them straight to its own, unless
dry_run). v5's `_responses_caption` comes with them. Tests: `tests/test_ti_campaign_chapter.py`
(guarantee math while a balance is live, the workbook's profit once it clears, both frames).
DUPLICATES row 27.

### 2026-10-26 — Transaction Intelligence: the Campaign chapter

Summary: The Transaction Intelligence decks gain an eighth chapter, Campaign: reach and response by
offer, the per-offer summary, the response ladder and NU conversion, segment trajectories, the
penalty box, the counterfactual, which offer earns its postage, the transaction increase over the
ask, lift by segment, depth of engagement, organic against program activation, what a response does
to spend against a control, sustained activity, first-time against repeat responders, who responds,
tier movement and migration, the most recent mailer, and an Offer detail appendix, newest first. A
slide whose figures are missing is stated. 1776, both lenses: 35 slides and 8 per-mailer appendix
slides drawn, 0 FAIL. No ARS deck changes.

`ti/deck/campaign_inline.py` lifts v5's campaign blocks out of `ars/deck/build.py` line for line (each
builder names its v5 lines), with v5's build-function closures bound to the helper bundle (`skip`
draws the cut's stated slide). Three changes, marked where they are made: six slides v5 drew as
`new()` + `register()` + `_title()` go through `slide()` so the title comes first; the per-offer
table shows as many offers as fit above its summary row and note (6 of 9 on 1776, where v5's 7 put
the note on the KPI row) and carries the response rate's "%" in its header; and `Deck.run` swaps
RPE's banned "lift" / "lifted" for "gain" / "raised" (never a figure, never on a Lift Matrix slide).
`ti/deck/migration_slides.py` is v5's tier matrix, with its test. `ti/chapters/campaign.py` computes
v5's migration, mailer, mailer_detail, mailer_summary and cohort sections in v5's order. Tests:
`tests/test_ti_campaign_chapter.py`. DUPLICATES rows 22-26 updated.

### 2026-10-26 — Transaction Intelligence: swipe-tier migration, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 swipe-tier migration: each eligible
cardholder's swipe tier a year ago and now (on a three-month average), how many moved up, held or
moved down, the full then-to-now matrix, the month-by-month movement, the non-users who started
swiping, and the same split by responders, mailed non-responders and the never mailed. Every figure
matches v5 for 1776 CoastHills and 1761 CapEd. No deck changes yet.

`ti/monthly_analysis/migration.py` is v5's section, unchanged, run through `ti/odd_sections.py`, with
v5's `test_migration_monthly.py` over `tests/ti_v5_harness.py`. v5's `test_migration_matrix_slide.py`
tests the slide module `deck/migration_slides.py` and ports with it in G9-06. Parity: 31/31 on 1776
(2026-09) and 1761 (2026-10), every migration key v5 writes. DUPLICATES row 26.

### 2026-10-26 — Transaction Intelligence: campaign lift, the ladder and the counterfactual, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 cohort and ladder figures: every
account's spend and swipes aligned on the month it was mailed, responders against mailed
non-responders and the never mailed, the lift net of that control at 1, 3, 6 and 12 months, what each
offer earns per 1,000 mailed, how far responders beat their ask and for how long, what spend would
have been without the program, first-time against repeat response, NU 1-4 to success conversion, and
the penalty box. Every figure matches v5 for 1776 CoastHills and 1761 CapEd. No deck changes yet.

`ti/monthly_analysis/cohort.py` and `ladder.py` are v5's, unchanged (ladder is the library cohort
imports, so they port together), run through `ti/odd_sections.py` as `cohort`, with v5's
`test_swipe_high.py` over `tests/ti_v5_harness.py`. Parity: 58/58 on 1776 (2026-09) and 1761
(2026-10), every cohort and ladder key v5 writes. DUPLICATES row 25.

### 2026-10-26 — Transaction Intelligence: each offer month by month, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 per-offer trajectories: for every
completed wave, average swipes and spend each month from a year before the mailing to three years
after, for responders against their own challenge segment's non-responders (and, where the ODD
carries it, by its own segmentation band). Matches v5 for 1776 CoastHills and 1761 CapEd. No deck
changes yet.

`ti/monthly_analysis/mailer_detail.py` is v5's section, unchanged, run through `ti/odd_sections.py`,
with v5's `test_mailer_detail.py` over `tests/ti_v5_harness.py`. Its one slide test skips until G9-06,
and the mailer-summary test that read these figures runs again. v5's `test_appendix_depth.py` is not
ported: it builds v5's whole deck through `deck.build`; the offer-detail slides get the cut's own
chapter test in G9-06. Parity: matches on 1776 (2026-09) and 1761 (2026-10), where v5 wrote only
`mailer_resp_detail` (the segmentation-band table is conditional). DUPLICATES row 24.

### 2026-10-26 — Transaction Intelligence: the per-mailer summary, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 per-mailer summary: for every
completed wave, mailed, responded and the response rate overall and by challenge tier, with five
"Inside the Numbers" figures (new accounts, holders 60+, Reg E opted in, first-time responders, and
repeat responders who moved up). Matches v5 for 1776 CoastHills and 1761 CapEd. No deck changes yet.

`ti/monthly_analysis/mailer_summary.py` is v5's section, unchanged, run through `ti/odd_sections.py`,
with v5's `test_mailer_summary.py` and `test_mailer_summary_chart.py`. Those tests build a synthetic ODD
with v5's `make_odd` and run v5's `metrics.compute`; `tests/ti_v5_harness.py` carries `make_odd` and its
`CONFIG` verbatim and a `compute` that takes v5's steps over the sections the cut has ported (v5's
harness file is a script that runs on import, so it is not ported as it stands). The one test that
reads mailer_detail's figures switches on with G9-03. Parity: `mailer_summary` matches on 1776
(2026-09) and 1761 (2026-10). DUPLICATES row 23.

### 2026-10-26 — Transaction Intelligence: mailing response, reach and lift, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 mailer figures from the ODD: each
offer's mailed, responded and response rate (offers still in flight left out, not shown as 0%), how
much of the base the program has reached, repeat response, the responder profile, organic against
program activation, and spend six months before against three months after each offer, net of the
mailed non-responders. Every figure matches v5 for 1776 CoastHills and 1761 CapEd. No deck changes
yet (the Campaign slides port in G9-06).

`ti/monthly_analysis/mailer.py` is v5's section, unchanged, run through `ti/odd_sections.py`, with v5's
`test_response_populations.py` (its 3 deck tests skip until G9-06 / G9-07). v5's
`test_mailer_consistency.py` is not ported: it drives v5's whole `metrics.compute` through the
`test_month_independence` harness, which the cut does not have. Parity: 47/47 on 1776 (2026-09) and
45/45 on 1761 (2026-10); the two keys 1761 lacks are conditional and absent from v5's run too.
DUPLICATES row 22.

### 2026-10-26 — Transaction Intelligence: the Value chapter

Summary: The Transaction Intelligence decks gain a seventh chapter, Value: What a card and an opt-in
earn (with the conversion math), The value ladder, Value per account by branch, What a responder is
worth, Where cards do not follow volume, and Where branches diverge. A slide whose figures are
missing is stated. 1776, both lenses: five slides drawn, "Where branches diverge" stated (no branch
diverges, as in v5's own run), 0 FAIL, 0 REVIEW. No ARS deck changes.

`ti/deck/value_inline.py` lifts v5's six inline value blocks out of `ars/deck/build.py` as `(h, m)`
builders, line for line. `ti/chapters/value.py` computes v5's dctr, rege, interchange and value
sections, then the leak post-passes on their figures, in v5's order, priced at the client's ICRate /
NSF_OD_Fee (filled from the workbook when blank), and registers the chapter after Economics. On 1776
(2026.10): a card is worth $183 a year and an opt-in $178. Tests: `tests/test_ti_value_chapter.py`.

### 2026-10-26 — Transaction Intelligence: where cards and opt-ins leak, priced, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 leak tables: the branches, age
bands, balance bands and products that hold more of the eligible base than of the debit cards or
Reg E opt-ins, ranked by accounts lost; the business gap; the Reg E default never asked; and what
each is worth a year at the value figures. Every figure matches v5 for 1776 CoastHills and 1761
CapEd. No deck changes yet (the Value slides port in G8-05).

`ti/monthly_analysis/leaks.py` is v5's post-pass, unchanged; `ti/odd_sections.leaks` runs it after the
dctr, rege and value figures and then v5's `value.apply_to_leaks`, in v5's order. It hands leaks the
account bases too: the debit half reads `n_eligible` from them, and the first version, without them,
skipped that half without a word (`tests/test_ti_leaks.py`). Parity: 14/14 on 1776 (2026-09) and 1761
(2026-10). The parity check only compares the keys the port returns, so a key v5 wrote that the port
never produces is not caught by it; for these sections every v5 `dctr_`, `rege_`, `value_`, `ic_`,
`wb_` and `gt_` key was checked by hand to be produced (the one left, `rege_by_balance_band`, is the
balance section's, ported earlier). DUPLICATES row 21.

### 2026-10-26 — Transaction Intelligence: what a card and an opt-in are worth, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 value figures: what a debit card
and a Reg E opt-in are each worth per account a year (interchange plus NSF/OD fees over the last 12
months, carded against not, opted in against not), the potential at three conversion rates, and the
same value by account age, response group and branch, with each gap split into how many accounts
carry the product and how much each one earns. Every figure matches v5 for 1776 CoastHills and 1761
CapEd. No deck changes yet (the Value slides port in G8-05).

`ti/monthly_analysis/value.py` is v5's section, unchanged, run through `ti/odd_sections.py`; it prices
at the client's ICRate / NSF_OD_Fee, filled from the workbook when the config leaves them blank
(G7-01). Its `apply_to_leaks` post-pass ships with leaks (G8-04). v5's empty-base test, skipped until
now, runs again. Parity: 54/54 on 1776 (2026-09) and 1761 (2026-10). DUPLICATES row 20.

### 2026-10-26 — Transaction Intelligence: an agenda of eight chapters fits

Summary: When a Transaction Intelligence deck carries more than four chapters, its agenda now lists
each chapter by name only, without the one-line description under it. With all eight chapters plus
Questions, each row is about half an inch tall, and each description ran into the next chapter's name
(validate_deck: eight FAILs on the agenda of 1776 CoastHills CU's eight-chapter deck). The description
still opens each chapter on its divider. Decks of up to four chapters are unchanged.

`build_ti_gen._agenda_headings_only` runs after the shared `assemble_combined.set_agenda`, which is not
changed, and removes the detail boxes once the agenda passes `AGENDA_DETAIL_ROWS` (5) rows.
`tests/test_ti_shell.py` builds four and eight stub chapters; at eight, the descriptions are gone and the
agenda has 0 FAIL (the test fails without the fix). Rebuilt 1776's eight-chapter shell: 0 FAIL.

### 2026-10-26 — Transaction Intelligence: PIN and signature interchange from the ODD, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 interchange figures from the ODD:
card spend split into PIN and signature, each priced at its own rate (solved so the blend equals the
client's interchange rate), the signature-share trend, what a PIN-to-signature shift would be worth,
and the PIN-heavy accounts, by type, age, product and response. Every figure matches v5 for 1776
CoastHills and 1761 CapEd. Figures only (v5 draws no slide from them); no deck changes.

`ti/monthly_analysis/interchange.py` is v5's section, unchanged, run through `ti/odd_sections.py` as
`interchange_odd` (apart from the transaction file's `interchange`). The parity check now fills a blank
`ICRate` / `NSF_OD_Fee` from the workbook figures v5's run recorded, as that run did before any section
priced anything. Parity: 36/36 on 1776 (2026-09) and 1761 (2026-10). DUPLICATES row 19.

### 2026-10-26 — Transaction Intelligence: the debit take rate and Reg E figures value reads, matching v5

Summary: The Transaction Intelligence cut now computes James's v5 debit take-rate and Reg E opt-in
figures, so the Value chapter can price what a card and an opt-in are worth and where the gaps are
(next stages). Every figure matches v5 for 1776 CoastHills and 1761 CapEd. The cut draws no
take-rate or Reg E slide of its own: those stay on the ARS deck. No deck changes.

`ti/monthly_analysis/dctr.py` and `rege.py` are v5's sections, unchanged, run through
`ti/odd_sections.py` (`dctr`, `rege`), with v5's Reg E code tests (`test_ti_rege_codes.py`; the one test
that reads v5's client config is skipped, since that file holds client data and stays out of this
repo). Parity: dctr 45/45 and rege 25/25 on 1776 (2026-09) and 1761 (2026-10). DUPLICATES rows 17-18.

### 2026-10-26 — Transaction Intelligence: the Economics chapter

Summary: The Transaction Intelligence decks gain a sixth chapter, Economics: Program P&L by offer, The
2:1 guarantee, Where the month's revenue came from, What each offer has earned, and What an account
earns as it climbs (the workbook's Lift Matrix). While a client has a deferred balance under the 2:1
guarantee, the P&L shows what the client actually pays; once the guarantee clears it shows the
workbook's billed figures. A client with no workbook or tracker gets each slide stated. 1776, both
lenses: all five slides drawn, 0 FAIL. No ARS deck changes.

`ti/deck/economics_inline.py` lifts v5's five inline economics blocks out of `ars/deck/build.py` as
`(h, m)` builders, line for line, with v5's stat tile. Two layout changes keep RPE's validator at 0
FAIL: a guarantee status wider than its tile steps its size down instead of wrapping ("Drawing Down"
on 1776), and the P&L's "latest n of N offers" note joins the footer instead of sitting on it.
`ti/chapters/economics.py` registers the chapter after ICS accounts. v5's deck-harness tests for
these slides are replaced by `tests/test_ti_economics_chapter.py`. On 1776 this repo's P&L slide and
v5's agree to the dollar ($1,121,691 revenue, $712,720 cost, $408,971 profit; DUPLICATES row 12).

### 2026-10-26 — Transaction Intelligence: the 2:1 guarantee from the client's deferral tracker, matching v5

Summary: The Transaction Intelligence cut now reads each ARS client's 2:1 guarantee deferral tracker,
as James's v5 engine does: revenue, charges, amount paid, amount deferred, the running deferred
balance, and whether the guarantee is clear, drawing down or in force. The trackers sit in a new
input folder, Inputs/Deferred Billing (30 clients today), filled from M:\My Rewards Logistics by
James's v5 fetch. Every figure matches v5 for 1776 CoastHills and 1761 CapEd. No deck changes yet
(the guarantee slide ports next); no ARS deck changes.

`ti/guarantee.py` is v5's `ars/guarantee.py`, unchanged, with v5's tests. `ti/deferred_input.py` finds
a client's tracker by its id as a whole number anywhere in the name (some names lead with a revision
date) and says what v5's run said after reading it: a missing tracker, one more than a month behind
the data, the guarantee's state, and any month whose revenue differs from the workbook's by more than
10%. `rpe_env.INPUT_KIND_DIRS` gains "Deferred Billing", in `NOT_SCANNED_KINDS` like "Deposits" (read
by exact folder; the watcher's copier and pruner never touch it). Parity (`--only guarantee`, on the
tracker v5's run read): 10/10 on 1776 (2026-08, 2026-09) and 1761 (2026-08, 2026-09). 1776 today:
$140,862 deferred, drawing down, through 2026-09. DUPLICATES row 16.

### 2026-10-26 — Transaction Intelligence: the ARS Workbook's economics, matching v5

Summary: The Transaction Intelligence cut now reads the client's ARS Workbook as James's v5 engine
does: the program P&L life to date and by month, revenue by offer, the Lift Matrix rate card, and the
current Interchange Rate and NSF Fee. Every figure matches v5 for 1761 CapEd and 1776 CoastHills.
When the client config leaves the Interchange Rate or NSF Fee blank, the workbook's values fill
them, as in v5. No deck changes yet (the economics slides port next); no ARS deck changes.

`ti/workbook.py` is v5's `ars/workbook.py`, unchanged, with v5's reader tests (`test_ti_workbook*`,
`test_ti_ic_rate_tolerance`); the tests for slides that port later are skipped under the stage that
brings them. `ti/workbook_input.py` finds the workbook in RPE's inputs by `build_month`'s rule
(`<id>-<yyyy.mm>-*Workbook*.xlsx`, never the Invitation Checking workbook) and backfills the rates;
`ti_build.compute_pack` merges the `wb_*` figures. Parity (`scripts/ti_parity.py --only workbook`, on the
workbook v5's run read): 26/26 on 1776 (2026-09) and 26/26 on 1761 (2026-10). DUPLICATES rows 12-15.
One line differs from v5: when the workbook is locked (open in Excel or syncing), the reader's temp
copy goes in an `rpe_env.temp_dir` folder instead of a bare `tempfile.mkstemp`, per this repo's
temp rule. The parity check skips a v5 run that read no workbook.

### 2026-10-27 — ILS is tracked in the roster

Summary: clients.md now lists Aaron's 67 ILS clients in an ILS roster table, so ILS is recorded alongside the other programs; it does not change what gets built.

Aaron, 2026-10-27: "Start tracking ILS in the roster too. You can check my clients for ILS analysis reviews." The table comes from the Velocity export's product list in `Client CSM List.csv`. ILS has no monthly deck, so `build_month.read_roster` skips the section and `read_ils_roster` reads it. Other CSMs' ILS clients are not listed yet.

### 2026-10-27 — The orange box is off the ARS Revenue Lift Matrix slide

Summary: The orange outline around one cell of the matrix on the ARS Revenue Lift Matrix slide is gone; the matrix and the bars beside it are unchanged.

Aaron, 2026-10-27: "Remove the orange box on the ARS Revenue Lift Matrix slide". `render_lift` no longer draws the outline on the caption's example cell. The caption text is unchanged.

### 2026-10-26 — A Transaction Intelligence slide with no data is stated, never silently left out

Summary: Two Transaction Intelligence slides, "When the card gets used" and "Recurring payments on the
card", were left out of 1776's deck without a word when their data was missing: v5's builders return
nothing in that case, and the cut only stated a slide whose builder gave a reason. Now any slide that
draws nothing is stated under its own title ("Not shown for this client: the figures it needs are not
in this client's files"), as every other missing slide is. No figure changes; the TI cut only, no ARS
deck changes. A 1776 deck gains those two stated slides (105 → 107 per lens).

`ti/deck/helpers.Deck.run` counts the slides before and after each builder; a builder that returned
None and drew nothing is treated as a decline. Found by reconciling the built 1776 deck (95 content
slides) against v5's slide list (97).

### 2026-10-27 — 1585 First Community Bank of the Heartland added to the roster

Summary: 1585 First Community Bank of the Heartland now appears in CSM Sheila and builds an ARS deck with its CashPlease section; it was missing from the roster.

James Gilmore, 2026-10-27, from Sheila: "1585 - ARS + CP + ILS - missing". The client has an ARS workbook, a DCO, a CashPlease tab (1,324 loans) and James as CSM, but no row in clients.md, so nothing built it. Added to the main table (MM path, ARS) and the CashPlease roster (ARS-CP section). ILS has no monthly deck and is not tracked in this file. 1766 Fort Sill FCU already reads ARS-ICS. The CashPlease summary names 1585 "First Community Bank of Tennessee", which looks like a name mix-up on the data team's side.

### 2026-10-27 — Sheila's button glow toned down

Summary: The glow and shading around Sheila's action buttons are much subtler; the buttons keep a light highlight and edge and still press down when clicked.

Aaron, 2026-10-27, from a screenshot: "buttons glow too much, let's tone it down". The coloured glow went from a 16 px blur at 38-42% to a 6 px blur at 16-18%, and the highlight and edge shading were halved. Colours, press movement and hover are unchanged.

### 2026-10-27 — Sheila redraws a client's buttons and verdicts when a build finishes

Summary: When a build finished, Sheila kept showing its button as "Building..." and, for Transaction Intelligence, the previous build's failure notice, beside a result that said Done. The client page now refreshes itself when the build ends.

Aaron, 2026-10-27, from a screenshot of 1075 Austin Bank: the Transaction Intelligence panel showed a greyed "Building..." button and "The last Transaction Intelligence build failed" over a "Done. The Transaction Intelligence decks are in Outputs." result. `follow()` redrew the progress when the job finished but not the page around it, which was drawn before the build started; it now re-reads the client's status (the server drops its cached one when a job ends) and draws it again, then the result. No figure or slide changes.

### 2026-10-27 — Transaction Intelligence deck: overlapping text and labels fixed

Summary: The Transaction Intelligence deck no longer has titles running into their subtitles or chart labels printing over each other, and the radar chart now shows all six of its axes.

Aaron, 2026-10-27, after reviewing the 1075 Austin Bank deck: "We also need to go through that transaction intelligence check and apply formatting rules. Lots of overlapping text." Found by rendering all 90 slides through PowerPoint, which the validator cannot do (it reads the picture charts as images). Fixed in the renderers, not in the deck:

- Titles are sized from the glyph measure of the bold face, with a 5% allowance for PowerPoint setting it wider, instead of a character count that put 98-character titles on two lines that rendered as three (slides 9 and 53). Down to 20 pt, then the lines are counted and the box grows.
- Block and treemap labels (`charts.fit_text`) wrap or step down to fit their block, and are cut with an ellipsis only at the floor (slides 8 and 63).
- Bubble names (`charts.place_point_labels`) are placed beside their own bubble, clear of other names and bubbles, instead of a fixed 14 points above the centre (slides 17, 46, 49, 50, 61).
- Two dollar signs in one label no longer turn it into italic mathtext ("$2,984 vs $6,044" printed as "2, 984vs6,044"), and the two comparison dumbbells (slides 15, 25) give each row its own unit and scale, with the change signed properly (it printed "2984.0%" and "+-3060.0").
- The Pareto's value labels stand clear of the cumulative line (slide 11); the donut's left-hand labels sit left of their leader (slide 48); the radar draws all six axes and their names (slide 39: matplotlib 3.11 had narrowed it to a quarter).

No figure changes. `tests/test_ti_formatting.py` pins each of these; every one of its twelve tests fails on the code before this change.

### 2026-10-27 — Sheila's action buttons are lit, not flat

Summary: The Build, Check again, Recalculate and Export buttons in Sheila now carry a light
along the top edge, shade along the bottom, a line where they meet the page and a glow in
their own colour, and they press in when clicked. Nothing about what they do changed.

The recipe is the four-shadow button Aaron pointed at (2026-10-27): `button.primary` in
`ars_launcher_web.py` layers `inset 0 1px 0` white, `inset 0 -2px 0` black, `0 1px 2px` black
and a `--glow` in the button's own colour (navy, or orange for `.warn`); `:active` swaps the
highlight for an inset shade and moves the button down a pixel; a disabled button is flat
grey as before; reduced motion drops the transition.

### 2026-10-26 — The cover, section dividers and closing slide use the CSI brand template's design

Summary: Every deck's cover, section dividers and closing slide now follow the CSI brand template: a white cover with the blue band and the CSI logo, gradient dividers with the sunrise wedge, and a gradient closing slide with the large logo.

Aaron, 2026-10-26: "start the larger template rebuild" (after the orange-only restyle, #62), from "Updated Brand Presentation Sept. 2026.potx".

`build/cover_divider.py` draws all three. The art (the slanted band, the red-to-gold wedge, the gradients, the three logo pictures) is lifted out of the template once by `scripts/extract_brand_art.py` into `build/assets/csi_brand/` with its theme colours made literal, because the shells' theme is the stock Office one and `accent2`..`accent5` mean other colours there; `build/brand_art.py` places it. The client name is now the 60 pt cover title with the "Executive Review  •  <month>" line under it (the line the validator and combiner read), the products are outline chips, and the client's logo sits on a white card at the top right; the 84 pt month and the orange client name are gone. Dividers: the section name at 52 pt, the benefits line at 24 pt, the progress track moved up to 5.65" to clear the wedge. The closing slide is redrawn by `cover_divider.restyle_closing` in the ARS, ICS and MRPC builders and `redraw_closing_in_place` in CashPlease and Transaction Intelligence, keeping the "<client>  •  <month>" line each swapped in; it adds the template's "csiweb.com". **The "| Velocity Solutions" half of the old lockup is gone from these three slide types:** the template's logo is CSI alone. A first render showed two defects, both fixed: the combiner put the product chips straight after the background, which hid them behind the band, and the logo's coloured mark vanished against the orange wedge (the divider uses an all-white version, made by the extractor). Checked by rendering Austin Bank 1075 (ARS+ICS+MRPC) and WesBanco 1632 (ICS+CashPlease) through PowerPoint and looking at the cover, dividers and closing slide; both validate with 0 FAIL. **Not done:** the Contact Us slide, the Executive Summit slide, the content slides' own look, the shells' theme colours, and Sheila and the dashboard pages.

### 2026-10-26 — The Sept. 2026 brand orange (#F15D22) on every deck

Summary: Decks are drawn with the new CSI orange from the Sept. 2026 brand template instead of the old one.

Aaron, 2026-10-26: attached "Updated Brand Presentation Sept. 2026.potx" and asked for a full multi-product deck with the branding template; tested on Austin Bank (1075) with the smaller restyle option, then "merge #62 once CI passes".

The template's slide 18 gives the palette: navy 00274C (unchanged), light blue 035B95, orange F15D22, gold F8971D, red EB2A2E. The pipeline's orange was F47A29. This changes the orange only: `brand.ORANGE` and the orange ramps, the literal colours inside the template shells and the five reference decks (`scripts/recolor_shells.py`, 259 literals; `--check` reports any left), and two builders (`build_mrpc_gen`, the ARS Contact slide) that wrote the old orange as their own literal and are now on `brand.ORANGE_RGB`. Light blue, gold and red are defined in `brand.py` (`CSI_LIGHT_BLUE`, `CSI_GOLD`, `CSI_RED`) but nothing uses them yet. **Not done:** the theme colours in the shells (the stock Office theme; much of the shells' fill and text follows `accent1` / `dk1`, and the new template's `dk1` is blue), the template's own cover, divider and closing layouts and its gradients, and the Sheila and dashboard pages, which keep the old orange. Austin Bank 1075 combined deck rebuilt: 67 slides as before, 0 FAIL / 35 REVIEW as before, 0 old-orange literals (126 before), and the 53 chart images are drawn in the new orange. `tests/test_brand_single_source.py` fails if a builder writes the orange itself or a shell holds a retired colour.

### 2026-10-26 — Sheila's build progress: no "Full output" box, and Transaction Intelligence builds show it in their own panel

Summary: CSM Sheila no longer has a "Full output" box under a build, and a Transaction Intelligence build now shows its progress inside the Transaction Intelligence panel at the bottom of the client page.

Aaron, 2026-10-26: "We can remove the 'full output' section. It's redundant, unless it actually shows more information than the summary workflow." and "move the workflow output to the bottom section."

The box repeated the step list and the checks already shown above it. It was the only place that showed the launcher's own lines after the first step, though: the validation result, a warning, where the deck went. Those lines are now part of the result under the steps (a warning in the warning colour; a STOP line stays the reason it was). The progress list of a Transaction Intelligence build is drawn in `#jobti`, inside that panel under its Build button; every other build draws it where it was. Checked in a browser against fake in-progress, finished and failed jobs for 1075.

### 2026-10-26 — Sheila shows her version, starting at 2.0

Summary: CSM Sheila's header now shows the version, v2.0, so you can tell which release a PC is running.

Aaron, 2026-10-26: "roll the version number forward since we've added a major feature"; then "VERSION file in Sheila's header, start at 2.0".

The project had no version number before this: what was released was named only by the date and commit in `RELEASE.txt`. `VERSION` at the root of the repo holds it (first line, `2.0`); `ars_launcher_web.app_version` reads it and the header shows it beside the name. `release_launcher.ps1` copies it with the code, so every PC's local copy carries it. A copy without the file, or with one that is not `N.N` or `N.N.N`, shows no version rather than a guess. It is bumped by hand, in the commit that adds a major feature. It starts at 2.0 because a major feature has just been added.

### 2026-10-26 — The ODD extract step is about a third faster on a large client

Summary: Reading a large client's ODD extract takes about a minute instead of a minute and a half, with identical figures. Small clients are unchanged.

Aaron, 2026-10-26: "start on oddd_optimize and metrics_gen."

`scripts/oddd_optimize.py`, profiled on 1100 Rally (439 MB extract): 92 s -> 63 s, and `oddd_metrics.json` and `oddd_pack.md` are byte-identical to the old code's on 1100, on 1549 Wellworth and on 1204 First State Bank (1549 and 1204 were 10 -> 9 s and 14 -> 13 s). Two changes: the CSV read uses `dtype=object` instead of `dtype=str` (pandas 3 builds Arrow strings for the latter; 22 s of the read), and `classify_rege` maps through a dict built from the column's unique values instead of a lambda that ran once per cell (12 million calls). `metrics_gen` was profiled but not changed: its time is the per-cell accessors in `odd_rows.py`, already tuned, and the saving would come from fewer calls, not faster ones.

### 2026-10-26 — A new ARS client builds: blank path reads as MM, the P&L reads three months

Summary: A new ARS client with no path recorded now builds on the Lift Matrix (MM) model instead of stopping on the template's placeholder tabs, and its Financial Performance slides now work with as few as three months of actuals.

Aaron: "All new clients will be on MM revenue calculations. Also we need to work with as few as 3 months of data. Use both revenue labels also (revenue/revenues)." 1805 Texar FCU's build stopped with UNEVALUATED WORKBOOK: its `clients.md` path was `—`, so `build_month` took the SM branch and read the plain `Executive Financials` tab, the template's "Bank Name, October 2007". Its `Executive Financials MM` tab was filled in (3 months, 1 mailing, $3,943).
- `clients.md`: 1805 is MM. Every other ARS row's path was checked against its workbook's `Executive Financials MM` tab (49 clients): all agree.
- `build_month.read_roster`: an ARS row whose path is blank or `—` is MM. SM is recorded, never assumed, so every consumer of the path (launcher, Sheila's Lift Matrix tab, dashboards) sees it.
- `actuals_tab.read`: the month header row needs 3 date columns, not 5, and the revenue row is found under "Total Marginal Revenue" as well as "Total Marginal Revenues".

### 2026-10-26 — A failed validation names its slide in Sheila; a decimal is not a count

Summary: When a build fails validation, Sheila now shows each FAIL line (the slide and the rule)
under the verdict instead of only "1 FAIL, 10 REVIEW". The validator no longer reads a decimal
such as "2.15 of 4" as the impossible count "15 of 4". A Transaction Intelligence build keeps
its own log, so its step list no longer replays the Executive Review's steps.

Austin Bank's Transaction Intelligence build (2026-10-26) stopped at "1 FAIL" with nothing in
Sheila to say why; the validator's own output had it: slide 26, "mean breadth 2.15 of 4" read as
"15 of 4". `ars_launcher.run_validator` runs the validator once and returns the verdict and the
FAIL lines, which both build paths print as STOP lines; the count rule requires whole numbers on
both sides. `tests/test_impossible_count.py` pins the decimal case.

### 2026-10-26 — Chart value labels shorten when they would run together

Summary: On the ICS revenue charts, the dollar figure above each bar is written in full unless the
figures would overlap, in which case every label on that chart is shortened to the $12.3K form. The
KEMBA CU composition chart Cindy reviewed had three labels running together across twelve cohorts.

Aaron, 2026-10-26: "some of the column labels were overlapping. This was due to longer currency
numbers. If labels are going to overlap we can summarize $17,200 as $17.2k, or M for millions."
Twelve cohorts (nine until 2026-10-13) of five-digit totals on an 11.5-inch figure leave 0.74 inches
per bar, and "$12,260" in 16 pt bold Carlito is wider than that. `brand.bar_labels` measures the
labels with `textfit` against the room `ics_charts_gen.slot_in` reads off the axes, and returns the
full set or the compact set (`usd_compact` with one decimal at K), never a mix; the cohort bar charts
and the composition chart use it. Nothing in the gate can see a chart's text, so the renderer proves
the fit; `tests/test_brand.py` pins the switch.

### 2026-10-23 — The Transaction Intelligence check's window ends at the data month

Summary: Sheila's count of transaction files on hand now covers the same twelve months the
Transaction Intelligence build reads, ending at the month before the cycle; it had run one month
ahead. No deck changes.

Running the portfolio analysis for 1615 Cape & Coast on 2026-10-23 showed the builder's window as
Oct 25 to Sep 26 (the ODD's newest month is September) while Sheila's check said Nov 25 to Oct 26 and
reported October missing. `ars_launcher.txn_months_on_hand` now anchors on the month before the
period, as `ti_build` does through `odd.frame_data_month`.

### 2026-10-23 — Sheila builds the Transaction Intelligence decks as a separate presentation

Summary: An ARS client's page in CSM Sheila now has a Transaction Intelligence panel under the
Executive Review checks, with its own readiness checks and a button that builds the Transaction
Intelligence decks (one per lens) into Outputs beside the Executive Review, never in its place. The
list shows "TI in Outputs" separately from "In Outputs". Until a chapter of the cut is ported the
panel says so and builds nothing.

Aaron, 2026-10-23: "add the ability to create a separate Transaction Intelligence presentation,
separate from the currently approved RPE presentation. Add checks for the dependencies to the
readiness check with appropriate caching and optimizations." `ars_launcher.py build <id> --ti`
runs James's `ti_build.py`, validates each deck (0 FAIL and the package check) and files it with
`ti_to_outputs`, which supersedes only the same file name; `status <id> --ti` prints the checks.
`ti_checks` names each dependency: a ported chapter, the client on ARS, this period's ODD extract,
the client's codes (the v5 config file, else `ars_code_tables.json`, which is parsed once and again
only when its size or time changes), the transaction files on hand for v5's twelve-month window
(counted from the file names in `Inputs/Txn Files/<id>/` with James's own name and window rules,
no zip opened; the folder listing is one of Sheila's share answers kept for `SHARE_TTL`), and the
ICS lists for the ICS lens. A TI deck in Outputs is never read as the period's RPE deck, and an RPE
build never archives one. A failure in the TI checks never costs the RPE status. The routing for
James's `feat/ars-ti/...` branches is written down in `CLAUDE.md`, `docs/COLLABORATORS.md` and a new
pull request template.

### 2026-10-23 — A Transaction Intelligence KPI card low on a slide keeps its note under its value

Summary: On a compact KPI card (one drawn low on the slide), a note long enough to wrap was moved by
fit_layout's caption rule into the logo zone and then lifted back over the card's value: 1776's ICS
habits slide drew "vs 72% non-ICS — the card has to exist first" over "75%" (validate_deck FAIL,
both lenses). `ti/deck/helpers._kpi` now places the note where its measured lines fit inside the
card and no lower than fit_layout's own estimate would put it, shrinking the value's box to make
room. No figure changes; the TI cut only, no ARS deck changes. 1776, both lenses: 104 slides, 0 FAIL.

### 2026-10-23 — The Transaction Intelligence cut's two stacks are one: five chapters in deck order

### 2026-10-23 — Deposits: "What arrives against what leaves" reads the transaction figures

Summary: The deposits slide that sets money arriving against card money leaving now draws: it needs the
transaction figures, and the deposits chapter now receives them the way James's v5 engine hands them on.
1776 CoastHills: the slide drew where it was stated before. No ARS deck changes.

v5's run passes the transaction figures to the ODD sections as `config["_txn"]`
(`monthly_analysis/metrics.py`: `config = dict(config, _txn=txn)`), and `deposit_behaviour` reads them for
`dep_vs_card_spend`. The Transaction Intelligence chapter computes first in deck order, so
`ti/chapters_txn.compute_all` ends by handing its figures on the same way. Test:
`test_ti_chapters_txn.py::test_the_transaction_figures_reach_the_odd_sections_as_v5_hands_them_on`.

### 2026-10-23 — Deposits: where money in flight is already going, matching v5

Summary: The flight overlay is ported: the accounts whose balance is falling against its average,
joined to the named competitors and providers their money already goes to. Matches James's v5 engine
for 1776 CoastHills. With this the transaction side of every chapter is in: the Attrition chapter's two
cross-source slides now draw. No ARS deck changes.

`ti/transaction_intelligence/overlay.py` is ported unchanged; it reads the competitor rows and the
addressable accounts the earlier sections hand on (`ti/txn_sections.overlay`, after relationship, as in
v5's run). v5's overlay tests rejoin `test_ti_txn_sections.py` (now whole) and
`test_ti_txn_attrition_slides.py` comes across. Parity: 18/18 on 1776 (2026-09).

### 2026-10-23 — Competition: where the branch loses accounts and leaks money, matching v5

Summary: The branch hotspots are ported: each branch's closure rate beside its competitor leakage, so the
branches losing on both show together. They feed "Where we leak, by branch" and "Where we lose and where we
leak". Matches James's v5 engine for 1776 CoastHills. No ARS deck changes.

`ti/transaction_intelligence/hotspots.py` is ported unchanged with v5's `test_hotspots.py`; it joins the
attrition and competition figures and recomputes neither (`ti/txn_sections.hotspots`, run after the
stressors and before the family tables, as in v5's run). Parity: 11/11 on 1776 (2026-09).

### 2026-10-23 — Attrition: stresses counted across the ODD and the transaction file, matching v5

Summary: The cross-source stressor count is ported: the ODD's at-risk conditions plus "banking
elsewhere", which only the transaction file can see, counted per account. Matches James's v5 engine for
1776 CoastHills. No ARS deck changes.

`ti/transaction_intelligence/stressors_txn.py` is ported unchanged with v5's `test_stressors_txn.py`; it
reads the competitor rows the competition section hands on and the ODD-side conditions, facts,
attrition hazard and stressor count (`ti/txn_sections.stressors_txn`, after leakage, as in v5's run).
Parity: 10/10 on 1776 (2026-09).

### 2026-10-23 — Attrition: competitor spend before a closure, matching v5

Summary: The "Competitor spend before closure" figures are ported: whether money paid to competitors
climbs in the months before an account closes, against open accounts of the same tenure. Matches James's
v5 engine for 1776 CoastHills. No ARS deck changes.

`ti/transaction_intelligence/leakage.py` is ported unchanged; it reads the competitor monthly series the
competition section hands on and the ODD's lifecycle curve, as in v5's run (`ti/txn_sections.leakage`,
after relationship). `ensure_competition` runs financial services and competition once per context, so
the checks of the sections that read them share one run. v5's `test_txn_attrition_report.py` comes
across. Parity: 9/9 on 1776 (2026-09); 1761 was not run (memory was short while another build ran).

### 2026-10-23 — The Transaction Intelligence cut's two stacks are one: four chapters in deck order

Summary: The transaction chapters (Transaction Intelligence, Competition) and the ODD chapters
(Attrition, Deposits, ICS accounts), built in parallel, are merged into one cut. Its chapters now run
in deck order: Transaction Intelligence, Competition, Attrition, Deposits, ICS accounts. No ARS deck
changes.

`ti/chapters/` is the one chapter registry (`ALL`, read lazily as `ti.cut.CHAPTERS`): the transaction
chapters are thin modules (`transaction_intelligence.py`, `competition.py`) over `ti/chapters_txn.py`,
which both share. `Deck.run` states only the reason when v5 words a decline as "<label> (<reason>)",
the label being the slide's title or close to it, and still fixes "1 accounts" after the run.

### 2026-10-23 — Transaction Intelligence: the ICS accounts chapter

Summary: The Transaction Intelligence cut gains the ICS accounts chapter: the accounts the ICS
programme opened, found in the ODD from the client's direct-mail and referral lists, against the
rest of the book (activation, cohorts, usage, quality, closure, branches, composition, personas,
retention). Nothing else in this repo reads ICS accounts from the ODD. Built for 1615 Cape & Coast
(241 ICS accounts) in both lenses, 0 FAIL. Opt-in (RPE_TI=1); no deck changes elsewhere.

v5's ICS section (`ti/monthly_analysis/ics.py`) and ICS chapter (`ti/deck/ics_slides.py`) are ported
unchanged with v5's ICS tests. `ti/chapters/ics.py` turns every slide v5 skips into a stated slide
under its own title, states the one v5 leaves out without a word (ICS channel with no channel rows),
and keeps v5's order; a client with no ICS accounts gets one stated slide. Primacy and merchants read
the transaction chapter's lens rows and are stated until it is in the build. Two adapter fixes:
slides are numbered after their title is drawn, so the first text shape is the title; and a KPI card
placed low is drawn compact above the content floor, since a full card ran to 7.15in and the layout
pass re-parked its note over its value (1615's ICS quality slide). Parity: ICS 46/46 on 1776
(2026-09). Real build, 1615: 46 slides per lens deck (attrition, deposits, ICS), 7 stated, 0 FAIL,
13 REVIEW (superlative and caption checks). Test: `test_ti_ics_accounts_chapter.py`.

### 2026-10-23 — Transaction Intelligence: the Attrition chapter

Summary: The Transaction Intelligence cut gains its Attrition chapter: closure rates by branch, how
much warning a closure gives, accounts under several stresses, new-account cohorts, where closures
cluster, where the risk sits, attrition by group and survival by tenure. Built for 1615 Cape & Coast
in both lenses with the Deposits chapter, 0 FAIL from the validator. Opt-in (RPE_TI=1); no ARS deck
changes.

`ti/chapters/attrition.py` computes v5's retention, lifecycle, attrition, stressors and profile
sections once (profile carries the survival figures; parity 64/64 on 1761) and draws v5's five
attrition-module slides (`ti/deck/attrition_slides.py`) plus three that v5 drew inline in its deck
builder, lifted out unchanged into `ti/deck/attrition_inline.py`. The two slides that read the
transaction file (competitor spend before closure, stresses across both files) come with the
transaction chapter's port; until it is in the build they are stated, not dropped. The chapter sits
ahead of Deposits. A ported table that would run into the slide number's band (7.0in) now tightens
its rows (to 0.18in, font scaled, never below 7pt) instead of running off the slide, and keeps every
row: 1615's closure-hazard table ended at 7.65in on a 7.5in slide. Real build, 1615: 28 slides per lens deck, 3 stated, 0 FAIL, 6 REVIEW
(superlative and caption checks). Tests: `test_ti_attrition_slides.py`, `test_ti_table_fit.py`.

### 2026-10-23 — Transaction Intelligence: the Deposits chapter

Summary: The Transaction Intelligence cut has its first full chapter, Deposits: how money arrives,
who is paid here, who stopped, income type, tax refunds, overdrafts by how members are paid, who
banks here first. Built for 1615 Cape & Coast from its own deposits file, in both lenses, 0 FAIL
from the validator. The cut is still opt-in (RPE_TI=1); no ARS deck changes.

v5's deposit-behaviour section (`ti/monthly_analysis/deposit_behaviour.py`, with the deposit streams
module) and its eleven slide builders (`ti/deck/deposit_slides.py`) are ported unchanged with v5's
deposit tests. `ti/chapters/` holds the cut's chapters in deck order (`ti.cut.CHAPTERS` resolves
from it on first use); `ti/chapters/deposits.py` computes balance and deposit behaviour once and
draws the eleven slides in each lens deck. A builder that declines is stated under its own title,
without repeating the title in the reason.

Real build, 1615 (2026-10-23, `Inputs/ODDD` and `Inputs/Deposits`): 135 deposit figures; each lens
deck 17 slides (shell, divider, eleven deposit slides); ten draw, and "What arrives against what
leaves" is stated (it needs the transaction chapter's card spend, which is ported separately);
`validate_deck` 0 FAIL, 2 REVIEW (the "largest" superlative check). Parity of deposit behaviour on
1100 (8 million deposit rows) is still to run: the machine had under 1 GB free during this change.

### 2026-10-23 — Inputs/Deposits: the ILS deposits extract, read by the Transaction Intelligence cut

Summary: A new input folder, Inputs/Deposits, holds each client's rolling 365-day deposits extract
(five clients so far). The Transaction Intelligence cut reads a client's own file from it; nothing
else reads it, and the morning watch leaves it alone. No deck changes.

`rpe_env.INPUT_KIND_DIRS["Deposits"]`, added to `NOT_SCANNED_KINDS` so the watcher's copier and pruner
never touch it. `ti/deposits_input.py` takes only the client's OWN file (the name must start with the
client id): v5 at a491b5c gave 1776 the only file on disk, 1100 Rally's, and joined 0% of accounts.
The CSV is staged out of its zip once into the local cache and parsed by v5's deposits loader
unchanged; `ti_build.py` attaches it to the config as v5's run does, and a client with no file, or a
file that parses to nothing, is stated, never attached. The parity check attaches the rows v5's own
run read, from v5's cache, and only when that file was the client's own. Parity with deposits: 1100
balance 36/36 and stressors 11/11 (2026-09). 1776's v5 deposit figures were computed on Rally's file
and are no reference. Test: `test_ti_deposits_input.py`.

### 2026-10-23 — Transaction Intelligence: accounts under several stresses, and balances

Summary: The stressor analysis (accounts carrying two or more at-risk conditions at once) and the
balance analysis it reads (flight risk, sleeping balances, primary-institution signals) are ported.
Every figure matches James's v5 engine for 1761 CapEd, which has no deposits file; for clients with
one, the deposit-driven figures wait on the deposits port. No deck changes.

`ti/core/conditions.py` (the named at-risk conditions), `ti/monthly_analysis/stressors.py` and
`ti/monthly_analysis/balance.py` (whose flight-risk mask a condition uses) are ported unchanged with
v5's conditions and stressors tests; the stressor frame v5 pops before writing is kept for the
call-ready list. Parity: on 1761 (2026-10) balance 36/36 and stressors 11/11. On 1776 and 1100
(2026-09) every difference is a deposit-driven figure (flight risk basis "inflow" vs "balance proxy",
the deposit join rate, the deposits-slowing condition): v5's runs read the clients' deposits files,
which the cut reads from the deposits port onward.

### 2026-10-23 — Transaction Intelligence: attrition, matching v5

Summary: The attrition analysis is ported: closure rates by branch, product, lens group and account
age, the censoring-correct closure hazard, and new accounts cohort by cohort. Every figure matches
James's v5 engine for 1761, 1776 and 1100. No deck changes.

`ti/monthly_analysis/attrition.py` is ported unchanged with v5's attrition tests (by lens, cohort,
exposure, months and control). Parity: 62/62 on 1761 and 1100, 67/67 on 1776. An overlap with the
opt-in "Where Accounts Close" view is already in `docs/migration/DUPLICATES.md` (rows 7 and 8).

### 2026-10-23 — Transaction Intelligence: how much warning a closure gives, matching v5

Summary: The lifecycle analysis is ported: card activity in the months before an account closes,
against open accounts of the same tenure, and the same curves for ICS accounts. Every figure matches
James's v5 engine for 1761, 1776 and 1100. No deck changes.

`ti/monthly_analysis/lifecycle.py` (the event-time maths), `lifecycle_report.py` (v5's "lifecycle"
section) and `lifecycle_ics.py` (the ICS cohort, which the section reads when ICS accounts are on the
frame) are ported unchanged with v5's lifecycle tests. Parity: 18/18 on 1761 and 1100, 31/31 on 1776
(an ICS client, so its ICS curves are compared too).

### 2026-10-23 — Transaction Intelligence: account retention, matching v5

Summary: The retention analysis is ported: which accounts are active, cooling, declining or dormant,
survival by tenure, and the at-risk cuts behind the attrition chapter. All 34 figures match James's
v5 engine for 1761 CapEd, 1776 CoastHills and 1100 Rally CU. No deck changes.

`ti/monthly_analysis/retention.py` is ported unchanged with v5's retention tests. `ti/odd_sections.py`
runs v5's ODD sections on the shared context, as `ti/txn_sections.py` runs the transaction ones; its
`PARITY` entries join the parity check's registry. A second pandas 2 / pandas 3 difference is
restored inside `ti.compat.legacy_strings()`: pandas 3 returns NaT for `pd.to_datetime(None)` where
pandas 2 returned None, and v5 tests `is not None` after reading an optional date column (24 places),
so a missing column raised instead of skipping its cut. `tests/conftest.py` now applies the same
`legacy_strings()` to `test_ti_*` tests. Parity: retention 34/34 on 1761 (2026-10), 1776 and 1100
(2026-09), run on v5's own config at `a491b5c`.

### 2026-10-23 — Transaction Intelligence charts put months in the house format

Summary: Months on the Transaction Intelligence charts now read "Sep'25", the format every other deck
uses, instead of v5's "Sep 25". Nothing changes on the ARS deck.

v5's two month-label helpers (`ti/deck/charts._month_label`, `ti/deck/txn_value._month_label`) now go
through `periods.mon_yy`, and `ti/deck/charts.py` installs `periods.install_month_axis_guard()` as RPE's
own chart modules do, so a month drawn off-format fails the render instead of shipping. The suite caught
it only when another chart test had installed the guard first; the cut now installs it itself. 1761
rebuilt with the guard: no chart failed, 0 FAIL.

### 2026-10-23 — The Transaction Intelligence and Competition chapters draw their slides

Summary: The cut now builds real slides: a Transaction Intelligence chapter (39 slides: money flow,
leakage to outside providers, card use, merchants, PIN or signature, channels) and a Competition chapter
(20 slides: who competes, the local field, wallet share, winback, BNPL), each with a divider carrying its
three headline figures. 1761 CapEd builds both lens decks from its real files at 0 FAIL. Still opt-in
(RPE_TI=1); no ARS deck changes.

`ti/deck/` gains v5's six transaction slide modules (`txn_slides`, `txn_leakage`, `txn_cards`,
`txn_value`, `txn_compete`, `txn_attrition`), ported unchanged except as listed below, with nine of
v5's slide test files. `ti/chapters_txn.py` defines the two chapters: the Transaction Intelligence
chapter computes v5's whole transaction sequence once for both chapters and both lenses; a client with
no transaction figures gets one stated slide per chapter. In the ICS lens deck the slides that walk v5's
lens list show all accounts plus the ICS groups; in the ARS deck they are drawn as v5 draws them.

Fixed against RPE's validator and a PowerPoint render of 1761 (v5's own validator passed all of these):
the callout tiles fit every label, value and note to the tile with RPE's glyph measure, and draw value
and note as one text box (as two boxes the lowest note sat in fit_layout's caption band and was lifted
onto the value); a subtitle is held to two lines (it ran under the chart); the content and the tile
stack start below wherever the headline block ends and never reach the logo band; "1 accounts" reads
"1 account" in text and chart labels; a tile that named v5's `clients_config` now says "in the client
config". 1761 (2026-10, from Inputs): 63 slides per lens deck, 56 drawn, 7 stated with v5's reasons
(one-rail feed, no filed store, no competitor past the winback threshold, …), 0 FAIL.
Tests: `test_ti_chapters_txn.py` and the ported slide tests.

### 2026-10-23 — Competition: filed growth from the regulators' own reports (no store yet)

Summary: The "Filed growth" figures are ported: what each named competitor reports to the FDIC or NCUA,
quarter by quarter. They need a public reference store that is not on the share yet, so for now the
build says the store is missing and adds nothing. No deck changes.

`ti/core/filed/` and `ti/core/market/` are ported unchanged with v5's five filed test files (31 tests).
`ti/txn_sections.filed` adds the `comp_filed*` figures to the competition figures, as v5's run does,
reading the store from `TI_REFERENCE_DIR`, else `Inputs/Market Reference`, and the client's market record
from `TI_MARKET_DIR`, else `Inputs/ARS Settings/market/<id>.json`. The store is ~100 MB of public FDIC and
NCUA data (no client data); where it should live on the share is an open question. There is no v5 figure
to check against: every reference run's own filed step was skipped (1761, 2026-10-23: "reference cache
incomplete … missing fdic_financials"). Test: `test_ti_filed_section.py` (no store is stated, the figures
handed in are never edited, only added or changed keys come back).

### 2026-10-23 — The Transaction Intelligence build log carries v5's competition and section read-outs

Summary: When the Transaction Intelligence cut builds, its log now lists the competition figures and
the section tables in the same plain-text form James's v5 engine printed after a run. Nothing changes
on any deck.

`ti/transaction_intelligence/competition_report.py` and `sections_report.py` are ported unchanged and
printed by `ti_build.py` after the pack is written. `test_ti_competition_part2.py` comes across, and the
two family-table read-out tests rejoin `test_ti_txn_sections.py` (the overlay tests return with the
flight overlay).

### 2026-10-23 — Transaction Intelligence: what the dictionaries do not know yet, matching v5

Summary: The mapping audit is ported: the card merchants and transfer counterparties none of the three
dictionaries recognise, ranked by dollars, so the dictionaries can be extended. Reports only; no other
figure moves. Matches James's v5 engine for 1761 CapEd. No deck changes.

`ti/transaction_intelligence/mapping_audit.py` is ported unchanged; it reads all three dictionary specs
and financial services' providers, as in v5's run. v5 has no test file for it; the parity check is its
test. Parity: 8/8 on 1761 (2026-10).

### 2026-10-23 — Competition: who competes for the client's members, matching v5

Summary: The competition analysis is ported: which banks, credit unions and payment ecosystems the
client's personal accounts send money to, how much, how many competitors each account uses, the local
field, winback targets and BNPL. Every figure matches James's v5 engine for 1761 CapEd. No deck changes.

`ti/transaction_intelligence/competition.py` is ported unchanged; it reads the competitor dictionary
(`ti/dictionaries/`), the client's own local-competitor and self names (`ti/config.py`), and financial
services' row classification, and hands the competitor rows on to the overlay, leakage and stressor
sections as v5's run does. Eight of v5's competition test files come across (`test_ti_competition*.py`,
`test_ti_fin_attribution.py`, `test_ti_matcher_normalise.py`, `test_ti_txn_formats_1192.py` /
`_1585.py`); one test that reads the slide builder's source waits for the chapter slides. Parity: 79/79
on 1761 (2026-10); on 1776 (2026-09) all 53 figures v5 wrote match.

### 2026-10-23 — Transaction Intelligence: transactions by branch, product and swipe tier, matching v5

Summary: The three family tables are ported (accounts, transactions and dollars per branch, per
product and per swipe tier). They match James's v5 engine for 1761 CapEd and 1776 CoastHills. No
deck changes.

v5's run builds them from the transaction-side lens (`family_table`, already ported); the closing
block of its run is now `ti/txn_sections.family_tables`. Parity: 6/6 on 1761 and 1776.

### 2026-10-23 — Transaction Intelligence: how broad the relationship is, matching v5

Summary: The relationship analysis is ported: how many channels each personal account uses, which
travel together, what a second channel is worth, and the billers paid from the account. Every figure
matches James's v5 engine for 1761 CapEd and 1776 CoastHills. No deck changes.

`ti/transaction_intelligence/relationship.py` is ported unchanged; it reads the row classification the
financial-services section leaves behind, as in v5's run. v5's relationship tests rejoin
`test_ti_txn_sections.py`, and `test_ti_interchange_txn.py` comes across. Parity: 21/21 on 1761
(2026-10); on 1776 (2026-09) all 19 figures v5 wrote match (2 were added to v5 after that run).

### 2026-10-23 — Transaction Intelligence: PIN or signature, matching v5

Summary: The PIN / signature mix is ported: who routes PIN, PIN-heavy accounts, where PIN gets pressed,
by age and product. Unpriced, as in v5 (the ARS deck owns interchange dollars). Every figure matches
James's v5 engine for 1761 CapEd. No deck changes.

`ti/transaction_intelligence/interchange.py` is ported unchanged on the personal card base. Parity:
30/30 on 1761 (2026-10); v5's 1776 run (2026-09) predates this section. Its v5 test also exercises
the relationship section and comes across with it.

### 2026-10-23 — Transaction Intelligence: how the card is used, matching v5

Summary: The card-behaviour analysis is ported: ticket size and intensity bands, recurring payments on
the card, when the card is used, and how each group behaves. Every figure matches James's v5 engine
for 1761 CapEd and 1776 CoastHills. No deck changes.

`ti/transaction_intelligence/card_behavior.py` is ported unchanged, on the personal card base
(`ti/txn_sections.py`). v5's `test_txn_sections.py` comes across as `test_ti_txn_sections.py` with
the tests for sections not yet ported held back (relationship, overlay, v5's text report; each
returns with its section). Parity: 15/15 on 1761 (2026-10) and 1776 (2026-09).

### 2026-10-23 — Transaction Intelligence: card spend by merchant and who spends, matching v5

Summary: The merchant analyses are ported: where personal card spend goes by merchant and category,
which merchants are rising, new or fading, the MCC codes behind the categories, and card use by age
and tenure. Every figure matches James's v5 engine for 1761 CapEd. No deck changes.

`ti/transaction_intelligence/merchants.py` and `merchant_profiles.py` are ported unchanged with v5's
MCC-mapping and merchant-profile tests; both run on the personal card base, sharing one category spec
(`ti/txn_sections.py`). Parity on 1761 (2026-10): merchants 28/28, merchant profiles 25/25. On 1776
(2026-09) merchants match 28/28; v5's run there predates the merchant profiles, so it has none of
their keys to compare.

### 2026-10-23 — Transaction Intelligence: financial services and leakage, matching v5

Summary: The financial-services analysis is ported: which outside lenders, card issuers, brokers,
P2P apps and fintechs the client's personal accounts pay, how much, how recently, and what is still
within reach; business accounts reported apart. Every figure matches James's v5 engine for 1761
CapEd. No deck changes.

`ti/transaction_intelligence/financial_services.py` is ported unchanged with v5's single-token test.
`ti/txn_sections.py` is v5's transaction run, one section at a time, shared by the build and the
parity check; what later sections need (the row classification, the personal and business accounts,
the addressable accounts) is handed on as v5's run hands it on. Parity: financial services 53/53 on
1761 (2026-10); on 1776 (2026-09) all 49 figures v5 wrote match, and the 5 it lacks (fin_reach,
fin_category_pairs and their columns) were added to v5 after that run.

### 2026-10-23 — Transaction Intelligence: the portfolio block, matching v5 on every figure

Summary: The first transaction analysis is ported: the feed's shape (rows, accounts, channels, card
spend, months, top merchants, MCC coverage). Its 31 figures match James's v5 engine exactly for
1761 CapEd and 1776 CoastHills. No deck changes.

`ti/transaction_intelligence/portfolio.py` is ported unchanged, with the v5 `core/deposits` package it
imports a constant from (`ti/core/deposits/`, unchanged; the deposits analysis itself comes later).
The check found one systemic difference and it is fixed once: v5 runs pandas 2.3, this repo pandas 3,
and under pandas 3 `astype(str)` keeps a missing value missing where pandas 2 wrote "nan", so v5's
"nan" clean-ups dropped rows (1761's field 9 / field 11 counts came back empty instead of 9,261,674
blanks). `ti/compat.legacy_strings()` restores pandas 2's string behaviour inside the cut's entry
points only (`ti_build.py`, `scripts/ti_parity.py`), and `tests/conftest.py` applies it to `test_ti_*`
modules only; nothing else in the repo is affected. Parity: bases 15/15 and portfolio 31/31 on 1761
(2026-10) and 1776 (2026-09).

A real load of 1761 from `Inputs/Txn Files` (2026-10-23) read 6 files where v5's run read 7: the
`[2026.10.01]` file is in v5's local copy but has not been landed into `Inputs/Txn Files/1761` yet
(`scripts/land_txn_files.py` is run by hand). A data-currency gap, not a porting one.

### 2026-10-23 — The Transaction Intelligence cut's reference dictionaries are in the repo

Summary: The competitor list, the financial-services patterns and the merchant categories that the
transaction analyses classify against now live with the code. No deck changes.

Copied unchanged from ARS v5 `0_Config/` into `build/ars_pipeline/ti/dictionaries/`. They name public
institutions and merchants, nothing about a client; a client's own competitor and self names come
from the client config (`ti/config.py`). `ti/dictionaries.folder()` is the folder v5's loaders take.
Test: `test_ti_dictionaries.py` (present, parse, carry the sections v5 reads, no client config keys).

### 2026-10-23 — The Transaction Intelligence cut reads the clients' transaction files

Summary: The Transaction Intelligence cut can now read a client's monthly debit-card transaction
files from Inputs/Txn Files, the twelve months up to the ODD's data month, the way James's v5
engine reads them. No deck changes.

v5's transaction loader, merchant key and transaction-side lenses are ported unchanged into
`build/ars_pipeline/ti/transaction_intelligence/` with v5's loader tests. The files stay zipped on
the share; `ti/txn_stage.py` copies the window's files ONCE into a local staging folder
(`%LOCALAPPDATA%/RPE/ti_cache`, or `TI_CACHE_DIR`), each dated with its zip entry's own date, so v5's
parquet cache keys are the same every build and the share is read once per new file. A file that
leaves the window leaves staging; the share copy is never touched. `ti_build.py` puts the rows and
lenses on the shared context, and a client with no transaction files is stated, not failed. The
parity check rebuilds the rows v5 read from v5's own parquet cache, so transaction figures are
compared on identical rows. Tests: `test_ti_txn_stage.py`, `test_ti_txn_loader_dedupe.py`,
`test_ti_txn_quote_swallow.py`, `test_ti_txn_wide_rows.py`, `test_ti_closed_account_lens.py`.

### 2026-10-23 — Ported v5 slides draw on RPE's slide anatomy

Summary: The Transaction Intelligence cut can now draw the slides ported from James's v5 engine
in the house style: RPE's colours, chart face, title, pill, logo and slide number, with a source
note on every slide. A v5 slide that would have been left out for missing data is shown with the
reason instead. No deck changes.

v5's chart renderers, headline writer and copy rules are ported into `build/ars_pipeline/ti/deck/`
(`charts`, `charts_txn`, `charts_story`, `headlines`, `polish`, `labels`, `txn_common`); the chart
palette now comes from `brand.py` (SLATE stands in for v5's steel, which `brand.STEEL` cannot
replace at 3:1 on white; the RAG red and green have no brand token and keep v5's values) and the
face from `rpe_env.use_font(brand.CHART_FONT)`. `ti/deck/helpers.py` re-implements the helper
bundle v5's builders call (`slide`, `chart`, `rail`, `table`, `kpi`, …) on RPE's grid: the title
stops before the period pill, the tile rail ends above the logo band. Every slide it makes gets a
Source note naming the client; a builder that declines becomes a slide saying "Not shown for this
client: <reason>" under its own title (CLAUDE.md: never drop slides automatically).
Test: `test_ti_deck_helpers.py` (0 FAIL from `validate_deck` in both lenses).

### 2026-10-23 — The monthly build can make the Transaction Intelligence cut (opt-in)

Summary: With RPE_TI=1, an ARS client's build also makes the Transaction Intelligence decks, one
per lens, into a ti/ folder beside the ARS deck. They are never delivered, never combined, and
cannot fail the ARS build. Without the flag nothing changes.

`scripts/build_month.build_client` runs `build/ars_pipeline/ti_build.py` after the ARS deck when
`RPE_TI=1`, passing `--ics` for a client on ICS in clients.md. It reads the ODD once, joins the
ICS lists, runs each chapter's compute on one shared context (`ti/context.py`, also the parity
check's), writes `ti_pack.json`, and builds a deck per lens. A lens with no accounts (an ICS
client whose lists match nothing) is stated in the log and the pack, never built empty; a chapter
whose compute fails is stated and the rest still build. The decks stay in `<stage>/<id>/ti/`:
`promote_month.deliverable()` reads only the stage folder's own files, and the step never adds
to the programs that are combined or delivered. With no chapter ported yet it builds nothing and
says so. `ars_launcher.STEPS` names the step. Test: `test_ti_build.py`.

### 2026-10-23 — Where the Transaction Intelligence cut overlaps the ARS deck is recorded

Summary: A new register lists every place the Transaction Intelligence cut overlaps a slide or
figure already in this repo, so nothing is replaced while the cut decision is open. No deck changes.

`docs/migration/DUPLICATES.md` (James Gilmore, 2026-10-22: "note where there are duplicate, we
can decide later what to cut"). Eleven rows to start: the eligible base (v5's curated codes vs
the ODD's Elig flag) and ten slides that overlap the opt-in James views or `spend_trend`; none
overlaps a default ARS slide. Each porting pull request adds the rows its own check finds.

### 2026-10-23 — Ported Transaction Intelligence figures are checked against v5's

Summary: A new script compares each analysis ported into the Transaction Intelligence cut with
the figures James's v5 engine produced for the same client and month. No deck changes.

`scripts/ti_parity.py <v5 run folder> --client <id> --config <v5 clients_config.json>` feeds
the frame v5 computed on (`enriched.parquet`) and the same client config to the ported code,
and compares every key it returns with v5's `metrics.json` / `txn_metrics.json`, nested values
included, with a float tolerance of 1e-9. Running on v5's own frame means a difference is a
porting defect, never a newer extract. `ti/parity.py` holds the compare and `REGISTRY`, which
each chapter's pull request extends. The account bases match on all 15 keys for 1100 Rally CU
and 1776 CoastHills (2026-09 runs) and 1761 CapEd (2026-10). Read-only. Test: `test_ti_parity.py`.

### 2026-10-23 — The Transaction Intelligence cut finds its ARS and ICS lens groups

Summary: The Transaction Intelligence cut can now split a client's accounts into its two
lenses: responders, mailed non-responders and not mailed, and the ICS accounts found in the
ODD by direct mail and referral. Nothing in the ARS deck changes.

v5's account lenses (`ti/core/account_lenses.py`) and its ICS list join
(`ti/monthly_analysis/ics_sources.py`) are ported unchanged with their tests. `ti/lens.py`
finds the client's newest lists where RPE files them, `Inputs/ICS Direct Mail/<id>-…` and
`Inputs/ICS Referrals/<id>_…`, stages them for the join, and returns the lens groups; a lens
with no accounts raises with the sentence the deck states rather than rendering empty. On
1615 Cape & Coast (2026-10-23) the direct-mail list matched 241 of 241 rows through the ODD's
own hash column; no referral list is on hand yet, so the referral channel is left out, not
shown as zero. The ICS lens groups in `ti/cut.py` are now v5's lens keys. Tests:
`test_ti_lens.py`, `test_ti_ics_sources.py`, `test_ti_declining_lens.py`.

### 2026-10-23 — The Transaction Intelligence cut reads the ODD the way v5 does

Summary: The new Transaction Intelligence cut can now read a client's ODD extract and build
its account bases. Nothing in the ARS deck changes, and no build calls it yet.

Five foundation modules of James Gilmore's ARS v5 engine are ported unchanged into
`build/ars_pipeline/ti/core/` (periods, the ODD transform, the account bases, the per-account
facts), with v5's facts tests. `ti/odd.py` reads `Inputs/ODDD/<id>_ODDD.zip` through
`rpe_env.extract_odd_csv` and detects the header row as v5 does. `ti/config.py` supplies the
client config the analyses read: a v5-shaped file when one is supplied, else derived from
`ars_code_tables.json`, and the build says which. The two disagree: 1615 Cape & Coast has
22,103 eligible accounts on v5's curated codes and 20,652 on the code tables' active and
actively offered flags (same extract, 2026-10-23). `ti/PORTING.md` records the porting rules.
Tests: `test_ti_odd.py`, `test_ti_config.py`, `test_ti_facts.py`.

### 2026-10-23 — The Transaction Intelligence cut has a deck shell (not wired into any build)

Summary: A new, separate deck is started for the analyses being moved over from James's ARS
engine — transaction intelligence, competition, attrition and deposits — in an ARS lens and an
ICS lens. This change adds only the empty shell and its builder; no build calls it and no
existing deck changes.

James Gilmore (2026-10-22): migrate the ARS v5 analytics one script per branch, "make sure not
to overwrite any of the aaron analysis, note where there are duplicate, we can decide later what
to cut", with "the ars and ics lenses as a separate cut". So the cut lives apart from the ARS
deck: its own package (`build/ars_pipeline/ti/`) and builder (`build_ti_gen.py`), started from
the ARS template shell, whose cover, Summit, agenda, Questions and Contact slides are found by
meaning as the CashPlease builder finds them, and every other shell slide stripped. The file
name is `<id>-<yyyy.mm>-TI-<ARS|ICS>-<Client> Transaction Intelligence.pptx`; "TI" is not a
program tag, so `promote_month` can never read it as an ARS deck, supersede one with it or
archive one for it. The chapter list is empty: the builder refuses to make a deck until the
first chapter lands. Every content slide's notes go through `ti.frame.notes`, which refuses a
note with no Source line. Test: `tests/test_ti_shell.py` (file name, shell shape, both months,
0 FAIL from `validate_deck` on a stub chapter in both lenses).

### 2026-10-20 — The clients' transaction files are collected from the CSM ODDD folders

Summary: A new script, land_txn_files.py, copies each client's monthly debit-card transaction file
out of the ODD extracts in every CSM's ODDD folder into Inputs/Txn Files, one zip per file, skipping
what is already there. September's and October's files were landed with it. No deck changes.

James Gilmore, issue #23 (2026-10-19): "TXN files are currently being delivered in the monthly ODDD
zips per CSM" — he asked for them to be grabbed automatically. Aaron (2026-10-20): "The zip files
of debit card transactions should be in the folders with each CSM's ODDD. Collect those and move
them to the reporting input folder." The data team ships the transaction file inside `<id>_ODDD.zip`
beside the ODD member (a few land unzipped in a `<id>_ODDD/` folder), and `Inputs/Txn Files/` had
been filled by hand through September. The script reads every member that is not the ODD member
(`watch_sources._odd_members`, the readers' rule), checks the export's banner line — 1121's
September extract carried "Monthly Account Data - Master File", which is not a transaction file and
is reported instead — and lands each as `<member name>.zip` in the form `zip_txn_files.py` keeps,
verified and written through a `.part`. The extracts on the share are the data team's originals and
are never changed. It is not in the 08:00 watch: a month's files run to about 10 GB and the task has
a 50-minute limit. The old `Inputs/Weekly Summaries/` cleanup the day before is unrelated.

### 2026-10-20 — Sheila's Feedback tab wraps each report

Summary: On the Feedback tab a report's title and text now wrap inside the table instead of
running off the right edge of the page. Nothing else changed.

"Feedback runs off the page. Make the rows wrap text to keep it clean." (Aaron, 2026-10-20). The
table reused the Lift Matrix table's style, whose cells are right-aligned and never wrap because
they hold figures; the Feedback table now has its own rule (`table.lm.rep`): left-aligned,
wrapping, top-aligned, the What column taking most of the width, and only the issue number,
state and date kept on one line.

### 2026-10-19 — Bradford's weeklies land with their program; the Weekly Summaries folder is gone

Summary: The MRPC Enrollment Summary weekly now lands in Inputs/MRPC Analyses beside the MRPCPM
analyses, and the CashPlease Summary weekly stays in Inputs/CashPlease. Nothing lands in
Inputs/Weekly Summaries any more and the folder has been removed. No figure changes.

Aaron, 2026-10-19: "Let's clean up the landing locations for the summaries from Bradford. We have a
weekly summaries folder and a cashplease folder and an MRPC analysis folder. Let's put them in the CP
and MRPC folders, not in the 'weekly summaries' folder." The CashPlease weekly had moved on
2026-09-16; the MRPC weekly was the last thing in the folder. `rpe_env.INPUT_KIND_DIRS["weekly"]`
now names `MRPC Analyses`, so two kinds share one folder; `rpe_env._scanned_dirnames` lists each
folder once for `report_dirs()` and the copier's `_report_dirs`, so no reader sees a file twice.
The two weeklies on disk were moved (one was already there, byte-identical) and the empty folder
removed. Readers never named the folder — `mrpc_weekly` and `build_cashplease` glob
`report_dirs()` — so no reader changed.

### 2026-10-13 — A month that collapses in the middle of an extract is left out, not read as complete

Summary: A month whose NSF/OD (or swipes or spend) collapses and then comes back is now left out of
every comparison, the same way an unfinished trailing month already was. Marine FCU's August 2026
NSF/OD (390 items against about 19,000) passed as complete once September was loaded, because the
check only looked at the newest months. It is now named in the slide notes and skipped by the
NSF/OD year-to-date tile (which reads n/a), the swipe-tier window, before/after, the Lift Matrix
value window and the Average Ticket window.

`month_complete.assess(..., interior=True)` and `odd_completeness` (which now sums every month, not
the last eight) report `interior` gaps: a month below half the median of the baseline months before
it, in a run of at most two, followed by a month back at or above that share. A fall that holds
(three months or more, or no recovery) is a real change and is left alone. Callers read
`usable_months(months, result)`, the complete prefix minus the gaps; `excluded_sentence` and
`excluded_months` name interior months too. Evidence: the 40 ODD extracts on hand carried six
recovering NSF/OD gaps (1529 Jan26, 1539 Aug26, 1615 Jul24, 1637 Oct-Nov25, 1748 Nov24, 1800
Dec25); the one interior spend fall that did not recover (1200 Jul24) is not flagged. Callers
changed: `metrics_gen`, `ticket_calc`, `responder_activity`, `james_views`, `lift_values`. The
swipe-tier caption names a gap inside its three months ("Jun-Sep 2026 (Aug left out)").
Tests: `tests/test_month_complete.py`, nine cases on Marine's real series.

### 2026-10-13 — The workbook-only ICS shape counts referrals, and the deck carries the workbook's ROI

Summary: An ICS deck built from the workbook alone now shows the ordinary referral slides — The
Power of Referrals, Referral Trend, Results by Branch, with the Charts goals — because the
workbook's "Accounts Opened via Invitation Checking System" row counts referrals. Every ICS deck
built from a workbook now carries the workbook's own ROI and Present Value instead of a
recalculation. KEMBA CU 1195 reads 7.17 to 1 and $6.81M, as its workbook does.

Cindy's review of KEMBA's first deck. The shape shipped earlier today worded its three count
slides "accounts opened via ICS, not referrals", on the premise that the row was a different
measure from a referral count (on 1776 it runs above the referral detail export, 2,575 vs 2,280).
Aaron: "The monthly detail tab in the workbook is counting referrals in the Accounts Opened via
Invitation Checking System row"; "That'll sum to Accounts Opened via Invitation Checking System on
Value of an ICS account" (it does: 3,877). So `ics_local_sheet.read_workbook_openings` builds the
referral block as `referral_sections` does — monthly goal, previous month against goal, branch
goals ×12 from the Charts Goals tab (now also read when its column is "Goal" beside ramp columns,
as 1195's is), names from the Goals tab then the branch-name dataset — the second vocabulary in
`build_ics_gen._WORDS` and `meta.count_basis` are gone, and the notes name the workbook row. The
1776 difference is between two referral counts and is a question for the data team, as is
Cindy's "data doesn't match VIP" on the count slides. "Carry the workbook's ROI figures" (Aaron):
`ics_workbook_extract` now reads the Value tab's "Present Value of New ICS Accounts @ 3%" and
"Present Value Per Account"; Performance of ICS Accounts and ICS Financial Summary show the
workbook's ROI and Present Value, the bullets say "Workbook present value at 3% over N years", and
the notes say so. The 2026-07-13 recalculation runs only for a sheet with no Present Value (the VIP
pulls carry none) and the notes then say it was recalculated. "Add the full monthly detail to an
ICS appendix" (Aaron): `ics_workbook_extract` now also emits `monthly_detail_full`, every cohort
column of the tab with the expense and profit-to-date rows, and `build_ics_gen` renders it as
"Appendix: Monthly Detail (k of n)" — ten cohorts a page at 12 pt (exempt from the 16 pt floor
like Program Results by Month Opened), placed after the education slides and before Questions &
Discussion so `assemble_combined` keeps the pages inside the ICS section; the notes carry the
program-to-date sums across all cohorts. A sheet without the block (a VIP pull not re-extracted)
gets no appendix. KEMBA's 46 cohorts make five pages.

### 2026-10-15 — Sheila's ARS dot is readable in dark mode

Summary: In Sheila's list, the ARS program dot now shows as steel blue when the page is in dark
mode, instead of brand navy that disappeared into the dark background. Light mode is unchanged.

"The ARS dot is too hard to see in dark mode" (Aaron, 2026-10-15). The dot took `--navy` in both
themes; it now takes `--dot-ars`, navy on the light ground and `#8FB4DA` on the dark one, the
blue the Sent chip already uses there. The header, buttons and the other three dots are as they were.

### 2026-10-15 — ICS for every client with a direct mail list: 36 clients added

Summary: Every client with a 2026.10 direct mail list is now an ICS client in Sheila: 17 ARS
clients gain an ICS section and 19 clients join as ICS only, 1657 Marine Credit Union among them.
Those with a current ICS workbook build the workbook-only ICS section with the Direct Mail slide;
the rest build no ICS section until a current workbook or a referral source lands, and Sheila
says which.

"List any client with a new direct mail list as having ICS" (Aaron, 2026-10-15). `clients.md`:
ICS = "yes (direct mail list, 2026-10-15; no VIP sheet)" and the deck tag gains ICS on 1217, 1487,
1542, 1615, 1637, 1652, 1673, 1680, 1745, 1746, 1759, 1761, 1765, 1766, 1780, 1799 and 1800; 1657's
row reads ICS; 1002, 1514, 1555, 1710, 1731, 1736, 1743, 1764, 1774, 1782, 1796, 1806, 1808, 1811,
1816, 1817, 1826 and 1835 join the ICS-only table with their CSM. The roster now carries 51 ICS
clients. Workbook-only builds are on offer for 1542, 1680, 1746, 1759, 1800, 1710, 1808, 1816 and
1826, which have 2026.10 workbooks; none of the 36 has a VIP sheet or referral export.

### 2026-10-15 — WesBanco's and Rosedale's sheets re-extracted from their 2026.10 workbooks; the extractor keeps a sheet's mystery-shop block

Summary: WesBanco 1632 and Rosedale Bank 1738 now carry their October ICS workbooks' figures,
so their next decks show the full ICS section with the current workbook. The quarterly extractor
no longer writes its mystery-shop placeholder over a sheet.

"Run the file check again. We've added a folder for ICS Direct Mail with files for all clients
with direct mail, and we've added a lot of ICS workbooks" (Aaron, 2026-10-15). A VIP client's
sheet takes its workbook sections from `ics_workbook_extract --write`, which is run by hand, so a
new workbook on disk changes nothing until it is run: 1632's sheet carried its 2026.07 workbook
and 1738's none while 2026.10 workbooks sat in Inputs. Both were re-extracted (backups in
`Build Artifacts/vip_backups/`): twelve cohorts, the workbook's present value, the program-to-date
benchmark, `monthly_detail_full` and `meta.workbook_month` (September 2026), referrals and direct
mail untouched. The write put the extractor's `{"include": false, "_status": "skip"}` mystery-shop
stub onto 1738's sheet, which had no block; it was removed, and `main` now drops the stub before
writing so a real block from a VIP pull can never be overwritten. All 44 direct-mail files parse;
the readers find each by client id.

### 2026-10-15 — The source watchdog fires once a day, at 08:10, or by hand

Summary: The "RPE Source Watch Watchdog" task runs once each morning, ten minutes after the
08:00 source check, instead of every half hour until noon. Any later check is started by hand.

"The source watchdog is running too often. I want this running only at 8am or manually"
(Aaron, 2026-10-15). Since 2026-09-21 it fired at 08:20 and every 30 minutes for four hours; this
morning the 08:00 run came off the VPN with exit 2 and the watchdog logged "needs a human look"
every half hour until 13:38. `register_watchdog_task.ps1` now defaults to `-Time 08:10` and
`-RepeatHours 0` and the task was re-registered; `-RepeatHours 4` restores the old window.
Ten minutes after the main fire is enough for a healthy run to finish and for a suspended one to
pass the four-minute age the watchdog judges by. `tests/test_watch_sources.py` pins the defaults.

### 2026-10-15 — The spend YoY tile falls back to a like-for-like window

Summary: On Overall Debit Swipes & Spend, a client whose workbook spend series does not reach
back to January of the prior year no longer shows n/a. The tile reads "Spend YoY, like for
like" and compares the months of this year to date that the prior year also carries, with the
caption naming them ("Feb–Sep 25 → Feb–Sep 26"). A full January-to-date pair is still used first.

"For Brooks Bank how do we have NSF YoY but not Debit card spend?" (Aaron, 2026-10-15). The NSF/OD
tile reads the ODD extract, which carries every month from July 2023; the spend tile reads the
workbook's Key Trends, which for Brooks start in February 2025, so Jan–Sep 25 had no January and
the rule of 2026-10-12 (every month of both windows complete, else n/a) left the tile empty while
the opt-in Debit Spend per Cardholder slide beside it already compared Feb–Sep like for like.
`build_ars_gen._spend_like_for_like` takes the longest run of months ending at the last complete
month that both years carry, at least three, sums each year over it, and the notes say which
window was used and why; fewer than three matching months still reads n/a. Same rule as
`spend_trend` (2026-10-12).

### 2026-10-15 — The two before/after chart pairs run the full slide width

Summary: On Responder Activity: Before vs After (Mean) and Before vs After by Offer, the pair
of charts now spans the slide instead of sitting narrow in the middle.

"Both charts could be wider on this slide" and "and this one" (Aaron, 2026-10-15, Brooks Bank).
The picture box was already 11.3in wide; the empty space was inside the image — `charts_gen`
drew both pairs at a 2639x1003 canvas with a legend above the panels and letterboxed the tight
crop into it, so the panels filled about two thirds of the box. `DIM` image10 / image31 are now
3240x1003 and the figures 3.8in tall at that aspect, so the tight crop comes out near the canvas
aspect and the panels fill its width; `slide_geometry` gives both titles the full 12.3in,
centered, top 2.0in, height from the image's own aspect and at most 4.0in, so nothing stretches
and the box ends above the caption. The ARS shell carries the rule (its placeholder image is
squarer, so it sits at 10.52 x 4.0) and the layout baseline was re-snapshotted for those two
slides. `tests/test_slide_geometry.py` pins the rule.

### 2026-10-15 — A prior-period ICS workbook is stamped with its data month, and Brooks Bank's onsite deck

Summary: When an ICS deck is built with a workbook older than its period (the opt-in
`ICS_ALLOW_STALE_WORKBOOK` override), the workbook slides now carry the workbook's data month
("PTD · August 2026" for a September workbook) rather than the workbook's file period. Brooks
Bank's 2026.10 deck was rebuilt that way for the 2026-10-16 onsite review, with the September
ICS workbook re-extracted so it carries today's fixes.

"I need a deck using the October ARS workbook and the September ICS workbook with the fixes
we've built since September was produced" (Aaron, 2026-10-15). `ics_workbook_extract` now reads
the Monthly Detail banner ("August 2026 Data") into `meta.workbook_month` on `--write`, and
`build_ics_gen`'s override prefers it to `_period_label(workbook period)`, which would have
stamped August's figures "September 2026". Brooks' VIP sheet was re-extracted from its 2026.09
workbook (a backup is in `Build Artifacts/vip_backups/`): twelve cohorts, the workbook's present
value, the program-to-date benchmark and the full Monthly Detail, referrals untouched. The deck
was built through the launcher with the override and `RPE_SPEND_SLIDES=1`, as the 2026-10-12
deck was, at 0 FAIL, and is in Outputs; the 2026-10-12 deck went to the archive.

### 2026-10-15 — The archive lives inside each CSM's Outputs folder

Summary: Superseded decks now go to `_Archive` inside your own Outputs folder
(`Outputs\<CSM>\_Archive\<id> <client>\`), with the review folder for older copies beside it,
instead of a shared `Outputs\_Archive\` at the root. Existing archived decks were moved there.

"Move the Archive under each CSM's folder in outputs rather than in the root Outputs folder"
(Aaron, 2026-10-15). `promote_month.client_folder` resolves `Outputs/<CSM>/_Archive/<id> <client>`
(`csm_archive`), reusing an existing folder there first, else one still under the root archive
(an older copy of the code could leave one), so a client is never split across two places;
`review_root` puts `_older decks - delete after review` beside the client's archive, and
`tidy_client_archive` mirrors that layout. `rpe_env.output_decks` never entered a CSM folder's
subfolders, so a CSM's `_Archive/` is not read as delivered decks, and the root name stays in
`_OUTPUT_SKIP_DIRS` for any leftover. The 2026-09-15 layout (`Outputs/_Archive/<CSM>/`) was
moved on the share: 54 client folders and 117 files under the CSM folders, plus 23 client folders
and 70 files of the review folder, by rename, nothing copied or deleted. `tests/test_promote_month.py`,
`tests/test_archive_dirname.py` and `tests/test_ars_launcher.py` pin the new layout and the
leftover-folder reuse. The user guide and the workflow page name the new path.

### 2026-10-13 — ICS revenue tiles are program to date, the cohort window is twelve, both expense lines are named, Comparisons is program to date

Summary: On every ICS deck with a workbook section, the Interchange, NSF/OD & Other, Spread and
profit-contribution tiles now show program-to-date totals across every cohort; the cohort charts
and the Program Results by Month Opened table show the newest twelve cohorts and say so; the
Financial Summary reads "Referral Fees to Date" and "Acquisition Cost"; and Comparisons uses the
workbook's Program to Date row.

The rest of Cindy's review of KEMBA 1195, decided with Aaron step by step (2026-10-13). (1) "This
is YTD data - labeled as PTD. PTD is $573,936.31": the tiles summed `monthly_detail`, the newest
nine cohorts ($11,044), beside an all-cohort account count — and CoastHills 1776's September deck
shipped the same way ($26,570 "Interchange PTD" beside 2,575 accounts and a $328,420 profit
contribution). `build_ics_gen` now reads the tiles from the sheet's revenue components
(`revenue.components`, every cohort; `revenue.total` for profit contribution) and names the window
on every chart subtitle ("newest 12 cohorts (Oct'25 – Sep'26); tile: program to date"); the
per-account figures use program-to-date revenue over all-cohort account-months when the sheet
carries `monthly_detail_full`, else the window's own sums, numerator and denominator always the
same scope, stated in the notes. (2) "I don't understand why you are picking the youngest
accounts": `ics_workbook_extract` keeps the newest TWELVE cohorts (nine until now), and the table
drops to 11 pt for them; its constant "$4.08 amortized per account per month" row — not a workbook
figure — is replaced by the workbook's own Total Expense (referral fee) row, and the amortization
caption is gone. (3) "Doesn't match workbook" on the Financial Summary: "Amortized Program
Expense" $364,433 was the workbook's Total Expense row (referral fees) and "Billed Expense"
$949,865 is $245 × 3,877 accounts, which the workbook does not carry and Net Profit does not
deduct; both stay, as "Referral Fees to Date" and "Acquisition Cost", with the caption saying the
latter is not deducted. (4) "YTD ONLY" on Comparisons: the extractor now reads the Program to Date
row of Life of Account Data for the openings share and the close rate ("Program-to-date
everywhere" — reversing the 2026-09-01 choice of Last 12 Months), the label reads "Close Rate",
the footnote names the window, and the notes say the Velocity close-rate average is a 12-month
benchmark; a workbook without the row falls back to Last 12 Months and `benchmark.window` says so.
Lifetime Value on that slide stays annual profit × life (undiscounted, the Velocity average's
basis), not the workbook's discounted present value per account, which the ROI change had let in.
A VIP sheet extracted before today keeps nine cohorts, no expense row and the 12-month window
until the quarterly step re-runs. `tests/test_ics_local_sheet.py` pins each.

### 2026-10-13 — An ODD extract the share refuses as a zip is landed as its ODD member alone

Summary: FedChoice FCU 1815's October ODD extract is now in Inputs. The share had been silently
deleting the zipped extract because of the monthly transaction file packed beside the ODD, so the
morning copy failed three times while Inputs kept September's. The copier now re-lands such an
extract as a zip of the ODD member alone, which every deck reads, and says so in the report.

Found by the hand run Aaron asked for ("Run the file check"): `1815_ODDD.zip FAILED: size mismatch
after copy (13838993 vs 13410387)` on 2026-10-07, -08 and -13. Probing the share: a `.part` file,
a plain zip and both raw CSVs survive; a zip holding the ODD CSV alone survives; the full extract
zip vanishes the instant it is written, under any name (`shutil.copy2` returns, the file is gone),
so `os.replace` failed, the fallback write left the old file, and the size check reported the old
size. `1147`'s zip, with a transaction member of a different kind, is held — the refusal is by
content. `watch_sources._land_odd_member_only` writes the ODD member(s) (the readers' own rule:
`-ODD` / `_V2_` in the name) into a new zip with their original entries, so the pull stamp
`deck_status.odd_stamp_period` reads is unchanged; the record carries `reduced` and the report line
reads "ODD member only (2.5 MB): the share refused the full zip; left out `…monthlytrans.csv`". A
workbook mismatch is never reduced, and an extract with nothing to leave out still fails. The
transaction member feeds only the opt-in "How the Money Moves" James view. The reduced copy's write
time is newer than the source, so the next morning's "differs" is left alone by the changed-on-purpose
guard rather than retried daily. 1815's October extract was landed this way by hand at 15:05;
`tests/test_watch_sources.py` pins the reduction, the report line and the two cases that still fail.

### 2026-10-13 — ICS from the workbook alone: a workbook-only shape, counted as accounts opened

Summary: An ICS client with the period's ICS workbook but no VIP sheet and no referral detail
file now gets a deck. Its three count slides show accounts opened via the Invitation Checking
System, from the workbook, and every title, label, caption and note says accounts opened, not
referrals. KEMBA CU 1195 is the first.

"Add a workbook-only ICS shape that draws the opening counts from Monthly Detail and the branch
tab, labelled as accounts opened" (Aaron, 2026-10-13). The two counts differ: on 1776 CoastHills,
the one client with both on file, the workbook's accounts opened run above the referral file every
month (Aug 26: 128 vs 124; program to date 2,575 vs 2,280), so a workbook figure is never put on a
slide titled referrals. `ics_local_sheet.available` returns the shape `workbook-only` when the
workbook is for the deck's period and nothing else is on file (an older workbook alone still builds
nothing); `read_workbook_openings` fills the count block from the "Accounts Opened via Invitation
Checking System" row (program to date from the Cumulative row, with a flag when it disagrees with
the monthly sum) and the "Invitation Checking DDA Openings by Branch" table's Year to Date column,
with branch names from the Charts Goals tab, else the branch-name dataset, else the number; the
block carries `count_basis` = `accounts_opened` and `meta.count_basis` with it. Completeness goes
through `month_complete.assess` as of the tab's "Report Generated" stamp: an incomplete last month
is charted hatched and left out of the previous-month and peak figures, stated in a flag. Goals are
not shown: the Charts goals are referral goals. `build_ics_gen._WORDS` holds the wording for both
bases — "Accounts Opened via Invitation Checking", "Accounts Opened by Month – Last N Months",
"Accounts Opened by Branch – Year to Date", "Opened Program-to-Date", "Opened YTD", the divider's
"ICS accounts opened, program to date", the agenda rows, the chart legend "Accounts opened via ICS"
— and the pills carry the workbook's month ("PTD · September 2026"). The selection line and the
trend caption step down to a shorter wording until they fit their boxes, measured with textfit.
The slide face says what IS counted; "not referral counts" is said in the notes, not on the slide
("we need to remove the word 'Not referrals' from Accounts Opened via Invitation checking", Aaron,
2026-10-13).
The workbook sections ride along as on a full build. `build_month` logs the shape and the workbook
instead of a referral file. The Charts Goals tab is now found with its name stripped (1195's is
" Goals"). `tests/test_ics_local_sheet.py` pins the shape, the counts, the branch table, the
fallbacks, the incomplete month, the deck wording and the build_month log line.

### 2026-10-13 — 1195 KEMBA CU joins the roster as ICS only (Jordan Berkowitz)

Summary: KEMBA CU now appears in Sheila's list as an ICS client. Its 2026.10 ICS workbook and
Charts workbook are on file, but there is no VIP ICS sheet and no referral detail file yet, so the
deck does not build until one lands.

`clients.md` ICS-only table (Aaron: "1195 Kemba should be added for Jordan. They have ILS and ICS";
"Kemba is listed as KEMBA CU"). ILS has no monthly deck. No ARS, per the Velocity export and Aaron's
2026-09-15 confirmation.

### 2026-10-13 — The watchdog no longer counts "no stuck process" as one blank process

Summary: The morning watchdog's log line for a stuck source-watch process carries its PID, parent,
age, CPU and handle count again, and an attempt whose retry is running fine is no longer logged as
"found 1 stuck process(es)" or fired a second time.

`scripts/watch_task_watchdog.ps1` returned its stuck processes as `,$stuck` so a single one kept
its `.Count` (2026-10-07), and every caller wrapped the call in `@()`. In Windows PowerShell 5.1 the
two together wrap the result twice: no process at all came back as one element, an empty array, so
on 2026-10-08 and 2026-10-12 attempts 2 and 3 logged "found 1 stuck process(es)" followed by
"PID  (parent ): age s, CPU , handles  --" with every field blank, killed nothing, and started the
task again while the retry it had just started was running. `Find-StuckWatchProcesses` now writes
each process to the pipeline as its own object and the callers keep their `@()`, which counts right
for none, one and several; `Kill-StuckRoots` builds its PID set the same way. "fix the watchdog log
bug too" (Aaron, 2026-10-13). `tests/test_watchdog_single_process.py` now calls the function the
way the script does and pins the empty case, the per-process fields, the logged line and the
root-only kill.

### 2026-10-13 — Three more list chips: Checking…, built today, and Sent for Aaron's clients

Summary: Sheila's list now says "Checking…" for a client whose checks have not run yet this
cycle, adds "· built 07:40" to the In Outputs chip on the day the launcher put the deck there, and
shows "Sent <date>" on Aaron's clients once a send is recorded.

"I like each of those status ideas" (Aaron, 2026-10-13). Checking… comes from the same stored
status as Ready and Blocked (none yet, or none for this cycle); the build time is the launcher's
own result record, or the job this server just ran; the Sent chip stays on Aaron's clients only,
because only Aaron records sends and the other CSMs have nowhere to mark theirs (2026-09-15).

### 2026-10-13 — Sheila's list: four dots per client, dividers, and a Blocked chip

Summary: Each client in CSM Sheila's list now shows four dots in a fixed order (ARS, ICS, MRPC,
CashPlease) in a right-hand column, filled when the program is in their deck, with a legend at the
top and hairline dividers between rows. A client whose checks stop shows a red "Blocked · <what>"
chip beside Ready, Building, Queued, Error and In Outputs.

The pills added earlier the same day wrapped under some names and sat beside others, because a
client's pills ran from two to six; Aaron chose dots in their own column ("go with B") so every row
has one shape and the column grows with the window. The client's other Velocity products left the
list; they stay on the client page. "We could add more status options": the Blocked chip comes from
the same stored status as Ready, naming the first stop's subject (`stop_label`: ODD extract, ARS
workbook, DCO, Lift Matrix, no data, product list, clients.md). `tests/test_ars_launcher_web.py`
pins it.

### 2026-10-13 — An ODD extract landed by hand vouches for itself by its own pull stamp

Summary: An ODD extract a CSM copies straight into Inputs (one that never crossed the share) now
counts as current when the member file's own pull stamp names this cycle, instead of reading as
"previous month" until the share holds a copy.

1509 Texas Bay's October extract came by email and Aaron copied it into `Inputs/ODDD/` on
2026-10-13; Sheila still said "ODD extract: previous month; no 2026.10 extract at source" ("I just
copied their ODD to the ODD inputs folder before hitting check again. I think something isn't
working"). The share had no copy and the watch no record, so nothing vouched for the file — but the
file itself does: the data team stamps the member "(MMDDYY_HHMMSS)", and a pull in October is the
2026.10 cycle. `deck_status.odd_stamp_period` reads that stamp from the zip's central directory;
`requirements` reports the copy PRESENT when it matches the cycle, STALE and naming the stamp's
month when it does not, and the old "previous month" when there is no stamp. The share, the watch's
record and now the stamp are the three things that can vouch; a file none of them vouches for is
still stale. `tests/test_deck_status.py` pins it.

### 2026-10-13 — Sheila builds every client's deck, not only the ARS ones

Summary: CSM Sheila and the launcher now list and build clients with no ARS: ICS only, MRPC only,
the standalone CashPlease module, and any mix of ICS, MRPC and CashPlease (ICS-CP, ICS-MRPC,
ICS-MRPC-CP). Such a client gets one button, named for the programs whose data is on hand, and
is checked on each program's own data rather than the ARS rules.

"Bring CP only, ICS only, and MRPC only decks into Sheila, also any combination of those" (Aaron,
2026-10-13). Until now the list held the clients.md ARS clients only and the launcher stopped anyone
else at "Not an ARS client". `ars_launcher.client_entry` gives a standalone CashPlease client (on
the CashPlease roster alone) an entry of its own with `["CP"]`; `rule_checks` checks a non-ARS
client's product list against the programs its deck covers and skips the ARS-only rules (ODD
extract, workbook, DCO, Lift Matrix, Aaron's combined-deck stop); `build_programs` takes every
program with data; `cashplease_availability(standalone=True)` admits a module client's weekly. The
deck goes to `Outputs/<CSM>/` like any other, superseding any other mix for the period
(`decks_in_outputs` and the supersede step now match every program, not `ARS*`). Sheila's list
reads the whole roster plus the module clients; `builds_on_offer` names the one button. The Lift
Matrix tab is unchanged (ARS only). `tests/test_ars_launcher.py` and `tests/test_ars_launcher_web.py`
pin it.

### 2026-10-13 — Sheila's client list shows which products each deck covers

Summary: Each client in CSM Sheila's list now carries small pills after the name: the programs
their deck covers (ARS, ICS, MRPC, CP) filled in, and the rest of their Velocity products (ILS,
Reg E, AE, and so on) outlined, so a CSM can see at a glance what the deck will and will not report.

"I feel like we should ID which products are covered for each client. Maybe add little pills after
the client name in the list" (Aaron, 2026-10-13). `ars_launcher_web.covered_programs` reads
clients.md's programs (ICS-REFERRALS is ICS) and adds CP when the CashPlease roster ships the
slides as a section; the other products come from the Client CSM List's product column. It is
computed with the list, never against the share. `tests/test_ars_launcher_web.py` pins it.

### 2026-10-13 — The issue pages take a file's kind from its name, not the folder it sits in

Summary: The ODD and Workbook Issues page, the CSM Data Gaps page and Sheila's Data Issues tab no
longer count a DCO or an MRPCPM analysis dropped into the ARS Workbooks folder as an ARS workbook.

Marine FCU's and Texas Bay's October DCOs (and Marine's MRPCPM analysis) were copied into
`Inputs/ARS Workbooks/` by hand on the morning of 2026-10-13; `gaps_matrix.kind_files` globbed
`<id>-*` in the kind folder and took the DCO for an October workbook, so both clients' real "no
2026.10 ARS workbook" blocker vanished from the refreshed pages. `common.KIND_TOKEN` /
`kind_matches` now require the name's own token (`-DCO`, `-Workbook`, `MRPCPM`, `Invitation
Checking`), whatever folder a file is in. The launcher and the delivery dashboard already matched
`*Workbook*` and were not fooled. `tests/test_issue_pages.py` pins it.

### 2026-10-13 — An ODD extract the watch copied for this period stays current after the share file goes

Summary: Sheila and the delivery dashboard no longer call a client's ODD extract "previous
month" when the share no longer holds the file the 08:00 watch copied for this period. The
watch's own landing record now vouches for the copy when the size matches.

1539 Marine FCU's 2026.10 extract landed in Aaron's folder on 2026-10-06, the watch copied it,
and by 2026-10-13 the file was gone from the share; Sheila read the copy (the same 65,794,434
bytes) as "previous month (2026-10-06); no 2026.10 extract at source" and stopped the build
(Aaron, 2026-10-13: "I think the file checker in Sheila isn't checking the share, because
Marine has those files"). It was checking the share; the share had changed. `deck_status.watch_landing`
reads `source_watch.json` for an ODDD record of that client and period, and `requirements`
reports the copy PRESENT with "the 2026.10 extract the watch copied on 2026-10-06, since removed
from the share" when the sizes agree. A record of a different file, a damaged inventory or no
inventory vouches for nothing, so the stale rule is otherwise unchanged. `tests/test_deck_status.py`
pins it. The ARS workbook stop was right: no 2026.10 Marine workbook has landed.

### 2026-10-12 — CashPlease rides on every Sheila deck of a client who ships it as a section

Summary: A client whose CashPlease slides ship inside their Executive Review now gets them on
the plain build too, not only the combined one. In CSM Sheila the first button reads "Build
ARS + CP" for those clients and the deck is tagged ARS-CP; the checks list says "CashPlease: in
the deck" or why it was left out.

"Add the CashPlease slides into Sheila decks" (Aaron, 2026-10-12). Until now CashPlease joined a
launcher build only with `--combined`, so a CSM who chose "ARS only" for 1192 Ascend, 1681 First
Financial or any other ARS-CP client shipped a deck with no CashPlease section, and nothing on
the page said so. `ars_launcher.build_programs` is the one place a build's program list is made:
ARS, plus CP when `cashplease_availability` says the roster ships it as a section and the weekly
is in Inputs, plus ICS and MRPC when the build is combined. A plain build with two sections is
assembled and package-checked like a combined one. `tests/test_ars_launcher.py` pins it.

### 2026-10-12 — Debit spend per cardholder: two opt-in slides with a like-for-like comparison

Summary: Two new ARS slides, "Debit Spend per Cardholder" and "Cards in Use and Spend per Card",
follow Overall Debit Swipes & Spend when a build asks for them (`RPE_SPEND_SLIDES=1`). They
compare the months of this year to date that the prior year also carries, so a client whose series
is too short for the YTD tile still gets a true year-on-year read.

Aaron, 2026-10-12: "Let's look at the debit card spend trend for Brooks Bank. The YoY says we don't
have enough data. How are they trending on spend per cardholder? how are they trending on spend per
eligible account? Is there a good story we can tell there?" and then "add the new debit card spend
slides to the Brooks deck. We may include those permanently."

Brooks Bank's workbook series starts in February 2025, so the Jan–Sep windows cannot be matched
and the Spend YTD YoY tile reads n/a — correctly. `spend_trend.windows` finds the months both years
share (Feb–Sep for Brooks; Jan–Sep for a full series; nothing, stated, for a series with no
prior-year month) and `spend_trend.compare` averages each window. Slide 1 is the workbook's monthly
spend over accounts with a card — the figure to quote (Brooks: $1,690 to $1,832 a month, +8.4%, on a
flat card base). Slide 2 reads the ODD's per-account monthly Sig $ + PIN $ for the shape: cards in
use (+10.6% for Brooks), spend per card in use (+4.8%) and spend per ARS-eligible account open in the
month (+4.9%). The ODD is today's book, so earlier months are understated and the notes say so.
Wording follows the +/-2% band; every number on both slides comes from `spend_trend`, with the
month-by-month table in the notes. `tests/test_spend_trend.py` pins the windows, the averages, the
wording, the ODD reader on a six-account fixture, and the slides' placement and notes. Opt-in only:
the monthly build and the golden deck are unchanged until the default is flipped.

### 2026-10-12 — build_month builds a CashPlease section for the clients whose roster row says so

Summary: The monthly driver now adds the CashPlease slides to a client's deck when the CashPlease
roster says they ship as a section (WesBanco and Altamaha as ICS-CP, Marine as ARS-ICS-MRPC-CP),
instead of building the deck without them.

Found while building the standalone decks (Aaron, 2026-10-12): 1632 WesBanco and 1734 Altamaha came
out as plain ICS decks. `read_roster` read the Active, MRPC-only and ICS-only tables and nothing read
the CashPlease roster's "Ships as" column, so `build_cashplease_section` was never reached for
anyone; only the launcher (through `cashplease_availability`) ever added a CashPlease section. The
roster reader now appends CP for a client whose CashPlease row is built and ships "as a section"; a
CashPlease row for a client not otherwise on the roster is a standalone module and is left to
`build_cashplease.py`. `tests/test_build_month.py` pins 1632, 1734, 1539 and 1542's program shapes,
the ICS-CP deck tag, and that a standalone client (1131) is not added.

### 2026-10-12 — Sheila's change log names its release instead of saying "Unreleased"

Summary: The change log page in CSM Sheila now starts with the release it belongs to — the stamp
from RELEASE.txt — instead of a heading that read "Unreleased" over changes that were long since
released.

Aaron, 2026-10-12: "in Sheila under the change log some updates were listed as unreleased. Is that
tracking just training or is there another step?" — neither; the heading was a convention nothing
updated. Every entry Sheila shows is in the released copy by construction, because CHANGELOG.md is
copied with the code at each release. `release_stamp` reads RELEASE.txt beside the change log;
`changelog_page` puts it in a banner at the top, or says "working copy, not a release" in a
checkout. The section heading in this file is now "Changes, newest first". Tests pin the banner
in both cases.

### 2026-10-12 — The performance dashboard takes a client's CSM from the Client CSM List first

Summary: The "RPE Client Performance" page now names each client's CSM from the Client CSM List
— the same file the decks' Contact card and Outputs folder come from — and reads the reports
share's folders only for a client the list does not name.

Aaron, 2026-10-12: "point the dashboard CSM at the Client CSM List."

The share came first until now, and the share is where the data team files reports, not where
clients are assigned: after Gregg Miller left on 2026-10-02, 1811 Dutch Point, 1816 Beginnings CU
and 1817 The County FCU were still being filed under his folder, so the page listed him as their
CSM ten days after the list had reassigned them. `refresh_performance_dashboard.csm_list` reads
the list once; `csm_assignments` takes it first, then the share (or its last answer, off the
VPN), then the CashPlease roster column in clients.md, then the settings record, else Unassigned
— never a default. A list-versus-share disagreement is logged, since it is the sign the data team
is still filing under an old folder. The page's provenance line says so. Tests pin the precedence,
the logged disagreement and the reader.

### 2026-10-12 — The performance dashboard's Build readiness section can be switched to another period

Summary: The "RPE Client Performance" page has a period picker in its Build readiness header. It
switches that section to the cycle period, either of the two before it, or the one after — the
inputs, the decks built for that period and the Sent column together — so the Sent list starts
clean for the period chosen, and every viewer sees the same period.

Aaron, 2026-10-12: "The RPE client performance artifact needs an option to change the reporting
period for the Build Readiness section. It should clear the Sent list and reset it for the current
period."

- `refresh_performance_dashboard.readiness_periods` names the periods the page carries (cycle −2
  to cycle +1) and the refresh builds each one's readiness through `deck_status`, as it always
  did for the cycle; `period_views` carries, per client and period, the decks built FOR that period
  and the delivery log's entry for it alone. The flat `readiness`, `decks` and `sent` the page has
  always read are still there, so an older page build still renders.
- On the page, the section reads everything through the selected period: the Deck column shows
  "built <period>" only for a deck of that period, Sent is keyed `<client>-<period>` and a Mark
  sent is stamped with the period showing, so `--merge-sent` files it against the right period in
  `deliveries.json`. Switching periods carries nothing over. The choice is written to the
  artifact's store (`settings/readiness_period`) and followed by every open view, with the
  browser's own last choice as the fallback for a saved copy.
- The figures above the section stay on the reporting period; the picker does not change them.
- Tests pin the period list, the per-period views (a malformed log entry reads as not sent) and
  the page's wiring; the two older template tests now pin the per-period key.

### 2026-10-12 — NSF/OD Items YoY is year to date, not one month against one month

Summary: The NSF/OD Activity slide's YoY tile now compares January through the last complete
month with the same months a year earlier, and says so: "Items YTD YoY (Jan–Sep 25 → Jan–Sep
26)". It used to compare the single latest month with the same month a year before.

Aaron, 2026-10-12: "is this slide comparing YTD Jan through Sept for 2025 and 2026, or just
September 2025 vs. September 2026?" — it was the single month — "change this to YTD rather than
month vs month."

`metrics_gen` sums NSF/OD items for January through the last complete month of the series and
for the same months a year earlier (`nsf_yoy`), names the two windows in `nsf_yoy_window`, and
carries both sums in `nsf_yoy_ytd` for the notes. Every month of BOTH windows must be in the
complete series; otherwise the tile reads n/a and the build says why — a partial sum is never
passed off as a year, and the complete-months rule still ends the series. `build_ars_gen`
relabels the tile "Items YTD YoY", writes the caption from the windows, and the slide's notes
read "Items YTD YoY compares Jan–Sep 25 (N items) to Jan–Sep 26 (N items)". Tests in
`test_metrics_gen`, `test_month_complete` (a partial July ends the window at June) and
`test_golden_deck` recompute the figure from the series rows the caption names.

**The Swipes & Spend tile follows the same rule** (Aaron, 2026-10-12: "did you also update the
YoY comparison for debit card spend?"): "Spend YTD YoY (Jan–Sep 25 → Jan–Sep 26)" sums the
workbook's monthly spend for January through the last complete month against the same months a
year earlier, in `build_ars_gen`; the notes carry both sums in $M, and a series that does not
hold every month of both windows reads n/a. The two YoY tiles on a deck now use one convention.

Client-facing effect, every ARS deck: the NSF/OD and Spend YoY tiles' percentages, labels and
captions change; the charts and the other tiles do not. On True Sky the single-month NSF/OD
figure was -2%; year to date it is -8%.

### 2026-10-12 — One program-to-date profitability ratio on every slide that states it

Summary: The ARS section divider, the overview bullets and the ARS Financial Performance P&L could
print different profitability ratios from the same figures (True Sky: 2.1 : 1 and 2.2 : 1). Every
slide now prints the one unrounded quotient the same way, and the gate fails a deck whose slides
disagree.

Aaron, 2026-10-12: "Profitability disagrees on True Sky between ARS Financial Performance and the
ARS segment slide."

True Sky's program-to-date revenue is $2,026,429 against $941,929 of fees: 2.1513 : 1. The
extractors (`extract_base_gen`, `base_tab_extract`) stored `profitability` rounded to two
decimals, 2.15, and the slides that print that value formatted it to one decimal —
`f"{2.15:.1f}"` is "2.1", because the float is 2.1499… The P&L formatted the unrounded quotient
and printed 2.2. Each slide was right by its own arithmetic, which is why no single-slide rule
caught it; the shipped 2026.10 deck carried 2.1 : 1 in the Program Overview and appendix bullets
against 2.2 : 1 on the P&L.

- The extractors keep the quotient at full precision; rounding happens only where a figure is
  printed. The one-pager's two-decimal figure and the guarantee note are unchanged by this.
- `revenue_guarantee_slide.ratio_of` is THE value: the Actuals series' quotient when the workbook
  has one — the P&L's own revenue and cost cells must divide to its Profitability cell — then the
  Executive Financials roll-up. It used to prefer base.json's roll-up `profitability` while the
  P&L divided the Actuals, so a workbook whose two tabs differ by a hair printed 3.5 : 1 on the
  divider over a P&L reading 3.4 : 1 (the golden deck, caught by the new check). The guarantee
  slide's gate reads the same value, so it still appears exactly when the deck states a ratio
  under 3 : 1.
- `revenue_guarantee_slide.ratio_text` is THE formatter for a ratio; the P&L's `money(…, "ratio")`
  delegates to it, and `build_ars_gen` builds `prof` — the divider stat and the overview and
  appendix bullets — from `ratio_text(ratio_of(B))`, the same value and formatter as the P&L.
- `validate_deck.ptd_ratio_findings` (standing rule: add the check that would have caught it)
  reads every place a deck states the program-to-date ratio — the P&L's Profitability row, last
  column; the divider stat labelled "revenue to fees, program to date"; any "N.N : 1
  profitability" sentence — and FAILs when they are not one string. The shipped True Sky deck
  fails it; the month and year-to-date columns are not mistaken for the program figure.
- `tests/test_ptd_ratio.py` pins the double-rounding trap on True Sky's own numbers, the
  formatter, the extractor change, the divider's source and the gate check.

Client-facing effect: a divider or bullet ratio moves by 0.1 for any client whose quotient sits
on a rounding boundary (True Sky 2.1 → 2.2 : 1); the P&L figure is unchanged. True Sky's 2026.10
deck was rebuilt.

### 2026-10-08 — Deck assembly is about 2.5 times faster on a large client

Summary: Assembling a large client's ARS deck takes about 1.5 minutes instead of 3.5, with the same slides, figures and notes.

Aaron, 2026-10-08: "continue to work on optimizations for presentation creation."

Profiled `build_ars_gen` on 1100 Rally (439 MB ODD extract): 216.8 s before, 88.4 s after, and the deck's text,
tables, notes and shape geometry compare identical (1,019 items). Four changes:
- `rpe_env.extract_odd_csv` unzips a given ODD once per process. `build_ars_gen`, Product Mix and Excluded
  Accounts each unzipped the same 2 GB member (about 21 s each).
- `odd_rows._code_sets` is computed once. It ran for every account (666,000 calls) and each call added
  `scripts/` to `sys.path` again, 160,000 entries that every later import then searched.
- `shapes.data_logo` resolves and trims a client's logo once per build; 40 slides each re-read it from the share.
- The three pandas readers of the ODD use `dtype=object` instead of `dtype=str`, which pandas 3 turns into
  Arrow strings (2.8 times slower to parse); each immediately `fillna('')`s and uses string methods.

### 2026-10-08 — The ARS workbook read is five times faster on SM clients

Summary: Reading a client's ARS workbook now takes about 3 seconds instead of 18 for clients on the
SM path, with exactly the same figures, so builds start sooner.

Aaron, 2026-10-08: "continue to work on optimizations for presentation creation."

`base_tab_extract.py` (SM clients) read the workbook cell by cell through openpyxl's read-only mode,
which streams the sheet from the top on every `ws.cell(r, c)` call. Profiled on 1038 Sugar River:
2.7 million cells parsed to read a few hundred. `build/ars_pipeline/xl_cache.py` reads each sheet once
into rows and serves the same cell, `max_row`, `max_column` and `iter_rows` calls from them;
`base_tab_extract`, `extract_base_gen` and `extract_lift` use it. Output checked byte-for-byte
against the old reader on 1038 (SM) and on 1200 and 1204 (MM): identical. The MM extractors were
already 3 to 4 seconds. No figure on any slide moves.

### 2026-10-08 — The all-clients ICS referrals query stops at the last completed month

Summary: The all-clients ICS referrals query now returns referrals only through the end of the last
completed month, and WesBanco's ICS launch (November 2025) is recorded in clients.md.

Aaron, 2026-10-08: "I need the query to run only through the end of the last completed month."

`scripts/sql/ics_referrals_all_clients.sql` has a new `@period_end` that defaults to the 1st of the
current month (exclusive). It filters both the client list and the per-client query, so a run on
2026-10-08 returns referrals issued through 2026-09-30. `@h_max_period`, the latest balance period,
is not capped. A capped run does not remove later referrals already merged into `ics_referrals.csv`
(the merge only adds and replaces), and the launcher runs the released copy, so this takes effect
at the next release.

Found while checking 1632 WesBanco: the all-clients pull held no referral issued before the November
2025 launch, so the query needed no launch bound. The per-client query that undercounted (2,333
against the view's 2,482 and VIP's 2,472) was a hand-run query, replaced by a rewrite that returns
2,482. The launch month is recorded on the 1632 row of `clients.md`.

### 2026-10-08 — A release comes from origin/main by default

Summary: Releasing the launcher now checks out origin/main into a release worktree of its own and
ships that, so a release never depends on the state of anyone's checkout. Releasing the working
tree is still possible with `-FromWorkingTree`, under yesterday's guard.

Aaron, 2026-10-08: "make -FromOrigin the default."

Yesterday's guard refused a dirty tree; today's release still had to be done from a throwaway
checkout by hand, because another session's uncommitted file sat in the working tree all day.
`scripts/release_launcher.ps1` now does that itself: fetch `origin/main`, check it out detached
into `%LOCALAPPDATA%\RPE\release-worktree`, and re-run inside it with `-FromWorkingTree`. The
worktree is kept between runs and moved with `git checkout --detach`, so robocopy copies only the
files that changed (a fresh checkout gives every file a new mtime and re-copied the templates and
fonts — ten minutes on the share). The `.venv` for `-Runtime` is read from the real checkout, which
is the one place it exists. `RELEASE.txt` names its source: "origin/main (release worktree)" or
"working tree <path>", and `FORCED` when the guard was overridden. A fetch that fails releases
nothing. `tests/test_release_launcher.py` pins the order (worktree, then guard, then copy), the
kept worktree, the venv path and the stamp.

### 2026-10-07 — A release ships only what is on origin/main; the repo gets CI and code owners

Summary: Releasing the launcher to the share now refuses when the checkout has uncommitted
changes or is not on origin/main, so CSMs only ever run code that is in git. The repo also gains
a GitHub Actions run of the unit suite on every pull request and a CODEOWNERS file.

Aaron, 2026-10-07: "i need to protect the repo now that i have multiple contributors" — "set up
3, 4 and 5 now."

- `scripts/release_launcher.ps1` fetches `origin/main` and stops before copying anything when
  the working tree is dirty or HEAD is not a commit on `origin/main`; the 15:06 release that day
  had stamped "with uncommitted changes" and shipped another session's half-finished
  `ils_dda_count_mail.py` to every CSM, because robocopy mirrors the working tree. `-Force`
  releases anyway and `RELEASE.txt` says `FORCED` with the reason. `tests/test_release_launcher.py`
  pins that the guard runs first, checks both conditions, and that the quiet old wording is gone.
- `.github/workflows/tests.yml` runs `pytest tests` on a Windows runner for every pull request
  and push to `main`, against an empty `RPE_DATA_ROOT` so tests that need the CSI share skip
  rather than fail. It is the status check for the branch ruleset to require.
- `.github/CODEOWNERS` asks Aaron to review any pull request touching `build/`, `validation/`,
  `templates/`, `clients.md`, `CLAUDE.md`, `.github/` or the release / task-registration scripts.
- The repo setting "automatically delete head branches" is on.

Branch protection on `main` (pull requests only, one approval, no force-push or deletion, the
`tests` check required) is the remaining step and is a GitHub plan matter: a private repo on a
Free personal account cannot protect a branch.

### 2026-10-07 — The monthly driver can assemble a combined deck with no ARS section

Summary: `build_month` can now build a two-program deck for a client that has no ARS — the
first such client is 1439 Horizon Bank NA (ICS + MRPC). It used to stop with an error before the
assembler ran.

Found while preparing the 1439 build (Aaron, 2026-10-07: "build the 1439 deck once the sheets
land"). `build_client` always passed `--ars made["ARS"]` to `assemble_combined`, so a client with
no ARS section raised `KeyError` in the driver. The assembler itself has not required `--ars`
since 2026-09-01 — the first program present in `BASE_PRECEDENCE` supplies the shell — so the
driver now passes each program flag only for a section it built, ARS included.
`tests/test_ics_local_sheet.py` builds an ICS (referrals-only) + MRPC client through the driver
with the subprocesses stubbed and pins the assemble command (no `--ars`, `--ics` and `--mrpc`
pointing at the built sections, the deliverable named `ICS-MRPC`). No figure moves: a deck that
assembled before assembles the same way.

### 2026-10-07 — The morning source watch can no longer hang in its mail step, and the watchdog clears a run that runs too long

Summary: The 08:00 source check no longer hangs for hours after its mailbox step times out, and
the watchdog now ends any source-check process older than three hours, so a hung run cannot
make the next morning's fire be skipped.

Aaron, 2026-10-07: "do both, with tests, and post them to the changelog."

On 2026-10-05 the run reached the shares at 11:34, copied until 13:49, started its mail step
and never ended; killed by hand that evening. On 2026-10-06 the same, from 08:16. The mechanism:
the endpoint agent on the build machine relaunches every python start as a child of the first
with the same command line, and a relaunch it leaves suspended inherits the mail child's output
pipe. `subprocess.run(timeout=600)` killed the child when the ten minutes were up, then read the
pipe to its end — which never came while the grandchild held it. The task is `MultipleInstances
IgnoreNew`, so a run still alive at 08:00 made the next fire be dropped; and the watchdog could
not see it, because a run with 73 s of CPU and 161 handles is nothing like the suspended fire it
was built to find. The scheduler's own 50-minute limit did not end it either.

- `watch_sources.mail_step` now hands the child two temporary FILES for its output and waits on
  the process, not the pipe; a timeout calls `_kill_tree`, which runs `taskkill /T /F` on the
  child so the relaunch under it goes too, and the report says so. `tests/test_watch_sources.py`
  stands in a fake child that writes to the file it is given and pins: a timeout kills the tree,
  the child is never handed `subprocess.PIPE`, and skip / failure / outcome reading are unchanged.
- `scripts/watch_task_watchdog.ps1` has `MaxAgeSecondsAlive` (10800): a `watch_sources.py`
  process older than that is stuck whatever its counters say, logged with its reason, and
  killed from the roots — including on a morning whose run DID reach the shares, which used to
  be a silent exit; nothing is retried in that case. `tests/test_watchdog_single_process.py`
  runs the real function against a live process aged four hours (found, "older than 10800 s"),
  one hour (not found) and the suspended signature (found, "created suspended"), and pins that
  the silent-exit path looks for an over-age process first.

The two open questions from 2026-10-05 are now one: the lone-process miss was the `.Count`
unrolling fixed earlier today, and the hang is the pipe. What is still open is why Task
Scheduler's execution limit does not end these processes. Nothing about what is copied, pruned
or filed changed.

### 2026-10-07 — The source-watch watchdog now finds a single stuck process

Summary: The watchdog that clears a stuck morning source watch missed it whenever exactly one process was stuck;
it now finds one or several.

On 2026-10-07 the 08:00 fire sat suspended from 08:00:01 to 09:49 (0 CPU, 0 handles, one thread) while the
watchdog logged "no suspended process found ... needs a human look" at 08:20, 08:50 and 09:20 (Aaron, 2026-10-07).
`Find-StuckWatchProcesses` returned its list bare, and Windows PowerShell 5.1 unrolls a one-element result to a
scalar; a `[pscustomobject]` has no `.Count` there, so `if ($stuck.Count -gt 0)` was false for exactly one stuck
process. Every "found" line in `source_watch_watchdog.log` (09-19, 09-22, 09-23, 09-24, 10-05) is a pair, and every
one-process morning (10-01, 10-07, 09-20 and others) is a miss. The function now returns `, $stuck` and the call
site wraps it in `@()`. A real suspended `pythonw.exe` was reproduced from a limited-rights scheduled task: its
counters read as stuck and the detection logic flags it from both limited and elevated contexts, so permissions
and thresholds were not the cause. `tests/test_watchdog_single_process.py` runs the real function with stubbed
processes (one, two, none); the single-process case failed against the old script.

### 2026-10-07 — New checking is compared on open accounts only (Debit Card Penetration, New Checking Balances)

Summary: The Debit Card Penetration and New Checking Balances slides compared open accounts with the book but
counted closed accounts among the new ones, which made new accounts look worse. They now compare open with open.

First State Bank's Debit Card Penetration slide read 67.0% for new checking against 78.2% for the book while its
12-Month Eligible Take Rate slide read 76.3% for the same new accounts (Aaron, 2026-10-07). `metrics_gen` built
the new-checking group from every personal checking account opened in the window, closed or charged-off ones
included, and 119 of the 990 were closed. A closed account's current-state fields are blank, so it read as no
card and a zero balance, while the book it was compared with (`open_chk`) already counted open accounts only.
Open against open the figures are 75.9% (871 accounts) and 78.2%, a gap of about -2.3 points, not -11.2.
`new_chk` is now `ischecking(r) and isopen(r)`; `new_stillopen_pct` and the other new-account measures keep the
closed ones on purpose. Slides affected for every ARS client: Debit Card Penetration, New Checking Balances and
the balance and funded-share figures that cite them. The October decks were rebuilt on 2026-10-07.

### 2026-10-07 — CashPlease client 1825 has a full name

Summary: The CashPlease tab for client 1825 now reads as "Mutual Savings Association" instead of the cut-off
"Mutual Savings Associatio".

The CashPlease workbook caps sheet names at 30 characters, so 1825's tab is `1825-Mutual Savings Associatio`.
The extractor flags any 30-character name with no `NAME_OVERRIDES` entry so a cut name cannot ship, and the
data-issues scan reported 1825 (Aaron, 2026-10-07). The full name comes from the client's own Product Settings
record (Company Name) and the Velocity client list, not a guess at the ending. 1825 is not on the `clients.md`
CashPlease roster, so no deck changes today; the entry is there for when it is.

### 2026-10-06 — MRPC revenue by month reads Accounting's MRPC Revenue.xlsx

Summary: The MRPC Revenue by Month and Revenue by Year slides now run through August 2026 for every client in
Accounting's new MRPC Revenue workbook, instead of stopping at May.

The VIP revenue dashboard trails the rest of the program: Austin Bank's series ended May 2026 in an October deck,
and VIP MRPC revenue is stale for every client (Aaron, 2026-10-06). Accounting's `Inputs/MRPC Analyses/MRPC
Revenue.xlsx` carries April to August 2026 per client. `mrpc_revenue_file` (read by `build_mrpc_gen` before
`complete_series`) keeps VIP's months before the workbook's first month, takes the workbook's from there on, and
cuts the result to the last 12 months, which is what the Avg Monthly and Trailing-12 tiles say they are. The
"<year> YTD" bar on Revenue by Year is recomputed from the extended series (VIP's own YTD is exactly the sum of its
months), so the projection's YTD and monthly series end on the same month, and life-of-program (the prior years plus the YTD) moves by the same amount, so VIP's and Accounting's figures for a month are never both counted (Aaron: the two do not stack; Accounting's is used). Austin Bank's life-of-program goes from $2,385,808 to $2,490,234. `complete_series` judges the extended
months against the workbook's date, not the VIP pull date, which predates them. A client the workbook does not list
is unchanged. Months at about twice the series median would be shown as the workbook states them and named in the notes of both revenue slides. Accounting's first file did have two: Austin Bank's May at $66,606 and Isabella Bank's April and July at about double. Accounting sent a corrected file on 2026-10-07 (MRPC Revenue Shares April-August.xlsx, installed as MRPC Revenue.xlsx) with Austin's May at $33,302.75, VIP's own figure, and Isabella's months fixed, so nothing is called out now and Austin's projected 2026 is not inflated. The corrected file has title rows above its header and a second sheet of customer refunds, so the reader takes the sheet named Sheet1 and the row that starts "Client". The workbook lives with the MRPCPM analyses but has no
`<id>-<period>` in its name, so the daily prune leaves it alone.

### 2026-10-06 — The money cross-check accepts a one-dollar rounding difference

Summary: The validation gate no longer fails a correct deck because the P&L's program-to-date total is
one dollar away from the extract's rounding. Rally CU's October deck was rejected on it and now passes.

`validate_deck.extract_findings` requires each headline money figure from `base_extract.json` to appear in
the deck. Rally CU's ARS Financial Performance table states program-to-date revenue as the sum of its own
rounded lines, $35,733,424, while the extract's unrounded total is 35,733,424.51, which rounds to
$35,733,425: one figure, two correct renderings, and the check accepted only one (Aaron, 2026-10-06; the
build was rejected with 1 FAIL and delivered after the check was corrected). A dollar either side of the
extract's rounding now passes; two dollars off, or the figure missing, still fails. The table is not
changed: rounding it to the extract's figure would stop its lines adding up.

### 2026-10-06 — A killed build no longer blocks its client for hours

Summary: If a build is killed or crashes, the next build of that client now takes over at once instead
of being refused for up to three hours with "Someone is already building this client".

Austin Bank and Sugar River Bank could not be rebuilt after a build was stopped, because the build's
`.launcher.lock` stayed behind and only expired after `LOCK_STALE_HOURS` (3). The lock now records the
holder's machine and process (`host H, pid N, started T`). `lock()` takes over immediately when the lock
names THIS machine and that process is gone (`_holder_is_gone`); the start time is compared too, so a
reused process number is not mistaken for the holder. A lock from another machine, or an old lock with
no process on it, is judged by its age as before, and a live holder still stops a second build. The
process check uses `OpenProcess` / `GetExitCodeProcess` on Windows and never `os.kill`, which would
terminate the process there.

### 2026-10-06 — Slide fixes from the Austin Bank 2026.10 review

Summary: Four slide corrections. Product Mix and Excluded Accounts now show the same smaller callout
subtext; the Business take-rate slide hides a Historical Take Rate that has nothing behind it; a month
that has only just begun, with nothing in it, is no longer charted on Referral Trend or MRPC
Enrollments by Month; and the labels on MRPC Revenue by Month no longer run together.

All four from Aaron's review of the 1075 deck (2026-10-06).
- **Callout subtext.** The 12 pt label under each KPI figure on Product Mix stayed at 12 pt (that slide
  is "dense" in `restyle_fonts`) while the same labels on Excluded Accounts were raised to 16 pt. Both
  now keep the smaller size: `shapes.tile(small_label=True)` names the label and
  `restyle_fonts.SMALL_TILE_LABEL` leaves it alone. Every other tile is unchanged. STYLE.md lists the
  exception.
- **Business Historical Take Rate.** It read 0.0% because Austin has no ARS-eligible business accounts:
  the rate was 0 / 0, not zero. `shapes.drop_kpi_tile` removes that tile and spreads the other three
  evenly; the notes already say no business account is eligible and now say no historical rate is shown.
  A client with eligible business accounts is unchanged.
- **Empty partial month.** `month_complete.drop_empty_partial_month` removes the latest month from a
  series when it is partial and 0, so Oct'26 is no longer drawn as a bar of 0 beside full-height
  months. ICS Referral Trend and MRPC Enrollments by Month use it; the title's month count, the legend
  and the caption follow, and the notes name the month left off. A partial month with any activity
  still shows, hatched; a complete month at 0 still shows.
- **MRPC Revenue by Month labels.** Twelve near-equal bars put their value labels side by side and they
  overlapped. The labels are now turned upright above each bar, so each is only as wide as its own column
  (navy: the chart rule bars the canvas colour from any mark).

### 2026-10-06 — October ARS decks pass validation: the period pill widens, the P&L table fits

Summary: ARS decks for October were failing the validation gate and could not reach Outputs. The
"PTD · September 2026" pill now widens to fit its text, and a P&L with many cost lines now fits
above the logo band.

All three October builds (1075 Austin Bank, 1204 First State Bank - Michigan, 1537 Brooks Bank)
failed with 4 to 5 FAILs (Aaron, 2026-10-06). Two causes. (1) The upper-right pill is 2.35 in wide,
sized for "PTD · June 2026"; "PTD · September 2026" needs 2.50 in at 16 pt and wrapped onto the
slide title on four slides (the "September 2026 Data" pill on a fifth). `shapes.widen_pill_to_text`
now widens any one-line pill in that corner to its measured text, right edge fixed, and
`build_ars_gen` runs it over every slide before the layout pass. Every deck whose data month is
September needed it. (2) Austin Bank carries nine cost lines, so the P&L table at a fixed 0.46 in
row height ended at 8.15 in on a 7.5 in slide. `pnl_slide` now tightens the row height to the room
above the logo band, never below `ROW_MIN` (one 16 pt line plus the cell margins), and leaves a
short table at 0.46 in as before.

### 2026-10-06 — The launcher runs its code from a copy on the PC

Summary: Sheila and Build ARS Deck now run from a local copy of the launcher code instead of the
network share, so builds no longer crawl or hang on file lookups. The first launch after each
release copies the code, which takes under a minute.

Austin Bank's 2026.10 combined build ran for over an hour and never finished (Aaron, 2026-10-06).
A stack trace showed the build inside `import summit_slide`, and a file lookup on the share costs
about 50 ms when the file is not there, which Python does constantly while importing; the same
build ran from a local checkout in about three minutes. `runtime.cmd` already put Python on each PC;
it now also copies `Tools\RPE` to `%LOCALAPPDATA%\RPE\Code` whenever `RELEASE.txt` changes, and both
.bat files run `ars_launcher_web.py` / `ars_launcher.py` from there. `RPE_DATA_ROOT` still points at
the share, so inputs, outputs and build artifacts are unchanged. A status check for 1075 took 4 s
from the local copy and 22 s from the share.

### 2026-10-06 — Sheila's header no longer carries the long name

Summary: CSM Sheila's header and browser tab now read just "CSM Sheila", without the "Smart Helper
for Executive Insights, Layouts & Analytics" line.

Removed at Aaron's request (2026-10-06) from the page header and the page title, and from the
launcher window title and banner in `ARS Deck Builder GUI.bat`. The module docstring and the
`--help` text still carry it.

### 2026-10-06 — Sheila's client list shows a Ready chip

Summary: In CSM Sheila's client list, a green Ready chip now appears under the client name when
every check passes and the deck can be built.

Ready (Aaron, 2026-10-06) comes from the client's stored status: every pre-build check passes and
no deck for the cycle is in Outputs yet. It is shown only for the cycle on screen, from a status
younger than `STATUS_TTL`, and not beside Building, Queued, Error or Lift Matrix expired, so an old
"ready" cannot read as current. No check changed; the chip reads what the client page already says.

### 2026-10-05 — Sheila's Reported tab is now Feedback

Summary: The tab in CSM Sheila that lists reported issues is now called Feedback. Nothing else
about it changed.

The tab button and the view's heading read "Feedback" (Aaron, 2026-10-05). The table's
"Reported" column stays — it is the date a report was made. Internal names (`tab-reported`,
`/api/reports`) are unchanged.

### 2026-10-05 — The morning copy takes the small files first

Summary: The 08:00 source check now copies DCOs, workbooks and analyses into `Inputs/`
before any ODD extract, and the extracts smallest first. A new workbook is on hand minutes
into the run instead of behind a month of extracts.

Aaron, 2026-10-05: "I see Austin Bank and Sugar River in the source but not inputs."

The copy went by kind — DCO, then ODDD, then Workbook — so on 2026-10-05 about 2 GB of
October ODD extracts for all five books stood between the start of the copy and the seven
1 MB workbooks the CSMs were waiting on. At the share's rate that morning (~0.3 MB/s beside
a launcher build) the task's 50-minute execution limit fell inside the third extract, and
the next morning's fire would have started the same list in the same order. `_copy_order`
in `watch_sources` is the rule; `tests/test_watch_sources.py` pins it. Nothing about WHAT
is copied changed — only the order — and an extract a cut-short run did not reach is copied
the next morning as before.

Also: `CLAUDE.md` said the task's execution limit was two hours; it is 50 minutes
(`register_watch_task.ps1`, 2026-09-21), and the file now says so, along with the standing
rule that the file-get runs once a day at 08:00 and is never started by hand beside the task.

### 2026-10-05 — Gregg's last eight clients are Unassigned

Summary: The eight clients the Gregg Miller assignment sheet never named a successor for are
now labelled **Unassigned** in Client CSM List.csv rather than still showing a CSM who has
left. Gregg now holds nothing.

Aaron, 2026-10-05: "I think those clients are inactive. Label them as Unassigned."

1088, 1092 Premier Bank, 1119, 1122, 1139, 1447, 1455 and 1664. Their `csm_source` says why —
left off the reassignment sheet, believed inactive — so the label is not mistaken later for a
CSM nobody recognises.

Labelled, never deleted: the row is the only record that the client exists and who used to
hold them, and `clients.md` decides what gets BUILT, not this file. None of the eight is on
the build or CashPlease roster, so no deck is affected and `Outputs\Unassigned` is never
created. The previous file is in `Build Artifacts/csm-reassignment/`.

### 2026-10-05 — The Lift Matrix says which accounts it is valued on, and the 08:00 run files Sheila's issue reports

Summary: `lift_values` has a POPULATION variable at the top — "both", "personal" or "business"
— defaulting to **both**, which is every ARS-eligible card holder and is what it already
valued. The scan records which was used. Separately, the 08:00 source watch now files the
issue reports CSM Sheila queues, so a report reaches GitHub the next morning without anyone
running the sync by hand.

Aaron, 2026-10-05: "For Lift Matrix builds we're only building the values based on Personal
accounts. Default to all accounts and add a variable at the top to do Personal, Business, or
Both"; "Add the issue sync to the 8am run."

**The Lift Matrix was not personal-only.** Its only account filters were ARS eligibility and
holding a debit card; business accounts were added on 2026-09-25 ("change the calculate to
include business accounts"). So the default does not change a single figure — what changes is
that the population is now a stated choice rather than an assumption, and the other two are
possible without editing the loop.

- `POPULATION` / `POPULATIONS` at the top, `in_population()` beside `segment()`, and
  `scan(..., population=...)` so Sheila or `build_lift_matrix` can ask for one.
- An account whose `Business?` is **blank** is neither personal nor business: valued under
  "both", left out of the other two rather than guessed at. The ODD carries them, and calling
  one personal would put it in a matrix the client reads as consumer-only.
- The filter sits AFTER the fee block on purpose: the OD fee is the CLIENT's, read off every
  eligible account, and valuing a narrower population must not narrow the fee with it.
- The scan carries `accounts` and `accounts_label`, so a matrix cannot be read without knowing
  what it was valued on. A population with no card holder in it is a stated failure naming how
  many accounts fell outside it, not an empty matrix.
- A setting that is not one of the three stops the build: the file goes to Bradford, and a typo
  must not quietly fall back to valuing everything.

**The issue sync runs at 08:00** (`watch_sources --issues`, now in the registered task):

- It goes with the MAIL step, after the share results are saved, for the reason the mail step
  is there: both reach off the machine, and a step that can hang must not take the share
  check's findings down with it.
- Never fatal. gh missing, no internet, a damaged report — the morning report says so and the
  reports stay queued, which is what queueing them is for.
- `register_watch_task.ps1` passes `--issues`, guarded the way `--once-daily` is: this script
  is routinely newer than the checkout it registers, and an argument argparse does not know
  makes every fire exit without checking anything. The live task was re-registered.

### 2026-10-02 — Report an issue from Sheila, and a view of what was reported

Summary: CSM Sheila has a Report an issue button and a Reported tab. A report is saved to the
share straight away and filed on GitHub by a sync run on Aaron's machine; the tab shows every
report with its GitHub number and state, so nothing reported gets lost or chased twice.

Aaron, 2026-10-02: "Add a button to report issues in Sheila that will send issues to github. I
also need a view into those issues so we can make sure we address them."

**No GitHub credentials on any CSM machine.** Sheila runs from the released copy under
`Tools\RPE` on each CSM's machine and the repo is private, so a token there would be readable
by anyone who can reach the share. So the button only QUEUES:

    Sheila   ->  issue_reports.queue()   a JSON file in Build Artifacts/issue_reports/
    Aaron    ->  issue_reports.sync()    gh issue create per queued report, then gh issue
                                         list written back as issues.json
    Sheila   ->  issue_reports.view()    the queue plus that cached list

The button answers instantly and works with no VPN and no internet. The cost is that an issue
reaches GitHub when the sync runs, which is why a report shows as **queued** until it does —
saying otherwise would have people waiting on an issue nobody can see.

- `scripts/issue_reports.py` is the whole thing: `queue`, `sync`, `view`, and
  `python scripts/issue_reports.py sync | list | report`.
- **A report that cannot be filed stays queued** and is reported, never dropped: the share
  holds the only copy and the person who wrote it has moved on.
- **sync is idempotent** — a filed report carries its issue number, so a re-run files nothing
  twice.
- **The label is created if the repo has not got one.** The first real report failed with
  "'sheila' not found"; a label is a filter, not the point, so a repo that refuses to create
  it gets issues filed without one.
- An issue filed by hand under that label still appears in the view — it is shown, never
  hidden, or the tab would quietly disagree with the repo.
- Verified end to end against the real repo: queued, filed as #13 and #14, closed on GitHub,
  and the view picked up `closed` on the next sync. Both test issues are closed.

`tests/test_issue_reports.py` pins that no path but `sync` calls gh, that a failure keeps the
report, that a second sync files nothing twice, and that a missing label does not stop a report
being filed.

### 2026-10-02 — The client's logo on every data slide, and three slides tightened

Summary: The bank's logo is now the bottom-right mark on every data slide, deliberately. The
agenda's large copy of it is gone, the section dividers no longer say "SECTION" above the
section name, and a client with a single fee line gets one cost row instead of that line and
an identical total.

Aaron, 2026-10-02: "Use the client logo on the data slides"; "with the bank logo moved to the
lower right corner, the larger logo can be removed from the agenda slide"; "remove SECTION
from heading slides"; "if we have just one fee line, we don't need that and a total line".

- **`shapes.data_logo`** is the one placement, because the box was stated in six slide modules
  and four builders. The logo is FITTED and centred in the 1.70 x 0.54 box, never stamped at
  the box's size: client logos run 1.50 to 8.77 wide-to-tall, so Marine comes out 1.70 x 0.52
  and Wellworth 1.70 x 0.19. Cropped to its ink first; a client with no logo, or an unreadable
  one, falls back to the CSI | Velocity lockup and never fails a build. Wired into the ARS
  branding pass (which re-stamps every data slide, so it covers the slide modules too), the
  ICS builder and the CashPlease builder. Section dividers keep the lockup top-left.
  This also makes the placement DELIBERATE: it had become a side effect of the redesigned
  cover, because the branding pass picks "the canonical lockup" by grabbing the first
  logo-shaped picture off the first big-title slide, which is now the cover.
- **The agenda's client logo is removed** from the ARS and ICS builders (MRPC decks have no
  agenda). It was the only slide carrying the client's mark before today; now every data slide
  does, and the cover carries it at cover size, so the agenda's was the third copy in four
  slides.
- **No "SECTION" kicker** on the dividers: the slide is full-bleed navy with the section name
  at 52 pt, so a label announcing that it is a section said nothing.
- **A lone fee line is its own total.** Marine carries only a Respondent Fee, so the itemised
  row and Total costs were the same three figures twice. The surviving row keeps the fee's
  NAME, which "Total costs" never said, and is styled as the total; two or more lines still
  get a total row to add them up. The notes read both kinds, or a one-fee client would have
  been described as having no itemised cost at all. One row fewer let the chart's ceiling go
  from 2.05in to 2.50in.

### 2026-10-02 — Gregg Miller's accounts reassigned

Summary: Gregg Miller is leaving Velocity. 58 of his clients move to other CSMs per the
assignment sheet, so their decks now file under the new owner's Outputs folder and carry the
new owner's Contact card. Max Willett takes 27 of them and is now in CSM Contacts.csv, without
which his clients' builds would have stopped.

Source: "Gregg Miller Account Assignments final 10-2-26.xlsx" (Aaron, 2026-10-02). Split:
Max Willett 27, Aaron Burgard 11, Jordan Berkowitz 10, James Gilmore 8, Daniel Wood 2; 17 of
them interim, the rest permanent.

- `Client CSM List.csv`: the `csm` column for all 58, with `csm_source` recording the
  reassignment and marking an interim owner as interim. That file is what
  `rpe_env.client_outputs` reads to file a deck and `rpe_env.csm_contact` reads to draw the
  Contact card, so this one column moves both. The previous file is in
  `Build Artifacts/csm-reassignment/`.
- `clients.md`: the CashPlease roster's CSM column for 1526 Create CU and 1652 Security CU.
- **Six clients build decks**: 1147 Sutton, 1487 Orsa CU, 1526 Create CU, 1637 Ouachita Valley
  FCU and 1652 Security CU to Max Willett; 1156 BancFirst to James Gilmore.
- `CSM Contacts.csv`: a row for Max Willett, from his signature block. **Five builds were
  blocked without it** — the Contact card is the managing CSM and never falls back to another
  one, so `csm_contact` raises rather than drawing the wrong person. His row carries a cell and
  no office line, like Daniel's and James's.
- Three built decks and five archived ones moved from Gregg's Outputs and `_Archive` folders to
  the new owners'. Each was copied, size-checked and only then removed.

**Gregg's ODD folder stays in the scan** (Aaron, 2026-10-02: "still scan gregg's folders"): his
clients' extracts are still landing there, and `deck_status.SRC_ODDD` keeps his entry.

**Max Willett has no ODD folder yet.** `\\PADMIS105\Velocity_company\MaxWillett` holds client
folders and no OD Data Dumps folder, so he is still not in `SRC_ODDD`. Nothing is broken while
his clients' extracts land in Gregg's folder; the morning watch stops seeing them the day the
data team switches. Add him to `SRC_ODDD` when the folder exists.

**Eight of Gregg's clients have no new CSM in the sheet** — 1088, 1092, 1119, 1122, 1139, 1447,
1455, 1664 — and are still recorded as his. None of them is on the build or CashPlease roster,
so no deck is blocked, but they are unowned.

### 2026-10-02 — A combined deck carries its CashPlease section

Summary: Asked for a combined deck, the launcher and CSM Sheila now include CashPlease for the
clients who ship it as a section. They did not before, so a combined rebuild produced a deck
without it and archived the four-product one as "replaced by a different program mix".

Found by rebuilding 1539 Marine FCU, whose deck is ARS-ICS-MRPC-CP: the rebuild came out
ARS-ICS-MRPC and the four-product deck went to the archive. `program_availability` reads the
programs in clients.md's MAIN roster row, and CashPlease is not there — it has its own table in
that file, because the weekly workbook carries every Velocity CashPlease client across all CSMs
and a tab proves a client is live on the program, never that a deck is wanted.

**Thirteen clients ship CashPlease as a combined section** — 1192, 1217, 1526, 1529, 1539, 1542,
1632, 1652, 1681, 1734, 1748, 1761, 1776 — and every one would have lost that section the same
way. Two of them (1632, 1734) have no ARS at all.

- `ars_launcher.cashplease_availability` reads the CashPlease ROSTER, never the workbook. Only a
  row that ships CashPlease AS A SECTION joins a combined deck: one marked "standalone deck"
  gets its own module, and a client whose slides ship inside a combined deck does not also get
  one (CLAUDE.md). A roster row with no weekly workbook in Inputs is REPORTED, not dropped.
- `combined_programs` returns CashPlease last, which is both its section order and how
  `deck_tag` names the file: 1539's is `ARS-ICS-MRPC-CP`.
- `build_month.build_cashplease_section` builds the slides in the build chain — cp_extract then
  build_cp_gen, always from the NEWEST weekly workbook, so the section can carry a later date
  than the sections beside it and is never re-dated to match them. A client on the roster with
  no tab in that week's workbook is named in the error, never guessed at.
- The launcher carried clients.md's own token for each extra program (`ICS-REFERRALS`);
  CashPlease has no token in the main row, so it now falls back to its own name.

Marine's deck was rebuilt by hand through the pipeline before this landed; the fix is what makes
the next one come out right without that.

### 2026-10-02 — The cover and the section dividers are redrawn, left-aligned, with the section's figures

Summary: Every deck's cover and section dividers now use one shared layout: the cover
shows the client's logo, the reporting month large, the client name and the products as
chips; each program divider carries that program's three headline figures, and in a
combined deck a progress track along the bottom shows every section with the current one
in orange. Nothing else on any slide changes.

Aaron, 2026-10-02: "Move the section dividers and title slides into main", from the
redesign prototype (`prototype/build_prototype.py`, `docs/STYLE-PROPOSAL-2026-10-02.md`).

`build/cover_divider.py` draws both for all four programs, and each builder calls it:
ARS redraws the shell's cover and every full-bleed divider in place at the end of the
build (sub-section dividers keep their own title and second line, which the builder has
already swapped); ICS, MRPC and CashPlease draw theirs directly. `assemble_combined`
replaces the cover's chips with the included products and draws the track on each program
divider. The slides keep everything the rest of the pipeline reads: the cover is still the
one slide with an "Executive Review" line and still yields the client and month to
`validate_deck` and the combiner's period check; the first text shape is still the title;
the full-bleed rectangle still marks the slide as un-numbered; nothing is below the 16 pt
floor and no shadow is drawn. `restyle_fonts` now leaves a Montserrat weight
("Montserrat ExtraBold") in place rather than flattening it to "Montserrat".

Figures on the dividers: ARS revenue-to-fees, profit PTD and the latest mailing's
response; ICS referrals PTD, YTD and the previous month against goal; MRPC enrollments
PTD, last complete month and trailing 12; CashPlease loans booked, principal advanced and
loans per 1,000 DDAs. The templates are unchanged (the shells still carry the old slides;
the builders redraw them), so the layout baseline did not move.

### 2026-10-02 — The ICS referrals landing says what is actually wrong with it

Summary: When a saved query result cannot be merged, the report now names what arrived —
usually the per-client summary grid instead of the member-level one — rather than telling
you to save it "with column headers" on a file that has them.

Aaron, 2026-10-02: the morning report said `ics_referrals.csv: header is not the ICS
referrals query's first result (save the first grid with column headers)`, and the file did
have headers. It was the SUMMARY grid: 87 rows of client_id, client_name, referrals,
accounts_found, first_issue, last_issue, where the merger wants the first grid's 20 columns,
one row per referred account. The query emits both and the summary is the readable one, so
it is the easy one to save by mistake; the old wording sent the reader looking for a missing
header row instead.

`_why()` now reports the per-client summary grid by name, an empty file, a file that is not
comma-separated, and otherwise the column count with the first few names that are missing.

Two things that made this worse and are worth knowing: the result was saved as
`ics_referrals.csv`, which is the MERGED store rather than a dated landing
(`ics_referrals <date>.csv`), so it overwrote the accumulated detail; and a full pull
(`@since = null`) is the way back, because the database is the source.

### 2026-10-02 — ARS Financial Performance is a P&L

Summary: The ARS Financial Performance slide is now the program's P&L — incremental revenue,
each cost line the workbook itemises, total costs, incremental profit and profitability — in
three columns: the last complete month, the year to date, and the program to date, over a
chart of the last twelve months. It replaces the five tiles and three bullets that were on
that slide. The Revenue Guarantee slide no longer repeats the table.

Aaron, 2026-10-02: "i wanted a P&L slide that makes it easier to see the full financial
picture", "replace the current [slide] with this format", "name it ARS Financial Performance".

The tiles stated four figures and could not show where the money went. Marine FCU's read
$144,999 of revenue and $144,999 of profit for August — the same number twice, because August
carried no respondent fee at all — and nothing on the slide said so. The P&L shows the cost
line, the zero, and a chart in which that month is a bar with no cost in it.

- `build/ars_pipeline/pnl_slide.py` builds it, from `revenue_guarantee_slide.pnl` — the one
  place the Actuals tab is read and the complete-month rule applied — so this slide and the
  guarantee arithmetic cannot disagree.
- **Year to date is new** (`pnl`): the complete months of the last complete month's own
  calendar year. On a 97-month program a month beside the lifetime total says nothing about
  how this year is running — Marine's 2026 is $1,217,922 of revenue against $131,040 of cost.
- **Profitability is a row, per column.** The program ratio was the only one the deck stated
  anywhere; Marine's year runs at 9.3 : 1 against the program's 5.4 : 1. A column with no cost
  has no ratio and reads as a dash — never infinity, never zero, which would say a program
  returned nothing in a month it simply was not charged for. The orange highlight is bound to
  the PROFIT row, so it did not slide onto the ratio when that row was added.
- **The chart** is each month's revenue split into cost and profit, so its bar heights are the
  table's revenue row and it reconciles with the figures above instead of restating them. It
  shows what the table cannot: when the cost lands. A waterfall was rejected — it would have
  drawn the program-to-date column's three numbers a second time. Sized from the room the
  table and any caption leave and RENDERED at that height, so it runs the full width whatever
  a client's P&L looks like; its margins are reserved in INCHES, because an axes-relative
  legend anchor cleared the top at 1.38in and was clipped against the table at 2.05in.
- **No caption about a month that carried no cost.** It was there first, on the reasoning that
  identical revenue and profit look like an error; the table shows the $0 line and the chart
  shows a bar with no cost, so it was the deck saying the same thing a third time at the cost
  of the chart's height. A month left out as incomplete is still stated.
- **The Revenue Guarantee slide drops its P&L table** and keeps the ratio, the gap and the
  sentence deriving them, as two centred callouts. A client under 3 : 1 gets both slides and a
  deck must not state one thing twice. Its notes point at this slide instead of describing a
  table it no longer draws.

**Drawn IN PLACE over the template's slide of that name.** The first version added the new
slide and dropped the old one from the slide list, which is the defect CLAUDE.md names:
freeing a partname lets python-pptx hand that number to a slide added later, and the Contact
slide is added later. The build log reported both slides built and the finished deck came out
with **Excluded Accounts gone**. Dropping it after every `add_slide` would avoid the partname
but leave an unpopulated shell slide in the deck for every pass in between, including the
figure-consistency gate. So nothing is added and nothing is dropped: the slide is emptied and
redrawn, keeping its partname, its position, its title and the deck's 49 slides.

What the tiles said that this slide does not: "Profitability of N : 1 is well above the 2 : 1
threshold — there is no deferred billing on this program." The ratio is here, but the 2 : 1
framing now appears only on the Revenue Guarantee slide, which builds below 3 : 1 — so for a
client above it that sentence has left the deck. Months and mailings are unaffected; they are
on Program Overview.

`validate_deck.extract_findings` required the extract's revenue and profit VERBATIM in compact
form (`$1.16M`), which only the tiles wrote. It now accepts the compact or the exact-dollar
rendering, since the P&L states the same figure to the dollar — the same trap that failed a
correct deck in 2026-09 over `$830K` against `$0.83M`.

`tests/test_pnl_slide.py` pins that the slide is ungated on profitability, that the guarantee
slide no longer tabulates a P&L, that a zero-cost month gets no sentence and no ratio, and
that the chart's box stays clear of the logo band. The golden deck's pinned slide count stays
at 49, which is the point.

### 2026-10-02 — BUILT leads the launcher's checks, and stops them

Summary: In CSM Sheila and the launcher, a client whose deck is already built now says so on
the first line, and the input, Lift Matrix and other-program checks are skipped — nothing is
going to read those inputs. Austin Bank went from eight lines to four, and from seconds of
share reads to 0.01s.

Aaron, 2026-10-02: "I'd think the BUILT check would be first. We don't need to check for
components if it's already built."

The skipped checks are the slow ones: the ODD extract's month at source, the ARS workbook, the
DCO, the Lift Matrix window and, for a combined deck, every other program's data. They were
being read to answer a question nobody asked about a deck that already exists. A rebuild runs
all of them — `all_checks` only short-circuits when the deck is built AND no rebuild was
asked for, and `ars_launcher.py build` passes `--rebuild` through.

`built_line` is now its own function so the line can lead the list rather than close it.

### 2026-10-02 — Obsidian is out of deck production

Summary: The project no longer names Aaron's Obsidian vault, its paths, or the script that
read it. The facts those notes carried are unchanged — they are about Aaron's client book,
which is a real record whatever application holds it — and nothing in a build ever read it.

Aaron, 2026-10-02: "remove references to Obsidian from the RPE project deck production."

- `scripts/obsidian_roster.py` removed. It read 61 client folders out of the vault for a
  one-time reconciliation on 2026-09-01 and nothing imports it; it is in git history if the
  check is ever wanted again.
- `CLAUDE.md`'s writing-style rule pointed at `Claude/Operating Instructions.md` in the
  vault. The banned words were already listed here in full, so the pointer bought nothing
  and a rule whose source sits outside the repo cannot be checked from inside it.
- `clients.md`: the CashPlease roster's provenance, three roster notes, the 2026-09-01
  reconciliation record and gaps 2 through 7 now say "the client book" and name no
  application, no vault path and no reader script. No fact changed, no gap was dropped —
  they are open questions about a client record, and they stay open.
- `build/cashplease_pipeline/cp_extract.py`: the `NAME_OVERRIDES` provenance comment.

Verified after the edits: `read_roster` still parses 55 clients and `read_cashplease_roster`
19 rows, with 1539 still carrying its "ARS-ICS-MRPC-CP section" row. `clients.md` is a build
input, so a wording pass over it is not a documentation-only change.

### 2026-10-02 — Sheila answers a refused request instead of dropping the connection

Summary: When Sheila refused a request (for example one without its access token), the
caller sometimes got a dropped connection instead of the refusal. Sheila now always sends
the answer. A test that failed now and then on a busy machine was caused by this.

Aaron asked to look into the Sheila token test that failed once in a full run
(`test_the_api_refuses_a_call_without_the_token`). The test was right; the server was not.
`do_POST` answered 403 before reading the request body, and on Windows a socket closed with
unread data is reset. The caller got `ConnectionAbortedError` in 28 of 2,000 tokenless POSTs,
and in 127 of 2,000 with a 100 KB body. Under a loaded full suite that occasionally hit the
test's one tokenless POST. `do_POST` now reads the body first, capped at `MAX_POST_BYTES`
(1 MB; larger is refused 413), then checks the token. 4,000 of 4,000 now answer 403. Tests:
`test_a_refused_post_is_answered_not_reset` (300 refused 100 KB POSTs, all answered) and
`test_a_post_over_the_size_cap_is_refused`.

### 2026-10-02 — Product Mix and Excluded Accounts count one book, and it adds up

Summary: The two account slides disagreed. Product Mix counted every account except closed
(71,466 on Marine FCU) while Excluded Accounts counted only the open ones (66,462), and the two
eligible counts were two apart. Both slides now count the same accounts, and on Excluded
Accounts the outside-ARS and ARS-eligible figures add up to the total above them.

Aaron, 2026-10-02: "The number of accounts (excluding closed) differs between slides. Make those
numbers flow better. I'd expect to see the same number of Open accounts on either slide, and then
the ARS eligible accounts and the outside ARS accounts should sum to the total open accounts."

Each slide was right on its own terms, which is why this survived two deliberate decisions in
opposite directions: Product Mix moved to the excluding-closed population on 2026-08-28 because
the status-Open count understated ARS's coverage, and Excluded Accounts was scoped to strictly
OPEN accounts on 2026-08-29 because a dormant account is not an answer to "why is this open
account excluded". Neither reading is wrong alone. Read on consecutive slides they cannot both
stand, because a reader's first move is to subtract one from the other.

The excluding-closed population wins, per Aaron, and Excluded Accounts now counts it:

- Its population is every account the shared classifier does not call closed — the same
  population, through the same classifier, that Product Mix counts.
- "Account not open" joins product code, debit card and other as a REASON, first in the
  waterfall, so the other three bars read exactly as before (Marine FCU: not open 5,002,
  product 22,473, no debit card 5,454, other 908 — 33,837 outside ARS, plus 37,629 eligible,
  = 71,466).
- Its eligible tile counts eligible accounts in that book, so it matches Product Mix's. The
  dormant-but-eligible accounts the core still flags (2 on 1539, 147 on 1204, 324 on 1509) are
  inside it rather than bridged by a footnote; the notes still name them. It used to count
  eligible accounts across the whole extract, closed ones included.
- Bar percentages are of that same book. Against the whole extract a bar read 17.5% under a
  tile saying 43% of the same accounts.
- Tiles 1 and 4 carry Product Mix's wording as well as its figures, so the two slides compare
  like with like.

Product Mix's table said "Open" over a column counting dormant and inactive accounts too, and
totalled as "Total — open accounts" — the same mislabel the tile above it was fixed for in
August, left in the table underneath. Now "Accounts" and "Total — excl. closed".

Added with the fix (CLAUDE.md: add the check that would have caught it):

- `validate_deck.account_population_findings` FAILs a deck whose Product Mix and Excluded
  Accounts slides state different totals or different eligible counts, or whose outside-ARS
  and eligible figures do not sum to the stated total. It FAILS rather than going quiet when
  it cannot find the tiles it reads, because a check that stops looking when a label is
  renamed reports a clean deck it never examined. It FAILs all 33 of the 2026.09 ARS decks,
  which is correct — they carry the split.
- `tests/test_account_population.py` runs both extractors over an ODD written for it, carrying
  the cases that pulled the slides apart: a dormant account the core flags eligible, and a
  closed one it also flags eligible. All five assertions fail against the old code. The
  synthetic ODD could not have caught this on its own — its `Elig` flag is only ever "Yes" on
  a status code of O or A, so the two readings agree on it by construction.

A general "one tile label, one figure" rule was written first and thrown away: 12-Month
Eligible Take Rate — Personal and — Business carry the same tile labels over different
populations by design, so it failed correct slides, and it could not have seen this defect
anyway — these two slides disagreed about the wording as well as the number.

Not rebuilt: the 2026.09 decks already delivered. Any deck built from now on reconciles.

### 2026-10-02 — The user guide covers the Sheila CSMs open today

Summary: The ARS Deck User Guide now explains CSM Sheila properly: the cycle pill and how to
look at an earlier cycle, the Decks, Lift Matrix and Data Issues tabs, the row of links under
every client, and where a code sheet gets corrected. Re-released to CSM_Reporting.

The guide was written on 2026-09-16, when Sheila was one paragraph inside step 1 of the
double-click-the-.bat instructions. Since then she has gained the cycle picker (2026-10-02),
the Data Issues tab and the Lift Matrix tab (both 2026-09-25) and the shared links row, none of
which a CSM could read about anywhere. A CSM opening the Lift Matrix tab had no written answer
to the question that decides what they do next — whether exporting a matrix changes this
month's deck (it does not; Bradford loads it into the workbook). The sample console output also
still showed `period 2026.09`, which reads as a guide nobody has looked at since.

### 2026-10-02 — MRPC Program to Date and Current Program Status, from the weekly

Summary: MRPC Card Portfolio and Key Metrics are replaced by two slides built from the MRPC
Enrollment Summary weekly. "Program to Date" shows everyone enrolled since the start.
"Current Program Status" shows who is active now. The figures the old slides showed did not
agree with each other or with any current count.

Aaron: "what's the gap between Active Enrollments and Total Cards billed? Create one slide with
Program to Date Totals and another with current program status." Then: "go ahead with the two
new MRPC slides using the weekly."

The gap could not be explained, because neither figure was current. For Marine FCU 1539:
- Key Metrics' "Active Enrollments" (VIP `key_metrics.active_enrollments`, 4,396) carried no
  date or source.
- Card Portfolio's "Total Cards Billed" (VIP "Total Fees by Fee Charged", 6,729) counts
  accounts per fee amount over a window VIP does not state.
- Key Metrics' "Tier Mix (Program to Date)" was that same billing breakdown.

The weekly's own figures reconcile: 7,942 cardholders and 7,408 accounts enrolled to date;
2,755 active accounts and 2,825 active cardholders as of 9/27/2026.

- **Program to Date** (`status_slides.fill_program_to_date`): cardholders and accounts
  enrolled, and the take rate over open debit accounts (19.1%). Also the Platinum / Gold /
  Business mix from the weekly's TOTAL row (6,808 / 1,134 for Marine). A "Who enrolled" panel
  shows primary / joint, new / existing account and employees (each pair sums to the
  cardholders), and new accounts opened that enrolled (3,019 of 26,898).
- **Current Program Status** (`status_slides.fill_current_status`): active accounts and
  cardholders, and cardholders enrolled in the last 12 complete calendar months (1,412,
  Sep'25–Aug'26). The weekly lists only months with an enrollment, so a missing month counts
  as none, not as a step back in the window. A chart shows every enrolled cardholder by status
  (active 1–90 / 91–180 / over 180 days, inactive). The callout gives the share still active
  (36%), the count past the 90-day trial (2,466) and the last complete month's new-account
  take rate. The notes state the one-count difference between the weekly's status rows and
  its own totals.
- **What is no longer on a slide.** VIP's active enrollments, program-to-date and trailing-12
  enrollments, and the card-billing breakdown (cards billed, monthly billing, average fee,
  cross-sale %) are kept in the Current Program Status notes, with the reason they are not
  shown. This replaces the 2026-07-25 rule to show VIP's Active Enrollments as-is. That rule
  defined active as past the 90-day trial, which the slide now shows from the weekly.
- **One reader.** `mrpc_weekly.py` holds the weekly reader that used to live inside
  `refresh_performance_dashboard.py`. The dashboard imports it, so the page and the deck read
  the weekly one way. `mrpc_charts_gen` swaps `chart_card_pie` / `card_types` for
  `chart_tier_donut` and `chart_status_bars`, drawn at their slot size. The MRPC template
  shell's two slides are retitled to match. A client with no tab in the weekly gets both
  slides with a sentence saying so, never zeros.
  Tests: `tests/test_mrpc_status_slides.py`.

### 2026-10-02 — Changing the cycle in Sheila threw an error

Summary: Picking a different cycle in CSM Sheila showed "Could not change cycle: Cannot set
properties of null". The cycle had actually changed; the error came from the redraw afterwards.
Fixed, and the page's own names are now checked by the test suite.

Two names in the new cycle code were only ever resolved when a CSM clicked, and both were
wrong: `$("#detail")`, an id this page does not have, and `load(true)`, where the function is
called `loadClients`. Each threw AFTER the switch had already happened, so the cycle moved and
the page then said it had failed.

`pickCycle` now reloads the list and re-draws the current tab through `setMode`, rather than
poking at one element — the open client's checks, the lift overview and the issue list were all
about the other cycle anyway.

Two checks were added, because this class of mistake is invisible to Python: the page is a
string, and a bad name costs nothing until someone clicks. One collects every id the script
asks for by name and fails if the page never creates it; the other reads the cycle functions
and fails on a call to a name the page does not define. Both were confirmed to fail on the two
real bugs and to be silent on the shipped page. The name check is deliberately scoped to those
functions: a regex cannot tell a call from CSS or an object key, and a check that cries wolf
over 2,000 lines of script would be switched off within a week.


### 2026-10-02 — MRPC 2026 revenue projection; MRPC chart text at slide size

Summary: MRPC Revenue by Year now projects the current year from the trend of the last six
complete months. The projected part is hatched on the 2026 bar, and the sentence beside the
chart gives the figures. MRPC chart text now reads at its set size on the slide; it used to
shrink to 7–11pt.

Aaron: "Add a revenue projection here based on the trajectory from the past 6 months." And for
MRPC Card Portfolio: "increase chart label font sizes here too."

- **Projection** (`revenue_projection.py`; `build_mrpc_gen.revenue_projection`). A
  least-squares straight line is fitted through the last 6 complete months of VIP Revenue by
  Month (after `complete_series`). It is extended through December, and any month below $0
  is floored at $0 and named in the notes. The projected year is the VIP year-to-date actual
  plus those months. It is computed once and stored as `revenue.projection`, so the chart,
  the narrative and the notes read the same figures. On the chart the projected remainder is
  a hatched, outlined segment on the YTD bar, with the projected total above it. The
  narrative sentence carries the window, the YTD actual, the projected remainder and the
  comparison to the prior year, worded by the +/-2% band. There is no projection when fewer
  than 6 complete months are on hand, or when the YTD bar does not end on the same month as
  the monthly series. The notes give the reason, and that the projection assumes the trend
  holds. Marine FCU 1539: $94.8K projected ($37.8K actual through May + $57.1K
  Jun–Dec), up 16.3% on 2025. VIP revenue currently ends at May, so Jun–Sep are projected
  though they have ended; the notes say so. Tests: `tests/test_revenue_projection.py`.
- **Chart text** (`mrpc_charts_gen.SLOT_IN`). Each figure was drawn 1.2–1.9x larger than its
  slot and shrunk to fit, so 13pt text landed at 7–11pt (the Card Portfolio legend at about
  8pt). Every chart on the deck is now drawn at its slot's size in inches, so the size set
  in the code is the size on the slide. The Card Portfolio donut and legend are re-set for
  that size (names 14pt, detail 12.5pt, centre 22pt/12pt) with wider legend spacing.
  Revenue by Month's value labels are 12pt so adjacent labels do not touch.

### 2026-10-02 — MRPC "Still Active" line drawn from real counts; Non-User vs Threshold test slide

Summary: The Still Active line on the MRPC Retention chart was invented. It is now drawn from
the VIP sheet's actual counts. A new opt-in test slide splits sustained ARS responder activity
into Non-User and Threshold offers, mailing by mailing.

- **MRPC Retention** (`mrpc_charts_gen.chart_retention`). The line read `still_active_approx`, a
  True/False flag, where it needed the `still_active` counts. Because that flag is False on
  every current sheet, the line fell back to 60% of enrolled on EVERY MRPC deck. For Marine FCU
  1539, Jun'26 showed about 92 still active where the sheet says 124 of 153. It now draws
  `still_active`. A sheet without a count for every cohort month stops the build instead of
  getting an invented line. The notes list still-active / enrolled for each cohort. Found while
  answering Aaron's 90-day retention question; he approved the fix 2026-10-02. Tests in
  `tests/test_mrpc_charts.py` check the line against the sheet and check that a missing count
  stops the build.
- **Sustained Activity: Non-User vs Threshold** (`sustained_split.py`,
  `sustained_split_slide.py`). Aaron: "create a test slide showing Non User sustained usage and
  Threshold sustained usage split out." It sits after Sustained Respondent Activity by Mailing
  and uses the same definition of sustained, now in import-safe `sustained_split.by_mailing`,
  which `metrics_gen` also calls. The existing slide's figures are unchanged. The segment is the
  offer the account was sent (`<Mon> Mail`: NU, or TH-nn). If that is blank it falls back to
  `<Mon> Resp`. An unknown code goes into "other", is listed in the notes, and is never put in
  a segment. If NU + TH + other does not equal the mailing's total, the build stops. A mailing
  with no month after it yet is left off and stated. A segment under 30 responders is hatched.
  OPT-IN: the slide is added only with `RPE_TEST_SLIDES=1` or `RPE_JAMES_SLIDES=1`, so a normal
  monthly build is unchanged.

### 2026-10-02 — Revenue Guarantee becomes a P&L; CashPlease chart text at slide size

Summary: The Revenue Guarantee slide is now a standard P&L — revenue, each cost line, total
costs and profit, for the last complete month and the program to date — next to the
profitability callout and the gap to (or room above) the 2 : 1 guarantee. The CashPlease
charts' labels now read at about 12–14pt on the slide; before, they were 5–7pt.

Aaron: "The Revenue Guarantee slide needs its spacing improved." Then: "Redo this slide as a
typical P&L, but keep callout for profitability." And for CashPlease Loan Portfolio by Status
and Peer Comparison: "the chart fonts on this slide are too small."

- **Revenue Guarantee** (`revenue_guarantee_slide.py`). The cumulative-lines / two-bar chart and
  its four tiles are replaced by a P&L table and two callouts. The callouts show the
  profitability ratio and the surplus or gap, with the guaranteed minimum beneath them. The
  caption sentence (run rate, months to cover) is unchanged. The figures still come from the
  Actuals tab. `actuals_tab.read` now also returns each cost line between the "Costs" heading
  and Total Cost (`lines`), under the sheet's own labels, because the MM and SM shapes carry
  different ones. A line that is zero for the whole program is left off the table and named in
  the notes. A workbook with no Actuals tab gives a program-to-date P&L of revenue, total costs
  and profit. Spacing: the old subtitle wrapped onto a second line and ran into the tiles. It
  is shorter now, and every element is placed from the measured height at 16pt (the restyle
  floor), not from a fixed top. Carlito measures about 3% narrower than PowerPoint draws
  Calibri, so wraps are measured against a shorter line (`WRAP_SLACK`).
- **CashPlease charts** (`cp_charts.py`, `build_cp_gen.py`). Each figure was drawn 8–11" wide
  and then shrunk into a 4.5–8.5" slide box, so 10–11pt text landed at 5–7pt. The renderers
  now take the slide box in inches and draw at exactly that size (`AXIS_PT` 12, `LABEL_PT` 12,
  `VALUE_PT` 13). The Peer Comparison chart wraps long metric names. Loan Volume and the
  Overview cumulative chart had the same scaling and are fixed the same way. Picture positions
  are unchanged.

### 2026-10-02 — Sheila's cycle advances on the 1st, and you can look back

Summary: CSM Sheila now shows the current month as its cycle from the 1st, and the cycle pill
opens a menu for stepping back to an earlier month — the client list, the checks and a rebuild
all follow the month you pick. The links row under a client's name (code sheet, File Explorer,
data issues) is now the same on every tab, with the other tabs one click away.

Aaron: "sheila needs to auto-advance the cycle on the 1st, so today's should show october. Also,
make it so you can click the date and select previous cycles." And: "I like this row of links on
the Lift Matrix tab. Make that consistent across the tabs."

`cycle_period()` was the newest period of ANY ARS workbook in Inputs, so the tool sat on last
month's cycle until the data team's first workbook of the new month landed — on 2026-10-02 it
still read 2026.09. A cycle is a calendar fact; whether its workbooks have arrived is a separate
question the per-client checks already answer by name ("no 2026.10 extract at source"), which is
the right thing to see on the 2nd of the month rather than a dashboard quietly showing last
month's finished work. `newest_workbook_period` keeps the old reading for the checks that want it.

The pill is now a button. Its menu offers this month and every earlier cycle this pipeline has
anything for — a deck in Outputs or an ARS workbook in Inputs — newest first; months with nothing
behind them are left out, because offering a cycle that cannot be read or built is an invitation
to a blank page. Picking one drops every cached list and status (all of it was about the other
cycle) and names that cycle on the build command line, so a rebuild of a finished month cannot
land under this one. A queued job keeps the cycle it was asked for.

One selection per server, not per browser tab: Sheila is a localhost tool one person uses at a
time, and "which cycle am I working in" belongs to that work rather than to a tab.

The links row is one function used by all three tabs, and it leaves out the tab you are already
on instead of linking to itself — so from a data issue you can open that client's deck checks or
Lift Matrix, and from either of those you can see its issues.


### 2026-10-02 — Sheila's Data Issues show the ODD page's findings; the page keeps last month's clients

Summary: CSM Sheila's Data Issues tab now also lists what the ODD and Workbook Issues page finds on its own (Personal/Business flag scan, Mail Flags, trial run, Lift Matrix dates), and the RPE Client Performance page no longer drops clients whose files for the new month haven't landed yet.

Aaron: "the refresh for data issues should also refresh what's shown in Sheila." Sheila read
`gaps.json` and the dashboard's `dataset.json`, but the ODD page adds findings of its own that it
only ever wrote into HTML; on 2026-10-02 that was 28 Personal/Business flag findings (e.g. 1204's
65 unflagged accounts) that the page showed and Sheila did not. `odd_wb_by_csm.py` now also writes
`Build Artifacts/issue_pages/odd_findings.json` (only the items that did not come from
`gaps.json`, in Sheila's issue shape, built by `common.odd_findings`), and `issues_doc` reads it as
a third source, re-read when its file changes. A Lift Matrix window finding is skipped when the
dashboard's Lift Matrix flag already covers that client. Tests: `tests/test_sheila_issues.py`.

With the period on the calendar month, `perf_clients.share_reports` read only the 2026.10 folder,
which held 27 clients' first DCOs, and the page fell from 85 clients to 65. It now merges the
newest two month folders, the newer one's CSM and name winning. Nothing dropped; 1782 and 1790
appeared with their first DCOs. Test: `tests/test_perf_clients.py`.

### 2026-10-02 — Performance page period follows the calendar

Summary: The RPE Client Performance page now shows the current month as its reporting period; each row still shows its own newest figures, tagged with their month.

The page's period was the newest ARS workbook in `Inputs/`, so on 2 October it still read
"Reporting period 2026.09" because no 2026.10 workbook had landed yet (only DCOs). Aaron chose the
calendar month. `refresh_performance_dashboard.calendar_period()` is now the default; `--period`
still overrides. Nothing goes blank: every section already takes each client's newest workbook,
sheet, sidecar and deck at or before the period and tags rows older than it, so until October's
inputs land the ARS rows read 2026.09 and the deck roster shows October as not built.
`derive_period` stays for anything that needs the newest workbook month. Test:
`tests/test_refresh_performance_dashboard.py`.

### 2026-09-29 — Two James views that broke on clients other than Marine

Summary: Two James review slides now handle clients with no respondent fees or only one measured mailing, so every sample client builds.

Building the Aaron & James mashups for 1549 Wellworth and 1800 First American (the new views had only
been built for 1539 Marine):

- **Revenue per Fee Dollar by Mailing** stopped both builds: neither workbook books a respondent
  fee against any mailing, so the ratio was empty and the caption crashed formatting it. The
  slide now states "the workbook books no respondent fees against any mailing" instead, never an
  empty chart. Test: `tests/test_james_views.py`.
- **Responders vs Non-Responders by Mailing** read "In 1 of 1 mailings … runs from X to X" for
  Wellworth, which has one mailing old enough to measure; the validator failed it ("1 mailings").
  One mailing now gets its own sentence with its one figure.

The four mashups (1539, 1038, 1549, 1800) all build at 0 FAIL.

### 2026-09-29 — Outputs/Test Builds is for test decks, and never counts as a delivered deck

Summary: Test decks, such as the Aaron & James mashups, go in Outputs/Test Builds. Sheila, the delivery dashboard and month archiving ignore that folder, so a test deck never shows as a client's delivered deck.

Aaron: "i added a folder for test builds. Push the Aaron & James mashup tests here."

Every reader of `Outputs/` treats each subfolder as a CSM's (`rpe_env.output_decks`). A test deck
is named like a real one (`1539-2026.09-ARS-...`), so in a folder of its own it would have read
as Marine's delivered September deck: "In Outputs" in Sheila, Built on the dashboard, and a
candidate for `promote_month`'s archiving. `rpe_env.TEST_BUILDS_DIRNAME` ("Test Builds") joins
`_OUTPUT_SKIP_DIRS` with the archive folders. Test: `tests/test_outputs_by_csm.py`.

### 2026-09-29 — "fewer than 1 swipe a month", not "1 swipes"

Summary: The Where the Balances Sit caption now reads "fewer than 1 swipe a month" instead of "1 swipes".

Found checking the rebuilt 1539 sample. The caption wrote its threshold with a fixed "swipes";
`combined_insight_slides.per_month` now makes the noun follow the number. Test:
`tests/test_balance_view.py`.

### 2026-09-28 — Data Issues: mark an item complete until a new workbook arrives

Summary: On Sheila's Data Issues tab each item can be marked complete. It stays complete until a new workbook arrives for that client, then comes back to be checked again.

Aaron: "on the Data Issues tab, I'd like to option to mark those items complete. They should stay
marked complete until we see a new workbook for that client, and then the status can be evaluated."

- Every item (issue-page issue, unmapped codes, Lift Matrix flag) has **Mark complete**. A mark
  records who, when, and the client's newest workbook in each of `Inputs/ARS Workbooks`,
  `Inputs/MRPC Analyses` and `Inputs/ICS Workbooks` at that moment.
- A marked item is left out of the list and the counts, and shown under a **Completed** chip with
  Undo. While the client's newest workbooks are unchanged it stays complete; when any is replaced
  by a newer file it comes back with "Marked complete <when> by <who>; a new workbook has arrived
  since (<file>). Check it again." Marking it again records the new workbook.
- An item is identified by the client, its kind and its own wording, so an issue re-worded by the
  next issue-page run is a new item.
- Marks are kept in `Build Artifacts/issue_pages/done.json` on the share, so every CSM's copy of
  Sheila sees the same marks; the file is merged on write. Tests: `tests/test_sheila_issues.py`.

### 2026-09-25 — Two James-view charts: a clipped legend and a legend over the bars

Summary: On the Revenue Build by Mailing and Where the Balances Sit review slides, the legend no longer gets cut off or covers the bars, and the charts use the full width.

Aaron: "work on additional optimizations ... making the slides clearer and easier to read, making
the charts large and balanced with the text." A read of every slide of the maximized 1539 deck,
rendered through PowerPoint, found:

- **Revenue Build by Mailing** (`insight_charts.build_chart`): the legend sat outside the plot on
  the right, was clipped at the figure edge ("$203K over 13 mo" lost its end) and squeezed the
  plot to 73% of the width. It now sits inside the plot's empty upper-left corner, on a white
  ground, at 12.5 pt, with labels shortened to "Jul 2025 · $203K, 13 mo"; the plot takes the full
  width.
- **Where the Balances Sit** (`insight_charts.balance_chart`): the legend sat on top of the
  bars. It now sits above the plot, in one row, at 12.5 pt.

Found and NOT changed in this pass, for a decision: the standard Responder Activity: Before vs
After (Mean) slide draws its two charts in about 60% of the slide width under a wide empty band
(its picture box comes from the ARS template, so the fix is a template and layout-baseline
change), and Overdraft Limits by Reg E Election and Where Reg E Opt-In Lags draw small panels
with much white space.

### 2026-09-25 — The 2 : 1 guarantee slide is back on every deck under 3 : 1; Sheila's change log shows summaries

Summary: Clients below 3 : 1 get the Revenue Guarantee slide in every ARS deck again, and Sheila's change log now shows a short summary of each update.

Aaron: "I do still want the two-to-one guarantee slide included for clients less than three-to-one,
period. Also, rewrite the change log shown in Sheila to show a summary of what was updated, not my
verbatim instructions."

- **Revenue Guarantee.** The merge earlier today had put the slide behind `RPE_JAMES_SLIDES` with
  the James views. It is not one of them: `build_ars_gen` builds it whenever
  `revenue_guarantee_slide.should_build` finds the client's ratio below 3 : 1, and skips it (and
  says so in the build log) at or above. The golden deck is unchanged (its synthetic client is
  above 3 : 1). A test pins that nothing gates it on the James switch.
- **Change log in Sheila.** Every entry now starts with a `Summary:` line in plain language, and
  Sheila shows that line: in the header's What's new and at the head of each entry on its change
  log page. Sheila's page also leaves out the quoted request paragraph and the inline attributions
  ("(Aaron, …)"), which stay in CHANGELOG.md as the record. An older entry without a Summary line
  shows its first paragraph that is not a quote. Entries from 2026-09-21 on were given summaries.

### 2026-09-25 — Faster: Sheila's status checks, and the monthly build three clients at a time

Summary: Sheila's client status checks are about twice as fast (a workbook is read once and remembered), and the monthly batch build now builds three clients at a time.

Aaron: "continue to find ways to optimize Sheila and the entire RPE build process." A profiling pass
(1705 CoastLife and 1156 BancFirst, the largest extract, 251 MB) found a client build is mostly CPU
in about twelve child processes that each read the ODD again, not share I/O (metrics_gen: 118 s
from a local copy of 1156's extract against 126 s from the share), and that Sheila opened each
workbook twice through two readers. Two changes now; the in-build ones wait for the James-slides
merge, which touches the same files.

- **Sheila reads a workbook once for both the Lift Matrix date check and the lift views.**
  `lift_values.read_workbook` now also returns the `lift_window` reading, and inside Sheila
  `ars_launcher._window` answers from the stored read (`workbooks.json`, keyed by size and modified
  time), installed with the share caches. `ars_launcher.py build` runs as its own process and never
  sees it, so a build's checks still open the file. The lift folder on the share is made once rather
  than on every call (39 times per overview), and `deck_status._mtime` / `_same_file` join the
  60-second share cache. Measured on 1705, 1539, 1204 and 1453: a cold status check 3.8-6.5 s ->
  2.2-3.4 s, a repeat 1.7-2.6 s -> 0.7-0.9 s; the lift overview 5.5 s -> 4.5 s. `WORKBOOK_VERSION`
  is 2, so every stored read was redone once (64 s, the first time only).
- **`build_month.py --jobs N` builds N clients at once (default 3).** Clients share nothing: each
  has its own folder and log, and `sweep_temp` only removes scratch older than six hours. Three, not
  the machine's 22 cores, because every build reads its extract from the share at about 3 MB/s.
  Progress prints as each finishes; `_results.json` keeps roster order. `--jobs 1` is the old
  one-at-a-time run.

### 2026-09-25 — Sheila: a Data Issues tab, and each client's code sheet one click away

Summary: New Data Issues tab listing each client's known data problems and their fixes, and an "Open code sheet" link on every client page.

Aaron: "build a new tab into Sheila with the data issues identified for each client" and "create a
link on the individual client pages that links to the code sheet saved in the inputs folder."

- **Data Issues tab.** One card per client, filtered by the CSM picker and the search box, with
  All / Blockers / Decisions / Gaps / Warnings / Codes and Lift Matrix chips. It finds nothing
  itself; it shows what two existing checks wrote, each with its own date, because they refresh on
  different days:
  - the issue pages' list (`Build Artifacts/issue_pages/gaps.json`: severity, program, issue, fix),
    as of the last `build_issue_pages.py` run (2026-09-21 today);
  - the morning dashboard's checks (`perf_dashboard/dataset.json` `actions`, from `perf_actions`):
    codes the client's code tables do not map, Lift Matrix filename flags, and what could not be
    checked.
  It re-reads either file only when it changes.
- **Code sheet link.** The Decks and Lift Matrix client pages, and every Data Issues card, carry
  "Open code sheet" (opens the client's newest sheet in `Inputs/Code Sheets` in Excel) and "Show it
  in File Explorer", plus a link to the client's data issues. A browser page cannot open a local
  file itself, so Sheila opens it, as it already shows decks in File Explorer. The file is found by
  client number on the server, never from a path the page sends; the newest is chosen by the data
  team's stamp in the name, and Excel lock files are skipped. The folder listing is kept until the
  folder changes.

### 2026-09-25 — Eighteen more of James's views, and the gap branch merged (opt-in; merged to main 2026-09-25)

Summary: 29 of James Gilmore's views are now available in the ARS deck (18 of them new), switched on only for review builds while we choose which to keep.

Aaron: "work on incorporating more of James's slides. We'll need to add in as many as possible
and then we'll edit down from the maximized copy."

`feature/james-deck-gaps` (through 8320b88) is merged onto main. The swipe-tier floor was
already on main (276d115), so main's `metrics_gen` is kept. **The Revenue Guarantee slide was made
opt-in with the James views too** (reversed the same day: see the entry above): the branch built it on every ARS deck under 3 : 1, which would
have changed the default monthly build before Aaron signed it off. Remove the `RPE_JAMES_SLIDES`
test in `build_ars_gen` to put it back on every deck.

Eighteen new REVIEW slides under `RPE_JAMES_SLIDES=1`, taken from the gap list in the "James vs
Aaron Decks" comparison and James's slide catalogue (`ars/deck/headlines.py`). They are in
`james_views.py` (figures), `james_view_charts.py` and `james_view_slides.py`:

| Slide | James's view | Source |
| --- | --- | --- |
| Revenue per Fee Dollar by Mailing | pnl | Workbook rollup: income, respondent fees and responders per mailing |
| Offer Segments per 1,000 Mailed | segments / segment_traj | ODD Mail/Resp codes; interchange at the workbook rate |
| Response by Offer Number | ladder_waves | ODD: first-time vs repeat met goals, rate by offer number, rung climbed |
| Responders vs Non-Responders by Mailing | per_mailer | ODD, before_after windows per mailing |
| What a Response Is Worth | responder_value / revenue_frames | Pooled difference x workbook Interchange Rate, beside booked revenue |
| Tier Movement by Response | tier_movement | ODD, a year apart, by response group |
| First Swipes: Program and Organic | activation_split | ODD first swipes, new vs mailed-first vs on their own |
| Where Card Spend Goes | card merchants | The ODD zip's monthly transaction file, SIG/PIN by MCC group |
| How the Money Moves | book and flow | Same file, every rail (1539's carries ACH and check) |
| Where Cards Lag | leaks / no_card | ODD by branch; value at the workbook rates |
| What a Card and an Opt-In Earn | value | ODD x workbook Interchange Rate and NSF Fee, 100% collection |
| Value by Account Age | value_ladder | Same, by tenure |
| Accounts Under Stress | concurrent_stressors | ODD: fading card spend, NSF/OD, balance drawdown |
| Branch Value per Account | branch_value / divergence | Same rates, by branch |
| Reg E Elections Over Time | Reg E 24-month trend, opt-in flips | Every month's Reg E Desc (now projected by `read_odd`) |
| Program Cascade | cascade | ODD counts, workbook booked revenue beside them |
| Where Accounts Close | attrition_branch | ODD, 12-month closure by product and branch (150+ floor) |
| Card Spend Before a Close | months_of_warning | ODD, closers vs open card holders in the same months |

Money is priced only at the workbook's own Interchange Rate and NSF Fee
(`lift_values.workbook_assumptions`); a client without them gets the slide saying so. Activity
windows read `month_complete` (1539's Aug 2026 NSF/OD month is left out and stated). A closer is a
card user by spend, not by the snapshot's Debit? flag: only 44 of 1539's year of closers still
carried the flag against 2,019 that swiped in the year before closing.

**Not built, and why:** the guarantee deferral tracker, outside-product / competitor / flight-risk
views and their lists (James's dictionaries and competitor config are not on the share), the
deposits chapter (`Inputs\Deposits` empty), interchange scenarios by rail (no per-rail rate), ICS
behaviour vs non-ICS (no ICS account list matched to the ODD), the penalty box (the suppression rule
is in no file this pipeline reads), PFI tiers (no definition to follow), account-level lists
(privacy; not deck content). Cumulative reach and repeat-responder depth were not rebuilt: the
appendix's Program Reach and Depth of Engagement slides already carry them.

Sample: `Build Artifacts\james_max_2026.09\1539\`, 84 slides, 0 FAIL / 43 REVIEW. Default builds
are unchanged: the golden deck still has 49 slides.

### 2026-09-25 — The Lift Matrix distribution counts NH

Summary: In the calculated Lift Matrix, NH accounts (eligible, no debit card) now count in the distribution, so the eight segment shares add to 100%.

Aaron: "recalculate the distribution including NH accounts."

The distribution was each segment's share of the card holders, with NH at 0% as in the workbook's
file. It is now each segment's share of every ARS-eligible account, NH (eligible, no debit card)
included, so the eight shares add to 100%, and NH's share goes into the file Bradford loads instead
of 0%. The DDA values and the matrix do not change; the seven card-holder segments' shares read
lower than the workbook's by NH's share. 1705: 13,534 eligible accounts, NH 13.4%, NU 16.0% -> 13.8%,
26 Plus 46.6% -> 40.4%. 1539: 37,629, NH 9.0%, NU 23.3% -> 21.2%, 26 Plus 39.0% -> 35.5%.
`SCAN_VERSION` is 5.

### 2026-09-25 — Sheila reads a workbook's Lift Matrix again only when the file has changed

Summary: The Lift Matrix tab opens in seconds instead of over a minute: a workbook is re-read only when the file has changed.

Aaron: "only rescan workbook lift matrix values if the file has changed since the last scan, that
should speed things up."

The Lift Matrix tab reads every ARS client's newest workbook (0.4-2 s each over the share). Sheila
kept those reads only while it ran, so each start, and each CSM's own copy, read all of them again.
Each read is now stored in `Build Artifacts/lift_values/workbooks.json` against the file's size and
modified time, and a workbook is read again only when either changes, or when the reader itself
changes (`lift_values.WORKBOOK_VERSION`). The file is on the share, so one CSM's reads serve every
copy of Sheila. Measured on 2026-09-25 across 49 ARS clients: 75.7 s for the overview with nothing
stored, 9.4 s from a fresh start with the reads stored. What remains is listing each client's files
on the share, not reading workbooks.

### 2026-09-25 — Lift Matrix: business accounts, an independent NH, 100% collection, the outlier cap as a variable, Recalculate, Export

Summary: The Lift Matrix now values business accounts too, gives NH its own value, defaults OD collection to 100%, lets you choose the outlier cap, and has Recalculate and Export this matrix buttons.

Six changes from Aaron the same afternoon, all in `lift_values` and Sheila's Lift Matrix tab.

- **Business accounts are valued; eligibility is the only account filter** ("change the calculate
  to include business accounts, but base the calculation only on ARS eligible accounts"). It was
  consumer only. The debit card is still required for the seven swipe segments, on purpose: counting
  eligible accounts with no card (1,809 on 1705, 3,370 on 1539) put them all in NU, which then read
  27% / 30% against the workbooks' 15% / 23%. Adding the eligible business card holders (135 and 921)
  keeps every segment within about a point of the workbook's distribution. Sheila shows the
  consumer / business split.
- **NH has its own value** ("with the ODD we should be able to calculate an independent NH value").
  NH is the eligible accounts with no debit card, valued on their own spend and NSF/OD items under the
  same cap, at 0% distribution as in Bradford's file. It carried NU's value before; workbooks already
  differ (1204: NH $0.84, NU $1.55). A client with no card-less eligible account falls back to NU's
  value and the page says so.
- **Collection defaults to 100%** ("default the collection rate to 100%"). It was 80%.
- **The outlier cap is a variable** ("Add the 99% percentile option as a variable at the top"):
  `WINSOR_PCT` (0.99) at the top of `lift_values`, and an Outlier cap field beside the three rates:
  95th, 97.5th, 98th, 99th, 99.5th percentile or no cap. The scan values every segment at each option,
  so choosing one never re-reads the ODD and no account-level figure is stored. `build_lift_matrix`
  takes `--winsor`.
- **Recalculate** ("we need an option to recalculate when the variables are changed too"). The page
  recalculated on every keystroke. Now a change greys the figures out, says they are for the previous
  values and holds Export until Recalculate (or Enter), so a matrix is never exported at values other
  than the ones shown.
- **Export this matrix replaces Approve** ("Instead of Approve this matrix, use Export this matrix").
  One click records the export in `Build Artifacts/lift_values/<id>-<period>-exported.json` and
  downloads the Excel file; the page then shows when it was exported, with Download again. The server
  still serves the file only for exactly what was recorded. An `-approved.json` written by the
  previous release (1526 has one) is not read as an export; export it again.

Measured at the new defaults (workbook rates, 100% collection, 99th percentile), new vs the current
workbook matrix. 1705: NH $0.52 ($1.92), NU $1.29 ($1.92), 1-5 $6.66 ($7.14), 6-10 $14.76 ($14.44),
11-15 $13.35 ($15.41), 16-20 $19.43 ($16.83), 21-25 $21.95 ($24.02), 26 Plus $28.89 ($28.34). 1539:
NH $2.38 ($0.92), NU $0.73 ($0.92), 1-5 $5.03 ($4.95), 6-10 $12.28 ($11.86), 11-15 $18.37 ($17.21),
16-20 $23.38 ($21.59), 21-25 $26.44 ($24.63), 26 Plus $31.21 ($28.66). 1539's NH sits above its NU:
its eligible card-less accounts carry more NSF/OD items than its card holders who do not swipe.
`SCAN_VERSION` is 4, so every stored ODD scan is read again.

### 2026-09-25 — build_lift_matrix is a wrapper over lift_values; lift_extract retired

Summary: The command-line Lift Matrix tool now uses the same calculation as Sheila, so both give the same file.

Aaron: "retire build_lift_matrix.py and have it use lift_values."

`build_lift_matrix.py` carried its own valuation: a `.pkl` from `lift_extract.py`, every
card-holding eligible account with business included, 12 months with no completeness check, an
optional book-wide trim and 100% collection by default. Next to Sheila's `lift_values` that was two
valuations of one matrix. It is now a command-line wrapper over `lift_values`:

    python build/ars_pipeline/build_lift_matrix.py <ODDD.zip> <id> "<client>" <yyyy.mm> <out dir|.xlsx>
        [--workbook <ARS workbook>] [--ic-rate] [--nsf-fee] [--collection]

The rates default as in Sheila, and with no NSF/OD fee from any source it stops and asks for
`--nsf-fee`. On 1705 it writes the same values Sheila shows, to the cent. A hand run has no approval
step, so check the values it prints against the current matrix before sending.

`lift_extract.py` is deleted. Its ODD reader (`open_source`, `find_header`) moved into
`lift_values`, the only thing still using it. `tests/test_nsf_is_items.py` now pins the
"MTD is items, priced once" contract on `lift_values`.

### 2026-09-25 — Lift Matrix: current and new side by side, approve, then download

Summary: A client's Lift Matrix page shows the current and new matrices side by side with the change and the step between segments, and the Excel file for Bradford is downloaded from the page.

Aaron: "When the lift matrix is calculated, I want it shown side by side with the previous matrix,
and the value difference between segments shown, and also show the current and new lift grids.
When the matrix is approved it'll allow you to download the file with the lift matrix values."

- The client page shows each segment's distribution and DDA value, current and new, the change, and
  the **step from the segment before** in both. Below it, the **current and new lift grids** side by
  side. The current grid is read from the workbook's Lift Matrix MM block as written, not re-derived.
  New cells are coloured against the current ones.
- **Approve this matrix** records the rates, the ODD landing and the values in
  `Build Artifacts/lift_values/<id>-<period>-approved.json`. Only then does **Download the Excel
  file** appear, and the server serves it only for exactly the approved rates from the ODD now in
  Inputs. Change a rate after approving and it has to be approved again.
- The file is **downloaded, no longer written to `Outputs/`**, which holds finished decks only.
  Its layout matches the CoastLife example cell for cell (text, number formats, bold, merges), now
  including the accounting format on the empty half of the lift triangle.
- Negative lift between segments is allowed (Aaron), so the page no longer warns about it.

### 2026-09-25 — Sheila builds a client's Lift Matrix

Summary: New Lift Matrix tab: every client's current matrix, a new one calculated from the client's ODD with editable interchange rate, NSF/OD fee and collection rate, and the file for Bradford in his format.

Aaron: "add functionality to Sheila to build client Lift Matrix for ARS", and "create a tab in
Sheila showing the lift matrices across clients, and the current calculated lift matrix. To have
the lift matrix implemented we email them to Bradford in this format (but use our standard naming
convention)."

Sheila has a **Lift Matrix** tab next to Decks. It lists every ARS client's current matrix (the
Revenue Segmentation DDA values its newest workbook carries, with the window and an Expired tag)
and, once the client's ODD has been read, the matrix calculated from it. A client's page shows the
calculated segmentation beside the current one, the lift triangle, and three editable rates, and
**Save the Lift Matrix** writes `<id>-<yyyy.mm>-ARS-<Client> ARS Lift Matrix.xlsx` to the client's
`Outputs/<CSM>/` folder in the layout of the file Bradford loads (CoastLife CU Lift Matrix
Values.xlsx). What it was made from goes to `Build Artifacts/lift_values/<id>-<period>-saved.json`.
SM clients are listed as "SM model: no Lift Matrix" and are never read or saved (Aaron: "Austin and
Sugar River are on the SM model that doesn't use the lift matrix"); their workbooks carry an empty
template Lift Matrix MM tab, which now reads as no matrix rather than a current one.

The valuation is `build/ars_pipeline/lift_values.py`, one definition:

- **Consumer accounts only** — `Business? = No`, debit card, ARS eligible. Business accounts are
  neither valued nor counted in the distribution.
- **Segment** on mean swipes per month over the last 12 **complete** months, rounded down into the
  band (the deck's rule, 2026-09-22).
- **Outliers**: each account's spend and NSF/OD items are capped at the **99th percentile of its
  own segment**. The 95th was tried and rejected: NSF/OD items sit on few accounts, and on 1539 and
  1705 it took 26-48% off each segment's items where the 99th takes 2-13% (spend 1-4%). 26 Plus is
  valued on its 26-30 swipe accounts, as `build_lift_matrix` already did.
- **Rates**, each editable and each shown with its source: IC rate = the workbook's Interchange
  Rate (Actuals MM, newest month), else 60 BP; NSF/OD fee = the **most common per-item fee** in the
  ODD's `Fees1` column when the extract carries it (Aaron: "For clients with tiered or multiple OD
  rates, we need to use the most common value"), else the workbook's NSF Fee × the monthly OD item
  counts, else nothing — Sheila asks rather than guess; OD collection rate = 80%.

None of the 83 extracts in `Inputs/ODDD/` on 2026-09-25 carries a `Fees1` column (nor does any
transaction file), so every client is valued from the workbook's NSF Fee today. The reader takes
either a dated `<Mon> Fees1` per month or one undated `Fees1`.

The calculated matrix is NOT smoothed. A segment valued below the one before it (CoastLife 11-15 at
$11.57 under 6-10 at $12.55: fewer NSF/OD items per account) puts a negative lift in the file, and
that is allowed (Aaron: "Negative lift between segments is allowed"). Live workbook matrices carry
the same thing (Foothills 16-20 under 11-15, FNB Alaska 26 Plus under 21-25).

### 2026-09-25 — The source watch fires once a morning

Summary: The morning source check now runs once at 08:00 instead of hourly until noon. If the VPN is down at 08:00, run it by hand once it is up.

Aaron: "let's run this source watch just once per day in the morning."

"RPE Source Watch" fired at 08:00 and then hourly for four hours — five fires a morning, with
`--once-daily` making every fire after a successful one exit at once. It now fires once, at
08:00. `register_watch_task.ps1 -RetryHours` defaults to 0 instead of 4, so the checked-in
script and the registered task agree; `-RetryHours 4` puts the old window back.

The retries were not decoration, so what they covered is worth naming:

- **A fire Windows created suspended** (2026-09-09, -10, -11, -18, -19: zero CPU, no modules
  loaded, killed at the execution limit) is still covered — by the watchdog, which recognises
  that signature, kills the tree and restarts the task.
- **A morning off the VPN is not covered any more.** The run goes, finds the shares
  unreachable, reports it and finishes, so there is no stuck process for the watchdog to
  recover — it logs "needs a human look" and stops — and no later fire to go and look. That
  day gets no copy, and `Inputs/` stays where yesterday left it. Run the watch by hand once
  the VPN is up. This is the case that had just happened: on 2026-09-25 the 08:00, 09:00 and
  10:00 fires all found the shares down, and under the new schedule only the first would have
  gone.

The 50-minute execution limit is unchanged. It was sized to clear before the next hourly fire;
with no next fire it is kept because a run that has not finished in 50 minutes is stuck rather
than slow, and the watchdog wants the slot cleared.

### 2026-09-23 — The run record does not live on the share any more

Summary: The morning check now records that it ran even when the VPN is down, so an off-VPN morning is no longer mistaken for a stuck run.

Aaron: "fix the run record flaw."

`source_watch_runs.json` was kept in `Build Artifacts/` with the rest of the morning check's
bookkeeping — on the share. On 2026-09-22 and -23 the 08:00 runs found the VPN down, could not
write a byte anywhere, and left no trace that they had run at all. `run_health` then read
"never", and the watchdog went hunting for a suspended process that did not exist and logged
**"needs a human look"** twice, when the true answer was "off VPN, nothing to do".

A record of WHETHER SOMETHING RAN cannot be stored on the resource whose absence is the most
common reason it did not.

- The record is written to `%LOCALAPPDATA%\RPE\` (the home directory elsewhere; never a temp
  dir, which is swept), and mirrored to the share when the share answers, for the dashboard and
  for anyone reading from another machine.
- `read_runs()` takes the NEWER of the two: a machine off the VPN for a day holds the newer
  local record, a fresh checkout has only the shared one, and neither is authoritative alone.
- `save_report` no longer dies on a share it cannot write to. That was the other half of the
  same flaw: the unguarded write killed the run one line BEFORE the stamp that would have
  recorded it, so the morning that most needed recording was the one that recorded nothing.

The tests are sealed off from the machine's own record: an un-isolated test would read the
developer's real one and pass or fail on whether the morning task had run today.


### 2026-09-22 — Swipe averages round down into their segment

Summary: Accounts averaging between two swipe tiers (5.5 swipes, say) now land in the lower tier instead of 26+. This changed the swipe-tier figures on every 2026.09 ARS deck, which were rebuilt.

Aaron: "round swipes down into the nearest segment."

`metrics_gen.tier` bands an account on its THREE-MONTH MEAN swipe count, against inclusive
integer ranges (`1..5`, `6..10`, …). An average between two bands — 5.5, 10.4, 20.2 — matched
none of them and fell through to the `26+` catch-all at the end of the loop. On 1539 Marine
that is **1,381 of the 15,676 accounts in `26+`, 8.8% of the top tier**, averaging fewer than
26 swipes, with the middle tiers short by those same accounts. The Lift Matrix reads its
per-tier values off these buckets, so the effect is not confined to the tier table.

The mean is floored into its segment first. 5.5 swipes is a 5-swipe account, and the bands
stay the plain integer ranges they read as.

**This moves client-facing numbers** on the swipe-tier table, the ranking by tier and anything
read off them. Every 2026.09 ARS deck was rebuilt the same night.

### 2026-09-21/22 — Filling the gaps against James's deck (branch `feature/james-deck-gaps`)

Summary: Ten views from James Gilmore's deck built for review (revenue guarantee, revenue build by mailing, swipe tier migration and others), plus three fixes to earlier James views.

A night's work on the gap list from the "James vs Aaron Decks" comparison. Everything below is
on the branch and **opt-in**: `build_ars_gen` adds these slides only under `RPE_JAMES_SLIDES=1`,
so the monthly build is unchanged. They are REVIEW slides — each one's speaker notes carry the
source, the method and the open issues in full, deliberately blunt (Aaron: "you can be obvious
about issues").

**One defect found that moves client-facing numbers, and needs a decision.** The swipe-tier
bands in `metrics_gen` are inclusive integer ranges (`1..5`, `6..10`) tested against a
THREE-MONTH MEAN, so an account averaging 5.5 swipes matched no band and fell through to the
`26+` catch-all at the end of the loop. On 1539 Marine that is **1,381 of the 15,676 accounts
in `26+` — 8.8% of the top tier — averaging fewer than 26 swipes**, with the middle tiers short
by those same accounts. The Lift Matrix reads its per-tier values off these buckets. Fixed
by flooring the mean into its segment — the 2026-09-22 entry above, which reached main ahead of
the rest of this branch; `combined_insights.swipe_tier` re-implements the same rule and a test
pins that the two agree.

Three defects from the comparison's own issue list, fixed:

- **Revenue by Mailing's per-month line** ranked mailings with 1–5 booked months above mature
  ones — revenue per responder is highest in a mailing's first months, so the newest offer
  peaked the line while the caption beside it read "6 or more months booked". The line now plots
  mature mailings only.
- **Card Account Health** put two denominators on one slide: the tile read "card holders at
  risk" over bars whose shares were of every eligible account. Card states are now shares of
  card holders; "No card" says on the bar that it is a share of eligible accounts.
- **The ARS Scorecard's first-year closure row** was compared with the 12-month closure rate of
  all accounts — a different measure on a different population, so "behind" meant nothing. It is
  compared with the same measure at the median reporting branch, and left off below three
  reporting branches.

Nine new views, each with tests:

| View | What it answers | Source |
| --- | --- | --- |
| Revenue Guarantee | The 2:1 guarantee as figures: program cost, the guaranteed minimum, revenue, the surplus or the gap and the months to cover it | ARS workbook |
| Revenue Build by Mailing | How each mailing got to its total, by months since the drop | Workbook rollup |
| Where This Month's Revenue Came From | Which mailings the newest booked month's revenue came from | Workbook rollup |
| Revenue per 1,000 Offers | What a mailing earned for the offers it sent | Workbook + ODD |
| Where Take Rate Lags / Where Reg E Opt-In Lags | The book cut by tenure, age, balance and product, with the lagging pockets named | ODD |
| Swipe Tier Migration | Where card holders sat a year ago against where they sit now | ODD |
| PIN and Signature Mix | The routing mix by month and each rail's ticket | ODD |
| Overdraft Limits by Reg E Election | Limit coverage and NSF/OD items, by election | ODD |
| Responders vs Their Own Segment | The control comparison split by pre-mailing tier | ODD |
| Where the Balances Sit | Balance concentration, and the top-decile cards that barely swipe | ODD |

Supporting changes: `read_odd`'s column projection now keeps DOB, Avg Bal, the product columns,
MTD and OD Limit (without MTD and OD Limit the overdraft view read 0.0 for every account — a
slide of zeros that reads as a client with no overdrafts rather than a reader with no columns);
`odd_rows` gained `routing()` and `od_limit()` accessors; the golden deck is 50 slides.

**Deliberately not built:** anything needing files that are not on the share — the deferred
expense tracker behind James's monthly guarantee table, the transaction-file views (dictionary
and competitor config absent), the deposits chapter (`Inputs\Deposits` empty), and his
interchange scenarios (no rate table). The Reg E what-if is stated in accounts only for the same
reason: the ODD carries overdraft ITEMS but no fee dollars, so a money figure there would be
invented.


### 2026-09-21 — The CashPlease marketing emails are their own input kind

Summary: Bradford's CashPlease marketing emails (monthly CSVs and per-client workbooks) are now collected automatically into Inputs/CashPlease Marketing.

Aaron: "add a kind for the loan marketing emails." Eight `<id>_<Client>_Loan_Marketing_Emails.xlsx`
attachments from Bradford's "CashPlease Marketing eMails" thread were reported by the morning mail
step and left in the mailbox, one per client, because their names carry no period and so read as
"does not match the `<id>-<period>-<kind>` convention".

That thread carries TWO families, and the reported eight were the smaller one. The monthly data is
`<id>_<Client>_<MM.YYYY>_Loan_Marketing_Emails.csv`, 0.3 to 30 MB per client per month, and the mail
step could not see those at all: it takes only `.xlsx`/`.xlsm` attachments.

Both now classify as kind `CP marketing` (`mail_sources.CP_MARKETING`) and file to
`Inputs/CashPlease Marketing/`; only Bradford may send them, as with his other kinds. A `.csv` is
accepted only when it is one of these (`CSV_KINDS`) — every other CSV these senders attach is not an
input. `cp_marketing_parts` is the one reading of both names, and reads `09.2026` as period
`2026.09`. Inputs holds the newest month per client, as it does for every other input: 10 CSVs
(September for eight clients, August for 1131 and 1734, who had no September send) and the eight
workbooks, 46 MB in all.

The folder stays in `NOT_SCANNED_KINDS` — no reader globs it — so `watch_sources` prune reaches it
through `PRUNE_ALSO_KINDS` instead, and drops a superseded month the same way it drops an old DCO.
The undated workbook has no newer version and is never pruned.

Two smaller fixes in the same pass. `newest_only` could not order two files that carry no period or
stamp, so it kept whichever the scan reached first — Inbox or Archive, by luck; `_is_newer` breaks
that tie on when the message was SENT. And a failed save printed the bare word FAILED
(`outcome.split(":")[0]`), so the error was dropped and nothing recorded why — it now carries its
reason into the morning report.

No deck reads these files yet, so no slide changes. Tests: `tests/test_mail_sources.py`,
`tests/test_watch_sources.py`.

### 2026-09-21 — The watchdog asks the run record, and looks every half hour

Summary: The watchdog now checks every 30 minutes each morning whether the source check actually ran, and restarts it if Windows left it stuck.

Watched live: the 09:01 and 09:06 fires of the morning task were both created SUSPENDED (zero
CPU, zero handles, 1.8 MB — the interpreter never started), while the same command started by
hand ran fine. The watchdog would not have touched either: it judged by the report's age, and
the 08:00 run's report was 52 minutes old — perfectly fresh — so the morning's copy would simply
never have happened.

- `watch_sources --check-today` exits 0 when a run REACHED THE SHARES today, read from the run
  record the runs stamp themselves. `--check-stale` (26-hour view) is unchanged.
- The watchdog asks that instead of reading the report's mtime, and falls back to the report
  when a checkout has no such flag. Its messages say "no run has reached the shares today".
- It now fires every 30 minutes for 4 hours from 08:20 (`register_watchdog_task.ps1
  -RepeatHours`), so a fire created suspended at 09:00 is cleared within half an hour rather
  than waiting for tomorrow.

Tests: `--check-today` over the record (including "off VPN today does not count"), and that the
watchdog asks it and still carries the report fallback.

### 2026-09-21 — The morning check saves its scan before the copy, and gets two hours

Summary: The morning source check saves its findings before copying files and may run up to two hours, so a slow morning no longer leaves no record at all.

The 08:00 source check produced NOTHING on 2026-09-18, -19 and -20: no report, no log entry,
no inventory. Two faults, not one. Windows created the 09-18 and 09-19 runs SUSPENDED (the
watchdog found them at 0 CPU / 0 handles and killed them — the 09-18 one was still sitting
there 24 hours later); the runs that did execute outran the task's 30-minute execution limit
on a slow share, and because the report was written only AFTER the copy, prune, referrals and
branch-name steps, a kill part way left no trace at all — indistinguishable from never having
started.

- `watch_sources.save_report` now writes the report, the log block and the inventory as soon
  as the SCAN is done, before the copy. The steps append to the log when they finish and the
  report is rewritten whole. Tests: a run killed mid-copy still leaves its report and
  inventory; the finished report carries one header, not two.
- The task's execution limit goes from 30 minutes to 2 hours (`register_watch_task.ps1`); today's
  run took 14 minutes, and a weekend's copy is slower.
- The watchdog moves from 08:15 to 08:45 (`register_watchdog_task.ps1`) and treats a report up
  to 2 hours old as fresh, so it judges a run that has had time to write its scan rather than
  one still in the copy.

Both tasks re-registered on this machine 2026-09-21.

### 2026-09-17 — A branch named Marshall is not March (correction)

`periods.parse_month` accepted any 3-9 letter word with a year and checked only its first three
letters, so "Marshall" read as March. With branch names now on the charts, Leading Edge CU's label
"Marshall\n74" parsed as Mar'74 and the month-axis guard stopped the build (`charts_gen`,
2026-09-17). A word must now be a month name (abbreviation, full name, or "Sept"). Nothing that
parsed as a real month before parses differently. Test: `tests/test_periods.py`.

### 2026-09-17 — CSM Sheila answers from memory and refreshes behind the page

Aaron: "work on ways to make Sheila's GUI refresh faster." The data root is a network share where every stat,
listing and open is a round trip, and the client list and a client's checks asked it the same questions over
and over: the list ran a `mkdir` on `Build Artifacts` and read a launcher result once per client (50 mkdirs,
2.3 s, for a folder that already existed), and one client's checks made 286 share calls, 157 of them an
`isfile` per file landed on the client reports share. Nothing changes what the page reports, or what a build
checks: `ars_launcher.py build` runs as its own process and reads everything fresh, as before.

- **The client list is served from memory.** Only the first request waits. After that the stored list comes
  back at once with its age ("List as of …", and a Refresh link), and it is rebuilt in the background when it
  is older than 60 s, when Refresh is clicked, or when a build finishes. Builds this server ran — Building,
  Queued, Error and the deck a finished build put in Outputs — and the Lift Matrix tags are laid over the
  stored list on every request, so they never wait for the rebuild. The page shows the last list it had
  (sessionStorage, labelled "Saved list … Updating…") while it loads. A rebuild that fails, or that suddenly
  finds no ARS workbooks at all, keeps the previous list and says the update failed.
- **A status older than ten minutes is shown at once, marked "checking again", with its Build buttons held**
  until the fresh check replaces it, so an old "ready" cannot be built from while a STOP may be on its way.
  "Check again" is still a full fresh read. A client whose list row changes (a deck in Outputs, a send
  recorded, a last build) has its stored status dropped; a check that started before a build finished is
  not stored.
- **Share answers repeated within a check are kept for 60 s, in the web server only**: reachability of the
  shares and the CSM ODD folders, the report folders in Inputs, the VIP manifest, the cycle period and the
  CSM List row. "Check again" reads past them.
- **Fewer round trips everywhere:** `rpe_env.build_artifacts` makes its folder once per process;
  `output_decks`, `report_dirs` and `deck_status._source_reports` read each folder with one listing instead
  of a stat per entry; launcher results are read only for clients with a launcher folder, several at once,
  and re-read only when the file changed. The server's warm-up checks four clients at a time.

Measured on Aaron's machine, same session, share calls counted in every thread (wall times swung 10x between
runs on the share today, so the call counts are the steadier figure):

| | Before | After |
| --- | --- | --- |
| Client list, first request | 267 calls; 34-91 s | 45 calls; 1.1-50 s (once per server start) |
| Client list, every later request | 267 calls; 8-160 s | 0 calls; 0.00 s (4-6 ms over HTTP); rebuilt behind the page with 23-24 calls |
| A client's status, first view | 286 calls; 6-45 s | 82-88 calls; 2-30 s (usually already done by the warm-up) |
| A client's status, later views | 0 calls within 10 min, then 286 calls while the page waits | 0 calls (13 ms over HTTP); past 10 min shown in 66 ms while 53-88 calls re-check it behind the page |
| "Check again" | 286 calls; 2-24 s | 97 calls; 2.6-30 s |

### 2026-09-17 — Take rate and Reg E slides: full-width branch charts; branch names on every branch chart

Aaron approved both on the test branch, then: "Yes, add to main" and "Main decks use names (numbers
where no name is known), wrapped to fit ... Long names will need to be shortened to fit the slide
axis labels."

**Layout** (`build/slide_geometry.py`, the one geometry contract). 12-Month Eligible Take Rate
(Personal, Business): the selection sentence moves from the slide face to the notes, the tiles are
1.05" tall instead of 1.45", and the branch chart runs the full width (12.3 x 3.70). Reg E Opt-In —
All Personal / Opened in Last 12 Months: donut, legend and sentence share one band across the top
and the branch chart runs full width beneath (12.3 x 3.10); selection sentence to the notes. The
charts render at those boxes' aspect (`charts_gen` DIM image11/14/16, the business chart via
`slide_geometry.CHART_DIMS`). STYLE.md's "selection on the slide" gives way on these four slides
at Aaron's direction; the selection is still on record in the notes.

**Branch names** (`metrics_gen`). Every branch series is relabelled from
`Inputs/Branch Names/branch_names.csv` when most of the deck's branch ids have a name; a branch with
no name keeps its number, and the monthly take-rate table keeps branch-number order. Names are
shortened once (`chart_lib.short_branch_name`), so charts, tables and captions agree, and the axis
labels wrap to two lines and size to the bar slot, with an ellipsis as the last resort
(`chart_lib.branch_tick_labels`). With names on the charts, the Branch Reference appendix slide is
no longer added.
The 12-Month Take Rate by Branch table widens its Branch column to the longest name, measured in the
bundled font. **New gate check** `validate_deck.table_label_fit_findings`: a table whose first-column
label wraps and pushes the table past the slide FAILs. It is the defect the first names build shipped
without failing: Great Lakes' "Member Contact Center" wrapped to three lines and the table ran to
about 8.6". Placeholder names from a source ("N/A", "NULL", "NONE") are never used. The geometry
contract parks the selection line at the foot of these slides and `slide_geometry.selection_to_notes`,
called by the builder, moves it to the notes, so the template shell still satisfies the contract.
Tests: `tests/test_table_label_fit.py`.

### 2026-09-17 — Transaction files stored zipped

Aaron: "Zip all the txn files so they read faster." `Inputs/Txn Files/<id>/` held 405 raw
transaction files, about 48 GB, read over the share. Each is now `<original name>.zip` beside
where it was, one file per zip with its original timestamp (`scripts/zip_txn_files.py`). A zip
replaces its original only after its size and CRC match the original and it decompresses cleanly.
402 of the 406 files are stored zipped, 48.2 GB down to 11.6 GB (24%); a full read of one took
4.2s instead of 7.4s.

**Four files could not be stored zipped and are still raw** (1200's 2025.02.07 and 2026.06.01
monthlytran, 1745's 2025.10.03 and 2026.03.02 transaction). Every byte of those archives reaches
the file handle and `fsync` returns, and the file is 0 bytes the moment it is closed on the share.
A zip built locally and copied over is emptied the same way, whatever its extension, and so are
bzip2 and lzma archives of the same rows, so it is the content being rejected by a security agent
on this machine or the share — nothing in this code, and nothing a retry fixes. The originals are
kept, the script reports each one, and `open_txn` reads them as they are.

No deck reads these files, and no slide or figure changes. The only scripts that open them are in
`z-legacy - do not use`, and they were left alone. Any new reader goes through
`rpe_env.txn_files()` / `rpe_env.open_txn()`, which read the zipped or the raw form, and an old
raw path still opens its zip. `Txn Files` is a new input kind, `Txn`, in `NOT_SCANNED_KINDS`, so
neither `report_dirs()` nor the watcher's copier and pruner looks inside it. Test:
`tests/test_txn_files.py`.

### 2026-09-17 — The business take-rate chart renders in Carlito on every deck

`build_ars_gen` set the chart face only on the Monthly Summary path, so on every MM deck the
"12-Month Eligible Take Rate — Business" chart (drawn by `chart_lib.branch_chart` from the builder,
not from `charts_gen`) fell back to matplotlib's DejaVu Sans. `branch_chart` now sets Carlito
itself through `rpe_env.use_font`, which raises rather than substitute.

### 2026-09-17 — Reg E "Anything else" reads as opted out (correction)

**A client-facing number moves.** Aaron: "Reg E Anything Else assigned to Opt-Out, Accepted = Opt-In,
Declined = Opt-Out." `odd_rows.rege_label` counted 1217 Pioneer FCU's "Anything else" as not
applicable, which left those card holders out of the opt-in rate's base; they now count as opted
out, so Pioneer's opt-in rate falls. "Accepted" and "Declined" were already read that way by
pattern; they are now exact entries. Test: `tests/test_rege_label.py`.

### 2026-09-17 — No trend line over a partial month; white space under the CashPlease Overview tiles

Aaron: "don't draw trend lines over partial months." The CashPlease Loan Volume by Month chart
hatched the part-month bar but ran the principal-advanced line into it, so September 1-11 read as a
drop from $9K to about $4K. The line now stops at the last complete month; the partial month keeps
its hatched bar and count (`cp_charts.monthly_volume_chart`). The ICS section-intro motif's
cumulative line stops the same way when the referral trend's last month is partial. The ARS, MRPC
and dashboard series already end on the last complete month (`build/month_complete.py`). Test:
`tests/test_partial_month_lines.py`.

Aaron: "add whitespace below the navy callout boxes by moving everything down 1/4"." On the
CashPlease Program Overview slide the chart label, cumulative chart, commentary box and cohort note
all sit 0.25" lower (`build_cp_gen.py`, `OV_DROP`).

### 2026-09-17 — CashPlease settings for 68 clients; prepaid finance no longer reads "N/A%"; September pill fits

Settings records: `Inputs/Product Settings/` went from one file (1632) to 68, exported from an
all-clients pull of the Business Utilities CashPlease records (`C:\Data Pipelines\Product
Settings\Inputs\CashPlease`, Aaron: "copy it to Sheila's inputs folder"). Test accounts and the 18
clients with no loan settings recorded get no file, so they keep getting no settings slide.

Three rendering defects that the wider data exposed on the first 2026.09 modules (Aaron: "build
the CashPlease modules for my clients"), all in `build_cp_gen.py`:
- **Prepaid finance charge** appended "%" to anything not ending in one, so slides read "N/A%
  (standard & MLA)" (1750, 1771), "6% / $25 max%" (1131), "6% up to $25 MAX%" (1770) and "$20%
  standard · $0% MLA" (1564). `_as_pct` now signs a bare number only, and the new `_as_charge`
  shows N/A/0 as "None" (a lone "None" drops the "(standard & MLA)" tail).
- **Four differing loan types** were lower-cased ("22% easy std · 23% manual mla"); they now keep
  "Easy Std / Manual MLA".
- **The content-slide date pill** is 2.70" wide (was the 2.35" `shapes.pill` default): "PTD ·
  September 13, 2026" is 2.16" of Montserrat 12pt in 2.15" usable and wrapped onto two lines on
  every content slide. It grows leftward into the gap after the title.
Tests: `test_cp_settings_slide.py` pins all three. Rebuilt 1131, 1564, 1750, 1770, 1771 — 0 FAIL,
0 REVIEW. Re-assembled the combined decks 1539 (ARS-ICS-MRPC-CP, 72 -> 73 slides), 1632 and 1734
(ICS-CP, 1734 19 -> 20) from the same ARS/ICS/MRPC decks they shipped with and a fresh CP section
(`Build Artifacts/cp_settings_2026.09/`): the only validator differences are the four CP pill
wraps gone; qa_all GATE PASS.

### 2026-09-17 — Comparisons use complete months only

Aaron: "Don't calculate YoY or comparisons on partial months, only use complete months." Marine FCU
1539's 2026.09 NSF/OD Activity slide said "-98% Items YoY (Aug 25 → Aug 26)". Its ODD extract was pulled
09/04/26 and carried whole August swipes and spend (1,104,224 swipes against 1,103,258 in July), but only
390 NSF/OD items on 290 accounts for August against 19,451 on 4,480 in July. The YoY, both NSF/OD tiles and
the chart's last bar all read that half-loaded month as a collapse.

**One definition, `build/month_complete.py`.** A month is incomplete for a measure when the data was
pulled before it ended (the ODD member's `(MMDDYY_HHMMSS)` stamp, a weekly's "Report Generated" date, a VIP
sheet's `data_pull`), or when its total is below half the median of the six months before it. Only
trailing months are judged, at most two, and only where the baseline median is 50 or more (a count floor;
small MRPC enrollment counts have real zeros). Evidence: over every ODD extract on hand (83), the trailing
three months of swipes, spend, NSF/OD items and NSF/OD accounts read 51% of baseline or more everywhere
except 1539 (2%) and 1774 (5%), both August NSF/OD.

**What moved.**
- ARS `metrics_gen`: judged per measure family. NSF/OD series, `nsf_last_*` tiles and `nsf_yoy` end on
  the last complete NSF/OD month; the left-out month is kept as `nsf_excluded`, never charted. The swipe-tier
  3-month window and the before/after windows use months complete in swipes, spend AND NSF/OD; the dot plot,
  sustained windows and the new-vs-book usage tiles use the last complete swipes+spend month
  (`activity_month`); Reg E vintage NSF/OD items per month use the last 12 complete NSF/OD months.
- ARS `ticket_calc`: the same call, so the Average Ticket window equals the swipe-tier window; a response
  window cut short now divides by the months it has, not by 3.
- ARS `build_ars_gen` / `charts_gen` / one-pager / performance dashboard: the workbook's Key Trends spend
  series (Spend YoY, monthly spend, card growth, the chart, the span caption) ends on its last complete month.
- Slides say it: the NSF/OD caption adds "<Mon YYYY> left out: incomplete in this extract.", its tiles name
  the month they show, the swipe-tier and Average Ticket captions name a left-out month, and the notes carry
  the figures behind the call and the months each YoY compares. No slide is dropped or zeroed.
- CashPlease `cp_extract`: a `*` month roll-up for a month that had not ended at report generation is held
  out of `monthly` (`monthly_in_progress`). None does today. The dashboard's `complete_months` now calls the
  shared rule.
- MRPC: `performance_vs_goal` and `revenue.by_month` are trimmed to complete months before slides 5 and 8
  average, peak and range them, with the exclusion in the notes (none today: the Sep pulls end Jul 26 / May 26).
  The enrollments subtitle, notes and chart legend said the last month "is a partial month" unconditionally;
  they now say it only when VIP flags `partial_last`.
- ICS: Results by Branch notes state that the YTD referrals include the month to date. VIP's branch counts
  cannot be split by month, so the pace figure is unchanged; this is the one comparison still on a partial month.

**Marine 1539, 2026.09 extract (rebuilt metrics in `Build Artifacts/complete_months_check_2026-09-17/`):**
Items YoY -98% (Aug 25 → Aug 26) → +10% (Jul 25 → Jul 26); tiles 390 items / 290 accounts → 19,451 / 4,480
(July 2026); swipe-tier window Jun–Aug → May–Jul 2026 (NSF/OD column 10,944 → 15,872); Average Ticket window
Jun–Aug → May–Jul; Reg E vintage items per participant up 0.02-0.10 per band. Before/after, dot plot and
usage tiles unchanged. No other 2026.09 ARS deck has a month this rule excludes.

### 2026-09-17 — Questions & Discussion carries the cover's month

Every 2026.09 ARS deck in Outputs — 33, the combined decks built on an ARS shell included — read
"<Client>  •  July 2026" on Questions & Discussion under a cover reading September 2026. `build_ars_gen`
swapped the cover's month but only the client NAME on the closing slide (by index, `S[30]`), so the template
shell's month rode through. It now swaps the whole "<client>  •  <month>" line to `PRESENT_MONTH`, resolved by
title, and a template that changes that line misses the swap gate. ICS, MRPC and CashPlease already wrote the
same month on both slides, and `assemble_combined` keeps the base program's cover and closing slide, so
fixing ARS fixes the combined decks.

New gate check, `validate_deck.closing_month_findings`: FAILs a deck whose Questions & Discussion line names
a different month or client than the cover. It FAILs all 33 of those decks, and passes every template shell
(both slides carry the dummy July 2026) and the 16 ICS / MRPC / CashPlease 2026.09 decks. The 33 decks need a
rebuild to pick up the fix.

### 2026-09-17 — The ILS DDA count is saved from Charles's weekly email automatically

Aaron: "Update the ILS DDA count from Charles's email with subject 'ILS Management Server DDA
Count'. Our CSI Email Monitor task can do this as part of its checks." `scripts/ils_dda_count_mail.py`
takes the newest such email (from charles.baker or velocityalerts) out of Outlook over COM and saves
its body as `Inputs/CashPlease/ILS-DDA-Count-<sent date>.txt`, the file `build_cashplease.py` reads
for the loans-per-DDA denominator. The CSI Email Monitor's runner calls it before its Claude step,
so the ~280 counts are copied, not retyped by a model. It saves only a body that parses to a table,
and a week already saved with a different table is reported and left alone (compared as parsed
counts, so `&amp;` versus `&` in a client name is not a difference). 2026-09-17 saved: 232 clients
with a count, 45 NULL.

### 2026-09-17 — A branch-name dataset in Inputs, kept by the morning source check

Aaron: "create a branch mapping data set in inputs and update it when new branch names are
discovered." `Inputs/Branch Names/branch_names.csv` holds one row per name a source has given a
client's branch number (client, number, name, source, source file, first and last seen); nothing
is removed. `watch_sources.py --branch-names` (now in the scheduled task) adds names from each
client's Charts workbook, Branch Results tab, and from the ICS referrals pull's VIP branch names.
A Charts file is tied to a client only when exactly one client's whole name fits its filename
("federal credit union" read as FCU, "credit union" as CU); the rest are reported for a row in
`charts_files.csv`. `branch_names.client_map(id)` reads it back: the Charts name wins, VIP fills
numbers the Charts file lacks, and a number one source names two different ways is left unnamed
("North Shore" and "North Shore Branch" count as one). First run: 1,638 names for 78 clients;
Marine FCU gets names for all 18 branch numbers its ODD uses, where its Charts file had 15.
Nothing in the monthly decks reads it yet. Tests: `tests/test_branch_name_dataset.py`.

### 2026-09-17 — The morning source check keeps the ICS referrals query current

Aaron: "For the ICS query we need to pull that list periodically. Automatically update the query
during the morning file scan to only pull from the last scan to now, then dedup any overlap."
`watch_sources.py --ics-referrals` (now in the scheduled task) runs `scripts/ics_referrals_pull.py`:
each result saved as `Inputs/ICS Referrals/ics_referrals <date>.csv` is merged into
`ics_referrals.csv`, and `ICS Referrals - new since last pull.sql` is rewritten with `@since` set
to the day of the newest referral merged. Overlap is removed per referral (client, account, issue
date): the newer pull's rows replace the older's, which also keeps the query's branch-join
duplicates from stacking up across pulls. A result whose header or column count is not the
query's (SSMS does not quote a comma in a name) is reported and not merged. The query moved into
the repo as `scripts/sql/ics_referrals_all_clients.sql`. Tests: `tests/test_ics_referrals_pull.py`.

### 2026-09-16 — Six views from James Gilmore's deck, opt-in (`RPE_JAMES_SLIDES=1`)

*Merged into main 2026-09-17 (Aaron: "merge the test branch into main"). Still opt-in: without
`RPE_JAMES_SLIDES=1` no deck changes. Its take rate / Reg E layout and branch names were already
on main by then, in `slide_geometry` and `metrics_gen`, so the branch's own copies were dropped.*

**Branch `test/james-aaron-combined` only; not for delivery.** Aaron: "create a test branch that
combines ideas from both my and James's decks, produce a sample." With `RPE_JAMES_SLIDES=1`,
`build_ars_gen` adds six slides; without it the build is unchanged (the template baseline does
not move). Figures come from the ODD and the ARS workbook the build already reads:

- **Revenue by Mailing** (after Mailing Response Summary) — each mailing's booked incremental
  revenue from the workbook's All Months Rollup MM sheet, with revenue per month booked; a
  workbook without the sheet says so on the slide.
- **Responders vs Mailed Non-Responders** (after Before vs After by Offer) — difference in
  differences. The responder side is the Responder Activity slide's own figure (the build stops
  if the two drift); the control is accounts mailed the same drop that did not meet the goal.
- **Card Account Health** (after NSF/OD Activity) — eligible personal accounts by card-spend state
  (active, declining, cooling, dormant, never used, no card), ratios of the last 3 months to the 3
  before.
- **Take Rate and Reg E Opt-In by Branch** and **Branch Scorecard** (after Reg E by Vintage) — on
  the deck's own definitions, so the Total row reconciles to Program Overview and First-Year
  Closure (pinned in `tests/test_combined_insights.py` against the synthetic ODD).
- **ARS Scorecard** (before Key Takeaways) — each measure against its own comparator; status
  ahead / within 2% / behind from Aaron's +/-2% band, glyph plus colour.

New: `build/ars_pipeline/combined_insights.py` (import-safe computations),
`insight_charts.py` (renderers), `combined_insight_slides.py` (slide insertion).

### 2026-09-16 — ICS per-account subtitles: the worked example is the client's first cohort

The subtitles on "Interchange Revenue per Account per Month", "NSF/OD & Other Fees per Account per
Month" and "Spread Revenue per Account per Month" explain the chart with one cohort. Its label,
account count and months open were literals from the reference client — "Nov 25 ... / 19 / 8" — on
every full (non-referrals-only) ICS deck; the interchange one was literal down to "$398.47 = $2.62",
and the other two put the client's own dollars over the literal divisors. 1776 CoastHills (2026.08)
printed "Nov 25: $3,693.10 / 19 / 8 = $24.30" while its first cohort was Dec 25 with 103 accounts.
New `build_ics_gen.cohort_example` reads the label, accounts opened and months open from the sheet's
first cohort (months open is `ics_charts_gen._months_open`, what the chart divides by), with each
slide's own series for the dollars. Because the caption's length now follows the data, the NSF/OD
subtitle opens "NSF/OD + other fees ÷ ..." instead of "(NSF/OD + other charges) ÷ ...": at
$123,456.78 / 1,234 the old wording overran its box and the validator failed the deck. Charts and
tiles are unchanged. `tests/test_ics_cohort_example.py` builds a synthetic full deck and checks each
example against the sheet, and checks a wide first cohort still passes `validate_deck`. Full ICS decks
already built carry the literal example and need a rebuild to correct it.

### 2026-09-16 — CSM Sheila shows what's new and links the change log

The page header has a "What's new" menu with the five newest entries of this file (date, title and the first
paragraph) and a "Change log" link to the whole file, rendered at `/changelog` (Aaron: "Add a link to the
change log at the top of Sheila's page, and show the last 5 updates"). `release_launcher.ps1` now copies
`CHANGELOG.md` beside the released code so the page reads the released version.

### 2026-09-16 — Contact Us card names the managing CSM; ICS Direct Mail New Accounts slide

**Contact card** (Aaron: "The contact card should always show the managing CSM"). Every deck's Contact Us
card was one CSM's static card: the ARS, MRPC and CashPlease template shells carried it and the builders
kept it, and ICS read it from the sheet. The card is now the client's managing CSM (`Client CSM List.csv`),
with that CSM's row in `CSM Contacts.csv`, resolved by `rpe_env.csm_contact` and written into the shell
cards by `shapes.fill_contact_card`. A CSM with no phone gets no phone line. A client with no CSM, or a CSM
with no row, stops the build rather than falling back to another CSM. Standalone ICS decks always carry the
Contact slide and add the ICS program contact, Cindy Draper, as a second card (Aaron: "Add Cindy on ICS";
her row added to `CSM Contacts.csv`); combined decks keep the base program's single card. The 24 2026.09
ARS decks in Outputs for other CSMs' clients carried Aaron's card and were rebuilt.

**ICS direct mail** (Aaron: "Direct mail should get its own slide"). A sheet's `direct_mail` block (from
`Inputs/ICS Direct Mail/`) renders as "Direct Mail New Accounts" after Results by Branch: a monthly chart,
program-to-date and latest-month callouts, and the top branches. Those accounts are a different channel and
are never added to referral figures (1776 CoastHills CU: 384 accounts, Apr'25 – Aug'26). VIP decks without
direct-mail data are unchanged (1676, 1549, 1075 rebuilt before and after).

### 2026-09-16 — ICS section from local files when there is no VIP sheet (1776 CoastHills CU)

New `build/ics_pipeline/ics_local_sheet.py` builds the ICS client sheet from the referral detail export
(`Inputs/ICS Referrals`), the current-period ICS workbook, the ICS Charts Goals tab and the direct-mail
list (`Inputs/ICS Direct Mail`, recorded, not rendered). `build_month.build_client` falls back to it only
when the VIP sheet is missing; what the files cannot supply (month to date, mystery shop, referred
accounts by product, contacts) is omitted, never zeroed, with the reason in the sheet's provenance.
`build_ics_gen` notes name those files and say "not VIP", the date pill uses the last referral date, and
goal tiles and columns are dropped when no goal is on file. VIP decks are unchanged (1676 and 1549
rebuilt before and after, identical). New `rpe_env.INPUT_KIND_DIRS` kinds `ICS referrals` and `ICS
direct mail`, both unscanned (hand-landed, member-level). The legacy `.xls` referral export is read with
xlrd or, without it, an Excel-converted copy in `Build Artifacts/ics_local_sheet/<id>/`.

**Fix (every ICS build):** a full ICS build with no Contact slide wrote `slide27.xml` twice — the Summit
slide took a static slide's part name, which the package check caught on 1776. Slide parts are now
renumbered before the Summit is inserted; `tests/test_ics_local_sheet.py` pins it.

Open for Aaron (1776): the Charts Goals Total row says 48/month but the branch goals sum to 80 (80 used);
169 pre-2025 referrals on the Charts tab are not in the referral file; the workbook's 2,575 accounts do
not reconcile to 2,280 referrals + 384 direct-mail accounts; whether direct mail gets its own slide.

### 2026-09-16 — CSM Sheila offers an ARS-only or a combined deck; 1776 is on ICS

**Two builds** (Aaron: "add a second Create button so the CSM can elect to build an ARS only deck, or a
combined deck for whichever products have the appropriate data"). `ars_launcher.program_availability`
decides, per clients.md program, whether its data is on hand this period: ICS from its VIP sheet or,
without one, the local ICS workbook and referral files (`ics_local_sheet.available`); MRPC from its
VIP sheet. When any is available the client page shows a second button, "Build combined (ARS + …)",
which runs `ars_launcher.py build <id> --combined`; programs without data are named as left out.
Any CSM may now choose a combined deck; for Aaron's multi-program clients the combined deck is the
only build offered (an ARS-only deck must not replace his combined one). A combined deck also passes
the package-integrity check before it goes to Outputs, and delivering either kind archives the
client's other ARS-bearing deck for the month, so a client has one deck per period.

**1776 CoastHills CU is on ICS** in clients.md (Aaron: "Add ICS, but don't pull from VIP"), built from
James Gilmore's ICS workbook, referral detail and direct-mail files rather than a VIP sheet.

### 2026-09-16 — The last two build files left in the temp folder are removed too

A 1539 Marine FCU build died in `build_ars_gen.py` with "OSError: [Errno 28] No space left on
device" while saving its phase deck, with C: at about 6 MB free and several ARS builds running.
The fix below covered the scratch *directories*, but two scratch *files* were still written
straight into `%TEMP%`, where `temp_dir` never sees them and `sweep_temp` (directories only)
never removes them:

- `build_ars_gen.py` copied the template shell to `%TEMP%\_<id>_ars_work.pptx` and never deleted
  it. It now lives in the build's `ars_assets_` scratch dir, removed at exit.
- `build_cp_gen.py` saved `<deck>.__full.pptx` to `%TEMP%` and deleted it only if `strip_dead.py`
  succeeded, so a failed strip left it behind. It is now written inside a `TemporaryDirectory`
  block, removed however the block ends.

`tests/test_temp_cleanup.py` only looked for `tempfile.mkdtemp(`, which is why neither was caught.
It now also fails on `mkstemp`, `gettempdir()`, `NamedTemporaryFile(delete=False)`, a
`TemporaryDirectory` outside a `with` block, and `extractall` (whole-zip extraction) anywhere in
`build/` or `scripts/`; and it checks that the extracted ODD is gone once the process exits and
that both `resolve_csv` functions go through `rpe_env.extract_odd_csv`. Path-only change: no
slide, figure or source note moves.

### 2026-09-16 — Build scratch is removed; every build sweeps the temp folder first

The C: drive reached 0.11 GB free and two Reg E rebuilds (1192, 1554) died with "No space left on
device". Every ARS build unzipped the ODD extract (up to 1.8 GB, plus the month's transaction file
beside it) into `oddd_*` / `oddcsv_*` folders and rendered images into `ars_assets_*` /
`ars_phase_*`, and none of them was ever deleted: 1,241 folders, about 180 GB, back to 2026-08-31.
They were cleared by hand (older than 2 hours only).

- `rpe_env.temp_dir(prefix)` is now the only way the pipeline makes build scratch; it is removed
  when the process exits.
- `rpe_env.extract_odd_csv` extracts only the ODD member of the zip, not the transaction file.
- `rpe_env.sweep_temp()` removes pipeline scratch older than 6 hours (left by a crashed or killed
  build); `build_month.build_client` — and so `ars_launcher` and CSM Sheila — run it first and log
  what they removed (Aaron: "make sure temp drive cleanup is part of the process").
- `tests/test_temp_cleanup.py` fails if any build or scripts file calls `tempfile.mkdtemp` directly.

### 2026-09-16 — Reg E opt-in read as zero for "Opted In / Opted Out" extracts (correction)

**A client-facing number was wrong.** `metrics_gen.regd` recognised only "opt in / opt-in / optin",
so extracts worded "Opted In" / "Opted Out" put every open personal card holder in "no election".
1776 CoastHills shipped Reg E opt-in at 0.0% on all five Reg E slides and Program Overview (the
extract's latest month has 12,967 opted in, 30,941 opted out, 8,892 default); James Gilmore's deck
for the same client showed 21.1%, which is how it surfaced. `oddd_optimize.classify_rege` read the
same files correctly: two definitions of one rule that had drifted. 16 decks in Outputs carried a
misread Reg E base: 1038, 1192, 1217, 1520, 1537, 1542, 1554, 1652, 1673, 1745, 1759, 1765, 1766,
1776, 1798, 1799.

**Fix.** `build/ars_pipeline/odd_rows.rege_label` is now the one reading, used by both. New wording
mapped with Aaron (2026-09-16): Yes/Y → Opt In; No/N, Revoked → Opt Out; Failed to Respond, No
Decision, Did Not Reply, D → Default; Ineligible, Exempt, "Tracking Type N Does Not Exist", "No
Vaule - No Reg E", "Anything else" → not applicable.

**The check that would have caught it.** `metrics_gen` now stops with a POSSIBLE DATA ISSUE when the
latest Reg E column carries wording no mapping covers, instead of counting it as no election; and
`tests/test_rege_label.py` fails if either file carries its own wording rule again. The synthetic
fixture's unmapped "Undetermined" became "Opted In" (unmapped handling is tested directly).

### 2026-09-16 — ARS Revenue Lift Matrix drawn as a heat grid; caption example is 1-5 → 11-15

**What the slide renders changed (every MM deck).** `render_lift.py` drew two plain tables (the matrix
and the Revenue Segmentation block). It now draws the matrix as a heat grid in the house chart style,
with impossible moves shown as a dash, and the segmentation block as bars of monthly value per card
account with each tier's share of cards (Aaron: "swap the heat grid into render_lift.py for all MM
decks"). No figure moved: both halves read the same lift.json as before, at the slide's picture aspect.

**The caption's worked example changed** (Aaron: "use 1-5 to 11-15 as the example in the bottom
text"). It was Non-User → 26+ written as an equation; it is now "a 1-5 account ($x a month) that moves
to 11-15 ($y) adds $z a month", and that cell is outlined orange on the chart. `render_lift.example_move`
is the one definition; a matrix without that cell falls back to its largest move. `render_lift.py` is
import-safe now so `build_ars_gen` can share it. Tests: `tests/test_render_lift.py`.

**No selection line on the slide** (Aaron: "remove the selection text on the lift matrix slide"). The two
chart titles inside the picture say what the grid and the bars show, and the window is on the pill; the
template's subtitle shape is removed, not blanked, and the build stops if it cannot be found.

**The browser builder is CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics.** WILL was renamed again the same day; `ARS Deck Builder GUI.bat`
still starts it.

### 2026-09-16 — The browser builder is WILL; a failed build shows a red Error pill

**Name.** ARS Deck Builder is now **WILL, the Workbook Intake & Layout Launcher** (Aaron). Its
launcher file is `ARS Deck Builder GUI.bat`; the old `ARS Deck Builder.bat` on the share was moved to
`Tools\_retired launchers - delete after review\`. The page title, header, console window and user
guide carry the new name.

**Error pill.** When a client's last build for the cycle was not put in Outputs, the client list
shows a red **Error 2026.09** pill (the cycle period) and the client's button reads **Retry build**
(or **Retry rebuild** when a deck is already in Outputs). `last_build_failed` decides it: a job this
server ran and still remembers wins (running or queued is never an error); otherwise the launcher's
`_launcher_result.json` for the period, unless a deck for the period reached Outputs after that record
was written. On the first run it flagged 1121 Timberland, 1615 Cape & Coast and 1748 Clearview.
A failed build followed live also turns its button back on as Retry. No deck output changes.

### 2026-09-16 — ARS Deck Builder: a second build queues instead of being refused

Starting a build while another ran on the same PC returned "A build for … is still running. Start the
next one when it finishes", so a CSM had to watch for the first to end. `start_build` now puts the job
in a first-in, first-out queue and one worker runs them one at a time, as before. The client list
polls `/api/queue` every 3 seconds and shows **Building** on the running client and **Queued #N** on
each waiting one, where N is its place in the line. A queued client's page and button say the same.
Asking to build a client that is already building or queued still returns 409. No deck output changes.

### 2026-09-16 — ARS Deck Builder: Full output stays open, shown as a terminal

Clicking "Full output" during a build opened the panel for at most 1.5 seconds: every
job poll rebuilt the whole build area with `innerHTML`, which replaced the open
`<details>` with a closed one. `renderJob` in `scripts/ars_launcher_web.py` now creates
the panel once per build and afterwards only updates the step list and the output
text. The open state survives switching clients, and the output stays scrolled to the
bottom unless someone has scrolled up. The output is drawn as a Windows Terminal
window with `[ok]`, `[!!]`, `[built]`, `[STOP]` and `[..]` in color. No deck output changes.

### 2026-09-16 — CashPlease inputs have their own folder

**CashPlease data now lands in `Inputs/CashPlease/`** (Aaron: "add inputs folder for CashPlease
data"). Bradford Sanders' CashPleaseSummary weeklies and the weekly `ILS-DDA-Count-<date>.txt`
used to share `Inputs/Weekly Summaries/` with the MRPC enrollment weeklies. The folder is the new
`"CP weekly"` kind in `rpe_env.INPUT_KIND_DIRS`. `mail_sources` files a CashPleaseSummary
attachment there, and still keeps only the newest. `build_cashplease` and the dashboard refresh
already search every scanned input folder, so they find it unchanged; their "save it here"
messages and the dashboard's source line name the new folder. The per-client production settings
stay in `Inputs/Product Settings/`, which is the Velocity Product Settings app's folder rather than
a CashPlease one. The two CashPlease files already on hand were moved, not copied.

### 2026-09-15 — the archive is `Outputs/_Archive/`

**`Outputs/Archive/` is renamed `Outputs/_Archive/`** (Aaron: "add to the archive folder names so they
stay at the top, above my name"). "Archive" sorted between "Aaron Burgard" and the other CSM
folders. The underscore puts it at the top of Outputs, beside `_Unassigned`. The name lives in
`rpe_env.ARCHIVE_DIRNAME`, which `promote_month` and `ars_launcher` archive into.
`output_decks` skips both the new and the old name, so a leftover `Archive/` is never read as a
CSM's folder. The folder on the share was renamed, not copied. `tests/test_archive_dirname.py`
covers the name, the skip of both names and the two writers.

### 2026-09-15 — client logos were clipped on the slide

**`rpe_env.trim_logo` cut into 26 of 122 client logos** (Aaron: "CoastHills needs a corrected
logo"). The logo file was fine. The CoastHills site's SVG renders pixel-identical to
`Inputs/Logos/1776.png`, but the deck's agenda slide carried a 1600x294 slice of the 1600x384 logo,
with the tops of the letters gone.

The cause: a transparent logo whose artwork touches the canvas edges has a full-canvas alpha box.
trim_logo took that as an opaque canvas, sampled the border (the lettering itself) as the
background colour, and subtracted it. The worst cases kept a fragment: 1183 came out 632x28,
1072 133x134 of 1195x258, 1526 166x166 of 1200x437, 1204 320x314 of 1200x314. The opaque-canvas
pass now runs only when at least 90% of the border ring is opaque. Those 26 now keep their full
artwork, and the other 95 trim exactly as before, including the white-canvas logos the pass exists
for (1549). `tests/test_trim_logo.py` covers the opaque canvas, transparent padding and the
edge-to-edge transparent logo.

Decks built before this carry the clipped logo until they are rebuilt. 2026.09 decks in Outputs
affected: 1156, 1204, 1218, 1673, 1734, 1759, 1776 and 1798.

### 2026-09-15 — the issue pages are built from the repo

**The ODD and Workbook Issues and CSM Data Gaps pages are now built by `scripts/issue_pages/`**
(Aaron: "move the issue page scripts into the repo"). They had been built from scripts in a Claude
session scratchpad, with the share and the repo checkout written into them. Every path now
resolves through rpe_env (`common.py`). Working data and both pages live in `Build Artifacts/issue_pages/`,
because they carry client names and products. `build_issue_pages.py` runs the chain in order and
copies both pages to `Notes/`. `tests/test_issue_pages.py` fails on a written-in share or machine
path, and covers the share-history scan and the Notes charset.

What changed on the way in:
- `missing_wb_history.py` is new. Nothing in the scratchpad had written that file; it scans every
  month on the client-reports share for the Missing Workbook clients.
- The ODD page no longer carries a separate "Missing Workbook" table above the CSM sections. A
  Missing Workbook client is listed in its CSM's section only (Aaron: "Jordan's missing Texar
  workbook should be in his section").
- Stale one-day patches came out: the "recalculated, rebuild in progress" note for 1192 and 1673,
  the hand-added uncalculated-workbook finding for 1673 (it has since built clean) and an empty
  ARS-confirmed override. The Data Gaps page drops from 120 to 119 issues as a result.
- "September" and the 20-client roster count are derived from the period and clients.md, not
  written in.

### 2026-09-15 — an expired Lift Matrix stops the launcher's build

**The launcher now checks the Lift Matrix before an MM client's build** (Aaron: "flag it as having
an expired lift matrix. Add the lift matrix date check to the build criteria"). It stops when the
workbook's data month is past the Lift Matrix MM End Date. It also stops when the workbook filename
carries the data team's flag ("LM EXPIRED", "NEEDS LIFT MATRIX", "NEW LIFT MATRIX NEEDED"; the
same `perf_actions.lift_matrix_flag` the performance page uses). The fix it names is the CSM's: a
new Lift Matrix. SM clients have no Lift Matrix and are not checked. `status`, `build` and ARS Deck
Builder all run it. The builder's client list tags an expired matrix "Lift Matrix expired", read in
the background when the builder starts.

The window reading moved out of `extract_lift.py`, which runs as a script, into import-safe
`build/ars_pipeline/lift_window.py`. The launcher reads the same definition the deck does.
extract_lift's output is byte-identical on 1780, 1441 and 1520. On the 2026.09 batch the dates
expire seven MM clients: 1453, 1487, 1526, 1529, 1637, 1681 and 1780. Five of those workbooks were
already flagged by filename. 1526 and 1681 were not flagged, but their windows ended May 2026 and
Feb 2026.

**The six 2026.09 decks already in Outputs on an expired matrix were taken out of Outputs**
(Aaron, 2026-09-15: move all six): 1453, 1487, 1526, 1529, 1681 and 1780. Each is in
`Outputs/Archive/_older decks - delete after review/<CSM>/<id> <client>/`, named "(expired lift
matrix 2026-09-15)". Nothing was deleted. They are rebuilt once a new Lift Matrix lands, and until
then the launcher refuses to build them.

**The launcher and the builder name a client from `clients.md`**, as its deck does. The Client CSM
List name comes from a workbook filename and had picked up the flag: 1780 read "LM EXPIRED-USF CU /
USF CU". That list entry is now "USF CU" (backup in `Build Artifacts/`). The builder's list also
drops the program tags and dates its Outputs tag: "In Outputs 2026.09".

**ARS Deck Builder caches what it has checked** (Aaron: "can we speed up the UI by caching
information?"). A client's status cost 3-6 seconds, mostly the share and Inputs checks (about 2s)
and opening the workbook for its Lift Matrix (0.4-2s). Now:
- each status is kept for 10 minutes, and the page says how old it is;
- "Check again" re-reads it, and a finished build drops that client's entry;
- every client is checked once in the background when the builder starts, so a click is usually
  instant;
- the launcher remembers each workbook's Lift Matrix window until the file changes.

`ars_launcher.py build` never uses the builder's cache: its checks run fresh right before the build.

**A deck already in Outputs asks before it is rebuilt** (Aaron: "The deck is already in Outputs, but
it says Build and put in Outputs. It should ask if we need to rebuild"). The rebuild question used
to follow the delivery log, and only Aaron records sends, so another CSM's client with a deck in
Outputs (1815 FedChoice) was offered a plain build. It now follows Outputs: any ARS-bearing deck
for the client and period in any CSM folder. The builder says "This month's deck is already in
Outputs", the console marks it `[built]`, and the .bat asks "Rebuild it and replace it".

**The launcher no longer tells anyone to mark a deck sent** (Aaron: "the other CSM don't have an
artifact to mark those, and i don't have to do that part for them"). The builder's "Sent" chips,
its "tell Aaron it went out" line, the console's "Mark it sent" line and the user guide's step are
gone. Rebuilding a deck already recorded as sent still asks first. Only Aaron's decks are ever
recorded, so other CSMs never see that question.

### 2026-09-15 — ARS Deck Builder: the launcher in a browser

**`ARS Deck Builder.bat` opens the ARS launcher as a page in the browser** (Aaron: "would it be
possible to run Build ARS Deck.bat in an application or browser?"). A browser cannot start a
program, so the .bat starts `scripts/ars_launcher_web.py`, a small server on 127.0.0.1, and opens
its page. The page lists the `clients.md` ARS clients by CSM, with sent and in-Outputs chips.
Picking a client runs `ars_launcher`'s own `rule_checks` and `input_checks`. The button is Build,
Rebuild (after a second click, when the deck was already sent), or Check again when something
stops it. The build is `ars_launcher.py build` run as a child process, and its step lines are
shown as they arrive. A finished deck gets a "Show it in File Explorer" link. The rules, the build
and the delivery to Outputs are unchanged, because the page only calls the launcher. One build
runs at a time per PC.

Only the page this server served can use it: every API call needs the random token baked into
that page and a 127.0.0.1 or localhost Host header, so another site open in the same browser
cannot start a build through localhost. The reveal call opens only a file under Outputs.
`Build ARS Deck.bat` stays as the plain-console fallback. `tests/test_ars_launcher_web.py` covers
the token and Host checks, a bad client number, a build job's lines and deck, the
one-build-at-a-time rule, and the Outputs-only reveal.

### 2026-09-15 — the MM lift matrix slide is titled "ARS Revenue Lift Matrix"

**The MM slide is now titled for what it shows** (Aaron: "This slide should be titled ARS
Revenue Lift Matrix"). It still read "Monthly Summary — Last 12 Months" over a lift matrix
table, because on 2026-08-20 both revenue models kept one title. That decision is reversed for
the MM path only. The SM slide is a 12-month revenue chart and keeps its title. The ARS agenda
line on MM decks names the slide the same way. The speaker note now sources the Lift Matrix
MM tab, because `_note_for` matches "lift matrix". The banned-word check already allows "lift"
inside the named Lift Matrix slide. The date pill still shows the matrix's own 12-month window
from the workbook's Start/End cells.

**The delivered 2026.09 MM decks were rebuilt with the new title** (Aaron: "put it in Outputs as a
v2, then fix the other decks"). Each ARS deck was re-assembled from its batch's staged metrics,
charts and extract; the inputs had not changed, only the builder. Aaron's combined clients were
re-assembled with the ICS section they shipped with. A deck already recorded as sent (1509, 1537,
1676, 1705), and 1539 as asked, went in as "<name> v2.pptx", with the deck it replaced moved to
Archive. Every other deck replaced its copy through `promote_month`. SM decks (1038, 1156, 1652)
have no lift matrix slide and were left alone. The original 1539 deck stays beside its v2 until
the person who has it open closes it.

**1676 True Sky was rebuilt in full on a re-pulled ODD** (`1676_ODDD_Code updated.zip`, 09/15
13:13). It carries the same 52,848 rows and columns as the 09/01 pull. The difference is the 6 open
accounts whose `Business?` flag was blank (product codes CBMM and BMM1); all 6 now read "Yes".
The zip also drops the monthly debit-card transaction file, which no reader opens: every reader
takes only the `.csv` member. The source watch did not copy it, because its name does not match
`<id>_ODDD.zip`; it was copied into `Inputs/ODDD/1676_ODDD.zip` by hand. The v2 built from it
replaced the title-batch v2 built on the old extract.

### 2026-09-15 — the four-program agenda hid its "1"

**Row 1's number was drawn under an orange circle on the Marine FCU 1539 ARS-ICS-MRPC-CP deck**
(Aaron: "the first bullet on the Agenda is missing the number 1"). The template's agenda has
four rows, so a fourth program clones a fifth. `set_agenda` cloned the number, then the badge
circle, so the circle sat above its number. During layout it then looked each row's circle
up by position. A clone sits exactly on its source until it is moved, so row 5 found ROW 1's
circle and carried it down. The clone's circle stayed on row 1, covering the "1". The clones
also kept their source's shape ids (119-122 twice on one slide). Each row's circle is now
resolved once, before cloning, and moves with its row. A clone's circle is cloned before its
number, and `_clone` gives every copy a new shape id. Only 1539 was affected: every other
combined deck has four rows or fewer and never clones. A new test assembles a four-program
agenda and checks that every number shows, sits on exactly one circle, and that no shape id
repeats. No earlier test assembled more than three programs.

### 2026-09-15 — 1615's empty debit-usage base stops with a named cause

`metrics_gen` averaged spend over the card holders who swiped in the latest month, for new
accounts and for the open book. 1615 Cape & Coast has no such open card holders: 18,912 personal
accounts carry Stat Code `0` with a blank Stat Desc, so only 720 read as open, and none of
those 287 card holders swiped in Aug26. `mean()` of nothing crashed the build with a
`StatisticsError` that named no cause. It now stops with POSSIBLE DATA ISSUE, giving the counts
and the most common status values on accounts that don't read as open. `0` is not mapped: it
is a code-sheet correction for the client, already on the Data Gaps page.

### 2026-09-15 — an ARS deck can be built without Claude

**`Build ARS Deck.bat` in the CSM_Reporting folder** (Aaron: "i'd like to develop a way where
anyone can run an ARS deck so long as the inputs are in place"). It asks for a client number
and runs `scripts/ars_launcher.py`, which applies the checks that used to be done by hand, all
of them BEFORE the build:

- the client is on the Client CSM List, its product list includes ARS (a blank list warns),
  and `clients.md` lists it for ARS;
- a client of Aaron's on more than one program stops, because it ships a combined deck;
- a deck already marked sent for the period is a question, not a stop (Aaron: "can the script
  prompt whether the user wants the presentation re-run rather than failing?"). `status` exits
  3 when that is the only thing in the way, and the .bat asks "Rebuild it and replace the one
  in Outputs". On the command line it takes `--rebuild`;
- the ODD extract and ARS workbook are there and current for the cycle period (the newest ARS
  workbook in `Inputs/`), through the same `deck_status.requirements` the dashboard uses. A
  missing DCO warns. A stale or missing input stops with the fix named for the data team;
- one build per client at a time (a lock in the work folder, taken over after 3 hours).

The build works in `Build Artifacts/launcher/<period>/<id>/`, where its log, charts and data stay
out of sight. A deck that validates with 0 FAIL goes straight to `Outputs/<CSM>/`, and what it
supersedes is archived by `promote_month.promote_one`. If the Outputs deck is open, nothing
moves and the launcher says to close it. There is no staging folder and no separate deliver
step. A `Staging/` folder and a `Deliver ARS Deck.bat` with a typed-YES prompt were built and
dropped the same day (Aaron: "Each CSM will manually review, PDF, and email these
presentations. We can skip staging altogether and go straight to Output.").

The build's own output goes to `build.log`, so the launcher watches that log and prints each
step as it starts. Without that, the window sat silent for up to 15 minutes.
`ARS Deck User Guide.html` sits beside the .bat file.

That exposed a `build.log` defect that affects every build, not only the launcher.
`build_month.run` wrote each step's command line without flushing before the step started, and
the step writes straight to the file. So each command line landed AFTER its own output. A
traceback therefore read as belonging to the step before: 1615's metrics_gen error sat under
the oddd_optimize command. It also meant the launcher named each step when it ended. `run` now
flushes first, and a test checks the order.

`scripts/release_launcher.ps1` copies the code to `Tools\RPE` on the share and, with `-Runtime`,
a zipped Python with the libraries that each PC unpacks to `%LOCALAPPDATA%\RPE` on first use.
The launcher runs the released copy, so a change in the repo reaches it only after a release.
`tests/test_ars_launcher.py` covers the rules.

### 2026-09-15 — the archive is filed by CSM

**`Outputs/Archive/` now has a folder per CSM, like `Outputs/`** (Aaron: "sort the archive by
CSM"). A superseded deck goes to `Archive/<CSM>/<id> <client>/`, and older decks of the same
period and kind go to `Archive/_older decks - delete after review/<CSM>/<id> <client>/`.
`promote_month.client_folder` takes the CSM from `rpe_env.client_csm` (else `_Unassigned`) and
still reuses an existing client folder wherever it is, including a flat one from before. A
rolled-back delivery removes the CSM folder it created if it is left empty. The existing
client folders, 15 in Archive plus those in the review folder, were moved, not copied. Nothing
was deleted. Folders for Max Willett (a CSM with no accounts yet) were created in `Outputs/` and
`Outputs/Archive/`.

`tests/test_promote_month.py` checks that archiving files under the CSM, that an existing
CSM-filed folder is reused, and that the review folder mirrors the CSM layout.

### 2026-09-15 — CSM action items on the performance page

**A new first section lists what a CSM has to take to the client** (Aaron: "If we have unmapped
values for current ARS clients the CSM needs to contact the client to get those fixed. The CSM
also needs to create a new lift matrix if the current one is out of date."). It covers current
ARS clients and follows the CSM, product and client filters.
- **Lift Matrix out of date** is the data team's flag in the ARS workbook's filename ("LM
  EXPIRED", "NEEDS LIFT MATRIX", "NEW LIFT MATRIX NEEDED"), as Aaron chose over the Lift Matrix
  tab's end date. On 2026.09: 1453, 1529, 1780, 1487, 1637; 1743's flag is on its 2026.08 workbook.
- **Codes not mapped** compare each client's ODD (Prod Code, Stat Code, the newest `<Mon><yy>
  Reg E Code` column) with that client's code tables in the ARS database. The terms are the VIP
  Data Specification's: "Product Codes not mapped", "Product codes with no Personal/Business
  flag" (a listed product code whose `is_business` is blank; Personal/Business is set per
  product code, Aaron), "Account Status Codes not mapped", "Mail Flags not mapped" and "Reg E
  Codes not mapped". The ODD carries no raw mail code, only `Mailable?`, which the database has
  already mapped, so a Mail Flag is flagged when that value is anything but Yes or No. Product
  and Account Status decide ARS eligibility, so those items list first and say so. Mail Flag
  decides who is mailed, not eligibility: on 12 clients about 99% of otherwise-eligible
  Mailable?=No accounts are Elig=Yes (1075 514 of 514). Reg E decides neither (Aaron). Each value shows its account count. **Nothing is mapped:** a CSM has the client correct the code
  sheet; no value is added to `STAT_CODE_MAP` or the Reg E classifier (Aaron: "don't force any
  mapping").
- **What cannot be checked is said.** No ODD extract, no code tables, or a column the extract
  lacks is written on the row, never read as "all mapped". A client with no table of a kind in
  the database gets every value listed with a "no table" tag.
- **Where the tables come from.** `scripts/ars_code_tables.py` reads the ARS database export
  (SQL Server text output) and writes only the product, Reg E and status code tables to
  `Inputs/ARS Settings/ars_code_tables.json` (new rpe_env kind "ARS codes", not scanned). The
  clients' code sheets themselves go in `Inputs/Code Sheets/` (kind "Code sheets", also not
  scanned, so the watch and the pruner leave it alone). The
  export's client SETTINGS table carries plaintext FTP passwords and salts: tables are found by
  their id column and only named columns are read, so it is never parsed past its header, copied
  or committed. The mail code table is left out; the ODD has no raw mail code to check against it.
- **No extract is read twice.** The codes are counted in the Client overview's pass
  (`perf_overview`, cache version 3, so every extract is re-read once) and dropped from the page
  data after the check.

### 2026-09-15 — an ARS workbook a month behind is shown the same way for every client

**Seven clients lost their ARS row for want of this month's workbook** (Aaron: "if that's the
case for austin isn't the same with others? make sure that behavior is consistent"). 1075
Austin Bank has no 2026.09 ARS workbook on the share. It is on the clients.md roster, so the
page showed its 2026.08 workbook tagged "workbook 2026.08". A client not on the roster had its
programs inferred from THIS month's share files only, so 1100 Rally, 1121 Timberland, 1126
Legend, 1147 Sutton, 1403 Adirondack, 1554 Isabella and 1743 Mid American all had a 2026.09
DCO, a 2026.08 workbook in Inputs, and no ARS row at all.
- **The rule now.** `page_clients` also puts an inferred client on ARS when Inputs holds its
  ARS workbook from the last two months (`ARS_WORKBOOK_LAG`). The row carries that workbook's
  period and the page tags it, exactly as for Austin Bank. An older lone workbook (the pruner
  never removes the last one) does not bring a client whose ARS ended back onto the page.
- **MRPC rows get the same tag.** A row whose VIP sheet is for an earlier period than the
  cycle now says "VIP <period>". ICS and the Client overview already tagged theirs;
  CashPlease and the MRPC weekly always use the newest weekly by design.

### 2026-09-14 — the performance page drops its subheading

**The line under the title is gone** (Aaron: remove "85 clients, 5 CSMs, across four programs.
Click a CSM, product or client to show only that one, click others to add them, or click All
for the whole row."). The element and the two script lines that filled it are removed. The
"How the decks are made" link stays in the header.

### 2026-09-14 — the performance page's summaries cover current clients only

**The CashPlease peer row is rebuilt over current clients** (Aaron: "For any of these summary
sections, or the client's statistics, only show current clients"). It was
`cp_extract`'s rollup of every tab in the weekly workbook, and on 2026-09-14 51 of those 72
client tabs were not current clients.
- **How it is built.** `refresh_performance_dashboard.current_peer` uses `cp_extract`'s
  formulas on the current clients' own packs. Cancelled programs and tabs with no loans are
  left out. Summed over every tab, those formulas reproduce the rollup's loans, average loan
  size and interest, and status shares.
- **What is left blank.** Charge-off % and the share of active accounts with loans are values
  the workbook reports, and no weighting of the per-client values reproduces them (the
  rollup's 6.26% against 4.72% principal-weighted, for example). The row shows them as absent,
  not approximated.
- **The decks are unchanged.** The CashPlease decks' own peer slide still uses the rollup.

**A program with no activity in six complete months is no longer shown as current.**
`inactive_since` looks at the six months before the weekly report's month: loans for
CashPlease, enrollments for MRPC.
- **Inferred from data.** The program is dropped and the refresh logs it. 1487 Orsa CU's
  CashPlease last booked a loan in Sep 2025.
- **Listed in `clients.md`.** The program stays, because that file decides, tagged "no loans
  since …". 1770 Central State Bank's CashPlease last booked a loan in Dec 2025.

### 2026-09-14 — the workflow page describes Outputs by CSM

### 2026-09-14 — an open account is open in any case, and by Stat Code when Stat Desc is blank

**`odd_rows.isopen`, which decides "open" for every ARS metric, disagreed with the two other status
readers beside it.** It matched Stat Desc case-sensitively and never read Stat Code, while
`odd_rows.status_class` (Product Mix, Excluded Accounts, the client overview) and `oddd_optimize`'s
classifier are case-insensitive and fall back to the code. In the all-client trial builds six clients
had no open account at all, and `metrics_gen` stopped with POSSIBLE DATA ISSUE:

- 1637 writes `open`, 1680 `ACTIVE` / `DORMANT`, 1759 `OPEN/ACTIVE`;
- 1743, 1746 and 1815 leave Stat Desc blank on every row and carry Stat Code `A` / `O`.

`isopen` now compares the description case-insensitively and, only when it is blank, reads the
Aaron-confirmed `STAT_CODE_MAP` (O / A = Open). An unmapped code (D, I, F, 0, word codes) is not
guessed open. `metrics_gen` now loads Stat Code.

**One delivered client's figures move: 1509 Texas Bay.** 1,755 of its accounts read `inactive` in
lower case. `Inactive` is in the open vocabulary, so the Product Mix slide already counted them open.
The ARS metrics did not, until now. The other roster ARS clients (1038, 1075, 1204, 1537, 1539,
1549, 1676, 1705) do not change by a single account. **1509's September deck has not been rebuilt.**

Still undecided and still stopping the build: 1226 (blank Stat Desc, word codes ACTIVE / DORMANT /
INACTIVE), 1585 (`File Maintenance` on 16,398 accounts and 11,396 blanks) and 1615 (18,912 blanks
with code `0`).

`tests/test_odd_rows.py` covers case-insensitive open and closed wording, the code fallback for the
confirmed codes only, the description winning over the code, and no fallback when Stat Code is absent.

### 2026-09-14 — a malformed ODD row is counted and flagged, and an empty base is named as a data issue

Found in the all-client ARS trial builds.

- **1147 Sutton died in `oddd_optimize`.** Three of its 28,930 ODD rows have one extra field,
  from an unquoted comma in a text cell. pandas keeps a row like that and shifts its cells,
  so "Customer Opt In" landed in `Sep23 OD Limit`. The fast (pyarrow) money path cast
  strictly and died, while the pandas fallback had always treated such a cell as missing.
  Both paths now agree: a non-numeric cell in a money or count column counts as missing, and
  the pack's `flags.non_numeric_cells` records how many there were and in which columns, so
  the defect is visible rather than silent. A well-formed extract gives identical figures.
  (`index_col=False` was tried first and does not stop the shift, so it was reverted.)
- **1226 Ellafi died dividing by zero** in the Reg E rate. Its Stat Desc is blank on every
  row, and the status is only in Stat Code (ACTIVE / DORMANT / INACTIVE), so no account read
  as open. **1121 Timberland died on an empty `mean()`**: its newer accounts carry numbers
  (`1`, `39`) in Prod Desc, so no new checking account was found. Neither is fixed by
  guessing. `metrics_gen` now stops with a `POSSIBLE DATA ISSUE` message that names the
  missing base and what the extract carries instead. Mapping word-valued Stat Codes is
  Aaron's call (CLAUDE.md: never guess a status mapping).

`tests/test_odd_malformed.py` covers the flagged non-numeric cells, a clean extract flagging
none, and both data-issue exits, all on the synthetic fixture.

### 2026-09-14 — Outputs is filed by CSM

**Finished decks now go to `Outputs/<CSM>/`, not the flat `Outputs/`** (Aaron: "sort the
Outputs folder by CSM"). The project covers all five CSMs' books now, and one flat folder
of every client's decks would not stay readable.

- `rpe_env.client_outputs(id)` is the one place the folder is decided. The CSM comes from
  `<RPE_DATA_ROOT>/Client CSM List.csv`, else the CashPlease roster's CSM column (the
  CashPlease-only clients 1131, 1564, 1750, 1770 and 1771 are not on the reports share the
  list is built from), else `Outputs/_Unassigned/`. It never guesses a CSM.
- `rpe_env.output_decks(pattern)` is how readers find decks. It searches every CSM folder
  and the flat root, never `Archive/`. `deck_status.built_deck` and b4's
  `refresh_performance_dashboard.decks_and_sent` use it; a reader left globbing the flat
  root would have shown every deck as not built.
- `promote_month` delivers into the CSM folder and archives a copy of the same deck still
  in the flat root, so a client never has a live deck in two places. `build_cashplease`
  writes into the CSM folder. `Outputs/Archive/` is unchanged, one folder per client.
- The 28 files already in Outputs (19 decks and 9 hand-made PDFs, all Aaron Burgard's
  clients) were moved into `Outputs/Aaron Burgard/`: moved, not copied or deleted.

`tests/test_outputs_by_csm.py` covers the CSM lookup, the Unassigned fallback, the roster
fallback, what the readers search (CSM folders and the root, not Archive, not lock files)
and the delivery dashboard finding a deck in a CSM folder. Two `test_promote_month` tests
now expect delivery into the CSM folder.

### 2026-09-14 — credit-union checking accounts count as checking

**`metrics_gen` found no new checking accounts at 1200 Guardians Credit Union and crashed.**
It counted an account as checking only when `Prod Desc` contained "checking". A credit
union's checking account is a *share draft* (Guardians: "Share Draft", "Share Draft
Aspire"), so the new-checking pool was empty and `mean()` of nothing stopped the build. The
match is now "checking" or "share draft", for both the new-checking pool and the top
checking product. **At a bank the figures do not change. At a credit union, the New Checking
Balances and debit-penetration slides now use its share drafts, where before they used
nothing or crashed.**

### 2026-09-14 — the MM extractor stops charting a blank Key Trends month as $0

**`extract_base_gen.py` turned a blank month into zero, silently.** It read each Key Trends
MM month as `round(spend.get(m, 0) or 0, 2)` and the card-holding count as
`(tot or 0) - (non or 0)`, so a month with no figures became $0 spend and zero
cardholders — a collapse on the Debit Card Swipes & Spend chart that nothing flagged. It
never crashed, which is why it went unseen; the SM extractor's version of the same read
crashed on 1657 and was fixed first (Aaron: "fix the extract_base_gen zeroing too").

- **One definition for both extractors.** `base_guard.key_trends` builds the 36-month
  series with a blank kept as None and its month listed, and `base_guard.data_issue`
  writes the POSSIBLE DATA ISSUE message. `base_tab_extract.py` now uses both instead of
  its own copy.
- **Same order as SM:** the unevaluated-workbook guard first, then any blank month stops
  the run with the workbook and months named and no `base.json` written.
- `extract_base_gen.py` is now import-safe (`main()`), with `extract()` and
  `dco_eligible()` testable directly; its output is otherwise unchanged.

`tests/test_extract_base_gen.py` pins None-not-zero, the data-issue exit, an uncalculated
MM workbook named as such, a populated workbook still extracting with its DCO, and that
neither extractor defaults a blank month any more.

### 2026-09-14 — SM builds had not been reading their DCO since the inputs were sorted

**Every SM (Monthly Summary) client has built without its DCO since 2026-09-09.**
`build_month.build_client` looked for the DCO with `glob(os.path.join(str(REPORTS), …))`.
`REPORTS` became a LIST of per-kind folders when Inputs were sorted by kind, and the string
of a list is not a folder, so the pattern matched nothing and `base_tab_extract` ran with no
DCO argument. Nothing failed — the DCO is optional to the extractor — so it went unseen:
1038 Sugar River's three staged builds on 2026-09-14 all carry `dco_eligible: null`. Found
while preparing staged ARS builds for every CSM's clients. No slide figure moves (the deck's
ARS eligibility comes from the ODD); the DCO's `Eligible ARS Accounts` now reaches
`base.json` again.

`build_month.dco_file()` searches every report folder, the same shape as `ars_workbook()`.
`tests/test_build_month_inputs.py` pins the multi-folder lookup, the period match, the
legacy folder, and that `build_client` no longer joins a pattern onto a list.

### 2026-09-14 — a blank Key Trends month is called out as a possible data issue, not a crash

**1657 Marine Credit Union's ARS extraction crashed, and the crash hid the real problem.**
`base_tab_extract.py` read each Key Trends month with `round(spend.get(m, 0), 2)`, which
defaults only a month that is ABSENT; a blank cell came back as None and raised
TypeError. The crash came before `base_guard`, so the performance page showed a Python
traceback for 1657 when the workbook was simply never calculated — one month, dated Sep
2007 (the template's), with no revenue: the same shape as 1192 Ascend and 1673
Neighborhood, which the guard did name (Aaron: "that should be called out as a possible
data issue").

- **Blank is None, never zero.** A blank spend or account cell now extracts as None and
  its month is listed in `key_trends_blank`; the old default would have charted a gap as
  $0 spend had the cell been absent rather than blank.
- **The guard runs first,** so an uncalculated workbook — the likeliest cause — is named
  as UNEVALUATED WORKBOOK with the Excel fix. 1657 now reports exactly that.
- **Any blank month left over stops the run** with `POSSIBLE DATA ISSUE: <workbook> has no
  Key Trends spend or card-holding figures for N of its last M month(s) (<months>)`,
  nothing extracted, so neither the deck builder nor the page receives a gap as data.
- The script is now import-safe (`main()`), so `extract()` is tested directly.

`tests/test_base_tab_extract.py` pins the None-not-zero extraction, the data-issue exit
(no traceback, workbook and month named), 1657's template shape reported as unevaluated,
and that a fully populated workbook still extracts.

### 2026-09-14 — the workflow page describes Outputs by CSM

**`workflow.html` now says decks go to `Outputs/<CSM name>/`**, where it used to say one flat
folder. The decks moved there the same day. The page's Outputs step, its "Writes" path and the
folder map follow the move, and the map names `_Unassigned/` for a client with no CSM. The
daily refresh does not republish this page, so the page was republished by hand.

### 2026-09-14 — the performance page finds decks in per-CSM Outputs folders

**`refresh_performance_dashboard.decks_and_sent` reads built decks through
`rpe_env.output_decks()` when rpe_env has it.** `Outputs/` is moving from one flat folder to
`Outputs/<CSM name>/` at Aaron's request. `output_decks` reads both layouts and never
`Archive/`. Before the helper exists, the refresh uses the old flat glob, which gives the same
answer. So the page's Deck and Sent columns stay right on both sides of the move. A test
covers a deck in a CSM folder with the helper, and the flat folder without it.

### 2026-09-14 — the Clients filter row folds

**The Clients row on the performance page is collapsible** (Aaron: "make the Clients filter
collapsible"). Across every CSM it runs to about ninety chips.
- **Closed by default**, and each viewer's open or closed choice is remembered.
- **The All chip stays visible**, beside a toggle. Closed, the toggle says how far the row
  is narrowed: "Show 85 clients", or "Show clients (3 of 85 selected)".
- **Unchanged:** narrowing works the same. The CSM and product rows still limit which clients
  the page shows.

### 2026-09-14 — ARS revenue to CSI on the performance page; totals before the month

**The two ARS callouts are replaced by ARS revenue to CSI** (Aaron: "we don't need
callouts for ARS incremental prof and ARS incremental revenue. I would like to see ARS
Revenue to CSI for the currently completed month (that's the ARS expense in the
workbook)").
- **The figure.** Executive Financials' "Total Costs" in the current-month Actual column,
  shown as a positive number. The ARS extractors emit it as `cur_costs`, and
  `refresh_performance_dashboard.csi_revenue` carries it.
- **Where it shows.** A summary tile, summed across the selection, and a "Revenue to CSI,
  current month" column in the ARS table.
- **What it includes.** For 2026.09, 1204 (Lift Matrix) reads $6,077.98 and 1038 (Monthly
  Summary) $5,734.80, both the Program Fee alone. A Monthly Summary workbook's Total Costs
  also counts spot and usage mail and points in months they occur.

**A total column now comes before its last-month figure** ("always show the big number
first"):
- **ARS:** Revenue PTD and Profit PTD come before the current month's incremental revenue.
- **ICS:** PTD and YTD come before last month, its goal and % of goal, and the YTD tile
  leads the last-month tile.
- **MRPC:** trailing-12 enrollments come before last month's.
- **Already total-first:** CashPlease and the Client overview.

### 2026-09-14 — trend lines on the performance page show complete months only

**The ICS, MRPC and CashPlease sparklines no longer end on a month in progress** (Aaron:
"on the trend line for ICS, MRPC and CashPlease don't include incomplete months"). A trend
that ends on a partial month reads as a fall-off. In 2026.09, nine ICS trends ended on 13
days of September.

- **ICS.** The VIP trend's month-to-date point, which VIP flags `partial_last`, is dropped
  from the referrals, goal and months series (`complete_trend`). The column header now reads
  "Referrals by month", because the trend is no longer a fixed 15 months.
- **MRPC and CashPlease.** A month on or after the month the weekly report was generated is
  dropped (`complete_months`). The 2026-09-13 weeklies already ended in August, so today
  that removes nothing, but it stops a mid-month weekly from adding a partial month. MRPC's
  "last month" and "trailing 12" columns are read from the same series, so they count
  complete months too.

Year-to-date, program-to-date and CashPlease's trailing-12 loans still come from VIP and the
CashPlease extractor, unchanged.

### 2026-09-14 — every table on the performance page sorts by its columns

**The product sections' tables sort, as the Build readiness table already did** (Aaron: "i
want to be able to sort the product columns too, such as by loss rate"). This covers Client
overview, ARS, ICS, MRPC and CashPlease. Every column that carries a value has a sort
button; the sparkline trend columns do not.
- **Clicks.** A numeric column sorts highest first on the first click, so CashPlease's
  charge-off rate is one click. A text column sorts A to Z. The next click reverses, and the
  third clears the sort.
- **Scope.** Each section keeps its own sort, remembered per viewer.
- **Values.** Each cell is sorted by what it shows (`$1.6M`, `−$1.2M`, `6.85%`, `5.75 : 1`,
  `Aug 2026`), never by its sub-label.
- **Rows that don't move.** A client with no figures and the CashPlease all-clients peer row
  stay at the bottom in both directions.

### 2026-09-14 — a Client overview section on the performance page, from each ODD extract

**The page opens with a Client overview.** Aaron asked for "total open checking accounts,
total business, total personal, 3-month average swipes per month for personal, 3-month
average NSF/OD items per month, 12-month personal openings, 12-month personal closings".
It has a ranked bar of open checking accounts, one table row per client, and a summary tile.
The section is client-level, so it shows whatever products are selected.

**Every figure uses the decks' definitions**, read by `scripts/perf_overview.py` through
`build/ars_pipeline/odd_rows`:

| Figure | Definition |
| --- | --- |
| Open checking | Accounts whose status is not closed: the Product Mix slide's "Excl. Closed" book, so the totals match that slide. Business and personal come from `Business?`; a blank is neither and counts in the total only. |
| Personal swipes | Signature plus PIN counts on personal accounts over the extract's last three months, averaged. |
| NSF/OD | Item counts, never dollars, on every account over the same three months. |
| Openings and closings | Personal `Date Opened` / `Date Closed` in the twelve months ending with the extract's month: `metrics_gen`'s openings-vs-closures rule, over 12 months instead of 24. |

**Each row names the month its extract describes and is tagged when that is older than the
cycle's.** `Inputs/ODDD/<id>_ODDD.zip` has no period in its name, so last month's file looks
like this month's. For 2026.09 a current extract ends in Aug 2026.

Reading 83 extracts (3.9 GB) over the share is slow, so each result is cached in
`Build Artifacts/perf_dashboard/odd/<id>.json`, keyed on the zip's size and time. A refresh
reads only an extract that changed. A client with no extract (1002 Republic, 1095 Landmark
Bank) says so. Tests: `tests/test_perf_overview.py`, plus new cases in
`tests/test_refresh_performance_dashboard.py`.

**The open counts are checked against the Product Mix slide's own extractor.** Run on the
real 2026.09 extracts, `product_mix_slide.extract_product_mix` and the overview agree exactly
for 1204 (19,933 open: 3,403 business, 16,465 personal, 65 unmarked). They also agree for
1549 (31,949: 4,155 / 27,794 / 0), whose core leaves `Stat Desc` blank.
`test_open_counts_match_the_product_mix_slide` pins that agreement, so the two cannot drift.

The first pass read 78 extracts in 571 s. Seventy-seven end in Aug 2026. **1195 KEMBA CU's
extract ends in Apr 2026** even though it was filed as 2026.09, and the page tags its row.

### 2026-09-14 — filter chip colors: white for a whole row, blue for a pick, gray for off

**The filter chips' three states now read white, blue and light gray** (Aaron: "go white for
all selected, blue for individual selections, and add a slight gray for unselected
options"). This replaces the green, blue and white set from earlier the same day.

| State | Chip |
| --- | --- |
| Whole row selected | White, hairline border |
| Selected | Blue `#245C8C` |
| Not selected | Light gray `#E9EDF1` |

Unselected filter chips have their own `--chip-off` tokens, so the white input chips in the
Build readiness table are unchanged. The dark theme has the same three steps, and the key
under the filters follows the tokens.

### 2026-09-14 — client marks removed from the performance page

**The per-client marks on the ranked bars are gone** (Aaron: "remove the favicon idea. Not
enough clients have them."). A mark could be cut from their own logo for only 20 of the 85
clients. The other 65 showed initials, and 58 of those would each have needed a hand-made
square mark.

Removed: `scripts/perf_marks.py`, its tests, the dataset's `marks` key, and the page's mark
tiles. The bars render as they did before the marks. The three-state filter chips and the
empty-selection filters stay, and so does the duplicate top-level name test, which guards the
page script rather than the marks. The marks cache in `Build Artifacts/perf_dashboard/marks/`
is no longer read.

### 2026-09-14 — client marks on the performance page's bars, and filter chips that show their state

**Each name on the four ranked bar charts has the client's mark beside it** (Aaron picked
concept A from four drawn on the real ARS bars). Client logos are wordmarks far more often
than square icons, so `scripts/perf_marks.py` chooses a mark in this order:
1. A curated `Inputs/Logos/<id>_mark.png`, which always wins.
2. The icon leading the logo, when a clear gap sets it apart from the wordmark.
3. The whole logo, when it is no wider than 1.6:1.
4. Otherwise, the client's initials.

A pure wordmark is never cropped, because a crop of its left edge cuts a letter in half.
The marks are part of the dataset, so a new or curated logo moves the hash and republishes
the page. They are cached by logo file size and time in
`Build Artifacts/perf_dashboard/marks/`. The first run over 85 clients took about three
minutes.

On 2026-09-14 the result was 11 icons, 9 whole logos and 65 monograms. 58 of those 65 have
a logo on file, and each refresh lists them by id: they need a curated square mark.

**The filter chips show three states** (Aaron: "use a 3rd color for when all of a row is
selected, blue for on, white for off"):
- Green (`#E3F1EA`): the whole row is selected.
- Blue (`#245C8C`): selected.
- White: not selected.

Before, a whole-row selection left every chip unmarked, so "all" and "none" looked the same.
Each row now leads with an All chip, which replaces the "All CSMs / products / clients" links
at the right, and a key under the filters names the three colors. Green was picked because
the product chips already carry the program colors. Tests: `tests/test_perf_marks.py`, plus
new template cases in `tests/test_refresh_performance_dashboard.py`.

**A top-level name declared twice in the page's script now fails the suite.** The marks
were first added as `const MARKS` beside Mark sent's `let MARKS`. That is a SyntaxError,
and the page rendered only its filter rows, while every string check in the tests still
passed. The preview caught it before it was published.
`test_template_declares_no_top_level_name_twice` reads the script's column-0
declarations.

### 2026-09-14 — the performance page's filters allow an empty selection

**Any chip can be clicked off, including the last one in its row** (Aaron: "allow zero
selection for CSM, client, etc at the top"). The CSM, product and client rows each used to
keep at least one chip selected. With a row empty, the page says which filter is empty and
points to its All link, instead of showing a blank page. An empty selection is saved as
empty and survives a reload, while "all" is still saved as all.

The page used to reset an empty client selection to all on every render. That reset was
meant for a stale saved selection, so it now runs once, on load, and only when saved
clients match none of the saved CSMs. `tests/test_refresh_performance_dashboard.py` pins
all three rows and the reload.

### 2026-09-14 — the performance page lists every current client and links the workflow

**The page shows all current clients across the five CSMs** (Aaron: "i want the artifact
to show ALL current clients, and then be able to filter by CSM"). It lists the
`clients.md` roster plus every client with reports filed on `Velocity_clientreports` for
the newest month at or before the cycle, except the clients `clients.md` marks as stopped.
1437 Canandaigua is one of those and still lands reports. `scripts/perf_clients.py` reads
the share, and its last answer is kept in `Build Artifacts/perf_dashboard/current.json` for
mornings off the VPN.

**Programs for a client `clients.md` does not list are inferred from that month's files**
(Aaron chose this over recording all 81 current clients in `clients.md`):

| File on hand | Program |
| --- | --- |
| ARS workbook on the share | ARS |
| VIP ICS sheet | ICS |
| MRPCPM analysis, or a tab in the MRPC weekly | MRPC |
| Tab in the CashPlease weekly | CP |

A DCO alone implies nothing. The page tags those clients "from data" and lists a client
with no program data this month under all products. The ARS format (Lift Matrix or Monthly
Summary) is read off the workbook, the same test that set `clients.md`'s Path column. This
is for reading only: `clients.md` still decides what gets built. On 2026-09-14 only 1 of
the 35 non-roster ARS workbooks on the share had been copied to `Inputs`, so the rest show
"not yet copied" until the daily copy picks them up.

**A click on a product chip now shows only that product**, the same as the CSM and client
chips. It used to remove the clicked product from the selection.

**A saved filter of "all" now stays "all".** The page remembered each filter as the exact
list selected, so "all" was saved as that day's 20 clients. The first all-clients build
therefore opened on Aaron's 20 and hid the other 65. "All" is now saved as all, under a new
storage key, so selections saved the old way are ignored.

**The page links a workflow page**, `scripts/perf_workflow.html`, published as
`workflow.html` in the same artifact. It covers:
- the cycle from files landing to a deck recorded as sent
- each program's inputs, and what happens when one is missing
- where everything lives
- what stops a deck
- the filename convention

The daily refresh republishes only the main page, so a change to the workflow page has to
be published by hand. Tests: `tests/test_perf_clients.py`, plus new cases in
`tests/test_refresh_performance_dashboard.py`.

### 2026-09-14 — the archive keeps one deck per period and kind, in a folder per client

**`Outputs/Archive/` had become a flat pile of every rebuild.** 97 files for 15 clients,
nine copies of 1038's September ARS deck among them — each rebuild during the month
archived the one before (Aaron: "in the archive, only keep the last deck created for each
individual period per client, and organize them into folders per client").

- **A folder per client.** `promote_month` archives a superseded deck to
  `Archive/<id> <client>/`. The id is the key: an existing folder for that id is reused
  whatever its name, because delivery names differ by program ("Marine FCU" on the
  Executive Review, "Marine Federal Credit Union" on the CashPlease module).
- **The newest deck of each kind per period is kept** — kind being the program tags, so a
  client's September CP module and its September ICS-CP deck both survive (Aaron's choice
  over one deck per period). Newest is the deck's own build time.
- **Older ones are moved, never deleted**, to
  `Archive/_older decks - delete after review/<id> <client>/`. The share has no Recycle
  Bin, so emptying that folder is a person's decision. The tidy runs only after a
  successful delivery, so it can never cost one.
- **PDFs never move** — they are exported by hand before sending.
- A failed promotion still leaves Outputs as it found it, and now also removes a client
  folder it had just created.

The existing archive was reorganised the same way, through the same functions.
`tests/test_promote_month.py` pins the name parsing, the client folder, folder reuse,
the keep rule with PDFs left alone, and the tidy after delivery.

### 2026-09-14 — the pipeline root moved to the CSM_Reporting share

**`RPE_DATA_ROOT` is `\\PADMIS105\Velocity_company\CSM_Reporting`** (Aaron: "we have a new
folder for imports, exports, and other project files … repoint everything"). With the ODD,
DCO and workbook copy now covering all five CSMs' books, a root on one laptop was the wrong
home for it. No code path changed: every reader already resolves through `rpe_env`, so the
move was a copy and one `.env` line — the reason the path was never hardcoded.

- **Copied, then proven, then switched.** A full robocopy (1,926 files, 2.365 GB, 0
  failures), a SHA-256 comparison of every file, and a catch-up pass for the files other
  sessions wrote during the copy (247 more, 0 failures) — ICS Charts workbooks re-saved at
  15:38, 67 CSM client logos, and the 16:00 performance-page rebuild including its
  `published_hash`, so the 08:30 refresh does not republish an unchanged page. Nothing on
  either side was deleted.
- **The old local root is retired, not deleted.** `C:\Data Pipelines\RPE Pipeline` was
  renamed to `C:\Data Pipelines\RPE Pipeline (retired 2026-09-14 - use CSM_Reporting)`
  after verification (all 2,050 files intact), so nothing can keep writing to a copy
  nobody reads; the share is the one copy.
- **The share needs the VPN off-site**, the same as the source shares it copies from.
- `.env.example`, the example path in `rpe_env`'s "RPE_DATA_ROOT is not set" message, and
  CLAUDE.md **File locations** name the share.

### 2026-09-14 — the ODD copy pulls from all five CSMs' folders

**The daily watch only ever looked in Aaron's ODD folder.** The data team lands each
CSM's extracts in that CSM's own folder on `Velocity_company`, so the 08:00 copy and the
delivery dashboard's "has it landed" check saw one book out of five (Aaron: "update the
ODD copy to pull from all 5 CSM folders"). `deck_status.SRC_ODDD` now lists all five as
`CSM=path` entries — Aaron Burgard, Daniel Wood, Gregg Miller, James Gilmore, Jordan
Berkowitz — overridable with `RPE_SRC_ODDD` in the same format; a bare path still works.

- **Five naming conventions for one month.** `2026.09 Sep` (Aaron), `2026.09` (James),
  `September, 2026` (Jordan, Gregg), `090126` (Dan, the first of the month).
  `deck_status.odd_folder_period` reads all four and nothing else, so `Archive`, `2025`
  or a folder named after a client's core migration is skipped rather than guessed at.
  The old code globbed `<period>*`, which matched only Aaron's naming.
- **Every client's files, not only the roster's.** `copy_plan(..., stopped=...)` copies
  ODD extracts, DCOs, ARS workbooks, MRPCPM analyses and ICS workbooks for any client on
  the shares — every CSM's book (Aaron: "update the DCO and workbook copy to pull all
  clients too") — except the clients `clients.md` marks as stopped (1437, 1174, 1658
  today). The reports share was already scanned across all five account-manager folders;
  only the roster filter kept the other books out. With `clients.md` unreadable the
  stopped set is unknown and the copy falls back to the roster rule, which copies nothing
  rather than everything.
- **A client in two folders.** Same client and month in two CSM folders (a handover —
  1808 Summit Choice sits in both James's and Jordan's) takes the more recent write.
- **One unreachable folder is off VPN.** The run exits 2 and saves nothing, and the
  report names which folder failed. Scanning the four that answered would have reported
  every extract in the fifth as gone.
- The report tags each ODD line with the CSM folder it came from.

The first run after this lists the other four CSMs' extracts as new once; that is the
inventory catching up, not a landing. `tests/test_watch_sources.py` pins the four
namings, the named/bare root parsing, the tagged scan, the unreachable-folder rule, the
stopped-client exclusion and the tie-break; `tests/test_deck_status.py` follows the
month-folder lookup.

### 2026-09-14 — filter the performance page by CSM

**The RPE Client Performance page has a CSM filter at the top** (Aaron: "the RPE artifact
is going to need the ability to filter by CSM at the top"), above Products and Clients.
It uses the same chips: from "All CSMs" a click isolates one CSM, later clicks add or
remove, and shift-click isolates. The Clients row then offers only that CSM's clients,
the summary tiles and every section follow, and the choice is remembered per viewer.
Changing CSM resets the client selection, so a client picked under one CSM cannot leave
another CSM's view empty.

**Where the CSM comes from.** The data team files every client's reports under
`Velocity_clientreports\<period>\<Account Manager>\`, so the refresh reads that folder as
the client's CSM. It uses the newest of the last two months at or before the cycle: a
client moved between CSMs follows the move (1805 went from Matt Lindsey in 2026.08 to
Jordan Berkowitz in 2026.09), and a client whose files have not landed yet keeps last
month's CSM. The share needs the VPN, so the last answer read is kept in
`Build Artifacts/perf_dashboard/csm.json`. Without it, a morning off the VPN would blank
every CSM, move the content hash and republish.

**When the share names nobody**, the refresh uses the new `CSM` column of the CashPlease
roster in `clients.md`, then the CSM on the client's CashPlease settings record. The column
exists for the five CashPlease-only clients (1131, 1564, 1750, 1770, 1771): their reports
never land on the share and none has a settings record, so the first build showed them as
Unassigned. If the share and the column disagree, the share wins and the refresh logs the
disagreement, because the share is kept by the people who assign clients. **A client
nothing names is shown as Unassigned, never given a default CSM**: a guessed CSM hides the
client from the CSM who actually owns it. As of 2026.09 every roster client resolves to
Aaron Burgard.

The refresh now reads the roster through `build_month.read_cashplease_roster` (columns by
header name) instead of its own parser. That parser took Build from the third cell, so
the new column would have dropped every CashPlease client from the page. Who appears on
the page is still decided by `clients.md`, so it shows only Aaron's clients; other CSMs'
clients appear only if they are added there.

### 2026-09-14 — undo a recorded send from the performance page, with a confirming click

**A recorded send can now be undone on the page** (Aaron: "click the Sent button to undo
the recorded date, add a click to confirm"). The sent date in the Build readiness table is a
button: one click turns it into "Undo send?", a second click within five seconds removes
the record, and a click elsewhere or Esc keeps it. The old "undo" link only reached sends
recorded on the page and not yet folded into `deliveries.json`; a send already in the log
showed as plain text and could not be undone at all.

**An undo is a row, never a deletion.** The page cannot change `deliveries.json`, and a send
recorded on the page may already have been folded in by the time someone undoes it — so
deleting the page's row would have left the log's copy standing and the date would come back
at the next refresh. The page now writes `{"unsent": true, "undo_of": "<date>"}`, and Mark
sent after an undo writes a send row carrying `undo_of` too. `merge_sent` applies either one
only while `deliveries.json` still holds exactly that date: an undo removes the entry, a send
replaces it, and a row naming any other date is reported as stale and left alone, so an
older undo can never erase a send recorded after it. "deliveries.json wins" still holds for
every plain row. The page reads its own rows by the same rule, so it shows the result
before the refresh does. `tests/test_refresh_performance_dashboard.py` pins removal,
replacement, the stale cases and malformed undo rows; the `rpe-dashboard-refresh` task
instructions describe the exception.

### 2026-09-14 — the Mailing Response Summary lists a mailing still in progress

**A mailing whose response is not yet measured was on no slide.** 1549 Wellworth's
September deck showed "The program's first mailing" — Jun 2026 — while its ODD extract
(Mar26–Aug26) also carries an Aug 2026 mailing on 9,643 accounts with `Aug26 Resp`
blank for every one. `metrics_gen` keeps only "mature" mailings (those with a following
month of activity), which is right for every rate, and dropped the rest without a word.
The workbook does not list it either: its Mail Response Summary MM ("August 2026 Data")
carries Jun 2026 only (Aaron: "if the client has a mailing in process but incomplete,
list it here").

`metrics_gen` now emits `mail_in_progress` — each mailing with no following month and at
least one offer, counted the way the completed rows count (personal accounts carrying a
`<Mon> Mail` value). The builder lists it first as "<Mon YYYY> (in progress)" with the
offers sent and "Pending" in every response column — never a blank or 0.0%, which would
read as a drop that drew nobody. It never enters a rate or the trailing total. The
subtitle names it ("The program's first completed mailing; Aug 2026 still in progress.")
and the notes say why the figures are pending. The label does not match "Mon YYYY", so
`mailing_table_findings` still compares only completed mailings with the count the deck
states. When twelve completed mailings, the total and an in-progress row exceed the
template's 14 rows, rows are added and the table held to the template rows' 5.60in, so
it ends at 7.10in exactly as the delivered 12-mailing decks do (checked in a PowerPoint
render of 1204: fifteen rows, total last, nothing clipped).

**It also lists a mailing dated AFTER the extract's last month.** Five extracts ending
Aug26 already carry populated `Sep26 Mail` offers with no response (1204, 1509, 1537,
1539, 1676), and by the same rule those read "Sep 2026 (in progress)". Of the delivered
2026.09 decks, eight would change: 1038, 1549, 1705 (Aug 2026) and those five (Sep 2026).
Only 1549 has been rebuilt (staged; gate PASS, slide 13 the only difference).

`tests/test_metrics_gen.py` adds a mailing to the synthetic ODD's last month and asserts
it is listed as in progress with the completed rows and total unchanged.

### 2026-09-14 — CashPlease Program Settings in the review, and pills that wrap

**The CashPlease section gains a Program Settings slide** for a client whose production
settings are on file (Aaron: "add those to the CashPlease section of the RPE review").
The record is the client's row on the CashPlease page of the Velocity Product Settings
Power BI app, first pulled for 1632 WesBanco on 2026-09-14 for their ops meeting. It now
lives at `Inputs/Product Settings/<id>_cp_settings.json` (a copy of
`C:\Data Pipelines\Product Settings\Inputs\1632 WesBanco\wesbanco_cp_settings.json`),
resolved by `rpe_env.cp_settings_file` — never read from the other project's tree.
`build_cashplease.py` passes it to `build_cp_gen.py`, which places the slide after the
Program Overview: loan terms beside eligibility and controls, and a program strip. The
module goes from ten slides to eleven and the combined section from five to six.

- **Production values only.** The ops deck's orange recommendations (a 120-day waiting
  period, a $150 first loan) are agenda items for that meeting, not settings, and are
  not on this slide.
- **Internal fields never reach the file.** The record carries Loan Notes ("Declined
  Best Practices…"), contract type, core, CSM, pricing and the regulator address.
  Speaker notes ship inside the `.pptx`, so the builder reads only the fields named in
  `SETTINGS_SHOWN`; a field added to the app later is ignored by construction.
  `tests/test_cp_settings_slide.py` plants sentinel values in every internal field and
  fails if any reaches the slide or its notes.
- **A record for another client or program is refused** (`Customer #`, `Record Type`),
  and so is one with no `_source`, since the slide's source note is built from it.
- **No record, no slide.** Seven of the eight CashPlease clients have no settings file
  yet. A slide of "Not recorded" would say nothing, so they keep the five-slide section
  and `build_cashplease.py` lists them by name at the end of every run.
- `Product Settings/` is excluded from `report_dirs()` and the watch's copy/prune scan
  (`rpe_env.NOT_SCANNED_KINDS`), like `ODDD/`: it is resolved by exact path.

**Every September CashPlease and ICS date pill wraps to two lines, and nothing said so.**
The settings slide's first pill, "As of September 14, 2026", rendered on two lines in
PowerPoint. The validator missed it because the pill box holds two lines and nothing
sits beneath it, and `single_line_overflow_findings` only fails a spill onto other text.
Worse, PowerPoint wraps before the measured text reaches the box: twelve pills rendered
through PowerPoint held one line at up to 0.940 of the usable width and took two from
0.974 — the settings pill was 0.993, "PTD · September 4, 2026" is 0.984.
`pill_wrap_findings` now REPORTS any pill past 0.955 (`PILL_WRAP_RATIO`). It is REVIEW,
not FAIL, because the fix is a cross-program style decision (a shorter date or a wider
pill) and is not made here. The settings pill uses the short month ("As of Sep 14, 2026").

### 2026-09-14 — the first four-program deck: a cover that overflowed, and a client with two names

Marine FCU's September deck is the first combined Executive Review with all four programs
(ARS-ICS-MRPC-CP), assembled alongside ICS-CP decks for 1632 WesBanco and 1734 Altamaha
(Aaron). WesBanco and Altamaha passed the gate; Marine failed it three times, on two
defects no earlier combined deck could reach.

**The cover listed four products in a box that seats three.** `set_title_products` adds a
paragraph per program at the shell's 40pt, and the product box is 2.0" deep — exactly three
lines. Four ran about 2.7" deep and drew over "Marine FCU / Executive Review" beneath them.
`_fit_product_lines` now shrinks the product lines only when they cannot fit at their own
size, so two- and three-product covers keep exactly 40pt and no existing deck changes.

**The leak checks treated one client's two names as two clients.** Marine FCU (1539) is the
old reference client, so both "Marine FCU" and "Marine Federal Credit Union" are on
`validate_deck.REFERENCE_CLIENTS`. A name is skipped only when it appears on the deck's own
filename or cover — and the cover says "Marine FCU" while the CashPlease workbook, and so
the CashPlease section's source notes, say "Marine Federal Credit Union". Slides 42 and 46
failed as "a different client's provenance". `REFERENCE_ALIASES` now groups the two names,
and both `reference_leak_findings` and `source_note_findings` count a name as the deck's own
when any name in its group is. A genuinely different client still fails.

`tests/test_combined_cover_and_names.py` pins both: four products fit, two and three keep
40pt, the alias works in both directions, and True Sky's deck naming Marine is still a leak.

### 2026-09-14 — the Build readiness table sorts by every column

Every column on the performance page's Build readiness section is now sortable (Aaron):
click a header for ascending, again for descending, a third time to clear back to client
id order. The choice is remembered per viewer in `localStorage`; a stored value the page
does not recognise is ignored. Headers are buttons inside the `th`, so they work from the
keyboard and carry `aria-sort`, and focus returns to the clicked header after re-render.

Each column sorts on what it means, not on its markup: **Ready** puts ready before blocked;
**Inputs** orders by missing, then stale, then unconfirmed inputs; **Deck** puts this
period's build first; **Sent** puts decks still to send before sent ones. A row the column
does not apply to — no readiness check (the CashPlease-only clients), or no deck to send —
stays at the bottom in both directions, so flipping a sort never floods the top with blanks.
Ties fall back to client name in a fixed direction so equal rows do not reshuffle.

**Caught in testing:** Deck first treated "no deck" as not-applicable. Every built deck
ties, so the unbuilt rows sat at the bottom both ways and descending rendered exactly like
ascending — the click looked broken. No deck is the state that column exists to show, so it
is now the last rank and descending puts it first.

### 2026-09-11 — revenue under $1M reads in K, and promote_month stops being a trap

**Five copies of the money rule, and they disagreed** (Aaron: "when revenue is less than
$1M, state it in K"). The ICS Present Value callout divided by a million unconditionally
and printed **$0.83M** for $830K; `ics_charts_gen`'s donut centre fell back to a full
`$830,000`; `build_ars_gen` carried both an unconditional `m2()` and a correct `_fmtk` two
hundred lines apart; `build_mrpc_gen` wrote life-of-program in M whatever its size. All
now call `brand.usd_compact` — `$1.24M` at a million and up, `$830K` below, and the whole
figure under a thousand because "$1K" for $950 is worse than the characters it saves.
MRPC's "$95.6K in 2025" keeps its decimal: it already states K, and the rule is about the
unit, not the precision.

**The fifth copy was in the VALIDATOR, and it failed a correct deck.** `extract_findings`
formatted the EXPECTED `ltd_profit` with its own `/1e6:.2f}M` and looked for it verbatim
in the deck. The moment the builders started writing $830K the cross-check went hunting
for "$0.83M" and the golden deck went red. An expected value formatted differently from
the rendered one is not a check. `tests/test_brand.py` now scans all five files — code
only, since it was flagging its own explanatory comment.

**promote_month: two failures and the trap underneath them.**

A deck open in PowerPoint raised PermissionError, **aborted the whole run at the first
client**, and left that client's hand-made PDF in `Archive/` while its superseded deck
stayed live. Promotion is now all-or-nothing per client — anything already moved is put
back, and the orphan `shutil.move` leaves behind when it falls back to copy-then-delete is
removed — and a blocked client is REPORTED while the run continues, with the exit code
carrying it.

Underneath both: **`main()` resolved its destination from `rpe_env.outputs()` and ignored
its caller.** A test that built a temp `Outputs/` and passed the staging dir to `main()`
wrote into the LIVE folder and delivered 1204's deck under 1038's filename. Recovered from
`Outputs/Archive/` and rebuilt; nothing was sent, and an audit of every delivered 2026.09
deck's title-slide client against its filename found no other mismatch. The destination is
a `--outputs` parameter now, and `tests/test_promote_month.py` re-runs that exact scenario
and asserts the real folder is untouched.

That is three defects in one module from the same root: it reached for globals instead of
taking parameters. Import-safe, parameterised, and covered now.

**PDFs in `Outputs/` are deliberate** (Aaron, 2026-09-11): they are exported by hand before
sending, so they are not strays to clean up. `promote_month` archiving them alongside the
deck is correct — a PDF of a superseded deck is stale — and that move is now part of the
same all-or-nothing group.

### 2026-09-11 — promote_month could not see a colour change, and skipped the delivery

**The navy Summit banner was silently not delivered.** True Sky was rebuilt with the
recoloured banner, passed the gate at 0 FAIL, and `promote_month` reported it
`unchanged` and left the old deck in `Outputs/`. `same()` compared slide TEXT and IMAGE
blobs only — a shape's FILL is neither, so a rebuild whose only change is a colour was
indistinguishable from no rebuild at all. A check that cannot see the change reports
success, which is the failure mode this pipeline keeps paying for.

`same()` now also compares how the shapes LOOK: kind, box, solid fill and line colour,
per shape per slide. All of it is derived from shape properties, so it stays stable
across rebuilds the way zip bytes are not — and zip bytes are still deliberately NOT
compared, because they differ on every build and comparing them would re-archive an
unchanged deck every run, which is the thing `same()` exists to prevent.

Verified three ways before delivering: navy vs delivered -> False (the change is seen),
each deck against itself -> True (no false positives).

### 2026-09-11 — the ODD accessors, measured: metrics_gen ~10%, and where the time really is

`odd_rows` accessors run tens of millions of times per client, so the obvious per-row
waste was removed: `mkey` memoised (185,000 `strptime` calls for about three dozen
distinct month tokens), the constant columns (`Business?`, `Debit?`, `Stat Desc`) bound
once instead of hashed per row, the per-month column indices cached so `swipes`/`spend`/
`nsf` stop building `"Jul26 Sig #"` on every call, and `fnum` trying `float()` on the raw
cell first — it already tolerates whitespace and raises on exactly the inputs the
strip/replace path exists for.

**Measured, not assumed.** `metrics_gen` 9179 -> 8262ms on 1676 and 16424 -> 15892ms on
1539 (means of 2-3 runs): 3-10%. **`oddd_optimize` did not change at all** — it has its
own classifiers and barely touches the shared accessors. Every metric is byte-identical:
the `metrics.json` for 1038, 1204, 1676 and 1539 match their pre-change SHA-256 exactly.

**A hypothesis that measured worse, and was removed.** `resp()`/`mail()` accessors were
added to kill the `g(r, f"{m} Resp")` f-string in the hottest loop — 28 call sites. They
made it SLOWER: one call plus a string build became two calls, and 1676 went 8882ms with
them to 8262ms without. Reverted.

**Where the build time actually is** (1676, ~70s): `build_ars_gen` 18.8s, `charts_gen`
11.7s, `oddd_optimize` 10.0s, `metrics_gen` 8.9s, the rest in the extractors, the ICS
build and assembly. The ODD stages are 27% of the build and the largest single stage
touches no ODD row, so this whole change is worth about 1% end to end. Profile the chain
before optimising a stage of it.

**The one structural ODD lever left, NOT taken.** Building the retained row store costs
~3.0s and reloading the same store costs 0.35s, and three processes each build it
independently — about 5s per ARS client. If that cache is ever built it must be
CONTENT-ADDRESSED, keyed on a hash of the zip (~0.2s for 49 MB) and never on path+mtime:
a cache that can go stale manufactures precisely the stale-ODD failure this pipeline has
shipped before, where the wrong month validates perfectly because it is internally
consistent.

`tests/test_odd_rows.py` gains 58 equivalence cases pinning every optimised accessor
against a literal transcription of the original — 24 cell shapes against every column,
the month helpers, the flags, short rows, empty rows and an empty header map. This is the
vocabulary that drifted across three implementations once; "it still runs" is not the bar.

### 2026-09-11 — build-order audit: a duplicate pass, a stale deck picker, and the Summit gap

**ARS decks were restyled twice.** `build_ars_gen` runs `restyle_fonts` and then its
branding, geometry and layout-fit passes before saving; `build_month` ran `restyle_fonts`
AGAIN on the finished file. Measured on a delivered 49-slide deck the second pass changed
nothing on any slide — a subprocess and a full load/save per ARS client for a no-op — and
it re-applied font roles after `fit_layout` had clamped them. ICS and MRPC never had it,
so ARS was the odd one out. Removed.

**`promote_month` could not pick a CashPlease combined deck.** Its combined-deck test was
three literals — `("ARS-ICS", "ARS-MRPC", "ICS-MRPC")` — written before CashPlease became
the fourth program. An `ICS-CP` deck matched none of them and fell through to the "most
slides wins" tiebreak, which picked the right file for 1632 and 1734 by luck rather than
by rule. `program_tags()` now derives them from the filename convention, and a combined
deck with MORE programs wins, so `ARS-ICS-MRPC-CP` beats `ARS-ICS` when both are staged.

**...and could not be imported, which is why that went unnoticed.** It read `sys.argv[1]`
at module scope and did the whole job there, so importing it RAN it — the hazard CLAUDE.md
names for `metrics_gen`. Nothing could import the module to test `deliverable()`, so the
stale tag list had no test to fail. Restructured behind `main()`.
`tests/test_entry_points.py` now pins the class rather than the instance across all eight
drivers: resolve siblings from `__file__` and never the home directory, no `sys.argv` at
module scope, and a `__main__` guard.

**QA gap — nothing failed a deck advertising a Summit that had already happened.** All
eighteen delivered 2026.09 decks named a Summit eleven days gone.
`summit_slide.summit_period()` warned on stderr, but only when a build called it for a
reporting month, and a warning in a build log is not a gate.
`validate_deck.summit_date_findings` reads the slide in every deck. It is **REVIEW, not
FAIL, deliberately**: a deck built the day before an event is indistinguishable from one
built the day after it ended, and a rebuild of an older period must not be blocked.

**The template shells still carried the Boston slide.** `ars_template.pptx`,
`cashplease_template.pptx` and `multi-product_reference_deck.pptx` were stale on slide 2.
Built decks were correct — the builders replace it from the asset — but the shells are
what the gate validates, and the new rule caught all three. Refreshed through
`insert_summit_after_title`, the same one source the builders use. Baseline re-snapshotted.

**No checks were removed.** Counting findings per rule across eleven decks and templates,
13 of 17 produced zero — which is the PASSING state for a FAIL-level rule on a clean
corpus, not evidence of dead code. Deleting them would delete the checks that keep the
corpus clean.

**Known and NOT changed:** the ARS build streams the ODD three times — `oddd_optimize`
(10s), `metrics_gen` (9s) and `build_ars_gen` again, on True Sky's 49 MB extract out of a
70s build. Consolidating is a real refactor: these were re-implemented standalone once
before and drifted, which is why they now share `odd_rows.py`. It needs a decision, not a
drive-by.

### 2026-09-11 — the Summit slide's date banner is navy

The band behind "Fort Lauderdale, FL · November 4-5, 2026" arrived a medium blue that is
not in the palette (Aaron). It is now `brand.NAVY` (#00274C), read from `build/brand.py`
rather than typed in, so it moves if the palette does. Both runs on it keep their colours
and stay legible: the venue is orange, the date is BACKGROUND_1 (white).

Only the fill changed — no geometry, no text. **Decks were NOT rebuilt** (Aaron: "on the
next run"), so the eighteen delivered 2026.09 decks still carry the blue band and the next
rebuild picks this up.

### 2026-09-11 — the LibreOffice render check is gone; the package check absorbs what it can

**Removed, deliberately** (Aaron): LibreOffice is not going on the build machine, so
`qa_all.py`'s render smoke test — open each deck, convert to PDF, compare the page count
to the slide count — had never once run there. Every gate closed with a banner saying the
one check that proves a deck OPENS had been skipped. A check that cannot run is not a
check; it is a banner. Gone with it: `_find_soffice`, `render_check`, `--no-render` and
both skip banners.

**What it covered that nothing covers now.** Steps 1 and 2 read the deck THROUGH
python-pptx, which cannot see a malformed package — not hypothetical: seven 2026.08 ICS
decks passed at 0 FAIL while being unopenable. So the recoverable half moved into
`validate_deck.package_findings`, which reads the ZIP directly and needs no renderer:

- **any part name written twice.** Exactly the defect produced the same day by cloning the
  Summit slide — relating the asset's image Part carried its partname along, so a deck
  that already held `/ppt/media/image2.png` got the entry twice. The existing checks could
  not see it: they look at SLIDE parts, and these are media.
- **a CRC check on every member**, catching a truncated or corrupt part.

What is NOT recovered is everything past "structurally sound": a deck that opens but
renders wrong, a font that does not resolve, an image that will not decode. CLAUDE.md says
so rather than implying the gate still proves a deck opens, and says to open one deck
before a batch goes to clients.

**The new test found a bug in the new check.** `testzip()` RETURNS the first bad name on a
CRC mismatch but RAISES when a stream will not decompress at all, so a badly corrupted deck
threw `zlib.error` out of the gate — which reads as a broken validator, not a broken deck.
Caught and reported as a FAIL now. `tests/test_validate_deck.py` covers a sound package, a
duplicated part and a corrupt member.

All 18 delivered 2026.09 decks were re-checked against the stricter rules: 0 findings.

### 2026-09-11 — one Summit slide, from one file: Fort Lauderdale replaces Boston

**Every 2026.09 deck advertised a Summit that had already happened.** The slide read
"Boston, MA — August 31-September 1, 2026"; the next Summit is Fort Lauderdale,
November 4-5, 2026. Fourteen of the eighteen delivered decks carried it as text and the
other four as a picture.

**It was in two forms, and neither could be replaced from the pipeline.** ICS and MRPC
decks got `assets/Velocity Executive Summit.jpg` — a flat PICTURE of the slide — while
ARS and CashPlease carried the real one baked into their template shells. So replacing
the Summit meant editing three template shells AND re-exporting a JPG, which needs
PowerPoint or LibreOffice and therefore could not be done from here at all.
`insert_summit_after_title` now clones `build/assets/summit_slide.pptx` into every deck,
and the ARS and CashPlease builders call it like ICS and MRPC always did. That file is
also the one `summit_date()` reads, so the slide on the page and the date the build
derives cannot disagree. Replacing the Summit is now one file.

**The asset had never been committed.** `build/assets/summit_slide.pptx` has no history
before today: `summit_date()` returned None, `summit_period()` with it, and four tests
failed on the missing file. The Fort Lauderdale slide is the first committed copy.

**Cloning across decks corrupted the package until it was fixed.** Relating the asset's
image Part into a deck carries that Part's OWN partname with it, so a deck that already
had `/ppt/media/image2.png` wrote the entry twice — zipfile says "Duplicate name:" and
the result is malformed while every text and geometry rule passes, which is exactly how
the 2026.08 ICS decks shipped unopenable at 0 FAIL. Images are re-added from their bytes
through `get_or_add_image_part`, which assigns a free partname and dedupes by hash.
`tests/test_summit_insert.py` promotes that warning to an error and asserts no duplicate
zip entries, that no cloned picture has a dangling relationship, that the slide count does
not move when a Summit slide is already present, and that all four builders call the
shared insert.

The slide is replaced in PLACE when one is already there, never deleted and re-added —
freeing a partname is what hands a later slide the same number.

**The Summit slide had been exempt from the source-note rule by accident.** CLAUDE.md
requires a source line in every slide's notes; while this one was a flat picture it
carried no TEXT, so the validator's data-slide rule never reached it. The moment it
became the real slide, all six ICS-only and MRPC-only decks failed on a missing note.
The rule had always applied — the old shape hid it. `insert_summit_after_title` now
writes one note on every deck, DERIVED from the date line printed on the slide rather
than written as a constant, because a note naming last Summit's city is the stale caption
this pipeline keeps re-learning. The ARS shells' own line called it "standard ARS
Executive Review front matter", which stopped being true when every program began
cloning the same file.

`test_summit_period_reads_the_current_slide` pinned `2026.08` and now pins `2026.11`.
It is meant to fail when the asset changes: replacing the Summit should be a decision,
not a side effect.

### 2026-09-11 — the template shells had never had the geometry contract applied

**The Reg E rewording fixed the built decks and left the shells failing.** Rewording the
opt-in sentence to "have elected to extend their overdraft access to the debit card"
(2026-09-10) made it four lines in a box that holds three. `slide_geometry.py` was
rebalanced to give it the room, and every BUILT deck passed — the builders run that pass.
The shells in `templates/` do not, so `ars_template.pptx` and
`multi-product_reference_deck.pptx` sat at 1 FAIL each and the gate reported FAIL for
anyone who ran it. CLAUDE.md's rule is to fix the builder AND the template shell; only
half of that was done.

Both shells now have `slide_geometry.apply()` applied and saved, so they carry the same
geometry a built deck gets rather than a hand-measured approximation of it — one
definition, per that module's own docstring. What moved, on both Reg E slides (27 and 28)
of both shells: donut 2.85" -> 2.45", the three legend rows and their chips up by 0.38",
the caption to 5.35" and 1.10" -> 1.60" tall, the branch chart to 1.60" and 3.40" -> 4.50"
tall, its caption to 6.22". Plus a 0.02" nudge on "Who Responds — Balance Profile" from
the existing caption-below-chart rule. The ICS, MRPC and CashPlease shells moved nothing:
the contract is ARS-only, as its docstring says.

Slide 28 was fixed in passing — it carries the same box as 27 and the gate had not
flagged it, because the template's dummy sentence there happens to be shorter.

**promote_month.py could not run at all.** Its `sys.path` insert was
`os.path.expanduser("~/Projects/RetailPerformanceEngine/build")`, which is not where this
repo is — it sits at `C:\Projects` — so the script raised ModuleNotFoundError on import
and delivery had to be driven with a PYTHONPATH set by hand. It now resolves `build/`
relative to its own file, the way every other entry point does. A path written into code
is a path that is wrong on the next machine; that is the whole reason `rpe_env` exists.

### 2026-09-11 — the performance page lost every CashPlease figure, and gained a shareable export

**The CashPlease section was blank for all eight clients and nothing failed.** CashPlease
moved into this repo on 2026-09-10, and its build code was deleted from the standalone
checkout in the move. `refresh_performance_dashboard.py` still resolved the extractor as
`CASHPLEASE_HOME` or a sibling `CashPlease/build/cp_extract.py`, so it found nothing, and
the CashPlease block for every one of 1131, 1539, 1564, 1632, 1734, 1750, 1770 and 1771
reported missing. The run still exited `STATUS: changed`, which is what the scheduled task
publishes on — the next 08:30 would have put a page with a hole in it at the live URL.
The extractor is now resolved in-repo first (`build/cashplease_pipeline/cp_extract.py`),
with `CASHPLEASE_HOME` kept as a fallback for a pre-migration checkout. The same move had
left the DDA counts behind too: they are read from
`Build Artifacts/cashplease/dda_counts.json`, where `build_cashplease.py` writes them,
instead of through a `cp_env` import that no longer exists and whose failure was swallowed.

`tests/test_perf_dashboard_export.py` pins the extractor's resolved PATH, not merely that
one was found — asserting "not None" would have passed on the broken morning for anyone
with the old checkout still beside the repo. It also pins cp_extract's argument count,
since the refresh builds that command line by hand.

**`--export` writes a copy that can be handed to someone.** The published artifact is
wrapped in a document skeleton at publish time, so the template carries no
`<!doctype>`/`<head>`/`<body>` of its own and a saved copy opened from a file share has no
publisher to supply one. `--export [PATH]` emits the same rendered HTML inside that
skeleton — charset first, or the em dashes arrive as mojibake — with a `<title>` (the
template's lands in the body, where browsers ignore it) and a line on the page saying the
copy is a static snapshot of its period. The page's own pill says "Last updated", which
reads as something that keeps updating; a file passed around never will.

### 2026-09-10 — the YoY tiles were not year-over-year, and their captions named the wrong months

Cherry-picked from `claude/gallant-allen-dzs1zv` (`7a47b93`, written 2026-09-01 and never
merged), plus one more instance found on the slide beside it.

**The Items YoY figure was not a year.** `metrics_gen` searched the NSF series for the row
labelled `'Jun 25'` and compared it to the LAST row — so it was year-over-year only for a
June deck. On the 2026.09 decks delivered this week the last row is Aug 2026, making it a
**14-month change presented as year-over-year**:

| Client | Deck said | Aug'25 → Aug'26 |
| --- | --- | --- |
| 1038 Sugar River | −10% | **−1%** |
| 1204 FSB Michigan | −3% | **+1%** (wrong sign) |
| 1509 Texas Bay | +16% | **+13%** |
| 1676 True Sky | −22% | **−26%** |
| 1705 CoastLife | +13% | **+4%** |

And a client whose series began after Jun 2025 found no row at all and fell to an `else 0`
branch, shipping a **phantom 0%**. The comparison is now the same month a year earlier by
month arithmetic; absent, it yields None and the tile reads "n/a" with a warning rather
than a zero.

**Three tile captions were template literals.** `(Jun 25 → Jun 26)` uses two-digit years
and `NSF/OD (June)` carries no year, so neither the as-of caption pass nor the
stale-caption gate could see them, and every deck shipped the reference client's months.
All three now come from the data.

The third — **Spend YoY** on the Debit Card Swipes & Spend slide — was not in the
cherry-picked commit. Its FIGURE was already derived correctly; only its caption was
stale, so the tile read "(Jun 25 → Jun 26)" over a number comparing Aug 25 to Aug 26. Same
shape, one slide over.

**The Reg E vintage axis was a typed `range(2018, 2027)`.** An account opened outside it
counted toward the vintage pool and then vanished from the chart, so the chart and its own
pool disagreed. The axis is the years present in the data now.

Verified on 1038 and 1204: `nsf_yoy` −1 and +1 against a window of `['Aug 25','Aug 26']`,
all three captions reading Aug. 721 tests pass.

### 2026-09-10 — CashPlease is merged into this pipeline

The CashPlease build ran out of `C:\Projects\CashPlease` against this repo's shared style
layer. It now lives here, as the fourth program: `build/cashplease_pipeline/` and
`scripts/build_cashplease.py`, dispatched by the new `cashplease-deck` subagent.

**No ARS, ICS or MRPC behaviour changes.** The pieces this depended on had already landed
— `--cashplease` and the four-product agenda in `assemble_combined`, the text-over-text
rule in `validate_deck`, `templates/cashplease_template.pptx`, and the roster in
`clients.md`. What moved is the build itself.

**Paths resolve through `rpe_env`, and `CP_DATA_ROOT` is gone.** The workbook and the DDA
count come from `Inputs/Weekly Summaries/` via `report_files()`, decks go to `Outputs/`,
and packs and figures to `Build Artifacts/cashplease/`. The separate CashPlease pipeline
folder on Drive is no longer read: two roots for one pipeline is the two-stores problem
that deleted `build/{ics,mrpc}_pipeline/data/`.

**Three deletions, each because the thing it duplicated now exists here.** `cp_qa.py` —
its check is `validate_deck`'s text-over-text rule, and the port is better than the
original: glyph boxes on both axes, priced per paragraph. `cp_env.py` — `rpe_env` resolves
these paths. The mirrored `brand.TEAL` / `periods.mon_yy` fallbacks in `cp_charts.py` —
they existed because `da20266` was not on `main`, and it is now. A fallback that can never
fire is a second definition of the palette waiting to drift, which is what `brand.py`
exists to prevent.

**One roster parser.** `cp_roster.py` is folded into `build_month.read_cashplease_roster`,
beside `read_roster`. Two parsers over one `clients.md` diverge, and these two already
proved it: the CashPlease table sits between the ICS-only table and Status changes, and
`read_roster` classifies a row by the section above it, so every CashPlease client was
briefly read as an ICS client — 1658 Truliant included, which has no RPE program at all
and is the exact row `clients.md` exists to keep unbuilt. A test now holds that shut.

**CashPlease is WEEKLY**, the only program in the cadence table that is not monthly, and
it always builds from the most recent workbook rather than the one nearest a deck's
period. So a CashPlease section inside a monthly Executive Review can report a later date
than the sections beside it. That is intended and visible: `assemble_combined` prints
each section's period.

Built on the 2026-09-06 workbook with the 2026-09-10 DDA counts: eight 2026.09 decks,
1658 skipped with its reason, 0 FAIL. `tests/test_cashplease.py` adds 19 tests, each one
a defect that shipped or nearly did — the 30-character sheet-name cap, the trailing-window
rule, L8 never reaching a slide, a NULL DDA count never becoming a zero.

### 2026-09-11 — sent is recorded from the performance page, and one section can no longer blank it

Aaron asked to mark a deck sent by clicking the "not recorded" chip on the RPE Client
Performance artifact, with no date to type. That chip is now a **Mark sent** button
(`scripts/perf_dashboard_template.html`) that records today's date against the deck named
in the Deck column, keyed on that deck's period — the same `<client>|<period>` key
`deliveries.json` uses, not the cycle period, which differ early in a month.

The page cannot write to this machine, so a click writes a row to the artifact's own
store (the `db` capability, declared on the artifact) and the daily refresh folds it into
the log: `refresh_performance_dashboard.py --merge-sent <read_db export>` merges before
rebuilding, so the republished page shows a plain sent date. **deliveries.json stays the
one ledger** — an entry already there is never rewritten, so a date corrected by hand
survives a stale page row, and a malformed row is reported and skipped rather than
repaired by guessing. A wrong sent date is the failure that lets a client go unsent, and
a second ledger is the two-stores problem that shipped month-old ICS figures in August.
A client with no built deck has no button at all: sent is recorded, never inferred.
Recorded-from-the-page sends carry an `undo` until they are merged, because a misclick
otherwise had no way back.

Also here, found while testing the above: **one failing section took the whole page
down.** A build that could not read the CashPlease rollup left `cp_peer` null, the peer
row threw on it, and the throw blanked every section AND the roster over one missing
figure. The peer row now states its absence, and `update()` renders each section behind a
guard so a section that cannot render says so while the rest of the page stands.

### 2026-09-11 — a watchdog for the daily source watch, and a registration drift fixed

Three mornings running (2026-09-09, -10, -11) the unattended 08:00 fire of the "RPE
Source Watch" scheduled task produced nothing: no log entry, no report, killed by
Task Scheduler at its 30-minute limit. The process was not hung in our code — it was
created SUSPENDED and never executed a single instruction (0 handles, 0 CPU, one
thread parked in Wait/Suspended). Every run started by hand on an awake machine
finished normally in 1-3 minutes, including a manual retry today that also surfaced
every python launch in this pipeline appearing twice in the process list — the
second a direct child of the first, identical command line and creation timestamp —
consistent with (never positively confirmed) Symantec Endpoint Protection
intercepting process creation and relaunching under its own supervision. Because the
process never gets far enough into our code to run a timeout, the fix cannot be a
code-level one; it has to watch from outside.

`scripts/watch_task_watchdog.ps1` + `scripts/register_watchdog_task.ps1` add a
second scheduled task, "RPE Source Watch Watchdog", firing 15 minutes after the main
task. A healthy morning is a silent no-op (checked: `Report-IsFresh`). Otherwise it
finds any `watch_sources.py` process matching the suspended signature (near-zero CPU
and handles, old enough a healthy run would be done), kills the whole process tree,
and retries the main task — up to two cycles before logging for a human. Verified: a
real idle-but-running process (handles ~123) is correctly NOT flagged; the
stale-report-but-nothing-stuck branch correctly logs and exits for a human; the
healthy-and-fresh branch is a confirmed silent no-op, including through
`Start-ScheduledTask` end to end. The kill-and-retry branch itself is code-reviewed
but not fire-tested against a genuine suspended process — this environment's
sandboxing refused the `CREATE_SUSPENDED` process-creation call needed to manufacture
one, even for a `notepad.exe` control case.

Also fixed: `register_watch_task.ps1`'s checked-in `Argument` string had not been
updated when `--mail` was added to the live task on 2026-09-09 — re-running the
script would have silently dropped mail reading from a task that already had it.

**No client-facing figure moves.** The point is that a morning's inputs reach
`Inputs/` even when the unattended trigger is hit by whatever this is.

### 2026-09-11 — the daily source watch had not run for three days, and nothing knew

**The 08:00 scheduled task produced no check on 09-09, 09-10 or 09-11.** Not a slow
run, not a hang: the process never executed a single instruction. All three were still
resident when this was diagnosed, each showing **zero CPU time ever, zero handles, zero
modules loaded, 2.4 MB peak working set and 7.7 MB peak virtual** against 89 handles and
4 GB peak virtual for a healthy venv interpreter. They were created by the scheduler and
left SUSPENDED, then killed at the 30-minute execution limit.

So it was none of the things it looked like. Not the Outlook hang fixed in `6b61c27` —
the 09-09 run predates `--mail` and failed identically. Not the share scan blocking off
VPN, not `copy_plan`, not prune: `import` never ran, let alone `check()`. Task Scheduler's
own log splits it cleanly — **every unattended time-triggered fire was killed at the
limit; every run started by hand on an awake machine finished in two to three minutes.**

Nothing landed on the shares during the three dead mornings, so no input was missed. What
was missed is that nobody noticed for three days.

**`watch_sources.py` now keeps a run record** (`Build Artifacts/source_watch_runs.json`):
a start stamped before the first share call, a finish stamped after the report is written
and before the mail step. `run_health()` reads it and answers one question — has the daily
watch actually been running — measuring age from the last FINISH, because a killed run
leaves a start with no finish and a run that never starts leaves neither. A damaged record
reads as unknown, never as healthy, and never stops a run: this is bookkeeping about runs,
the opposite trade to the inventory, which is still refused rather than read as empty.

**The check that would have caught this had to live outside the process.** A heartbeat
inside the watch cannot report a run that never starts — nothing in this script could have
caught it. So `refresh_performance_dashboard.py`, which runs at 08:30 on a different
scheduler, prints `source watch: ok|STALE|NOT RUNNING` every morning, and the delivery
dashboard raises a banner: a watch that has stopped means "not copied" below may be the
watch's silence rather than the data team's. `--check-stale` asks the same question from
anywhere, and scans nothing, so it answers off VPN.

**The fire is retried.** `register_watch_task.ps1` registers hourly repeats for four hours
after 08:00 with `-WakeToRun`, on the reasoning that a later fire meets a machine that is
properly awake. The execution limit drops 30 -> 20 minutes so a stuck fire is cleared
before the next one is due, or `MultipleInstances IgnoreNew` would drop it. The repeats
are cheap: `--once-daily` exits at once after a run that **reached the shares** — a run
that found the VPN down does not stop the later ones going to look, which is also why
`run_health` ignores outcome and `completed_today` does not.

The script also gained `-Repo`, because it could only ever register the checkout it lived
in, and it now omits `--once-daily` when the target checkout's `watch_sources.py` does not
know the flag. This script is routinely newer than the code it registers; an unrecognised
argument would make every fire exit without checking anything — trading three silent
mornings for a permanent silent failure.

`--mail` was also added to the registration, which had drifted: the live task passed it,
the script that writes the task did not.

### 2026-09-10 — the Reg E slides are rebalanced, and the opt-in sentence reworded

**The branch chart was 3.40" tall and stopped at 5.35**, leaving roughly 1.4" of empty
slide under its caption while twelve bars and a rate line shared half the height the donut
column used. It is now **7.60 x 4.50**, running 1.60 to 6.10 alongside the left-hand stack,
with the caption following it down to 6.22. `charts_gen` DIM moved to 1520 x 900 to match
the box aspect, or the PNG would stretch.

Making the box taller made the chart WORSE at first: `chart_lib` sized the matplotlib
figure from its height (`H x aspect`), so a taller box produced a NARROWER figure — 5.40"
instead of 7.15" — with the same 10pt tick labels, and "3,825" met "2,434" under the bars.
The figure is now never rendered narrower than the box it lands in. The take-rate chart is
unaffected: identical figure at 8.20 x 3.20 before and after.

**"…are opted in to overdraft" became "…have elected to extend their overdraft access to
the debit card"** (Aaron, 2026-09-10) — the old phrasing reads as opting in to overdrafts
themselves, when the election is about extending existing access to the card. Changed in
both template shells and the builder swap.

That sentence needs FOUR lines at 16pt in the 3.75" left column and the box held three, so
**the gate failed the build** rather than letting it wrap into the page number. The donut
gives up 0.40" (2.85 -> 2.45), the legend moves up with it, and the sentence gets 1.60".
Nothing is shrunk below the 16pt floor.

Three positions that `build_ars_gen` and `slide_geometry` both set — the branch caption,
the legend rows and the summary sentence — now have **one owner**, `slide_geometry`. Two
owners for one stack is how a caption ends up floating in the middle of a taller chart.

All ten deliverable clients rebuilt at 0 FAIL and delivered; 12 Reg E charts verified at
the new height, 6 sentences verified reworded.

### 2026-09-10 — the daily source watch hung in Outlook two mornings running; it cannot now

The 08:00 "RPE Source Watch" runs of 2026-09-09 and 2026-09-10 were killed by the
scheduler at the 30-minute limit (Task Scheduler event 329), with nothing logged.
By hand the whole run takes about two minutes, mail step included. The hang is a COM
call into Outlook while it is starting up after login: `Dispatch` blocks with no
timeout and a thread cannot interrupt it. Meanwhile eleven files had landed on the
shares since 2026-09-08, six of them for roster clients, and none had been copied —
the share check had finished in under a minute both mornings and died unwritten.

Three changes in `scripts/watch_sources.py` and `scripts/mail_sources.py`: the share
results are written before the mail step; the mail step runs as its own process with a
ten-minute deadline (`mail_step`, `MAIL_TIMEOUT`) and a timeout is reported as
"TIMED OUT" rather than lost; and `_outlook()` attaches to the running Outlook with
`GetActiveObject`, which fails at once while Outlook is starting, and only launches a
windowless instance with `Dispatch` when none is running. Pinned by four tests in
`tests/test_watch_sources.py`, including that the report and inventory exist on disk
before the mail step is entered.

Run by hand today after the diagnosis: 6 copied (1218 and 1549 DCOs and ODD extracts,
1539 and 1549 September workbooks), 4 superseded removed, mail step 0 to take.

**No figure moves.** A morning's landings now reach `Inputs/` even when Outlook is busy.

### 2026-09-10 — the dashboard shows build READINESS, not just what was built

Three changes to the "RPE Client Performance" artifact (Aaron, 2026-09-09/10).

**"Clients and decks" became "Build readiness · <period>".** It listed the newest deck
BUILT; what is in front of you at the start of a cycle is what CAN be built and what is
missing. Each row now reads ready or blocked, names what it is blocked on, and shows one
chip per required input — carrying that product's colour, red with a cross when missing,
amber when stale, with the detail in its tooltip. The header counts `N of M ready · K
built`. Austin reads "blocked: ARS workbook", which is the true answer for that client
today.

The readiness comes from `deck_status.collect()`, not a second implementation, so this
page and the delivery dashboard cannot disagree about whether a client is ready. It
degrades to "not checked" rather than failing the refresh — which is what the five
CashPlease-only clients show, since they are not on the roster `deck_status` reads.

**The provenance footer is a bulleted list**, one line per program, plus a new Build
readiness line naming its sources and stating that the CSI shares are not checked there,
so readiness reflects what is on this machine. It was a single dense paragraph carrying
five different sourcing rules.

**A "Last updated" pill sits under the title.** It carries the time as well as the date,
because the page can be refreshed several times a day; `content_hash` already excludes
`generated`, so the timestamp cannot cause a spurious republish.

### 2026-09-09 — branch-chart rate labels moved into a band above the line

They rode their own markers, which put them in the gap between the rate line and the
bars — and that gap closes exactly where a branch is both large and typical. True Sky's
377-account branch topped out a hair under its own 81% label on the personal take-rate
slide, shipped this morning.

The labels now sit at one constant height above the line. A bar cannot reach them,
because the bars are held to the lower band by their own headroom, and each label is
still directly above the branch it belongs to. The halo stays: on a chart whose rates
run near the top, the line passes beneath the band and must pass behind a number rather
than through it. `tests/test_branch_chart.py` watches where the text is actually drawn.

Affects all four branch charts. **No figure moves**; the decks in `Outputs/` carry the
old placement until they are rebuilt.

### 2026-09-09 — no backup copy; the original sources are the backup

Reverses this morning's write-only-backup decision (Aaron, 2026-09-09). There is no
second copy of the pipeline tree and nothing syncs it anywhere. Every input can be
re-fetched from where it came from — the CSI shares hold the ODD extracts, DCOs, ARS
workbooks and MRPCPM analyses; the mailbox holds the MRPC / CashPlease reports and the
ICS workbooks — and `watch_sources.py --copy --mail` is how they come back. Outputs are
rebuildable from those inputs by definition, and `Outputs/Archive/` keeps every
superseded deck.

Google Drive is gone from the project: **~236 references across 20 files**, including a
set of code identifiers that had become actively misleading once the tree moved —
`drive_glob`, `rec["drive"]`, `drive_odd`, `_drive_periods`, `--no-drive`, `drive_state`
— all naming a location nothing used any more. Also removed: `.env.drive.bak`, the Mac
Google-Drive example root, and the Drive-streaming hints in `rpe_env`'s error messages
("mark it available offline"), which advised a fix for a problem that can no longer
occur.

**This file is deliberately untouched** (Aaron, 2026-09-09 — "keep the changelog, strip
the rest"). Its purpose is that a reversal is findable, and the move off Drive is exactly
such a reversal; scrubbing it would erase the account of how the pipeline got where it
is. `docs/PRD-2026-08-26-…` is marked superseded at the top for the same reason — its
body describes the Drive era accurately and rewriting it would falsify a dated document.

**No figure moves**; `deck_status 2026.09` reports the same 15 clients / 11 ready / 10
built, and the watch and mail steps run unchanged.

### 2026-09-09 — the daily run takes the inputs that arrive by email

MRPC and CashPlease reports (Bradford Sanders) and ICS workbooks (Matt Milliman) never land
on the CSI shares. `deck_status` has said "arrives by email / n/a" for the ICS workbook
since 2026-08-31 because there was no source-side signal to wait on. There is one now.

`scripts/mail_sources.py` reads Outlook over COM — chosen over Graph because the scheduled
task already runs as the logged-on user, so there is no app registration or consent to own
— and `watch_sources.py --mail` runs it as part of the 08:00 check. The task now passes
`--notify --copy --prune --mail`.

Findings from building it, each of which is now a rule:

- **The Inbox is not where these live.** A 45-day Inbox scan read 35 messages and 123
  attachments and found neither sender: a rule files them into **Archive**. The scan covers
  Inbox and Archive plus subfolders.
- **An Exchange sender's `SenderEmailAddress` is an X500 `/o=` path**, not an address, so
  matching on it accepts nobody. Resolved through the Exchange user, then
  PR_SENT_REPRESENTING_SMTP_ADDRESS. Matching is on the SMTP address only — a display name
  is spoofable — and each sender may supply only their own kinds.
- **Only the newest of each thing.** A 120-day scan proposed 25 files; twenty were
  superseded weeklies the pipeline never reads and `--prune` would have deleted the same
  run, and one was a 2026.05 ICS workbook for a client already holding 2026.07. With the
  rule applied: **1 file to take, 21 skipped, each with its reason.**
- A local copy written after the message arrived is not clobbered — the same
  recalculated-workbook guard the share copier has.
- An attachment whose name does not match `<id>-<period>-<kind>` is parked in the legacy
  folder and reported.

Read-only throughout: nothing is marked read, moved or deleted. An unreachable mailbox is
reported and skipped rather than failing the share check. 24 tests, all driving an injected
message list so they run without Outlook.

### 2026-09-09 — the pipeline runs locally; Drive is a write-only backup

`RPE_DATA_ROOT` is now `C:\Data Pipelines\RPE Pipeline` (Aaron, 2026-09-09). The tree
moved with robocopy — **308 files, 1.229 GB, 0 failed, 0 mismatch** — and was verified by
file count, byte total per folder and hashes on a sample before `.env` was repointed.
`deck_status 2026.09` reads identically from the new root.

No code changed: every path resolves through `rpe_env`, which is the whole reason that
indirection exists. What did change is the documentation that would have undone it —
CLAUDE.md said "Google Drive is the source… on every machine" and, separately, **"do not
point `RPE_DATA_ROOT` anywhere under `C:\Data Pipelines\`"**. Both are rewritten, with
the old rule kept as dated history and labelled so it is not "corrected" back, plus a note
that `Renewals Pipeline` is a different project sharing that parent. `.env.example` too.

**One source, always**: the backup direction is local → Drive and never the reverse. A
file read back from Drive recreates the two-stores problem that shipped month-old ICS
figures in August. *Nothing pushes local → Drive yet — that mechanism is still to build.*

### 2026-09-09 — inputs are sorted into a folder per kind

Everything landed in one flat `Inputs/ARS & MRPC Reports/` — DCOs, ARS workbooks, MRPC
analyses, ICS workbooks, ICS Charts and the weekly summaries together, 55 files deep, with
the kind readable only from the filename. `scripts/watch_sources.py` now files each copy
by kind on arrival:

| Kind | Folder | Existing files moved |
| --- | --- | --- |
| DCO | `Inputs/DCOs/` | 17 |
| ARS workbook | `Inputs/ARS Workbooks/` | 10 |
| MRPCPM analysis | `Inputs/MRPC Analyses/` | 6 |
| ICS workbook | `Inputs/ICS Workbooks/` | 8 |
| ICS Charts | `Inputs/ICS Charts/` | 12 |
| Weekly summaries | `Inputs/Weekly Summaries/` | 2 |

All 55 classified, none unrecognised, moved rather than copied. `Inputs/ODDD/` is
unchanged.

**`rpe_env.INPUT_KIND_DIRS` is the only place the folder names live.** Readers resolve
through `rpe_env.report_dirs()` / `report_files()` — `build_month`, `deck_status`,
`build_ics_gen`'s workbook-period check and the dashboard refresh all changed from globbing
one literal folder to globbing the set. The set still includes the old flat folder, for
good, so a file dropped there by hand still resolves and the sort never had to be perfect.

Two rules the copier keeps: a file Inputs/ already holds is replaced **where it is**, so
sorting cannot create a second copy of a workbook sitting in the legacy folder; and prune
compares names across every folder, since a superseded file and its replacement no longer
share one.

**No figure moves**; `deck_status 2026.09` reports the same 15 clients / 11 ready / 10
built before and after.

### 2026-09-09 — the source-watch report said "Drive" while writing to C:

After the move the daily report still read *"not yet current on Drive"*, *"Drive: differs"*,
*"Would copy to Drive"*, *"Copied 1 to Drive."* — describing a destination it no longer
used. 19 strings corrected, four test assertions with them. The destination itself needed
no change: it was always `rpe_env`'s answer, never a literal.


### 2026-09-08 — the Summit one-pager and the monthly deck now share one before/after

Aaron: "the Summits and the regular delivery decks should use the same logic." They did
not. `responder_activity.py` (the one-pager) claimed in its own docstring to mirror
`metrics_gen` (the deck) "so the one-pager agrees with the client's deck instead of
restating it", and differed in four ways at once:

| | deck | one-pager |
| --- | --- | --- |
| cohort | every personal responder | only those still `Elig=Yes` at the snapshot |
| after window | 6 fixed months | every month to the end of the extract |
| winsorizing | ONE cap over before+after | a separate cap per window |
| headline | pooled over responder-observations | mean of the per-mailing means |

Every difference pushed the same way. On True Sky 1676, measured against the same
extract on the same day:

| | one-pager (was) | deck, and one-pager now |
| --- | --- | --- |
| responder spend | $459 → $999 (**+118%**) | $467 → $947 (**+103%**) |
| responders | 8,153 | **9,962** |
| customers reached | ~510 / mailing | ~623 / mailing |
| mailings | 15 | 12 |

A Summit attendee could have been handed a one-pager saying +118% while their own
monthly deck said +103%, and 1,809 responders — 22% of them — were missing from the
one-pager because they had closed or gone ineligible since responding. That is the
survivorship filter `metrics_gen` dropped on 2026-08-27; the one-pager kept it.

**The fix is one function, not two matching ones.** `build/ars_pipeline/before_after.py`
holds the measure — cohort, window ladder, winsorizing, pooling, the offer split and the
NSF/OD figures — and both entry points call it. It is import-safe, like `odd_rows`:
importing `metrics_gen` RUNS it (`sys.argv` at module scope), which is the hazard that
made the one-pager re-implement everything in the first place.

Verified behaviour-preserving for the deck: rebuilding 1676 before and after the
extraction gives **121 metric keys identical, none differing**, plus one new key the
one-pager needs. `tests/test_before_after.py` pins each decision and that neither caller
keeps a copy. Also fixed while there: the one-pager's method note described the old
window and cohort as fixed text, and its two headline tiles hardcoded a `+` sign that
would have rendered "+-5%" on a decline. `responder_activity` now also keeps the `MTD`
column, without which its NSF/OD figures would have come back 0 while the deck reported
them.

### 2026-09-08 — responder before/after now measures 6 months after the mailing

Both Responder Activity charts (Before vs After Mean, and by Offer) compared a 3-month
baseline against the **3** months after each mailing. They now compare it against the
**6** months after (Aaron, 2026-09-08).

Measured across all nine ARS clients first, on the mailings every window supports so
that window length was the only difference. The gain decays, consistently, and three
months does not show it:

| Client | Threshold gain, 3 mo | 6 mo | all months after |
| --- | --- | --- | --- |
| 1038 Sugar River | +50% | +44% | +39% |
| 1075 Austin | +50% | +45% | +40% |
| 1204 FSB Michigan | +77% | +68% | +63% |
| 1509 Texas Bay | +93% | +83% | +71% |
| 1537 Brooks Bank | +83% | +73% | +69% |
| 1539 Marine | +81% | +71% | +63% |
| 1676 True Sky | +97% | +86% | +78% |
| 1705 CoastLife | +71% | +62% | +55% |

Six months still shows the lift holding well clear of baseline, which is the durable
claim; three months reads closest to a spike. **"All months after" was rejected**: each
bar's window is a different length — the oldest mailing averages 30-plus months, the
newest one — so the bars decline left to right partly by arithmetic. That is the defect
the fixed window was introduced to fix.

Cost: the newest one or two mailings drop out (True Sky 14 → 12; the axis now ends Jan
2026, not Mar 2026). A young program falls back down a ladder that shrinks the AFTER
side first — the baseline is what the comparison is anchored to, so it gives ground
last — and both lengths are recorded (`ba_before_months` / `ba_after_months`) and stated
on the slide, so a 3-and-1 comparison is never passed off as a 3-and-6 one. The chart
legend derives from them too; it read "After (3-mo window)" as a constant.

True Sky 1676: pooled Threshold **$548 → $1,078 (+97%)** becomes **$547 → $1,015
(+86%)**; the Mean slide's headline **$467 → $947 (+103%)**.

### 2026-09-08 — "NSF/OD activity stayed roughly flat" was canned; it now carries figures

That clause sat, as fixed template text, beside the NSF/OD panel of the very chart that
measures it. It is the sentence behind the Marine FCU correction and Aaron's +/-2% rule
(2026-08-31) — the rule was written, the sentence was not fixed.

It now follows the data and states the figures: within +/-2% reads "almost flat", a rise
states the increase, a fall says the mailings did not have an impact on NSF/OD activity.
`metrics_gen` pools NSF/OD items per responder per month across every responder-mailing
observation, unwinsorized, so the clause agrees with the panel beside it.

**True Sky 1676 was not flat**: 0.33 → 0.36 items per responder per month, **+9%**. The
slide had been saying otherwise.

Also derived: "Debit spend rose after every mailing" is a claim about all of them, so it
is now made only when it is true of all of them, and states the count when it is not.
(True Sky: 12 of 12.)

### 2026-09-08 — branch charts: no program-average line

Removed from all four (Aaron, 2026-09-08). The figure is the donut on the Reg E slides
and the 12-Mo Take Rate tile on the take-rate slides, so the dashed rule was a third
rendering of a number already twice on the slide. The four captions dropped their
"Dashed line = X% …" sentence in both `ars_template.pptx` and
`multi-product_reference_deck.pptx`, and the builder swaps that filled that figure in
are gone — a swap matching nothing fails the build, which is what would have caught a
half-done version of this. `tests/test_branch_chart.py` watches for the `axhline` call
rather than reading the source, so a line reintroduced by any route fails.

### 2026-09-08 — branch charts: accounts in the bars, rate on the line

The four branch charts — 12-Month Take Rate Personal (image11), Business
(biz_branch), Reg E All Personal (image14), Reg E Last 12 Months (image16) — drew the
RATE as the bars. A rate without its denominator is not readable: a branch with 15
accounts and 4 opt-ins drew exactly as tall as one with 900 accounts at the same
percentage. Accounts opened now set the bar height and the rate is a line on its own
axis. (The program average was kept as a dashed reference at first and removed the
same day — see the entry above.)

What it surfaces: on True Sky 1676, branch **1004 is the largest by a distance — 513
of the last twelve months' accounts, roughly twice the next branch — and the worst on
new-account Reg E opt-in at 8%** against a 14% book. The old chart drew it as the
shortest bar on the slide and said nothing about its size.

Details: one renderer (`chart_lib.branch_chart`) now serves all four — `c_rege_branch`
had its own near-copy that had already drifted on halo, headroom and tick sizes. The
account count sits under the axis beneath its branch number rather than above the bar,
because above is where the rate line lives and the two collide exactly when a big
branch has a low rate. The average line was grey rather than the series colour so it did not
read as a second line where the two cross — it was removed outright the same day (see
above). The rate axis stops at 100%: 1.30x label headroom over a 99% peak
had been printing a 120% tick. The business chart's line is TEAL over its navy bars
(STYLE.md — a mark is never drawn in the canvas colour).

**No figure moves**; the bars now carry a second measure that was not on the slide.

### 2026-09-08 — five ARS charts never adopted `MMM'YY`; a render-time guard now enforces it

`mon_yy` settled the axis format on 2026-09-01 and three ARS charts adopted it. Five
did not, because they build their labels by string-slicing and so call no formatter
for anything to check:

| Chart | Slide | Drew | Now |
| --- | --- | --- | --- |
| `c_before_after_split` (image31) | Before vs After by Offer | `Feb24`, flat | `Feb'24`, 45° |
| `c_before_after` (image10) | Before vs After (Mean) | `Feb24`, rotated 90° | `Feb'24`, 45° |
| `c_sustained` (image9) | Sustained Respondent Activity | `Sep '23`, 30° | `Sep'23`, 45° |
| `c_monthly` (image5) | Monthly incremental revenue | `Aug` — **year discarded** | `Aug'25` |
| `c_ranking` (image6) | Ranking by Tier (y-axis) | `Sep 2023` | `Sep'23` |

`c_monthly` was the one that could mislead: `m.split()[0]` threw the year away on a
12-bar axis that spans two of them, so `Aug'25` and `Aug'26` would have been
indistinguishable had the window ever covered both.

**The check.** `periods.install_month_axis_guard()`, called at the top of all three
chart modules, wraps `set_xticklabels` / `set_yticklabels`: a label `parse_month`
recognises must already equal its `mon_yy` form, or the render raises
`MonthAxisError` and the build stops. It runs where the label is DRAWN because that
is the only place the value exists — a source lint sees `cats`, not `"Feb24"`.
Categories that are not months (branch numbers, offer tiers, age bands, `2025 YTD`)
pass through untouched. `tests/test_chart_axes.py` pins both directions.

`periods.parse_month` also now reads `Sep '23` (space *and* apostrophe). It was the
form Sustained actually drew and the one form the parser could not read, so the guard
would have looked straight past the chart that prompted this.

**No figure moves**; five axes change how they read.

### 2026-09-08 — the ARS builder refuses an unevaluated workbook

`build/ars_pipeline/base_guard.py` holds the one check (at most one month in the
program, no lifetime revenue, no current revenue = the template's defaults). Both
extractors (`extract_base_gen.py`, `base_tab_extract.py`) and `build_ars_gen.py` exit
with `UNEVALUATED WORKBOOK: <file> ... open it in Excel, save, and rebuild` instead of
producing a base of zeros; the dashboard refresh imports the same function and reports
the row. `tests/test_base_guard.py` pins that every ARS entry point uses it.

Why: the guard the dashboard got earlier today would have caught 1539's $0 page and
let the same workbook build a deck saying Marine FCU has run ARS for 1 month with $0
in revenue, in prose, on slide 6. Nothing on the deck would have flagged it — a
month-1, $0 client is a shape the builder accepts.

**No figure moves**; a build that would have shipped zeros now stops.

### 2026-09-08 — the copy step overwrote a recalculated workbook; it no longer can

The first `--copy` run replaced Drive's `1539-2026.08-Marine FCU-Workbook_v2_1_0.xlsx`
with the share's copy because the two differed in size. The share's copy had never
had its formulas evaluated — Executive Financials MM read "Months in the Program: 1,
Mailings to date: 0" and every revenue cell 0 — while the Drive copy had been opened
and saved in Excel, which is what gives the extractors values to read. The dashboard
rebuilt from it showed Marine FCU with $0 revenue; a deck built from it would have
too. Recovered by recalculating the Drive copy in Excel (COM, `CalculateFullRebuild`,
save): months 96, mailings 38, current revenue $154,881.24, matching the shipped deck.

Two guards: `copy_plan` now overwrites a "differs" file only when the SOURCE is the
newer write (a real re-landing); a Drive copy modified after the landing is a
deliberate change and stays. And `refresh_performance_dashboard.uncalculated()` reports
a workbook whose base extracts as one month, no mailings and no revenue as "carries no
calculated values — open it in Excel and save", instead of rendering zeros.

Open question for Aaron: whether other landed workbooks arrive unevaluated too. The
seven September workbooks copied today all carry values; 1539's August one did not.

### 2026-09-08 — the performance dashboard shows each client's newest figures, not one cycle's

`refresh_performance_dashboard.py` picked the ARS workbook, the figure sidecar and
the decks by the cycle period alone. The first September rebuild showed what that
costs: three ARS clients (1075, 1539, 1549) lost their section because their
September workbook had not landed, every client read "not built" because no
September deck exists, and every mailing-response cell went blank. It now takes,
per client, the newest ARS workbook, the newest shipped-deck sidecar and the newest
built deck at or before the cycle period, and the page tags a row whose workbook or
deck is older than the cycle ("workbook 2026.08", "built 2026.08 — no 2026.09 deck
yet"). The footer reads its source lines from the dataset instead of carrying dates
by hand. The scripted 2026.09 page: seven ARS clients on September workbooks, three
tagged August, all decks tagged August.

**Figures move on the page**: the seven September workbooks carry August data, one
month on from what the page showed. Nothing client-facing is touched.

### 2026-09-08 — superseded inputs are deleted from Drive

`watch_sources.py --prune` (passed by the "RPE Source Watch" task after `--copy`)
deletes a file in `Inputs/ARS & MRPC Reports/` when a newer version of the same thing
is there: same client and kind with a later period, or the same weekly family with a
later stamp. The newest is always kept, a lone file is never touched however old, a
tie (a weekly and its "- Copy") keeps both, and the ICS Charts workbooks, ODD extracts
and anything unpatterned are out of scope. The first run removed 53 files (the
2026.07 and 2026.08 DCOs, ARS workbooks and MRPCPM analyses that 2026.09 landings
superseded), leaving 55.

Why: Aaron asked (2026-09-08) that old versions go once an updated input exists.
Every builder resolves the newest file for its period, so nothing reads the pruned
ones; the one visible effect is that the delivery dashboard's input columns for a
past period now read "not copied" — that period's decks are built and sent, which is
the column that matters.

### 2026-09-08 — the daily source check now copies roster clients' files to Drive

`watch_sources.py --copy` (passed by the "RPE Source Watch" task) copies every file on
the CSI shares for a roster client that Drive lacks or holds a different landing of into
`Inputs/`: DCOs, ARS workbooks, MRPCPM analyses and ICS workbooks to `ARS & MRPC Reports/`,
the ODD extract to `ODDD/<id>_ODDD.zip`. Copy-only, `.part`-then-rename, size-verified.
The ODD extract is copied only from the NEWEST month on the share per client: with two
months scanned and no period in the Drive filename, last month's extract at source
"differs" from Drive forever once this month's is copied, and copying it back would be
the stale-ODD failure this pipeline guards against everywhere else.

Why: Aaron found 26 September files sitting in his `Velocity_clientreports` folder that the
watch had recorded at its baseline and nobody had copied; Drive held zero 2026.09 files
and the performance dashboard was still on 2026.08. The first `--copy` run moved 37
files (13 DCOs, 7 workbooks, 4 MRPCPM analyses, 13 ODD extracts) for the 15 roster
clients; 1437 Canandaigua's files were left on the share because `clients.md` ends it.

**A client-facing figure can move as a result** — that is the point: the next build and
the next dashboard refresh read this month's inputs instead of last month's.

### 2026-09-08 — the performance dashboard artifact refreshes itself after the source check

`scripts/refresh_performance_dashboard.py` is the aggregator behind the "RPE Client
Performance" artifact, promoted from a per-session scratchpad script into the repo
so a refresh is reproducible: ARS figures through `extract_base_gen` / `base_tab_extract`
and the shipped deck's figure sidecar, ICS and MRPC from the VIP sheets, MRPC and
CashPlease from the newest weeklies (CashPlease through that repo's own `cp_extract.py`).
It injects the dataset into `scripts/perf_dashboard_template.html` (the artifact's
page, checked in) and reports `STATUS: changed|unchanged` against the hash last
published. The Claude scheduled task `rpe-dashboard-refresh` runs it daily after the
08:00 source watch and republishes the artifact in place only when figures moved.

Verified: the scripted dataset reproduces the hand-built 2026-09-08 artifact figure for
figure; the one addition is the CashPlease peer cohort's DDA fields, now populated
because the extractor is given the DDA counts the CashPlease pipeline already keeps.
The page does not render those fields, so nothing visible changed on the republish.
The period is derived from the newest ARS workbook on Drive (2026.08 today) rather
than assumed from the calendar — the same rule the monthly decks follow.

### 2026-09-08 — a daily check of the CSI shares for new inputs

`scripts/watch_sources.py` scans this month's and last month's folders on
`\\PADMIS105\Velocity_company\Aburgard\ODDD` and `\\PADMIS105\Velocity_clientreports`,
diffs the inventory against the one it saved last run (`Build Artifacts/source_watch.json`),
and reports what is new, re-landed or gone — roster clients first, each with whether
the Drive copy the builders read is already current. `scripts/register_watch_task.ps1`
schedules it as the Windows task "RPE Source Watch", daily at 08:00, with a toast
when there is news. Registered on Aaron's Windows machine the same day; the first run
recorded a 309-file baseline.

Why: `deck_status.py` says whether a file is there now, and a morning glance at the
dashboard misses the straggler — 1174's 2026.08 extract landed four days after the
batch, 1502's 2026.09 extract six days after, and a re-landed extract (1539, 2026.09)
keeps its name. Two rules carried over from the dashboard: off VPN the shares are
unknown, not empty (the run exits 2 and leaves the inventory alone), and a damaged
inventory is refused rather than read as "nothing seen".

**No client-facing figure moves; nothing is copied to Drive automatically.**

### 2026-09-02 — CashPlease gets its own shell

`templates/cashplease_template.pptx`: a 10-slide Union Financial demo (cover, Summit,
one-row agenda, divider, the four CashPlease content slides, Questions, Contact),
materialized by running `build_cp_gen.py` on a synthetic pack for client 999 with
invented figures and a dummy source filename. Until now the CashPlease builder
started from `ars_template.pptx` as a bare shell and stripped 42 slides and 33 media
files on every build, and the CashPlease look had no template of record to diff
against. The shell now goes through the gate like the other three, and the layout
baseline carries it. `build_all_cp.py` points at it. Verified: the dummy pack and
1734 Altamaha both rebuild from the new shell at 0 FAIL, and an ICS-CP deck
assembles from the shells.

**No client-facing figure moves, nothing renders differently.** The five CashPlease
slides are built from the pack either way; the shell only supplies the theme,
masters, embedded fonts and the five shell slides it always did.

### 2026-09-02 — the style guide, the gate and its companions, cleaned up

`templates/STYLE.md` was rewritten as one document (this supersedes the 17:49 reorganization below, done in a parallel session and merged into it: its verified facts — Excluded Accounts open-only, the ICS one-decimal row, label halos and axis striding, the builder-inserted slides — are carried here) with a scope table (Executive
Reviews, the CashPlease module, the ILS review prep slides, the Summit one-pager),
an enforcement map naming the file behind every rule, and a dated decision log
replacing the per-date reversal notes that had accreted through the body. Stale
content went: the 2026-07-10 Austin per-chart to-do list (all fixed by 07-24),
`style_tables.py` and `kickoff_lib` (retired), `build_gen`/`build_gen_b`, the
two contradictory MRPC tier-color sections, and a divider line the shells never
carried ("Program Performance Review" — the ARS shell reads "Mailings · Debit Card ·
Reg E"). `templates/TEMPLATES.md` lost the superseded 67-slide Marine map and now
tables the three shells with their slide counts, plus the two families that have no
shell (CashPlease, ILS prep). `tests/test_style_doc.py` fails the suite if either
document cites a repo path that does not exist.

`validation/validate_deck.py` was restructured: every rule is a named function
listed in `RULES`, `run()` returns the findings, and the inline rules that lived in
`main()` are now `text_rule_findings`, `geometry_findings`, `autofit_findings`,
`mailing_table_findings`, `extract_findings` and `labelled_metric_findings`.
**Output is byte-identical** on all four templates and all seventeen 2026.08 decks
on Drive, checked by diff. One rule was added.

**Text drawn over text now FAILs.** Ported from the CashPlease project's `cp_qa.py`:
its Peer Comparison footnote was pulled up by `fit_layout` onto a row of capsule
pills and this validator returned 0 FAIL, because every overlap rule it had looked
for text over a CHART. The port compares estimated GLYPH boxes rather than frames —
per paragraph, at that paragraph's size, placed by alignment and vertical anchor.
A frame comparison flagged 109 places on the shipped decks (every ARS title box
overlaps the selection line's box by 0.10"; the ICS education titles sit in boxes
two inches tall; an ICS callout stacks 40 pt over 16 pt); the glyph comparison
flags none of them and still catches the 0.56" footnote. `tests/test_validate_deck.py`
carries both halves.

`validation/qa_all.py`: argparse, and the unit suite is no longer skipped quietly.
The Windows Store python has no pytest, so a gate started with plain `python`
reported PASS having run zero tests; it now prefers the repo `.venv` interpreter
for both pytest and the validator, and prints a banner when the suite could not run.

**Every MRPC and ICS deck renders differently, by two alpha points, and no figure
moves.** The callout drop shadow is now defined once, `shapes.shadow`, and the ARS,
ICS and MRPC builders import it. The ICS builder had its own copy at alpha 26%
against 28% everywhere else — a drift STYLE.md described as "matching".

Docstrings in `build/fit_layout.py`, `build/restyle_fonts.py` and
`build/slide_geometry.py` now state what the code does (the dense-table titles,
the geometry rules per title, the numbers `fit_layout` uses), and `build/README.md`
no longer lists the `data/` folders deleted 2026-08-29.

Not fixed, reported: `build/assets/summit_slide.pptx` is gitignored by the blanket
`*.pptx` rule and is absent on the Windows machine (no Drive `Inputs/Summit/`
either), so the four `tests/test_summit.py` cases fail here and every ICS/MRPC
build would. The asset needs committing (an ignore exception) or copying to Drive.


### 2026-09-02 — the ODD fixture regenerates when its generator changes

`conftest` only built the synthetic ODD when the file was missing, so pulling a change to
`make_odd.py` left a stale CSV in place. When MTD changed from fee dollars to NSF/OD item
counts, a cached fixture failed three correct tests with "non-integer MTD values" — pointing
at the tests rather than at the fixture. It now regenerates whenever the generator is newer
than the file.

### 2026-09-02 — STYLE.md reorganized, and three contradictions in it resolved

The style guide had accreted chronologically — thirty flat sections with headings like
"Slide-check additions (round 2)" — which reads as a changelog rather than something a
colleague can look something up in. Reorganized into eight numbered sections plus an
appendix, with a table of contents: foundations, slide anatomy, the two months, elements,
deck structure, per-product rules, adapting to client data, enforcement.

**The MRPC tier colours were stated three times and disagreed with each other**, and
`build_mrpc_gen.py`'s own docstring stated a fourth, superseded version. The code is the
truth — Gold = orange, Platinum = steel `#9DB8CC`, Business = navy, and the callouts MATCH
the bars. Stated once now, as a table, and the docstring is corrected.

The colour list also named `STEEL #9DB8CC`, but `brand.py` has `STEEL = #7B9BB8` (ARS) and
`STEEL_SOFT = #9DB8CC` (ICS/MRPC). The palette now matches `brand.py` name for name, so a
reader who copies a name gets the colour they read about.

Promoted two things to their own sections because they are the mistakes that actually
recur: **the two months** (reporting vs data, the distinction behind several defects) and
**enforcement** (what runs, in what order, and the three rules learned the hard way).

Dropped the nine "Known per-chart fixes (Austin 1075 review, 2026-07-10)" — one-off bug
reports rather than style rules, and the builders have moved past them. Added this week's
rules: Excluded Accounts is open-only, the ICS one-decimal comparison, chart striding and
label halos, and a note that Product Mix, Excluded Accounts and Reg E by Branch are
INSERTED by the builder, so they appear in a built deck but not in the template shell —
which is not obvious from opening the shell.

Divider lines, Reg E slide titles and Responder Activity titles were verified against the
templates and a built deck rather than carried over on trust.

### 2026-09-01 — MRPC Enrollment Performance was drawn from an invented denominator

`chart_perf` read `new_checking_approx`, a key **no client sheet has ever
carried**, and fell back to `enrollments / 0.11` — a guessed 11% penetration. The
real counts sit in `new_accounts` and the real goal in `goal`, present in every
sheet. Because the goal line was derived from those invented bars, every month's
goal was wrong too.

On Austin 1075 the fabrication drew 1,036 new accounts for a month that actually
had 873; on Marine 1539 it drew 236 where the truth was 341. **Figures move on
every MRPC deck.** There is no fallback now — absent keys raise, because a chart
that cannot be drawn from the client's data must not be drawn from a constant.

Enrollment counts also moved from the line to **above the bar**, matching
Retention (Aaron).

### 2026-09-01 — every MRPC deck shipped the template's enrollment sentence

The Enrollment-vs-Goal caption was resolved by POSITION: `txt_at(S[4], top=6.7)`
with a 0.15" tolerance, against a box that sits at **6.40"**. `txt_at` returned
`None`, the `if` fell through, and the caption was never swapped — silently, with
no swap gate in the MRPC builder to catch it. Austin, Ideal, Summit, Capital and
Marine all shipped the same sentence: *"averages ~55% of goal, peaking at 72% in
Feb 2026"* — Union Financial's numbers.

It would not have worked anyway: the replacement read `penetration_summary` from
the client sheet with a `''` default, and no sheet carries that key, so a caption
that DID match would have read "Enrollment penetration ."

Now resolved by CONTENT, derived from `pct_of_goal` (which is present), and it
raises if either the shape or the series is missing. Marine reads "averages 58%
of goal, peaking at 78% in Jun 26". Geometry drifts; the words do not.

### 2026-09-01 — the ICS 12-month close rate was the client's NON-ICS rate

The Comparisons row was inverted. `client` carried the client's **non-ICS**
close rate program-to-date, while the client's own **ICS** rate sat in the
*Velocity average* column — so the row compared a client against themselves and
labelled neither side correctly. It went unnoticed because the first client it
was checked against, CoastLife 1705, happened to have a 6.7% ICS rate identical
to the Velocity benchmark.

The Velocity average is a **constant**, like the 29% of openings and $1,828
lifetime value beside it, read off the template's "Velocity Clients' Average"
column: `VELOCITY_CLOSE_RATE_12M_PCT = 6.7`.

The footnote had its own defect: it says "your Non-ICS accounts' **12-month**
close rate" and was handed the program-to-date figure. **Figures move on every
ICS deck with a current workbook:**

| Client | Row was | Row now | Footnote was | now |
| --- | --- | --- | --- | --- |
| 1075 Austin | 5.4 vs 51.7 | 6.7 vs 5.4 | 51.7% | 6.5% |
| 1509 Texas Bay | 8.3 vs 44.5 | 6.7 vs 8.3 | 44.5% | 15.3% |
| 1539 Marine | 6.9 vs 35.5 | 6.7 vs 6.9 | 35.5% | 10.4% |
| 1734 Altamaha | 7.9 vs 13.8 | 6.7 vs 7.9 | 13.8% | 9.0% |

Austin's deck previously showed a 51.7% close rate for their ICS programme; it is
5.4%, against a 6.7% benchmark. The stored `benchmark` block is written by
`ics_workbook_extract`, so the client JSONs were re-extracted — the diff was
exactly these three fields on all four clients.

### 2026-09-01 — life-of-account metrics use Last 12 Months only

Program-to-date spans the whole programme and answers a different question: on
Austin it reports a 51.66% non-ICS close rate against 6.45% over the last year.
Mixing the two windows in one table compares figures that are not comparable, so
every metric off the *Life of Account Data* sheet now reads the **Last 12
Months** row (Aaron). *% of Total Openings* moves with it — Austin from 25% to
32% (3,609 of 11,109 openings).

### 2026-09-01 — "a program high" was asserted, not found

Two ICS captions declared a record without testing for one. The Power-of-
Referrals line called the PREVIOUS month a programme high unconditionally, and
the Referral Trend caption said the same of whatever sat at `[-2]`. Both were
**false on every client checked**: Marine's July was 103 against a June of 129,
Austin's July 363 against 423, Texas Bay's July 40 against a March of 73.

The claim is now earned or dropped, and scoped to what the data can support —
`trend` is a 14-month window, not the whole programme, so nothing there can prove
a *programme* high. Marine reads "July brought 103; the last 13 months peaked at
129 in Jun 26." This is also the "no superlatives or unsupported claims" rule in
CLAUDE.md.

### 2026-09-01 — canned claims that future data can falsify

An audit of every string the three builders write into a deck, bucketed by how it
goes stale: fully canned, fixed-index, and interpolated-but-unearned. Three MRPC
sentences asserted something no one had checked:

- *"Revenue has grown across the life of the program"* — Capital Bank 1502 peaked
  at $8.4K and has fallen for three years. Now tested against the annual series;
  1502 reads "Life-of-program revenue reached".
- *"Monthly MRPC revenue has held around $XK"* — 1502 swings ±15% around its
  mean. Now claims stability only within ±10%, else "has averaged". (The average
  also printed at `,.0f`, so a $669 mean rendered "$1K" beside a "$0.6K–$0.7K"
  range — an average outside its own range. One decimal now.)
- *"Platinum ($14.95/mo) is the most-held card"* — both the leader and the price
  were hardcoded. Both now come from `card_billing`, so a client whose Gold or
  Business Platinum book overtakes Platinum is not told otherwise.

### 2026-09-01 — the gate FAILs a slide whose text contradicts its own figures

`validate_deck.claim_consistency_findings` reads one sentence at a time and
matches each claim to its NEAREST figure pair: a stated percentage against that
pair, a movement or flatness word against the change, a comparative against the
ordering. Flatness is held to Aaron's ±2% band.

Getting it to FAIL rather than advise took three corrections, each found by
running it over shipped decks rather than invented examples: a COMPARISON is not
a MOVEMENT ("lower balances than non-responders, $924 vs $2,477" is correct, and
reading it as a change looks like a +168% rise — that failed six correct slides);
a sentence carries more than one claim (testing every claim against the FIRST
pair failed six more); and negation ("did not increase" is not an increase).

A rule that flagged claims with no supporting figure was **dropped**: it produced
156 findings across 20 files, almost all legitimate bullets whose evidence is the
chart on the slide. A rule that cries wolf 156 times is a rule nobody reads.

Separately, the validator was truncating its own output — findings quote slide
text, and printing an em dash to a pipe on Windows raised `UnicodeEncodeError`
part-way through the report, so the summary line landed and every finding after
it was lost. A gate that cannot say what failed is not a gate.

### 2026-09-01 — Average Ticket describes what the figures actually did

The caption hardcoded "ticket **holds** through response" — true of the
template's own $50→$50 example and of nothing else. It shipped over declines of
5.2% to 8.6% on six 2026.08 decks (1509, 1537, 1539, 1549, 1676, 1705). The same
sentence hardcoded "monthly swipes **rise**"; real clients do rise, so that never
showed on a delivered deck until the golden deck's synthetic ODD fell 3.0% and
said "rise" anyway. Both verbs now derive from the values they introduce, on the
±2% band, as does the chart title above the bars in `ticket_chart.py`.

The closing clause — "the gain is more transactions, not larger ones" — was
dropped (Aaron, 2026-09-01). The two movements are stated; the reader can draw
that themselves.

### 2026-09-01 — one month format on every chart axis, and one overlay-line color

**Axes.** Every month label is now `MMM'YY`, angled 45° — `periods.mon_yy()` /
`axis_months()`. Three formats were in service and none agreed: ARS drew
`Jun'25`, MRPC drew `Aug 25`, and the ICS quarter panels drew `Jul` —
`mm.split()[0]` threw the YEAR away, so a 14-month axis read Jan…Dec…Jan. Fixing
it exposed a gap in the shared parser: `parse_month` never handled `Jun 25` or
`Jun'25`, the pipeline's two commonest forms, so every VIP series fell through to
`None`.

**Overlay lines.** Three goes at this. The MRPC Retention line was drawn plain
WHITE on the assumption it never left a navy bar — it does, and the line was
invisible for its whole length on the 2026.08 decks, legend swatch included.
Then navy with a white casing, which was legible but rejected on looks. Now
**teal `#0D9488`**, which needs no stroke: 4.02:1 against navy and 3.74:1 against
white, both clear of WCAG's 3:1, and close to the best any flat color can manage
against those two extremes (3.88:1). Orange reference lines are left alone —
they already read at 5.5:1 on navy. `tests/test_chart_colors.py` still fails the
build if a mark is drawn in the canvas color.

### 2026-09-01 — ICS Billed Expense drops the account count

"Billed Expense for 6,785 Accounts" wrapped onto the value beneath it. The count
was already conditional on `fits_one_line`, which passed 6,785 and let it wrap
anyway; it is now dropped unconditionally (Aaron). The same figure is already on
the slide in the "ICS Accounts" callout.

### 2026-09-01 — the ODD's `<mon> MTD` column is NSF/OD ITEMS, not fee income

`odd_rows.nsf()` documented the `<mon> MTD` column as "NSF/OD fee income", while
every consumer read it as an item count: `charts_gen` titles it "NSF/OD Items",
`metrics_gen` names it `items12`/`nsf_last_items`, and `build_lift_matrix`
multiplies it BY a per-item NSF fee. Two descriptions of one column, with the
dollar reading only in prose.

Checked against the 2026.08 extracts for 1539, 1705, 1204, 1075, 1549 and 1218
(~580k account-months): every populated `MTD` cell is a non-negative INTEGER,
frequencies decay smoothly from 0 through 1, 2, 3, ..., no value carries cents,
and nothing clusters on a multiple of any fee amount. `<mon> YTD` is the
calendar-year cumulative of the same integers (19,552 of 19,573 sampled 1539
accounts reconcile exactly against Jan..Jul MTD). The ODD carries no OD-fee
dollar column at all — NSF revenue reaches the deck from the workbook's
"Total NSF Revenue" via `base_tab_extract`. ITEMS is correct.

**No client-facing figure moves.** Nothing on a slide was computed from the
dollar reading; every deck consumer already treated it as items, and no template
slide carries "fee income" wording. This is entirely about what the number is
called. Renamed and corrected:

- `odd_rows.nsf()` — docstring now states ITEM COUNT, with the evidence.
- `lift_extract` — `fee12` -> `items12`. A `.pkl` cached before today must be
  regenerated; `build_lift_matrix` now says so instead of raising `KeyError`
  inside the valuation.
- `oddd_optimize` — `od_fee_income_MTD` -> `nsf_od_items_MTD`,
  `od_fee_income_YTD` -> `nsf_od_items_YTD`,
  `top_branches_by_od_income_latest` -> `top_branches_by_nsf_od_items_latest`.
  These were formatted with a `$` in `oddd_pack.md`, including in the DERIVED
  block labelled "for Key Metrics slide" — a mislabelled dollar figure sitting
  where a deck author would reach for one. Now printed as counts, with a line
  saying NSF revenue is not in the ODD. Nothing outside the script read the old
  keys. MTD/YTD/PYTD moved from `money_fams` to `num_fams`; both paths take the
  same sum, so the totals are unchanged.
- `.claude/agents/oddd-optimizer.md` — the sanity-check and pack-contents wording.
- `tests/fixtures/make_odd.py` — the fixture wrote `MTD` as `35.00`/`70.00`, i.e.
  two $35 fees, teaching the wrong meaning to every test built on it. It now
  writes small integers, and `YTD` as their calendar-year cumulative.

Standing-rule check added: `tests/test_nsf_is_items.py` pins the meaning from
both ends — the fixture data must keep the shape of a count (integers, count-scale
magnitudes, YTD >= MTD), and no module that reads the column may describe it in
money terms again. The guard is itself tested against the exact lines the defect
shipped as.

Incidental, same commit: `oddd_optimize` wrote `oddd_pack.md` and
`oddd_metrics.json` with the platform default encoding, so it died on Windows
with `UnicodeEncodeError` on the arrow in "mailed -> responded". Both writes are
now `encoding="utf-8"`. This was blocking all 26 `test_golden_deck` tests on this
machine.

### 2026-08-30 — Average Life of Account prints one decimal on both sides

The ICS Comparisons row compared a pair at two precisions: the Velocity average
rendered "6.9 Years" against a client "6.21 Years". `cfmt`'s `years` format used
`{v:g}`, which prints the shortest form — so it also gave a client at exactly 7 a
bare "7 Years". Both sides go through the one formatter, so `{v:.1f}` fixes the
pair. Affects 1075 (7.66 -> 7.7), 1509 (7.05 -> 7.0), 1539 (7.24 -> 7.2) and 1734
(6.21 -> 6.2); those four decks were rebuilt and reissued, one value each and
nothing else touched.

1537, 1632 and 1676 have no Comparisons slide to fix — their workbooks are 2026.06
and 2026.07 against a 2026.08 deck, so their financial detail is suppressed by the
stale-workbook rule. Checked rather than assumed, since "the slide is missing" and
"the fix broke the slide" look the same from the outside.

### 2026-08-30 — promote_month.py, and its archive stamp comes from the clock

The staging-to-Outputs step is now a script in the repo rather than one written
per run. It archives whatever a deck supersedes, and leaves a deck alone when its
rendered content is identical to the delivered copy — a rebuild that changed
nothing should not churn the archive and bury the copies that matter.

Its date stamp was a literal, which dated four archives to the wrong day and
collided with the previous run, producing "-2" and "-3" suffixes. Now derived from
today; the four mis-stamped files were renamed.

### 2026-08-29 — a whole deck is built in the test suite

`tests/test_golden_deck.py` runs the real chain end to end — oddd_optimize,
metrics_gen, charts_gen, build_ars_gen, restyle_fonts — on the synthetic ODD and a
new synthetic workbook extract (`tests/fixtures/make_base.py`). A pipeline
regression now surfaces in **9 seconds** instead of in a seven-minute run across
fifteen real clients. No client data is involved; both fixtures are invented and
generated on demand.

Assertions are structural, not a hash: a hash fails on every intended change and
teaches people to re-baseline without looking. What is pinned is what must not
silently move — it builds, all 28 charts render, the slide count holds at 49, the
expected slides are present, its own validator passes it, the provenance sidecar
is emitted, and no real client's name appears anywhere in it.

Building it exposed the fixture's own limits: eight branches over 800 rows left
every per-branch cohort under metrics_gen's 15-account threshold, so the Reg E and
take-rate branch tables came out empty and their charts had nothing to draw. The
fixture now uses three branches and a larger new-account cohort.

### 2026-08-29 — the Summit slide may come from Drive

`build/assets/summit_slide.pptx` is replaced by hand before each Summit by whoever
prepares it, who should not need a commit to ship it. `Inputs/Summit/summit_slide.pptx`
now wins when present; the committed copy is the default, so the common path
touches no network and cannot drift.

Everything else stays in the repo deliberately. Fonts are committed precisely so
both machines render identically; the template shells are versioned build inputs
whose geometry `qa_all` diffs against a baseline every run. Moving those to a
streamed folder would trade fast-and-identical-everywhere for a consistency the
pipeline already has.

The optional lookup caught a latent bug on the way in: `rpe_env` raises
`SystemExit` when `RPE_DATA_ROOT` is unset, and `SystemExit` does not inherit from
`Exception` — so an `except Exception` around an OPTIONAL lookup would have killed
the build on a machine that had never configured Drive.

### 2026-08-29 — README

The repo had a one-line README. It now says what the pipeline builds, how to build
a month, where data lives, and what each companion file decides — `CLAUDE.md`,
`clients.md`, `CHANGELOG.md`, `STYLE.md`, `TEMPLATES.md`, the agent docs and the
PRD — so the split between them is discoverable without reading all six.

---


---

## 2026-08-29 — 2026.08 monthly delivery

Everything the 2026.08 client review decks were built with.

The monthly reviews and the Executive Summit are two different deliveries: the
reviews go to every active client each month, the Summit runs a couple of times a
year and only for attendees (Aaron, 2026-08-29). This heading is the monthly one.

### 2026-08-29 — clients.md decides a client's name, and 1204 is renamed

1204 is **First State Bank - Michigan** (Aaron). It shipped as "FSB Michigan" while its
workbook said "First State Bank-MI" — three names for one client, none of them agreeing.

The roster's `Client` column is now the delivery name: it goes in the filename AND
overrides what the workbook carries, so the cover and every source note match. Renaming a
client is a delivery decision, so it belongs in the file where such decisions are recorded,
not inferred from a previous filename (which is how "FSB Michigan" survived a cycle) or
read off a workbook nobody chose.

Six other roster entries carried short forms that had never reached a deck — "Texas Bay
CU", "CoastLife CU", "Ideal CU", "WesBanco Bank", "FNB&T Chickasha", "Altamaha Bank and
Trust". They are aligned to the delivered names, so making the roster authoritative renames
1204 and nothing else. 1204's 2026.08 deck was rebuilt and reissued; the old file is
archived as `(renamed 2026-08-29)`.

### 2026-08-29 — the Summit slide stays, and its date parser is ready for the next one

Confirmed: every results deck carries the Executive Summit slide (Aaron). The slide is
replaced by hand before each Summit — Ft. Lauderdale is next, in November — so
`summit_date()` reads the date off the slide rather than hardcoding it, and now accepts
abbreviated month names and a range that crosses a month boundary. A format it silently
missed would fall back to the previous Summit's date, which is worse than failing.
`summit_period()` warns when the slide still names a Summit that has passed.

### 2026-08-29 — Excluded Accounts explains OPEN accounts only

The slide answered "why is any account on file outside ARS", so its largest bar was the
closed book — an account that is closed is outside ARS by definition and explains nothing.
Dormant and inactive accounts were a second bar, which conflates "this account is not
active" with "this OPEN account is not eligible". Neither is a reason.

The population is now the open book. Reasons are product code, no debit card, and an
account-level remainder. The closed and dormant counts are still computed and named in the
source note, so the scope is stated rather than implied.

The tiles now reconcile — open accounts = open-and-excluded + open-and-eligible. The
eligible tile counts OPEN eligible accounts and says so; the whole-book figure includes
dormant accounts the core still flags eligible (147 on 1204), which left the three tiles
147 apart with nothing on the slide to explain the gap.

### 2026-08-29 — a slide module's own source note is no longer overwritten

`build_ars_gen`'s note pass wrote a title-keyword note onto every slide, including the ones
Product Mix and Excluded Accounts had already written for themselves — losing the
population, eligibility column and scope those modules actually know. It now skips slides
whose module wrote a note. Not "skip any slide that already has one": the template shell
carries stale dummy-client notes that must be replaced.

### 2026-08-29 — ICS and MRPC read the VIP store, and only the VIP store

`resolve_client_json` no longer falls back to `build/{ics,mrpc}_pipeline/data/`, and those
folders are deleted. They held copies that drifted: the Drive store carried 2026-08-29
pulls while the repo still had 2026-08-10, and a build reading the repo shipped month-old
figures that validated perfectly because they were internally consistent. Two stores for
one fact is the problem. Every active ICS and MRPC client was confirmed present in
`Inputs/VIP Data/` first; the only files that existed solely in the repo were two
`_PARTIAL` captures the store's README already records as not copied.

### 2026-08-29 — two chart collisions

*Monthly Summary — Last 12 Months.* The orange average label was drawn with `va='center'`
on the dashed average line, so the dash ran through the text. It now sits just above the
line. The same dash also struck through any bar label near the average — `$284K`, `$282K`
and `$298K` on Austin — so bar labels carry a white halo and the line passes behind them.

*Responder Activity: Before vs After by Offer.* The axis labels the newest mailing on top
of a strided tick list, and appended it blindly. Austin 1075 has ten mailings and a stride
of two, so ticks ran `... 8, 9` and "Nov25"/"Feb26" printed on top of each other. The
neighbouring tick is dropped rather than crowded.


---

### 2026-08-29 — the figure sidecar now reaches the deck that ships

`build_ars_gen` names its sidecar after the deck IT wrote — the ARS component. For a
multi-product client that component is an intermediate; the deck that ships is the
combined one. `validate_deck` looks for a sidecar named after the deck in front of it, so
the FAIL-grade figure check silently did not run on any combined deck.

`assemble_combined` now merges each section's sidecar onto the combined deck. Measures are
prefixed with their program (`ARS:responders_latest_mailing`): two programs using one
measure name is coincidence, not identity, and pooling them unprefixed would invent a
conflict between unrelated figures. Within a program the check is unchanged.

### 2026-08-29 — a multi-product client gets the combined deck only

Recorded because the archive shows both shapes historically: some cycles delivered a
client's per-program decks alongside the combined one. The per-program decks are
intermediates that feed `assemble_combined` — one client, one deck (Aaron, 2026-08-29).

### 2026-08-29 — ICS Comparisons header fits the client name

"Altamaha Bank and Trust Company Data" is 4.64in of Montserrat 16pt in a 3.7in box: it
wrapped onto the value below. Shrinking is not available — `enforce_min_font` floors every
run at `MIN_PT`, which its own comment warns about. The header band now grows upward and
anchors to its bottom edge, so the values never move; a name that fits keeps the original
geometry and anchor exactly, and no other client's deck changes.

### 2026-08-29 — a missing MRPC channel count is not the same fact as a zero

Re-running all 15 2026.08 decks crashed Marine 1539's MRPC build: `chart_channel`
plotted `counts["Paper"] = None` and died on `vals + max(vals)`.

A channel count can be absent for two reasons and the chart must not conflate them. The
client may genuinely have no enrolments on that channel — a real zero, and a normal
state. Or VIP may decline to surface the number: Marine's Paper bar is too small to
trigger a tooltip, and the sheet records `None` with the note "~3 implied by 0.04%".
Writing `0` there would be false precision; the share is not zero.

Both now draw a zero-length bar and only the LABEL differs — the count when known, `0`
when the share is also zero, `n/a` when the share is non-zero but the count was not
readable. The totals chart is kept either way. A first attempt fell back to the share
chart whenever any count was missing, which threw away three good counts because of one
and read a genuine zero as a gap.

Affects Marine 1539 only: slide 58's Paper bar is now labelled `n/a` rather than `0`.

### 2026-08-29 — figure provenance sidecar: a measure renders one value, or the build fails

The 2026-08-28 Wellworth defect — the Jun 2026 drop reading 1,077 on the mailing slides and
1,026 on Reach/Depth/Ranking/Sustained — got past two guards. The builder's swap gate fails a
build whose swap string matched NOTHING, but here both swaps landed; they just wrote
different numbers. And `validate_deck.figure_identity_findings` has to INFER from wording
whether two figures are the same measure, which misfires on legitimately different cuts
(personal vs business take rate), so it can only advise.

The builder does not have to infer. It knows which measure produced each number, so it now
says so: `set_exact`/`set_shape_text` take an optional `measure=`, and `build/figures.py`
records (measure, rendered value, slide) as the deck is written. Two consumers:

* **Build gate.** `conflicts()` runs before the phase that materializes the output file, and
  a measure carrying two values fails the build with exit 2, naming both values and the
  slides they landed on. Placement matters — at the final save it still exited 2, but a
  partly-built deck was already sitting at the delivery path.
* **`validate_deck.figure_sidecar_findings`** reads `<deck>.pptx.figures.json` and FAILs on
  the same conflict. This is the FAIL-grade counterpart to the inferred rule, which stays at
  REVIEW: here the builder named the measure, so a difference is arithmetic, not a guess.

Naming is opt-in and only worth doing where one measure reaches more than one slide. Five are
named today (`responders_latest_mailing` across three slides, `mailed_latest_mailing` across
two, plus `resprate_latest_mailing`, `reach_total`, `dot_n`). No deck changes: 1204 rebuilds
to 49 slides, 38 chart images byte-identical, 0 text differences. Only the ARS builder emits
a sidecar; a deck without one validates exactly as before.

The sidecar goes to `Build Artifacts/` under `RPE_DATA_ROOT`, named after its deck, NOT
beside it: `Outputs/` is the delivery folder and holds finished decks only. `validate_deck`
looks there first and then beside the deck, so anything built before the move still
validates. The `.A/.B/.C/.D` phase decks no longer go next to the output at all — they are written to a
temp directory and dropped through `atexit`. They used to land in the delivery folder and
were only removed on the happy path, so a build that died partway left four intermediate
decks there. Cleanup alone would not have been enough: the CSI mount allows creating and
copying but NOT deleting (`rm` returns "Operation not permitted"), so nothing written there
could ever be removed. Verified both ways: a clean build leaves the output folder holding
exactly one file, and a failed one leaves it empty.

### 2026-08-29 — build from the template shell, never from a client deck

CLAUDE.md contradicted itself: one paragraph said each program "clones-and-swaps from the
latest Marine FCU (1539) reference deck", while its own file listing and every builder said
the input is the stripped `templates/*_template.pptx` shell. The builders were right — that
is what `build_ars_gen.py` takes as argv[1].

Cloning a finished client deck carries that client's numbers, captions, branch names and
speaker notes into the next client's file. It is the mechanism behind the reference-leak
rule and behind `validate_deck.reference_leak_findings` existing at all: a figure that was
never swapped is indistinguishable from one that was. Corrected in CLAUDE.md,
`templates/TEMPLATES.md` and all three deck agents, which also still named the retired
Client Presentations drop as the delivery target.

### 2026-08-29 — MRPC template shell carried misleading slide titles

`mrpc_template.pptx` titled two slides "MRPC Revenue to Union Financial" and two "MRPC Key
Metrics". They are four DIFFERENT slides — `build_mrpc_gen` retitles them by position to
Revenue by Year, Revenue by Month, Card Portfolio and Key Metrics — so no client deck was
ever affected, and a real build validates at 0 FAIL with four distinct titles. But a shell
that does not describe what it becomes is a trap for the next person reading it, and it made
the deck look like it shipped duplicate slides. The shells now carry the titles the builder
produces, in both `mrpc_template.pptx` and the reference deck. Built output is unchanged,
verified by rebuilding 1075 (13 slides, 0 text differences).

`assemble_combined.section_slides` also stopped resolving the opening block by position. It
dropped indices 1 and 2 outright, assuming every deck opens with cover + Executive Summit;
that holds for a BUILT deck of any program (summit_slide.py inserts one), so no delivered
deck lost anything — but it is not true of the MRPC template shell, which has no summit
slide and whose divider sits at index 2. Slides are now identified by meaning, as CLAUDE.md
requires: the cover carries the "Executive Review" line, the divider carries the program's
benefits line. Verified to produce identical results to the old rule on a built deck.

### 2026-08-29 — the reporting month comes from the period, never the clock

`build_ars_gen`'s slide-1 note and the one-pager header both took `date.today()`. Correct
only while a deck is rebuilt in the month it ships; rebuild an August deck in October and
the note said October while the cover still said August.

Both now resolve the same way, so a one-pager and its deck cannot disagree: `ARS_PERIOD` /
`RPE_PERIOD`, then the `<yyyy.mm>` tag in the output filename, and nothing else. An
unresolvable period is a hard failure naming both ways to fix it.

There is deliberately no fallback. Not the clock, for the reason above. And not the
Executive Summit's month either — that was tried and reverted the same day: a Summit runs a
couple of times a year and only for attendees, while these are the MONTHLY reviews, so
deriving one from the other would be wrong ten months out of twelve (Aaron, 2026-08-29).
`summit_slide.summit_date()` still reads the date off the slide, but nothing in a builder
depends on it.

STYLE.md draws the distinction and it is easy to invert: the cover and one-pager header
carry the month the report is PRESENTED (STYLE.md:85), while the period pills and PTD
figures carry the DATA month (STYLE.md:44, explicitly "NOT the report/generation month").

### 2026-08-29 — superseded: two reporting months came from the wall clock

The slide-1 speaker note (`build_ars_gen.py`) and the one-pager header
(`build_ars_onepager.py`) both took `date.today()`. Correct only while a deck is rebuilt in
the month it ships; rebuild an August deck in October and the note said October while the
cover, which resolves `PRESENT_MONTH` properly, still said August.

Both now resolve the reporting month the same way — `ARS_PERIOD`/`RPE_PERIOD`, else the
`<yyyy.mm>` tag in the output filename — so a one-pager and its deck cannot disagree. Note
that STYLE.md draws a real distinction here and it is easy to get backwards: the cover and
one-pager header carry the month the report is PRESENTED (STYLE.md:85), while the period
pills and PTD figures carry the DATA month (STYLE.md:44). These are the first kind.

### 2026-08-29 — blank `Business?` counted two different ways in one deck

`ticket_calc.personal()` read `!= 'yes'` while `metrics_gen.personal()` read `== 'No'`, so an
account with a blank `Business?` cell was PERSONAL to one slide and BUSINESS to another in
the same deck. `product_mix_slide` had already settled the house rule by splitting the book
three ways — Yes, No, and everything else — so a blank is neither.

Both now import one definition from the new `build/ars_pipeline/odd_rows.py`. Blanks are
real: 1218 carries 271, 1204 carries 57, 1038 carries 2. No delivered deck moves — the blank
accounts in 1038 and 1204 have no trailing-quarter swipes, so `ticket_calc` skipped them
anyway, and 1218 ships no ARS deck. 1218's blended average ticket would move $44.87 -> $44.79.

### 2026-08-29 — validator gained three rules and the gate gained a test suite

Nearly every entry above this one is a wrong-number bug, but `validate_deck` was a text and
geometry linter. Added, with the calibration each needed to stay quiet on a correct deck:

* **figure identity** (REVIEW) — one labelled measure carrying two different values across
  slides, the shape of the Wellworth 1,077/1,026 split. Labels are discovered from the deck
  rather than hardcoded to four words. REVIEW, not FAIL: proving two renderings are the same
  measure needs a builder-emitted sidecar, and inference should not block a ship.
* **period consistency** — FAIL on a span whose stated month count contradicts its own
  endpoints, and on a caption naming a month after the data snapshot. REVIEW on an earlier
  month, which is sometimes correct (carried-forward ICS financials).
* **source-note provenance** — FAIL on a data slide with no note or no Source line, and on a
  note naming a different client. That last is the CoastLife-defaults defect;
  `reference_leak_findings` reads slide text only, so a leak in the NOTES was invisible.

`pytest tests/` (277 tests) now runs as step 0 of `qa_all.py` and a failure fails the gate,
because a classifier regression that mis-buckets 18,000 accounts still produces a deck that
passes every layout rule. The fixture is a synthetic 800-row ODD carrying no member data.

### 2026-08-29 — one source for the palette, the slide primitives and the date phrases

Not a behavior change — every rendered colour and every rebuilt deck is byte-identical,
verified by rebuilding 1204 (49 slides, 38 chart images matching, 0 text differences). Logged
because it changes where these are sourced from.

The palette had been re-declared in seven files under four naming conventions, and five
different greys were in service as "the light grey"; it now lives in `build/brand.py`. The
slide primitives lived inside `product_mix_slide.py` — a module about one slide — where ICS
and MRPC could not reach them; they now live in `build/shapes.py`. `slide_geometry.py` moved
to `build/` and all three builders call it, so the next ICS or MRPC layout fix lands in the
contract instead of in one deck. Date phrasing derives from `build/periods.py`; a literal
month is still fine when it is the month being described, but spans and counts are no longer
hand-computed. ICS/MRPC client sheets resolve through `rpe_env.resolve_client_json` under
`Inputs/VIP Data/<PROGRAM>/<id>-<Name>/`, indexed by that folder's `manifest.json`, so a
fresh checkout on the CSI machine is no longer missing them. The loose
`data/<id>_<program>.json` stubs in the repo are searched LAST: the README there records
them as superseded by the per-client folders, and they are an older pull — 1705's stub is
the 2026-07-13 capture against the folder's 2026-07-15, so an earlier search silently
returned the stale one.

### 2026-08-28 — orange KPI tile label read grey

`_tile` drew every tile label in GREYB (#CFDBE8), the muted grey picked for a NAVY tile.
Against ORANGE that pairing carries almost no contrast and the label reads as grey text on
the fill — Aaron flagged it on FNB&T 1537's Reg E Opt-In by Branch slide.

The label is now white on an orange tile and unchanged on navy. Affects every slide with an
orange tile: Reg E Opt-In by Branch, Excluded Accounts, Product Mix & ARS Eligibility, and
the swipe-tier movement slides.

### 2026-08-28 — Reg E new-account branch caption claimed a staffing effect

The caption under the by-branch chart on "Reg E Opt-In — Opened in Last 12 Months" read
"Lower-staffed branches lag; higher-touch branches lead on new-account opt-in." The ODD
carries no staffing count and no measure of customer contact, so neither half of that claim
could be shown from the data behind the chart. It was template text, so it shipped on every
ARS deck regardless of what a client's branches actually did.

It now states what the chart plots — "Dashed line = <rate> overall." — matching the sibling
caption on the all-accounts slide. Both templates are corrected and the builder also sweeps
the old sentence, so a re-seeded reference deck cannot reintroduce it silently.

### 2026-08-28 — "ODD" no longer appears on a slide face

The Mailing Response Summary subtitle ended "Offers sent and responders counted from the
ODD", naming an internal system on a client-facing page. Removed from all three variants of
the line — first mailing, trailing window, all mailings — so it is gone regardless of how
many mailings a client has. Slide 13's speaker notes still name the workbook, the ODD
extract, its pull stamp and the period, so the figures stay auditable. Verified across all
nine 2026.08 decks; that subtitle was the only on-slide mention.

### 2026-08-28 — ICS financial detail is absent when the workbook predates the deck

Replaces the carry-forward rule. A monthly build carried the last ICS workbook's financial
sections forward and stamped the DECK's period on them: 1537 FNB&T and 1676 True Sky both
showed "PTD · August 2026" over an ICS Financial Summary built from a 2026.06 and a 2026.07
workbook respectively.

The builder now resolves the newest ICS workbook for the client from
`Inputs/ARS & MRPC Reports/` and compares its period to the deck's. On a mismatch the
workbook-driven sections are ABSENT rather than re-dated, reusing the referrals-only path —
the section divider drops to "Referrals" and the agenda stops naming account value, ROI and
financial results. Referrals, Referral Trend, Results by Branch and the education slides are
unaffected.

2026.08 effect: 1075, 1509 and 1539 have current workbooks and keep their financial detail;
1537 and 1676 lose it (ICS section 28 → 14 slides); 1549 had no workbook and was already
referrals-only. The referrals-only log banner no longer claims "no ICS workbook has landed"
in this case, which was untrue when one landed and is merely older.

### 2026-08-28 — empty age chart no longer drawn; last n= notation removed

The Age Profile slide already wrote the right sentence when DOB is absent — "Date of birth is
not carried in this client's data extract" — and then drew the chart anyway: an empty axis
with a row of twelve zeros. Missing data is stated and never zeroed; only the text half of
that rule was implemented. The plot is removed, the statement takes its place, and the
Selection line no longer promises an age mix that is not shown. 1537 FNB&T is the case: the
DOB column is present and blank on all 29,852 rows, which is a data-sourcing question for
CSI, not a pipeline defect. The PNG is still generated — skipping it would leave the
template's image19 in place and display the REFERENCE client's age chart.

Separately, the two Selection captions still carrying "n=" (New-Account Debit Adoption,
First-Year Closure) now state their population as a bare parenthetical like every other
Selection line.

### 2026-08-28 — Before vs After by Offer chart was unreadable at mailing volume

Every mailing month was labelled with an "(n=…)" second line beneath it. At fifteen mailings
(Sugar River 1038) the axis rendered as overlapping mush and the per-bar dollar labels
overprinted each other. The axis now labels every Nth mailing capped at 8 ticks, always
including the newest; "(n=…)" moves to the speaker notes as NU / TH per mailing, so the count
behind each bar stays auditable rather than dropped; per-bar dollar labels are drawn only
below 8 mailings, above which the y-axis carries the scale.

Affects the seven 2026.08 clients with more than 8 mailings: 1038, 1075, 1204, 1509, 1539,
1676, 1705. Slide 19's Mean chart needed nothing — its rotated labels handle fifteen. Same
shape as the excluded-accounts footnote bug: correct on Wellworth's single mailing, wrong at
volume, and passed by the gate because nothing overflows a box.

### 2026-08-28 — clients.md decides what gets built, not the presence of a data file

Program membership was inferred from whether input files happened to exist. That is how
CoastLife 1705 kept producing an ICS section after cancelling — their ICS data was still on
disk. `clients.md` now records intent and is the authority; leftover program data and a
2026.08 DCO file are explicitly not signals to build.

Confirmed by Aaron the same day: PointBank 1174 off the books entirely; Truliant FCU 1658 has
no RPE at all; CoastLife 1705 ICS cancelled with ARS continuing; Canandaigua 1437 ends
2026-10-31 with no further reviews; 1218, 1477 and 1502 MRPC-only; 1632, 1734 and 1738
ICS-only. Building the roster surfaced that 1204 FSB Michigan had 2026.08 inputs and no deck.

### 2026-08-28 — Excluded Accounts footnote is measured, not assumed

The footnote block sits at 6.05in with the logo band starting at 6.78in, so it holds two
lines. Which observations exist varies by client — 1549 has no Mail column at all, 1537 has
all three and estimated five lines, which failed the gate. Lines are now measured at the 16pt
floor `restyle_fonts` enforces and truncated to what fits; every observation still goes to
the speaker notes, so nothing is lost, only moved. The mail-funnel sentence is shortened to
one line.

The stale-caption check also stopped flagging derived pills. It compared any
template-identical dated text and caught "PTD · June 2026" on four of CoastLife's ICS slides,
correct at the time because ICS financials carried forward. It now covers caption prose over
40 characters, which still guards all 21 real template captions and exempts three pill forms
that each have their own swap guard.

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


### 2026-08-27 — tier response rate denominators (shipped)

Landed in `metrics_gen.mail_summary` (`metrics_gen.py:184-199`): `nu_sent` and
`th_sent` split on `<mon> Mail`, each group is rated against its own base, the
trailing total pools each group's own recipients rather than averaging the
per-mailing rates, and an unknown offer code raises the warning the PRD asked
for. Verified 2026-08-29. The description of the defect follows, kept because
the reasoning is the reason the fix looks the way it does.

`NU 5+` and `Threshold Met` on the ARS Mailing Response Summary divided by total
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
rates from the workbook rather than the ODD. The generator fix has since landed,
so v3 is superseded — regenerate CoastLife rather than referring to it.

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
