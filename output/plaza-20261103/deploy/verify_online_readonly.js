// 生产只读验收 v2
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

const BASE = process.env.BASE || 'http://8.138.34.151';
const POST = process.env.POST || 'post-miqsxprw';
const SHOT = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/';

const probe = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  const btns = [...document.querySelectorAll('[data-am-action]')];
  return {
    isManager: document.documentElement.classList.contains('is-manager') || !!window.isManager,
    total: btns.length,
    visible: btns.filter(vis).length,
    cards: document.querySelectorAll('a[href^="/archives/"]').length,
    title: document.title,
  };
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const log = (m) => console.log('[check] ' + m);
  page.on('pageerror', (e) => console.log('  [pageerror] ' + e.message.slice(0, 120)));

  // 1. 匿名
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  log('匿名: ' + JSON.stringify(await page.evaluate(probe)));

  // 2. 登录
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await page.fill('input[name="username"]', 'admin');
  await page.fill('#plainPassword', 'Passw0rd!2026');
  await Promise.all([
    page.waitForLoadState('domcontentloaded').catch(() => {}),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(3000);
  log('登录后: ' + page.url());

  // 3. 编辑器结构化表单
  await page.goto(BASE + '/console/posts/editor?name=' + POST, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(7000);
  const form = await page.evaluate(() => {
    const tas = [...document.querySelectorAll('textarea')];
    const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const text = document.body.innerText;
    return {
      url: location.href,
      textareas: tas.length,
      visibleTas: tas.filter(vis).length,
      hasStruct: /作品说明|项目信息|体验方式|参考资料/.test(text),
      hits: ['作品说明', '项目信息', '体验方式', '参考资料'].filter((k) => text.includes(k)),
      title: document.title,
    };
  });
  log('编辑器: ' + JSON.stringify(form));
  await page.screenshot({ path: SHOT + 'prod-01-editor.png', fullPage: false });

  // 4. 登录态前台
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const mgr = await page.evaluate(probe);
  const api = await page.evaluate(async () => {
    try {
      const r = await fetch('/api/manage/achievements', { credentials: 'include' });
      return r.status;
    } catch (e) { return 'ERR'; }
  });
  log('登录态前台: ' + JSON.stringify(mgr) + ' /api/manage=' + api);
  await page.screenshot({ path: SHOT + 'prod-02-manager-home.png', fullPage: false });

  // 5. 匿名调管理接口
  const c2 = await browser.newContext();
  const p2 = await c2.newPage();
  await p2.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  const anonApi = await p2.evaluate(async () => {
    try { const r = await fetch('/api/manage/achievements'); return r.status; } catch (e) { return 'ERR'; }
  });
  log('匿名 /api/manage = ' + anonApi + '（应 401）');

  await browser.close();
  log('完成');
})().catch((e) => { console.error('验证失败:', e.message); process.exit(1); });
