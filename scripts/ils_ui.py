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
then the codes the CSM confirms and **Build** (step 2: the report or workbook, and the deck). Until
the client's extract has landed (Inputs/ILS PGL/<id>/ or Inputs/ILS Kickoff/<id>/) the card says where to
put it. The codes a client's last run was confirmed with are offered back with that run's date and file;
they are the CSM's to keep or change and are never applied until Build is pressed. The CSM confirms
the codes, never the client (James Gilmore, 2026-10-28: "the user will confirm the limits. the client
wont confirm anything"). What the CSM types is
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
details.ilsinputs{margin:8px 0 4px;border:1px solid var(--rule);border-radius:8px;padding:6px 10px}
details.ilsinputs summary{cursor:pointer;font-weight:600;color:var(--ink)}
.ilsin{display:grid;grid-template-columns:minmax(180px,max-content) minmax(220px,520px);gap:8px 14px;align-items:start;margin:8px 0}
.ilsin label{font-size:13px;color:var(--ink2)} .ilsin label b{color:var(--ink)}
.ilsin input,.ilsin textarea{font:inherit;padding:6px 8px;border:1px solid var(--rule);border-radius:6px;background:var(--surface);color:var(--ink)}
.ilsin textarea{min-height:70px;resize:vertical}
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
    <p class="small">${esc(ILS_WHAT[kind])} First read the field summary (nothing is computed), then confirm the codes from it — which value means open, personal, OD-eligible or opted in — type them, and Build.</p>
    ${saved}${ilsSuggested(kind, j)}<div class="ilsform">${ILS.doc.fields[kind].map(f => ilsField(kind, f, c.saved)).join("")}</div>
    ${ilsOptions(kind, c)}${kind === "pgl" ? ilsInputsHtml(c) : ""}<div id="ilsjob${kind}">${j ? ilsJobHtml(j) : ""}</div></section>`;
}

function ilsDraw() {
  const box = $("#ilscards"); if (!box || !ILS.doc) return;
  box.innerHTML = ilsCard("pgl") + ilsCard("kickoff") +
    `<section class="card" id="ilsreview"><div class="cardhead"><h3>ILS Review <span class="mix">a live ILS client's results</span> <span class="chip soon">Coming soon</span></h3><div class="act"></div></div>
     <p class="fact">The review of a client already live on ILS will build here.</p></section>`;
}

// The deck's CSM inputs (James Gilmore, 2026-10-28): what only the CSM can tell a pre-go-live deck. Saved per
// client (ils_runs.save_inputs) and read by every Build; a field left empty draws "to be completed" in the deck.
const ILS_PROGRAM = {od_fee: "Current OD (paid) fee", nsf_fee: "Current NSF (return) fee",
  de_minimis_balance: "De minimis balance amount", de_minimis_txn: "De minimis transaction amount",
  sustained_fee: "Sustained (continuous) OD fee", stop_payment_fee: "Stop payment fee", daily_cap: "Daily fee cap"};
function ilsInputsHtml(c) {
  const v = c.inputs || {}, prog = v.program || {};
  const dates = (v.key_dates || []).map(r => r.filter(Boolean).join(" | ")).join("\n");
  const od = Object.entries(v.od_descriptions || {}).map(([k, d]) => `${k} = ${d}`).join("\n");
  const d = (ILS.draft || {})[ILS.cid] || {};
  const field = (id, label, hint, saved, area) => { const val = d[id] !== undefined ? d[id] : saved; return `<label for="ilsin_${id}"><b>${esc(label)}</b>${hint ? `<br><span class="sub">${esc(hint)}</span>` : ""}</label>` +
    (area ? `<textarea id="ilsin_${id}">${esc(val || "")}</textarea>` : `<input type="text" id="ilsin_${id}" value="${esc(val || "")}" autocomplete="off">`); };
  const filled = [dates, od, v.data_notes].some(Boolean) || Object.values(prog).some(Boolean);
  return `<details class="ilsinputs"${filled ? "" : " open"}><summary>Deck inputs — key dates, current program, data notes, OD code descriptions${v.saved ? ` <span class="sub">(saved ${esc(v.saved)}${v.by ? " by " + esc(v.by) : ""})</span>` : ""}</summary>
    <div class="ilsin">
      ${field("key_dates", "Key decisions and dates", "one per line: milestone | date", dates, true)}
      ${Object.entries(ILS_PROGRAM).map(([k, lbl]) => field("p_" + k, lbl, "", prog[k])).join("")}
      ${field("data_notes", "Notes on the data", "date range, codes still needing descriptions, First Notice File observations", v.data_notes, true)}
      ${field("od", "OD code descriptions", "one per line: code = description (used where the matrix has none)", od, true)}
    </div>
    <span class="btns"><button class="quiet" id="ilsinsave">Save the deck inputs</button></span> <span class="small" id="ilsinmsg"></span></details>`;
}

async function ilsSaveInputs() {
  const val = id => ($("#ilsin_" + id) || {}).value || "";
  const body = {client: ILS.cid, key_dates: val("key_dates"), data_notes: val("data_notes"), od_descriptions: val("od"),
                program: Object.fromEntries(Object.keys(ILS_PROGRAM).map(k => [k, val("p_" + k)]))};
  const msg = $("#ilsinmsg");
  try {
    const {body: r} = await api("/api/ils/inputs", {method: "POST", body: JSON.stringify(body)});
    if (ILS.doc && ILS.doc.kinds.pgl) ILS.doc.kinds.pgl.inputs = r.inputs;
    if (ILS.draft) delete ILS.draft[ILS.cid];
    if (msg) msg.textContent = `Saved ${r.inputs.saved}. The next Build uses them.`;
  } catch (e) { if (msg) msg.textContent = "Couldn't save: " + e.message; }
}

function ilsJobHtml(j) {
  const what = j.step === 1 ? "Field summary" : "Build";
  let state;
  if (!j.done) state = `<p class="small">${what} running… ${j.seconds}s</p>`;
  else if (j.ok && j.step === 1) state = `<p class="small"><b>Field summary read.</b> Confirm the codes from it, type them above, then Build.</p>`;
  else if (j.ok) state = `<p class="small"><b>Built.</b> ${j.deck ? `<button class="link" data-ilsreveal="${esc(j.deck)}">open the deck</button> · ` : ""}${j.folder ? `<button class="link" data-ilsreveal="${esc(j.folder)}">open the folder</button>` : ""} — read the warnings below before quoting any number.</p>`;
  else state = `<p class="small err">${what} stopped${j.error ? ": " + esc(j.error) : ""}. The run's own words are below.</p>`;
  return state + `<pre class="ilslog">${esc((j.lines || []).join("\n"))}</pre>`;
}

// The codes the ILS system's own dumps hold (pre_go_live/dump_codes.py), with the evidence for each. A field
// the CSM has typed, or a saved run filled, is never overwritten; the CSM still confirms by pressing Build.
function ilsSuggested(kind, j) {
  const b = j && j.done && j.ok && j.step === 1 ? (j.suggested_basis || {}) : {};
  const rows = Object.entries(b).map(([f, why]) => `<li><b>${esc((ILS_LABELS[f] || [f])[0])}</b>: ${esc((j.suggested || {})[f] || "not offered")} — ${esc(why)}</li>`).join("");
  return rows ? `<div class="ilssaved ilssuggested">From the ILS system's own settings (matrix validation and integrity check), filled in where a field was empty — check them, then Build:<ul>${rows}</ul></div>` : "";
}

function ilsFill(kind, j) {
  if (!(j && j.done && j.ok && j.step === 1 && j.suggested)) return false;
  const key = ILS.cid + kind, f = (ILS.form[key] = ILS.form[key] || {});
  let changed = false;
  for (const [field, v] of Object.entries(j.suggested)) {
    const el = $(`#ils_${kind}_${field}`);
    if (el && !el.value.trim() && v) { el.value = v; f[field] = v; changed = true; }
  }
  return changed;
}

function ilsShow(kind, j) {
  if (ILS.doc && ILS.doc.kinds[kind]) ILS.doc.kinds[kind].job = j;
  if (j && j.done && j.step === 1 && j.ok && j.suggested_basis && Object.keys(j.suggested_basis).length) {
    ilsFill(kind, j);
    const card = $("#ils" + kind);
    if (card && !card.querySelector(".ilssuggested")) {
      card.querySelector(".ilsform").insertAdjacentHTML("beforebegin", ilsSuggested(kind, j));
    }
  }
  const box = $("#ilsjob" + kind); if (!box || !j) return;
  box.innerHTML = ilsJobHtml(j);
  const pre = box.querySelector("pre"); if (pre && !j.done) pre.scrollTop = pre.scrollHeight;
  for (const b of document.querySelectorAll(`#ils${kind} [data-ilsrun]`)) b.disabled = !j.done;
}

async function ilsRun(kind, step) {
  const f = ILS.form[ILS.cid + kind] || {};
  const known = (typeof CLIENTS !== "undefined" && CLIENTS.find(x => x.id === ILS.cid)) || {};
  const body = {kind, client: ILS.cid, client_name: known.name || ""};
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
  if (e.target.id && e.target.id.startsWith("ilsin_") && ILS.cid) {       // a typed, unsaved input survives a redraw
    ILS.draft = ILS.draft || {};
    (ILS.draft[ILS.cid] = ILS.draft[ILS.cid] || {})[e.target.id.slice(6)] = e.target.value;
    return;
  }
  const el = e.target.closest("[data-ilsfield]"); if (!el || !ILS.cid) return;
  const key = ILS.cid + el.dataset.ilskind;
  (ILS.form[key] = ILS.form[key] || {})[el.dataset.ilsfield] = el.type === "checkbox" ? el.checked : el.value;
});
$("#main").addEventListener("click", async e => {
  const t = e.target;
  const run = t.closest("[data-ilsrun]"); if (run) return ilsRun(run.dataset.ilskind, +run.dataset.ilsrun);
  if (t.closest("#ilsinsave")) return ilsSaveInputs();
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
    """POST /api/ils/run, /api/ils/inputs and /api/ils/reveal."""
    if path == "/api/ils/inputs":
        code, doc = ils_runs.save_inputs(body)
        return handler._send(code, doc)
    if path == "/api/ils/run":
        code, doc = ils_runs.start(body)
        return handler._send(code, doc)
    if path == "/api/ils/reveal":
        code, doc = ils_runs.reveal(str(body.get("path", "")))
        return handler._send(code, doc)
    return handler._send(404, {"error": "not found"})
