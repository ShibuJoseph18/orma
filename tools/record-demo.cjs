const {chromium}=require('C:/Users/shibu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),work=path.join(root,'.data/narration'),out=path.join(root,'.data/recording');
function wavDuration(file){const b=fs.readFileSync(file);let pos=12,rate=0;while(pos+8<=b.length){let tag=b.toString('ascii',pos,pos+4),len=b.readUInt32LE(pos+4);if(tag==='fmt ')rate=b.readUInt32LE(pos+16);if(tag==='data')return len/rate;pos+=8+len+(len%2);}throw Error('Bad WAV '+file);}
(async()=>{fs.mkdirSync(out,{recursive:true});const segs=JSON.parse(fs.readFileSync(path.join(work,'segments.json'),'utf8'));const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const context=await browser.newContext({viewport:{width:1600,height:900},recordVideo:{dir:out,size:{width:1600,height:900}}});const page=await context.newPage();const start=Date.now();const timeline=[];
const pause=ms=>page.waitForTimeout(ms);
async function say(i){const s=segs[i],file=path.join(work,s.id+'.wav'),duration=wavDuration(file);timeline.push({id:s.id,file,start_ms:Date.now()-start,duration});console.log('Recording '+s.id+' ('+duration.toFixed(1)+'s)');await pause(duration*1000+650);}
async function slide(n){const data=fs.readFileSync(path.join(root,'.data/deck-build/slide-'+n+'.png')).toString('base64');await page.setContent('<html style="background:#101b2c"><body style="margin:0"><img style="width:100vw;height:100vh;object-fit:contain" src="data:image/png;base64,'+data+'"></body></html>');await pause(500);}
try{
await slide(1);await say(0);await slide(2);await say(1);await slide(4);await say(2);
await page.goto('http://localhost:5173/?demo=1');await page.getByRole('button',{name:'My library 240',exact:true}).waitFor();await page.mouse.move(1530,870);
await Promise.all([say(3),(async()=>{await pause(4000);await page.getByRole('button',{name:'Connect sources',exact:true}).click();await pause(2000);await page.getByRole('button',{name:'Ingest selected platforms',exact:true}).click();})()]);
await page.locator('.graph-page svg[role=img]').waitFor();await say(4);
await page.getByRole('button',{name:'Ask your library',exact:true}).click();await page.getByRole('textbox',{name:'Ask your saved library'}).fill('What have I saved about software engineering career?');await say(5);
const responsePending=page.waitForResponse(r=>r.url().endsWith('/api/search')&&r.request().method()==='POST');
await page.getByRole('button',{name:'Search your saves'}).click();const data=await(await responsePending).json();if(new Set(data.resources.map(r=>r.platform)).size!==4)throw Error('Missing source in recording search');
await page.locator('.answer-section').waitFor();
await Promise.all([say(6),(async()=>{await pause(6000);await page.getByText('See how Orma found this').click();await pause(4500);await page.evaluate(()=>window.scrollTo({top:650,behavior:'smooth'}));})()]);
await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'}));await pause(600);await page.locator('.answer-copy .citation').first().click();await page.locator('.resource-drawer').waitFor();await say(7);await page.getByRole('button',{name:'Close resource details'}).click();
await page.getByRole('button',{name:'My library 240',exact:true}).click();await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
await Promise.all([say(8),(async()=>{await pause(5000);await page.getByRole('textbox',{name:'Filter your library'}).fill('Rust');await pause(3000);await page.getByRole('textbox',{name:'Filter your library'}).fill('');})()]);
await slide(6);await say(9);await pause(500);
fs.writeFileSync(path.join(out,'timeline.json'),JSON.stringify({start,duration_ms:Date.now()-start,segments:timeline},null,2));
const video=page.video();await context.close();const v=await video.path();fs.copyFileSync(v,path.join(out,'walkthrough.webm'));console.log('Recording ready '+v);
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});