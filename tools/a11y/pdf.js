// Print one built page to a PDF. Usage: node tools/a11y/pdf.js SITE_DIR PAGE OUT.pdf
// The site header, navigation and footer are hidden so the PDF is just the page's content.
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const [root, page, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const p = await browser.newPage();
  await p.goto('file://' + path.resolve(root, page));
  await p.addStyleTag({ content: 'header.site-header, footer, nav, .skip-link { display: none !important; } body { background: #fff !important; }' });
  await p.pdf({ path: out, format: 'A4', printBackground: true, scale: 0.62, margin: { top: '16mm', bottom: '16mm', left: '14mm', right: '14mm' } });
  await browser.close();
})();
