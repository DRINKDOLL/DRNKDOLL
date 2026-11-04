const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: 'zh-CN' });
  const p = await c.newPage();
  await p.goto('http://boot.jeecg.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(4000);
  const imgs = await p.$$('img');
  for (let i = 0; i < imgs.length; i++) {
    const box = await imgs[i].boundingBox();
    if (box && box.width > 60 && box.width < 200 && box.height > 20) {
      console.log('captcha candidate', i, JSON.stringify(box), await imgs[i].getAttribute('src'));
      await imgs[i].screenshot({ path: 'shots/captcha.png' });
    }
  }
  await b.close();
})();
