"""The ILS cards on a client's ILS page in CSM Sheila (James Gilmore, 2026-10-28), in the Hub layout.

The client page opened from ILS Decks is ILS only (Aaron, 2026-11-25: "the ILS Pre-GoLive and Kickoff can be moved to
the ILS Decks section, and it no longer needs the dropdown to show them"): the ILS Review card, then the ILS Pre-go-live
card and the ILS Kickoff card, all shown, with no fold. The RPE page carries none of them.

Run James's ILS pre-go-live or kickoff analysis from the client's ILS page. Each card is the engine's two steps in order: **Read the field
summary** (step 1, computes nothing), then the codes the CSM confirms and **Build** (step 2: the report or workbook,
and the deck). Until the client's extract has landed (Inputs/ILS PGL/<id>/ or Inputs/ILS Kickoff/<id>/) the card
is a compact one that says which extract is missing and where it goes, with Check again. The codes a client's last run was confirmed with are offered back with that run's date and
file; they are the CSM's to keep or change and are never applied until Build is pressed (James Gilmore, 2026-10-28:
"the user will confirm the limits. the client wont confirm anything"). What the CSM types is held in the page, so the
status refresh that redraws the client page does not lose it.

Above the two, the **ILS Review** card (Aaron, 2026-11-24; it was "Coming soon"): the ILS Program
Analysis deck for a client on the ILS analysts' review schedule, built from the client's landed data pull, with its
readiness checks, Build, and Build with prep slides when the client's prep deck is on hand (the file it merges is
named on the card). A client not on the schedule gets the card too, saying so. Its facts and run are
ils_review_runs.py's.

The runs and the files are in ils_runs.py and the routes in ils_ui.py (`get`, `post`); this is the page side, moved
here from the old page's `ils_ui.JS` when Sheila moved to the Hub layout. It is not a tab: sheila_hub.py draws
`<div id="ilscards">` on the ILS side of the client page (renderIlsDetail) and calls `ilsCards(client)` after drawing it;
the header's "ILS checked at" and "Check ILS again" are this read.
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
details.ilsinputs{margin:6px 0 2px;border:1px solid var(--line);border-radius:12px;padding:6px 12px}
details.ilsinputs summary{cursor:pointer;font-weight:600;color:var(--ink)}
.ilsin{display:grid;grid-template-columns:minmax(170px,max-content) minmax(200px,520px);gap:8px 14px;align-items:start;margin:8px 0}
.ilsin textarea{min-height:70px;resize:vertical}
.sub{color:var(--muted)}
ul.ilsnotes{margin:4px 0 0;padding-left:18px;font-size:12.5px;color:var(--muted)}
/* a long folder path or file name wraps inside its card rather than widening the page (a phone, 2026-11-25) */
#ilscards{min-width:0} #ilscards .pc{min-width:0;overflow-wrap:anywhere}
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
  try { ({body: ILS.doc} = await api("/api/ils/client?client=" + encodeURIComponent(cid))); ILS.at = new Date(); }
  catch (e) { box.innerHTML = `<section class="pc"><p class="err">Couldn't read the ILS folders: ${esc(e.message)}</p></section>`; return; }
  if (ILS.cid !== cid) return;
  ilsDraw();
  for (const k of ["pgl", "kickoff"]) { const j = ILS.doc.kinds[k] && ILS.doc.kinds[k].job; if (j && !j.done) ilsPoll(k); }
  const rj = ILS.doc.review && ILS.doc.review.job; if (rj && !rj.done) ilsPoll("review");
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
  const state = !c.extract ? `<span class="chip k-idle">${si("idle")}No extract yet</span>` : c.last ? `<span class="chip k-outputs">Deck built</span>` : `<span class="chip k-ready">Extract landed</span>`;
  const head = (btns) => `<div class="pch"><h3>${esc(title)} <span class="mix">${kind === "pgl" ? "report and board deck" : "workbook and deck"}</span> ${state}</h3><div class="act">${btns}</div></div>`;
  // No extract yet (2026-11-25): a compact card, like the review card waiting for its data: what is missing, where it goes.
  if (!c.extract) return `<section class="pc" id="ils${kind}">${head(`<button class="btn" data-ilsreview="recheck">Check again</button>`)}
      <ul class="checks">${ilsWarn(`No ${kind === "pgl" ? "pre-go-live" : "kickoff one-time data"} extract has landed for this client. Put it in ${c.folder || "its folder"}, then Check again.`)}</ul>
      <p class="why">${kind === "pgl" ? "Expected: <code>&lt;id&gt;_&lt;Client&gt;_PreGL_&lt;yyyymmdd&gt;.csv</code> with the vendor's MatrixValidation / IntegrityCheck dumps beside it, or the delivery's <code>&lt;id&gt;_…_PGL_&lt;yyyymmdd&gt;.zip</code> in the folder above." : "Expected: <code>&lt;id&gt;_OneTimeData_&lt;yyyymmdd&gt;.csv</code> or <code>.xlsx</code>."}</p></section>`;
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

// The ILS page shows every ILS card (Aaron, 2026-11-25: "it no longer needs the dropdown to show them"): the review
// card, then pre-go-live and kickoff, each saying plainly what it is waiting for. The header says when this was read.
function ilsWarn(text) {
  return `<li><span class="t ck-warn">${ICONS.warn.replace('<svg', '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"')}</span><span>${esc(text)}</span></li>`;
}

function ilsDraw() {
  const box = $("#ilscards"); if (!box || !ILS.doc) return;
  box.innerHTML = ilsReviewCard() + ilsCard("pgl") + ilsCard("kickoff");
  const age = $("#ilsage");
  if (age && ILS.at) age.textContent = "ILS checked at " + ILS.at.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
}

// ------------------------------------------------------------------ the ILS Review card (Aaron, 2026-11-24)
// The ILS Program Analysis deck for a client on the analysts' review schedule, from its landed data pull
// (ils_review_runs.py). First on the ILS page; a client not on the schedule gets the card saying so (2026-11-25), with
// Check again. Build with prep slides is offered only when the
// client's prep deck is on hand, and names the file it will merge.
const ILS_REVIEW_CHIP = {ready: ["k-ready", "ready", "Ready to build"], waiting: ["k-idle", "idle", "Waiting for data"],
  blocked: ["k-blocked", "blocked", "Can't build yet"], unknown: ["k-checking", "checking", "Unknown"],
  not_scheduled: ["k-idle", "idle", "Not scheduled"]};
function ilsReviewCard() {
  const r = ILS.doc && ILS.doc.review; if (!r) return "";
  const j = r.job, running = !!(j && !j.done), d = r.decks || {};
  // a deck counts as this review's only when it was built from this review's pull (its period is the pull month)
  const delivered = (d.review && d.review.current) || (d.analysis && d.analysis.current);
  const [cls, icon, label] = (delivered && r.state === "ready") ? ["k-outputs", "outputs", "In Outputs"] : (ILS_REVIEW_CHIP[r.state] || ILS_REVIEW_CHIP.unknown);
  const ready = r.state === "ready";
  const btns = ready ? `<span class="btns"><button class="btn primary" data-ilsreview="plain"${running ? " disabled" : ""}>${d.analysis && d.analysis.current ? "Rebuild" : "Build"}</button>` +
    (r.prep ? `<button class="btn" data-ilsreview="prep"${running ? " disabled" : ""} title="${esc(r.prep.name)}">Build with prep slides</button>` : "") +
    `</span><span class="why">goes to Outputs\\ILS when it passes validation</span>` : `<button class="btn" data-ilsreview="recheck">Check again</button>`;
  const facts = [];
  if (r.pull) facts.push(`Data pull <b>${esc(r.pull)}</b>`);
  if (r.review_date) facts.push(`review <b>${esc(r.review_date)}</b>`);
  for (const [k, what] of [["analysis", "analysis deck"], ["review", "review deck with prep slides"]]) {
    if (d[k]) facts.push(`${d[k].current ? "" : "an earlier review's "}${what} ${esc(d[k].when)} · <button class="link" data-ilsreveal="${esc(d[k].deck)}">open it</button>`);
  }
  const prep = ready && r.prep ? `<p class="ilssaved">Build with prep slides merges <b>${esc(r.prep.name)}</b> (matched by client number) and leaves out the analysis deck's own matrix slides.</p>` : "";
  const rows = (r.checks || []).map(c => ({...c, ck: LEVEL[c.level] || "ok"}));
  const li = c => `<li><span class="t ck-${c.ck}">${ICONS[c.ck === "ok" ? "ok" : c.ck === "warn" ? "warn" : "stop"].replace('<svg', '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"')}</span><span>${esc(c.text)}</span></li>`;
  const shown = rows.filter(c => c.ck !== "ok"), folded = rows.filter(c => c.ck === "ok");
  return `<section class="pc${r.state === "blocked" ? " stopc" : ""}" id="ilsreview">
    <div class="pch"><h3>ILS Review <span class="mix">ILS Program Analysis</span> <span class="chip ${cls}">${si(icon)}${esc(label)}</span></h3><div class="act">${btns}</div></div>
    ${facts.length ? `<p class="fact">${facts.join(" · ")}</p>` : ""}${prep}
    ${shown.length ? `<ul class="checks">${shown.map(li).join("")}</ul>` : ""}
    ${folded.length ? `<details class="fold"><summary>${folded.length}${shown.length ? " other" : ""} check${folded.length === 1 ? "" : "s"} passed</summary><ul class="checks" style="margin-top:6px">${folded.map(li).join("")}</ul></details>` : ""}
    <div id="ilsjobreview">${j ? ilsReviewJobHtml(j) : ""}</div></section>`;
}

function ilsReviewJobHtml(j) {
  const what = j.merge_prep ? "Build with prep slides" : "Build";
  let state;
  if (!j.done) state = `<p class="why">${what} running… ${j.seconds}s</p>`;
  else if (j.ok) state = `<p class="why"><b>In Outputs.</b> ${j.deck ? `<button class="link" data-ilsreveal="${esc(j.deck)}">Show in File Explorer</button>` : ""}${j.verdict ? " · validation " + esc(j.verdict) : ""} — read the builder's notes below before quoting any number.</p>`;
  else state = `<p class="why err">${what} stopped${j.error ? ": " + esc(j.error) : ""}.${j.deck ? ` <button class="link" data-ilsreveal="${esc(j.deck)}">Show the deck in File Explorer</button>` : ""}</p>`;
  const notes = (j.notes || []).filter(Boolean);
  return state + (notes.length ? `<ul class="ilsnotes">${notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : "") +
    `<pre class="ilslog">${esc((j.lines || []).join("\n"))}</pre>`;
}

async function ilsReviewRun(mode) {
  if (mode === "recheck") return ilsCards(ILS.cid);
  const known = (typeof CLIENTS !== "undefined" && CLIENTS.find(x => x.id === ILS.cid)) || {};
  const body = {kind: "review", client: ILS.cid, client_name: known.name || "", merge_prep: mode === "prep"};
  let r;
  try { r = await api("/api/ils/run", {method: "POST", body: JSON.stringify(body)}); }
  catch (e) { const b = $("#ilsjobreview"); if (b) b.innerHTML = `<p class="why err">${esc(e.message)}</p>`; return; }
  if (!r.body.job) { const b = $("#ilsjobreview"); if (b) b.innerHTML = `<p class="why err">Not started: ${esc(r.body.error || "the server refused it")}</p>`; return; }
  ilsShow("review", r.body.job); ilsPoll("review");
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
  if (kind === "review") {
    if (ILS.doc && ILS.doc.review) ILS.doc.review.job = j;
    const rb = $("#ilsjobreview"); if (!rb || !j) return;
    rb.innerHTML = ilsReviewJobHtml(j);
    const rp = rb.querySelector("pre"); if (rp && !j.done) rp.scrollTop = rp.scrollHeight;
    for (const b of document.querySelectorAll("#ilsreview [data-ilsreview]")) if (b.dataset.ilsreview !== "recheck") b.disabled = !j.done;
    return;
  }
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
  const rv1 = t.closest("[data-ilsreview]"); if (rv1) return ilsReviewRun(rv1.dataset.ilsreview);
  if (t.closest("#ilsinsave")) return ilsSaveInputs();
  const rv = t.closest("[data-ilsreveal]");
  if (rv) { try { await api("/api/ils/reveal", {method: "POST", body: JSON.stringify({path: rv.dataset.ilsreveal})}); } catch (err) { alert(err.message); } }
});
"""

JS = JS.replace("__ILS_LABELS__", __import__("json").dumps(LABELS))
