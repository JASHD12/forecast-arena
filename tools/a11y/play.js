// Plays one round of "Can you beat the AI?" in Chromium (T130), checks the page without
// JavaScript, and checks that no request leaves the site. Usage: node tools/a11y/play.js site
const path = require('path');
const { chromium } = require('playwright');

function fail(msg) { console.error('FAIL ' + msg); process.exitCode = 1; }

(async () => {
  const root = path.resolve(process.argv[2] || 'site');
  const url = 'file://' + path.join(root, 'play.html');
  const browser = await chromium.launch();

  const ctx = await browser.newContext({ viewport: { width: 390, height: 900 } });
  const page = await ctx.newPage();
  const outside = [];
  page.on('request', (r) => { if (!r.url().startsWith('file://')) outside.push(r.url()); });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(url);
  if (!(await page.locator('#game').isVisible())) fail('game not shown with JavaScript on');
  for (const deck of ['live', 'practice']) {
    await page.click(`.deck[data-deck="${deck}"]`);
    if ((await page.locator('.game-lock').isVisible())) {
      await page.locator('#game-p').fill('80');
      if ((await page.locator('#game-out').textContent()) !== '80%') fail('slider output');
      await page.click('.game-lock');
      const reveal = await page.locator('.game-reveal').textContent();
      if (!/The answer was (YES|NO)/.test(reveal)) fail(`${deck}: no reveal (${reveal})`);
      const score = await page.locator('.game-score').textContent();
      if (!score.includes('You')) fail(`${deck}: no session score`);
      await page.click('.game-next');
      console.log(`ok   ${deck}: played one round`);
    } else {
      console.log(`skip ${deck}: deck is empty in this build`);
    }
  }
  if (errors.length) fail('page errors: ' + errors.join('; '));
  if (outside.length) fail('requests outside the site: ' + outside.join(', '));

  const lb = await ctx.newPage();
  await lb.goto('file://' + path.join(root, 'leaderboard.html'));
  await lb.evaluate(() => document.querySelectorAll('details.lb-more').forEach((d) => { d.open = true; }));  // the heatmap sits in a disclosure
  const sortBtn = lb.locator('table.sortable thead th button').nth(1);
  if (await sortBtn.count()) {
    await sortBtn.click();
    const sorted = await lb.locator('table.sortable thead th').nth(1).getAttribute('aria-sort');
    if (sorted !== 'ascending') fail('leaderboard: sort did not set aria-sort');
    else console.log('ok   leaderboard: sortable heatmap');
  } else {
    console.log('skip leaderboard: no sortable table in this build');
  }

  const home = await ctx.newPage();
  await home.goto('file://' + path.join(root, 'index.html'));
  const cd = await home.locator('.lock-countdown').textContent();
  // the wording depends on the time of day: "lock in" before 09:30 UTC, "are locked ... lock is in" after
  if (!/lock[^]*\d+ h \d+ min/.test(cd)) fail('countdown not running: ' + cd);
  else console.log('ok   home: lock countdown');
  await home.setViewportSize({ width: 1200, height: 800 });  // on a phone the toggle lives inside the menu
  const tg = home.locator('.theme-toggle').first();
  if (!(await tg.isVisible())) fail('theme toggle hidden with JavaScript');
  await tg.click();
  if ((await home.evaluate(() => document.documentElement.getAttribute('data-theme'))) !== 'light') fail('theme toggle did not set light');
  await tg.click();
  const bg = await home.evaluate(() => getComputedStyle(document.body).backgroundColor);
  if ((await home.evaluate(() => document.documentElement.getAttribute('data-theme'))) !== 'dark') fail('theme toggle did not set dark');
  else console.log('ok   theme toggle: auto -> light -> dark (' + bg + ')');
  const qs = await ctx.newPage();
  await qs.goto('file://' + path.join(root, 'questions', 'index.html'));
  const total = await qs.locator('.qlist li').count();
  // folded days are not 'visible' to the browser, so count the rows the filter has not hidden
  const shown = () => qs.evaluate(() => document.querySelectorAll('.qlist li:not([hidden])').length);
  await qs.locator('#qsearch').fill('zzzz-no-match');
  if ((await shown()) !== 0) fail('search did not filter');
  await qs.locator('#qsearch').fill('');
  if ((await shown()) !== total) fail('search did not reset');
  else console.log('ok   archive search filters ' + total + ' questions');
  // the state filter narrows the list and opens the days it keeps
  await qs.locator('.state-filter button[data-state="answered"]').click();
  const answered = await shown();
  if (answered > total || (await qs.evaluate(() => document.querySelectorAll('.qlist li:not([hidden]):not([data-state="answered"])').length)) !== 0) fail('state filter did not filter');
  await qs.locator('.state-filter button[data-state="all"]').click();
  if ((await shown()) !== total) fail('state filter did not reset');
  else console.log('ok   archive state filter: ' + answered + ' answered of ' + total);

  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const n1 = await noJs.newPage();
  await n1.goto('file://' + path.join(root, 'index.html'));
  if (await (await n1.locator('.theme-toggle').count()) > 0 && (await n1.locator('.theme-toggle').first().isVisible())) fail('toggle visible without JavaScript');
  if (!/09:30 UTC/.test(await n1.locator('.lock-countdown').textContent())) fail('static lock text missing');
  await n1.goto('file://' + path.join(root, 'questions', 'index.html'));
  if (await n1.locator('#qsearch').isVisible()) fail('search visible without JavaScript');
  console.log('ok   without JavaScript: static lock text, no toggle, no search box');
  const p2 = await noJs.newPage();
  await p2.goto(url);
  if (await p2.locator('#game').isVisible()) fail('game shown without JavaScript');
  if (!(await p2.locator('.game-static').isVisible())) fail('static fallback hidden without JavaScript');
  console.log('ok   without JavaScript: the static table is shown');

  // T203: no top-level page may scroll sideways at phone or laptop width.
  const fs = require('fs');
  const tops = fs.readdirSync(root).filter((f) => f.endsWith('.html') && f !== '404.html');
  for (const width of [390, 1366]) {
    const wctx = await browser.newContext({ viewport: { width, height: 800 } });
    const wp = await wctx.newPage();
    const wide = [];
    for (const f of tops) {
      await wp.goto('file://' + path.join(root, f));
      const [sw, iw] = await wp.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      if (sw > iw) wide.push(`${f} (${sw} > ${iw})`);
    }
    // chart text: inside its own picture, and readable (at least 11 px as rendered)
    const bad = [];
    for (const f of tops) {
      await wp.goto('file://' + path.join(root, f));
      const issues = await wp.evaluate(() => {
        const out = [];
        document.querySelectorAll('svg').forEach((svg) => {
          const box = svg.getBoundingClientRect();
          if (box.width === 0) return; // the layout the CSS hides
          const vb = svg.viewBox.baseVal;
          if (!vb || !vb.width) return;
          const scale = box.width / vb.width;
          svg.querySelectorAll('text').forEach((t) => {
            const px = parseFloat(getComputedStyle(t).fontSize) * scale;
            const b = t.getBBox();
            if (px < 10.5) out.push(`${t.textContent.slice(0, 18)} is ${px.toFixed(1)}px`);
            if (!t.hasAttribute('transform') && (b.x < -1 || b.x + b.width > vb.width + 1)) out.push(`${t.textContent.slice(0, 18)} leaves the picture`);
          });
        });
        return out;
      });
      if (issues.length) bad.push(`${f}: ${issues.slice(0, 3).join('; ')}`);
    }
    if (bad.length) fail(`chart text at ${width}px: ${bad.join(' | ')}`);
    else console.log(`ok   chart text readable and inside its picture at ${width}px`);
    if (wide.length) fail(`page wider than the viewport at ${width}px: ${wide.join(', ')}`);
    else console.log(`ok   no horizontal page scroll at ${width}px (${tops.length} pages)`);
    await wctx.close();
  }

  await browser.close();
  console.log(process.exitCode ? 'play: FAIL' : 'play: PASS');
})();
