#!/usr/bin/env python3
"""roster_candidate.py — the clients.md rows a client is missing (Aaron, 2026-10-28; 1585 was missing).

clients.md decides what gets BUILT, and Sheila can only offer a client that has a row there: James reported
1585 First Community Bank of the Heartland "missing" and the cause was no row at all. This reads what the data side
already knows about a client (Client CSM List.csv, the ARS workbook, the CashPlease pack) and prints the rows that
would be added, so the person (or Claude) adding them starts from facts, not memory. It WRITES NOTHING.

    python scripts/roster_candidate.py 1585 [1586 ...]

What it cannot know, it says: the delivery name is a decision (the CSM list name is a starting point), ICS and MRPC
need their own data, and ILS is not tracked in the main table. Paths come from rpe_env. Import-safe.
"""
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, os.pardir, "build"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DASH = "—"
# the CSM list names programs in words; clients.md uses the short tags
_TAGS = (("ARS", "ARS"), ("ICS", "ICS"), ("MRPC", "MRPC"), ("CashPlease", "CP"))


def programs(row):
    """The RPE programs a CSM list row carries, in section order: ['ARS', 'ICS', 'MRPC', 'CP'].

    `rpe_programs` is the column for it; `products` (which also carries ILS and others) is the fallback."""
    text = (row.get("rpe_programs") or row.get("products") or "")
    have = {t.strip().lower() for t in text.split(";") if t.strip()}
    return [tag for word, tag in _TAGS if word.lower() in have]


def main_row(cid, name, path, progs):
    """The main-table row: `| 1585 | Name | MM | yes | — | — | ARS |`. CP never appears here (its own table)."""
    ars = "yes" if "ARS" in progs else DASH
    ics = "yes" if "ICS" in progs else DASH
    mrpc = "yes" if "MRPC" in progs else DASH
    deck = "-".join(p for p in progs if p != "CP") or DASH
    return f"| {cid} | {name} | {path or DASH} | {ars} | {ics} | {mrpc} | {deck} |"


def cp_row(cid, name, csm, loans, progs):
    """The CashPlease-roster row, or None when the client has no CashPlease."""
    if "CP" not in progs:
        return None
    others = [p for p in progs if p != "CP"]
    ships = "**%s-CP** section" % "-".join(others) if others else "standalone deck  "
    note = "" if others else "no other RPE program"
    return f"| {cid} | {name} | {csm} | yes | {loans if loans is not None else '?'} | {ships} | {note} |"


def newest_workbook(report_dirs, cid):
    """The newest ARS workbook (never the Invitation Checking one) for the client, or None."""
    hits = [p for d in report_dirs for p in glob.glob(os.path.join(str(d), f"{cid}-*Workbook*.xlsx"))
            if "invitation checking" not in os.path.basename(p).lower()]
    return max(hits, key=os.path.getmtime) if hits else None


def gather(cids):
    import rpe_env as R
    import build_month as BM
    import perf_clients as PC
    listed = {}
    csm_file = R.csm_list_file()
    if csm_file and csm_file.is_file():
        with open(csm_file, encoding="utf-8-sig", newline="") as fh:
            listed = {r.get("client_id", "").strip(): r for r in csv.DictReader(fh)}
    roster = {c[0] for c in BM.read_roster()[0]}
    cp_ids = {r["client_id"] for r in BM.read_cashplease_roster()}
    out = []
    for cid in cids:
        row = listed.get(cid)
        doc = {"client": cid, "in_clients_md": cid in roster, "in_cashplease_roster": cid in cp_ids}
        if not row:
            doc["problem"] = "not in Client CSM List.csv"
            out.append(doc)
            continue
        progs = programs(row)
        name = row.get("client_name", "").strip()
        wb = newest_workbook(R.report_dirs(), cid) if "ARS" in progs else None
        path = PC.detect_path(wb) if wb else None
        loans = None
        pack = R.build_artifacts() / "cashplease" / "packs" / f"{cid}_cashplease.json"
        if "CP" in progs and pack.is_file():
            try:
                loans = json.loads(pack.read_text(encoding="utf-8"))["total"]["loans"]
            except (OSError, ValueError, KeyError):
                loans = None
        csm = row.get("csm", "").strip()
        doc.update(name=name, csm=csm, status=row.get("velocity_status"), programs=progs,
                   products=row.get("products"), workbook=os.path.basename(wb) if wb else None, path=path,
                   main_row=None if doc["in_clients_md"] else main_row(cid, name, path, progs),
                   cp_row=None if doc["in_cashplease_roster"] else cp_row(cid, name, csm, loans, progs))
        notes = []
        if "ARS" in progs and not wb:
            notes.append("ARS is listed but no ARS workbook is in Inputs, so Path is unknown: leave it as a dash (a blank Path on an ARS row reads as MM, the Lift Matrix model every new ARS client is on) and the build stops until a workbook lands")
        if "ICS" in progs:
            notes.append("ICS: the row says 'yes'; add '(direct mail list...)' or 'referrals-only' only if that is the data on hand")
        notes.append("the delivery name is a decision; the CSM list name is the starting point")
        notes.append("ILS is not tracked in the main table (Aaron's ILS clients have their own section)")
        doc["notes"] = notes
        out.append(doc)
    return out


def render(docs):
    lines = []
    for d in docs:
        lines.append(f"{d['client']}: " + (d.get("name") or d.get("problem", "")))
        if d.get("problem"):
            lines.append("")
            continue
        lines.append(f"  CSM {d['csm']}; programs {'-'.join(d['programs']) or 'none'}; products: {d['products']}")
        lines.append("  main table:  " + ("already in clients.md" if d["in_clients_md"] else d["main_row"]))
        lines.append("  CashPlease:  " + ("already in the CashPlease roster" if d["in_cashplease_roster"]
                                           else (d["cp_row"] or "no CashPlease")))
        for n in d["notes"]:
            lines.append("  - " + n)
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    cids = argv if argv is not None else sys.argv[1:]
    if not cids or any(not re.fullmatch(r"\d{3,5}", c) for c in cids):
        print("usage: roster_candidate.py <client id> [<client id> ...]")
        return 2
    print(render(gather(cids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
