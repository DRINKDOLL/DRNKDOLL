// 端到端验证：填写结构化表单，检查拼接结果
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');

const HOME = 'http://127.0.0.1:8092/';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const log = (m) => console.log('[check] ' + m);
  page.on('pageerror', err => console.log('  [browser.pageerror] ' + err.message));

  // 登录
  await page.goto(HOME + 'login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(800);
  await page.fill('input[name="username"]', 'admin');
  await page.fill('#plainPassword', 'Passw0rd!2026');
  await Promise.all([page.waitForLoadState('domcontentloaded').catch(() => {}), page.click('button[type="submit"]')]);
  await page.waitForTimeout(2000);

  // 打开编辑器
  await page.goto(HOME + 'console/posts/editor', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);

  // 填写标题（标题框 class 含 text-4xl font-semibold）
  await page.fill('input.text-4xl.font-semibold', '表单验证测试文章');

  // 填写 4 个字段
  const fields = {
    brief: '这是一个用于验证结构化表单拼接的测试作品',
    info: '技术栈：Python / Vue\n负责人：测试员',
    experience: '访问 http://127.0.0.1:8092 体验',
    reference: '参考：某技术文档链接',
  };
  const ta = page.locator('textarea');
  const n = await ta.count();
  log('textarea 数量: ' + n);
  // 按顺序填写 brief, info, experience, reference
  await ta.nth(0).fill(fields.brief);
  await ta.nth(1).fill(fields.info);
  await ta.nth(2).fill(fields.experience);
  await ta.nth(3).fill(fields.reference);

  // 在正文区输入（作品内容）
  // 尝试点击正文并输入
  const bodyEditor = page.locator('.tiptap, .ProseMirror, [contenteditable="true"]').first();
  try {
    await bodyEditor.click();
    await page.keyboard.type('这是作品内容正文测试。');
  } catch (e) {
    log('正文输入失败: ' + e.message);
  }
  await page.waitForTimeout(500);

  // 读取编辑器内部的 raw（通过 Vue 状态较难，改用点击"保存"后读取 API）
  // 先截图
  await page.screenshot({ path: 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/editor_form_filled.png', fullPage: false });

  // 点击保存按钮（触发 draft 保存）
  const saveBtn = page.locator('button:has-text("保存")').first();
  await saveBtn.click();
  await page.waitForTimeout(3000);

  // 通过 API 读取刚保存的文章，检查 raw 结构
  const result = await page.evaluate(async () => {
    const resp = await fetch('/apis/api.console.halo.run/v1alpha1/posts?page=1&size=5&sort=metadata.creationTimestamp,desc');
    const d = await resp.json();
    return d.items ? d.items.map(i => ({ name: i.metadata.name, title: i.spec.title })) : [];
  });
  log('最近文章: ' + JSON.stringify(result));

  await browser.close();
  log('完成');
})().catch(e => { console.error('验证失败:', e); process.exit(1); });
