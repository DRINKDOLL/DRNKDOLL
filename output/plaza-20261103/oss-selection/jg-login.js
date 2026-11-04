const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, locale: 'zh-CN' });
  const p = await c.newPage();
  await p.goto('http://boot.jeecg.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(3500);

  // fill account / password
  await p.fill('input[placeholder*="账号"], input[placeholder*="用户"]', 'jeecg').catch(() => {});
  await p.fill('input[type="password"]', 'jeecg@123456').catch(() => {});
  await p.waitForTimeout(500);

  // captcha image is the data:image one
  const imgs = await p.$$('img');
  let cap = null;
  for (const im of imgs) {
    const src = await im.getAttribute('src');
    if (src && src.startsWith('data:image')) { cap = im; break; }
  }
  if (cap) await cap.screenshot({ path: 'shots/captcha2.png' });
  console.log('CAPTCHA_READY');

  // wait for code file
  const f = 'C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/oss-selection/cap.txt';
  let code = null;
  for (let i = 0; i < 60; i++) {
    if (fs.existsSync(f)) {
      const t = fs.readFileSync(f, 'utf8').trim();
      if (t) { code = t; break; }
    }
    await p.waitForTimeout(1000);
  }
  console.log('CODE', code);
  if (!code) { await b.close(); return; }

  // fill captcha: the input next to captcha
  const inputs = await p.$$('input');
  // last empty visible text input is usually captcha
  for (let i = inputs.length - 1; i >= 0; i--) {
    const type = await inputs[i].getAttribute('type');
    const val = await inputs[i].inputValue().catch(() => '');
    const vis = await inputs[i].isVisible().catch(() => false);
    if (vis && type !== 'password' && !val) { await inputs[i].fill(code); break; }
  }
  await p.waitForTimeout(400);
  await p.click('button:has-text("登 录"), button:has-text("登录")').catch(() => {});
  await p.waitForTimeout(8000);
  console.log('AFTER', p.url(), await p.title());
  await p.screenshot({ path: 'shots/jeecg-in.png' });
  await b.close();
})();
