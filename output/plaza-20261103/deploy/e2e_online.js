// 线上端到端验收：登录后台 -> 前台出现管理按钮 -> 打开编辑弹窗 -> 保存（不改动内容）
// 只做「保存原值」的写操作，验证 PUT + 重新发布链路，不改变成果内容。
const { chromium } = require('playwright');

const BASE = 'http://8.138.34.151';
const USER = 'admin';
const PASS = 'Passw0rd!2026';
const SHOT = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots';

(async () => {
  const browser = await chromium.launch();
  const out = [];

  // ---------- 1) 匿名态 ----------
  const anon = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p1 = await anon.newPage();
  await p1.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p1.waitForTimeout(2500);
  const anonManager = await p1.evaluate(() => document.documentElement.classList.contains('is-manager'));
  const anonBtnVisible = await p1.locator('[data-am-action]').first().isVisible().catch(() => false);
  const anonProxy = await p1.evaluate(() => fetch('/api/manage/achievements').then(r => r.status).catch(e => 'ERR:' + e.message));
  out.push(`匿名：is-manager=${anonManager} 按钮可见=${anonBtnVisible} /api/manage 状态=${anonProxy}`);
  await anon.close();

  // ---------- 2) 管理员登录 ----------
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/console', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  out.push(`登录页 URL=${page.url().replace(BASE, '')}`);

  // Halo 登录页：#username 可见；密码明文填 #plainPassword，提交前由 jsencrypt 加密进隐藏的 #password
  await page.fill('#username', USER);
  await page.fill('#plainPassword', PASS);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {}),
    page.click('button[type="submit"], button:has-text("登录")'),
  ]);
  await page.waitForTimeout(4000);
  const loggedIn = !page.url().includes('/login');
  out.push(`登录后 URL=${page.url().replace(BASE, '')} 登录成功=${loggedIn}`);
  if (!loggedIn) { console.log(out.join('\n')); await browser.close(); process.exit(1); }

  // ---------- 3) 前台：按钮是否出现 ----------
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  const mgr = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
  const btnCount = await page.locator('[data-am-action="edit"]').count();
  const editVisible = await page.locator('[data-am-action="edit"]').first().isVisible().catch(() => false);
  out.push(`管理员：is-manager=${mgr} 编辑按钮数=${btnCount} 首个可见=${editVisible}`);
  await page.screenshot({ path: SHOT + '/online-01-manager-home.png' });

  // ---------- 4) 代理接口（带会话）----------
  const proxyStatus = await page.evaluate(() => fetch('/api/manage/achievements').then(r => r.status).catch(e => 'ERR'));
  out.push(`管理员调 /api/manage 状态=${proxyStatus}`);

  // ---------- 5) 打开编辑弹窗，原值保存 ----------
  const card = page.locator('[data-am-action="edit"]').first();
  const postName = await card.getAttribute('data-am-name');
  await card.click();
  await page.waitForTimeout(800);
  const modalVisible = await page.locator('#am-edit-modal').isVisible();
  const origTitle = await page.inputValue('#am-f-title');
  const origExcerpt = await page.inputValue('#am-f-excerpt');
  out.push(`弹窗可见=${modalVisible} 目标=${postName} 原标题=${origTitle}`);
  await page.screenshot({ path: SHOT + '/online-02-edit-modal.png' });

  await page.click('#am-btn-save');
  await page.waitForTimeout(6000);
  const msg = (await page.locator('#am-edit-msg').innerText().catch(() => '')).trim();
  out.push(`保存结果：${msg}`);
  await page.screenshot({ path: SHOT + '/online-03-saved.png' });

  // ---------- 6) 删除确认弹窗（只打开，不执行）----------
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await page.locator('[data-am-action="delete"]').first().click();
  await page.waitForTimeout(800);
  const delVisible = await page.locator('#am-del-modal').isVisible();
  const delText = (await page.locator('#am-del-body').innerText().catch(() => '')).trim();
  out.push(`删除确认弹窗可见=${delVisible} 文案=${delText.slice(0, 40)}`);
  await page.screenshot({ path: SHOT + '/online-04-delete-confirm.png' });

  // ---------- 7) 数据未被改动 ----------
  const after = await page.evaluate(async (name) => {
    const r = await fetch('/apis/api.content.halo.run/v1alpha1/posts/' + name);
    const d = await r.json();
    return { title: d.spec.title, excerpt: (d.spec.excerpt || {}).raw || '', publish: d.spec.publish };
  }, postName);
  out.push(`保存后：标题=${after.title} 简介=${(after.excerpt || '').slice(0, 30)} 已发布=${after.publish}`);
  out.push(`内容一致=${after.title === origTitle && (after.excerpt || '') === (origExcerpt || '')}`);

  console.log(out.join('\n'));
  await browser.close();
})().catch(e => { console.error('E2E 失败:', e.message); process.exit(2); });
