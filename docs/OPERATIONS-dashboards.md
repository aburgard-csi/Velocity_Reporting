# Operations: the delivery dashboard and the performance dashboard artifact

Moved verbatim from `CLAUDE.md` on 2026-11-25, when Aaron asked for a shorter CLAUDE.md. `CLAUDE.md` keeps the rules that change what a session does; this file keeps the full sections. The daily source watch, which sat between these two in CLAUDE.md, is in `docs/OPERATIONS-source-watch.md`.

## Delivery dashboard

```
python3 scripts/dashboard.py [--period 2026.09] [--port 8787] [--no-source]
```

Serves `http://127.0.0.1:8787/` — data readiness, what is built, and what still
needs sending, per client for one period. Loopback only: it exposes a write
endpoint and the delivery log is not public. `scripts/deck_status.py <period>
--json out.json` produces the same document without a browser.

**Where each fact comes from.** The dashboard invents nothing; it displays
`deck_status.collect()`.

| Fact | Source |
| --- | --- |
| Who gets a deck | `clients.md`, via `build_month.read_roster` — the same parser the builder uses |
| Has the data team landed it | every CSM's ODD folder (`deck_status.SRC_ODDD` — all five, each with its own month-folder naming; see **Daily source watch**) and `\\PADMIS105\Velocity_clientreports\<YYYY.MM>\<Account Manager>\` |
| Can the build run | `Inputs/` — the copy the builders actually read |
| Built | `Outputs/<CSM>/<id>-<period>-*.pptx` (via `rpe_env.output_decks`) |
| Sent | `Build Artifacts/deliveries.json` |

Override the share paths with `RPE_SRC_ODDD` / `RPE_SRC_REPORTS`; they are never
hardcoded, for the same reason `RPE_DATA_ROOT` is not.

**The CSI shares need the VPN (Aaron, 2026-08-31).** Off VPN they are not empty,
they are *unknown*, and the dashboard says so rather than reporting a full cycle
of phantom gaps. The input columns stay accurate either way.

**Sent is recorded, never inferred.** A deck in `Outputs/` proves it was BUILT.
Nothing on disk knows whether it reached the client, so sent-state is written to
`Build Artifacts/deliveries.json` by the dashboard's Mark sent button (Aaron,
2026-08-31) — bookkeeping, so it stays out of `Outputs/`. A damaged log raises
rather than reading as "nothing sent", which would invite sending twice.

**An ODD extract in `Inputs/` is only current if the SOURCE says so.** `Inputs/ODDD/`
holds `<id>_ODDD.zip` with no period in the name, overwritten in place each
month — so last month's extract sits at the same path under the same name and
"a file is there" does NOT mean this period's data is there. The dashboard
reports that as **stale**, and stale blocks exactly as hard as missing: a build
on the previous month's ODD completes, validates, and reports the wrong month.
Off VPN the period cannot be confirmed and is reported as unknown, not current.
**The watch's landing record also counts as the source saying so** (2026-10-13): when the
share no longer holds this period's file but `source_watch.json` recorded an ODDD landing
for this client and period whose size matches the copy, `deck_status.watch_landing` vouches
for it (1539 Marine's October extract was taken back off the share a week after the watch
copied it, and Sheila called the copy "previous month"). **So does the extract's own pull stamp**
(2026-10-13, 1509 Texas Bay: an extract that came by email and was copied into Inputs by hand):
`deck_status.odd_stamp_period` reads the member file's `(MMDDYY_HHMMSS)` stamp, and a pull in the
cycle's month is that cycle's extract. A stamp naming another month is stale and says which; no
share copy, no watch record and no stamp is the stale case it always was.

**ICS workbooks arrive by email, not on the share (Aaron, 2026-08-31).** They
have no source-side signal, so their source column is `n/a` and a missing one
does not block — without a workbook for the period the ICS section builds
referrals-only, which is a valid deck.

### The performance dashboard artifact — refreshed after each source check

```
python scripts/refresh_performance_dashboard.py [--period 2026.08] [--csm "Aaron Burgard"] [--force]
python scripts/refresh_performance_dashboard.py --mark-published
```

The "RPE Client Performance" artifact
(`https://claude.ai/artifact/F4jLMLqxmQdBNYXpJHH6We`; the older `claude.ai/code/artifact/71e542f6-cb48-4386-ae73-708e513c854b` form opens the same artifact, and the refresh task still uses it) is the
cross-client, cross-product page Aaron asked for on 2026-09-08: one section per
program (ARS, ICS, MRPC, CashPlease) with a ranked bar, a metrics table and trend
sparklines, and a deck roster. It is a static page with its dataset embedded.
`refresh_performance_dashboard.py` rebuilds that dataset from the same inputs the
deck builders read (ARS workbooks + DCOs through the ARS extractors, mailing response
from the shipped deck's figure sidecar, the VIP ICS / MRPC sheets, the newest
MRPCEnrollmentSummary and CashPleaseSummary weeklies — the last through the
in-repo `build/cashplease_pipeline/cp_extract.py`, so the page and the CashPlease
decks are computed once), injects it into `scripts/perf_dashboard_template.html`, and writes the
page and its bookkeeping to `Build Artifacts/perf_dashboard/`. **The period is the
calendar month (Aaron, 2026-10-02).** It used to be the newest ARS workbook in `Inputs/`,
which left the page reading "Reporting period 2026.09" on 2 October while that month's
workbooks were still landing. **Within that cycle every client shows its own newest figures**
(Aaron, 2026-09-08): the newest ARS workbook, shipped-deck sidecar and built deck at or
before the cycle period, with the row tagged when that is older than the cycle. A
cycle-only page went blank for three ARS clients and every deck the first morning of a
month. It ends with `STATUS: changed|unchanged`, comparing a content hash (generation
date excluded) to the hash last published.

Publishing needs the Artifact tool, so the script never publishes. The Claude
scheduled task **`rpe-dashboard-refresh`** (daily 08:30, after the 08:00 source
watch; stored under `~/.claude/scheduled-tasks/`) runs the script, republishes to the
URL above only on `changed`, then runs `--mark-published`. It runs while the Claude
desktop app is open and catches up on next launch. **Do not create a new artifact
for this page** — republish to the URL, or the link people hold goes stale.

**The page lists ONE CSM's clients (Aaron, 2026-11-02: "limit that artifact to my own clients, since we
now have Sheila").** `--csm "Name"`, else `RPE_DASH_CSM`, else Aaron Burgard; the Client CSM List decides, and the
scope is applied before a client's inputs are read, so another CSM's client is not extracted and is nowhere in the
embedded dataset (`tests/test_refresh_performance_dashboard.py` pins it). There is no all-CSMs option. The CashPlease
company rows span EVERY current client in the weekly, all CSMs (Aaron, 2026-11-24; they covered only the clients whose
roster row carried CP until then): the **median current client** (`cp_peer_median`), the figure every client is compared
with, and the book pooled (`cp_peer`), labelled "CashPlease book, pooled" and internal only; medians, counts, rates and
averages only, never a client's volume. The page is in the Sheila
Hub's look (sidebar, KPI tiles, Hub colors, no orange): edit `scripts/perf_dashboard_template.html` and
`scripts/perf_workflow.html`, never the published copy.
