const { chromium } = require('playwright');
const fs = require('fs');

const targets = [
  { name: 'halo-demo', url: 'https://demo.halo.run/' },
  { name: 'nocobase-demo', url: 'https://demo.nocobase.com/new' },
  { name: 'jeecg-demo', url: 'http://boot.jeecg.com/' },
  { name: 'piwigo-demo', url: 'https://piwigo.org/demo' },
  { name: 'directus-site', url: 'https://directus.io/' },
];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    locale: 'zh-CN',
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  });
  for (const t of targets) {
    const page = await ctx.newPage();
    try {
      await page.goto(t.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(6000);
      const info = { name: t.name, finalUrl: page.url(), title: await page.title() };
      console.log(JSON.stringify(info));
      await page.screenshot({ path: `shots/${t.name}.png` });
    } catch (e) {
      console.log(JSON.stringify({ name: t.name, error: String(e).slice(0, 160) }));
      try { await page.screenshot({ path: `shots/${t.name}.png` }); } catch (_) {}
    }
    await page.close();
  }
  await browser.close();
})();
