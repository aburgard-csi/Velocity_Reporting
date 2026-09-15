"""ODD and ARS workbook issues only, grouped by CSM -> 'ODD and Workbook Issues.html'.

    python scripts/issue_pages/odd_wb_by_csm.py

Reads gaps.json, business_flags.json, mail_flags.json, noprog_odd_dates.json, missing_wb_history.json and
clients_products.json from Build Artifacts/issue_pages/, the period's all-client trial run, and each ARS
workbook's Lift Matrix window. Writes the page beside them. Only clients the Velocity export lists with
ARS appear; every row carries the client's id and name.
"""
import collections, csv, datetime, html, json, os, re
from collections import OrderedDict, defaultdict
from pathlib import Path

from common import ODD_PAGE, R, TEMPLATE, trial_dir, work_dir  # noqa: E402
import build_month as BM          # noqa: E402
import deck_status as DS          # noqa: E402
from lift_window import workbook_window   # noqa: E402
from perf_actions import lift_matrix_flag  # noqa: E402

S = work_dir()
d = json.load(open(S / "gaps.json", encoding="utf-8"))
C = {c["id"]: c for c in d["clients"]}
LIST = {r["client_id"]: r for r in csv.DictReader(open(R.data_root() / R.CSM_LIST_NAME, encoding="utf-8-sig"))}
PERIOD = d["summary"]["period"]
MONTH_NAME = datetime.datetime.strptime(PERIOD, "%Y.%m").strftime("%B")
_trial_p = trial_dir(PERIOD) / "_trial_results.json"
TRIAL = json.load(open(_trial_p, encoding="utf-8")) if _trial_p.exists() else {}
esc = html.escape
# Exact generation time, shown after the period (Aaron, 2026-09-15). Local time with the zone.
_now = datetime.datetime.now().astimezone()
_tz = _now.tzname() or ""
_tz = "".join(w[0] for w in _tz.split()) if " " in _tz else _tz   # "Eastern Daylight Time" -> "EDT"
UPDATED = _now.strftime("%b %d, %Y %I:%M %p ").replace(" 0", " ") + _tz
OVERRIDE_TRIAL = json.load(open(S / "odd_wb_overrides.json", encoding="utf-8")) if (S / "odd_wb_overrides.json").exists() else {}

CATS = OrderedDict([
    # Terms follow the VIP Data Specification (DDA Master File), Aaron 2026-09-15.
    # Grouped by kind (Aaron, 2026-09-15): blocks the deck, fix on code sheet, needs fixing, missing workbook.
    ("status",   ("Account Status Codes can't be read", "block", "CSM: correct the Account Status mapping on the client's code sheet (field 33); it determines ARS eligibility")),
    ("prod",     ("New accounts have no Product Code Description", "block", "CSM: correct the Product mapping on the client's code sheet so each code has a Product Code Description (field 32); it determines ARS eligibility")),
    ("stale",    (f"No {PERIOD} ARS workbook", "block", "Data team: land this month's workbook")),
    ("uncalc",   ("Workbook saved without calculated formulas", "block", "Open in Excel, save, rebuild")),
    # The launcher stops an MM build on this since 2026-09-15, so it blocks the deck.
    ("lm",       ("Lift Matrix expired", "block", "CSM: create a new Lift Matrix; the deck isn't built until the data month is inside its window")),
    ("prodflag", ("Product codes with no Personal/Business flag", "map", "CSM: correct the Product mapping on the client's code sheet so each product code is Personal or Business; it determines ARS eligibility")),
    ("statusraw", ("Account Status Codes not mapped", "map", "CSM: correct the Account Status mapping on the client's code sheet: O, C, X, I, F, R, D or Z (field 33); it determines ARS eligibility")),
    ("mailflag", ("Mail Flags not mapped", "map", "CSM: correct the Mail Flag mapping on the client's code sheet so each value is Yes or No; it decides who is mailed")),
    ("rege",     ("Reg E Codes not mapped", "map", "CSM: correct the Reg E mapping on the client's code sheet: Y, N or D (field 70)")),
    ("malformed", ("Malformed or incomplete ODD extract", "fix", "Data team: correct the export")),
    ("nowb",     ("Missing Workbook", "pending", "Data team: confirm whether an ARS workbook is due for this client")),
])
BADGE = {"block": ("Blocks the deck", "blocker"), "fix": ("Needs fixing", "gap"),
         "map": ("Fix on code sheet", "decision"), "pending": ("Missing Workbook", "ok")}


def categorize(i):
    t = i["issue"]
    if t.startswith("Newest ARS workbook is"):
        return "stale", t.replace("Newest ARS workbook is", "Newest is").replace(f"; no {PERIOD} workbook", "")
    if "never calculated" in t:
        return "uncalc", ""
    if "flagged in its filename" in t:
        return "lm", t.split(": ", 1)[1]
    if t.startswith("ODD pack flag regE_unmapped"):
        return "rege", t.split(": ", 1)[1]
    if t.startswith("ODD pack flag status_other_raw"):
        return "statusraw", t.split(": ", 1)[1]
    if t.startswith("ODD pack flag non_numeric_cells"):
        v = json.loads(t.split(": ", 1)[1])
        return "malformed", f"{v['total']} cell(s) shifted into {', '.join(v['columns'])}"
    if "no program inputs" in t:
        return "nowb", ""
    # Old (column-name) and new (VIP Data Specification) wording both match.
    if "Prod Desc" in t or "Product Code Description" in t:
        return "prod", t
    if "Stat Desc" in t or "Stat Code" in t or "Account Status" in t or "no open personal" in t:
        return "status", t
    return None, None


def pretty_values(s):
    try:
        v = json.loads(s)
        return "; ".join(f"“{k}” ({n:,})" for k, n in v.items())
    except Exception:
        return s


items = []
for i in d["issues"]:
    cat, detail = categorize(i)
    if not cat:
        continue
    if cat in ("rege", "statusraw"):
        detail = pretty_values(detail)
    if cat == "nowb" and not C.get(i["id"], {}).get("odd_current"):
        continue
    items.append({"id": i["id"], "name": i["name"], "csm": i["csm"], "cat": cat, "detail": detail})

# Trial results the gaps snapshot did not carry (clients outside the current list, e.g. 1585).
have = {(x["id"], x["cat"]) for x in items}
for cid, t in TRIAL.items():
    tail = (t.get("log_tail") or "")
    line = next((l.strip() for l in tail.splitlines() if "POSSIBLE DATA ISSUE" in l), "")
    if not line or t.get("gate", "").startswith("0 FAIL"):
        continue
    cat = "prod" if "Prod Desc" in line else "status"
    if (cid, cat) in have:
        continue
    row = LIST.get(cid, {})
    items.append({"id": cid, "name": t.get("name") or row.get("client_name", ""), "csm": row.get("csm") or "Unassigned",
                  "cat": cat, "detail": line.replace("POSSIBLE DATA ISSUE: ", "")})

# Lift Matrix date check (Aaron, 2026-09-15: "add the lift matrix date check to the issue list"): the same
# lift_window reading and filename flag the launcher stops an MM build on. SM workbooks have no Lift Matrix
# MM tab and are skipped. Each workbook is read once per landing (cached on name + mtime).
_LWC = S / "lift_window_cache.json"
_lcache = json.load(open(_LWC, encoding="utf-8")) if _LWC.exists() else {}
for cid, c in C.items():
    wbs = BM.ars_workbook(R.report_dirs(), cid, PERIOD)
    if not wbs:
        continue
    p = Path(wbs[0])
    key = f"{p.name}|{p.stat().st_mtime_ns}"
    if key not in _lcache:
        try:
            _lcache[key] = workbook_window(str(p))
        except Exception as e:
            _lcache[key] = {"error": type(e).__name__}
    w = _lcache[key]
    if not w or w.get("error"):
        continue
    flag = lift_matrix_flag(p.name)
    if not (w["data_past_end"] or flag):
        continue
    detail = f"window {w['window'] or 'undated'}, data {w['data_date']}" + (f" · workbook flagged “{flag}”" if flag else "")
    have_lm = next((x for x in items if x["id"] == cid and x["cat"] == "lm"), None)
    if have_lm:
        have_lm["detail"] = detail
    else:
        items.append({"id": cid, "name": c.get("name", ""), "csm": c.get("csm") or LIST.get(cid, {}).get("csm") or "Unassigned",
                      "cat": "lm", "detail": detail})
json.dump(_lcache, open(_LWC, "w", encoding="utf-8"), indent=1)

# Names from the current Client CSM List: the gaps snapshot can predate a name fix (1780 read
# "LM EXPIRED-USF CU / USF CU" until 2026-09-15).
for x in items:
    x["name"] = LIST.get(x["id"], {}).get("client_name") or x["name"]

# Drop problems a later rebuild cleared.
for x in list(items):
    t = OVERRIDE_TRIAL.get(x["id"]) or TRIAL.get(x["id"], {})
    clean = str(t.get("gate", "")).startswith("0 FAIL") and not t.get("error")
    if x["cat"] in ("status", "prod", "uncalc") and clean:
        items.remove(x)

# How current each "ODD but no workbook" extract is (Aaron, 2026-09-15: are they out of date?).
_DP = S / "noprog_odd_dates.json"
DATES = {r["id"]: r for r in json.load(open(_DP, encoding="utf-8"))} if _DP.exists() else {}
fmt_mon = lambda t: f"{t[:3]} {2000 + int(t[3:])}" if t else "?"
# Every month on the client-reports share searched for an earlier ARS workbook (Aaron, 2026-09-15).
_HP = S / "missing_wb_history.json"
HIST = json.load(open(_HP, encoding="utf-8")) if _HP.exists() else None
if HIST is not None and HIST.get("months"):
    _months = HIST["months"]
elif HIST is not None and os.path.isdir(DS.SRC_REPORTS):
    _months = sorted(m for m in os.listdir(DS.SRC_REPORTS) if re.match(r"^\d{4}\.\d{2}$", m))
else:
    _months = []
HIST_SPAN = f"{len(_months)} month folders, {_months[0]} to {_months[-1]}" if _months else ""


def _kind(n):
    for k in ("DCO", "MRPCPM", "Workbook", "Invitation Checking", "CashPlease", "Charts"):
        if k.lower() in n.lower():
            return k
    return "other"


for x in items:
    if x["cat"] == "nowb" and x["id"] in DATES:
        r = DATES[x["id"]]
        a, _, b = (r.get("data_period") or "").partition(" to ")
        x["detail"] = f"{MONTH_NAME} ODD extract on hand (created {r.get('extract_created')}; data {fmt_mon(a)} to {fmt_mon(b)})"
        if HIST is not None:
            hist = HIST["all"].get(x["id"], [])
            wbs = HIST["hits"].get(x["id"], [])
            kinds = collections.Counter(_kind(n) for _, _, n in hist)
            months = sorted({m for m, _, _ in hist})
            x["detail"] += ("; " + (f"newest ARS workbook on the client-reports share: {sorted(wbs)[-1][0]}" if wbs else
                            f"no ARS workbook in any month on the client-reports share ({HIST_SPAN})")
                            + (f"; files there {months[0]} to {months[-1]}: " + ", ".join(f"{k} ×{n}" for k, n in kinds.most_common()) if hist else ""))
        if r.get("latest_month_col") and b and r["latest_month_col"] != b:
            items.append({"id": x["id"], "name": x["name"], "csm": x["csm"], "cat": "malformed",
                          "detail": f"The extract's data period runs to {fmt_mon(b)}, but its debit swipe and spend columns (Sig / PIN) stop at {fmt_mon(r['latest_month_col'])}: the latest months of card activity are missing"})

# Personal/Business flag: part of the product mapping on the client's code sheet (Aaron,
# 2026-09-15). The ODD's Business? must read Yes or No; anything else (blank included) puts the
# account in neither the personal nor the business counts. Listed by product code.
BF = S / "business_flags.json"
if BF.exists():
    for cid, r in json.load(open(BF, encoding="utf-8")).items():
        if not r.get("values"):
            continue
        row = LIST.get(cid, {})
        c = C.get(cid, {})
        vals = "; ".join(f"“{k}” ({n:,})" for k, n in r["values"].items())
        prods = "; ".join(f"{k} ({n:,})" for k, n in r["products"].items())
        name = c.get("name") or row.get("client_name") or TRIAL.get(cid, {}).get("name", "")
        csm = c.get("csm") or row.get("csm") or "Unassigned"
        if set(r["products"]) == {"(no code)"}:
            # No product code at all on those rows: nothing on the code sheet to correct (1539).
            items.append({"id": cid, "name": name, "csm": csm, "cat": "malformed",
                          "detail": f"{r['unflagged']:,} of {r['accounts']:,} accounts that are not closed or charged off have no Product Code and no Personal/Business flag in the extract, so there is no product to map"})
            continue
        items.append({"id": cid, "name": name, "csm": csm, "cat": "prodflag",
                      "detail": f"{r['unflagged']:,} of {r['accounts']:,} accounts that are not closed or charged off; flag values {vals}; by product code: {prods}"})

# Mail Flag (ODD Mailable?): mapped on the client's code sheet. In the ODD it does not set Elig
# (12 clients tested 2026-09-15: ~99% of otherwise-eligible not-mailable accounts are Elig=Yes);
# it suppresses offers, so it decides who is mailed.
MF = S / "mail_flags.json"
if MF.exists():
    for cid, r in json.load(open(MF, encoding="utf-8")).items():
        if not r.get("values"):
            continue
        row = LIST.get(cid, {}); c = C.get(cid, {})
        vals = "; ".join(f"“{k}” ({n:,})" for k, n in r["values"].items())
        items.append({"id": cid, "name": c.get("name") or row.get("client_name") or TRIAL.get(cid, {}).get("name", ""),
                      "csm": c.get("csm") or row.get("csm") or "Unassigned", "cat": "mailflag",
                      "detail": f"{r['unmapped']:,} of {r['accounts']:,} accounts; values {vals}"})

# Products and location from the Velocity client/product export (Aaron, 2026-09-15). Everything on
# this page is about ARS inputs, so a client the export shows without ARS, or does not list at all,
# is dropped: an ODD pulled for ICS or ILS is not missing an ARS workbook.
PRODUCTS = {}
_CP = S / "clients_products.json"
if _CP.exists():
    PRODUCTS = json.load(open(_CP, encoding="utf-8"))["clients"]
    _no_ars = lambda cid: "ARS" not in PRODUCTS.get(cid, {}).get("products", [])
    dropped = sorted({x["id"] for x in items if _no_ars(x["id"])}, key=int)
    items = [x for x in items if not _no_ars(x["id"])]
    print("dropped for no ARS product:", dropped)


def profile(cid):
    e = PRODUCTS.get(cid)
    if not e:
        return "not in the Velocity client export" if PRODUCTS else ""
    where = ", ".join(v for v in (e["city"], e["state"]) if v)
    return " · ".join(v for v in (where, ", ".join(e["products"]), "" if e["status"] == "Active" else e["status"]) if v)


# Every row carries the client's id AND name (Aaron, 2026-09-15). A blank name falls back to
# the trial build's name, then the CSM list — never id alone.
for x in items:
    if not (x.get("name") or "").strip():
        x["name"] = (TRIAL.get(x["id"], {}).get("name") or LIST.get(x["id"], {}).get("client_name")
                     or "(name not on any source)")
    x["name"] = x["name"].strip()

by_csm = defaultdict(list)
for x in items:
    by_csm[x["csm"]].append(x)
order = sorted(by_csm, key=lambda k: (k == "Unassigned", k))
kind_of = lambda x: CATS[x["cat"]][1]

style = re.search(r"(?s)<style>(.*?)</style>", TEMPLATE.read_text(encoding="utf-8")).group(1)
style += """
.csm{display:grid;gap:14px}
.csm-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 18px;border-bottom:2px solid var(--navy);padding-bottom:8px}
.csm-head h2{margin:0}
.tally{display:flex;flex-wrap:wrap;gap:6px}
.cat{background:var(--surface);border:1px solid var(--rule);border-radius:8px;overflow:hidden}
.cat-head{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;padding:10px 14px;border-bottom:1px solid var(--rule);background:var(--soft)}
.cat-head h3{font:700 15px/1.3 var(--head);margin:0;color:var(--heading)}
.cat-head .next{font-size:13px;color:var(--muted);margin-left:auto}
.cat ul{list-style:none;margin:0;padding:0}
.cat li{display:grid;grid-template-columns:4.2em minmax(10em,16em) minmax(0,1fr);gap:4px 12px;padding:8px 14px;border-top:1px solid var(--rule);font-size:14px}
.cat li:first-child{border-top:0}
.cat li .id{font:500 13px/1.5 var(--mono)}
.cat li .nm{font-weight:600}
.cat li .dt{color:var(--muted)}
.cat li .nm small.pf{display:block;font-weight:400;font-size:12px;line-height:1.35;color:var(--muted);margin-top:2px}
.summary{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:8px}
.summary td.n{font-variant-numeric:tabular-nums;text-align:right}
.summary a{color:var(--heading)}
.pill.ok{color:var(--ok);background:var(--ok-bg)}
@media (max-width:640px){.cat li{grid-template-columns:4.2em 1fr}.cat li .dt{grid-column:1/-1}}
@media print{.wrap{padding:0}.cat,.csm{break-inside:avoid-page}}
"""


def tally(xs):
    n = defaultdict(int)
    for x in xs:
        n[kind_of(x)] += 1
    return n


rows = []
for csm in order:
    n = tally(by_csm[csm]); nclients = len({x["id"] for x in by_csm[csm]})
    anchor = re.sub(r"\W+", "-", csm.lower())
    rows.append(f'<tr><td><a href="#{anchor}">{esc(csm)}</a></td><td class="n">{nclients}</td>'
                + "".join(f'<td class="n">{n.get(k, 0) or "—"}</td>' for k in ("block", "map", "fix", "pending")) + "</tr>")

sections = []
for csm in order:
    xs = by_csm[csm]
    anchor = re.sub(r"\W+", "-", csm.lower())
    n = tally(xs)
    # Same order as the sections below them (Aaron, 2026-09-15): by first appearance in CATS.
    kind_order = []
    for _cat, (_t, _k, _n) in CATS.items():
        if _k not in kind_order and any(x["cat"] == _cat for x in xs):
            kind_order.append(_k)
    pills = "".join(f'<span class="pill {BADGE[k][1]}">{n[k]} · {BADGE[k][0]}</span>' for k in kind_order if n.get(k))
    cats = []
    for cat, (title, kind, nxt) in CATS.items():
        cx = sorted((x for x in xs if x["cat"] == cat), key=lambda x: x["id"])
        if not cx:
            continue
        lis = "".join(f'<li><span class="id">{esc(x["id"])}</span><span class="nm">{esc(x["name"])}<small class="pf">{esc(profile(x["id"]))}</small></span>'
                      f'<span class="dt">{esc(x["detail"])}</span></li>' for x in cx)
        cats.append(f'<div class="cat"><div class="cat-head"><h3>{esc(title)}</h3>'
                    f'<span class="pill {BADGE[kind][1]}">{BADGE[kind][0]}</span>'
                    f'<span class="next">Next step: {esc(nxt)}</span></div><ul>{lis}</ul></div>')
    sections.append(f'<section class="csm" id="{anchor}"><div class="csm-head"><h2>{esc(csm)}</h2>'
                    f'<div class="tally">{pills}</div></div>{"".join(cats)}</section>')

# A Missing Workbook client is listed in its CSM's section only (Aaron, 2026-09-15: "Jordan's missing
# Texar workbook should be in his section"); the separate Missing Workbook table above the sections is gone.
total_clients = len({x["id"] for x in items})
# The charset must come first: opened from the share (file://) there is no server header,
# and without it browsers read the UTF-8 quotes and dashes as Windows-1252 (“ -> â€œ).
page = f"""<meta charset="utf-8">
<title>ODD and Workbook Issues</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Mono:wght@500&display=swap">
<style>{style}</style>
<div class="wrap">
<header>
  <div class="eyebrow">CSM Reporting · {esc(PERIOD)} · Updated {esc(UPDATED)}</div>
  <h1>ODD and Workbook Issues</h1>
</header>
<div class="summary"><table>
  <thead><tr><th>CSM</th><th>Clients</th><th>Blocks the deck</th><th>Fix on code sheet</th><th>Needs fixing</th><th>Missing Workbook</th></tr></thead>
  <tbody>{"".join(rows)}</tbody></table></div>
{"".join(sections)}
<footer>Terms follow the VIP Data Specification (DDA Master File). Unmapped Reg E Codes and Account Status Codes come from the data packs of clients built in the {esc(PERIOD)} trial run; clients not trial-built this run are not scanned for them here.</footer>
</div>"""
(S / ODD_PAGE).write_text(page, encoding="utf-8")
print(f"{ODD_PAGE}: {len(items)} findings, {total_clients} clients;", {c: len(v) for c, v in by_csm.items()})
