// 验证文章编辑器中的结构化表单
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

const HOME = 'http://127.0.0.1:8092/';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
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
  log('登录后 URL: ' + page.url());

  // 打开文章编辑器（新建文章）
  await page.goto(HOME + 'console/posts/editor', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  log('编辑器 URL: ' + page.url());

  // 检查结构化表单是否出现
  const formCount = await page.locator('text=结构化信息').count();
  log('「结构化信息」出现次数: ' + formCount);

  const fieldLabels = ['作品说明', '项目信息', '体验方式', '参考资料'];
  for (const lbl of fieldLabels) {
    const c = await page.locator('text=' + lbl).count();
    log('字段「' + lbl + '」出现次数: ' + c);
  }

  // 检查 textarea 数量
  const taCount = await page.locator('textarea').count();
  log('textarea 数量: ' + taCount);

  // 截图
  await page.screenshot({ path: 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/editor_form_check.png', fullPage: false });

  await browser.close();
  log('完成');
})().catch(e => { console.error('验证失败:', e); process.exit(1); });
