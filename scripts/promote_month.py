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


def _shape_look(sh):
    """What a shape LOOKS like: kind, box, solid fill, line colour.

    Derived from shape properties, so it is stable across rebuilds the way the
    zip bytes are not — no relationship ids, no timestamps.
    """
    def rgb(fmt):
        try:
            return str(fmt.fore_color.rgb) if fmt.type is not None else None
        except (AttributeError, TypeError, ValueError):
            return None          # scheme colour, gradient, inherited — not an RGB
    try:
        line = rgb(sh.line.fill) if hasattr(sh, "line") else None
    except (AttributeError, TypeError, ValueError):
        line = None
    try:
        fill = rgb(sh.fill)
    except (AttributeError, TypeError, ValueError):
        fill = None
    return (int(sh.shape_type) if sh.shape_type is not None else -1,
            sh.left, sh.top, sh.width, sh.height, fill, line)


def same(a, b):
    """Identical rendered content — text, images, AND how the shapes look.

    It used to compare text and image blobs only, which cannot see a shape's FILL.
    On 2026-09-11 the Summit banner was recoloured to navy, every figure and every
    image stayed byte-identical, and this reported "unchanged" — so the rebuilt
    deck was silently not delivered and the old one stayed in Outputs. A check that
    cannot see the change reports success, which is the worst failure mode here.

    Geometry and colour are included for the same reason: a rebuild whose only
    change is a box, a font size or a colour is still a different deck. Zip bytes
    are still NOT compared — they differ on every build, and comparing them would
    re-archive an unchanged deck every run, which is what this function exists to
    prevent.
    """
    def fp(p):
        prs = Presentation(p)
        return ([[sh.text_frame.text.strip() for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()] for s in prs.slides],
                sorted(hashlib.md5(x.blob).hexdigest()
                       for x in prs.part.package.iter_parts() if "image" in x.content_type),
                [[_shape_look(sh) for sh in s.shapes] for s in prs.slides])
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


def promote_one(src, out, arch, stamp, apply=False, log=print):
    """Archive whatever `src` supersedes, then deliver it. ALL OR NOTHING.

    Every file for this deck moves or none does. It used to archive each match in
    turn and then copy, so a lock part way left a SPLIT state: on 2026-09-11 a deck
    was open in PowerPoint, its .pdf was archived, the .pptx move raised
    PermissionError, and that client ended up with its PDF in Archive/ and its old
    deck still live. Anything already moved is put back before the error leaves
    here.

    Returns (n_archived, delivered). Raises OSError if the deck could not be
    promoted; the caller decides whether that stops the run.
    """
    name = os.path.basename(src)
    stem = os.path.splitext(name)[0]
    olds = sorted(glob.glob(str(out / f"{glob.escape(stem)}.*")))
    plan_moves = []
    for old in olds:
        ext = os.path.splitext(old)[1]
        dest = arch / f"{stem} (superseded {stamp}){ext}"
        n = 1
        while dest.exists() or dest in [d for _, d in plan_moves]:
            n += 1
            dest = arch / f"{stem} (superseded {stamp}-{n}){ext}"
        plan_moves.append((old, dest))
        log(f"{'archive':<9} {os.path.basename(old)[:62]:<62}")
    log(f"{'deliver':<9} {name[:62]:<62}")
    if not apply:
        return len(plan_moves), True

    arch.mkdir(parents=True, exist_ok=True)
    moved = []
    inflight = None
    try:
        for old, dest in plan_moves:
            inflight = dest
            shutil.move(old, dest)
            moved.append((old, dest))
            inflight = None
        shutil.copy2(src, out / name)
    except OSError:
        # shutil.move falls back to copy-then-delete when os.rename fails, so a lock
        # on the SOURCE still leaves a full copy at the destination before raising.
        # Without this the rollback restored Outputs correctly and left an orphan in
        # Archive/ that looks like a real superseded deck (2026-09-11).
        if inflight is not None and os.path.exists(inflight):
            try:
                os.remove(inflight)
            except OSError:
                pass
        # Put back exactly what this call moved, newest first, so a failure leaves
        # Outputs as it was found. A rollback that itself fails is reported but does
        # not mask the original error.
        for old, dest in reversed(moved):
            try:
                shutil.move(dest, old)
            except OSError as back:
                log(f"{'!! ':<9} could not restore {os.path.basename(old)}: {back}")
        raise
    return len(moved), True


def _why(e):
    """A locked file is the common case and deserves to say so."""
    if isinstance(e, PermissionError):
        return "in use by another program (close it and re-run)"
    return str(e)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", help="staging directory built by build_month.py")
    ap.add_argument("--apply", action="store_true",
                    help="actually move and copy; without it this is a dry run")
    ap.add_argument("--outputs", default=None, metavar="DIR",
                    help="deliver HERE instead of the pipeline Outputs folder "
                         "(for tests and rehearsals; the real run never passes it)")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    # The destination is a PARAMETER, not a constant this function reaches for.
    # It used to be `R.outputs()` unconditionally: a caller could hand main() a
    # staging dir and its own output dir, and main would quietly ignore the second
    # and write to the real Outputs. That is not hypothetical — on 2026-09-11 a test
    # did exactly that and delivered one client's deck under another client's
    # filename into the live folder. A function that silently overrides where the
    # caller said to write cannot be exercised safely, which is the same reason this
    # module was made import-safe.
    out = Path(a.outputs) if a.outputs else R.outputs()
    arch = out / "Archive"
    # Today, not a literal. A hardcoded stamp dated four archives to the wrong
    # day and collided with the previous run, producing "-2"/"-3" suffixes.
    stamp = datetime.date.today().isoformat()

    picks = plan(a.stage)
    print(f"{'action':<9} {'file':<62}")
    print("-" * 88)
    archived = copied = skipped = 0
    failed = []
    for src in picks:
        name = os.path.basename(src)
        cur = out / name
        if cur.exists() and same(str(cur), src):
            print(f"{'unchanged':<9} {name[:62]:<62}")
            skipped += 1
            continue
        try:
            n, _ = promote_one(src, out, arch, stamp, a.apply)
        except OSError as e:
            # One locked deck must not cost the other ten. It is REPORTED, the run
            # continues, and the exit code carries the failure so a caller can gate
            # on it (2026-09-11: a deck open in PowerPoint aborted the whole run at
            # the first client and nothing was delivered).
            print(f"{'BLOCKED':<9} {name[:62]:<62}")
            print(f"{'':<9}   {_why(e)}")
            failed.append(name)
            continue
        archived += n
        copied += 1
    print("-" * 88)
    print(f"{archived} archived, {copied} delivered, {skipped} unchanged"
          + (f", {len(failed)} BLOCKED" if failed else "")
          + ("" if a.apply else "   [DRY RUN — nothing moved]"))
    if failed:
        print("\nnot delivered — close these and re-run (the run is idempotent):")
        for f in failed:
            print("  " + f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
