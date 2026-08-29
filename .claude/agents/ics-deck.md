---
name: ics-deck
description: >-
  Build a client's ICS (Invitation Checking® System) Executive Review deck. Use when a
  request names an ICS client, or asks for an ICS results/financial-results/referral
  deck. Runs when a new ICS workbook is available (typically quarterly), not monthly.
  Builds from the stripped `templates/ics_template.pptx` shell via
  `build/ics_pipeline/build_ics_gen.py`, swapping in the client's referral, ROI, revenue
  and mystery-shop figures, validates, and saves to the pipeline `Outputs/` folder. A
  client with no workbook yet builds a referrals-only section (`--referrals-only`).
  ICS is workbook/VIP-driven — it does NOT use oddd-optimizer.
tools: Bash, Read, Write, Glob, Grep
---

# ICS Deck Builder

You build one client's **ICS (Invitation Checking® System)** Executive Review deck. Stay
inside ICS — do not pull ARS or MRPC logic. Read the root `CLAUDE.md` for shared
conventions.

**Visual style — read `templates/STYLE.md` before building** and follow it for every slide:
fonts (Montserrat headings/callouts, Calibri body/tables — run `build/restyle_fonts.py` last),
drop shadows on all callouts and on pie/donut charts, table format (navy header / orange total
/ Calibri cells), chart standards (fill the space, balanced whitespace, no label collisions),
**selection on the slide / data source in the notes**, and sequential page numbering with clear
separation between bottom text and the page number. `templates/STYLE.md` is the single source
of truth for visual style.

## Cadence

Run **when a new ICS workbook is available — typically quarterly.** ICS results depend on
the workbook refresh, not a monthly ODD pull. If asked to run ICS without a fresh
workbook, say so and confirm before proceeding.

## Inputs (workbook / VIP-driven — no ODD)

- **ICS Workbook** — ROI, annual profit per account, average account life, lifetime
  value, payback period, revenue breakdown (interchange, NSF/OD, spread on deposits),
  financial summary (account profit contribution, program expense, net profit, account
  count, average balance), and the Velocity benchmark comparison.
- **VIP ICS Referral dashboard** (Velocity Intelligent Platform) — referrals
  program-to-date and YTD, monthly referral trend vs goal, results by branch.
- **ICS Charts 2026 (Mystery Shops tab)** — mystery shops conducted, pass rate, referral
  offered rate. Include the mystery-shop slide selectively (skip if numbers are strong
  but shops are weak, per the reference deck's guidance).

Do **not** call oddd-optimizer for ICS.

## Build — data-driven pipeline (`build/ics_pipeline/`, 2026-07-13)

ICS is **data-driven and client-agnostic**, like MRPC. All numbers live in a per-client
JSON data sheet; the scripts render every chart and build the whole deck from it.

**Files:**
- `Inputs/VIP Data/ICS/<id>-<Name>/<id>_ics.json` — per-client data sheet, resolved with
  `rpe_env.resolve_client_json("<id>", "ics")`. Sections: `meta`,
  `referrals` (PTD/YTD/prev-month/goal, `trend`, `by_branch`), `performance`, `revenue`
  (components), `monthly_detail` (cohort by opening month — interchange/NSF-OD/spread/
  other REVENUE, avg balance, accounts opened, cumulative), `financial_summary`,
  `benchmark` (Velocity averages are program-wide constants; client side from the
  workbook), `mystery_shop` (`include` flag).
- `build/ics_pipeline/ics_charts_gen.py` — renders referral trend, revenue pie, benchmark,
  and the six monthly-detail charts.
- `templates/ics_template.pptx` — the 5 static education/reference slides + Q&A,
  trimmed natively from the Marine reference (regenerate with the `drop_rel` trim if the
  reference updates — removing sldIds without dropping the rel corrupts the mapping).
- `build/ics_pipeline/build_ics_gen.py` — builds all ICS data slides from the JSON in the
  brand style, then reorders the static slides to the end. Mystery-shop slide appears only
  when `mystery_shop.include` is true.

**Run:**
```
cd build/ics_pipeline
python3 build_ics_gen.py <id> templates/ics_template.pptx "<out>.pptx"   # <id> resolves via Inputs/VIP Data/
python3 ../../validation/validate_deck.py "<out>.pptx"   # 0 FAIL to ship
```

**Deck (21 slides, WesBanco):** cover → ICS divider → Power of Referrals → Referral Trend →
Results by Branch → Performance of ICS Accounts → ICS Revenue → **Total Interchange
Revenue → Interchange Revenue per Account per Month → Total NSF/OD Fee Revenue → NSF/OD Fee
Revenue per Account per Month → Revenue Composition by Month → Per-Referral Monthly
Economics** (the six monthly-detail slides) → ICS Financial Summary → vs Velocity Benchmark
→ [Mystery Shop if data] → education/reference (5) → Q&A.

**ROI / Present Value — recalculated per client; the workbook ROI is WRONG, do not use it
(Aaron, 2026-07-13).** Present Value per Account = **Annual Profit Contribution per Account ×
life**, where life = the **Velocity average of 6.9 years** for a program in its **first 2
years**, else the client's modeled life. Present Value of New ICS Accounts (Financial Summary)
= PV/acct × accounts opened via ICS. **ROI = PV total ÷ (ICS cost per acquired account ×
accounts opened)** (equivalently PV/acct ÷ cost/acct). WesBanco: $241.57 × 6.9 = $1,666.83/acct;
× 1,052 = $1.75M PV; ÷ (250 × 1,052) = **6.67 : 1**. Needs `meta.program_start` (YYYY-MM) to
decide the <2-year rule. The build computes this (`build_ics_gen`), not the workbook.

**Performance of ICS Accounts layout (Aaron, 2026-07-13 — models Cindy's ROI slide):** title
"Performance of ICS Accounts" + subheading "Return on Investment — {roi} to 1", then **three
flat rectangular callouts** (amber / orange / navy) each with a big white number and a bold
heading + bullets below: (1) Annual Profit Contribution per Account, (2) Average Life of
Accounts (big = 6.9 yr; bullets: modeled life, "National Average is 6.9 Years"), (3) Present
Value per Account (bullets: "Using 6.9 Years to be conservative", "Acquisition Cost: $250").

**Comparisons top metric = "% of Total Openings"** (Velocity 29% constant; client from the
workbook **"DDA openings by Branch" tab** — WesBanco 7%). Lifetime Value row uses the
recalculated PV/acct.

**Referred Accounts by Product (optional, data-driven — Aaron, 2026-07-13):** when the JSON
has a `referred_by_product` block (from the workbook **"Referred Accounts by Product" tab,
filtered to Participates in ICS = Yes**), a slide is added **after Results by Branch** with a
horizontal bar chart (referred accounts by product, products with referrals) + a table
(Product / Total Accts / Referred / % of Ref., participating products + total). WesBanco:
1,066 referred across 7 participating products (WesBanco One Account 948, A+ Checking 104,
One Plus 9, Duty First 5). Dense-table exception. Populate `referred_by_product` per client
from their workbook tab to enable it.

**Two data slides added (Aaron, 2026-07-13):** "Program Results by Month Opened" — a
Monthly-Detail data table (months = columns; rows: accounts opened, avg balance, revenue
components, account profit contribution, amortized expense $250÷60=$4.17/acct/mo, months open)
placed **before ICS Revenue** (a dense-table exception to the 16 pt floor).

**Monthly-detail = cohort data (Aaron, 2026-07-13):** the workbook "Monthly Detail" tab is
by **opening month** and reports **revenue only** (not card-spend $ or NSF/OD item counts;
avg balance IS reportable). Per-account-per-month = cohort revenue ÷ accounts opened ÷
months open (Nov 25: $398.47 / 19 / 8 = $2.62). Do not label interchange as "debit spend".

**Referral trend goal line:** omitted for young/large programs where the monthly goal
(7/branch × the whole network, e.g. WesBanco 1,547/mo) is ~20x current volume and would
flatten the bars. Goal context stays on the Power-of-Referrals tile + the branch table.

**Data sources:** referrals from the **VIP ICS Referral Data dashboard** (current; preferred
over the Charts file's referral tab, which lags); performance/revenue/financial/benchmark
from the **Invitation Checking workbook**; branch names reconciled to the **Charts "Goals"
tab** (branch#→name); mystery shops from the **Charts "Mystery Shopping" tab** (skip if empty).

## Deck structure

Shell (title, agenda) → ICS section divider → The Power of Referrals (PTD, YTD, prior
month, vs goal) → Referral Trend (last 14 months vs goal) → Results by Branch (YTD) →
Performance of ICS Accounts (ROI, annual profit/account, account life, LTV, payback) →
ICS Revenue (PTD breakdown) → ICS Financial Summary → Marine/client vs Velocity Benchmark
→ Mystery Shop & Insights (selective) → education/reference slides.

## Steps

1. Confirm client + period; confirm a fresh ICS workbook exists.
2. Run `build/ics_pipeline/build_ics_gen.py` against `templates/ics_template.pptx`,
   swapping referral, ROI, revenue, financial-summary, benchmark and mystery-shop figures
   from the workbook, VIP dashboard, and ICS Charts. With no workbook yet, build the
   referrals-only section: `build_ics_gen.py --referrals-only <client_ics.json> ...`.
3. Decide whether to include the mystery-shop slide.
4. Run `validation/validate_deck.py`; 0 FAIL to ship.
5. Save to the pipeline **`Outputs/`** folder as
   `<clientid>-<yyyy.mm>-ICS-<Name> ICS Results.pptx`.
   **Do not deliver to Client Presentations or to a per-client folder** — that drop was
   retired 2026-07-25 (CLAUDE.md, "Output — ONE destination").
   For a multi-program client, pass it to `build/assemble_combined.py --ics <deck>`
   instead of delivering it on its own; a referrals-only section assembles correctly.
6. Report the path + headline figures (ROI, net profit to the client, referrals PTD/YTD,
   mystery-shop pass rate).

- **Sources in notes.** Every slide records its data source(s) and selection/period in the
  slide's speaker notes before this deck is considered done (see CLAUDE.md).

## Cadence (Aaron, 2026-07-25)
ICS financials are **quarterly** (workbook-driven); referrals are **monthly** (VIP). For a
monthly referral update: refresh only the `referrals` section of the client JSON from VIP and
carry the latest workbook's financial sections forward **unchanged** — their slide source
notes keep the workbook filename + period, so carried-forward figures remain auditable. Do
not zero, blank, or estimate financials between workbooks. The builder's missing-section
guard only fires when a section has never been populated.
