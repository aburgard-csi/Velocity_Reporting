"""The Live Review card on a client's page in CSM Sheila (Aaron, 2026-11-06; prototype).

Live Review presents a client's review from a web page: the packs the deck build left, drawn in the browser, with
the "how you compare" screens (a peer is a dot whose hover gives its client number and nothing else). The card sits
under the Executive Review, Transaction Intelligence, ARS Companion and ILS cards. It is not a build and not a deck:
**Open** starts the page's server inside Sheila (live_review_ui.py), builds the page's data in the background (the
share is slow, so this can take minutes) and opens it in the CSM's browser; **Stop** ends it.

It is deliberately not drawn through `presentation()`: that card is built around Build buttons and decks in Outputs.
This one has an Open button, a Stop button, a readiness list and a link. sheila_hub.py draws `<div id="livecard">` on
the client page and calls `liveCard()` after drawing it. The routes and the server are live_review_ui.py.
"""
TAB = None
NAME = "Live Review"
VIEW = ""

CSS = r"""
/* Live Review card: the shared .pc card, plus the prototype tag and the page's address. */
.protochip{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);font:600 11.5px/1.5 var(--body);color:var(--muted);letter-spacing:.02em}
.livelink{font-family:var(--mono);font-size:12.5px;color:var(--muted);word-break:break-all}
ul.livepr{margin:6px 0 0 18px;padding:0;font-size:13px;color:var(--muted)}
"""

JS = r"""
// ------------------------------------------------------------------ Live Review card (Aaron, 2026-11-06)
// Open starts the page's server inside Sheila and opens it in this browser's PC; the build of the page's data
// runs in the background, so the card polls /api/live/state until it is ready or failed. Stop ends it.
let LIVE = {cid: null, doc: null, timer: null};

function liveCard() {
  const box = $("#livecard"); if (!box) return;
  const s = S; if (!s) return;
  if (LIVE.cid !== s.client) { LIVE.cid = s.client; LIVE.doc = null; clearTimeout(LIVE.timer); liveFetch(s.client); }
  liveDraw();
}

async function liveFetch(cid) {
  clearTimeout(LIVE.timer);
  let doc;
  try { ({body: doc} = await api("/api/live/state?client=" + encodeURIComponent(cid))); } catch (e) { return; }
  if (LIVE.cid !== cid || CUR !== cid) return;
  LIVE.doc = doc; liveDraw();
  if (doc && doc.state === "starting") LIVE.timer = setTimeout(() => liveFetch(cid), 3000);
}

function liveDraw() {
  const box = $("#livecard"), s = S; if (!box || !s) return;
  const live = s.live || {state: "stop", checks: []}, d = LIVE.doc || {state: "idle"};
  const li = r => `<li><span class="t ck-${r.level === "ok" ? "ok" : r.level === "ask" ? "warn" : "stop"}">${ICONS[r.level === "ok" ? "ok" : r.level === "ask" ? "warn" : "stop"].replace('<svg', '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"')}</span><span>${esc(r.text)}</span></li>`;
  const chip = d.state === "ready" ? `<span class="chip k-outputs">${si("outputs")}Running</span>`
    : d.state === "starting" ? `<span class="chip k-ready">${si("ready")}Building the page</span>`
    : d.state === "failed" ? `<span class="chip k-blocked">${si("blocked")}Could not open</span>`
    : live.state === "stop" ? `<span class="chip k-blocked">${si("blocked")}Nothing to show yet</span>`
    : `<span class="chip k-ready">${si("ready")}Ready to open</span>`;
  let btns = "", fact = "";
  if (d.state === "ready") {
    btns = `<button class="btn primary" data-live="open">Open again</button><button class="btn" data-live="stop">Stop</button>`;
    fact = `Running for ${esc(d.period)}. It opens in your browser; if it did not, use this address (it works on this PC only): <a class="livelink" href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.url)}</a>`;
  } else if (d.state === "starting") {
    btns = `<button class="btn primary" disabled>Building…</button><button class="btn" data-live="stop">Cancel</button>`;
    const m = Math.floor((d.seconds || 0) / 60), sec = String((d.seconds || 0) % 60).padStart(2, "0");
    fact = `Reading each program's data from the share (${m}:${sec}). This can take a few minutes on the first open; the page opens by itself when it is ready.`;
  } else if (d.state === "failed") {
    btns = live.state === "stop" ? `<button class="btn" data-act="recheck">Check again <kbd>R</kbd></button>` : `<button class="btn primary" data-live="open">Try again</button>`;
    fact = `<span class="err">${esc(d.error || "The page could not be built.")}</span>` +
      ((d.problems || []).length ? `<ul class="livepr">${d.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul>` : "");
  } else {
    btns = live.state === "stop" ? `<button class="btn" data-act="recheck">Check again <kbd>R</kbd></button>` : `<button class="btn primary" data-live="open">Open Live Review</button>`;
  }
  const checks = (live.checks || []);
  box.innerHTML = `<section class="pc${live.state === "stop" && d.state === "idle" ? " stopc" : ""}" id="pc-live">
    <div class="pch"><h3>Live Review <span class="protochip">prototype</span> <span class="mix">present this review from a web page</span>${chip}</h3>
      <div class="act">${btns}<span class="why">built from the ${esc(s.period || "")} deck build's data; nothing is written to Outputs</span></div></div>
    ${fact ? `<p class="fact">${fact}</p>` : ""}
    ${checks.length ? `<ul class="checks">${checks.map(li).join("")}</ul>` : ""}</section>`;
}

$("#detail").addEventListener("click", async e => {
  const b = e.target.closest("[data-live]"); if (!b || !S) return;
  const cid = S.client;
  if (b.dataset.live === "stop") {
    try { await api("/api/live/stop", {method: "POST", body: JSON.stringify({client: cid})}); } catch (err) { toast("Could not stop it: " + err.message, "bad"); return; }
    LIVE.doc = {state: "idle"}; clearTimeout(LIVE.timer); liveDraw(); return;
  }
  b.disabled = true;
  try {
    const {body} = await api("/api/live/open", {method: "POST", body: JSON.stringify({client: cid, period: S.period})});
    LIVE.doc = body; liveDraw();
    if (body && body.state === "starting") { clearTimeout(LIVE.timer); LIVE.timer = setTimeout(() => liveFetch(cid), 3000); }
  } catch (err) { b.disabled = false; toast("Could not open Live Review: " + err.message, "bad"); }
});
"""
