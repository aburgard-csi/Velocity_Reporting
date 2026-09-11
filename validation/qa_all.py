#!/usr/bin/env python3
"""qa_all.py — the one-command QA gate for the whole deck project.

    python3 validation/qa_all.py [deck.pptx ...] [--snapshot] [--no-tests]
                                 [--extract base.json]

Runs on every template in templates/ plus any decks given, in three steps:

  0. The unit suite (`pytest tests/`). Deck rules check a BUILT deck; these check
     the logic that builds it — classifiers, the ODD row vocabulary, metrics
     invariants, the palette, the period derivations, the deck rules and
     assemble_combined. A classifier regression that mis-buckets 18,000 accounts
     still produces a deck that passes every layout rule (the 2026-08-28
     STAT_CODE_MAP bug). A failure fails the gate.
  1. validate_deck.py on each deck — every rule in that file's docstring. Any
     FAIL fails the gate. When a base.json / base_extract.json sits beside a
     deck (or --extract names one) the data-vs-deck cross-check runs too.
  2. Layout-fingerprint drift: each slide's shape layout (kind, box, font sizes)
     against validation/layout_baseline.json. DRIFT means a shared pass touched a
     slide you did not intend to change — review, then --snapshot to accept.
There WAS a fourth step: LibreOffice opened each deck and its PDF page count was
compared to the slide count — the only check that proved a file actually OPENS.
It was removed on 2026-09-11 because LibreOffice is not going on the build machine
(Aaron), so it had never once run there and every gate closed with a banner saying
so.

**Know what that costs.** Steps 1 and 2 read the deck THROUGH python-pptx, which
cannot see a malformed package, and that is not a hypothetical: seven 2026.08 ICS
decks passed at 0 FAIL while being unopenable. What is recoverable without a
renderer now lives in validate_deck.package_findings — duplicate, dangling and
orphaned slide parts, any part name written twice, and a CRC check on every member.
What is NOT recoverable is everything past "structurally sound": a deck that opens
but renders wrong, a font that does not resolve, an image that will not decode.
Open a deck before it goes to a client.

A skipped step is still reported LOUDLY, per deck and in a closing banner: the
Windows Store python has no pytest, and a gate started under it used to skip the
whole unit suite with one quiet line.

Exit 0 = gate passed (no FAILs). Drift is a warning, never a failure.

Standing rule (Aaron, 2026-08-17): when a defect gets through, add the check
that would have caught it here — do not just fix the instance.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TPL = os.path.join(ROOT, "templates")
BASE = os.path.join(HERE, "layout_baseline.json")
VALIDATOR = os.path.join(HERE, "validate_deck.py")


# ---------------------------------------------------------------- interpreters
def _has_module(python, name):
    try:
        r = subprocess.run([python, "-c", f"import {name}"], capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _python():
    """The interpreter every subprocess runs under.

    The one we are running under, unless it lacks pytest and the repo's own
    .venv has it — the Windows Store python on the CSI machine has python-pptx
    but no pytest, so a gate started with plain `python` skipped the whole unit
    suite (2026-09-02). Using ONE interpreter for pytest AND validate_deck keeps
    the two steps reading the same installed packages.
    """
    if _has_module(sys.executable, "pytest"):
        return sys.executable
    for cand in (os.path.join(ROOT, ".venv", "Scripts", "python.exe"),
                 os.path.join(ROOT, ".venv", "bin", "python")):
        if os.path.exists(cand) and _has_module(cand, "pytest"):
            return cand
    return sys.executable




# ---------------------------------------------------------------- steps
def run_unit_tests(python):
    """Step 0. Returns (fails, message, skipped)."""
    tests = os.path.join(ROOT, "tests")
    if not os.path.isdir(tests):
        return 0, "no tests/ directory", True
    if not _has_module(python, "pytest"):
        return 0, "pytest unavailable — unit suite NOT run", True
    r = subprocess.run([python, "-m", "pytest", tests, "-q", "--no-header", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    tail = [l for l in r.stdout.strip().splitlines() if l.strip()]
    msg = tail[-1] if tail else "pytest produced no output"
    if r.returncode != 0:
        failed = [l for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR"))]
        msg += "\n" + "\n".join("     " + l for l in failed[:12])
    return (0 if r.returncode == 0 else 1), msg, False


def validate(python, deck, extract):
    """Step 1. Returns (fail_count, summary_line, fail_lines)."""
    cmd = [python, VALIDATOR, deck] + ([extract] if extract else [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = next((l for l in p.stdout.splitlines() if "FAIL," in l), "")
    if not line.strip():
        err = (p.stderr or "").strip().splitlines()
        return 1, "validator crashed" + (f" — {err[-1][:100]}" if err else ""), []
    nf = int(line.strip().split()[0])
    return nf, line.strip(), [l.strip() for l in p.stdout.splitlines() if "[FAIL" in l]


def _extract_for(target, cli_extract):
    """The base_extract JSON to cross-check `target` against, or None.

    Explicit --extract wins; otherwise a base.json / base_extract.json beside the
    deck. Template shells have neither, so they validate exactly as before.
    """
    if cli_extract:
        return cli_extract
    d = os.path.dirname(os.path.abspath(target))
    for cand in ("base.json", "base_extract.json"):
        p = os.path.join(d, cand)
        if os.path.exists(p):
            return p
    return None


def fingerprint(path):
    """Step 2's input: per slide, every shape's kind, box (to 0.05") and run sizes."""
    from pptx import Presentation
    from pptx.util import Emu

    def r(v):
        return round(Emu(v).inches * 20) / 20 if v is not None else None
    prs = Presentation(path)
    out = []
    for sl in prs.slides:
        title = next((sh.text_frame.text.strip().split("\n")[0][:40] for sh in sl.shapes
                      if sh.has_text_frame and sh.text_frame.text.strip()), "")
        shapes = []
        for sh in sl.shapes:
            kind = {13: "pic", 1: "shape", 19: "table"}.get(int(sh.shape_type),
                                                            "txt" if sh.has_text_frame else "other")
            sizes = (sorted(set(int(rn.font.size.pt) for pa in sh.text_frame.paragraphs
                                for rn in pa.runs if rn.font.size))[:4]
                     if sh.has_text_frame else [])
            shapes.append([kind, r(sh.left), r(sh.top), r(sh.width), r(sh.height), sizes])
        shapes.sort(key=lambda x: (str(x[0]), x[1] if x[1] is not None else 99,
                                   x[2] if x[2] is not None else 99))
        out.append({"title": title, "shapes": shapes})
    return out


def drift(old, new):
    """Step 2. Returns (count, message) comparing two fingerprints."""
    if len(old) != len(new):
        return 1, f"[DRIFT: slide count {len(old)}->{len(new)}]"
    moved = [i + 1 for i, (a, b) in enumerate(zip(old, new)) if a != b]
    if moved:
        return len(moved), f"[DRIFT on slides {moved[:8]}{'...' if len(moved) > 8 else ''}]"
    return 0, ""



# ---------------------------------------------------------------- main
def _args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("decks", nargs="*", help="built decks to gate, in addition to every template")
    ap.add_argument("--snapshot", action="store_true",
                    help="accept the current layouts as the new drift baseline")
    ap.add_argument("--no-tests", action="store_true", help="skip the unit suite")
    ap.add_argument("--extract", help="base_extract.json to cross-check the given decks against")
    return ap.parse_args(argv)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    a = _args(sys.argv[1:] if argv is None else argv)
    python = _python()
    targets = [os.path.join(TPL, f) for f in sorted(os.listdir(TPL)) if f.endswith(".pptx")] + a.decks
    baseline = json.load(open(BASE, encoding="utf-8")) if os.path.exists(BASE) else {}
    newbase, fails, drifts = {}, 0, 0
    skipped_tests = False

    if a.no_tests:
        print("unit suite: skipped by request (--no-tests)")
        skipped_tests = True
    else:
        tf, tmsg, skipped_tests = run_unit_tests(python)
        print(f"unit suite: {tmsg}")
        fails += tf

    for t in targets:
        name = os.path.basename(t)
        nf, line, fail_lines = validate(python, t, _extract_for(t, a.extract))
        fails += nf
        fp = fingerprint(t)
        newbase[name] = fp
        msg = f"  {name}: {line}"
        if name in baseline and not a.snapshot:
            n, dmsg = drift(baseline[name], fp)
            drifts += n
            if dmsg:
                msg += "  " + dmsg
        print(msg)
        for l in fail_lines:
            print("     " + l)

    if a.snapshot:
        json.dump(newbase, open(BASE, "w", encoding="utf-8"), indent=0)
        print(f"\nbaseline snapshot saved ({len(newbase)} decks)")
    if skipped_tests and not a.no_tests:
        print("\n!!  UNIT SUITE SKIPPED: no interpreter with pytest was found (tried this python\n"
              "    and the repo .venv). The gate proved nothing about the builders' logic.")
    print(f"\nGATE: {'PASS' if fails == 0 else 'FAIL'} ({fails} FAILs, {drifts} layout drifts"
          f"{' — review, then --snapshot to accept' if drifts else ''})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
