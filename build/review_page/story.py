#!/usr/bin/env python3
"""story.py — the storyline: which screens, in what order, under which section.

Aaron, 2026-11-03: "go through them and pick the most impactful as if you're a banker in charge of retail
performance." The tests the head of retail banking applies, in order, to every candidate slide:

  1. Does it tie to dollars (revenue, profit, fee income, deposits, interchange)?
  2. Does it name a decision (where to mail, which branches to coach, what to fix in Reg E opt-in, which
     competitors take our members' spend, which accounts may leave)?
  3. Is the finding clear without explanation, and comparable (to a goal, to the prior period, to the rest of the book)?
  4. Is it not already on the page?

`docs/LIVE-REVIEW-SELECTION.md` holds the whole ranked table, kept and skipped, with the data each view needs.
This module is the kept list. A `ref` is "<program>:<screen id>"; a screen whose program has no pack on this
machine is shown as a "run X first" state in its place, so the storyline keeps its shape for every client.

Import-safe.
"""

# (section id, product, title, one line on why it is in the review, [(ref, title, kicker)])
# Organised by product (Aaron, 2026-11-03: "the sections need to be organized by product", "treat Transaction
# Intelligence as a product"): ARS first (its Companion views are ARS screens), then Transaction Intelligence, then the
# client's other programs. A section holds the screens of ONE product.
SECTIONS = [
    ("program", "ars", "The program", "What the program has returned, and whether the guarantee holds.", [
        ("ars:summary", "Summary", "ARS · Program overview"),
        ("ars:financial", "Financial performance", "ARS · Program P&L"),
    ]),
    ("revenue", "ars", "Where the revenue comes from", "Which mailings pay, what a thousand offers return, and what a response is worth.", [
        ("ars:mailings", "Mailings", "ARS · Offers and response"),
        ("analysis:waves", "Where the revenue comes from", "Revenue · By mailing"),
        ("analysis:offers", "What 1,000 offers return", "Revenue · Offer efficiency"),
        ("analysis:response", "What a response is worth", "Revenue · Response against a control"),
    ]),
    ("branches", "ars", "Branch performance", "Which branches to coach on take rate and Reg E opt-in.", [
        ("ars:take", "Debit take rate", "ARS · By branch"),
        ("ars:rege", "Reg E opt-in", "ARS · By branch"),
        ("analysis:scorecard", "Branch scorecard", "Branches · Who to coach"),
    ]),
    ("members", "ars", "Member behavior", "How members use their cards, and who is moving up.", [
        ("ars:usage", "Debit use and NSF/OD", "ARS · Swipes, spend, overdraft"),
        ("ars:lift", "Lift Matrix", "ARS · Revenue by swipe tier"),
        ("analysis:migration", "Swipe tier migration", "Member behavior · Tier movement"),
    ]),
    ("worth", "ars", "What it is worth next", "What closing the gaps would earn.", [
        ("analysis:five-points", "What five points would be worth", "What it is worth · Sizing"),
    ]),
    ("competition", "ti", "Competition and leakage", "Who takes our members' spend, and who else they borrow from.", [
        ("ti:competition", "Where members spend elsewhere", "Competition · Share of wallet"),
        ("ti:leakage", "Who else members borrow from", "Competition · Financial leakage"),
    ]),
    ("attrition", "ti", "Attrition and deposits", "Which accounts are leaving, and the deposits behind them.", [
        ("ti:attrition", "Attrition by branch", "Attrition · Who is leaving"),
        ("ti:at-risk", "Deposits at risk", "Attrition · Who to call"),
        ("ti:deposits", "Where deposit inflow is falling", "Deposits · Inflow"),
    ]),
    ("ti-worth", "ti", "What it is worth", "What an opt-in and a card earn, and where the branch gaps sit.", [
        ("ti:value", "What a card and an opt-in earn", "What it is worth · Per account"),
        ("ti:branch-gap", "Branch value gap", "What it is worth · By branch"),
    ]),
]

# The client's other programs, one section each, shown only when the client has the program (nothing is stubbed for a
# product it does not have): the results, then how the client compares with its peers on that product.
OPTIONAL = [
    ("ics", "ics", "Referrals and results", "Referrals, results by branch, and how the client compares with other ICS clients.", [
        ("ics:referrals", "ICS referrals", "ICS · Invitation Checking"),
        ("ics:branch", "ICS results by branch", "ICS · Year to date"),
        ("ics:peers", "ICS: how you compare", "ICS · How you compare"),
    ]),
    ("mrpc", "mrpc", "Enrollments and status", "Program status, enrollments, and how the client compares with other MRPC clients.", [
        ("mrpc:status", "MRPC program status", "MRPC · From the weekly"),
        ("mrpc:enrollments", "MRPC enrollments", "MRPC · By month"),
        ("mrpc:peers", "MRPC: how you compare", "MRPC · How you compare"),
    ]),
    ("cashplease", "cashplease", "Loans and portfolio", "Loan summary, volume, and how the client compares with other CashPlease clients.", [
        ("cashplease:summary", "CashPlease loan summary", "CashPlease · Weekly"),
        ("cashplease:volume", "CashPlease volume", "CashPlease · Loans"),
        ("cashplease:peers", "CashPlease: how you compare", "CashPlease · How you compare"),
    ]),
]

TITLE = "The review"


def refs():
    return [r for _id, _p, _t, _b, items in SECTIONS for r, _tt, _k in items]


def resolve(programs):
    """The storyline against the programs that built: {"title", "sections": [...], "stubs": {...}}.

    A section lists its screens as {"ref", "prog", "id", "title"}. A ref whose screen does not exist is a
    STUB, carried in "stubs" as a full screen that says what is missing and what to run (its program's own
    note and fix), so the page never hides a part of the story the client has not got data for.
    """
    from review_page import blocks as B
    by = {e["key"]: e for e in programs}
    out, stubs = [], {}
    for sid, product, title, blurb, items, optional in [(*sec, False) for sec in SECTIONS] + [(*sec, True) for sec in OPTIONAL]:
        scr = []
        for ref, ttl, kicker in items:
            prog, _, scid = ref.partition(":")
            e = by.get(prog)
            have = e and any(s["id"] == scid for s in e["screens"])
            if optional and not have:
                continue                  # a program the client does not have is not a section of its review
            if not have:
                if e and e["state"] == "ready":
                    why, fix = "This client's pack does not carry the data this view needs.", "Rebuild the pack this view reads (see Sources) and reload."
                else:
                    why = (e or {}).get("note") or f"{prog} is not on the page."
                    fix = (e or {}).get("fix") or "Build the program's pack first."
                stubs[ref] = B.screen(scid, ttl, kicker, f"{ttl} needs data this client does not have on this machine yet.",
                                      [{"t": "needs", "what": why, "fix": fix}], [], [])
            scr.append({"ref": ref, "prog": prog, "id": scid, "title": ttl, "stub": not have})
        if scr:
            out.append({"id": sid, "prog": product, "title": title, "blurb": blurb, "screens": scr})
    return {"title": TITLE, "sections": out, "stubs": stubs}
