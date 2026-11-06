// 刷新 shots/ui-check.json：抓取当前控制台/前台页面可见文本快照（en-US 上下文）
// 依赖：oss-selection/node_modules/playwright + 已下载 chromium
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');
const fs = require('fs');

const BASE = 'http://127.0.0.1:8092';
const OUT = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/ui-check.json';
const USER = 'admin';
const PASS = 'Passw0rd!2026';

const PAGES = [
  { name: '首页', url: BASE + '/' },
  { name: '文章详情', url: BASE + '/archives/hello-halo' },
  { name: '控制台登录页', url: BASE + '/login?authentication_required' },
  { name: '控制台仪表盘', url: BASE + '/console/dashboard' },
  { name: '控制台设置', url: BASE + '/console/settings' },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ locale: 'en-US', extraHTTPHeaders: { 'Accept-Language': 'en-US' } });
  const page = await ctx.newPage();

  // 先登录控制台（保持会话）
  try {
    await page.goto(BASE + '/console', { waitUntil: 'domcontentloaded', timeout: 20000 });
    if (page.url().includes('/login')) {
      // 切到「本地账号登录」模式（绕过统一身份 BFF）
      const toggle = await page.$('#unified-login-toggle');
      if (toggle) { await toggle.click(); await page.waitForTimeout(300); }
      await page.fill('#username', USER);
      await page.fill('#plainPassword', PASS);
      await page.click('button[type="submit"]');
      await page.waitForTimeout(3000);
      console.log('[login] ok ->', page.url());
    }
  } catch (e) {
    console.log('[login] skipped:', e.message);
  }

  const out = { locale: 'en-US', pages: [] };
  for (const p of PAGES) {
    try {
      await page.goto(p.url, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(1800);
      const lang = await page.evaluate(() => document.documentElement.lang || '');
      const text = (await page.evaluate(() => document.body.innerText || '')).replace(/\s+/g, ' ').trim();
      out.pages.push({ name: p.name, url: p.url, lang, text });
      console.log('[ok]', p.name, 'lang=' + lang, 'len=' + text.length);
    } catch (e) {
      console.log('[fail]', p.name, e.message);
      out.pages.push({ name: p.name, url: p.url, lang: '', text: '' });
    }
  }

  fs.writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf-8');
  console.log('written:', OUT);
  await browser.close();
})();
