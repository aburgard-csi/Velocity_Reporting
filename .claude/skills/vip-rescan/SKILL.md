---
name: vip-rescan
description: Rescan the VIP dashboards (vip.myvelocity.com) for the ICS and MRPC clients and update Inputs/VIP Data (the per-client JSON, manifest.json, README Currency section, a raw capture log) and the RPE Client Performance dashboard. Use when told VIP has been updated, to scrape or refresh VIP ICS / MRPC results, or to update the VIP tracking. Needs a signed-in VIP session in Chrome; a person signs in, never Claude.
---

# VIP rescan — ICS and MRPC

Values come off rendered Looker embeds (cross-origin iframe): the page's JS and network log
cannot read them. Read zoomed screenshots, write each reading down as you go, reconcile
to the tiles, then update the store. `Inputs/VIP Data/` is the ONLY copy (see CLAUDE.md);
`rpe_env.resolve_client_json` reads it. Worked example of a whole run: `reference/`.

## 0. Before starting

1. **Sign-in is the user's.** Open `https://vip.myvelocity.com` in the Claude-in-Chrome tab
   and look. Signed in shows "Aaron Burgard" and a left nav; "Login Error: User is not active"
   or a sign-in page means STOP and ask the user to sign in (MFA included). Never enter
   credentials. Never open a `/dashboard/...` URL cold; it logs the session out. Navigate
   by the left nav. If this Chrome will not sign in, `switch_browser` pairs "Work Laptop".
2. Load the Chrome tools in one ToolSearch call (tabs_context_mcp, navigate, computer,
   find, javascript_tool), then `tabs_context_mcp` with `createIfEmpty`.
3. Read the current store state: `Inputs/VIP Data/README.md` (Currency, last scan),
   `manifest.json`, and one existing `<id>_ics.json` / `<id>_mrpc.json` for the shapes.
4. Scope: **ICS** 1075 1509 1537 1539 1549 1632 1676 1734 1738. **MRPC** 1075 1218 1437 1477
   1502 1539. Leave 1658 Truliant (inactive) and 1705 CoastLife (cancelled) as they are.
   1549 Wellworth has no MRPC. 1437 is marked stopped in `clients.md` but is scanned anyway.
   Re-check `clients.md` and the manifest if the roster has changed.

## 1. Navigation (works on the 2026-10-27 UI)

- Client selector, top left, at about (100, 95): click, `ctrl+a`, `Delete`, type the id,
  wait 3 s, key `Down Return`. This selects the one filtered option without needing a ref.
  The page reloads; Looker takes 20-40 s, so wait 10 s three times, not once.
- Left nav: **My Rewards Premium Cards** expands to MRPC Revenue to FI / Enrollments /
  Performance / Retention; **Invitation Checking System** to ICS Referral Data. Menu
  positions shift per client (some have CashPlease, Account Engagement), so use `find`
  for the item, or the `/dashboard/mrpc/...` button's ref, never a fixed coordinate.
- Staying on one dashboard and switching client reloads that same dashboard. Do all
  clients on one dashboard before moving to the next.
- Each page is long; scroll 6 ticks to bring the tables into view, then `zoom` the region.
  Zoom regions that worked at 1053x1148: tiles + tables `[242,90,1026,780]`; Branch Success
  `[246,205,796,490]`; YTD table `[802,205,1026,490]`. A table scrolls inside itself:
  scroll with the cursor over it, 2 ticks at a time, zoom after each.
- If `Page.captureScreenshot` times out, the renderer is busy: take a plain 0.5-scale
  screenshot, then retry the zoom.

## 2. What to read

### ICS Referral Data (one dashboard per client)
- Trend chart: every month's bar and the goal line.
- Tiles: Latest Data (truncated to `2026-1`, so it is the current month when October has data),
  Previous Month, Month-to-Date, Year-to-Date, Program-to-Date.
- Branch Success by Month (branch, goal, referrals), YTD Compared to Goal Totals, and
  Referrals by Branch. Scroll each to the end.
- **Issue Month filter:** it defaults to This Month. On the 1st-3rd of a month that returns
  nothing for the branch tables, so use Previous Month (filter pill > Presets > Previous Month
  > the reload icon), and it resets on every client change. Later in the month This Month
  works and the branch tables are month-to-date; say which in the capture log.
- **The Origination pie always shows the PREVIOUS month's split.** Do not record it as the
  current month.

### MRPC (four dashboards)
- **Enrollments:** stacked Personal bars (Gold labelled in the teal base, Platinum above),
  Business bars, % by Channel donut, Aging Summary, Enrollments by Branch (previous
  month, YTD). A bar with no label is 0 or too short to print; read it from the axis and
  say so. Channel donut and branch panels can still be loading: scroll away and back, wait,
  and if still blank carry the old value and say so.
- **Performance:** "New Accounts Performance by Period" table (period, goal %, % of goal,
  new accounts, goal, enrollments) and the Top Performers branch tables. The table updates
  on the 15th and then ends at the previous month; before the 15th it does not move.
- **Retention:** "Retention by Month Enrolled" (Total and Total Active per cohort) and the
  % Cancellations by Reason donut. Cohorts trail about four months.
- **Revenue to FI:** NOT re-read. Revenue is stale for all clients and is being fixed with
  Accounting (CLAUDE.md memory, 2026-10-06). Carry `revenue` and `card_billing` forward and
  say so in the notes. Do not flag it per client.

## 3. Reconcile before writing

- ICS: `previous + month-to-date` against the old YTD and PTD tiles. YTD and PTD should
  move by exactly the month-to-date, plus any restatement. Branch Success referrals sum to
  the MTD tile; the YTD table sums to the YTD tile. 1632 WesBanco has ~220 branches, so its
  lists are top rows only (`partial_list: true`) and do not sum.
- A closed month that changes is a **restatement by VIP**: record it (old -> new), let the
  PTD and YTD follow, and do not "correct" it.
- MRPC: Gold + Platinum + Business per month against the old file; list every changed
  closed month in the README table. Retention cohorts and enrolled counts may be restated
  upward (1437 on 2026-10-27).
- A reading that contradicts the old file with no explanation is flagged for the user, not
  silently written (1502's blank September bar on 2026-10-27).

## 4. Write the store

For each file: back up first as `<id>_<type>.<date>.bak.json` beside it, change only the VIP
blocks (ICS `referrals`; MRPC enrollments, channel, performance, retention, aging, branch
tables), keep every workbook-sourced block, set `meta.data_pull` and `meta.note_period`,
and write with `ensure_ascii=False`. Keep the file's existing key shapes: see
`reference/example_write_ics_*.py` and `example_write_mrpc_*.py` for the exact mapping,
and for the raw capture shape: `R[client_id] = dict(prev, mtd, ytd, ptd, goal_oct, oct_branch=[(name, goal, referrals)], ytd_branches=[(name, referrals, goal)])` for ICS, and `M[client_id] = dict(enroll, channel, aging, perf, retention, branch_prev, branch_ytd, branch_ptd)` for MRPC. Keep raw readings in the scratchpad and in `_rescan_<date>_capture.md` on the share, never in the repo (client data). **The example scripts hard-code the
2026-10 month labels (`Oct 26`, `Sep 26`, `2026-10`); adapt them, do not run them as-is.**
Resolve truncated branch names ("Lebanon...") against the previous file's names, and
disambiguate by old + month-to-date referrals.

Then:
1. `manifest.json`: back it up as `manifest.<date>.bak.json`; set `data_pull` on every
   refreshed entry; extend `note` and `generated`.
2. Write `_rescan_<date>_capture.md` (raw readings per client, the filter used, anything
   unread).
3. README.md > Currency: change "Last full scan", add a dated `### <date> rescan` section
   above the previous one with the ICS table, the MRPC table and every restatement.
4. Verify by reloading every file: latest month, tiles, branch sums.

## 5. Tracking dashboard

```
python scripts/refresh_performance_dashboard.py          # run from the repo .venv; ends STATUS: changed|unchanged
python scripts/refresh_performance_dashboard.py --mark-published
```
On `changed`, republish to the existing artifact (never create a new one):
- The Artifact tool cannot publish from the share. Copy
  `Build Artifacts/perf_dashboard/rpe_dashboard.html` into the scratchpad and publish that.
- The first publish is refused until the live version has been read. It hands back a saved
  copy; diff it against yours with the data line removed (line 263 live, 262 local). If
  the diff is empty, publish again unchanged.
- URL: `https://claude.ai/code/artifact/71e542f6-cb48-4386-ae73-708e513c854b`.
  The tool echoed `https://claude.ai/artifact/F4jLMLqxmQdBNYXpJHH6We` (Version 64) on
  2026-10-27; confirm the two are the same page.
- Then `--mark-published`. The "MISSING ics" rows in its output are clients with no VIP sheet,
  not a failure of this run.

## 6. Finish

Report: the ICS table (Sep, MTD, YTD, PTD), restatements, MRPC performance and enrollments,
what was carried forward (revenue, card billing, anything that did not load), and anything
to verify. Commit nothing unless asked: `Inputs/VIP Data` is not in git, and this skill
changes only with the repo.

## Do not

- Sign in, handle MFA, or type any credential.
- Open dashboard URLs directly, or use another client id's page for a client.
- Zero or invent a value that did not load; carry it and say so.
- Re-copy anything into `build/*/data/`; that store was deleted on purpose.
- Add a mirror of `Inputs/VIP Data` anywhere.
