/** Independent TM-001 configuration cases against one installed, isolated App. */
import { test, expect, chromium, type Browser, type ElectronApplication, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { launchObserved, observations } from './main-observer';

type Context = {run_id:string;case_id:string;app_path:string;profile_path:string;service_url:string;
  secondary_service_url:string|null;service_log_path:string;secondary_service_log_path?:string;
  service_control_url:string;service_control_token:string;secondary_control_url:string;secondary_control_token:string;
  update_url?:string|null;update_control_url?:string|null;update_control_token?:string|null;update_nonce?:string|null;
  cdp_port?:number|null;expected_upgrade_build?:string};
const input=process.env.TM_E2E_CONTEXT, output=process.env.TM_E2E_CASE_OUTPUT;
if(!input||!output) throw Error('Owned granular config context is missing');
const c=JSON.parse(readFileSync(input,'utf8')) as Context;
const executable=join(c.app_path,'Contents/MacOS/TokenMeter');
const events=join(output,'events.jsonl');
let app:ElectronApplication|null=null, page:Page|null=null, tracing=false, traceNumber=0;
let reconnected:Browser|null=null, runnerLaunches=0;
function evidence(step:number,action:string,expected:unknown,actual:unknown,source:'ui'|'service'|'filesystem'|'process'='ui') {
  const passed=JSON.stringify(expected)===JSON.stringify(actual);
  appendFileSync(events,JSON.stringify({run_id:c.run_id,case_id:c.case_id,step,action,expected,actual,passed,source,
    timestamp:new Date().toISOString()})+'\n',{mode:0o600});
  expect(actual,`${c.case_id} step ${step}: ${action}`).toEqual(expected);
}
function childEnv():Record<string,string> {
  return Object.fromEntries(Object.entries(process.env).filter((entry):entry is [string,string]=>entry[1]!==undefined).filter(([key])=>!key.startsWith('TM_E2E_')&&!key.startsWith('TM_INTERNAL_')&&!key.includes('SIGNING')&&!key.includes('TOKEN')));
}
async function launch(diagnostic=false) {
  const args=[`--user-data-dir=${c.profile_path}`];
  if(diagnostic){if(!c.cdp_port)throw Error('Owned diagnostic CDP port is absent');args.push(`--diagnostic-cdp-port=${c.cdp_port}`);}
  app=await launchObserved({executablePath:executable,args,env:childEnv(),chromiumSandbox:true,timeout:60_000},
    {run_id:c.run_id,case_id:c.case_id,output:output!});
  runnerLaunches++;
  page=await app.firstWindow(); await expect(page.getByTestId('app.build')).toBeVisible();
  await app.context().tracing.start({screenshots:true,snapshots:true,sources:false});tracing=true;
}
async function close() {
  if(app){if(tracing){await app.context().tracing.stop({path:join(output!,`trace-${String(++traceNumber).padStart(2,'0')}.zip`)});tracing=false;}
    await app.close();app=null;page=null;}
}
async function restart(){await close();await launch();}
async function open(){await page!.getByTestId('configuration.open').click();await expect(page!.getByTestId('configuration.api-url')).toBeVisible();}
async function settings(){await open();return {api:await page!.getByTestId('configuration.api-url').inputValue(),
  feed:await page!.getByTestId('configuration.update-url').inputValue()};}
async function save(api:string,feed?:string){await open();await page!.getByTestId('configuration.api-url').fill(api);
  if(feed!==undefined)await page!.getByTestId('configuration.update-url').fill(feed);
  await page!.getByTestId('configuration.save').click();
  await expect.poll(async()=>!(await page!.getByTestId('configuration.api-url').isVisible()) ||
    await page!.getByTestId('configuration.error').isVisible()).toBe(true);}
async function login(name='test-alice',password='TEST-ONLY-alice-42!'){
  await page!.getByTestId('auth.username').fill(name);await page!.getByTestId('auth.password').fill(password);
  await page!.getByTestId('auth.login').click();
}
async function changePassword(current='TEST-ONLY-alice-42!',next='TEST-ONLY-Changed-42!'){
  const origin=saved().server;
  const previous=existsSync(tokenPath(origin))?token(origin):null;
  await page!.getByTestId('password.current').fill(current);await page!.getByTestId('password.new').fill(next);
  await page!.getByTestId('password.confirm').fill(next);await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('password.status')).toHaveText('密码已更新；旧会话已撤销');
  await expect(page!.getByTestId('password.current')).toBeHidden();
  await expect.poll(()=>existsSync(tokenPath(origin))?token(origin):null,{timeout:15_000})
    .not.toBe(previous);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
}
function tokenPath(origin:string){return join(c.profile_path,'credentials',createHash('sha256').update(origin).digest('hex')+'.token');}
function token(origin:string){return readFileSync(tokenPath(origin),'utf8');}
async function api(origin:string,access:string){const response=await fetch(origin+'/v1/me',{headers:{Authorization:'Bearer '+access,'X-TM-Test-Probe':'1'}});return response.status;}
async function observed(secondary=false){const response=await fetch((secondary?c.secondary_control_url:c.service_control_url)+'/observations',
  {headers:{Authorization:'Bearer '+(secondary?c.secondary_control_token:c.service_control_token)}});
  return (await response.json() as {requests:{probe:boolean;authorization_sha256:string|null;
    method:string;route:string;mode:string;forwarded:boolean;status:number;received_at:string;finished_at:string}[]}).requests;}
function requests(log:string){return existsSync(log)?readFileSync(log,'utf8').split('\n').filter(line=>/"(?:GET|POST|PUT|PATCH|DELETE) \/v1\//.test(line)):[];}
function saved(){return JSON.parse(readFileSync(join(c.profile_path,'settings.json'),'utf8')) as {server:string;feed:string;automaticLogin:boolean};}
function settingsDigest(){return createHash('sha256').update(readFileSync(join(c.profile_path,'settings.json'))).digest('hex');}
async function readConfiguration(){const value=await settings();await page!.getByTestId('configuration.cancel').click();return value;}
function mainRows(){const rows=observations(output!);
  if(rows.some(row=>row.run_id!==c.run_id||row.case_id!==c.case_id))throw Error('Main observer identity differs from owned TC');
  return rows;}
function mainRequests(){return mainRows().filter(row=>row.kind==='request');}
function defaultRequests(){return mainRequests().filter(row=>
  row.origin===builtin.api||row.origin==='http://127.0.0.1:49177');}
function ownedPids(){return execFileSync('/bin/ps',['-axo','pid=,command='],{encoding:'utf8'}).split('\n')
  .map(line=>line.trim().match(/^(\d+)\s+(.*)$/))
  .filter((match):match is RegExpMatchArray=>Boolean(match&&match[2]!.startsWith(executable)))
  .map(match=>Number(match[1]));}
async function waitForAutonomousPid(oldPid:number,launchesAtHandoff:number){
  const deadline=Date.now()+180_000;
  while(Date.now()<deadline){
    const pids=ownedPids();
    if(!pids.includes(oldPid)&&pids.length===1&&pids[0]!==oldPid&&runnerLaunches===launchesAtHandoff)return pids[0]!;
    await new Promise(resolve=>setTimeout(resolve,500));
  }
  throw Error('Native updater did not autonomously replace the owned App process');
}
async function reconnectAutonomous(){
  if(!c.cdp_port)throw Error('Owned diagnostic CDP port is absent');
  const endpoint=`http://127.0.0.1:${c.cdp_port}`;const deadline=Date.now()+30_000;
  while(Date.now()<deadline){try{reconnected=await chromium.connectOverCDP(endpoint,{timeout:2000});break;}
    catch{await new Promise(resolve=>setTimeout(resolve,300));}}
  if(!reconnected)throw Error('Autonomously restarted App has no owned CDP endpoint');
  const next=reconnected.contexts()[0]?.pages().find(item=>item.url().startsWith('tokenmeter://app/'));
  if(!next)throw Error('Autonomously restarted App has no real TokenMeter renderer');
  page=next;
}
type PhaseObservation={kind:'snapshot'|'dom';segment:'upgrade';sequence:number;time:string;
  phase:string;canConfigure:boolean;feedDisabled:boolean|null;resetDisabled:boolean|null;
  cancelVisible:boolean;status:string};
async function attachConfigPhaseObserver():Promise<PhaseObservation[]>{
  const rows:PhaseObservation[]=[];
  const path=join(output!,'config-phase-observations.jsonl');
  await page!.exposeBinding('tmRecordConfigPhase',(_source:unknown,raw:PhaseObservation)=>{
    if(raw.segment!=='upgrade'||!['snapshot','dom'].includes(raw.kind)||!Number.isSafeInteger(raw.sequence))
      throw Error('Malformed renderer phase observation');
    rows.push(raw);
    appendFileSync(path,JSON.stringify({run_id:c.run_id,case_id:c.case_id,...raw,received_at:new Date().toISOString()})+'\n',{mode:0o600});
  });
  await page!.evaluate(async()=>{
    type UpdateState={updates:{phase:string;canConfigure:boolean}};
    const bridge=(window as unknown as {tokenmeter:{onState:(cb:(state:UpdateState)=>void)=>()=>void;
      snapshot:()=>Promise<UpdateState>}}).tokenmeter;
    const report=(window as unknown as {tmRecordConfigPhase:(row:PhaseObservation)=>Promise<void>}).tmRecordConfigPhase;
    let phase='unknown',canConfigure=false,sequence=0,lastDom='';
    const capture=(kind:'snapshot'|'dom')=>{
      const feed=document.querySelector<HTMLInputElement>('[data-testid="configuration.update-url"]');
      const reset=document.querySelector<HTMLButtonElement>('[data-testid="configuration.reset-defaults"]');
      const row:PhaseObservation={kind,segment:'upgrade',sequence:++sequence,time:new Date().toISOString(),
        phase,canConfigure,feedDisabled:feed?.disabled??null,resetDisabled:reset?.disabled??null,
        cancelVisible:!!document.querySelector('[data-testid="updates.cancel"]'),
        status:document.querySelector('[data-testid="updates.status"]')?.textContent??''};
      if(kind==='dom'){
        const now=JSON.stringify([row.phase,row.feedDisabled,row.resetDisabled,row.cancelVisible,row.status]);
        if(now===lastDom)return;
        lastDom=now;
      }
      void report(row);
    };
    bridge.onState(state=>{phase=state.updates.phase;canConfigure=state.updates.canConfigure;capture('snapshot');});
    const dom=new MutationObserver(()=>capture('dom'));
    dom.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,
      attributeFilter:['disabled']});
    const initial=await bridge.snapshot();phase=initial.updates.phase;
    canConfigure=initial.updates.canConfigure;capture('snapshot');
    capture('dom');
  });
  return rows;
}
const builtin={api:'http://127.0.0.1:49176',feed:'http://127.0.0.1:49177/version.json'};
test.afterEach(async()=>{try{if(page&&!page.isClosed())await page.screenshot({path:join(output!,'final.png')});}catch{}
  try{await close();}catch{}
  try{await reconnected?.close();}catch{}reconnected=null;});

test('TC-TM001-CONFIG-01',async()=>{
  await launch();const first={api:await page!.getByTestId('auth.server').inputValue(),feed:(await settings()).feed};
  const resource=JSON.parse(readFileSync(join(c.app_path,'Contents/Resources/release-config.json'),'utf8')) as {api_url:string;update_feed_url:string};
  evidence(1,'首启UI两项默认地址与本版签名资源相同',{ui:builtin,signed:builtin},
    {ui:first,signed:{api:resource.api_url,feed:resource.update_feed_url}},'filesystem');
  await page!.getByTestId('configuration.cancel').click();
  await page!.waitForTimeout(1000);
  const unauthenticated=await page!.getByTestId('auth.login').isVisible();
  const ownRequests=requests(c.service_log_path).filter(line=>/ \/v1\/(auth|admin)\//.test(line)).length;
  const armed=mainRows().filter(row=>row.kind==='installed-before-entry');
  evidence(2,'启动前观察器确认未登录且默认服务零请求',
    {unauthenticated:true,ownedAuthenticationRequests:0,observerArmed:true,defaultRequests:0},
    {unauthenticated,ownedAuthenticationRequests:ownRequests,
      observerArmed:armed.length===1&&armed[0]?.pid===app?.process().pid,
      defaultRequests:defaultRequests().length},'service');
  await save(c.service_url);await expect(page!.getByTestId('auth.server')).toHaveValue(c.service_url);
  await login();await expect(page!.getByTestId('password.submit')).toBeVisible();
  const ownLogin=requests(c.service_log_path).some(line=>line.includes('POST /v1/auth/login'));
  const observedLogin=mainRequests().some(row=>row.origin===c.service_url&&row.path==='/v1/auth/login'&&row.method==='POST');
  evidence(3,'配置页切到owned服务且真实App登录为观察器正控制',
    {origin:c.service_url,ownedLogin:true,observedLogin:true},
    {origin:saved().server,ownedLogin:ownLogin,observedLogin},'service');
  await restart();const after=await settings();
  evidence(4,'重启后覆盖仍在且新进程也从入口前被观察',
    {api:c.service_url,observerLaunches:2,defaultRequests:0},
    {api:after.api,observerLaunches:mainRows().filter(row=>row.kind==='installed-before-entry').length,
      defaultRequests:defaultRequests().length},'filesystem');
  await page!.getByTestId('configuration.cancel').click();
});

test('TC-TM001-CONFIG-02',async()=>{
  await launch();
  const valid=['http://127.0.0.1:49176','http://localhost:49176','http://[::1]:49176','https://example.invalid'];
  const accepted:{input:string;canonical:string;ui:string;fileOverride:string|null;requestDelta:number}[]=[];
  for(const url of valid){
    const before=mainRequests().length;
    await save(url);await expect(page!.getByTestId('configuration.api-url')).toBeHidden();
    const ui=(await readConfiguration()).api;
    accepted.push({input:url,canonical:url,ui,fileOverride:saved().server??null,
      requestDelta:mainRequests().length-before});
  }
  evidence(1,'逐项保存合法API地址并从UI与本机设置回读',valid.map(url=>({input:url,canonical:url,ui:url,
    fileOverride:url===builtin.api?null:url,requestDelta:0})),accepted,'filesystem');
  const original=saved().server;const invalid=['http://example.invalid','http://127.1:49176','http://2130706433:49176',
    'http://','http://127.0.0.1:65536','http://user:pass@127.0.0.1:49176',
    'http://127.0.0.1:49176/path','http://127.0.0.1:49176?x=1','http://127.0.0.1:49176/#f'];
  const priorDigest=settingsDigest();const priorAuth=requests(c.service_log_path).filter(line=>/ \/v1\/(auth|admin)\//.test(line)).length;
  const priorMain=mainRequests().length;
  const rejected:{input:string;error:string;fileSha:string;server:string;ownedAuthCount:number;mainRequestCount:number}[]=[];
  for(const url of invalid){
    await save(url);await expect(page!.getByTestId('configuration.error')).toBeVisible();
    rejected.push({input:url,error:(await page!.getByTestId('configuration.error').textContent())?.trim()??'',
      fileSha:settingsDigest(),server:saved().server,
      ownedAuthCount:requests(c.service_log_path).filter(line=>/ \/v1\/(auth|admin)\//.test(line)).length,
      mainRequestCount:mainRequests().length});
    await page!.getByTestId('configuration.cancel').click();
  }
  evidence(2,'非法API origin逐项可见拒绝，配置原子保留且owned服务无认证',invalid.map(url=>({
    input:url,error:'请输入 HTTPS 服务地址或本机回环 HTTP 地址（invalid_server_url）',fileSha:priorDigest,
    server:original,ownedAuthCount:priorAuth,mainRequestCount:priorMain})),rejected,'filesystem');
  await save('https://EXAMPLE.invalid:443/');const normalizedA=saved().server;
  const uiA=(await readConfiguration()).api;
  await save('https://example.invalid');const normalizedB=saved().server;
  const uiB=(await readConfiguration()).api;
  evidence(3,'等价HTTPS地址规范化为同一origin与凭据位置',
    {first:'https://example.invalid',second:'https://example.invalid',uiA:'https://example.invalid',uiB:'https://example.invalid',sameCredentialPath:true},
    {first:normalizedA,second:normalizedB,uiA,uiB,sameCredentialPath:tokenPath(normalizedA)===tokenPath(normalizedB)},'filesystem');
  await save(c.service_url);const own=saved().server;const ownUi=(await readConfiguration()).api;
  evidence(4,'不同origin使用不同凭据位置且UI无地址错误',
    {origin:c.service_url,ui:c.service_url,differentCredentialPath:true,newCredentialPresent:false},
    {origin:own,ui:ownUi,differentCredentialPath:tokenPath(own)!==tokenPath(normalizedB),newCredentialPresent:existsSync(tokenPath(own))},'filesystem');
});

test('TC-TM001-CONFIG-03',async()=>{
  if(!c.secondary_service_url)throw Error('Owned secondary service is required');
  const second=c.secondary_service_url;
  await launch();await save(c.service_url);await login();await changePassword();const first=token(c.service_url);
  evidence(1,'A真实改密和跨服务身份校验',{a:200,b:401},
    {a:await api(c.service_url,first),b:await api(second,first)},'service');
  await restart();await expect(page!.getByTestId('session.verified')).toBeVisible();
  await page!.getByTestId('session.logout').click();await expect(page!.getByTestId('auth.login')).toBeVisible();
  evidence(2,'A重启恢复、在线退出清除A凭据',{origin:c.service_url,credentialPresent:false},
    {origin:await page!.getByTestId('auth.server').inputValue(),credentialPresent:existsSync(tokenPath(c.service_url))});
  await save(second);await login('test-alice','TEST-ONLY-alice-43!');
  await changePassword('TEST-ONLY-alice-43!','TEST-ONLY-Changed-43!');const other=token(second);
  evidence(3,'B新会话仅在B有效',{a:401,b:200},
    {a:await api(c.service_url,other),b:await api(second,other)},'service');
  const bBefore=(await observed(true)).length;
  await restart();await expect(page!.getByTestId('session.verified')).toBeVisible();
  const firstHash=createHash('sha256').update('Bearer '+first).digest('hex');
  const secondHash=createHash('sha256').update('Bearer '+other).digest('hex');
  const bNew=(await observed(true)).slice(bBefore).filter(row=>!row.probe&&row.method==='GET'&&row.route==='/v1/me');
  evidence(4,'B重启后新请求由B真实服务确认，A凭据未串用',
    {differentCredentialPath:true,username:'test-alice',origin:second,newBMe200:true,oldAUsed:false},
    {differentCredentialPath:tokenPath(c.service_url)!==tokenPath(second),
      username:(await page!.getByTestId('session.username').textContent())?.trim(),origin:saved().server,
      newBMe200:bNew.some(row=>row.mode==='normal'&&row.forwarded&&row.status===200&&row.authorization_sha256===secondHash),
      oldAUsed:bNew.some(row=>row.authorization_sha256===firstHash)},'service');
  await page!.getByTestId('session.logout').click();await expect(page!.getByTestId('auth.login')).toBeVisible();
  evidence(5,'B退出清本机B凭据且保留B地址',{credentialPresent:false,origin:second},
    {credentialPresent:existsSync(tokenPath(second)),origin:saved().server});
});

test('TC-TM001-CONFIG-04',async()=>{
  const configFile=join(c.app_path,'Contents/Resources/release-config.json');
  const originalConfigHash=createHash('sha256').update(readFileSync(configFile)).digest('hex');
  await launch();const loopback=`http://127.0.0.1:${new URL(c.service_url).port}/version.json`;
  const valid=[loopback,'https://updates.example.invalid/version.json'];
  const accepted:{input:string;ui:string;file:string;afterRestartUi:string;afterRestartFile:string;requestDelta:number}[]=[];
  for(const feed of valid){
    const before=mainRequests().length;
    await save(c.service_url,feed);await expect(page!.getByTestId('configuration.api-url')).toBeHidden();
    const ui=(await readConfiguration()).feed;const file=saved().feed;
    await restart();const afterRestartUi=(await readConfiguration()).feed;
    accepted.push({input:feed,ui,file,afterRestartUi,afterRestartFile:saved().feed,
      requestDelta:mainRequests().length-before});
  }
  evidence(1,'合法回环及HTTPS更新源逐项保存并重启回读UI和设置文件',valid.map(feed=>({
    input:feed,ui:feed,file:feed,afterRestartUi:feed,afterRestartFile:feed,requestDelta:0})),accepted,'filesystem');
  const keep=saved().feed;
  const invalid=['http://example.invalid/version.json','http://','http://user:pass@127.0.0.1/version.json',
    'http://127.0.0.1/version.json?','http://127.0.0.1/version.json#',
    'http://127.0.0.1:65536/version.json','http://127.1/version.json','http://2130706433/version.json'];
  const priorDigest=settingsDigest();const priorAuth=requests(c.service_log_path).filter(line=>/ \/v1\/(auth|admin)\//.test(line)).length;
  const priorMain=mainRequests().length;
  const rejected:{input:string;error:string;fileSha:string;feed:string;ownedAuthCount:number;mainRequestCount:number}[]=[];
  for(const feed of invalid){
    await save(c.service_url,feed);await expect(page!.getByTestId('configuration.error')).toBeVisible();
    rejected.push({input:feed,error:(await page!.getByTestId('configuration.error').textContent())?.trim()??'',
      fileSha:settingsDigest(),feed:saved().feed,
      ownedAuthCount:requests(c.service_log_path).filter(line=>/ \/v1\/(auth|admin)\//.test(line)).length,
      mainRequestCount:mainRequests().length});
    await page!.getByTestId('configuration.cancel').click();
  }
  evidence(2,'非法更新源逐项可见拒绝，文件不落盘且owned服务无认证',invalid.map(feed=>({
    input:feed,error:'更新地址无效，仅支持 HTTPS 或本机回环 HTTP（update_source_rejected）',fileSha:priorDigest,
    feed:keep,ownedAuthCount:priorAuth,mainRequestCount:priorMain})),rejected,'filesystem');
  const resource=JSON.parse(readFileSync(join(c.app_path,'Contents/Resources/release-config.json'),'utf8')) as {update_public_key:string};
  await open();const fields=await page!.getByRole('dialog').locator('input').evaluateAll(elements=>elements.map(element=>element.getAttribute('data-testid')).sort());
  const noKeyInput=JSON.stringify(fields)===JSON.stringify(['configuration.api-url','configuration.update-url']);
  await page!.getByTestId('configuration.cancel').click();
  evidence(3,'覆盖feed不改变受签名资源公钥',{publicKeyPinned:true,noKeyEditor:true},
    {publicKeyPinned:resource.update_public_key.length>20&&originalConfigHash===createHash('sha256').update(readFileSync(configFile)).digest('hex'),noKeyEditor:noKeyInput},'filesystem');
  await restart();const retained=await settings();
  evidence(4,'重启后合法覆盖保留',keep,retained.feed);await page!.getByTestId('configuration.cancel').click();
});

test('TC-TM001-CONFIG-05',async()=>{
  if(!c.secondary_service_url)throw Error('Owned secondary service is required');
  const firstFeed=`http://127.0.0.1:${new URL(c.service_url).port}/a.json`;
  const secondFeed=`http://127.0.0.1:${new URL(c.secondary_service_url).port}/b.json`;
  await launch();await save(c.service_url,firstFeed);const before=saved();
  await save(c.secondary_service_url,'http://example.invalid/version.json');
  await expect(page!.getByTestId('configuration.error')).toBeVisible();
  evidence(1,'成对校验不产生部分提交',{server:before.server,feed:before.feed},
    {server:saved().server,feed:saved().feed},'filesystem');
  await page!.getByTestId('configuration.cancel').click();await open();
  await page!.getByTestId('configuration.api-url').fill(c.secondary_service_url);
  await page!.getByTestId('configuration.update-url').fill(secondFeed);
  await page!.getByTestId('configuration.cancel').click();await restart();
  evidence(2,'取消修改后原值保留',{server:before.server,feed:before.feed},
    {server:saved().server,feed:saved().feed},'filesystem');
  await save(c.secondary_service_url,secondFeed);await restart();
  const persisted=saved();
  evidence(3,'API和feed同时持久化且不含凭据',true,
    persisted.server===c.secondary_service_url&&persisted.feed===secondFeed&&
    !/TEST-ONLY-|access_token|password/i.test(readFileSync(join(c.profile_path,'settings.json'),'utf8')),'filesystem');
  await open();await page!.getByTestId('configuration.reset-defaults').click();
  await page!.getByTestId('configuration.cancel').click();await restart();const restored=await settings();
  const armed=mainRows().filter(row=>row.kind==='installed-before-entry');
  evidence(4,'恢复默认后两项地址来自内置值且所有启动窗口零默认请求',
    {ui:builtin,observerLaunches:4,defaultRequests:0},
    {ui:restored,observerLaunches:new Set(armed.map(row=>row.launch_id)).size,
      defaultRequests:defaultRequests().length},'service');
  await page!.getByTestId('configuration.cancel').click();
  const resource=JSON.parse(readFileSync(join(c.app_path,'Contents/Resources/release-config.json'),'utf8')) as {api_url:string;update_feed_url:string};
  evidence(5,'恢复是删除覆盖且受签名内置值未被修改',true,
    resource.api_url===builtin.api&&resource.update_feed_url===builtin.feed&&
    (!existsSync(join(c.profile_path,'settings.json'))||
      (!Object.hasOwn(saved(),'server')&&!Object.hasOwn(saved(),'feed'))),'filesystem');
});

test('TC-TM001-CONFIG-06',async()=>{
  test.setTimeout(360_000);
  const full=c as Context&{update_url:string;update_control_url:string;update_control_token:string;update_nonce:string};
  if(!full.update_url||!full.update_control_url||!full.update_control_token||!full.update_nonce||!full.cdp_port)
    throw Error('CONFIG-06 requires owned update fixture, nonce, CDP and ShipIt');
  async function mode(value:string){const r=await fetch(c.service_control_url+'/mode',{method:'POST',headers:{Authorization:'Bearer '+c.service_control_token,'Content-Type':'application/json'},body:JSON.stringify({mode:value,route:'/v1/auth/logout'})});expect(r.ok).toBe(true);}
  async function locks(){return {api:await page!.getByTestId('configuration.api-url').isDisabled(),feed:await page!.getByTestId('configuration.update-url').isDisabled(),reset:await page!.getByTestId('configuration.reset-defaults').isDisabled()};}
  async function stage(name:'slow'|'release-slow'){
    const response=await fetch(full.update_control_url+'/'+name,{method:'POST',headers:{Authorization:'Bearer '+full.update_control_token}});
    if(response.status!==200)throw Error(`Owned update source refused ${name}`);
    const result=await response.json() as {stage:string;nonce:string};
    if(result.nonce!==full.update_nonce||result.stage!==(name==='slow'?'slow':'slow-released'))
      throw Error('Owned update source stage/nonce differs');
  }
  async function waitingRequests(){
    const response=await fetch(new URL('/observations',full.update_url),
      {headers:{Authorization:'Bearer '+full.update_control_token}});
    if(response.status!==200)throw Error('Owned update observations unavailable');
    const body=await response.json() as {nonce:string;requests:{stage:string;method:string;route:string;waiting?:boolean}[]};
    if(body.nonce!==full.update_nonce)throw Error('Owned update observation nonce differs');
    return body.requests.filter(row=>row.stage==='slow'&&row.method==='GET'&&row.route==='/update.zip'&&row.waiting===true).length;
  }
  await launch(true);await save(c.service_url,full.update_url);await login();await changePassword();await open();
  evidence(1,'登录状态API和总恢复锁定、更新源可编辑',{api:true,feed:false,reset:true},await locks());
  await page!.getByTestId('configuration.cancel').click();await mode('offline');await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('session.retry-logout')).toBeVisible();await open();
  evidence(2,'退出未确认继续锁定API和总恢复',{api:true,feed:false,reset:true},await locks());
  await page!.getByTestId('configuration.cancel').click();await mode('normal');await page!.getByTestId('session.retry-logout').click();
  await expect(page!.getByTestId('session.retry-logout')).toBeHidden();await open();
  evidence(3,'在线退出完成恢复配置编辑',{api:false,feed:false,reset:false},await locks());
  await page!.getByTestId('configuration.cancel').click();
  const firstWaiting=await waitingRequests();await stage('slow');
  await login('test-alice','TEST-ONLY-Changed-42!');await expect(page!.getByTestId('session.verified')).toBeVisible();
  await expect(page!.getByTestId('updates.check')).toBeEnabled();await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();await page!.getByTestId('updates.install').click();
  await expect.poll(waitingRequests,{timeout:15_000}).toBeGreaterThan(firstWaiting);
  await expect(page!.getByTestId('updates.cancel')).toBeVisible();await open();
  const firstDownloadLocked=await page!.getByTestId('configuration.update-url').isDisabled();
  await page!.getByTestId('configuration.cancel').click();await page!.getByTestId('updates.cancel').click();
  await expect(page!.getByTestId('updates.check')).toBeEnabled();await open();
  const preHandoffCancelRestored=!(await page!.getByTestId('configuration.update-url').isDisabled());
  await page!.getByTestId('configuration.cancel').click();
  await stage('release-slow'); // Drain only the cancelled owned request before the next stage.
  const secondWaiting=await waitingRequests();await stage('slow');
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  await page!.getByTestId('updates.install').click();
  await expect.poll(waitingRequests,{timeout:15_000}).toBeGreaterThan(secondWaiting);
  await expect(page!.getByTestId('updates.cancel')).toBeVisible();await open();
  await expect(page!.getByTestId('configuration.update-url')).toBeDisabled();
  const phases=await attachConfigPhaseObserver();
  const oldPid=app?.process().pid;
  if(!oldPid)throw Error('Old App process has no owned PID');
  const launchesAtHandoff=runnerLaunches;
  if(tracing){await app!.context().tracing.stop({path:join(output!,`trace-${String(++traceNumber).padStart(2,'0')}.zip`)});tracing=false;}
  await stage('release-slow');
  const newPid=await waitForAutonomousPid(oldPid,launchesAtHandoff);
  app=null;page=null;
  await reconnectAutonomous();
  await expect(page!.getByTestId('app.build')).toContainText(`build ${full.expected_upgrade_build??'101'}`);
  const busy=['downloading','verifying','ready','installing'];
  const snapshots=phases.filter(row=>row.kind==='snapshot'&&busy.includes(row.phase));
  const allPhases=busy.every(phase=>snapshots.some(row=>row.phase===phase));
  const stateLocked=snapshots.length>0&&snapshots.every(row=>row.canConfigure===false);
  const visible=phases.filter(row=>row.feedDisabled!==null);
  const uiStayedLocked=visible.length>0&&visible.every(row=>row.feedDisabled===true&&row.resetDisabled===true);
  evidence(4,'真实下载、验证、ready、安装状态锁定更新源并自主升级',
    {firstDownloadLocked:true,allPhases:true,stateLocked:true,uiStayedLocked:true,
      autonomousNewPid:true,feedUnchanged:true},
    {firstDownloadLocked,allPhases,stateLocked,uiStayedLocked,
      autonomousNewPid:newPid!==oldPid&&runnerLaunches===launchesAtHandoff,
      feedUnchanged:saved().feed===full.update_url},'process');
  const installingDom=phases.filter(row=>row.kind==='dom'&&row.phase==='installing');
  const handoffNoCancel=installingDom.some(row=>row.cancelVisible===false);
  evidence(5,'交接前取消恢复编辑；原生交接后没有可取消入口',
    {preHandoffCancelRestored:true,handoffNoCancel:true},
    {preHandoffCancelRestored,handoffNoCancel},'ui');
  writeFileSync(join(output!,'config-upgrade-process.json'),JSON.stringify({run_id:c.run_id,case_id:c.case_id,
    old_pid:oldPid,new_pid:newPid,runner_launches_before:launchesAtHandoff,
    runner_launches_after:runnerLaunches,observed_phases:[...new Set(snapshots.map(row=>row.phase))]},null,2)+'\n',{mode:0o600});
});
