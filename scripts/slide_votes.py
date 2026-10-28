#!/usr/bin/env python3
"""
slide_votes.py — the CSMs' keep / delete / appendix votes, and favourite stars, on each program's slides.

Aaron, 2026-10-27: "an evaluation process for all of the decks so the CSM can vote whether to keep or
delete a slide, or to add it to an appendix." Aaron, 2026-10-28: the page is "not tied to a client ... a CSM can
open Sheila and a deck side by side and make their election. The Summary should be for ARS, ICS, MRPC slides, etc.
in whole, not per client", with "a little clickable Star icon where we can select favorite slides."
CSM Sheila's **Slide Review** tab is the front end; this module owns the record and the arithmetic, and is
import-safe (no server, no Outlook, no deck builder).

    A vote is on a PROGRAM's slide (ARS, ICS, MRPC, CP, TI, COMP), never on a client's. The tab lists each
                program's slides from the newest decks in Outputs; the CSM reads them in a deck open beside Sheila.
    One vote  = one small JSON file in Build Artifacts/slide_votes/. Never a shared file that several
                CSMs read, change and write back: on the share the last writer would drop the others'
                votes. A file is written through a `.part` and never changed afterwards.
    Changing a vote or a star = writing a newer file that carries the whole current state (vote, comment, star).
                For one (voter, program, slide) the NEWEST file wins on read; the older ones stay as history.
    A slide is its TITLE, never its position — the same rule the builders follow (`SB(title)`): a
                rebuilt deck that gains a slide moves every number after it. The slide number is stored
                for reference only. A title is compared with the client's name and every number taken out
                (Transaction Intelligence headlines carry the client's own figures).
    A star is the voter's favourite flag, beside the vote: a slide can be starred and kept, or starred
                and moved to an appendix.

    python scripts/slide_votes.py summary      # what the Summary view shows
"""
import datetime as dt
import getpass
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (HERE.parent / "build", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rpe_env as R  # noqa: E402

VOTES = ("keep", "delete", "appendix")
FOLDER = "slide_votes"
TITLE_MAX = 200
COMMENT_MAX = 500
SOURCE_MAX = 240

PROGRAMS = ("ARS", "ICS", "MRPC", "CP", "TI", "COMP")
PROGRAM_LABEL = {"ARS": "ARS", "ICS": "ICS", "MRPC": "MRPC", "CP": "CashPlease",
                 "TI": "Transaction Intelligence", "COMP": "ARS Companion"}
SHARED = "Shared"          # cover, agenda, dividers, Questions, Contact: in every deck, not voted on
_DIVIDER_WORDS = (("ARS", ("account revenue solution",)), ("ICS", ("invitation checking",)),
                  ("MRPC", ("myrewards",)), ("CP", ("cashplease",)))
_SHARED_TITLES = ("questions", "contact", "agenda", "executive summit", "the executive summit",
                  "velocity executive summit")

# The tags a deck's file name carries (`<id>-<yyyy.mm>-<TAG>-<client> ...pptx`): the four programs, the
# Transaction Intelligence cut, the ARS Companion deck. A combined deck joins program tags with hyphens;
# a TI deck is `TI-<lens>`.
_TOKENS = "ARS|ICS|MRPC|CP|TI|COMP"
DECK_RX = re.compile(r"^(\d{3,5})-(\d{4}\.\d{2})-((?:%s)(?:-(?:%s))*)-(.+)\.pptx$" % (_TOKENS, _TOKENS))


class VoteError(ValueError):
    """A vote that cannot be recorded; the message is for the CSM."""


# ------------------------------------------------------------------ decks
def parse_deck(name):
    """(client id, period, kind, family) from a deck file name, or None when it is not one of ours."""
    m = DECK_RX.match(os.path.basename(str(name)))
    if not m:
        return None
    kind = m.group(3)
    family = "TI" if kind.startswith("TI") else "COMP" if kind.startswith("COMP") else "RPE"
    return m.group(1), m.group(2), kind, family


def deck_programs(kind):
    """The programs whose slides a deck of this kind can carry: 'ARS-ICS-MRPC' -> ARS, ICS, MRPC; 'TI-ARS' -> TI."""
    if kind.startswith("TI"):
        return ["TI"]
    if kind.startswith("COMP"):
        return ["COMP"]
    return [t for t in kind.split("-") if t in ("ARS", "ICS", "MRPC", "CP")]


def norm_title(title, client_name=""):
    """The slide's identity across clients: lower case, the client's name and every number removed."""
    t = re.sub(r"\s+", " ", str(title or "")).strip()
    if client_name and len(client_name.strip()) > 2:
        t = re.sub(re.escape(client_name.strip()), "<client>", t, flags=re.I)
    t = re.sub(r"\d[\d,.]*", "#", t.lower())
    return t.strip(" .:;-—")


def _first_line(slide):
    """The first line of the first text shape that is not just a slide number."""
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() and not sh.text_frame.text.strip().isdigit():
            return sh.text_frame.text.strip().splitlines()[0].strip()
    return ""


def _all_text(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def _is_shared(slide, first):
    if first.lower().startswith(_SHARED_TITLES):
        return True
    return "Executive Review  •" in _all_text(slide)       # the cover


def _divider_program(slide, first):
    """The program a section divider opens, else None. A divider is short: name, benefits line, figures."""
    low = first.lower().replace("®", "").strip()
    for prog, words in _DIVIDER_WORDS:
        if any(low == w or low.startswith(w + " ") for w in words):
            text = _all_text(slide)
            if len(text) < 500 and "Executive Review  •" not in text:
                return prog
    return None


_slides_cache = {}


def deck_slides(path):
    """[{n, title, source, program}] for every slide of a deck, in order. Cached against the file's size and time.

    The title is the slide's title placeholder when it has text, else its first text shape — the
    convention the validator and the builders read titles by. `source` is the speaker notes' Source line.
    `program` is the program the slide belongs to (ARS, ICS, MRPC, CP, TI, COMP) or SHARED: a single-program deck
    is all its program's; a combined deck is walked section by section from each divider, and the ARS Appendix,
    which follows Questions and Contact, is ARS's."""
    p = Path(path)
    st = p.stat()
    key = (str(p), st.st_size, st.st_mtime_ns)
    hit = _slides_cache.get(key)
    if hit is not None:
        return hit
    from pptx import Presentation
    prs = Presentation(str(p))
    parsed = parse_deck(p.name)
    progs = deck_programs(parsed[2]) if parsed else []
    combined = len(progs) > 1
    current = progs[0] if len(progs) == 1 else None
    out = []
    for n, slide in enumerate(prs.slides, 1):
        title = ""
        t = slide.shapes.title
        if t is not None and t.has_text_frame and t.text_frame.text.strip():
            title = t.text_frame.text
        else:
            title = _first_line(slide)
        title = re.sub(r"\s+", " ", title).strip()[:TITLE_MAX] or "(untitled)"
        source = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text if slide.notes_slide.notes_text_frame else ""
            m = re.search(r"Source[s]?\s*[:\-—]\s*(.+)", notes, re.S)
            if m:
                source = re.sub(r"\s+", " ", m.group(1)).strip()[:SOURCE_MAX]
        first = _first_line(slide)
        prog = current
        if combined:
            opens = _divider_program(slide, first)
            if opens:
                current, prog = opens, SHARED
            elif first.lower().startswith(("questions", "contact")):
                current, prog = None, SHARED
            elif current is None and title.lower().startswith("appendix") and "ARS" in progs:
                current = prog = "ARS"              # the ARS Appendix follows Contact; its pages follow it
            elif _is_shared(slide, first):
                prog = SHARED
            else:
                prog = current or SHARED
        elif parsed and (_is_shared(slide, first) or _divider_program(slide, first)):
            prog = SHARED
        out.append({"n": n, "title": title, "source": source, "program": prog or SHARED})
    for k in [k for k in _slides_cache if k[0] == str(p)]:
        del _slides_cache[k]
    _slides_cache[key] = out
    return out


# ------------------------------------------------------------------ the record
def votes_dir(create=True):
    d = R.build_artifacts() / FOLDER
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def whoami():
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME") or "unknown"


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def check_vote(program, slide, title, vote, comment="", star=False):
    """The vote as it will be stored, or VoteError. Everything a caller can send is checked here.

    `vote` may be empty when the slide is only starred: a star is a favourite flag beside the vote."""
    if program not in PROGRAMS:
        raise VoteError("not a program")
    vote = vote or ""
    if (vote and vote not in VOTES) or (not vote and not star):
        raise VoteError("a vote is keep, delete or appendix")
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    if not title:
        raise VoteError("the slide has no title")
    if len(title) > TITLE_MAX:
        raise VoteError("the slide title is too long")
    try:
        slide = int(slide)
    except (TypeError, ValueError):
        raise VoteError("not a slide number")
    if slide < 1 or slide > 999:
        raise VoteError("not a slide number")
    comment = str(comment or "").strip()
    if len(comment) > COMMENT_MAX:
        raise VoteError(f"keep the comment under {COMMENT_MAX} characters")
    return {"program": program, "slide": slide, "title": title, "vote": vote, "comment": comment, "star": bool(star)}


def write_vote(program, slide, title, vote, comment="", star=False, voter=None, client_name="", deck=""):
    """Record one vote (and the star beside it) as its own file. Returns the stored document.

    Each document carries the voter's whole current state for the slide (vote, comment, star), so the newest
    one is all anyone needs to read. `deck` names the reference deck the slide was read from, for the record."""
    v = check_vote(program, slide, title, vote, comment, star)
    voter = str(voter or whoami())[:60]
    doc = {"v": 2, "voter": voter, "program": program, "slide": v["slide"], "title": v["title"],
           "key": program + "|" + norm_title(v["title"], client_name), "vote": v["vote"], "star": v["star"],
           "comment": v["comment"], "deck": os.path.basename(str(deck or "")), "at": _now()}
    d = votes_dir()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", voter)[:40]
    tag = hashlib.sha1(json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    final = d / f"{doc['at'].replace(':', '').replace('-', '').replace('.', '')}-{safe}-{program}-{tag}.json"
    part = final.with_name(final.name + ".part")
    part.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(part, final)
    _files.pop(final.name, None)
    return doc


def _legacy(doc):
    """A first-round vote (per client and deck, 2026-10-27) as a program vote. A single-program, TI or Companion
    deck maps to its program; a combined deck's slide cannot be placed in one program, so it is left out."""
    progs = deck_programs(str(doc.get("kind", "")))
    if len(progs) != 1:
        return None
    return dict(doc, program=progs[0], star=False, v=1,
                key=progs[0] + "|" + str(doc.get("key", "")).split("|", 1)[-1])


_files = {}            # file name -> parsed document (a vote file never changes once written) or None


def read_votes():
    """Every vote on record, oldest first. A damaged file is skipped, not fatal; each file is read once."""
    d = votes_dir(create=False)
    if not d.is_dir():
        return []
    names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
    for gone in set(_files) - set(names):
        del _files[gone]
    for n in names:
        if n in _files:
            continue
        try:
            doc = json.loads((d / n).read_text(encoding="utf-8"))
            if isinstance(doc, dict) and not doc.get("program"):
                doc = _legacy(doc) if doc.get("vote") in VOTES else None
            ok = (isinstance(doc, dict) and doc.get("program") in PROGRAMS and doc.get("key") and doc.get("voter")
                  and doc.get("at") and (doc.get("vote") in VOTES or (doc.get("star") and not doc.get("vote"))))
            _files[n] = doc if ok else None
        except (OSError, ValueError):
            _files[n] = None
    docs = [(doc.get("at", ""), n, doc) for n, doc in _files.items() if doc]
    return [doc for _, _, doc in sorted(docs, key=lambda t: (t[0], t[1]))]


def latest(votes):
    """The newest document per (voter, program, slide): what anyone currently holds."""
    cur = {}
    for v in votes:                       # oldest first, so a later one replaces
        cur[(v["voter"], v["key"])] = v
    return list(cur.values())


def mine(votes, voter, program):
    """{slide key: document} — this voter's current votes and stars on one program's slides."""
    return {v["key"]: v for v in latest(votes) if v["voter"] == voter and v["program"] == program}


def aggregate(votes, program=None):
    """One row per slide (program, normalised title), with the vote counts, stars, who, and the comments.

    Sorted so the slides most likely to go surface first: most delete votes, then the largest share of
    them, then the most votes overall, then the most stars."""
    rows = {}
    for v in latest(votes):
        if program and v.get("program") != program:
            continue
        r = rows.setdefault(v["key"], {"key": v["key"], "program": v["program"], "title": v["title"],
                                       "keep": 0, "delete": 0, "appendix": 0, "stars": 0,
                                       "voters": set(), "comments": [], "_at": ""})
        if v.get("vote") in VOTES:
            r[v["vote"]] += 1
        if v.get("star"):
            r["stars"] += 1
        r["voters"].add(v["voter"])
        if v.get("comment"):
            r["comments"].append({"voter": v["voter"], "vote": v.get("vote", ""), "text": v["comment"], "at": v["at"]})
        if v["at"] >= r["_at"]:
            r["_at"], r["title"] = v["at"], v["title"]
    out = []
    for r in rows.values():
        total = r["keep"] + r["delete"] + r["appendix"]
        ranked = sorted((r[k] for k in VOTES), reverse=True)
        top = max(VOTES, key=lambda k: (r[k], -VOTES.index(k)))
        r.update(total=total, voters=sorted(r["voters"]),
                 leading=("" if not total else "split" if ranked[0] == ranked[1] else top),
                 comments=sorted(r["comments"], key=lambda c: c["at"], reverse=True))
        del r["_at"]
        out.append(r)
    out.sort(key=lambda r: (-r["delete"], -(r["delete"] / r["total"] if r["total"] else 0), -r["total"],
                            -r["stars"], r["title"]))
    return out


def summary_csv(rows):
    """The Summary as CSV text, one line per slide."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Program", "Slide", "Keep", "Delete", "Appendix", "Stars", "Leading", "Voters", "Comments"])
    for r in rows:
        w.writerow([PROGRAM_LABEL.get(r["program"], r["program"]), r["title"], r["keep"], r["delete"], r["appendix"],
                    r["stars"], r["leading"], len(r["voters"]),
                    " | ".join(f'{c["voter"]} ({c["vote"] or "star"}): {c["text"]}' for c in r["comments"])])
    return buf.getvalue()


if __name__ == "__main__":
    if sys.argv[1:] == ["summary"]:
        for r in aggregate(read_votes()):
            print(f'{r["program"]:5} keep {r["keep"]:3} delete {r["delete"]:3} appendix {r["appendix"]:3} '
                  f'stars {r["stars"]:3}  {r["title"]}')
    else:
        print(__doc__)
