"""Every month on the client-reports share, searched for the Missing Workbook clients -> missing_wb_history.json.

    python scripts/issue_pages/missing_wb_history.py

Aaron, 2026-09-15: for the clients listed as Missing Workbook, look through each CSM's folders in
previous months for an ARS workbook. The ODD and Workbook Issues page says whether one ever landed and
what did land there instead. Layout scanned: `<reports share>/<YYYY.MM>/<account manager>/<id>-...`.
Off VPN the share is unreachable; the previous file is kept and the page says what it last knew.
"""
import json, os, re

from common import work_dir  # noqa: E402
import deck_status as DS  # noqa: E402

MONTH_RX = re.compile(r"^\d{4}\.\d{2}$")


def is_ars_workbook(name):
    low = name.lower()
    return "workbook" in low and "invitation checking" not in low


def scan(root, ids):
    """{'months': [...], 'all': {id: [[month, account manager, file]]}, 'hits': {id: [...ARS workbooks]}}."""
    ids = set(ids)
    all_, hits = {}, {}
    months = sorted(m for m in os.listdir(root) if MONTH_RX.match(m) and os.path.isdir(os.path.join(root, m)))
    for m in months:
        mdir = os.path.join(root, m)
        for am in sorted(os.listdir(mdir)):
            adir = os.path.join(mdir, am)
            if not os.path.isdir(adir):
                continue
            for name in sorted(os.listdir(adir)):
                cid = name.split("-", 1)[0]
                if cid not in ids:
                    continue
                all_.setdefault(cid, []).append([m, am, name])
                if is_ars_workbook(name):
                    hits.setdefault(cid, []).append([m, am, name])
    return {"months": months, "all": all_, "hits": hits}


def main():
    S = work_dir()
    d = json.load(open(S / "gaps.json", encoding="utf-8"))
    C = {c["id"]: c for c in d["clients"]}
    ids = sorted({i["id"] for i in d["issues"]
                  if "no program inputs" in i["issue"] and C.get(i["id"], {}).get("odd_current")})
    if not os.path.isdir(DS.SRC_REPORTS):
        print(f"missing_wb_history: {DS.SRC_REPORTS} is not reachable (VPN?); keeping the previous file")
        return 0
    out = scan(DS.SRC_REPORTS, ids)
    json.dump(out, open(S / "missing_wb_history.json", "w", encoding="utf-8"), indent=1)
    print(f"missing_wb_history.json: {len(ids)} clients, {len(out['months'])} month folders, "
          f"{len(out['hits'])} with an ARS workbook somewhere")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
