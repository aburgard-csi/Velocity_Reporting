"""
The deck shell: RPE blank slides, built from the stripped RPE template.

PROVENANCE. The analysis team's `template.py` opened their CSI ILS review template (a hand-built
copy of a previous client's review), purged the previous client's slides, rebranded its
institution name and inserted generated slides at anchors. None of that applies here: our deck
is built from BLANK slides on the RPE shell's own layouts, so there is no previous client's
content to purge, no institution name to rewrite and no anchor to miss. That is also why the
RPE pipeline never starts from a finished deck (CLAUDE.md, "Templates").

WHY A BLANK-SLIDE BUILD AND NOT A STRIPPED ILS SHELL. The ILS deck is the analysis team's
hand-assembled review: a fixed 75-slide run of generic industry slides plus the client's own
data slides, and the client's own slides are the ones that change. We build only the second
kind, so there is nothing for a shell to hold except the master, theme, layouts and embedded
fonts, which `templates/ars_template.pptx` already carries. Its demo slides are DETACHED
(relationship dropped, slide id removed) before the first slide is added, so the package
holds no orphan part and no slide part is written twice (checked by
`validate_deck.package_findings`); a freed partname is handed to the first new slide, which
is the point. Slides are never deleted after being added.
"""
from __future__ import annotations

import os
from pathlib import Path

from pptx import Presentation

_REPO = Path(__file__).resolve().parents[3]
DEFAULT_SHELL = _REPO / "templates" / "ars_template.pptx"
_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
LAYOUT_BLANK = 0


class Title:
    """Kept so old anchor definitions import; the RPE build has no anchors (see the docstring)."""

    def __init__(self, text):
        self.text = text


class Shell:
    """The open presentation plus what the builders need from it."""

    size_warning = None

    def __init__(self, shell_path=None):
        path = Path(shell_path or DEFAULT_SHELL)
        if not path.is_file():
            raise FileNotFoundError(f"RPE shell not found: {path}")
        self.path = path
        self.prs = Presentation(str(path))
        lst = self.prs.slides._sldIdLst
        for sld in list(lst):
            self.prs.part.drop_rel(sld.get(_REL_ID))
            lst.remove(sld)
        self.sections = {}                 # id(slide) -> section key

    def add_slide(self):
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[LAYOUT_BLANK])
        for ph in list(slide.placeholders):
            ph._element.getparent().remove(ph._element)
        return slide

    def tag(self, slide, section):
        self.sections[id(slide)] = section

    def save(self, out_path):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(out_path))
        return str(out_path)
