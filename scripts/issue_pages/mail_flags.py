"""Mail Flag (ODD 'Mailable?') values outside Yes / No, per current client, with the raw values.

    python scripts/issue_pages/mail_flags.py [extra client ids ...]

The Mail Flag is mapped on the client's code sheet. In the ODD it does not set Elig; it decides who is
mailed (Aaron, 2026-09-15). A value that is not Yes or No is unmapped.
-> Build Artifacts/issue_pages/mail_flags.json. Scans every extract: allow several minutes.
"""
import collections, io, json, sys, zipfile

import pandas as pd

from common import R, work_dir  # noqa: E402

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
    member = next((n for n in zf.namelist() if "-ODD" in n or "_v2_" in n.lower()), None)
    if not member:
        continue
    counts, total = collections.Counter(), 0
    try:
        for ch in pd.read_csv(io.TextIOWrapper(zf.open(member), encoding="latin-1", newline=""), skiprows=4,
                              dtype=str, usecols=lambda c: c.strip() == "Mailable?", chunksize=200000,
                              on_bad_lines="skip"):
            if ch.shape[1] == 0:
                break
            s = ch.iloc[:, 0].fillna("").str.replace("\x00", "", regex=False).str.strip()
            total += len(s)
            bad = s[~s.str.lower().isin(["yes", "no"])]
            counts.update(v if v else "(blank)" for v in bad)
    except Exception as e:
        out[cid] = {"error": str(e)[:120]}
        continue
    if total == 0:
        out[cid] = {"error": "no Mailable? column"}
    elif counts:
        out[cid] = {"accounts": total, "unmapped": sum(counts.values()), "values": dict(counts.most_common(8))}
json.dump(out, open(S / "mail_flags.json", "w", encoding="utf-8"), indent=1)
print("mail_flags.json:", len([k for k, v in out.items() if v.get("values")]), "clients with unmapped Mail Flags;",
      "errors:", {k: v["error"] for k, v in out.items() if "error" in v})
