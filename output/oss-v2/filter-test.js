const { chromium } = require('playwright-core');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
(async()=>{
  const b=await chromium.launch({executablePath:EXE,headless:true});
  const ctx=await b.newContext({viewport:{width:1440,height:900},locale:'zh-CN'});
  const p=await ctx.newPage();
  const errors=[];
  p.on('pageerror',e=>errors.push(String(e)));
  await p.goto('http://127.0.0.1:8092/',{waitUntil:'networkidle',timeout:60000});
  await p.waitForTimeout(3000);

  // 记录初始卡片数
  const countCards=()=>p.locator('#post-list > div.group').count();

  // 向下滚动，制造非顶部位置
  await p.evaluate(()=>window.scrollTo(0, 400));
  const beforeScroll=await p.evaluate(()=>window.scrollY);
  console.log('初始滚动位置:', beforeScroll);

  // 点击「实训项目」
  const link=p.locator('#filters a[data-filter="cat-sqi57crw"]');
  await link.click();
  await p.waitForTimeout(2500);

  const afterScroll=await p.evaluate(()=>window.scrollY);
  const cards1=await countCards();
  const titles1=await p.locator('#post-list h1 a').allTextContents();
  console.log('点击实训项目后滚动位置:', afterScroll, '(是否保持:', afterScroll===beforeScroll, ')');
  console.log('实训项目卡片数:', cards1, '标题:', JSON.stringify(titles1));

  // 点击「全部」
  const allLink=p.locator('#filters a[data-filter="all"]');
  await allLink.click();
  await p.waitForTimeout(2500);
  const afterScroll2=await p.evaluate(()=>window.scrollY);
  const cards2=await countCards();
  console.log('点击全部后滚动位置:', afterScroll2);
  console.log('全部卡片数:', cards2);

  // 点击「算法模型」
  const link3=p.locator('#filters a[data-filter="cat-i1uojun4"]');
  await link3.click();
  await p.waitForTimeout(2500);
  const cards3=await countCards();
  const titles3=await p.locator('#post-list h1 a').allTextContents();
  console.log('算法模型卡片数:', cards3, '标题:', JSON.stringify(titles3));

  console.log('pageerror:', JSON.stringify(errors));
  await p.screenshot({path:'shots/filter-test.png'});
  await b.close();
})();
