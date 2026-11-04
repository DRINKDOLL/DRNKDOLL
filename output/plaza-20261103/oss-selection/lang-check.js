const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch();
  // 故意用 en-US，检验界面的中文是否由服务端配置决定，而不是靠浏览器语言
  const ctx = await b.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    locale: 'en-US',
    extraHTTPHeaders: { 'Accept-Language': 'en-US,en;q=0.9' },
  });
  const p = await ctx.newPage();

  // 1) 站点前台
  await p.goto('http://127.0.0.1:8090/', { waitUntil: 'networkidle', timeout: 45000 }).catch(e => console.log('front err', e.message));
  await p.waitForTimeout(2500);
  console.log('FRONT title =', await p.title());
  console.log('FRONT lang =', await p.evaluate(() => document.documentElement.lang));
  const frontText = await p.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 400));
  console.log('FRONT text =', frontText);
  await p.screenshot({ path: 'langshots/front-en-locale.png' });

  // 2) 控制台登录页
  await p.goto('http://127.0.0.1:8090/console', { waitUntil: 'networkidle', timeout: 45000 }).catch(e => console.log('console err', e.message));
  await p.waitForTimeout(3000);
  console.log('CONSOLE url =', p.url());
  console.log('CONSOLE html lang =', await p.evaluate(() => document.documentElement.lang));
  const consoleText = await p.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 400));
  console.log('CONSOLE text =', consoleText);
  await p.screenshot({ path: 'langshots/console-en-locale.png' });

  await b.close();
})();
