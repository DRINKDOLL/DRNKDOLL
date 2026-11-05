// 删除后卡片实时移除的验证（删除后立即还原）
const { chromium } = require('C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/node_modules/playwright');
const http = require('http');

const HOME = 'http://127.0.0.1:8092/';
const shots = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn/shots/';

function restoreDeleted(name, title, excerpt, cover) {
  return new Promise((resolve) => {
    // 直接调 Halo console API 恢复：先查 console 列表拿 post，再设 deleted=false + publish
    const auth = 'Basic ' + Buffer.from('admin:Passw0rd!2026').toString('base64');
    const get = (path, cb) => {
      const r = http.request({ host:'127.0.0.1', port:8092, path, method:'GET', headers:{'Authorization':auth} }, res => {
        let d=''; res.on('data',c=>d+=c); res.on('end',()=>cb(res.statusCode, d));
      }); r.end();
    };
    const put = (path, body, cb) => {
      const payload = JSON.stringify(body);
      const r = http.request({ host:'127.0.0.1', port:8092, path, method:'PUT', headers:{'Authorization':auth,'Content-Type':'application/json','Content-Length':Buffer.byteLength(payload)} }, res => {
        let d=''; res.on('data',c=>d+=c); res.on('end',()=>cb(res.statusCode, d));
      }); r.end(payload);
    };
    get('/apis/api.console.halo.run/v1alpha1/posts?page=1&size=100', (s1, list) => {
      const items = JSON.parse(list).items;
      const item = items.find(it => it.post.metadata.name === name);
      const post = item.post;
      const spec = Object.assign({}, post.spec, { deleted: false });
      const metadata = Object.assign({}, post.metadata);
      delete metadata.creationTimestamp; delete metadata.generation; delete metadata.managedFields; delete metadata.deletionTimestamp;
      get('/apis/api.console.halo.run/v1alpha1/posts/' + name + '/head-content', (s2, hcRaw) => {
        const hc = JSON.parse(hcRaw);
        put('/apis/api.console.halo.run/v1alpha1/posts/' + name, {
          post: { spec, metadata },
          content: { raw: hc.raw || '', content: hc.content || '', rawType: hc.rawType || 'markdown' }
        }, (s3) => {
          put('/apis/api.console.halo.run/v1alpha1/posts/' + name + '/publish', {}, (s4) => resolve(s4));
        });
      });
    });
  });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const log = (m) => console.log('[check] ' + m);

  await page.goto(HOME + 'login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(800);
  await page.fill('input[name="username"]', 'admin');
  await page.fill('#plainPassword', 'Passw0rd!2026');
  await Promise.all([page.waitForLoadState('domcontentloaded').catch(() => {}), page.click('button[type="submit"]')]);
  await page.waitForTimeout(2000);
  await page.goto(HOME, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);

  // 选最后一个项目（work-robot）来测试删除（避免动第一个）
  const name = await page.evaluate(() => {
    const btns = document.querySelectorAll('.am-btn-del');
    return btns[btns.length - 1].getAttribute('data-am-name');
  });
  const title = await page.evaluate((n) => document.querySelector('.am-btn-del[data-am-name="' + n + '"]').getAttribute('data-am-title'), name);
  log('删除目标 name=' + name + '，title=' + title);

  const beforeCount = await page.evaluate(() => document.querySelectorAll('[data-am-name]').length);
  log('删除前卡片数=' + beforeCount);

  // 点删除按钮
  await page.evaluate((n) => {
    const btn = document.querySelector('.am-btn-del[data-am-name="' + n + '"]');
    btn.click();
  }, name);
  await page.waitForTimeout(600);
  const delModal = await page.evaluate(() => getComputedStyle(document.getElementById('am-del-modal')).display);
  log('删除确认弹窗 display=' + delModal);

  // 确认删除
  await page.click('#am-btn-del');
  await page.waitForTimeout(2000);
  const afterCount = await page.evaluate(() => document.querySelectorAll('[data-am-name]').length);
  const stillThere = await page.evaluate((n) => !!document.querySelector('[data-am-name="' + n + '"]'), name);
  log('删除后卡片数=' + afterCount + '，目标卡片仍存在=' + stillThere);
  await page.screenshot({ path: shots + '41-管理-删除后列表.png' });

  // 还原
  await restoreDeleted(name, title);
  await new Promise(r => setTimeout(r, 1500));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const restored = await page.evaluate((n) => !!document.querySelector('[data-am-name="' + n + '"]'), name);
  log('还原后目标卡片存在=' + restored);

  await browser.close();
  log('删除流程验收完成');
})().catch(e => { console.error('失败:', e.message); process.exit(1); });
