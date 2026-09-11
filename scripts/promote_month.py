#!/usr/bin/env python3
"""Promote a staged month to Outputs, archiving whatever it supersedes.

Pairs with build_month.py: that stages and validates, this delivers. Kept apart
so a build can be inspected before anything reaches the delivery folder.

    python3 scripts/promote_month.py <staging-dir>            # dry run
    python3 scripts/promote_month.py <staging-dir> --apply

A deck whose rendered content is identical to the delivered copy is left alone
rather than re-archived — otherwise a rebuild that changed nothing still churns
the archive and buries the copies that matter.
"""
import datetime
import glob, os, shutil, sys
from pathlib import Path

# Relative to THIS file, never to a home directory. `~/Projects/RetailPerformanceEngine`
# is not where the repo is on this machine — it sits at C:\Projects — so the import
# raised ModuleNotFoundError and the script could not run at all (2026-09-11). Every
# other entry point resolves its siblings this way; the reason `rpe_env` exists is that
# a path written into code is a path that is wrong on the next machine.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from pptx import Presentation                                    # noqa: E402
import rpe_env as R                                              # noqa: E402

STAGE = sys.argv[1]; APPLY = "--apply" in sys.argv
OUT = R.outputs(); ARCH = OUT/"Archive"
# Today, not a literal. A hardcoded stamp dated four archives to the wrong
# day and collided with the previous run, producing "-2"/"-3" suffixes.
STAMP = datetime.date.today().isoformat()

def deliverable(cdir):
    decks=[f for f in glob.glob(os.path.join(cdir,"*.pptx"))
           if not any(f.endswith(x) for x in (".A.pptx",".B.pptx",".C.pptx",".D.pptx"))]
    if not decks: return None
    combo=[f for f in decks if any(t in os.path.basename(f) for t in ("ARS-ICS","ARS-MRPC","ICS-MRPC"))]
    return combo[0] if combo else max(decks, key=lambda f: len(Presentation(f).slides))

picks=[]
for cdir in sorted(glob.glob(os.path.join(STAGE,"1*"))):
    d=deliverable(cdir)
    if d: picks.append(d)

print(f"{'action':<9} {'file':<62}")
print("-"*88)
def same(a,b):
    """Identical rendered content — text and images. Zip bytes differ per build."""
    import hashlib
    def fp(p):
        prs=Presentation(p)
        return ([[sh.text_frame.text.strip() for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()] for s in prs.slides],
                sorted(hashlib.md5(x.blob).hexdigest()
                       for x in prs.part.package.iter_parts() if "image" in x.content_type))
    try: return fp(a)==fp(b)
    except Exception: return False

archived=copied=skipped=0
for src in picks:
    name=os.path.basename(src); stem=os.path.splitext(name)[0]
    cur = OUT/name
    if cur.exists() and same(str(cur), src):
        print(f"{'unchanged':<9} {name[:62]:<62}")
        skipped+=1
        continue
    for old in sorted(glob.glob(str(OUT/f"{glob.escape(stem)}.*"))):
        ext=os.path.splitext(old)[1]
        dest=ARCH/f"{stem} (superseded {STAMP}){ext}"
        n=1
        while dest.exists():
            n+=1; dest=ARCH/f"{stem} (superseded {STAMP}-{n}){ext}"
        print(f"{'archive':<9} {os.path.basename(old)[:62]:<62}")
        if APPLY: shutil.move(old, dest)
        archived+=1
    print(f"{'deliver':<9} {name[:62]:<62}")
    if APPLY: shutil.copy2(src, OUT/name)
    copied+=1
print("-"*88)
print(f"{archived} archived, {copied} delivered, {skipped} unchanged" + ("" if APPLY else "   [DRY RUN — nothing moved]"))
