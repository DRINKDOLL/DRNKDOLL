const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2, locale: 'zh-CN',
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  });
  const page = await ctx.newPage();

  // 1) Piwigo demo gallery links
  try {
    await page.goto('https://piwigo.org/demo', { waitUntil: 'domcontentloaded', timeout: 40000 });
    await page.waitForTimeout(2500);
    const links = await page.$$eval('a', as => as.map(a => ({ t: (a.textContent || '').trim(), h: a.href })).filter(x => /visit|demo gallery/i.test(x.t)));
    console.log('PIWIGO_LINKS', JSON.stringify(links.slice(0, 8)));
  } catch (e) { console.log('PIWIGO_ERR', String(e).slice(0, 100)); }

  // 2) Halo site: demo/theme links
  try {
    await page.goto('https://www.halo.run/', { waitUntil: 'domcontentloaded', timeout: 40000 });
    await page.waitForTimeout(3000);
    const links = await page.$$eval('a', as => as.map(a => ({ t: (a.textContent || '').trim().slice(0, 20), h: a.href })).filter(x => /demo|主题|预览|theme/i.test(x.h + x.t)));
    console.log('HALO_LINKS', JSON.stringify(links.slice(0, 12)));
    await page.screenshot({ path: 'shots/halo-site.png' });
  } catch (e) { console.log('HALO_ERR', String(e).slice(0, 100)); }

  // 3) NocoBase docs images
  try {
    await page.goto('https://docs.nocobase.com/cn/handbook/data-modeling/collection', { waitUntil: 'domcontentloaded', timeout: 40000 });
    await page.waitForTimeout(3500);
    const imgs = await page.$$eval('img', is => is.map(i => i.src).filter(s => /nocobase|static-docs/.test(s) && !/logo|icon/.test(s)));
    console.log('NB_IMGS', JSON.stringify([...new Set(imgs)].slice(0, 10)));
    await page.screenshot({ path: 'shots/nocobase-doc.png' });
  } catch (e) { console.log('NB_ERR', String(e).slice(0, 100)); }

  await browser.close();
})();
