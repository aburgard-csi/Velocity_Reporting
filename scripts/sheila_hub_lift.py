"""The Lift Matrix tab of CSM Sheila, in the Hub layout (Aaron, 2026-09-25; moved to the Hub 2026-11-02).

Every ARS client's current matrix (from its workbook) beside the one calculated from its ODD, the rates behind the
calculation editable, and the file for Bradford exported from here. The numbers come from the server
(build/ars_pipeline/lift_values.py through ars_launcher_web: `GET /api/lift/overview`, `GET /api/lift/client`,
`POST /api/lift/export`, `/download`, `/rescan`, `/scan-all`); this page only shows them and passes the four rates.
Each ODD is read once in the background and kept, so editing a rate never re-reads the extract.

The overview is a dense table, workbook row then calculated row with the change as an up or down chip, and the client's
page opens from a row (the row again, or Esc, goes back). On the client page the figures follow the rates as they are
typed: a change marks the matrix below out of date and recalculates a moment later (Enter does it at once), and Export
is held until the figures on screen are the ones for the values in the fields, so a matrix is never exported at values
other than the ones shown (Aaron, 2026-09-25: "we need an option to recalculate when the variables are changed").
"""
TAB = "lift"
NAME = "Lift Matrix"

VIEW = r"""
<div id="lm-ov">
  <div class="vh"><div><h1>Lift Matrix</h1><p id="lm-sub">Reading every ARS client's workbook…</p></div><div class="vhr" id="lm-csm"></div></div>
  <div class="kpis" id="lm-kpis" role="group" aria-label="Filter by matrix"></div>
  <section class="card" aria-label="Lift Matrices">
    <div class="lhead">
      <div class="row1"><label class="find"><svg viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/></svg><input id="lm-q" type="search" placeholder="Name or number" autocomplete="off" aria-label="Find a client"><kbd>/</kbd></label>
        <button class="btn" id="lm-all">Calculate every MM client from its ODD</button></div>
      <div class="filt" id="lm-filt"></div>
    </div>
    <div class="lmwrap"><table class="lmt" id="lm-table"></table></div>
    <p class="srcnote">Workbook rows are the matrix each client's newest ARS workbook carries. Calculated rows use the client's own rates and appear once its ODD has been read. Pick a client to compare the full matrices, change the values and export the file for Bradford.</p>
  </section>
</div>
<div id="lm-cl" hidden></div>
"""

CSS = r"""
/* Lift Matrix */
.kpis3{grid-template-columns:repeat(3,minmax(0,1fr))}
.vhr{display:flex;gap:8px;align-items:center}
.lmwrap{overflow-x:auto;padding:0 6px 6px}
table.lmt{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:13.5px}
.lmt th{position:sticky;top:0;text-align:right;font-size:11.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);padding:8px 10px;white-space:nowrap;background:var(--sheet)}
.lmt th.l,.lmt td.l{text-align:left}
.lmt td{text-align:right;padding:7px 10px;border-top:1px solid var(--line);white-space:nowrap}
.lmt tr.pick{cursor:pointer}
.lmt tr.pick:hover td{background:var(--glass-hi)}
.lmt tr.pick[aria-current="true"] td{background:var(--fill)}
.lmt tr.grp td{border-top:0}
.lmt tr.calc td{color:var(--ink)}
.lmt tr.calc td.l{color:var(--muted)}
.lmt td .sub{display:block;font-size:12px;color:var(--muted)}
.lmt .nm{font-weight:600}
.dchip{display:inline-flex;align-items:center;gap:3px;margin-left:6px;padding:0 7px;border-radius:999px;font-size:11.5px;font-weight:700;line-height:18px}
.dline{display:block;line-height:1.2}.dline .dchip{margin-left:0}
.dchip.up{background:var(--good-soft);color:var(--good)} .dchip.down{background:var(--bad-soft);color:var(--bad)} .dchip.flat{background:var(--fill);color:var(--muted)}
.lmt td.up{background:var(--good-soft);color:var(--good)} .lmt td.down{background:var(--bad-soft);color:var(--bad)}
.lmhead{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.lmhead h2{font:700 24px/1.15 var(--display);margin:0;letter-spacing:-.01em}
.lmhead .meta{color:var(--muted);font-size:13px}
.lmnote{margin:6px 0 0;color:var(--muted);font-size:13.5px}
.rates{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding:14px 16px 4px}
.rates label{display:grid;gap:5px;font-size:13px;color:var(--muted)}
.rates .fld{display:flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--sheet);border-radius:12px;padding:0 10px;min-height:38px;color:var(--ink)}
.rates .fld:focus-within{border-color:var(--good);box-shadow:0 0 0 2px var(--good-soft)}
.rates input,.rates select{font:inherit;color:var(--ink);background:none;border:0;outline:0;width:100%;min-width:0}
.rates .src{font-size:12px;color:var(--muted)}
.recalc{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;padding:8px 16px 14px}
.stalewrap.stale{opacity:.5;transition:opacity .15s}
.panelh{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline;padding:14px 16px 4px}
.panelh h3{margin:0;font:700 15px var(--display)}
.panelh .sub{color:var(--muted);font-size:13px}
.grids{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:6px 16px 6px}
.gridbox h4{margin:6px 0;font-size:13px;color:var(--muted);font-weight:700}
.exportbar{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;padding:14px 16px;border-radius:14px;margin:6px 0}
.exportbar.ready{background:var(--good-soft)} .exportbar.ask{background:var(--warn-soft)}
.exportbar p{margin:0;flex:1;min-width:240px}
.mono{font:12.5px var(--mono)}
.method{margin:6px 0 0;padding:0 16px 14px 34px;display:grid;gap:4px;font-size:13px;color:var(--muted)}
details.logd{padding:2px 16px 10px}
details.logd summary{cursor:pointer;font-size:13px;color:var(--muted)}
@media (max-width:1180px){.rates{grid-template-columns:repeat(2,minmax(0,1fr))}.grids{grid-template-columns:1fr}}
@media (max-width:520px){.rates{grid-template-columns:1fr}}
"""

JS = r"""
// ------------------------------------------------------------ Lift Matrix
const SEGS = ["NH", "NU", "1-5", "6-10", "11-15", "16-20", "21-25", "26 Plus"];
const money = v => v == null ? "–" : (v < 0 ? "−$" : "$") + Math.abs(Number(v)).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const pct = (v, d = 1) => v == null ? "–" : (100 * v).toFixed(d) + "%";
(function () {
  const L = {ov: null, d: null, id: null, req: 0, timer: null, debounce: null, q: "", kind: "", cursor: null, loaded: false, ovTimer: null};
  const signed = v => v == null ? "" : (v > 0 ? "+" : "") + money(v);
  const cls = v => v == null ? "flat" : v > 0.004 ? "up" : v < -0.004 ? "down" : "flat";
  const chip = (v) => v == null ? "" : `<span class="dchip ${cls(v)}">${v > 0.004 ? "▲" : v < -0.004 ? "▼" : "="} ${money(Math.abs(v))}</span>`;

  // ---------------------------------------------------------------- overview
  async function ovLoad() {
    clearTimeout(L.ovTimer);
    try { ({body: L.ov} = await api("/api/lift/overview")); L.error = ""; }
    catch (e) { L.error = "Couldn't read the Lift Matrices: " + e.message; }
    L.loaded = true;
    if (TAB === "lift" && !L.id) paintOv();
    const scanning = L.ov ? Object.values(L.ov.scans || {}).filter(x => x === "queued" || x === "scanning").length : 0;
    if (TAB === "lift" && !L.id) L.ovTimer = setTimeout(ovLoad, !L.ov || !L.ov.doc || L.ov.refreshing || scanning ? 3500 : 60000);
  }
  const statusOf = c => c.current ? (c.expired ? "expired" : "current") : "none";
  function ovRows() {
    const csm = $("#csm").value, q = L.q.trim().toLowerCase();
    return (L.ov && L.ov.doc ? L.ov.doc.clients : []).filter(c => (!csm || c.csm === csm) && (!q || c.id.includes(q) || (c.name || "").toLowerCase().includes(q)));
  }
  function paintOv() {
    $("#lm-csm").innerHTML = csmPick();
    const d = L.ov && L.ov.doc, scanning = L.ov ? Object.values(L.ov.scans || {}).filter(x => x === "queued" || x === "scanning").length : 0;
    if (L.error && !d) { $("#lm-table").innerHTML = `<tr><td class="l err">${esc(L.error)}</td></tr>`; return; }
    if (!d) {
      $("#lm-sub").textContent = "Reading every ARS client's workbook. This takes about a minute the first time.";
      $("#lm-kpis").innerHTML = ["Current", "Expired", "Calculated", "No matrix", "Reading now"].map(w => `<div class="kpi"><span class="k">${w}</span><span class="v">–</span></div>`).join("");
      $("#lm-table").innerHTML = Array.from({length: 8}, () => `<tr><td class="l" colspan="10"><span class="sk" style="height:16px;width:${40 + Math.random() * 50 | 0}%"></span></td></tr>`).join("");
      return;
    }
    const all = ovRows(), n = {current: 0, expired: 0, none: 0, calc: 0};
    for (const c of all) { n[statusOf(c)]++; if (c.calculated) n.calc++; }
    $("#lm-sub").textContent = `DDA value per account per month, by swipe segment · ${L.ov.refreshing ? "updating…" : "as of " + ago(L.ov.age_seconds)}`;
    const T = [["current", "Current", "outputs", n.current, "in their window"], ["expired", "Expired", "attention", n.expired, "need a new matrix"], ["calc", "Calculated", "ready", n.calc, "from the ODD"], ["none", "No matrix", "checking", n.none, "SM, or no workbook"]];
    $("#lm-kpis").innerHTML = T.map(([k, w, ic, v, s]) => `<button class="kpi" data-lkind="${k}" aria-pressed="${L.kind === k}" title="Show only: ${esc(w)}"><span class="k">${si(ic)}${esc(w)}</span><span class="v">${v}</span><span class="n">${esc(s)}</span></button>`).join("") +
      `<div class="kpi"><span class="k">${si(scanning ? "building" : "idle")}Reading now</span><span class="v">${scanning}</span><span class="n">${scanning ? "ODD extracts, one at a time" : "nothing being read"}</span></div>`;
    const rows = all.filter(c => !L.kind || (L.kind === "calc" ? !!c.calculated : statusOf(c) === L.kind));
    $("#lm-filt").innerHTML = L.kind ? `Showing <b>${esc(T.find(x => x[0] === L.kind)[1])}</b> <button class="x" data-lclear>Clear ✕</button>` : `${rows.length} client${rows.length === 1 ? "" : "s"}`;
    const head = `<thead><tr><th class="l">Client</th><th class="l">Matrix</th>${SEGS.map(s => `<th>${esc(s)}</th>`).join("")}</tr></thead>`;
    const body = rows.map(c => {
      const st = c.current ? (c.expired ? `<span class="chip k-attention">Expired</span>` : `<span class="chip k-outputs">Current</span>`)
        : `<span class="chip">${c.path === "SM" ? "SM model" : c.workbook ? "No matrix" : "No workbook"}</span>`;
      const cur = SEGS.map(s => `<td>${c.current ? money(c.current[s]) : ""}</td>`).join("");
      const calc = c.calculated ? `<tr class="calc pick" data-lid="${esc(c.id)}"><td class="l"></td><td class="l">Calculated</td>${SEGS.map(s => `<td>${money(c.calculated[s])}${c.current ? `<span class="dline">${chip(c.calculated[s] != null && c.current[s] != null ? c.calculated[s] - c.current[s] : null)}</span>` : ""}</td>`).join("")}</tr>` : "";
      return `<tr class="pick${calc ? " grp" : ""}" data-lid="${esc(c.id)}" aria-current="${L.cursor === c.id}"><td class="l"><span class="nm">${esc(c.name)}</span> <span class="sub" style="display:inline">${esc(c.id)}</span></td>
        <td class="l">${st}${c.window ? `<span class="sub">${esc(c.window)}</span>` : ""}</td>${cur}</tr>${calc}`;
    }).join("");
    $("#lm-table").innerHTML = head + `<tbody>${body || `<tr><td class="l" colspan="10"><p class="empty">No clients match.</p></td></tr>`}</tbody>`;
  }

  // ---------------------------------------------------------------- one client
  function ratesQuery(id) {
    const q = new URLSearchParams({client: id}), bp = $("#lm-ic"), fee = $("#lm-fee"), col = $("#lm-col"), cap = $("#lm-cap");
    if (bp && bp.value !== "") q.set("ic_rate", String(Number(bp.value) / 10000));
    if (fee && fee.value !== "") q.set("nsf_fee", fee.value);
    if (col && col.value !== "") q.set("collection", String(Number(col.value) / 100));
    if (cap) q.set("winsor", cap.value);
    return q.toString();
  }
  function ratesBody(d) {
    const q = new URLSearchParams(ratesQuery(d.client)), body = {client: d.client};
    for (const k of ["ic_rate", "nsf_fee", "collection", "winsor"]) if (q.has(k)) body[k] = q.get(k);
    return body;
  }
  async function liftOpen(id, keep) {
    clearTimeout(L.ovTimer); clearTimeout(L.timer);
    L.id = id; L.cursor = id; setTabParams({client: id});
    $("#lm-ov").hidden = true; $("#lm-cl").hidden = false;
    const c = CLIENTS.find(x => x.id === id) || {id};
    if (!keep) $("#lm-cl").innerHTML = `<div class="lmhead"><h2>${esc(c.name || id)}</h2><span class="meta">${esc(id)}</span></div><div class="pres" style="padding:14px 0"><div class="pc"><span class="sk" style="width:40%;height:18px"></span><span class="sk" style="width:90%;height:12px"></span><span class="sk" style="width:60%;height:12px"></span></div></div><p class="lmnote">Reading the workbook and the ODD…</p>`;
    const n = ++L.req;
    let d;
    try { ({body: d} = await api("/api/lift/client?" + (keep ? ratesQuery(id) : "client=" + encodeURIComponent(id)))); }
    catch (e) {
      if (n !== L.req) return;
      const box = $("#lm-out"); if (box) box.innerHTML = `<p class="err">${esc(e.message)}</p>`; else $("#lm-cl").insertAdjacentHTML("beforeend", `<p class="err">${esc(e.message)}</p>`);
      return;
    }
    if (n !== L.req || L.id !== id || TAB !== "lift") return;
    L.d = d;
    if (keep && $("#lm-out") && d.scan_state === "ready") { paintResults(d); return; }
    paintClient(d);
  }
  function back() { clearTimeout(L.timer); clearTimeout(L.debounce); L.req++; L.id = null; L.d = null; setTabParams({client: ""}); $("#lm-cl").hidden = true; $("#lm-ov").hidden = false; paintOv(); ovLoad(); }

  function paintClient(d) {
    const cur = d.current ? `Current matrix: ${esc(d.current.window)} (${d.current.data_past_end ? "expired" : "data " + esc(d.current.data_date)}) in ${esc(d.workbook)}.`
      : d.workbook ? `${esc(d.workbook)} carries no Lift Matrix (SM).` : d.workbook_error ? `The workbook could not be read: ${esc(d.workbook_error)}` : "No ARS workbook in Inputs.";
    let html = `<div class="lmhead"><button class="btn" data-lback>← All clients <kbd>Esc</kbd></button><h2>${esc(d.name || d.client)}</h2><span class="meta">${esc(d.client)} · ${esc(d.csm || "")} · ${esc(d.period || "")}</span><span class="meta clientlinks" id="lm-links"></span></div><p class="lmnote">${cur}</p>`;
    if (d.scan_state === "sm") html += `<p class="lmnote">${esc(d.name || d.client)} is on the SM model, which does not use a Lift Matrix.</p>`;
    else if (d.scan_state === "no-odd") html += `<p class="lmnote err">No ODD extract for ${esc(d.client)} in Inputs, so nothing can be calculated.</p>`;
    else if (d.scan_state !== "ready") {
      html += d.scan_state === "error" ? `<p class="lmnote err">Reading the ODD stopped: ${esc(d.scan_error)}</p><button class="btn primary" id="lm-retry">Try again</button>`
        : `<div class="pres" style="padding:14px 0"><div class="pc"><span class="why">${si("building")} Reading the ODD (${esc(d.scan_state)}). This takes up to a minute; this page fills in when it is done.</span><span class="sk" style="width:70%;height:12px"></span></div></div>`;
      if (d.scan_state !== "error") L.timer = setTimeout(() => liftOpen(d.client), 3000);
    } else {
      const df = d.defaults, r = d.rates;
      html += `<div id="lm-kpis2" class="kpis kpis3" style="margin-top:14px"></div>
      <section class="card" style="margin-top:14px"><header><h2>Rates</h2><p class="sub">Change one and the figures below follow. Enter recalculates at once.</p></header><div class="rates">
        <label>Interchange rate<span class="fld"><input id="lm-ic" type="number" step="0.5" min="0" max="500" value="${+(r.ic_rate * 10000).toFixed(2)}"><span>BP</span></span><span class="src">${esc(df.ic_source)}</span></label>
        <label>NSF/OD fee<span class="fld"><span>$</span><input id="lm-fee" type="number" step="0.01" min="0" max="200" value="${r.nsf_fee ?? ""}" placeholder="Enter the fee"></span><span class="src">${esc(df.nsf_source)}</span></label>
        <label>OD collection rate<span class="fld"><input id="lm-col" type="number" step="1" min="0" max="100" value="${+(r.collection * 100).toFixed(1)}"><span>%</span></span><span class="src">${esc(df.collection_source)}</span></label>
        <label>Outlier cap<span class="fld"><select id="lm-cap">${d.winsor_options.map(o => `<option value="${o.value}"${o.value === r.winsor ? " selected" : ""}>${esc(o.label)}</option>`).join("")}</select></span><span class="src">${esc(df.winsor_source)}</span></label>
      </div><div class="recalc"><button class="btn primary" id="lm-calc">Recalculate <kbd>R</kbd></button><span class="why" id="lm-stale"></span><button class="link" id="lm-reset">Reset to the defaults</button></div></section>
      <div id="lm-out" class="stalewrap"></div>`;
    }
    $("#lm-cl").innerHTML = html;
    clientLinks(d.client, "lift", $("#lm-links"));
    const re = $("#lm-retry"); if (re) re.addEventListener("click", async () => { await api("/api/lift/rescan", {method: "POST", body: JSON.stringify({client: d.client})}); liftOpen(d.client); });
    if (d.scan_state !== "ready") return;
    paintResults(d);
    const stale = () => {
      $("#lm-out").classList.add("stale"); $("#lm-stale").textContent = "Updating the figures…";
      for (const b of ["#lm-ok", "#lm-dl"]) { const x = $(b); if (x) { x.disabled = true; x.title = "Recalculating first"; } }
      clearTimeout(L.debounce); L.debounce = setTimeout(recalc, 700);
    };
    for (const el of ["#lm-ic", "#lm-fee", "#lm-col", "#lm-cap"]) {
      $(el).addEventListener(el === "#lm-cap" ? "change" : "input", stale);
      $(el).addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); recalc(); } });
    }
    $("#lm-calc").addEventListener("click", recalc);
    $("#lm-reset").addEventListener("click", () => { clearTimeout(L.debounce); liftOpen(d.client); });
  }
  function recalc() { clearTimeout(L.debounce); if (L.id) liftOpen(L.id, true); }

  // The headline numbers, which move as the rates do: the book's weighted DDA value, the biggest single change, and where the export stands.
  function paintKpis(d) {
    const calc = d.calculated, cur = d.current || {}, curSeg = cur.segments || {}, bySeg = calc ? Object.fromEntries(calc.segments.map(x => [x.segment, x])) : {};
    let n = 0, nw = 0, cw = 0, curOk = !!d.current, big = null;
    for (const s of SEGS) {
      const g = d.segments[s], nv = bySeg[s] ? bySeg[s].dda : null, cv = curSeg[s] ? curSeg[s].dda : null;
      if (!g || nv == null) continue;
      n += g.n; nw += g.n * nv; if (cv == null) curOk = false; else { cw += g.n * cv; if (!big || Math.abs(nv - cv) > Math.abs(big.d)) big = {s, d: nv - cv}; }
    }
    const done = d.exported && JSON.stringify(d.exported.rates) === JSON.stringify(d.rates);
    const wavg = n ? nw / n : null, cavg = n && curOk ? cw / n : null, delta = wavg != null && cavg != null ? wavg - cavg : null;
    $("#lm-kpis2").innerHTML = `<div class="kpi"><span class="k">${si("ready")}Value per account, per month</span><span class="v">${calc ? money(wavg) : "–"}${chip(delta)}</span><span class="n">${cavg != null ? "workbook " + money(cavg) + ", weighted by accounts" : "weighted by accounts"}</span></div>
      <div class="kpi"><span class="k">${si("attention")}Biggest change</span><span class="v">${big ? esc(big.s) : "–"}${big ? chip(big.d) : ""}</span><span class="n">${big ? "segment DDA value against the workbook" : "needs the fee to compare"}</span></div>
      <div class="kpi"><span class="k">${si(done ? "outputs" : "checking")}Export</span><span class="v" style="font-size:20px">${done ? "Exported" : calc ? "Not yet" : "–"}</span><span class="n">${done ? esc(d.exported.at) + (d.exported.by ? " by " + esc(d.exported.by) : "") : "review it, then Export"}</span></div>`;
  }

  // Current (the workbook's) and new (calculated) side by side: each segment's DDA value in both, the change, and the step from the segment before; then both lift grids.
  function paintResults(d) {
    paintKpis(d);
    const segs = d.segments, calc = d.calculated, cur = d.current || {}, curSeg = cur.segments || {}, curGrid = cur.grid || {};
    const bySeg = calc ? Object.fromEntries(calc.segments.map(x => [x.segment, x])) : {};
    const newV = s => { const c = bySeg[s]; return c ? c.dda : null; }, curV = s => curSeg[s] ? curSeg[s].dda : null;
    const step = (f, i) => i < 2 || f(SEGS[i]) == null || f(SEGS[i - 1]) == null ? null : f(SEGS[i]) - f(SEGS[i - 1]);
    const rows = SEGS.map((s, i) => {
      const g = segs[s], nv = newV(s), cv = curV(s), dlt = nv != null && cv != null ? nv - cv : null;
      return `<tr><td class="l"><b>${esc(s)}</b></td><td>${g ? g.n.toLocaleString() : ""}</td><td>${curSeg[s] && curSeg[s].dist != null ? pct(curSeg[s].dist) : "–"}</td><td>${pct(g.dist)}</td>
        <td>${money(cv)}</td><td><b>${money(nv)}</b></td><td>${chip(dlt)}</td><td>${signed(step(curV, i))}</td><td>${signed(step(newV, i))}</td></tr>`;
    }).join("");
    const seg = `<section class="card" style="margin-top:14px"><div class="panelh"><h3>Revenue segmentation: current and new</h3><span class="sub">Current is the matrix in ${esc(d.workbook || "the workbook")}${cur.window ? " (" + esc(cur.window) + ")" : ""}. A step is a segment's DDA value less the one above it.</span></div>
      <div class="lmwrap"><table class="lmt"><thead><tr><th class="l" rowspan="2">Segment</th><th rowspan="2">Accounts</th><th colspan="2">Distribution</th><th colspan="3">DDA value</th><th colspan="2">Step from the segment before</th></tr>
      <tr><th>Current</th><th>New</th><th>Current</th><th>New</th><th>Change</th><th>Current</th><th>New</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
    const detail = `<details class="logd"><summary>How each new value is made up</summary><div class="lmwrap"><table class="lmt"><thead><tr><th class="l">Segment</th><th>Avg spend / mo</th><th>NSF/OD items / mo</th><th>Interchange</th><th>NSF/OD</th><th>DDA value</th></tr></thead><tbody>${
      SEGS.map(s => { const g = segs[s], c = bySeg[s]; return `<tr><td class="l"><b>${esc(s)}</b></td><td>${money(g.spend)}</td><td>${g.items.toFixed(3)}</td><td>${c ? money(c.interchange) : ""}</td><td>${c ? money(c.nsf) : ""}</td><td>${c ? money(c.dda) : ""}</td></tr>`; }).join("")
    }</tbody></table></div></details>`;
    let out;
    if (!calc) out = seg + `<p class="lmnote err" style="margin-top:12px">Enter the client's NSF/OD fee to calculate the new matrix.</p>`;
    else {
      const cols = SEGS.slice(2), bases = SEGS.slice(1, 6);
      const grid = (title, get, compare) => `<div class="gridbox"><h4>${title}</h4><div class="lmwrap" style="padding:0"><table class="lmt"><thead><tr><th class="l">Baseline</th>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${
        bases.map(b => `<tr><td class="l"><b>${esc(b)}</b></td>${cols.map(c => {
          const v = get(b, c); if (v == null) return "<td></td>";
          const was = compare ? compare(b, c) : null, k = was == null ? "" : cls(Math.round((v - was) * 100) / 100);
          return `<td class="${k === "up" || k === "down" ? k : ""}"${was == null ? "" : ` title="Current ${money(was)}"`}>${money(v)}</td>`;
        }).join("")}</tr>`).join("")}</tbody></table></div></div>`;
      const curGet = (b, c) => (curGrid[b] || {})[c] ?? null, newGet = (b, c) => calc.matrix[b][c] ?? null;
      const grids = `<section class="card" style="margin-top:14px"><div class="panelh"><h3>Monthly incremental revenue lift</h3><span class="sub">New cells are tinted where they are above the current matrix and where they are below. Hover a cell for the current value.</span></div><div class="grids">
        ${grid("Current" + (cur.window ? " · " + esc(cur.window) : ""), curGet)}${grid("New", newGet, Object.keys(curGrid).length ? curGet : null)}</div></section>`;
      const sc = d.scan, fee = sc.fee;
      const feeLine = fee ? (fee.values.length ? `NSF/OD fee in the ODD (${esc(fee.columns.join(", "))}): ${fee.values.map(x => `${money(x.fee)} on ${pct(x.share, 0)} of items`).join(", ")}. The most common is the default.` : `The ODD has ${esc(fee.columns.join(", "))} but no fee on any NSF/OD item, so the fee comes from the workbook.`)
        : `This ODD carries no NSF/OD fee column (Fees1), so NSF/OD is valued as the monthly OD item count × the fee.`;
      const method = `<section class="card" style="margin-top:14px"><div class="panelh"><h3>How it was calculated</h3></div><ul class="method">
        <li>${sc.population.toLocaleString()} ARS-eligible accounts, consumer and business: ${sc.card_holders.toLocaleString()} with a debit card in the seven swipe segments (${(sc.counts.consumer || 0).toLocaleString()} consumer, ${(sc.counts.business || 0).toLocaleString()} business${sc.counts["business? blank"] ? ", " + sc.counts["business? blank"].toLocaleString() + " with Business? blank" : ""}) and ${(segs.NH ? segs.NH.n : 0).toLocaleString()} without one in NH. The distribution is of all of them.</li>
        <li>Swipes, spend and NSF/OD items averaged over ${esc(sc.window_label)} (${sc.window.length} complete months), from ${esc(sc.source_file)}.${sc.excluded_months ? " " + esc(sc.excluded_months) : ""}</li>
        <li>Segment: average swipes per month, rounded down into its band.</li>
        <li>Outliers: ${d.rates.winsor >= 1 ? "no cap on spend or NSF/OD items" : `each account's spend and NSF/OD items are capped at the ${+(d.rates.winsor * 100).toFixed(1)}th percentile of its segment`}. 26 Plus is valued on its accounts averaging 26 to ${25 + sc.top_band} swipes; its distribution counts all of them.</li>
        <li>DDA value = interchange rate × spend + NSF/OD fee × items × collection rate. Lift = DDA of the new segment − DDA of the baseline.</li>
        <li>NH: ${bySeg.NH && bySeg.NH.from_nu ? "this client has no eligible account without a debit card, so NH carries NU's value" : `the ${(segs.NH ? segs.NH.n : 0).toLocaleString()} eligible accounts with no debit card, valued on their own spend and NSF/OD items`}.</li>
        <li>${feeLine}</li></ul></section>`;
      const done = d.exported && JSON.stringify(d.exported.rates) === JSON.stringify(d.rates);
      const exp = done
        ? `<div class="exportbar ready"><p><b>Exported</b> ${esc(d.exported.at)}${d.exported.by ? " by " + esc(d.exported.by) : ""} at these values as <span class="mono">${esc(d.file_name)}</span>. Email it to Bradford to have it loaded.</p><button class="btn primary" id="lm-dl">Download again</button></div>`
        : `<div class="exportbar ask"><p><b>Review the new matrix against the current one, then export it.</b> Export this matrix downloads <span class="mono">${esc(d.file_name)}</span>, the Excel file for Bradford.${d.exported ? " The last export was at different values." : ""}</p><button class="btn primary" id="lm-ok">Export this matrix <kbd>E</kbd></button></div>`;
      out = seg + detail + grids + exp + method;
    }
    $("#lm-out").innerHTML = out; $("#lm-out").classList.remove("stale"); const st = $("#lm-stale"); if (st) st.textContent = "";
    wireSave(d);
  }

  async function download(d) {
    const r = await fetch("/api/lift/download", {method: "POST", headers: {"X-Token": TOKEN, "Content-Type": "application/json"}, body: JSON.stringify(ratesBody(d))});
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.error || "HTTP " + r.status); }
    const url = URL.createObjectURL(await r.blob()), a = document.createElement("a");
    a.href = url; a.download = d.file_name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }
  // Export this matrix: record what is exported, then download it: one click (Aaron, 2026-09-25).
  function wireSave(d) {
    const ok = $("#lm-ok"), dl = $("#lm-dl");
    if (ok) ok.addEventListener("click", async () => {
      ok.disabled = true; ok.textContent = "Exporting…";
      try {
        const {status, body: r} = await api("/api/lift/export", {method: "POST", body: JSON.stringify(ratesBody(d))});
        if (status !== 200) throw new Error(r.error || "not exported");
        await download(d); await liftOpen(d.client, true);
        toast(`Exported. ${d.file_name} is in your Downloads folder.`, "good", 6000); celebrate();
      } catch (e) { ok.disabled = false; ok.textContent = "Try again"; toast("Couldn't export: " + e.message, "bad", 6000); }
    });
    if (dl) dl.addEventListener("click", async () => {
      dl.disabled = true;
      try { await download(d); toast(`Downloaded ${d.file_name}.`, "good", 4000); } catch (e) { toast("Couldn't download: " + e.message, "bad", 6000); }
      dl.disabled = false;
    });
  }

  function move(dir) {
    const rows = ovRows().filter(c => !L.kind || (L.kind === "calc" ? !!c.calculated : statusOf(c) === L.kind)), i = rows.findIndex(c => c.id === L.cursor);
    const next = rows[Math.max(0, Math.min(rows.length - 1, i < 0 ? 0 : i + dir))]; if (!next) return;
    L.cursor = next.id; paintOv(); const el = $(`tr.pick[data-lid="${next.id}"]`); if (el) el.scrollIntoView({block: "nearest"});
  }

  $("#v-lift").addEventListener("click", e => {
    const t = e.target, k = t.closest("[data-lkind]"); if (k) { L.kind = L.kind === k.dataset.lkind ? "" : k.dataset.lkind; return paintOv(); }
    if (t.closest("[data-lclear]")) { L.kind = ""; return paintOv(); }
    if (t.closest("[data-lback]")) return back();
    const r = t.closest("tr.pick[data-lid]"); if (r) return liftOpen(r.dataset.lid);
    if (t.closest("#lm-all")) api("/api/lift/scan-all", {method: "POST", body: "{}"}).then(({body}) => { toast(`${body.queued} queued. The table fills in as each one finishes.`, "good", 5000); ovLoad(); }).catch(err => toast(err.message, "bad"));
  });
  $("#lm-q").addEventListener("input", () => { L.q = $("#lm-q").value; paintOv(); });

  registerTab("lift", {
    enter(p) { if (p && p.client) liftOpen(p.client); else { L.id = null; $("#lm-cl").hidden = true; $("#lm-ov").hidden = false; paintOv(); ovLoad(); } },
    leave() { clearTimeout(L.ovTimer); clearTimeout(L.timer); clearTimeout(L.debounce); },
    refresh() { if (!L.id) paintOv(); },
    keys: [["j  k", "Move down or up the clients"], ["Enter", "Open the client"], ["Esc", "Back to every client"], ["R", "Recalculate (on a client)"], ["E", "Export this matrix (on a client)"], ["/", "Find a client"]],
    key(e) {
      const k = e.key;
      if (L.id) {
        if (k === "Escape") back();
        else if (k === "r") recalc();
        else if (k === "e") { const b = $("#lm-ok") || $("#lm-dl"); if (b && !b.disabled) b.click(); }
        return;
      }
      if (k === "j" || k === "ArrowDown") { e.preventDefault(); move(1); }
      else if (k === "k" || k === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (k === "Enter" && L.cursor && !document.activeElement.closest("tr")) liftOpen(L.cursor);
      else if (k === "/") { e.preventDefault(); $("#lm-q").focus(); }
      else if (k === "Escape" && L.kind) { L.kind = ""; paintOv(); }
    },
    palette: () => L.id ? [{t: "Recalculate the matrix", s: "R", run: recalc}, {t: "Export this matrix", s: "E", run: () => { const b = $("#lm-ok") || $("#lm-dl"); if (b) b.click(); }}, {t: "Back to every Lift Matrix", s: "Esc", run: back}]
      : [{t: "Calculate every MM client from its ODD", s: "", run: () => $("#lm-all").click()}],
  });
})();
"""
