"use strict";
// Forecast Arena: progressive enhancement for the static site (T130, TypeScript since T296).
// One self-hosted file, no dependencies, no storage, no network requests: the data the
// game needs is embedded in the page as a JSON data block. Every page works without it.
// Source of src/arena/site/static/app.js: edit this file and run `make site-ts`.
(function () {
    'use strict';
    function brier(p, y) { return (p - y) * (p - y); }
    function pct(p) { return Math.round(p * 100) + '%'; }
    function el(tag, attrs, text) {
        const e = document.createElement(tag);
        Object.keys(attrs || {}).forEach((k) => { e.setAttribute(k, attrs[k]); });
        if (text !== undefined)
            e.textContent = text;
        return e;
    }
    function shuffle(a) {
        for (let i = a.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            const t = a[i];
            a[i] = a[j];
            a[j] = t;
        }
        return a;
    }
    function must(root, sel) {
        const node = root.querySelector(sel);
        if (!node)
            throw new Error('missing element ' + sel);
        return node;
    }
    function initGame(root) {
        const dataEl = document.getElementById('game-data');
        if (!dataEl)
            return;
        const data = JSON.parse(dataEl.textContent || '{}');
        const names = data.names || {};
        const q = (sel) => must(root, sel);
        const slider = q('#game-p');
        const out = q('#game-out');
        const lockBtn = q('.game-lock');
        const nextBtn = q('.game-next');
        const state = { deck: data.live.length ? 'live' : 'practice', order: [], i: 0, played: [] };
        function deckItems() { return data[state.deck] || []; }
        function current() { return deckItems()[state.order[state.i]]; }
        function setDeck(name) {
            state.deck = name;
            state.i = 0;
            state.played = [];
            state.order = shuffle(deckItems().map((_, k) => k));
            root.querySelectorAll('.deck').forEach((b) => {
                b.setAttribute('aria-pressed', String(b.getAttribute('data-deck') === name));
            });
            root.querySelectorAll('.game-deck-note').forEach((n) => {
                n.hidden = n.getAttribute('data-for') !== name;
            });
            renderScore();
            show();
        }
        function show() {
            const g = current();
            const card = q('.game-card');
            q('.game-reveal').textContent = '';
            nextBtn.hidden = true;
            lockBtn.hidden = false;
            slider.disabled = false;
            if (!g) {
                q('.game-title').textContent = deckItems().length
                    ? 'You have played every question in this deck.' : 'No questions in this deck yet.';
                q('.game-topic').textContent = '';
                q('.game-rule').textContent = '';
                q('.game-series').textContent = '';
                lockBtn.hidden = true;
                slider.disabled = true;
                return;
            }
            card.hidden = false;
            q('.game-topic').textContent = g.topic + (state.deck === 'practice' ? ' · practice' : '');
            q('.game-title').textContent = g.title;
            q('.game-rule').textContent = g.rule;
            const s = q('.game-series');
            s.textContent = '';
            if (g.series && g.series.length) {
                const t = el('table', { 'class': 'game-mini' });
                const cap = el('caption', {}, 'Known before the forecast (' + g.unit + ')' +
                    (g.threshold !== null && g.threshold !== undefined ? ', threshold ' + g.threshold : ''));
                t.appendChild(cap);
                const tb = el('tbody');
                g.series.forEach((r) => {
                    const tr = el('tr');
                    tr.appendChild(el('th', { scope: 'row' }, r.day));
                    tr.appendChild(el('td', { 'class': 'num' }, r.value === null ? '–' : String(r.value)));
                    tb.appendChild(tr);
                });
                t.appendChild(tb);
                s.appendChild(t);
            }
            else if (g.url) {
                const a = el('a', { href: (root.getAttribute('data-root') || '') + g.url }, 'See the data on the question page');
                a.setAttribute('target', '_blank');
                a.setAttribute('rel', 'noopener');
                s.appendChild(a);
            }
            slider.value = '50';
            out.textContent = '50%';
            slider.focus();
        }
        function reveal() {
            const g = current();
            if (!g)
                return;
            const p = Number(slider.value) / 100, y = g.outcome;
            state.played.push({ p, y, f: g.forecasts });
            const box = q('.game-reveal');
            box.textContent = '';
            box.appendChild(el('p', { 'class': 'game-answer ' + (y ? 'yes' : 'no') }, 'The answer was ' + (y ? 'YES' : 'NO') + '. Your score on this question: ' +
                brier(p, y).toFixed(3) + ' (lower is better).'));
            const ul = el('ul', { 'class': 'plain' });
            Object.keys(g.forecasts).sort().forEach((fid) => {
                const fp = g.forecasts[fid];
                ul.appendChild(el('li', {}, (names[fid] || fid) + ' said ' + pct(fp) + ': score ' +
                    brier(fp, y).toFixed(3) + (brier(p, y) < brier(fp, y) ? ' (you were closer)' : '')));
            });
            box.appendChild(ul);
            lockBtn.hidden = true;
            nextBtn.hidden = false;
            slider.disabled = true;
            nextBtn.focus();
            renderScore();
        }
        function renderScore() {
            const box = q('.game-score');
            box.textContent = '';
            if (!state.played.length) {
                box.appendChild(el('p', { 'class': 'empty' }, 'Play a question to see your score.'));
                return;
            }
            const rows = { you: { s: 0, n: 0 } };
            state.played.forEach((r) => {
                rows.you.s += brier(r.p, r.y);
                rows.you.n += 1;
                Object.keys(r.f).forEach((fid) => {
                    rows[fid] = rows[fid] || { s: 0, n: 0 };
                    rows[fid].s += brier(r.f[fid], r.y);
                    rows[fid].n += 1;
                });
            });
            const t = el('table');
            t.appendChild(el('caption', {}, 'Mean Brier score over ' + state.played.length + ' question(s)'));
            const tb = el('tbody');
            Object.keys(rows).sort((a, b) => rows[a].s / rows[a].n - rows[b].s / rows[b].n)
                .forEach((k) => {
                const tr = el('tr');
                tr.appendChild(el('th', { scope: 'row' }, k === 'you' ? 'You' : (names[k] || k)));
                tr.appendChild(el('td', { 'class': 'num' }, (rows[k].s / rows[k].n).toFixed(3)));
                tb.appendChild(tr);
            });
            t.appendChild(tb);
            box.appendChild(t);
        }
        slider.addEventListener('input', () => { out.textContent = slider.value + '%'; });
        lockBtn.addEventListener('click', reveal);
        nextBtn.addEventListener('click', () => { state.i += 1; show(); });
        root.querySelectorAll('.deck').forEach((b) => {
            b.addEventListener('click', () => { setDeck(b.getAttribute('data-deck') || 'live'); });
        });
        root.hidden = false;
        const stat = document.querySelector('.game-static');
        if (stat)
            stat.hidden = true;
        setDeck(state.deck);
    }
    // Sortable tables (T134): header buttons sort by the cell's data-sort or its text.
    function initSortable(table) {
        const heads = table.querySelectorAll('thead th');
        heads.forEach((th, col) => {
            const b = el('button', { type: 'button' }, th.textContent || '');
            th.textContent = '';
            th.appendChild(b);
            b.addEventListener('click', () => {
                const asc = th.getAttribute('aria-sort') !== 'ascending';
                heads.forEach((h) => { h.removeAttribute('aria-sort'); });
                th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
                const tb = table.tBodies[0];
                const rows = Array.prototype.slice.call(tb.rows);
                const key = (r) => {
                    const c = r.cells[col];
                    let v = c.getAttribute('data-sort');
                    if (v === null)
                        v = (c.textContent || '').trim();
                    const n = parseFloat(v);
                    return v === '' ? null : (isNaN(n) ? v.toLowerCase() : n);
                };
                rows.sort((x, y) => {
                    const a = key(x), b2 = key(y);
                    if (a === null)
                        return 1;
                    if (b2 === null)
                        return -1;
                    return (a < b2 ? -1 : a > b2 ? 1 : 0) * (asc ? 1 : -1);
                });
                rows.forEach((r) => { tb.appendChild(r); });
            });
        });
    }
    // Theme toggle (T137): auto -> light -> dark, in memory only (no storage).
    function initTheme(btns) {
        const modes = ['auto', 'light', 'dark'];
        btns.forEach((btn) => {
            btn.hidden = false;
            btn.addEventListener('click', () => {
                const cur = document.documentElement.getAttribute('data-theme') || 'auto';
                const next = modes[(modes.indexOf(cur) + 1) % modes.length];
                if (next === 'auto')
                    document.documentElement.removeAttribute('data-theme');
                else
                    document.documentElement.setAttribute('data-theme', next);
                btns.forEach((x) => { x.textContent = 'Theme: ' + next; });
            });
        });
    }
    // Countdown to the next daily lock (T137), from the visitor's own clock.
    function initCountdown(node) {
        const hm = (node.getAttribute('data-lock-utc') || '09:30').split(':');
        function tick() {
            const now = new Date();
            let lock = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), Number(hm[0]), Number(hm[1])));
            const past = now >= lock;
            if (past)
                lock = new Date(lock.getTime() + 864e5);
            const mins = Math.max(0, Math.round((lock.getTime() - now.getTime()) / 6e4));
            const h = Math.floor(mins / 60), m = mins % 60;
            node.textContent = '';
            node.appendChild(document.createTextNode(past
                ? "Today's forecasts are locked. The next lock is in "
                : "Today's forecasts lock in "));
            node.appendChild(el('strong', {}, h + ' h ' + m + ' min'));
            node.appendChild(document.createTextNode(' (' + hm.join(':') + ' UTC).'));
        }
        tick();
        setInterval(tick, 30000);
    }
    // Archive search (T137) and state filter: filters the question list in place; days are
    // collapsed (older ones) and are opened while a search or filter is active.
    function initSearch(input) {
        const label = input.closest('.qsearch');
        const count = document.querySelector('.qsearch-count');
        const bar = document.querySelector('.state-filter');
        if (!label || !count)
            return;
        label.hidden = false;
        count.hidden = false;
        if (bar)
            bar.hidden = false;
        const items = Array.prototype.slice.call(document.querySelectorAll('.qlist li'));
        const days = Array.prototype.slice.call(document.querySelectorAll('details.day'));
        days.forEach((d) => { d.dataset.wasOpen = d.open ? '1' : '0'; });
        let state = 'all';
        function run() {
            const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
            let shown = 0;
            const active = words.length > 0 || state !== 'all';
            items.forEach((li) => {
                const t = (li.textContent || '').toLowerCase();
                const ok = words.every((w) => t.indexOf(w) >= 0) &&
                    (state === 'all' || li.dataset.state === state);
                li.hidden = !ok;
                if (ok)
                    shown += 1;
            });
            days.forEach((d) => {
                const ul = d.querySelector('.qlist');
                const any = ul ? Array.prototype.some.call(ul.children, (li) => !li.hidden) : false;
                d.hidden = !any;
                d.open = active ? any : d.dataset.wasOpen === '1';
            });
            count.textContent = shown + ' of ' + items.length + ' questions shown';
        }
        input.addEventListener('input', run);
        if (bar)
            bar.addEventListener('click', (e) => {
                const target = e.target;
                const b = target ? target.closest('button[data-state]') : null;
                if (!b)
                    return;
                state = b.dataset.state || 'all';
                Array.prototype.forEach.call(bar.querySelectorAll('button'), (x) => {
                    const on = x === b;
                    x.classList.toggle('active', on);
                    x.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                run();
            });
        run();
    }
    // Long reference pages: on phones each section heading becomes a button that folds its section.
    function initFold() {
        const heads = Array.prototype.slice.call(document.querySelectorAll('main h2, main h3'));
        heads.forEach((h, i) => {
            const body = [];
            for (let n = h.nextElementSibling; n && n.tagName !== 'H2' && n.tagName !== h.tagName; n = n.nextElementSibling)
                body.push(n);
            if (!body.length)
                return;
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'fold-btn';
            const set = (open) => {
                b.setAttribute('aria-expanded', open ? 'true' : 'false');
                body.forEach((n) => { n.hidden = !open; });
            };
            while (h.firstChild)
                b.appendChild(h.firstChild);
            h.appendChild(b);
            b.addEventListener('click', () => { set(b.getAttribute('aria-expanded') !== 'true'); });
            h._open = () => { set(true); };
            set(i === 0 && h.tagName === 'H2');
        });
        document.querySelectorAll('.toc a[href^="#"]').forEach((a) => {
            a.addEventListener('click', () => {
                const t = document.getElementById((a.getAttribute('href') || '').slice(1));
                if (t && t._open)
                    t._open();
            });
        });
    }
    document.addEventListener('DOMContentLoaded', () => {
        const g = document.getElementById('game');
        if (g)
            initGame(g);
        document.querySelectorAll('table.sortable').forEach(initSortable);
        const t = document.querySelectorAll('.theme-toggle');
        if (t.length)
            initTheme(Array.prototype.slice.call(t));
        const c = document.querySelector('.lock-countdown');
        if (c)
            initCountdown(c);
        // the contents list starts closed on phones, where it would push the page down
        const toc = document.querySelector('.toc details');
        if (toc && window.matchMedia('(max-width: 640px)').matches)
            toc.open = false;
        if (document.querySelector('main[data-fold]') && window.matchMedia('(max-width: 640px)').matches)
            initFold();
        const s = document.getElementById('qsearch');
        if (s)
            initSearch(s);
    });
})();
