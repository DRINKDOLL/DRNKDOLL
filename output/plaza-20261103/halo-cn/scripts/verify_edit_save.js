// 编辑保存 + 列表原地更新 + 还原的端到端验证
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');
const http = require('http');

const HOME = 'http://127.0.0.1:8092/';
const shots = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/';

function proxyPut(name, body) {
  return new Promise((resolve) => {
    const payload = JSON.stringify(body);
    const req = http.request({
      host: '127.0.0.1', port: 8093,
      path: '/api/manage/achievements/' + encodeURIComponent(name),
      method: 'PUT', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) }
    }, res => { let d=''; res.on('data',c=>d+=c); res.on('end',()=>resolve(res.statusCode)); });
    req.end(payload);
  });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const log = (m) => console.log('[check] ' + m);
  page.on('console', msg => console.log('  [browser.' + msg.type() + '] ' + msg.text()));
  page.on('pageerror', err => console.log('  [browser.pageerror] ' + err.message));

  // 登录
  await page.goto(HOME + 'login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(800);
  await page.fill('input[name="username"]', 'admin');
  await page.fill('#plainPassword', 'Passw0rd!2026');
  await Promise.all([page.waitForLoadState('domcontentloaded').catch(() => {}), page.click('button[type="submit"]')]);
  await page.waitForTimeout(2000);

  await page.goto(HOME, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);

  const name = await page.evaluate(() => document.querySelector('.am-btn-edit').getAttribute('data-am-name'));
  const origTitle = await page.evaluate(() => document.querySelector('.am-btn-edit').getAttribute('data-am-title'));
  const origExcerpt = await page.evaluate(() => document.querySelector('.am-btn-edit').getAttribute('data-am-excerpt'));
  log('目标 name=' + name + '，原标题=' + origTitle);

  // 编辑：改标题 + 简介，保存
  await page.click('.am-btn-edit');
  await page.waitForTimeout(500);
  const newTitle = origTitle + '[临时]';
  await page.fill('#am-f-title', newTitle);
  await page.fill('#am-f-excerpt', '临时测试简介');
  await page.click('#am-btn-save');
  await page.waitForTimeout(2000);

  // 检查弹窗内的成功提示
  const editMsg = await page.evaluate(() => {
    const el = document.getElementById('am-edit-msg');
    return (el.style.display !== 'none') ? el.textContent : '(无提示)';
  });
  log('编辑提示=' + editMsg);

  // 检查卡片标题是否原地更新
  const cardTitle = await page.evaluate((n) => {
    const card = document.querySelector('[data-am-name="' + n + '"]');
    const t = card && card.querySelector('[data-am-title]');
    return t ? t.textContent : '(未找到)';
  }, name);
  log('保存后卡片标题=' + cardTitle + '（期望=' + newTitle + '）');
  await page.screenshot({ path: shots + '40-管理-编辑保存后.png' });

  // 还原
  await proxyPut(name, { title: origTitle, excerpt: origExcerpt });
  await new Promise(r => setTimeout(r, 1500));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const reverted = await page.evaluate((n) => {
    const card = document.querySelector('[data-am-name="' + n + '"]');
    const t = card && card.querySelector('[data-am-title]');
    return t ? t.textContent : '(未找到)';
  }, name);
  log('还原后卡片标题=' + reverted);

  await browser.close();
  log('编辑保存验收完成');
})().catch(e => { console.error('失败:', e.message); process.exit(1); });
