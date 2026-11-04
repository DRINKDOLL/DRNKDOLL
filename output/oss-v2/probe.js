const { chromium } = require('playwright-core');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
(async()=>{
 const b=await chromium.launch({executablePath:EXE,headless:true});
 const c=await b.newContext({viewport:{width:1600,height:1000},locale:'zh-CN'});
 const p=await c.newPage();
 await p.goto('http://127.0.0.1:8092/console',{waitUntil:'domcontentloaded',timeout:60000});
 await p.waitForTimeout(3000);
 const ins=await p.$$eval('input',a=>a.map(x=>({name:x.name,type:x.type,ph:x.placeholder,id:x.id,vis:!!x.offsetParent})));
 console.log(JSON.stringify(ins,null,1));
 const btn=await p.$$eval('button',a=>a.map(x=>x.textContent.trim()).slice(0,8));
 console.log('BTN',JSON.stringify(btn));
 await b.close();
})();
