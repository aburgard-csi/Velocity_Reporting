"""What Sheila answers, one function per question. Each returns {"answer": text for Claude to relay,
"data": the same facts as fields}, built from the functions Sheila's page calls (ars_launcher_web), so a
CSM asking and a CSM clicking always see the same thing.

Nothing here decides anything: the checks, the builds and the delivery stay in ars_launcher.
"""
import re
import threading
from concurrent.futures import ThreadPoolExecutor, wait

import rpe_env as R

from . import who

KINDS = ("ars", "combined", "ti", "companion")
_web = {"mod": None}
_web_lock = threading.Lock()
CHECK_WORKERS = 6
CHECK_SECONDS = 40


def web():
    """Sheila's server module, imported once, with the share caches its own main() installs."""
    with _web_lock:
        if _web["mod"] is None:
            import ars_launcher_web as W
            W.install_share_caches()
            _web["mod"] = W
        return _web["mod"]


def reply(answer, **data):
    return {"answer": answer, "data": data}


def label(c):
    return f"{c['id']} {c.get('name') or ''}".strip()


# ------------------------------------------------------------------ resolving people and clients
def _csm_or_none(csm):
    name = who.resolve_csm(csm)
    if name:
        return name, None
    if not csm or csm.strip().lower() in ("me", "mine", "my"):
        return None, ("I can't tell which CSM you are from this PC's sign-in. Say whose book you mean, "
                      "e.g. \"Jordan's clients\".")
    return None, f"No CSM in the Client CSM List matches '{csm}'. The CSMs are: {', '.join(sorted(who.csm_names()))}."


def all_clients():
    return web().clients_doc()


def find_client(client):
    """(the client's list row, None) or (None, why not). A number is exact; words match the name."""
    doc = all_clients()
    text = str(client or "").strip()
    rows = doc["clients"]
    if re.fullmatch(r"\d{3,5}", text):
        hit = next((c for c in rows if c["id"] == text), None)
        return (hit, None) if hit else (None, f"{text} is not a client Sheila builds for.")
    words = text.lower().split()
    hits = [c for c in rows if words and all(w in (c.get("name") or "").lower() for w in words)]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, f"No client's name matches '{text}'. Give the SRDB number."
    return None, "More than one client matches '%s': %s. Which one?" % (
        text, "; ".join(label(c) for c in hits[:8]))


# ------------------------------------------------------------------ my month
def _bucket(c, status):
    if c.get("sent"):
        return "sent"
    if c.get("decks"):
        return "in_outputs"
    if c.get("error"):
        return "failed"
    if status is None:
        return "unchecked"
    state = status.get("state")
    if state == "stop":
        return "blocked"
    return "ready"


GROUPS = [("ready", "Ready to build"), ("blocked", "Blocked"), ("failed", "Last build failed"),
          ("in_outputs", "Built, in Outputs (not sent)"), ("sent", "Sent"),
          ("unchecked", "Not checked yet")]


def my_month(csm="me", check=True):
    """The CSM's book for the cycle, grouped by where each client stands, with the next step."""
    name, why = _csm_or_none(csm)
    if why:
        return reply(why)
    W = web()
    doc = all_clients()
    book = [c for c in doc["clients"] if c.get("csm") == name]
    todo = [c for c in book if not (c.get("sent") or c.get("decks") or c.get("error"))]
    statuses = {}
    if check and todo:
        # Checked several at a time, for at most CHECK_SECONDS: a client still being checked is listed as
        # "Not checked yet" and its check finishes behind the answer, so asking again a minute later has it.
        ex = ThreadPoolExecutor(CHECK_WORKERS)
        futs = {ex.submit(_status_or_error, W, c["id"]): c["id"] for c in todo}
        done, _ = wait(futs, timeout=CHECK_SECONDS)
        for f in done:
            statuses[futs[f]] = f.result()
        ex.shutdown(wait=False)
    groups = {k: [] for k, _ in GROUPS}
    for c in book:
        st = statuses.get(c["id"])
        row = {"id": c["id"], "name": c.get("name"), "programs": c.get("covered") or c.get("programs"),
               "ti_in_outputs": bool(c.get("ti_decks")), "sent": c.get("sent"), "decks": c.get("decks")}
        if st is not None:
            row["state"] = st.get("state")
            row["blocked_by"] = W.stop_label(st.get("checks") or []) if st.get("state") == "stop" else None
            row["asks"] = [k["text"] for k in st.get("checks") or [] if k.get("level") == "ask"]
        groups[_bucket(c, st)].append(row)
    lines = [f"{name}'s book for {doc['period']}: {len(book)} clients."]
    for key, title in GROUPS:
        rows = groups[key]
        if not rows:
            continue
        lines.append(f"\n{title} ({len(rows)}):")
        for r in rows:
            extra = []
            if r.get("blocked_by"):
                extra.append(r["blocked_by"])
            if key == "ready" and r.get("asks"):
                extra.append("asks first: " + r["asks"][0])
            if r.get("ti_in_outputs"):
                extra.append("TI in Outputs")
            lines.append(f"  {r['id']} {r['name']}" + (f" ({'; '.join(extra)})" if extra else ""))
    nxt = []
    if groups["ready"]:
        nxt.append(f"{len(groups['ready'])} ready: say \"build all ready\" or name one.")
    if groups["blocked"]:
        nxt.append("Ask \"why is <client> blocked\" for what's missing and where it goes.")
    if groups["failed"]:
        nxt.append("Ask \"what happened to <client>'s build\" for the launcher's message.")
    if groups["unchecked"]:
        nxt.append(f"{len(groups['unchecked'])} still being checked: ask again in a minute.")
    if nxt:
        lines.append("\nNext: " + " ".join(nxt))
    return reply("\n".join(lines), csm=name, period=doc["period"], groups=groups)


def _status_or_error(W, cid):
    try:
        return W.status_doc(cid)
    except (Exception, SystemExit) as e:          # noqa: BLE001 — one client's failure never costs the book
        return {"state": "stop", "checks": [{"level": "stop", "text": f"The checks could not run ({type(e).__name__}: {e})"}]}


# ------------------------------------------------------------------ one client
def _check_lines(checks):
    mark = {"ok": "ok", "warn": "!!", "stop": "STOP", "ask": "ASK"}
    return [f"  [{mark.get(k.get('level'), k.get('level'))}] {k.get('text')}" for k in checks or []]


def client_status(client, fresh=False):
    """The client page: the launcher's checks, what can be built, the last build, TI and Companion."""
    c, why = find_client(client)
    if why:
        return reply(why)
    W = web()
    st = W.status_doc(c["id"], fresh=bool(fresh))
    b = st.get("builds") or {}
    verdict = {"ready": "Ready to build.",
               "ask": ("Built: this cycle's deck is in Outputs. A rebuild would replace it." if c.get("decks")
                       else "Ready, but the build asks first (see below)."),
               "stop": "Blocked: a check below must pass before it can build."}.get(st.get("state"), st.get("state"))
    lines = [f"{label(c)} (CSM {st.get('csm') or c.get('csm')}), cycle {st.get('period')}: {verdict}"]
    if b.get("base"):
        lines.append("The build makes: " + " + ".join(b["base"]) + ".")
    if b.get("combined") and b.get("has_ars"):
        lines.append("A combined deck is also on offer: " + " + ".join(b["combined"]) + ".")
    for p, reason in (b.get("left_out") or {}).items():
        lines.append(f"Left out: {p} ({reason}).")
    lines.append("Checks:")
    lines += _check_lines(st.get("checks"))
    if st.get("last"):
        last = st["last"]
        lines.append(f"Last build: {last.get('finished')}, {last.get('result') or ''}"
                     f"{', in Outputs' if last.get('delivered') else ', NOT put in Outputs'}.")
        if not last.get("delivered"):
            import ars_launcher as L
            why = L._log_reason(R.build_artifacts() / "launcher" / st["period"] / c["id"] / "build.log")
            if why:
                lines.append(f"Why, from its build log: {why}")
    for key, title in (("ti", "Transaction Intelligence"), ("companion", "ARS Companion")):
        blk = st.get(key)
        if blk:
            lines.append(f"{title}: {blk.get('state')}.")
            lines += _check_lines(blk.get("checks"))
    if c.get("sent"):
        lines.append(f"Marked sent {c['sent']}.")
    job = st.get("job")
    if job and not job.get("done"):
        lines.append("A build is running or queued for this client now.")
    return reply("\n".join(lines), client=c["id"], name=c.get("name"), status=st)


# ------------------------------------------------------------------ data issues
def data_issues(client=None, csm="me", include_done=False):
    """Data Issues for one client, or every client in a CSM's book."""
    W = web()
    doc = W.issues_doc()
    if client:
        c, why = find_client(client)
        if why:
            return reply(why)
        rows = [e for e in doc["clients"] if e["id"] == c["id"]]
        who_for = label(c)
    else:
        name, why = _csm_or_none(csm)
        if why:
            return reply(why)
        rows = [e for e in doc["clients"] if e.get("csm") == name]
        who_for = f"{name}'s book"
    lines, out = [], []
    for e in rows:
        items = [i for i in e.get("issues") or [] if include_done or not i.get("done")]
        codes = e.get("codes") or []
        lm = e.get("lift_matrix")
        if not (items or codes or lm):
            continue
        lines.append(f"\n{e['id']} {e.get('name')}:")
        for i in items:
            lines.append(f"  [{i.get('severity')}] {i.get('program') or ''}: {i.get('issue')}"
                         + (f" Fix: {i['fix']}" if i.get("fix") else "") + ("  (marked complete)" if i.get("done") else ""))
        for k in codes:
            vals = ", ".join(str(v.get("value")) for v in (k.get("values") or [])[:8])
            lines.append(f"  [codes] {k.get('label')}: {vals}")
        if lm:
            lines.append(f"  [Lift Matrix] {lm.get('flag')} ({lm.get('workbook') or ''})")
        if e.get("code_sheet"):
            lines.append(f"  Code sheet: Inputs\\Code Sheets\\{e['code_sheet']}")
        out.append(e)
    src = doc.get("sources") or {}
    head = f"Data issues for {who_for}" + (f" (issue pages {src.get('issue_pages')}, dashboard {src.get('dashboard')})"
                                            if src else "") + ":"
    if not out:
        return reply(f"No open data issues for {who_for}.", clients=[])
    return reply(head + "\n".join(lines), clients=out)


# ------------------------------------------------------------------ decks
def _deck_kind(name):
    import ars_launcher as L
    return "ti" if L.is_ti_deck(name) else "companion" if L.is_companion_deck(name) else "ars"


def find_deck(cid, kind="ars", period=None):
    """The newest deck of this kind for the client in Outputs (this cycle first), or None."""
    want = "ars" if kind == "combined" else kind
    period = period or web().current_period()
    for pat in ([f"{cid}-{period}-*.pptx"] if period else []) + [f"{cid}-*-*.pptx"]:
        hits = [d for d in R.output_decks(pat) if _deck_kind(d.name) == want]
        if hits:
            return sorted(hits, key=lambda d: d.name)[-1]
    return None


def _result_file(cid, period, kind):
    import ars_launcher as L
    name = {"ti": L.TI_RESULT_NAME, "companion": L.COMPANION_RESULT_NAME}.get(kind, "_launcher_result.json")
    return R.build_artifacts() / "launcher" / period / cid / name


def slide_titles(path):
    """[(number, title)] for every slide: its title placeholder, else its top-most line of text."""
    from pptx import Presentation
    out = []
    for n, s in enumerate(Presentation(str(path)).slides, 1):
        title = s.shapes.title.text_frame.text if s.shapes.title is not None and s.shapes.title.has_text_frame else ""
        if not title.strip():
            texts = sorted((sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()),
                           key=lambda sh: (sh.top or 0, sh.left or 0))
            title = texts[0].text_frame.text if texts else ""
        out.append((n, " ".join(title.split())[:140]))
    return out


def deck_summary(client, kind="ars"):
    """What's in the client's deck in Outputs: where it is, how it validated, and every slide's title."""
    c, why = find_client(client)
    if why:
        return reply(why)
    kind = (kind or "ars").lower()
    if kind not in KINDS:
        return reply(f"kind is one of {', '.join(KINDS)}.")
    deck = find_deck(c["id"], kind)
    if not deck:
        return reply(f"{label(c)} has no {kind.upper()} deck in Outputs.", client=c["id"])
    period = re.match(r"^\d+-(\d{4}\.\d{2})-", deck.name).group(1)
    rec = web().result_record(_result_file(c["id"], period, "ars" if kind == "combined" else kind))[0] or {}
    titles = slide_titles(deck)
    from .actions import review_items
    flagged = {}
    for lvl, n, _ in review_items(deck, c["id"]) or []:
        if n:
            flagged.setdefault(n, set()).add(lvl)
    lines = [f"{label(c)}: {deck.name}", f"In Outputs: {deck}",
             f"{len(titles)} slides" + (f"; validation {rec['result']}" if rec.get("result") else "")
             + (f"; built {rec['finished']}" if rec.get("finished") else "") + "."]
    lines += [f"  {n}. {t}" + (f"  [{'/'.join(sorted(flagged[n]))}]" if n in flagged else "") for n, t in titles]
    return reply("\n".join(lines), client=c["id"], deck=str(deck), slides=len(titles),
                 validation=rec.get("result"), titles=titles, flagged=sorted(flagged))


def outputs(csm="me"):
    """The decks in a CSM's Outputs folder for this cycle."""
    name, why = _csm_or_none(csm)
    if why:
        return reply(why)
    period = web().current_period()
    folder = R.outputs() / name
    decks = sorted(p for p in folder.glob(f"*-{period}-*.pptx") if not p.name.startswith("~$")) if folder.is_dir() else []
    if not decks:
        return reply(f"Nothing in {folder} for {period} yet.", folder=str(folder), decks=[])
    lines = [f"{len(decks)} deck(s) in {folder} for {period}:"] + [f"  {d.name}" for d in decks]
    return reply("\n".join(lines), folder=str(folder), decks=[d.name for d in decks])


def clients(csm="me", query="", program=""):
    """A CSM's clients (or anyone's, with csm="all"), optionally filtered by name words or program."""
    rows = all_clients()["clients"]
    if (csm or "").strip().lower() != "all":
        name, why = _csm_or_none(csm)
        if why:
            return reply(why)
        rows = [c for c in rows if c.get("csm") == name]
    if program:
        p = program.strip().upper()
        rows = [c for c in rows if p in [x.upper() for x in (c.get("covered") or []) + (c.get("products") or [])]]
    if query:
        words = query.lower().split()
        rows = [c for c in rows if all(w in (c.get("name") or "").lower() or w == c["id"] for w in words)]
    lines = [f"{len(rows)} client(s):"] + [
        f"  {c['id']} {c.get('name')} [{', '.join(c.get('covered') or c.get('programs') or [])}]"
        + (" sent" if c.get("sent") else " in Outputs" if c.get("decks") else "")
        + (" | TI in Outputs" if c.get("ti_decks") else "") for c in rows]
    return reply("\n".join(lines), clients=[{k: c.get(k) for k in ("id", "name", "csm", "covered", "products",
                                                                   "sent", "decks", "ti_decks")} for c in rows])


# ------------------------------------------------------------------ about Sheila
def version():
    """Sheila's version (the VERSION file's first line), without importing her server module."""
    from . import REPO
    try:
        return (REPO / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip() or "?"
    except (OSError, IndexError):
        return "?"


def whats_new(n=5):
    entries = web().changelog_entries(max(1, min(int(n or 5), 20)))
    lines = []
    for e in entries:
        lines.append(f"{e.get('date')}: {e.get('title')}")
        if e.get("summary"):
            lines.append(f"  {e['summary']}")
    return reply("\n".join(lines) or "No change log entries.", entries=entries)
