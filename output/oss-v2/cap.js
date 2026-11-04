const { chromium } = require('playwright-core');
const path = require('path');

const EXE = 'C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT = path.join(__dirname, 'shots');
require('fs').mkdirSync(OUT, { recursive: true });

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';

async function shot(page, name) {
  await page.screenshot({ path: path.join(OUT, name + '.png') });
  console.log('SAVED', name, page.url());
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, headless: true, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 2,
    locale: 'zh-CN',
    userAgent: UA,
  });

  const which = process.argv[2] || 'all';

  // ---------- NocoBase ----------
  if (which === 'all' || which === 'noco') {
    const p = await ctx.newPage();
    try {
      await p.goto('https://demo.nocobase.com/new', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await p.waitForTimeout(9000);
      console.log('NOCO url', p.url(), 'title', await p.title());
      await shot(p, 'noco-01-landing');
      // 找进入应用的按钮
      const btn = await p.$('text=Enter');
      if (btn) { await btn.click().catch(() => {}); await p.waitForTimeout(6000); }
      await shot(p, 'noco-02-app');
    } catch (e) { console.log('NOCO ERR', String(e).slice(0, 200)); }
    await p.close();
  }

  // ---------- JeecgBoot ----------
  if (which === 'all' || which === 'jeecg') {
    const p = await ctx.newPage();
    try {
      await p.goto('http://boot.jeecg.com/', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await p.waitForTimeout(5000);
      console.log('JEECG url', p.url(), 'title', await p.title());
      await shot(p, 'jeecg-01-login');
      // 尝试登录 admin / 123456
      const inputs = await p.$$('input');
      console.log('inputs', inputs.length);
      for (const i of inputs) {
        const ph = (await i.getAttribute('placeholder')) || '';
        const id = (await i.getAttribute('id')) || '';
        console.log('  input', id, ph);
      }
    } catch (e) { console.log('JEECG ERR', String(e).slice(0, 200)); }
    await p.close();
  }

  // ---------- uni-app ----------
  if (which === 'all' || which === 'uniapp') {
    const p = await ctx.newPage();
    try {
      await p.goto('https://hellouniapp.dcloud.net.cn/pages/tabBar/component', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await p.waitForTimeout(6000);
      console.log('UNI url', p.url(), 'title', await p.title());
      await shot(p, 'uniapp-01-h5');
    } catch (e) { console.log('UNI ERR', String(e).slice(0, 200)); }
    await p.close();
  }

  await browser.close();
})();
