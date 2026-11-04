const { chromium } = require('playwright-core');
const path=require('path'), fs=require('fs');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT=path.join(__dirname,'shots');
const UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const ANS=path.join(__dirname,'answer.txt');
(async()=>{
 const b=await chromium.launch({executablePath:EXE,headless:true});
 const c=await b.newContext({viewport:{width:1600,height:1000},deviceScaleFactor:2,locale:'zh-CN',userAgent:UA});
 const p=await c.newPage();
 await p.goto('http://boot.jeecg.com/login?redirect=/dashboard/analysis',{waitUntil:'domcontentloaded',timeout:60000});
 await p.waitForTimeout(5000);
 const ins=p.locator('input');
 await ins.nth(0).fill('jeecg');
 await ins.nth(1).fill('jeecg@123456');
 const src=await p.locator('img[src^="data:image"]').first().getAttribute('src');
 fs.writeFileSync(path.join(OUT,'captcha.jpg'), src.split(',')[1], 'base64');
 fs.writeFileSync(path.join(__dirname,'ready.flag'),'1');
 let ans=null;
 for(let i=0;i<150;i++){
   if(fs.existsSync(ANS)){ ans=fs.readFileSync(ANS,'utf8').trim(); if(ans) break; }
   await p.waitForTimeout(1000);
 }
 if(!ans){ console.log('NO ANSWER'); await b.close(); return; }
 console.log('answer',JSON.stringify(ans));
 await ins.nth(2).fill(ans);
 await p.locator('button:has-text("登")').first().click();
 await p.waitForTimeout(10000);
 console.log('url',p.url());
 await p.screenshot({path:path.join(OUT,'jeecg-03-dashboard.png')});
 const err=await p.locator('.ant-message-notice-content').first().textContent().catch(()=>'');
 if(err) console.log('MSG',err);
 await b.close();
})();
