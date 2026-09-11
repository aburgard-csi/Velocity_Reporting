#!/usr/bin/env python3
"""Promote a staged month to Outputs, archiving whatever it supersedes.

Pairs with build_month.py: that stages and validates, this delivers. Kept apart
so a build can be inspected before anything reaches the delivery folder.

    python3 scripts/promote_month.py <staging-dir>            # dry run
    python3 scripts/promote_month.py <staging-dir> --apply

A deck whose rendered content is identical to the delivered copy is left alone
rather than re-archived — otherwise a rebuild that changed nothing still churns
the archive and buries the copies that matter.

**Import-safe on purpose.** This used to read `sys.argv[1]` at module scope and do
the whole job there, so importing it RAN it — and an IndexError was all you got
without arguments. That is the hazard CLAUDE.md calls out for `metrics_gen`, and
it is why `deliverable()` had no test while its combined-deck detection silently
went stale against CashPlease (2026-09-11).
"""
import argparse
import datetime
import glob
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

# Relative to THIS file, never to a home directory. `~/Projects/RetailPerformanceEngine`
# is not where the repo is on this machine — it sits at C:\Projects — so the import
# raised ModuleNotFoundError and the script could not run at all (2026-09-11). Every
# other entry point resolves its siblings this way; the reason `rpe_env` exists is that
# a path written into code is a path that is wrong on the next machine.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from pptx import Presentation                                    # noqa: E402
import rpe_env as R                                              # noqa: E402

PROGRAM_TAGS = ("ARS", "ICS", "MRPC", "CP")   # the filename tags, per CLAUDE.md
PHASE_SUFFIXES = (".A.pptx", ".B.pptx", ".C.pptx", ".D.pptx")


def program_tags(name):
    """The program tags in a deck filename, per `<id>-<yyyy.mm>-<TAGS>-<name>`.

    Derived from the convention, not matched against a list of PAIRS. That list
    used to be the three literals ("ARS-ICS", "ARS-MRPC", "ICS-MRPC"), which
    predates CashPlease becoming the fourth program: an ICS-CP deck matched none
    of them and fell through to the "most slides wins" tiebreak, which happened
    to pick the right file for 1632 and 1734 by luck rather than by rule.
    """
    m = re.match(r"^\d{3,5}-\d{4}\.\d{2}-((?:(?:%s)-)+)" % "|".join(PROGRAM_TAGS), name)
    return tuple(t for t in m.group(1).split("-") if t) if m else ()


def deliverable(cdir):
    """The one deck to ship from a client's staging folder: the combined deck when
    there is one, else the fullest single-program deck."""
    decks = [f for f in glob.glob(os.path.join(cdir, "*.pptx"))
             if not any(f.endswith(x) for x in PHASE_SUFFIXES)]
    if not decks:
        return None
    combo = [f for f in decks if len(program_tags(os.path.basename(f))) > 1]
    if combo:
        # More programs wins, so ARS-ICS-MRPC-CP beats ARS-ICS if both are staged.
        return max(combo, key=lambda f: len(program_tags(os.path.basename(f))))
    return max(decks, key=lambda f: len(Presentation(f).slides))


def same(a, b):
    """Identical rendered content — text and images. Zip bytes differ per build."""
    def fp(p):
        prs = Presentation(p)
        return ([[sh.text_frame.text.strip() for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()] for s in prs.slides],
                sorted(hashlib.md5(x.blob).hexdigest()
                       for x in prs.part.package.iter_parts() if "image" in x.content_type))
    try:
        return fp(a) == fp(b)
    except Exception:
        return False


def plan(stage):
    """The decks to promote, one per client folder."""
    picks = []
    for cdir in sorted(glob.glob(os.path.join(stage, "1*"))):
        d = deliverable(cdir)
        if d:
            picks.append(d)
    return picks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", help="staging directory built by build_month.py")
    ap.add_argument("--apply", action="store_true",
                    help="actually move and copy; without it this is a dry run")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    out = R.outputs()
    arch = out / "Archive"
    # Today, not a literal. A hardcoded stamp dated four archives to the wrong
    # day and collided with the previous run, producing "-2"/"-3" suffixes.
    stamp = datetime.date.today().isoformat()

    picks = plan(a.stage)
    print(f"{'action':<9} {'file':<62}")
    print("-" * 88)
    archived = copied = skipped = 0
    for src in picks:
        name = os.path.basename(src)
        stem = os.path.splitext(name)[0]
        cur = out / name
        if cur.exists() and same(str(cur), src):
            print(f"{'unchanged':<9} {name[:62]:<62}")
            skipped += 1
            continue
        for old in sorted(glob.glob(str(out / f"{glob.escape(stem)}.*"))):
            ext = os.path.splitext(old)[1]
            dest = arch / f"{stem} (superseded {stamp}){ext}"
            n = 1
            while dest.exists():
                n += 1
                dest = arch / f"{stem} (superseded {stamp}-{n}){ext}"
            print(f"{'archive':<9} {os.path.basename(old)[:62]:<62}")
            if a.apply:
                arch.mkdir(parents=True, exist_ok=True)
                shutil.move(old, dest)
            archived += 1
        print(f"{'deliver':<9} {name[:62]:<62}")
        if a.apply:
            shutil.copy2(src, out / name)
        copied += 1
    print("-" * 88)
    print(f"{archived} archived, {copied} delivered, {skipped} unchanged"
          + ("" if a.apply else "   [DRY RUN — nothing moved]"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
