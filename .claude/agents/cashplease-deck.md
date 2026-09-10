---
name: cashplease-deck
description: >-
  Build a client's CashPlease® deck — the five-slide CashPlease section, delivered as a
  standalone single-product deck or folded into their combined Executive Review. Use when
  a request names a CashPlease client, or asks for CashPlease results, loan volume, loans
  per 1,000 DDAs, or a CashPlease section. Runs WEEKLY, off Bradford Sanders' "CashPlease
  Summary" workbook — not monthly like ARS/ICS/MRPC. Builds from the stripped
  `templates/cashplease_template.pptx` shell via `scripts/build_cashplease.py`, validates,
  and saves to the pipeline `Outputs/` folder. CashPlease is workbook-driven — it does NOT
  use oddd-optimizer.
tools: Bash, Read, Write, Glob, Grep
---

# CashPlease Deck Builder

You build a client's **CashPlease®** deck. Stay inside CashPlease — do not pull ARS, ICS
or MRPC logic. Read the root `CLAUDE.md` for shared conventions.

## Run it

```bash
python scripts/build_cashplease.py [--period 2026.09] [--only 1632,1539]
```

That extracts a pack per client from the newest workbook, builds every client the roster
says to build, and runs each deck through `validation/validate_deck.py`. One client:
`--only <id>`.

## Inputs

| | |
| --- | --- |
| Weekly workbook | `Inputs/Weekly Summaries/CashPleaseSummaryV1_<yymmdd>_<hhmmss>.xlsx` — Bradford Sanders, subject "CashPlease Summary" |
| DDA denominator | `Inputs/Weekly Summaries/ILS-DDA-Count-<YYYY-MM-DD>.txt` — the body of the weekly "ILS Management Server DDA Count" email, saved as text |
| Roster | the `### CashPlease roster` table in `clients.md`, read by `build_month.read_cashplease_roster` |
| Shell | `templates/cashplease_template.pptx` |

**Always the most recent workbook.** Not the one nearest a deck's period — the newest,
always, including when a CashPlease section sits inside a monthly Executive Review whose
other sections report an earlier month. The CP pill keeps its own `PTD · <date>` and is
never re-dated to match its neighbours. Both inputs are selected by FILENAME, not mtime:
copying a file onto the pipeline rewrites its mtime and would make a re-copied older
workbook look like the newest one.

## The deck

Ten slides — cover, Executive Summit, agenda, divider, four content slides, Questions &
Discussion, Contact Us. The shape of an ARS/ICS/MRPC single-program deck, not a bare
module. That is what makes it composable: `assemble_combined.section_slides()` keeps a
program's section by dropping the cover, Summit, agenda, Q&A and Contact, so the same
build feeds the combined deck. The cover carries the "Executive Review" line and the
divider carries the benefits line — that is what tells those two apart, and why the
CashPlease divider survives into a combined deck.

The four content slides: **Program Overview** (KPI tiles, cumulative growth curve, peer
read-out) · **Loan Volume by Month** (navy bars, last complete month orange, partial month
hatched steel, principal as a teal line) · **Loan Portfolio by Status** (status table with
an orange total row, ranked status bars) · **Peer Comparison** (pill layout plus an index
chart where the cohort is 100).

## Multi-product clients

A client with other RPE programs does NOT get a standalone deck — their CashPlease slides
go into the combined Executive Review:

```bash
python build/assemble_combined.py --ics <ics.pptx> --cashplease <cp.pptx> --out <out.pptx>
```

`--ars` is not required. The first program present of ARS → ICS → CP → MRPC supplies the
shared shell. The roster's `Ships as` column says which clients take which path.

## Rules that cost something to learn

**The roster is `clients.md`, never the workbook.** The workbook carries all 73 Velocity
CashPlease tabs across every CSM. A tab proves a client is LIVE on CashPlease and proves
nothing about whether a deck is wanted — an early run built 71 decks and 63 were other
CSMs' clients. A client absent from the table is not built even with 11,000 loans in their
tab. A `no` row is skipped WITH its reason, so a cancelled client cannot return just
because their tab keeps arriving (1658 Truliant, every week, 8,296 loans).

**Never claim a share of accounts.** The workbook's `Percentage of Active Accounts with
Loans` (L8) is never rendered. An account can take more than one CashPlease loan, so a
loan count over an account base is not the share of accounts that borrowed, and the
workbook does not state its denominator. `loans per 1,000 DDAs` replaces it — a volume
rate, labelled as one, over a trailing 12-month window so tenure does not decide the
comparison. L8 stays in the speaker notes with the reason it is unused.

**Missing data is stated, never zeroed.** A client with no DDA count gets no rate and says
why. A client live under a month has no completed-month row and gets a chart of just the
partial bar. An empty chart captioned "0 in the most recent complete month" shipped once
and must not again.

**Cohorts are not interchangeable.** The rollup cohort is every tab in the workbook; the
DDA rate's cohort is only the clients with a count AND a full 12 months. Any slide
carrying both names both.

**Name the client, never "this client".** The deck is read in a room with them in it.

**Excel caps the workbook's sheet names at 30 characters**, and B4 says "All Clients
Rollup" on every tab, so a client's name can only come from the sheet name. Length alone
cannot tell a cut name from a complete one — `Coosa Valley Credit Union` fits exactly — so
every 30-char name needs a `NAME_OVERRIDES` entry and the extractor flags any that lacks
one.

**Verbs are derived from the figures** (the ±2% band in `templates/STYLE.md`), and the
partial month follows the house treatment — hatched steel with its through-date, never
invented afresh.
