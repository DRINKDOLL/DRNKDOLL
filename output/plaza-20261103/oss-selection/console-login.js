const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    locale: 'en-US',
    extraHTTPHeaders: { 'Accept-Language': 'en-US,en;q=0.9' },
  });
  const p = await ctx.newPage();
  await p.goto('http://127.0.0.1:8090/console', { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(2500);
  if (p.url().includes('/login')) {
    await p.fill('input[name="username"], input[placeholder*="用户名"], input[type="text"]', 'admin');
    const pw = await p.$('input[type="password"]');
    if (pw) await pw.fill('Passw0rd!2026');
    await p.click('button[type="submit"], button:has-text("登录")');
    await p.waitForTimeout(7000);
  }
  console.log('URL =', p.url());
  const txt = await p.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 700));
  console.log('TEXT =', txt);
  await p.screenshot({ path: 'langshots/console-dashboard.png' });

  // 侧边栏菜单项
  const menu = await p.evaluate(() =>
    Array.from(document.querySelectorAll('aside a, .sidebar a, nav a'))
      .map(a => (a.innerText || '').trim())
      .filter(t => t && t.length < 20)
  );
  console.log('MENU =', JSON.stringify([...new Set(menu)].slice(0, 40)));

  // localStorage 里的语言偏好
  const ls = await p.evaluate(() => JSON.stringify({ ...localStorage }).slice(0, 600));
  console.log('LS =', ls);

  await b.close();
})();
