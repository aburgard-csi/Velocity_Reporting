"""Per-client products, location and profile from the Velocity client/product export -> clients_products.json.

    python scripts/issue_pages/clients_products.py "<path to Velocity Clients and Products export.csv>"

Run when a new export arrives (the first was "Velocity Clients and Products 9-15-26.csv"). Both issue pages
drop clients the export does not list, and the ODD page drops clients it lists without ARS. Also prints
checks: Relationship Manager vs the Client CSM List CSM, RPE products vs clients.md programs, and the
Missing Workbook clients' products.
"""
import collections, csv, json, re, sys
from pathlib import Path

from common import R, work_dir  # noqa: E402
import build_month as BM  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
SRC = Path(sys.argv[1])
S = work_dir()
rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", errors="replace")))
cols = list(rows[0].keys())


def col(name):
    hit = next((c for c in cols if c.strip().lower().startswith(name.lower())), None)
    if hit is None:
        sys.exit(f"no column starting {name!r}; columns: {[c.strip()[:40] for c in cols]}")
    return hit


C = {k: col(v) for k, v in dict(id="Prospect/Customer #", rev="Last 12 Months", prod="Product", sold="Sold Date",
                                 impl="Implementation Date", name="Company Profile Link", rm="Relationship Manager",
                                 dir="Director of Relationship", status="Status", dda="# of DDA", city="Mailing Address City",
                                 state="Mailing Address State", assets="Assets", type="Financial Institution Type").items()}


# Product families. ARS "with Account Engagement" is still ARS; Account Engagement is recorded alongside.
def families(p):
    p = p.strip()
    out = []
    if p.startswith("Account Revenue Solution (ARS)"):
        out.append("ARS")
        if "Account Engagement" in p:
            out.append("Account Engagement")
        if "Credit Card Rewards" in p:
            out.append("ARS Credit Card Rewards")
    elif p.startswith("Invitation Checking System (ICS)"):
        out.append("ICS")
        if "Account Engagement" in p:
            out.append("Account Engagement")
    elif p.startswith("My Rewards Premium Cards"):
        out.append("MRPC")
    elif p.startswith("CashPlease"):
        out.append("CashPlease")
    elif p.startswith("Intelligent Limit System (ILS):"):
        out.append("ILS " + p.split(":", 1)[1].strip())
    elif p.startswith("Intelligent Limit System (ILS)"):
        out.append("ILS")
    elif p.startswith("Reg. E Management"):
        out.append("Reg E Management")
    elif p.startswith("IMPACT: ODM Guardian"):
        out.append("ODM Guardian")
    elif p == "Professional Services - Velocity":
        out.append("Professional Services")
    else:
        out.append(p)
    return out


def person(v):
    v = v.strip()
    return " ".join(reversed([x.strip() for x in v.split(",", 1)])) if "," in v else v


by = collections.defaultdict(list)
for r in rows:
    by[r[C["id"]].strip()].append(r)

clients = {}
for cid, rs in by.items():
    r0 = rs[0]
    name = re.sub(r"\s*\([^()]*\)\s*$", "", r0[C["name"]].strip())
    prods, detail = [], []
    for r in rs:
        prods += families(r[C["prod"]])
        detail.append({"product": r[C["prod"]].strip(), "sold": r[C["sold"]].strip(), "implemented": r[C["impl"]].strip(),
                       "cloud": r[C["prod"]].strip().endswith("- Cloud")})
    order = ["ARS", "ICS", "MRPC", "CashPlease", "Account Engagement", "ARS Credit Card Rewards", "ILS", "Reg E Management",
             "ODM Guardian", "Professional Services"]
    uniq = sorted(set(prods), key=lambda p: (order.index(p) if p in order else 99, p))
    clients[cid] = {"id": cid, "name": name, "relationship_manager": person(r0[C["rm"]]),
                    "director": person(r0[C["dir"]]), "status": r0[C["status"]].strip(),
                    "city": r0[C["city"]].strip(), "state": r0[C["state"]].strip(),
                    "fi_type": r0[C["type"]].strip(), "assets_millions": r0[C["assets"]].strip(),
                    "dda_accounts": r0[C["dda"]].strip(), "recurring_revenue_12m": r0[C["rev"]].strip(),
                    "products": uniq, "rpe_programs": [p for p in ("ARS", "ICS", "MRPC", "CashPlease") if p in uniq],
                    "product_detail": detail}
json.dump({"source": SRC.name, "clients": clients}, open(S / "clients_products.json", "w", encoding="utf-8"), indent=1)
print("clients:", len(clients), "| statuses:", collections.Counter(c["status"] for c in clients.values()))

cur = {r["client_id"]: r for r in csv.DictReader(open(R.data_root() / R.CSM_LIST_NAME, encoding="utf-8-sig"))}
current = {k for k, v in cur.items() if not v["notes"].startswith("ODD only in older months")}
dis = [(cid, cur[cid]["csm"], clients[cid]["relationship_manager"]) for cid in sorted(current & set(clients))
       if cur[cid]["csm"] != clients[cid]["relationship_manager"]]
print("\nCSM (list) vs Relationship Manager (export) disagreements:", dis)
print("current clients not in export:", sorted(current - set(clients)))

roster, stopped = BM.read_roster()
cp = {r["client_id"]: r for r in BM.read_cashplease_roster() if r["build"]}
PMAP = {"ARS": "ARS", "ICS": "ICS", "ICS-REFERRALS": "ICS", "MRPC": "MRPC"}
print("\nclients.md vs export RPE programs:")
for cid, name, mmsm, progs in roster:
    have = set(PMAP.get(p, p) for p in progs) | ({"CashPlease"} if cid in cp else set())
    exp = set(clients.get(cid, {}).get("rpe_programs", []))
    if cid not in clients:
        print(f"  {cid} {name}: NOT in export (clients.md: {sorted(have)})")
    elif have != exp:
        print(f"  {cid} {name}: clients.md {sorted(have)} | export {sorted(exp)}")
for cid, name, why in stopped:
    if cid in clients:
        print(f"  stopped {cid} {name} ({why}) still in export with {clients[cid]['rpe_programs']}")

gp = S / "gaps.json"
if gp.exists():
    gaps = json.load(open(gp, encoding="utf-8"))
    nowb = sorted({i["id"] for i in gaps["issues"] if "no program inputs" in i["issue"]})
    print("\nMissing Workbook clients - products in export:")
    for cid in nowb:
        c = clients.get(cid)
        print(f"  {cid} {c['name'] if c else '?'}: {', '.join(c['products']) if c else 'NOT in export'}")
