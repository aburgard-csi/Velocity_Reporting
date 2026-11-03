"""The Slide Review tab of CSM Sheila, in the Hub layout (Aaron, 2026-10-27, 2026-10-28; moved to the Hub 2026-11-02).

"an evaluation process for all of the decks so the CSM can vote whether to keep or delete a slide, or to add it to an
appendix." Not tied to a client: a program's slide list (ARS, ICS, MRPC, CashPlease, Transaction Intelligence, ARS
Companion), beside a deck open in PowerPoint. **Review** is each slide with Keep / Delete / Appendix, a favourite star
and a comment; **Summary** is the votes and stars for the program's slides in whole, with the CSV export. One file per
vote on the share (slide_votes.py); a changed mind or a star is a newer vote, and a slide is matched by its title.

In the Hub layout voting is one keystroke per slide: 1, 2 or 3 votes and moves to the next slide, S stars, C writes a
comment, N jumps to the next slide not voted on, [ and ] change program. The routes are the same as ever
(`GET /api/votes/programs`, `/program`, `/summary`, `/export`; `POST /api/votes/vote`); this is the page side, moved
here from the old page's slide_review_ui.py (the Hub layout, 2026-11-02).
"""
TAB = "votes"
NAME = "Slide Review"

VIEW = r"""
<div class="vh"><div><h1>Slide Review</h1><p id="sv-sub">Reading the slide list…</p></div>
  <div class="vhr"><span class="seg" role="group" aria-label="View"><button id="sv-rv" aria-pressed="true">Review</button><button id="sv-sm" aria-pressed="false">Summary</button></span></div></div>
<div class="kpis kpis4" id="sv-kpis"></div>
<section class="card">
  <div class="svbar"><div class="svprogs" id="sv-progs" role="group" aria-label="Program"></div><button class="btn" id="sv-export" hidden>Export CSV <kbd>E</kbd></button></div>
  <div class="svmeter" id="sv-meter" aria-hidden="true"></div>
  <div class="svbody" id="sv-body" role="list" aria-live="polite"></div>
</section>
"""

CSS = r"""
/* Slide Review */
.kpis4{grid-template-columns:repeat(4,minmax(0,1fr))}
.svbar{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:12px 14px 6px}
.svprogs{display:flex;flex-wrap:wrap;gap:6px;flex:1}
.pill{display:inline-flex;align-items:center;gap:7px;min-height:34px;padding:0 13px;border-radius:999px;border:1px solid var(--line);background:var(--sheet);font-size:13.5px;font-weight:600}
.pill:hover{border-color:var(--muted)}
.pill[aria-pressed="true"]{background:var(--ink);color:var(--ground);border-color:transparent}
.pill small{font-weight:500;opacity:.75;font-variant-numeric:tabular-nums}
.svmeter{display:flex;height:8px;margin:6px 16px 4px;border-radius:5px;overflow:hidden;background:var(--fill)}
.svmeter i{display:block;height:100%;transition:width .25s ease}
.svmeter .m-keep{background:var(--good)} .svmeter .m-delete{background:var(--bad)} .svmeter .m-appendix{background:var(--muted)}
.svbody{padding:6px 8px 12px}
.vrow{display:grid;grid-template-columns:2.4em 34px minmax(0,1.6fr) auto minmax(150px,1fr);gap:8px 12px;align-items:center;padding:8px 8px;border-radius:12px;border:1px solid transparent}
.vrow:hover{background:var(--glass-hi)}
.vrow[aria-current="true"]{background:var(--fill);box-shadow:inset 0 0 0 1px var(--glass-line)}
.vrow .vn{font:12.5px var(--mono);color:var(--muted);text-align:right}
.vrow .vt b{font-weight:600} .vrow .vt small{display:block;color:var(--muted);font-size:12px}
button.star{font:400 21px/1 "Segoe UI Symbol","Segoe UI",sans-serif;background:none;border:0;padding:2px 6px;color:var(--muted);border-radius:8px}
button.star:hover{color:var(--warn);background:var(--warn-soft)}
button.star[aria-pressed="true"]{color:var(--warn)}
.vseg{display:inline-flex;gap:4px}
button.vb{display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:0 11px;border-radius:10px;border:1px solid var(--line);background:var(--sheet);font-size:13px;font-weight:600}
button.vb:hover{border-color:var(--muted)}
button.vb kbd{font-size:10.5px;padding:2px 5px}
button.vb.keep[aria-pressed="true"]{background:var(--good-soft);color:var(--good);border-color:var(--good)}
button.vb.delete[aria-pressed="true"]{background:var(--bad-soft);color:var(--bad);border-color:var(--bad)}
button.vb.appendix[aria-pressed="true"]{background:var(--fill);color:var(--ink);border-color:var(--ink)}
input.vc{font:inherit;width:100%;min-width:0;padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:var(--sheet);color:var(--ink)}
input.vc:focus-visible{outline:2px solid var(--good);outline-offset:1px}
.vsaved{color:var(--good);font-size:12px;opacity:0;transition:opacity .2s}
.vrow.just .vsaved{opacity:1}
table.vtbl{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
.vtbl th{text-align:right;font-size:11.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);padding:8px 10px;white-space:nowrap}
.vtbl td{text-align:right;padding:8px 10px;border-top:1px solid var(--line);vertical-align:top}
.vtbl th.l,.vtbl td.l{text-align:left}
.vtbl .vsrc{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.vtbl .stars{color:var(--warn);white-space:nowrap}
.vtbl tr:hover td{background:var(--glass-hi)}
.lead{font-weight:700;text-transform:capitalize}
.lead.delete{color:var(--bad)} .lead.keep{color:var(--good)}
.vempty{padding:22px 16px;color:var(--muted)}
@media (max-width:980px){.kpis4{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:820px){.kpis4{display:flex}.vrow{grid-template-columns:2em 34px minmax(0,1fr)}.vrow .vseg,.vrow .vcw{grid-column:1/4}.vrow .vseg{flex-wrap:wrap}.vtbl{display:block;overflow-x:auto}}
"""

JS = r"""
// ------------------------------------------------------------ Slide Review
(function () {
  const V = {view: "review", program: "ARS", filter: "", progs: [], me: "", period: "", d: null, sum: null, cur: -1, loaded: false, error: ""};
  const WORD = {keep: "Keep", delete: "Delete", appendix: "Appendix"}, KEY = {keep: "1", delete: "2", appendix: "3"};

  async function loadProgs() { const {body} = await api("/api/votes/programs"); V.progs = body.programs || []; V.me = body.me || ""; V.period = body.period || ""; }
  async function loadReview() { const {body} = await api("/api/votes/program?program=" + encodeURIComponent(V.program)); V.d = body; V.me = body.me || V.me; }
  async function loadSummary() { const {body} = await api("/api/votes/summary" + (V.filter ? "?program=" + encodeURIComponent(V.filter) : "")); V.sum = body; }

  async function load() {
    V.error = "";
    try { await loadProgs(); if (V.view === "summary") await loadSummary(); else await loadReview(); }
    catch (e) { V.error = "Couldn't read the slide list: " + e.message; }
    V.loaded = true; paint();
  }

  const mineOf = s => s.mine || {};
  const counts = () => { const c = {keep: 0, delete: 0, appendix: 0, star: 0, total: 0}; for (const s of (V.d ? V.d.slides : [])) { const m = mineOf(s); c.total++; if (m.vote) c[m.vote]++; if (m.star) c.star++; } return c; };

  function row(s, i) {
    const m = mineOf(s);
    const b = v => `<button class="vb ${v}" data-vote="${v}" aria-pressed="${m.vote === v}" title="${WORD[v]} (${KEY[v]})">${WORD[v]} <kbd>${KEY[v]}</kbd></button>`;
    return `<div class="vrow" role="listitem" data-i="${i}" data-n="${s.n}" aria-current="${V.cur === i}">
      <span class="vn">${s.n}</span>
      <button class="star" data-star aria-pressed="${!!m.star}" title="Favorite slide (S)" aria-label="Favorite slide">${m.star ? "★" : "☆"}</button>
      <span class="vt"><b>${esc(s.title)}</b>${s.source ? `<small>${esc(s.source)}</small>` : ""}</span>
      <span class="vseg">${b("keep")}${b("delete")}${b("appendix")}<span class="vsaved" aria-hidden="true">✓</span></span>
      <span class="vcw"><input class="vc" type="text" maxlength="500" placeholder="Comment (optional)" value="${esc(m.comment || "")}" aria-label="Comment on slide ${s.n}"></span></div>`;
  }

  function paintProgs(list, key, all) {
    const b = (id, label, n, extra) => `<button class="pill" data-vprog="${esc(id)}" aria-pressed="${V[key] === id}">${esc(label)}${n === undefined ? "" : ` <small>${extra || n}</small>`}</button>`;
    $("#sv-progs").innerHTML = (all ? b("", "All programs") : "") + list.map(p => b(p.id, p.label, p.slides, p.slides !== undefined ? ((p.voted || 0) + "/" + p.slides) : undefined)).join("");
  }

  function paint() {
    $("#sv-rv").setAttribute("aria-pressed", V.view === "review"); $("#sv-sm").setAttribute("aria-pressed", V.view === "summary");
    $("#sv-export").hidden = V.view !== "summary";
    if (!V.loaded) {
      $("#sv-sub").textContent = "Reading the slide list…";
      $("#sv-kpis").innerHTML = ["Voted", "Keep", "Delete", "Appendix"].map(w => `<div class="kpi"><span class="k">${w}</span><span class="v">–</span></div>`).join("");
      $("#sv-body").innerHTML = Array.from({length: 7}, () => `<div class="vrow"><span class="sk" style="height:12px"></span><span class="sk" style="width:20px;height:20px"></span><span class="sk" style="height:14px;width:${50 + Math.random() * 40 | 0}%"></span></div>`).join("");
      return;
    }
    if (V.error) { $("#sv-body").innerHTML = `<p class="vempty err">${esc(V.error)}</p>`; return; }
    if (V.view === "summary") return paintSummary();
    paintProgs(V.progs, "program", false);
    const c = counts(), done = c.keep + c.delete + c.appendix;
    $("#sv-sub").innerHTML = V.d ? `${esc(V.d.label)} · ${esc(V.d.period)} · voting as ${esc(V.d.me)}. Your choices save as you make them and can be changed.` : "";
    $("#sv-kpis").innerHTML = [["Voted", done + " of " + c.total, "ready", "slides"], ["Keep", c.keep, "outputs", "stay in the deck"], ["Delete", c.delete, "blocked", "come out"], ["Appendix", c.appendix, "checking", "move to the appendix"]]
      .map(([w, v, ic, n]) => `<div class="kpi"><span class="k">${si(ic)}${w}</span><span class="v">${v}</span><span class="n">${n}${w === "Voted" && c.star ? " · " + c.star + " starred" : ""}</span></div>`).join("");
    const pc = k => c.total ? (100 * c[k] / c.total) : 0;
    $("#sv-meter").innerHTML = `<i class="m-keep" style="width:${pc("keep")}%"></i><i class="m-delete" style="width:${pc("delete")}%"></i><i class="m-appendix" style="width:${pc("appendix")}%"></i>`;
    $("#sv-meter").hidden = false;
    const slides = V.d ? V.d.slides : [];
    $("#sv-body").innerHTML = slides.length ? slides.map(row).join("") : `<p class="vempty">No ${esc(V.d ? V.d.label : "")} deck in Outputs for ${esc(V.d ? V.d.period : "")} yet.</p>`;
  }

  function paintSummary() {
    paintProgs(V.sum.programs, "filter", true);
    $("#sv-meter").hidden = true;
    const b = V.sum, label = Object.fromEntries(b.programs.map(p => [p.id, p.label]));
    $("#sv-sub").textContent = "One row per slide, for each program as a whole, not by client. The slides with the most Delete votes come first.";
    $("#sv-kpis").innerHTML = [["Votes", b.votes, "ready", "keep, delete or appendix"], ["Stars", b.stars, "attention", "favorites"], ["Voters", b.voters, "outputs", "CSMs who voted"], ["Slides", b.rows.length, "checking", "with a vote or a star"]]
      .map(([w, v, ic, n]) => `<div class="kpi"><span class="k">${si(ic)}${w}</span><span class="v">${v}</span><span class="n">${n}</span></div>`).join("");
    const rows = b.rows.map(r => `<tr><td class="l">${esc(label[r.program] || r.program)}</td><td class="l"><b>${esc(r.title)}</b>${r.comments.length ? `<span class="vsrc">${r.comments.slice(0, 3).map(c => esc(c.voter + (c.vote ? " (" + c.vote + ")" : "") + ": " + c.text)).join("<br>")}${r.comments.length > 3 ? `<br>+${r.comments.length - 3} more in the export` : ""}</span>` : ""}</td>
      <td>${r.keep}</td><td>${r.delete}</td><td>${r.appendix}</td><td class="stars">${r.stars ? "★ " + r.stars : ""}</td><td class="l"><span class="lead ${esc(r.leading)}">${esc(r.leading)}</span></td><td>${r.voters.length}</td></tr>`).join("");
    $("#sv-body").innerHTML = rows ? `<div style="overflow-x:auto"><table class="vtbl"><thead><tr><th class="l">Program</th><th class="l">Slide</th><th>Keep</th><th>Delete</th><th>Appendix</th><th>Stars</th><th class="l">Leading</th><th>Voters</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<p class="vempty">No votes yet. Review a program to add the first.</p>`;
  }

  // Each send carries the slide's whole state, so a star keeps the vote and a vote keeps the star. The page changes at once and puts it back if the share refuses.
  async function send(i, patch) {
    const s = V.d.slides[i], before = s.mine, m = mineOf(s);
    const next = {vote: m.vote || "", star: !!m.star, comment: m.comment || "", ...patch};
    s.mine = next; paintRow(i);
    try {
      await api("/api/votes/vote", {method: "POST", body: JSON.stringify({program: V.program, slide: s.n, title: s.title, vote: next.vote, star: next.star, comment: next.comment})});
      const el = $(`.vrow[data-i="${i}"]`); if (el) { el.classList.add("just"); setTimeout(() => el.classList.remove("just"), 900); }
      loadProgs().then(() => paintProgs(V.progs, "program", false)).catch(() => {});
      return true;
    } catch (e) { s.mine = before; paintRow(i); paintHead(); toast("Couldn't save that: " + e.message, "bad", 6000); return false; }
  }
  function paintRow(i) {
    const el = $(`.vrow[data-i="${i}"]`); if (!el) return paint();
    const had = document.activeElement && document.activeElement.classList && document.activeElement.classList.contains("vc") && el.contains(document.activeElement);
    el.outerHTML = row(V.d.slides[i], i); paintHead();
    if (had) { const c = $(`.vrow[data-i="${i}"] .vc`); if (c) c.focus(); }
  }
  function paintHead() {
    const c = counts(), done = c.keep + c.delete + c.appendix, pc = k => c.total ? (100 * c[k] / c.total) : 0;
    const k = $$("#sv-kpis .kpi"); if (k.length === 4) {
      k[0].querySelector(".v").textContent = done + " of " + c.total; k[0].querySelector(".n").textContent = "slides" + (c.star ? " · " + c.star + " starred" : "");
      k[1].querySelector(".v").textContent = c.keep; k[2].querySelector(".v").textContent = c.delete; k[3].querySelector(".v").textContent = c.appendix;
    }
    $("#sv-meter").innerHTML = `<i class="m-keep" style="width:${pc("keep")}%"></i><i class="m-delete" style="width:${pc("delete")}%"></i><i class="m-appendix" style="width:${pc("appendix")}%"></i>`;
  }

  function setCursor(i, scroll) {
    const slides = V.d ? V.d.slides : []; if (!slides.length) return;
    i = Math.max(0, Math.min(slides.length - 1, i)); const old = V.cur; V.cur = i;
    for (const j of [old, i]) { const el = $(`.vrow[data-i="${j}"]`); if (el) el.setAttribute("aria-current", j === i); }
    const el = $(`.vrow[data-i="${i}"]`); if (el && scroll !== false) el.scrollIntoView({block: "nearest"});
  }
  function nextUnvoted(from) {
    const sl = V.d ? V.d.slides : [];
    for (let k = 1; k <= sl.length; k++) { const j = (from + k) % sl.length; if (!mineOf(sl[j]).vote) return j; }
    return -1;
  }
  async function voteKey(v) {
    if (V.cur < 0 || !V.d) { setCursor(0); if (V.cur < 0) return; }
    const i = V.cur, same = mineOf(V.d.slides[i]).vote === v;
    if (await send(i, {vote: same ? "" : v}) && !same) { const n = nextUnvoted(i); setCursor(n >= 0 ? n : Math.min(i + 1, V.d.slides.length - 1)); }
  }
  function setView(v) { V.view = v; setTabParams({view: v === "summary" ? "summary" : "", program: V.view === "summary" ? V.filter : V.program}); V.loaded = false; paint(); load(); }
  function setProgram(id) {
    if (V.view === "summary") V.filter = id; else { V.program = id; V.cur = -1; }
    setTabParams({view: V.view === "summary" ? "summary" : "", program: id}); V.loaded = false; paint(); load();
  }
  function stepProgram(d) {
    const ids = V.progs.map(p => p.id); if (V.view === "summary" || !ids.length) return;
    setProgram(ids[(Math.max(0, ids.indexOf(V.program)) + d + ids.length) % ids.length]);
  }
  async function exportCsv() {
    const r = await fetch("/api/votes/export" + (V.filter ? "?program=" + encodeURIComponent(V.filter) : ""), {headers: {"X-Token": TOKEN}});
    if (!r.ok) { toast("Couldn't export the votes.", "bad"); return; }
    const url = URL.createObjectURL(await r.blob()), a = document.createElement("a");
    a.href = url; a.download = "slide-votes-" + new Date().toISOString().slice(0, 10) + ".csv"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000); toast("Exported the votes as a CSV in your Downloads folder.", "good", 4000);
  }

  $("#sv-rv").addEventListener("click", () => V.view !== "review" && setView("review"));
  $("#sv-sm").addEventListener("click", () => V.view !== "summary" && setView("summary"));
  $("#sv-export").addEventListener("click", exportCsv);
  $("#v-votes").addEventListener("click", e => {
    const t = e.target, pg = t.closest("[data-vprog]"); if (pg) return setProgram(pg.dataset.vprog);
    const r = t.closest(".vrow[data-i]"); if (!r) return;
    const i = +r.dataset.i; setCursor(i, false);
    if (t.closest("[data-star]")) return send(i, {star: !mineOf(V.d.slides[i]).star});
    const b = t.closest("button.vb"); if (b) { const v = b.dataset.vote; send(i, {vote: mineOf(V.d.slides[i]).vote === v ? "" : v}); }
  });
  // A comment typed after the vote is saved with it again; typed before, it travels with the first click.
  $("#v-votes").addEventListener("change", e => {
    if (!e.target.classList.contains("vc")) return;
    const r = e.target.closest(".vrow"), i = +r.dataset.i, m = mineOf(V.d.slides[i]);
    if (m.vote || m.star || e.target.value) send(i, {comment: e.target.value});
  });
  $("#v-votes").addEventListener("keydown", e => { if (e.target.classList.contains("vc") && e.key === "Enter") e.target.blur(); });

  registerTab("votes", {
    enter(p) {
      if (p && p.view === "summary") { V.view = "summary"; V.filter = p.program || ""; } else { V.view = "review"; if (p && p.program) V.program = p.program; }
      V.loaded = false; paint(); load();
    },
    refresh() {},
    keys: [["1  2  3", "Keep, Delete or Appendix, then the next slide"], ["S", "Star the slide"], ["C", "Write a comment"], ["0", "Clear the vote"], ["j  k", "Move down or up the slides"], ["N", "Jump to the next slide not voted on"],
           ["[  ]", "Previous or next program"], ["W", "Switch between Review and Summary"], ["E", "Export the votes (Summary)"]],
    key(e) {
      const k = e.key;
      if (V.view === "summary") { if (k === "w") { setView("review"); return true; } if (k === "e") { exportCsv(); return true; } return; }
      if (k === "1" || k === "2" || k === "3") voteKey(["keep", "delete", "appendix"][+k - 1]);
      else if (k === "0" || k === "Backspace") { if (V.cur >= 0 && V.d) send(V.cur, {vote: ""}); }
      else if (k === "s") { if (V.cur >= 0 && V.d) send(V.cur, {star: !mineOf(V.d.slides[V.cur]).star}); }
      else if (k === "c") { e.preventDefault(); const c = $(`.vrow[data-i="${V.cur}"] .vc`); if (c) c.focus(); }
      else if (k === "j" || k === "ArrowDown") { e.preventDefault(); setCursor(V.cur + 1); }
      else if (k === "k" || k === "ArrowUp") { e.preventDefault(); setCursor(V.cur < 0 ? 0 : V.cur - 1); }
      else if (k === "n") { const n = nextUnvoted(V.cur < 0 ? -1 : V.cur); if (n >= 0) setCursor(n); else toast("Every slide in this program has your vote.", "good", 3000); }
      else if (k === "[") stepProgram(-1);
      else if (k === "]") stepProgram(1);
      else if (k === "w") setView("summary");
      else if (k === "Escape") { if (V.cur >= 0) { const o = V.cur; V.cur = -1; const el = $(`.vrow[data-i="${o}"]`); if (el) el.setAttribute("aria-current", "false"); } }
      else return;
      return true;       // taken here: the page's own c (compact rows) and the rest do not also act
    },
    palette: () => [...(V.progs || []).map(p => ({t: "Slide Review: " + p.label, s: (p.voted || 0) + "/" + p.slides, run: () => { V.view = "review"; setProgram(p.id); }})),
      {t: V.view === "summary" ? "Slide Review: back to voting" : "Slide Review: summary and export", s: "W", run: () => setView(V.view === "summary" ? "review" : "summary")}],
  });
})();
"""
