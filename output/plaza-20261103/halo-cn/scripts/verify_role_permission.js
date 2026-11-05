// 端到端验证：管理员可编辑/删除，普通用户不可见且直接调接口被拒
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

const HOME = 'http://127.0.0.1:8092/';
const MANAGE = 'http://127.0.0.1:8093/api/manage/achievements';
const shots = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/';

async function login(page, user, pass) {
  await page.goto(HOME + 'login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(800);
  await page.fill('input[name="username"]', user);
  await page.fill('#plainPassword', pass);
  await Promise.all([
    page.waitForLoadState('domcontentloaded').catch(() => {}),
    page.click('button[type="submit"]')
  ]);
  await page.waitForTimeout(2500);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const log = (m) => console.log('[check] ' + m);

  // ===== 场景 1：匿名访问首页，按钮应隐藏 =====
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(HOME, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const isMgr = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
    const btnDisp = await page.evaluate(() => {
      const el = document.querySelector('.am-mgmt');
      return el ? getComputedStyle(el).display : 'none(无元素)';
    });
    log('匿名：is-manager=' + isMgr + '，管理按钮 display=' + btnDisp);
    await page.screenshot({ path: shots + '40-权限-匿名.png' });
    await page.close();
  }

  // ===== 场景 2：student 登录，按钮应隐藏 =====
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await login(page, 'student', 'Student!2026');
    await page.goto(HOME, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const isMgr = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
    const btnCount = await page.evaluate(() => document.querySelectorAll('.am-btn-edit').length);
    const btnDisp = await page.evaluate(() => {
      const el = document.querySelector('.am-mgmt');
      return el ? getComputedStyle(el).display : 'none(无元素)';
    });
    log('student：is-manager=' + isMgr + '，编辑按钮数=' + btnCount + '，管理按钮 display=' + btnDisp);

    // student 直接调用后端接口（带会话 Cookie）应被 403 拒绝
    const direct = await page.evaluate(async (url) => {
      const resp = await fetch(url, { method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: 'hack' }) });
      const txt = await resp.text();
      return { status: resp.status, body: txt };
    }, MANAGE + '/test-hack');
    log('student 直接调接口：HTTP ' + direct.status + ' -> ' + direct.body);
    await page.screenshot({ path: shots + '41-权限-student.png' });
    await page.close();
  }

  // ===== 场景 3：admin 登录，按钮应显示 =====
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await login(page, 'admin', 'Passw0rd!2026');
    await page.goto(HOME, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const isMgr = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
    const btnCount = await page.evaluate(() => document.querySelectorAll('.am-btn-edit').length);
    log('admin：is-manager=' + isMgr + '，编辑按钮数=' + btnCount);
    await page.screenshot({ path: shots + '42-权限-admin.png' });
    await page.close();
  }

  await browser.close();
  console.log('=== 验证完成 ===');
})().catch(e => { console.error('验证出错：', e); process.exit(1); });
