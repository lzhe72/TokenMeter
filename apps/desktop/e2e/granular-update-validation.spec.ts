/** Negative UPDATE-05 variants against a real installed App and owned loopback feed. */
import { test, expect, type ElectronApplication, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { appendFileSync, existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {launchObserved, observations as mainObservations} from './main-observer';

type Context = {
  run_id:string; case_id:string; candidate_sha:string;
  app_path:string; profile_path:string; database_path:string; service_url:string;
  update_url:string; validation_fixture_url:string;
  validation_fixture_control_url:string; validation_fixture_control_token:string;
  validation_variant:string; validation_fixture_manifest_path:string;
  owned_sentinel_path:string; package_manifest_path:string;
  expected_app_version:string; expected_app_build:string;
  expected_upgrade_version:string; expected_upgrade_build:string;
};
type Observation = {stage:string; route:string; method:string; status:number;
  bytes_sent:number; declared_bytes?:number; body_sha256:string; time:string};
type FixtureManifest = {variant_id:string; archive_sha256:string; archive_bytes:number;
  metadata_sha256:string; metadata_bytes:number; metadata_version:string; metadata_build:string;
  ed25519_signature_present:boolean; sentinel_sha256:string; source_nonce:string;
  code_signature_verified?:boolean; candidate_requirement_rejected?:boolean;
  certificate_matches_candidate?:boolean|null};
type PackageManifest = {app:{version:string; build:string; tree_sha256:string}; update_app:{version:string; build:string};
  artifacts:{update_zip:{bytes:number; sha256:string}}};
const contextPath=process.env.TM_E2E_CONTEXT;
const output=process.env.TM_E2E_CASE_OUTPUT;
if (!contextPath || !output) throw new Error('Owned granular context/output are required');
const c=JSON.parse(readFileSync(contextPath,'utf8')) as Context;
const binary=join(c.app_path,'Contents/MacOS/TokenMeter');
const events=join(output,'events.jsonl');
const variant=c.case_id.split('#',2)[1];
let app:ElectronApplication|null=null;
let page:Page|null=null;
let tracing=false;
test.setTimeout(420_000);

function required<T>(value:T|null|undefined,label:string):T {
  if (value==null || value==='') throw new Error(`${label} has no owned runner fixture`);
  return value;
}
const expectedAppVersion=required(c.expected_app_version,'expected_app_version');
const expectedAppBuild=required(c.expected_app_build,'expected_app_build');
const expectedUpgradeVersion=required(c.expected_upgrade_version,'expected_upgrade_version');
const expectedUpgradeBuild=required(c.expected_upgrade_build,'expected_upgrade_build');
function nextPatch(version:string):string {
  const match=/^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if(!match)throw new Error('Approved update version is not a three-part version');
  return `${match[1]}.${match[2]}.${Number(match[3])+1}`;
}
function nextBuild(build:string):string {
  if(!/^[1-9]\d*$/.test(build))throw new Error('Approved update build is not a positive integer');
  return String(Number(build)+1);
}
function digest(input:Buffer|string):string {return createHash('sha256').update(input).digest('hex');}
function digestFile(path:string):string {return digest(readFileSync(path));}
function dbState():string {
  const sql="SELECT id,username,role,is_active,must_change_password,credential_version FROM users ORDER BY id;"+
    "SELECT user_id,credential_version,COUNT(*) FROM sessions GROUP BY user_id,credential_version;"+
    "SELECT version_num FROM alembic_version;"+
    "SELECT COUNT(*) FROM audit;";
  return digest(execFileSync('/usr/bin/sqlite3',['-readonly',c.database_path,sql],{encoding:'utf8'}));
}
function originalTree():string {
  const root=resolve(process.cwd(),'../..');
  return execFileSync('python3',['-c',
    'from pathlib import Path; from scripts.package_release_dmg import tree_sha256; import sys; print(tree_sha256(Path(sys.argv[1])))',
    c.app_path],{cwd:root,encoding:'utf8',timeout:120_000}).trim();
}
function build():string {
  return execFileSync('/usr/bin/plutil',['-extract','CFBundleVersion','raw',
    join(c.app_path,'Contents/Info.plist')],{encoding:'utf8'}).trim();
}
function ownedPids():number[] {
  return execFileSync('/bin/ps',['-axo','pid=,command='],{encoding:'utf8'}).split('\n')
    .map(line=>line.trim().match(/^(\d+)\s+(.*)$/))
    .filter((match):match is RegExpMatchArray=>Boolean(match&&match[2]!.startsWith(binary)))
    .map(match=>Number(match[1]));
}
function tempDownloads():string[] {return readdirSync(c.profile_path).filter(name=>name.startsWith('update-'));}
function childEnvironment():Record<string,string> {
  return Object.fromEntries(Object.entries(process.env).filter(([key,value])=>
    value!==undefined&&!key.startsWith('TM_E2E_')&&!key.startsWith('TM_INTERNAL_')&&
    !key.includes('SIGNING')&&!key.includes('TOKEN'))) as Record<string,string>;
}
async function step(index:number,action:string,source:'ui'|'service'|'database'|'filesystem'|'process',
                    expected:unknown,actual:unknown):Promise<void> {
  let screenshot:string|null=null;
  if (page&&!page.isClosed()) {
    screenshot=`TC-step-${String(index).padStart(2,'0')}.png`;
    await page.screenshot({path:join(output!,screenshot)});
  }
  const passed=JSON.stringify(expected)===JSON.stringify(actual);
  appendFileSync(events,JSON.stringify({run_id:c.run_id,case_id:c.case_id,step:index,action,source,
    expected,actual,passed,timestamp:new Date().toISOString(),screenshot})+'\n',{mode:0o600});
  expect(actual,`${c.case_id} step ${index}: ${action}`).toEqual(expected);
}
async function launch():Promise<void> {
  if (!existsSync(binary)) throw new Error('Installed final-DMG App is unavailable');
  app=await launchObserved({executablePath:binary,args:[`--user-data-dir=${c.profile_path}`],
    env:childEnvironment(),chromiumSandbox:true,timeout:60_000},
    {run_id:c.run_id,case_id:c.case_id,output:output!});
  page=await app.firstWindow();
  await expect(page.getByTestId('app.build')).toContainText(`build ${expectedAppBuild}`);
  expect(build()).toBe(expectedAppBuild);
  await app.context().tracing.start({screenshots:true,snapshots:true,sources:false});
  tracing=true;
}
async function close():Promise<void> {
  if (app) {
    if (tracing) {
      await app.context().tracing.stop({path:join(output!,'trace-01.zip')});
      tracing=false;
    }
    await app.close();app=null;page=null;
  }
}
async function configure():Promise<void> {
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(c.service_url);
  await page!.getByTestId('configuration.update-url').fill(c.update_url);
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('configuration.status')).toContainText('配置已保存');
  await expect(page!.getByTestId('auth.server')).toHaveValue(c.service_url);
}
async function memberReady():Promise<void> {
  await page!.getByTestId('auth.username').fill('test-alice');
  await page!.getByTestId('auth.password').fill('TEST-ONLY-alice-42!');
  await page!.getByTestId('auth.login').click();
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await page!.getByTestId('password.current').fill('TEST-ONLY-alice-42!');
  await page!.getByTestId('password.new').fill('TEST-ONLY-Changed-42!');
  await page!.getByTestId('password.confirm').fill('TEST-ONLY-Changed-42!');
  await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('session.username')).toHaveText('test-alice');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await expect(page!.getByTestId('updates.status')).toContainText('当前已是最新版本');
}
async function activate(nonce:string):Promise<void> {
  const response=await fetch(required(c.validation_fixture_control_url,'validation_fixture_control_url')+'/activate',
    {method:'POST',headers:{Authorization:'Bearer '+required(c.validation_fixture_control_token,'validation_fixture_control_token')}});
  if (response.status!==200) throw new Error('Owned validation source refused activation');
  const body=await response.json() as {stage:string;nonce:string};
  if (body.stage!=='negative'||body.nonce!==nonce) throw new Error('Validation source nonce/stage mismatch');
}
async function observations(nonce:string):Promise<Observation[]> {
  const response=await fetch(required(c.validation_fixture_url,'validation_fixture_url')+'/observations',
    {headers:{Authorization:'Bearer '+required(c.validation_fixture_control_token,'validation_fixture_control_token')}});
  if (response.status!==200) throw new Error('Owned validation source observations unavailable');
  const body=await response.json() as {nonce:string;requests:Observation[]};
  if (body.nonce!==nonce) throw new Error('Validation source observation nonce mismatch');
  return body.requests;
}

type Variant = {id:string;step:1|2|3|4;error:string;archive:boolean;archiveBody:boolean};
const variants:Variant[]=[
  {id:'BYTES',step:1,error:'update_integrity_failed',archive:true,archiveBody:true},
  {id:'SHA',step:1,error:'update_integrity_failed',archive:true,archiveBody:true},
  {id:'TRUNCATED',step:1,error:'update_integrity_failed',archive:true,archiveBody:true},
  {id:'ZIP_LIMIT_METADATA',step:1,error:'update_metadata_invalid',archive:false,archiveBody:false},
  {id:'ZIP_LIMIT_HEADER',step:1,error:'update_integrity_failed',archive:true,archiveBody:false},
  {id:'UNPACK_LIMIT',step:1,error:'update_bundle_invalid',archive:true,archiveBody:true},
  {id:'INFO_VERSION',step:2,error:'update_bundle_invalid',archive:true,archiveBody:true},
  {id:'INFO_BUILD',step:2,error:'update_bundle_invalid',archive:true,archiveBody:true},
  {id:'BUNDLE_ID',step:3,error:'update_bundle_invalid',archive:true,archiveBody:true},
  {id:'CERT_MISMATCH',step:3,error:'update_bundle_invalid',archive:true,archiveBody:true},
  {id:'DR_MISMATCH',step:3,error:'update_bundle_invalid',archive:true,archiveBody:true},
  {id:'PATH_ESCAPE',step:4,error:'update_bundle_invalid',archive:true,archiveBody:true},
  {id:'SYMLINK_PARENT',step:4,error:'update_bundle_invalid',archive:true,archiveBody:true},
];

test.beforeEach(async ({},info)=>{
  if (info.title!==c.case_id||c.validation_variant!==c.case_id||variant!==info.title.split('#')[1])
    throw new Error('Runner selected a different UPDATE-05 variant');
});
test.afterEach(async ()=>{
  try {if (page&&!page.isClosed()) await page.screenshot({path:join(output!,'final.png')});} catch {/* raw failure */}
  try {await close();} catch {/* runner checks owned process cleanup */}
});

for (const selected of variants) {
  test(`TC-TM001-UPDATE-05#${selected.id}`,async ()=>{
    const fixture=JSON.parse(readFileSync(required(c.validation_fixture_manifest_path,
      'validation_fixture_manifest_path'),'utf8')) as FixtureManifest;
    const packageInfo=JSON.parse(readFileSync(c.package_manifest_path,'utf8')) as PackageManifest;
    expect({appVersion:packageInfo.app.version,appBuild:String(packageInfo.app.build),
      upgradeVersion:packageInfo.update_app.version,upgradeBuild:String(packageInfo.update_app.build)}).toEqual({
      appVersion:expectedAppVersion,appBuild:expectedAppBuild,
      upgradeVersion:expectedUpgradeVersion,upgradeBuild:expectedUpgradeBuild});
    if (fixture.variant_id!==c.case_id||fixture.ed25519_signature_present!==true)
      throw new Error('Negative fixture manifest does not bind this case');
    if (selected.id==='BUNDLE_ID'&&fixture.code_signature_verified!==true)
      throw new Error('Wrong-bundle-ID fixture lacks verified complete App code signature');
    if (selected.id==='CERT_MISMATCH'||selected.id==='DR_MISMATCH') {
      if (fixture.code_signature_verified!==true||fixture.candidate_requirement_rejected!==true||
          fixture.certificate_matches_candidate!==(selected.id==='DR_MISMATCH'))
        throw new Error('Identity-layer fixture did not reach the intended candidate DR check');
    }
    await launch();await configure();await memberReady();
    const beforePid=required(app?.process().pid,'old App PID');
    const beforeTree=originalTree();
    const beforeDb=dbState();
    const beforeSentinel=digestFile(c.owned_sentinel_path);
    const beforeRequests=await observations(fixture.source_nonce);
    await activate(fixture.source_nonce);
    await page!.getByTestId('updates.check').click();
    if (selected.archive) {
      await expect(page!.getByTestId('updates.install')).toBeVisible();
      await page!.getByTestId('updates.install').click();
    }
    await expect(page!.getByTestId('updates.status')).toContainText(selected.error);
    const afterRequests=(await observations(fixture.source_nonce)).slice(beforeRequests.length);
    const manifest=afterRequests.filter(item=>item.stage==='negative'&&item.route==='/version.json'&&item.status===200);
    const downloads=afterRequests.filter(item=>item.stage==='negative'&&item.route==='/update.zip'&&item.status===200);
    const actualArchive=downloads[0];
    const status=(await page!.getByTestId('updates.status').textContent())??'';
    const advertisedMismatch=selected.id==='INFO_VERSION'
      ? fixture.metadata_version===nextPatch(expectedUpgradeVersion)&&fixture.metadata_build===expectedUpgradeBuild
      : selected.id==='INFO_BUILD'
        ? fixture.metadata_build===nextBuild(expectedUpgradeBuild)&&fixture.metadata_version===expectedUpgradeVersion
        : fixture.metadata_version===expectedUpgradeVersion&&fixture.metadata_build===expectedUpgradeBuild;
    const identityLayerReached=selected.step!==3||selected.id==='BUNDLE_ID'
      ? true
      : fixture.code_signature_verified===true&&fixture.candidate_requirement_rejected===true;
    await step(selected.step,'Use the real update UI with one independently generated negative package or metadata variant','ui',
      {error:true,sourceManifest:true,archiveCount:selected.archive?1:0,
        archiveBody:selected.archiveBody,advertisedMismatch:true,identityLayerReached:true},
      {error:status.includes(selected.error),sourceManifest:manifest.length>=1,
        archiveCount:downloads.length,archiveBody:Boolean(actualArchive&&actualArchive.bytes_sent>0),
        advertisedMismatch,identityLayerReached});
    const cleanupStarted=Date.now();
    const cleanupSamples:Array<{time:string;elapsed_ms:number;entries:string[]}>=[];
    try {
      await expect.poll(()=>{
        const entries=tempDownloads();
        cleanupSamples.push({time:new Date().toISOString(),elapsed_ms:Date.now()-cleanupStarted,entries});
        return entries;
      },{timeout:20_000,intervals:[100,250,500,1000],message:'Owned update scratch must finish asynchronous cleanup'}).toEqual([]);
    } finally {
      writeFileSync(join(output!,'cleanup-observation.json'),JSON.stringify({run_id:c.run_id,case_id:c.case_id,
        started_at:new Date(cleanupStarted).toISOString(),timeout_ms:20_000,business_action_repeated:false,
        samples:cleanupSamples},null,2)+'\n',{mode:0o600});
    }
    const afterTree=originalTree();
    const observed=mainObservations(output!);
    await step(5,'Compare original installed App, running PID, isolated DB, update scratch and external sentinel','process',
      {samePid:true,sameTree:true,originalPackage:true,originalBuild:true,dbUnchanged:true,
        sentinelUnchanged:true,noUpdateScratch:true,noNativeReplacement:true,
        observerBeforeEntry:true,nativeHandoffCount:0},
      {samePid:JSON.stringify(ownedPids())===JSON.stringify([beforePid]),
        sameTree:afterTree===beforeTree,
        originalPackage:beforeTree===packageInfo.app.tree_sha256,
        originalBuild:build()===expectedAppBuild,dbUnchanged:dbState()===beforeDb,
        sentinelUnchanged:digestFile(c.owned_sentinel_path)===beforeSentinel&&beforeSentinel===fixture.sentinel_sha256,
        noUpdateScratch:tempDownloads().length===0,
        noNativeReplacement:app?.process().pid===beforePid&&!app?.process().killed,
        observerBeforeEntry:observed[0]?.kind==='installed-before-entry'&&observed[0]?.pid===beforePid,
        nativeHandoffCount:observed.filter(row=>row.kind==='native-updater').length});
  });
}
