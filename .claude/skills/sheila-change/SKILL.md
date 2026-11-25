---
name: sheila-change
description: Add or change a page, tab, card or button in CSM Sheila (the local browser front end every CSM builds decks from). Use when Aaron asks for a new Sheila tab or card, a change to the client list, the client page, the Lift Matrix, Data Issues, Slide Review, Feedback or the ILS cards, or a fix to how Sheila looks or behaves. Covers where the code lives, the page conventions, the tests, seeing it on synthetic data, and shipping it with VERSION, the user guide, CHANGELOG and a release.
---

# Change CSM Sheila

Sheila runs on every CSM's PC from the released code, so a change reaches them only through a release, and a broken page
stops every CSM building. CLAUDE.md's file map has the full account of each file; this skill is the working order.

## 1. Find where it goes

- **The page:** `scripts/sheila_hub.py` is the shell and the Decks tab (sidebar, KPI tiles, client list, client page,
  palette, keys, theming). Every other tab is its own module listed in `sheila_hub.TAB_MODULES`, each exporting `TAB`
  (the hash route, or `None` for a module that only adds cards), `NAME`, `VIEW`, `CSS` and `JS`; `_assemble()` splices
  them into the page. A new tab is a new `scripts/sheila_hub_<tab>.py` plus its name in `TAB_MODULES`.
- **Routes and logic:** `scripts/ars_launcher_web.py` (every `/api/...` route, the background client-list refresh, the
  build queue, the caches). The page modules hold no logic of their own.
- **ILS cards:** `scripts/ils_ui.py` (routes and labels), `scripts/ils_runs.py` (pre-go-live and kickoff runs),
  `scripts/ils_review_runs.py` (the ILS Review card); the page side is `scripts/sheila_hub_ils.py`.
- **Sheila in Claude** (`sheila_mcp/`) calls the same functions the buttons call. Decide whether it needs the change too
  (a new answer a CSM would ask Claude for), and say so in the PR either way.

## 2. Keep the page conventions

- **Hash routes.** The address names the tab (`#lift`, `#issues`, `#votes`, `#reported`; none is Decks) and what it
  shows (`#lift&client=<id>`), so bookmarks and cross-tab links land where they say. A new tab gets a route.
- **Keys.** `G` then a letter between tabs (`TAB_KEY` in `sheila_hub.py`), the Ctrl K palette (it lists every tab from
  the same table), and `?` for the keys of the tab you are on. A new tab gets a letter, a palette entry and its `?` help.
- **The client list is computed in the background refresh** (`CLIENTS_TTL`, `STATUS_TTL`, `SHARE_TTL` in
  `ars_launcher_web.py`), never per request; a request reads what the refresh left. A read that fails shows "not
  checked", never Ready (see `ils_list_state`). A slow share read in a request handler freezes every CSM's page.
- **Look.** The Hub's own colours (the CSS tokens at the top of the page's style, light and dark under
  `prefers-color-scheme`), its chips and status shapes, and the Mission Control table style for tables. Use the existing
  tokens (`--accent`, `--good`, `--warn`, `--bad` and their `-soft` pairs), never a new colour, and nothing that breaks at
  phone width (the sidebar becomes a bottom bar).
- **Security.** Loopback only, every API call carries the page's token, and "Show in File Explorer" opens only files under
  Outputs. Keep it that way for any new route.

## 3. Test

Work in a scratch worktree on a new branch from `origin/main`. Add tests beside the existing ones and run them like CI
(empty `RPE_DATA_ROOT`; merge-and-release skill, section 3):

```
... -m pytest tests/test_sheila_hub.py tests/test_sheila_hub_tabs.py tests/test_sheila_ils.py tests/test_ils_review_card.py tests/test_sheila_build_panel.py tests/test_ars_launcher_web.py -q -p no:cacheprovider
```

The page-parse test in `tests/test_sheila_ils.py` runs `node --check` over the page's script and SKIPS when `node` is
not installed: a skip there is not a pass, so say so if it skipped. Then the full suite.

## 4. See it

Run Sheila on a SCRATCH data root with synthetic clients, never the share:

1. A scratch folder with `Inputs`, `Outputs`, `Build Artifacts`, and a `Client CSM List.csv` / `CSM Contacts.csv` holding
   made-up client ids and names (copy the column headers from the real files' first line only; no real rows).
2. `$env:RPE_DATA_ROOT = '<scratch>'`, then from the worktree:
   `<.venv python> scripts/ars_launcher_web.py --no-open --port <free port>`. It prints the URL; the token is baked into
   the page served at `/`.
3. Screenshot it with a SEPARATE headless Chrome (`--headless=new --remote-debugging-port=<n> --user-data-dir=<temp>`)
   over DevTools: `Emulation.setDeviceMetricsOverride` for desktop (1440 wide) and phone (390 wide, mobile),
   `Emulation.setEmulatedMedia` with `prefers-color-scheme` light and dark, `Page.captureScreenshot` to the scratchpad.
   Look at every shot with Read.
4. Stop the server when done.

**Never move, resize or screen-grab Aaron's desktop windows** to get a picture: his Chrome and his Sheila console are in use.

## 5. Ship

1. **`VERSION`**: bump it for a visible feature (first line, `N.N`; Sheila shows it in her header). Bump from what is on
   `origin/main` at merge time: another open PR may have bumped it too.
2. **The user guide**, `scripts/launchers/ARS Deck User Guide.html` (released to the CSM_Reporting root): describe the
   new tab, card or button the way a CSM meets it.
3. **CHANGELOG** entry starting `Summary:` in plain words for a CSM: Sheila shows that line in What's new.
4. CLAUDE.md's file map line for the file, if what it does changed.
5. Commit, push, PR. **STOP: merge and release only on Aaron's word** (merge-and-release skill). After the release, tell
   Aaron to close and reopen Sheila: each PC copies the new code when its launcher starts.

## Gotchas

- **Every module's `JS` is concatenated into ONE page script** (`_assemble()` replaces placeholders in raw strings): a
  syntax error in one tab's script stops the whole page, Decks included. The node page-parse test is what catches it,
  so make sure it ran rather than skipped.
- **The CSM is detected from the Windows login** (`sheila_hub.detect`, `RPE_SHEILA_CSM` overrides); a scratch root with no
  match shows every client, which is fine for screenshots.
- **Sent state is not Sheila's** (that is the delivery dashboard); do not add it here.
- **No client data in git**: scratch roots, screenshots and fixtures with real names stay out of the repo.
