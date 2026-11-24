"""Build docs/financial-services.html, the Financial Services manual.

The page is generated, in the way v5's operating manual was: the categories, the slide list, the list
columns and the figures it names are read out of the code every time it is built, and the build stops
if a figure the page documents is no longer computed. Never hand-edit the HTML; change this file and
run it again.

    python scripts/build_financial_services_guide.py [out.html]

The look is the v5 manual's (docs/guide-style.css, docs/guide-nav.js, copied unchanged).
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in ("build", "build/ars_pipeline"):
    sys.path.insert(0, str(REPO / p))

import pandas as pd  # noqa: E402

from ti import chapters_txn as X  # noqa: E402
from ti import ledger  # noqa: E402
from ti.transaction_intelligence import financial_services as F  # noqa: E402
from ti.transaction_intelligence import institution_view as IV  # noqa: E402
from ti.transaction_intelligence.lens import Lenses  # noqa: E402

E = html.escape
DICT = REPO / "build" / "ars_pipeline" / "ti" / "dictionaries"

# The figures this page documents, and what each one answers. The build checks every key against a
# real run of compute() on a small frame, so a figure that is renamed or dropped stops the build.
FIGURES = [
    ("Headline", [
        ("fin_leaking_pct", "Share of the base paying any outside financial product (any leakage)."),
        ("fin_leakage_dollars", "Dollars a year to those products, adjacency excluded."),
        ("fin_addressable_pct", "Share of the base paying a category the institution offers."),
        ("fin_addressable_dollars", "Dollars in those categories."),
        ("fin_definitions", "Any, addressable and adjacency side by side: accounts, % of the base, dollars, with the base printed."),
        ("fin_coverage", "Matched rows and dollars, card and transfer rows, whether wallet share can be computed, review-queue dollars."),
    ]),
    ("Who and what", [
        ("fin_by_category", "Per category: accounts, transactions, dollars, dollars per account, median wallet share, card share."),
        ("fin_top_providers", "The named providers in each category, by dollars; generic descriptors show as (unnamed)."),
        ("fin_provider_concentration", "How much of a category the top three providers take."),
        ("fin_by_lens", "Addressable accounts by program group (responders, mailed non-responders, no mail, ICS groups)."),
    ]),
    ("Over time", [
        ("fin_recency", "Per category, relationships active, cooling, dormant and lapsed."),
        ("fin_new_recurring_stopped", "Started, continuing and stopped in the last 90 days."),
        ("fin_months", "The months in the window."),
        ("fin_monthly", "Per category and month: accounts paying and dollars. A month with no payments reads zero."),
        ("fin_mail_months", "The months a mailing dropped, from the ODD's Mail columns, so the series can mark them. Months outside the window are left out."),
        ("fin_trend", "Last three months against the three before, per category; peak month from twelve months on file."),
    ]),
    ("Depth", [
        ("fin_multi_category", "How many categories each leaker pays."),
        ("fin_category_pairs", "Which categories leave together."),
        ("fin_reach", "How much of each addressable category was paid in the last 90 days."),
        ("fin_leakers_profile", "Balance, tenure and response of the accounts paying each addressable category."),
        ("fin_leakers_hold", "The top products those accounts hold with us."),
    ]),
    ("Named institutions", [
        ("fininst_by_category", "Per category: how many accounts, and how many dollars, sit at a named bank or credit union."),
        ("fininst_matrix", "The largest category by institution pairs, each with its tier."),
        ("fininst_source", "Which match named the institution: the registry (Competition layers ran) or the configured names."),
    ]),
    ("Data quality", [
        ("fin_unmatched_top", "The biggest counterparties on the transfer rail that matched nothing."),
        ("fin_review_queue", "Descriptors that look financial and matched nothing, by dollars (top rows; the whole queue is a file)."),
    ]),
]

FINSERV_BUILDER_NAMES = {
    "the_book_narrowed", "twelve_months", "their_financial_life", "_where_the_money_goes",
    "where_the_leakage_goes", "who_they_pay", "how_long_it_has_run", "started_and_stopped", "how_deep",
    "leakage_by_group", "leakage_by_group_and_category", "what_leakers_hold", "how_the_leakage_builds",
    "which_services_travel_together", "still_within_reach", "dictionary_gaps",
}


# ------------------------------------------------------------------ read from the code
def smoke_figures() -> dict:
    """compute() on a small frame, to prove every documented figure is still produced."""
    rows = []
    for m in pd.period_range(end="2026-10", periods=12, freq="M"):
        for a in range(25):
            rows.append((f"b{a}", "AFFIRM INC", "SIG", 40.0, m.to_timestamp() + pd.Timedelta(days=9)))
        rows.append(("b0", "STATE FARM INS", "SIG", 90.0, m.to_timestamp() + pd.Timedelta(days=3)))
        rows.append(("b1", "NUSENDA CU AUTO LOAN", "SIG", 300.0, m.to_timestamp() + pd.Timedelta(days=5)))
        rows.append(("b2", "ZZZ FINANCIAL REVIEW ME", "SIG", 20.0, m.to_timestamp() + pd.Timedelta(days=5)))
    df = pd.DataFrame(rows, columns=["primary_account_num", "merchant_name", "transaction_type",
                                     "amount", "transaction_date"])
    df["merchant_key"] = df["merchant_name"]
    attrs = pd.DataFrame({"Mailable?": "Yes", "Prod Desc": "Basic Checking"},
                         index=[f"b{a}" for a in range(25)])
    lenses = Lenses(key_column="Acct Number", accounts=attrs.index, masks={}, attrs=attrs)
    client = {"LocalCompetitors": {"Nusenda Credit Union": ["NUSENDA CU", "NUSENDA CREDIT UNION"]}}
    spec = F.load_patterns(DICT, client)
    cls = F.classify_rows(df, spec)
    out, _ = F.compute(df, lenses, spec, pd.Timestamp("2026-10-31"), None, lambda m: None,
                       base_label="transacting personal accounts", classification=cls,
                       mail_months=["2026-03", "2026-10"])
    from ti.transaction_intelligence import competition as C
    out.update(IV.compute(df, cls, C.load_config(DICT, client)))
    return out


def check_figures(out: dict) -> None:
    missing = [k for _g, items in FIGURES for k, _d in items if k not in out]
    if missing:
        raise SystemExit("the guide documents figures compute() no longer produces: " + ", ".join(missing)
                         + "\nUpdate FIGURES in scripts/build_financial_services_guide.py.")


def commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def categories() -> list[dict]:
    spec = json.loads((DICT / "financial_services_patterns.json").read_text(encoding="utf-8"))
    return [{"name": n, "kind": c.get("kind", "leakage"), "addressable": bool(c.get("addressable")),
             "patterns": len(c.get("patterns", []))} for n, c in spec["categories"].items()], spec


def finserv_slides() -> list[list[str]]:
    by_title = {r[1]: r for r in ledger.rows()}
    out = []
    for b in X.TI_BUILDERS:
        if b.__name__ in FINSERV_BUILDER_NAMES:
            out.append(by_title[X.TITLES[b.__name__]])
    return out


# ------------------------------------------------------------------ html helpers
def table(head, rows, cls=""):
    th = "".join(f"<th>{E(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table{cls}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def code(s):
    return f"<code>{E(s)}</code>"


def block(kind, label, body):
    return f'<div class="{kind}"><span class="blab">{E(label)}</span>{body}</div>'


def section(sid, eyebrow, title, body):
    return f'<section id="{sid}"><span class="eyebrow">{E(eyebrow)}</span><h2>{E(title)}</h2>{body}</section>'


# ------------------------------------------------------------------ the page
def build() -> str:
    out = smoke_figures()
    check_figures(out)
    cats, spec = categories()
    slides = finserv_slides()
    n_leak = sum(c["kind"] == "leakage" for c in cats)
    n_adj = sum(c["kind"] == "adjacency" for c in cats)
    n_addr = sum(c["addressable"] for c in cats)
    n_pat = sum(c["patterns"] for c in cats)
    states = {}
    for r in slides:
        states[r[2]] = states.get(r[2], 0) + 1

    S = []   # (id, group, short title, html)

    S.append(("what-this-is", "Start here", "What this is, and what you do", f"""
<p>Financial Services is the part of the Transaction Intelligence deck that answers one question:
<strong>where do our members and customers send money that is not to us?</strong> It reads the
debit-card transaction files, finds the payments that go to someone else's financial product (an
auto loan, a credit card, insurance, a buy-now-pay-later plan) and tells you how many accounts, how
many dollars, how recent, and who they pay.</p>
<p>It is not the same as Competition. <strong>Competition is banks and credit unions</strong> (who holds the
relationship). <strong>Financial Services is the product</strong> (what they are buying). The same payment can
appear in both, and the two views are never added together; see <a href="#competition">How it relates to Competition</a>.</p>
{block("callout", "What you do with it", f'''<p>You read the numbers (<a href="#numbers">Read the numbers</a>), open the mail
lists (<a href="#lists">The lists and the master list</a>) and give the client's marketing team the master list. If a client's
numbers look thin, the <a href="#coverage">coverage line</a> says how much the dictionary could see, and
<a href="#fixing">the review queue</a> says what to add.</p>''')}
<p>Everything on this page is read out of the code when it is built, so it cannot describe a figure the
pipeline no longer computes. If a number here looks wrong, the code moved: rebuild the page.</p>"""))

    S.append(("numbers", "Start here", "Read the numbers", f"""
<p>Three words are used on every slide and in every list. Learn them once.</p>
{table(["Word", "Means", "Use it for"], [
    ["<strong>Any leakage</strong>", "The account paid at least one outside financial product, in any of the "
     f"{n_leak} leakage categories.", "The headline: how many members or customers have a financial life elsewhere."],
    ["<strong>Addressable</strong>", f"The account paid one of the {n_addr} categories the institution offers "
     "(auto loans, mortgage, cards, personal loans, student loans, and others; not insurance or tax).",
     "What the institution could realistically win back."],
    ["<strong>Adjacency</strong>", f"{n_adj} categories: person-to-person payments and fintech wallets. Reported apart, "
     "never added to leakage.", "Context, not a leak: a Venmo payment may be rent."],
])}
{block("stop", "Two percentages, one client", '''<p>On 1798 the headline reads 42% (any leakage) and the by-lens table reads 18% (addressable). Both are
right; they answer different questions. Every figure in the pack now carries both, with the base printed
(<code>fin_definitions</code>), so quote them together.</p>''')}
<h3>Every figure is a floor</h3>
<p>The files are <strong>debit-card rows</strong>. Payments made by ACH, check or a bill-pay service are not in them, so every
account and dollar figure is the least that is true. The slides say &ldquo;card rails only&rdquo; for this reason.
Wallet share (the category's share of an account's ACH and check dollars) needs those rails and is blank on a card-only file;
the coverage line says so.</p>
<h3>Dollars are payments, not balances</h3>
<p>A $50M figure is money that moved in twelve months. It is not a loan book and carries no rate or margin. No revenue-at-stake
estimate is made, by decision.</p>"""))

    S.append(("needs", "Get running", "What it needs", """
<p>Nothing beyond what a Transaction Intelligence build already reads:</p>
<ul>
<li><strong>The ODD extract</strong> for the month (the account list, branch, product, <code>Mailable?</code>, business or personal).</li>
<li><strong>The monthly debit-card transaction files</strong> for the client (<code>Inputs\\Txn Files\\&lt;id&gt;</code>). Twelve months is the
full picture; a single month works but has no trend.</li>
<li><strong>The client's config</strong> (<code>ti_clients_config.json</code>): <code>SelfNames</code> (the client's own names, so internal transfers are never leakage) and,
if the client has providers the dictionary lacks, <code>LocalFinancialServices</code>.</li>
</ul>
<p>A client with no transaction files has no Financial Services chapter, and the build says so instead of drawing empty slides.</p>"""))

    S.append(("run", "Get running", "How to run it", """
<p>From CSM Sheila, open the client and use the <strong>Transaction Intelligence</strong> panel. There is nothing separate to run for Financial Services:
it is a chapter of that build.</p>
<p>By hand, for one client (the Sheila button runs this):</p>
<pre><code>python build\\ars_pipeline\\ti_build.py &lt;id&gt; &lt;period&gt; "&lt;client name&gt;" &lt;out dir&gt;    (add --ics for an ICS client)</code></pre>
<p>The build prints a read-out near the end: the three definitions, the coverage line, and the slide ledger summary. Read it before you open the deck.</p>"""))

    S.append(("comes-out", "Get running", "What comes out", f"""
<p>A build writes three kinds of thing. The deck goes to Outputs as before; the lists and the ledger now go beside it.</p>
<div class="tree">Outputs\\&lt;CSM&gt;\\
  &lt;id&gt;-&lt;period&gt;-TI-&lt;client&gt; Transaction Intelligence.pptx      the deck (one per lens)
  &lt;id&gt;-&lt;period&gt;-TI-Lists\\
     finserv_master_list.csv                                  <strong>the one to hand over</strong>
     finserv_&lt;category&gt;.csv                                   one per category ({len(cats)})
     finserv_review_queue.csv                                 what the dictionary missed
     ti_slide_ledger.csv                                      every slide: drawn, merged, hidden, tossed</div>
{table(["File", "Who uses it", "What it is"], [
    [code("finserv_master_list.csv"), "Client marketing", "One row per account per category. Filter on <code>list_type</code> to mail one category."],
    [code("finserv_<category>.csv"), "CSM, client marketing", "The same accounts for one category, with balance, tenure and the ODD columns beside them."],
    [code("finserv_review_queue.csv"), "CSM, the dictionary owner", "Every descriptor that looks financial and matched nothing, by dollars."],
    [code("ti_slide_ledger.csv"), "Whoever reviews the deck", "A line for every slide with its status and the reason it is not drawn."],
])}
{block("note", "The staging folder", '''<p>The build writes into a staging folder first. Only the validated deck used to be copied to Outputs; the
<code>-TI-Lists</code> folder is copied after it. If a CSM cannot find the lists, the build log says whether the copy failed.</p>''')}"""))

    master_cols = ", ".join(F.MASTER_COLUMNS)
    S.append(("lists", "Use it", "The lists and the master list", f"""
<p>Every category gets a list, and there is one master list across all of them, so a campaign is a filter, not a rebuild.</p>
{table(["Column", "What it is"], [
    [code("acct_id"), "The account, as the ODD and the transaction file key it (a long hashed id, not an account number)."],
    [code("cif"), "The member's customer information file number. <strong>Blank today</strong>: no client file carries one. It fills when a crosswalk is supplied; nothing else changes."],
    [code("list_type"), "The category, which is the campaign or list type (Auto Loans, Credit Cards, &hellip;)."],
    [code("kind"), "<code>leakage</code> or <code>adjacency</code>."],
    [code("addressable"), "<code>yes</code> if the institution offers this category."],
    [code("tier"), "How recently the account last paid: <code>active</code> (30 days), <code>cooling</code> (90), <code>dormant</code> (a year), <code>lapsed</code>."],
    [code("txns"), "How many payments in the window."],
    [code("dollars"), "How much, in the window."],
    [code("wallet_share"), "That category's share of the account's ACH and check dollars; blank without the transfer rail."],
    [code("last"), "The date of the last payment."],
    [code("mailable"), "The ODD's <code>Mailable?</code> flag, or <code>unknown</code> for an account the ODD does not list."],
])}
<p>The master list's columns, in order: {code(master_cols)}.</p>
<h3>How to use it</h3>
<ol class="steps">
<li><p><strong>Open the master list</strong> and filter <code>mailable</code> to <code>Yes</code>. An account marked <code>unknown</code> is not in this month's ODD: leave it out.</p></li>
<li><p><strong>Pick the campaign</strong> by <code>list_type</code> and <code>addressable</code>. Start with <code>cooling</code>: those accounts paid in the last 31 to 90 days and are the cheapest to keep.</p></li>
<li><p><strong>Add the CIF</strong> from the institution's own system when marketing needs it; the file carries the account id only.</p></li>
</ol>
{block("stop", "Business accounts", '''<p>The lists cover the <strong>personal-account</strong> base, the same accounts the headline counts. Business accounts are not in them.</p>''')}
{block("note", "Mailing is not Competition", '''<p>These lists are financial-services lists only. Competition keeps its own files, and competition-based mail targeting is not part of this work.</p>''')}"""))

    cat_rows = [[E(c["name"]), c["kind"], "yes" if c["addressable"] else "no", f'{c["patterns"]:,}'] for c in cats]
    S.append(("categories", "Use it", "The categories", f"""
<p>{len(cats)} categories ({n_leak} leakage, {n_adj} adjacency), {n_pat:,} name patterns. Read from the dictionary
(<code>financial_services_patterns.json</code>), so this is the list in force.</p>
{table(["Category", "Kind", "Addressable", "Patterns"], cat_rows)}
<p>A payment is matched on its description. Longest match wins, a descriptor that names a product but no lender
(<code>AUTO LOAN</code>, <code>CARD PAYMENT</code>, <code>LOAN PMT</code>, {len(spec.get("generic_descriptors", []))} in all) keeps its category and
shows as <code>(unnamed)</code> instead of as a provider, and a pattern lives in exactly one category.</p>"""))

    S.append(("deck", "Use it", "Its deck, slide by slide", f"""
<p>The Financial Services slides inside the Transaction Intelligence deck, and what became of each in a build.
{states.get('drawn', 0)} drawn, {states.get('merged', 0)} merged, {states.get('hidden', 0)} hidden, {states.get('tossed', 0)} tossed
(by the selection file, <code>ti/slides.json</code>). The ledger file lists every slide of the deck, not only these.</p>
{table(["Slide", "Status", "Why"], [[E(r[1]), f'<code>{r[2]}</code>', E(r[3])] for r in slides])}
{block("note", "Nothing is dropped silently", '''<p><strong>Tossed</strong> is a reviewed decision for every client. <strong>Hidden</strong> means this client's files
do not hold the figures. <strong>Merged</strong> means two slides share one page. The ledger file says which, for the client in front of you.</p>''')}"""))

    fig_html = ""
    for group, items in FIGURES:
        fig_html += f"<h3>{E(group)}</h3>" + table(["Figure", "What it answers"], [[code(k), E(d)] for k, d in items])
    S.append(("figures", "Reference", "The figures it computes", f"""
<p>Every figure below is checked against a real run when this page is built. They are keys in the pack
(<code>ti_pack.json</code>) and in the metrics the deck reads.</p>{fig_html}"""))

    S.append(("coverage", "Reference", "Coverage: how much the dictionary can see", """
<p>The dictionary matches names, so it can only count what it knows. Every build reports it, in the build log and in the pack
(<code>fin_coverage</code>):</p>
<ul>
<li><strong>Matched rows and dollars</strong> as a share of the file. Most card rows are ordinary shopping, so the row share is low by design; look at dollars.</li>
<li><strong>Review queue dollars</strong>: money that went to something financial-looking the dictionary did not recognise. This is the number to bring down.</li>
<li><strong>Wallet share available</strong>: <code>False</code> on a card-only file.</li>
</ul>
<p>On 1798's October 2026 file, the first run matched 15.9% of dollars and left $1.14M in the review queue; adding the names
from that queue moved 1,765 rows into categories.</p>"""))

    S.append(("competition", "Reference", "How it relates to Competition", """
<p>Competition counts <strong>who</strong>; Financial Services counts <strong>what</strong>. A payment to a named bank or credit union is in both:</p>
<div class="callout"><span class="blab">The rule</span><p><code>NUSENDA CU AUTO LOAN</code> is an <strong>auto loan</strong> here and <strong>Nusenda</strong> in Competition.
Each view counts it. The two are <strong>never added</strong>. Where the page or a slide shows both, it says the other view exists.</p></div>
<p><code>fininst_by_category</code> and <code>fininst_matrix</code> are the bridge: for each category, how much sits at a named bank or credit union,
and the largest pairs with their tier. They are cross-tabs of the two views, not a third total.</p>
<p>When the Competition layers run, the institution is named by the registry (every FDIC bank and NCUA credit union, matched on the card description,
with its tier: National, Digital, Local, Regional, State, Other, or a card-issuing bank). A name that fits several institutions is left unplaced, never
guessed. Without the layers (no reference store), the match falls back to the institutions Competition is configured with, and a depository in neither is
not found. <code>fininst_source</code> says which was used. Either way the share is a floor, because the files are card rows.</p>"""))

    S.append(("cannot", "Know the limits", "What it cannot do", """
<ul>
<li><strong>See payments off the card rail.</strong> ACH, checks and bill pay are not in the files. Every figure is a floor.</li>
<li><strong>Know a loan balance, rate or margin.</strong> It sees payments. It does not estimate revenue or opportunity.</li>
<li><strong>Name a lender that is not in the dictionary.</strong> It shows in the review queue until someone adds it.</li>
<li><strong>Tell you who an account is.</strong> No client file carries a name, address or CIF. The lists key on the account id.</li>
<li><strong>Prove a program effect.</strong> The responder-against-control gap is descriptive: responders are chosen by a dip in activity. Only a before-and-after comparison against a control is causal.</li>
<li><strong>Cover business accounts in the lists.</strong> The headline and the lists are personal accounts.</li>
</ul>"""))

    S.append(("fixing", "Know the limits", "When the numbers look wrong", """
<table><thead><tr><th>You see</th><th>It means</th><th>Do this</th></tr></thead><tbody>
<tr><td>No Financial Services slides</td><td>No transaction files for the period, or the chapter failed.</td><td>Read the build log for <code>failed:</code> or <code>not on hand</code>. The ledger lists the slides as <code>hidden</code> with the reason.</td></tr>
<tr><td>A provider shows as <code>(unnamed)</code></td><td>The descriptor names a product but no lender (<code>LOAN PMT</code>).</td><td>Normal. If it is a big dollar amount, look it up in the review queue.</td></tr>
<tr><td>A large review queue</td><td>Financial-looking counterparties the dictionary does not know.</td><td>Open <code>finserv_review_queue.csv</code>, take the top names, and add them (below).</td></tr>
<tr><td>A bank or credit union in the review queue</td><td>It is a Competition name, not a product.</td><td>Add it to the client's <code>LocalCompetitors</code> (Competition's config), not to this dictionary.</td></tr>
<tr><td>Wallet share is blank</td><td>The file has no ACH or check rows.</td><td>Expected for a card-only client.</td></tr>
<tr><td>A category list is empty</td><td>Nobody paid that category this month.</td><td>The file is still written, header only, so the set of files never changes.</td></tr>
</tbody></table>
<h3>Adding a name to the dictionary</h3>
<ol class="steps">
<li><p><strong>Read the review queue</strong> and pick names that are real lenders, insurers or wallets. Leave out look-alikes (a store called &ldquo;Sun Valley Hardware&rdquo; is not Sun Loans).</p></li>
<li><p><strong>One client only?</strong> Put the name under <code>LocalFinancialServices</code> in that client's config.
<strong>Every client?</strong> Add it to the category in <code>financial_services_patterns.json</code>, once. A pattern in two categories fails the tests.</p></li>
<li><p><strong>Change goes through a branch and pull request,</strong> with the before and after for a real client. A dictionary change moves figures, so it is its own PR.</p></li>
</ol>"""))

    S.append(("terms", "Reference", "Wording on slides and lists", """
<p>Credit union: say <strong>member</strong> (members, member accounts, members at GECU). Bank: say <strong>customer</strong>.
Text that covers both: &ldquo;members and customers&rdquo;, or the institution's own word per row. Never &ldquo;user&rdquo;, &ldquo;consumer&rdquo; or &ldquo;account holder&rdquo;.</p>"""))

    S.append(("status", "Reference", "What ships when", f"""
<p>This page describes the code at commit {code(commit())}. The Financial Services work lands as a stack of pull requests,
one purpose each, because a change to what a figure counts is reviewed on its own.</p>
{table(["Stage", "What it adds", "Moves a figure?"], [
    ["Dictionary v6", "One category per pattern, generic descriptors never the provider, bank and product patterns, payday category, known misses.", "Yes"],
    ["Mail lists", "Lists for every category, the master list, the build sets where they are written, <code>Mailable?</code> carried through.", "No"],
    ["Definitions and coverage", "Any, addressable and adjacency side by side; the coverage line; the whole review queue as a file.", "No"],
    ["Trend and depth", "A monthly series and trend per category; the products leakers hold.", "No"],
    ["Named institutions", "Each category against the bank or credit union that holds it, named by the registry when the Competition layers run.", "No"],
    ["Ledger and portfolio row", "A line for every slide; one row per client and month for benchmarking.", "No"],
    ["Dictionary v7", "Names read from 1798's review queue.", "Yes"],
    ["Delivery", "The lists and ledger copied to Outputs beside the deck (a launcher change).", "No"],
])}
{block("note", "Merged is not released", '''<p>These stages are merged to <code>main</code> (2026-11-17), but the build CSMs run comes from the release, which is Aaron's. Until he
releases, Sheila builds do not have them. Rebuild this page after each merge and the commit named above follows the code.</p>''')}"""))

    S.append(("glossary", "Reference", "Glossary", """
<dl>
<dt>Leakage</dt><dd>Money to someone else's financial product (loan, card, insurance, brokerage, BNPL, crypto, payday).</dd>
<dt>Addressable</dt><dd>A leakage category the institution offers.</dd>
<dt>Adjacency</dt><dd>Person-to-person and fintech wallet payments, reported apart.</dd>
<dt>Review queue</dt><dd>Financial-looking descriptors the dictionary did not match, by dollars.</dd>
<dt>Wallet share</dt><dd>A category's share of an account's ACH and check dollars; needs the transfer rail.</dd>
<dt>Coverage</dt><dd>How much of the file the dictionary can see.</dd>
<dt>CIF</dt><dd>The member or customer's customer information file number. Not in any file today.</dd>
<dt>Master list</dt><dd>One row per account per category; the single hand-off to marketing.</dd>
<dt>Ledger</dt><dd>A line for every slide with its status and reason.</dd>
<dt>ODD</dt><dd>The monthly account-level extract.</dd>
<dt>Lens</dt><dd>A program group: for ARS, responders, mailed non-responders and no mail; for ICS, ICS accounts and their sources.</dd>
</dl>"""))

    jobs = [("what-this-is", "I am new here"), ("numbers", "Read a client's numbers"), ("lists", "Get the mail list"),
            ("coverage", "Check the numbers can be trusted"), ("fixing", "Fix a missing provider"),
            ("competition", "Tell Financial Services from Competition"), ("cannot", "Know what it cannot say")]
    jobs_html = "".join(f'<li><a href="#{i}">{E(t)}</a></li>' for i, t in jobs)
    rail, last = "", None
    for sid, grp, title, _h in S:
        if grp != last:
            rail += f'<span class="grp">{E(grp)}</span>'
            last = grp
        rail += f'<a href="#{sid}">{E(title)}</a>'
    secs = "".join(section(sid, f"{grp} &middot; {i + 1:02d}".replace("&middot;", "·"), title, body)
                   for i, (sid, grp, title, body) in enumerate(S))
    css = (REPO / "docs" / "guide-style.css").read_text(encoding="utf-8")
    js = (REPO / "docs" / "guide-nav.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Financial Services Guide</title>
<style>
{css}</style>
</head><body>
<div class="wrap">
<header class="top">
  <h1>Financial Services Guide</h1>
  <p class="sub">Where members' and customers' money goes outside the institution: what the analysis computes,
  how to read it, the mail lists it produces, and what it cannot say. {len(S)} sections; use the contents on the left,
  or Ctrl+F &mdash; every word is on this page.</p>
  <p class="built">Generated by <code>scripts/build_financial_services_guide.py</code> on {date.today().isoformat()}
  from commit {E(commit())}. Never hand-edited: change the script and run it again.</p>
</header>
<div class="jobs"><h2>I need to&hellip;</h2><ul>{jobs_html}</ul></div>
<nav class="rail">{rail}</nav>
<main>{secs}</main>
<footer>
  <p>A guide that promises the wrong thing is worse than no guide. The categories, slides, list columns and figures named
  here are read from the code when this page is built, and the build stops if one is no longer there.</p>
</footer>
</div>
<script>
{js}</script>
</body></html>
"""


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dest = Path(argv[0]) if argv else REPO / "docs" / "financial-services.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(build(), encoding="utf-8")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
