# Ported from v5 02-Scripts/core/layout.py at 7ba1e63. Logic unchanged; the folder lookups read the RPE checkout through rpe_env.REPO_ROOT (templates/ read only, build/assets/ for the logo, byte-identical to v5's).
"""Where the kit's fixed files are, spelled once.

Every deck builder used to find the template and the logo with its own
``Path(__file__).resolve().parents[N] / "templates" / ...``. Fourteen sites
built the template path by hand, and the logo path pointed at a folder that
did not exist for weeks without anything noticing, because the lookup was
guarded and the deck simply went out without its mark (#210).

This module is the one spelling. A static asset a deck needs is declared
here, and ``missing_assets()`` is what a test and a health check read, so a
lost file fails the suite instead of shipping a blank corner.
"""
from __future__ import annotations

from pathlib import Path

import rpe_env

SCRIPTS = rpe_env.REPO_ROOT / "build"
KIT_ROOT = rpe_env.REPO_ROOT

TEMPLATES = KIT_ROOT / "templates"
TEMPLATE = TEMPLATES / "ars_template.pptx"
ASSETS = SCRIPTS / "assets"

LOGO = ASSETS / "logo.png"
CSI_LOGO = ASSETS / "csi_logo.png"

# Every static file a deck build may reach for. Name -> path. A build that
# needs one not listed here adds it here, not a new parents[N].
REQUIRED_ASSETS: dict[str, Path] = {
    "template": TEMPLATE,
    "logo": LOGO,
    "csi_logo": CSI_LOGO,
}


def missing_assets(required: dict[str, Path] | None = None) -> dict[str, Path]:
    """{name: path} for every declared asset that is not on disk."""
    required = REQUIRED_ASSETS if required is None else required
    return {name: path for name, path in required.items() if not path.is_file()}
