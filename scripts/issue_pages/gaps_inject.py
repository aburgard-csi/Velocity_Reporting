"""The CSM Data Gaps page: gaps.json, filtered to the Velocity product listing, injected into the template.

    python scripts/issue_pages/gaps_inject.py
"""
import collections
import json

from common import GAPS_PAGE, TEMPLATE, work_dir  # noqa: E402
import build_month as BM  # noqa: E402

S = work_dir()
d = json.load(open(S / "gaps.json", encoding="utf-8"))

# Only clients on the Velocity product listing (Aaron, 2026-09-15: "any client that wasn't on the
# product listing should be removed from the tracking pages and email").
_CP = S / "clients_products.json"
if _CP.exists():
    _prods = json.load(open(_CP, encoding="utf-8"))["clients"]
    LISTED = set(_prods)
    _removed = sorted({c["id"] for c in d["clients"]} - LISTED)
    d["clients"] = [c for c in d["clients"] if c["id"] in LISTED]
    d["issues"] = [i for i in d["issues"] if i["id"] in LISTED]
    d["former"] = [f for f in d["former"] if f["id"] in LISTED]
    # ARS findings only for clients the listing shows with ARS (Aaron, 2026-09-15: ARS workbooks only for ARS clients).
    _before = len(d["issues"])
    d["issues"] = [i for i in d["issues"] if not (i["program"] == "ARS" and "ARS" not in _prods.get(i["id"], {}).get("products", []))]
    print("ARS findings dropped for non-ARS clients:", _before - len(d["issues"]))
    s0 = d["summary"]
    s0["current_clients"] = len(d["clients"])
    s0["by_csm"] = dict(collections.Counter(c["csm"] for c in d["clients"]))
    print("removed (not on the product listing):", _removed)
else:
    LISTED = None

# Found while building the CashPlease trial decks (2026-09-14).
d["name_mismatches"] = [
    {"id": "1526", "a": "Clark County Credit Union (CashPlease workbook)", "b": "Create CU (DCO and ARS workbook)"},
    {"id": "1652", "a": "Security Rewards (CashPlease workbook)", "b": "Security CU (DCO and MRPCPM analysis)"},
    {"id": "1806", "a": "Streator Onized CU (CashPlease workbook)", "b": "SOCU (client-reports share)"},
    {"id": "1585", "a": "First Community Bank of Tenn (CashPlease workbook)", "b": "Heartland (client-reports share)"},
]
if LISTED is not None:
    d["name_mismatches"] = [m for m in d["name_mismatches"] if m["id"] in LISTED]

s = d["summary"]
inp, vip = s["inputs"], s["vip_sheets"]
roster_n = s.get("roster_clients") or len(BM.read_roster()[0])
cp_clients = sum(1 for c in d["clients"] if c["cp_tab"] or "CP" in c["programs"])
mrpc_clients = sum(1 for c in d["clients"] if c["mrpc_analysis"] or "MRPC" in c["programs"])
noprog = sum(1 for i in d["issues"] if "no program inputs" in i["issue"])
d["unknowns"] = [
    {"title": "Which other CSMs' clients are on ICS",
     "body": f"Only {inp.get('ICS workbook', 0)} ICS workbooks and {vip.get('ICS', 0)} VIP ICS sheets are on hand, all for Aaron's clients. "
             f"The {inp.get('ICS charts', 0)} ICS Charts workbooks are named by client name, not id, so they cannot say who is live on ICS.",
     "next": "A client list from Matt Milliman or the VIP ICS Referral dashboard for all five CSMs."},
    {"title": "MRPC beyond the VIP pull",
     "body": f"{inp.get('MRPCPM', 0)} MRPCPM analyses but {vip.get('MRPC', 0)} VIP MRPC sheets, so {mrpc_clients} MRPC clients have analysis data "
             "and most of them no dashboard sheet to build from.",
     "next": "Pull every MRPC client's sheet from the VIP MyRewards dashboard, not only Aaron's."},
    {"title": "CashPlease program settings",
     "body": f"{inp.get('CP settings', 0)} settings record(s) on hand for {cp_clients} CashPlease clients, so the Program Settings slide is missing for the rest.",
     "next": "Export each client's record from the Velocity Product Settings Power BI app."},
    {"title": "What the other clients are on",
     "body": f"{noprog} clients have a current ODD extract and nothing else: no workbook, analysis, CashPlease tab or VIP sheet. "
             "An ODD extract alone does not say which program it was pulled for.",
     "next": "Confirm each one's programs with its CSM before asking the data team for workbooks."},
    {"title": "Malformed rows at the source",
     "body": "1147 Sutton's extract has 3 rows with an extra field (an unquoted comma). The pipeline now counts and flags them, but the extract itself is wrong.",
     "next": "Data team: quote text fields in the ODD export."},
]
d["sources"] = [
    {"input": "ODD extract", "source": "Data team → each CSM's OD Data Dumps folder", "have": f"{inp.get('ODDD', 0)}", "use": "ARS decks, client overview"},
    {"input": "DCO", "source": "Client-reports share", "have": f"{inp.get('DCO', 0)}", "use": "ARS eligible accounts"},
    {"input": "ARS workbook", "source": "Client-reports share", "have": f"{inp.get('Workbook', 0)}", "use": "ARS financials, Lift Matrix, Key Trends"},
    {"input": "MRPCPM analysis", "source": "Client-reports share", "have": f"{inp.get('MRPCPM', 0)}", "use": "MRPC enrollments, revenue"},
    {"input": "VIP MRPC sheet", "source": "VIP MyRewards dashboard (pulled by hand)", "have": f"{vip.get('MRPC', 0)}", "use": "MRPC deck"},
    {"input": "VIP ICS sheet", "source": "VIP ICS Referral dashboard (pulled by hand)", "have": f"{vip.get('ICS', 0)}", "use": "ICS referrals, trend, branches"},
    {"input": "ICS workbook", "source": "Matt Milliman, by email, quarterly", "have": f"{inp.get('ICS workbook', 0)}", "use": "ICS financial sections"},
    {"input": "ICS Charts", "source": "Mystery shop workbooks", "have": f"{inp.get('ICS charts', 0)}", "use": "ICS mystery shop slide"},
    {"input": "CashPlease Summary", "source": "Bradford Sanders, by email, weekly", "have": f"{s['cp_tabs_total']} client tabs", "use": "CashPlease decks"},
    {"input": "CashPlease settings", "source": "Velocity Product Settings Power BI app", "have": f"{inp.get('CP settings', 0)}", "use": "Program Settings slide"},
    {"input": "DDA count", "source": "ILS Management Server DDA Count email", "have": "weekly text file", "use": "Loans per 1,000 DDAs"},
    {"input": "Client CSM List", "source": "Built from the share folders", "have": f"{s['current_clients']} current", "use": "Filing Outputs by CSM"},
    {"input": "clients.md roster", "source": "Aaron", "have": f"{roster_n} clients", "use": "What gets delivered"},
]

page = TEMPLATE.read_text(encoding="utf-8")
page = page.replace("/*__DATA__*/null", json.dumps(d, ensure_ascii=False).replace("</", "<\\/"))
(S / GAPS_PAGE).write_text(page, encoding="utf-8")
print(f"{GAPS_PAGE}: {len(d['issues'])} issues, {len(page):,} bytes")
