const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, locale: 'zh-CN' });
  const p = await c.newPage();
  await p.goto('http://boot.jeecg.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(3500);
  await p.fill('input[placeholder="账号"]', 'jeecg');
  await p.fill('input[placeholder="密码"]', 'jeecg@123456');
  const imgs = await p.$$('img');
  for (const im of imgs) {
    const src = await im.getAttribute('src');
    if (src && src.startsWith('data:image')) { await im.screenshot({ path: 'shots/captcha3.png' }); break; }
  }
  const f = 'cap3.txt';
  try { fs.unlinkSync(f); } catch (e) {}
  console.log('READY');
  let code = null;
  for (let i = 0; i < 70; i++) {
    if (fs.existsSync(f)) { const t = fs.readFileSync(f, 'utf8').trim(); if (t) { code = t; break; } }
    await p.waitForTimeout(1000);
  }
  console.log('CODE=' + code);
  if (!code) { await b.close(); return; }
  await p.fill('input[placeholder="验证码"]', code);
  await p.waitForTimeout(300);
  await p.click('button:has-text("登 录")');
  await p.waitForTimeout(9000);
  console.log('URL=' + p.url());
  await p.screenshot({ path: 'shots/jeecg-in2.png' });
  await b.close();
})();
