const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, locale: 'zh-CN' });
  const p = await c.newPage();
  for (const u of ['https://help.jeecg.com/', 'https://help.jeecg.com/jeecgboot/']) {
    try {
      await p.goto(u, { waitUntil: 'domcontentloaded', timeout: 40000 });
      await p.waitForTimeout(4000);
      const imgs = await p.$$eval('img', is => is.map(i => ({ s: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight })).filter(x => x.w > 600 && x.h > 300));
      console.log('PAGE', u, JSON.stringify(imgs.slice(0, 6)));
    } catch (e) { console.log('ERR', u, String(e).slice(0, 90)); }
  }
  await b.close();
})();
