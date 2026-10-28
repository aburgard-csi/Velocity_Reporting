# Ported from v5 02-Scripts/core/env.py at 7ba1e63. Logic unchanged; copied whole.
"""Environment guardrails + atomic writes, shared by every product.

check_environment: the kit needs pandas >= 2.0 (format="mixed" date parsing);
a CSM with pandas 1.x otherwise fails on an opaque TypeError deep in a loader.

write_text_atomic / save_pptx: outputs land whole or not at all. A crash or a
OneDrive lock mid-write must never leave a truncated metrics.json that a
later deck build reads as "unreadable, proceed without". On Windows the
TARGET itself can be locked (the pptx open in PowerPoint); save_pptx then
falls back to a versioned name and says so, instead of dying.
"""

from __future__ import annotations

import os
from pathlib import Path

MIN_PANDAS = (2, 0)


def check_environment(fail) -> None:
    """Call with result.fail (or any callable). No-op when healthy."""
    import pandas as pd
    version = tuple(int(p) for p in pd.__version__.split(".")[:2])
    if version < MIN_PANDAS:
        fail(f"pandas {pd.__version__} is too old for this kit (needs "
             f">= {'.'.join(map(str, MIN_PANDAS))}). Fix: python -m pip install "
             f"--upgrade pandas   (see requirements.txt at the repo root)")


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)
    return path


def save_pptx(prs, out: Path, warn=None) -> Path:
    """Atomic save; on a locked target (PowerPoint / OneDrive) fall back to
    out-2.pptx, out-3.pptx ... and warn with the reason and the fix."""
    out = Path(out)
    tmp = out.with_name(out.stem + ".tmp.pptx")
    prs.save(str(tmp))
    for attempt in range(1, 6):
        target = out if attempt == 1 else out.with_name(f"{out.stem}-{attempt}{out.suffix}")
        try:
            os.replace(tmp, target)
            if attempt > 1 and warn:
                warn(f"{out.name} is locked (open in PowerPoint, or a OneDrive "
                     f"sync lock); deck written to {target.name} instead -- "
                     f"close the file to reuse the original name")
            return target
        except PermissionError:
            continue
    tmp.unlink(missing_ok=True)
    raise PermissionError(f"could not write {out.name} or any -2..-5 variant; "
                          f"close the open copies and re-run")
