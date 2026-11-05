"""`python -m sheila_mcp`: CSM Sheila as a Claude Desktop connector (stdio MCP server).

Each tool is one thing Sheila's page does; the function behind it is the one the page's button calls.
"""
import os
import sys
import threading

from . import REPO  # noqa: F401  (puts build/ and scripts/ on the path)

from . import actions, core, reports
from .stdio import Server

INSTRUCTIONS = """You are talking to CSM Sheila, the Velocity CSM team's deck and reporting helper. Sheila builds
client decks (ARS / RPE, combined ARS+ICS+MRPC+CashPlease, CashPlease-, ICS- or MRPC-only, the ARS Companion,
Transaction Intelligence) and runs the ILS pre-go-live and kickoff analyses, all from the files on
M:\\CSM_Reporting, and files finished decks in Outputs\\<CSM name>\\.

How to work with Sheila:
- The person is a CSM. "Me" and "my" mean them: Sheila knows who they are from their Windows sign-in.
- Clients are 4-digit SRDB numbers. Say back the SRDB and name ("1798 FirstLight FCU") before acting,
  and if a name matches more than one client, ask which.
- Relay Sheila's answer text plainly. When something failed or is blocked, quote Sheila's words; do not
  guess at causes.
- Before a build, say what it will make (Sheila's answer names the programs). A build that would replace
  a deck already in Outputs comes back asking to confirm: ask the person, and only on their yes call
  build again with confirm=true.
- Builds take minutes (Transaction Intelligence about half an hour). Start one, tell the person, and check
  build_progress when they ask. Never claim a deck is done until build_progress says it is in Outputs.
- ILS: step 1 shows the field summary and computes nothing. Which code means open, personal, eligible or
  opted in is the CSM's call; never pick codes for them. Run step 2 only with codes they confirmed.
- Sheila never sends email or anything else. To share a deck, give its Outputs path.
- For "where does this number come from", use explain on the slide, then name the source it gives.
- For a call or meeting, use client_brief or client_prepare. Notes, tasks, calendar and email are not Sheila's:
  if the person's Microsoft 365 connector is available, use it for those, and say which part came from where.
- Peer figures are against every client whose deck was built the same cycle; with fewer than 5, give ranks,
  not percentiles."""

mcp = Server("sheila", core.version(), INSTRUCTIONS)


@mcp.tool
def my_month(csm: str = "me") -> dict:
    """The CSM's book for this cycle, grouped: Ready to build, Blocked (and by what), Last build failed,
    Built in Outputs. Use for "where am I this month", "what's left", "what can I build".
    csm: "me" (default), or a CSM's name ("Jordan")."""
    return core.my_month(csm)


@mcp.tool
def clients(csm: str = "me", query: str = "", program: str = "") -> dict:
    """List clients: a CSM's book ("me", a name, or "all"), optionally by name words or program (ARS, ICS,
    MRPC, CP, ILS ...). Use to find a client's SRDB."""
    return core.clients(csm, query, program)


@mcp.tool
def client_status(client: str, fresh: bool = False) -> dict:
    """One client: Sheila's pre-build checks (what is missing and where it goes), what a build would make,
    the last build and why it failed, and the Transaction Intelligence and Companion checks.
    client: SRDB number or name words. fresh=true re-reads the share instead of the last 10 minutes' check."""
    return core.client_status(client, fresh)


@mcp.tool
def build(client: str, kind: str = "ars", confirm: bool = False, deck_only: bool = False) -> dict:
    """Start building a client's deck into Outputs. kind: "ars" (the client's regular deck: ARS, with
    CashPlease where it ships, or every program with data for a client with no ARS), "combined" (ARS plus
    ICS/MRPC/CP with data), "ti" (Transaction Intelligence), "companion" (ARS Companion).
    Returns at once; check build_progress. If a deck is already in Outputs it asks first: pass confirm=true
    only after the person says yes. deck_only=true (ti only) redraws slides from the last build's figures."""
    return actions.build(client, kind, confirm, deck_only)


@mcp.tool
def build_progress(client: str) -> dict:
    """Where a client's build stands: queued, the step it is on, done (with the Outputs path and the
    validation verdict), or not put in Outputs (with the launcher's own words)."""
    return actions.build_progress(client)


@mcp.tool
def build_queue() -> dict:
    """What is building now and what is waiting, from Claude on this PC."""
    return actions.queue()


@mcp.tool
def deck_summary(client: str, kind: str = "ars") -> dict:
    """What's in a client's deck in Outputs: its path, slide count, validation verdict, when it was built,
    and every slide's headline (slides needing review are marked). kind: ars, combined, ti or companion."""
    return core.deck_summary(client, kind)


@mcp.tool
def review(client: str, kind: str = "ars") -> dict:
    """What the validator asked a person to check in the client's deck: each FAIL and REVIEW with its
    slide number and reason. Use for "what needs my review"."""
    return actions.review(client, kind)


@mcp.tool
def explain(client: str, slide: int, kind: str = "ars") -> dict:
    """Where a slide's numbers come from: its headline, every figure on it, the source data its notes
    name (file, lens, analysis), and any validator finding for that slide."""
    return actions.explain(client, slide, kind)


@mcp.tool
def outputs(csm: str = "me") -> dict:
    """The decks in a CSM's Outputs folder for this cycle, with the folder path."""
    return core.outputs(csm)


@mcp.tool
def data_issues(client: str = "", csm: str = "me", include_done: bool = False) -> dict:
    """Data Issues (Sheila's tab): missing or stale inputs, unmapped codes, Lift Matrix flags, for one
    client, or every client in a CSM's book when client is empty."""
    return core.data_issues(client or None, csm, include_done)


@mcp.tool
def ils_status(client: str) -> dict:
    """A client's ILS pre-go-live and kickoff: whether the extract has landed (and where it goes), the codes
    last confirmed, the newest output, any run going."""
    return actions.ils_status(client)


@mcp.tool
def ils_run(client: str, kind: str, codes: dict = None, period: str = "", fee: str = "") -> dict:
    """Run an ILS analysis. kind: "pgl" (pre-go-live) or "kickoff". Without codes: step 1, the field
    summary, computing nothing. With codes: step 2, on the codes the CSM confirmed (pgl: open_status,
    od_eligible, rege_opt_in, rege_opt_out; kickoff: personal_code, business_code, open_code,
    eligible_stat_codes, rege_opt_in, rege_opt_out). period: YYYY-MM (kickoff). fee: the OD fee (pgl)."""
    return actions.ils_run(client, kind, codes, period or None, fee or None)


@mcp.tool
def ils_progress(client: str, kind: str) -> dict:
    """An ILS run's progress; when step 1 is done, the field summary the CSM confirms codes from."""
    return actions.ils_progress(client, kind)


@mcp.tool
def cashplease_report(client: str) -> dict:
    """One institution's CashPlease (small-dollar loans): volume, loans per 1,000 checking accounts, loan size,
    charge-off, overdue and paid-off rates, each against all CashPlease clients and the current cohort, plus
    the last six months. From the newest CashPleaseSummary export on the share."""
    return reports.cashplease_report(client)


@mcp.tool
def cashplease_portfolio() -> dict:
    """The whole CashPlease book: institutions live and cancelled, loans and dollars lent, charge-off, active
    loans, and who leads and trails on loans per 1,000 checking accounts."""
    return reports.cashplease_portfolio()


@mcp.tool
def peer_compare(client: str, kpis: str = "", period: str = "") -> dict:
    """How a client's ARS figures rank against every client whose deck was built the same cycle: value, rank,
    median and middle half. kpis: comma-separated from debit_take, debit_take_new, rege, rege_new, response,
    repeat, active_new, active_book, debit_on_checking, retention_1yr, retention_3yr (default: debit_take,
    rege, response, active_book, retention_1yr). period: YYYY.MM (default: the client's newest)."""
    return reports.peer_compare(client, kpis, period)


@mcp.tool
def one_pager(client: str) -> dict:
    """One page on a client: programs and products, ARS results to date, up to three figures worth saying
    (each beats the client's prior cycle or the peer median), CashPlease, and this cycle's deck."""
    return reports.one_pager(client)


@mcp.tool
def client_brief(client: str) -> dict:
    """Everything Sheila knows about a client for a call: the one-pager, this cycle's inputs, ICS/MRPC, the TI
    deck, open data issues and ILS. Notes, tasks, calendar and mail come from the CSM's own Microsoft 365."""
    return reports.client_brief(client)


@mcp.tool
def client_prepare(client: str) -> dict:
    """Meeting prep: the client brief, then what to fix before the call (unbuilt deck, a failed
    build, missing inputs) and what to raise (the figures worth saying)."""
    return reports.client_prepare(client)


@mcp.tool
def whats_new(n: int = 5) -> dict:
    """Sheila's newest changes, from her change log."""
    return core.whats_new(n)


@mcp.prompt("my-month", "Where my book stands this cycle, and what to do next")
def p_month() -> str:
    return "Sheila, where am I this month? Group my clients and tell me what to do next."


@mcp.prompt("build-a-client", "Check a client and build its deck")
def p_build(client: str) -> str:
    return (f"Sheila, check {client} and tell me what its deck would include. If it's ready, build it and "
            "keep me posted.")


@mcp.prompt("review-a-deck", "What's in a client's deck and what needs review")
def p_review(client: str, kind: str = "ars") -> str:
    return f"Sheila, summarize {client}'s {kind} deck and list what needs my review, slide by slide."


@mcp.prompt("run-an-ils-analysis", "Pre-go-live or kickoff, field summary first")
def p_ils(client: str, kind: str = "pgl") -> str:
    return (f"Sheila, start the ILS {kind} for {client}. Show me the field summary and wait for me to "
            "confirm the codes.")


def _warm():
    """Read the client list and check every client once, behind the first question, as the page does."""
    try:
        core.web().prewarm()
    except (Exception, SystemExit):         # noqa: BLE001 — warming is a convenience
        pass


def main():
    if not os.environ.get("RPE_DATA_ROOT"):
        print("sheila: RPE_DATA_ROOT is not set; using the default share root.", file=sys.stderr)
    threading.Thread(target=_warm, daemon=True).start()
    mcp.run()


if __name__ == "__main__":
    main()
