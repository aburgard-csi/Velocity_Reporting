"""What Sheila does, as opposed to what she reports: builds, a deck's review list, where a slide's figures
came from, and the two ILS analyses. Each start returns at once; the work runs in Sheila's own queue
(ars_launcher_web.start_build / ils_runs.start), one build at a time on this PC, the page's included.
"""
import re

import rpe_env as R

from . import core
from .core import find_client, label, reply, web

STEP_RX = re.compile(r"^\s*\[(ok|!!|built|STOP|\.\.)\]\s+(.*)$")
MINUTES = {"ars": "about 5 minutes", "combined": "about 5 to 10 minutes", "companion": "about 5 minutes",
           "ti": "about 25 minutes, plus validation"}


# ------------------------------------------------------------------ building
def _block(st, kind):
    """(state, checks) of the build this kind starts."""
    if kind in ("ti", "companion"):
        blk = st.get(kind) or {}
        return blk.get("state"), blk.get("checks") or []
    return st.get("state"), st.get("checks") or []


def build(client, kind="ars", confirm=False, deck_only=False):
    """Start a build. A deck already in Outputs (or marked sent) is replaced only with confirm=True."""
    c, why = find_client(client)
    if why:
        return reply(why)
    kind = (kind or "ars").lower()
    if kind not in core.KINDS:
        return reply(f"kind is one of {', '.join(core.KINDS)}.")
    if deck_only and kind != "ti":
        return reply("deck_only redraws Transaction Intelligence decks only.")
    W = web()
    st = W.status_doc(c["id"], fresh=True)
    b = st.get("builds") or {}
    if kind in ("ti", "companion") and not st.get(kind):
        return reply(f"{label(c)} has no {'Transaction Intelligence' if kind == 'ti' else 'ARS Companion'} "
                     "deck to build: it is for ARS clients.", client=c["id"])
    if kind == "combined" and not b.get("combined"):
        return reply(f"{label(c)} has no combined deck on offer this cycle: "
                     + ("; ".join(f"{p}: {r}" for p, r in (b.get("left_out") or {}).items()) or "no other program has data")
                     + ".", client=c["id"])
    # The page's own rule: a client with no ARS, and Aaron's multi-program clients, have only the combined
    # button, so "build 1539" means that one.
    combined = kind == "combined" or (kind == "ars" and not b.get("ars_only", True))
    if combined and not b.get("combined"):
        return reply(f"{label(c)} has nothing to build this cycle: no program has its data.", client=c["id"])
    state, checks = _block(st, kind)
    if state == "stop":
        stops = [k["text"] for k in checks if k.get("level") == "stop"]
        return reply(f"Not started: {label(c)} can't build yet.\n" + "\n".join(f"  [STOP] {t}" for t in stops),
                     client=c["id"], state=state, checks=checks)
    asks = [k["text"] for k in checks if k.get("level") == "ask"]
    if (state == "ask" or deck_only) and not confirm:
        what = asks or ["This replaces the Transaction Intelligence decks in Outputs."]
        return reply(f"Not started yet. {label(c)}: " + " ".join(what)
                     + " Building again replaces it, and the one it replaces goes to _Archive. "
                     "Ask the CSM to confirm, then call build again with confirm=true.",
                     client=c["id"], needs_confirm=True, would_replace=what)
    programs = (b.get("combined") if combined else b.get("base")) or []
    what = {"ti": "the Transaction Intelligence decks" + (" (redrawn from the last build's figures)" if deck_only else ""),
            "companion": "the ARS Companion deck"}.get(kind, "the " + " + ".join(programs) + " deck")
    code, doc = W.start_build(c["id"], state == "ask" or bool(deck_only), combined and kind not in ("ti", "companion"),
                              ti=kind == "ti", companion=kind == "companion",
                              **({"deck_only": True} if deck_only else {}))
    if code != 202:
        return reply(f"Not started: {doc.get('error')}", client=c["id"])
    when = f"queued #{doc['queued']} behind {doc['after']}" if doc.get("queued") else "started"
    return reply(f"{label(c)}: {what} {when}, cycle {st.get('period')}. "
                 f"It takes {('under a minute' if deck_only else MINUTES[kind])}. "
                 "Ask for its progress any time; nothing reaches Outputs unless it passes.",
                 client=c["id"], kind=kind, job=doc)


def _job_text(c, j):
    steps = [STEP_RX.match(l) for l in j.get("lines") or []]
    steps = [m.group(2).strip() for m in steps if m]
    mins = j.get("seconds", 0) // 60
    if j.get("queued"):
        return f"{label(c)}: queued #{j['queued']}, behind {j.get('after')}."
    if not j.get("done"):
        return f"{label(c)}: building, {mins} min so far. Now: {steps[-1] if steps else 'starting'}."
    if not j.get("code") and j.get("deck"):
        verdict = next((s for s in reversed(steps) if "FAIL," in s), "")
        return f"{label(c)}: done in {mins} min. In Outputs: {j['deck']}" + (f" ({verdict.split(':', 1)[-1].strip()})" if verdict else "") + "."
    tail = [l for l in j.get("lines") or [] if l.strip()][-6:]
    return f"{label(c)}: NOT put in Outputs. The launcher said:\n" + "\n".join(tail)


def build_progress(client):
    """Where a build stands: queued, the step it's on, or how it ended (the launcher's words if it failed)."""
    c, why = find_client(client)
    if why:
        return reply(why)
    W = web()
    j = W.job_doc(c["id"])
    if j:
        return reply(_job_text(c, j), client=c["id"], job={k: v for k, v in j.items() if k != "lines"},
                     steps=[m.group(2) for m in map(STEP_RX.match, j.get("lines") or []) if m])
    # Not built from this Claude session: report the last build on record, whoever ran it.
    st = W.status_doc(c["id"])
    out = []
    for key, title, last in (("ars", "Deck", st.get("last")), ("ti", "Transaction Intelligence", (st.get("ti") or {}).get("last")),
                             ("companion", "ARS Companion", (st.get("companion") or {}).get("last"))):
        if last:
            out.append(f"{title}: last built {last.get('finished')}"
                       + (f", {last.get('result')}" if last.get("result") else "")
                       + (", in Outputs." if last.get("delivered") else ", NOT put in Outputs."))
    return reply(f"{label(c)}: no build running from here. " + (" ".join(out) if out else "No build on record this cycle."),
                 client=c["id"])


def queue():
    q = web().queue_doc()
    if not q.get("building") and not q.get("queued"):
        return reply("Nothing is building from Claude on this PC.", **q)
    return reply(f"Building: {q.get('building') or 'nothing'}. Waiting: {', '.join(q.get('queued') or []) or 'none'}.", **q)


# ------------------------------------------------------------------ review and provenance
def _work_deck(cid, deck):
    period = re.match(r"^\d+-(\d{4}\.\d{2})-", deck.name).group(1)
    base = R.build_artifacts() / "launcher" / period / cid
    for p in (base / deck.name, base / "ti" / deck.name, base / "companion" / deck.name):
        if p.is_file():
            return p
    return None


def review_items(deck_path, cid):
    """[(level, slide or None, message)] from the validator's report kept beside the built deck."""
    import ars_launcher as L
    from pathlib import Path
    work = _work_deck(cid, Path(deck_path))
    rpt = Path(str(work) + L.VALIDATION_SUFFIX) if work else None
    if not rpt or not rpt.is_file():
        return None
    out = []
    for line in rpt.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^\s*\[(FAIL|REVIEW)\s*\]\s+(slide (\d+)|deck-wide)\s+(.*)$", line)
        if m:
            out.append((m.group(1), int(m.group(3)) if m.group(3) else None, m.group(4).strip()))
    return out


def review(client, kind="ars"):
    """What the validator asked a person to look at in the client's deck, slide by slide."""
    c, why = find_client(client)
    if why:
        return reply(why)
    deck = core.find_deck(c["id"], kind)
    if not deck:
        return reply(f"{label(c)} has no {kind.upper()} deck in Outputs.", client=c["id"])
    items = review_items(deck, c["id"])
    if items is None:
        return reply(f"{label(c)}: {deck.name} was built before Sheila kept the validator's report, so only its "
                     "count is known (see deck_summary). The next build keeps the full list.", client=c["id"])
    if not items:
        return reply(f"{label(c)}: nothing to review in {deck.name}.", client=c["id"], items=[])
    lines = [f"{label(c)}: {sum(1 for i in items if i[0] == 'FAIL')} FAIL, "
             f"{sum(1 for i in items if i[0] == 'REVIEW')} REVIEW in {deck.name}:"]
    lines += [f"  [{lvl}] {'slide ' + str(n) if n else 'deck-wide'}: {msg}" for lvl, n, msg in items]
    return reply("\n".join(lines), client=c["id"], deck=str(deck), items=items)


FIGURE_RX = re.compile(r"(?<![A-Za-z\d.])\$?\d[\d,]*(?:\.\d+)?(?:%|[KMB]\b)?")


def figures_in(text, slide_no=None):
    """The numbers a slide states, in reading order: not its page number, not a bare year, not the
    digits of a month label like Aug26."""
    out = []
    for f in FIGURE_RX.findall(text):
        bare = f.strip("$%KMB")
        if bare == str(slide_no) or re.fullmatch(r"(19|20)\d\d", bare) or f in out:
            continue
        out.append(f)
    return out


def explain(client, slide, kind="ars"):
    """One slide: its headline, every figure on it, the source its notes name, and any review finding."""
    c, why = find_client(client)
    if why:
        return reply(why)
    deck = core.find_deck(c["id"], kind)
    if not deck:
        return reply(f"{label(c)} has no {kind.upper()} deck in Outputs.", client=c["id"])
    from pptx import Presentation
    pres = Presentation(str(deck))
    n = int(slide)
    if not 1 <= n <= len(pres.slides):
        return reply(f"{deck.name} has {len(pres.slides)} slides.", client=c["id"])
    s = pres.slides[n - 1]
    texts = sorted((sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()),
                   key=lambda sh: (sh.top or 0, sh.left or 0))
    words = [" ".join(sh.text_frame.text.split()) for sh in texts]
    tables = []
    for sh in s.shapes:
        if sh.has_table:
            tables.append([[cell.text.strip() for cell in row.cells] for row in sh.table.rows])
    notes = s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
    figures = figures_in(" ".join(words), n)
    found = [i for i in (review_items(deck, c["id"]) or []) if i[1] == n]
    lines = [f"{label(c)}, {deck.name}, slide {n}:", f"Headline: {words[0] if words else '(no text)'}"]
    if len(words) > 1:
        lines.append("Other text: " + " | ".join(words[1:6]))
    if figures:
        lines.append("Figures on the slide: " + ", ".join(figures[:20]))
    if tables:
        lines.append(f"{len(tables)} table(s); first row: " + " | ".join(tables[0][0]))
    lines.append("Source (the slide's notes): " + (notes or "none recorded on this slide."))
    for lvl, _, msg in found:
        lines.append(f"Validator {lvl}: {msg}")
    return reply("\n".join(lines), client=c["id"], deck=str(deck), slide=n, text=words, tables=tables,
                 notes=notes, figures=figures, review=found)


# ------------------------------------------------------------------ ILS
def ils_status(client):
    """The two ILS cards: whether an extract has landed, the codes last confirmed, the newest deck, a run."""
    import ils_runs
    text = str(client or "").strip()
    if not re.fullmatch(r"\d{3,5}", text):
        c, why = find_client(client)
        if why:
            return reply(why)
        text = c["id"]
    doc = ils_runs.client_doc(text)
    lines = [f"ILS for {text}:"]
    for kind, k in doc["kinds"].items():
        if k.get("error"):
            lines.append(f"  {k['label']}: {k['error']}")
            continue
        if not k.get("exists"):
            lines.append(f"  {k['label']}: no extract yet. It goes in {k['folder']}.")
            continue
        bits = [f"extract {k['extract']}" if k.get("extract") else f"no extract file in {k['folder']} now"]
        if k.get("period"):
            bits.append(f"period {k['period']}")
        if k.get("saved"):
            bits.append(f"codes last confirmed {k['saved'].get('confirmed')} on {k['saved'].get('extract')}")
        last = k.get("last")
        if last:
            bits.append(f"newest deck {last.get('deck') or last.get('name')} ({last.get('when')})"
                        if isinstance(last, dict) else f"newest output {last}")
        job = k.get("job")
        if job and not job.get("done"):
            bits.append(f"step {job['step']} running")
        lines.append(f"  {k['label']}: " + "; ".join(str(b) for b in bits) + ".")
    return reply("\n".join(lines), **doc)


def ils_run(client, kind, codes=None, period=None, fee=None):
    """Step 1 (no codes): the field summary, computing nothing. Step 2: the run on the codes the CSM confirmed."""
    import ils_runs
    kind = (kind or "").lower()
    if kind not in ils_runs.KINDS:
        return reply("kind is pgl or kickoff.")
    c, why = find_client(client)
    cid = c["id"] if c else str(client).strip()
    if why and not re.fullmatch(r"\d{3,5}", cid):
        return reply(why)
    body = {"kind": kind, "client": cid, "client_name": (c or {}).get("name") or ""}
    if codes:
        body["codes"] = codes
    if period:
        body["period"] = period
    if fee not in (None, ""):
        body["fee"] = fee
    code, doc = ils_runs.start(body)
    if code != 200:
        return reply(f"Not started: {doc.get('error')}", **doc)
    step = doc["job"]["step"]
    return reply(f"ILS {ils_runs.KINDS[kind]['label']} for {cid}: step {step} of 2 started. "
                 + ("It reads the extract's code fields and computes nothing; ask for its progress to see the "
                    "field summary, then confirm which values mean what." if step == 1 else
                    "It runs on the codes you confirmed. Ask for its progress."), **doc)


def ils_progress(client, kind):
    import ils_runs
    kind = (kind or "").lower()
    cid = str(client).strip()
    if not re.fullmatch(r"\d{3,5}", cid):
        c, why = find_client(client)
        if why:
            return reply(why)
        cid = c["id"]
    j = ils_runs.job_doc(kind, cid)
    if not j:
        return reply(f"No ILS {kind} run from here for {cid}.")
    if not j["done"]:
        return reply(f"ILS {kind} for {cid}: step {j['step']} running, {j['seconds']} s.", job=j)
    body = "\n".join(j["lines"][-80:])
    if j.get("needs_codes"):
        sug = j.get("suggested") or {}
        return reply(f"ILS {kind} for {cid}, step 1 done. The field summary:\n{body}\n\n"
                     + (f"Suggested from the last confirmed run ({j.get('suggested_basis')}): {sug}. " if sug else "")
                     + "The CSM decides which value means what. Then call ils_run with those codes.", job=j)
    if j.get("ok"):
        return reply(f"ILS {kind} for {cid}: done. Deck: {j.get('deck')}; folder: {j.get('folder')}.", job=j)
    return reply(f"ILS {kind} for {cid}: failed. {j.get('error') or ''}\n{body}", job=j)
