#!/usr/bin/env python3
"""
lift_extract.py — per-account ODDD extraction for the ARS Lift Matrix.

Streams the raw ODDD (.zip or .csv), projects only the columns the lift
valuation needs, and caches a compact per-account record set.

Per account it captures:
  * tier_swipes  — 3-month average swipes (Sig # + PIN #), the basis the
                   workbook's Segmentation Legend uses to assign a segment.
  * spend12      — 12-month average MONTHLY debit purchases (Sig $ + PIN $).
  * swipes12     — 12-month average MONTHLY swipes.
  * items12      — 12-month average MONTHLY NSF/OD ITEM COUNT (the `MTD`
                   column). Items, not dollars: build_lift_matrix multiplies
                   this BY the per-item NSF fee, so a dollar reading here
                   would price the fee twice. This field was called `fee12`
                   until 2026-09-01; a `.pkl` cached before then must be
                   regenerated.
  * eligibility/status fields for population filtering.

Usage:  python3 lift_extract.py <ODDD.zip|.csv> <out.pkl> [n_tier_months] [n_val_months]
"""
import csv, io, os, pickle, re, sys, zipfile

TIER_MONTHS = 3    # segmentation legend: 3-month average swipes
VAL_MONTHS = 12    # segment values reflect the last 12 months of activity


def open_source(src):
    """Return a factory yielding a fresh text stream over the ODD csv."""
    if src.lower().endswith(".zip"):
        zf = zipfile.ZipFile(src)
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise SystemExit(f"ERROR: no .csv inside {src}")
        # Some ODDD zips also carry the raw monthly transaction file, which is
        # also a .csv — pick the ODD extract, not the transaction dump.
        odd = [n for n in members if "-odd" in n.lower() or "_v2_" in n.lower()]
        member = odd[0] if odd else max(
            members, key=lambda n: zf.getinfo(n).file_size)

        def factory():
            raw = io.TextIOWrapper(zf.open(member), encoding="utf-8",
                                   errors="replace", newline="")
            return (line.replace("\0", "") for line in raw)
        return factory, os.path.basename(member)

    def factory():
        raw = open(src, encoding="utf-8", errors="replace", newline="")
        return (line.replace("\0", "") for line in raw)
    return factory, os.path.basename(src)


def find_header(factory):
    """The ODD carries preamble rows; the real header is the 'Acct ID' row."""
    for i, row in enumerate(csv.reader(factory())):
        if any(str(c).strip() == "Acct ID" for c in row):
            return i, [str(c).strip() for c in row]
        if i > 25:
            break
    raise SystemExit("ERROR: could not locate the 'Acct ID' header row")


def num(s):
    s = (s or "").strip().replace(",", "").replace("$", "")
    if not s or s in ("-", "."):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def extract(src, n_tier=TIER_MONTHS, n_val=VAL_MONTHS):
    factory, base = open_source(src)
    hdr_idx, hdr = find_header(factory)
    idx = {h: i for i, h in enumerate(hdr)}

    months = [m.group(1) for m in
              (re.match(r"^([A-Z][a-z]{2}\d{2}) Sig #$", h) for h in hdr) if m]
    if len(months) < n_val:
        raise SystemExit(f"ERROR: ODD carries {len(months)} months, need {n_val}")
    tier_win = months[-n_tier:]
    val_win = months[-n_val:]

    def col(name):
        return idx.get(name)

    # snapshot eligibility columns are prefixed with the latest month
    elig_c = col(f"{months[-1]} Elig")
    prog_c = col(f"{months[-1]} Prog")
    base_cols = {k: col(k) for k in
                 ("Acct ID", "Branch", "Prod Code", "Prod Desc", "Business?",
                  "Stat Code", "Stat Desc", "Mailable?", "Date Opened",
                  "Date Closed", "Avg Bal", "Curr Bal", "Debit?")}

    tier_cols = [(idx[f"{m} Sig #"], idx[f"{m} PIN #"]) for m in tier_win]
    val_cols = [(idx[f"{m} Sig #"], idx[f"{m} PIN #"],
                 idx[f"{m} Sig $"], idx[f"{m} PIN $"], idx[f"{m} MTD"])
                for m in val_win]

    reader = csv.reader(factory())
    for _ in range(hdr_idx + 1):
        next(reader, None)

    ncol = len(hdr)
    recs = []
    for row in reader:
        if len(row) < ncol:
            continue
        tier_sw = sum(num(row[a]) + num(row[b]) for a, b in tier_cols) / n_tier
        sw = sp = items = 0.0
        for a, b, c, d, e in val_cols:
            sw += num(row[a]) + num(row[b])
            sp += num(row[c]) + num(row[d])
            items += num(row[e])
        rec = {k: (row[v].strip() if v is not None else "")
               for k, v in base_cols.items()}
        rec["elig"] = row[elig_c].strip() if elig_c is not None else ""
        rec["prog"] = row[prog_c].strip() if prog_c is not None else ""
        rec["tier_swipes"] = tier_sw
        rec["swipes12"] = sw / n_val
        rec["spend12"] = sp / n_val
        rec["items12"] = items / n_val
        recs.append(rec)

    meta = {"source_file": base, "months": months, "tier_window": tier_win,
            "val_window": val_win, "n_accounts": len(recs)}
    return meta, recs


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    nt = int(sys.argv[3]) if len(sys.argv) > 3 else TIER_MONTHS
    nv = int(sys.argv[4]) if len(sys.argv) > 4 else VAL_MONTHS
    meta, recs = extract(src, nt, nv)
    pickle.dump((meta, recs), open(out, "wb"), protocol=4)
    print(f"{meta['source_file']}\n  accounts      {meta['n_accounts']:,}"
          f"\n  months        {meta['months'][0]}..{meta['months'][-1]}"
          f" ({len(meta['months'])})"
          f"\n  tier window   {', '.join(meta['tier_window'])}"
          f"\n  value window  {meta['val_window'][0]}..{meta['val_window'][-1]}")
