const { chromium } = require('playwright-core');
const path=require('path');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT=path.join(__dirname,'shots');
const UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
(async()=>{
 const b=await chromium.launch({executablePath:EXE,headless:true});
 const ctx=await b.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:2,locale:'zh-CN',userAgent:UA});
 const p=await ctx.newPage();
 await p.goto('http://127.0.0.1:8092/',{waitUntil:'networkidle',timeout:60000});
 await p.waitForTimeout(5000);
 await p.screenshot({path:path.join(OUT,'verify-1440.png')});
 console.log('desktop 1440 ok');
 // 移动端
 await p.setViewportSize({width:390,height:844});
 await p.waitForTimeout(1500);
 await p.screenshot({path:path.join(OUT,'verify-390.png')});
 console.log('mobile 390 ok');
 await b.close();
})();
