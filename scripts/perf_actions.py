#!/usr/bin/env python3
"""
perf_actions.py — the CSM action items on the performance page, for current ARS clients.

Aaron, 2026-09-15: "If we have unmapped values for current ARS clients the CSM needs to contact
the client to get those fixed. The CSM also needs to create a new lift matrix if the current one
is out of date."

Two kinds of item:

  Lift matrix      the data team flags a workbook whose Lift Matrix is out of date in its
                   FILENAME ("LM EXPIRED", "NEEDS LIFT MATRIX", "NEW LIFT MATRIX NEEDED"). That
                   flag is the rule (Aaron chose it over the Lift Matrix tab's own end date).
  Codes not mapped a value in the client's ODD that the client's code table in the ARS database
                   does not list. Terms follow the VIP Data Specification (DDA Master File):
                   "Reg E Codes not mapped" (field 70), "Account Status Codes not mapped"
                   (field 33), and product codes (field 32).

**Nothing here maps a value.** An unmapped code is corrected on the client's code sheet by the
CSM, never forced in the pipeline (Aaron, 2026-09-15: "don't force any mapping. those should be
corrected on each client's code sheet"). So the page lists the values and their account counts,
and does not suggest what they mean.

The code tables come from `scripts/ars_code_tables.py`. The ODD values come from the Client
overview's pass over each extract (`perf_overview`), so no extract is read twice.
"""
import re

LIFT_MATRIX_RX = re.compile(
    r"LM[\s_-]*EXPIRED|NEW[\s_-]+LIFT[\s_-]+MATRIX[\s_-]+NEEDED|NEEDS?[\s_-]+(?:A[\s_-]+)?(?:NEW[\s_-]+)?LIFT[\s_-]+MATRIX",
    re.I)

# page label, ODD overview key, code table key
CODE_KINDS = (
    ("Reg E Codes not mapped", "reg_e", "rege_codes"),
    ("Account Status Codes not mapped", "status", "status_codes"),
    ("Product Codes not mapped", "product", "product_codes"),
)
NO_PB_FLAG = "Product codes with no Personal/Business flag"     # is_business blank on the code sheet
MAIL_FLAG = "Mail Flags not mapped"                              # Mailable? other than Yes/No

# The code sheet maps Product (with its Personal/Business flag), Account Status, Mail Flag and Reg E.
# Product and Account Status decide ARS eligibility, so they list first. Mail Flag decides who is
# mailed but not eligibility: on 12 clients about 99% of otherwise-eligible Mailable?=No accounts
# are Elig=Yes (Aaron, 2026-09-15). Reg E decides neither.
ORDER = ("product", "pb_flag", "status", "mail", "reg_e")
ELIGIBILITY = {"product", "pb_flag", "status"}


def lift_matrix_flag(workbook_name):
    """The data team's out-of-date Lift Matrix flag in a workbook filename, as written, or None."""
    m = LIFT_MATRIX_RX.search(workbook_name or "")
    return m.group(0).replace("_", " ").strip() if m else None


def unmapped(values, table):
    """Values the table does not list, most accounts first: [{value, accounts, open, desc}].

    `values` is perf_overview's {value: [accounts, open accounts, desc]}; `table` the client's
    {code: {...}} from the ARS database. Codes are compared exactly, as the database stores them.
    """
    listed = set(table or {})
    out = [{"value": v, "accounts": n[0], "open": n[1], "desc": (n[2] if len(n) > 2 else "") or ""}
           for v, n in (values or {}).items() if v not in listed]
    return sorted(out, key=lambda r: (-r["accounts"], r["value"]))


def client_actions(cid, overview, tables, ars):
    """The action items for one current ARS client.

    {"lift_matrix": {"flag", "workbook"} | None,
     "codes": [{"label", "kind", "values": [...], "no_table": bool}],   only kinds with an item
     "unchecked": [reason, ...],                                          what could not be checked
     "count": number of items}
    """
    ars = ars or {}
    wb = ars.get("workbook")
    flag = lift_matrix_flag(wb)
    out = {"lift_matrix": {"flag": flag, "workbook": wb} if flag else None, "codes": [], "unchecked": []}
    codes = (overview or {}).get("codes") if isinstance(overview, dict) else None
    if not isinstance(overview, dict) or "missing" in overview:
        out["unchecked"].append("codes: %s" % ((overview or {}).get("missing") or "no ODD extract"))
    elif not codes:
        out["unchecked"].append("codes: the ODD overview predates the code check")
    elif tables is None:
        out["unchecked"].append("codes: no ARS database code tables in Inputs/ARS Settings")
    else:
        for label, okey, tkey in CODE_KINDS:
            values = codes.get(okey)
            if values is None:
                out["unchecked"].append("%s: the ODD extract has no such column" % label)
                continue
            table = (tables.get(tkey) or {}).get(cid)
            miss = unmapped(values, table)
            if miss:
                out["codes"].append({"label": label, "kind": okey, "values": miss, "no_table": not table})
        # Personal/Business is part of the product mapping, set per product code on the code sheet
        # (Aaron, 2026-09-15). A product code the client's ODD uses whose row carries no
        # is_business value is listed; one missing from the table altogether is already above.
        products = codes.get("product")
        table = (tables.get("product_codes") or {}).get(cid) or {}
        if products is not None and table:
            miss = unmapped({v: n for v, n in products.items()
                             if v in table and (table[v].get("is_business") or "") not in ("0", "1")}, {})
            if miss:
                out["codes"].append({"label": NO_PB_FLAG, "kind": "pb_flag", "values": miss, "no_table": False})
        # The ODD's Mailable? is already the database's mapped answer, Yes or No; the raw mail codes
        # are not in the extract, so this is the check there is. Anything else, a blank included,
        # is a mail flag the code sheet does not map.
        mail = codes.get("mail")
        if mail is None:
            out["unchecked"].append("%s: the ODD extract has no Mailable? column" % MAIL_FLAG)
        else:
            miss = unmapped({v: n for v, n in mail.items() if v.strip().lower() not in ("yes", "no")}, {})
            if miss:
                out["codes"].append({"label": MAIL_FLAG, "kind": "mail", "values": miss, "no_table": False})
        out["codes"].sort(key=lambda c: ORDER.index(c["kind"]))
        for c in out["codes"]:
            c["eligibility"] = c["kind"] in ELIGIBILITY
    out["count"] = (1 if flag else 0) + len(out["codes"])
    return out
