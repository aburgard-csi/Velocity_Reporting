"""For clients with an ODD extract but no program workbook: how current is that ODD? -> noprog_odd_dates.json.

    python scripts/issue_pages/noprog_odd_dates.py

Aaron, 2026-09-15: "what's the latest period or creation date for the ODD file? Are they out of date?"
Reads each Missing Workbook client's extract in Inputs (created stamp, data period, newest Sig # column)
and the share file's date.
"""
import csv, datetime, json, os, re, zipfile

from common import R, work_dir  # noqa: E402
import deck_status as DS  # noqa: E402

S = work_dir()
d = json.load(open(S / "gaps.json", encoding="utf-8"))
C = {c["id"]: c for c in d["clients"]}
ids = sorted({i["id"] for i in d["issues"] if "no program inputs" in i["issue"] and C[i["id"]]["odd_current"]})
LIST = {r["client_id"]: r for r in csv.DictReader(open(R.data_root() / R.CSM_LIST_NAME, encoding="utf-8-sig"))}
I = R.inputs()
out = []
for cid in ids:
    rec = {"id": cid, "name": C[cid]["name"] or LIST.get(cid, {}).get("client_name", ""), "csm": C[cid]["csm"],
           "share_month_folder": LIST.get(cid, {}).get("newest_odd_month")}
    z = I / "ODDD" / f"{cid}_ODDD.zip"
    if z.exists():
        rec["inputs_copied"] = datetime.datetime.fromtimestamp(z.stat().st_mtime).strftime("%Y-%m-%d")
        zf = zipfile.ZipFile(z)
        mem = [n for n in zf.namelist() if not n.endswith("/")]
        odd = next((n for n in mem if "-ODD" in n or "_v2_" in n.lower()), None)
        rec["files"] = len(mem)
        if odd:
            info = zf.getinfo(odd)
            rec["odd_member"] = odd
            m = re.search(r"\((\d{2})(\d{2})(\d{2})_\d{6}\)", odd)          # (090126_154106) = mmddyy
            rec["extract_created"] = f"20{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else None
            rec["zip_entry_date"] = "%04d-%02d-%02d" % info.date_time[:3]
            with zf.open(odd) as fh:
                head = [fh.readline().decode("latin-1", "replace") for _ in range(5)]
            per = next((re.search(r"Data Period:\s*([A-Za-z]{3}\d{2})\s*to\s*([A-Za-z]{3}\d{2})", l) for l in head
                        if "Data Period" in l), None)
            rec["data_period"] = f"{per.group(1)} to {per.group(2)}" if per else None
            hdr = next((l for l in head if "Acct ID" in l), "")
            months = sorted({m for m in re.findall(r"([A-Z][a-z]{2}\d{2}) Sig #", hdr)},
                            key=lambda t: datetime.datetime.strptime(t, "%b%y"))
            rec["latest_month_col"] = months[-1] if months else None
    try:
        hit = DS.find_source_odd(cid, d["summary"]["period"])
        if hit:
            p, csm = hit
            rec["share_file_date"] = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")
    except Exception as e:
        rec["share_error"] = str(e)[:80]
    out.append(rec)
json.dump(out, open(S / "noprog_odd_dates.json", "w", encoding="utf-8"), indent=1)
print(f"noprog_odd_dates.json: {len(out)} clients")
