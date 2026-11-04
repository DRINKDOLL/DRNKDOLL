const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: 'zh-CN' });
  const p = await c.newPage();
  await p.goto('https://docs.halo.run/guide/demo', { waitUntil: 'domcontentloaded', timeout: 40000 }).catch(e => console.log('ERR', e.message));
  await p.waitForTimeout(3000);
  const links = await p.$$eval('a', as => as.map(a => ({ t: (a.textContent || '').trim().slice(0, 18), h: a.href })).filter(x => /^https?:\/\/(demo|www\.demo)/.test(x.h)));
  console.log('DEMO_LINKS', JSON.stringify([...new Map(links.map(l => [l.h, l])).values()].slice(0, 10)));
  await b.close();
})();
