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

**CashPlease is a section of the combined Executive Review deck (Aaron, 2026-09-01)** —
and, for clients who have no other RPE program, a standalone module for their ILS
Analysis Review. Both, because neither path covers the roster on its own: five of the
eight CashPlease clients have no other RPE program and so have no combined deck to join.

The slides are the same five either way — divider · Program Overview · Loan Volume by
Month · Loan Portfolio by Status · Peer Comparison — built once by the module builder.
The combined deck is a second consumer of that output, the way it already consumes the
ICS and MRPC decks. The pipeline lives in `C:\Projects\CashPlease\build\` and imports
this repo's shared style layer (`brand`, `shapes`, `periods`, `fit_layout`) so a
CashPlease slide matches the ARS/ICS/MRPC slides beside it; it is staged to move into
this repo (`C:\Projects\CashPlease\MIGRATION.md`). Everything is validated with
`validation/validate_deck.py` like every other deck.

**This file is the roster, like every other program here (Aaron, 2026-09-01).** An
earlier pass built a module for all 71 client tabs in the workbook. It no longer does:
**only Aaron's clients get a CashPlease module.** The workbook carries every Velocity
CashPlease client across all CSMs, so a tab in it says a client is live on the program —
never that a deck is wanted. `build_all_cp.py` reads the table below and builds nothing
that is not in it.

| Source | Where |
| --- | --- |
| Weekly workbook | Bradford Sanders, subject "CashPlease Summary" — `CashPleaseSummaryV1_<yymmdd>_<hhmmss>.xlsx` |
| DDA denominator | the weekly "ILS Management Server DDA Count" email body, saved as `ILS-DDA-Count-<YYYY-MM-DD>.txt` |
| Both land in | `<Drive>/Work/CashPlease Pipeline/Inputs/` — resolved from `CP_DATA_ROOT`, never hardcoded |
| Decks go to | `<Drive>/Work/CashPlease Pipeline/Outputs/` |
| Cadence | Weekly (the 2026-08-30 workbook is the current one) |

### CashPlease roster — BUILD ONLY THESE

Aaron's client book (Obsidian) intersected with the 2026-08-30 workbook. `Build` is what
`build_all_cp.py` reads; a row marked `no` is parsed and deliberately skipped, so a
cancelled client cannot come back just because their tab keeps arriving.

| ID | Client | Build | Loans | Ships as | Note |
| --- | --- | --- | --- | --- | --- |
| 1131 | People's Bank AL | yes | 10,507 | standalone module | no other RPE program |
| 1539 | Marine FCU | yes | 6,705 | **ARS-ICS-MRPC-CP** section | Obsidian `products` omits CashPlease — see gap 3 |
| 1564 | OneUnited Bank | yes | 11,444 | standalone module | no other RPE program |
| 1632 | WesBanco Bank | yes | 11,869 | **ICS-CP** section | |
| 1658 | Truliant FCU | **no** | 8,296 | — | CashPlease cancelled 2026-09-01 |
| 1734 | Altamaha Bank and Trust Company | yes | 646 | **ICS-CP** section | |
| 1750 | All In FCU | yes | 5,657 | standalone module | no other RPE program |
| 1770 | Central State Bank | yes | 27 | standalone module | Obsidian `products` omits CashPlease — see gap 3 |
| 1771 | Copper State CU | yes | 153 | standalone module | Obsidian `products` omits CashPlease — see gap 3 |

**Three combined decks and five standalone modules per run.** A client whose CashPlease
slides ship inside a combined deck does NOT also get a standalone module (Aaron,
2026-09-01) — the Executive Review and the ILS review would otherwise carry the same five
slides. Loan counts are program-to-date as of the 2026-08-30 workbook and are a
convenience, not an input; the builder reads them from the workbook.

**1566 People's Bank NC is on this list's edge:** Obsidian says they are on CashPlease
but they have **no tab in the workbook**, so no module can be built. They are left off
the table rather than added with `Build: yes`, which would fail every run. See gap 4.

**Truliant 1658 has cancelled CashPlease (Aaron, 2026-09-01).** Their tab still carries
8,296 loans and will keep arriving every week. It is not a signal to build — the same
rule that governs CoastLife's ICS folder and PointBank's ODD extract.

---

## Status changes

- **2026-09-01 — CashPlease added as a fourth program** (Aaron). First recorded as an
  ILS-review-only module; **superseded the same day** by the combined-deck decision
  below. See the **CashPlease** section above.
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
- **2026-09-01 — CashPlease outputs live on Drive** (Aaron). `G:\My Drive\Work\CashPlease
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
  decks already shipped as FNBT Chickasha are not reissued. Files on Drive for 2026.08
  and earlier keep the old name — match 1537 by ID, never by client name.
- **2026-08-29 — VIP sheets live only in `Inputs/VIP Data/`** (Aaron). The repo copies
  under `build/{ics,mrpc}_pipeline/data/` are deleted; `resolve_client_json` reads the
  Drive store and nothing else. Where a status note below points at a repo data folder as
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
  workbook, no VIP sheet, no Drive folder. Confirmed as not on the RPE list at all, so the
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

1. **Client logos** exist for 1075, 1509, 1537, 1539, 1549, 1676 only. Every other client
   builds its Agenda slide without one — see CLAUDE.md **File locations**.

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
   particular is a 6,705-loan program recorded nowhere in its own client note.

4. **1566 People's Bank NC is the mirror image**: Obsidian lists `products: [ILS,
   CashPlease]` but the client has **no tab in the 2026-08-30 workbook**, so no module
   could be built. Either they are sold but not yet live, or their data is missing from
   the weekly pull — worth asking Bradford which.

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
