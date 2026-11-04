"""
Parser for the ILS Matrix Validation report (query 1822).

parse(path) -> {section_name: {"columns": [...], "rows": [{col: val}, ...]}}

The report is a plain-text dump of many SQL result sets. Two export styles
exist in the wild and both are supported:

  * Newer exports precede each result set with a banner line
    `=== SECTION NAME ===`.
  * Older exports have no banners — just the result sets back to back,
    separated by blank lines.

Every result set is a header row immediately followed by a line of dashes; the
dash runs define the column boundaries. When a banner is present it names the
section; otherwise the section is identified from its column signature, so the
deck builder finds the tables it needs regardless of export style.

Carried over unchanged from the Matrix Deck Generator — it is pure parsing with
no layout in it, and it has been exercised against every client export to date.
"""
import re

# Column signatures -> canonical section name (used when there is no banner).
_SIGNATURES = [
    ({"Account Type", "Matrix Code", "Calc?", "Min", "Max"}, "ACCOUNT TYPES AND MIN/MAX LIMITS"),
    ({"Account Type", "Override Criteria", "Override Value", "Order Index"}, "OVERRIDES"),
    ({"Account Type", "Category", "Range", "Factor"}, "RANGES AND FACTORS"),
    ({"Account Type", "Repository Name", "Calculation", "Factor"}, "TRENDS"),
    ({"Account Type", "Min Value", "Max Value", "Limit Value"}, "TIERS AND ROUNDING"),
    ({"Account Type", "Exclusion Name"}, "EXCLUSIONS"),
    ({"STATUS_CODE", "DESCRIPTION", "CAN_OVERDRAFT"}, "OD STATUS CODE MAPPING"),
    ({"ProdCode", "DESCRIPTION"}, "PRODUCT CODE MAPPING"),
    ({"MATRIX_ID", "MATRIX_CODE", "LOG_DATE"}, "ILS MATRIX CHANGE HISTORY"),
]


def _spans(dash_line):
    """(start, end) character spans for each run of dashes."""
    return [(m.start(), m.end()) for m in re.finditer(r"-+", dash_line)]


def _slice(line, spans):
    out = []
    for i, (s, e) in enumerate(spans):
        seg = line[s:e] if i < len(spans) - 1 else line[s:]   # last col -> end of line
        out.append(seg.strip())
    return out


def _infer_name(columns, used):
    cols = set(c for c in columns if c)
    for sig, name in _SIGNATURES:
        if sig <= cols and name not in used:
            return name
    return None


def parse(path):
    """Parse an ILS Matrix Validation .txt export into a dict of sections."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()
    sections = {}
    pending_banner = None
    unnamed = 0
    i = 0
    while i < len(lines):
        ln = lines[i]

        m = re.match(r"^===\s*(.*?)\s*===\s*$", ln)
        if m:
            pending_banner = m.group(1)
            i += 1
            continue

        # a header line immediately followed by a dashed separator starts a block
        if (i + 1 < len(lines)
                and re.match(r"^[-\s]+$", lines[i + 1]) and "-" in lines[i + 1]):
            spans = _spans(lines[i + 1])
            cols = _slice(lines[i], spans)
            j = i + 2
            rows = []
            while j < len(lines):
                r = lines[j]
                if r.strip() == "" or re.match(r"^\(\d+ rows? affected\)", r.strip()):
                    break
                if re.match(r"^===", r):
                    break
                rows.append(dict(zip(cols, _slice(r, spans))))
                j += 1

            name = pending_banner or _infer_name(cols, sections)
            pending_banner = None
            if name is None:
                unnamed += 1
                name = f"UNNAMED_{unnamed}"
            # keep the first occurrence of a named section
            if name not in sections:
                sections[name] = {"columns": cols, "rows": rows}
            i = j
            continue

        i += 1
    return sections


if __name__ == "__main__":
    import sys
    secs = parse(sys.argv[1])
    print(f"{len(secs)} sections\n")
    for name, d in secs.items():
        cols = [c for c in d["columns"] if c]
        print(f"### {name}  ({len(d['rows'])} rows)   cols: {cols}")
