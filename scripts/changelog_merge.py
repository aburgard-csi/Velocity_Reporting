#!/usr/bin/env python3
"""changelog_merge.py — resolve a CHANGELOG.md merge conflict by keeping both sides (Aaron, 2026-10-28).

Every branch adds its own entry at the top of CHANGELOG.md, so two branches merged into each other conflict in the
same place, and the right resolution is always the same: keep BOTH entries. Doing it by hand cost a blank line
between entries more than once and, once, a stray backspace character from a PowerShell string. This does it the one
way, keeps the file's line endings, and refuses to leave a marker behind.

    python scripts/changelog_merge.py [CHANGELOG.md]

It exits 1 and changes nothing when the file has no conflict markers, or when a marker is malformed. It prints each
entry heading it kept and warns about any entry with no `Summary:` line (CLAUDE.md: every entry starts with one).
The Git merge itself, the tests and the commit stay with the caller. Import-safe.
"""
import re
import sys

_MARKER = re.compile(r"^(<<<<<<<[^\r\n]*|=======|>>>>>>>[^\r\n]*)\r?\n", re.M)
_HEADING = re.compile(r"^### ", re.M)


def resolve(text):
    """The text with every conflict resolved by keeping both sides, and entries separated by a blank line.

    Raises ValueError when the markers do not pair up (a conflict that is not an add/add of entries)."""
    opens = len(re.findall(r"^<<<<<<<", text, re.M))
    mids = len(re.findall(r"^=======\s*$", text, re.M))
    closes = len(re.findall(r"^>>>>>>>", text, re.M))
    if not (opens == mids == closes) or opens == 0:
        raise ValueError(f"{opens} '<<<<<<<', {mids} '=======', {closes} '>>>>>>>': not a conflict to resolve")
    out = _MARKER.sub("", text)
    nl = "\r\n" if "\r\n" in out else "\n"
    # an entry heading must follow a blank line, whatever side it came from
    out = re.sub(r"([^\r\n])(\r?\n)(### )", lambda m: m.group(1) + m.group(2) + nl + m.group(3), out)
    return out


def entries(text):
    """[(heading, has_summary)] for every `### ` entry in the file."""
    parts = _HEADING.split(text)[1:]
    res = []
    for p in parts:
        head = p.splitlines()[0].strip() if p.strip() else ""
        res.append((head, bool(re.search(r"^Summary:", p, re.M))))
    return res


def main(argv=None):
    path = (argv or sys.argv[1:] or ["CHANGELOG.md"])[0]
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    try:
        new = resolve(text)
    except ValueError as e:
        print(f"Not changed: {e}")
        return 1
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    seen = entries(new)
    print(f"Kept both sides; {len(seen)} entries in the file. The top five:")
    for head, ok in seen[:5]:
        print(f"  {'ok ' if ok else 'NO Summary: line'}  {head}")
    missing = [h for h, ok in seen[:8] if not ok]
    if missing:
        print("Warning: an entry has no 'Summary:' line (CLAUDE.md requires one).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
