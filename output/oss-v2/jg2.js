const { chromium } = require('playwright-core');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
(async()=>{
 const b=await chromium.launch({executablePath:EXE,headless:true});
 const c=await b.newContext({viewport:{width:1600,height:1000},locale:'zh-CN'});
 const p=await c.newPage();
 await p.goto('http://boot.jeecg.com/login',{waitUntil:'domcontentloaded',timeout:60000});
 await p.waitForTimeout(5000);
 const html=await p.content();
 const i=html.indexOf('验证码');
 console.log(html.slice(i-200,i+1200).replace(/\s+/g,' '));
 await b.close();
})();
