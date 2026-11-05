#!/usr/bin/env python3
"""Promote a staged month to Outputs, archiving whatever it supersedes.

Pairs with build_month.py: that stages and validates, this delivers. Kept apart
so a build can be inspected before anything reaches the delivery folder.

    python3 scripts/promote_month.py <staging-dir>            # dry run
    python3 scripts/promote_month.py <staging-dir> --apply

A deck whose rendered content is identical to the delivered copy is left alone
rather than re-archived — otherwise a rebuild that changed nothing still churns
the archive and buries the copies that matter.

**The archive is one folder per client, and keeps the newest deck of each kind per
period (Aaron, 2026-09-14).** A superseded deck goes to `Outputs/<CSM>/_Archive/<id> <client>/`
(inside the CSM's folder since 2026-10-15; `Outputs/_Archive/<CSM>/...` before).
After a delivery, any OLDER archived deck with the same period and program tags is
moved to `Outputs/<CSM>/_Archive/_older decks - delete after review/<id> <client>/` — moved,
never deleted: the share has no Recycle Bin, so removing them is a person's call. A
hand-made PDF is never moved by that rule.

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
REVIEW_DIRNAME = "_older decks - delete after review"

_DECK_NAME_RX = re.compile(
    r"^(\d{3,5})-(\d{4}\.\d{2})-((?:(?:%s)-)+)(.+?)(?: \(superseded [\d-]+\))?\.(pptx|pdf)$"
    % "|".join(PROGRAM_TAGS), re.I)
_TITLE_TAIL_RX = re.compile(
    r"\s+(?:(?:(?:%s)\s+)?Results|CashPlease Module)$" % "|".join(PROGRAM_TAGS), re.I)


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


def parse_deck_name(name):
    """{client_id, period, tags, client, ext} for a delivered or archived deck/PDF name.

    Accepts the "(superseded <date>)" suffix the archive adds. None for anything that
    does not follow the filename convention — such a file is left where it is.
    """
    m = _DECK_NAME_RX.match(os.path.basename(name))
    if not m:
        return None
    cid, period, tags, rest, ext = m.groups()
    return {"client_id": cid, "period": period,
            "tags": tuple(t.upper() for t in tags.split("-") if t),
            "client": _TITLE_TAIL_RX.sub("", rest).strip(), "ext": ext.lower()}


def _is_client_dir(d, client_id):
    return d.is_dir() and d.name.split(" ", 1)[0] == client_id


def csm_archive(arch, client_id):
    """`Outputs/<CSM>/_Archive` — the archive inside the client's CSM folder.

    `arch` is the root archive (`Outputs/_Archive`); its parent is Outputs and its name is
    the archive's one name (`rpe_env.ARCHIVE_DIRNAME`), so the CSM's archive is
    `<Outputs>/<CSM>/<that name>`. The CSM comes from `rpe_env.client_csm`, else `_Unassigned`.
    """
    arch = Path(arch)
    csm = re.sub(r'[<>:"/\\|?*]', "", R.client_csm(client_id) or "").strip() or R.UNASSIGNED_CSM
    return arch.parent / csm / arch.name


def client_folder(arch, client_id, client_name=""):
    """`Outputs/<CSM>/_Archive/<id> <client>` — and an existing folder for that id, whatever its name.

    The archive sits INSIDE each CSM's folder (Aaron, 2026-10-15: "Move the Archive under each
    CSM's folder in outputs rather than in the root Outputs folder"), so a CSM's folder holds
    their live decks and, beneath `_Archive`, what those decks replaced. It was
    `Outputs/_Archive/<CSM>/<id> <client>` from 2026-09-15 (sorted by CSM) and flat
    `Outputs/Archive/<id>` before that; the folders were moved on 2026-10-15.

    The id is the key. Delivery names differ between programs (the CashPlease module
    for 1539 says "Marine Federal Credit Union", the Executive Review "Marine FCU"), so
    naming the folder from each deck would split one client across two folders. The
    first name wins and every later deck for that id lands beside it. An existing folder
    is reused: in the CSM's archive first, else wherever it still sits under the root
    archive (a folder an older copy of the code made after the move), so one client is
    never split across two places.
    """
    arch = Path(arch)
    mine = csm_archive(arch, client_id)
    if mine.is_dir():
        for d in sorted(mine.iterdir()):
            if _is_client_dir(d, client_id):
                return d
    if arch.is_dir():
        for c in sorted(arch.iterdir()):
            if not c.is_dir() or c.name == REVIEW_DIRNAME:
                continue
            if _is_client_dir(c, client_id):          # a flat folder from before the CSM sort
                return c
            if not c.name[:1].isdigit():              # a CSM folder under the root archive
                for d in sorted(c.iterdir()):
                    if _is_client_dir(d, client_id):
                        return d
    safe = re.sub(r'[<>:"/\\|?*]', "", client_name or "").strip()
    return mine / (("%s %s" % (client_id, safe)) if safe else client_id)


def review_root(arch, target):
    """The review folder for a client's archive folder: beside it, `<its archive>/<REVIEW_DIRNAME>`.

    `Outputs/<CSM>/_Archive/_older decks - delete after review/<id> <client>` for the layout since
    2026-10-15; for a folder still under the root archive, that archive's review folder, whose
    layout `tidy_client_archive` mirrors (`<CSM>/<id> <client>`).
    """
    arch, target = Path(arch), Path(target)
    if target.parent.name == arch.name and target.parent != arch:
        return target.parent / REVIEW_DIRNAME
    return arch / REVIEW_DIRNAME


def _free(dest):
    """`dest`, or `dest (2)`, `(3)`… — never overwrite a file already there."""
    dest = Path(dest)
    n = 1
    cand = dest
    while cand.exists():
        n += 1
        cand = dest.with_name("%s (%d)%s" % (dest.stem, n, dest.suffix))
    return cand


def tidy_client_archive(folder, review_root, apply=False, log=print):
    """Keep only the newest deck per (period, program tags) in one client's folder.

    Newest is the deck's own modified time — when it was built — which a move keeps.
    The rest go to `review_root/<folder name>/`, never deleted. PDFs are never moved:
    they are exported by hand, on purpose (Aaron, 2026-09-14). Returns [(src, dest)].
    """
    folder, review_root = Path(folder), Path(review_root)
    # The review folder mirrors the archive's layout: <CSM>/<id> <client> for a CSM-filed folder.
    try:
        sub = folder.relative_to(review_root.parent)
    except ValueError:
        sub = Path(folder.name)
    groups = {}
    for p in sorted(folder.glob("*.pptx")):
        info = parse_deck_name(p.name)
        if info:
            groups.setdefault((info["period"], info["tags"]), []).append(p)
    moves = []
    for decks in groups.values():
        keep = max(decks, key=lambda p: (p.stat().st_mtime, p.name))
        for p in decks:
            if p != keep:
                moves.append((p, review_root / sub / p.name))
    for src, dest in moves:
        log(f"{'older':<9} {src.name[:62]:<62}")
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(_free(dest)))
    return moves


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


def _run_sizes(sh):
    """Every run's font size in a shape, table cells included, in order.

    A table is a graphic frame with no text_frame, so a rebuild that changed only a
    table's font size (1441's Reg E by Branch tables, 16 -> 10 pt, 2026-11-02) looked
    identical to `same` and the old deck stayed in Outputs.
    """
    frames = []
    if getattr(sh, "has_text_frame", False):
        frames.append(sh.text_frame)
    if getattr(sh, "has_table", False):
        frames += [c.text_frame for row in sh.table.rows for c in row.cells]
    return tuple(r.font.size.pt if r.font.size is not None else None
                 for tf in frames for p in tf.paragraphs for r in p.runs)


def _shape_look(sh):
    """What a shape LOOKS like: kind, box, solid fill, line colour, run font sizes.

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
            sh.left, sh.top, sh.width, sh.height, fill, line, _run_sizes(sh))


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


def promote_one(src, out, arch, stamp, apply=False, log=print, legacy=()):
    """Archive whatever `src` supersedes, then deliver it. ALL OR NOTHING.

    Every file for this deck moves or none does. It used to archive each match in
    turn and then copy, so a lock part way left a SPLIT state: on 2026-09-11 a deck
    was open in PowerPoint, its .pdf was archived, the .pptx move raised
    PermissionError, and that client ended up with its PDF in Archive/ and its old
    deck still live. Anything already moved is put back before the error leaves
    here, and a client folder this call created is removed again if it is empty.

    The superseded files go to the CLIENT's folder under `arch`. Once the new deck is
    delivered, older archived decks of the same period and kind are moved to the
    review folder (`tidy_client_archive`) — after delivery, so a failure there can
    never cost a delivery; it is reported instead.

    `out` is the client's delivery folder (`Outputs/<CSM>/`). A copy of the same deck
    still sitting in any `legacy` folder — the flat Outputs/ root from before decks were
    filed by CSM — is superseded too, so a client never has a live deck in two places.

    Returns (n_archived, delivered). Raises OSError if the deck could not be
    promoted; the caller decides whether that stops the run.
    """
    out, arch = Path(out), Path(arch)
    name = os.path.basename(src)
    stem = os.path.splitext(name)[0]
    info = parse_deck_name(name)
    target = client_folder(arch, info["client_id"], info["client"]) if info else arch
    olds = sorted({f for d in [out, *map(Path, legacy)]
                   for f in glob.glob(str(d / f"{glob.escape(stem)}.*")) if os.path.isfile(f)})
    plan_moves = []
    for old in olds:
        ext = os.path.splitext(old)[1]
        dest = target / f"{stem} (superseded {stamp}){ext}"
        n = 1
        while dest.exists() or dest in [d for _, d in plan_moves]:
            n += 1
            dest = target / f"{stem} (superseded {stamp}-{n}){ext}"
        plan_moves.append((old, dest))
        log(f"{'archive':<9} {os.path.basename(old)[:62]:<62}")
    log(f"{'deliver':<9} {name[:62]:<62}")
    if not apply:
        return len(plan_moves), True

    created = not target.exists()
    if plan_moves:
        target.mkdir(parents=True, exist_ok=True)
    moved = []
    inflight = None
    try:
        for old, dest in plan_moves:
            inflight = dest
            shutil.move(old, dest)
            moved.append((old, dest))
            inflight = None
        out.mkdir(parents=True, exist_ok=True)
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
        # Remove the client folder this call created, and its CSM folder if that is now empty.
        for d in (target, target.parent):
            if created and d != arch and d.is_dir() and not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:
                    pass
        raise
    if moved and target != arch:
        try:
            tidy_client_archive(target, review_root(arch, target), apply=True, log=log)
        except OSError as e:
            log(f"{'!! ':<9} could not tidy {target.name}: {_why(e)}")
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
    arch = out / R.ARCHIVE_DIRNAME
    # Each deck is delivered to its CSM's folder (Aaron, 2026-09-14); the flat root is
    # read as a legacy location so a deck left there is superseded, not duplicated.
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
        info = parse_deck_name(name)
        dest = R.client_outputs(info["client_id"], root=out) if info else out
        cur = dest / name
        if cur.exists() and same(str(cur), src):
            print(f"{'unchanged':<9} {name[:62]:<62}")
            skipped += 1
            continue
        try:
            n, _ = promote_one(src, dest, arch, stamp, a.apply,
                               legacy=(out,) if dest != out else ())
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
