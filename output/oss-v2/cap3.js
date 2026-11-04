const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');
const EXE = 'C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT = path.join(__dirname, 'shots');
fs.mkdirSync(OUT, { recursive: true });
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';

(async () => {
  const b = await chromium.launch({ executablePath: EXE, headless: true });
  const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, locale: 'zh-CN', userAgent: UA, timezoneId: 'Asia/Shanghai' });
  const p = await ctx.newPage();

  // 前台首页
  await p.goto('http://127.0.0.1:8092/', { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(5000);
  await p.screenshot({ path: path.join(OUT, 'halo-01-front.png') });
  console.log('front', await p.title());

  // 作品详情页
  const link = p.locator('a').filter({ hasText: '涉诈资金流向可视化分析平台' }).first();
  if (await link.count()) {
    await link.click();
    await p.waitForTimeout(5000);
    await p.screenshot({ path: path.join(OUT, 'halo-02-detail.png') });
    console.log('detail', p.url());
  }

  // 控制台登录
  await p.goto('http://127.0.0.1:8092/console', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(4000);
  if (await p.locator('#username').count()) {
    await p.locator('#username').fill('admin');
    await p.locator('#plainPassword').fill('Passw0rd!2026');
    await p.locator('button:has-text("登录")').first().click();
    await p.waitForTimeout(7000);
  }
  console.log('console url', p.url());
  await p.screenshot({ path: path.join(OUT, 'halo-03-console.png') });

  // 文章管理列表
  await p.goto('http://127.0.0.1:8092/console/posts', { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
  await p.waitForTimeout(6000);
  await p.screenshot({ path: path.join(OUT, 'halo-04-posts.png') });
  console.log('posts url', p.url());

  await b.close();
})();
