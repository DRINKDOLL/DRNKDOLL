const { chromium } = require('playwright');
const targets = [
  { name: 'halo-front', url: 'https://demo.halocms.site/', wait: 6000 },
  { name: 'halo-console', url: 'https://demo.halocms.site/console', wait: 7000 },
  { name: 'piwigo-gallery', url: 'https://demo1.piwigo.com/', wait: 6000 },
];
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: 'zh-CN',
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
  for (const t of targets) {
    const p = await c.newPage();
    try {
      await p.goto(t.url, { waitUntil: 'domcontentloaded', timeout: 50000 });
      await p.waitForTimeout(t.wait);
      console.log(JSON.stringify({ name: t.name, url: p.url(), title: await p.title() }));
      await p.screenshot({ path: `shots/${t.name}.png` });
    } catch (e) { console.log(JSON.stringify({ name: t.name, err: String(e).slice(0, 120) }));
      try { await p.screenshot({ path: `shots/${t.name}.png` }); } catch (_) {}
    }
    await p.close();
  }
  await b.close();
})();
