const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' });
  const p = await ctx.newPage();
  const hits = [];
  p.on('request', r => {
    const u = r.url();
    if (u.includes('/apis/') || u.includes('/api/')) hits.push(r.method() + ' ' + u.replace('http://127.0.0.1:8090', ''));
  });

  await p.goto('http://127.0.0.1:8090/console', { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(2000);
  if (p.url().includes('/login')) {
    await p.fill('input[type="text"]', 'admin');
    await p.fill('input[type="password"]', 'Passw0rd!2026');
    await p.click('button[type="submit"]');
    await p.waitForTimeout(6000);
  }
  await p.goto('http://127.0.0.1:8090/console/settings', { waitUntil: 'networkidle', timeout: 60000 }).catch(e => console.log('nav err', e.message));
  await p.waitForTimeout(4000);
  console.log('SETTINGS URL =', p.url());
  console.log([...new Set(hits)].join('\n'));
  await p.screenshot({ path: 'langshots/console-settings.png' });
  await b.close();
})();
