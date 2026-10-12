# PRD — the RPE Client Performance artifact

Date: 2026-09-11
Owner: Aaron Burgard
Status: Shipped 2026-09-08; build readiness and provenance added 2026-09-09/10.
Live at `https://claude.ai/code/artifact/71e542f6-cb48-4386-ae73-708e513c854b`.

---

## Problem

Every figure this pipeline produces lives inside one client's deck. That is correct
for a deliverable and useless for a question about the book:

- *Which ICS client is furthest from goal this month?* — open nine decks.
- *Whose ARS revenue fell?* — open nine more, or re-run the extractors by hand.
- *What can I still build this cycle, and what is it waiting on?* — a different
  tool again (`deck_status`), on a different screen, answering a different half of
  the question.

A cross-client view existed nowhere, so it got rebuilt ad hoc each time it was
wanted, from whichever numbers were nearest to hand. That is the failure mode this
repo already knows by name: a second place a figure is calculated is a second
figure.

## Success criteria

1. **One page** carries every roster client across all four programs — ARS, ICS,
   MRPC and CashPlease — with no per-client digging.
2. **Every figure comes from the input a deck builder reads**, through the same
   extractor, so the page and the deck cannot disagree. No second calculation and
   no second store.
3. It **refreshes without anyone running anything**, and rolls to a new cycle the
   morning that cycle's inputs land.
4. It is **never republished over nothing** — a rebuild finding identical inputs
   does not churn the page.
5. **The link never changes.** People hold this URL.
6. It answers **what can be built**, not only what was built.

## Scope

**In**

- A **Client overview** first *(2026-09-14)*, from each client's ODD extract. It shows open
  checking accounts (total, business, personal), the 3-month average of personal swipes and
  of NSF/OD items per month, and 12-month personal openings and closings, all with the decks'
  definitions (`scripts/perf_overview.py`). Each row names its extract's month and is tagged
  when that is older than the cycle's.
- One section per program: a ranked bar, a metrics table, trend sparklines. Every table
  sorts by any column with a value *(2026-09-14)*. A numeric column sorts highest first.
- A **build readiness** section for the current period: ready or blocked per
  client, what it is blocked on, and one chip per required input. Every column
  sorts (ascending → descending → off), remembered per viewer (2026-09-14).
  **A period picker in its header** *(2026-10-12)* switches the section to the cycle
  period, either of the two before it, or the one after: its readiness, the decks built
  FOR that period and the sends recorded AGAINST it all swap together, so the Sent column
  starts clean for the period chosen — nothing carries over — and a Mark sent is recorded
  against the period showing. The choice is shared through the artifact's store, so
  every viewer sees the same period; the page is static, so the refresh builds each
  period's readiness in full (`readiness_periods`, `period_views`). The figures above
  the section stay on the reporting period.
- **Every current client across the five CSMs** *(2026-09-14)*. That is the `clients.md`
  roster plus every client with reports filed on `Velocity_clientreports` for the newest
  month at or before the cycle, less the clients `clients.md` marks as stopped. Programs
  for a client `clients.md` does not list are inferred from that month's files and tagged
  "from data". A client with no program data this month is listed under all products.
- A link to the pipeline workflow page: `workflow.html`, published beside the page from
  `scripts/perf_workflow.html`. The daily refresh does not republish it.
- ARS shows **revenue to CSI** for the current completed month *(2026-09-14)*: the workbook's
  current-month "Total Costs", emitted by both ARS extractors as `cur_costs`. It replaces the
  incremental profit and revenue callouts. In every table a total column comes before its
  last-month figure.
- CSM, product and client filters, each row led by an All chip. The Clients row folds, and is
  closed by default. While all are selected, a
  click shows only that one; later clicks add or remove others, down to none. Chips are
  white while their whole row is selected, blue when on and light gray when off. *(CSM added
  2026-09-14.)* A client's CSM is the account-manager folder its reports land in on
  `Velocity_clientreports`, else the `CSM` column of the CashPlease roster in `clients.md`,
  else the CSM on its CashPlease settings record; a client nothing names is shown as
  Unassigned, never given a default CSM.
- A provenance block naming the source of every figure on the page.
- A last-updated stamp, carrying the time as well as the date.
- CashPlease peer comparison over **current clients only** *(2026-09-14)*, rebuilt from their
  own packs with `cp_extract`'s formulas. Charge-off % and the share of accounts with loans
  cannot be derived that way and are shown as absent. A program inferred from data with no
  activity in six complete months is not shown; a `clients.md` program is tagged instead.

**Out**

- **Not client-facing.** Nothing here is built to the deck style contract, and no
  figure on it should be pasted into a deck. The builders remain the source for
  anything a client sees.
- **Not a replacement for the delivery dashboard.** `Build Artifacts/deliveries.json`
  stays the record of what was sent. This page's Mark sent button writes a row to the
  artifact's own store, and the refresh's `--merge-sent` folds those rows into
  `deliveries.json`, where an existing entry wins over any plain row. *(Corrected
  2026-09-14: this used to say the page never writes sent-state, which stopped being true
  when Mark sent merged to main.)* The one exception is an undo (2026-09-14): clicking a
  sent date and confirming writes a row naming the date it cancels, and marking sent again
  afterwards writes a send naming the date it replaces. `--merge-sent` removes or replaces
  the entry only while `deliveries.json` still holds exactly that date, so a stale row
  can never erase a newer send.
- **Not self-publishing.** See Constraints.
- No editing and no data entry beyond Mark sent and its confirmed undo.

## Constraints

1. **It reads only what the builders read.** `Inputs/` sorted by kind, the VIP
   store, `Build Artifacts/*.figures.json`, `Build Artifacts/deliveries.json`. It
   may not keep a copy of anything. Two stores for one fact is the defect that
   shipped month-old ICS figures in August.
2. **The period is derived, never assumed** — the newest `<yyyy.mm>` on an ARS
   workbook in `Inputs/ARS Workbooks/`.
3. **Publishing needs the Artifact tool, so the script cannot publish.**
   `refresh_performance_dashboard.py` writes the page and exits with
   `STATUS: changed|unchanged`; the Claude scheduled task `rpe-dashboard-refresh`
   (daily 08:30, after the 08:00 source watch) republishes on `changed` and then
   runs `--mark-published`.
4. **Republish to the URL. Never create a new artifact.** A new one strands
   everybody holding the old link.
5. **Self-contained HTML** with the dataset embedded — no runtime fetch, no
   database, no server. It has to render for anyone the link is shared with.
6. **Theme-aware.** Light and dark both, including the system default.
7. Edits go to `scripts/perf_dashboard_template.html`, **never to the published
   copy**, which is overwritten on the next refresh.

## How it works

```
08:00  watch_sources.py --copy --prune --mail
         CSI shares + Outlook  ->  Inputs/<kind>/
08:30  rpe-dashboard-refresh (Claude scheduled task)
         refresh_performance_dashboard.py
           Inputs/ARS Workbooks + DCOs   -> ARS extractors
           Build Artifacts/*.figures.json -> mailing response
           Inputs/VIP Data/{ICS,MRPC}     -> referrals, enrollments
           Inputs/Weekly Summaries        -> MRPC weekly, CashPlease weekly
                                             (CP via the CashPlease repo's cp_extract)
           deck_status.collect(period)    -> build readiness
         -> Build Artifacts/perf_dashboard/{dataset.json, rpe_dashboard.html, state.json}
         -> STATUS: changed | unchanged
       on `changed`: publish to the URL, then --mark-published
```

## Decisions

**2026-09-08 — one section per program, ranked, cross-client.** The unit of the
page is the program, not the client, because the questions it exists to answer are
comparisons across clients within a product.

**2026-09-08 — within a cycle, every client shows its own newest figures.** A
cycle-only page went blank for three ARS clients and every deck on the first
morning of a month. A row whose newest workbook is older than the cycle is shown
and **tagged**, not hidden: absent data is stated, never zeroed — the same rule the
builders follow.

**Mailing response comes from the shipped deck's figure sidecar, not the
workbook.** The workbook's mailing rates use a different denominator than the
mailed population: 1549 read 16.3% from the workbook against 10.7% on the deck for
the same drop. The sidecar is what the client was actually shown.

**CashPlease figures run through the CashPlease extractor**
(`build/cashplease_pipeline/cp_extract.py`) so the page and the CashPlease decks are
computed once, in one place. It was resolved as an external repo until 2026-09-11 — see
Open 5.

**CashPlease may report a later date than its neighbours.** CP is weekly and always
uses the most recent workbook; ARS/ICS/MRPC are monthly. The divergence is intended
and visible, not smoothed.

**2026-09-09 — the roster section became build readiness.** It listed the newest
deck BUILT. What is in front of you at the start of a cycle is what CAN be built and
what is missing. The answer comes from `deck_status.collect()` rather than a second
implementation, so this page and the delivery dashboard cannot disagree about
whether a client is ready. A failure there degrades the section to "not checked"
rather than failing the refresh.

**2026-09-09 — readiness reflects local inputs only.** The CSI shares need the VPN;
checking them here would make the page's freshness depend on network state. The
provenance block says so plainly rather than implying a completeness it does not
have.

**2026-09-10 — provenance is a bulleted list**, one line per program plus one for
readiness. It was a single paragraph carrying five different sourcing rules, which
is a paragraph nobody finishes.

**2026-09-10 — the last-updated stamp carries the time.** The page can be refreshed
several times in a day. `content_hash` already excludes `generated`, so a timestamp
there cannot cause a spurious republish.

**Change detection compares figures, not runs.** The hash excludes the generation
date, so rebuilding the same inputs tomorrow reports `unchanged`.

**2026-09-15 — a workbook a month behind is shown the same way for every client.** 1075
Austin Bank (on the roster) showed its 2026.08 workbook, tagged, while seven clients not on
the roster in the same state lost their ARS row, because their programs were inferred from
this month's share files alone. An inferred client is now on ARS when Inputs holds its
workbook from the last two months. MRPC rows are tagged when their VIP sheet is older than
the cycle, like ARS, ICS and the Client overview.

**2026-09-15 — CSM action items come first, and nothing is mapped for them.** For current
ARS clients: a Lift Matrix the data team flags out of date in the workbook filename (Aaron
chose that flag over the Lift Matrix tab's end date), and ODD codes the client's code tables
in the ARS database do not list. The items that decide ARS eligibility (Product, its
Personal/Business flag, Account Status) list first; Mail Flag, which decides who is mailed but
not eligibility, and Reg E follow. The pipeline never
maps a value; the CSM has the client correct the code sheet. The code tables come from a
database export whose settings table holds plaintext FTP credentials, so
`scripts/ars_code_tables.py` keeps only the code tables, found by id column, and the export
itself is never copied or committed.

## Open

1. **Five CashPlease-only clients show "not checked"** for readiness. They are not
   on the roster `deck_status` reads, which covers the monthly ARS/ICS/MRPC
   cadence. Either `deck_status` learns the CashPlease roster, or the section
   states why those rows are blank.
2. **No automated render check.** The page's markup and JavaScript are verified
   structurally before publishing, but nothing renders it and looks. The preview
   pane will not drive a local file, and the published page needs a signed-in
   browser. A broken layout would reach the reader first.
3. **1632 WesBanco and 1734 Altamaha** show two decks each — an ICS-only and an
   ICS-CP combined. The page reports what is in `Outputs/`; the duplication is a
   delivery question, not a dashboard one, but it reads as an inconsistency here.
4. **The refresh depends on the 08:00 watch having run.** If the watch fails, the
   page silently reports yesterday's inputs as current. It has no signal of its own
   that the inputs it read are stale.
5. **An absent section is reported, but nothing fails.** The CashPlease extractor moved
   into this repo on 2026-09-10; the refresh went on resolving the old standalone
   checkout, and on 2026-09-11 every CashPlease figure — all eight clients — read as
   missing while the run exited `changed`, ready to publish. `tests/test_perf_dashboard_export.py`
   now pins the extractor's path, but that is one source covered by name. A section that
   is empty for EVERY client is a different thing from one client having no data, and
   the refresh does not yet distinguish them.
