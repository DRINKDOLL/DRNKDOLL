// 统一身份登录（论坛账号 → Halo 本地会话）端到端验收脚本
// 依赖：oss-selection/node_modules/playwright + 已下载 chromium
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

const BASE = 'http://127.0.0.1:8092';
const shots = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/';
const log = (m) => console.log('[check] ' + m);

let failures = 0;
function assert(cond, name, extra) {
  console.log((cond ? '[PASS] ' : '[FAIL] ') + name + (extra ? ' -> ' + extra : ''));
  if (!cond) failures++;
}

async function newPage(browser, tag) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  return { ctx, page, errors };
}

async function isLoggedIn(page) {
  // 登录成功后 Spring Security 跳转，页面出现登出入口 / 个人中心入口
  return page.evaluate(async () => {
    const r = await fetch('/apis/api.console.halo.run/v1alpha1/users/-', { credentials: 'include' });
    if (r.status === 200) {
      const j = await r.json();
      return { ok: true, name: (j.user && j.user.metadata && j.user.metadata.name) || '' };
    }
    return { ok: false, name: '' };
  });
}

(async () => {
  const browser = await chromium.launch({ headless: true });

  // ---------- 用例 1：统一身份登录成功（论坛管理员账号） ----------
  {
    const { ctx, page, errors } = await newPage(browser, 'unified-ok');
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: shots + '50-登录页-统一身份.png' });

    const hintVisible = await page.isVisible('#unified-login-hint');
    const toggleText = (await page.textContent('#unified-login-toggle')) || '';
    assert(hintVisible, '登录页展示统一身份提示');
    assert(toggleText.includes('本地账号'), '存在「使用本地账号登录」兜底入口', toggleText.trim());

    await page.fill('input[name="username"]', 'admin');
    await page.fill('#plainPassword', 'Admin@12345');
    await page.click('#login-form button[type="submit"]');
    await page.waitForTimeout(6000);

    const state = await isLoggedIn(page);
    assert(state.ok, '统一身份登录后已建立 Halo 会话', state.name);
    assert(state.name === 'forum-1', '会话身份为 forum-<uid> 映射账号', state.name);
    assert(errors.length === 0, '控制台无 JS 报错', errors.join(' | '));
    await page.screenshot({ path: shots + '51-登录后-统一身份.png' });

    // 管理员应能进入控制台
    await page.goto(BASE + '/console/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    const consoleOk = page.url().includes('/console');
    assert(consoleOk, '统一身份管理员可进入 /console', page.url());
    await page.screenshot({ path: shots + '52-控制台-统一身份管理员.png' });
    await ctx.close();
  }

  // ---------- 用例 2：密码错误统一提示（防枚举） ----------
  {
    const { ctx, page } = await newPage(browser, 'unified-bad');
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);
    await page.fill('input[name="username"]', 'admin');
    await page.fill('#plainPassword', 'definitely-wrong');
    await page.click('#login-form button[type="submit"]');
    await page.waitForTimeout(4000);
    const errText = (await page.textContent('#unified-login-error-text')) || '';
    const errShown = await page.isVisible('#unified-login-error');
    const url = page.url();
    assert(errShown && errText.includes('账号或密码错误'), '错误密码显示统一提示', errText.trim());
    assert(url.includes('/login'), '错误密码未跳转（未建立会话）', url);
    await page.screenshot({ path: shots + '53-登录失败提示.png' });
    await ctx.close();
  }

  // ---------- 用例 3：本地账号兜底登录（admin / 本地密码） ----------
  {
    const { ctx, page } = await newPage(browser, 'local-ok');
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);
    await page.click('#unified-login-toggle');
    await page.waitForTimeout(300);
    const hintHidden = !(await page.isVisible('#unified-login-hint'));
    assert(hintHidden, '切换到本地登录后隐藏统一身份提示');

    await page.fill('input[name="username"]', 'admin');
    await page.fill('#plainPassword', 'Passw0rd!2026');
    await page.click('#login-form button[type="submit"]');
    await page.waitForTimeout(6000);
    const state = await isLoggedIn(page);
    assert(state.ok && state.name === 'admin', '本地账号 admin 可正常登录', state.name);
    await page.screenshot({ path: shots + '54-本地账号登录.png' });
    await ctx.close();
  }

  await browser.close();
  console.log(failures === 0 ? '\n=== 全部通过 ===' : '\n=== 失败 ' + failures + ' 项 ===');
  process.exit(failures === 0 ? 0 : 1);
})();
