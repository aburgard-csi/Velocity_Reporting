# Transaction intelligence: analysis approvals

James approves every analysis personally (the engine started as his Jupyter work). Nothing is drawn
on a slide until its card is approved. Each section gets a card per analysis: exact definition, a
real example, and the decision needed. Decisions are recorded here with the date.

Status values: `approved` (as built), `approved + change` (approved with the change noted, built or
queued), `pending` (card not yet shown), `dropped`.

## Section 1: Portfolio (`txn_*`)  -  decided 2026-10-02

| ID | Analysis | Decision | Change asked for | Status |
|---|---|---|---|---|
| P1 | Feed shape | Approved. "Love visuals here." | Name a missing month (1441 has no Feb 2026 file); a timeline visual of coverage | approved + change (queued) |
| P2 | Channel mix | Approved. The mix varies by client. | Isolate transfers and credit-card payments inside ACH/check. P2P will be large. | approved + change (queued) |
| P3 | Rails statement | Approved. | None | approved (built: `txn_rails`, `txn_rails_label`, `txn_transfer_rails`) |
| P4 | Data coverage | Approved. MCC is the basis for everyday-spend primacy. | Keep the 50% MCC-or-keyword switch | approved |
| P5 | Accounts | Approved. Important for ARS and ICS. | Account counts by program tag once the account spine exists | approved + change (queued) |
| P6 | ODD join | 95% or better is the expectation. "Big for deposits." | `EXPECTED_JOIN_PCT = 95`: under it the run says "partial join"; under 50% (the deposits gate) it says the formats probably differ. | approved + change (built) |
| P7 | Concentration | Approved. Visuals, expansion, dollars. | Rank ACH/check counterparties by **dollars**; add **duration** (how long each counterparty has been paid) | approved + change (queued) |
| P8 | Monthly series | Approved. | Same missing-month handling as P1 | approved + change (queued) |
| P9 | Family tables (by branch, product, swipe tier) | Approved. | Overlay swipe spend and deposits by branch once the deposit file is available | approved + change (queued; card to follow after the code is read) |

## Restored from v5, awaiting section cards

These put the branch back to v5 behaviour. They are approved for the section they belong to only
when that section's cards are approved.

| Commit | What | Section |
|---|---|---|
| Loader | Widest-line read, short reads never cached, READ SHORT banner | Portfolio / loader |
| Matching | `merchant_text`, normalised matching on both sides, marketplace purchases, pairs and reach | Financial services |
| Rails and join gate | P3 and P6 above | Portfolio |

## Queued sections

Financial services, competition, merchants, card behaviour, relationship, interchange,
cross-source. Cards are shown one section at a time.

## Standing decisions

- Peer comparison groups: FI type, then asset band (<0.5B, 0.5-1B, 1-2.5B, 2.5-5B, 5-10B, 10B+),
  from `Client CSM List.csv`. At least 5 peers or fall back; always state the peer count.
- Everyday-spend primacy (accelerating, steady, decelerating, lapsed) is a focus area, with
  competition and cross-sell.
- DDA master and "z-accounts" are future state; the engine does not depend on them.
- `deck_manifest.json` is legacy and unused; the chapter's main cut lives in code.
