# Client roster — who gets which programs

**Why this file exists.** Program membership used to be inferred from whether input
files happened to exist. That is how CoastLife 1705 kept producing an ICS section after
the program was cancelled: their ICS data was still on disk, so the build still made the
slides. A cancelled program leaves its files behind — only this file records intent.

**Rule: this file decides what gets built, not the presence of a data file.** If a client
here says ARS only, do not add an ICS section because `Inputs/VIP Data/ICS/<client>/`
exists. If a client should get a program whose inputs are missing, that is a
data-sourcing task — ask Aaron, do not silently drop the section.

Keep it current: update it when a program starts, stops, or changes cadence, and record
the date and who confirmed it.

---

## Active clients — 2026.08 cycle

**`Client` is the name that goes on the deck and in the filename** — the delivery name,
decided here (Aaron, 2026-08-29). It is not read from the workbook: 1204's workbook says
"First State Bank-MI" and its 2026.08 deck shipped as "FSB Michigan", neither of which is
what the client is called. Renaming a client is a delivery decision, so it is recorded in
this file and the builders follow it.

`Path` is the ARS financial extractor: **MM** = Lift Matrix (`extract_base_gen` +
`extract_lift`), **SM** = Monthly Summary (`base_tab_extract` + DCO). Detected from the
workbook's `Executive Financials MM` tab — a real client name means MM, the `Bank Name`
template placeholder means SM. Verified 2026-08-28.

| ID | Client | Path | ARS | ICS | MRPC | Deck |
| --- | --- | --- | --- | --- | --- | --- |
| 1038 | Sugar River Bank | SM | yes | — | — | ARS |
| 1075 | Austin Bank | SM | yes | yes | yes | ARS-ICS-MRPC |
| 1204 | First State Bank - Michigan | MM | yes | — | — | ARS |
| 1437 | Canandaigua National Bank | MM | ended | — | ended | **none — no further reviews** |
| 1509 | Texas Bay Credit Union | MM | yes | yes | — | ARS-ICS |
| 1537 | Brooks Bank | MM | yes | yes | — | ARS-ICS |
| 1539 | Marine FCU | MM | yes | yes | yes | ARS-ICS-MRPC |
| 1549 | Wellworth Bank | MM | yes | referrals-only | — | ARS-ICS |
| 1676 | True Sky CU | MM | yes | yes | — | ARS-ICS |
| 1705 | CoastLife Credit Union | MM | yes | **cancelled** | — | ARS |

**MRPC-only clients** — confirmed by Aaron 2026-08-28.

| ID | Client | Programs |
| --- | --- | --- |
| 1218 | Ideal Credit Union | MRPC only |
| 1477 | The Summit FCU | MRPC only |
| 1502 | Capital Bank | MRPC only |

**Cancelled / ending**

| ID | Client | What changed | Effective |
| --- | --- | --- | --- |
| 1174 | PointBank | ICS cancelled; **no ARS either — no programs** | 2026-08-28 |
| 1658 | Truliant FCU | **no RPE at all** — off the books | 2026-08-28 |
| 1705 | CoastLife Credit Union | ICS cancelled — ARS continues | 2026-08-28 |
| 1437 | Canandaigua National Bank | ARS + MRPC end; **no further reviews will be produced** | 2026-10-31 |

**ICS-only clients** — confirmed by Aaron 2026-08-28.

| ID | Client | ICS workbook | Note |
| --- | --- | --- | --- |
| 1632 | WesBanco | 2026.07 | |
| 1734 | Altamaha Bank and Trust Company | 2026.08 | |
| 1738 | Rosedale Bank | none on file | referrals-only unless a workbook lands |

---

## CashPlease — the fourth program

**CashPlease ships WITH ICS or another RPE product, and that deck is what goes to the
annual ILS review (Aaron, 2026-09-02).** CashPlease slides are never inserted into the
data team's ILS Analysis Review deck — they ride in the client's own RPE deck, and that
deck is included in the ILS review alongside it. For a client with no other RPE program
the standalone single-product CashPlease deck plays that role.

This **changes the earlier decision** (2026-09-01) that CashPlease slides would be added
into the ILS review deck itself. The ILS deck is built by the data team and ships as a
28 MB macro-enabled `.pptm`; editing it means a second pipeline writing into someone
else's deliverable. Delivering a deck beside it does not.

The slides are the same five either way — divider · Program Overview · Loan Volume by
Month · Loan Portfolio by Status · Peer Comparison — built once, plus a Program Settings
slide after the Overview for a client with a settings record in `Inputs/Product Settings/`. The combined deck is a
second consumer of that output, the way it already consumes the ICS and MRPC decks.

**The pipeline lives in this repo as of 2026-09-10**: `build/cashplease_pipeline/` and
`scripts/build_cashplease.py`, dispatched by the `cashplease-deck` subagent, using the
same `brand` / `shapes` / `periods` / `fit_layout` layer as every other program and
validated by `validation/validate_deck.py` like every other deck. It ran out of
`C:\Projects\CashPlease` until then; that tree is retired and builds nothing.

**This file is the roster, like every other program here (Aaron, 2026-09-01).** An
earlier pass built a deck for all 71 client tabs in the workbook. It no longer does:
**only Aaron's clients get a CashPlease deck.** The workbook carries every Velocity
CashPlease client across all CSMs, so a tab in it says a client is live on the program —
never that a deck is wanted. `scripts/build_cashplease.py` reads the table below, via
`build_month.read_cashplease_roster`, and builds nothing that is not in it.

| Source | Where |
| --- | --- |
| Weekly workbook | Bradford Sanders, subject "CashPlease Summary" — `CashPleaseSummaryV1_<yymmdd>_<hhmmss>.xlsx` |
| DDA denominator | the weekly "ILS Management Server DDA Count" email body, saved as `ILS-DDA-Count-<YYYY-MM-DD>.txt` |
| Both land in | `Inputs/Weekly Summaries/` under `RPE_DATA_ROOT` — resolved through `rpe_env`, never hardcoded |
| Decks go to | `Outputs/`; packs and figures to `Build Artifacts/cashplease/` |
| Cadence | **Weekly** — the build always uses the most recent workbook, currently 2026-09-06 |

### CashPlease roster — BUILD ONLY THESE

Aaron's client book (Obsidian) intersected with the 2026-09-06 workbook. `Build` is what
the builder reads; a row marked `no` is parsed and deliberately skipped, so a
cancelled client cannot come back just because their tab keeps arriving.

`CSM` is the client's CSM on the RPE Client Performance page (Aaron, 2026-09-14). The page
takes each client's CSM from the account-manager folder its reports land in on
`Velocity_clientreports`, and the CashPlease-only clients never land there, so this column
is the only place their CSM is recorded. Where the share names a CSM it wins, and the
refresh logs a disagreement with this column. Columns are read by header name, so the
column's position is free.

| ID | Client | CSM | Build | Loans | Ships as | Note |
| --- | --- | --- | --- | --- | --- | --- |
| 1131 | People's Bank AL | Aaron Burgard | yes | 10,540 | standalone deck   | no other RPE program |
| 1539 | Marine FCU | Aaron Burgard | yes | 6,745 | **ARS-ICS-MRPC-CP** section | Obsidian `products` omits CashPlease — see gap 3 |
| 1564 | OneUnited Bank | Aaron Burgard | yes | 11,495 | standalone deck   | no other RPE program |
| 1632 | WesBanco Bank | Aaron Burgard | yes | 11,927 | **ICS-CP** section | |
| 1658 | Truliant FCU | Aaron Burgard | **no** | 8,296 | — | CashPlease cancelled 2026-09-01 |
| 1734 | Altamaha Bank and Trust Company | Aaron Burgard | yes | 651 | **ICS-CP** section | |
| 1750 | All In FCU | Aaron Burgard | yes | 5,701 | standalone deck   | no other RPE program |
| 1770 | Central State Bank | Aaron Burgard | yes | 27 | standalone deck   | Obsidian `products` omits CashPlease — see gap 3 |
| 1771 | Copper State CU | Aaron Burgard | yes | 156 | standalone deck   | Obsidian `products` omits CashPlease — see gap 3 |

**Three combined decks and five standalone decks per run.** A client whose CashPlease
slides ship inside a combined deck does NOT also get a standalone deck (Aaron,
2026-09-01) — the Executive Review and the ILS review would otherwise carry the same five
slides. Loan counts are program-to-date **as of the 2026-09-06 workbook** and are a
convenience, not an input; the builder reads them from the workbook every run.

**Two counts did not move over the week to 2026-09-06**, and both are worth knowing
rather than smoothing over. **1658 Truliant is frozen at 8,296** — no new loans since the
program was cancelled, which is what a closed book should look like and is independent
corroboration of the `Build: no` row. **1770 Central State Bank is flat at 27**, and it is
NOT cancelled: 27 loans program-to-date with none in a week is either a program that never
took hold or one that has stopped. Worth asking before their next review, because the deck
reports it either way.

**1566 People's Bank NC is on this list's edge:** Obsidian says they are on CashPlease
but they have **no tab in the workbook**, so no deck can be built. They are left off
the table rather than added with `Build: yes`, which would fail every run. See gap 4.

**Truliant 1658 has cancelled CashPlease (Aaron, 2026-09-01).** Their tab still carries
8,296 loans and will keep arriving every week. It is not a signal to build — the same
rule that governs CoastLife's ICS folder and PointBank's ODD extract.

---

## Status changes

- **2026-09-14 — the CashPlease roster carries a `CSM` column** (Aaron). The RPE Client
  Performance page filters by CSM and reads each client's CSM from its account-manager
  folder on `Velocity_clientreports`. The five CashPlease-only clients (1131, 1564, 1750,
  1770, 1771) never land there, so they showed as Unassigned. Every row is Aaron Burgard,
  which is what this table already was: Aaron's client book intersected with the workbook.
  A new row needs its CSM filled in; `tests/test_cashplease.py` fails on a CashPlease-only
  client without one.
- **2026-09-01 — CashPlease added as a fourth program** (Aaron). First recorded as an
  ILS-review-only module; **superseded the same day** by the combined-deck decision
  below. See the **CashPlease** section above.
- **2026-09-10 — the CashPlease pipeline moved into this repo.** It ran out of
  `C:\Projects\CashPlease` against this repo's shared style layer; it is now
  `build/cashplease_pipeline/` + `scripts/build_cashplease.py`, dispatched by the
  `cashplease-deck` subagent. Paths resolve through `rpe_env` and **`CP_DATA_ROOT` no
  longer exists** — inputs come from `Inputs/Weekly Summaries/`, decks go to `Outputs/`.
  The standalone tree is retired and builds nothing; two working copies reading different
  data roots is the two-stores problem this file's opening paragraph is about. The
  2026-09-01 entry below describing `CP_DATA_ROOT` is superseded and kept as history.
- **2026-09-02 — CashPlease is delivered WITH ICS, not inserted into the ILS deck**
  (Aaron). "Ship CP with ICS or other RPE products, but I also want it included in our
  annual ILS reviews... rather than insert the cashplease slides into the ILS deck, just
  include them with ICS — this changes my past decision." So the CashPlease slides ride
  in the client's own RPE deck and that deck accompanies the ILS review; nothing is
  written into `ILS Program Analysis - <Client>.pptm`. Built 2026-09-02:
  `1734-2026.08-ICS-CP-Altamaha Bank and Trust Company Results.pptx` (33 slides) and
  `1632-2026.08-ICS-CP-WesBanco Results.pptx` (19 slides), both 0 FAIL.
  **1539 Marine is not yet buildable as ARS-ICS-MRPC-CP**: only the already-combined
  2026.08 deck is in `Outputs/` and a combined deck is never a build input, so the three
  program decks have to be rebuilt from their own sources first.
- **2026-09-01 — CashPlease is a section of the combined deck** (Aaron). It joins ARS,
  ICS and MRPC in the combined Executive Review. Two consequences decided with it:
  `assemble_combined.py`'s **`--ars` requirement is relaxed** so an ICS-CP deck can be
  assembled for 1632 and 1734, and **a client whose CashPlease slides ship inside a
  combined deck does not also get a standalone module**. The module remains for the five
  CashPlease clients with no other RPE program, which is the ILS-review case the work
  started from. Relaxing `--ars` does not move the shared shell out of the ARS deck —
  every program deck already builds its own Title/Summit/Agenda/Q&A/Contact, so it is a
  precedence rule (ARS → ICS → MRPC → CP) for which deck supplies them. The ARS Appendix
  stays ARS-only.
- **2026-09-01 — CashPlease builds only Aaron's clients** (Aaron). The first pass built
  all 71 client tabs in the workbook, on the reading that the modules would be handed to
  whichever CSM owned each ILS review. That is not wanted: **only Aaron's clients get a
  module**, and the roster table above is what the builder reads. The other 63 decks
  from that run were removed from `Outputs/`. This puts CashPlease back under the same
  rule as every other program on this page — a data file is never the roster.
- **2026-09-01 — CashPlease outputs live under `CP_DATA_ROOT`** (Aaron). `<CP_DATA_ROOT>\CashPlease
  Pipeline\` holds `Inputs/`, `Outputs/` and `Build Artifacts/`, mirroring the RPE
  pipeline folder. Resolved through `CP_DATA_ROOT` in the CashPlease project's `.env`;
  the path is not written into any code. Create and delete both confirmed working on the
  mount 2026-09-01.
- **2026-09-01 — Truliant FCU 1658 cancelled CashPlease** (Aaron). They already had no
  ARS, ICS or MRPC (2026-08-28), so 1658 now has no RPE program and no CashPlease
  module. Their workbook tab and ICS data folder both stay on disk as the record of
  what shipped.
- **2026-09-01 — this file reconciled against the Obsidian client book** (Claude, from
  `C:\Obsidian\My Vault\Work\Clients` — 61 client folders, read via
  `C:\Projects\CashPlease\build\obsidian_roster.py`). **No ARS/ICS/MRPC membership was
  changed:** every program row here still reflects Aaron's confirmations, and the vault
  is contract/CRM notes, not a build roster. The check found **no client with an
  ARS/ICS/MRPC product in Obsidian that is missing from this file** — the RPE roster is
  complete. Four disagreements were found and are recorded as gaps below rather than
  applied, because a note is evidence a program *was* running, never proof it still is
  — the same rule that made this file exist.

- **2026-08-31 — FNBT Chickasha 1537 rebranded to Brooks Bank** (Aaron). The rebrand
  took effect 2026-08-31, and the data team's 2026.09 DCO already lands as
  `1537-2026.09-Brooks Bank-DCO v2_2.xlsx`. 2026.09 forward delivers as **Brooks Bank**;
  decks already shipped as FNBT Chickasha are not reissued. Files for 2026.08
  and earlier keep the old name — match 1537 by ID, never by client name.
- **2026-08-29 — VIP sheets live only in `Inputs/VIP Data/`** (Aaron). The repo copies
  under `build/{ics,mrpc}_pipeline/data/` are deleted; `resolve_client_json` reads the
  VIP store and nothing else. Where a status note below points at a repo data folder as
  "the record of what shipped", that record is now the store's per-client folder.
- **2026-08-28 — CoastLife 1705 cancelled ICS** (Aaron). They get an ARS-only deck from
  2026.08 forward. Their ICS data under `Inputs/VIP Data/ICS/1705-CoastLife Credit Union/`
  is left in place as the record of what shipped through 2026.07; it must not be used to
  build a new ICS section.
- **2026-08-28 — Truliant FCU 1658 no longer has RPE** (Aaron). No ARS, ICS or MRPC.
  Their ICS data folder stays in `Inputs/VIP Data/ICS/1658-Truliant FCU/` as the
  record of what shipped; it is not a signal to build.
- **2026-08-28 — PointBank 1174 is off the books** (Aaron). ICS cancelled and they do
  not have ARS. Their ODD extract stays in `Inputs/ODDD/` — it is not a signal to build.
- **2026-08-28 — Canandaigua 1437: no further reviews** (Aaron). The program terminates
  2026-10-31 and they will not receive another Executive Review before it does. Do not
  build 2026.08 or any later cycle. Their inputs (ODD, 2026.08 workbook, 2026.08 MRPCPM)
  are still on disk and must not be taken as a signal to build.
- **2026-08-30 — 1732 is not an RPE client** (Aaron). It was named as ICS-only on
  2026-08-28 and no data for it ever existed on this machine — no ODD extract, no
  workbook, no VIP sheet, no input folder. Confirmed as not on the RPE list at all, so the
  gap is closed rather than left open: nothing is built for it and nothing is missing.
- **2026-08-29 — 1204 is "First State Bank - Michigan"** (Aaron). Was delivered as
  "FSB Michigan" for 2026.08 while its workbook said "First State Bank-MI". The roster
  name is now the delivery name and the builders follow it; 2026.08 was rebuilt and
  reissued under the correct name.
- **2026-08-28 — FSB Michigan 1204 confirmed ARS** (Aaron). Was missed in the 2026.08
  run; built after confirmation.
- **2026-08-28 — Wellworth 1549 is ICS referrals-only.** Live on ICS and generating
  referrals before their first ICS workbook has landed. Built with
  `build_ics_gen.py --referrals-only` (see CLAUDE.md **Cadence**).

---

## Gaps needing Aaron's confirmation

These are stated as open questions, not assumptions.

1. **Client logos** (updated 2026-09-14). `Inputs/Logos/` (and the copy on
   `\\PADMIS105\Velocity_company\CSM_Reporting\Inputs\Logos\`) covers 74 of the 81 current
   clients across all CSMs — current clients only, per Aaron. **Deferred for now (Aaron,
   2026-09-14):** 1038 Sugar River, 1192 Ascend and 1487 orsa (white-only — need the
   brand-kit file); 1195 KEMBA CU and 1799 Central Bank (several institutions share the
   name — which one?); 1403 Adirondack (→ Arrow Bank) and 1795 Premier Members
   (→ Meritrust) need a brand call after a merger. A client without a file still builds,
   just without a logo — see CLAUDE.md **File locations**.

2. **Obsidian disagrees with this file on three clients' program membership.** In every
   case this file is the one that shipped decks, so it is left as-is pending Aaron:
   - **1174 PointBank** — here: ICS cancelled, no programs (2026-08-28). Obsidian: still
     `products: [ILS, ICS]`. Is the vault simply stale, or did ICS come back?
   - **1705 CoastLife CU** — here: ARS active. Obsidian: `products: []`, status "Pending
     contract review". CoastLife's 2026.08 ARS deck shipped, so this file looks right and
     the vault looks unfilled — confirm.
   - **1738 Rosedale Bank** — here: ICS, referrals-only until a workbook lands. Obsidian:
     `products: []`, status "Pending contract review". Same question.

3. **Obsidian's `products` does not list CashPlease for three clients who have real
   CashPlease volume in the workbook**: 1539 Marine FCU (6,705 loans), 1771 Copper State
   CU (153) and 1770 Central State Bank (27). The modules are built regardless — the
   workbook is the CashPlease roster — but the vault entries look out of date. Marine in
   particular is a 6,745-loan program recorded nowhere in its own client note.

4. **1566 People's Bank NC is the mirror image**: Obsidian lists `products: [ILS,
   CashPlease]` but the client has **no tab in the workbook** — still absent from the
   2026-09-06 one, so this is not a one-week gap. Either they are sold but not yet live,
   or their data is missing from the weekly pull; worth asking Bradford which.

5. **1537 is still "FNB&T Chickasha" in Obsidian.** This file renamed 1537 to **Brooks
   Bank** effective 2026-08-31 and decks deliver under that name. The vault folder and
   note were not renamed. Match 1537 by ID, never by name.

6. **Obsidian tracks ILS on nearly every client; this file does not track ILS at all.**
   That was harmless while the three programs were the only deliverables. Now that
   CashPlease modules are inserted into ILS review decks, the ILS review schedule is a
   real dependency and it lives in William Ferra's weekly email, not here. Worth deciding
   whether this file should carry an ILS column.

7. **1549 Wellworth carries a fourth product in Obsidian — "Account Engagement"** — which
   this file does not track and no pipeline builds. Is it a deliverable?

## What is NOT a signal to build

- **A 2026.08 DCO file.** 1218, 1477, 1502, 1632, 1734 and 1738 all carry one and none of
  them are ARS clients. A DCO accompanies an ARS build but does not imply one.
- **Leftover program data.** CoastLife's ICS folder, PointBank's ODD extract and
  Canandaigua's 2026.08 workbook and MRPCPM all still exist for programs that have
  stopped.

## What the evidence was

Compiled 2026-08-28 from: `Inputs/ODDD/`, `Inputs/ARS & MRPC Reports/` (ARS workbooks,
DCO files, MRPCPM analyses, Invitation Checking workbooks), `Inputs/Logos/`, the ICS and
MRPC per-client data folders in this repo, and the MM/SM probe described above. Presence
of a file is evidence a program *was* running, never proof it still is — which is the
whole reason for this file.
