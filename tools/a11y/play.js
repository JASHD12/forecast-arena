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
  const sortBtn = lb.locator('table.sortable thead th button').nth(1);
  if (await sortBtn.count()) {
    await sortBtn.click();
    const sorted = await lb.locator('table.sortable thead th').nth(1).getAttribute('aria-sort');
    if (sorted !== 'ascending') fail('leaderboard: sort did not set aria-sort');
    else console.log('ok   leaderboard: sortable heatmap');
  } else {
    console.log('skip leaderboard: no sortable table in this build');
  }

  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const p2 = await noJs.newPage();
  await p2.goto(url);
  if (await p2.locator('#game').isVisible()) fail('game shown without JavaScript');
  if (!(await p2.locator('.game-static').isVisible())) fail('static fallback hidden without JavaScript');
  console.log('ok   without JavaScript: the static table is shown');

  await browser.close();
  console.log(process.exitCode ? 'play: FAIL' : 'play: PASS');
})();
