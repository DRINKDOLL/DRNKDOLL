const { chromium } = require('playwright-core');
const path=require('path');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const OUT=path.join(__dirname,'shots');
(async()=>{
  const b=await chromium.launch({executablePath:EXE,headless:true});
  const ctx=await b.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:2,locale:'zh-CN'});
  const p=await ctx.newPage();
  await p.goto('http://127.0.0.1:8092/',{waitUntil:'networkidle',timeout:60000});
  await p.waitForTimeout(3000);
  const filters=await p.locator('#filters a').allTextContents();
  console.log('分类栏:', JSON.stringify(filters.map(s=>s.trim())));
  const menu=await p.locator('#header-menu a').allTextContents();
  console.log('导航菜单:', JSON.stringify(menu.map(s=>s.trim())));
  await p.screenshot({path:path.join(OUT,'verify-nofilter.png')});
  await b.close();
})();
