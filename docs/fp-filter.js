/* FP filter: one search bar per page that limits every FP table on the page to the selected models.
   A table takes part when its first header cell reads "FP". Rows are only hidden, never removed or
   reordered, so sorting, best-in-column marks and color scales keep using every model. The selection
   is shared across pages (localStorage) and can be shared as a link (?fp=MACE,DPA4). */
(function () {
  'use strict';

  var STORE = 'fpdeerr-fp-filter';
  var MAX_SUGGEST = 40;

  function norm(s) { return s.toLowerCase().replace(/[^a-z0-9]/g, ''); }

  function cellName(td) {
    var c = td.cloneNode(true);
    c.querySelectorAll('sup, button, [class^="tag-"], [class*=" tag-"]').forEach(function (n) { n.remove(); });
    return c.textContent.replace(/↳/g, '').replace(/[\s*†‡§¶‖#]+$/u, '').trim();
  }

  function fpTables() {
    return Array.prototype.filter.call(document.querySelectorAll('table'), function (t) {
      var th = t.querySelector('th');
      return th && th.textContent.trim() === 'FP';
    });
  }

  function bodyRows(t) {
    return Array.prototype.filter.call(t.querySelectorAll('tr'), function (r) {
      return r.firstElementChild && r.firstElementChild.tagName === 'TD' && !r.classList.contains('frac-row');
    });
  }

  function loadSelection() {
    var q = new URLSearchParams(location.search).get('fp');
    if (q !== null) return q.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    try { return JSON.parse(localStorage.getItem(STORE) || '[]'); } catch (e) { return []; }
  }

  function saveSelection(sel) {
    try { localStorage.setItem(STORE, JSON.stringify(sel)); } catch (e) {}
    try {
      var u = new URL(location.href);
      u.searchParams.delete('fp');
      var rest = u.searchParams.toString();
      var q = sel.length ? 'fp=' + sel.map(encodeURIComponent).join(',') : '';
      u.search = [rest, q].filter(Boolean).join('&');
      history.replaceState(null, '', u);
    } catch (e) {}
  }

  var CSS = [
    '#fpf-bar{position:sticky;z-index:50;background:var(--bg,#0d1117);border-bottom:1px solid var(--border,#30363d);padding:0.55rem 0 0.6rem;margin-bottom:0.8rem}',
    '#fpf-bar .fpf-row{display:flex;flex-wrap:wrap;align-items:center;gap:0.4rem;background:var(--surface,#161b22);border:1px solid var(--border,#30363d);border-radius:8px;padding:0.3rem 0.5rem;position:relative}',
    '#fpf-bar .fpf-row:focus-within{border-color:var(--accent,#58a6ff)}',
    '#fpf-bar .fpf-icon{color:var(--muted,#8b949e);flex:none;display:flex}',
    '#fpf-bar input{flex:1 1 12rem;min-width:8rem;background:transparent;border:0;outline:0;color:var(--heading,#e6edf3);font:inherit;font-size:0.92rem;padding:0.25rem 0.1rem}',
    '#fpf-bar input::placeholder{color:var(--muted,#8b949e)}',
    '#fpf-bar .fpf-chip{display:inline-flex;align-items:center;gap:0.25rem;background:var(--surface2,#1c2230);border:1px solid var(--border,#30363d);color:var(--heading,#e6edf3);border-radius:999px;font-size:0.82rem;padding:0.08rem 0.3rem 0.08rem 0.6rem;white-space:nowrap}',
    '#fpf-bar .fpf-chip.absent{opacity:0.5}',
    '#fpf-bar .fpf-chip button{background:none;border:0;color:var(--muted,#8b949e);cursor:pointer;font-size:0.95rem;line-height:1;padding:0 0.15rem}',
    '#fpf-bar .fpf-chip button:hover{color:var(--accent3,#f78166)}',
    '#fpf-bar .fpf-status{font-size:0.8rem;color:var(--muted,#8b949e);margin-top:0.3rem;display:flex;gap:0.8rem;flex-wrap:wrap}',
    '#fpf-bar .fpf-status button{background:none;border:0;color:var(--accent,#58a6ff);cursor:pointer;font:inherit;padding:0}',
    '#fpf-list{position:absolute;left:0;right:0;top:calc(100% + 4px);background:var(--surface,#161b22);border:1px solid var(--border,#30363d);border-radius:8px;max-height:min(22rem,60vh);overflow-y:auto;box-shadow:0 8px 24px rgba(0,0,0,0.45);display:none;padding:0.25rem 0}',
    '#fpf-list.open{display:block}',
    '#fpf-list .fpf-opt{display:flex;justify-content:space-between;gap:1rem;padding:0.35rem 0.75rem;cursor:pointer;font-size:0.9rem;color:var(--text,#c9d1d9)}',
    '#fpf-list .fpf-opt .fpf-meta{color:var(--muted,#8b949e);font-size:0.8rem;white-space:nowrap}',
    '#fpf-list .fpf-opt.group{color:var(--accent,#58a6ff);font-weight:600;border-bottom:1px solid var(--border,#30363d)}',
    '#fpf-list .fpf-opt.active{background:var(--surface2,#1c2230)}',
    '#fpf-list .fpf-opt mark{background:none;color:var(--heading,#e6edf3);font-weight:700}',
    '#fpf-list .fpf-foot{position:sticky;bottom:-0.25rem;display:flex;align-items:center;gap:0.7rem;flex-wrap:wrap;padding:0.5rem 0.75rem;margin-bottom:-0.25rem;background:var(--surface,#161b22);border-top:1px solid var(--border,#30363d);font-size:0.78rem;color:var(--muted,#8b949e)}',
    '#fpf-list .fpf-show{background:var(--accent,#58a6ff);color:#0d1117;border:0;border-radius:6px;font:inherit;font-size:0.85rem;font-weight:600;padding:0.35rem 0.9rem;cursor:pointer}',
    '#fpf-list .fpf-show:hover{opacity:0.88}',
    '#fpf-list .fpf-empty{padding:0.45rem 0.75rem;color:var(--muted,#8b949e);font-size:0.88rem}',
    'tr.fpf-hide{display:none}',
    'td.fpf-pick{cursor:pointer}',
    'td.fpf-pick:hover{text-decoration:underline;text-decoration-color:var(--accent,#58a6ff);text-underline-offset:3px}',
    '.fpf-none{display:none;font-size:0.85rem;color:var(--muted,#8b949e);padding:0.4rem 0 0.8rem}',
    '.fpf-none.show{display:block}',
    '@media (max-width:640px){#fpf-bar input{font-size:16px}#fpf-bar .fpf-chip{font-size:0.78rem}}'
  ].join('\n');

  function init() {
    var main = document.querySelector('main') || document.body;
    var tables = fpTables();
    if (!tables.length) return;

    // Suggestions and the count cover the tables in view: on a page with dataset tabs, only the open tab's.
    var models = [], seen = {};
    function scan() {
      models = [];
      seen = {};
      tables.forEach(function (t) {
        if (t.closest('.tab-panel:not(.active)')) return;
        bodyRows(t).forEach(function (r) {
          var n = cellName(r.firstElementChild);
          if (n && !seen[n]) { seen[n] = true; models.push(n); }
        });
      });
    }
    scan();

    var sel = loadSelection();
    var style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    var bar = document.createElement('div');
    bar.id = 'fpf-bar';
    bar.setAttribute('role', 'search');
    bar.innerHTML =
      '<div class="fpf-row">' +
        '<span class="fpf-icon" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg></span>' +
        '<span class="fpf-chips"></span>' +
        '<input type="text" autocomplete="off" spellcheck="false" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="fpf-list" aria-label="Filter the tables by FP" placeholder="Filter by FP: type a name, e.g. MACE or DPA4">' +
        '<div id="fpf-list" role="listbox"></div>' +
      '</div>' +
      '<div class="fpf-status"></div>';
    main.insertBefore(bar, main.firstChild);

    var input = bar.querySelector('input');
    var list = bar.querySelector('#fpf-list');
    var chips = bar.querySelector('.fpf-chips');
    var status = bar.querySelector('.fpf-status');
    var opts = [], active = -1;

    function placeBar() {
      var nav = document.querySelector('nav');
      var top = nav && getComputedStyle(nav).position === 'sticky' ? nav.offsetHeight : 0;
      bar.style.top = top + 'px';
      document.documentElement.style.scrollPaddingTop = (top + bar.offsetHeight + 8) + 'px';
    }

    tables.forEach(function (t) {
      var anchor = t.closest('.scroll-shell, .table-scroll, .table-scroll-plain') || t;
      var none = document.createElement('div');
      none.className = 'fpf-none';
      none.textContent = 'None of the selected FPs are in this table.';
      anchor.parentNode.insertBefore(none, anchor.nextSibling);
      t._fpfNone = none;
    });

    function apply() {
      var on = sel.length > 0, want = {};
      sel.forEach(function (n) { want[n] = true; });
      tables.forEach(function (t) {
        var shown = 0;
        bodyRows(t).forEach(function (r) {
          var td = r.firstElementChild;
          if (!td.classList.contains('fpf-pick')) {
            td.classList.add('fpf-pick');
            td.title = 'Click to add or remove this FP from the filter';
          }
          var hide = on && !want[cellName(td)];
          r.classList.toggle('fpf-hide', hide);
          if (!hide) shown++;
        });
        t._fpfNone.classList.toggle('show', on && shown === 0);
      });
      chips.innerHTML = '';
      sel.forEach(function (n) {
        var c = document.createElement('span');
        c.className = 'fpf-chip' + (seen[n] ? '' : ' absent');
        if (!seen[n]) c.title = 'Not in the tables shown here';
        c.appendChild(document.createTextNode(n));
        var x = document.createElement('button');
        x.type = 'button';
        x.setAttribute('aria-label', 'Remove ' + n);
        x.innerHTML = '&times;';
        x.addEventListener('click', function () { toggle(n); input.focus(); });
        c.appendChild(x);
        chips.appendChild(c);
      });
      input.placeholder = on ? 'Add more FPs…' : 'Filter by FP: type a name, e.g. MACE or DPA4';
      var present = sel.filter(function (n) { return seen[n]; }).length;
      status.innerHTML = '';
      var s = document.createElement('span');
      s.textContent = on
        ? 'Showing ' + present + ' of ' + models.length + ' FPs'
        : 'Showing all ' + models.length + ' FPs. Pick one or more to compare; you can also click an FP name in any table.';
      status.appendChild(s);
      if (on) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = 'Show all FPs';
        b.addEventListener('click', function () { sel = []; commit(); });
        status.appendChild(b);
      }
      if (window.fpbUpdateShells) window.fpbUpdateShells();
      placeBar();
    }

    function commit() { saveSelection(sel); apply(); render(); }

    function toggle(n) {
      var i = sel.indexOf(n);
      if (i >= 0) sel.splice(i, 1); else sel.push(n);
      commit();
    }

    function addAll(names) {
      names.forEach(function (n) { if (sel.indexOf(n) < 0) sel.push(n); });
      commit();
    }

    function highlight(name, q) {
      var frag = document.createDocumentFragment();
      if (!q) { frag.appendChild(document.createTextNode(name)); return frag; }
      var lower = name.toLowerCase(), i = lower.indexOf(q.toLowerCase());
      if (i < 0) { frag.appendChild(document.createTextNode(name)); return frag; }
      frag.appendChild(document.createTextNode(name.slice(0, i)));
      var m = document.createElement('mark');
      m.textContent = name.slice(i, i + q.length);
      frag.appendChild(m);
      frag.appendChild(document.createTextNode(name.slice(i + q.length)));
      return frag;
    }

    function render() {
      if (document.activeElement !== input) { close(); return; }
      var raw = input.value.trim(), q = norm(raw);
      var hits = models.filter(function (n) { return !q || norm(n).indexOf(q) >= 0; });
      hits.sort(function (a, b) {
        var pa = norm(a).indexOf(q) === 0 ? 0 : 1, pb = norm(b).indexOf(q) === 0 ? 0 : 1;
        return q ? pa - pb : 0;
      });
      list.innerHTML = '';
      opts = [];
      if (q && hits.length > 1) {
        var g = document.createElement('div');
        g.className = 'fpf-opt group';
        g.setAttribute('role', 'option');
        g.innerHTML = '<span></span><span class="fpf-meta"></span>';
        g.firstChild.textContent = 'All FPs matching “' + raw + '”';
        g.lastChild.textContent = hits.length + ' FPs';
        g._fpfPick = function () { addAll(hits); input.value = ''; render(); };
        list.appendChild(g);
        opts.push(g);
      }
      hits.slice(0, MAX_SUGGEST).forEach(function (n) {
        var o = document.createElement('div');
        o.className = 'fpf-opt';
        o.setAttribute('role', 'option');
        var picked = sel.indexOf(n) >= 0;
        o.setAttribute('aria-selected', picked ? 'true' : 'false');
        var l = document.createElement('span');
        l.appendChild(highlight(n, raw));
        var meta = document.createElement('span');
        meta.className = 'fpf-meta';
        meta.textContent = picked ? '✓ selected' : '';
        o.appendChild(l);
        o.appendChild(meta);
        o._fpfPick = function () { toggle(n); input.value = ''; render(); };
        list.appendChild(o);
        opts.push(o);
      });
      if (!opts.length) {
        var e = document.createElement('div');
        e.className = 'fpf-empty';
        e.textContent = 'No FP here matches “' + raw + '”.';
        list.appendChild(e);
      }
      if (sel.length) {
        var foot = document.createElement('div');
        foot.className = 'fpf-foot';
        var go = document.createElement('button');
        go.type = 'button';
        go.className = 'fpf-show';
        go.textContent = 'Show ' + sel.length + ' selected FP' + (sel.length === 1 ? '' : 's');
        go.addEventListener('mousedown', function (ev) { ev.preventDefault(); });
        go.addEventListener('click', done);
        var tip = document.createElement('span');
        tip.textContent = 'or press Enter with the box empty';
        foot.appendChild(go);
        foot.appendChild(tip);
        list.appendChild(foot);
      }
      opts.forEach(function (o, i) {
        o.addEventListener('mousedown', function (ev) { ev.preventDefault(); });
        o.addEventListener('click', function () { o._fpfPick(); });
        o.addEventListener('mousemove', function () { setActive(i); });
      });
      active = -1;
      if (q && opts.length) setActive(0);
      list.classList.add('open');
      input.setAttribute('aria-expanded', 'true');
    }

    function setActive(i) {
      opts.forEach(function (o, j) { o.classList.toggle('active', j === i); });
      active = i;
      if (opts[i]) opts[i].scrollIntoView({ block: 'nearest' });
    }

    function done() {
      input.value = '';
      close();
      input.blur();
    }

    function close() {
      list.classList.remove('open');
      input.setAttribute('aria-expanded', 'false');
      active = -1;
    }

    input.addEventListener('input', render);
    input.addEventListener('focus', render);
    input.addEventListener('blur', close);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (!list.classList.contains('open')) render(); setActive(Math.min(active + 1, opts.length - 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(active - 1, 0)); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        if (!input.value.trim() && sel.length) done();
        else if (opts[active]) opts[active]._fpfPick();
      }
      else if (e.key === 'Escape') { if (input.value) { input.value = ''; render(); } else { close(); input.blur(); } }
      else if (e.key === 'Backspace' && !input.value && sel.length) { sel.pop(); commit(); }
    });

    document.addEventListener('click', function (e) {
      var td = e.target.closest && e.target.closest('td.fpf-pick');
      if (!td || e.target.closest('button, a, summary')) return;
      toggle(cellName(td));
    });

    var pending = false;
    var mo = new MutationObserver(function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        var before = models.join('|');
        scan();
        mo.disconnect();
        apply();
        if (models.join('|') !== before) render();
        tables.forEach(function (t) { mo.observe(t, { childList: true, subtree: true }); });
      });
    });
    tables.forEach(function (t) { mo.observe(t, { childList: true, subtree: true }); });

    document.addEventListener('click', function (e) {
      if (!e.target.closest || !e.target.closest('.tab-btn')) return;
      setTimeout(function () { scan(); apply(); }, 0);
    });
    window.addEventListener('resize', placeBar);
    if (sel.length) saveSelection(sel);
    apply();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
