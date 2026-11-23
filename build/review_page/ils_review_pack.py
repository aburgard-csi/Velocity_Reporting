#!/usr/bin/env python3
"""ils_review_pack.py — read a client's finished ILS Program Analysis review (the PDF) into a data pack.

Live Review's ILS section (Aaron, 2026-11-06: "build a LR page for Marine FCU using their last ILS analysis
review") presents the figures the consultant's review already carries. The review is a deck, so its tables
are text on the page and its charts are pictures. This reads the TEXT tables only and says which ones it found:

    page 14   institution (asset size, branches, active DDA accounts, go-live, contract, data through)
    page 15   peer comparison (the client against the median of its peer set)
    page 16   account utilization (fees by how often an account uses the program)
    page 17   mature accounts by 365-day deposits
    page 23   twelve months, Period 1      page 24   twelve months, Period 2
    page 25   the two periods side by side
    page 42   OD risk metrics against all Velocity clients     page 43   against credit unions of its size
    page 51   the opportunity analysis, as presented

Pages are found by their headings, not their numbers, so a review that adds a slide still reads. A table that is
not in a review is left out of the pack and the page does not show it; a table that does not reconcile (the
twelve months against the annual row, the tiers against the total) STOPS the read, because a pack that adds up
wrongly would put a wrong figure on a client's page.

Import-safe: nothing runs at import; pypdf is imported inside `read_pdf`.
"""
import re
from pathlib import Path

PACK_VERSION = 1

_NUM = r"[\d,]+(?:\.\d+)?"


class ReviewReadError(Exception):
    pass


# Said when a review is an ILS Program Analysis but its figures are not in the PDF's text. The analysis team's decks from about
# 2024 paste each table in as a picture (the KPI rollup, the peer comparison, the monthly summaries), so the text layer holds the
# slide titles and the consultant's bullets and nothing a figure can be read from. Reading a picture is OCR, which is a decision
# for Aaron (a new dependency, and every figure still has to reconcile), not something this reader does quietly.
IMAGE_TABLES_MESSAGE = ("only {n} of the review's tables are text: the rest are pictures in the PDF, which this reader cannot "
                        "read (the review itself is an ILS Program Analysis)")


def _flat(s):
    return " ".join((s or "").split())


def read_pdf(path):
    """[page text, one string per page, whitespace collapsed]."""
    from pypdf import PdfReader
    return [_flat(p.extract_text()) for p in PdfReader(str(path)).pages]


def _n(s):
    s = str(s).replace("$", "").replace(",", "").replace("%", "").strip()
    return float(s) if "." in s else int(s)


def _join_split_digits(text):
    """The PDF text layer breaks a long dollar figure at a page-width boundary ("$1,970,60 5"). A comma group
    always has three digits, so a group of two followed by one digit is one number cut in two."""
    return re.sub(r"(\$\d{1,3}(?:,\d{3})*,\d{2}) (\d)(?!\d)", r"\1\2", text)


def _find(pages, *needles):
    """The first page whose text contains every needle (case-insensitive), as (1-based page number, text)."""
    for i, t in enumerate(pages, 1):
        low = t.lower()
        if all(n.lower() in low for n in needles):
            return i, t
    return None, None


# ----------------------------------------------------------------- the pages
def _spaced(phrase):
    """A pattern for `phrase` that survives the text layer's stray spaces inside words ("PA RTNERING FO R SUCCESS")."""
    return r"\s+".join(r"\s*".join(re.escape(c) for c in word) for word in phrase.split())


# The covers say it in four ways (all read from the text layer, whatever the page's case or spacing):
#   "Partnering for Success <client> <Month d, yyyy>"                      the original layout (Marine FCU)
#   "PARTNERING FOR SUCCESS · ANNUAL REVIEW ILS® Program Analysis <client> <date> Prepared by ..."   (2026)
#   "ILS Program Analysis <client> <date>"                                 the 2018 layout
#   a cover with no client or date at all (the legal notice first, or "INTELLIGENT LIMIT SYSTEM® Program Performance Analysis")
_TITLE_RX = re.compile(
    r"(?:" + _spaced("Partnering for Success") + r"(?:\s*·\s*" + _spaced("ANNUAL REVIEW") + r")?"
    r"|ILS\s*®?\s*Program\s+Analysis)\s*(?:ILS\s*®?\s*Program\s+Analysis\s+)?"
    r"(?P<client>[^\d•|]{2,80}?)\s+(?P<date>[A-Z][a-z]+ \d{1,2}, \d{4})", re.IGNORECASE)


_LEADING_MARKER_RX = re.compile(
    r"^(?:(?:" + _spaced("Partnering for Success") + r"|" + _spaced("ANNUAL REVIEW") + r"|ILS\s*®?\s*Program\s+(?:Performance\s+)?Analysis)\s*·?\s*)+",
    re.IGNORECASE)


def _name_from_file(source_file):
    """`1204-2026.09-ILS-FSB Michigan ILS Review.pdf` -> `FSB Michigan`."""
    stem = re.sub(r"\.pdf$", "", Path(source_file).name, flags=re.IGNORECASE)
    m = re.match(r"^\d{3,5}-\d{4}\.\d{2}-ILS-(.+?)(?:\s+ILS Review)?$", stem, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _title_block(pages, source_file=""):
    """(client name, ISO review date or None, where they came from). A cover that carries no title line falls back to the
    file name: the name from it, and no date, because the file's YYYY.MM is a month and never becomes a day."""
    import datetime
    for t in pages[:3]:
        for m in _TITLE_RX.finditer(t):
            client = m.group("client").strip(" ·-")
            # a layout that prints both phrases ("ILS Program Analysis Partnering for Success <client>") leaves one in the capture
            client = _LEADING_MARKER_RX.sub("", client).strip(" ·-")
            if re.search(r"confidential|this document|proprietary|^\d", client, re.IGNORECASE) or len(client) < 2:
                continue
            try:
                d = datetime.datetime.strptime(m.group("date"), "%B %d, %Y").date()
            except ValueError:
                continue
            return client, d.isoformat(), "cover"
    name = _name_from_file(source_file)
    if name:
        return name, None, "file name"
    raise ReviewReadError("the cover has no title line and the file name does not give the client")


def _mdy(s):
    import datetime
    return datetime.datetime.strptime(s, "%m/%d/%Y").date().isoformat()


def _institution(pages):
    pg, t = _find(pages, "FI DEMOGRAPHIC INFORMATION", "Active DDA Accounts")
    if not pg:
        return None, None

    def g(rx):
        m = re.search(rx, t)
        return m.group(1).strip() if m else None
    out = {"hq": g(r"HQ:\s*(.+?)\s*•"), "asset_size": g(r"Asset Size:\s*(.+?)\s*•"),
           "branches": _n(g(r"Branches:\s*(\d+)")) if g(r"Branches:\s*(\d+)") else None,
           "active_dda": _n(g(r"Active DDA Accounts:\s*([\d,]+)")) if g(r"Active DDA Accounts:\s*([\d,]+)") else None,
           "regulator": g(r"Primary Federal Regulator:\s*(.+?)\s*•"), "core": g(r"Core Provider:\s*(.+?)\s*•"),
           "core_product": g(r"Core Product:\s*(.+?)\s*•"), "version": g(r"ILS® Version:\s*(.+?)\s*•")}
    for key, label in (("go_live", r"ILS® Go Live Date:"), ("contract_start", r"Contract Start:"),
                       ("contract_end", r"Contract End:"), ("data_through", r"Data Analyzed Through:")):
        v = g(label + r"\s*(\d{2}/\d{2}/\d{4})")
        out[key] = _mdy(v) if v else None
    return out, pg


# metric code -> (plain label or None, kind). kind: int, pct, usd, dec. The review names only a few in words
# (its own bullets: Eligible %, RegE %, Items/User, Charge-offs); the others keep the review's code.
PEER_METRICS = {
    "MED.OFFICES": ("Branches", "int"),
    "MED.ACTIVE.CHK": ("Active checking accounts", "int"),
    "MED.USERS": ("Users", "int"),
    "MED.USER.PER": ("Users, % of accounts", "pct"),
    "MED.ELIG.PER": ("Eligible %", "pct"),
    "MED.REGE.PER": ("Reg E opt-in %", "pct"),
    "MED.ITEMSxUS": ("Items per user", "dec"),
    "MED.ELIG.LIM": ("MED.ELIG.LIM", "int"),
    "MED.DEPT33": ("MED.DEPT33", "usd"),
    "MED.DAYS": ("MED.DAYS", "int"),
    "MED.WF": ("MED.WF", "dec"),
    "MED.DEPT365": ("MED.DEPT365", "usd"),
    "MED.ACB": ("MED.ACB", "usd"),
    "MED.PD.AMT": ("MED.PD.AMT", "usd"),
    "MED.PAY.RT": ("MED.PAY.RT", "pct"),
    "USR.CHGOFF.PER": ("Charge-offs, % of users", "pct"),
    "LOSS.RT": ("LOSS.RT", "pct"),
    "REF.RT": ("REF.RT", "pct"),
    "MED.NET.CHG": ("MED.NET.CHG", "usd"),
    "MED.NET.REF": ("MED.NET.REF", "usd"),
    "MED.AVG.FEE": ("Average fee", "usd"),
}


def _peer_comparison(pages):
    pg, t = _find(pages, "Peer Comparison", "MED.OFFICES")
    if not pg:
        return None, None
    body = t.split("•")[0]
    m = re.search(r"COUNT\s+(\d+)\s+(\d+)", body)
    ftype = re.search(r"FI_TYPE\s+(\w+)\s+(\w+)", body)
    rows = []
    for code, (label, kind) in PEER_METRICS.items():
        mm = re.search(re.escape(code) + r"\s+(\S+)\s+(\S+)", body)
        if not mm:
            continue
        rows.append({"code": code, "label": label, "kind": kind, "client": _n(mm.group(1)), "peer": _n(mm.group(2))})
    if not rows or not m:
        raise ReviewReadError(f"peer comparison on page {pg} has no readable metric rows")
    bullets = [b.strip() for b in t.split("•")[1:] if b.strip()]
    return {"peer_count": int(m.group(2)), "peer_type": ftype.group(2) if ftype else None, "rows": rows, "commentary": bullets}, pg


_TIERS = [("NON-USER", "Non-user"), ("<= 6 ITEMS", "6 items or fewer"), ("7-23 ITEMS", "7 to 23 items"),
          (r"HEAVY USER \(24\+\)", "Heavy user (24+ items)"), ("TOTAL", "All accounts")]


def _utilization(pages):
    pg, t = _find(pages, "Account Utilization", "HEAVY USER")
    if not pg:
        return None, None
    t = _join_split_digits(t)
    rows = []
    for rx, label in _TIERS:
        m = re.search(rx + rf"\s+({_NUM})\s+({_NUM})%\s+({_NUM})%\s+({_NUM})%\s+\$({_NUM})\s+(NaN%|{_NUM}%)\s+\$({_NUM})\s+({_NUM})%", t)
        if not m:
            raise ReviewReadError(f"account utilization on page {pg}: no row for {label!r}")
        pd = None if m.group(6).startswith("NaN") else _n(m.group(6))
        rows.append({"tier": label, "accounts": _n(m.group(1)), "accounts_pct": _n(m.group(2)), "reg_e_pct": _n(m.group(3)),
                     "eligible_pct": _n(m.group(4)), "deposits_365": _n(m.group(5)), "paid_pct": pd,
                     "fees_365": _n(m.group(7)), "fees_pct": _n(m.group(8))})
    parts, total = rows[:-1], rows[-1]
    if sum(r["accounts"] for r in parts) != total["accounts"]:
        raise ReviewReadError(f"account utilization on page {pg}: the tiers' accounts do not add to the total")
    if sum(r["fees_365"] for r in parts) != total["fees_365"]:
        raise ReviewReadError(f"account utilization on page {pg}: the tiers' fees do not add to the total")
    return {"rows": parts, "total": total}, pg


def _mature(pages):
    pg, t = _find(pages, "Mature Accounts", "depAmt365cut")
    if not pg:
        return None, None
    t = _join_split_digits(t)
    rx = re.compile(rf"(ZERO DEPS|<10k|\d+-\d+k|\d+-per\.cap|per\.cap-\d+k|\d+k\+|TOTAL)\s+({_NUM})\s+({_NUM})%\s+({_NUM})%\s+({_NUM})%\s+({_NUM})%\s+\$({_NUM})\s+\$({_NUM})\s+({_NUM})%")
    rows = [{"band": m.group(1), "accounts": _n(m.group(2)), "accounts_pct": _n(m.group(3)), "reg_e_pct": _n(m.group(4)),
             "eligible_pct": _n(m.group(5)), "paid_pct": _n(m.group(6)), "median_paid_od": _n(m.group(7)),
             "fees_365": _n(m.group(8)), "fees_pct": _n(m.group(9))} for m in rx.finditer(t)]
    if len(rows) < 3 or rows[-1]["band"] != "TOTAL":
        raise ReviewReadError(f"mature accounts on page {pg}: the table did not read (found {len(rows)} rows)")
    parts, total = rows[:-1], rows[-1]
    if sum(r["accounts"] for r in parts) != total["accounts"]:
        raise ReviewReadError(f"mature accounts on page {pg}: the bands' accounts do not add to the total")
    return {"rows": parts, "total": total}, pg


_MONTH_RX = re.compile(rf"(\d{{4}}) (\d{{2}}) ({_NUM}) (\d+) ({_NUM})% (\d+) ({_NUM}) \$({_NUM}) \$({_NUM}) \$({_NUM}) \$({_NUM}) ({_NUM})%")


def _month_rows(text):
    return [{"ym": f"{m.group(1)}-{m.group(2)}", "count": _n(m.group(3)), "cure": _n(m.group(4)), "default_rt": _n(m.group(5)),
             "biz_days": _n(m.group(6)), "accts_with_od": _n(m.group(7)), "fees": _n(m.group(8)), "fees_per_bizday": _n(m.group(9)),
             "fees_per_acct": _n(m.group(10)), "losses": _n(m.group(11)), "loss_rt": _n(m.group(12))}
            for m in _MONTH_RX.finditer(text)]


def _monthly(pages):
    pg1, t1 = _find(pages, "Period 1 Revenue", "C.FEES")
    pg2, t2 = _find(pages, "YoY Monthly Summary (Period 2)", "C.FEES")
    if not (pg1 and pg2):
        return None, None
    p1, p2 = _month_rows(t1), _month_rows(t2)
    if len(p1) != 12 or len(p2) != 12:
        raise ReviewReadError(f"monthly summary: read {len(p1)} and {len(p2)} months, expected 12 and 12")
    return {"period1": p1, "period2": p2}, (pg1, pg2)


def _annual(pages, monthly):
    pg, t = _find(pages, "Annual Comparison", "COMP365")
    if not pg:
        return None, None
    rx = re.compile(rf"\b([12]) ({_NUM}) ({_NUM}) ({_NUM})% (\d+) ({_NUM}) \$({_NUM}) \$({_NUM}) \$({_NUM}) \$({_NUM}) ({_NUM})%")
    got = {}
    for m in rx.finditer(t):
        got[int(m.group(1))] = {"count": _n(m.group(2)), "cure": _n(m.group(3)), "default_rt": _n(m.group(4)), "biz_days": _n(m.group(5)),
                                "accts_with_od": _n(m.group(6)), "fees": _n(m.group(7)), "fees_per_bizday": _n(m.group(8)),
                                "fees_per_acct": _n(m.group(9)), "losses": _n(m.group(10)), "loss_rt": _n(m.group(11))}
    if set(got) != {1, 2}:
        raise ReviewReadError(f"annual comparison on page {pg}: did not read both periods")
    if monthly:
        for k, key in ((1, "period1"), (2, "period2")):
            for f in ("count", "fees", "losses"):
                s = sum(r[f] for r in monthly[key])
                if s != got[k][f]:
                    raise ReviewReadError(f"annual comparison on page {pg}: period {k} {f} is {got[k][f]} but its twelve months add to {s}")
    bullets = [b.strip() for b in t.split("•")[1:] if b.strip()]
    return {"period1": got[1], "period2": got[2], "commentary": bullets}, pg


_RISK_RX = re.compile(rf"(BANK|CU|<= 1B|1B-2B|2B-5B|5B-10B|10B\+|[A-Z][A-Z0-9 .&'/-]*? \(\d{{3,5}}\))\s+(\d+)\s+({_NUM})\s+({_NUM})\s+({_NUM})%\s+({_NUM})\s+\$({_NUM})\s+({_NUM})%")


def _risk_rows(text, client):
    out = []
    for m in _RISK_RX.finditer(text):
        grp = m.group(1)
        out.append({"group": "this client" if re.search(r"\(\d{3,5}\)$", grp) else grp, "n": _n(m.group(2)),
                    "active_checking": _n(m.group(3)), "od_rate": _n(m.group(4)), "default_rt": _n(m.group(5)),
                    "fee_income": _n(m.group(6)), "fees_per_acct": _n(m.group(7)), "loss_rt": _n(m.group(8))})
    return out


def _risk(pages, client_name):
    pg_g, t_g = _find(pages, "OD Risk Metrics", "GLOBAL RISK METRICS")
    pg_p, t_p = _find(pages, "OD Risk Metrics", "PEER RISK METRICS")
    if not (pg_g or pg_p):
        return None, None
    peer_label = None
    if t_p:
        m = re.search(r"PEER RISK METRICS:\s*(.+?)\s+Asset Size", t_p)
        peer_label = m.group(1).strip() if m else None
    return {"global": _risk_rows(t_g, client_name) if t_g else [], "by_asset_size": _risk_rows(t_p, client_name) if t_p else [],
            "peer_label": peer_label}, (pg_g, pg_p)


def _opportunity(pages):
    pg, t = _find(pages, "OPPORTUNITY ANALYSIS")
    if not pg:
        return None, None
    body = t.split("Confidential and proprietary information", 1)[-1]
    return [b.strip() for b in body.split("•") if b.strip()], pg


# ----------------------------------------------------------------- the pack
def parse(pages, source_file, client_id):
    name, review_date, title_from = _title_block(pages, source_file)
    per = review_period(source_file)
    pack = {"version": PACK_VERSION, "client_id": str(client_id), "client_name": name, "review_date": review_date,
            # the month the file name gives the review: all a cover with no date can say, and never made into a day
            "review_period": f"{per[0]}-{per[1]}" if per else (review_date[:7] if review_date else None),
            "title_from": title_from, "source_file": source_file, "page_count": len(pages), "pages": {}}
    for key, fn in (("institution", _institution), ("peer_comparison", _peer_comparison),
                    ("utilization", _utilization), ("mature", _mature), ("monthly", _monthly)):
        val, pg = fn(pages)
        if val is not None:
            pack[key] = val
            pack["pages"][key] = pg
    ann, pg = _annual(pages, pack.get("monthly"))
    if ann is not None:
        pack["annual"] = ann
        pack["pages"]["annual"] = pg
    risk, pg = _risk(pages, name)
    if risk is not None:
        pack["risk"] = risk
        pack["pages"]["risk"] = pg
    opp, pg = _opportunity(pages)
    if opp is not None:
        pack["opportunity"] = opp
        pack["pages"]["opportunity"] = pg
    if len(pack["pages"]) < 3:
        raise ReviewReadError(IMAGE_TABLES_MESSAGE.format(n=len(pack["pages"])))
    return pack


def pack_path(client, root=None):
    import rpe_env
    base = Path(root) if root else rpe_env.build_artifacts()
    return base / "ils_analysis" / "review_packs" / f"{client}_ils_review.json"


def client_from_filename(path):
    m = re.match(r"^(\d{3,5})-\d{4}\.\d{2}-ILS-", Path(path).name)
    return m.group(1) if m else None


# ----------------------------------------------------------------- the reviews on the share (Aaron, 2026-11-06)
# `Inputs/ILS Reviews/<id>/<id>-<yyyy.mm>-ILS-<Client> ILS Review.pdf`: the finished review, landed from the Clients library by
# scripts/land_ils_reviews.py and read into the pack above. The YYYY.MM in the name is the review's period, so the newest review
# is the one with the latest period (a tie goes to the later write). Nothing here reads the share at import.
REVIEW_NAME_RX = re.compile(r"^(\d{3,5})-(\d{4})\.(\d{2})-ILS-.*ILS Review\.pdf$", re.IGNORECASE)


def review_period(name):
    """('2026', '07') for `1539-2026.07-ILS-Marine FCU ILS Review.pdf`, or None when the name is not a review's."""
    m = REVIEW_NAME_RX.match(Path(name).name)
    return (m.group(2), m.group(3)) if m else None


def reviews_dir(client, create=False):
    import rpe_env
    p = rpe_env.input_dir("ILS reviews", create=create) / str(client)
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def newest(names):
    """The newest review among file names (or paths): latest period, then the name. None when none is a review's."""
    best = None
    for n in names:
        per = review_period(n)
        if per and (best is None or (per, Path(n).name) > (review_period(best), Path(best).name)):
            best = n
    return best


def newest_review(client):
    """The client's newest review PDF on the share, or None."""
    d = reviews_dir(client)
    try:
        names = [f.name for f in d.iterdir() if f.is_file()]
    except OSError:
        return None
    got = newest(names)
    return d / got if got else None
