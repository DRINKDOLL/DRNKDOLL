// 线上登录页验收：统一身份提示可见、本地账号可切换、前端无 JS 报错、bffUrl 走同源
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  await page.goto('http://8.138.34.151/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);

  const hint = await page.locator('#unified-login-hint').isVisible().catch(() => false);
  const hintText = (await page.locator('#unified-login-hint').innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 80);
  const toggle = await page.locator('#unified-login-toggle').innerText().catch(() => '');
  const hasUser = await page.locator('input[name="username"]').count();
  const hasPwd = await page.locator('#plainPassword').count();
  const bffProbe = await page.evaluate(async () => {
    const r = await fetch('/api/unified-login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'x', password: 'y' })
    });
    return r.status;
  });

  console.log('[1] 统一身份提示可见:', hint, '|', hintText);
  console.log('[2] 切换入口文案:', toggle);
  console.log('[3] 用户名框:', hasUser, '密码框:', hasPwd);
  console.log('[4] 同源 BFF 探测 HTTP:', bffProbe);
  console.log('[5] 前端错误:', errors.length ? errors.join(' || ') : '无');

  // 点一下兜底切换，确认本地模式可用
  await page.click('#unified-login-toggle').catch(() => {});
  await page.waitForTimeout(500);
  const toggleAfter = await page.locator('#unified-login-toggle').innerText().catch(() => '');
  console.log('[6] 切换后文案:', toggleAfter);

  await page.screenshot({ path: 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/deploy/login-online.png' });
  await browser.close();
})().catch((e) => { console.error('验收出错：', e.message); process.exit(1); });
