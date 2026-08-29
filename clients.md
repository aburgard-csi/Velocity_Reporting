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
| 1537 | FNBT Chickasha | MM | yes | yes | — | ARS-ICS |
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

## Status changes

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

1. **1732 — no such client on this machine, and no longer explainable as a typo.** Named
   as ICS-only on 2026-08-28, but there is no 1732 anywhere: no ODD extract, no workbook,
   no ICS or MRPC data folder, no client folder in Drive. The obvious candidate for a
   transposition was 1658, but 1658 has since been confirmed off RPE entirely, so that
   reading is out. Either 1732 is a client whose data has never reached this machine, or
   the id is wrong. Nothing is built for it until confirmed.
2. **Client logos** exist for 1075, 1509, 1537, 1539, 1549, 1676 only. Every other client
   builds its Agenda slide without one — see CLAUDE.md **File locations**.

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
