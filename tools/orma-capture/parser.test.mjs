import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseSavedPage,collectSaved,mediaReferences} from './parser.mjs';
const page = ids => ({data:{data:{searchDashClustersByAll:{elements:[{items:ids.map(id=>({item:{'*entityResult':id}}))}],metadata:{paginationToken:'next'}}}},included:[...ids].reverse().map(id=>({entityUrn:id,trackingUrn:id,title:{text:id},summary:{text:'post '+id},entityEmbeddedObject:{showPlayButton:id==='a'}}))});
test('follows ordered references despite reversed included entities',()=>{
  assert.deepEqual(parseSavedPage(page(['a','b','c'])).items.map(x=>x.id),['a','b','c']);
  assert.equal(parseSavedPage(page(['a'])).items[0].extraction.binaryMediaDownloaded,false);
});
test('deduplicates pages, continues and truncates to exact requested count',async()=>{
  const pages=[page(['a','b']),page(['b','c']),page(['d','e'])];
  const result=await collectSaved({limit:4,fetchPage:async(i,cursor)=>{if(i)assert.equal(cursor,'next');return pages[i];}});
  assert.deepEqual(result.items.map(x=>x.id),['a','b','c','d']);
  assert.deepEqual(result.items.map(x=>x.savedListPosition),[1,2,3,4]);
  assert.equal(result.stopReason,'requested_limit');
});
test('no inherited 100-post cap',async()=>{
  const result=await collectSaved({limit:123,fetchPage:async i=>page(Array.from({length:10},(_,n)=>String(i*10+n)))});
  assert.equal(result.items.length,123);assert.equal(result.items[122].id,'122');
});
test('empty and repeated pages terminate',async()=>{
  assert.equal((await collectSaved({limit:5,fetchPage:async()=>page([])})).stopReason,'end_of_results');
  assert.equal((await collectSaved({limit:5,fetchPage:async()=>page(['a'])})).stopReason,'repeated_page');
});
test('missing ordering or unresolved post fails rather than reorders',()=>{
  assert.throws(()=>parseSavedPage({included:[]}));
  const input=page(['a']);input.included=[];assert.throws(()=>parseSavedPage(input));
});
test('invalid limits and cancellation fail',async()=>{
  await assert.rejects(collectSaved({limit:1.5,fetchPage:async()=>page([])}));
  const controller=new AbortController();controller.abort();
  await assert.rejects(collectSaved({limit:2,signal:controller.signal,fetchPage:async()=>page(['a'])}));
});
test('extracts attachment images and caption/video references without treating arbitrary URLs as assets',()=>{
  const refs=mediaReferences({image:{rootUrl:'https://example.com/',artifacts:[{fileIdentifyingUrlPathSegment:'photo.jpg'}]},video:{playableUrl:'https://example.com/video.mp4'},captionsUrl:'https://example.com/sub.vtt',navigationUrl:'https://example.com/post'});
  assert.deepEqual(refs.map(x=>x.kind),['image','video','caption']);
});
