// Screenshot one built page. Usage: node tools/a11y/shot.js SITE_DIR PAGE OUT.png [WIDTH HEIGHT]
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const [root, page, out, w, h] = process.argv.slice(2);
  const browser = await chromium.launch();
  const p = await browser.newPage({ viewport: { width: +(w || 1366), height: +(h || 768) } });
  await p.goto('file://' + path.resolve(root, page));
  await p.waitForTimeout(300);
  await p.screenshot({ path: out });
  await browser.close();
})();
