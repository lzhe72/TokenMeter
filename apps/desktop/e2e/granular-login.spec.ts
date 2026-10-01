/**
 * Task-level TM-001 login and password cases. Run one TC against a newly seeded
 * D42 database, an installed App copy, and an owned profile. The runner must
 * select exactly one test by its full TC ID and verify every catalog step.
 *
 * No production credentials, tokens, password values, or hashes are written to
 * events. Unsupported variants are deliberately absent until their isolated
 * data or fault fixture is available; the runner must mark them BLOCKED.
 */
import { test, expect, _electron as electron, type ElectronApplication, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { appendFileSync, existsSync, lstatSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve, sep } from 'node:path';

type Context = {
  run_id: string; case_id: string; candidate_sha: string;
  app_path: string; profile_path: string; database_path: string;
  service_url: string; fixture_kind?: string;
  service_control_url?: string; service_control_token?: string; backend_service_url?: string;
  clock_path?: string; clock_start?: number;
  peer_app_path?: string; peer_profile_path?: string;
};
const contextFile = process.env.TM_E2E_CONTEXT;
const output = process.env.TM_E2E_CASE_OUTPUT;
if (!contextFile || !output) throw new Error('Owned granular case context is missing');
const c = JSON.parse(readFileSync(contextFile, 'utf8')) as Context;
const binary = join(c.app_path, 'Contents/MacOS/TokenMeter');
const eventsFile = join(output, 'events.jsonl');
const dbPath = c.database_path;
if (!dbPath || !existsSync(dbPath) || lstatSync(dbPath).isSymbolicLink() ||
    !realpathSync(dbPath).startsWith(realpathSync(dirname(contextFile)) + sep) ||
    dbPath.includes('/database/production/')) {
  throw new Error('Owned test SQLite path is missing or outside the case directory');
}
let app: ElectronApplication | null = null;
let page: Page | null = null;
let tracing = false;
let traceNumber = 0;
const extraApps: ElectronApplication[] = [];

function record(step: number, action: string, source: 'ui' | 'service' | 'database' | 'filesystem' | 'process',
                expected: unknown, actual: unknown): void {
  const passed = JSON.stringify(actual) === JSON.stringify(expected);
  appendFileSync(eventsFile, JSON.stringify({run_id:c.run_id, case_id:c.case_id, step, action,
    source, expected, actual, passed, timestamp:new Date().toISOString()}) + '\n', {mode:0o600});
  expect(actual, `${c.case_id} step ${step}: ${action}`).toEqual(expected);
}
function q<T = Record<string, unknown>>(sql: string): T[] {
  const raw = execFileSync('/usr/bin/sqlite3', ['-readonly', '-json', dbPath, sql], {encoding:'utf8'}).trim();
  return raw ? JSON.parse(raw) as T[] : [];
}
function scalar(sql: string): number { return Number(Object.values(q(sql)[0] ?? {})[0] ?? 0); }
function sessions(): number { return scalar('SELECT COUNT(*) AS n FROM sessions;'); }
function users(): number { return scalar('SELECT COUNT(*) AS n FROM users;'); }
function changedAudits(): number { return scalar("SELECT COUNT(*) AS n FROM audit WHERE action='password_changed';"); }
function user(name: 'test-alice' | 'test-admin' | 'test-bob' | 'test-disabled') {
  return q<{id:string;role:string;is_active:number;must_change_password:number}>(
    `SELECT id,role,is_active,must_change_password FROM users WHERE username='${name}';`)[0];
}
const BOUNDARY_ID='00000000-0000-4000-8000-000000000101';
function boundaryUser() {
  return q<{id:string;username:string;role:string;is_active:number;must_change_password:number}>(
    `SELECT id,username,role,is_active,must_change_password FROM users WHERE id='${BOUNDARY_ID}';`)[0];
}
function credentialPath(): string {
  return join(c.profile_path, 'credentials', createHash('sha256').update(c.service_url).digest('hex') + '.token');
}
function savedToken(): string {
  const path = credentialPath();
  if (!existsSync(path) || lstatSync(path).isSymbolicLink()) throw new Error('Owned profile has no regular saved token');
  const value = readFileSync(path, 'utf8');
  if (!/^[A-Za-z0-9_-]{43}$/.test(value)) throw new Error('Saved token shape invalid');
  return value;
}
function childEnvironment(): Record<string,string> {
  return Object.fromEntries(Object.entries(process.env).filter(([key,value]) =>
    value !== undefined && !key.startsWith('TM_E2E_') && !key.startsWith('TM_INTERNAL_') &&
    !key.includes('SIGNING') && !key.includes('TOKEN'))) as Record<string,string>;
}
async function launch(): Promise<void> {
  if (!existsSync(binary)) throw new Error('Installed Electron App is missing');
  app = await electron.launch({executablePath:binary, args:[`--user-data-dir=${c.profile_path}`],
    env:childEnvironment(), chromiumSandbox:true, timeout:60_000});
  page = await app.firstWindow();
  await expect(page.getByTestId('app.build')).toBeVisible();
  await app.context().tracing.start({screenshots:true, snapshots:true, sources:false});
  tracing = true;
}
async function close(): Promise<void> {
  if (app) {
    if (tracing) {
      await app.context().tracing.stop({path:join(output!,`trace-${String(++traceNumber).padStart(2,'0')}.zip`)});
      tracing = false;
    }
    await app.close(); app = null; page = null;
  }
}
async function restart(): Promise<void> { await close(); await launch(); }
async function configure(): Promise<void> {
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(c.service_url);
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('auth.server')).toHaveValue(c.service_url);
}
async function configurePage(other: Page): Promise<void> {
  await other.getByTestId('configuration.open').click();
  await other.getByTestId('configuration.api-url').fill(c.service_url);
  await other.getByTestId('configuration.save').click();
  await expect(other.getByTestId('auth.server')).toHaveValue(c.service_url);
}
async function start(): Promise<void> {
  if (c.fixture_kind && c.fixture_kind !== 'auth_accounts') throw new Error('D42 auth_accounts fixture required');
  expect(users()).toBe(4);
  expect(sessions()).toBe(0);
  await launch(); await configure();
}
async function startBounds(): Promise<void> {
  if (c.fixture_kind !== 'D42-BOUNDS') throw new Error('Owned D42-BOUNDS fixture required');
  expect(users()).toBe(5);
  expect(sessions()).toBe(0);
  await launch(); await configure();
}
async function fillLogin(name: string, password: string): Promise<void> {
  await page!.getByTestId('auth.username').fill(name);
  await page!.getByTestId('auth.password').fill(password);
}
async function login(name: string, password: string): Promise<void> {
  await fillLogin(name,password);
  await page!.getByTestId('auth.login').click();
}
async function uiError(code: string): Promise<boolean> {
  await expect(page!.getByTestId('auth.error')).toContainText(code);
  return (await page!.getByTestId('auth.error').textContent() ?? '').includes(code);
}
async function uiName(name: string): Promise<boolean> {
  await expect(page!.getByTestId('session.username')).toHaveText(name);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  return (await page!.getByTestId('session.username').textContent())?.trim() === name;
}
async function fillPassword(current: string, next: string, confirm = next): Promise<void> {
  await page!.getByTestId('password.current').fill(current);
  await page!.getByTestId('password.new').fill(next);
  await page!.getByTestId('password.confirm').fill(confirm);
}
async function changePassword(current: string, next: string): Promise<void> {
  await fillPassword(current,next);
  await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('password.status')).toBeVisible();
}
async function api(method: string, route: string, body?: Record<string,unknown>, token?: string) {
  const response = await fetch(c.service_url + route, {method,
    headers:{...(body ? {'Content-Type':'application/json'} : {}),...(token ? {Authorization:`Bearer ${token}`} : {}),
      'X-TM-Test-Probe':'1'},
    body:body ? JSON.stringify(body) : undefined});
  const raw = await response.text();
  return {status:response.status, body:raw ? JSON.parse(raw) as Record<string,any> : {}};
}
type TransportMode = 'normal' | 'offline' | 'unavailable' | 'delay';
type TransportRequest = {route:string; mode:TransportMode; forwarded:boolean;
  status?:number; probe:boolean; received_at:string; finished_at?:string; delayed_seconds?:number};
async function controlTransport(mode: TransportMode, route: string, releaseDelayed = true): Promise<void> {
  if (!c.service_control_url || !c.service_control_token || !c.backend_service_url) {
    throw new Error('Owned loopback transport control is missing');
  }
  const response=await fetch(c.service_control_url+'/mode',{method:'POST',
    headers:{'Content-Type':'application/json',Authorization:'Bearer '+c.service_control_token},
    body:JSON.stringify({mode,route,release_delayed:releaseDelayed})});
  if (response.status!==200) throw new Error('Owned transport control refused mode change');
}
async function releaseDelayedTransport(): Promise<void> {
  if (!c.service_control_url || !c.service_control_token) throw new Error('Owned transport control missing');
  const response=await fetch(c.service_control_url+'/release-delayed',{method:'POST',
    headers:{Authorization:'Bearer '+c.service_control_token}});
  if (response.status!==200) throw new Error('Owned delayed request could not be released');
}
async function transportRequests(): Promise<TransportRequest[]> {
  if (!c.service_control_url || !c.service_control_token) throw new Error('Owned transport observations missing');
  const response=await fetch(c.service_control_url+'/observations',{
    headers:{Authorization:'Bearer '+c.service_control_token}});
  if (response.status!==200) throw new Error('Owned transport observations rejected');
  const value=await response.json() as {requests:TransportRequest[]};
  return value.requests;
}
async function apiLogin(name: string, password: string): Promise<string> {
  const response = await api('POST','/v1/auth/login',{username:name,password});
  expect(response.status).toBe(200);
  expect(response.body.access_token).toMatch(/^[A-Za-z0-9_-]{43}$/);
  return response.body.access_token as string;
}
async function prepareChangedAlice(next = 'TEST-ONLY-Changed-42!'): Promise<void> {
  const old = await apiLogin('test-alice','TEST-ONLY-alice-42!');
  const changed = await api('POST','/v1/auth/change-password',
    {current_password:'TEST-ONLY-alice-42!',new_password:next},old);
  expect(changed.status).toBe(200);
  const logout = await api('POST','/v1/auth/logout',undefined,changed.body.access_token as string);
  expect(logout.status).toBe(204);
  expect(user('test-alice')?.must_change_password).toBe(0);
}
async function firstAlice(): Promise<void> {
  await start(); await login('test-alice','TEST-ONLY-alice-42!');
  await expect(page!.getByTestId('password.new')).toBeVisible();
}
async function oldAndNewStatus(next: string): Promise<{old:number;next:number}> {
  const old = await api('POST','/v1/auth/login',{username:'test-alice',password:'TEST-ONLY-alice-42!'});
  const after = await api('POST','/v1/auth/login',{username:'test-alice',password:next});
  return {old:old.status,next:after.status};
}

test.beforeEach(async ({}, info) => {
  if (info.title !== c.case_id) throw new Error('Runner selected the wrong granular TC');
});
test.afterEach(async () => {
  try { if (page && !page.isClosed()) await page.screenshot({path:join(output!,'final.png')}); } catch { /* raw result records failure */ }
  try { await close(); } catch { /* runner checks cleanup separately */ }
  for (const extra of extraApps.splice(0)) {
    try { await extra.close(); } catch { /* runner checks owned process cleanup */ }
  }
});

test('TC-TM001-LOGIN-01', async () => {
  await start(); await fillLogin('test-alice','TEST-ONLY-alice-42!');
  record(1,'Fill preset member credentials before submission','ui',
    {name:'test-alice',masked:true,sessions:0},
    {name:await page!.getByTestId('auth.username').inputValue(),
     masked:await page!.getByTestId('auth.password').getAttribute('type') === 'password',sessions:sessions()});
  await page!.getByTestId('auth.login').click();
  record(2,'Submit first member login and inspect identity','ui',
    {identity:true,role:'成员',forced:true,admin:false,storedSessions:1},
    {identity:await uiName('test-alice'),role:(await page!.getByTestId('session.role').textContent())?.trim(),
     forced:await page!.getByTestId('password.new').isVisible(),
     admin:await page!.getByTestId('admin.accounts').isVisible(),storedSessions:sessions()});
  const token = savedToken();
  const me = await api('GET','/v1/me',undefined,token);
  const admin = await api('GET','/v1/admin/users',undefined,token);
  record(3,'Verify member identity and administrator denial through real API','service',
    {me:200,id:'00000000-0000-4000-8000-000000000002',role:'member',mustChange:true,admin:403},
    {me:me.status,id:me.body.id,role:me.body.role,mustChange:me.body.must_change_password,admin:admin.status});
});

test('TC-TM001-LOGIN-02', async () => {
  await start(); await login('test-missing','TEST-ONLY-alice-42!');
  const firstError = await uiError('invalid_credentials');
  record(1,'Attempt login with unknown account and valid password of another account','ui',
    {error:true,loginVisible:true,users:4,sessions:0},
    {error:firstError,loginVisible:await page!.getByTestId('auth.login').isVisible(),users:users(),sessions:sessions()});
  await login('test-alice','TEST-ONLY-Wrong-42!');
  const secondError = await uiError('invalid_credentials');
  record(2,'Compare error category with wrong password for an existing account','ui',
    {unknown:'invalid_credentials',known:'invalid_credentials',same:true},
    {unknown:firstError?'invalid_credentials':'other',known:secondError?'invalid_credentials':'other',same:firstError===secondError});
});

test('TC-TM001-LOGIN-03', async () => {
  await start(); await login('test-alice','TEST-ONLY-Wrong-42!');
  record(1,'Submit wrong password for known account','ui',
    {error:true,loginVisible:true,sessions:0,unchanged:true},
    {error:await uiError('invalid_credentials'),loginVisible:await page!.getByTestId('auth.login').isVisible(),
     sessions:sessions(),unchanged:user('test-alice')?.must_change_password===1});
  await login('test-alice','TEST-ONLY-alice-42!');
  record(2,'Correct password after one failed attempt','ui',
    {identity:true,forced:true,role:'成员',sessions:1},
    {identity:await uiName('test-alice'),forced:await page!.getByTestId('password.new').isVisible(),
     role:(await page!.getByTestId('session.role').textContent())?.trim(),sessions:sessions()});
});

test('TC-TM001-LOGIN-04', async () => {
  await start(); await login('test-missing','TEST-ONLY-Wrong-42!');
  record(1,'Reject both invalid account and password without revealing account existence','ui',
    {error:true,loginVisible:true,users:4,sessions:0},
    {error:await uiError('invalid_credentials'),loginVisible:await page!.getByTestId('auth.login').isVisible(),
     users:users(),sessions:sessions()});
  await page!.getByTestId('auth.username').fill(''); await page!.getByTestId('auth.password').fill('');
  record(2,'Clear inputs and ensure no cached identity appears','ui',
    {name:'',passwordEmpty:true,loginVisible:true,users:4},
    {name:await page!.getByTestId('auth.username').inputValue(),
     passwordEmpty:(await page!.getByTestId('auth.password').inputValue())==='',
     loginVisible:await page!.getByTestId('auth.login').isVisible(),users:users()});
});

for (const [id,name,password] of [
  ['TC-TM001-LOGIN-05','','TEST-ONLY-alice-42!'],
  ['TC-TM001-LOGIN-06','test-alice',''],
  ['TC-TM001-LOGIN-07','',''],
] as const) {
  test(id, async () => {
    await start(); await fillLogin(name,password);
    await page!.getByTestId('auth.password').press('Enter');
    record(1,'Attempt login with empty required field through the App form','ui',
      {buttonDisabled:true,loginVisible:true,users:4,sessions:0},
      {buttonDisabled:await page!.getByTestId('auth.login').isDisabled(),
       loginVisible:await page!.getByTestId('auth.login').isVisible(),users:users(),sessions:sessions()});
    const direct = await api('POST','/v1/auth/login',{username:name,password});
    record(2,'Submit identical invalid input to the real service','service',
      {rejected:true,users:4,sessions:0},
      {rejected:direct.status>=400&&direct.status<500,users:users(),sessions:sessions()});
  });
}

test('TC-TM001-LOGIN-08', async () => {
  await start(); await login('test-disabled','TEST-ONLY-disabled-42!');
  record(1,'Reject disabled account despite correct password','ui',
    {error:true,loginVisible:true,sessions:0,disabled:true},
    {error:await uiError('account_disabled'),loginVisible:await page!.getByTestId('auth.login').isVisible(),
     sessions:sessions(),disabled:user('test-disabled')?.is_active===0});
  await restart();
  record(2,'Restart App without restoring a disabled identity','ui',
    {loginVisible:true,saved:false,sessions:0},
    {loginVisible:await page!.getByTestId('auth.login').isVisible(),
     saved:existsSync(credentialPath()),sessions:sessions()});
});

test('TC-TM001-LOGIN-09', async () => {
  await start(); await login('test-alice','x');
  record(1,'Submit one-character incorrect login password','ui',
    {error:true,loginVisible:true,sessions:0},
    {error:await uiError('invalid_credentials'),loginVisible:await page!.getByTestId('auth.login').isVisible(),sessions:sessions()});
  const direct=await api('POST','/v1/auth/login',{username:'test-alice',password:'x'});
  record(2,'Confirm service treats one character as a wrong credential, not a new-password policy error','service',
    {status:401,sessions:0,unchanged:true},
    {status:direct.status,sessions:sessions(),unchanged:user('test-alice')?.must_change_password===1});
});

test('TC-TM001-LOGIN-10', async () => {
  await prepareChangedAlice(); await startAfterPreparation();
  await login('test-alice','TEST-ONLY-Changed-42!');
  record(1,'Login with a password changed through the real API','ui',
    {identity:true,role:'成员',forced:false,mustChange:false},
    {identity:await uiName('test-alice'),role:(await page!.getByTestId('session.role').textContent())?.trim(),
     forced:(await page!.getByText('首次登录，请更改密码').count())>0,mustChange:user('test-alice')?.must_change_password===1});
  await page!.getByTestId('session.refresh').click();
  const me=await api('GET','/v1/me',undefined,savedToken());
  record(2,'Refresh normal member identity through App and service','service',
    {identity:true,me:200,role:'member',adminVisible:false},
    {identity:await uiName('test-alice'),me:me.status,role:me.body.role,
     adminVisible:await page!.getByTestId('admin.accounts').isVisible()});
});

async function startAfterPreparation(): Promise<void> {
  if (c.fixture_kind && c.fixture_kind !== 'auth_accounts') throw new Error('D42 auth_accounts fixture required');
  expect(users()).toBe(4); await launch(); await configure();
}

test('TC-TM001-LOGIN-11', async () => {
  await start(); await login('test-admin','TEST-ONLY-admin-42!');
  await expect(page!.getByTestId('password.new')).toBeVisible();
  const first=savedToken(); const restricted=await api('GET','/v1/admin/users',undefined,first);
  record(1,'Login as preset administrator before mandatory password change','service',
    {identity:true,role:'管理员',forced:true,adminVisible:false,adminStatus:403},
    {identity:await uiName('test-admin'),role:(await page!.getByTestId('session.role').textContent())?.trim(),
     forced:await page!.getByTestId('password.new').isVisible(),
     adminVisible:await page!.getByTestId('admin.accounts').isVisible(),adminStatus:restricted.status});
  await changePassword('TEST-ONLY-admin-42!','TEST-ONLY-Admin-New-42!');
  await expect(page!.getByTestId('admin.accounts')).toBeVisible();
  await expect.poll(()=>savedToken()!==first).toBeTruthy();
  const newToken=savedToken(); const oldMe=await api('GET','/v1/me',undefined,first);
  const allowed=await api('GET','/v1/admin/users',undefined,newToken);
  record(2,'Complete required change and verify management access','service',
    {oldStatus:401,newStatus:200,mustChange:false,adminVisible:true},
    {oldStatus:oldMe.status,newStatus:allowed.status,mustChange:user('test-admin')?.must_change_password===1,
     adminVisible:await page!.getByTestId('admin.accounts').isVisible()});
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await login('test-admin','TEST-ONLY-Admin-New-42!'); await page!.getByTestId('admin.accounts').click();
  await expect(page!.getByTestId('admin.state.test-disabled')).toBeVisible();
  record(3,'Login again and load all four seed accounts','ui',
    {identity:true,users:4,forced:false},
    {identity:await uiName('test-admin'),users:await page!.locator('[data-testid^="admin.state."]').count(),
     forced:(await page!.getByText('首次登录，请更改密码').count())>0});
});

test('TC-TM001-LOGIN-12', async () => {
  await prepareChangedAlice(); await startAfterPreparation();
  await login('test-alice','TEST-ONLY-Changed-42!'); await uiName('test-alice');
  const token=savedToken();
  const me=await api('GET','/v1/me',undefined,token);
  record(1,'Inspect member identity and available controls','ui',
    {identity:true,role:'成员',meStatus:200,meRole:'member',adminVisible:false},
    {identity:await uiName('test-alice'),role:(await page!.getByTestId('session.role').textContent())?.trim(),
     meStatus:me.status,meRole:me.body.role,adminVisible:await page!.getByTestId('admin.accounts').isVisible()});
  const list=await api('GET','/v1/admin/users',undefined,token);
  const audit=await api('GET','/v1/admin/audit',undefined,token);
  const disable=await api('POST','/v1/admin/users/00000000-0000-4000-8000-000000000003/disable',undefined,token);
  record(2,'Deny three real administrator API operations with member token','service',
    {list:403,audit:403,disable:403,bobActive:true},
    {list:list.status,audit:audit.status,disable:disable.status,bobActive:user('test-bob')?.is_active===1});
  const injected=await api('POST','/v1/auth/login',
    {username:'test-alice',password:'TEST-ONLY-Changed-42!',role:'admin'});
  record(3,'Ignore or reject role injection in a genuine login request','service',
    {safe:true,dbRole:'member'},
    {safe:injected.status>=400 || injected.body.user?.role==='member',dbRole:user('test-alice')?.role});
});

test('TC-TM001-LOGIN-13', async () => {
  await start(); await controlTransport('offline','/v1/auth/login');
  await login('test-alice','TEST-ONLY-alice-42!');
  const failed=await uiError('network_unavailable');
  const first=(await transportRequests()).filter(item=>item.route==='/v1/auth/login' && !item.probe);
  record(1,'Disconnect the owned login transport before forwarding','service',
    {error:true,loginVisible:true,offlineUnforwarded:true,sessions:0,users:4},
    {error:failed,loginVisible:await page!.getByTestId('auth.login').isVisible(),
     offlineUnforwarded:first.length===1&&first[0]?.mode==='offline'&&first[0]?.forwarded===false,
     sessions:sessions(),users:users()});
  await controlTransport('normal','/v1/auth/login');
  await login('test-alice','TEST-ONLY-alice-42!');
  const second=(await transportRequests()).filter(item=>item.route==='/v1/auth/login' && !item.probe);
  record(2,'Restore owned transport and authenticate against the real backend','service',
    {identity:true,forced:true,normalForwarded:true,sessions:1},
    {identity:await uiName('test-alice'),forced:await page!.getByTestId('password.new').isVisible(),
     normalForwarded:second.length===2&&second[1]?.mode==='normal'&&second[1]?.forwarded===true,
     sessions:sessions()});
});

test('TC-TM001-LOGIN-14', async () => {
  await start(); await controlTransport('unavailable','/v1/auth/login');
  await login('test-alice','TEST-ONLY-alice-42!');
  await expect(page!.getByTestId('auth.error')).toBeVisible();
  const errorText=(await page!.getByTestId('auth.error').textContent()??'').trim();
  const first=(await transportRequests()).filter(item=>item.route==='/v1/auth/login' && !item.probe);
  record(1,'Return controlled 503 without forwarding authentication','service',
    {failureVisible:true,noStack:true,unforwarded503:true,sessions:0},
    {failureVisible:errorText.length>0&&await page!.getByTestId('auth.login').isVisible(),
     noStack:!/Traceback|Exception|at\s+\S+\s*\(/i.test(errorText),
     unforwarded503:first.length===1&&first[0]?.status===503&&first[0]?.forwarded===false,
     sessions:sessions()});
  await controlTransport('normal','/v1/auth/login');
  await login('test-alice','TEST-ONLY-alice-42!');
  const second=(await transportRequests()).filter(item=>item.route==='/v1/auth/login' && !item.probe);
  record(2,'Resume genuine backend forwarding and confirm login','service',
    {identity:true,forced:true,forwarded:true,sessions:1},
    {identity:await uiName('test-alice'),forced:await page!.getByTestId('password.new').isVisible(),
     forwarded:second.length===2&&second[1]?.mode==='normal'&&second[1]?.forwarded===true,
     sessions:sessions()});
});

test('TC-TM001-LOGIN-15', async () => {
  await start(); await controlTransport('delay','/v1/auth/login');
  const started=Date.now(); await login('test-alice','TEST-ONLY-alice-42!');
  const timeout=await uiError('network_unavailable');
  const elapsed=Date.now()-started;
  const first=(await transportRequests()).filter(item=>item.route==='/v1/auth/login' && !item.probe);
  record(1,'Hold authentication past the approved fifteen-second timeout','service',
    {timeout:true,withinTolerance:true,loginVisible:true,unforwarded:true,sessions:0},
    {timeout,withinTolerance:elapsed>=14_000&&elapsed<=20_000,
     loginVisible:await page!.getByTestId('auth.login').isVisible(),
     unforwarded:first.length===1&&first[0]?.mode==='delay'&&first[0]?.forwarded===false,
     sessions:sessions()});
  await controlTransport('normal','/v1/auth/login',false);
  await login('test-bob','TEST-ONLY-bob-42!');
  await uiName('test-bob');
  const current=savedToken();
  const beforeMe=await api('GET','/v1/me',undefined,current);
  await releaseDelayedTransport();
  const deadline=Date.now()+10_000;
  let late:TransportRequest|undefined;
  while (Date.now()<deadline) {
    late=(await transportRequests()).find(item=>item.route==='/v1/auth/login'&&item.mode==='delay'&&!item.probe);
    if (late?.finished_at) break;
    await new Promise(resolve=>setTimeout(resolve,200));
  }
  await new Promise(resolve=>setTimeout(resolve,500));
  const afterMe=await api('GET','/v1/me',undefined,savedToken());
  const second=(await transportRequests()).filter(item=>item.route==='/v1/auth/login'&&!item.probe);
  record(2,'Authenticate Bob, release the older Alice response, and keep Bob as the verified App identity','service',
    {identity:true,beforeMe:200,afterMe:200,bobBefore:true,bobAfter:true,
     newForwarded:true,lateFinished:true,tokenStable:true},
    {identity:await uiName('test-bob'),beforeMe:beforeMe.status,afterMe:afterMe.status,
     bobBefore:beforeMe.body.id==='00000000-0000-4000-8000-000000000003',
     bobAfter:afterMe.body.id==='00000000-0000-4000-8000-000000000003',
     newForwarded:second.length>=2&&second.some(item=>item.mode==='normal'&&item.forwarded),
     lateFinished:!!late?.finished_at&&late.forwarded===true&&[0,200].includes(late.status??-1),
     tokenStable:savedToken()===current});
});

test('TC-TM001-LOGIN-16', async () => {
  if(!c.clock_path || !Number.isInteger(c.clock_start)) throw Error('Owned service clock fixture is missing');
  await start();
  let invalid=0;
  for (let attempt=0;attempt<5;attempt++) {
    await login('test-alice','TEST-ONLY-Wrong-42!');
    if (await uiError('invalid_credentials')) invalid++;
  }
  await login('test-alice','TEST-ONLY-Wrong-42!');
  const limited=await uiError('rate_limited');
  const limitedApi=await api('POST','/v1/auth/login',
    {username:'test-alice',password:'TEST-ONLY-Wrong-42!'});
  record(1,'Submit five wrong passwords and observe the next request being rate-limited','ui',
    {invalid:5,limited:true,apiStatus:429,sessions:0},
    {invalid,limited,apiStatus:limitedApi.status,sessions:sessions()});
  await login('test-alice','TEST-ONLY-alice-42!');
  const aliceLimited=await uiError('rate_limited');
  await login('test-bob','TEST-ONLY-bob-42!');
  const bobLimited=await uiError('rate_limited');
  const aliceApi=await api('POST','/v1/auth/login',
    {username:'test-alice',password:'TEST-ONLY-alice-42!'});
  const bobApi=await api('POST','/v1/auth/login',
    {username:'test-bob',password:'TEST-ONLY-bob-42!'});
  record(2,'Reject correct passwords for both the limited account and the shared source','ui',
    {aliceLimited:true,bobLimited:true,aliceApi:429,bobApi:429,sessions:0},
    {aliceLimited,bobLimited,aliceApi:aliceApi.status,bobApi:bobApi.status,sessions:sessions()});
  writeFileSync(c.clock_path,String(c.clock_start!+299),{mode:0o600});
  await login('test-alice','TEST-ONLY-alice-42!');
  const limitedAt299=await uiError('rate_limited');
  writeFileSync(c.clock_path,String(c.clock_start!+300),{mode:0o600});
  await login('test-alice','TEST-ONLY-alice-42!');
  record(3,'Advance the owned service clock: reject at 299s, allow at 300s, with no counter edits','service',
    {limitedAt299:true,serviceElapsedSeconds:300,identity:true,forced:true,sessions:1},
    {limitedAt299,serviceElapsedSeconds:Number(readFileSync(c.clock_path,'utf8'))-c.clock_start!,
     identity:await uiName('test-alice'),forced:await page!.getByTestId('password.new').isVisible(),
     sessions:sessions()});
});

for (const [id,input] of [
  ['TC-TM001-LOGIN-19#A','a_1'],
  ['TC-TM001-LOGIN-19#B','a'.repeat(64)],
  ['TC-TM001-LOGIN-19#C','test_A-42'],
] as const) {
  test(id, async () => {
    await startBounds();
    const seeded=boundaryUser();
    await fillLogin(input,'TEST-ONLY-Boundary-42!');
    record(1,'Verify generated boundary account and enter the complete username','database',
      {input,accountId:BOUNDARY_ID,storedUsername:input.toLowerCase(),length:input.length,
       role:'member',active:true,mustChange:true,users:5,sessions:0},
      {input:await page!.getByTestId('auth.username').inputValue(),accountId:seeded?.id,
       storedUsername:seeded?.username,length:(await page!.getByTestId('auth.username').inputValue()).length,
       role:seeded?.role,active:seeded?.is_active===1,mustChange:seeded?.must_change_password===1,
       users:users(),sessions:sessions()});
    await page!.getByTestId('auth.login').click();
    await expect(page!.getByTestId('session.verified')).toBeVisible();
    await expect(page!.getByTestId('password.new')).toBeVisible();
    await page!.getByTestId('session.refresh').click();
    const me=await api('GET','/v1/me',undefined,savedToken());
    record(2,'Authenticate the exact seeded boundary account and refresh its identity','service',
      {me:200,id:BOUNDARY_ID,role:'member',mustChange:true,forced:true,sessions:1,users:5},
      {me:me.status,id:me.body.id,role:me.body.role,mustChange:me.body.must_change_password,
       forced:await page!.getByTestId('password.new').isVisible(),sessions:sessions(),users:users()});
  });
}

const PASSWORD_128='A'.repeat(127)+'!';
test('TC-TM001-LOGIN-20', async () => {
  await prepareChangedAlice(PASSWORD_128); await startAfterPreparation();
  await login('test-alice',PASSWORD_128);
  record(1,'Login with the full 128-character password prepared by real change','ui',
    {identity:true,role:'成员',forced:false},
    {identity:await uiName('test-alice'),role:(await page!.getByTestId('session.role').textContent())?.trim(),
     forced:(await page!.getByText('首次登录，请更改密码').count())>0});
  await page!.getByTestId('session.refresh').click();
  const me=await api('GET','/v1/me',undefined,savedToken());
  record(2,'Refresh authenticated identity for 128-character password','service',
    {me:200,name:'test-alice',role:'member'},
    {me:me.status,name:me.body.username,role:me.body.role});
});

test('TC-TM001-LOGIN-21', async () => {
  await prepareChangedAlice(PASSWORD_128); await startAfterPreparation();
  await login('test-alice',PASSWORD_128+'X');
  record(1,'Reject a 129-character login password whose first 128 characters are valid','ui',
    {loginVisible:true,sessionCount:0,unchanged:true},
    {loginVisible:await page!.getByTestId('auth.login').isVisible(),sessionCount:sessions(),
     unchanged:user('test-alice')?.must_change_password===0});
  const direct=await api('POST','/v1/auth/login',{username:'test-alice',password:PASSWORD_128+'X'});
  record(2,'Reject the complete 129-character value at the real API','service',
    {rejected:true,sessionCount:0},
    {rejected:direct.status>=400&&direct.status<500,sessionCount:sessions()});
});

for (const [id,name] of [
  ['TC-TM001-LOGIN-17#A','ab'],
  ['TC-TM001-LOGIN-17#B','a'.repeat(65)],
  ['TC-TM001-LOGIN-18#A','测试用户'],
  ['TC-TM001-LOGIN-18#B','test.alice'],
  ['TC-TM001-LOGIN-18#C','test alice'],
  ['TC-TM001-LOGIN-18#D',"test'alice"],
] as const) {
  test(id, async () => {
    await start(); await login(name,'TEST-ONLY-alice-42!');
    record(1,'Submit this exact invalid username through App','ui',
      {loginVisible:true,sessions:0,users:4,unchanged:true},
      {loginVisible:await page!.getByTestId('auth.login').isVisible(),sessions:sessions(),
       users:users(),unchanged:user('test-alice')?.must_change_password===1});
    const direct=await api('POST','/v1/auth/login',
      {username:name,password:'TEST-ONLY-alice-42!'});
    record(2,'Submit the complete invalid username to the real API','service',
      {rejected:true,sessions:0,users:4},
      {rejected:direct.status>=400&&direct.status<500,sessions:sessions(),users:users()});
  });
}

for (const [id,input,accepted] of [
  ['TC-TM001-LOGIN-22#A','TEST-ALICE',true],
  ['TC-TM001-LOGIN-22#B',' test-alice',false],
  ['TC-TM001-LOGIN-22#C','test-alice ',false],
] as const) {
  test(id, async () => {
    await start(); await login(input,'TEST-ONLY-alice-42!');
    if (accepted) {
      record(1,'Submit case-varied username and verify the original account identity','ui',
        {identity:true,id:'00000000-0000-4000-8000-000000000002',role:'成员',users:4,sessions:1},
        {identity:await uiName('test-alice'),id:user('test-alice')?.id,
         role:(await page!.getByTestId('session.role').textContent())?.trim(),users:users(),sessions:sessions()});
    } else {
      record(1,'Submit username containing ASCII space and ensure no identity is granted','ui',
        {loginVisible:true,users:4,sessions:0},
        {loginVisible:await page!.getByTestId('auth.login').isVisible(),users:users(),sessions:sessions()});
    }
    const direct=await api('POST','/v1/auth/login',
      {username:input,password:'TEST-ONLY-alice-42!'});
    record(2,'Compare App result to the real service username matching rule','service',
      accepted ? {status:200,id:'00000000-0000-4000-8000-000000000002',users:4,role:'member'}
               : {rejected:true,users:4,sessions:0},
      accepted ? {status:direct.status,id:direct.body.user?.id,users:users(),role:direct.body.user?.role}
               : {rejected:direct.status>=400&&direct.status<500,users:users(),sessions:sessions()});
  });
}

test('TC-TM001-PASSWORD-01', async () => {
  await firstAlice(); const original=savedToken();
  await fillPassword('TEST-ONLY-Wrong-42!','TEST-ONLY-Changed-42!');
  await page!.getByTestId('password.submit').click();
  record(1,'Submit wrong current password in required change form','ui',
    {error:true,forced:true,mustChange:true,changedAudit:0},
    {error:await uiError('invalid_credentials'),forced:await page!.getByTestId('password.new').isVisible(),
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
  const status=await oldAndNewStatus('TEST-ONLY-Changed-42!');
  const prior=await api('GET','/v1/me',undefined,original);
  record(2,'Check old password and session survive, new password fails','service',
    {old:200,next:401,oldSession:200,changedAudit:0},
    {old:status.old,next:status.next,oldSession:prior.status,changedAudit:changedAudits()});
});

test('TC-TM001-PASSWORD-02', async () => {
  await firstAlice(); await fillPassword('TEST-ONLY-alice-42!','TEST-ONLY-Changed-42!','TEST-ONLY-Changed-43!');
  await page!.getByTestId('password.submit').click();
  record(1,'Submit different new password and confirmation values','ui',
    {error:true,forced:true,mustChange:true,changedAudit:0},
    {error:await uiError('password_confirmation_mismatch'),forced:await page!.getByTestId('password.new').isVisible(),
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
  const status=await oldAndNewStatus('TEST-ONLY-Changed-42!');
  record(2,'Verify old password remains active and candidate remains invalid','service',
    {old:200,next:401,changedAudit:0},
    {old:status.old,next:status.next,changedAudit:changedAudits()});
});

test('TC-TM001-PASSWORD-03', async () => {
  await firstAlice(); const token=savedToken(); const short='A'.repeat(10)+'!';
  await fillPassword('TEST-ONLY-alice-42!',short); await page!.getByTestId('password.confirm').press('Enter');
  record(1,'Reject eleven-character new password in App form','ui',
    {buttonDisabled:true,forced:true,mustChange:true,changedAudit:0},
    {buttonDisabled:await page!.getByTestId('password.submit').isDisabled(),
     forced:await page!.getByTestId('password.new').isVisible(),
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
  const direct=await api('POST','/v1/auth/change-password',
    {current_password:'TEST-ONLY-alice-42!',new_password:short},token);
  record(2,'Real API rejects eleven-character replacement independently of App validation','service',
    {rejected:true,mustChange:true,changedAudit:0},
    {rejected:direct.status>=400&&direct.status<500,
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
});

test('TC-TM001-PASSWORD-04', async () => {
  await firstAlice(); await fillPassword('TEST-ONLY-alice-42!','TEST-ONLY-alice-42!');
  await page!.getByTestId('password.submit').click();
  record(1,'Submit unchanged password through App','ui',
    {error:true,forced:true,mustChange:true},
    {error:await uiError('password_unchanged'),forced:await page!.getByTestId('password.new').isVisible(),
     mustChange:user('test-alice')?.must_change_password===1});
  const old=await api('POST','/v1/auth/login',
    {username:'test-alice',password:'TEST-ONLY-alice-42!'});
  const blocked=await api('GET','/v1/admin/users',undefined,savedToken());
  record(2,'Confirm current credential and mandatory scope persist without success audit','service',
    {old:200,admin:403,changedAudit:0},
    {old:old.status,admin:blocked.status,changedAudit:changedAudits()});
});

test('TC-TM001-PASSWORD-05', async () => {
  await firstAlice(); const first=savedToken();
  if (!c.peer_app_path || !c.peer_profile_path) throw Error('Owned independent peer App and profile are required');
  const secondProfile=c.peer_profile_path;
  const secondBinary=join(c.peer_app_path,'Contents/MacOS/TokenMeter');
  const secondApp=await electron.launch({executablePath:secondBinary,
    args:[`--user-data-dir=${secondProfile}`],env:childEnvironment(),chromiumSandbox:true,timeout:60_000});
  extraApps.push(secondApp);
  const secondPage=await secondApp.firstWindow();
  await expect(secondPage.getByTestId('app.build')).toBeVisible();
  await secondApp.context().tracing.start({screenshots:true,snapshots:true,sources:false});
  await configurePage(secondPage);
  await secondPage.getByTestId('auth.username').fill('test-alice');
  await secondPage.getByTestId('auth.password').fill('TEST-ONLY-alice-42!');
  await secondPage.getByTestId('auth.login').click();
  await expect(secondPage.getByTestId('password.new')).toBeVisible();
  const secondPath=join(secondProfile,'credentials',createHash('sha256').update(c.service_url).digest('hex')+'.token');
  const second=readFileSync(secondPath,'utf8');
  expect(second).toMatch(/^[A-Za-z0-9_-]{43}$/);
  await changePassword('TEST-ONLY-alice-42!','TEST-ONLY-Changed-42!');
  record(1,'Change password in first App while a second App holds another old session','ui',
    {identity:true,mustChange:false,role:'成员',sessions:1},
    {identity:await uiName('test-alice'),mustChange:user('test-alice')?.must_change_password===1,
     role:(await page!.getByTestId('session.role').textContent())?.trim(),sessions:sessions()});
  const firstMe=await api('GET','/v1/me',undefined,first);
  const secondMe=await api('GET','/v1/me',undefined,second);
  const newMe=await api('GET','/v1/me',undefined,savedToken());
  await page!.getByTestId('session.refresh').click();
  record(2,'Check both old sessions are revoked and App keeps the new identity','service',
    {old1:401,old2:401,newSession:200,identity:true},
    {old1:firstMe.status,old2:secondMe.status,newSession:newMe.status,identity:await uiName('test-alice')});
  const oldLogin=await api('POST','/v1/auth/login',
    {username:'test-alice',password:'TEST-ONLY-alice-42!'});
  const newLogin=await api('POST','/v1/auth/login',
    {username:'test-alice',password:'TEST-ONLY-Changed-42!'});
  record(3,'Compare old and new passwords and the success audit','service',
    {old:401,new:200,changedAudit:1,role:'member'},
    {old:oldLogin.status,new:newLogin.status,changedAudit:changedAudits(),role:user('test-alice')?.role});
  await secondApp.context().tracing.stop({path:join(output!,'trace-second-before-restart.zip')});
  await secondApp.close(); extraApps.splice(extraApps.indexOf(secondApp),1);
  const restarted=await electron.launch({executablePath:secondBinary,
    args:[`--user-data-dir=${secondProfile}`],env:childEnvironment(),chromiumSandbox:true,timeout:60_000});
  extraApps.push(restarted);
  const restartedPage=await restarted.firstWindow();
  await restarted.context().tracing.start({screenshots:true,snapshots:true,sources:false});
  try {
    await expect(restartedPage.getByTestId('auth.login')).toBeVisible();
    await restartedPage.screenshot({path:join(output!,'second-profile-after-restart.png')});
    record(4,'Restart second App and reject its persisted old token','ui',
      {loginVisible:true,savedCredential:false,oldSession:401},
      {loginVisible:await restartedPage.getByTestId('auth.login').isVisible(),
       savedCredential:existsSync(secondPath),oldSession:(await api('GET','/v1/me',undefined,second)).status});
  } finally {
    await restarted.context().tracing.stop({path:join(output!,'trace-second-after-restart.zip')});
  }
});

test('TC-TM001-PASSWORD-06', async () => {
  await firstAlice(); const next='A'.repeat(11)+'!'; const old=savedToken();
  await changePassword('TEST-ONLY-alice-42!',next);
  const oldMe=await api('GET','/v1/me',undefined,old);
  record(1,'Submit minimum valid twelve-character replacement','service',
    {identity:true,oldRevoked:401,mustChange:false,changedAudit:1},
    {identity:await uiName('test-alice'),oldRevoked:oldMe.status,
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible(); await login('test-alice',next);
  record(2,'Reauthenticate with the complete twelve-character password','ui',
    {identity:true,role:'成员',forced:false},
    {identity:await uiName('test-alice'),role:(await page!.getByTestId('session.role').textContent())?.trim(),
     forced:(await page!.getByText('首次登录，请更改密码').count())>0});
});

test('TC-TM001-PASSWORD-07', async () => {
  await firstAlice(); const old=savedToken();
  await changePassword('TEST-ONLY-alice-42!',PASSWORD_128);
  const oldMe=await api('GET','/v1/me',undefined,old);
  record(1,'Submit maximum valid 128-character replacement','service',
    {identity:true,oldRevoked:401,mustChange:false,changedAudit:1},
    {identity:await uiName('test-alice'),oldRevoked:oldMe.status,
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await login('test-alice',PASSWORD_128.slice(0,127));
  const prefixError=await uiError('invalid_credentials');
  await login('test-alice',PASSWORD_128);
  record(2,'Reject 127-character prefix and accept full 128-character value','ui',
    {prefixError:true,identity:true,changedAudit:1},
    {prefixError,identity:await uiName('test-alice'),changedAudit:changedAudits()});
});

test('TC-TM001-PASSWORD-08', async () => {
  await firstAlice(); const token=savedToken(); const over='A'.repeat(128)+'!';
  await fillPassword('TEST-ONLY-alice-42!',over);
  await page!.getByTestId('password.confirm').press('Enter');
  record(1,'Attempt 129-character replacement through App without truncation','ui',
    {forced:true,mustChange:true,changedAudit:0},
    {forced:await page!.getByTestId('password.new').isVisible(),
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
  const direct=await api('POST','/v1/auth/change-password',
    {current_password:'TEST-ONLY-alice-42!',new_password:over},token);
  const old=await api('POST','/v1/auth/login',
    {username:'test-alice',password:'TEST-ONLY-alice-42!'});
  record(2,'Reject 129-character replacement at real service and retain original','service',
    {rejected:true,old:200,mustChange:true,changedAudit:0},
    {rejected:direct.status>=400&&direct.status<500,old:old.status,
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
});

for (const [id,current,next,confirmation] of [
  ['TC-TM001-PASSWORD-09#A','','TEST-ONLY-Changed-42!','TEST-ONLY-Changed-42!'],
  ['TC-TM001-PASSWORD-09#B','TEST-ONLY-alice-42!','',''],
  ['TC-TM001-PASSWORD-09#C','TEST-ONLY-alice-42!','TEST-ONLY-Changed-42!',''],
  ['TC-TM001-PASSWORD-09#D','','',''],
] as const) {
  test(id, async () => {
    await firstAlice(); const original=savedToken();
    await fillPassword(current,next,confirmation);
    await page!.getByTestId('password.confirm').press('Enter');
    record(1,'Attempt password change with this required-field variant','ui',
      {buttonDisabled:true,forced:true,mustChange:true,changedAudit:0},
      {buttonDisabled:await page!.getByTestId('password.submit').isDisabled(),
       forced:await page!.getByTestId('password.new').isVisible(),
       mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
    let directStatus: number | null=null;
    if (!id.endsWith('#C')) {
      const direct=await api('POST','/v1/auth/change-password',
        {current_password:current,new_password:next},original);
      directStatus=direct.status;
    }
    const me=await api('GET','/v1/me',undefined,original);
    record(2,'Confirm no change; direct API rejects missing actual fields where applicable','service',
      {directRejected:id.endsWith('#C')?null:true,session:200,changedAudit:0,mustChange:true},
      {directRejected:directStatus===null?null:directStatus>=400&&directStatus<500,
       session:me.status,changedAudit:changedAudits(),mustChange:user('test-alice')?.must_change_password===1});
  });
}

test('TC-TM001-PASSWORD-10', async () => {
  await firstAlice(); const old=savedToken();
  const sessionsBefore=sessions();
  await controlTransport('offline','/v1/auth/change-password');
  await fillPassword('TEST-ONLY-alice-42!','TEST-ONLY-Changed-42!');
  await page!.getByTestId('password.submit').click();
  const failed=await uiError('network_unavailable');
  const first=(await transportRequests()).filter(item=>item.route==='/v1/auth/change-password'&&!item.probe);
  record(1,'Disconnect the owned change-password transport before the real backend receives it','service',
    {error:true,forced:true,unforwarded:true,mustChange:true,sessions:sessionsBefore,changedAudit:0},
    {error:failed,forced:await page!.getByTestId('password.new').isVisible(),
     unforwarded:first.length===1&&first[0]?.mode==='offline'&&first[0]?.forwarded===false,
     mustChange:user('test-alice')?.must_change_password===1,sessions:sessions(),changedAudit:changedAudits()});
  await controlTransport('normal','/v1/auth/change-password');
  await fillPassword('TEST-ONLY-alice-42!','TEST-ONLY-Changed-42!');
  await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('password.status')).toBeVisible();
  const oldMe=await api('GET','/v1/me',undefined,old);
  const second=(await transportRequests()).filter(item=>item.route==='/v1/auth/change-password'&&!item.probe);
  record(2,'Restore backend forwarding; only the confirmed retry updates the password','service',
    {identity:true,oldRevoked:401,forwarded:true,mustChange:false,changedAudit:1},
    {identity:await uiName('test-alice'),oldRevoked:oldMe.status,
     forwarded:second.length===2&&second[1]?.mode==='normal'&&second[1]?.forwarded===true,
     mustChange:user('test-alice')?.must_change_password===1,changedAudit:changedAudits()});
});

for (const [id,current,valid] of [
  ['TC-TM001-PASSWORD-11#A',PASSWORD_128,true],
  ['TC-TM001-PASSWORD-11#B',PASSWORD_128+'X',false],
] as const) {
  test(id, async () => {
    await prepareChangedAlice(PASSWORD_128); await startAfterPreparation();
    await login('test-alice',PASSWORD_128);
    await expect(page!.getByTestId('password.toggle')).toBeVisible();
    const old=savedToken();
    await page!.getByTestId('password.toggle').click();
    await fillPassword(current,'TEST-ONLY-Second-New-42!');
    await page!.getByTestId('password.submit').click();
    if (valid) await expect(page!.getByTestId('password.status')).toBeVisible();
    const oldMe=await api('GET','/v1/me',undefined,old);
    record(1,'Attempt password change using this exact current-password boundary','ui',
      {success:valid,oldSession:valid?401:200,changedAudit:valid?2:1,role:'member'},
      {success:await page!.getByTestId('password.status').isVisible(),oldSession:oldMe.status,
       changedAudit:changedAudits(),role:user('test-alice')?.role});
    if (valid) {
      const before=await api('POST','/v1/auth/login',{username:'test-alice',password:PASSWORD_128});
      const after=await api('POST','/v1/auth/login',
        {username:'test-alice',password:'TEST-ONLY-Second-New-42!'});
      record(2,'A branch: verify old 128-character password revoked and new password accepted','service',
        {old:401,new:200}, {old:before.status,new:after.status});
    } else {
      const rejected=await api('POST','/v1/auth/change-password',
        {current_password:PASSWORD_128+'X',new_password:'TEST-ONLY-Second-New-42!'},old);
      const preserved=await api('POST','/v1/auth/login',
        {username:'test-alice',password:PASSWORD_128});
      record(2,'B branch: direct API rejects the full 129-character current password','service',
        {rejected:true,oldPassword:200,changedAudit:1},
        {rejected:rejected.status>=400&&rejected.status<500,
         oldPassword:preserved.status,changedAudit:changedAudits()});
    }
  });
}
