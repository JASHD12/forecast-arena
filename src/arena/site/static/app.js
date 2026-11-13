// Forecast Arena: progressive enhancement for the static site (T130).
// One self-hosted file, no dependencies, no storage, no network requests: the data the
// game needs is embedded in the page as a JSON data block. Every page works without it.
(function () {
  'use strict';

  function brier(p, y) { return (p - y) * (p - y); }
  function pct(p) { return Math.round(p * 100) + '%'; }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function shuffle(a) {
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function initGame(root) {
    var dataEl = document.getElementById('game-data');
    if (!dataEl) return;
    var data = JSON.parse(dataEl.textContent);
    var names = data.names || {};
    var q = function (sel) { return root.querySelector(sel); };
    var slider = q('#game-p'), out = q('#game-out');
    var lockBtn = q('.game-lock'), nextBtn = q('.game-next');
    var state = { deck: data.live.length ? 'live' : 'practice', order: [], i: 0, played: [] };

    function deckItems() { return data[state.deck] || []; }
    function current() { return deckItems()[state.order[state.i]]; }

    function setDeck(name) {
      state.deck = name; state.i = 0; state.played = [];
      state.order = shuffle(deckItems().map(function (_, k) { return k; }));
      root.querySelectorAll('.deck').forEach(function (b) {
        b.setAttribute('aria-pressed', String(b.getAttribute('data-deck') === name));
      });
      root.querySelectorAll('.game-deck-note').forEach(function (n) {
        n.hidden = n.getAttribute('data-for') !== name;
      });
      renderScore(); show();
    }

    function show() {
      var g = current();
      var card = q('.game-card');
      q('.game-reveal').textContent = '';
      nextBtn.hidden = true; lockBtn.hidden = false; slider.disabled = false;
      if (!g) {
        q('.game-title').textContent = deckItems().length
          ? 'You have played every question in this deck.' : 'No questions in this deck yet.';
        q('.game-topic').textContent = ''; q('.game-rule').textContent = '';
        q('.game-series').textContent = '';
        lockBtn.hidden = true; slider.disabled = true;
        return;
      }
      card.hidden = false;
      q('.game-topic').textContent = g.topic + (state.deck === 'practice' ? ' · practice' : '');
      q('.game-title').textContent = g.title;
      q('.game-rule').textContent = g.rule;
      var s = q('.game-series'); s.textContent = '';
      if (g.series && g.series.length) {
        var t = el('table', { 'class': 'game-mini' });
        var cap = el('caption', {}, 'Known before the forecast (' + g.unit + ')' +
          (g.threshold !== null && g.threshold !== undefined ? ', threshold ' + g.threshold : ''));
        t.appendChild(cap);
        var tb = el('tbody');
        g.series.forEach(function (r) {
          var tr = el('tr'); tr.appendChild(el('th', { scope: 'row' }, r.day));
          tr.appendChild(el('td', { 'class': 'num' }, r.value === null ? '–' : String(r.value)));
          tb.appendChild(tr);
        });
        t.appendChild(tb); s.appendChild(t);
      } else if (g.url) {
        var a = el('a', { href: (root.getAttribute('data-root') || '') + g.url }, 'See the data on the question page');
        a.setAttribute('target', '_blank'); a.setAttribute('rel', 'noopener');
        s.appendChild(a);
      }
      slider.value = 50; out.textContent = '50%';
      slider.focus();
    }

    function reveal() {
      var g = current(); if (!g) return;
      var p = Number(slider.value) / 100, y = g.outcome;
      state.played.push({ p: p, y: y, f: g.forecasts });
      var box = q('.game-reveal'); box.textContent = '';
      box.appendChild(el('p', { 'class': 'game-answer ' + (y ? 'yes' : 'no') },
        'The answer was ' + (y ? 'YES' : 'NO') + '. Your score on this question: ' +
        brier(p, y).toFixed(3) + ' (lower is better).'));
      var ul = el('ul', { 'class': 'plain' });
      Object.keys(g.forecasts).sort().forEach(function (fid) {
        var fp = g.forecasts[fid];
        ul.appendChild(el('li', {}, (names[fid] || fid) + ' said ' + pct(fp) + ': score ' +
          brier(fp, y).toFixed(3) + (brier(p, y) < brier(fp, y) ? ' (you were closer)' : '')));
      });
      box.appendChild(ul);
      lockBtn.hidden = true; nextBtn.hidden = false; slider.disabled = true;
      nextBtn.focus();
      renderScore();
    }

    function renderScore() {
      var box = q('.game-score'); box.textContent = '';
      if (!state.played.length) {
        box.appendChild(el('p', { 'class': 'empty' }, 'Play a question to see your score.'));
        return;
      }
      var rows = { you: { s: 0, n: 0 } };
      state.played.forEach(function (r) {
        rows.you.s += brier(r.p, r.y); rows.you.n += 1;
        Object.keys(r.f).forEach(function (fid) {
          rows[fid] = rows[fid] || { s: 0, n: 0 };
          rows[fid].s += brier(r.f[fid], r.y); rows[fid].n += 1;
        });
      });
      var t = el('table');
      t.appendChild(el('caption', {}, 'Mean Brier score over ' + state.played.length + ' question(s)'));
      var tb = el('tbody');
      Object.keys(rows).sort(function (a, b) { return rows[a].s / rows[a].n - rows[b].s / rows[b].n; })
        .forEach(function (k) {
          var tr = el('tr');
          tr.appendChild(el('th', { scope: 'row' }, k === 'you' ? 'You' : (names[k] || k)));
          tr.appendChild(el('td', { 'class': 'num' }, (rows[k].s / rows[k].n).toFixed(3)));
          tb.appendChild(tr);
        });
      t.appendChild(tb); box.appendChild(t);
    }

    slider.addEventListener('input', function () { out.textContent = slider.value + '%'; });
    lockBtn.addEventListener('click', reveal);
    nextBtn.addEventListener('click', function () { state.i += 1; show(); });
    root.querySelectorAll('.deck').forEach(function (b) {
      b.addEventListener('click', function () { setDeck(b.getAttribute('data-deck')); });
    });
    root.hidden = false;
    var stat = document.querySelector('.game-static');
    if (stat) stat.hidden = true;
    setDeck(state.deck);
  }

  // Sortable tables (T134): header buttons sort by the cell's data-sort or its text.
  function initSortable(table) {
    var heads = table.querySelectorAll('thead th');
    heads.forEach(function (th, col) {
      var b = el('button', { type: 'button' }, th.textContent);
      th.textContent = ''; th.appendChild(b);
      b.addEventListener('click', function () {
        var asc = th.getAttribute('aria-sort') !== 'ascending';
        heads.forEach(function (h) { h.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
        var tb = table.tBodies[0];
        var rows = Array.prototype.slice.call(tb.rows);
        var key = function (r) {
          var c = r.cells[col]; var v = c.getAttribute('data-sort');
          if (v === null) v = c.textContent.trim();
          var n = parseFloat(v);
          return v === '' ? null : (isNaN(n) ? v.toLowerCase() : n);
        };
        rows.sort(function (x, y) {
          var a = key(x), b = key(y);
          if (a === null) return 1; if (b === null) return -1;
          return (a < b ? -1 : a > b ? 1 : 0) * (asc ? 1 : -1);
        });
        rows.forEach(function (r) { tb.appendChild(r); });
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var g = document.getElementById('game');
    if (g) initGame(g);
    document.querySelectorAll('table.sortable').forEach(initSortable);
  });
})();
