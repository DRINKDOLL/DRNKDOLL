// 线上只读+权限验收：匿名 401 / student 403 / admin 通过权限校验（用不存在的 name 探测，无副作用）
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

const HOME = 'http://8.138.34.151/';
const API = 'http://8.138.34.151/api/manage/achievements';
const PROBE = '__perm_probe_not_exist__';

async function login(page, user, pass) {
  await page.goto(HOME + 'login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  await page.fill('input[name="username"]', user);
  await page.fill('#plainPassword', pass);
  await Promise.all([
    page.waitForLoadState('domcontentloaded').catch(() => {}),
    page.click('button[type="submit"]')
  ]);
  await page.waitForTimeout(2500);
}

const probe = (page, name) => page.evaluate(async ([url, n]) => {
  const r = await fetch(url + '/' + n, {
    method: 'PUT', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'perm-probe' })
  });
  return { status: r.status, body: (await r.text()).slice(0, 160) };
}, [API, name]);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const out = [];
  const log = (m) => { console.log('[online] ' + m); out.push(m); };

  // 1) 匿名
  {
    const page = await browser.newPage();
    await page.goto(HOME, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    const r = await probe(page, PROBE);
    log('匿名 PUT：HTTP ' + r.status + ' -> ' + r.body);
    await page.close();
  }

  // 2) student
  {
    const page = await browser.newPage();
    await login(page, 'student', 'Student!2026');
    const url = page.url();
    const isMgr = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
    await page.goto(HOME, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const isMgrHome = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
    const btnCount = await page.evaluate(() => document.querySelectorAll('.am-btn-edit').length);
    const r = await probe(page, PROBE);
    log('student 登录后落地页：' + url);
    log('student：首页 is-manager=' + isMgrHome + '，编辑按钮数=' + btnCount + '，PUT HTTP ' + r.status + ' -> ' + r.body);
    await page.close();
  }

  // 3) admin
  {
    const page = await browser.newPage();
    await login(page, 'admin', 'Passw0rd!2026');
    await page.goto(HOME, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const isMgrHome = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
    const btnCount = await page.evaluate(() => document.querySelectorAll('.am-btn-edit').length);
    const r = await probe(page, PROBE);
    const list = await page.evaluate(async (u) => {
      const resp = await fetch(u, { credentials: 'include' });
      const j = await resp.json().catch(() => null);
      return { status: resp.status, count: j && j.items ? j.items.length : (Array.isArray(j) ? j.length : null) };
    }, API);
    log('admin：首页 is-manager=' + isMgrHome + '，编辑按钮数=' + btnCount);
    log('admin：GET 列表 HTTP ' + list.status + '，条目数=' + list.count);
    log('admin：PUT 探测 HTTP ' + r.status + ' -> ' + r.body + '（非 403 即通过权限校验）');
    await page.close();
  }

  await browser.close();
  console.log('=== 验收结束 ===');
})().catch(e => { console.error('验收出错：', e); process.exit(1); });
