#!/usr/bin/env python3
"""packs.py — find and read the data a deck build left behind, and the source lines its slides carry.

The page reads exactly what the deck builders read:

  ARS         Build Artifacts/launcher/<period>/<id>/{metrics,base,lift}.json and oddd/oddd_metrics.json
              (written by `ars_launcher.py build`; `metrics.json` is metrics_gen's output, `base.json`
              the workbook's financials, `lift.json` its Lift Matrix)
  ICS, MRPC   rpe_env.resolve_client_json(<id>, "ics" | "mrpc"): the VIP sheets the deck builders read
  CashPlease  Build Artifacts/cashplease/packs/<id>_cashplease.json (cp_extract's output)

The SOURCE LINES are the deck's own: each slide's speaker notes in the program's deck, found in the
same launcher folder, by slide title. A screen that mirrors "Reg E Opt-In by Branch" shows that
slide's note. When the folder holds no deck for a program the screen composes the line from the pack
(file names and pull dates), and says so.

Import-safe: nothing runs at import. Needs the share for any real read; the tests use fixtures.
"""
import json
import re
from pathlib import Path


class PackMissing(Exception):
    """A pack the page needs is not there. `fix` says what to run, in the words a CSM would use."""

    def __init__(self, what, fix):
        super().__init__(what)
        self.what, self.fix = what, fix


CID_RX = re.compile(r"^\d{3,5}$")
PERIOD_RX = re.compile(r"^\d{4}\.\d{2}$")


def check_ids(client, period):
    if not CID_RX.match(str(client)):
        raise ValueError("not a client number")
    if not PERIOD_RX.match(str(period)):
        raise ValueError("not a period (yyyy.mm)")


def launcher_dir(client, period, root=None):
    """`Build Artifacts/launcher/<period>/<id>/`, where a launcher build leaves its working files."""
    check_ids(client, period)
    if root is None:
        import rpe_env
        root = rpe_env.build_artifacts()
    return Path(root) / "launcher" / period / str(client)


def read_json(path, what, fix):
    p = Path(path)
    if not p.is_file():
        raise PackMissing(f"{what} not found at {p}", fix)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PackMissing(f"{what} could not be read ({e})", fix)


def build_hint(client, period):
    return (f"Build the {period} ARS deck for {client} in CSM Sheila (or run "
            f"`python scripts/ars_launcher.py build {client}`); the build leaves its data pack in "
            f"Build Artifacts/launcher/{period}/{client}/. Nothing here builds a deck.")


# ----------------------------------------------------------------- the deck's own source lines
def deck_notes(deck_path):
    """{slide title: speaker-notes text} for a finished deck, or {} when it cannot be read."""
    try:
        from pptx import Presentation
    except ImportError:
        return {}
    try:
        prs = Presentation(str(deck_path))
    except Exception:
        return {}
    out = {}
    for s in prs.slides:
        title = ""
        for sh in s.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                title = sh.text_frame.text.strip().split("\n")[0].strip()
                break
        if not title:
            continue
        note = s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
        out.setdefault(title, note)
    return out


def find_deck(folder, tag):
    """The program's deck in a launcher folder: `<id>-<period>-<TAG>-*.pptx` (not a combined deck,
    not a TI or Companion deck)."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    for p in sorted(folder.glob("*.pptx")):
        parts = p.name.split("-", 3)
        if len(parts) >= 3 and parts[2] == tag:
            return p
    return None


def pick_notes(notes, needles):
    """Notes of the slides whose title contains any needle (case-insensitive), in the order asked,
    each distinct note once. Returns [{"title", "text"}]."""
    seen, out = set(), []
    for needle in needles:
        n = needle.lower()
        for title, text in notes.items():
            if n in title.lower() and text and text not in seen:
                seen.add(text)
                out.append({"title": title, "text": text})
    return out


def sources_for(notes, needles, fallback):
    """The source entries for one screen: the deck's notes for the mirrored slides, else `fallback`
    (a list of {"title","text"} composed from the pack), marked as composed."""
    got = pick_notes(notes, needles) if notes else []
    if got:
        return got
    return [dict(f, composed=True) for f in fallback]
