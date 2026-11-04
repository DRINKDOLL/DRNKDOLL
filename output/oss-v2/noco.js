const { chromium } = require('playwright-core');
const path=require('path');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT=path.join(__dirname,'shots');
const UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
(async()=>{
 const b=await chromium.launch({executablePath:EXE,headless:true});
 const c=await b.newContext({viewport:{width:1600,height:1000},deviceScaleFactor:2,locale:'zh-CN',userAgent:UA});
 for (const [name,url] of [['noco-site','https://www.nocobase.com/cn/'],['noco-docs','https://docs-cn.nocobase.com/welcome/getting-started/overview']]) {
  const p=await c.newPage();
  try{
    await p.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
    await p.waitForTimeout(7000);
    await p.mouse.wheel(0, 1400); await p.waitForTimeout(2500);
    console.log(name, p.url(), await p.title());
    await p.screenshot({path:path.join(OUT,name+'.png')});
  }catch(e){console.log(name,'ERR',String(e).slice(0,120));}
  await p.close();
 }
 await b.close();
})();
