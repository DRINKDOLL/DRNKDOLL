const { chromium } = require('playwright-core');
const EXE='C:/Users/LENOVO/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
(async()=>{
 const b=await chromium.launch({executablePath:EXE,headless:true});
 const ctx=await b.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
 const p=await ctx.newPage();
 await p.goto('http://127.0.0.1:8092/',{waitUntil:'networkidle',timeout:60000});
 await p.waitForTimeout(3000);
 const info=await p.evaluate(()=>{
   const list=document.querySelector('#post-list');
   const cards=document.querySelectorAll('#post-list > div.group');
   const sidebar=document.querySelector('aside, .sidebar, [class*=sidebar]');
   const section=document.querySelector('.mx-auto.mt-6.grid');
   function rect(el){ if(!el) return null; const r=el.getBoundingClientRect(); return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}; }
   const cardRects=[];
   cards.forEach(c=>{const r=c.getBoundingClientRect(); cardRects.push({x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width)});});
   const gs=getComputedStyle(list);
   return { listRect:rect(list), listGridCols:gs.gridTemplateColumns, cardCount:cards.length, cardRects:cardRects.slice(0,6), sectionRect:rect(section), viewport:window.innerWidth };
 });
 console.log(JSON.stringify(info,null,2));
 await b.close();
})();
