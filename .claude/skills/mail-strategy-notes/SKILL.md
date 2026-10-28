---
name: mail-strategy-notes
description: Update Aaron's Delivery Call Notes, review dates and on-site dates in the Business Utilities Mail Strategy form. Use when asked to update delivery call notes, Mail Strategy notes, a client's Recent Review Date or Recent On-Site Review Date, or "the Mail Strategy form". Drafts the notes from deck data, shows a table, and only writes to the live form after Aaron says yes.
---

# Mail Strategy: Delivery Call Notes

The notes live in the Business Utilities **Mail Strategy** form, one record per client, opened from the
"Velocity Product Settings" Power BI app (MailStrategy page, filtered to the CSM). It is a live record shared by
the whole company. Work in four phases and stop for Aaron's yes at the two marked **STOP**.

## 1. Pick the clients and gather the facts

- **Which clients:** ask. The usual set is the clients Aaron has sent a deck this cycle (`Build Artifacts/deliveries.json`,
  `sent` entries for the period). A visit or call can add one client on its own.
- **Run the figures tool**, which reads the same inputs the decks read and never writes anything:

  ```
  .venv/Scripts/python scripts/mail_strategy_facts.py 1038 1075 1204 --json
  ```

  It returns per client: the programs (clients.md), the last send (this is Recent Review Date), ARS profitability
  (a phrase only below 3:1), and the ICS / MRPC / CashPlease lines (last COMPLETE month against the prior six months'
  average, +/-20% band, already worded). Use its wording as it is.
- **Proof status (ARS) comes from the mailbox**, not a file. Vicki Citarelli sends the proofs and copies Aaron; the subject is
  `<id> <Client> <Month> for <Month> ARS offer approval` ("Nov-for-Dec" is the November proof for the December mailing).
  Search Outlook by that subject pattern, newest first: approved (the client replied and Vicki thanked them), awaiting, or past due with
  follow-ups. If you find nothing newer than the existing note, carry the status forward and tell Aaron you could not confirm it.
- **On-site date** comes from Aaron's calendar: the event in the **Onsite** category (e.g. "Velocity - <Client> - ARS/ICS Program
  Review"). If it is ambiguous, ask.
- **Read the existing notes first.** Get each client's current notes and review dates from the Power BI MailStrategy page: tick the
  columns "ARS Delivery Call Notes", "ICS Delivery Call Notes", "MRPC Delivery Call Notes" in the field list (a view setting, it does
  not save) and read the table with `get_page_text` (the full note text is in the page text).

## 2. Write the notes (Aaron's rules, 2026-10-02 / 2026-10-28)

- **Format per product line, which REPLACES the previous note:** `<rating 1-5>. <facts>. <open issues>. [MM/DD]`, with today's date.
- **Rating:** Aaron's 1-5 (contract under 6 months or 6+ months, crossed with good or bad results). Keep the existing rating unless
  new evidence changes it; propose a change, never silently rescore.
- **Recent Review Date** = the date Aaron last SENT the client their results (the tool's `last_sent`).
- **ARS line:** proof status (latest campaign, approved or awaiting) and the schedule. **No response rate and no revenue.** Mention
  profitability only when below 3:1 (`Profitability 2.15:1, below 3:1.`). If nothing is scheduled ahead, copy the 2026 schedule into 2027
  and say so on the ARS line (never copy U-M, the one-time direct mailing). Do not copy it for a client that is not renewing or is winding down.
- **ICS, MRPC and CashPlease:** never % of goal. Say consistent with, higher than or lower than the usual level (the tool does this).
- **Only ARS, ICS, MRPC and CP.** ILS tickets, ILS reviews and ILS calls do not belong in these notes (Aaron, 2026-10-28): leave them out and
  drop any that an old note carries.
- **Banned words apply** (CLAUDE.md, Writing style): no "healthy", "robust", "companion" and so on. State figures; no unsupported claims.
- Remove an open issue only when you have evidence it closed, and say what you removed.

## 3. STOP: show Aaron a table

One row per client with the new Recent Review Date, On-Site date if changing, and each product note in full. List what changed against the
10/02 (previous) notes and every fact you could not confirm. Wait for a yes.

## 4. Fill, STOP again, submit, verify

Use **Claude in Chrome** on Aaron's **Work Laptop** (call `switch_browser`; he clicks Connect). Never act in a hidden iframe or submit from one:
on 2026-10-02 that saved the notes but wiped part of the 2026 month grid on five clients.

1. Create your own tab, open the Power BI MailStrategy report, and **click the client's name in the table**: it opens that client's form in a new tab.
   (The form URL is `.../ProductSettingsMailStrategy?AccountID=<guid>`; the AccountID is not derivable, so open it from the table.)
2. In each form tab, read the fields with `javascript_tool` (the page has jQuery and Kendo). Fields: `RecentReviewDate`, `RecentOnSiteReviewDate`
   (Kendo DatePicker), `ARSDeliveryCallNotes`, `ICSDeliveryCallNotes`, `MRPCDeliveryCallNotes`, `CashPleaseDeliveryCallNotes` (textareas), and one
   Kendo MultiSelect per month named like `FEB26List`, `NOV27List`.
3. **Snapshot the month grid first**: for every `[name$="List"]`, `kendoMultiSelect.value()`, keep the non-empty ones as JSON in `window.__snap` and
   in your notes. This is what lets you prove nothing else changed.
4. **Set** the date with `kendoDatePicker.value(new Date(y, m-1, d))` then `.trigger('change')`; set a textarea's `.value` and dispatch `input` and
   `change`. Then re-read the grid and compare with the snapshot (`monthsUnchanged` must be true) and re-read the fields you set.
5. **STOP: tell Aaron the form is filled and verified and ask before Submit.** Submitting saves to the live record. One confirmation may cover
   several clients if the table was approved, but say what you are about to submit.
6. **Submit** on the visible page: `find` the Submit button on THAT tab (refs can repeat across tabs, so find, scroll to and click one tab at a time),
   wait, then **reload the record** (navigate to the same URL) and compare: the month grid against the snapshot and the notes and dates against what you intended.
   Report any difference at once and restore from the snapshot.
7. Close the tabs you opened (and any that opened by accident) when done. Do not touch Aaron's own Power BI tab.

## Gotchas

- A script whose result contains the page URL or query string (for example `location.search`) is blocked by the tool; return other fields.
- The Power BI table has two "First State Bank" rows (1204 and an old terminated one): tell them apart by the month grid and the note.
- The report is read-only; ticking columns in the field list only changes your view.
- Recent Multi-Product Review Date and the other review dates are separate fields: change only what was asked.
- Today's date goes in the `[MM/DD]` tag; the facts are as of the last complete month.
