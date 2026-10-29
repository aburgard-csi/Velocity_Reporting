"""
slide_review_ui.py — the Slide Review tab of CSM Sheila: its style and script, spliced into the page.

Kept out of ars_launcher_web.py (Aaron, 2026-10-27) so the tab is one block to read, and so the page's
own text changes in six one-line places (the tab button, the mode list, the client-list click, the
two ends of the page) and nowhere else. `install` raises when an anchor it needs has moved, so a
change to the page that breaks the splice fails the unit suite instead of dropping the tab.

The tab is not tied to a client (Aaron, 2026-10-28): **Review** is a program's slide list (ARS, ICS, MRPC,
CashPlease, Transaction Intelligence, ARS Companion) to elect on with a deck open beside Sheila, each slide
with Keep / Delete / Appendix, a favourite star and a comment; **Summary** is the votes and stars for the
program's slides in whole. The record and the arithmetic are in slide_votes.py.
"""

CSS = r"""
/* Slide Review (Aaron, 2026-10-27). The vote buttons are the action buttons' smaller sibling: the same
   toned-down highlight and edge, the colour only when chosen. */
.vtabs{display:flex;gap:8px;margin:6px 0 12px}
button.vb,button.vt{font:600 13px/1 "Segoe UI",Arial,sans-serif;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:8px;padding:7px 12px;cursor:pointer;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.16),0 1px 2px rgba(0,0,0,.12);transition:box-shadow .12s ease,transform .12s ease,filter .12s ease}
button.vb:hover,button.vt:hover{filter:brightness(.97)}
button.vb:active{transform:translateY(1px)}
button.vb[aria-pressed=true],button.vt[aria-pressed=true]{background:var(--navy);color:#fff;border-color:transparent;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.16),inset 0 -1px 0 rgba(0,0,0,.16),0 1px 2px rgba(0,0,0,.22),0 2px 6px rgba(0,39,76,.16)}
button.vb.delete[aria-pressed=true]{background:var(--orange);box-shadow:inset 0 1px 0 rgba(255,255,255,.16),inset 0 -1px 0 rgba(0,0,0,.16),0 1px 2px rgba(0,0,0,.22),0 2px 6px rgba(244,122,41,.18)}
button.vb.appendix[aria-pressed=true]{background:#1f7a8c;box-shadow:inset 0 1px 0 rgba(255,255,255,.16),inset 0 -1px 0 rgba(0,0,0,.16),0 1px 2px rgba(0,0,0,.22),0 2px 6px rgba(31,122,140,.18)}
button.star{font:400 20px/1 "Segoe UI Symbol","Segoe UI",Arial,sans-serif;background:none;border:0;padding:2px 6px;cursor:pointer;color:var(--ink3);border-radius:6px}
button.star:hover{color:#d99a00;background:rgba(217,154,0,.10)}
button.star[aria-pressed=true]{color:#d99a00}
table.vr td.vstar{width:34px;text-align:center}
table.vr td.vbtns{white-space:nowrap;text-align:left}
table.vr td.vbtns button{margin-right:6px}
table.vr td.vt{text-align:left;white-space:normal;max-width:520px}
table.vr input.vc{font:inherit;width:100%;min-width:180px;padding:6px 8px;border:1px solid var(--rule);border-radius:6px;background:var(--surface);color:var(--ink)}
table.vr th:nth-child(2),table.vr.rv th{text-align:left}
table.vr td.vn{color:var(--ink3);width:34px}
.vsrc{font-size:12px;color:var(--ink3);margin-top:2px}
.vprog{margin:10px 0 4px;font-size:13px;color:var(--ink2)}
.vdecks{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.vlead{font-weight:700} .vlead.delete{color:var(--orange)}
.vstars{color:#d99a00;white-space:nowrap}
"""

JS = r"""
// ------------------------------------------------------------------ Slide Review (Aaron, 2026-10-27, 2026-10-28)
// "an evaluation process for all of the decks so the CSM can vote whether to keep or delete a slide, or to
// add it to an appendix." Not tied to a client: a program's slide list, beside a deck open in PowerPoint.
// One file per vote on the share (slide_votes.py); a changed mind or a star is a newer vote.
let VOTE = {view: "review", program: "ARS", filter: ""};
$("#tab-votes").addEventListener("click", () => setMode("votes"));

function votesPick(id) { votesView(); }

function votesTabs() {
  return `<div class="vtabs"><button type="button" class="vt" data-vview="review" aria-pressed="${VOTE.view === "review"}">Review</button>
    <button type="button" class="vt" data-vview="summary" aria-pressed="${VOTE.view === "summary"}">Summary</button></div>`;
}

function votesPrograms(list, key, all) {
  const b = (id, label, n) => `<button type="button" class="vt" data-vprogram="${esc(id)}" aria-pressed="${VOTE[key] === id}">${esc(label)}${n === undefined ? "" : ` <span class="sub">${n}</span>`}</button>`;
  return `<div class="vdecks">${all ? b("", "All programs") : ""}${list.map(p => b(p.id, p.label, p.slides)).join("")}</div>`;
}

async function votesView() {
  current = null; renderList();
  if (VOTE.view === "summary") return votesSummary();
  return votesProgram();
}

async function votesProgram() {
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2></div>${votesTabs()}<p class="note">Reading the slide list…</p>`;
  let progs, d;
  try {
    ({body: progs} = await api("/api/votes/programs"));
    ({body: d} = await api("/api/votes/program?program=" + encodeURIComponent(VOTE.program)));
  } catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read the decks: ${esc(e.message)}</p>`; return; }
  if (MODE !== "votes" || VOTE.view !== "review") return;
  const rows = d.slides.map(s => {
    const m = s.mine || {};
    const b = v => `<button type="button" class="vb ${v}" data-vote="${v}" aria-pressed="${m.vote === v}">${v === "keep" ? "Keep" : v === "delete" ? "Delete" : "Appendix"}</button>`;
    return `<tr data-n="${s.n}" data-title="${esc(s.title)}"><td class="vn">${s.n}</td>
      <td class="vstar"><button type="button" class="star" aria-pressed="${!!m.star}" title="Favorite slide" aria-label="Favorite slide">${m.star ? "★" : "☆"}</button></td>
      <td class="vt"><b>${esc(s.title)}</b>${s.source ? `<div class="vsrc">${esc(s.source)}</div>` : ""}</td>
      <td class="vbtns">${b("keep")}${b("delete")}${b("appendix")}</td>
      <td><input class="vc" type="text" maxlength="500" placeholder="Comment (optional)" value="${esc(m.comment || "")}"></td></tr>`;
  }).join("");
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2><span class="sub">${esc(d.label)} · ${esc(d.period)} · voting as ${esc(d.me)}</span></div>${votesTabs()}
    <p class="note">Open a deck beside Sheila, then <b>Keep</b>, <b>Delete</b> or move to an <b>Appendix</b> each slide of the program, and star your favorites. Not tied to a client; your choices save as you click and can be changed. The slide list is the build itself — the templates and the slides each builder adds — the same for every client, so nothing is read from a deck.</p>
    ${votesPrograms(progs.programs, "program", false)}
    <div class="vprog" id="vprog"></div>
    ${rows ? `<table class="lm vr rv"><thead><tr><th>#</th><th></th><th>Slide</th><th>Your vote</th><th>Comment</th></tr></thead><tbody id="vbody">${rows}</tbody></table>`
           : `<p class="note">No ${esc(d.label)} deck in Outputs for ${esc(d.period)} yet.</p>`}`;
  votesProgress();
}

function votesProgress() {
  const rows = [...document.querySelectorAll("#vbody tr")];
  const done = rows.filter(r => r.querySelector('.vb[aria-pressed="true"]')).length;
  const stars = rows.filter(r => r.querySelector('.star[aria-pressed="true"]')).length;
  const el = $("#vprog"); if (el) el.textContent = `You have voted on ${done} of ${rows.length} slides` + (stars ? ` and starred ${stars}.` : ".");
}

// Each send carries the slide's whole state, so a star keeps the vote and a vote keeps the star.
async function votesSend(tr, patch) {
  const on = tr.querySelector('.vb[aria-pressed="true"]'), starred = tr.querySelector('.star').getAttribute("aria-pressed") === "true";
  const state = Object.assign({vote: on ? on.dataset.vote : "", star: starred, comment: tr.querySelector(".vc").value}, patch);
  try {
    await api("/api/votes/vote", {method: "POST", body: JSON.stringify({program: VOTE.program,
      slide: +tr.dataset.n, title: tr.dataset.title, vote: state.vote, star: state.star, comment: state.comment})});
  } catch (e) { alert("Couldn't save that: " + e.message); return false; }
  for (const b of tr.querySelectorAll(".vb")) b.setAttribute("aria-pressed", b.dataset.vote === state.vote);
  const st = tr.querySelector(".star"); st.setAttribute("aria-pressed", state.star); st.textContent = state.star ? "★" : "☆";
  votesProgress();
  return true;
}

async function votesSummary() {
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2></div>${votesTabs()}<p class="note">Reading the votes…</p>`;
  let body;
  try { ({body} = await api("/api/votes/summary" + (VOTE.filter ? "?program=" + encodeURIComponent(VOTE.filter) : ""))); }
  catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read the votes: ${esc(e.message)}</p>`; return; }
  if (MODE !== "votes" || VOTE.view !== "summary") return;
  const label = Object.fromEntries(body.programs.map(p => [p.id, p.label]));
  const rows = body.rows.map(r => `<tr><td class="l">${esc(label[r.program] || r.program)}</td><td class="l vt"><b>${esc(r.title)}</b>
      ${r.comments.length ? `<div class="vsrc">${r.comments.slice(0, 3).map(c => esc(c.voter + (c.vote ? " (" + c.vote + ")" : "") + ": " + c.text)).join("<br>")}${r.comments.length > 3 ? `<br>+${r.comments.length - 3} more in the export` : ""}</div>` : ""}</td>
      <td>${r.keep}</td><td>${r.delete}</td><td>${r.appendix}</td><td class="vstars">${r.stars ? "★ " + r.stars : ""}</td>
      <td class="l"><span class="vlead ${esc(r.leading)}">${esc(r.leading)}</span></td><td>${r.voters.length}</td></tr>`).join("");
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2><span class="sub">${body.votes} vote${body.votes === 1 ? "" : "s"} · ${body.stars} star${body.stars === 1 ? "" : "s"} · ${body.voters} voter${body.voters === 1 ? "" : "s"}</span>
      <button type="button" class="vt" id="vexport" style="margin-left:auto">Export CSV</button></div>${votesTabs()}
    ${votesPrograms(body.programs, "filter", true)}
    <p class="note">One row per slide, for each program as a whole — not by client. The slides with the most Delete votes come first. A slide is matched by its title, with any client's name and figures taken out.</p>
    ${rows ? `<table class="lm vr"><thead><tr><th>Program</th><th>Slide</th><th>Keep</th><th>Delete</th><th>Appendix</th><th>Stars</th><th>Leading</th><th>Voters</th></tr></thead><tbody>${rows}</tbody></table>`
           : `<p class="note">No votes yet.</p>`}`;
}

async function votesExport() {
  const r = await fetch("/api/votes/export" + (VOTE.filter ? "?program=" + encodeURIComponent(VOTE.filter) : ""), {headers: {"X-Token": TOKEN}});
  if (!r.ok) { alert("Couldn't export the votes."); return; }
  const url = URL.createObjectURL(await r.blob()), a = document.createElement("a");
  a.href = url; a.download = "slide-votes-" + new Date().toISOString().slice(0, 10) + ".csv"; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

$("#main").addEventListener("click", async e => {
  if (MODE !== "votes") return;
  const t = e.target;
  const view = t.closest("[data-vview]"); if (view) { VOTE.view = view.dataset.vview; return votesView(); }
  const pg = t.closest("[data-vprogram]");
  if (pg) { if (VOTE.view === "summary") { VOTE.filter = pg.dataset.vprogram; return votesSummary(); } VOTE.program = pg.dataset.vprogram; return votesProgram(); }
  if (t.closest("#vexport")) return votesExport();
  const tr = t.closest("tr[data-n]"); if (!tr) return;
  const st = t.closest("button.star");
  if (st) return void await votesSend(tr, {star: st.getAttribute("aria-pressed") !== "true"});
  const b = t.closest("button.vb"); if (b) await votesSend(tr, {vote: b.dataset.vote});
});
// A comment typed after the vote is saved with it again; typed before, it travels with the first click.
$("#main").addEventListener("change", async e => {
  if (MODE !== "votes" || !e.target.classList.contains("vc")) return;
  const tr = e.target.closest("tr");
  if (tr && (tr.querySelector('.vb[aria-pressed="true"]') || tr.querySelector('.star[aria-pressed="true"]'))) await votesSend(tr, {});
});
"""

TAB = '<button role="tab" id="tab-votes" aria-selected="false">Slide Review</button>'


def install(page):
    """`page` with the Slide Review tab spliced in. Raises when an anchor the splice needs has moved."""
    def swap(text, old, new, count=1):
        if text.count(old) < 1:
            raise RuntimeError("Slide Review could not be added to the page: anchor not found: " + old[:70])
        return text.replace(old, new, count)

    page = swap(page, '<button role="tab" id="tab-reported"', TAB + '<button role="tab" id="tab-reported"')
    page = swap(page, 'm === "lift" || m === "issues" || m === "reported");',
                'm === "lift" || m === "issues" || m === "reported" || m === "votes");')
    page = swap(page, 'for (const t of ["decks", "lift", "issues", "reported"])',
                'for (const t of ["decks", "lift", "issues", "reported", "votes"])')
    page = swap(page, 'else if (m === "reported") reportedView();',
                'else if (m === "votes") votesView();\n  else if (m === "reported") reportedView();')
    page = swap(page, 'MODE === "issues" ? issuesView : select)(b.dataset.id)',
                'MODE === "issues" ? issuesView : MODE === "votes" ? votesPick : select)(b.dataset.id)')
    page = swap(page, "</style>", CSS + "</style>")
    i = page.rindex("</script>")
    return page[:i] + JS + page[i:]
