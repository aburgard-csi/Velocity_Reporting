#!/usr/bin/env python3
"""
obsidian_roster.py — read Aaron's client book out of the Obsidian vault.

Each client folder under `Work/Clients/` holds a note whose YAML frontmatter carries
`client_id`, `client_name`, `products` and `status`. Two shapes of the same field are
in use and both have to be read, because reading only one silently truncates the
answer: Austin Bank 1075 writes `products` as a BLOCK list and a first-item-only
parse reported it as ARS-only when it is on ARS, ICS, ILS and MRPC.

A folder can also hold more than one id-prefixed note (1734 has a proposal email
alongside the client note), so the note is chosen by whether it actually declares
`client_id` — not by sort order.

Usage:
    python obsidian_roster.py [vault_clients_dir] [--json out.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT = Path(r"C:\Obsidian\My Vault\Work\Clients")


def frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    return m.group(1) if m else ""


def scalar(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    return m.group(1).strip() if m else ""


def listfield(fm, key):
    """Read `key: [a, b]` and the block form `key:\\n  - a\\n  - b` alike."""
    inline = scalar(fm, key)
    if inline.startswith("["):
        body = inline.strip()[1:-1]
        return [v.strip().strip("'\"") for v in body.split(",") if v.strip()]
    if inline:
        return [inline.strip().strip("'\"")]
    m = re.search(rf"^{key}:[ \t]*\r?\n((?:[ \t]*-[ \t]*.*\r?\n?)+)", fm, re.M)
    if not m:
        return []
    return [ln.strip().lstrip("-").strip().strip("'\"")
            for ln in m.group(1).splitlines() if ln.strip()]


def read_client(folder):
    """The note that declares client_id wins; a folder may hold several notes."""
    notes = sorted(folder.glob("*.md"))
    best = None
    for p in notes:
        fm = frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if scalar(fm, "client_id"):
            # Prefer the note named for the folder over an ancillary one.
            if best is None or p.stem in folder.name or folder.name in p.stem:
                best = (p, fm)
    if best is None:
        return {"folder": folder.name, "note": None,
                "issue": "no note in this folder declares client_id"}
    p, fm = best
    return {
        "folder": folder.name,
        "note": p.name,
        "client_id": scalar(fm, "client_id"),
        "client_name": scalar(fm, "client_name"),
        "status": scalar(fm, "status"),
        "products": listfield(fm, "products"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clients_dir", nargs="?", default=str(DEFAULT))
    ap.add_argument("--json")
    a = ap.parse_args()

    root = Path(a.clients_dir)
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")

    recs = [read_client(d) for d in sorted(root.iterdir()) if d.is_dir()]
    if a.json:
        Path(a.json).write_text(json.dumps(recs, indent=2), encoding="utf-8")

    ok = [r for r in recs if r.get("client_id")]
    print(f"{len(recs)} client folders, {len(ok)} with a client_id\n")
    for r in sorted(recs, key=lambda r: r.get("client_id") or "zzz"):
        if not r.get("client_id"):
            print(f"  {'?':>7} | {r['folder']:42} | {r['issue']}")
            continue
        print(f"  {r['client_id']:>7} | {r['client_name']:34} | "
              f"{r['status'][:10]:10} | {', '.join(r['products']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
