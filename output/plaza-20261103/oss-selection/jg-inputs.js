const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1600, height: 1000 } });
  const p = await c.newPage();
  await p.goto('http://boot.jeecg.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(3500);
  const ins = await p.$$eval('input', is => is.map((i, idx) => ({ idx, ph: i.placeholder, type: i.type, cls: i.className.slice(0, 40), vis: !!i.offsetParent })));
  console.log(JSON.stringify(ins, null, 1));
  await b.close();
})();
