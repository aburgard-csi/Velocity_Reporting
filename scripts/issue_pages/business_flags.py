"""Personal/Business flag (ODD 'Business?', VIP spec field 29 Account Type) values the pipeline can't read.

    python scripts/issue_pages/business_flags.py [extra client ids ...]

odd_rows reads 'No' as personal and 'Yes' as business (case-insensitive); anything else, blank
included, is NEITHER and falls out of both denominators. Counts per current client with an ODD extract
in Inputs -> Build Artifacts/issue_pages/business_flags.json. Scans every extract: allow several minutes.
"""
import collections, io, json, sys, zipfile

import pandas as pd

from common import R, work_dir  # noqa: E402
from odd_rows import status_class, odd_member, business_class_series  # noqa: E402

S = work_dir()
ODDD = R.inputs() / "ODDD"
d = json.load(open(S / "gaps.json", encoding="utf-8"))
ids = sorted(set(c["id"] for c in d["clients"] if c["odd_in_inputs"]) | set(sys.argv[1:]))
out = {}
for cid in ids:
    z = ODDD / f"{cid}_ODDD.zip"
    if not z.exists():
        continue
    zf = zipfile.ZipFile(z)
    try:
        member = odd_member(zf)          # the one rule for which member is the ODD
    except FileNotFoundError:
        continue
    # The flag is part of the product mapping on the client's code sheet (Aaron, 2026-09-15), so count
    # by product code: that is the row a CSM corrects. Only accounts that could be eligible count: a
    # closed or charged-off account needs no mapping, so it is never called out. Status is read by
    # odd_rows.status_class (description, else the confirmed Stat Code), as on the Excluded Accounts slide.
    counts, prods, total, closed_skipped = collections.Counter(), collections.Counter(), 0, 0
    want = {"Business?", "Prod Code", "Prod Desc", "Stat Desc", "Stat Code"}
    try:
        for ch in pd.read_csv(io.TextIOWrapper(zf.open(member), encoding="latin-1", newline=""), skiprows=4,
                              dtype=str, usecols=lambda c: c.strip() in want, chunksize=200000,
                              on_bad_lines="skip"):
            ch.columns = [c.strip() for c in ch.columns]
            if "Business?" not in ch:
                break
            ch = ch.reindex(columns=["Business?", "Prod Code", "Prod Desc", "Stat Desc", "Stat Code"]).fillna("")
            ch = ch.apply(lambda s: s.str.replace("\x00", "", regex=False).str.strip())
            # status_class re-imports its code map per call, so classify each distinct pair once.
            pairs = ch["Stat Desc"] + "\x1f" + ch["Stat Code"]
            live_of = {p: status_class(*p.split("\x1f", 1)) != "closed" for p in pairs.unique()}
            live = pairs.map(live_of).astype(bool)
            total += int(live.sum())
            unflag = business_class_series(ch["Business?"]).eq("other")   # neither Yes nor No
            closed_skipped += int((unflag & ~live).sum())
            bad = ch[unflag & live]
            counts.update(v if v else "(blank)" for v in bad["Business?"])
            prods.update(f"{c or '(no code)'}" + (f" {d}" if d else "") for c, d in zip(bad["Prod Code"], bad["Prod Desc"]))
    except Exception as e:
        out[cid] = {"error": str(e)[:120]}
        continue
    if total == 0:
        out[cid] = {"error": "no Business? column"}
    elif counts:
        out[cid] = {"accounts": total, "values": dict(counts.most_common(8)),
                    "products": dict(prods.most_common(8)), "unflagged": sum(counts.values()),
                    "closed_skipped": closed_skipped}
json.dump(out, open(S / "business_flags.json", "w", encoding="utf-8"), indent=1)
print("business_flags.json:", len([k for k, v in out.items() if v.get("values")]), "clients with unreadable flags;",
      "errors:", {k: v["error"] for k, v in out.items() if "error" in v})
