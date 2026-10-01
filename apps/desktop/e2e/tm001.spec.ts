import { test, expect, _electron as electron, chromium, type ElectronApplication, type Page, type Browser } from '@playwright/test';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, lstatSync, readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { parseLsofPaths } from './lsof';

type Context = {
  run_id: string; candidate_sha: string; case_id: string; app_path: string; profile_path: string;
  service_url: string; secondary_service_url: string | null; update_url: string | null;
  update_control_url: string | null; update_control_token: string | null; update_nonce: string | null;
  cdp_port: number | null; expected_app_version: string; expected_app_build: string;
  expected_upgrade_version: string; expected_upgrade_build: string; expected_app_tree_sha256: string;
  expected_update_tree_sha256: string;
};
const input = process.env.TM_E2E_CONTEXT;
const output = process.env.TM_E2E_CASE_OUTPUT;
if (!input || !output) throw new Error('Owned case context is missing');
const c = JSON.parse(readFileSync(input, 'utf8')) as Context;
for (const key of ['expected_app_version', 'expected_app_build', 'expected_upgrade_version', 'expected_upgrade_build'] as const) {
  if (typeof c[key] !== 'string' || !c[key]) throw new Error(`Owned case context lacks ${key}`);
}
const binary = join(c.app_path, 'Contents/MacOS/TokenMeter');
const events = join(output, 'events.jsonl');
let application: ElectronApplication | null = null;
let page: Page | null = null;
let reconnected: Browser | null = null;
let tracing = false;
let traceSequence = 0;
let runnerLaunchCount = 0;
function nextTrace(): string { return join(output!, `trace-${String(++traceSequence).padStart(2,'0')}.zip`); }

function event(step: string, source: 'ui' | 'service' | 'filesystem' | 'process', expected: unknown, actual: unknown, testid?: string): void {
  const record = { run_id: c.run_id, case_id: c.case_id, timestamp: new Date().toISOString(), step,
    source, testid: testid ?? null, expected, actual, passed: JSON.stringify(expected) === JSON.stringify(actual) };
  appendFileSync(events, JSON.stringify(record) + '\n', { mode: 0o600 });
  expect(actual, `${step} ${testid ?? ''}`).toEqual(expected);
}
async function uiText(id: string): Promise<string> { return (await page!.getByTestId(id).textContent())?.trim() ?? ''; }
async function uiValue(id: string): Promise<string> { return page!.getByTestId(id).inputValue(); }
async function visible(id: string): Promise<boolean> { return page!.getByTestId(id).isVisible(); }
async function uiEquals(step: string, id: string, expected: string): Promise<void> {
  await expect(page!.getByTestId(id)).toHaveText(expected);
  event(step, 'ui', expected, await uiText(id), id);
}
async function capture(name: string): Promise<void> {
  await page!.screenshot({ path: join(output!, name + '.png') });
}
function childEnvironment(): Record<string,string> {
  return Object.fromEntries(Object.entries(process.env).filter(([key,value]) => value !== undefined &&
    !key.startsWith('TM_E2E_') && !key.startsWith('TM_INTERNAL_') && !key.includes('SIGNING') && !key.includes('TOKEN'))) as Record<string,string>;
}
async function launch(): Promise<void> {
  if (!existsSync(binary)) throw new Error('Installed final-DMG executable is missing');
  application = await electron.launch({ executablePath: binary,
    args: [`--user-data-dir=${c.profile_path}`, ...(c.cdp_port ? [`--diagnostic-cdp-port=${c.cdp_port}`] : [])],
    env: childEnvironment(), chromiumSandbox: true, timeout: 60_000 });
  runnerLaunchCount += 1;
  event('runner_launch', 'process', runnerLaunchCount, runnerLaunchCount);
  page = await application.firstWindow();
  await expect(page.getByTestId('app.build')).toContainText(`build ${c.expected_app_build}`);
  expect(bundleVersion()).toEqual({version:c.expected_app_version,build:c.expected_app_build});
  await application.context().tracing.start({ screenshots: true, snapshots: true, sources: false });
  tracing = true;
}
function bundleVersion(): {version:string;build:string} {
  const plist=join(c.app_path,'Contents/Info.plist');
  return {version:execFileSync('/usr/bin/plutil',['-extract','CFBundleShortVersionString','raw',plist],{encoding:'utf8'}).trim(),
    build:execFileSync('/usr/bin/plutil',['-extract','CFBundleVersion','raw',plist],{encoding:'utf8'}).trim()};
}
async function close(): Promise<void> {
  if (application) {
    if (tracing) {
      await application.context().tracing.stop({ path: nextTrace() });
      tracing = false;
    }
    await application.close();
    application = null; page = null;
  }
}
async function ensureTraceBeforeNativeRestart(): Promise<void> {
  if (application && tracing) {
    await application.context().tracing.stop({ path: nextTrace() });
    tracing = false;
  }
}
async function defaults(step='default_routes'): Promise<void> {
  await expect(page!.getByTestId('auth.server')).toHaveValue('http://127.0.0.1:49176');
  const api = await uiValue('auth.server');
  await page!.getByTestId('configuration.open').click();
  const feed = await uiValue('configuration.update-url');
  event(step, 'ui', { api: 'http://127.0.0.1:49176', feed: 'http://127.0.0.1:49177/version.json' }, { api, feed }, 'configuration.api-url');
  await page!.getByTestId('configuration.cancel').click();
}
async function configure(api: string, feed?: string): Promise<void> {
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(api);
  if (feed !== undefined) await page!.getByTestId('configuration.update-url').fill(feed);
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('configuration.status')).toBeVisible();
  await expect(page!.getByTestId('auth.server')).toHaveValue(api);
}
async function login(username: string, password: string): Promise<void> {
  await page!.getByTestId('auth.username').fill(username);
  await page!.getByTestId('auth.password').fill(password);
  await page!.getByTestId('auth.login').click();
}
async function changePassword(current: string, next = 'TEST-ONLY-Changed-42!'): Promise<void> {
  await page!.getByTestId('password.current').fill(current);
  await page!.getByTestId('password.new').fill(next);
  await page!.getByTestId('password.confirm').fill(next);
  await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('password.status')).toBeVisible();
}
function credentialPath(origin = c.service_url): string {
  return join(c.profile_path, 'credentials', createHash('sha256').update(origin).digest('hex') + '.token');
}
function savedToken(origin = c.service_url): string {
  const dir = dirname(credentialPath(origin));
  const d = lstatSync(dir), f = lstatSync(credentialPath(origin));
  event('credential_directory_mode', 'filesystem', 0o700, d.mode & 0o777);
  event('credential_file_mode', 'filesystem', 0o600, f.mode & 0o777);
  event('credential_file_owner', 'filesystem', process.getuid!(), f.uid);
  const token = readFileSync(credentialPath(origin), 'utf8');
  event('credential_token_shape', 'filesystem', true, /^[A-Za-z0-9_-]{43}$/.test(token));
  return token;
}
async function request(base: string, method: string, route: string, body?: object, token?: string): Promise<{status: number; body: any}> {
  const response = await fetch(base + route, { method,
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : {} };
}
async function apiToken(username: string, password: string, base = c.service_url): Promise<string> {
  const response = await request(base, 'POST', '/v1/auth/login', { username, password });
  event('service_login', 'service', 200, response.status);
  const token = response.body.access_token;
  if (typeof token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(token)) throw new Error('Real service did not issue an opaque token');
  return token;
}
async function status(step: string, expected: number, base: string, method: string, route: string, body?: object, token?: string): Promise<any> {
  const response = await request(base, method, route, body, token);
  event(step, 'service', expected, response.status);
  return response.body;
}
async function identity(step: string, name: string): Promise<void> {
  await uiEquals(step, 'session.username', name);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
}
async function restart(): Promise<void> { await close(); await launch(); }
async function control(stage: string): Promise<void> {
  if (!c.update_control_url || !c.update_control_token) throw new Error('Owned update control missing');
  const response = await fetch(c.update_control_url + '/' + stage, { method: 'POST', headers: {Authorization: 'Bearer ' + c.update_control_token} });
  event('update_fixture_' + stage, 'service', 200, response.status);
}
async function updateObservations(): Promise<Array<{stage:string;route:string;status:number}>> {
  if (!c.update_url || !c.update_control_token) throw new Error('Owned update observations unavailable');
  const response = await fetch(new URL('/observations',c.update_url), {headers:{Authorization:'Bearer '+c.update_control_token}});
  if (response.status !== 200) throw new Error('Owned update observations refused');
  const body = await response.json() as {nonce:string;requests:Array<{stage:string;route:string;status:number}>};
  if (body.nonce !== c.update_nonce) throw new Error('Wrong update source nonce');
  return body.requests;
}
function ownedAppPids(): number[] {
  const lines = execFileSync('/bin/ps', ['-axo', 'pid=,command='], { encoding: 'utf8' }).split('\n');
  return lines.map(line => line.trim().match(/^(\d+)\s+(.*)$/)).filter((match): match is RegExpMatchArray => !!match && match[2]!.startsWith(binary)).map(match => Number(match[1]));
}
function openedFilePaths(pid: number): string[] {
  const output = execFileSync('/usr/sbin/lsof', ['-nP', '-p', String(pid), '-Fn'],
    { encoding: 'utf8', timeout: 10_000, maxBuffer: 4 * 1024 * 1024 });
  return parseLsofPaths(output);
}
async function waitForNewPid(oldPid: number): Promise<number> {
  const end = Date.now() + 180_000;
  while (Date.now() < end) {
    const found = ownedAppPids().filter(pid => pid !== oldPid);
    if (found.length === 1 && !ownedAppPids().includes(oldPid)) return found[0]!;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error('Native updater did not autonomously start one new App process');
}

test.afterEach(async () => {
  try { if (page && !page.isClosed()) await page.screenshot({ path: join(output!, 'final.png') }); } catch { /* failure still leaves raw Playwright result */ }
  try { await close(); } catch { /* runner will mark missing trace and clean owned process */ }
  try { await reconnected?.close(); } catch { /* runner owns process cleanup */ }
});

test('E2E-TM001-001 first password, automatic login and logout', async () => {
  const old = await apiToken('test-alice', 'TEST-ONLY-alice-42!');
  await launch(); await defaults(); await capture('TM001-001-01-login');
  event('auto_default', 'ui', true, await page!.getByTestId('auth.automatic-login').isChecked(), 'auth.automatic-login');
  await configure(c.service_url); await login('test-alice', 'TEST-ONLY-alice-42!');
  await expect(page!.getByTestId('password.new')).toBeVisible();
  event('forced_password', 'ui', false, await visible('admin.accounts'), 'admin.accounts');
  await changePassword('TEST-ONLY-alice-42!'); await identity('identity', 'test-alice');
  const current = savedToken(); await capture('TM001-001-02-authenticated-account');
  await status('old_session_revoked', 401, c.service_url, 'GET', '/v1/me', undefined, old);
  await status('old_password_revoked', 401, c.service_url, 'POST', '/v1/auth/login', {username:'test-alice',password:'TEST-ONLY-alice-42!'});
  await restart(); await identity('auto_restore', 'test-alice');
  await page!.getByTestId('session.refresh').click(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  await page!.getByTestId('session.logout').click(); await expect(page!.getByTestId('auth.login')).toBeVisible();
  event('logout_revokes', 'filesystem', false, existsSync(credentialPath()));
  await status('logout_token_revoked', 401, c.service_url, 'GET', '/v1/me', undefined, current);
  await restart(); await page!.getByTestId('auth.automatic-login').click();
  await expect(page!.getByTestId('auth.automatic-login')).not.toBeChecked();
  await login('test-alice', 'TEST-ONLY-Changed-42!'); await identity('auto_off', 'test-alice');
  event('auto_off_file', 'filesystem', false, existsSync(credentialPath()));
  await restart(); event('auto_off_restart', 'ui', true, await visible('auth.login'), 'auth.login');
  await page!.getByTestId('auth.automatic-login').click();
  await expect(page!.getByTestId('auth.automatic-login')).toBeChecked();
  await login('test-alice', 'TEST-ONLY-Changed-42!');
  await identity('auto_reenabled', 'test-alice'); savedToken();
});

test('E2E-TM001-002 invalid login, disabled account and member permissions', async () => {
  await launch(); await defaults(); await configure(c.service_url);
  await login('test-bob','TEST-ONLY-Wrong-42!');
  await expect(page!.getByTestId('auth.error')).toContainText('invalid_credentials');
  event('login_errors', 'ui', true, (await uiText('auth.error')).includes('invalid_credentials'), 'auth.error');
  await login('test-disabled','TEST-ONLY-disabled-42!');
  await expect(page!.getByTestId('auth.error')).toContainText('account_disabled');
  event('disabled_error', 'ui', true, (await uiText('auth.error')).includes('account_disabled'), 'auth.error');
  await login('test-bob','TEST-ONLY-bob-42!'); await changePassword('TEST-ONLY-bob-42!');
  await identity('member_identity', 'test-bob'); await uiEquals('member_role','session.role','成员');
  event('admin_hidden', 'ui', false, await visible('admin.accounts'), 'admin.accounts');
  const token = savedToken();
  await status('member_forbidden_users',403,c.service_url,'GET','/v1/admin/users',undefined,token);
  await status('member_forbidden_audit',403,c.service_url,'GET','/v1/admin/audit',undefined,token);
  await status('member_forbidden_manage',403,c.service_url,'POST','/v1/admin/users/00000000-0000-4000-8000-000000000002/disable',undefined,token);
  event('member_forbidden', 'service', 3, 3);
  await page!.getByTestId('session.refresh').click(); await identity('member_refreshed','test-bob');
  await capture('TM001-002-01-member-permissions');
});

test('E2E-TM001-003 administrator reset, audit and revoked sessions', async () => {
  const bobOld = await apiToken('test-bob','TEST-ONLY-bob-42!');
  await launch(); await defaults(); await configure(c.service_url);
  await login('test-admin','TEST-ONLY-admin-42!'); await changePassword('TEST-ONLY-admin-42!');
  await identity('admin_identity','test-admin');
  await restart();
  await identity('admin_restored_identity','test-admin');
  await uiEquals('admin_restored_role','session.role','管理员');
  const verifiedAdmin = await status('admin_session_verified',200,c.service_url,'GET','/v1/me',undefined,savedToken());
  event('admin_session_matches_ui','service',
    {username:'test-admin',role:'admin'},
    {username:verifiedAdmin.username,role:verifiedAdmin.role});
  await page!.getByTestId('admin.accounts').click();
  await expect(page!.getByTestId('admin.reset.test-bob')).toBeVisible();
  await page!.getByTestId('admin.reset.test-bob').click();
  await page!.getByTestId('admin.temporary-password').fill('TEST-ONLY-Reset-42!');
  await page!.getByTestId('admin.reset.confirm').click();
  await expect(page!.getByTestId('admin.status')).toContainText('password_reset');
  await status('reset_revokes',401,c.service_url,'GET','/v1/me',undefined,bobOld);
  await page!.getByTestId('admin.disable.test-bob').click();
  await expect(page!.getByTestId('admin.state.test-bob')).toContainText('已停用');
  await status('disable_login',403,c.service_url,'POST','/v1/auth/login',{username:'test-bob',password:'TEST-ONLY-Reset-42!'});
  await page!.getByTestId('admin.enable.test-bob').click();
  await expect(page!.getByTestId('admin.state.test-bob')).toContainText('已启用');
  event('admin_actions','ui','已启用',(await uiText('admin.state.test-bob')).split(' ')[0], 'admin.state.test-bob');
  await page!.getByTestId('admin.audit').click();
  for (const action of ['password_reset','account_disabled','account_enabled']) await expect(page!.getByTestId('audit.action.'+action).first()).toBeVisible();
  event('audit','ui',true,await visible('audit.action.password_reset'),'audit.action.password_reset');
  await capture('TM001-003-01-admin-audit');
  savedToken();
  const admin = await apiToken('test-admin','TEST-ONLY-Changed-42!');
  await page!.getByTestId('session.logout').click(); await expect(page!.getByTestId('auth.login')).toBeVisible();
  await login('test-bob','TEST-ONLY-Reset-42!'); await changePassword('TEST-ONLY-Reset-42!','TEST-ONLY-Bob-New-42!');
  await identity('bob_identity','test-bob'); const bob = savedToken();
  await status('external_reset',200,c.service_url,'POST','/v1/admin/users/00000000-0000-4000-8000-000000000003/reset-password',{temporary_password:'TEST-ONLY-Bob-Reset-Again-42!'},admin);
  await status('reset_revokes_again',401,c.service_url,'GET','/v1/me',undefined,bob);
  await restart(); await expect(page!.getByTestId('auth.login')).toBeVisible();
  event('reset_revokes_saved','ui',true,await visible('auth.login'),'auth.login');
  await login('test-bob','TEST-ONLY-Bob-Reset-Again-42!'); await changePassword('TEST-ONLY-Bob-Reset-Again-42!','TEST-ONLY-Bob-Third-42!');
  const newest = savedToken();
  await status('external_disable',200,c.service_url,'POST','/v1/admin/users/00000000-0000-4000-8000-000000000003/disable',undefined,admin);
  await status('disable_revokes',401,c.service_url,'GET','/v1/me',undefined,newest);
  await restart(); event('disable_revokes_saved','ui',true,await visible('auth.login'),'auth.login');
  await capture('TM001-003-02-revoked-automatic-login');
});

test('E2E-TM001-005 production bootstrap and restored database', async () => {
  const initial = await apiToken('admin','123456');
  await status('bootstrap_forced_api',403,c.service_url,'GET','/v1/admin/users',undefined,initial);
  await launch(); await defaults(); await configure(c.service_url);
  await login('admin','123456'); await expect(page!.getByTestId('password.new')).toBeVisible();
  event('bootstrap_forced','ui',false,await visible('admin.accounts'),'admin.accounts');
  await capture('TM001-005-01-first-login');
  await changePassword('123456','TEST-ONLY-Admin-New-42!');
  await identity('admin_identity','admin');
  await status('bootstrap_old_token',401,c.service_url,'GET','/v1/me',undefined,initial);
  await status('bootstrap_old_password',401,c.service_url,'POST','/v1/auth/login',{username:'admin',password:'123456'});
  await page!.getByTestId('admin.accounts').click();
  await expect(page!.getByTestId('admin.state.admin')).toBeVisible();
  const names = await page!.locator('[data-testid^="admin.state."]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-testid')?.slice('admin.state.'.length)));
  event('admin_only','ui',['admin'],names,'admin.accounts');
  await capture('TM001-005-02-admin-only');
  await restart(); await identity('password_persists','admin');
  await page!.getByTestId('session.logout').click(); await expect(page!.getByTestId('auth.login')).toBeVisible();
  await login('admin','TEST-ONLY-Admin-New-42!'); await identity('restore','admin');
  await capture('TM001-005-03-restored');
});

test('E2E-TM001-006 default and configurable endpoints isolate origins', async () => {
  if (!c.secondary_service_url) throw new Error('Second owned service missing');
  await launch(); await defaults(); await configure(c.service_url);
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(c.secondary_service_url);
  await page!.getByTestId('configuration.update-url').fill('http://example.invalid/version.json');
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('configuration.error')).toContainText('update_source_rejected');
  await page!.getByTestId('configuration.cancel').click();
  event('atomic_config','ui',c.service_url,await uiValue('auth.server'),'auth.server');
  await login('test-alice','TEST-ONLY-alice-42!'); await changePassword('TEST-ONLY-alice-42!');
  const first = savedToken();
  await status('origin1_accept',200,c.service_url,'GET','/v1/me',undefined,first);
  await status('origin2_reject',401,c.secondary_service_url,'GET','/v1/me',undefined,first);
  await restart(); await identity('origin1_restore','test-alice');
  await page!.getByTestId('session.logout').click(); await expect(page!.getByTestId('auth.login')).toBeVisible();
  await configure(c.secondary_service_url);
  await status('secondary_password_not_primary',401,c.service_url,'POST','/v1/auth/login',{username:'test-alice',password:'TEST-ONLY-alice-43!'});
  await login('test-alice','TEST-ONLY-alice-43!'); await changePassword('TEST-ONLY-alice-43!','TEST-ONLY-Changed-43!');
  const second = savedToken(c.secondary_service_url);
  await status('origin2_accept',200,c.secondary_service_url,'GET','/v1/me',undefined,second);
  await status('origin1_reject',401,c.service_url,'GET','/v1/me',undefined,second);
  event('origin_isolation','filesystem',false,credentialPath()===credentialPath(c.secondary_service_url));
  await capture('TM001-006-01-origin-isolation');
  await restart(); await identity('origin2_restore','test-alice');
  await page!.getByTestId('session.logout').click();
  for (const invalid of ['http://example.invalid/version.json','http://user:pass@127.0.0.1/version.json','http://127.0.0.1:65536/version.json']) {
    await page!.getByTestId('configuration.open').click();
    await page!.getByTestId('configuration.update-url').fill(invalid);
    await page!.getByTestId('configuration.save').click();
    await expect(page!.getByTestId('configuration.error')).toBeVisible();
    await page!.getByTestId('configuration.cancel').click();
  }
  const custom = `http://127.0.0.1:${new URL(c.secondary_service_url).port}/configuration-only.json`;
  await configure(c.secondary_service_url, custom);
  await restart();
  await page!.getByTestId('configuration.open').click();
  event('config_validation','ui',custom,await uiValue('configuration.update-url'),'configuration.update-url');
  await page!.getByTestId('configuration.cancel').click();
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.update-url').fill('https://updates.example.invalid/version.json');
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('configuration.status')).toBeVisible();
  event('https_config_only','ui',true,!(await visible('configuration.error')),'configuration.status');
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.reset-defaults').click();
  await expect(page!.getByTestId('configuration.status')).toContainText('已恢复默认地址');
  await expect(page!.getByTestId('configuration.api-url')).toHaveValue('http://127.0.0.1:49176');
  await expect(page!.getByTestId('configuration.update-url')).toHaveValue('http://127.0.0.1:49177/version.json');
  await page!.getByTestId('configuration.cancel').click();
  await restart(); await defaults('restore_defaults');
  await capture('TM001-006-02-restored-defaults');
});

test('E2E-TM001-004 four update refusals and native self-relaunch', async () => {
  if (!c.update_url || !c.cdp_port) throw new Error('Owned update fixture and diagnostic port required');
  await launch(); await defaults(); await configure(c.service_url,c.update_url);
  await login('test-alice','TEST-ONLY-alice-42!'); await changePassword('TEST-ONLY-alice-42!');
  const token = savedToken(); const oldPid = application!.process().pid!;
  const profileBefore = await application!.evaluate(({app}) => app.getPath('userData'));
  event('profile_before_upgrade','process',c.profile_path,profileBefore);
  const runtimePath = join(dirname(c.app_path),'TokenMeter.runtime.json');
  const runtimeBefore = createHash('sha256').update(readFileSync(runtimePath)).digest('hex');
  const runtimeData = JSON.parse(readFileSync(runtimePath,'utf8')) as {profile_path:string;diagnostic_cdp_port:number};
  event('runtime_profile_before','filesystem',c.profile_path,runtimeData.profile_path);
  event('runtime_cdp_before','filesystem',c.cdp_port,runtimeData.diagnostic_cdp_port);
  await expect.poll(async()=> (await updateObservations()).filter(item=>item.stage==='current' && item.route==='/version.json' && item.status===204).length,
    {timeout:20_000}).toBeGreaterThanOrEqual(1);
  await expect(page!.getByTestId('updates.status')).toContainText('当前已是最新版本');
  event('auto_discovery','ui',true,(await uiText('updates.status')).includes('当前已是最新版本'),'updates.status');
  await control('forbidden'); await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_source_rejected');
  event('forbidden','ui',true,(await uiText('updates.status')).includes('update_source_rejected'),'updates.status');
  await capture('TM001-004-01-forbidden');
  await control('redirect'); await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible(); await page!.getByTestId('updates.install').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_transport_rejected');
  event('redirect','ui',true,(await uiText('updates.status')).includes('update_transport_rejected'),'updates.status');
  await capture('TM001-004-02-redirect');
  await control('invalid'); await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible(); await page!.getByTestId('updates.install').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_signature_rejected');
  event('invalid_signature','ui',true,(await uiText('updates.status')).includes('update_signature_rejected'),'updates.status');
  await capture('TM001-004-03-bad-signature');
  await control('valid'); await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  await ensureTraceBeforeNativeRestart();
  const launchesAtHandoff = runnerLaunchCount;
  await page!.getByTestId('updates.install').click();
  const newPid = await waitForNewPid(oldPid);
  event('self_relaunch','process',true,newPid!==oldPid && !ownedAppPids().includes(oldPid) && runnerLaunchCount===launchesAtHandoff);
  const runtimeAfter = createHash('sha256').update(readFileSync(runtimePath)).digest('hex');
  const afterData = JSON.parse(readFileSync(runtimePath,'utf8')) as {profile_path:string;diagnostic_cdp_port:number};
  event('runtime_unchanged','filesystem',runtimeBefore,runtimeAfter);
  event('runtime_profile_after','filesystem',profileBefore,afterData.profile_path);
  const installed=bundleVersion();
  expect(installed.version).toBe(c.expected_upgrade_version);
  event('valid_install','filesystem',c.expected_upgrade_build,installed.build);
  application = null; page = null;
  const endpoint = `http://127.0.0.1:${c.cdp_port}`;
  const deadline = Date.now()+30_000;
  while (Date.now()<deadline) {
    try { reconnected = await chromium.connectOverCDP(endpoint,{timeout:2000}); break; }
    catch { await new Promise(resolve=>setTimeout(resolve,300)); }
  }
  if (!reconnected) throw new Error('Autonomously restarted App did not expose owned loopback CDP');
  const context = reconnected.contexts()[0];
  if (!context) throw new Error('Reconnected process has no browser context');
  const rendererDeadline = Date.now()+30_000;
  while (!page && Date.now()<rendererDeadline) {
    page = context.pages().find(p=>p.url().startsWith('tokenmeter://app/')) ?? null;
    if (!page) await new Promise(resolve=>setTimeout(resolve,300));
  }
  if (!page) throw new Error('Reconnected process has no real TokenMeter renderer');
  await expect(page.getByTestId('session.username')).toHaveText('test-alice',{timeout:30_000});
  await identity('identity_restored','test-alice');
  await expect(page.getByTestId('app.build')).toContainText(`build ${c.expected_upgrade_build}`);
  event('new_build','ui',true,(await uiText('app.build')).includes(`build ${c.expected_upgrade_build}`),'app.build');
  await page.getByTestId('session.refresh').click();
  await expect(page.getByTestId('session.verified')).toBeVisible();
  await status('restarted_me',200,c.service_url,'GET','/v1/me',undefined,token);
  const opened = openedFilePaths(newPid);
  const defaultHome = process.env.HOME;
  if (!defaultHome) throw new Error('HOME is required to check the default profile boundary');
  const defaultProfile = join(defaultHome,'Library/Application Support/TokenMeter');
  const ownedOpenPaths = opened.filter(name=>name.startsWith(c.profile_path+'/'));
  const defaultOpenPaths = opened.filter(name=>name===defaultProfile || name.startsWith(defaultProfile+'/'));
  writeFileSync(join(output!,'process-open-files.json'),JSON.stringify({run_id:c.run_id,case_id:c.case_id,
    pid:newPid,observed_at:new Date().toISOString(),all_open_paths:opened,
    owned_profile_paths:ownedOpenPaths,default_profile:defaultProfile,
    default_profile_paths:defaultOpenPaths},null,2)+'\n',{mode:0o600});
  const profileUsed = ownedOpenPaths.length>0;
  event('new_process_profile_files','process',true,profileUsed);
  event('new_process_no_default_profile','process',true,
    c.profile_path!==defaultProfile && defaultOpenPaths.length===0);
  writeFileSync(join(output!,'upgrade-process.json'),JSON.stringify({run_id:c.run_id,case_id:c.case_id,
    old_pid:oldPid,new_pid:newPid,installed_executable:binary,
    observed_open_paths:opened,observed_owned_open_paths:ownedOpenPaths,
    observed_default_open_paths:defaultOpenPaths,profile_path:c.profile_path,
    process_open_files:'process-open-files.json',observed_at:new Date().toISOString()})+'\n',{mode:0o600});
  await capture('TM001-004-04-upgraded');
  writeFileSync(join(output!,'upgrade-result.json'),JSON.stringify({old_pid:oldPid,new_pid:newPid,
    old_build:c.expected_app_build,new_build:installed.build,profile_before_after:{before:profileBefore,after:afterData.profile_path},me_status:200,
    runtime_sha256_before:runtimeBefore,runtime_sha256_after:runtimeAfter,profile_observed_in_lsof:profileUsed,
    default_profile_observed_in_lsof:defaultOpenPaths.length>0,
    all_open_file_count:opened.length,profile_open_file_count:ownedOpenPaths.length,
    runner_launch_count_after_install:runnerLaunchCount-launchesAtHandoff,
    reconnected_at:new Date().toISOString(),diagnostic_loopback:endpoint})+'\n',{mode:0o600});
});
