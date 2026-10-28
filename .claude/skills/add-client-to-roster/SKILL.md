---
name: add-client-to-roster
description: Add a client, or a program for a client, to clients.md so CSM Sheila lists it and can build its deck. Use when a CSM reports a client "missing" in Sheila, when Aaron says to add a client or start/stop a program (ARS, ICS, MRPC, CashPlease), or when a new client appears in Client CSM List.csv without a roster row. Reads the data side first, proposes the rows, then edits clients.md with a test and a CHANGELOG entry.
---

# Add a client to the roster

`clients.md` decides what gets BUILT, not the presence of a file (CLAUDE.md). A client with no row there never appears in
Sheila, whatever data has landed: James reported 1585 First Community Bank of the Heartland "missing" and that was the whole
cause. Program membership is recorded here, never inferred from files.

## 1. See what is already known

```
.venv/Scripts/python scripts/roster_candidate.py <id> [<id> ...]      # RPE_DATA_ROOT set; read-only
```

It prints, per client: the CSM list name, CSM and programs (the `rpe_programs` column, else `products`), whether the client is already
in the main table and the CashPlease roster, the detected Path (MM or SM, from the newest ARS workbook), the CashPlease loans, and the
proposed rows. It writes nothing. Reports of "missing" often turn out to be a client that IS in the file but blocked by a check
(no workbook, an expired Lift Matrix, a stale ODD): run `python scripts/ars_launcher.py status <id>` to see Sheila's own checks first.

## 2. Decide what is a decision

- **The delivery name** (the `Client` column) is Aaron's call: the CSM list name is a starting point and carries suffixes ("..., Inc.").
  Use the name on the data team's files and the client's own usage; say which you chose and why.
- **Programs** come from the Velocity export. ARS, ICS and MRPC get a "yes" in the main table (`yes (...)` notes say what the ICS data is:
  `direct mail list`, `referrals-only`, `local files`). CashPlease is NOT a main-table column: it gets a row in the
  `### CashPlease roster` table, and `Ships as` says whether it rides inside the client's deck (`**ARS-CP** section`) or stands alone
  (`standalone deck`, only for a client with no other RPE program).
- **ILS is not tracked in the main table** (ILS has no monthly deck). Aaron's own ILS clients have the `## ILS roster` section; add to
  it only when told.
- **Path:** a blank Path on an ARS row reads as MM (every new ARS client is on the Lift Matrix model). Put SM only when the
  workbook's `Executive Financials MM` tab holds the `Bank Name` placeholder (the tool checks this).
- **A client that left or a program that stopped** goes under the Cancelled / ending table or gets `**cancelled**` in its column, with the
  date and who confirmed it. Do not delete the row and do not build from leftover files (the CoastLife ICS lesson).
- A client with no workbook yet can still be added; its Sheila page says the build is blocked until one lands.

## 3. Edit, test, record

1. Work in a scratch worktree from `origin/main` (never the main checkout). Add the row(s) in the right table, in client-id order:
   main table `| ID | Client | Path | ARS | ICS | MRPC | Deck |`, CashPlease table `| ID | Client | CSM | Build | Loans | Ships as | Note |`.
   Put the date and who asked in the Note (`added 2026-10-28 (James: "1585 - ARS + CP + ILS - missing")`).
2. If a CashPlease combined deck was added, fix the count in the prose line that says how many combined and standalone decks a run builds.
3. Run `python scripts/roster_candidate.py <id>` again (it should now say "already in clients.md") and the tests:
   `pytest tests -q -k "roster or clients or cashplease or changelog"` with an empty `RPE_DATA_ROOT` (see the merge-and-release skill).
4. Add a CHANGELOG entry with a `Summary:` line saying the client now appears and what it builds. Commit, push, open a PR.
5. **The roster reaches the CSMs only through a release** (`clients.md` ships with the code). After the PR merges, tell Aaron it needs a
   release, and offer it (merge-and-release skill). Do not release unasked.

## 4. Check it shows

After a release (or in Aaron's own checkout), open Sheila's client list or run `ars_launcher.py status <id>`: the client should appear
with its programs and either "Ready to build" or the specific STOP that explains what data is missing.

## Gotchas

- `read_roster` reads the main table BY POSITION and each section by its heading: never add a column to the main table, and put any
  new table under its own `##` heading that the parser knows (see the `ILS roster` pattern in `scripts/build_month.py`).
- The CashPlease table is read by HEADER NAME; its column order is free.
- Two files can disagree about a client's CSM: the Client CSM List wins (`rpe_env.client_csm`); the CashPlease roster's `CSM` column is the
  only place a CashPlease-only client's CSM is recorded.
- Never put client logos, member data or ODD extracts in git.
