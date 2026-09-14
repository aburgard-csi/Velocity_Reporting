"""Machine-local configuration for the RPE pipelines.

Two things differ between Aaron's Mac and the CSI Windows machine, and both
have failed silently before:

  * The pipeline data root. It differs per machine — this one keeps it at
    C:\\Data Pipelines\\RPE Pipeline — and cannot be hardcoded.

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

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = REPO_ROOT / "fonts"

_env_cache: dict[str, str] | None = None


def _load_dotenv() -> dict[str, str]:
    """Parse the repo-root .env. Values are taken raw to the end of the line.

    No unescaping: a Windows path like C:\\Data Pipelines\\RPE Pipeline must survive,
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
    """The pipeline folder holding Inputs/, Outputs/ and Build Artifacts/."""
    raw = os.environ.get("RPE_DATA_ROOT") or _load_dotenv().get("RPE_DATA_ROOT")

    if not raw:
        raise SystemExit(
            "RPE_DATA_ROOT is not set.\n"
            f"  Copy {REPO_ROOT / '.env.example'} to {REPO_ROOT / '.env'} and\n"
            "  set it to your machine's path, e.g.\n"
            "    C:\\Data Pipelines\\RPE Pipeline"
        )

    root = Path(raw).expanduser()
    if not root.is_dir():
        raise SystemExit(
            f"RPE_DATA_ROOT points at {root!s}, which is not a directory.\n"
            "  If the path looks right, the folder may not exist yet — check "
            "it in Explorer and try again."
        )
    return root


def inputs() -> Path:
    return _require_subdir("Inputs")


def outputs() -> Path:
    return _require_subdir("Outputs")


# ------------------------------------------------------------------ input kinds
# One folder per kind of input, sorted on arrival by scripts/watch_sources.py
# (Aaron, 2026-09-09). Everything used to land in one "ARS & MRPC Reports"
# folder: DCOs, ARS workbooks, MRPC analyses, ICS workbooks, ICS Charts and the
# weekly summaries, 55 files deep and growing, with the kind readable only from
# the filename.
#
# THIS MAPPING IS THE ONLY PLACE THE FOLDER NAMES LIVE. Renaming a folder is a
# one-line change here plus a move on disk; every reader and the copier resolve
# through `input_dir()` / `report_dirs()`.
INPUT_KIND_DIRS = {
    "ODDD": "ODDD",                       # <id>_ODDD.zip, from the ODDD share
    "DCO": "DCOs",
    "Workbook": "ARS Workbooks",
    "MRPCPM": "MRPC Analyses",
    "ICS workbook": "ICS Workbooks",
    "ICS charts": "ICS Charts",           # "<Client> Charts 2026.xlsx" — mystery shops
    "weekly": "Weekly Summaries",         # MRPCEnrollmentSummary, CashPleaseSummary
    "CP settings": "Product Settings",    # <id>_cp_settings.json, Velocity Product Settings app
}

# Kinds resolved by exact path, never by scanning for workbook-ish files. Neither
# report_dirs() nor the copier/pruner in watch_sources.py looks inside these.
NOT_SCANNED_KINDS = ("ODDD", "CP settings")

# The flat folder everything used to land in. Kept as a READ location for good:
# a file dropped there by hand still resolves, and the migration does not have to
# be perfect for a build to work. Nothing is written here any more.
LEGACY_REPORTS_DIRNAME = "ARS & MRPC Reports"


def input_dir(kind: str, create: bool = True) -> Path:
    """Where a file of this kind belongs. Unknown kinds go to the legacy folder,
    which is where an unrecognised file would have landed anyway."""
    name = INPUT_KIND_DIRS.get(kind, LEGACY_REPORTS_DIRNAME)
    p = inputs() / name
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def report_dirs() -> list:
    """Every folder that can hold a workbook-ish input, newest scheme first.

    Readers glob across all of them rather than one, so the sort can happen
    incrementally and a stray file in the old folder is still found. `ODDD/` and
    `Product Settings/` are NOT here — both are resolved by exact path.
    """
    I = inputs()
    names = [v for k, v in INPUT_KIND_DIRS.items() if k not in NOT_SCANNED_KINDS]
    names.append(LEGACY_REPORTS_DIRNAME)
    return [I / n for n in names if (I / n).is_dir()]


def cp_settings_file(client_id):
    """A CashPlease client's production settings, or None when none are on file.

    `Inputs/Product Settings/<id>_cp_settings.json` — one client's record from the
    CashPlease page of the Velocity Product Settings Power BI app, with a `_source`
    key naming the app and its data-updated stamp (Aaron, 2026-09-14). It is a
    snapshot of configuration, not a period's figures, so it carries no period in
    its name and is replaced in place when re-pulled.
    """
    p = inputs() / INPUT_KIND_DIRS["CP settings"] / f"{client_id}_cp_settings.json"
    return p if p.is_file() else None


def report_files(pattern: str = "*") -> list:
    """Every workbook-ish input matching `pattern`, across all report folders.

    Sorted by name so callers that pick a "newest" by string comparison behave
    the same as they did against one folder.
    """
    out = []
    for d in report_dirs():
        out.extend(d.glob(pattern))
    return sorted(out, key=lambda p: p.name)


BUILD_ARTIFACTS_DIRNAME = "Build Artifacts"


def build_artifacts() -> Path:
    """Where a build drops evidence that is NOT a deliverable.

    `Outputs/` is the delivery folder and holds finished decks only. Provenance
    sidecars, phase files and anything else a build emits to prove itself belong
    here instead (Aaron, 2026-08-29).

    Created on demand — unlike inputs()/outputs(), whose absence means a broken
    mount and must raise. Falls back to a repo-local directory when
    RPE_DATA_ROOT is unset, so a build never fails for want of somewhere to put
    its bookkeeping.
    """
    try:
        path = data_root() / BUILD_ARTIFACTS_DIRNAME
    except SystemExit:
        path = REPO_ROOT / "build_artifacts"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return REPO_ROOT / "build_artifacts"
    return path


VIP_DATA_DIRNAME = "VIP Data"


def vip_data() -> Path | None:
    """`Inputs/VIP Data/` under RPE_DATA_ROOT, or None if it is not there.

    ICS and MRPC read a per-client JSON (`<id>_ics.json`, `<id>_mrpc.json`)
    assembled from the VIP dashboards — `1075_mrpc.json` names its own source as
    "VIP MyRewards Premium Cards dashboards (Enrollments, Performance,
    Retention, Revenue to FI) + MRPCPM Analysis workbook". It is real client
    data, correctly gitignored, so it does not travel with the repo — which
    means a fresh checkout on the CSI machine has the code and none of the
    ICS/MRPC inputs, and PRD success criterion 1 ("the same client built on both
    machines produces identical decks") is unreachable for two of the three
    programs.

    Unlike inputs()/outputs() this never raises: the folder is a migration
    target, and until every client JSON has moved there the repo-local
    `build/<program>_pipeline/data/` is still a legitimate place to find one.
    resolve_client_json() prefers this and falls back to that.
    """
    try:
        path = data_root() / "Inputs" / VIP_DATA_DIRNAME
    except SystemExit:
        return None
    return path if path.is_dir() else None


VIP_MANIFEST = "manifest.json"


def vip_manifest() -> list | None:
    """The `clients` list from `Inputs/VIP Data/manifest.json`, or None.

    The manifest is the authoritative index of the VIP store: one row per file
    with program, client id, period, pull date and the relative path. Preferred
    over walking the tree because it also records WHICH pull a file is, and two
    copies of a client can differ by pull date.
    """
    root = vip_data()
    if root is None:
        return None
    try:
        with open(root / VIP_MANIFEST, encoding="utf-8") as fh:
            return json.load(fh).get("clients") or None
    except (OSError, ValueError):
        return None


def _client_id_of(arg) -> str:
    """The leading client id in `1705`, `1705_ics.json`, `1705-CoastLife...`."""
    m = re.match(r"(\d{3,5})", os.path.basename(str(arg)))
    return m.group(1) if m else ""


def resolve_client_json(arg, program) -> Path:
    """Find a client's ICS/MRPC data sheet in the VIP store.

    Accepts a path (used as-is when it exists) or a bare `1705_ics.json` / `1705`.

    Search order:

      1. the literal argument, if it exists;
      2. `Inputs/VIP Data/manifest.json` — the authoritative index, which also
         records each file's period and pull date;
      3. `Inputs/VIP Data/<PROGRAM>/<id>-<Name>/<id>_<program>.json`, in case the
         manifest is stale.

    There is NO repo fallback (Aaron, 2026-08-29). `build/<program>_pipeline/data/`
    held copies that drifted: the store carried 2026-08-29 pulls while the repo
    still had 2026-08-10, and a build reading the repo shipped month-old figures
    that validated perfectly because they were internally consistent. Two stores
    for one fact is the problem; `Inputs/VIP Data/` is the fact.
    """
    if not arg:
        raise SystemExit(f"resolve_client_json: no {program} client file given")
    candidate = Path(arg)
    if candidate.exists():
        return candidate

    prog = program.lower()
    cid = _client_id_of(arg)
    name = os.path.basename(str(arg))
    if not name.endswith(".json"):
        name = f"{cid or name}_{prog}.json"

    root = vip_data()
    if root is None:
        raise SystemExit(
            f"Inputs/VIP Data is not available, so {name!r} cannot be resolved.\n"
            "  Set RPE_DATA_ROOT for this machine (see .env.example) and check\n"
            "  that Inputs/VIP Data exists under it."
        )

    tried = []
    if cid:
        for row in (vip_manifest() or []):
            if (str(row.get("program", "")).lower() == prog
                    and str(row.get("client_id", "")) == cid):
                hit = root / row["file"]
                tried.append(hit)
                if hit.exists():
                    return hit
        for hit in sorted(root.glob(f"{program.upper()}/{cid}-*/{name}")):
            tried.append(hit)
            if hit.exists():
                return hit

    where = "\n  ".join(str(t) for t in [candidate] + tried) or str(root)
    raise SystemExit(
        f"Could not find the {program.upper()} client file {name!r} in the VIP store.\n"
        f"  Looked in:\n  {where}\n"
        "  Refresh it from VIP per Inputs/VIP Data/README.md, or check\n"
        "  the client id."
    )


def client_logo(client_id) -> Path | None:
    """The client's own logo, or None. Never raises — a missing logo degrades.

    Lives in `Inputs/Logos/<clientid>.<ext>`, alongside the other client inputs
    rather than in the repo: it is the client's brand asset and nothing
    client-identifiable belongs in git: data under RPE_DATA_ROOT, code in git.

    Filenames in that folder are not uniform — 1075 has both a .jpg and a .png, and
    1539 carries no extension at all while still being a valid PNG. So candidates are
    tried in preference order and each is OPENED before being accepted; an unreadable
    or non-image file is skipped rather than handed to python-pptx, which fails the
    whole build on a bad picture.
    """
    cid = str(client_id).strip()
    if not cid:
        return None
    try:
        folder = data_root() / "Inputs" / "Logos"
    except SystemExit:
        return None
    if not folder.is_dir():
        return None
    # .png first (transparency), then jpg, then the extensionless form
    cands = [folder / f"{cid}.png", folder / f"{cid}.PNG",
             folder / f"{cid}.jpg", folder / f"{cid}.jpeg", folder / cid]
    for c in cands:
        if not c.is_file():
            continue
        try:
            from PIL import Image
            with Image.open(c) as im:
                im.verify()
            return c
        except Exception:
            continue
    return None


def trim_logo(img_path, out_dir):
    """Crop a logo to its ink and return the new path (or the original, untouched).

    Client logo files are not tightly cropped, and the padding is not always the same
    kind: 1549 is a 2940x1532 canvas whose artwork sits in the top-left with the rest
    OPAQUE WHITE, while 1676 carries 56% TRANSPARENT margin. Fitting the raw canvas
    renders a correctly-sized box containing a tiny logo — how it first shipped on the
    agenda slide (Aaron, 2026-08-28).

    Two passes, and which one applies is decided by the file, not guessed:

      * transparent padding -> the alpha bbox already bounds the ink; use it.
      * opaque canvas -> subtract the background colour, sampled from the border RING
        rather than the four corners. 1539's bottom-right corner is semi-transparent
        teal ARTWORK; sampling corners took that as the background and masked the logo
        down to 115x97 of its 420x128.

    Returns the original path when nothing can be trimmed, so an already-tight logo is
    never re-encoded.
    """
    try:
        from PIL import Image, ImageChops
    except Exception:
        return img_path
    try:
        im = Image.open(img_path).convert("RGBA")
    except Exception:
        return img_path
    w, h = im.size
    if not w or not h:
        return img_path

    alpha = im.getchannel("A")
    ink = alpha.point(lambda v: 255 if v > 8 else 0)
    abox = ink.getbbox()
    if not abox:
        return img_path
    a_w, a_h = abox[2] - abox[0], abox[3] - abox[1]

    # Real transparency already bounds the ink; only an (effectively) opaque canvas
    # needs the background colour subtracted.
    if a_w >= w * 0.97 and a_h >= h * 0.97:
        px = im.load()
        step = max(1, min(w, h) // 64)
        ring = []
        for x in range(0, w, step):
            ring.append(px[x, 0]); ring.append(px[x, h - 1])
        for y in range(0, h, step):
            ring.append(px[0, y]); ring.append(px[w - 1, y])
        ring = [c for c in ring if c[3] > 200]
        if ring:
            bg = max(set(ring), key=ring.count)
            # only trust it if the border is genuinely uniform
            if ring.count(bg) >= len(ring) * 0.7:
                flat = Image.new("RGB", im.size, bg[:3])
                diff = ImageChops.difference(im.convert("RGB"), flat).convert("L")
                not_bg = diff.point(lambda v: 255 if v > 12 else 0)
                ink = ImageChops.multiply(ink, not_bg)

    bbox = ink.getbbox()
    if not bbox:
        bbox = (0, 0, w, h)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if bw <= 0 or bh <= 0:
        bbox, bw, bh = (0, 0, w, h), w, h
    tight = bw >= w * 0.97 and bh >= h * 0.97

    # python-pptx accepts only BMP/GIF/JPEG/PNG/TIFF/WMF and goes by CONTENT, not
    # extension. 1539.png is really a WEBP: PIL opens it happily, so it passed
    # client_logo's check, and add_picture then refused the whole image. Re-encode
    # anything outside that set even when there is nothing to crop.
    fmt = (getattr(im, "format", None) or "").upper()
    if tight and fmt in ("BMP", "GIF", "JPEG", "JPG", "PNG", "TIFF", "WMF"):
        return img_path                       # already tight and already usable

    pad = max(1, int(round(min(bw, bh) * 0.02)))
    box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
           min(w, bbox[2] + pad), min(h, bbox[3] + pad))
    try:
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"logo_trim_{os.path.basename(str(img_path))}.png")
        im.crop(box).save(out)
        return out
    except Exception:
        return img_path


def fit_box(img_path, max_w_in, max_h_in):
    """(width, height) in inches that fits `img_path` inside the box, aspect kept.

    Client logos run from 1.50 to 4.47 in aspect, so a fixed width stretches or
    overflows depending on the client. Returns None if the image cannot be read.
    """
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            w, h = im.size
    except Exception:
        return None
    if not w or not h:
        return None
    scale = min(max_w_in / w, max_h_in / h)
    return w * scale, h * scale


def _require_subdir(name: str) -> Path:
    path = data_root() / name
    if not path.is_dir():
        raise SystemExit(
            f"Expected {path!s} to exist.\n"
            "  Check RPE_DATA_ROOT in .env — this folder is created by the "
            "pipeline, not by a build."
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
