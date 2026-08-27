"""Machine-local configuration for the RPE pipelines.

Two things differ between Aaron's Mac and the CSI Windows machine, and both
have failed silently before:

  * The Google Drive mount root. Mac puts it under
    ~/Library/CloudStorage/GoogleDrive-<account>/My Drive; Windows mounts it at
    G:\\My Drive. Neither can be hardcoded.

  * Font availability. matplotlib SUBSTITUTES a missing font family rather than
    raising, so a chart renders in the wrong face and nothing tells you. The
    only way to catch it is to check before drawing.

Usage:

    from rpe_env import data_root, inputs, outputs, use_font

    wb = inputs() / "1705-2026.08-CoastLife Credit Union-Workbook_v2_1_0.xlsx"
    use_font("Carlito")

Resolution order for RPE_DATA_ROOT: real environment variable first (so an
agent or CI run can override), then the .env file at the repo root. Absent
from both, or pointing somewhere that isn't a directory, raises.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = REPO_ROOT / "fonts"

_env_cache: dict[str, str] | None = None


def _load_dotenv() -> dict[str, str]:
    """Parse the repo-root .env. Values are taken raw to the end of the line.

    No unescaping: a Windows path like G:\\My Drive\\Work must survive intact,
    and values contain spaces, so nothing is stripped beyond surrounding
    whitespace and one optional layer of matching quotes.
    """
    global _env_cache
    if _env_cache is not None:
        return _env_cache

    _env_cache = {}
    path = REPO_ROOT / ".env"
    if not path.exists():
        return _env_cache

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        _env_cache[key.strip()] = value

    return _env_cache


def data_root() -> Path:
    """The Drive-side pipeline folder: <Drive>/Work/RPE Pipeline."""
    raw = os.environ.get("RPE_DATA_ROOT") or _load_dotenv().get("RPE_DATA_ROOT")

    if not raw:
        raise SystemExit(
            "RPE_DATA_ROOT is not set.\n"
            f"  Copy {REPO_ROOT / '.env.example'} to {REPO_ROOT / '.env'} and\n"
            "  set it to your machine's path, e.g.\n"
            "    Mac:     /Users/<you>/Library/CloudStorage/"
            "GoogleDrive-<account>/My Drive/Work/RPE Pipeline\n"
            "    Windows: G:\\My Drive\\Work\\RPE Pipeline"
        )

    root = Path(raw).expanduser()
    if not root.is_dir():
        raise SystemExit(
            f"RPE_DATA_ROOT points at {root!s}, which is not a directory.\n"
            "  If the path looks right, Drive for Desktop may not be mounted "
            "yet — open the folder in Finder/Explorer and try again."
        )
    return root


def inputs() -> Path:
    return _require_subdir("Inputs")


def outputs() -> Path:
    return _require_subdir("Outputs")


def _require_subdir(name: str) -> Path:
    path = data_root() / name
    if not path.is_dir():
        raise SystemExit(
            f"Expected {path!s} to exist.\n"
            "  Drive streams files on demand — if the folder is there in "
            "Finder/Explorer but not here, mark it available offline."
        )
    return path


def register_bundled_fonts() -> list[str]:
    """Hand every .ttf under fonts/ to matplotlib.

    Fonts committed to the repo are identical on both machines, so anything
    registered here needs no OS-level install and can't drift.
    """
    from matplotlib import font_manager

    added = []
    for ttf in sorted(FONT_DIR.rglob("*.ttf")):
        font_manager.fontManager.addfont(str(ttf))
        added.append(ttf.name)
    return added


def use_font(family: str) -> None:
    """Set matplotlib's font family, failing loudly if it isn't available.

    matplotlib's default behaviour is to warn and substitute. A substituted
    face is a silent rendering difference between machines, which is exactly
    the class of bug this module exists to prevent.
    """
    import matplotlib
    from matplotlib import font_manager

    register_bundled_fonts()

    if family not in set(font_manager.get_font_names()):
        raise SystemExit(
            f"Font {family!r} is not available to matplotlib.\n"
            f"  Charts would silently render in a substitute face and the deck\n"
            f"  would not match the other machine.\n"
            f"  Fix: install {family}, or commit its .ttf files under "
            f"{FONT_DIR!s} so both machines share one copy."
        )

    matplotlib.rcParams["font.family"] = family


if __name__ == "__main__":
    print(f"repo root:  {REPO_ROOT}")
    print(f"data root:  {data_root()}")
    print(f"inputs:     {inputs()}")
    print(f"outputs:    {outputs()}")
    fonts = register_bundled_fonts()
    print(f"bundled fonts registered: {len(fonts)}")
    for name in ("Carlito", "Montserrat", "Calibri"):
        from matplotlib import font_manager
        mark = "ok " if name in set(font_manager.get_font_names()) else "MISSING"
        print(f"  {mark} {name}")
