/** Fixed observer contract tests. These synthetic modules are not product E2E. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';
import {join} from 'node:path';

const source = readFileSync(join(process.cwd(), 'e2e/main-observer.cjs'), 'utf8');

type Row = {run_id:string;case_id:string;launch_id:string;pid:number;sequence:number;
  kind:string;origin?:string;path?:string;method?:string;transport?:string};

function makeProbe(throwMethod?: 'checkForUpdates' | 'https.get') {
  const writes:string[]=[];
  const calls:Array<{method:string;receiver:unknown;args:unknown[]}>=[];
  const marker={from:'original-method'};
  const thrown=new Error('original failure');
  let undiciListener:((value:unknown)=>void)|undefined;
  let contentsListener:((_event:unknown,contents:unknown)=>void)|undefined;
  let chromiumListener:((details:{method:string;url:string},callback:(response:unknown)=>void)=>void)|undefined;
  let chromiumRegistrations=0;
  const native={
    setFeedURL(...args:unknown[]){calls.push({method:'setFeedURL',receiver:this,args});return marker;},
    checkForUpdates(...args:unknown[]){calls.push({method:'checkForUpdates',receiver:this,args});
      if(throwMethod==='checkForUpdates')throw thrown;return marker;},
    quitAndInstall(...args:unknown[]){calls.push({method:'quitAndInstall',receiver:this,args});return marker;},
  };
  const originalNative={...native};
  const http={
    request(...args:unknown[]){calls.push({method:'http.request',receiver:this,args});return marker;},
    get(...args:unknown[]){calls.push({method:'http.get',receiver:this,args});return marker;},
  };
  const https={
    request(...args:unknown[]){calls.push({method:'https.request',receiver:this,args});return marker;},
    get(...args:unknown[]){calls.push({method:'https.get',receiver:this,args});
      if(throwMethod==='https.get')throw thrown;return marker;},
  };
  const electron={autoUpdater:native,app:{on(event:string,listener:typeof contentsListener){
    assert.equal(event,'web-contents-created');contentsListener=listener;
  }}};
  const modules:Record<string,unknown>={
    'node:fs':{appendFileSync(path:string,value:string,options:{mode:number}){
      assert.equal(path,'/owned/main-observer.jsonl');assert.equal(options.mode,0o600);writes.push(value);}},
    'node:diagnostics_channel':{channel(name:string){assert.equal(name,'undici:request:create');
      return {subscribe(listener:(value:unknown)=>void){undiciListener=listener;}};}},
    'electron':electron,'node:http':http,'node:https':https,
  };
  const module={exports:undefined as unknown};
  runInNewContext(source,{module,require(name:string){
    if(!(name in modules))throw new Error(`Unexpected module ${name}`);return modules[name];
  },process:{pid:4242},URL},{filename:'e2e/main-observer.cjs'});
  const install=module.exports as (options:Record<string,unknown>)=>unknown;
  const installed=install({path:'/owned/main-observer.jsonl',run_id:'owned-run',case_id:'TC-TM001-UPDATE-04',
    launch_id:'owned-launch',source_sha256:'a'.repeat(64),paused_function:'entry',paused_url:'file:///owned/main.cjs'}) as
    {installed:boolean;pid:number};
  assert.equal(installed.installed,true);assert.equal(installed.pid,4242);
  const rows=()=>writes.map(line=>JSON.parse(line) as Row);
  const session={webRequest:{onBeforeRequest(filter:{urls:string[]},listener:typeof chromiumListener){
    assert.deepEqual(Array.from(filter.urls),['http://*/*','https://*/*']);
    chromiumRegistrations++;chromiumListener=listener;
  }}};
  return {writes,rows,calls,marker,thrown,native,originalNative,http,https,
    get undiciListener(){return undiciListener;},
    get contentsListener(){return contentsListener;},
    get chromiumListener(){return chromiumListener;},
    get chromiumRegistrations(){return chromiumRegistrations;},session};
}

test('native observer delegates the original receiver, arguments and return value',()=>{
  const probe=makeProbe();
  assert.equal(probe.rows()[0]?.kind,'installed-before-entry');
  for(const method of ['setFeedURL','checkForUpdates','quitAndInstall'] as const){
    const argument={url:'http://127.0.0.1/owned?secret=never-record'};
    assert.notEqual(probe.native[method],probe.originalNative[method]);
    assert.equal(probe.native[method](argument),probe.marker);
    const call=probe.calls.at(-1)!;
    assert.equal(call.method,method);assert.equal(call.receiver,probe.native);
    assert.equal(call.args[0],argument);
  }
  assert.deepEqual(probe.rows().slice(1).map(row=>row.method),
    ['setFeedURL','checkForUpdates','quitAndInstall']);
  assert.equal(probe.rows().every((row,index)=>row.sequence===index+1&&row.pid===4242&&
    row.run_id==='owned-run'&&row.case_id==='TC-TM001-UPDATE-04'&&row.launch_id==='owned-launch'),true);
  assert.doesNotMatch(probe.writes.join(''),/never-record/);
});

test('native observer propagates the original thrown error',()=>{
  const probe=makeProbe('checkForUpdates');
  assert.throws(()=>probe.native.checkForUpdates('same-input'),error=>error===probe.thrown);
  assert.equal(probe.calls.at(-1)?.args[0],'same-input');
  assert.equal(probe.rows().at(-1)?.method,'checkForUpdates');
});

test('undici and Node request observers keep the request behavior and redact secrets',()=>{
  const probe=makeProbe('https.get');
  probe.undiciListener?.({request:{method:'POST',origin:'https://api.example',
    path:'/v1/me?token=never-record',body:'prompt=never-record'}});
  const headers={Authorization:'Bearer never-record'};
  assert.equal(probe.http.request('http://127.0.0.1:1234/version.json?token=never-record',
    {method:'POST',headers}),probe.marker);
  assert.equal(probe.calls.at(-1)?.receiver,probe.http);
  assert.deepEqual(probe.calls.at(-1)?.args,
    ['http://127.0.0.1:1234/version.json?token=never-record',{method:'POST',headers}]);
  assert.throws(()=>probe.https.get('https://api.example/v1/me?token=never-record'),error=>error===probe.thrown);
  const requests=probe.rows().filter(row=>row.kind==='request');
  assert.deepEqual(requests.map(row=>row.transport),['undici','node-http','node-https']);
  assert.deepEqual(requests.map(row=>row.path),['/v1/me','/version.json','/v1/me']);
  assert.doesNotMatch(probe.writes.join(''),/never-record|Authorization|prompt/);
});

test('Chromium observer allows the request and registers once per session',()=>{
  const probe=makeProbe();
  probe.contentsListener?.({}, {session:probe.session});
  probe.contentsListener?.({}, {session:probe.session});
  assert.equal(probe.chromiumRegistrations,1);
  let decision:unknown;
  probe.chromiumListener?.({method:'GET',url:'https://api.example/owned?secret=never-record'},
    response=>{decision=response;});
  assert.equal(JSON.stringify(decision),JSON.stringify({cancel:false}));
  const row=probe.rows().at(-1)!;
  assert.equal(row.kind,'request');assert.equal(row.transport,'chromium');
  assert.equal(row.origin,'https://api.example');assert.equal(row.path,'/owned');
  assert.doesNotMatch(probe.writes.join(''),/never-record/);
});
