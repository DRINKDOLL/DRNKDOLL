const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const EXE = 'C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT = path.join(__dirname, 'shots');
fs.mkdirSync(OUT, { recursive: true });
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';

async function shot(p, name) {
  await p.screenshot({ path: path.join(OUT, name + '.png') });
  console.log('SAVED', name, '|', p.url());
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, locale: 'zh-CN', userAgent: UA });
  const which = process.argv[2] || 'all';

  if (which === 'all' || which === 'halo') {
    const p = await ctx.newPage();
    try {
      await p.goto('http://127.0.0.1:8092/', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await p.waitForTimeout(4000);
      console.log('HALO-FRONT title:', await p.title());
      await shot(p, 'halo-01-front');
      // 控制台登录
      await p.goto('http://127.0.0.1:8092/console', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await p.waitForTimeout(3000);
      const u = p.locator('input[name="username"], input[type="text"]').first();
      if (await u.count()) {
        await u.fill('admin');
        await p.locator('input[name="password"], input[type="password"]').first().fill('Passw0rd!2026');
        await p.keyboard.press('Enter');
        await p.waitForTimeout(6000);
      }
      console.log('HALO-CONSOLE url:', p.url());
      await shot(p, 'halo-02-console');
      // 文章管理
      await p.goto('http://127.0.0.1:8092/console/posts', { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
      await p.waitForTimeout(4000);
      await shot(p, 'halo-03-posts');
    } catch (e) { console.log('HALO ERR', String(e).slice(0, 200)); }
    await p.close();
  }

  if (which === 'all' || which === 'jeecg') {
    const p = await ctx.newPage();
    try {
      await p.goto('http://boot.jeecg.com/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await p.waitForTimeout(4000);
      const ins = p.locator('input');
      console.log('JEECG inputs:', await ins.count());
      await p.locator('input').nth(0).fill('admin').catch(() => {});
      await p.locator('input').nth(1).fill('123456').catch(() => {});
      await p.locator('input').nth(2).fill('1234').catch(() => {});
      await p.waitForTimeout(500);
      await shot(p, 'jeecg-02-filled');
      const btn = p.locator('button:has-text("登录"), button:has-text("登 录")').first();
      if (await btn.count()) { await btn.click().catch(() => {}); }
      await p.waitForTimeout(8000);
      console.log('JEECG after login url:', p.url());
      await shot(p, 'jeecg-03-after');
    } catch (e) { console.log('JEECG ERR', String(e).slice(0, 200)); }
    await p.close();
  }

  if (which === 'all' || which === 'uniapp') {
    const p = await ctx.newPage();
    try {
      await p.goto('https://hellouniapp.dcloud.net.cn/pages/tabBar/component', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await p.waitForTimeout(7000);
      console.log('UNI title:', await p.title(), p.url());
      await shot(p, 'uniapp-01-h5');
    } catch (e) { console.log('UNI ERR', String(e).slice(0, 200)); }
    await p.close();
  }

  await browser.close();
})();
