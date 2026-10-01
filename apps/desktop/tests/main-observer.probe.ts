/** Fixed runner diagnostic: never classifies a product TC as PASS. */
import {mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createServer} from 'node:http';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {launchObserved,observations} from '../e2e/main-observer.ts';
const [source,outputArg]=process.argv.slice(2);if(!source||!outputArg)throw Error('App and new output required');
const output=resolve(outputArg);mkdirSync(output,{mode:0o700});
const temp=realpathSync(mkdtempSync(join(tmpdir(),'tm-observer-probe-')));
const profile=join(temp,'profile');mkdirSync(profile,{mode:0o700});
const target=join(temp,'TokenMeter.app');execFileSync('/usr/bin/ditto',[source,target],{timeout:120_000});
const received:{method:string;path:string}[]=[];
const server=createServer((req,res)=>{received.push({method:req.method??'',path:req.url??''});req.resume();res.writeHead(503,{'Content-Type':'application/json'});res.end('{"error":"probe-service-unavailable"}');});
await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
const address=server.address();if(!address||typeof address==='string')throw Error('port absent');
let app;let status='FAIL';let detail='';
try{
  app=await launchObserved({executablePath:join(target,'Contents/MacOS/TokenMeter'),
    args:[`--user-data-dir=${profile}`],chromiumSandbox:true,timeout:60_000},
    {run_id:'observer-component-probe',case_id:'observer-component-probe',output});
  const page=await app.firstWindow();
  page.on('console',message=>writeFileSync(join(output,'renderer-console.log'),message.text()+'\n',{flag:'a',mode:0o600}));
  page.on('pageerror',error=>writeFileSync(join(output,'renderer-errors.log'),String(error)+'\n',{flag:'a',mode:0o600}));
  try{await page.getByTestId('auth.login').waitFor();}catch(error){
    writeFileSync(join(output,'failure-dom.json'),JSON.stringify({url:page.url(),body:await page.locator('body').textContent()},null,2),{mode:0o600});
    await page.screenshot({path:join(output,'failure.png')});throw error;}

  const startup=observations(output);assert.equal(startup[0]?.kind,'installed-before-entry');
  assert.equal(startup.filter(row=>row.kind==='request').length,0);
  await page.getByTestId('configuration.open').click();
  await page.getByTestId('configuration.api-url').fill(`http://127.0.0.1:${address.port}`);
  await page.getByTestId('configuration.save').click();
  await page.getByTestId('auth.username').fill('observer-synthetic');
  await page.getByTestId('auth.password').fill('OBSERVER-TEST-PASSWORD');
  await page.getByTestId('auth.login').click();await page.getByTestId('auth.error').waitFor();
  const all=observations(output);
  assert.equal(received.filter(row=>row.method==='POST'&&row.path==='/v1/auth/login').length,1);
  assert.equal(all.filter(row=>row.kind==='request'&&row.method==='POST'&&row.path==='/v1/auth/login').length,1);
  assert.equal(all.filter(row=>row.kind==='native-updater').length,0);
  assert(!readFileSync(join(output,'main-observer.jsonl'),'utf8').includes('OBSERVER-TEST-PASSWORD'));
  status='PASS';
}catch(error){detail=String(error);process.exitCode=1;}
finally{if(app)await app.close();await new Promise<void>((resolve,reject)=>server.close(error=>error?reject(error):resolve()));
  rmSync(temp,{recursive:true});writeFileSync(join(output,'result.json'),JSON.stringify({scope:'observer_component_probe',status,detail,received},null,2),{mode:0o600});}
console.log(JSON.stringify({status,detail,output}));
