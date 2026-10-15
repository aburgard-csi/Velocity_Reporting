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
| 1100 | Rally CU | SM | yes | yes (no ICS data on file yet) | — | ARS-ICS |
| 1121 | Timberland Bank | SM | yes | — | — | ARS |
| 1126 | Legend Bank | SM | yes | yes (no ICS data on file yet) | yes | ARS-ICS-MRPC |
| 1147 | Sutton | SM | yes | — | — | ARS |
| 1156 | BancFirst | SM | yes | — | — | ARS |
| 1192 | Ascend FCU | MM | yes | — | — | ARS |
| 1200 | Guardians Credit Union | MM | yes | — | — | ARS |
| 1204 | First State Bank - Michigan | MM | yes | — | — | ARS |
| 1217 | Pioneer FCU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1226 | Ellafi FCU | MM | yes | — | — | ARS |
| 1403 | Adirondack Bank | SM | yes | yes (no ICS data on file yet) | yes | ARS-ICS-MRPC |
| 1437 | Canandaigua National Bank | MM | ended | — | ended | **none — no further reviews** |
| 1439 | Horizon Bank NA | — | — | referrals-only (no ICS data on file yet) | yes (no VIP MRPC sheet yet) | ICS-MRPC |
| 1441 | FNB Alaska | MM | yes | — | — | ARS |
| 1453 | Connex CU | MM | yes | — | yes | ARS-MRPC |
| 1487 | Orsa CU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1509 | Texas Bay Credit Union | MM | yes | yes | — | ARS-ICS |
| 1520 | Cashmere Valley Bank | MM | yes | — | yes | ARS-MRPC |
| 1526 | Create CU | MM | yes | — | — | ARS |
| 1529 | Vantage West CU | MM | yes | — | — | ARS |
| 1537 | Brooks Bank | MM | yes | yes | — | ARS-ICS |
| 1539 | Marine FCU | MM | yes | yes | yes | ARS-ICS-MRPC |
| 1542 | The Friendship SB | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | yes | ARS-ICS-MRPC |
| 1549 | Wellworth Bank | MM | yes | referrals-only | — | ARS-ICS |
| 1554 | Isabella Bank | MM | yes | — | — | ARS |
| 1615 | Cape & Coast Bank | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | yes | ARS-ICS-MRPC |
| 1637 | Ouachita Valley FCU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | yes | ARS-ICS-MRPC |
| 1652 | Security CU | SM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | yes | ARS-ICS-MRPC |
| 1657 | Marine Credit Union | SM | — | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ICS |
| 1673 | Neighborhood CU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | yes | ARS-ICS-MRPC |
| 1676 | True Sky CU | MM | yes | yes | — | ARS-ICS |
| 1680 | Great Lakes CU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1681 | First Financial CU | MM | yes | — | — | ARS |
| 1705 | CoastLife Credit Union | MM | yes | **cancelled** | — | ARS |
| 1745 | Leading Edge CU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | yes | ARS-ICS-MRPC |
| 1746 | PrimeTrust FCU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1748 | Clearview FCU | MM | yes | — | — | ARS |
| 1759 | First Central CU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1761 | Capital Educators FCU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1765 | Foothills CU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1766 | Fort Sill FCU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1776 | CoastHills CU | MM | yes | yes (local files, no VIP) | yes | ARS-ICS-MRPC |
| 1777 | West-Aircomm FCU | MM | yes | — | — | ARS |
| 1780 | USF CU | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | yes | ARS-ICS-MRPC |
| 1798 | FirstLight FCU | MM | yes | — | — | ARS |
| 1799 | Central Bank | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1800 | First American Bank | MM | yes | yes (direct mail list, 2026-10-15; no VIP sheet) | — | ARS-ICS |
| 1805 | Texar FCU | — | yes | — | — | ARS |
| 1807 | Patriot FCU | MM | yes | — | — | ARS |
| 1815 | FedChoice FCU | MM | yes | — | — | ARS |

**ARS added for every client with a 2026.09 ARS workbook (Aaron, 2026-09-15)** — 34 clients
across the other four CSMs' books. `Client` is the DCO's spelling (the house name; the workbook
often spells it out, e.g. "Guardians Credit Union" / "Leading Edge Credit Union") and `Path` was
detected from each workbook. **MRPC and CashPlease are recorded where their data exists (Aaron, 2026-09-15):** MRPC for
1453, 1520, 1542, 1615, 1637, 1652, 1673, 1745, 1776 and 1780, and CashPlease roster rows
for 1192, 1217, 1526, 1529, 1542, 1652, 1681, 1748, 1761 and 1776. None of the ten MRPC
clients has a VIP MRPC sheet yet, so their MRPC builds stop until one is pulled.

**1100 Rally CU (ARS, ICS) and 1126 Legend Bank (ARS, ICS, MRPC) added (Aaron, 2026-09-17)** —
both Daniel Wood's. Their 2026.09 ARS workbooks landed after the 2026-09-15 pass (Rally's on
2026-09-16), so they were missed. Both workbooks are Monthly Summary (SM: `Executive Financials MM`
carries the `Bank Name` placeholder). Neither has a VIP ICS sheet, an ICS workbook or a detailed
referral export yet, and Legend has no VIP MRPC sheet, so CSM Sheila offers ARS only until that
data lands.

**1147 Sutton (ARS; Gregg Miller) and 1403 Adirondack Bank (ARS, ICS, MRPC; Daniel Wood) added
(Aaron, 2026-09-17)** — their 2026.09 ARS workbooks landed 2026-09-16 evening and were copied by
the 2026-09-17 08:00 source check. Both workbooks are Monthly Summary (SM). Adirondack has no VIP
ICS or MRPC sheet, ICS workbook or referral export yet, so CSM Sheila offers ARS only until one lands.

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
| 1632 | WesBanco | 2026.07 | ICS launched **November 2025** (Aaron, 2026-10-08) — referral queries must start at 2025-11-01 |
| 1734 | Altamaha Bank and Trust Company | 2026.08 | |
| 1738 | Rosedale Bank | none on file | referrals-only unless a workbook lands |
| 1195 | KEMBA CU | 2026.10 | Jordan Berkowitz's. Added 2026-10-13 (Aaron: "1195 Kemba should be added for Jordan. They have ILS and ICS"; "Kemba is listed as KEMBA CU"). ILS has no monthly deck. No VIP ICS sheet and no referral detail file: the deck builds from the 2026.10 workbook alone — the **workbook-only** shape: the ordinary referral slides from the Monthly Detail row "Accounts Opened via Invitation Checking System", which counts referrals (Aaron, 2026-10-13), and the branch tab. Goals and branch names from `Inputs/ICS Charts/KEMBA Financial CU  Charts 2026.xlsx` (its tab is ` Goals`, column "Goal"); its 2023 Referral Trend / Branch Results tabs are stale and unused |
| 1002 | Republic | none on file | Jordan Berkowitz's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1514 | 1st Community FCU | none on file | Daniel Wood's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1555 | Garden Savings FCU | none on file | Jordan Berkowitz's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1710 | Guardian Credit Union | 2026.10 | Daniel Wood's; builds workbook-only. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1731 | Texoma CCU | none on file | James Gilmore's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1736 | The Peoples Bank Co | none on file | Jordan Berkowitz's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1743 | Mid American CU | none on file | Daniel Wood's (the Velocity export also lists ARS; not asked for). Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1764 | FBT Bank | none on file | Daniel Wood's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1774 | INB NA | none on file | Jordan Berkowitz's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1782 | Meridian Trust FCU | none on file | Daniel Wood's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1796 | ACCESSbank | none on file | Daniel Wood's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1806 | SOCU | none on file | Daniel Wood's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1808 | Summit Choice CU | 2026.10 | Jordan Berkowitz's; builds workbook-only. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1811 | Dutch Point Credit Union | none on file | Max Willett's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1816 | Beginnings CU | 2026.10 | Max Willett's; builds workbook-only. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1817 | The County FCU | none on file | Max Willett's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1826 | Air Academy FCU | 2026.10 | James Gilmore's; builds workbook-only. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |
| 1835 | Citizens Bank | none on file | Daniel Wood's. Added 2026-10-15 from the ICS Direct Mail list (Aaron: "List any client with a new direct mail list as having ICS"); no VIP sheet or referral export, so the deck builds only once a current workbook or referral source is on file |

**1439 Horizon Bank NA added to the active table as ICS + MRPC (Aaron, 2026-10-07: "horizon bank 1439
should be on my list. they have ILS and ICS"; then "add MRPC too")** — Gregg Miller's until the
2026-10-02 reassignment, Aaron's since. ILS has no monthly deck (the ILS review prep slides are
hand-run, see the `ils-prep-deck` skill). No ARS: the data team lands an ODD extract and a DCO for
1439 every month and the Velocity export lists ARS, but no ARS workbook has ever landed and Aaron
did not name it. Neither program has its data on file yet — no VIP ICS sheet, ICS workbook or
referral export (only `Inputs/ICS Charts/Horizon Bank ICS Charts 2026.xlsx`), and no VIP MRPC sheet
beside the monthly `1439-<period>-MRPC-Horizon Bank NA-MRPCPM_Analysis_v10.xlsx` — so no deck builds
until the VIP ICS and MRPC sheets are pulled; the combined deck is then ICS-MRPC.

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
*Widened 2026-09-15 (Aaron): the table also carries the other CSMs' ARS clients that run
CashPlease. A tab in the workbook still says nothing on its own.*

| Source | Where |
| --- | --- |
| Weekly workbook | Bradford Sanders, subject "CashPlease Summary" — `CashPleaseSummaryV1_<yymmdd>_<hhmmss>.xlsx` |
| DDA denominator | the weekly "ILS Management Server DDA Count" email body, saved as `ILS-DDA-Count-<YYYY-MM-DD>.txt` |
| Both land in | `Inputs/Weekly Summaries/` under `RPE_DATA_ROOT` — resolved through `rpe_env`, never hardcoded |
| Decks go to | `Outputs/`; packs and figures to `Build Artifacts/cashplease/` |
| Cadence | **Weekly** — the build always uses the most recent workbook, currently 2026-09-06 |

### CashPlease roster — BUILD ONLY THESE

Aaron's client book intersected with the 2026-09-06 workbook. Since 2026-09-15 it also
carries the other CSMs' ARS clients that run CashPlease, with loans from the 2026-09-13 weekly. `Build` is what
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
| 1192 | Ascend FCU | Jordan Berkowitz | yes | 6,325 | **ARS-CP** section | added 2026-09-15 with the ARS roster |
| 1217 | Pioneer FCU | James Gilmore | yes | 750 | **ARS-CP** section | added 2026-09-15 with the ARS roster; the workbook tab reads "Pioneer Federal Credit Union" |
| 1526 | Create CU | Max Willett | yes | 64 | **ARS-CP** section | added 2026-09-15 with the ARS roster; the workbook tab reads "Clark County Credit Union" |
| 1529 | Vantage West CU | Jordan Berkowitz | yes | 13,494 | **ARS-CP** section | added 2026-09-15 with the ARS roster |
| 1539 | Marine FCU | Aaron Burgard | yes | 6,745 | **ARS-ICS-MRPC-CP** section | the client book's product list omits CashPlease — see gap 3 |
| 1542 | The Friendship SB | Daniel Wood | yes | 401 | **ARS-MRPC-CP** section | added 2026-09-15 with the ARS roster; the workbook tab reads "Friendship State Bank" |
| 1564 | OneUnited Bank | Aaron Burgard | yes | 11,495 | standalone deck   | no other RPE program |
| 1632 | WesBanco Bank | Aaron Burgard | yes | 11,927 | **ICS-CP** section | |
| 1652 | Security CU | Max Willett | yes | 51 | **ARS-MRPC-CP** section | added 2026-09-15 with the ARS roster; the workbook tab reads "Security Rewards" |
| 1658 | Truliant FCU | Aaron Burgard | **no** | 8,296 | — | CashPlease cancelled 2026-09-01 |
| 1681 | First Financial CU | Jordan Berkowitz | yes | 24,715 | **ARS-CP** section | added 2026-09-15 with the ARS roster |
| 1734 | Altamaha Bank and Trust Company | Aaron Burgard | yes | 651 | **ICS-CP** section | |
| 1748 | Clearview FCU | Jordan Berkowitz | yes | 10,886 | **ARS-CP** section | added 2026-09-15 with the ARS roster; the workbook tab reads "Clearview Federal Credit Union" |
| 1750 | All In FCU | Aaron Burgard | yes | 5,701 | standalone deck   | no other RPE program |
| 1761 | Capital Educators FCU | James Gilmore | yes | 223 | **ARS-CP** section | added 2026-09-15 with the ARS roster; the workbook tab reads "CapEd CU" |
| 1770 | Central State Bank | Aaron Burgard | yes | 27 | standalone deck   | the client book's product list omits CashPlease — see gap 3 |
| 1771 | Copper State CU | Aaron Burgard | yes | 156 | standalone deck   | the client book's product list omits CashPlease — see gap 3 |
| 1776 | CoastHills CU | James Gilmore | yes | 1,246 | **ARS-MRPC-CP** section | added 2026-09-15 with the ARS roster |

**Thirteen combined decks and five standalone decks per run.** A client whose CashPlease
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

**1566 People's Bank NC is on this list's edge:** the client book says they are on CashPlease
but they have **no tab in the workbook**, so no deck can be built. They are left off
the table rather than added with `Build: yes`, which would fail every run. See gap 4.

**Truliant 1658 has cancelled CashPlease (Aaron, 2026-09-01).** Their tab still carries
8,296 loans and will keep arriving every week. It is not a signal to build — the same
rule that governs CoastLife's ICS folder and PointBank's ODD extract.

---

## Status changes

- **2026-10-15 — ICS added for every client with a new direct mail list** (Aaron: "List any client with a new direct mail list as having ICS"). The data team landed `Inputs/ICS Direct Mail/` with a 2026.10 list for 43 clients. 17 active-table rows gain ICS (1217, 1487, 1542, 1615, 1637, 1652, 1673, 1680, 1745, 1746, 1759, 1761, 1765, 1766, 1780, 1799, 1800) and their deck tag gains ICS; 1657 Marine Credit Union, ICS-only since 2026-09-15, now builds; 18 clients join the ICS-only table. None of them has a VIP sheet or a referral export: the five with a 2026.10 ICS workbook (1542, 1680, 1746, 1759, 1800 among the ARS clients; 1710, 1808, 1816, 1826 ICS-only) build the workbook-only shape with the Direct Mail slide, and the rest build no ICS section until a current workbook or a referral source lands — CSM Sheila says so per client rather than guessing.
- **2026-10-13 — 1195 KEMBA CU added as ICS only, Jordan Berkowitz's** (Aaron: "1195 Kemba should be
  added for Jordan. They have ILS and ICS"; the name is the DCO's and the CSM list's: "Kemba is listed as
  KEMBA CU"). ILS has no monthly deck (the ILS review prep slides are hand-run). No ARS: the data team
  lands an ODD extract and a DCO for 1195 every month, but the Velocity export lists ICS and ILS only and
  Aaron confirmed ICS only on 2026-09-15. On file: the 2026.10 ICS workbook (`v1.7.1-DM`, landed
  2026-10-09) and the Charts workbook. No VIP ICS sheet and no referral detail file. The same day
  Aaron asked for a **workbook-only ICS shape** ("Add a workbook-only ICS shape that draws the opening
  counts from Monthly Detail and the branch tab"), so the deck builds from the workbook alone. It was
  first worded "accounts opened, not referrals"; Aaron corrected that the same day ("The monthly
  detail tab in the workbook is counting referrals in the Accounts Opened via Invitation Checking
  System row" — it sums to the Value tab's 3,877), so the slides are the ordinary referral slides
  with the workbook named in the notes, and the Charts goals apply. The 1776 difference (workbook
  row 2,575 vs the referral detail export 2,280) is between two referral counts and is for the data
  team. Cindy's "doesn't match VIP" on the count slides is the same kind of question. A referral
  detail file or VIP sheet, when one lands, takes precedence automatically. The deck also carries
  the workbook's own ROI (7.17 to 1) and Present Value ($6,814,201 at 3%), not a recalculation
  (Aaron, 2026-10-13, "Carry the workbook's ROI figures").
- **2026-09-16 — 1776 CoastHills CU is on ICS** (Aaron: "Add ICS, but don't pull from VIP since I
  don't have access to their clients"). James Gilmore landed a 2026.09 ICS workbook, a detailed referral
  file and a direct-mail new-accounts list in Inputs. There is no VIP ICS sheet and none will be pulled:
  the ICS section is built from those local files (uild/ics_pipeline/ics_local_sheet.py), with any
  section they cannot supply left out. James's client, so the CSM chooses an ARS-only or a combined deck
  in CSM Sheila.
- **2026-09-16 — ARS added for three of Jordan Berkowitz's clients: 1121 Timberland Bank, 1554
  Isabella Bank and 1805 Texar FCU** (Aaron: "all 3 have ARS"). Path was read from each workbook's
  `Executive Financials MM` tab: 1121's carries the `Bank Name` placeholder (SM), and 1554's is
  filled in (MM, 101 months, 40 mailings). 1805 has a 2026.09 DCO but no ARS workbook yet, so its
  Path is open and its build stops at the missing workbook until one lands. Names follow the DCOs.
  Only ARS is recorded. The Velocity export also lists ICS and MRPC for 1121 and 1554 (and
  CashPlease for 1121), but those programs were not asked for.
- **2026-09-15 — 1657 Marine Credit Union is ICS only, not ARS** (Aaron). It was added to the
  active table as ARS earlier the same day because a 2026.09 ARS workbook for it is on the
  client-reports share (a workbook saved with no calculated figures). The Velocity client/product
  export lists ICS and ILS only, and Aaron confirmed ICS only. ARS is removed, so no ARS deck is
  built for it; ICS is not recorded here because no ICS build for the other CSMs' clients has been
  asked for.
- **2026-09-15 — MRPC and CashPlease recorded for the new ARS clients that run them** (Aaron
  chose this over leaving them ARS-only, where the performance page would have dropped the
  sections). MRPC = yes for 1453, 1520, 1542, 1615, 1637, 1652, 1673, 1745, 1776 and 1780
  (each has an MRPCPM analysis). CashPlease roster rows, Build: yes, for 1192, 1217, 1526,
  1529, 1542, 1652, 1681, 1748, 1761 and 1776 (each has a tab in the 2026-09-13 weekly). That
  puts them in the monthly MRPC and weekly CashPlease builds and widens the 2026-09-01 rule
  that only Aaron's clients get a CashPlease deck. **None of the ten MRPC clients has a VIP
  MRPC sheet**, so those builds stop on the missing sheet until one is pulled.
- **2026-09-15 — ARS roster extended to every client with a 2026.09 ARS workbook** (Aaron:
  "Add all clients with a september ARS workbook to clients.md"). 34 clients from the other
  four CSMs' books join the active table as ARS-only: 1156, 1192, 1200, 1217, 1226, 1441,
  1453, 1487, 1520, 1526, 1529, 1542, 1615, 1637, 1652, 1657, 1673, 1680, 1681, 1745, 1746,
  1748, 1759, 1761, 1765, 1766, 1776, 1777, 1780, 1798, 1799, 1800, 1807, 1815. Names are
  the DCO spelling; paths were detected from each workbook. **Not yet buildable as of this
  date:** 1226, 1615 (account status needs a mapping), 1637, 1748 (no product names on new
  accounts in the ODD) and 1657 (workbook never calculated); 1192 and 1673 were
  recalculated today and are being rebuilt. MRPC and CashPlease were then recorded where
  their data exists; see the entry above.
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
- **2026-09-01 — this file reconciled against Aaron's client book** (Claude, a one-time
  read of 61 client records; the reader that did it was removed on 2026-10-02 and nothing
  in deck production reads that book). **No ARS/ICS/MRPC membership was
  changed:** every program row here still reflects Aaron's confirmations, and the client
  book is contract/CRM notes, not a build roster. The check found **no client with an
  ARS/ICS/MRPC product there that is missing from this file** — the RPE roster is
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
   brand-kit file); 1799 Central Bank (several institutions share the
   name — which one?); 1403 Adirondack (→ Arrow Bank) and 1795 Premier Members
   (→ Meritrust) need a brand call after a merger. A client without a file still builds,
   just without a logo — see CLAUDE.md **File locations**. **1195 KEMBA CU resolved
   2026-10-13** (Aaron: "Looks like we need a KEMBA logo"): the CSM list puts the client in
   Gahanna, OH, and the Charts workbook says "KEMBA Financial CU", so it is KEMBA Financial
   Credit Union (kemba.org); the site's colour header logo (black wordmark, green swoosh,
   transparent) is `Inputs/Logos/1195.png`, rasterized from the SVG with resvg.

2. **The client book disagreed with this file on three clients' program membership**
   at that check. In every
   case this file is the one that shipped decks, so it is left as-is pending Aaron:
   - **1174 PointBank** — here: ICS cancelled, no programs (2026-08-28). There: still
     `products: [ILS, ICS]`. Is that record simply stale, or did ICS come back?
   - **1705 CoastLife CU** — here: ARS active. There: `products: []`, status "Pending
     contract review". CoastLife's 2026.08 ARS deck shipped, so this file looks right and
     that record looks unfilled — confirm.
   - **1738 Rosedale Bank** — here: ICS, referrals-only until a workbook lands. There:
     `products: []`, status "Pending contract review". Same question.

3. **The client book's product list does not carry CashPlease for three clients who have real
   CashPlease volume in the workbook**: 1539 Marine FCU (6,705 loans), 1771 Copper State
   CU (153) and 1770 Central State Bank (27). The modules are built regardless — the
   workbook is the CashPlease roster — but those records look out of date. Marine in
   particular is a 6,745-loan program recorded nowhere in its own client note.

4. **1566 People's Bank NC is the mirror image**: the client book lists `products: [ILS,
   CashPlease]` but the client has **no tab in the workbook** — still absent from the
   2026-09-06 one, so this is not a one-week gap. Either they are sold but not yet live,
   or their data is missing from the weekly pull; worth asking Bradford which.

5. **1537 is still "FNB&T Chickasha" in the client book.** This file renamed 1537 to
   **Brooks Bank** effective 2026-08-31 and decks deliver under that name. That record was
   not renamed. Match 1537 by ID, never by name.

6. **The client book tracks ILS on nearly every client; this file does not track ILS at all.**
   That was harmless while the three programs were the only deliverables. Now that
   CashPlease modules are inserted into ILS review decks, the ILS review schedule is a
   real dependency and it lives in William Ferra's weekly email, not here. Worth deciding
   whether this file should carry an ILS column.

7. **1549 Wellworth carries a fourth product in the client book — "Account Engagement"** — which
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
