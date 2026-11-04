const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 3, locale: 'zh-CN' });
  const p = await c.newPage();
  await p.goto('http://boot.jeecg.com/', { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(2500);
  await p.fill('input[placeholder="账号"]', 'jeecg');
  await p.fill('input[placeholder="密码"]', 'jeecg@123456');
  const imgs = await p.$$('img');
  for (const im of imgs) {
    const src = await im.getAttribute('src');
    if (src && src.startsWith('data:image')) { await im.screenshot({ path: 'shots/captcha4.png' }); break; }
  }
  try { fs.unlinkSync('cap4.txt'); } catch (e) {}
  console.log('READY');
  let code = null;
  for (let i = 0; i < 80; i++) {
    if (fs.existsSync('cap4.txt')) { const t = fs.readFileSync('cap4.txt', 'utf8').trim(); if (t) { code = t; break; } }
    await p.waitForTimeout(1000);
  }
  if (!code) { await b.close(); return; }
  await p.fill('input[placeholder="验证码"]', code);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(9000);
  console.log('URL=' + p.url());
  await p.screenshot({ path: 'shots/jeecg-in3.png' });
  await b.close();
})();
