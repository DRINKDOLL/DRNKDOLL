// 成果管理功能端到端验收脚本（使用 oss-selection 里的 playwright + 已下载 chromium）
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

const HOME = 'http://127.0.0.1:8092/';
const shots = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const log = (m) => console.log('[check] ' + m);

  // 1. 匿名访问首页
  await page.goto(HOME, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const isManagerAnon = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
  const btnDisplayAnon = await page.evaluate(() => {
    const el = document.querySelector('.am-mgmt');
    return el ? getComputedStyle(el).display : 'none(no-el)';
  });
  log('匿名：is-manager=' + isManagerAnon + '，管理按钮容器 display=' + btnDisplayAnon);
  await page.screenshot({ path: shots + '35-管理-匿名首页.png' });

  // 2. 登录 admin
  await page.goto(HOME + 'login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  const loginInfo = await page.evaluate(() => {
    return {
      hasUser: !!document.querySelector('input[name="username"]'),
      hasPass: !!document.querySelector('input[name="password"]'),
      hasCsrf: !!document.querySelector('input[name="_csrf"]'),
      csrfVal: (document.querySelector('input[name="_csrf"]') || {}).value || ''
    };
  });
  log('登录表单：' + JSON.stringify(loginInfo));

  if (loginInfo.hasUser && loginInfo.hasPass) {
    await page.fill('input[name="username"]', 'admin');
    // Halo 登录用明文框 #plainPassword，JS 会加密后写入隐藏的 #password
    await page.fill('#plainPassword', 'Passw0rd!2026');
    await Promise.all([
      page.waitForLoadState('domcontentloaded').catch(() => {}),
      page.click('button[type="submit"]')
    ]);
    await page.waitForTimeout(2500);
    const url = page.url();
    log('登录后 URL=' + url);
    await page.screenshot({ path: shots + '36-管理-登录后.png' });
  }

  // 3. 回到首页，检查管理按钮是否显示
  await page.goto(HOME, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const isManager = await page.evaluate(() => document.documentElement.classList.contains('is-manager'));
  const btnDisplay = await page.evaluate(() => {
    const el = document.querySelector('.am-mgmt');
    return el ? getComputedStyle(el).display : 'none(no-el)';
  });
  const btnCount = await page.evaluate(() => document.querySelectorAll('.am-btn-edit').length);
  log('登录后：is-manager=' + isManager + '，按钮容器 display=' + btnDisplay + '，编辑按钮数=' + btnCount);
  await page.screenshot({ path: shots + '37-管理-管理员首页.png' });

  // 4. 测试编辑弹窗
  if (btnCount > 0) {
    const firstName = await page.evaluate(() => document.querySelector('.am-btn-edit').getAttribute('data-am-name'));
    const firstTitle = await page.evaluate(() => document.querySelector('.am-btn-edit').getAttribute('data-am-title'));
    log('编辑目标：name=' + firstName + '，title=' + firstTitle);
    await page.click('.am-btn-edit');
    await page.waitForTimeout(600);
    const modalVisible = await page.evaluate(() => getComputedStyle(document.getElementById('am-edit-modal')).display);
    const titleVal = await page.inputValue('#am-f-title');
    log('编辑弹窗 display=' + modalVisible + '，标题输入框值=' + titleVal);
    await page.screenshot({ path: shots + '38-管理-编辑弹窗.png' });
    // 关闭
    await page.evaluate(() => window.AchievementManage.close());
  }

  // 5. 测试删除确认弹窗
  await page.click('.am-btn-del');
  await page.waitForTimeout(600);
  const delVisible = await page.evaluate(() => getComputedStyle(document.getElementById('am-del-modal')).display);
  const delBody = await page.evaluate(() => document.getElementById('am-del-body').textContent);
  log('删除弹窗 display=' + delVisible + '，内容=' + delBody.slice(0, 40));
  await page.screenshot({ path: shots + '39-管理-删除确认弹窗.png' });
  // 取消（不真正删除）
  await page.evaluate(() => window.AchievementManage.close());

  await browser.close();
  log('验收完成');
})().catch(e => { console.error('验收失败:', e.message); process.exit(1); });
