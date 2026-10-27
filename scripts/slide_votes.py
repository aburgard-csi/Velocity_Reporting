#!/usr/bin/env python3
"""
slide_votes.py — the CSMs' keep / delete / appendix votes on the slides of every deck.

Aaron, 2026-10-27: "an evaluation process for all of the decks so the CSM can vote whether to keep or
delete a slide, or to add it to an appendix." CSM Sheila's **Slide Review** tab is the front end; this
module owns the record and the arithmetic, and is import-safe (no server, no Outlook, no deck builder).

    One vote  = one small JSON file in Build Artifacts/slide_votes/. Never a shared file that several
                CSMs read, change and write back: on the share the last writer would drop the others'
                votes. A file is written through a `.part` and never changed afterwards.
    Changing a vote = writing a newer file. For one (voter, client, period, deck kind, slide) the
                NEWEST file wins on read; the older ones stay as history.
    A slide is its TITLE, never its position — the same rule the builders follow (`SB(title)`): a
                rebuilt deck that gains a slide moves every number after it. The slide number is stored
                for reference only.

A vote counts across clients under the slide's family and normalised title, so "Account Retention"
voted on in forty clients' decks is one row. The family groups the deck kinds whose slides are the same
slides: RPE (ARS, ICS, MRPC, CP and every combination), TI (both Transaction Intelligence lenses),
COMP (the ARS Companion deck). A Transaction Intelligence title is a headline with the client's own
figures in it, so digits become `#` and the client's name `<client>` before titles are compared; two
headlines that differ in their words still count as two slides.

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

# The tags a deck's file name carries (`<id>-<yyyy.mm>-<TAG>-<client> ...pptx`): the four programs, the
# Transaction Intelligence cut, the ARS Companion deck. A combined deck joins program tags with hyphens;
# a TI deck is `TI-<lens>`. Anything else is OTHER, so an unexpected file is listed rather than refused.
_TOKENS = "ARS|ICS|MRPC|CP|TI|COMP"
DECK_RX = re.compile(r"^(\d{3,5})-(\d{4}\.\d{2})-((?:%s)(?:-(?:%s))*)-(.+)\.pptx$" % (_TOKENS, _TOKENS))
CID_RX = re.compile(r"^\d{3,5}$")


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


def norm_title(title, client_name=""):
    """The slide's identity across clients: lower case, the client's name and every number removed."""
    t = re.sub(r"\s+", " ", str(title or "")).strip()
    if client_name and len(client_name.strip()) > 2:
        t = re.sub(re.escape(client_name.strip()), "<client>", t, flags=re.I)
    t = re.sub(r"\d[\d,.]*", "#", t.lower())
    return t.strip(" .:;-—")


_slides_cache = {}


def deck_slides(path):
    """[{n, title, source}] for every slide of a deck, in order. Cached against the file's size and time.

    The title is the slide's title placeholder when it has text, else its first text shape — the
    convention the validator and the builders read titles by. `source` is the speaker notes' Source line."""
    p = Path(path)
    st = p.stat()
    key = (str(p), st.st_size, st.st_mtime_ns)
    hit = _slides_cache.get(key)
    if hit is not None:
        return hit
    from pptx import Presentation
    prs = Presentation(str(p))
    out = []
    for n, slide in enumerate(prs.slides, 1):
        title = ""
        t = slide.shapes.title
        if t is not None and t.has_text_frame and t.text_frame.text.strip():
            title = t.text_frame.text
        else:
            for sh in slide.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip():
                    title = sh.text_frame.text
                    break
        title = re.sub(r"\s+", " ", title).strip()[:TITLE_MAX] or "(untitled)"
        source = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text if slide.notes_slide.notes_text_frame else ""
            m = re.search(r"Source[s]?\s*[:\-—]\s*(.+)", notes, re.S)
            if m:
                source = re.sub(r"\s+", " ", m.group(1)).strip()[:SOURCE_MAX]
        out.append({"n": n, "title": title, "source": source})
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


def check_vote(client, deck, slide, title, vote, comment=""):
    """The vote as it will be stored, or VoteError. Everything a caller can send is checked here."""
    if not CID_RX.match(str(client or "")):
        raise VoteError("not a client number")
    parsed = parse_deck(deck)
    if str(deck) != os.path.basename(str(deck)) or "\\" in str(deck):
        raise VoteError("that is not one of this client's decks")
    if parsed is None or parsed[0] != str(client):
        raise VoteError("that is not one of this client's decks")
    if vote not in VOTES:
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
    return {"client": str(client), "deck": os.path.basename(str(deck)), "slide": slide, "title": title,
            "vote": vote, "comment": comment}


def write_vote(client, deck, slide, title, vote, comment="", voter=None, client_name=""):
    """Record one vote as its own file. Returns the stored document."""
    v = check_vote(client, deck, slide, title, vote, comment)
    cid, period, kind, family = parse_deck(v["deck"])
    voter = str(voter or whoami())[:60]
    doc = {"v": 1, "voter": voter, "client": cid, "period": period, "kind": kind, "family": family,
           "deck": v["deck"], "slide": v["slide"], "title": v["title"],
           "key": family + "|" + norm_title(v["title"], client_name), "vote": v["vote"],
           "comment": v["comment"], "at": _now()}
    d = votes_dir()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", voter)[:40]
    tag = hashlib.sha1(json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    final = d / f"{doc['at'].replace(':', '').replace('-', '').replace('.', '')}-{safe}-{cid}-{tag}.json"
    part = final.with_name(final.name + ".part")
    part.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(part, final)
    _files.pop(final.name, None)
    return doc


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
            ok = (isinstance(doc, dict) and doc.get("vote") in VOTES and doc.get("key") and doc.get("client")
                  and doc.get("voter") and doc.get("at"))
            _files[n] = doc if ok else None
        except (OSError, ValueError):
            _files[n] = None
    docs = [(doc.get("at", ""), n, doc) for n, doc in _files.items() if doc]
    return [doc for _, _, doc in sorted(docs, key=lambda t: (t[0], t[1]))]


def latest(votes):
    """The newest vote per (voter, client, period, deck kind, slide): what anyone currently holds."""
    cur = {}
    for v in votes:                       # oldest first, so a later one replaces
        cur[(v["voter"], v["client"], v.get("period", ""), v.get("kind", ""), v["key"])] = v
    return list(cur.values())


def mine(votes, voter, client, deck):
    """{slide title: vote doc} — this voter's current votes on one deck, by title."""
    return {v["title"]: v for v in latest(votes)
            if v["voter"] == voter and v["client"] == client and v.get("deck") == deck}


def aggregate(votes, family=None):
    """One row per slide (family, normalised title), with the vote counts, who and where, and the comments.

    Sorted so the slides most likely to go surface first: most delete votes, then the largest share of
    them, then the most votes overall."""
    rows = {}
    for v in latest(votes):
        if family and v.get("family") != family:
            continue
        r = rows.setdefault(v["key"], {"key": v["key"], "family": v.get("family", ""), "title": v["title"],
                                       "keep": 0, "delete": 0, "appendix": 0, "clients": set(),
                                       "voters": set(), "kinds": set(), "comments": [], "_at": ""})
        r[v["vote"]] += 1
        r["clients"].add(v["client"])
        r["voters"].add(v["voter"])
        r["kinds"].add(v.get("kind", ""))
        if v.get("comment"):
            r["comments"].append({"voter": v["voter"], "client": v["client"], "vote": v["vote"],
                                  "text": v["comment"], "at": v["at"]})
        if v["at"] >= r["_at"]:
            r["_at"], r["title"] = v["at"], v["title"]
    out = []
    for r in rows.values():
        total = r["keep"] + r["delete"] + r["appendix"]
        top = max(VOTES, key=lambda k: (r[k], -VOTES.index(k)))
        ranked = sorted((r[k] for k in VOTES), reverse=True)
        r.update(total=total, clients=sorted(r["clients"]), voters=sorted(r["voters"]),
                 kinds=sorted(r["kinds"]), leading=("split" if ranked[0] == ranked[1] else top),
                 comments=sorted(r["comments"], key=lambda c: c["at"], reverse=True))
        del r["_at"]
        out.append(r)
    out.sort(key=lambda r: (-r["delete"], -(r["delete"] / r["total"] if r["total"] else 0), -r["total"], r["title"]))
    return out


def summary_csv(rows):
    """The Summary as CSV text, one line per slide."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Deck family", "Slide", "Keep", "Delete", "Appendix", "Leading", "Clients", "Voters",
                "Deck kinds", "Comments"])
    for r in rows:
        w.writerow([r["family"], r["title"], r["keep"], r["delete"], r["appendix"], r["leading"],
                    len(r["clients"]), len(r["voters"]), " ".join(r["kinds"]),
                    " | ".join(f'{c["voter"]} ({c["client"]}, {c["vote"]}): {c["text"]}' for c in r["comments"])])
    return buf.getvalue()


if __name__ == "__main__":
    if sys.argv[1:] == ["summary"]:
        for r in aggregate(read_votes()):
            print(f'{r["family"]:5} keep {r["keep"]:3} delete {r["delete"]:3} appendix {r["appendix"]:3}  {r["title"]}')
    else:
        print(__doc__)
