#!/usr/bin/env python3
"""
ars_code_tables.py — the ARS database's per-client code tables, extracted from a query export.

    python scripts/ars_code_tables.py "<ARS Database Export for Client Settings.txt>"

The ARS database (also the MRPC and ICS settings store) maps each client's core codes: product
codes, Reg E codes and account status codes. When a client's ODD carries a code the client's
table does not list, the CSM has to have the client correct it on their code sheet (Aaron,
2026-09-15). The performance page's CSM action items compare each current ARS client's ODD with
these tables, and this script is how the tables get to the share.

**Only the code tables are kept.** The export is SQL Server's text output of one query with
several result sets. The first is the client SETTINGS table, which carries plaintext FTP
passwords, salts and IVs; it is never parsed past its header, never copied, and never
committed (Aaron, 2026-09-15: "Keep only the code tables"). Each table is found by its id
column, not by position, and only the columns named in KEEP are read, so a reordered or widened
export cannot carry a settings column into the output.

Mail codes are in the export too but are left out: the ODD carries no raw mail code to check
against them, only `Mailable?`, which the database has already mapped to Yes/No (1226, 1615 and
1204 on 2026-09-15). The Mail Flag check reads that column instead (perf_actions).

Writes `Inputs/ARS Settings/ars_code_tables.json` (rpe_env kind "ARS codes"), replaced in place.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build"))
import rpe_env as R                                              # noqa: E402

OUT_NAME = "ars_code_tables.json"

# table key: (id column that identifies it, code column, other columns kept)
KEEP = {
    "product_codes": ("product_code_id", "product_code",
                      ("description", "is_business", "eligible_for_debit_card", "actively_offered_product")),
    "rege_codes": ("rege_code_id", "rege_code", ("description", "optinstatus")),
    "status_codes": ("status_code_id", "status", ("description", "active")),
}
_DASHES = re.compile(r"^-+( -+)*\s*$")


def _spans(dash_line):
    return [(m.start(), m.end()) for m in re.finditer(r"-+", dash_line)]


def _value(line, span):
    v = line[span[0]:span[1]].strip()
    return None if v == "NULL" else v


def parse_export(text):
    """{table key: {client_id: {code: {column: value}}}} for the tables in KEEP."""
    lines = text.replace("\r\n", "\n").split("\n")
    out = {}
    for i, dash in enumerate(lines):
        if i == 0 or not _DASHES.match(dash) or "-" not in dash:
            continue
        spans = _spans(dash)
        header = [lines[i - 1][s:e].strip() for s, e in spans]
        key = next((k for k, (idcol, _c, _o) in KEEP.items() if header and header[0] == idcol), None)
        if key is None:
            continue                        # the settings table, mail codes, anything unknown
        _idcol, codecol, others = KEEP[key]
        need = ("client_id", codecol) + others
        missing = [c for c in need if c not in header]
        if missing:
            raise ValueError("%s table has no %s column" % (key, ", ".join(missing)))
        at = {c: spans[header.index(c)] for c in need}
        table = out.setdefault(key, {})
        for line in lines[i + 1:]:
            if not line.strip() or re.match(r"^\(\d+ rows? affected\)", line.strip()):
                break
            cid = _value(line, at["client_id"])
            if not cid or not cid.isdigit():
                raise ValueError("%s table: unexpected client_id %r" % (key, cid))
            code = _value(line, at[codecol]) or ""
            table.setdefault(cid, {})[code] = {c: _value(line, at[c]) for c in others}
    absent = [k for k in KEEP if k not in out]
    if absent:
        raise ValueError("export has no %s table" % ", ".join(absent))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("export", help="the ARS database export (.txt)")
    ap.add_argument("--out", help="default: Inputs/ARS Settings/%s" % OUT_NAME)
    a = ap.parse_args(argv)
    text = Path(a.export).read_text(encoding="utf-8-sig", errors="replace")
    tables = parse_export(text)
    st = os.stat(a.export)
    doc = {
        "_source": {
            "export": os.path.basename(a.export),
            "exported": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "extracted": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tables": sorted(tables),
            "note": "Code tables only. The export's client settings table is never copied.",
        },
        **tables,
    }
    out = Path(a.out) if a.out else R.input_dir("ARS codes") / OUT_NAME
    tmp = out.with_suffix(".json.part")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(out)
    print("wrote %s: %s" % (out, ", ".join("%s %d clients" % (k, len(v)) for k, v in sorted(tables.items()))))


def load(path=None):
    """The extracted code tables, or None when none have been extracted."""
    p = Path(path) if path else R.inputs() / R.INPUT_KIND_DIRS["ARS codes"] / OUT_NAME
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    main()
