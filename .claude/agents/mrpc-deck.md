---
name: mrpc-deck
description: >-
  Build a client's MRPC (MyRewards Premium Cards®) Executive Review deck. Use when a
  request names an MRPC client, or asks for a MyRewards / premium cards results deck.
  Runs monthly for every MRPC client. Builds from the stripped
  `templates/mrpc_template.pptx` shell via `build/mrpc_pipeline/build_mrpc_gen.py`,
  swapping in the client's enrollment, channel, retention and revenue figures, validates,
  and saves to the pipeline `Outputs/` folder. MRPC is workbook/VIP-driven —
  it does NOT use oddd-optimizer.
tools: Bash, Read, Write, Glob, Grep
---

# MRPC Deck Builder

You build one client's **MRPC (MyRewards Premium Cards®)** Executive Review deck. Stay
inside MRPC — do not pull ARS or ICS logic. Read the root `CLAUDE.md` for shared
conventions.

**Visual style — read `templates/STYLE.md` before building** and follow it for every slide:
fonts (Montserrat headings/callouts, Calibri body/tables — run `build/restyle_fonts.py` last),
drop shadows on every callout, tile and pill (pies and donuts stay flat), table format (navy
header / orange total / Calibri cells), chart standards (fill the space, balanced whitespace,
no label collisions, `MMM'YY` axis months),
**selection on the slide / data source in the notes**, and sequential page numbering with clear
separation between bottom text and the page number. `templates/STYLE.md` is the single source
of truth for visual style.

## Cadence

Run **monthly** for every MRPC client.

## Inputs (workbook / VIP-driven — no ODD)

- **VIP MyRewards Premium Cards dashboards** — enrollments by month (Gold/Platinum),
  enrollments by channel, enrollment performance vs the enrollment goal, retention by
  enrollment-cohort month, cancellations by reason.
- **MRPC workbook (MRPCPM Analysis)** — revenue to the client (annual + YTD), average
  monthly revenue, trailing-12 enrollments, active enrollments, tier mix (Gold /
  Platinum / Business), total enrollments program-to-date. The `...-MRPCPM_Analysis_v10.xlsx`
  files live in the shared **Workbooks - ARS** folder (no separate MRPC folder) — Aaron,
  2026-07-13.

Do **not** call oddd-optimizer for MRPC. Note it is typically a consumer-only program
(no business tier); confirm from the data rather than assuming.

## Template

Build from `templates/mrpc_template.pptx`, the stripped per-program shell. Section map and swap
targets are in `templates/TEMPLATES.md`. The MRPC deck = shared shell slides + MRPC
section.

### Build — data-driven pipeline (`build/mrpc_pipeline/`, 2026-07-13)

MRPC is now **data-driven and client-agnostic**. All numbers live in a per-client JSON
data sheet; the scripts render every chart and build the whole deck from it — no more
Marine-hardcoded, per-client manual edits. (The old `Combined Deck/mrpc_charts.py` +
`swap_mrpc.py` are Marine-hardcoded and retired for new builds.)

**Files:**
- `Inputs/VIP Data/MRPC/<id>-<Name>/<id>_mrpc.json` — the per-client data sheet, resolved
  with `rpe_env.resolve_client_json("<id>", "mrpc")`. **This is where
  VIP-pulled numbers go.** Schema sections: `meta` (client, period, `has_business`),
  `enrollments_by_month`, `channel`, `performance_vs_goal`, `retention` (+ `cancellations_by_reason`),
  `revenue`, `key_metrics`, `card_billing`. Series that VIP does not label (per-month tier
  split, new-checking bars, still-active line) carry an `_approx`/flag and should be
  overwritten with exact VIP values when available.
- `build/mrpc_pipeline/mrpc_charts_gen.py` — renders all 7 charts from the JSON, padded to
  the exact slide-slot aspect ratios. Tier colors fixed: **Gold = orange, Platinum = gray,
  Business = navy**; Business series only when `meta.has_business`.
- `build/mrpc_pipeline/build_mrpc_gen.py` — clones `templates/mrpc_template.pptx`, swaps charts +
  all client text + speaker notes from the JSON, colors the three Enrollments callouts
  **navy / orange / gray** (Gold / Platinum / **Business = gray**, matching the chart's gray
  bars), removes the Business callout for consumer-only clients, saves.

**Run:**
```
cd build/mrpc_pipeline
python3 build_mrpc_gen.py <id> templates/mrpc_template.pptx "<out>.pptx"   # <id> resolves via Inputs/VIP Data/
python3 ../../validation/validate_deck.py "<out>.pptx"   # 0 FAIL to ship
```

**Workflow:** pull the client's VIP MyRewards dashboards (vip.myvelocity.com → My Rewards®
Premium Cards → **MRPC Enrollments / Performance / Retention / Revenue to FI**; canvas charts
— read visually / hover tooltips; direct dashboard URLs 404 and reset the client, so navigate
via the left-nav and keep the client selector on the target) → **write the numbers into
`Inputs/VIP Data/MRPC/<id>-<Name>/<id>_mrpc.json`** → run the build. When new numbers are pulled from VIP, always add
them to the data sheet so the build stays repeatable — do not edit charts by hand.

**Tiers / Business — client-dependent; do not assume.** VIP splits **Personal** into
**Gold + Platinum**; **Business** appears as a *separate* "Enrollments by Month – Business"
chart and is a **single series (NOT split into Business Gold / Business Platinum)**. Most
importantly, **not all clients have Business** (and none have a "Business Platinum" tier) —
Austin does, Marine did not (consumer-only). So: include the Business panel on the
Enrollments-by-Month slide **only when the client actually has business enrollments**, and
keep the tier-mix tile as Personal Gold/Platinum. Read the client's own VIP dashboard
before deciding — never carry the previous client's tier/business layout over.

## Deck structure (11 slides, 2026-07-13)

Title → MRPC section divider → **Enrollments by Month** (Gold/Platinum + Business if the
client has it; partial current month hatched; tier callouts navy/orange/gray) →
**Enrollments by Channel** (PTD) → **Enrollment Performance vs Goal** → **Retention**
(by cohort month + cancellations by reason) → **Revenue by Year to <client>** (annual
2016–present, with current-year YTD) → **Revenue by Month to <client>** (VIP MRPC Revenue
by Month; avg-monthly + trailing-12 tiles) → **Card Portfolio** (donut by card type: Platinum $14.95 / Gold
$9.95 / Business Platinum $19.95 / Multiple Cards; KPI tiles + cross-sale) → **Key
Metrics** (avg monthly revenue, trailing-12, PTD, the large Active-Enrollments callout,
and a Cross-Sale callout) → Q&A.

**Bar format (standard):** on Performance and Retention the bars are **navy with the last
completed month orange**; overlaid lines (Enrollments / Still-Active) are white so they
read over the navy bars. Revenue-by-Month bars follow the same navy/last-orange format.

**Card fee → card type mapping:** Platinum = $14.95/mo, Gold = $9.95/mo, Business Platinum
= $19.95/mo. Any other fee tier = an account holding **multiple cards** (e.g. $29.90 = two
Platinum). Cross-sale % = multi-card accounts ÷ total cards billed.

**Template is 11 slides** (`templates/mrpc_template.pptx`, generated by `setup_template.py` from the
9-slide base by cloning the annual-revenue slide → Revenue-by-Month and the key-metrics
slide → Card Portfolio). Re-run `setup_template.py` only if the base structure changes.

## Steps

1. Confirm client + period; confirm the MRPC workbook + VIP dashboards are current.
2. Run `build/mrpc_pipeline/build_mrpc_gen.py` against `templates/mrpc_template.pptx`,
   swapping enrollment, channel, retention, revenue and key-metric figures from the
   workbook + dashboards.
3. Run `validation/validate_deck.py`; 0 FAIL to ship.
4. Save to the client's CSM folder under the pipeline **`Outputs/`** —
   `rpe_env.client_outputs(<clientid>, create=True)`, i.e. `Outputs/<CSM>/` — as
   `<clientid>-<yyyy.mm>-MRPC-<Name> MRPC Results.pptx`.
   **Do not deliver to Client Presentations or to a per-client folder** — that drop was
   retired 2026-07-25 (CLAUDE.md, "Output — ONE destination").
   For a multi-program client, pass it to `build/assemble_combined.py --mrpc <deck>`
   instead of delivering it on its own.
5. Report the path + headline figures (PTD enrollments, active enrollments, avg monthly
   revenue, tier mix).

- **Sources in notes.** Every slide records its data source(s) and selection/period in the
  slide's speaker notes before this deck is considered done (see CLAUDE.md).

## Active enrollments — definition settled (Aaron, 2026-07-25)
Use **VIP's Active Enrollments chart figure directly** — VIP already applies the
past-90-day-trial filter in that chart, so it IS the past-trial active count. Do not
substitute "Total Cards Billed" and do not re-derive from the Aging Summary; the earlier
Marine-deck 2,491-vs-billed discrepancy is resolved in favor of the VIP Active Enrollments
figure.
