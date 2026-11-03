#!/usr/bin/env python3
"""peer_tables.py — the per-client rows behind the peer comparisons that the existing sheets do not carry.

Added 2026-11-03 (Aaron: "enhance the peer comparisons - revenue per account for ICS, response rate for ARS, improved
swipe/spend for ARS"). ICS referrals, MRPC enrollments and CashPlease loans already have per-client rows in
`review_page/peer_pool.py` (the VIP sheets, the MRPC weekly, the CashPlease packs). Two sources were missing:

  ICS workbooks   Inputs/ICS Workbooks/<id>-<yyyy.mm>-*.xlsx, one per client (about 27 of the ICS book). The Monthly Detail
                  tab gives each opening-month cohort's accounts and revenue by source. `ics_revenue` is the ICS deck's own
                  "revenue per account per month by source" arithmetic (build_ics_gen: revenue over account-months, every
                  cohort, program to date), so the peer row and the deck's slide cannot state two figures. Reading a
                  workbook takes seconds over the share, so a row is CACHED by the file's size and modified time
                  (`Build Artifacts/peer_tables/ics_revenue.json`) and only a changed workbook is read again.
  ARS data packs  Build Artifacts/launcher/<period>/<id>/{metrics,base}.json, the files a deck build leaves behind: the
                  deck's own response rate (metrics_gen.mail_summary), responder before/after (before_after.py), tier
                  movement, swipes and spend per eligible account, Reg E, take rate, retention and active cards. Every
                  client that was built has one; the newest pack at or before the period is the client's row. They are
                  small, so they are read directly, not cached. No ODD extract is opened for a peer.

Nothing here is scheduled: the watch at 08:00 is unchanged. `scripts/peer_tables.py` refreshes the ICS cache by hand and
prints what each table holds; any deck or Live Review run refreshes a stale entry itself.

Import-safe: nothing is read until a function is called.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import month_complete as MC                                  # noqa: E402

CACHE_ENV = "RPE_PEER_TABLES_DIR"      # a folder to keep the caches in, instead of Build Artifacts/peer_tables
ICS_MIN_ACCOUNT_MONTHS = 2000          # a program with fewer account-months than this has no stable revenue per account
ICS_MAX_AGE_MONTHS = 3                 # a peer's workbook may be this many months older than the client's
ARS_MIN_OFFERS = 1000                  # offers sent in the window for a response rate to mean anything
ARS_MIN_MAILED = 500                   # ... and in one mailing for the by-mailing rate
ARS_MIN_RESPONDERS = 100               # responders behind a before/after or tier-movement figure
ARS_WINDOW = 12                        # months of mailings pooled for the response rate


def cache_dir(root=None):
    env = os.environ.get(CACHE_ENV)
    if env:
        return Path(env)
    if root is not None:
        return Path(root) / "peer_tables"
    import rpe_env
    return rpe_env.build_artifacts() / "peer_tables"


# ================================================================= ICS: revenue per account per month
def ics_revenue(mdf):
    """The ICS deck's revenue per account per month by source, from a workbook's `monthly_detail_full` block, or None.

    Account-months = sum over cohorts of accounts opened x months open, the newest cohort counting one month
    (build_ics_gen: `am = sum(accounts_opened[i] * (n - i))`). Sources: interchange; spread on deposits; NSF/OD and other
    fees together (the deck's third bucket); and the total of the three. A source whose revenue is exactly zero across the
    whole program is not carried by that workbook (the row was never filled) and is left out, not compared as $0.00.
    Returns None when the program has fewer than ICS_MIN_ACCOUNT_MONTHS account-months."""
    if not mdf or not mdf.get("months"):
        return None
    n = len(mdf["months"])
    opened = mdf.get("accounts_opened") or []
    if len(opened) != n:
        return None
    am = sum(opened[i] * (n - i) for i in range(n))
    if am < ICS_MIN_ACCOUNT_MONTHS:
        return None
    ic = sum(mdf.get("interchange") or [])
    sp = sum(mdf.get("spread") or [])
    nso = sum(mdf.get("nsf_od") or []) + sum(mdf.get("other_fees") or [])
    out = {"account_months": am, "accounts": sum(opened)}
    for key, v in (("rev_interchange", ic), ("rev_spread", sp), ("rev_nsf_od", nso)):
        if v:
            out[key] = v / am
    if ic or sp or nso:
        out["rev_total"] = (ic + sp + nso) / am
    return out


def newest_ics_workbooks(folder):
    """{client id: (period, path)}: the newest workbook per client (a later period wins; at one period the later name, so
    v1.7.2 beats v1.7.1). Lock files (`~$`) are skipped."""
    best = {}
    for f in glob.glob(os.path.join(str(folder), "*.xlsx")):
        b = os.path.basename(f)
        if b.startswith("~$"):
            continue
        m = re.match(r"^(\d{3,5})-(\d{4}\.\d{2})-", b)
        if not m:
            continue
        cur = best.get(m.group(1))
        if not cur or (m.group(2), b) > (cur[0], os.path.basename(cur[1])):
            best[m.group(1)] = (m.group(2), f)
    return best


def _read_workbook(path):
    """(monthly_detail_full, data month 'YYYY-MM' or None) from one ICS workbook, through the ICS extractor."""
    sys.path.insert(0, os.path.join(HERE, "ics_pipeline"))
    import ics_workbook_extract as X
    d = X.extract(str(path))
    mm = MC.month_start(d.get("_workbook_month"))
    return d.get("monthly_detail_full"), (mm.strftime("%Y-%m") if mm else None)


def ics_revenue_rows(folder=None, cache=None, read=None, refresh=True):
    """{client id: {"period","month","file","vals": {metric: value}}} for the newest ICS workbook of every client.

    `cache` is the cache folder (see `cache_dir`); a client's entry is reused while its file's size and modified time are
    unchanged. A workbook that cannot be read, or has too few account-months, is a client with no row. `read` is the
    function that opens a workbook (tests pass a stub). Reads and writes fail soft: no share, no cache, an empty table."""
    if folder is None:
        import rpe_env
        folder = rpe_env.input_dir("ICS workbook", create=False)
    read = read or _read_workbook
    cdir = Path(cache) if cache else cache_dir()
    cfile = cdir / "ics_revenue.json"
    try:
        old = json.loads(cfile.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    out, new, changed = {}, {}, False
    for cid, (period, path) in sorted(newest_ics_workbooks(folder).items()):
        try:
            st = os.stat(path)
        except OSError:
            continue
        sig = [st.st_size, int(st.st_mtime)]
        ent = old.get(cid)
        if ent and ent.get("sig") == sig and ent.get("file") == os.path.basename(path):
            new[cid] = ent
        elif not refresh:
            continue
        else:
            try:
                mdf, month = read(path)
                vals = ics_revenue(mdf)
            except BaseException:
                vals, month = None, None
            new[cid] = {"sig": sig, "file": os.path.basename(path), "period": period, "month": month, "vals": vals}
            changed = True
        if new[cid].get("vals"):
            out[cid] = {k: new[cid][k] for k in ("period", "month", "file", "vals")}
    if changed or set(new) != set(old):
        try:
            cdir.mkdir(parents=True, exist_ok=True)
            tmp = cfile.with_suffix(".tmp")
            tmp.write_text(json.dumps(new), encoding="utf-8")
            os.replace(tmp, cfile)
        except OSError:
            pass
    return out


def months_between(a, b):
    """Whole months from 'YYYY.MM' / 'YYYY-MM' `a` to `b` (b later is positive)."""
    da, db = MC.month_start(str(a).replace(".", "-")), MC.month_start(str(b).replace(".", "-"))
    if not da or not db:
        return None
    return (db.year - da.year) * 12 + db.month - da.month


# ================================================================= ARS: the data packs
def _num(v):
    return None if isinstance(v, bool) or not isinstance(v, (int, float)) else float(v)


def window_months(end_label, k=ARS_WINDOW):
    """The `k` month labels ending at `end_label` ('Sep 2026'), oldest first, as 'Mon YYYY'."""
    d = MC.month_start(end_label)
    if not d:
        return []
    out = []
    for i in range(k - 1, -1, -1):
        y, m = divmod(d.year * 12 + d.month - 1 - i, 12)
        out.append(MC.label(f"{y:04d}-{m + 1:02d}"))
    return out


def ars_metrics(m, base=None):
    """One client's ARS peer row from its data packs: {"activity", "point": {...}, "series": {...}}.

    Every figure is read from the pack the deck was built from; nothing is recomputed from an ODD extract:
      resp_12m       responders over offers sent, personal accounts, mailings in the 12 months to the activity month
                     (the deck's Mailing Response Summary arithmetic, pooled); offers >= ARS_MIN_OFFERS
      resp_rate      by mailing month, the deck's Response % (offers >= ARS_MIN_MAILED)
      spend_gain     responders' monthly debit spend, 3 months before a mailing against the 6 after (before_after.py),
                     percent change; only a pack whose windows are 3 and 6 months
      spend_after    the same, the after side in dollars a month
      moved_up       of repeat responders to the latest mailing, the share who reached a higher swipe tier than in their
                     previous response (the deck's Movement slide: Improved / (Improved + Same + Declined))
      swipes_per_acct, spend_per_acct   3-month average monthly debit swipes / spend per ARS-eligible account
      rege_pct, rege_new_pct   Reg E opt-in among open personal debit accounts / among those opened in the last 12 months
      take_new_pct   share of new eligible accounts holding a debit card
      active_cards   share of open personal card holders swiping in the month
      ret_1yr        one-year account survival (Kaplan-Meier)
      rev_per_1k     incremental ARS revenue a month per 1,000 eligible accounts, average of the last 12 months (workbook)
    """
    activity = m.get("activity_month")
    point, series = {}, {}
    rows = m.get("mail_summary") or []
    ok = []
    for r in rows:
        try:
            ok.append((r[0], float(r[1]), float(r[2]), float(r[5])))
        except (IndexError, TypeError, ValueError):
            continue
    if activity:
        win = set(window_months(activity))
        sent = sum(r[1] for r in ok if MC.label(r[0]) in win)
        rs = sum(r[2] for r in ok if MC.label(r[0]) in win)
        if sent >= ARS_MIN_OFFERS:
            point["resp_12m"] = 100.0 * rs / sent
    series["resp_rate"] = {MC.label(r[0]): r[3] for r in ok if r[1] >= ARS_MIN_MAILED}
    b, a = _num(m.get("ba_spend_before")), _num(m.get("ba_spend_after"))
    if (b and a and m.get("ba_before_months") == 3 and m.get("ba_after_months") == 6
            and (m.get("ba_n_mailings") or 0) >= 1):
        point["spend_gain"] = 100.0 * (a - b) / b
        point["spend_after"] = a
    mv = {k: v for k, v in (m.get("movement") or [])}
    base_n = sum(mv.get(k, 0) for k in ("Improved", "Same", "Declined"))
    if base_n >= ARS_MIN_RESPONDERS:
        point["moved_up"] = 100.0 * mv.get("Improved", 0) / base_n
    tot = m.get("swipe_tier_total") or []
    if len(tot) >= 3 and tot[0]:
        point["swipes_per_acct"] = tot[1] / tot[0]
        point["spend_per_acct"] = tot[2] / tot[0]
    for key, src in (("rege_pct", "rege_pct"), ("rege_new_pct", "rege_new_pct"), ("take_new_pct", "take_new_pct"),
                     ("active_cards", "book_active_pct"), ("ret_1yr", "ret_1yr")):
        v = _num(m.get(src))
        if v is not None:
            point[key] = v
    if m.get("rege_pool", 1) == 0:
        point.pop("rege_pct", None)
    if (m.get("take_new_total") or 0) < 100:
        point.pop("take_new_pct", None)
    if (m.get("rege_new_pool") or 0) < 100:
        point.pop("rege_new_pct", None)
    rev_month = None
    if base:
        last12 = base.get("monthly_rev_last12") or []
        avg, n = _num(base.get("monthly_rev_avg12")), _num(m.get("n_eligible"))
        if len(last12) == 12 and avg and n:
            point["rev_per_1k"] = 1000.0 * avg / n
            rev_month = MC.label(last12[-1][0])
    return {"activity": MC.label(activity) if activity else None, "rev_month": rev_month, "point": point, "series": series}


def ars_pack_dirs(root, period=None):
    """{client id: folder} of the newest launcher folder per client holding a metrics.json, at or before `period`
    ('YYYY.MM') when given."""
    best = {}
    for f in glob.glob(os.path.join(str(root), "launcher", "*", "*", "metrics.json")):
        folder = os.path.dirname(f)
        per = os.path.basename(os.path.dirname(folder))
        cid = os.path.basename(folder)
        if not re.match(r"^\d{4}\.\d{2}$", per) or not re.match(r"^\d{3,5}$", cid):
            continue
        if period and per > period:
            continue
        if cid not in best or per > best[cid][0]:
            best[cid] = (per, folder)
    return {c: (p, d) for c, (p, d) in best.items()}


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ars_rows(root, period=None):
    """{client id: {"pack_period", "activity", "point", "series"}} for every client with a launcher pack."""
    out = {}
    for cid, (per, folder) in ars_pack_dirs(root, period).items():
        m = _json(Path(folder) / "metrics.json")
        if not isinstance(m, dict) or not m.get("mail_summary"):
            continue
        row = ars_metrics(m, _json(Path(folder) / "base.json"))
        row["pack_period"] = per
        out[cid] = row
    return out
