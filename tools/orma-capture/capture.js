import {collectSaved, mediaReferences} from './parser.mjs';
const $ = id => document.getElementById(id);
let controller, output;
function status(text) { $('status').textContent = text; }
function render() {
  $('results').replaceChildren();
  for (const item of output.items) {
    const article = document.createElement('article');
    const link = document.createElement('a');
    link.textContent = `${item.savedListPosition}. ${item.author.name}`;
    try { const url = new URL(item.sourceUrl); if (url.protocol === 'https:') link.href = url.href; } catch {}
    link.target = '_blank'; link.rel = 'noopener noreferrer'; article.append(link);
    const text = document.createElement('p'); text.textContent = item.text; article.append(text);
    const details = document.createElement('details'), summary = document.createElement('summary'), pre = document.createElement('pre');
    summary.textContent = 'Captured fields and media availability'; pre.textContent = JSON.stringify(item,null,2);
    details.append(summary,pre); article.append(details); $('results').append(article);
  }
}
function delay(ms, signal) { return new Promise((resolve,reject) => {
  signal.throwIfAborted();
  const abort = () => {clearTimeout(timer); reject(signal.reason);};
  const timer = setTimeout(() => {signal.removeEventListener('abort',abort); resolve();},ms);
  signal.addEventListener('abort',abort,{once:true});
}); }
async function inspectPost(item, signal) {
  const url = new URL(item.sourceUrl);
  if (url.origin !== 'https://www.linkedin.com') throw Error('Skipped non-LinkedIn post URL');
  const response = await fetch(url.href,{credentials:'include',signal});
  if (!response.ok) throw Error(`Post page HTTP ${response.status}`);
  if (!response.url.startsWith('https://www.linkedin.com/') || /\/(authwall|login|checkpoint)(?:[/?]|$)/.test(new URL(response.url).pathname)) throw Error('Post page requires login or verification');
  const doc = new DOMParser().parseFromString(await response.text(),'text/html');
  const meta = key => doc.querySelector(`meta[property="${key}"],meta[name="${key}"]`)?.content || null;
  const structured = [];
  for (const script of doc.querySelectorAll('script[type="application/ld+json"]')) {
    try {structured.push(JSON.parse(script.textContent));} catch {}
  }
  const media = mediaReferences(structured);
  for (const [key,kind] of [['og:image','image'],['og:video','video'],['og:video:url','video'],['og:video:secure_url','video']]) {
    const value = meta(key); if (value && /^https?:\/\//i.test(value)) media.push({kind,url:value,evidence:'post-page '+key});
  }
  item.postPage = {status:'fetched',title:meta('og:title'),description:meta('og:description'),media,structuredData:structured,
    limitations:['Open Graph images may be previews. Video URLs can be players or expire. No OCR, transcription, or binary download performed.']};
}
$('start').onclick = async () => {
  const limit = Number($('limit').value);
  if (!Number.isSafeInteger(limit) || limit < 1) {status('Enter a positive whole number.');return;}
  controller = new AbortController(); const signal = controller.signal;
  $('start').disabled = true; $('stop').disabled = false; $('export').disabled = true;
  output = {schemaVersion:1,provider:'linkedin',capturedAt:new Date().toISOString(),requestedCount:limit,
    ordering:'LinkedIn saved-list reference order, starting at offset zero; exact save times unavailable; not an atomic snapshot',items:[],stopReason:'running'};
  render();
  try {
    const cookie = await chrome.cookies.get({url:'https://www.linkedin.com',name:'JSESSIONID'});
    if (!cookie) throw Error('Sign into LinkedIn in this Chrome profile first.');
    const csrf = cookie.value.replace(/^"|"$/g,'');
    const result = await collectSaved({limit,signal,onProgress:items=>{
      output.items = items; status(`Captured ${items.length}/${limit} saved posts in source order…`);
    },fetchPage:async(page,cursor)=>{
      if (page) await delay(600,signal);
      const token = cursor ? `,paginationToken:${encodeURIComponent(cursor)}` : '';
      const variables = `(start:${page*10}${token},query:(flagshipSearchIntent:SEARCH_MY_ITEMS_SAVED_POSTS))`;
      const url = `https://www.linkedin.com/voyager/api/graphql?variables=${variables}&queryId=voyagerSearchDashClusters.a7a0567fa66c52d645b5ff2f960b92aa`;
      const res = await fetch(url,{credentials:'include',signal,headers:{accept:'application/vnd.linkedin.normalized+json+2.1','csrf-token':csrf,'x-restli-protocol-version':'2.0.0'}});
      if (!res.ok) throw Error(`LinkedIn HTTP ${res.status}. Sign-in, throttling, or an API change may require attention. No automatic retries.`);
      return res.json();
    }});
    Object.assign(output,result);
    if ($('enrich').checked) {
      for (const item of output.items) {
        await delay(600,signal); status(`Inspecting post page ${item.savedListPosition}/${output.items.length}…`);
        try {await inspectPost(item,signal);} catch(e) {if(signal.aborted) throw e; item.postPage={status:'unavailable',error:e.message};}
      }
    }
    status(`Captured ${output.items.length}/${limit}. Stop reason: ${output.stopReason}. Expand each item to inspect media availability.`);
  } catch(e) {
    output.stopReason = signal.aborted ? 'cancelled' : 'error'; output.error = e.message;
    status(`${output.stopReason}: ${e.message}. ${output.items.length} captured posts available for export.`);
  } finally {
    render(); $('start').disabled = false; $('stop').disabled = true; $('export').disabled = !output.items.length;
  }
};
$('stop').onclick = () => controller?.abort(new DOMException('Stopped by user','AbortError'));
$('export').onclick = () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(output,null,2)],{type:'application/json'}));
  const link = document.createElement('a'); link.href=url; link.download=`orma-linkedin-${Date.now()}.json`; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
};
