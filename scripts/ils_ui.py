"""
ils_ui.py — the ILS cards on a client's page in CSM Sheila: run James's ILS pre-go-live or kickoff analysis.

James Gilmore, 2026-10-28: "a CSM can run either ILS analysis option from the Sheila webpage", on the
client's page beside the Executive Review, Transaction Intelligence and ARS Companion cards ("the option
should be when i click a client"), with an "ILS Review - Coming Soon" card beside them. Kept out of
ars_launcher_web.py, as the Slide Review tab is (slide_review_ui.py), so the cards are one block to read:
the page's own text changes in two one-line places and the handler in two. `install` raises when an
anchor it needs has moved, so a page change that breaks the splice fails the unit suite instead of
dropping the cards.

Each card is the engine's two steps, in order: **Read the field summary** (step 1, computes nothing),
then the codes the client confirmed and **Build** (step 2: the report or workbook, and the deck). Until
the client's extract has landed (Inputs/ILS PGL/<id>/ or Inputs/ILS Kickoff/<id>/) the card says where to
put it. The codes a client's last run was confirmed with are offered back with that run's date and file;
they are the CSM's to keep or change and are never applied until Build is pressed. What the CSM types is
held in the page, so the status refresh that redraws the client page does not lose it. The runs and the
files are in ils_runs.py.
"""
import json

import ils_runs

CSS = r"""
/* ILS cards (James Gilmore, 2026-10-28): the page's own cards, a form of code fields, and the run's own
   output in a scrolling box. */
.ilsform{display:grid;grid-template-columns:minmax(180px,max-content) minmax(200px,360px);gap:8px 14px;align-items:center;margin:8px 0 6px}
.ilsform label{font-size:13px;color:var(--ink2)}
.ilsform label b{color:var(--ink)}
.ilsform input[type=text]{font:inherit;padding:6px 8px;border:1px solid var(--rule);border-radius:6px;background:var(--surface);color:var(--ink)}
.ilsopts{display:flex;flex-wrap:wrap;gap:6px 18px;margin:6px 0 8px;font-size:13px;color:var(--ink2)}
.ilsopts label{display:flex;gap:6px;align-items:center;width:auto;margin:0}
.ilsopts input[type=checkbox]{width:auto;margin:0;flex:none}
.ilsopts input[type=text]{font:inherit;width:90px;padding:4px 6px;border:1px solid var(--rule);border-radius:6px;background:var(--surface);color:var(--ink)}
pre.ilslog{font:12px/1.45 Consolas,"Cascadia Mono",monospace;background:rgba(127,127,127,.08);border:1px solid var(--rule);border-radius:8px;padding:10px 12px;max-height:360px;overflow:auto;white-space:pre-wrap;color:var(--ink);margin:8px 0 0}
.ilssaved{font-size:12.5px;color:var(--ink3);margin:4px 0 2px}
.chip.soon{background:var(--rule);color:var(--ink2)}
"""

LABELS = {
    "open_status": ("Open account status", "the Account Status value(s) meaning open"),
    "od_eligible": ("ILS-eligible OD status", "the OD Status value(s) eligible for ILS"),
    "rege_opt_in": ("Reg E opted in", "the Reg E value(s) meaning opted in"),
    "rege_opt_out": ("Reg E opted out", "the value(s) meaning opted out"),
    "personal_code": ("Personal", "the Business Flag value meaning personal"),
    "business_code": ("Business", "the Business Flag value meaning business"),
    "open_code": ("Open account status", "the Account Status value meaning open"),
    "eligible_stat_codes": ("OD-eligible Stat Code(s)", "the Stat Code value(s) eligible for OD"),
}

JS = r"""
// ------------------------------------------------------------------ ILS cards (James Gilmore, 2026-10-28)
// James's two ILS engines on the client page, each in its two steps: the field summary first (computes
// nothing), then a run on the codes the CSM confirmed. ILS.form keeps what was typed across the status
// refresh that redraws this page. The runs and the remembered codes are in ils_runs.py.
let ILS = {cid: null, doc: null, form: {}, timer: {}};
const ILS_LABELS = __ILS_LABELS__;
const ILS_WHAT = {
  pgl: "Reconciles the client's extract against the vendor's system dumps before go-live, and builds the board deck.",
  kickoff: "How the book is made up and where the NSF activity sits: a 19-tab workbook and the kickoff deck."};

async function ilsCards(cid) {
  const box = $("#ilscards"); if (!box) return;
  if (ILS.cid !== cid) { ILS.cid = cid; ILS.doc = null; }
  if (ILS.doc) ilsDraw();
  try { ({body: ILS.doc} = await api("/api/ils/client?client=" + encodeURIComponent(cid))); }
  catch (e) { box.innerHTML = `<section class="card"><p class="err">Couldn't read the ILS folders: ${esc(e.message)}</p></section>`; return; }
  if (ILS.cid !== cid) return;
  ilsDraw();
  for (const k of ["pgl", "kickoff"]) { const j = ILS.doc.kinds[k] && ILS.doc.kinds[k].job; if (j && !j.done) ilsPoll(k); }
}

function ilsVal(kind, f, dflt) {
  const v = (ILS.form[ILS.cid + kind] || {})[f];
  return v === undefined ? dflt : v;
}

function ilsField(kind, f, saved) {
  const [label, hint] = ILS_LABELS[f] || [f, ""];
  const req = ILS.doc.required[kind].includes(f);
  const v = ilsVal(kind, f, saved && saved.codes ? (saved.codes[f] || "") : "");
  return `<label for="ils_${kind}_${f}"><b>${esc(label)}</b>${req ? "" : " (optional)"}<br><span class="sub">${esc(hint)}</span></label>
    <input type="text" id="ils_${kind}_${f}" data-ilskind="${kind}" data-ilsfield="${f}" value="${esc(v)}" placeholder="${req ? "required" : ""}" autocomplete="off">`;
}

function ilsOptions(kind, c) {
  const o = (c.saved && c.saved.options) || {};
  const box = (f, on, text) => `<label><input type="checkbox" data-ilskind="${kind}" data-ilsfield="${f}"${ilsVal(kind, f, !!on) ? " checked" : ""}> ${text}</label>`;
  if (kind === "kickoff") return `<div class="ilsopts">
      <label>Period <input type="text" data-ilskind="kickoff" data-ilsfield="period" value="${esc(ilsVal(kind, "period", c.period || ""))}" placeholder="YYYY-MM"></label>
      ${box("items_from_calc", o.items_from_calc, `Use the extract's "# Calc" item estimates (only when the counted items are blank; the deck says ESTIMATED)`)}</div>`;
  return `<div class="ilsopts">
      <label>Current NSF/OD fee $ <input type="text" data-ilskind="pgl" data-ilsfield="fee" value="${esc(ilsVal(kind, "fee", o.fee == null ? "" : o.fee))}" placeholder="confirmed"></label>
      ${box("current_only", o.current_only, "Current state only (leave out the go-live chapter)")}
      ${box("include_deleted", o.include_deleted, "Keep deletion-flagged rows")}</div>`;
}

function ilsCard(kind) {
  const c = ILS.doc.kinds[kind], title = "ILS " + (kind === "pgl" ? "Pre-go-live" : "Kickoff");
  if (!c || c.error) return `<section class="card"><div class="cardhead"><h3>${esc(title)}</h3></div><p class="err">${esc((c && c.error) || "unavailable")}</p></section>`;
  const j = c.job, running = j && !j.done;
  const state = !c.extract ? `<span class="chip stop">No extract yet</span>` : c.last ? `<span class="chip out">Deck built</span>` : `<span class="chip ready">Extract landed</span>`;
  const head = (btns) => `<div class="cardhead"><h3>${esc(title)} <span class="mix">${kind === "pgl" ? "report and board deck" : "workbook and deck"}</span> ${state}</h3><div class="act">${btns}</div></div>`;
  if (!c.extract) return `<section class="card stopcard" id="ils${kind}">${head("")}
      <p class="fact">${esc(ILS_WHAT[kind])}</p>
      <p class="small">Land the client's ${kind === "pgl" ? "pre-go-live extract (<code>&lt;id&gt;_&lt;Client&gt;_PreGL_&lt;yyyymmdd&gt;.csv</code>, with the vendor's MatrixValidation / IntegrityCheck dumps beside it)" : "one-time data extract (<code>&lt;id&gt;_OneTimeData_&lt;yyyymmdd&gt;.csv</code> or <code>.xlsx</code>)"} in <b>${esc(c.folder || "")}</b>${kind === "pgl" ? " (or the delivery's zip, <code>&lt;id&gt;_…_PGL_&lt;yyyymmdd&gt;.zip</code>, in the folder above it)" : ""}, then Check again.</p></section>`;
  const step1 = `<button class="quiet" data-ilsrun="1" data-ilskind="${kind}"${running ? " disabled" : ""}>Read the field summary</button>`;
  const step2 = `<button class="primary" data-ilsrun="2" data-ilskind="${kind}"${running ? " disabled" : ""}>${c.last ? "Rebuild" : "Build"}</button>`;
  const fact = `Extract <b>${esc(c.extract)}</b>` + (c.last ? ` · last deck ${esc(c.last.when)} · <button class="link" data-ilsreveal="${esc(c.last.deck)}">open the deck</button>` : "");
  const saved = c.saved ? `<p class="ilssaved">Codes filled in from the run confirmed ${esc(c.saved.confirmed)}${c.saved.by ? " by " + esc(c.saved.by) : ""}${c.saved.extract ? " on " + esc(c.saved.extract) : ""}. Check them against this extract's field summary before you build.</p>` : "";
  return `<section class="card" id="ils${kind}">${head(`<span class="btns">${step1}${step2}</span><span class="why">files go to Build Artifacts\\ils</span>`)}
    <p class="fact">${fact}</p>
    <p class="small">${esc(ILS_WHAT[kind])} First read the field summary (nothing is computed), then type the codes the client confirmed — which value means open, personal, OD-eligible or opted in is the client's answer — and Build.</p>
    ${saved}<div class="ilsform">${ILS.doc.fields[kind].map(f => ilsField(kind, f, c.saved)).join("")}</div>
    ${ilsOptions(kind, c)}<div id="ilsjob${kind}">${j ? ilsJobHtml(j) : ""}</div></section>`;
}

function ilsDraw() {
  const box = $("#ilscards"); if (!box || !ILS.doc) return;
  box.innerHTML = ilsCard("pgl") + ilsCard("kickoff") +
    `<section class="card" id="ilsreview"><div class="cardhead"><h3>ILS Review <span class="mix">a live ILS client's results</span> <span class="chip soon">Coming soon</span></h3><div class="act"></div></div>
     <p class="fact">The review of a client already live on ILS will build here.</p></section>`;
}

function ilsJobHtml(j) {
  const what = j.step === 1 ? "Field summary" : "Build";
  let state;
  if (!j.done) state = `<p class="small">${what} running… ${j.seconds}s</p>`;
  else if (j.ok && j.step === 1) state = `<p class="small"><b>Field summary read.</b> Confirm the codes with the client, type them above, then Build.</p>`;
  else if (j.ok) state = `<p class="small"><b>Built.</b> ${j.deck ? `<button class="link" data-ilsreveal="${esc(j.deck)}">open the deck</button> · ` : ""}${j.folder ? `<button class="link" data-ilsreveal="${esc(j.folder)}">open the folder</button>` : ""} — read the warnings below before quoting any number.</p>`;
  else state = `<p class="small err">${what} stopped${j.error ? ": " + esc(j.error) : ""}. The run's own words are below.</p>`;
  return state + `<pre class="ilslog">${esc((j.lines || []).join("\n"))}</pre>`;
}

function ilsShow(kind, j) {
  if (ILS.doc && ILS.doc.kinds[kind]) ILS.doc.kinds[kind].job = j;
  const box = $("#ilsjob" + kind); if (!box || !j) return;
  box.innerHTML = ilsJobHtml(j);
  const pre = box.querySelector("pre"); if (pre && !j.done) pre.scrollTop = pre.scrollHeight;
  for (const b of document.querySelectorAll(`#ils${kind} [data-ilsrun]`)) b.disabled = !j.done;
}

async function ilsRun(kind, step) {
  const f = ILS.form[ILS.cid + kind] || {};
  const body = {kind, client: ILS.cid};
  if (step === 2) {
    body.codes = Object.fromEntries(ILS.doc.fields[kind].map(k => [k, ($(`#ils_${kind}_${k}`) || {}).value || ""]));
    const opt = k => { const el = document.querySelector(`#ils${kind} [data-ilsfield="${k}"]`); return el ? (el.type === "checkbox" ? el.checked : el.value) : f[k]; };
    if (kind === "kickoff") { body.period = opt("period") || ""; body.items_from_calc = !!opt("items_from_calc"); }
    else { body.fee = opt("fee") || ""; body.current_only = !!opt("current_only"); body.include_deleted = !!opt("include_deleted"); }
  }
  let r;
  try { r = await api("/api/ils/run", {method: "POST", body: JSON.stringify(body)}); }
  catch (e) { $("#ilsjob" + kind).innerHTML = `<p class="small err">${esc(e.message)}</p>`; return; }
  ilsShow(kind, r.body.job); ilsPoll(kind);
}

async function ilsPoll(kind) {
  clearTimeout(ILS.timer[kind]);
  const cid = ILS.cid; if (!cid) return;
  let j;
  try { ({body: j} = await api(`/api/ils/job?kind=${kind}&client=${encodeURIComponent(cid)}`)); } catch (e) { return; }
  if (ILS.cid !== cid) return;
  ilsShow(kind, j);
  if (j && !j.done) ILS.timer[kind] = setTimeout(() => ilsPoll(kind), 1500);
  else if (j && j.done && j.step === 2 && j.ok) ilsCards(cid);
}

$("#main").addEventListener("input", e => {
  const el = e.target.closest("[data-ilsfield]"); if (!el || !ILS.cid) return;
  const key = ILS.cid + el.dataset.ilskind;
  (ILS.form[key] = ILS.form[key] || {})[el.dataset.ilsfield] = el.type === "checkbox" ? el.checked : el.value;
});
$("#main").addEventListener("click", async e => {
  const t = e.target;
  const run = t.closest("[data-ilsrun]"); if (run) return ilsRun(run.dataset.ilskind, +run.dataset.ilsrun);
  const rv = t.closest("[data-ilsreveal]");
  if (rv) { try { await api("/api/ils/reveal", {method: "POST", body: JSON.stringify({path: rv.dataset.ilsreveal})}); } catch (err) { alert(err.message); } }
});
"""


def install(page):
    """`page` with the ILS cards spliced into the client page. Raises when an anchor has moved."""
    def swap(text, old, new, count=1):
        if text.count(old) != 1:
            raise RuntimeError("the ILS cards could not be added to the page: anchor not found once: " + old[:70])
        return text.replace(old, new, count)

    page = swap(page, "${companionPanel(s)}${aside}", '${companionPanel(s)}<div id="ilscards"></div>${aside}')
    page = swap(page, 'clientLinks(s.client, "decks");', 'clientLinks(s.client, "decks");\n  ilsCards(s.client);')
    page = swap(page, "</style>", CSS + "</style>")
    i = page.rindex("</script>")
    labels = {k: list(v) for k, v in LABELS.items()}
    return page[:i] + JS.replace("__ILS_LABELS__", json.dumps(labels)) + page[i:]


def get(handler, path, params):
    """GET /api/ils/client and /api/ils/job."""
    kind, cid = params.get("kind", ""), params.get("client", "")
    if not ils_runs.CID_RX.match(cid):
        return handler._send(400, {"error": "not a client number"})
    if path == "/api/ils/client":
        return handler._send(200, ils_runs.client_doc(cid))
    if path == "/api/ils/job":
        if kind not in ils_runs.KINDS:
            return handler._send(400, {"error": "not an ILS analysis"})
        return handler._send(200, ils_runs.job_doc(kind, cid) or {})
    return handler._send(404, {"error": "not found"})


def post(handler, path, body):
    """POST /api/ils/run and /api/ils/reveal."""
    if path == "/api/ils/run":
        code, doc = ils_runs.start(body)
        return handler._send(code, doc)
    if path == "/api/ils/reveal":
        code, doc = ils_runs.reveal(str(body.get("path", "")))
        return handler._send(code, doc)
    return handler._send(404, {"error": "not found"})
