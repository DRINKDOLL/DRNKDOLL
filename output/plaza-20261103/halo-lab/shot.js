const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 });
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:8090/upload/ssrf-canary.txt', { waitUntil: 'domcontentloaded', timeout: 20000 });
  await p.waitForTimeout(800);
  await p.screenshot({ path: 'evidence/shot-public-file.png' });
  console.log('title=', await p.title());
  await b.close();
})();
