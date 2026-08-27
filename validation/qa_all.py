#!/usr/bin/env python3
"""qa_all.py — the one-command QA gate for the whole deck project.

    python3 validation/qa_all.py [--snapshot] [--no-render] [extra_deck.pptx ...]

Runs on every template in templates/ plus any deck paths given:
  1. validate_deck.py rules (banned words, counts, geometry, glyph overflow,
     autofit shrink, chart-vs-tile collisions, OOXML package integrity, ...)
     -> any FAIL fails the gate.
  2. Layout-fingerprint regression check: every slide's shape layout (kind, box,
     font sizes) is compared against validation/layout_baseline.json. Unexpected
     layout drift on slides you did NOT mean to touch is reported. After an
     INTENTIONAL change, re-run with --snapshot to accept the new layout.
  3. Render smoke test: each deck is opened by LibreOffice and converted to PDF,
     and the page count is compared to the slide count. This is the only check
     that proves the file actually OPENS — rules 1 and 2 read the deck through
     python-pptx, which cannot see a malformed package. `--no-render` skips it
     (it costs a few seconds per deck).

Standing rule (Aaron, 2026-08-17): when a defect gets through, add the check that
would have caught it, here — do not just fix the instance.

Exit 0 = gate passed (no FAILs). Regressions print as DRIFT warnings — review them;
they are how a shared pass silently breaking an unrelated slide gets caught.
"""
import sys, os, json, subprocess, hashlib, shutil, tempfile, glob, re
HERE=os.path.dirname(os.path.abspath(__file__))
ROOT=os.path.dirname(HERE)
TPL=os.path.join(ROOT,"templates")
BASE=os.path.join(HERE,"layout_baseline.json")


def render_check(path):
    """Open the deck with a real renderer and count the pages.

    Added 2026-08-17. Every text/geometry rule in validate_deck reads the deck
    THROUGH python-pptx, which will happily enumerate a duplicated slide
    reference twice — so seven structurally broken ICS decks passed the gate at
    0 FAIL while LibreOffice could not open them at all. Actually rendering the
    file is the only check that proves it opens, and the page count proves the
    deck contains the slides it claims.

    Returns (ok, message). Skipped (ok) when soffice isn't installed.
    """
    soffice=shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return True,"render skipped (no soffice)"
    try:
        from pptx import Presentation
        n_slides=len(Presentation(path).slides)
    except Exception as e:
        return False,f"python-pptx cannot open the deck: {e}"
    tmp=tempfile.mkdtemp(prefix="qa_render_")
    try:
        # copy to a plain ASCII path — soffice fails on some mounted/odd names
        src=os.path.join(tmp,"deck.pptx"); shutil.copyfile(path,src)
        p=subprocess.run([soffice,"-env:UserInstallation=file://"+os.path.join(tmp,"lo"),
                          "--headless","--convert-to","pdf","--outdir",tmp,src],
                         capture_output=True,text=True,timeout=300)
        pdf=os.path.join(tmp,"deck.pdf")
        if not os.path.exists(pdf):
            err=(p.stderr or p.stdout or "").strip().splitlines()
            return False,("renderer could not open the deck"
                          +(f" — {err[-1][:90]}" if err else ""))
        try:
            pages=len(re.findall(rb"/Type\s*/Page\b",open(pdf,"rb").read()))
        except Exception:
            pages=None
        if pages and pages!=n_slides:
            return False,f"rendered {pages} pages but the deck reports {n_slides} slides"
        return True,f"renders ({pages if pages else '?'} pages)"
    except subprocess.TimeoutExpired:
        return False,"renderer timed out"
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def fingerprint(path):
    from pptx import Presentation
    from pptx.util import Emu
    def r(v): return round(Emu(v).inches*20)/20 if v is not None else None
    prs=Presentation(path); out=[]
    for sl in prs.slides:
        title=next((sh.text_frame.text.strip().split("\n")[0][:40] for sh in sl.shapes
                    if sh.has_text_frame and sh.text_frame.text.strip()),"")
        shapes=[]
        for sh in sl.shapes:
            kind={13:"pic",1:"shape",19:"table"}.get(int(sh.shape_type),"txt" if sh.has_text_frame else "other")
            sizes=sorted(set(int(rn.font.size.pt) for pa in (sh.text_frame.paragraphs if sh.has_text_frame else [])
                             for rn in pa.runs if rn.font.size))[:4] if sh.has_text_frame else []
            shapes.append([kind,r(sh.left),r(sh.top),r(sh.width),r(sh.height),sizes])
        shapes.sort(key=lambda x:(str(x[0]),x[1] if x[1] is not None else 99,x[2] if x[2] is not None else 99))
        out.append({"title":title,"shapes":shapes})
    return out

def main():
    snap="--snapshot" in sys.argv
    norender="--no-render" in sys.argv
    extra=[a for a in sys.argv[1:] if not a.startswith("--")]
    targets=[os.path.join(TPL,f) for f in sorted(os.listdir(TPL)) if f.endswith(".pptx")]+extra
    baseline=json.load(open(BASE)) if os.path.exists(BASE) else {}
    newbase={}; fails=0; drifts=0
    for t in targets:
        name=os.path.basename(t)
        p=subprocess.run([sys.executable,os.path.join(HERE,"validate_deck.py"),t],
                         capture_output=True,text=True)
        line=next((l for l in p.stdout.splitlines() if "FAIL," in l),"? ")
        nf=int(line.strip().split()[0]) if line.strip().split()[0].isdigit() else 1
        fails+=nf
        fp=fingerprint(t); newbase[name]=fp
        msg=f"  {name}: {line.strip()}"
        if name in baseline and not snap:
            old=baseline[name]
            if len(old)!=len(fp):
                msg+=f"  [DRIFT: slide count {len(old)}->{len(fp)}]"; drifts+=1
            else:
                moved=[i+1 for i,(a,b) in enumerate(zip(old,fp)) if a!=b]
                if moved: msg+=f"  [DRIFT on slides {moved[:8]}{'...' if len(moved)>8 else ''}]"; drifts+=len(moved)
        if not norender:
            ok,rmsg=render_check(t)
            if not ok:
                fails+=1; msg+=f"  [RENDER FAIL: {rmsg}]"
        print(msg)
        if nf:
            for l in p.stdout.splitlines():
                if "[FAIL" in l: print("     "+l.strip())
    if snap:
        json.dump(newbase,open(BASE,"w"),indent=0); print(f"\nbaseline snapshot saved ({len(newbase)} decks)")
    print(f"\nGATE: {'PASS' if fails==0 else 'FAIL'} ({fails} FAILs, {drifts} layout drifts{' — review, then --snapshot to accept' if drifts else ''})")
    sys.exit(1 if fails else 0)

if __name__=="__main__":
    main()
