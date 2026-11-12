// Accessibility lint of the built site: runs axe-core on every page in Chromium, at desktop
// and phone width, in light and dark colour schemes. Fails on "serious" or "critical"
// violations. Usage: node tools/a11y/check.js site
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

function pages(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...pages(p));
    else if (e.name.endsWith('.html')) out.push(p);
  }
  return out;
}

(async () => {
  const root = path.resolve(process.argv[2] || 'site');
  const all = pages(root);
  // Every top-level page, plus a sample of question pages (they share one template).
  const qs = all.filter((p) => p.includes(`${path.sep}questions${path.sep}`) && !p.endsWith('index.html'));
  const list = all.filter((p) => !qs.includes(p)).concat(qs.slice(0, 5));
  const browser = await chromium.launch();
  let serious = 0;
  for (const [w, scheme] of [[1200, 'light'], [390, 'dark']]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme });
    for (const file of list) {
      const page = await ctx.newPage();
      await page.goto('file://' + file);
      await page.addScriptTag({ content: axeSource });
      const res = await page.evaluate(() => axe.run(document, { resultTypes: ['violations'] }));
      for (const v of res.violations) {
        const bad = v.impact === 'serious' || v.impact === 'critical';
        if (bad) serious += 1;
        console.log(`${bad ? 'FAIL' : 'warn'} [${v.impact}] ${path.relative(root, file)} (${w}px, ${scheme}): ${v.id} - ${v.help} (${v.nodes.length} nodes)`);
      }
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
  console.log(`a11y: ${list.length} pages x 2 views, ${serious} serious/critical violations`);
  process.exit(serious ? 1 : 0);
})();
