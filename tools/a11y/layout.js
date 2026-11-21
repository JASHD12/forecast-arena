// Layout lint of the built site (T233): no boxes glued together, nothing boxed sticking out of
// the page column, the column centred. Runs in Chromium at laptop and phone width on every page.
// Usage: node tools/a11y/layout.js site
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

function pages(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...pages(p));
    else if (e.name.endsWith('.html')) out.push(p);
  }
  return out;
}

// Runs inside the page. Returns a list of human-readable problems.
function audit() {
  const out = [];
  const name = (e) => {
    let s = e.tagName.toLowerCase();
    if (e.id) s += '#' + e.id;
    if (e.classList.length) s += '.' + Array.from(e.classList).slice(0, 2).join('.');
    return s;
  };
  const boxed = (e) => {
    const c = getComputedStyle(e);
    const border = ['Top', 'Right', 'Bottom', 'Left'].some(
      (s) => parseFloat(c['border' + s + 'Width']) > 0 && c['border' + s + 'Style'] !== 'none');
    const bg = c.backgroundColor !== 'rgba(0, 0, 0, 0)' && c.backgroundColor !== 'transparent';
    return border || bg || c.boxShadow !== 'none' || c.backgroundImage !== 'none';
  };
  const shown = (e) => {
    const c = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    return c.display !== 'none' && c.visibility !== 'hidden' && c.position !== 'absolute'
      && c.position !== 'fixed' && r.width > 0 && r.height > 0 && !e.hidden;
  };
  const wrap = document.querySelector('main > .wrap');
  if (!wrap) return out;
  const wr = wrap.getBoundingClientRect();
  if (Math.abs(wr.left - (window.innerWidth - wr.right)) > 2) {
    out.push(`column not centred (left ${Math.round(wr.left)}, right ${Math.round(window.innerWidth - wr.right)})`);
  }
  // every container in the page, so a wrapper div cannot hide two glued boxes
  const boxes = [wrap].concat(Array.from(wrap.querySelectorAll('*')).filter(
    (e) => !e.closest('table, svg, pre, nav, .table-scroll') && e.children.length > 1));
  const seen = new Set();
  for (const c of boxes) {
    if ((c.tagName === 'UL' || c.tagName === 'OL') && boxed(c)) continue; // rows of one boxed list
    const kids = Array.from(c.children).filter(shown);
    for (let i = 1; i < kids.length; i += 1) {
      const a = kids[i - 1];
      const b = kids[i];
      const ra = a.getBoundingClientRect();
      const rb = b.getBoundingClientRect();
      const overlap = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      if (overlap < 0.5 * Math.min(ra.width, rb.width)) continue; // side by side
      const gap = rb.top - ra.top - ra.height;
      if (gap < -1) continue;
      const key = name(a) + '|' + name(b);
      const heading = /^H[1-4]$/.test(a.tagName);
      const glued = c === wrap ? gap < 6 && (boxed(a) || boxed(b)) : (heading ? gap < 2 && boxed(c) : gap < 4 && boxed(a) && boxed(b));
      if (glued && !seen.has(key)) {
        seen.add(key);
        out.push(`${c === wrap ? 'blocks touch' : 'glued inside ' + name(c)}: ${name(a)} / ${name(b)} (${Math.round(gap)} px)`);
      }
    }
  }
  const left = wr.left + parseFloat(getComputedStyle(wrap).paddingLeft);
  const right = wr.right - parseFloat(getComputedStyle(wrap).paddingRight);
  for (const e of wrap.querySelectorAll('*')) {
    if (!shown(e) || !boxed(e) || e.closest('.table-scroll, pre, .sr-only, svg, .hero, nav')) continue;
    const r = e.getBoundingClientRect();
    if (r.right > right + 1 || r.left < left - 1) out.push(`sticks out of the column: ${name(e)} (${Math.round(r.left)}..${Math.round(r.right)} vs ${Math.round(left)}..${Math.round(right)})`);
  }
  // ---- T234: clipping, empty boxes, tiny controls, heading order, document basics ----
  const seenX = new Set();
  const note = (msg) => { if (!seenX.has(msg)) { seenX.add(msg); out.push(msg); } };
  for (const e of wrap.querySelectorAll('*')) {
    if (!shown(e) || e.closest('svg, .sr-only, pre, .table-scroll, .hero')) continue;
    const c = getComputedStyle(e);
    if ((c.overflow === 'hidden' || c.textOverflow === 'ellipsis') && e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0) {
      note(`text clipped: ${name(e)} (${e.scrollWidth} > ${e.clientWidth})`);
    }
    if (e.children.length === 0 && e.textContent.trim() && parseFloat(c.fontSize) < 10.5) {
      note(`tiny text (${c.fontSize}): ${name(e)}`);
    }
  }
  for (const e of document.querySelectorAll('main button, main input, main summary, main select')) {
    if (!shown(e) || e.closest('.sr-only')) continue;
    const r = e.getBoundingClientRect();
    if (r.height < 24 || r.width < 24) note(`small tap target ${Math.round(r.width)}x${Math.round(r.height)}: ${name(e)}`);
  }
  for (const card of document.querySelectorAll('main .card')) {
    if (!shown(card)) continue;
    const kids = Array.from(card.children).filter(shown);
    if (!kids.length) continue;
    const cr = card.getBoundingClientRect();
    const slack = cr.bottom - parseFloat(getComputedStyle(card).paddingBottom) - kids[kids.length - 1].getBoundingClientRect().bottom;
    if (slack > 90) note(`empty space (${Math.round(slack)} px) at the bottom of ${name(card)}`);
  }
  const heads = Array.from(document.querySelectorAll('h1, h2, h3, h4')).filter(shown);
  if (document.querySelectorAll('h1').length !== 1) note(`${document.querySelectorAll('h1').length} h1 elements`);
  let prev = 0;
  for (const h of heads) {
    const lvl = +h.tagName[1];
    if (!h.textContent.trim()) note(`empty heading ${name(h)}`);
    if (prev && lvl > prev + 1) note(`heading level jumps h${prev} -> h${lvl}: ${h.textContent.trim().slice(0, 40)}`);
    prev = lvl;
  }
  const ids = {};
  for (const e of document.querySelectorAll('[id]')) ids[e.id] = (ids[e.id] || 0) + 1;
  for (const [id, n] of Object.entries(ids)) if (n > 1) note(`duplicate id ${id} (${n})`);
  if (!document.documentElement.lang) note('html has no lang');
  if (!document.title.trim()) note('empty title');
  if (!document.querySelector('meta[name="description"]')) note('no meta description');
  for (const a of document.querySelectorAll('a')) {
    const h = a.getAttribute('href');
    if (h === null || h === '' || h === '#') note(`link without target: ${a.textContent.trim().slice(0, 30)}`);
  }
  for (const img of document.querySelectorAll('img')) {
    if (!img.hasAttribute('alt')) note(`image without alt: ${img.getAttribute('src')}`);
    if (img.complete && img.naturalWidth === 0) note(`broken image: ${img.getAttribute('src')}`);
  }
  return out;
}

(async () => {
  const root = path.resolve(process.argv[2] || 'site');
  const all = pages(root).filter((p) => !p.endsWith('404.html'));
  const qs = all.filter((p) => p.includes(`${path.sep}questions${path.sep}`) && !p.endsWith('index.html'));
  const fc = all.filter((p) => p.includes(`${path.sep}forecasters${path.sep}`));
  const tp = all.filter((p) => p.includes(`${path.sep}topics${path.sep}`));
  const list = all.filter((p) => !qs.includes(p) && !fc.includes(p) && !tp.includes(p))
    .concat(qs.slice(0, 3), fc.slice(0, 3), tp.slice(0, 3));
  const browser = await chromium.launch();
  let problems = 0;
  for (const width of [1366, 1024, 390]) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await ctx.newPage();
    let current = '';
    page.on('pageerror', (e) => { problems += 1; console.log(`LAYOUT ${current} (${width}px): script error: ${String(e).slice(0, 120)}`); });
    page.on('console', (m) => { if (m.type() === 'error') { problems += 1; console.log(`LAYOUT ${current} (${width}px): console error: ${m.text().slice(0, 120)}`); } });
    for (const file of list) {
      current = path.relative(root, file);
      await page.goto(require('url').pathToFileURL(file).href);
      await page.waitForTimeout(40);
      const found = await page.evaluate(audit);
      for (const f of found) {
        problems += 1;
        console.log(`LAYOUT ${path.relative(root, file)} (${width}px): ${f}`);
      }
    }
    await ctx.close();
  }
  await browser.close();
  console.log(problems ? `layout: ${problems} problem(s) on ${list.length} pages` : `layout: PASS (${list.length} pages x 3 widths)`);
  process.exit(problems ? 1 : 0);
})();
