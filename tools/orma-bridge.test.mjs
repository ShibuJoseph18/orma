import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('./linkosh-test/extension/ext/background.js',import.meta.url),'utf8');
function harness(){
 const calls=[];let listener;
 const context={URL,Set,Error,chrome:{runtime:{getManifest:()=>({version:'test'}),onMessageExternal:{addListener:f=>{listener=f;}}}},
 prefs:{get:async()=>false,set:async()=>{}},
 service:{syncStatus:async()=>({running:false}),syncStop:async()=>({}),sync:async options=>{calls.push(options);return{providerId:options.provider,status:'ok',inserted:1};},
 exportDb:async()=>({data:{items:[{provider:'linkedin',url:'https://linkedin.com/post/a'},{provider:'youtube',url:'https://youtube.com/watch?v=a'},{provider:'facebook',url:'https://facebook.com/a'}],rawPages:[{private:'must not leave bridge'}]}})}};
 vm.runInNewContext(source.slice(source.indexOf('// Orma local web-app bridge.')),context);
 return {calls,send:(message,origin='http://localhost:5173')=>new Promise(resolve=>listener(message,{origin,url:origin+'/'},resolve))};
}
test('bridge rejects other origins and ports',async()=>{
 const h=harness();
 for(const origin of ['https://evil.example','http://localhost:9000','http://localhost.evil.example:5173']){
  assert.match((await h.send({action:'ping'},origin)).error,/Only the local/);
 }
 assert.equal((await h.send({action:'ping'})).ok,true);
});
test('bridge enforces requested per-platform caps and exports only selected items',async()=>{
 const h=harness();
 await h.send({action:'start',platforms:['linkedin','instagram','youtube','x','facebook','x']});
 for(let i=0;i<20;i++){if(!(await h.send({action:'status'})).running)break;await new Promise(r=>setTimeout(r,1));}
 assert.deepEqual(h.calls.map(c=>[c.provider,c.maxItems]),[['linkedin',100],['instagram',50],['youtube',50],['twitter',50]]);
 const result=await h.send({action:'result'});
 assert.equal(result.items.length,2);
 assert.equal(result.rawPages,undefined);
 assert.equal(JSON.stringify(result).includes('must not leave bridge'),false);
});
