/* Wire page script. Reads the inlined payload; makes no network requests.
   Headline text is always inserted with textContent, never as HTML. */
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("payload").textContent);
  var $ = function (id) { return document.getElementById(id); };

  /* ---------- relative ages ---------- */
  function ago(iso) {
    if (!iso) { return ""; }
    var t = Date.parse(iso);
    if (isNaN(t)) { return ""; }
    var s = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (s < 60) { return "just now"; }
    if (s < 3600) { return Math.floor(s / 60) + "m ago"; }
    if (s < 86400) { return Math.floor(s / 3600) + "h ago"; }
    return Math.floor(s / 86400) + "d ago";
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text != null) { n.textContent = text; }
    return n;
  }

  /* ---------- status ---------- */
  var NAMES = { drudge: "Drudge", fox: "Fox", cnbc: "CNBC", categories: "Categories" };
  function statusNote(key) {
    var s = D.status[key] || { state: "stale" };
    var when = s.fetched_at ? ago(s.fetched_at) : "";
    if (s.state === "failed") {
      return { cls: "s-failed", text: "Last refresh failed" + (s.last_error_at ? " (" + ago(s.last_error_at) + ")" : "") +
        ". Showing the previous copy" + (when ? " from " + when : "") + ". " + (s.last_error || "") };
    }
    if (s.state === "stale") {
      return { cls: "s-stale", text: s.fetched_at ? "Stale: this copy is from " + when + "." : "No data fetched yet." };
    }
    return null;
  }
  function partialNote(failed) {
    var names = Object.keys(failed || {});
    if (!names.length) { return null; }
    return { cls: "s-stale", text: "Partial: " + names.join(", ") + (names.length > 1 ? " feeds" : " feed") +
      " failed this refresh; those items are from the previous copy." };
  }

  function buildBus() {
    var bus = $("bus");
    Object.keys(NAMES).forEach(function (k) {
      var s = D.status[k] || { state: "stale" };
      var c = el("span", "chip s-" + s.state);
      c.appendChild(el("span", "nm", NAMES[k] + " " + s.state));
      c.title = NAMES[k] + ": " + s.state + (s.fetched_at ? ", fetched " + s.fetched_at.replace("T", " ").replace("+00:00", "") + " UTC (" + ago(s.fetched_at) + ")" : "") +
        (s.last_error ? ". Error: " + s.last_error : "");
      bus.appendChild(c);
    });
  }

  /* ---------- lists ---------- */
  function row(it, showFeed) {
    var li = el("li");
    var a = el("a", null, it.t);
    a.href = it.u;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    li.appendChild(a);
    var bits = [];
    if (showFeed && it.f) { bits.push(it.f); }
    if (it.s) { bits.push(it.s); }
    var age = ago(it.p);
    if (age) { bits.push(age); }
    if (bits.length) { li.appendChild(el("span", "meta", bits.join(" · "))); }
    li.setAttribute("data-q", (it.t + " " + (it.s || "") + " " + (it.f || "")).toLowerCase());
    return li;
  }

  var lists = []; /* {ol, total, countEl, emptyEl} */

  function fill(ol, items, showFeed) {
    ol.textContent = "";
    var frag = document.createDocumentFragment();
    items.forEach(function (it) { frag.appendChild(row(it, showFeed)); });
    ol.appendChild(frag);
  }

  function section(key, title, items, failed, showFeed) {
    var host = $(key);
    var head = el("div", "head");
    head.appendChild(el("h2", null, title));
    var count = el("span", "n");
    head.appendChild(count);
    var s = D.status[key];
    if (s && s.fetched_at) { head.appendChild(el("span", "stamp", "fetched " + ago(s.fetched_at))); }
    host.appendChild(head);
    [statusNote(key), partialNote(failed)].forEach(function (n) {
      if (n) { host.appendChild(el("p", "note " + n.cls, n.text)); }
    });
    var ol = el("ol", "list");
    var empty = el("p", "empty");
    empty.hidden = true;
    host.appendChild(ol);
    host.appendChild(empty);
    fill(ol, items, showFeed);
    if (!items.length) { empty.hidden = false; empty.textContent = "No headlines yet."; }
    return { ol: ol, total: items.length, countEl: count, emptyEl: empty, none: !items.length };
  }

  /* ---------- filter ---------- */
  function applyFilter() {
    var q = $("q").value.trim().toLowerCase();
    var terms = q ? q.split(/\s+/) : [];
    var shown = 0, all = 0;
    lists.forEach(function (L) {
      var n = 0;
      Array.prototype.forEach.call(L.ol.children, function (li) {
        var hay = li.getAttribute("data-q");
        var ok = terms.every(function (t) { return hay.indexOf(t) !== -1; });
        li.hidden = !ok;
        if (ok) { n++; }
      });
      L.countEl.textContent = (terms.length ? n + " of " : "") + L.total;
      if (!L.none) {
        L.emptyEl.hidden = n > 0;
        L.emptyEl.textContent = "No headlines match.";
      }
      shown += n; all += L.total;
    });
    $("q-n").textContent = terms.length ? shown + " of " + all + " shown" : all + " headlines";
  }

  /* ---------- categories ---------- */
  function buildCategories() {
    var host = $("categories");
    var C = D.categories;
    var keys = Object.keys(C.labels);
    var saved = null;
    try { saved = localStorage.getItem("wire-category"); } catch (e) { /* ignore */ }
    var active = keys.indexOf(saved) !== -1 ? saved : keys[0];

    var head = el("div", "head");
    head.appendChild(el("h2", null, "By category"));
    var count = el("span", "n");
    head.appendChild(count);
    var s = D.status.categories;
    if (s && s.fetched_at) { head.appendChild(el("span", "stamp", "fetched " + ago(s.fetched_at))); }
    host.appendChild(head);
    [statusNote("categories"), partialNote(C.failed_feeds)].forEach(function (n) {
      if (n) { host.appendChild(el("p", "note " + n.cls, n.text)); }
    });
    var tabs = el("div", "tabs");
    tabs.setAttribute("role", "tablist");
    host.appendChild(tabs);
    var ol = el("ol", "list");
    var empty = el("p", "empty");
    empty.hidden = true;
    host.appendChild(ol);
    host.appendChild(empty);

    var L = { ol: ol, total: 0, countEl: count, emptyEl: empty, none: false };
    lists.push(L);

    function show(k) {
      active = k;
      try { localStorage.setItem("wire-category", k); } catch (e) { /* ignore */ }
      Array.prototype.forEach.call(tabs.children, function (b) {
        b.setAttribute("aria-selected", b.getAttribute("data-k") === k ? "true" : "false");
      });
      var items = C.items[k] || [];
      fill(ol, items, false);
      L.total = items.length;
      L.none = !items.length;
      empty.hidden = !!items.length;
      if (!items.length) { empty.textContent = "No headlines in this category yet."; }
      applyFilter();
    }
    keys.forEach(function (k) {
      var b = el("button", null, C.labels[k] + " (" + (C.items[k] || []).length + ")");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("data-k", k);
      b.addEventListener("click", function () { show(k); });
      tabs.appendChild(b);
    });
    show(active);
  }

  /* ---------- theme ---------- */
  function initTheme() {
    var btn = $("theme");
    function apply(mode) {
      document.documentElement.setAttribute("data-theme", mode);
      btn.textContent = mode === "dark" ? "Light" : "Dark";
      try { localStorage.setItem("wire-theme", mode); } catch (e) { /* private mode */ }
    }
    btn.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "Light" : "Dark";
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      apply(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
  }

  /* ---------- boot ---------- */
  buildBus();
  ["drudge", "fox", "cnbc"].forEach(function (k) {
    var src = D.sources[k];
    lists.push(section(k, src.label, src.items || [], src.failed_feeds, true));
  });
  buildCategories();
  $("q").addEventListener("input", applyFilter);
  initTheme();
  applyFilter();
})();
