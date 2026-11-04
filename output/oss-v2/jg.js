const { chromium } = require('playwright-core');
const path=require('path');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT=path.join(__dirname,'shots');
const UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
(async()=>{
 const b=await chromium.launch({executablePath:EXE,headless:true});
 const c=await b.newContext({viewport:{width:1600,height:1000},deviceScaleFactor:2,locale:'zh-CN',userAgent:UA});
 const p=await c.newPage();
 await p.goto('http://boot.jeecg.com/login?redirect=/dashboard/analysis',{waitUntil:'domcontentloaded',timeout:60000});
 await p.waitForTimeout(5000);
 const ins=p.locator('input');
 const n=await ins.count(); console.log('inputs',n);
 for(let i=0;i<n;i++){const el=ins.nth(i);console.log(i, await el.getAttribute('placeholder'), await el.getAttribute('type'));}
 await ins.nth(0).fill('admin');
 await ins.nth(1).fill('123456');
 await ins.nth(2).fill('1234');
 await p.waitForTimeout(300);
 await p.locator('button:has-text("登")').first().click().catch(e=>console.log('click err'));
 await p.waitForTimeout(9000);
 console.log('url',p.url());
 await p.screenshot({path:path.join(OUT,'jeecg-after.png')});
 const msg=await p.locator('.ant-message, .el-message, .ivu-message').first().textContent().catch(()=>null);
 console.log('msg',msg);
 await b.close();
})();
