/* Live Review — draws the view model. It knows block types, not programs; every figure arrives raw and is formatted here. */
(function () {
  "use strict";
  var MODEL = JSON.parse(document.getElementById("model").textContent);
  var TOKEN = document.querySelector('meta[name="token"]').content;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); };

  /* ---------- number formats ---------- */
  var grp = function (n) { return Math.round(n).toLocaleString("en-US"); };
  var F = {
    int: function (v) { return grp(v); },
    usd: function (v) { return (v < 0 ? "-" : "") + "$" + grp(Math.abs(v)); },
    usd2: function (v) { return (v < 0 ? "-$" : "$") + Math.abs(v).toFixed(2); },
    usdk: function (v) { var a = Math.abs(v), s = v < 0 ? "-" : ""; return a >= 1e6 ? s + "$" + (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? s + "$" + Math.round(a / 1e3) + "K" : s + "$" + grp(a); },
    pct1: function (v) { return v.toFixed(1) + "%"; },
    pct2: function (v) { return v.toFixed(2) + "%"; },
    pct0: function (v) { return Math.round(v) + "%"; },
    frac1: function (v) { return (v * 100).toFixed(1) + "%"; },
    dec1: function (v) { return v.toFixed(1); },
    dec2: function (v) { return v.toFixed(2); },
    ratio: function (v) { return v.toFixed(1) + " : 1"; }
  };
  function fmt(v, f) { if (v == null || (typeof v === "number" && !isFinite(v))) return "—"; return (F[f] || F.int)(v); }
  function money(v, kind) { // the P&L's rule: a cost in parentheses, a loss in parentheses
    if (v == null) return "—";
    var t = "$" + grp(Math.abs(v));
    if (kind === "line" || kind === "total") return v < 0 ? t : "(" + t + ")";
    return v < 0 ? "(" + t + ")" : t;
  }
  var COLORS = {navy: "var(--c-navy)", steel: "var(--c-steel)", orange: "var(--c-orange)", teal: "var(--c-teal)", tick: "var(--c-tick)", gold: "var(--c-gold)"};
  var col = function (n) { return COLORS[n] || COLORS.navy; };

  /* ---------- state ---------- */
  var S = {prog: "", screen: 0, v: {}, m: {}, bs: {}, sort: {}, q: {}, drill: null, panel: null, tableId: null, present: false, plain: false};
  var T = {};
  try { T.theme = localStorage.getItem("lr-theme") || ""; } catch (e) { T.theme = ""; }
  try { var qp = new URLSearchParams(location.search); if (/^(light|dark)$/.test(qp.get("theme") || "")) T.theme = qp.get("theme"); T.present = qp.get("present") === "1"; T.drill = qp.get("drill") || ""; T.panel = qp.get("panel") || ""; } catch (e) {}
  if (T.theme) document.documentElement.setAttribute("data-theme", T.theme);

  function programs() { return MODEL.programs; }
  function visiblePrograms() { return programs().filter(function (p) { return !p.hidden; }); }
  function programOf(key) { return programs().filter(function (p) { return p.key === key; })[0] || null; }
  /* The storyline: each section's screens in order, a screen of a program with no pack standing in as its "run X first" stub. */
  function storyItems() {
    if (!MODEL.story) return [];
    var out = [], n = 0;
    MODEL.story.sections.forEach(function (sec, si) {
      sec.screens.forEach(function (r, ri) {
        var pr = programOf(r.prog), scr = null;
        if (pr && !r.stub) scr = pr.screens.filter(function (x) { return x.id === r.id; })[0];
        if (!scr) scr = MODEL.story.stubs[r.ref];
        if (scr) out.push({scr: scr, sec: sec, si: si, ri: ri, ref: r.ref, prog: sec.prog || r.prog, n: n++});
      });
    });
    return out;
  }
  function curProgram() { return programs().filter(function (p) { return p.key === S.prog; })[0] || null; }
  function cname() { return (MODEL.client && MODEL.client.name) || "This client"; }   // the peer screens call the client by its name
  var PRODUCT = {ars: "ARS", ti: "Transaction Intelligence", ics: "ICS", mrpc: "MRPC", cashplease: "CashPlease", rems: "REMS"};
  function prodLabel(k) { return PRODUCT[k] || (programOf(k) || {}).label || k; }
  /* A product's sections are numbered within the product ("section 2 of 5"), never across the whole review. */
  function prodSections(k) { return MODEL.story.sections.filter(function (s) { return s.prog === k; }); }
  function prodIndex(sec) { return prodSections(sec.prog).indexOf(sec) + 1; }
  function progNow() { var it = curStory(); return it ? it.prog : (S.prog === "all" ? "" : S.prog); }
  /* Which product is on screen: a coloured tag in the story bar, a coloured rule across the top, and a title card for a second or two when the
     story moves on into another product. The card is dismissed by any key or click and never holds a key back. */
  /* The title card is the deck's section divider (build/cover_divider.py): the blue gradient, the orange wedge and the white CSI logo bottom-left,
     the product at 52 pt, its line of topics at 24 pt, three headline figures at 40 pt and the progress track with this product in orange. */
  var DIVIDER = {
    ars: {title: "Account Revenue Solution\u00ae", topics: "Mailings \u00b7 Debit Card \u00b7 Reg E", track: "ARS"},
    ti: {title: "Transaction Intelligence", topics: "Competition \u00b7 Attrition \u00b7 Deposits", track: "TI"},
    ics: {title: "Invitation Checking\u00ae System", topics: "Referrals \u00b7 Account Performance \u00b7 Revenue", track: "ICS"},
    mrpc: {title: "MyRewards Premium Cards\u00ae", topics: "Enrollments \u00b7 Retention \u00b7 Revenue", track: "MRPC"},
    cashplease: {title: "CashPlease\u00ae", topics: "Loan Volume \u00b7 Portfolio Status \u00b7 Peer Comparison", track: "CashPlease"},
    rems: {title: "Reg E Management Solution", topics: "Responses \u00b7 Opt-Ins \u00b7 Peer Comparison", track: "REMS"}
  };
  function hideProgramCard() { var el = $("#pdiv"); if (el) el.className = ""; clearTimeout(S.pdivT); }
  function showProgramCard(pk, hold) {
    var info = DIVIDER[pk], pr = programOf(pk); if (!info || !pr) return;   // ti is a product like the others
    var kp = ((pr.summary || {}).kpis || []).slice(0, 3);
    if (!kp.length) {   // a program with no summary (Transaction Intelligence) shows the first figures its first screen carries
      (pr.screens || []).some(function (s) { var b = (s.blocks || []).filter(function (x) { return x.t === "kpis"; })[0]; if (b) { kp = b.items.slice(0, 3); return true; } return false; });
    }
    var order = Object.keys(DIVIDER).filter(function (k) { var p = programOf(k); return p && p.state === "ready"; });
    var stats = kp.map(function (k, i) {
      return '<div class="dstat" style="left:' + (6.67 + i * 29.63) + '%"><b>' + esc(fmt(k.value, k.fmt === "usd" ? "usdk" : k.fmt)) + "</b><span>" + esc(k.label) + "</span></div>";
    }).join("");
    var track = order.length > 1 ? '<div class="dtrack">' + order.map(function (k) { return '<span' + (k === pk ? ' class="on"' : "") + ">" + esc(DIVIDER[k].track) + "</span>"; }).join("") + "</div>" : "";
    var el = $("#pdiv");
    if (!el) { el = document.createElement("div"); el.id = "pdiv"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.innerHTML = '<div class="dwedge"></div><div class="dlogo" role="img" aria-label="CSI"></div><h2' + (info.title.length > 24 ? ' class="long"' : "") + ">" + esc(info.title) + '</h2><p class="dben">' + esc(info.topics) + "</p>" + stats + track + (hold ? '<p class="dhint">Press \u2192 to start ' + esc(info.title) + "</p>" : "");
    el.className = "on"; clearTimeout(S.pdivT);
    if (!hold) S.pdivT = setTimeout(hideProgramCard, 2600);   // a held card waits for the next press
  }
  function screens() {
    if (S.prog === "story") return storyItems().map(function (x) { return x.scr; });
    if (S.prog === "all") return MODEL.combined ? MODEL.combined.screens : [];
    var p = curProgram();
    return p && p.state === "ready" ? p.screens : [];
  }
  function curScreen() { return screens()[S.screen] || null; }
  function curStory() { return S.prog === "story" ? storyItems()[S.screen] || null : null; }

  /* ---------- routing ---------- */
  function readHash() {
    var h = location.hash.replace(/^#/, "").split("/");
    var p = h[0], sid = h[1];
    if (p === "story" && MODEL.story) {
      var its = storyItems(), k = its.map(function (x) { return x.ref; }).indexOf(decodeURIComponent(sid || ""));
      S.prog = "story"; S.screen = k < 0 ? 0 : k; return;
    }
    if (p === "all" && MODEL.combined) {
      var cs = MODEL.combined.screens, ci = cs.map(function (x) { return x.id; }).indexOf(sid);
      S.prog = "all"; S.screen = ci < 0 ? 0 : ci; return;
    }
    var pr = programs().filter(function (x) { return x.key === p; })[0];
    if (pr) { S.prog = pr.key; var i = pr.screens.map(function (s) { return s.id; }).indexOf(sid); S.screen = i < 0 ? 0 : i; return; }
    var first = programs().filter(function (x) { return x.state === "ready"; })[0];
    S.prog = MODEL.story ? "story" : (MODEL.combined ? "all" : (first ? first.key : (programs()[0] || {}).key));
    S.screen = 0;
  }
  function writeHash() {
    var s = curScreen(), st = curStory();
    var h = "#" + S.prog + (S.prog === "story" && st ? "/" + encodeURIComponent(st.ref) : (s ? "/" + s.id : ""));
    if (location.hash !== h) history.replaceState(null, "", h);
  }
  function go(prog, sid) {
    S.prog = prog;
    if (prog === "story") { S.screen = Math.max(0, storyItems().map(function (x) { return x.ref; }).indexOf(sid)); S.drill = null; closePanel(); render(); window.scrollTo({top: 0}); return; }
    var scr = prog === "all" ? [] : (programs().filter(function (x) { return x.key === prog; })[0] || {screens: []}).screens;
    var i = scr.map(function (s) { return s.id; }).indexOf(sid);
    S.screen = i < 0 ? 0 : i; S.drill = null; closePanel(); render();
  }
  function walkOrder() {   // the arrow keys walk every section in turn: All programs, then each program that has data
    return (MODEL.story ? ["story"] : []).concat(MODEL.combined ? ["all"] : []).concat(visiblePrograms().filter(function (p) { return p.state === "ready"; }).map(function (p) { return p.key; }));
  }
  function screensOf(key) {
    if (key === "story") return storyItems().map(function (x) { return x.scr; });
    if (key === "all") return MODEL.combined ? MODEL.combined.screens : [];
    var p = programs().filter(function (x) { return x.key === key; })[0];
    return p && p.state === "ready" ? p.screens : [];
  }
  /* While presenting The review the arrows go one product at a time (Aaron, 2026-11-03: "it should do one product at a time"):
     on a product's last screen, \u2192 holds the next product's title card, and the next \u2192 starts that product. They never carry on out of
     the review into All programs or a product's own tab. */
  function step(d) {
    var n = screens().length, i = S.screen + d;
    if (S.present && S.prog === "story" && d > 0 && n && i < n) {
      var here = curStory(), nxt = storyItems()[i];
      if (here && nxt && nxt.prog !== here.prog) {
        if (S.hold !== nxt.prog) { S.hold = nxt.prog; showProgramCard(nxt.prog, true); return; }   // first press: the title card, held
        S.hold = null; S.lastFam = nxt.prog;                                                       // second press: on into the product, no card twice
      }
    }
    if (S.present && S.prog === "story" && (i < 0 || i >= n)) return;                              // the review's first and last screen are its ends
    if (n && i >= 0 && i < n) S.screen = i;
    else {   // past the last (or before the first) screen of a section: carry on into the neighbouring one, never wrap round
      var order = walkOrder(), at = order.indexOf(S.prog), to = at < 0 ? -1 : at + (d > 0 ? 1 : -1);
      if (to < 0 || to >= order.length) return;
      var next = screensOf(order[to]); if (!next.length) return;
      S.prog = order[to]; S.screen = d > 0 ? 0 : next.length - 1;
    }
    S.drill = null; closePanel(); render(); window.scrollTo({top: 0});
  }
  function stepProgram(d) {
    var keys = (MODEL.story ? ["story"] : []).concat(MODEL.combined ? ["all"] : []).concat(visiblePrograms().map(function (p) { return p.key; }));
    var i = keys.indexOf(S.prog);
    var j = (i + d + keys.length) % keys.length;
    go(keys[j]);
  }

  /* ---------- chrome ---------- */
  var ICON = {
    src: '<svg viewBox="0 0 24 24"><path d="M4 5h16M4 12h16M4 19h10"/></svg>',
    play: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
    moon: '<svg viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>',
    help: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01"/></svg>',
    refresh: '<svg viewBox="0 0 24 24"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/></svg>',
    search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>',
    info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/></svg>',
    close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    table: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/></svg>',
    dl: '<svg viewBox="0 0 24 24"><path d="M12 4v11M7 11l5 5 5-5M5 20h14"/></svg>'
  };

  function renderTop() {
    var seg = [];
    if (MODEL.story) seg.push('<button role="tab" data-prog="story" aria-selected="' + (S.prog === "story") + '">' + esc(MODEL.story.title || "The review") + "</button>");
    if (MODEL.combined) seg.push('<button role="tab" data-prog="all" aria-selected="' + (S.prog === "all") + '">All programs</button>');
    visiblePrograms().forEach(function (p) {
      var ok = p.state === "ready";
      seg.push('<button role="tab" data-prog="' + p.key + '" aria-selected="' + (S.prog === p.key) + '"' + (ok ? "" : ' title="' + esc(p.note || "") + '"') + (ok ? "" : ' style="opacity:.62"') + ">" + esc(p.label) + '<span class="dot ' + (ok ? "ok" : "") + '"></span></button>');
    });
    var c = MODEL.client;
    $("#top").innerHTML =
      '<div class="brand"><div class="mark" aria-hidden="true">' + esc((MODEL.product || "LR").split(/\s+/).map(function (w) { return w.charAt(0); }).join("").slice(0, 2)) + '</div><div class="who"><b>' + esc(c.name) + '</b><span>' + esc(MODEL.product || "") + " · " + esc(c.id) + " · " + esc(MODEL.month) + "</span></div></div>" +
      '<div class="seg grow" role="tablist" aria-label="Program">' + seg.join("") + "</div>" +
      '<div class="tools">' +
      '<button class="ibtn" id="b-src" title="Sources (S)">' + ICON.src + "<span>Sources</span></button>" +
      '<button class="ibtn" id="b-pres" title="Present (P)">' + ICON.play + "<span>Present</span></button>" +
      '<button class="ibtn" id="b-rel" title="Reload data (R)">' + ICON.refresh + "</button>" +
      '<button class="ibtn" id="b-theme" title="Light or dark (D)">' + ICON.moon + "</button>" +
      '<button class="ibtn" id="b-help" title="Keyboard (?)">' + ICON.help + "</button></div>";
  }

  function renderRail() {
    var sc = screens(), items;
    var btn = function (s, i) { return '<button data-i="' + i + '"' + (i === S.screen ? ' aria-current="page"' : "") + '><span class="n">' + (i + 1) + '</span><span class="l">' + esc(s.title) + "</span></button>"; };
    if (S.prog === "story") {   // grouped by section, numbered straight through
      var sts = storyItems(), last = -1, lastP = "";
      items = sts.map(function (x, i) {
        var h = "";
        if (x.sec.prog !== lastP) { h += '<h5 class="prod" data-p="' + esc(x.sec.prog) + '">' + esc(prodLabel(x.sec.prog)) + "</h5>"; lastP = x.sec.prog; }
        if (x.si !== last) { h += '<h6 class="sec">' + prodIndex(x.sec) + " · " + esc(x.sec.title) + "</h6>"; last = x.si; }
        return h + btn(x.scr, i);
      }).join("");
    } else items = sc.map(btn).join("");
    var rail = $("#rail");
    rail.innerHTML = '<h6>' + esc(S.prog === "story" ? (MODEL.story.title || "The review") : S.prog === "all" ? "Overview" : (curProgram() || {}).label || "") + '</h6><nav class="nav" aria-label="Screens">' + items + "</nav>";
    var nav = $(".nav", rail), cur = $('[aria-current="page"]', rail);   // on a phone the nav scrolls sideways: keep this screen in view
    if (nav && cur && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = cur.offsetLeft - nav.clientWidth / 2 + cur.offsetWidth / 2;
  }

  /* ---------- blocks ---------- */
  function tipAttr(html) { return ' data-tip="' + esc(html) + '"'; }

  function blockHTML(b, scr) {
    if (b.t === "kpis") return kpisHTML(b);
    if (b.t === "bars" || b.t === "line" || b.t === "donut" || b.t === "waterfall" || b.t === "scatter") return '<div class="card blk">' + chartHead(b) + '<div class="cbox" data-chart="' + b.id + '"></div><div class="legend" data-legend="' + b.id + '"></div></div>';
    if (b.t === "matrix") return matrixHTML(b);
    if (b.t === "table") return '<div class="card blk">' + tableCard(b) + "</div>";
    if (b.t === "variants") return variantsHTML(b, scr);
    if (b.t === "drill") return drillHTML(b);
    if (b.t === "cards") return cardsHTML(b);
    if (b.t === "statement") return b.lead ? '<p class="lede blk">' + esc(b.text) + "</p>" : '<div class="card blk"><h3>' + esc(b.title) + "</h3><p>" + esc(b.text) + "</p></div>";
    if (b.t === "peerstrip") return '<div class="card blk"><div class="head"><div class="hgrow"><h3>' + esc(b.title) + (b.month ? " · " + esc(b.month) : "") + '</h3></div></div>' + (b.sentence ? '<p class="psent">' + esc(b.sentence) + "</p>" : "") + '<div class="cbox" data-strip="' + b.id + '"></div>' +
      '<div class="legend"><span><i style="background:var(--orange)"></i>' + esc(cname()) + '</span><span><i style="background:var(--c-steel)"></i>Another client (hover for its number)</span><span><i style="background:var(--line);border:1px solid var(--axis)"></i>Middle half of peers</span><span><i style="background:var(--c-navy)"></i>Peer median</span></div></div>';
    if (b.t === "needs") return '<div class="card blk needs"><h3>Not on this client yet</h3><p>' + esc(b.what) + '</p><p class="hint">What to run first</p><code>' + esc(b.fix) + "</code></div>";
    return "";
  }

  function kpisHTML(b) {
    return '<div class="tiles blk">' + b.items.map(function (k) {
      var tag = k.go ? "button" : "div";
      return "<" + tag + ' class="tile' + (k.hot ? " hot" : "") + '"' + (k.go ? ' data-go="' + esc(k.go) + '"' : "") + '><span class="k">' + esc(k.label) + '</span><span class="v">' + esc(fmt(k.value, k.fmt)) + "</span>" + (k.sub ? '<span class="s">' + esc(k.sub) + "</span>" : "") + (k.go ? '<span class="go">→</span>' : "") + "</" + tag + ">";
    }).join("") + "</div>";
  }

  /* A chart with several measures on a switch also gets a Combined view (Aaron, 2026-11-03: "for charts like this give me a combined option"):
     measures that are rates in one unit sit side by side as they are; measures in different units (dollars, accounts, items) are each drawn as
     its share of its own total, so a tier that holds 80% of the spend but 5% of the accounts shows it. The tooltip gives the raw value. */
  var CPAL = ["navy", "orange", "steel", "teal", "gold"];
  function combinable(b) {
    return b.t === "bars" && b.metrics && b.metrics.length > 1 && b.metrics.length <= 5 && b.cats.length <= 14 &&
      b.metrics.every(function (m) { return m.series.length === 1 && m.series[0].values.every(function (v) { return v == null || v >= 0; }); });
  }
  function combinedOf(b) {
    var rates = b.metrics.every(function (m) { return /^pct/.test(m.fmt) && m.fmt === b.metrics[0].fmt; });
    var series = b.metrics.map(function (m, i) {
      var raw = m.series[0].values, tot = raw.reduce(function (a, v) { return a + (v || 0); }, 0);
      return {name: rates ? m.label : m.label + " (share of total)", color: CPAL[i % CPAL.length], raw: raw, rawFmt: m.fmt, tot: tot,
              values: rates ? raw : raw.map(function (v) { return v == null || !tot ? null : 100 * v / tot; })};
    });
    return {series: series, fmt: rates ? b.metrics[0].fmt : "pct1", key: "__all", steps: null};
  }
  function tipVal(s, i, v, f) {   // the value a bar's tooltip names: a share also says what it is a share of
    return fmt(v, f) + (s.raw && s.raw[i] != null && s.rawFmt !== f ? " (" + fmt(s.raw[i], s.rawFmt) + " of " + fmt(s.tot, s.rawFmt) + ")" : "");
  }
  function metricOf(b) {
    if (!b.metrics || !b.metrics.length) return {series: b.series, fmt: b.fmt, key: null, steps: b.steps};
    var k = S.m[b.id] || b.metrics[0].key;
    if (k === "__all" && combinable(b)) return combinedOf(b);
    var m = b.metrics.filter(function (x) { return x.key === k; })[0] || b.metrics[0];
    return {series: m.series, fmt: m.fmt, key: m.key, steps: m.steps};
  }

  var SORTS = [["desc", "Largest"], ["asc", "Smallest"], ["az", "A\u2013Z"], ["list", "Listed"]];
  function sortOf(b) { return S.bs[b.id] || (S.present && b.cats.length > 6 ? "desc" : "list"); }   // 2026-11-03: "make charts like this sortable"
  function chartHead(b) {
    var ctl = "";
    if (b.metrics && b.metrics.length > 1) {
      var cur = metricOf(b).key;
      var opts = b.metrics.map(function (m) { return [m.key, m.label]; }).concat(combinable(b) ? [["__all", "Combined"]] : []);
      ctl = '<div class="mini" role="group" aria-label="Show">' + opts.map(function (m) { return '<button data-metric="' + b.id + '" data-key="' + m[0] + '" aria-pressed="' + (m[0] === cur) + '">' + esc(m[1]) + "</button>"; }).join("") + "</div>";
    }
    if (b.t === "bars" && b.horizontal && b.cats.length > 2) {
      var how = sortOf(b);
      ctl += '<div class="mini" role="group" aria-label="Sort">' + SORTS.map(function (s) { return '<button data-bsort="' + b.id + '" data-how="' + s[0] + '" aria-pressed="' + (s[0] === how) + '">' + s[1] + "</button>"; }).join("") + "</div>";
    }
    return '<div class="head"><div class="hgrow"><h3>' + esc(b.title) + "</h3>" + (b.sub ? '<p class="sub">' + esc(b.sub) + "</p>" : "") + "</div>" + ctl + "</div>";
  }

  function drillHTML(b) {
    var c = b.chart, t = b.table;
    var sel = S.drill && S.drill.table === t.id ? S.drill.key : null;
    var row = sel ? t.rows.filter(function (r) { return r[t.key] === sel; })[0] : null;
    var det = "";
    if (row) det = '<span class="hint" style="margin:0"><b>' + esc(sel) + "</b> — " + t.columns.filter(function (cc) { return cc.fmt && cc.key !== t.key; }).slice(0, 4).map(function (cc) { return esc(cc.label) + " " + esc(fmt(row[cc.key], cc.fmt)); }).join(" · ") + "</span>";
    return '<div class="card blk">' + chartHead(c) + '<div class="cbox" data-chart="' + c.id + '"></div><div class="legend" data-legend="' + c.id + '"></div>' +
      '<div class="drillbar"><button class="btn" data-open-table="' + t.id + '">' + ICON.table + ' Open the full table <kbd>T</kbd></button>' + det + (sel ? "" : '<span class="hint" style="margin:0">Click a bar to open its row.</span>') + "</div></div>";
  }

  function variantsHTML(b, scr) {
    var cur = S.v[b.id] || b.options[0].key;
    var opt = b.options.filter(function (o) { return o.key === cur; })[0] || b.options[0];
    var ctl = '<div class="blk" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap"><span class="hint" style="margin:0;font-weight:700">' + esc(b.label) + '</span><div class="seg" role="group">' +
      b.options.map(function (o) { return '<button data-variant="' + b.id + '" data-key="' + o.key + '" aria-pressed="' + (o.key === cur) + '">' + esc(o.label) + "</button>"; }).join("") + "</div></div>";
    return ctl + opt.blocks.map(function (x) { return blockHTML(x, scr); }).join("");
  }

  function cardsHTML(b) {
    return '<div class="pcards blk">' + b.cards.map(function (c) {
      return '<button class="pcard" data-go="' + esc(c.open) + '"><span class="pl">' + esc(c.label) + "</span><p>" + esc(c.headline) + '</p><div class="mk">' +
        c.kpis.map(function (k) { return "<div><b>" + esc(fmt(k.value, k.fmt === "usd" ? "usdk" : k.fmt)) + "</b><span>" + esc(k.label) + "</span></div>"; }).join("") + "</div></button>";
    }).join("") + "</div>";
  }

  function matrixHTML(b) {
    var vals = [].concat.apply([], b.values).filter(function (v) { return typeof v === "number"; });
    var max = Math.max.apply(null, vals) || 1;
    var cells = '<div class="h"></div>' + b.cols.map(function (c) { return '<div class="h">' + esc(c) + "</div>"; }).join("");
    b.rowsl.forEach(function (r, i) {
      cells += '<div class="rh">' + esc(r) + "</div>";
      b.values[i].forEach(function (v, j) {
        if (v == null) { cells += '<div class="c na">—</div>'; return; }
        var a = 0.1 + 0.9 * (v / max);
        var dark = a > 0.5;
        cells += '<div class="c" style="background:color-mix(in srgb,var(--c-navy) ' + Math.round(a * 100) + '%,var(--surface));color:' + (dark ? "#fff" : "var(--ink)") + '"' + tipAttr("<b>" + esc(r) + " → " + esc(b.cols[j]) + "</b><br>" + esc(fmt(v, b.fmt)) + " a month") + ">" + esc(fmt(v, b.fmt)) + "</div>";
      });
    });
    return '<div class="card blk"><div class="head"><div class="hgrow"><h3>' + esc(b.title) + "</h3>" + (b.sub ? '<p class="sub">' + esc(b.sub) + "</p>" : "") + '</div></div><div class="tw"><div class="mx" style="grid-template-columns:90px repeat(' + b.cols.length + ',minmax(58px,1fr));min-width:' + (90 + b.cols.length * 62) + 'px">' + cells + "</div></div></div>";
  }

  /* ---------- tables ---------- */
  function tableState(t) {
    var s = S.sort[t.id];
    if (!s) s = t.sort ? {key: t.sort.key, dir: t.sort.dir || "desc"} : {key: null, dir: "desc"};
    return s;
  }
  function rowsFor(t) {
    var rows = t.rows.slice();
    var q = (S.q[t.id] || "").toLowerCase().trim();
    if (q) rows = rows.filter(function (r) { return String(r[t.key]).toLowerCase().indexOf(q) >= 0 || t.columns.some(function (c) { return !c.fmt && String(r[c.key] == null ? "" : r[c.key]).toLowerCase().indexOf(q) >= 0; }); });
    var s = tableState(t);
    if (s.key) {
      var d = s.dir === "asc" ? 1 : -1;
      rows.sort(function (a, b) {
        var x = a[s.key], y = b[s.key];
        if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
        return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * d;
      });
    }
    return rows;
  }
  function cellText(t, c, r) {
    var v = r[c.key];
    if (t.kind === "pnl" && c.key !== "label") return money(v, r.fmt === "ratio" ? null : r.kind) === "—" ? "—" : (r.fmt === "ratio" ? fmt(v, "ratio") : money(v, r.kind));
    return c.fmt ? fmt(v, c.fmt) : (v == null ? "—" : String(v));
  }
  function tableInner(t) {
    var s = tableState(t), rows = rowsFor(t);
    var sel = S.drill && S.drill.table === t.id ? S.drill.key : null;
    var head = t.columns.map(function (c) {
      return '<th class="' + (c.align === "right" ? "r" : "") + '" data-sort="' + c.key + '" data-table="' + t.id + '" aria-sort="' + (s.key === c.key ? (s.dir === "asc" ? "ascending" : "descending") : "none") + '">' + esc(c.label) + '<span class="ar">' + (s.key === c.key ? (s.dir === "asc" ? "▲" : "▼") : "") + "</span></th>";
    }).join("");
    var body = rows.map(function (r) {
      return '<tr data-key="' + esc(r[t.key]) + '"' + (sel != null && r[t.key] === sel ? ' class="sel ' + esc(r.kind || "") + '"' : ' class="' + esc(r.kind || "") + '"') + ">" + t.columns.map(function (c) { return '<td class="' + (c.align === "right" ? "r" : "") + '">' + esc(cellText(t, c, r)) + "</td>"; }).join("") + "</tr>";
    }).join("");
    var tot = "";
    if (t.total) tot = '<tr class="tot">' + t.columns.map(function (c) { return '<td class="' + (c.align === "right" ? "r" : "") + '">' + esc(c.fmt ? fmt(t.total[c.key], c.fmt) : (t.total[c.key] == null ? "" : t.total[c.key])) + "</td>"; }).join("") + "</tr>";
    var empty = rows.length ? "" : '<tr><td colspan="' + t.columns.length + '" class="empty">No rows match.</td></tr>';
    return '<table class="t ' + (t.kind === "pnl" ? "pnl" : "") + '"><thead><tr>' + head + "</tr></thead><tbody>" + body + empty + (rows.length ? tot : "") + "</tbody></table>";
  }
  function searchBox(t) {
    return '<label class="search">' + ICON.search + '<input type="search" data-q="' + t.id + '" placeholder="Search" aria-label="Search ' + esc(t.title) + '" value="' + esc(S.q[t.id] || "") + '"></label>';
  }
  function tableCard(t) {
    return '<div class="head"><div class="hgrow"><h3>' + esc(t.title) + "</h3>" + (t.sub ? '<p class="sub">' + esc(t.sub) + "</p>" : "") + "</div>" + (t.search && t.rows.length > 8 ? searchBox(t) : "") + '</div><div class="tw" data-twrap="' + t.id + '">' + tableInner(t) + "</div>";
  }
  function allTables() {
    var out = {};
    (function walk(bs) { bs.forEach(function (b) { if (b.t === "table") out[b.id] = b; if (b.t === "drill") out[b.table.id] = b.table; if (b.t === "variants") b.options.forEach(function (o) { walk(o.blocks); }); }); })((curScreen() || {blocks: []}).blocks);
    return out;
  }
  function drillTableOnScreen() {
    var found = null;
    (function walk(bs) { bs.forEach(function (b) { if (found) return; if (b.t === "drill") found = b.table; if (b.t === "variants") { var cur = S.v[b.id] || b.options[0].key; var o = b.options.filter(function (x) { return x.key === cur; })[0]; if (o) walk(o.blocks); } }); })((curScreen() || {blocks: []}).blocks);
    return found;
  }
  function csv(t) {
    var rows = rowsFor(t);
    var q = function (v) { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    var lines = [t.columns.map(function (c) { return q(c.label); }).join(",")];
    rows.forEach(function (r) { lines.push(t.columns.map(function (c) { return q(r[c.key]); }).join(",")); });
    if (t.total) lines.push(t.columns.map(function (c) { return q(t.total[c.key]); }).join(","));
    return lines.join("\r\n");
  }

  /* ---------- charts (SVG, drawn at the box's real width) ---------- */
  var cv = document.createElement("canvas").getContext("2d");
  function textW(s, px) { cv.font = (px || 12) + "px Carlito, Calibri, sans-serif"; return cv.measureText(s).width; }
  /* A scale whose top is a round number and whose ticks fall on round numbers (never 37.5 or 113). */
  function scaleFor(v, f) {
    var cap = f === "frac1" ? 1 : 100, isPct = /^pct|^frac/.test(f || "");
    if (!(v > 0)) return {top: 1, ticks: [0, 1]};
    if (isPct && v <= cap && v >= 0.6 * cap) return {top: cap, ticks: [0, cap * 0.25, cap * 0.5, cap * 0.75, cap]};
    var p = Math.pow(10, Math.floor(Math.log10(v / 5))), mults = [1, 2, 2.5, 5, 10, 20, 25, 50];
    for (var i = 0; i < mults.length; i++) {
      var st = mults[i] * p, n = Math.ceil(v * 1.02 / st - 1e-9);
      if (n <= 6) { var ticks = []; for (var k = 0; k <= n; k++) ticks.push(k * st); return {top: n * st, ticks: ticks}; }
    }
    return {top: v, ticks: [0, v]};
  }
  function axisLabel(v, f) {   // axis ticks drop trailing zeros: $12.5M, $40M, 75%
    if (f === "usd" || f === "usdk") { var a = Math.abs(v); return a >= 1e6 ? "$" + +(a / 1e6).toFixed(2) + "M" : a >= 1e3 ? "$" + +(a / 1e3).toFixed(1) + "K" : "$" + a; }
    if (f === "pct1" || f === "pct2" || f === "pct0") return +v.toFixed(1) + "%";
    if (f === "frac1") return +(v * 100).toFixed(0) + "%";
    if (f === "usd2") return "$" + +v.toFixed(2);
    return F.int(v);
  }

  function barsSVG(b, W) {
    var mt = metricOf(b), ser = mt.series, f = mt.fmt, cats = b.cats, n = cats.length, capped = 0;
    var fs = S.present ? 16 : 14, rowH1 = S.present ? 32 : 28;   // the branch names are read from across a room
    var how = b.horizontal ? sortOf(b) : "list", room = S.present ? Math.max(6, Math.floor((window.innerHeight - 540) / rowH1)) : n;
    if (b.horizontal && (how !== "list" || (S.present && n > room))) {   // sorted as asked; presenting, as many bars as the window holds under the title (never fewer than six), the rest one keypress away
      var val = function (i) { return b.stacked ? ser.reduce(function (a, s) { return a + (s.values[i] || 0); }, 0) : ser[0].values[i]; };
      var idx = cats.map(function (c, i) { return i; });
      if (how === "desc") idx.sort(function (x, y) { return (val(y) || 0) - (val(x) || 0); });
      else if (how === "asc") idx.sort(function (x, y) { return (typeof val(x) === "number" ? val(x) : Infinity) - (typeof val(y) === "number" ? val(y) : Infinity); });
      else if (how === "az") idx.sort(function (x, y) { return String(cats[x]).localeCompare(String(cats[y]), undefined, {numeric: true}); });
      if (S.present && n > room) { idx = idx.slice(0, room); capped = n; }
      cats = idx.map(function (i) { return cats[i]; });
      ser = ser.map(function (sr) { return {name: sr.name, color: sr.color, values: idx.map(function (i) { return sr.values[i]; })}; }); n = idx.length;
    }
    if (!n) return '<div class="empty">' + esc(b.empty || "Nothing to chart.") + "</div>";
    var stacked = b.stacked;
    var vals = [].concat.apply([], ser.map(function (s) { return s.values.filter(function (v) { return typeof v === "number"; }); }));
    var mx = stacked ? Math.max.apply(null, cats.map(function (_, i) { return ser.reduce(function (a, s) { return a + (s.values[i] || 0); }, 0); })) : Math.max.apply(null, vals);
    var sc = scaleFor(mx, f), top = sc.top;
    var clickable = !!b.drill;
    var h = [];
    if (b.horizontal) {
      var rowH = ser.length > 1 ? 14 * ser.length + 12 : rowH1, pad = {l: 0, r: 56, t: 6, b: 24};
      var lw = Math.min(W * 0.4, Math.max.apply(null, cats.map(function (c) { return textW(c, fs); })) + 14);
      pad.l = lw;
      var H = pad.t + n * rowH + pad.b, pw = W - pad.l - pad.r;
      h.push('<svg class="chart" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(b.title) + '">');
      sc.ticks.forEach(function (tv) {
        var x = pad.l + pw * tv / top;
        h.push('<line class="gl" x1="' + x + '" x2="' + x + '" y1="' + pad.t + '" y2="' + (H - pad.b) + '"/><text x="' + x + '" y="' + (H - 6) + '" text-anchor="middle">' + esc(axisLabel(tv, f)) + "</text>");
      });
      cats.forEach(function (c, i) {
        var y = pad.t + i * rowH, bh = ser.length > 1 ? 11 : (S.present ? 18 : 16);
        var sel = S.drill && S.drill.key === c && S.drill.table === (b.drill || {}).table;
        h.push('<text class="cat' + (clickable ? " click" : "") + '" data-cat="' + esc(c) + '" x="' + (pad.l - 8) + '" y="' + (y + rowH / 2 + 4) + '" text-anchor="end" style="font-size:' + fs + 'px;' + (sel ? "fill:var(--ink);font-weight:700" : "") + '">' + esc(c) + "</text>");
        ser.forEach(function (s, k) {
          var v = s.values[i]; if (typeof v !== "number") return;
          var w = Math.max(1, pw * v / top), yy = y + (rowH - ser.length * bh - (ser.length - 1) * 2) / 2 + k * (bh + 2);
          h.push('<rect class="bar grow-x' + (clickable ? " click" : "") + (sel ? " sel" : "") + '" data-cat="' + esc(c) + '" x="' + pad.l + '" y="' + yy + '" width="' + w + '" height="' + bh + '" rx="4" style="fill:' + col(s.color) + ";animation-delay:" + Math.min(i * 18, 400) + 'ms"' + tipAttr("<b>" + esc(c) + "</b><br>" + esc(s.name) + ": " + esc(tipVal(s, i, v, f))) + "/>");
          if (ser.length === 1 || k === 0) h.push('<text class="v" x="' + (pad.l + w + 6) + '" y="' + (yy + bh - 3) + '">' + esc(fmt(v, f)) + "</text>");
        });
      });
      if (capped) h.push('<text x="' + (W - 8) + '" y="' + (pad.t + 2) + '" text-anchor="end">' + {desc: "Largest ", asc: "Smallest ", az: "First ", list: "First "}[how] + n + ' of ' + capped + " · T for the table</text>");
      h.push("</svg>");
    } else {
      var rot = false, groupW0 = (W - 64) / n;
      var longest = Math.max.apply(null, cats.map(function (c) { return textW(c, 12); }));
      rot = longest > groupW0 - 4;
      var pad2 = {l: 56, r: 8, t: 22, b: rot ? Math.min(78, longest * 0.72 + 14) : 28}, H2 = S.present ? 250 : 300;
      var ph = H2 - pad2.t - pad2.b, pw2 = W - pad2.l - pad2.r, gw = pw2 / n;
      h.push('<svg class="chart" width="' + W + '" height="' + H2 + '" viewBox="0 0 ' + W + " " + H2 + '" role="img" aria-label="' + esc(b.title) + '">');
      sc.ticks.forEach(function (tv) {
        var y = pad2.t + ph * (1 - tv / top);
        h.push('<line class="' + (tv === 0 ? "ax" : "gl") + '" x1="' + pad2.l + '" x2="' + (W - pad2.r) + '" y1="' + y + '" y2="' + y + '"/><text x="' + (pad2.l - 8) + '" y="' + (y + 4) + '" text-anchor="end">' + esc(axisLabel(tv, f)) + "</text>");
      });
      var every = Math.ceil((rot ? 13 : longest + 8) / gw);
      var sw = Math.max(6, Math.min(54, (gw * 0.72) / (stacked ? 1 : ser.length)));
      var showVals = n * (stacked ? 1 : ser.length) <= 16 && sw >= 18;
      cats.forEach(function (c, i) {
        var cx = pad2.l + gw * i + gw / 2, acc = 0;
        var isHi = b.highlight === i;
        ser.forEach(function (s, k) {
          var v = s.values[i]; if (typeof v !== "number") return;
          var bh = Math.max(1, ph * v / top);
          var x = stacked ? cx - sw / 2 : cx - (ser.length * sw) / 2 + k * sw;
          var y = stacked ? pad2.t + ph - ph * (acc + v) / top : pad2.t + ph - bh;
          acc += v;
          var fill = isHi && ser.length === 1 ? "var(--orange)" : col(s.color);
          var sel = S.drill && S.drill.key === c && S.drill.table === (b.drill || {}).table;
          h.push('<rect class="bar grow-y' + (clickable ? " click" : "") + (sel ? " sel" : "") + '" data-cat="' + esc(c) + '" x="' + x + '" y="' + y + '" width="' + (sw - (stacked ? 0 : 2)) + '" height="' + bh + '" rx="' + Math.min(5, sw / 3) + '" style="fill:' + fill + ";animation-delay:" + Math.min(i * 22, 420) + 'ms"' + tipAttr("<b>" + esc(c) + "</b><br>" + esc(s.name) + ": " + esc(tipVal(s, i, v, f))) + "/>");
          if (showVals && (!stacked || k === ser.length - 1)) h.push('<text class="v" x="' + (stacked ? cx : x + (sw - 2) / 2) + '" y="' + (y - 5) + '" text-anchor="middle">' + esc(fmt(stacked ? acc : v, f)) + "</text>");
        });
        if (i % every === 0 || i === n - 1) {
          if (rot) h.push('<text class="cat' + (clickable ? " click" : "") + '" data-cat="' + esc(c) + '" transform="translate(' + cx + "," + (H2 - pad2.b + 14) + ') rotate(-38)" text-anchor="end">' + esc(c) + "</text>");
          else h.push('<text class="cat' + (clickable ? " click" : "") + '" data-cat="' + esc(c) + '" x="' + cx + '" y="' + (H2 - 8) + '" text-anchor="middle">' + esc(c) + "</text>");
        }
      });
      h.push("</svg>");
    }
    return h.join("");
  }

  function lineSVG(b, W) {
    var ser = b.series, cats = b.cats, n = cats.length, f = b.fmt;
    if (!n) return '<div class="empty">' + esc(b.empty || "Nothing to chart.") + "</div>";
    var vals = [].concat.apply([], ser.map(function (s) { return s.values.filter(function (v) { return typeof v === "number"; }); }));
    var sc = scaleFor(Math.max.apply(null, vals), f), top = sc.top, pad = {l: 56, r: 12, t: 16, b: 30}, H = 280;
    var pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    var X = function (i) { return pad.l + (n === 1 ? pw / 2 : pw * i / (n - 1)); }, Y = function (v) { return pad.t + ph * (1 - v / top); };
    var h = ['<svg class="chart" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(b.title) + '">'];
    sc.ticks.forEach(function (tv) {
      var y = pad.t + ph * (1 - tv / top);
      h.push('<line class="' + (tv === 0 ? "ax" : "gl") + '" x1="' + pad.l + '" x2="' + (W - pad.r) + '" y1="' + y + '" y2="' + y + '"/><text x="' + (pad.l - 8) + '" y="' + (y + 4) + '" text-anchor="end">' + esc(axisLabel(tv, f)) + "</text>");
    });
    var every = Math.ceil(46 / (pw / Math.max(1, n - 1)));
    cats.forEach(function (c, i) { if (i % every === 0 || i === n - 1) h.push('<text x="' + X(i) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(c) + "</text>"); });
    ser.forEach(function (s) {
      var d = "", pen = false;
      s.values.forEach(function (v, i) { if (typeof v !== "number") { pen = false; return; } d += (pen ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1); pen = true; });
      h.push('<path d="' + d + '" fill="none" style="stroke:' + col(s.color) + ';stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round"/>');
      s.values.forEach(function (v, i) {
        if (typeof v !== "number") { h.push('<line x1="' + X(i) + '" x2="' + X(i) + '" y1="' + pad.t + '" y2="' + (H - pad.b) + '" style="stroke:var(--axis);stroke-dasharray:3 4"/><text x="' + X(i) + '" y="' + (pad.t + 10) + '" text-anchor="middle" style="fill:var(--warn);font-size:11px">left out</text>'); return; }
        h.push('<circle cx="' + X(i) + '" cy="' + Y(v) + '" r="' + (n > 28 ? 2.5 : 3.6) + '" style="fill:var(--surface);stroke:' + col(s.color) + ';stroke-width:2"' + tipAttr("<b>" + esc(cats[i]) + "</b><br>" + esc(s.name) + ": " + esc(tipVal(s, i, v, f))) + "/>");
      });
    });
    h.push("</svg>");
    return h.join("");
  }

  /* One metric against the peers: every other client is a dot (its value; the hover gives its client number, nothing else), the middle half is a band,
     the median a tick, and this client is the large orange dot. Nothing here carries a name or an id: the model has none. */
  function stripSVG(b, W) {
    var pad = {l: 16, r: 16, t: 34, b: 34}, H = 170, vals = b.dots.concat([b.client]);
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), span = (hi - lo) || 1;
    lo -= span * 0.06; hi += span * 0.06;
    var X = function (v) { return pad.l + (W - pad.l - pad.r) * (v - lo) / (hi - lo); }, base = H - pad.b, mid = pad.t + (base - pad.t) / 2;
    var h = ['<svg class="chart" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(b.title) + ': ' + esc(cname()) + ' against ' + b.n + ' anonymous peers">'];
    h.push('<rect x="' + X(b.q1) + '" y="' + (pad.t + 6) + '" width="' + Math.max(2, X(b.q3) - X(b.q1)) + '" height="' + (base - pad.t - 12) + '" rx="8" style="fill:var(--line);stroke:var(--axis);stroke-width:1"' + tipAttr("Middle half of peers: " + fmt(b.q1, b.fmt) + " to " + fmt(b.q3, b.fmt)) + "/>");
    h.push('<line x1="' + pad.l + '" x2="' + (W - pad.r) + '" y1="' + base + '" y2="' + base + '" class="ax"/>');
    for (var k = 0; k <= 4; k++) { var v = lo + (hi - lo) * k / 4; h.push('<text x="' + X(v) + '" y="' + (H - 10) + '" text-anchor="' + (k === 0 ? "start" : k === 4 ? "end" : "middle") + '">' + esc(fmt(v, b.fmt)) + "</text>"); }
    h.push('<line x1="' + X(b.median) + '" x2="' + X(b.median) + '" y1="' + (pad.t + 2) + '" y2="' + (base) + '" style="stroke:var(--c-navy);stroke-width:2.5"' + tipAttr("Peer median: " + fmt(b.median, b.fmt)) + "/>");
    h.push('<text x="' + X(b.median) + '" y="' + (pad.t - 4) + '" text-anchor="middle" style="font-weight:700;fill:var(--ink)">Median ' + esc(fmt(b.median, b.fmt)) + "</text>");
    b.dots.forEach(function (v, i) {   // a fixed spread of heights so dots do not hide each other; the order carries nothing
      var y = mid + (((i * 37) % 7) - 3) * 8;
      h.push('<circle cx="' + X(v) + '" cy="' + y + '" r="6" class="peerdot grow-y" style="fill:var(--c-steel);fill-opacity:.82;stroke:var(--surface);stroke-width:1.5;animation-delay:' + Math.min(i * 12, 360) + 'ms"' + tipAttr((b.dot_ids && b.dot_ids[i] ? "Client " + b.dot_ids[i] : "Another client") + ": " + fmt(v, b.fmt)) + "/>");
    });
    h.push('<circle cx="' + X(b.client) + '" cy="' + mid + '" r="11" style="fill:var(--orange);stroke:var(--surface);stroke-width:3"' + tipAttr(cname() + ": " + fmt(b.client, b.fmt)) + "/>");
    var me = cname() + " " + fmt(b.client, b.fmt), meW = textW(me, 13) / 2 + 6;
    h.push('<text x="' + X(b.client) + '" y="' + (mid - 20) + '" text-anchor="' + (X(b.client) + meW > W ? "end" : X(b.client) - meW < 0 ? "start" : "middle") + '" style="font-weight:700;fill:var(--orange-ink)">' + esc(me) + "</text>");
    h.push("</svg>");
    return h.join("");
  }

  /* ---------- more chart types (Aaron, 2026-11-03: "I'd like to see more chart types in LR too") ---------- */
  var PAL = ["navy", "orange", "steel", "teal", "gold", "tick"];
  function emptyBox(b) { return '<div class="empty">' + esc(b.empty || "Nothing to chart.") + "</div>"; }
  function arcPath(cx, cy, r0, r1, a0, a1) {
    var big = a1 - a0 > Math.PI ? 1 : 0;
    var X = function (r, a) { return (cx + r * Math.cos(a)).toFixed(2); }, Y = function (r, a) { return (cy + r * Math.sin(a)).toFixed(2); };
    return "M" + X(r1, a0) + " " + Y(r1, a0) + "A" + r1 + " " + r1 + " 0 " + big + " 1 " + X(r1, a1) + " " + Y(r1, a1) +
      "L" + X(r0, a1) + " " + Y(r0, a1) + "A" + r0 + " " + r0 + " 0 " + big + " 0 " + X(r0, a0) + " " + Y(r0, a0) + "Z";
  }
  /* A whole split into parts: the ring on one side, each part with its value and its share on the other. */
  function donutSVG(b, W) {
    var f = b.fmt, items = b.cats.map(function (c, i) { return {c: c, v: b.values[i]}; }).filter(function (d) { return typeof d.v === "number" && d.v > 0; });
    var tot = items.reduce(function (a, d) { return a + d.v; }, 0);
    if (!(tot > 0)) return emptyBox(b);
    var fs = S.present ? 16 : 14, row = S.present ? 32 : 28, side = W >= 480;
    var D = side ? Math.min(250, W * 0.4) : Math.min(230, W - 20), R = D / 2, r = R * 0.62;
    var legH = items.length * row, H = side ? Math.max(D + 16, legH + 16) : D + 24 + legH;
    var cx = side ? R + 8 : W / 2, cy = R + 8;
    var h = ['<svg class="chart" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(b.title) + '">'];
    var a = -Math.PI / 2, gap = items.length > 1 ? 0.014 : 0;
    items.forEach(function (d, k) {
      var sweep = d.v / tot * Math.PI * 2, a0 = a + gap / 2, a1 = a + sweep - gap / 2; a += sweep;
      var tip = tipAttr(d.c + ": " + fmt(d.v, f) + " (" + (100 * d.v / tot).toFixed(1) + "%)"), color = col(PAL[k % PAL.length]);
      if (items.length === 1) h.push('<circle cx="' + cx + '" cy="' + cy + '" r="' + ((R + r) / 2) + '" fill="none" stroke="' + color + '" stroke-width="' + (R - r) + '"' + tip + "/>");
      else h.push('<path class="slice" d="' + arcPath(cx, cy, r, R, a0, a1) + '" style="fill:' + color + '"' + tip + "/>");
    });
    h.push('<text class="v" x="' + cx + '" y="' + (cy + 2) + '" text-anchor="middle" style="font-size:' + (S.present ? 28 : 22) + 'px">' + esc(fmt(tot, f)) + "</text>");
    h.push('<text x="' + cx + '" y="' + (cy + (S.present ? 24 : 20)) + '" text-anchor="middle">' + esc(b.center || "Total") + "</text>");
    var lx = side ? D + 30 : 8, ly = side ? (H - legH) / 2 + row / 2 : D + 24 + row / 2, vx = side ? lx + Math.min(440, W - D - 60) : W - 8;
    items.forEach(function (d, k) {
      var y = ly + k * row;
      h.push('<rect x="' + lx + '" y="' + (y - 10) + '" width="12" height="12" rx="3" style="fill:' + col(PAL[k % PAL.length]) + '"/>');
      h.push('<text x="' + (lx + 20) + '" y="' + (y + 1) + '" style="font-size:' + fs + 'px">' + esc(d.c) + "</text>");
      h.push('<text class="v" x="' + vx + '" y="' + (y + 1) + '" text-anchor="end" style="font-size:' + fs + 'px">' + esc(fmt(d.v, f)) + " · " + (100 * d.v / tot).toFixed(1) + "%</text>");
    });
    h.push("</svg>");
    return h.join("");
  }
  /* A running total built up or down in steps: totals stand on the baseline, a cost steps down from the line before it. */
  function waterfallSVG(b, W) {
    var mt = metricOf(b), steps = (mt.steps || b.steps || []), f = b.fmt;
    if (!steps.length) return emptyBox(b);
    var run = 0, bars = steps.map(function (s) {
      var lo, hi;
      if (s.kind === "total") { lo = Math.min(0, s.value); hi = Math.max(0, s.value); run = s.value; }
      else { var to = run + s.value; lo = Math.min(run, to); hi = Math.max(run, to); run = to; }
      return {s: s, lo: lo, hi: hi, end: run};
    });
    var mx = Math.max.apply(null, bars.map(function (x) { return x.hi; })), mn = Math.min.apply(null, bars.map(function (x) { return x.lo; })), neg = mn < 0;
    var sc = scaleFor(Math.max(mx, neg ? -mn : 0, 1), f), top = sc.top, lo0 = neg ? -top : 0;
    var longest = Math.max.apply(null, bars.map(function (x) { return textW(x.s.label, 12); }));
    var pw0 = W - 64, gw0 = pw0 / bars.length, rot = longest > gw0 - 6;
    var pad = {l: 56, r: 8, t: 24, b: rot ? Math.min(80, longest * 0.62 + 16) : 30}, H = S.present ? 260 : 300;
    var ph = H - pad.t - pad.b, pw = W - pad.l - pad.r, gw = pw / bars.length, bw = Math.max(14, Math.min(72, gw * 0.62));
    var py = function (v) { return pad.t + ph * (top - v) / (top - lo0); };
    var h = ['<svg class="chart" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(b.title) + '">'];
    var ticks = neg ? sc.ticks.concat(sc.ticks.slice(1).map(function (t) { return -t; })) : sc.ticks;
    ticks.forEach(function (tv) {
      var y = py(tv);
      h.push('<line class="' + (tv === 0 ? "ax" : "gl") + '" x1="' + pad.l + '" x2="' + (W - pad.r) + '" y1="' + y + '" y2="' + y + '"/><text x="' + (pad.l - 8) + '" y="' + (y + 4) + '" text-anchor="end">' + esc(axisLabel(tv, f)) + "</text>");
    });
    bars.forEach(function (x, i) {
      var cx = pad.l + gw * i + gw / 2, x0 = cx - bw / 2, up = x.s.kind !== "total" && x.s.value > 0, down = x.s.kind !== "total" && x.s.value < 0;
      var color = x.s.kind === "total" ? (x.s.value < 0 ? "var(--c-orange)" : "var(--c-navy)") : down ? "var(--c-orange)" : "var(--c-teal)";
      var y1 = py(x.hi), y2 = py(x.lo), hh = Math.max(1.5, y2 - y1);
      var label = x.s.kind === "total" ? fmt(x.s.value, f) : (down ? "\u2212" : "+") + fmt(Math.abs(x.s.value), f);
      var tip = tipAttr(x.s.label + ": " + label + (x.s.kind === "total" ? "" : " \u2192 " + fmt(x.end, f)));
      h.push('<rect class="bar" x="' + x0 + '" y="' + y1 + '" width="' + bw + '" height="' + hh + '" rx="3" style="fill:' + color + '"' + tip + "/>");
      if (i < bars.length - 1) h.push('<line class="gl" x1="' + (x0 + bw) + '" x2="' + (pad.l + gw * (i + 1) + gw / 2 - bw / 2) + '" y1="' + py(x.end) + '" y2="' + py(x.end) + '" style="stroke-dasharray:3 3"/>');
      h.push('<text class="v" x="' + cx + '" y="' + (x.s.kind !== "total" && down ? y2 + 15 : y1 - 6) + '" text-anchor="middle">' + esc(label) + "</text>");
      if (rot) h.push('<text transform="translate(' + cx + "," + (H - pad.b + 14) + ') rotate(-30)" text-anchor="end">' + esc(x.s.label) + "</text>");
      else h.push('<text x="' + cx + '" y="' + (H - 10) + '" text-anchor="middle">' + esc(x.s.label) + "</text>");
    });
    h.push("</svg>");
    return h.join("");
  }
  function niceTicks(lo, hi, n) {
    var span = hi - lo || 1, raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
    var step = (m < 1.5 ? 1 : m < 3 ? 2 : m < 7 ? 5 : 10) * p, a = Math.floor(lo / step) * step, t = [];
    for (var v = a; ; v += step) { t.push(+v.toFixed(10)); if (v >= hi - step * 0.001) break; }
    return t;
  }
  function median(a) { var s = a.slice().sort(function (x, y) { return x - y; }), k = s.length >> 1; return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2; }
  /* Points on two measures, sized by a third; the medians cross, and the corner below both is shaded: the branches to coach. */
  function scatterSVG(b, W) {
    var pts = (b.points || []).filter(function (p) { return isFinite(p.x) && isFinite(p.y); });
    if (pts.length < 3) return emptyBox(b);
    var H = S.present ? 340 : 400, pad = {l: 60, r: 18, t: 26, b: 48}, pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    var xs = pts.map(function (p) { return p.x; }), ys = pts.map(function (p) { return p.y; });
    var dx = (Math.max.apply(null, xs) - Math.min.apply(null, xs)) * 0.08 || 1, dy = (Math.max.apply(null, ys) - Math.min.apply(null, ys)) * 0.08 || 1;
    var dom = function (a, d, f) {   // padded, but a measure that is never negative gets no negative axis, and a percentage stops at 100
      var lo = Math.min.apply(null, a), hi = Math.max.apply(null, a);
      lo = lo >= 0 ? Math.max(0, lo - d) : lo - d; hi = /^pct/.test(f || "") ? Math.min(100, hi + d) : hi + d;
      return niceTicks(lo, hi, 5);
    };
    var xt = dom(xs, dx, b.xfmt), yt = dom(ys, dy, b.yfmt);
    var x0 = xt[0], x1 = xt[xt.length - 1], y0 = yt[0], y1 = yt[yt.length - 1];
    var px = function (v) { return pad.l + pw * (v - x0) / (x1 - x0); }, py = function (v) { return pad.t + ph * (1 - (v - y0) / (y1 - y0)); };
    var mx = median(xs), my = median(ys);
    var sz = pts.map(function (p) { return p.size || 0; }), smin = Math.min.apply(null, sz), smax = Math.max.apply(null, sz);
    var rad = function (p) { return smax > smin ? 5 + 13 * Math.sqrt(((p.size || 0) - smin) / (smax - smin)) : 8; };
    var h = ['<svg class="chart" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(b.title) + '">'];
    if (b.quad) h.push('<rect class="quad" x="' + pad.l + '" y="' + py(my) + '" width="' + (px(mx) - pad.l) + '" height="' + (pad.t + ph - py(my)) + '"/>');
    xt.forEach(function (v) { var x = px(v); h.push('<line class="gl" x1="' + x + '" x2="' + x + '" y1="' + pad.t + '" y2="' + (pad.t + ph) + '"/><text x="' + x + '" y="' + (H - 28) + '" text-anchor="middle">' + esc(axisLabel(v, b.xfmt)) + "</text>"); });
    yt.forEach(function (v) { var y = py(v); h.push('<line class="gl" x1="' + pad.l + '" x2="' + (W - pad.r) + '" y1="' + y + '" y2="' + y + '"/><text x="' + (pad.l - 8) + '" y="' + (y + 4) + '" text-anchor="end">' + esc(axisLabel(v, b.yfmt)) + "</text>"); });
    h.push('<line class="med" x1="' + px(mx) + '" x2="' + px(mx) + '" y1="' + pad.t + '" y2="' + (pad.t + ph) + '"/><line class="med" x1="' + pad.l + '" x2="' + (W - pad.r) + '" y1="' + py(my) + '" y2="' + py(my) + '"/>');
    h.push('<text x="' + (px(mx) + 4) + '" y="' + (pad.t + 11) + '" style="font-size:11.5px">median ' + esc(fmt(mx, b.xfmt)) + '</text><text x="' + (pad.l + 4) + '" y="' + (py(my) - 5) + '" style="font-size:11.5px">median ' + esc(fmt(my, b.yfmt)) + "</text>");
    h.push('<text x="' + (pad.l + pw / 2) + '" y="' + (H - 8) + '" text-anchor="middle" class="v">' + esc(b.xlabel) + '</text><text x="' + pad.l + '" y="' + (pad.t - 10) + '" class="v">\u2191 ' + esc(b.ylabel) + "</text>");
    var order = pts.slice().sort(function (p, q) { return (q.size || 0) - (p.size || 0); }), placed = [];
    order.forEach(function (p) {
      var low = p.x < mx && p.y < my, r = rad(p);
      var tip = tipAttr(p.name + " \u00b7 " + b.xlabel + " " + fmt(p.x, b.xfmt) + " \u00b7 " + b.ylabel + " " + fmt(p.y, b.yfmt) + (p.size ? " \u00b7 " + fmt(p.size, b.sfmt) + " " + b.slabel : ""));
      h.push('<circle class="pt" cx="' + px(p.x) + '" cy="' + py(p.y) + '" r="' + r + '" style="fill:' + (low && b.quad ? "var(--c-orange)" : "var(--c-navy)") + '"' + tip + "/>");
    });
    order.slice(0, 16).forEach(function (p) {   // the larger points are named; a name that would sit on another is left to its tooltip
      var r = rad(p), w = textW(p.name, 12), right = px(p.x) + r + 4 + w < W - pad.r, x = right ? px(p.x) + r + 4 : px(p.x) - r - 4 - w, y = py(p.y) + 4;
      var box = {x: x, y: y - 11, w: w, h: 13};
      if (placed.some(function (q) { return box.x < q.x + q.w && q.x < box.x + box.w && box.y < q.y + q.h && q.y < box.y + box.h; })) return;
      placed.push(box);
      h.push('<text x="' + x + '" y="' + y + '" style="font-size:12px">' + esc(p.name) + "</text>");
    });
    h.push("</svg>");
    return h.join("");
  }

  function drawCharts() {
    var all = {};
    var strips = {};
    (function walk(bs) { bs.forEach(function (b) { if (b.t === "peerstrip") strips[b.id] = b; if (b.t === "bars" || b.t === "line" || b.t === "donut" || b.t === "waterfall" || b.t === "scatter") all[b.id] = b; if (b.t === "drill") all[b.chart.id] = b.chart; if (b.t === "variants") { var cur = S.v[b.id] || b.options[0].key; var o = b.options.filter(function (x) { return x.key === cur; })[0]; if (o) walk(o.blocks); } }); })((curScreen() || {blocks: []}).blocks);
    $$("[data-strip]").forEach(function (el) { var b = strips[el.getAttribute("data-strip")]; if (b) el.innerHTML = stripSVG(b, Math.max(280, Math.floor(el.clientWidth))); });
    $$(".cbox").forEach(function (el) {
      var b = all[el.getAttribute("data-chart")]; if (!b) return;
      var W = Math.max(280, Math.floor(el.clientWidth));
      el.innerHTML = ({line: lineSVG, donut: donutSVG, waterfall: waterfallSVG, scatter: scatterSVG}[b.t] || barsSVG)(b, W);
      var lg = $('[data-legend="' + b.id + '"]');
      var ser = b.t === "line" ? b.series : b.t === "bars" ? metricOf(b).series : [];
      if (lg) lg.innerHTML = ser.length > 1 ? ser.map(function (s) { return '<span><i style="background:' + col(s.color) + '"></i>' + esc(s.name) + "</span>"; }).join("") : "";
    });
  }

  /* ---------- screen ---------- */
  /* The storyline's progress: one segment per section, filled up to this one, and where we are inside it. */
  function storyBar() {
    var it = curStory(); if (!it) return "";
    var secs = prodSections(it.sec.prog), n = secs.length, at = prodIndex(it.sec);
    var segs = secs.map(function (sec, i) { return '<i class="' + (i < at - 1 ? "done" : i === at - 1 ? "now" : "") + '" title="' + esc(sec.title) + '"></i>'; }).join("");
    var tag = '<span class="ptag" data-p="' + esc(it.prog) + '">' + esc(prodLabel(it.prog)) + "</span>";
    return '<div class="storybar" role="img" aria-label="' + esc(prodLabel(it.prog)) + ", section " + at + " of " + n + '">' + tag + '<div class="segs">' + segs + '</div><span><b>' + esc(it.sec.title) + "</b> · section " + at + " of " + n + " · screen " + (it.ri + 1) + " of " + it.sec.screens.length + " · <kbd>A</kbd> agenda</span></div>";
  }

  /* Presenting (windowed, shared in a call at 1280x720): the finding as the headline, the tiles, ONE chart and the first so-what line.
     The rest of the screen (tables, further charts, the other notes) is one keypress away, never on the slide. */
  function presentBlocks(blocks, sid) {
    if (sid === "compare") {   // the combined "How you compare": one chart per product while presenting, all of them in the regular view
      var firsts = blocks.filter(function (b) { return b.t === "peerstrip" && b.first; });
      if (firsts.length) return firsts;
    }
    var kp = blocks.filter(function (b) { return b.t === "kpis"; })[0], main = blocks.filter(function (b) { return b.t !== "kpis" && !(b.t === "statement" && b.lead); })[0];
    var out = [];
    if (main && main.t === "variants") {   // keep the control, and only each option's first real block (its chart)
      main = Object.assign({}, main, {options: main.options.map(function (o) { return Object.assign({}, o, {blocks: o.blocks.filter(function (x) { return !(x.t === "statement" && x.lead); }).slice(0, 1)}); })});
    }
    if (kp && (!main || sid === "summary")) out.push({t: "kpis", items: kp.items.slice(0, 4)});   // tiles are the slide only where there is no chart, or on a summary
    if (main) out.push(main);
    return out.length ? out : blocks;
  }

  function render(keepScroll) {
    var sc = curScreen(), main = $("#stage");
    $("#tip").classList.remove("on");   // the mouse has not moved, so nothing else would clear a tooltip over bars that just went away
    renderTop(); renderRail();
    var html;
    if (S.prog !== "all" && curProgram() && curProgram().state !== "ready") {
      var p = curProgram();
      html = '<section class="screen"><p class="eyebrow">' + esc(p.label) + '</p><h1>' + esc(p.label) + ' is not on the page yet</h1><div class="card"><div class="empty">' + esc(p.note || "") + (p.fix ? "<code>" + esc(p.fix) + "</code>" : "") + "</div></div></section>";
    } else if (!sc) {
      html = '<section class="screen"><h1>Nothing to show</h1></section>';
    } else {
      html = '<section class="screen' + (S.plain ? " " : "") + '" style="' + (S.plain ? "animation:none" : "") + '">' + storyBar() + '<p class="eyebrow">' + esc(sc.kicker) + "</p><h1>" + esc(sc.headline) + "</h1>" +
        ((S.present ? sc.notes.slice(0, 1) : sc.notes) && (S.present ? sc.notes.slice(0, 1) : sc.notes).length ? '<div class="notes">' + (S.present ? sc.notes.slice(0, 1) : sc.notes).map(function (n) { return '<div class="note">' + ICON.info + "<span>" + esc(n) + "</span></div>"; }).join("") + "</div>" : "") +
        '<div class="blocks">' + (S.present ? presentBlocks(sc.blocks, sc.id) : sc.blocks).map(function (b) { return blockHTML(b, sc); }).join("") + "</div>" +
        '<p class="stamp">Data pack read ' + esc(MODEL.generated.replace("T", " ")) + " · sources on every screen (S)</p></section>";
    }
    var pk = progNow();
    document.documentElement.setAttribute("data-product", pk || "")   // not data-prog: the click handler reads that one as "go to this program";
    if (S.lastFam && pk && pk !== S.lastFam && S.prog === "story" && S.present) showProgramCard(pk);   // presenting only (Aaron, 2026-11-03)
    S.lastFam = pk || S.lastFam;
    main.innerHTML = html;
    main.classList.toggle("still", !!S.plain);   // bars draw in once, when a screen first appears; opening or closing a table must not replay them
    S.plain = false;
    drawCharts();
    renderFoot();
    writeHash();
    document.title = (MODEL.client.name || "") + " · " + (MODEL.product || "");
  }
  function renderFoot() {
    var n = screens().length;
    var dots = ""; for (var i = 0; i < n; i++) dots += '<i class="' + (i === S.screen ? "on" : "") + '"></i>';
    var sc = curScreen();
    $("#foot").innerHTML = '<button class="ibtn" data-step="-1" aria-label="Previous">←</button><span class="lbl">' + esc(sc ? sc.title : "") + '</span><div class="dots">' + dots + '</div><button class="ibtn" data-step="1" aria-label="Next">→</button><button class="ibtn" data-exit>' + ICON.close + "</button>";
  }

  /* ---------- panels ---------- */
  function openPanel(kind, id) {
    S.panel = kind; S.tableId = id || null;
    var el = $("#panel"), sc = curScreen(), html = "";
    el.classList.toggle("wide", kind === "table");
    if (kind === "sources") {
      var srcs = (sc && sc.sources) || [];
      html = '<header><h2>Sources for this screen</h2><button class="ibtn" data-close aria-label="Close">' + ICON.close + '</button></header><div class="body">' +
        (srcs.length ? srcs.map(function (s) { return '<div class="src"><b>' + esc(s.title) + "</b><p>" + esc(s.text) + "</p>" + (s.composed ? '<span class="tag">Composed from the pack: no deck was found beside it to copy the slide’s note from.</span>' : "") + "</div>"; }).join("") : '<div class="empty">This screen has no source lines of its own.</div>') +
        '<p class="hint">These are the speaker-note lines of the deck slides this screen mirrors. The figures come from the same data pack the deck was built from, read ' + esc(MODEL.generated.replace("T", " ")) + ".</p></div>";
    } else if (kind === "agenda") {
      var cur = curStory(), its = storyItems();
      html = '<header><h2>The agenda</h2><button class="ibtn" data-close aria-label="Close">' + ICON.close + '</button></header><div class="body agenda">' +
        MODEL.story.sections.map(function (sec, si, all) {
          var ph = si === 0 || all[si - 1].prog !== sec.prog ? '<h5 class="prod" data-p="' + esc(sec.prog) + '">' + esc(prodLabel(sec.prog)) + "</h5>" : "";
          return ph + '<div class="asec"><h4><span class="n">' + prodIndex(sec) + "</span>" + esc(sec.title) + "</h4><p>" + esc(sec.blurb) + "</p>" +
            sec.screens.map(function (r) {
              var at = its.filter(function (x) { return x.ref === r.ref; })[0];
              return '<button data-agenda="' + esc(r.ref) + '"' + (cur && cur.ref === r.ref ? ' aria-current="page"' : "") + (r.stub ? ' class="stub"' : "") + ">" + esc(r.title) + (r.stub ? "<em>run first</em>" : "") + "</button>";
            }).join("") + "</div>";
        }).join("") + "</div>";
    } else if (kind === "help") {
      html = '<header><h2>Keyboard</h2><button class="ibtn" data-close aria-label="Close">' + ICON.close + '</button></header><div class="body help"><dl>' +
        [["← →", "Previous / next screen, on into the next program"], ["1 – 9", "Jump to a screen"], ["[ ]", "Previous / next program"], ["T", "Open the full table behind the chart"], ["/", "Search the table"], ["A", "The agenda: every section of the review"], ["S", "Sources for this screen"], ["P", "Present: chrome out, type up"], ["D", "Light or dark"], ["R", "Reload the data pack"], ["Esc", "Close a panel, leave presenter"]]
          .map(function (r) { return "<dt><kbd>" + r[0] + "</kbd></dt><dd>" + r[1] + "</dd>"; }).join("") + "</dl></div>";
    } else if (kind === "table") {
      var t = allTables()[id];
      if (!t) return;
      html = '<header><h2>' + esc(t.title) + '</h2><button class="ibtn" data-csv="' + t.id + '" title="Save as CSV">' + ICON.dl + "<span>CSV</span></button><button class=\"ibtn\" data-close aria-label=\"Close\">" + ICON.close + '</button></header><div class="body tbl">' +
        '<div class="head"><div class="hgrow">' + (t.sub ? '<p class="sub" style="margin:0">' + esc(t.sub) + "</p>" : "") + "</div>" + searchBox(t) + '</div><div class="tw" data-twrap="' + t.id + '">' + tableInner(t) + "</div></div>";
    }
    el.innerHTML = html; el.classList.add("on"); $("#scrim").classList.add("on");
    el.setAttribute("aria-hidden", "false");
    if (kind === "table") {
      var sel = $("tr.sel", el), tw = $(".tw", el);   // centre the row inside the table's own scroll, below its sticky header
      var centre = function () { if (sel && tw && sel.isConnected) tw.scrollTop = Math.max(0, sel.offsetTop - tw.clientHeight / 2 + sel.offsetHeight / 2); };
      centre(); setTimeout(centre, 380);   // again once the panel has finished sliding in and the table has its final height
      var q = $("[data-q]", el); if (q && S.focusSearch) { q.focus(); S.focusSearch = false; }
    }
  }
  function closePanel() {
    S.panel = null; $("#panel").classList.remove("on"); $("#scrim").classList.remove("on"); $("#panel").setAttribute("aria-hidden", "true");
    if (S.drill) { S.drill = null; S.plain = true; var y = window.scrollY; render(); window.scrollTo({top: y}); }   // the bar picked to open a row stops being highlighted once the table slides back out
  }
  function refreshTables() {
    $$("[data-twrap]").forEach(function (w) {
      var t = allTables()[w.getAttribute("data-twrap")]; if (t) w.innerHTML = tableInner(t);
    });
  }

  /* ---------- toast + tooltip ---------- */
  var toastT;
  function toast(msg) { var el = $("#toast"); el.textContent = msg; el.classList.add("on"); clearTimeout(toastT); toastT = setTimeout(function () { el.classList.remove("on"); }, 2200); }
  function tip(e) {
    var el = $("#tip"), t = e.target.closest ? e.target.closest("[data-tip]") : null;
    if (!t) { el.classList.remove("on"); return; }
    el.innerHTML = t.getAttribute("data-tip"); el.classList.add("on");
    var w = el.offsetWidth, x = Math.min(window.innerWidth - w - 10, e.clientX + 14);
    el.style.left = Math.max(8, x) + "px"; el.style.top = Math.max(8, e.clientY - el.offsetHeight - 14) + "px";
  }

  /* ---------- data reload ---------- */
  function reload() {
    toast("Reading the data pack…");
    fetch("/api/model", {headers: {"X-Token": TOKEN}}).then(function (r) { return r.json().then(function (j) { return {ok: r.ok, j: j}; }); }).then(function (x) {
      if (!x.ok) { toast(x.j.error || "Could not reload"); return; }
      MODEL = x.j; S.plain = true; readHashKeep(); render(); toast("Data reloaded");
    }).catch(function () { toast("The server is not answering"); });
  }
  function readHashKeep() { var p = S.prog, s = S.screen; if (!programs().some(function (x) { return x.key === p; }) && p !== "all") readHash(); else S.screen = Math.min(s, Math.max(0, screens().length - 1)); }

  /* ---------- events ---------- */
  document.addEventListener("click", function (e) {
    var t = e.target;
    var g = function (sel) { return t.closest ? t.closest(sel) : null; };
    var el;
    if ((el = g("[data-prog]"))) return go(el.getAttribute("data-prog"));
    if ((el = g("#rail [data-i]"))) { S.screen = +el.getAttribute("data-i"); S.drill = null; closePanel(); render(); window.scrollTo({top: 0}); return; }
    if ((el = g("[data-agenda]"))) return go("story", el.getAttribute("data-agenda"));
    if ((el = g("[data-go]"))) { var p = el.getAttribute("data-go").split(":"); return go(p[0], p[1]); }
    if ((el = g("[data-bsort]"))) { S.bs[el.getAttribute("data-bsort")] = el.getAttribute("data-how"); S.plain = true; var yy = window.scrollY; render(); window.scrollTo({top: yy}); return; }
    if ((el = g("[data-metric]"))) { S.m[el.getAttribute("data-metric")] = el.getAttribute("data-key"); S.plain = true; return render(); }
    if ((el = g("[data-variant]"))) { S.v[el.getAttribute("data-variant")] = el.getAttribute("data-key"); S.drill = null; S.plain = true; return render(); }
    if ((el = g("[data-open-table]"))) return openPanel("table", el.getAttribute("data-open-table"));
    if ((el = g("[data-sort]"))) {
      var id = el.getAttribute("data-table"), k = el.getAttribute("data-sort"), cur = S.sort[id] || (allTables()[id] && allTables()[id].sort && {key: allTables()[id].sort.key, dir: allTables()[id].sort.dir}) || {};
      S.sort[id] = {key: k, dir: cur.key === k && cur.dir === "desc" ? "asc" : "desc"}; return refreshTables();
    }
    if ((el = g("[data-csv]"))) {
      var tb = allTables()[el.getAttribute("data-csv")]; if (!tb) return;
      var url = URL.createObjectURL(new Blob([csv(tb)], {type: "text/csv"})), a = document.createElement("a");
      a.href = url; a.download = (MODEL.client.id + "-" + tb.id + ".csv"); document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
      return toast("Saved " + a.download);
    }
    if ((el = g("[data-cat]")) && g(".chart")) {
      var d = drillTableOnScreen(); if (!d) return;
      var chartEl = g(".cbox"); var key = el.getAttribute("data-cat");
      if (!chartEl) return;
      S.drill = {table: d.id, key: key}; S.plain = true; var y = window.scrollY; render(); window.scrollTo({top: y}); return openPanel("table", d.id);
    }
    if (g("#b-src")) return openPanel("sources");
    if (g("#b-help")) return openPanel("help");
    if (g("#b-pres")) return present(true);
    if (g("#b-rel")) return reload();
    if (g("#b-theme")) return theme();
    if (g("[data-close]") || t.id === "scrim") return closePanel();
    if ((el = g("[data-step]"))) return step(+el.getAttribute("data-step"));
    if (g("[data-exit]")) return present(false);
  });
  document.addEventListener("input", function (e) {
    var q = e.target.getAttribute && e.target.getAttribute("data-q");
    if (q) { S.q[q] = e.target.value; refreshTables(); }
  });
  document.addEventListener("mousemove", tip);
  /* the glass cards' pointer-following sheen: the pointer's place inside the card, read by live.css (--mx / --my) */
  var sheenBusy = false;
  document.addEventListener("pointermove", function (e) {
    if (sheenBusy || e.pointerType === "touch" || !e.target || !e.target.closest) return;
    var c = e.target.closest(".card,.tile,.pcard"); if (!c) return;
    sheenBusy = true;
    requestAnimationFrame(function () {
      sheenBusy = false; var r = c.getBoundingClientRect();
      c.style.setProperty("--mx", (e.clientX - r.left) + "px"); c.style.setProperty("--my", (e.clientY - r.top) + "px");
    });
  }, {passive: true});
  document.addEventListener("mouseleave", function () { $("#tip").classList.remove("on"); });
  window.addEventListener("scroll", function () { $("#tip").classList.remove("on"); }, {passive: true});
  var rz; window.addEventListener("resize", function () { clearTimeout(rz); rz = setTimeout(function () { $("#stage").classList.add("still"); drawCharts(); }, 120); });
  window.addEventListener("hashchange", function () { var h = location.hash; readHash(); render(); });

  function theme() {
    var root = document.documentElement, dark = root.getAttribute("data-theme") === "dark" || (!root.getAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches);
    var next = dark ? "light" : "dark"; root.setAttribute("data-theme", next);
    try { localStorage.setItem("lr-theme", next); } catch (e) {}
    S.plain = true; render();
  }
  function present(on) {
    S.present = on; document.documentElement.classList.toggle("present", on); S.plain = true;
    render(); if (on) toast("Presenting. Esc to leave.");
  }

  document.addEventListener("click", function (e) { if (!(e.target.closest && e.target.closest('[data-step="1"]'))) S.hold = null; hideProgramCard(); }, true);
  document.addEventListener("keydown", function (e) { if (!(e.key === "ArrowRight" || e.key === "PageDown")) S.hold = null; hideProgramCard(); }, true);
  document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target || {}).tagName || "");
    if (e.key === "Escape") { if (S.panel) { closePanel(); } else if (S.present) { present(false); } if (typing) e.target.blur(); return; }
    if (typing) return;
    var k = e.key;
    if (k === "ArrowRight" || k === "PageDown") { e.preventDefault(); step(1); }
    else if (k === "ArrowLeft" || k === "PageUp") { e.preventDefault(); step(-1); }
    else if (/^[1-9]$/.test(k)) { var i = +k - 1; if (i < screens().length) { S.screen = i; S.drill = null; closePanel(); render(); window.scrollTo({top: 0}); } }
    else if (k === "]") stepProgram(1);
    else if (k === "[") stepProgram(-1);
    else if (k === "s" || k === "S") { S.panel === "sources" ? closePanel() : openPanel("sources"); }
    else if (k === "a" || k === "A") { if (MODEL.story) { S.panel === "agenda" ? closePanel() : openPanel("agenda"); } }
    else if (k === "p" || k === "P") present(!S.present);
    else if (k === "d" || k === "D") theme();
    else if (k === "r" || k === "R") reload();
    else if (k === "?") { S.panel === "help" ? closePanel() : openPanel("help"); }
    else if (k === "t" || k === "T") { var d = drillTableOnScreen(); if (d) { S.panel === "table" ? closePanel() : openPanel("table", d.id); } }
    else if (k === "/") { var d2 = drillTableOnScreen(); e.preventDefault(); if (d2) { S.focusSearch = true; openPanel("table", d2.id); } else { var q = $("[data-q]"); if (q) q.focus(); } }
  });

  /* ---------- go ---------- */
  readHash();
  render();
  if (T.drill) { var dt = drillTableOnScreen(); if (dt) { S.drill = {table: dt.id, key: T.drill}; S.plain = true; render(); openPanel("table", dt.id); } }   // ?drill=<branch> opens a row, for a link or a screenshot
  if (T.panel === "sources" || T.panel === "help" || (T.panel === "agenda" && MODEL.story)) openPanel(T.panel);
  if (T.present) { S.present = true; document.documentElement.classList.add("present"); S.plain = true; render(); }
  window.__LR = {state: S, model: function () { return MODEL; }, go: go, present: present};
})();
