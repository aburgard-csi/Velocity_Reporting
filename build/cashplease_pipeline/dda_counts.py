#!/usr/bin/env python3
"""
dda_counts.py — parse the weekly "ILS Management Server DDA Count" email.

The ILS Hosted Server sends a fixed-width table every Thursday (forwarded by Charles
Baker): client id + name, the DDA account count most recently imported into the ILS
Data Warehouse, and the date that import last ran.

Two things about this source drive everything downstream:

  * **A count can be NULL**, and a client can be absent entirely. CashPlease clients
    who are not on ILS have no row here at all. Neither case is a zero.
  * **`Last Updated On` is per client and some are badly stale** — the 2026-08-27
    send still carried 1044 Trustmark from 2026-04-09. A denominator four months old
    is not wrong, but it is not current either, and a rate built on it has to say so.
    The staleness is carried through to the deck rather than dropped here.

Usage:
    python dda_counts.py <email_body.txt> <out.json>
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# '1002 - Republic Bank        236054      08/21/2026'
# The separator varies: '1840- FNB Kentucky' and '1842-bankcda' both appear.
ROW = re.compile(
    r"^(?P<cid>\d+)\s*-\s*(?P<name>.+?)\s{2,}"
    r"(?P<count>NULL|[\d,]+)\s*"
    r"(?P<updated>\d{2}/\d{2}/\d{4})?\s*$"
)
SENT = re.compile(r"^Sent:\s*\w+,\s*(?P<d>\w+ \d{1,2}, \d{4})")


def parse(text):
    sent = None
    rows, nulls = {}, []
    for line in text.splitlines():
        line = line.rstrip()
        if sent is None:
            m = SENT.match(line.strip())
            if m:
                try:
                    sent = datetime.strptime(m.group("d"), "%B %d, %Y").date().isoformat()
                except ValueError:
                    pass
                continue
        m = ROW.match(line)
        if not m:
            continue
        cid = m.group("cid")
        raw = m.group("count")
        if raw == "NULL":
            nulls.append(f"{cid} {m.group('name').strip()}")
            continue
        updated = m.group("updated")
        iso = None
        if updated:
            try:
                iso = datetime.strptime(updated, "%m/%d/%Y").date().isoformat()
            except ValueError:
                iso = None
        rows[cid] = {
            "client_id": cid,
            "ils_name": m.group("name").strip(),
            "dda_accounts": int(raw.replace(",", "")),
            "last_updated": iso,
        }
    return {"sent": sent, "clients": rows, "null_counts": nulls}


def age_days(pack, cid, asof):
    """How stale the denominator is, in days, or None when it cannot be told."""
    rec = pack["clients"].get(cid)
    if not rec or not rec.get("last_updated"):
        return None
    try:
        return (date.fromisoformat(asof) - date.fromisoformat(rec["last_updated"])).days
    except ValueError:
        return None


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__.strip())
    text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    pack = parse(text)
    Path(sys.argv[2]).write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(f"sent {pack['sent']}: {len(pack['clients'])} clients with a DDA count, "
          f"{len(pack['null_counts'])} NULL")
    stale = [(c["client_id"], c["ils_name"], c["last_updated"])
             for c in pack["clients"].values()
             if c["last_updated"] and c["last_updated"] < "2026-08-01"]
    print(f"{len(stale)} counts last imported before 2026-08-01")


if __name__ == "__main__":
    main()
