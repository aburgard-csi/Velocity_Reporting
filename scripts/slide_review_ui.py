"""
slide_review_ui.py — the Slide Review tab of CSM Sheila: its style and script, spliced into the page.

Kept out of ars_launcher_web.py (Aaron, 2026-10-27) so the tab is one block to read, and so the page's
own text changes in six one-line places (the tab button, the mode list, the client-list click, the
two ends of the page) and nowhere else. `install` raises when an anchor it needs has moved, so a
change to the page that breaks the splice fails the unit suite instead of dropping the tab.

The tab: **Review** (pick a client, a deck of theirs in Outputs, vote on each slide) and **Summary**
(every vote across clients, by slide). The record and the arithmetic are in slide_votes.py.
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
table.vr td.vbtns{white-space:nowrap;text-align:left}
table.vr td.vbtns button{margin-right:6px}
table.vr td.vt{text-align:left;white-space:normal;max-width:520px}
table.vr input.vc{font:inherit;width:100%;min-width:220px;padding:6px 8px;border:1px solid var(--rule);border-radius:6px;background:var(--surface);color:var(--ink)}
table.vr th:nth-child(2),table.vr.rv th{text-align:left}
table.vr td.vn{color:var(--ink3);width:34px}
.vsrc{font-size:12px;color:var(--ink3);margin-top:2px}
.vprog{margin:10px 0 4px;font-size:13px;color:var(--ink2)}
.vdecks{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.vlead{font-weight:700} .vlead.delete{color:var(--orange)}
"""

JS = r"""
// ------------------------------------------------------------------ Slide Review (Aaron, 2026-10-27)
// "an evaluation process for all of the decks so the CSM can vote whether to keep or delete a slide, or to
// add it to an appendix." One file per vote on the share (slide_votes.py); a changed mind is a newer vote.
let VOTE = {view: "review", client: null, deck: null, family: ""};
$("#tab-votes").addEventListener("click", () => setMode("votes"));

function votesPick(id) { VOTE.client = id; VOTE.deck = null; current = id; renderList(); votesView(id); }

function votesTabs() {
  return `<div class="vtabs"><button type="button" class="vt" data-vview="review" aria-pressed="${VOTE.view === "review"}">Review</button>
    <button type="button" class="vt" data-vview="summary" aria-pressed="${VOTE.view === "summary"}">Summary</button></div>`;
}

async function votesView(focus) {
  if (focus) VOTE.client = focus;
  current = VOTE.view === "review" ? VOTE.client : null; renderList();
  if (VOTE.view === "summary") return votesSummary();
  if (!VOTE.client) return votesClients();
  return votesClient(VOTE.client);
}

async function votesClients() {
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2></div>${votesTabs()}<p class="note">Reading the decks in Outputs…</p>`;
  let body;
  try { ({body} = await api("/api/votes/clients")); } catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read the decks: ${esc(e.message)}</p>`; return; }
  if (MODE !== "votes" || VOTE.view !== "review" || VOTE.client) return;
  const rows = (body.clients || []).map(c => `<tr class="pick" data-id="${esc(c.id)}"><td class="l"><b>${esc(c.name || c.id)}</b> <span class="sub">${esc(c.id)}</span></td>
    <td class="l">${c.decks.map(d => esc(d.kind)).join(", ")}</td></tr>`).join("");
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2><span class="sub">${esc(body.period)} · voting as ${esc(body.me)}</span></div>${votesTabs()}
    <p class="note">Vote on each slide of a deck: <b>Keep</b> it, <b>Delete</b> it, or move it to an <b>Appendix</b>. Pick a client below or on the left. Your votes are saved as you click and can be changed.</p>
    ${rows ? `<table class="lm"><thead><tr><th>Client</th><th>Decks in Outputs</th></tr></thead><tbody>${rows}</tbody></table>`
           : `<p class="note">No deck in Outputs for ${esc(body.period)} yet.</p>`}`;
}

async function votesClient(id) {
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2></div>${votesTabs()}<p class="note">Reading the decks…</p>`;
  let list;
  try { ({body: list} = await api("/api/votes/decks?client=" + encodeURIComponent(id))); } catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read the decks: ${esc(e.message)}</p>`; return; }
  if (MODE !== "votes" || VOTE.client !== id) return;
  const decks = list.decks || [];
  if (!decks.length) {
    $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2><span class="sub">${esc(id)}</span></div>${votesTabs()}<p class="note">No deck in Outputs for ${esc(list.period)} for this client yet.</p>`;
    return;
  }
  if (!decks.some(d => d.name === VOTE.deck)) VOTE.deck = decks[0].name;
  let d;
  try { ({body: d} = await api("/api/votes/deck?client=" + encodeURIComponent(id) + "&deck=" + encodeURIComponent(VOTE.deck))); }
  catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read that deck: ${esc(e.message)}</p>`; return; }
  if (MODE !== "votes" || VOTE.client !== id) return;
  const rows = d.slides.map(s => {
    const m = s.mine || {};
    const b = v => `<button type="button" class="vb ${v}" data-vote="${v}" aria-pressed="${m.vote === v}">${v === "keep" ? "Keep" : v === "delete" ? "Delete" : "Appendix"}</button>`;
    return `<tr data-n="${s.n}" data-title="${esc(s.title)}"><td class="vn">${s.n}</td>
      <td class="vt"><b>${esc(s.title)}</b>${s.source ? `<div class="vsrc">${esc(s.source)}</div>` : ""}</td>
      <td class="vbtns">${b("keep")}${b("delete")}${b("appendix")}</td>
      <td><input class="vc" type="text" maxlength="500" placeholder="Comment (optional)" value="${esc(m.comment || "")}"></td></tr>`;
  }).join("");
  const chips = decks.map(x => `<button type="button" class="vt" data-vdeck="${esc(x.name)}" aria-pressed="${x.name === VOTE.deck}" title="${esc(x.name)}">${esc(x.kind)}</button>`).join("");
  $("#main").innerHTML = `<div class="head"><h2>${esc(list.name || id)}</h2><span class="sub">${esc(id)} · ${esc(list.period)} · voting as ${esc(list.me)}</span></div>${votesTabs()}
    <div class="vdecks">${chips}</div>
    <div class="vprog" id="vprog"></div>
    <table class="lm vr rv"><thead><tr><th>#</th><th>Slide</th><th>Your vote</th><th>Comment</th></tr></thead><tbody id="vbody">${rows}</tbody></table>`;
  votesProgress();
}

function votesProgress() {
  const rows = [...document.querySelectorAll("#vbody tr")];
  const done = rows.filter(r => r.querySelector('.vb[aria-pressed="true"]')).length;
  const el = $("#vprog"); if (el) el.textContent = `You have voted on ${done} of ${rows.length} slides in this deck.`;
}

async function votesSend(tr, vote) {
  const comment = tr.querySelector(".vc").value;
  try {
    await api("/api/votes/vote", {method: "POST", body: JSON.stringify({client: VOTE.client, deck: VOTE.deck,
      slide: +tr.dataset.n, title: tr.dataset.title, vote, comment})});
  } catch (e) { alert("Couldn't save that vote: " + e.message); return false; }
  for (const b of tr.querySelectorAll(".vb")) b.setAttribute("aria-pressed", b.dataset.vote === vote);
  votesProgress();
  return true;
}

async function votesSummary() {
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2></div>${votesTabs()}<p class="note">Reading the votes…</p>`;
  let body;
  try { ({body} = await api("/api/votes/summary" + (VOTE.family ? "?family=" + encodeURIComponent(VOTE.family) : ""))); }
  catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read the votes: ${esc(e.message)}</p>`; return; }
  if (MODE !== "votes" || VOTE.view !== "summary") return;
  const fam = [["", "All decks"], ["RPE", "Executive Review"], ["TI", "Transaction Intelligence"], ["COMP", "ARS Companion"]]
    .map(([k, n]) => `<button type="button" class="vt" data-vfamily="${k}" aria-pressed="${VOTE.family === k}">${n}</button>`).join("");
  const rows = body.rows.map(r => `<tr><td class="l">${esc(r.family)}</td><td class="l vt"><b>${esc(r.title)}</b>
      ${r.comments.length ? `<div class="vsrc">${r.comments.slice(0, 3).map(c => esc(c.voter + " (" + c.client + ", " + c.vote + "): " + c.text)).join("<br>")}${r.comments.length > 3 ? `<br>+${r.comments.length - 3} more in the export` : ""}</div>` : ""}</td>
      <td>${r.keep}</td><td>${r.delete}</td><td>${r.appendix}</td>
      <td class="l"><span class="vlead ${esc(r.leading)}">${esc(r.leading)}</span></td><td>${r.clients.length}</td><td>${r.voters.length}</td></tr>`).join("");
  $("#main").innerHTML = `<div class="head"><h2>Slide Review</h2><span class="sub">${body.votes} vote${body.votes === 1 ? "" : "s"} · ${body.voters} voter${body.voters === 1 ? "" : "s"}</span>
      <button type="button" class="vt" id="vexport" style="margin-left:auto">Export CSV</button></div>${votesTabs()}
    <div class="vdecks">${fam}</div>
    <p class="note">One row per slide, across clients. The slides with the most Delete votes come first. A slide is matched by its title, with the client's name and figures taken out.</p>
    ${rows ? `<table class="lm vr"><thead><tr><th>Deck</th><th>Slide</th><th>Keep</th><th>Delete</th><th>Appendix</th><th>Leading</th><th>Clients</th><th>Voters</th></tr></thead><tbody>${rows}</tbody></table>`
           : `<p class="note">No votes yet.</p>`}`;
}

async function votesExport() {
  const r = await fetch("/api/votes/export" + (VOTE.family ? "?family=" + encodeURIComponent(VOTE.family) : ""), {headers: {"X-Token": TOKEN}});
  if (!r.ok) { alert("Couldn't export the votes."); return; }
  const url = URL.createObjectURL(await r.blob()), a = document.createElement("a");
  a.href = url; a.download = "slide-votes-" + new Date().toISOString().slice(0, 10) + ".csv"; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

$("#main").addEventListener("click", async e => {
  if (MODE !== "votes") return;
  const t = e.target;
  const pick = t.closest("tr.pick");
  if (pick && pick.dataset.id) return votesPick(pick.dataset.id);
  const view = t.closest("[data-vview]"); if (view) { VOTE.view = view.dataset.vview; return votesView(); }
  const dk = t.closest("[data-vdeck]"); if (dk) { VOTE.deck = dk.dataset.vdeck; return votesClient(VOTE.client); }
  const fm = t.closest("[data-vfamily]"); if (fm) { VOTE.family = fm.dataset.vfamily; return votesSummary(); }
  if (t.closest("#vexport")) return votesExport();
  const b = t.closest("button.vb"); if (b) { const tr = b.closest("tr"); if (tr) await votesSend(tr, b.dataset.vote); }
});
// A comment typed after the vote is saved with it again; typed before, it travels with the first click.
$("#main").addEventListener("change", async e => {
  if (MODE !== "votes" || !e.target.classList.contains("vc")) return;
  const tr = e.target.closest("tr"), on = tr && tr.querySelector('.vb[aria-pressed="true"]');
  if (on) await votesSend(tr, on.dataset.vote);
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
                'else if (m === "votes") votesView(focus);\n  else if (m === "reported") reportedView();')
    page = swap(page, 'MODE === "issues" ? issuesView : select)(b.dataset.id)',
                'MODE === "issues" ? issuesView : MODE === "votes" ? votesPick : select)(b.dataset.id)')
    page = swap(page, "</style>", CSS + "</style>")
    i = page.rindex("</script>")
    return page[:i] + JS + page[i:]
