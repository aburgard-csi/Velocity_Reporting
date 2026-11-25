"""The ILS Decks tab of CSM Sheila, in the Hub layout (Aaron, 2026-11-25: "We'll need to view ILS only clients in Sheila
now. On the left side bar change Decks to RPE Decks, add another entry for ILS Decks").

One row per ILS client the CSM can act on: the clients on the ILS analysts' review schedule snapshot, the clients with
ILS pre-go-live or kickoff inputs landed, and the clients.md ILS roster (a CSM's own ILS clients, even with nothing
scheduled). Each row has the client's name and number, its programs (the RPE dots, and whether it is on ILS alone), the
review status, the review date and status from the schedule, the newest data pull, and which other ILS cards apply (the
pre-go-live or kickoff inputs landed). The KPI tiles filter the list, as the RPE Decks tiles do, and the CSM filter is
the one every tab shares.

Every figure is worked out in the background list refresh (`ars_launcher_web.ils_clients`, from the schedule snapshot,
pulls.json and the landed folders in Inputs, never the analysts' shares) and served with the client list as each
client's `ils` block; the page's `ilsKind` maps it to a state. A client whose ILS state could not be read is "Not
checked", never Ready.

The sidebar badge counts the CSM's ILS reviews that are **Ready to build**: on the schedule, this review's data pull
landed and sound, and no deck for this review in Outputs yet (`paintIlsBadge` in sheila_hub.py).

A row opens the client's ILS page: the one client page (`#detail`, whose listeners the ILS cards are bound to) moved
into this tab and drawn ILS only (sheila_hub.renderIlsDetail; Aaron, 2026-11-25: "fix the ILS client page clutter"): the
ILS Review, Pre-go-live and Kickoff cards, all shown, and none of the RPE page's cards, links or Live Review. A client on
both lists gets one line opening its RPE page, and the RPE page one line opening this. Back, Close and Esc return to
this list, and `#ils&client=<id>` opens it from a bookmark.
"""
TAB = "ils"
NAME = "ILS Decks"

VIEW = r"""
<div class="vh"><div><h1>ILS Decks</h1><p id="il-sub">Loading the ILS clients…</p></div><div class="vhr" id="il-csm"></div></div>
<div class="kpis" id="il-kpis" role="group" aria-label="Filter by review status"></div>
<section class="card v-table-card" id="il-listcard" aria-label="ILS clients">
  <div class="lhead">
    <label class="find"><svg viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/></svg><input id="il-q" type="search" placeholder="Name or number" autocomplete="off" aria-label="Find an ILS client"><kbd>/</kbd></label>
    <div class="filt" id="il-filt"></div>
  </div>
  <div class="v-scroll"><table class="v-table il-table">
    <thead><tr><th>Client</th><th class="il-opt">Programs</th><th>Review</th><th>Review date</th><th class="v-num il-opt">Data pull</th><th class="il-opt">Other ILS cards</th></tr></thead>
    <tbody id="il-rows"></tbody>
  </table></div>
  <p class="il-note">From the analysts' review schedule and the data pulls the morning landing step copied into Inputs, and the ILS roster in clients.md. Open a client for its ILS cards.</p>
</section>
<div id="il-host"></div>
"""

CSS = r"""
/* ILS Decks: the Mission Control table, one row per ILS client; a row opens the client page here. */
.vhr{display:flex;gap:8px;align-items:center}
.il-table tbody tr{cursor:pointer}
.il-table tbody tr[aria-current="true"] td{background:var(--fill)}
.il-table tbody tr:focus-visible{outline:2px solid var(--good);outline-offset:-2px}
.il-table .pd{vertical-align:middle}
.il-pill{display:inline-flex;align-items:center;font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--fill);color:var(--muted);white-space:nowrap;margin:0 4px 4px 0}
.il-note{margin:0;padding:0 24px 16px;font-size:12.5px;color:var(--muted)}
#il-listcard .lhead{padding:12px 16px 8px;border-bottom:0}
.xlist{padding:0 2px}
@media (max-width:720px){.il-table .il-opt{display:none}.il-table th,.il-table td{padding-inline:10px}.il-note{padding-inline:16px}}
"""

JS = r"""
// ------------------------------------------------------------ ILS Decks (Aaron, 2026-11-25)
(function () {
  const IL = {kind: "", q: "", cursor: null, open: null, wait: null};
  // Most to do first: ready, then the reviews waiting on data or with a problem, then the done and the unscheduled.
  const RANK = {ready: 0, waiting: 1, problem: 2, unchecked: 3, outputs: 4, none: 5};
  const ICON = {ready: "ready", outputs: "outputs", waiting: "blocked", problem: "blocked", none: "idle"};
  const CARDS = {pgl: "Pre-go-live", kickoff: "Kickoff"};
  const day = v => { const s = String(v || ""); return /^\d{8}$/.test(s) ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}` : s; };

  function base() { const csm = $("#csm").value; return CLIENTS.filter(c => c.ils && (!csm || c.csm === csm)); }
  function listed() {
    const q = IL.q.trim().toLowerCase();
    return base().filter(c => (!q || c.id.includes(q) || (c.name || "").toLowerCase().includes(q)) && (!IL.kind || ilsKind(c).k === IL.kind))
      .sort((a, b) => (RANK[ilsKind(a).k] - RANK[ilsKind(b).k]) || String(a.ils.review_date || "9999").localeCompare(String(b.ils.review_date || "9999"))
        || (a.name || "").localeCompare(b.name || ""));
  }

  function row(c) {
    const k = ilsKind(c), s = c.ils || {};
    const cards = (s.landed || []).map(x => `<span class="il-pill">${esc(CARDS[x] || x)}</span>`).join("") || `<span class="v-meta">none</span>`;
    return `<tr data-ilid="${esc(c.id)}" tabindex="0" aria-current="${IL.cursor === c.id}">
      <td><span class="v-cell-main">${esc(c.name || c.id)}</span><span class="v-cell-sub">${esc(c.id)} · ${esc(c.csm)}</span></td>
      <td class="il-opt">${pdots(c)}<span class="v-cell-sub">${c.ils_only ? "ILS only" : "RPE and ILS"}${s.roster ? " · ILS roster" : ""}</span></td>
      <td><span class="chip k-${k.cls}" title="${esc(k.label)}">${esc(k.short || k.label)}</span></td>
      <td class="v-meta">${s.review_date ? esc(day(s.review_date)) : "none"}${s.review_status ? `<span class="v-cell-sub">${esc(s.review_status)}</span>` : ""}</td>
      <td class="v-num v-meta il-opt">${s.pull ? esc(day(s.pull)) : "none"}</td>
      <td class="il-opt">${cards}</td></tr>`;
  }

  function paintHead() {
    const box = $("#il-csm"); if (box) box.innerHTML = IL.open ? "" : csmPick();
    if (IL.open) {
      const c = CLIENTS.find(x => x.id === IL.open) || {id: IL.open};
      $("#il-sub").innerHTML = `<button class="link" data-ilback>← All ILS clients</button> · ${esc(c.name || c.id)}`;
    }
  }

  function paint() {
    paintHead();
    if (IL.open) return;
    const all = base();
    if (!LOADED) {
      $("#il-kpis").innerHTML = ILS_KINDS.map(([k, w]) => `<div class="kpi"><span class="k">${si(ICON[k])}${esc(w)}</span><span class="v">–</span></div>`).join("");
      $("#il-filt").textContent = "Loading clients…";
      $("#il-rows").innerHTML = Array.from({length: 6}, () => `<tr><td colspan="6"><span class="sk" style="width:${40 + Math.random() * 50 | 0}%;height:14px"></span></td></tr>`).join("");
      return;
    }
    const n = {}; for (const [k] of ILS_KINDS) n[k] = 0;
    let unchecked = 0;
    for (const c of all) { const k = ilsKind(c).k; if (n[k] !== undefined) n[k]++; else unchecked++; }
    $("#il-kpis").innerHTML = ILS_KINDS.map(([k, w, sub]) => `<button class="kpi" data-ilkind="${k}" aria-pressed="${IL.kind === k}" title="Show only: ${esc(w)}">
      <span class="k">${si(ICON[k])}${esc(w)}</span><span class="v">${n[k]}</span><span class="n">${esc(sub)}</span></button>`).join("");
    $("#il-sub").innerHTML = `${all.length} ILS client${all.length === 1 ? "" : "s"}${unchecked ? ` · ${unchecked} not checked (the share could not be read)` : ""} · list as of ${esc(ago(AGE))}`;
    const rows = listed();
    $("#il-filt").innerHTML = IL.kind ? `Showing <b>${esc(ILS_KINDS.find(x => x[0] === IL.kind)[1])}</b> <button class="x" data-ilclear>Clear ✕</button>` : `${rows.length} client${rows.length === 1 ? "" : "s"}`;
    $("#il-rows").innerHTML = rows.length ? rows.map(row).join("")
      : `<tr><td class="v-empty" colspan="6">${all.length ? "No ILS client matches." : "No ILS clients for this CSM: none on the review schedule, none with pre-go-live or kickoff inputs landed, none on the ILS roster."}</td></tr>`;
  }

  // The client page is the one #detail, moved here while a client is open and back to RPE Decks when it closes.
  function host(on) {
    const d = $("#detail");
    if (on) $("#il-host").appendChild(d); else if (d.parentElement !== $("#split")) $("#split").appendChild(d);
    $("#il-kpis").hidden = on; $("#il-listcard").hidden = on;
  }
  function open(id) {
    clearInterval(IL.wait);
    // From a bookmark the list may not be here yet, and the page needs it to know a client is on ILS alone.
    if (!LOADED) { IL.wait = setInterval(() => { if (LOADED) { clearInterval(IL.wait); open(id); } }, 200); return; }
    IL.open = id; IL.cursor = id; setTabParams({client: id});
    host(true); paintHead(); openClient(id); window.scrollTo(0, 0);
  }
  function back() {
    IL.open = null; host(false); setTabParams({client: ""}); paint();
    const el = IL.cursor && $(`#il-rows tr[data-ilid="${IL.cursor}"]`); if (el) el.scrollIntoView({block: "nearest"});
  }
  function move(d) {
    const rows = listed(), i = rows.findIndex(c => c.id === IL.cursor), next = rows[Math.max(0, Math.min(rows.length - 1, i < 0 ? 0 : i + d))];
    if (!next) return; IL.cursor = next.id; paint();
    const el = $(`#il-rows tr[data-ilid="${next.id}"]`); if (el) el.scrollIntoView({block: "nearest"});
  }
  const toggleKind = k => { IL.kind = IL.kind === k ? "" : k; paint(); };

  $("#v-ils").addEventListener("click", e => {
    const t = e.target;
    if (t.closest("#detail")) return;
    const k = t.closest("[data-ilkind]"); if (k) return toggleKind(k.dataset.ilkind);
    if (t.closest("[data-ilclear]")) { IL.kind = ""; return paint(); }
    if (t.closest("[data-ilback]")) return closeClient();
    const r = t.closest("tr[data-ilid]"); if (r) open(r.dataset.ilid);
  });
  $("#il-q").addEventListener("input", () => { IL.q = $("#il-q").value; paint(); });

  registerTab("ils", {
    enter(p) {
      if (p && p.client) return open(p.client);
      if (IL.open) return closeClient();        // the sidebar link again: back to the list
      paint();
    },
    leave() { clearInterval(IL.wait); if (IL.open) { IL.open = null; host(false); } },
    closed() { if (IL.open) back(); },
    refresh() { paint(); },
    keys: [["j  k", "Move through the clients"], ["Enter", "Open the client's page"], ["/", "Find a client"],
      ["1  2  3  4  5", "Ready, In Outputs, Waiting for data, Data problem, No review scheduled"], ["R", "Check the open client again"],
      ["Esc", "Back to the ILS list, or clear the filter"]],
    palette() {
      return ILS_KINDS.map(([k, w]) => ({t: "Show ILS clients: " + w, s: "", run: () => { if (IL.open) closeClient(); IL.kind = k; paint(); }}));
    },
    key(e) {
      const k = e.key;
      if (k === "Escape") { if (IL.open) closeClient(); else if (IL.kind) { IL.kind = ""; paint(); } return true; }
      if (IL.open) {
        if (k === "r" && CUR) { openClient(CUR, true); return true; }
        if (k === "b" && CUR) { firstBuild(); return true; }
        return false;
      }
      if (k === "j" || k === "ArrowDown") { e.preventDefault(); move(1); return true; }
      if (k === "k" || k === "ArrowUp") { e.preventDefault(); move(-1); return true; }
      if (k === "/") { e.preventDefault(); $("#il-q").focus(); return true; }
      if (k === "Enter") {
        const tr = document.activeElement && document.activeElement.closest && document.activeElement.closest("tr[data-ilid]");
        const id = tr ? tr.dataset.ilid : IL.cursor; if (id) { open(id); return true; }
        return false;
      }
      if (/^[1-5]$/.test(k)) { toggleKind(ILS_KINDS[+k - 1][0]); return true; }
      return false;
    },
  });
})();
"""
