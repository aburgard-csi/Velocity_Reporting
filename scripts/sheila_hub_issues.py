"""The Data Issues tab of CSM Sheila, in the Hub layout (Aaron, 2026-09-25; moved to the Hub 2026-11-02).

Each client's data issues from the issue pages and the morning dashboard's checks, with a link to its code sheet.
Items are marked complete with one click (`POST /api/issues/mark`); a mark stays until a newer workbook lands for the
client, then the item comes back with the date it was marked and what arrived since (Aaron, 2026-09-28). The
issues come from `GET /api/issues` (ars_launcher_web.issues_doc); the code sheets open through `POST /api/code-sheet`.

The tab is a client list (with open counts) beside the cards: no client chosen shows every visible client's card, one
chosen shows only that client's, and choosing it again goes back. The links row (code sheet, deck checks, Lift
Matrix, issue count) is the same everywhere a client is named, as before (Aaron, 2026-10-02: "consistent across the
tabs"); `clientLinks` draws it on the Decks client page too. The sidebar badge is the open count for the CSM shown.
"""
TAB = "issues"
NAME = "Data Issues"

VIEW = r"""
<div class="vh"><div><h1>Data Issues</h1><p id="is-sub">Reading the data issues…</p></div><div class="vhr" id="is-csm"></div></div>
<div class="kpis kpis6" id="is-kpis" role="group" aria-label="Filter by kind"></div>
<div class="split" id="is-split">
  <section class="card" aria-label="Clients with issues">
    <div class="lhead">
      <label class="find"><svg viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/></svg><input id="is-q" type="search" placeholder="Name or number" autocomplete="off" aria-label="Find a client"><kbd>/</kbd></label>
      <div class="filt" id="is-filt"></div>
    </div>
    <div class="list" id="is-list" role="list" aria-live="polite"></div>
  </section>
  <section class="card isdetail" id="is-detail" aria-label="Issues" aria-live="polite"></section>
</div>
"""

CSS = r"""
/* Data Issues */
.vhr{display:flex;gap:8px;align-items:center}
.kpis6{grid-template-columns:repeat(6,minmax(0,1fr))}
select.ctl{padding-right:8px}
.isrow{grid-template-columns:20px 3.2em minmax(0,1fr) auto}
.isrow .chip{min-width:26px;justify-content:center}
.sev{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;padding:2px 8px;border-radius:999px;background:var(--fill);color:var(--muted);flex:none}
.sev.blocker{background:var(--bad-soft);color:var(--bad)} .sev.decision{background:var(--warn-soft);color:var(--warn)} .sev.codes{background:var(--warn-soft);color:var(--warn)} .sev.lift{background:var(--bad-soft);color:var(--bad)}
.icard{border:1px solid var(--line);border-radius:14px;background:var(--sheet);padding:12px 14px;display:grid;gap:8px}
.ihead{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline}
.ihead h3{margin:0;font:700 15px var(--display)}
.ihead .sub{color:var(--muted);font-size:13px}
.ihead .clientlinks{margin-left:auto}
.ilist{list-style:none;margin:0;padding:0;display:grid;gap:2px}
.iitem{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:start;padding:8px 6px;border-radius:10px;border-top:1px solid var(--line)}
.iitem:first-child{border-top:0}
.iitem:hover{background:var(--glass-hi)}
.iitem.idone{opacity:.8}
.iitem .it{font-size:14px}
.iitem .sub{display:block;color:var(--muted);font-size:12.5px;margin-top:2px}
.iitem .reopened{color:var(--warn)}
.iitem .imark{padding-top:1px}
.chipbtn{display:inline-flex;align-items:center;gap:6px;min-height:30px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:var(--sheet);font-size:13px;font-weight:600;white-space:nowrap}
.chipbtn:hover{border-color:var(--good);color:var(--good)}
.chipbtn:disabled{opacity:.6}
.clientlinks{display:flex;flex-wrap:wrap;gap:2px 10px;align-items:center;font-size:13px;color:var(--muted)}
.clientlinks .link{font-size:13px}
.srcnote{padding:0 18px 14px;font-size:12.5px;color:var(--muted)}
.allclear{padding:22px 18px;display:grid;gap:4px;justify-items:start}
.allclear b{font:700 16px var(--display)}
@media (max-width:980px){.kpis6{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:820px){.kpis6{display:flex}.iitem{grid-template-columns:auto minmax(0,1fr)}.iitem .imark{grid-column:2}}
"""

JS = r"""
// ------------------------------------------------------------ Data Issues
let ISSUES = null, ISSUES_AT = 0;
async function loadIssues(fresh) {
  if (ISSUES && !fresh && Date.now() - ISSUES_AT < 60000) return ISSUES;
  const {body} = await api("/api/issues"); ISSUES = body; ISSUES_AT = Date.now(); paintIssueBadge(); return ISSUES;
}
const issueOpen = x => !!x && !x.done;
const issueCount = e => (e.issues || []).filter(issueOpen).length + (e.codes || []).filter(issueOpen).length + (issueOpen(e.lift_matrix) ? 1 : 0);
function paintIssueBadge() {
  const b = $("#b-issues"); if (!b || !ISSUES) return;
  const csm = $("#csm").value, n = (ISSUES.clients || []).filter(e => !csm || e.csm === csm).reduce((t, e) => t + issueCount(e), 0);
  b.textContent = n ? String(n) : "";
}

function codeSheetLinks(cid, name) {
  return name ? `<button class="link" data-cs="${esc(cid)}" title="${esc(name)}">Open code sheet</button> · <button class="link" data-csr="${esc(cid)}">Show it in File Explorer</button>`
              : `<span>No code sheet in Inputs/Code Sheets</span>`;
}
// The one links row under a client's name on every tab: the code sheet first, then where else the client can be looked at;
// the tab you are on is left out rather than linking to itself.
function linksRowHTML(cid, codeSheet, count, here) {
  const parts = [codeSheetLinks(cid, codeSheet)];
  if (here !== "decks") parts.push(`<button class="link" data-goto="decks" data-client="${esc(cid)}">Deck checks</button>`);
  if (here !== "lift") parts.push(`<button class="link" data-goto="lift" data-client="${esc(cid)}">Lift Matrix</button>`);
  if (here !== "issues") parts.push(`<button class="link" data-goto="issues" data-client="${esc(cid)}">${count ? count + " data issue" + (count === 1 ? "" : "s") : "No data issues"}</button>`);
  return parts.join(" · ");
}
async function clientLinks(cid, here, box) {
  if (!box) return;
  try {
    const d = await loadIssues(), e = (d.clients || []).find(x => x.id === cid);
    if (!box.isConnected) return;
    box.innerHTML = linksRowHTML(cid, e && e.code_sheet, e ? issueCount(e) : 0, here);
  } catch (err) { box.innerHTML = `<span class="err">Couldn't read the data issues: ${esc(err.message)}</span>`; }
}
document.addEventListener("click", async ev => {
  const go_ = ev.target.closest("[data-goto]");
  if (go_) { const t = go_.dataset.goto, c = go_.dataset.client; if (t === "decks") { go("decks"); openClient(c); } else go(t, {client: c}); return; }
  const cs = ev.target.closest("[data-cs],[data-csr]");
  if (cs) {
    const cid = cs.dataset.cs || cs.dataset.csr;
    try { await api("/api/code-sheet", {method: "POST", body: JSON.stringify({client: cid, action: cs.dataset.csr ? "reveal" : "open"})}); }
    catch (e) { toast(e.message, "bad"); }
  }
});

(function () {
  const I = {kind: "", cur: null, q: "", lastMark: null, loaded: false, error: ""};
  const SEV = {blocker: "Blocker", decision: "Decision", gap: "Gap", warning: "Warning"};
  const KINDS = [["blocker", "Blockers", "stop"], ["decision", "Decisions", "attention"], ["gap", "Gaps", "checking"], ["warning", "Warnings", "checking"], ["codes", "Codes and Lift", "attention"], ["done", "Completed", "outputs"]];
  const ORDER = ["blocker", "decision", "gap", "warning"];

  function shownClients() {
    const csm = $("#csm").value, q = I.q.trim().toLowerCase();
    return ((ISSUES && ISSUES.clients) || []).filter(e => (!csm || e.csm === csm) && (!q || e.id.includes(q) || (e.name || "").toLowerCase().includes(q)));
  }
  const kindCount = (list, k) => list.reduce((n, e) => n + (k === "done" ? (e.done_count || 0)
    : k === "codes" ? (e.codes || []).filter(issueOpen).length + (issueOpen(e.lift_matrix) ? 1 : 0)
    : (e.issues || []).filter(i => issueOpen(i) && i.severity === k).length), 0);
  // The clients the list shows: those with something to show under the chosen kind.
  function listed() {
    return shownClients().filter(e => I.kind === "done" ? (e.done_count || 0) > 0 : I.kind ? kindCount([e], I.kind) > 0 : issueCount(e) > 0);
  }
  const worst = e => { const s = (e.issues || []).filter(issueOpen).map(i => i.severity); for (const k of ORDER) if (s.includes(k)) return k; return issueOpen(e.lift_matrix) ? "blocker" : "warning"; };

  function item(e, it, tag, body) {
    if (I.kind === "done" ? !it.done : !!it.done) return "";
    const btn = it.done ? `<button class="link" data-mark="${esc(it.key)}" data-client="${esc(e.id)}" data-done="0">Undo</button>`
      : `<button class="chipbtn" data-mark="${esc(it.key)}" data-client="${esc(e.id)}" data-done="1">${si("ok")}Mark complete</button>`;
    const state = it.done ? `<span class="sub">Marked complete ${esc(it.done.at)}${it.done.by ? " by " + esc(it.done.by) : ""}. It stays complete until a new workbook arrives for this client.</span>`
      : it.reopened ? `<span class="sub reopened">Marked complete ${esc(it.reopened.at)}${it.reopened.by ? " by " + esc(it.reopened.by) : ""}; a new workbook has arrived since${it.reopened.new && it.reopened.new.length ? " (" + esc(it.reopened.new.join(", ")) + ")" : ""}. Check it again.</span>` : "";
    return `<li class="iitem${it.done ? " idone" : ""}">${tag}<span class="it">${body}${state}</span><span class="imark">${btn}</span></li>`;
  }

  function card(e, solo) {
    const rows = [];
    for (const i of (e.issues || [])) {
      if (I.kind && I.kind !== "done" && I.kind !== i.severity) continue;
      rows.push(item(e, i, `<span class="sev ${esc(i.severity)}">${esc(SEV[i.severity] || i.severity)}</span>`,
        `<b>${esc(i.program || "")}</b> ${esc(i.issue)}${i.fix ? `<span class="sub">Fix: ${esc(i.fix)}</span>` : ""}`));
    }
    if (!I.kind || I.kind === "codes" || I.kind === "done") {
      if (e.lift_matrix) rows.push(item(e, e.lift_matrix, `<span class="sev lift">Lift</span>`,
        `<b>ARS</b> Lift Matrix flagged "${esc(e.lift_matrix.flag)}" in ${esc(e.lift_matrix.workbook)}<span class="sub">Fix: create a new Lift Matrix (the Lift Matrix tab), then send it to Bradford</span>`));
      for (const c of (e.codes || [])) {
        const vals = (c.values || []).map(v => `${esc(v.value)}${v.desc ? " (" + esc(v.desc) + ")" : ""}: ${(v.accounts || 0).toLocaleString()} account${v.accounts === 1 ? "" : "s"}${v.open != null ? ", " + v.open.toLocaleString() + " open" : ""}`).join("; ");
        rows.push(item(e, c, `<span class="sev codes">Codes</span>`,
          `<b>ARS</b> ${esc(c.label)}${c.eligibility ? " (decides eligibility)" : ""}: ${vals}${c.no_table ? ' <span class="sub">(no code table for this kind)</span>' : ""}<span class="sub">Fix: correct the client's code sheet</span>`));
      }
    }
    const body = rows.filter(Boolean);
    if (!body.length) return "";
    const unchecked = !I.kind && (e.unchecked || []).length ? `<p class="sub" style="margin:2px 0 0;color:var(--muted);font-size:12.5px">Not checked: ${esc(e.unchecked.join("; "))}</p>` : "";
    return `<section class="icard" id="issue-${esc(e.id)}"><div class="ihead"><h3>${esc(e.name || e.id)}</h3><span class="sub">${esc(e.id)} · ${esc(e.csm)}</span>
      <span class="clientlinks">${linksRowHTML(e.id, e.code_sheet, issueCount(e), "issues")}</span></div><ul class="ilist">${body.join("")}</ul>${unchecked}</section>`;
  }

  function paint() {
    const csmBox = $("#is-csm"); if (csmBox) csmBox.innerHTML = csmPick();
    if (!I.loaded) {
      $("#is-sub").textContent = "Reading the data issues…";
      $("#is-kpis").innerHTML = KINDS.map(([k, w]) => `<div class="kpi"><span class="k">${esc(w)}</span><span class="v">–</span></div>`).join("");
      $("#is-list").innerHTML = Array.from({length: 7}, () => `<div class="row isrow"><span class="sk" style="width:16px;height:16px"></span><span class="sk" style="width:38px;height:12px"></span><span class="sk" style="width:${50 + Math.random() * 40 | 0}%;height:14px"></span></div>`).join("");
      $("#is-detail").innerHTML = `<div class="pres"><div class="icard"><span class="sk" style="width:45%;height:18px"></span><span class="sk" style="width:90%;height:12px"></span><span class="sk" style="width:70%;height:12px"></span></div></div>`;
      return;
    }
    if (I.error) { $("#is-detail").innerHTML = `<p class="empty err">${esc(I.error)}</p>`; return; }
    const all = shownClients(), src = (ISSUES && ISSUES.sources) || {};
    $("#is-sub").innerHTML = `${all.reduce((t, e) => t + issueCount(e), 0)} open across ${all.filter(e => issueCount(e) > 0).length} client${all.filter(e => issueCount(e) > 0).length === 1 ? "" : "s"} · issue list as of ${esc(src.issue_pages || "never")}, code and Lift Matrix checks as of ${esc(src.dashboard || "never")}`;
    $("#is-kpis").innerHTML = KINDS.map(([k, w, ic]) => `<button class="kpi" data-ikind="${k}" aria-pressed="${I.kind === k}" title="Show only: ${esc(w)}"><span class="k">${si(ic)}${esc(w)}</span><span class="v">${kindCount(all, k)}</span><span class="n">${k === "done" ? "done for now" : "open"}</span></button>`).join("");
    const list = listed();
    $("#is-filt").innerHTML = I.kind ? `Showing <b>${esc(KINDS.find(x => x[0] === I.kind)[1])}</b> <button class="x" data-iclear>Clear ✕</button>` : `${list.length} client${list.length === 1 ? "" : "s"} with open issues`;
    $("#is-list").innerHTML = list.length ? list.map(e => {
      const n = I.kind === "done" ? e.done_count : I.kind ? kindCount([e], I.kind) : issueCount(e), w = worst(e);
      return `<button class="row isrow" role="listitem" data-iid="${esc(e.id)}" aria-current="${I.cur === e.id}">${si(w === "blocker" ? "blocked" : w === "decision" ? "attention" : "checking")}<span class="rid">${esc(e.id)}</span><span class="rnm">${esc(e.name || e.id)}</span><span class="chip k-${w === "blocker" ? "blocked" : w === "decision" ? "attention" : "ready"}">${n}</span></button>`;
    }).join("") : `<p class="empty">${I.kind === "done" ? "Nothing marked complete." : "No open data issues" + (I.kind ? " of this kind." : ".")}</p>`;
    const focus = I.cur ? all.find(e => e.id === I.cur) : null;
    const cards = (focus ? [focus] : all).map(e => card(e)).filter(Boolean);
    const head = focus ? `<div class="dh"><h2>${esc(focus.name || focus.id)}</h2><span class="meta">${esc(focus.id)} · ${esc(focus.csm)}<button class="link" data-iall style="margin-left:auto">All clients <kbd>Esc</kbd></button></span></div>` : "";
    $("#is-detail").innerHTML = head + (cards.length ? `<div class="pres">${cards.join("")}</div>`
      : `<div class="allclear"><b>${I.kind === "done" ? "Nothing marked complete." : "Nothing open here."}</b><span class="sub" style="color:var(--muted)">${I.kind ? "Clear the filter to see everything else." : "Every data issue for " + (focus ? "this client" : "these clients") + " is complete or none was found."}</span></div>`);
    const nb = $("#is-detail .allclear"); if (nb && !I.kind && !focus) nb.querySelector("b").textContent = "No open data issues. Nicely done.";
  }

  async function mark(btn) {
    const cid = btn.dataset.client, key = btn.dataset.mark, done = btn.dataset.done === "1";
    btn.disabled = true; btn.textContent = "Saving…";           // the mark is written to the share: a few seconds
    try {
      await api("/api/issues/mark", {method: "POST", body: JSON.stringify({client: cid, key, done})});
      await loadIssues(true); paint();
      I.lastMark = done ? {cid, key} : null;
      toast(done ? "Marked complete. It stays complete until a new workbook arrives." : "Back on the list.", "good", 5000);
    } catch (err) { btn.disabled = false; btn.textContent = done ? "Mark complete" : "Undo"; toast("Couldn't save that: " + err.message, "bad", 6000); }
  }

  function select(id) { I.cur = I.cur === id ? null : id; setTabParams({client: I.cur}); paint(); }
  function move(d) {
    const rows = listed(), i = rows.findIndex(e => e.id === I.cur), next = rows[Math.max(0, Math.min(rows.length - 1, i < 0 ? 0 : i + d))];
    if (!next) return; I.cur = next.id; setTabParams({client: I.cur}); paint();
    const el = $(`[data-iid="${next.id}"]`); if (el) el.scrollIntoView({block: "nearest"});
  }
  const toggleKind = k => { I.kind = I.kind === k ? "" : k; paint(); };

  $("#v-issues").addEventListener("click", e => {
    const t = e.target, k = t.closest("[data-ikind]"); if (k) return toggleKind(k.dataset.ikind);
    if (t.closest("[data-iclear]")) { I.kind = ""; return paint(); }
    const r = t.closest("[data-iid]"); if (r) return select(r.dataset.iid);
    if (t.closest("[data-iall]")) { I.cur = null; setTabParams({client: ""}); return paint(); }
    const m = t.closest("[data-mark]"); if (m) mark(m);
  });
  $("#is-q").addEventListener("input", () => { I.q = $("#is-q").value; paint(); });

  registerTab("issues", {
    async enter(p) {
      I.cur = p && p.client || null; paint();
      try { await loadIssues(); I.error = ""; } catch (e) { I.error = "Couldn't read the data issues: " + e.message; }
      I.loaded = true; paint();
    },
    refresh() { paint(); paintIssueBadge(); },
    keys: [["j  k", "Move through the clients"], ["Enter", "Show one client; again for all"], ["/", "Find a client"], ["1  2  3  4  5  6", "Blockers, decisions, gaps, warnings, codes, completed"], ["Esc", "Back to every client"]],
    key(e) {
      const k = e.key;
      if (k === "j" || k === "ArrowDown") { e.preventDefault(); move(1); }
      else if (k === "k" || k === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (k === "Enter" && I.cur && !document.activeElement.closest("[data-iid]")) select(I.cur);
      else if (k === "/") { e.preventDefault(); $("#is-q").focus(); }
      else if (/^[1-6]$/.test(k)) toggleKind(KINDS[+k - 1][0]);
      else if (k === "Escape") { if (I.cur) { I.cur = null; setTabParams({client: ""}); paint(); } else if (I.kind) { I.kind = ""; paint(); } }
    },
  });
  // The sidebar badge is right from the start, not only after the tab has been opened.
  setTimeout(() => loadIssues().then(() => { I.loaded = true; paintIssueBadge(); if (TAB === "issues") paint(); }).catch(() => {}), 1200);
})();
"""
