"""The ILS cards on a client's page in CSM Sheila (James Gilmore, 2026-10-28), in the Hub layout.

Run James's ILS pre-go-live or kickoff analysis from the client's page, beside the Executive Review,
Transaction Intelligence and ARS Companion cards. Each card is the engine's two steps in order: **Read the field
summary** (step 1, computes nothing), then the codes the CSM confirms and **Build** (step 2: the report or workbook,
and the deck). Until the client's extract has landed (Inputs/ILS PGL/<id>/ or Inputs/ILS Kickoff/<id>/) the card
says where to put it. The codes a client's last run was confirmed with are offered back with that run's date and
file; they are the CSM's to keep or change and are never applied until Build is pressed (James Gilmore, 2026-10-28:
"the user will confirm the limits. the client wont confirm anything"). What the CSM types is held in the page, so the
status refresh that redraws the client page does not lose it.

The runs and the files are in ils_runs.py and the routes in ils_ui.py (`get`, `post`); this is the page side, moved
here from the old page's `ils_ui.JS` when Sheila moved to the Hub layout. It is not a tab: sheila_hub.py draws
`<div id="ilscards">` on the client page and calls `ilsCards(client)` after drawing it.
"""
TAB = None
NAME = "ILS"
VIEW = ""

from ils_ui import LABELS  # noqa: E402  (the field labels the routes and the cards share)

CSS = r"""
/* ILS cards: the page's own cards, a form of code fields, and the run's own output in a scrolling box. */
.err{color:var(--bad)}
.ilsform{display:grid;grid-template-columns:minmax(170px,max-content) minmax(180px,340px);gap:8px 14px;align-items:center;margin:6px 0}
.ilsform label,.ilsin label{font-size:13px;color:var(--muted)}
.ilsform label b,.ilsin label b{color:var(--ink)}
.ilsform input[type=text],.ilsin input,.ilsin textarea,.ilsopts input[type=text]{font:inherit;padding:6px 9px;border:1px solid var(--line);border-radius:10px;background:var(--sheet);color:var(--ink)}
.ilsform input:focus-visible,.ilsin input:focus-visible,.ilsin textarea:focus-visible,.ilsopts input:focus-visible{outline:2px solid var(--good);outline-offset:1px}
.ilsopts{display:flex;flex-wrap:wrap;gap:6px 18px;margin:4px 0 6px;font-size:13px;color:var(--muted)}
.ilsopts label{display:flex;gap:6px;align-items:center}
.ilsopts input[type=checkbox]{margin:0;flex:none}
.ilsopts input[type=text]{width:90px;padding:4px 8px}
pre.ilslog{font:12px/1.45 var(--mono);background:var(--fill);border:1px solid var(--line);border-radius:12px;padding:10px 12px;max-height:360px;overflow:auto;white-space:pre-wrap;color:var(--ink);margin:8px 0 0}
.ilssaved{font-size:12.5px;color:var(--muted);margin:2px 0}
details.ilsfold{margin-top:2px}
details.ilsfold>summary{cursor:pointer;font:600 13.5px/1.3 var(--body);color:var(--ink);padding:6px 2px;list-style:none;display:flex;gap:8px;align-items:baseline}
details.ilsfold>summary::-webkit-details-marker{display:none}
details.ilsfold>summary::before{content:"\25B8";font-size:11px;color:var(--muted)}
details.ilsfold[open]>summary::before{content:"\25BE"}
details.ilsfold>summary .sub{font-weight:400;color:var(--muted)}
details.ilsfold>.pc{margin-top:10px}
details.ilsinputs{margin:6px 0 2px;border:1px solid var(--line);border-radius:12px;padding:6px 12px}
details.ilsinputs summary{cursor:pointer;font-weight:600;color:var(--ink)}
.ilsin{display:grid;grid-template-columns:minmax(170px,max-content) minmax(200px,520px);gap:8px 14px;align-items:start;margin:8px 0}
.ilsin textarea{min-height:70px;resize:vertical}
.sub{color:var(--muted)}
@media (max-width:820px){.ilsform,.ilsin{grid-template-columns:1fr}}
"""

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
  catch (e) { box.innerHTML = `<section class="pc"><p class="err">Couldn't read the ILS folders: ${esc(e.message)}</p></section>`; return; }
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
  if (!c || c.error) return `<section class="pc"><div class="pch"><h3>${esc(title)}</h3></div><p class="err">${esc((c && c.error) || "unavailable")}</p></section>`;
  const j = c.job, running = j && !j.done;
  const state = !c.extract ? `<span class="chip k-blocked">No extract yet</span>` : c.last ? `<span class="chip k-outputs">Deck built</span>` : `<span class="chip k-ready">Extract landed</span>`;
  const head = (btns) => `<div class="pch"><h3>${esc(title)} <span class="mix">${kind === "pgl" ? "report and board deck" : "workbook and deck"}</span> ${state}</h3><div class="act">${btns}</div></div>`;
  if (!c.extract) return `<section class="pc stopc" id="ils${kind}">${head("")}
      <p class="fact">${esc(ILS_WHAT[kind])}</p>
      <p class="why">Land the client's ${kind === "pgl" ? "pre-go-live extract (<code>&lt;id&gt;_&lt;Client&gt;_PreGL_&lt;yyyymmdd&gt;.csv</code>, with the vendor's MatrixValidation / IntegrityCheck dumps beside it)" : "one-time data extract (<code>&lt;id&gt;_OneTimeData_&lt;yyyymmdd&gt;.csv</code> or <code>.xlsx</code>)"} in <b>${esc(c.folder || "")}</b>${kind === "pgl" ? " (or the delivery's zip, <code>&lt;id&gt;_…_PGL_&lt;yyyymmdd&gt;.zip</code>, in the folder above it)" : ""}, then Check again.</p></section>`;
  const step1 = `<button class="btn" data-ilsrun="1" data-ilskind="${kind}"${running ? " disabled" : ""}>Read the field summary</button>`;
  const step2 = `<button class="btn primary" data-ilsrun="2" data-ilskind="${kind}"${running ? " disabled" : ""}>${c.last ? "Rebuild" : "Build"}</button>`;
  const fact = `Extract <b>${esc(c.extract)}</b>` + (c.last ? ` · last deck ${esc(c.last.when)} · <button class="link" data-ilsreveal="${esc(c.last.deck)}">open the deck</button>` : "");
  const saved = c.saved ? `<p class="ilssaved">Codes filled in from the run confirmed ${esc(c.saved.confirmed)}${c.saved.by ? " by " + esc(c.saved.by) : ""}${c.saved.extract ? " on " + esc(c.saved.extract) : ""}. Check them against this extract's field summary before you build.</p>` : "";
  return `<section class="pc" id="ils${kind}">${head(`<span class="btns">${step1}${step2}</span><span class="why">files go to Build Artifacts\\ils</span>`)}
    <p class="fact">${fact}</p>
    <p class="why">${esc(ILS_WHAT[kind])} First read the field summary (nothing is computed), then confirm the codes from it — which value means open, personal, OD-eligible or opted in — type them, and Build.</p>
    ${saved}${ilsSuggested(kind, j)}<div class="ilsform">${ILS.doc.fields[kind].map(f => ilsField(kind, f, c.saved)).join("")}</div>
    ${ilsOptions(kind, c)}${kind === "pgl" ? ilsInputsHtml(c) : ""}<div id="ilsjob${kind}">${j ? ilsJobHtml(j) : ""}</div></section>`;
}

// The pre-go-live and kickoff reports are made once per client, so for almost every client the cards only
// said "No extract yet" (Aaron, 2026-10-29). They fold under one line, opened only when a kind has an
// extract, a run in progress or a deck built; a CSM opens it to land an extract. The open state a CSM
// chose is kept while the page lives, so the status refresh that redraws the cards does not close it.
function ilsSummary() {
  const parts = [];
  for (const k of ["pgl", "kickoff"]) {
    const c = ILS.doc.kinds[k], name = k === "pgl" ? "Pre-go-live" : "Kickoff";
    if (!c || c.error) parts.push(`${name}: unavailable`);
    else if (c.job && !c.job.done) parts.push(`${name}: running`);
    else if (c.last) parts.push(`${name}: deck built`);
    else if (c.extract) parts.push(`${name}: extract landed`);
  }
  return parts.length ? parts.join(" · ") : "one-time reports, not set up for this client";
}

function ilsActive() {
  return ["pgl", "kickoff"].some(k => { const c = ILS.doc.kinds[k]; return c && !c.error && (c.extract || c.last || (c.job && !c.job.done)); });
}

function ilsDraw() {
  const box = $("#ilscards"); if (!box || !ILS.doc) return;
  const was = box.querySelector("details.ilsfold");
  const open = was ? was.open : ilsActive();
  box.innerHTML = `<details class="ilsfold"${open ? " open" : ""}><summary>ILS pre-go-live and kickoff <span class="sub">${esc(ilsSummary())}</span></summary>` +
    ilsCard("pgl") + ilsCard("kickoff") +
    `<section class="pc" id="ilsreview"><div class="pch"><h3>ILS Review <span class="mix">a live ILS client's results</span> <span class="chip">Coming soon</span></h3><div class="act"></div></div>
     <p class="fact">The review of a client already live on ILS will build here.</p></section></details>`;
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
      ${field("key_dates", "Key decisions and dates", "one per line: milestone | date | done or at risk (optional). Left empty, the timeline slide lists the standard ILS milestones as TBD", dates, true)}
      ${Object.entries(ILS_PROGRAM).map(([k, lbl]) => field("p_" + k, lbl, "", prog[k])).join("")}
      ${field("data_notes", "Notes on the data", "date range, codes still needing descriptions, First Notice File observations", v.data_notes, true)}
      ${field("od", "OD code descriptions", "one per line: code = description (used where the matrix has none)", od, true)}
    </div>
    <span class="btns"><button class="btn" id="ilsinsave">Save the deck inputs</button></span> <span class="why" id="ilsinmsg"></span></details>`;
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
  if (!j.done) state = `<p class="why">${what} running… ${j.seconds}s</p>`;
  else if (j.ok && j.step === 1) state = `<p class="why"><b>Field summary read.</b> Confirm the codes from it, type them above, then Build.</p>`;
  else if (j.ok) state = `<p class="why"><b>Built.</b> ${j.deck ? `<button class="link" data-ilsreveal="${esc(j.deck)}">open the deck</button> · ` : ""}${j.folder ? `<button class="link" data-ilsreveal="${esc(j.folder)}">open the folder</button>` : ""} — read the warnings below before quoting any number.</p>`;
  else state = `<p class="why err">${what} stopped${j.error ? ": " + esc(j.error) : ""}. The run's own words are below.</p>`;
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
  catch (e) { $("#ilsjob" + kind).innerHTML = `<p class="why err">${esc(e.message)}</p>`; return; }
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

$("#detail").addEventListener("input", e => {
  if (e.target.id && e.target.id.startsWith("ilsin_") && ILS.cid) {       // a typed, unsaved input survives a redraw
    ILS.draft = ILS.draft || {};
    (ILS.draft[ILS.cid] = ILS.draft[ILS.cid] || {})[e.target.id.slice(6)] = e.target.value;
    return;
  }
  const el = e.target.closest("[data-ilsfield]"); if (!el || !ILS.cid) return;
  const key = ILS.cid + el.dataset.ilskind;
  (ILS.form[key] = ILS.form[key] || {})[el.dataset.ilsfield] = el.type === "checkbox" ? el.checked : el.value;
});
$("#detail").addEventListener("click", async e => {
  const t = e.target;
  const run = t.closest("[data-ilsrun]"); if (run) return ilsRun(run.dataset.ilskind, +run.dataset.ilsrun);
  if (t.closest("#ilsinsave")) return ilsSaveInputs();
  const rv = t.closest("[data-ilsreveal]");
  if (rv) { try { await api("/api/ils/reveal", {method: "POST", body: JSON.stringify({path: rv.dataset.ilsreveal})}); } catch (err) { alert(err.message); } }
});
"""

JS = JS.replace("__ILS_LABELS__", __import__("json").dumps(LABELS))
