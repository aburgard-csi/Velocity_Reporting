---
name: summit-one-pager
description: Build an Executive Summit one-pager (8.5x11 print handout) for a client who is ATTENDING a Summit - the multi-program Key Performance Metrics page used for Fort Lauderdale 2026, or the older ARS-only page. Use only when Aaron asks for a Summit one-pager for named attendees. Never run on a schedule, never for the whole roster, and never choose the metrics yourself - Aaron decides which story each attendee sees. Gathers and verifies the figures, shows them neutrally, builds, renders, checks and hands over the file. Update this skill whenever Aaron corrects how these pages are built.
---

# Executive Summit one-pager

CLAUDE.md, "Executive Summit one-pagers - NOT a canned deliverable": the one-pager is hand-built, per attendee, and
the point is to show THAT attendee their strongest metrics at THAT Summit. Which metrics is Aaron's judgement; there is no
correct set to automate toward. This skill is the checklist around that judgement, not a way around it.

**Build every Summit page through this skill and write down what you learn in it** (Aaron, 2026-10-30: "If you aren't using and
updating a skill to build these, you should do that"). A correction from Aaron that changes how a page is built belongs in
"Standards", with the date, before you hand the next page over.

## Do not

- Build one for a client who is not ATTENDING (Aaron, 2026-10-30: "Only clients attending the Summit"). A CSM's name or "their RPE-only
  clients" is not an attendee list: ask for the attendee names, then map company to client id through `Client CSM List.csv`.
- Add it to `scripts/build_month.py` or any schedule. The monthly reviews are every client, every month, no curation.
- Rank, highlight or drop figures because they "look best". Aaron's brief for the Summit sets the story (for Fort Lauderdale 2026:
  ROI and year-over-year improvement, positive results only, complete months only); inside that brief, state what you left out.
- Put the file in `Outputs/` (finished decks only) or send it to anyone. Where each page type is saved is below.
- Name another CSM on a page. The contact line is the client's own CSM (`rpe_env.csm_contact`), never a hardcoded card.

## Which page

| | Key Performance Metrics page (use this) | ARS one-pager (older) |
| --- | --- | --- |
| Used for | Fort Lauderdale 2026 onward; any mix of ILS, ARS, ICS, MRPC, CashPlease, Account Engagement | Boston-era ARS-only handout |
| Builder | `.claude/skills/summit-one-pager/kpm_page.py` (+ `kpm_charts.py`, `assets/brand.pptx`) | `build/ars_pipeline/build_ars_onepager.py` |
| Inputs | a JSON spec you write, figures verified against the newest reports | the ARS launcher's data pack |

Ask which one if it is not clear. Aaron's Fort Lauderdale pages are the Key Performance Metrics page.

---

# Key Performance Metrics page

## 1. Confirm what is being built

In one message, for anything not already said: **the attendee list** (the pasted name / company / title list), **which Summit** (city and
month; the header says "<City> Executive Summit"), **the brief** (what story: ROI, growth, early results), and **the data period** (the last
COMPLETE month). Map each company to a client id and its CSM. For a client with no CSM or no `CSM Contacts.csv` row, stop and say so.

## 2. Verify every figure against the newest reports (one read-only pass per client)

Do not reuse figures from an earlier page or from memory. For each client, check every number against the NEWEST source on disk
and say what is newer than what the page cited. Run it as one read-only agent per client, in parallel, told to write nothing in the repo,
the share or OneDrive. Where things are (resolve paths through `rpe_env`, data root `\\PADMIS105\Velocity_company\CSM_Reporting`):

| Figure | Newest source |
| --- | --- |
| ARS return, profit, mailings | `Build Artifacts\launcher\<yyyy.mm>\<id>\base.json`; ARS workbook (Actuals MM, Key Trends MM) |
| Responder before/after, take rate, Reg E | `...\<id>\metrics.json`; the ODD in `Inputs\ODDD` |
| ICS referrals, branches | `Inputs\VIP Data\ICS` (`rpe_env.resolve_client_json(id, "ics")`; the VIP pull restates months, so use the newest and say the date); 2025 months from `Inputs\ICS Referrals\ics_referrals.csv` |
| ICS ROI, present value, lifetime value | newest `Inputs\ICS Workbooks` file (note the data month it carries) |
| MRPC enrollments | the newest MRPCEnrollmentSummary weekly in `Inputs\MRPC Analyses` (cards, primary plus joint; a different basis from VIP's account counts, say which) |
| MRPC revenue | VIP; stale for every client (Aaron is fixing it with Accounting), so do not flag per client |
| CashPlease | the newest CashPleaseSummary weekly in `Inputs\CashPlease`; peer figures from the CP module in Outputs |
| ILS | the newest ILS review in `OneDrive\Clients\<Client> <id>\ILS Delivery\` (PDF or .pptx/.pptm; render slides with PowerPoint COM, `AutomationSecurity = 3`, when the figures are in chart images) |
| Account Engagement | the Digital Onboarding Insights capture in the client's OneDrive `Account Engagement` folder |

Report each claim as: page text, source file and period, the value read, PASS / FAIL / UNVERIFIABLE, corrected wording.

## Standards (Aaron's corrections, newest first)

- **Year over year, never month over month** (2026-10-30). ICS and MRPC: the same months this year against last year, state both windows
  (Jan-Sep 2026 against Jan-Sep 2025), also last 12 months against the prior 12 when the series allows. A new client has no prior year: say
  totals since launch, never "grew from X in May to Y in September".
- **A short window can be a base effect.** Marine's "+38% referrals Aug-Sep" was a weak Aug-Sep 2025; year to date it was +6.3% and the last
  12 months were -2.5%. Check the longer window before quoting a short one, and tell Aaron when the longer window is negative.
- **Complete months only.** The last complete month is the month before the pull; a pull that includes the current month to date
  (VIP, the CashPlease weekly) is not a complete-month figure. A restated month wins (Wellworth/WesBanco September 357 became 356).
- **Border around the client logo** (2026-10-30): the white badge carries a 1.25 pt navy line so it does not vanish on the white page.
  `kpm_page.py` draws it; do not turn it off.
- **Do not claim what a list cannot show.** "All 15 branches referring" was the top 15 of about 220 on the VIP sheet; "all 39 branches" was 38
  plus Online Account Opening. Count from the member-level referral file, or do not state a count.
- **Name the basis.** Cards enrolled, not cardholders; personal accounts, not all accounts; "since March", not "new". If two figures use
  different bases (Austin's 35,526 enrolled), print the one you can name.
- **A figure with no data behind it is left off**, not zeroed: Wellworth sends no charge-off data, so no loss rate.
- **Put the vintage on an old figure.** If the newest ILS review is a year old, the bullet says "(November 2025 review)" and the window.
- **Remove a number when Aaron says to** (2026-10-30: the survey respondent count on WesBanco). Do not put it back in the next page.
- **A return ratio he dislikes is replaced, not argued** (2026-10-30: WesBanco's 7.17 : 1). Offer candidates from verified data, pick one,
  and list the others.
- **Equal gaps between sections** (2026-10-30). Use `"measure": true` and `"accurate": true` in the spec; the builder then counts wrapped lines with the
  bundled Montserrat and uses the rendered line pitch, so a section with more bullets does not get a bigger gap. `"bottom"` (inches)
  sets where content must end; Marine, with five sections, uses 9.5 so the last line clears the contact line.
- **The velocity average $1,828** (ICS lifetime value) is a constant in `ics_workbook_extract.py`, not computed. It is on the page as the
  house benchmark; say so in the notes.
- **Positive results only** is Aaron's brief for Fort Lauderdale; the negatives you found go in your hand-over message, not the page.
- **White space on a short page** (2026-10-30, WesBanco): fill it with verified material from the client's other products, such as a conversion chart
  beside the Account Engagement bullets and one ICS profit line, never with padding. Offer a short list of options first and build the ones Aaron agrees to.
- **A thin client is built thin** (2026-10-30, Dutch Point: ICS only, no workbook, no VIP sheet). Lead with the window that two sources agree on
  (May-August), leave out a month that has one source or unmatched records, and say in the hand-over what the longer window would show.
- **Only attending clients, mapped from the attendee list** (2026-10-30). The Cvent attendee list lives on the event's registration page; map each company to the
  Client CSM List by name, check its products, and tell Aaron which attendees are not RPE-only or not clients of the CSM he named.

## 3. Build

Work in the session scratchpad, never in the repo or OneDrive. Resolve the logo and contact through `RPE_DATA_ROOT` (set it to the share).

```
# 1. charts (a JSON list; see kpm_charts.py)
.venv/Scripts/python .claude/skills/summit-one-pager/kpm_charts.py <scratch>/charts.json <scratch>/out
# 2. one page per spec (see "Spec")
.venv/Scripts/python .claude/skills/summit-one-pager/kpm_page.py <scratch>/spec_<id>.json <scratch>/out/<id>.pptx
```

Run them from a script file (never a heredoc into `python -`: it hangs), without `-I` when a script imports a neighbor.

### Spec

```
{"id": "1075", "name": "Austin Bank", "measure": true, "accurate": true, "bottom": 9.62, "min_gap": 0.0,
 "band": {"title": "ROI & Year-over-Year Growth", "chip": "Jan-Sep 2026 vs Jan-Sep 2025", "chart": "<scratch>/out/m1075.png",
          "tiles": [["3.9 : 1", "ARS return, program to date"], ... four tiles, the first is orange]},
 "sections": [{"title": "Account Revenue Solution|®| (ARS)", "chip": "ARS since February 2009", "bullets": ["...", "..."]}],
 "notes": "Client 1075 Austin Bank. Verified <date>. ARS: <file, tab, period> ...  Positive results only."}
```

- `notes` is required and must name the file, tab or page and period behind every figure (the builder refuses fewer than 150 characters).
- `contact` overrides the contact line; leave it out and the client's CSM is read from `CSM Contacts.csv`.
- `logo` overrides `Inputs\Logos\<id>.png`; a missing logo prints a warning and leaves the badge empty.
- Heading text splits on `|`: `Name|®| (AB)` keeps the ® as its own run.
- A section may carry its own chart: `"chart": "<png>"`, `"chart_w": 3.4` (inches). The picture sits on the right of that section's bullets,
  the bullets narrow to make room, and the section grows to fit it. Chart titles must stay short (about 20 characters): a longer one is clipped.
- Chart types in `kpm_charts.py`: `yoy` (bars labelled `+12.3%`), `share` (bars labelled `48%`, for conversion or share) and `bars` (monthly columns).

## 4. Render and look at it

Do not trust the code. Export each page with PowerPoint (`$ppt.Presentations.Open(path, $true, $false, $false)`,
`Slides.Item(1).Export(png, "PNG", 1600, 2070)`; LibreOffice is not on this machine) and read the PNG. Check: nothing touches the contact line,
section gaps look equal, the logo badge has its border, no number is clipped, the client name and logo are the attendee's, the notes
carry the client's own sources (grep for another client's name: zero hits).

## 5. Save and hand over

Pages go to `OneDrive - Computer Services, Inc\Executive Summits\<yyyy> <City>\<Client> - <CSM initials>.pptx` (`AB` for Aaron).
Before overwriting a file there, copy it to a subfolder `previous version (<reason or date>)`. After saving, compare file hashes with the
build and send the renders (`SendUserFile`). In the hand-over, list: figures you corrected and why, comparisons you left off because they
were negative, figures you could not verify, and anything older than the newest data (an ILS review a year old). Do not mark anything sent.

---

# ARS one-pager (older, ARS-only)

For an ARS-only print handout from the launcher's data pack. Do not build it for a client with no ARS, or whose ARS deck for the period has
not been built. Save it under `Build Artifacts/summit/<yyyy.mm>/`, not in `Outputs/`.

## A1. Confirm what is being built

Ask, in one message, for anything not already said: **which attendees** (client ids), **which Summit** (the month it is
presented in sets the header: `RPE_PERIOD`, not the data month), and **the data period** to use. If the client is on the Summit list but has
no ARS (`clients.md`), say so and skip it.

## A2. Check the inputs exist

For each attendee, the ARS build for the period must already have written its data pack. `python scripts/ars_launcher.py status <id>`
names what is missing; if no ARS deck exists for the period, build it first (`build <id>`), and tell Aaron.

```
<RPE_DATA_ROOT>\Build Artifacts\launcher\<yyyy.mm>\<id>\base.json            # workbook financials
<RPE_DATA_ROOT>\Build Artifacts\launcher\<yyyy.mm>\<id>\oddd\oddd_metrics.json
<RPE_DATA_ROOT>\Inputs\ODDD\<id>_ODDD.zip                                    # for the responder measure
```

(Open the `*_launcher_result.json` beside them if a name differs; resolve paths through `rpe_env`, never hardcode.)

## A3. Gather the figures, show them, ask

```
.venv/Scripts/python build/ars_pipeline/responder_activity.py "<ODDD.zip>" <scratch>/<id>_resp.json
```

The responder before/after is `before_after.compute`, the same function the monthly deck uses: if the figure here and the client's
deck disagree, that is a defect to report, not to pick between.

Then show Aaron, per attendee, a plain table of what the one-pager prints, in the page's own order, no ranking and no
adjectives: revenue program to date; net profit; return on program cost; customers reached and repeat-responder share;
mailings and months; accounts enrolled vs eligible; Reg E opt-in rate; last-12-month revenue and best month; 36-month debit spend change
and cards in force; responder spend before vs after; transactions over the ask. Mark any figure that is missing or from an incomplete
month (`month_complete`), stated rather than zeroed. Comparisons use complete months only, and the +/-2% band words apply
to any sentence you write (almost flat / state the increase / did not have an impact).

Ask: **"This is the page as `build_ars_onepager.py` lays it out today. Right story for <client>, or what should change?"**
The layout is fixed in code (four tiles, three charts). If Aaron wants a different set of metrics, a tile swapped or a figure left
off, that is an edit to `build_ars_onepager.py`: propose the change, make it on a branch with a test, and let him review it. Never edit it
on the way to a deliverable and never leave it changed for the next attendee.

## A4. Build

Only after Aaron has said the figures are right:

```
$env:RPE_PERIOD = "<yyyy.mm of the Summit>"
.venv/Scripts/python build/ars_pipeline/build_ars_onepager.py <base.json> <oddd_metrics.json> templates/ars_template.pptx `
    <scratch>/assets "<RPE_DATA_ROOT>\Build Artifacts\summit\<yyyy.mm>\<id>-<yyyy.mm>-Summit One-Pager-<Client>.pptx" <id>_resp.json
```

It deliberately skips `restyle_fonts`, `fit_layout` and `validate_deck` (print page, not the 13.33 x 7.5 deck contract). So
check by hand: open the file and look at it (render it, do not trust the code), confirm the header month is the Summit month, the
client name and logo are the attendee's, and the notes carry the client's own sources and no other client's (grep for the reference
client: zero hits). Report what you checked and what you did not.

## A5. Hand over

Give Aaron the file path, the figures it printed, and anything unusual (an incomplete month left out, a stated gap). Do not mark
anything delivered or sent. If a figure surprised you, say so plainly and let him decide.

## Gotchas

- `RPE_PERIOD` (or the output file name's `<yyyy.mm>`) sets the header month. Without it the build stops rather than use the clock.
- A Summit is a couple of times a year and the date lives on `build/assets/summit_slide.pptx`; that slide is unrelated to the one-pager.
- Never import `metrics_gen` (it reads `sys.argv` at import and RUNS). `before_after` and `odd_rows` are the import-safe pieces.
- Shell quoting: Git Bash eats `\u` in a Windows path inside a command; write a script file and run it, or use PowerShell.
- A VIP or CashPlease pull may include the current month to date: its program-to-date total is not "through September".
