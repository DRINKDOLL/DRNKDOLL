const { chromium } = require('playwright-core');
const path=require('path'), fs=require('fs');
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
 await ins.nth(0).fill('jeecg');
 await ins.nth(1).fill('jeecg@123456');
 // 保存验证码
 const src=await p.locator('img[src^="data:image"]').first().getAttribute('src');
 fs.writeFileSync(path.join(OUT,'captcha.b64'), src.split(',')[1], 'base64');
 console.log('captcha saved');
 // 等待答案文件
 const ansFile='/tmp/jg_answer.txt';
 try{fs.unlinkSync(ansFile);}catch(e){}
 let ans=null;
 for(let i=0;i<180;i++){
   if(fs.existsSync(ansFile)){ ans=fs.readFileSync(ansFile,'utf8').trim(); if(ans) break; }
   await p.waitForTimeout(1000);
 }
 if(!ans){ console.log('NO ANSWER'); await b.close(); return; }
 console.log('answer',ans);
 await ins.nth(2).fill(ans);
 await p.locator('button:has-text("登")').first().click();
 await p.waitForTimeout(9000);
 console.log('url',p.url());
 await p.screenshot({path:path.join(OUT,'jeecg-03-dashboard.png')});
 if(p.url().includes('login')){
   const err=await p.locator('.ant-message-notice-content').first().textContent().catch(()=>'');
   console.log('ERRMSG',err);
 }
 await b.close();
})();
