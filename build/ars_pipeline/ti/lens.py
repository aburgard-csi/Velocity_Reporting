"""
lens.py — the two lenses of the Transaction Intelligence cut, on a client's ODD frame.

  ARS lens  responders · mailed non-responders · not mailed
  ICS lens  all ICS accounts · ICS direct mail · ICS referral

The masks are v5's (`ti/core/account_lenses.py`). The ICS accounts are found the way v5
finds them (`ti/monthly_analysis/ics_sources.py`): the client's direct-mail and referral
lists are joined onto the ODD by account hash, and the frame gets a `DM-REF Source` column.

v5 reads both lists from one folder per client. RPE files them by kind, each named from the
client id: `Inputs/ICS Direct Mail/<id>-<yyyy.mm>-ICS-…-Direct Mail …xlsx` and
`Inputs/ICS Referrals/<id>_ics_detailed referral_v<N>.xls`. `stage_ics_lists` copies the
client's newest of each into a scratch folder and hands that to v5's join unchanged.

A lens that cannot be built is said so, never rendered empty: `LensUnavailable` carries
the sentence the deck states.
"""
import re
import shutil
from pathlib import Path

from ti import cut
from ti.core import account_lenses as AL
from ti.monthly_analysis import ics_sources


class LensUnavailable(Exception):
    """The lens has no accounts to show for this client; str() is the sentence to state."""


def _newest(folder: Path, client_id, pattern):
    if not folder.is_dir():
        return None
    rx = re.compile(rf"^{re.escape(str(client_id))}\D")
    # The id is also read where a person put it by hand: a folder named for the client
    # (`ICS Referrals/1766/`) or the id closing the name (`ics_detailed referral_1766.xls`).
    rx_any = re.compile(rf"(?<!\d){re.escape(str(client_id))}(?!\d)")
    own = folder / str(client_id)
    candidates = [p for p in folder.iterdir() if p.is_file() and rx.match(p.name)]
    if own.is_dir():
        candidates += [p for p in own.iterdir() if p.is_file()]
    candidates += [p for p in folder.iterdir() if p.is_file() and not rx.match(p.name)
                   and rx_any.search(p.stem)]
    hits = [p for p in candidates
            if re.search(pattern, p.name, re.I) and not p.name.startswith("~$")]
    return max(hits, key=lambda p: (p.name, p.stat().st_mtime)) if hits else None


def ics_list_files(client_id) -> dict:
    """{'DM': path|None, 'REF': path|None}: the client's newest list of each kind."""
    import rpe_env
    return {"DM": _newest(rpe_env.input_dir("ICS direct mail", create=False), client_id,
                          r"direct mail.*\.xlsx?$"),
            "REF": _newest(rpe_env.input_dir("ICS referrals", create=False), client_id,
                           r"referral.*\.xlsx?$")}


def stage_ics_lists(client_id):
    """A scratch folder holding the client's lists, as v5's join expects; None when there are none."""
    files = ics_list_files(client_id)
    if not any(files.values()):
        return None
    import rpe_env
    folder = Path(rpe_env.temp_dir("oddd_"))
    for p in files.values():
        if p is not None:
            shutil.copy2(p, folder / p.name)
    return folder


def attach_ics(frame, client_id, warn, expected=False):
    """The frame with `DM-REF Source` stamped from the client's ICS lists (v5's join)."""
    folder = stage_ics_lists(client_id)
    if folder is None:
        if expected:
            warn(f"ICS: no direct-mail or referral list for client {client_id} in Inputs; "
                 f"the ICS lens and the ICS chapter are stated, not rendered")
        return frame
    return ics_sources.attach(frame, folder, warn, expected=expected)


def lens_masks(frame, lens_key, anchor_end, warn=lambda *_a: None) -> dict:
    """{group key: boolean mask} for the lens's groups, in display order.

    Raises LensUnavailable when the lens has no group with an account in it."""
    ln = cut.lens(lens_key)
    masks = AL.masks_for(frame, anchor_end, warn)
    out = {k: masks[k] for k in ln.groups if k in masks and bool(masks[k].any())}
    if not out:
        if ln.key == "ics":
            raise LensUnavailable("No ICS accounts were found in this extract: the client's "
                                  "direct-mail and referral lists did not match any account.")
        raise LensUnavailable("No responder, mailed non-responder or not-mailed group "
                              "could be formed from this extract.")
    return out


def label(key) -> str:
    return AL.label(key)
