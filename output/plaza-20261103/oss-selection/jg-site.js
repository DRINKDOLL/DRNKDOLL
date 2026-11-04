const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, locale: 'zh-CN' });
  const p = await c.newPage();
  try {
    await p.goto('https://www.jeecg.com/', { waitUntil: 'networkidle', timeout: 60000 });
    await p.waitForTimeout(5000);
    await p.screenshot({ path: 'shots/jeecg-site.png', fullPage: false });
    console.log('OK', p.url(), await p.title());
  } catch (e) { console.log('ERR', String(e).slice(0, 120)); }
  await b.close();
})();
