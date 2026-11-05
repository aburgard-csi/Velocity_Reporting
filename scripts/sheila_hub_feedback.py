"""The Feedback tab of CSM Sheila, in the Hub layout: the issue reports people sent from Sheila, and a short form to send one.

Reports are QUEUED to the share by `issue_reports.queue` and filed on GitHub by the next sync (Sheila never talks
to GitHub: it runs on each CSM's machine and the repo is private, so there are no credentials here by design), so
a row that says `queued` is recorded but not yet an issue. The list is `GET /api/reports` (the queue merged with the
issue cache); the form is `POST /api/report`. The logic is in issue_reports.py and ars_launcher_web.py; this is the
page side, moved here from the old page's `reportedView` and its dialog when Sheila moved to the Hub layout.
"""
TAB = "reported"
NAME = "Feedback"

VIEW = r"""
<div class="vh"><div><h1>Feedback</h1><p id="fb-sub">Reading the reports…</p></div></div>
<div class="kpis kpis3" id="fb-kpis" role="group" aria-label="Filter by state"></div>
<div class="split fbsplit">
  <section class="card" aria-label="Report a problem">
    <header><h2>Report a problem</h2><p class="sub">With Sheila or with a deck. Saved to the share now; it reaches GitHub on the next sync.</p></header>
    <form class="fbform" id="fb-form" autocomplete="off">
      <label for="fb-title">What is wrong?</label>
      <input id="fb-title" type="text" maxlength="200" required placeholder="e.g. Lift Matrix is slow for 1549">
      <label for="fb-body">Anything that would help fix it</label>
      <textarea id="fb-body" maxlength="8000" placeholder="What you did, what happened, what you expected."></textarea>
      <label for="fb-client">Client, if it is about one</label>
      <select id="fb-client"></select>
      <div class="fbact"><button class="btn primary" type="submit" id="fb-send">Send report <kbd>Ctrl Enter</kbd></button><span class="why" id="fb-hint"></span></div>
    </form>
  </section>
  <section class="card" aria-label="Reports">
    <div class="lhead">
      <label class="find"><svg viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/></svg><input id="fb-q" type="search" placeholder="Find a report" autocomplete="off" aria-label="Find a report"><kbd>/</kbd></label>
      <div class="filt" id="fb-filt"></div>
    </div>
    <div class="list fblist" id="fb-list" role="list" aria-live="polite"></div>
  </section>
</div>
"""

CSS = r"""
/* Feedback */
.kpis3{grid-template-columns:repeat(3,minmax(0,1fr))}
.fbsplit{grid-template-columns:minmax(300px,.8fr) minmax(0,1.4fr)}
.fbform{display:grid;gap:6px;padding:4px 16px 16px}
.fbform label{font-size:13px;color:var(--muted);margin-top:6px}
.fbform input,.fbform textarea,.fbform select{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:12px;background:var(--sheet);color:var(--ink);width:100%}
.fbform textarea{min-height:110px;resize:vertical}
.fbform input:focus-visible,.fbform textarea:focus-visible,.fbform select:focus-visible{outline:2px solid var(--good);outline-offset:1px}
.fbact{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin-top:10px}
.fblist{max-height:none}
.frow{display:grid;grid-template-columns:20px 4.2em minmax(0,1fr) auto;gap:2px 10px;align-items:start;width:100%;padding:9px 10px;border:0;border-radius:12px;background:none;text-align:left}
.frow:hover{background:var(--glass-hi)}
.frow[aria-current="true"]{background:var(--fill);box-shadow:inset 0 0 0 1px var(--glass-line)}
.frow .fn{font:12.5px var(--mono);color:var(--muted);padding-top:2px}
.frow .ft{font-weight:600;min-width:0}
.frow .fm{grid-column:3/5;font-size:12.5px;color:var(--muted);display:flex;flex-wrap:wrap;gap:2px 12px}
.frow .fb{grid-column:3/5;font-size:13.5px;color:var(--ink);white-space:pre-wrap;margin:4px 0 2px}
.frow a{color:var(--good)}
@media (max-width:1180px){.fbsplit{grid-template-columns:1fr}}
@media (max-width:820px){.frow{grid-template-columns:20px minmax(0,1fr) auto}.frow .fn{display:none}.frow .fm,.frow .fb{grid-column:2/4}}
"""

JS = r"""
// ------------------------------------------------------------ Feedback
(function () {
  const F = {rows: [], loaded: false, filter: "", cur: null, open: new Set(), error: "", fetched: "", queued: 0};
  const KIND = {open: ["ready", "Open"], closed: ["outputs", "Closed"], queued: ["checking", "Queued"]};
  const stateOf = r => r.state === "open" ? "open" : r.state === "closed" ? "closed" : "queued";
  const key = r => r.number ? "#" + r.number : "q" + (r.id || r.title);

  async function load() {
    try {
      const {body} = await api("/api/reports");
      F.rows = body.rows || []; F.error = body.error || ""; F.fetched = body.fetched_at ? body.fetched_at.replace("T", " ") : ""; F.queued = body.queued || 0;
    } catch (e) { F.error = "Couldn't read the reports: " + e.message; }
    F.loaded = true; paint();
  }

  function visible() {
    const q = ($("#fb-q").value || "").trim().toLowerCase();
    return F.rows.filter(r => (!F.filter || stateOf(r) === F.filter) && (!q || [r.title, r.body, r.client_id, r.reporter, r.number].join(" ").toLowerCase().includes(q)));
  }

  function paint() {
    const n = {open: 0, closed: 0, queued: 0};
    for (const r of F.rows) n[stateOf(r)]++;
    $("#fb-sub").innerHTML = !F.loaded ? "Reading the reports…" : `${F.rows.length} report${F.rows.length === 1 ? "" : "s"}${F.queued ? " · " + F.queued + " not yet filed" : ""}${F.fetched ? " · GitHub as of " + esc(F.fetched) : ""}`;
    $("#fb-kpis").innerHTML = Object.entries(KIND).map(([k, [ic, w]]) => `<button class="kpi" data-fbkind="${k}" aria-pressed="${F.filter === k}" title="Show only: ${esc(w)}">
      <span class="k">${si(ic)}${esc(w)}</span><span class="v">${F.loaded ? n[k] : "–"}</span><span class="n">${k === "queued" ? "recorded, not on GitHub yet" : k === "open" ? "being worked on" : "done"}</span></button>`).join("");
    const rows = visible();
    $("#fb-filt").innerHTML = !F.loaded ? "" : F.filter ? `Showing <b>${esc(KIND[F.filter][1])}</b> <button class="x" data-fbclear>Clear ✕</button>` : `${rows.length} report${rows.length === 1 ? "" : "s"}`;
    if (!F.loaded) { $("#fb-list").innerHTML = Array.from({length: 6}, () => `<div class="frow"><span class="sk" style="width:16px;height:16px"></span><span class="sk" style="width:40px;height:12px"></span><span class="sk" style="width:${45 + Math.random() * 40 | 0}%;height:14px"></span></div>`).join(""); return; }
    let html = F.error ? `<p class="empty err">${esc(F.error)}</p>` : "";
    html += rows.map(r => {
      const [ic, lab] = KIND[stateOf(r)], k = key(r), open = F.open.has(k);
      const num = r.number ? `<a href="${esc(r.url || "#")}" target="_blank" rel="noopener">#${r.number}</a>` : "–";
      return `<div role="listitem"><button class="frow" data-fbkey="${esc(k)}" aria-current="${F.cur === k}" aria-expanded="${open}">${si(ic)}<span class="fn">${num}</span><span class="ft">${esc(r.title || "")}</span><span class="chip k-${ic}">${esc(lab)}</span>
        <span class="fm">${r.client_id ? `<span>Client ${esc(r.client_id)}</span>` : ""}${r.reporter ? `<span>${esc(r.reporter)}</span>` : ""}<span>${esc((r.created || "").replace("T", " ").slice(0, 16))}</span></span>
        ${open && r.body ? `<span class="fb">${esc(r.body)}</span>` : !open && r.body ? `<span class="fm">${esc(r.body.slice(0, 140))}${r.body.length > 140 ? "…" : ""}</span>` : ""}</button></div>`;
    }).join("");
    $("#fb-list").innerHTML = html || `<p class="empty">${F.filter || $("#fb-q").value ? "No reports match." : "Nothing reported yet. Be the first."}</p>`;
  }

  function fillClients() {
    const sel = $("#fb-client"), keep = sel.value || (TAB === "decks" ? CUR : "") || "";
    sel.innerHTML = `<option value="">No client</option>` + CLIENTS.map(c => `<option value="${esc(c.id)}">${esc(c.id)} ${esc(c.name || "")}</option>`).join("");
    sel.value = [...sel.options].some(o => o.value === keep) ? keep : "";
  }

  async function send(ev) {
    ev.preventDefault();
    const title = $("#fb-title").value.trim(); if (!title) { $("#fb-title").focus(); return; }
    $("#fb-send").disabled = true; $("#fb-hint").textContent = "Saving…";
    try {
      await api("/api/report", {method: "POST", body: JSON.stringify({title, body: $("#fb-body").value, client: $("#fb-client").value, page: "reported"})});
      $("#fb-title").value = ""; $("#fb-body").value = ""; $("#fb-hint").textContent = "";
      toast("Reported. It is saved, and reaches GitHub on the next sync.", "good", 5000);
      await load();
    } catch (e) { $("#fb-hint").textContent = "Couldn't save it: " + e.message; toast("Couldn't save the report: " + e.message, "bad", 6000); }
    $("#fb-send").disabled = false;
  }

  function move(d) {
    const rows = visible(), i = rows.findIndex(r => key(r) === F.cur), next = rows[Math.max(0, Math.min(rows.length - 1, i < 0 ? 0 : i + d))];
    if (!next) return; F.cur = key(next); paint();
    const el = $(`[data-fbkey="${CSS.escape(F.cur)}"]`); if (el) el.scrollIntoView({block: "nearest"});
  }

  function focusForm() { go("reported"); setTimeout(() => $("#fb-title").focus(), 0); }

  $("#fb-form").addEventListener("submit", send);
  $("#fb-form").addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $("#fb-form").requestSubmit(); } });
  $("#fb-q").addEventListener("input", paint);
  $("#v-reported").addEventListener("click", e => {
    const k = e.target.closest("[data-fbkind]"); if (k) { F.filter = F.filter === k.dataset.fbkind ? "" : k.dataset.fbkind; return paint(); }
    if (e.target.closest("[data-fbclear]")) { F.filter = ""; return paint(); }
    if (e.target.closest("a")) return;
    const row = e.target.closest("[data-fbkey]");
    if (row) { const kk = row.dataset.fbkey; F.cur = kk; if (F.open.has(kk)) F.open.delete(kk); else F.open.add(kk); paint(); }
  });
  $("#reportbtn").addEventListener("click", focusForm);

  registerTab("reported", {
    enter() { fillClients(); paint(); load(); },
    refresh() { paint(); },
    keys: [["j  k", "Move through the reports"], ["Enter", "Open or close a report"], ["N", "Write a new report"], ["/", "Find a report"], ["Ctrl  Enter", "Send the report you are writing"]],
    key(e) {
      const k = e.key;
      if (k === "j" || k === "ArrowDown") { e.preventDefault(); move(1); }
      else if (k === "k" || k === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (k === "Enter" && F.cur && !document.activeElement.closest(".frow")) { if (F.open.has(F.cur)) F.open.delete(F.cur); else F.open.add(F.cur); paint(); }
      else if (k === "n") { e.preventDefault(); $("#fb-title").focus(); }
      else if (k === "/") { e.preventDefault(); $("#fb-q").focus(); }
      else if (k === "Escape") { if (F.cur) { F.cur = null; paint(); } }
    },
    global: () => [{t: "Report a problem", s: "Feedback", run: focusForm}],
  });
})();
"""
