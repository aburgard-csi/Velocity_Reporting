#!/usr/bin/env python3
"""mrpc_weekly.py — the ONE reader of Bradford Sanders' MRPCEnrollmentSummary weekly.

The weekly carries one tab per client (`<id>-<Name>`), and two places read it: the
performance dashboard (`scripts/refresh_performance_dashboard.py`) and, since 2026-10-02,
the MRPC deck's "Program to Date" and "Current Program Status" slides. It used to live inside
the dashboard script; it moved here so the deck and the page cannot read it two ways.

Why the deck reads it (Aaron, 2026-10-02: "go ahead with the two new MRPC slides using the
weekly"). The deck's Key Metrics used VIP's `active_enrollments` (4,396 for Marine FCU 1539)
and Card Portfolio's "Total Cards Billed" (6,729). Neither was current: the active count had
no date or source and had been carried forward unreconciled, and 6,729 is VIP's "Total Fees by
Fee Charged" — accounts per fee amount over an unknown window, more than double every current
active count. The weekly's own figures reconcile with each other and with VIP's aging summary
(Marine, 9/27/2026: 2,755 active accounts, 2,825 active cardholders, 7,942 cardholders and
7,408 accounts enrolled to date). This replaces the 2026-07-25 decision to show VIP's Active
Enrollments as-is.

What each figure is, as the weekly labels it:
    all_mrpc_accounts       accounts ever enrolled ("All MRPC Accounts")
    active_mrpc_accounts    accounts active/signed now ("Active/Signed MRPC Accounts")
    all_cardholders         primary + joint cardholders ever enrolled
    active_cardholders      primary + joint cardholders active now
    cardholders_active_buckets  active cardholders by days since enrollment, plus inactive
    totals                  program-to-date cardholders by tier / role / channel / new vs
                            existing account / employee — each set sums to all_cardholders
    monthly                 enrollments per COMPLETE month (month_complete), newest last

IMPORT-SAFE: nothing here runs at import.
"""
import glob
import os


def report_glob(reports, pattern):
    """Every match for `pattern` across the report folders, sorted by file name.

    `reports` is a LIST since inputs are sorted into a folder per kind (Aaron, 2026-09-09);
    a single folder is still accepted.
    """
    dirs = [reports] if isinstance(reports, (str, os.PathLike)) else list(reports)
    return sorted((f for d in dirs for f in glob.glob(os.path.join(str(d), pattern))),
                  key=os.path.basename)


def complete_months(rows, generated, key="month"):
    """Rows for months that had ended when the report was generated.

    `generated` is the weekly's stamp ("9/13/2026 8:06:12 AM"), `key` holds "YYYY-MM".
    A month on or after the stamp's month is still in progress and is dropped. An
    unreadable stamp keeps every row rather than guessing.
    """
    # The one definition of "had the month ended" lives in build/month_complete.py
    # (Aaron, 2026-09-17), shared with the deck builders.
    import month_complete
    as_of = month_complete.report_date(generated)
    if as_of is None:
        return list(rows)
    return [r for r in rows if month_complete.month_ended(str(r.get(key, "")), as_of) is not False]


class MrpcWeekly:
    """The newest MRPCEnrollmentSummary weekly, one tab per client.

    `reports` is the folder list to search (rpe_env.report_dirs() when omitted).
    """

    def __init__(self, reports=None):
        import openpyxl
        if reports is None:
            import rpe_env
            reports = rpe_env.report_dirs()
        hits = report_glob(reports, "*MRPCEnrollmentSummary*.xlsx")
        self.path = hits[-1] if hits else None
        self.tabs = {}
        if self.path:
            self.wb = openpyxl.load_workbook(self.path, read_only=True, data_only=True)
            self.tabs = {s[:4]: s for s in self.wb.sheetnames
                         if s[:4].isdigit() and not s.endswith(("-Loans", "-Issues"))}

    @property
    def name(self):
        return os.path.basename(self.path) if self.path else None

    def client(self, cid):
        cid = str(cid)
        if cid not in self.tabs:
            return None
        ws = self.wb[self.tabs[cid]]
        rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))
        gen = str(rows[5][1] or "").replace("Report Generated:", "").strip()
        kv, take = {}, {}
        for r in rows[7:60]:
            if isinstance(r[15], str) and r[21] is not None:
                kv[r[15].strip()] = r[21]
            if r[15] == "New Account Take Rates":
                take["ptd_label"], take["cur_label"] = r[18], r[21]
            if r[15] == "New Accounts Opened":
                take["ptd_opened"], take["cur_opened"] = r[18], r[20]
            if r[15] == "New Accounts Enrolled":
                take["ptd_enrolled"], take["ptd_rate"] = r[18], r[19]
                take["cur_enrolled"], take["cur_rate"] = r[20], r[21]
        hdr_i = next(i for i, r in enumerate(rows) if r[1] == "Enroll Date")
        tot = next(r for r in rows if r[1] == "TOTAL ")
        ah = next((r for r in rows if r[1] == "TOTAL ACCOUNTHOLDERS"), None)
        monthly = []
        for r in rows[hdr_i + 1:]:
            lab = r[1]
            if not isinstance(lab, str) or not lab.endswith("*") or "roll-up" in lab.lower():
                continue
            mm, dd, yy = lab.rstrip("*").split("/")
            monthly.append({
                "platinum": r[2] or 0, "gold": r[3] or 0, "business": r[4] or 0,
                "primary": r[6] or 0, "joint": r[7] or 0, "web_branch": r[9] or 0,
                "web_enduser": r[10] or 0, "phone": r[11] or 0, "paper": r[12] or 0,
                "existing": r[14] or 0, "new": r[15] or 0, "employees": r[17] or 0,
                "non_employees": r[18] or 0, "month": f"{yy}-{mm}"})
        monthly.sort(key=lambda r: r["month"])
        return {
            "file": self.name, "tab": self.tabs[cid], "report_generated": gen,
            "open_with_debit": kv.get("Open/Active Accounts w/ Debit Card"),
            "open_without_debit": kv.get("Open/Active Accounts w/o Debit Card (Not Factored in Rates Below)"),
            "all_mrpc_accounts": kv.get("All MRPC Accounts"),
            "take_rate_all": kv.get("Take Rate - All MRPC Accounts"),
            "active_mrpc_accounts": kv.get("Active/Signed MRPC Accounts"),
            "take_rate_active": kv.get("Take Rate - Active MRPC Accounts"),
            "all_cardholders": kv.get("All MRPC Primary and Joint Card Holders"),
            "active_cardholders": kv.get("Active MRPC Primary and Joint Card Holders"),
            "take_rate_active_cardholders": kv.get("Take Rate - Active MRPC Primary and Joint Card Holders"),
            "new_account_take": take,
            "totals": {"platinum": tot[2], "gold": tot[3], "business": tot[4], "primary": tot[6],
                       "joint": tot[7], "web_branch": tot[9], "web_enduser": tot[10],
                       "phone": tot[11], "paper": tot[12], "existing": tot[14], "new": tot[15],
                       "employees": tot[17], "non_employees": tot[18]},
            "cardholders_active_buckets": ({"1-90": ah[10], "91-180": ah[11], "180+": ah[12],
                                            "inactive": ah[13]} if ah else None),
            "monthly": complete_months(monthly, gen)[-24:],
        }
