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



def _find_soffice():
    """Locate LibreOffice. PATH first, then the standard install locations.

    macOS ships it as an .app bundle and does NOT put `soffice` on PATH, so a
    shutil.which() lookup alone reported "no soffice" on a machine that has
    LibreOffice installed — and the one check that proves a deck actually OPENS
    silently never ran (Aaron, 2026-08-28). Override with RPE_SOFFICE.
    """
    env = os.environ.get("RPE_SOFFICE")
    if env and os.path.exists(env):
        return env
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    for c in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",
              os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
              "/opt/homebrew/bin/soffice", "/usr/local/bin/soffice",
              "/usr/bin/soffice", "/usr/bin/libreoffice",
              r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.exists(c):
            return c
    return None


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
    soffice=_find_soffice()
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

def _extract_for(target, cli_extract):
    """The base_extract JSON to cross-check `target` against, or None.

    Explicit --extract wins; otherwise a base.json / base_extract.json sitting
    beside the deck is used. Template decks in templates/ have neither, so they
    validate exactly as before.
    """
    if cli_extract:
        return cli_extract
    d=os.path.dirname(os.path.abspath(target))
    for cand in ("base.json","base_extract.json"):
        p=os.path.join(d,cand)
        if os.path.exists(p):
            return p
    return None


def run_unit_tests():
    """Gate step 0 — the unit suite.

    Deck rules check a BUILT deck; these check the logic that builds it
    (classifiers, ODD predicates, metrics invariants, the palette). A classifier
    regression that mis-buckets 18,000 accounts still produces a deck that
    passes every layout rule, which is how the 2026-08-28 STAT_CODE_MAP bug
    shipped. Skipped with --no-tests, and skipped silently if pytest is absent
    so the gate still runs on a machine without it.
    """
    root=os.path.dirname(HERE)
    tests=os.path.join(root,"tests")
    if not os.path.isdir(tests):
        return 0, "no tests/ directory"
    r=subprocess.run([sys.executable,"-m","pytest",tests,"-q","--no-header"],
                     capture_output=True,text=True,cwd=root)
    if r.returncode==5 or "No module named pytest" in (r.stderr or ""):
        return 0, "pytest unavailable — unit suite skipped"
    tail=[l for l in r.stdout.strip().splitlines() if l.strip()]
    return (0 if r.returncode==0 else 1), (tail[-1] if tail else "pytest produced no output")


def main():
    snap="--snapshot" in sys.argv
    norender="--no-render" in sys.argv
    cli_extract=None
    if "--extract" in sys.argv:
        i=sys.argv.index("--extract")
        if i+1 < len(sys.argv):
            cli_extract=sys.argv[i+1]
    extra=[a for a in sys.argv[1:]
           if not a.startswith("--") and a != cli_extract]
    targets=[os.path.join(TPL,f) for f in sorted(os.listdir(TPL)) if f.endswith(".pptx")]+extra
    baseline=json.load(open(BASE)) if os.path.exists(BASE) else {}
    newbase={}; fails=0; drifts=0; skipped_render=0
    if "--no-tests" not in sys.argv:
        tf,tmsg=run_unit_tests()
        print(f"unit suite: {tmsg}")
        fails+=tf
    else:
        print("unit suite: skipped by request (--no-tests)")
    for t in targets:
        name=os.path.basename(t)
        # validate_deck has carried a data-vs-deck cross-check on argv[2] since it
        # was written, but this gate never passed one — so the only automated
        # wrong-number check in the repo was switched off in the gate everyone
        # actually runs. Pass --extract, or drop a base.json beside the deck.
        ex=_extract_for(t,cli_extract)
        cmd=[sys.executable,os.path.join(HERE,"validate_deck.py"),t]+([ex] if ex else [])
        p=subprocess.run(cmd,capture_output=True,text=True)
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
            elif rmsg.startswith("render skipped"):
                # A skip must never read like a pass. This check was silent on success AND
                # silent on skip, so a machine with no LibreOffice reported a clean gate while
                # the one check that proves the file opens had not run at all.
                skipped_render+=1; msg+=f"  [{rmsg}]"
        print(msg)
        if nf:
            for l in p.stdout.splitlines():
                if "[FAIL" in l: print("     "+l.strip())
    if snap:
        json.dump(newbase,open(BASE,"w"),indent=0); print(f"\nbaseline snapshot saved ({len(newbase)} decks)")
    if skipped_render:
        print(f"\n!!  RENDER CHECK SKIPPED on {skipped_render} deck(s): LibreOffice (soffice) is not\n"
              f"    installed, so \"does this deck actually open\" was NOT verified. Every text and\n"
              f"    geometry rule reads the deck THROUGH python-pptx, which cannot see a malformed\n"
              f"    package — seven 2026.08 ICS decks passed at 0 FAIL and were unopenable. Install\n"
              f"    LibreOffice to close this, or pass --no-render to skip it deliberately.")
    elif norender:
        print("\n!!  --no-render: the deck-opens check was skipped by request.")
    print(f"\nGATE: {'PASS' if fails==0 else 'FAIL'} ({fails} FAILs, {drifts} layout drifts{' — review, then --snapshot to accept' if drifts else ''})")
    sys.exit(1 if fails else 0)

if __name__=="__main__":
    main()
