/** Independent task-level TM-001 checks. One Playwright invocation runs one TC. */
import { test, expect, _electron as electron, type ElectronApplication, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { appendFileSync, chmodSync, existsSync, linkSync, lstatSync, mkdirSync, readFileSync, renameSync, rmdirSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

type Context = {
  run_id: string; candidate_sha: string; case_id: string; app_path: string; profile_path: string;
  service_url: string; database_path: string; fixture_kind: string; service_log_path?: string;
  comparison_database_path?: string; bootstrap_original_path?: string;
  bootstrap_backup_path?: string; bootstrap_restored_path?: string;
  bootstrap_seed_sql_path?: string; bootstrap_exit_code?: number;
  service_control_url?: string; service_control_token?: string; backend_service_url?: string;
  peer_app_path?: string; peer_profile_path?: string;
  clock_path?: string; clock_start?: number;
  bootstrap_root?: string; seed_path?: string; python_executable?: string;
  service_restart_control_url?: string; service_restart_control_token?: string;
};
const input = process.env.TM_E2E_CONTEXT;
const output = process.env.TM_E2E_CASE_OUTPUT;
if (!input || !output) throw new Error('Owned granular context and output are required');
const c = JSON.parse(readFileSync(input, 'utf8')) as Context;
const executable = join(c.app_path, 'Contents/MacOS/TokenMeter');
const events = join(output, 'events.jsonl');
const MEMBER_PASSWORD = 'TEST-ONLY-alice-42!';
const ADMIN_PASSWORD = 'TEST-ONLY-admin-42!';
const BOB_PASSWORD = 'TEST-ONLY-bob-42!';
const NEW_PASSWORD = 'TEST-ONLY-Changed-42!';
const RESET_PASSWORD = 'TEST-ONLY-Reset-42!';
const PRODUCTION_NEW_PASSWORD = 'TEST-ONLY-Admin-New-42!';
const ADMIN_ID = '00000000-0000-4000-8000-000000000001';
const BOB_ID = '00000000-0000-4000-8000-000000000003';
let app: ElectronApplication | null = null;
let page: Page | null = null;
let tracing = false;
let traceIndex = 0;

function required<T>(value: T | null | undefined, name: string): T {
  if (value === null || value === undefined || value === '') throw new Error(`${name} has no owned runner fixture; this TC is unbound`);
  return value;
}
function dbRows<T extends Record<string, unknown>>(sql: string, database = c.database_path, ...args: (string | number)[]): T[] {
  const handle = new DatabaseSync(required(database, 'database_path'), { readOnly: true });
  try { return handle.prepare(sql).all(...args) as T[]; }
  finally { handle.close(); }
}
function dbOne<T extends Record<string, unknown>>(sql: string, database = c.database_path, ...args: (string | number)[]): T {
  const row = dbRows<T>(sql, database, ...args)[0];
  if (!row) throw new Error('Expected read-only database row is missing');
  return row;
}
function countAudit(action: string): number {
  return Number(dbOne<{ n: number }>('SELECT count(*) AS n FROM audit WHERE action=?', c.database_path, action).n);
}
function tokenPath(): string {
  return join(c.profile_path, 'credentials', createHash('sha256').update(c.service_url).digest('hex') + '.token');
}
function savedToken(): string {
  const value = readFileSync(tokenPath(), 'utf8');
  if (!/^[A-Za-z0-9_-]{43}$/.test(value)) throw new Error('Owned App did not save an opaque session token');
  return value;
}
function digestFile(path: string): string { return createHash('sha256').update(readFileSync(path)).digest('hex'); }
function childEnvironment(): Record<string, string> {
  return Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined)
    .filter(([key]) => !key.startsWith('TM_E2E_') && !key.startsWith('TM_INTERNAL_') &&
      !key.includes('SIGNING') && !key.includes('TOKEN')));
}
async function launch(): Promise<void> {
  if (!existsSync(executable)) throw new Error('Installed candidate executable is missing');
  app = await electron.launch({ executablePath: executable, args: [`--user-data-dir=${c.profile_path}`],
    env: childEnvironment(), chromiumSandbox: true, timeout: 60_000 });
  page = await app.firstWindow();
  await expect(page.getByTestId('app.build')).toBeVisible();
  await app.context().tracing.start({ screenshots: true, snapshots: true, sources: false });
  tracing = true;
}
async function launchPeer(): Promise<void> {
  const peerApp = required(c.peer_app_path, 'peer_app_path');
  const peerProfile = required(c.peer_profile_path, 'peer_profile_path');
  const peerBinary = join(peerApp, 'Contents/MacOS/TokenMeter');
  if (!existsSync(peerBinary) || !existsSync(peerProfile)) throw new Error('Owned independently installed peer App is missing');
  app = await electron.launch({ executablePath: peerBinary, args: [`--user-data-dir=${peerProfile}`],
    env: childEnvironment(), chromiumSandbox: true, timeout: 60_000 });
  page = await app.firstWindow();
  await expect(page.getByTestId('app.build')).toBeVisible();
  await app.context().tracing.start({ screenshots: true, snapshots: true, sources: false });
  tracing = true;
}
async function restartPeer(): Promise<void> { await close(); await launchPeer(); }
function peerTokenPath(): string {
  return join(required(c.peer_profile_path, 'peer_profile_path'), 'credentials',
    createHash('sha256').update(c.service_url).digest('hex') + '.token');
}
function peerToken(): string {
  const value = readFileSync(peerTokenPath(), 'utf8');
  if (!/^[A-Za-z0-9_-]{43}$/.test(value)) throw new Error('Peer App did not persist a valid opaque token');
  return value;
}
async function close(): Promise<void> {
  if (!app) return;
  if (tracing) {
    await app.context().tracing.stop({ path: join(output!, `trace-${String(++traceIndex).padStart(2, '0')}.zip`) });
    tracing = false;
  }
  await app.close(); app = null; page = null;
}
async function restart(): Promise<void> { await close(); await launch(); }
async function step(index: number, action: string, source: 'ui' | 'service' | 'filesystem' | 'process',
                    expected: unknown, actual: unknown, soft = false): Promise<void> {
  let screenshot: string | null = null;
  if (page && !page.isClosed()) {
    screenshot = `TC-step-${String(index).padStart(2, '0')}.png`;
    await page.screenshot({ path: join(output!, screenshot) });
  }
  const record = { run_id: c.run_id, case_id: c.case_id, step: index, action, source,
    expected, actual, passed: JSON.stringify(expected) === JSON.stringify(actual),
    timestamp: new Date().toISOString(), screenshot };
  appendFileSync(events, JSON.stringify(record) + '\n', { mode: 0o600 });
  if (soft) expect.soft(actual, `${c.case_id} step ${index}: ${action}`).toEqual(expected);
  else expect(actual, `${c.case_id} step ${index}: ${action}`).toEqual(expected);
}
async function request(method: string, route: string, body?: object, token?: string): Promise<{ status: number; body: any }> {
  const response = await fetch(c.service_url + route, { method,
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined });
  const raw = await response.text();
  return { status: response.status, body: raw ? JSON.parse(raw) : {} };
}
async function apiToken(username: string, password: string): Promise<string> {
  const result = await request('POST', '/v1/auth/login', { username, password });
  if (result.status !== 200 || !/^[A-Za-z0-9_-]{43}$/.test(String(result.body.access_token ?? '')))
    throw new Error('Owned service failed to issue a real synthetic session');
  return result.body.access_token as string;
}
async function configure(): Promise<void> {
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(c.service_url);
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('auth.server')).toHaveValue(c.service_url);
}
async function login(username: string, password: string): Promise<void> {
  await page!.getByTestId('auth.username').fill(username);
  await page!.getByTestId('auth.password').fill(password);
  await page!.getByTestId('auth.login').click();
}
async function changePassword(current: string, next = NEW_PASSWORD): Promise<void> {
  await page!.getByTestId('password.current').fill(current);
  await page!.getByTestId('password.new').fill(next);
  await page!.getByTestId('password.confirm').fill(next);
  await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('password.status')).toBeVisible();
}
async function memberReady(): Promise<void> {
  await launch(); await configure(); await login('test-alice', MEMBER_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await changePassword(MEMBER_PASSWORD);
  await expect(page!.getByTestId('session.username')).toHaveText('test-alice');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
}
async function adminReady(): Promise<void> {
  await launch(); await configure(); await login('test-admin', ADMIN_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await changePassword(ADMIN_PASSWORD);
  await expect(page!.getByTestId('session.username')).toHaveText('test-admin');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await page!.getByTestId('admin.accounts').click();
  await expect(page!.getByTestId('admin.state.test-bob')).toBeVisible();
}
async function resetBob(password = RESET_PASSWORD): Promise<void> {
  await page!.getByTestId('admin.reset.test-bob').click();
  await page!.getByTestId('admin.temporary-password').fill(password);
  await page!.getByTestId('admin.reset.confirm').click();
  await expect(page!.getByTestId('admin.status')).toContainText('password_reset');
}
function meCount(): number {
  const log = readFileSync(required(c.service_log_path, 'service_log_path'), 'utf8');
  return [...log.matchAll(/"GET \/v1\/me HTTP\/[0-9.]+" 200/g)].length;
}
function loginCount(): number {
  const log = readFileSync(required(c.service_log_path, 'service_log_path'), 'utf8');
  return [...log.matchAll(/"POST \/v1\/auth\/login HTTP\/[0-9.]+" 200/g)].length;
}
type TransportRequest = { method: string; route: string; mode: string; forwarded: boolean;
  probe?: boolean; status?: number; received_at: string; finished_at?: string };
async function serviceControl(mode: 'normal' | 'offline' | 'unavailable' | 'delay', route = '*',
                              releaseDelayed = true): Promise<void> {
  const response = await fetch(required(c.service_control_url, 'service_control_url'), {
    method: 'POST', headers: { Authorization: 'Bearer ' + required(c.service_control_token, 'service_control_token'),
      'Content-Type': 'application/json' }, body: JSON.stringify({ mode, route, release_delayed: releaseDelayed }) });
  if (response.status !== 200) throw new Error('Owned transport control refused mode');
  const body = await response.json() as { mode: string; route: string };
  if (body.mode !== mode || body.route !== route) throw new Error('Owned transport mode differs');
}
async function releaseDelayed(): Promise<void> {
  const response = await fetch(required(c.service_control_url, 'service_control_url') + '/release-delayed',
    { method: 'POST', headers: { Authorization: 'Bearer ' + required(c.service_control_token, 'service_control_token') } });
  if (response.status !== 200 || (await response.json() as { released?: boolean }).released !== true)
    throw new Error('Owned delayed transport did not release');
}
async function ownedNoEgressTarget(): Promise<{ url: string; requests: Array<{ method: string; hasAuthorization: boolean }>;
  close: () => Promise<void> }> {
  const requests: Array<{ method: string; hasAuthorization: boolean }> = [];
  const server = createServer((incoming, response) => {
    requests.push({ method: incoming.method ?? '', hasAuthorization: Boolean(incoming.headers.authorization) });
    response.writeHead(204); response.end();
  });
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    server.close();
    throw new Error('Owned no-egress listener has no loopback port');
  }
  return { url: `http://127.0.0.1:${address.port}`, requests,
    close: () => new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())) };
}
async function transportRequests(): Promise<TransportRequest[]> {
  const response = await fetch(required(c.service_control_url, 'service_control_url'),
    { headers: { Authorization: 'Bearer ' + required(c.service_control_token, 'service_control_token') } });
  if (response.status !== 200) throw new Error('Owned transport observations unavailable');
  const body = await response.json() as { requests: TransportRequest[] };
  if (!Array.isArray(body.requests)) throw new Error('Owned transport request audit is malformed');
  return body.requests;
}
async function restartBackend(): Promise<{ old_pid: number; new_pid: number; same_origin: boolean; health: number }> {
  const response = await fetch(required(c.service_control_url, 'service_control_url') + '/restart-backend',
    { method: 'POST', headers: { Authorization: 'Bearer ' + required(c.service_control_token, 'service_control_token') } });
  if (response.status !== 200) throw new Error('Owned backend restart control failed');
  return response.json() as Promise<{ old_pid: number; new_pid: number; same_origin: boolean; health: number }>;
}
function setClock(second: number): void {
  const path = required(c.clock_path, 'clock_path');
  if (!Number.isSafeInteger(second)) throw new Error('Invalid private test clock');
  const temp = `${path}.next`;
  writeFileSync(temp, `${second}\n`, { flag: 'wx', mode: 0o600 });
  renameSync(temp, path);
}

test.beforeEach(async ({}, info) => {
  if (info.title.split(' ')[0] !== c.case_id) throw new Error('Runner TC identity differs from Playwright test');
  if (c.fixture_kind.startsWith('production_bootstrap') !== c.case_id.includes('BOOTSTRAP'))
    throw new Error('Case and isolated fixture kind differ');
});
test.afterEach(async () => {
  try { if (page && !page.isClosed()) await page.screenshot({ path: join(output!, 'final.png') }); } catch { /* original test failure retained */ }
  try { await close(); } catch { /* runner verifies trace and owned process cleanup */ }
});

test('TC-TM001-SESSION-01', async () => {
  await launch();
  const automatic = await page!.getByTestId('auth.automatic-login').isChecked();
  await configure(); await login('test-alice', MEMBER_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  const forced = await page!.getByTestId('password.new').isVisible();
  await changePassword(MEMBER_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(1, 'Read default automatic-login option; authenticate synthetic member and finish forced password change', 'ui',
    { automatic: true, forced: true, identity: 'test-alice' },
    { automatic, forced, identity: await page!.getByTestId('session.username').textContent() });

  const path = tokenPath(); const token = savedToken();
  const directory = lstatSync(dirname(path)); const file = lstatSync(path);
  await step(2, 'Read only owned credential metadata and opaque shape', 'filesystem',
    { directory_mode: 0o700, file_mode: 0o600, owner: true, ordinary_single_link: true, opaque: true, no_plaintext: true },
    { directory_mode: directory.mode & 0o777, file_mode: file.mode & 0o777,
      owner: directory.uid === process.getuid?.() && file.uid === process.getuid?.(),
      ordinary_single_link: file.isFile() && !file.isSymbolicLink() && file.nlink === 1,
      opaque: /^[A-Za-z0-9_-]{43}$/.test(token),
      no_plaintext: !token.includes('test-alice') && !token.includes(MEMBER_PASSWORD) && !token.includes(NEW_PASSWORD) });

  const me = await request('GET', '/v1/me', undefined, token);
  const hashes = dbRows<{ token_hash: string }>(
    "SELECT token_hash FROM sessions WHERE user_id='00000000-0000-4000-8000-000000000002'");
  await step(3, 'Use saved token against real /v1/me and compare read-only session digest', 'service',
    { status: 200, username: 'test-alice', one_stored_session: true, digest_matches: true, raw_absent: true },
    { status: me.status, username: me.body.username, one_stored_session: hashes.length === 1,
      digest_matches: hashes.some(row => row.token_hash === createHash('sha256').update(token).digest('hex')),
      raw_absent: hashes.every(row => row.token_hash !== token) });

  const settings = readFileSync(join(c.profile_path, 'settings.json'), 'utf8');
  await step(4, 'Archive synthetic UI and compare settings against secret-free session state', 'filesystem',
    { verified: true, credential_present: true, settings_have_no_secret: true, event_file_present: true },
    { verified: await page!.getByTestId('session.verified').isVisible(), credential_present: existsSync(path),
      settings_have_no_secret: !settings.includes(token) && !settings.includes(MEMBER_PASSWORD) && !settings.includes(NEW_PASSWORD),
      event_file_present: existsSync(events) });
});

test('TC-TM001-SESSION-02', async () => {
  await memberReady();
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  const path = tokenPath();
  if (existsSync(path)) throw new Error('Logout did not clear owned credential before fault setup');
  mkdirSync(path, { mode: 0o700 }); // Only this case's own profile; blocks atomic rename to the token filename.
  await login('test-alice', NEW_PASSWORD);
  await expect(page!.getByTestId('auth.error')).toContainText('unsafe_storage');
  await step(1, 'With owned filename directory blocking token save, submit a valid login in the real App', 'ui',
    { save_error: true, authenticated_home: false },
    { save_error: (await page!.getByTestId('auth.error').textContent())?.includes('unsafe_storage') ?? false,
      authenticated_home: await page!.getByTestId('session.verified').count() > 0 });

  const blocker = lstatSync(path);
  await step(2, 'Inspect failure state and untouched owned blocking directory', 'filesystem',
    { login_visible: true, blocker_still_directory: true, no_token_file: true },
    { login_visible: await page!.getByTestId('auth.login').isVisible(), blocker_still_directory: blocker.isDirectory(),
      no_token_file: !blocker.isFile() });

  await close(); rmdirSync(path); await launch();
  await step(3, 'Remove only this case blocker and restart the same owned profile', 'ui',
    { login_visible: true, no_persisted_token: true },
    { login_visible: await page!.getByTestId('auth.login').isVisible(), no_persisted_token: !existsSync(path) });

  await login('test-alice', NEW_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(4, 'Repeat real login after restoring safe credential storage', 'filesystem',
    { identity: 'test-alice', saved_opaque_token: true },
    { identity: await page!.getByTestId('session.username').textContent(),
      saved_opaque_token: /^[A-Za-z0-9_-]{43}$/.test(savedToken()) });
});

test('TC-TM001-SESSION-03', async () => {
  required(c.service_log_path, 'service_log_path');
  await memberReady();
  const tokenBefore = savedToken(); const countBefore = meCount(); const oldPid = app!.process().pid;
  await restart();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const persisted = JSON.parse(readFileSync(join(c.profile_path, 'settings.json'), 'utf8')) as { server?: string };
  await step(1, 'Restart installed App using the same owned profile and origin', 'process',
    { new_process: true, same_saved_credential: true, same_origin: true },
    { new_process: app!.process().pid !== oldPid, same_saved_credential: savedToken() === tokenBefore,
      same_origin: persisted.server === c.service_url });

  await expect.poll(() => meCount()).toBeGreaterThan(countBefore);
  await step(2, 'Observe a new real GET /v1/me 200 before accepting restored identity', 'service',
    { me_request_incremented: true, verified_username: 'test-alice' },
    { me_request_incremented: meCount() > countBefore,
      verified_username: await page!.getByTestId('session.username').textContent() });

  const countBeforeRefresh = meCount();
  await page!.getByTestId('session.refresh').click();
  await expect.poll(() => meCount()).toBeGreaterThan(countBeforeRefresh);
  await step(3, 'Use refresh identity and observe another real service verification', 'service',
    { another_me_200: true, still_verified: true },
    { another_me_200: meCount() > countBeforeRefresh,
      still_verified: await page!.getByTestId('session.verified').isVisible() });

  await step(4, 'Correlate owned process, profile credential and UI without entering a password again', 'process',
    { process_changed: true, credential_unchanged: true, identity: 'test-alice' },
    { process_changed: app!.process().pid !== oldPid, credential_unchanged: savedToken() === tokenBefore,
      identity: await page!.getByTestId('session.username').textContent() });
});

test('TC-TM001-SESSION-04', async () => {
  await memberReady();
  const persisted = savedToken();
  const before = meCount();
  await close();
  await serviceControl('offline', '/v1/me');
  await launch();
  await expect(page!.getByTestId('auth.error')).toContainText('network_unavailable');
  await step(1, '同profile重启时让认证请求遇到owned服务断线', 'ui',
    { visibleFailure: true, noVerifiedIdentity: true, noAdminPanel: true },
    { visibleFailure: (await page!.getByTestId('auth.error').textContent())?.includes('network_unavailable') === true,
      noVerifiedIdentity: await page!.getByTestId('session.verified').count() === 0,
      noAdminPanel: await page!.getByTestId('admin.accounts').count() === 0 });
  const failed = (await transportRequests()).filter(row => row.route === '/v1/me' && row.mode === 'offline');
  await step(2, '核对持久token未被当成认证成功且无伪造me响应', 'service',
    { tokenRetained: true, failedRequestObserved: true, noNewMe200: true },
    { tokenRetained: savedToken() === persisted,
      failedRequestObserved: failed.some(row => row.status === 0 && !row.forwarded),
      noNewMe200: meCount() === before });
  await serviceControl('normal');
  const hasRetry = await page!.getByTestId('session.refresh').count() > 0;
  await expect(page!.getByTestId('session.refresh')).toBeVisible();
  const beforeRecoveryRefresh = meCount();
  await page!.getByTestId('session.refresh').click();
  await expect.poll(() => meCount()).toBeGreaterThan(beforeRecoveryRefresh);
  await step(3, '同地址恢复后经UI重试并以新me200确认身份', 'service',
    { retryEntryAvailable: true, newMe200: true, verified: true },
    { retryEntryAvailable: hasRetry, newMe200: meCount() > beforeRecoveryRefresh,
      verified: await page!.getByTestId('session.verified').isVisible() }, true);
  await serviceControl('delay', '/v1/me');
  await page!.getByTestId('session.refresh').click();
  await expect(page!.getByTestId('auth.error')).toContainText('network_unavailable', { timeout: 20_000 });
  const timeoutErrorObserved = (await page!.getByTestId('auth.error').textContent())?.includes('network_unavailable') === true;
  const timedOut = (await transportRequests()).some(row => row.route === '/v1/me' && row.mode === 'delay');
  // Keep the old delayed request suspended while the UI starts a fresh one.
  // A completed old request cannot count as the required new /v1/me 200.
  await serviceControl('normal', '*', false);
  const requestsBeforeRetry = (await transportRequests()).length;
  await page!.getByTestId('session.refresh').click();
  const newNormalMe = async (): Promise<TransportRequest[]> => (await transportRequests()).slice(requestsBeforeRetry)
    .filter(row => row.method === 'GET' && row.route === '/v1/me' && row.mode === 'normal' &&
      row.probe === false && row.forwarded && row.status === 200 && Boolean(row.finished_at));
  await expect.poll(async () => (await newNormalMe()).length).toBeGreaterThan(0);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const identityBeforeLate = await page!.evaluate(async () => {
    const state = await (window as unknown as { tokenmeter: { snapshot: () => Promise<{
      account: { id: string } | null; identityVerified: boolean; lastIdentityCheck: string }> } }).tokenmeter.snapshot();
    return { id: state.account?.id, verified: state.identityVerified, checkedAt: state.lastIdentityCheck };
  });
  await releaseDelayed();
  await expect.poll(async () => (await transportRequests()).some(row =>
    row.route === '/v1/me' && row.mode === 'delay' && Boolean(row.finished_at))).toBeTruthy();
  await page!.waitForTimeout(300);
  const identityAfterLate = await page!.evaluate(async () => {
    const state = await (window as unknown as { tokenmeter: { snapshot: () => Promise<{
      account: { id: string } | null; identityVerified: boolean; lastIdentityCheck: string }> } }).tokenmeter.snapshot();
    return { id: state.account?.id, verified: state.identityVerified, checkedAt: state.lastIdentityCheck };
  });
  await step(4, '15秒超时后恢复；迟到响应不得取代新me结果', 'service',
    { delayRequestObserved: true, timeoutErrorObserved: true, newMe200: true,
      staleResponseDidNotOverwrite: true, finalIdentity: 'test-alice' },
    { delayRequestObserved: timedOut, timeoutErrorObserved,
      newMe200: (await newNormalMe()).length > 0,
      staleResponseDidNotOverwrite: identityBeforeLate.verified &&
        JSON.stringify(identityAfterLate) === JSON.stringify(identityBeforeLate),
      finalIdentity: await page!.getByTestId('session.username').textContent() }, true);
});

async function session05(variant: 'RESET' | 'DISABLE'): Promise<void> {
  await memberReady();
  const old = savedToken();
  const originalMe = await request('GET', '/v1/me', undefined, old);
  await close();
  await launchPeer(); await configure(); await login('test-admin', ADMIN_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await changePassword(ADMIN_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const adminPersisted = peerToken();
  await page!.getByTestId('admin.accounts').click();
  if (variant === 'RESET') {
    await page!.getByTestId('admin.reset.test-alice').click();
    await page!.getByTestId('admin.temporary-password').fill(RESET_PASSWORD);
    await page!.getByTestId('admin.reset.confirm').click();
    await expect(page!.getByTestId('admin.status')).toContainText('password_reset');
  } else {
    await page!.getByTestId('admin.disable.test-alice').click();
    await expect(page!.getByTestId('admin.status')).toContainText('account_disabled');
  }
  const target = dbOne<{ is_active: number; must_change_password: number }>(
    "SELECT is_active,must_change_password FROM users WHERE username='test-alice'");
  await step(1, `先证实原token有效，再由另一owned App执行${variant === 'RESET' ? '管理员重置' : '管理员停用'}`, 'service',
    { originalMe: 200, operationSucceeded: true, targetStateCorrect: true,
      committedAudit: 1, peerAdminStillValid: true },
    { originalMe: originalMe.status,
      operationSucceeded: (await page!.getByTestId('admin.status').textContent())?.includes(
        variant === 'RESET' ? 'password_reset' : 'account_disabled') === true,
      targetStateCorrect: variant === 'RESET' ? target.is_active === 1 && target.must_change_password === 1 :
        target.is_active === 0,
      committedAudit: countAudit(variant === 'RESET' ? 'password_reset' : 'account_disabled'),
      peerAdminStillValid: (await request('GET', '/v1/me', undefined, adminPersisted)).status === 200 });
  const revoked = await request('GET', '/v1/me', undefined, old);
  await step(2, '独立访问真实me核对被重置会话已撤销', 'service',
    { status: 401, noAliceSessionRows: true },
    { status: revoked.status,
      noAliceSessionRows: dbOne<{ n: number }>("SELECT count(*) AS n FROM sessions WHERE user_id='00000000-0000-4000-8000-000000000002'").n === 0 });
  await close();
  const meBeforeRestore = meCount();
  const rejectedBeforeRestore = (await transportRequests()).filter(row => row.route === '/v1/me' && row.status === 401).length;
  await launch();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await step(3, '重启原App使持久旧token走真实me拒绝流程', 'ui',
    { meAttempted: true, loginVisible: true, noVerifiedIdentity: true, invalidSessionPrompt: true },
    { meAttempted: meCount() === meBeforeRestore &&
        (await transportRequests()).filter(row => row.route === '/v1/me' && row.status === 401).length > rejectedBeforeRestore,
      loginVisible: await page!.getByTestId('auth.login').isVisible(),
      noVerifiedIdentity: await page!.getByTestId('session.verified').count() === 0,
      invalidSessionPrompt: (await page!.getByTestId('auth.error').textContent())?.includes('invalid_session') === true });
  const removed = !existsSync(tokenPath());
  const previousRequests = (await transportRequests()).filter(row => row.route === '/v1/me').length;
  await restart();
  const laterRequests = (await transportRequests()).filter(row => row.route === '/v1/me').length;
  await step(4, '检查原origin凭据删除；再次启动不重试旧token', 'filesystem',
    { deletedCredential: true, noRepeatedRestore: true, peerCredentialKept: true },
    { deletedCredential: removed && !existsSync(tokenPath()),
      noRepeatedRestore: laterRequests === previousRequests,
      peerCredentialKept: existsSync(peerTokenPath()) });
}
test('TC-TM001-SESSION-05#RESET', async () => { await session05('RESET'); });
test('TC-TM001-SESSION-05#DISABLE', async () => { await session05('DISABLE'); });

test('TC-TM001-SESSION-07', async () => {
  const t0 = required(c.clock_start, 'clock_start');
  const duration = 2_592_000;
  setClock(t0);
  await memberReady();
  const token = savedToken();
  const digest = createHash('sha256').update(token).digest('hex');
  const issued = dbOne<{ expires_at: number }>('SELECT expires_at FROM sessions WHERE token_hash=?', c.database_path, digest);
  await step(1, '私有时钟T0经真实App登录并只读检查持久会话期限', 'filesystem',
    { exactExpiry: t0 + duration, realSession: true },
    { exactExpiry: issued.expires_at,
      realSession: (await request('GET', '/v1/me', undefined, token)).status === 200 });
  setClock(t0 + duration - 1);
  const before = await request('GET', '/v1/me', undefined, token);
  const restarted = await restartBackend();
  const after = await request('GET', '/v1/me', undefined, token);
  const unchanged = dbOne<{ expires_at: number }>('SELECT expires_at FROM sessions WHERE token_hash=?', c.database_path, digest);
  await step(2, '推进到到期前1秒并重启真实FastAPI实例', 'service',
    { before: 200, afterRestart: 200, exactExpiryUnchanged: true, restartedOwnedBackend: true },
    { before: before.status, afterRestart: after.status,
      exactExpiryUnchanged: unchanged.expires_at === issued.expires_at,
      restartedOwnedBackend: restarted.old_pid !== restarted.new_pid && restarted.same_origin && restarted.health === 200 });
  setClock(t0 + duration);
  const at = await request('GET', '/v1/me', undefined, token);
  setClock(t0 + duration + 1);
  const afterBoundary = await request('GET', '/v1/me', undefined, token);
  await step(3, '到期瞬间和后一秒均向真实服务请求同一token', 'service',
    { atExpiry: 401, afterExpiry: 401, noSlidingExtension: true },
    { atExpiry: at.status, afterExpiry: afterBoundary.status,
      noSlidingExtension: dbOne<{ expires_at: number }>('SELECT expires_at FROM sessions WHERE token_hash=?', c.database_path, digest).expires_at === issued.expires_at });
  await page!.getByTestId('session.refresh').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  setClock(t0);
  await login('test-alice', NEW_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const legacy = savedToken();
  const legacyHash = createHash('sha256').update(legacy).digest('hex');
  const historicalExpiry = t0 + 60;
  const db = new DatabaseSync(c.database_path);
  try {
    const changed = db.prepare('UPDATE sessions SET expires_at=? WHERE token_hash=?').run(historicalExpiry, legacyHash);
    if (changed.changes !== 1) throw new Error('Owned legacy session fixture update did not affect one session');
  } finally { db.close(); }
  writeFileSync(join(output!, 'legacy-expiry-setup.sql'),
    '-- Owned pre-existing session fixture; token hash is supplied as a parameter.\nUPDATE sessions SET expires_at = :historical_expiry WHERE token_hash = :owned_token_digest;\n',
    { flag: 'wx', mode: 0o600 });
  setClock(historicalExpiry - 1);
  const legacyRestart = await restartBackend();
  const oneBefore = await request('GET', '/v1/me', undefined, legacy);
  const stillHistorical = dbOne<{ expires_at: number }>('SELECT expires_at FROM sessions WHERE token_hash=?', c.database_path, legacyHash);
  setClock(historicalExpiry);
  const expired = await request('GET', '/v1/me', undefined, legacy);
  await page!.getByTestId('session.refresh').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await step(4, '模拟已有短期限会话并重启服务，App收到拒绝后清理凭据', 'service',
    { previousExpiryPreserved: true, beforeExpiry: 200, atExpiry: 401,
      AppReturnsToLogin: true, credentialRemoved: true, ownedRestart: true },
    { previousExpiryPreserved: stillHistorical.expires_at === historicalExpiry,
      beforeExpiry: oneBefore.status, atExpiry: expired.status,
      AppReturnsToLogin: await page!.getByTestId('auth.login').isVisible(),
      credentialRemoved: !existsSync(tokenPath()),
      ownedRestart: legacyRestart.old_pid !== legacyRestart.new_pid && legacyRestart.health === 200 });
});

test('TC-TM001-SESSION-06', async () => {
  required(c.service_log_path, 'service_log_path');
  await memberReady();
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await page!.getByTestId('auth.automatic-login').click();
  await expect(page!.getByTestId('auth.automatic-login')).not.toBeChecked();
  // This file is synthetic, owned, and created only after the App has returned
  // to its login page. It models a stale but valid persisted session.
  const stale = await apiToken('test-alice', NEW_PASSWORD);
  writeFileSync(tokenPath(), stale, { flag: 'wx', mode: 0o600 });
  const beforeLogin = loginCount();
  await login('test-alice', NEW_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await expect.poll(() => loginCount()).toBeGreaterThan(beforeLogin);
  await step(1, 'Disable automatic login in UI, seed only an owned stale credential, and authenticate anew', 'ui',
    { new_real_login: true, current_identity: 'test-alice', persisted_credential_cleared: true },
    { new_real_login: loginCount() > beforeLogin,
      current_identity: await page!.getByTestId('session.username').textContent(),
      persisted_credential_cleared: !existsSync(tokenPath()) });

  const beforeMe = meCount();
  await page!.getByTestId('session.refresh').click();
  await expect.poll(() => meCount()).toBeGreaterThan(beforeMe);
  await step(2, 'Refresh real in-memory identity with persistence disabled', 'service',
    { me_confirmed: true, no_credential_file: true, verified: true },
    { me_confirmed: meCount() > beforeMe, no_credential_file: !existsSync(tokenPath()),
      verified: await page!.getByTestId('session.verified').isVisible() });

  await restart();
  await step(3, 'Restart the same profile while automatic login is disabled', 'ui',
    { login_visible: true, option_disabled: true, no_credential_file: true },
    { login_visible: await page!.getByTestId('auth.login').isVisible(),
      option_disabled: !(await page!.getByTestId('auth.automatic-login').isChecked()),
      no_credential_file: !existsSync(tokenPath()) });

  await page!.getByTestId('auth.automatic-login').click();
  await expect(page!.getByTestId('auth.automatic-login')).toBeChecked();
  await login('test-alice', NEW_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const persisted = savedToken();
  const beforeRestore = meCount();
  await restart();
  await expect(page!.getByTestId('session.username')).toHaveText('test-alice');
  await expect.poll(() => meCount()).toBeGreaterThan(beforeRestore);
  await step(4, 'Reenable automatic login in UI, save a new token, and restore through real service', 'service',
    { saved_opaque_token: true, restored_identity: 'test-alice', same_credential: true, me_confirmed: true },
    { saved_opaque_token: /^[A-Za-z0-9_-]{43}$/.test(persisted),
      restored_identity: await page!.getByTestId('session.username').textContent(),
      same_credential: savedToken() === persisted, me_confirmed: meCount() > beforeRestore });
});

test('TC-TM001-SESSION-08', async () => {
  await memberReady();
  const current = savedToken(); const second = await apiToken('test-alice', NEW_PASSWORD);
  const before = countAudit('logout');
  const firstMe = await request('GET', '/v1/me', undefined, current);
  const secondMe = await request('GET', '/v1/me', undefined, second);
  await step(1, 'Establish two distinct real member sessions and read logout audit baseline', 'service',
    { separate: true, first_status: 200, second_status: 200, before_audit: before },
    { separate: current !== second, first_status: firstMe.status, second_status: secondMe.status,
      before_audit: before });

  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await step(2, 'Exit through App UI and wait for real server logout', 'ui',
    { login_visible: true, credential_removed: true, pending_notice_absent: true },
    { login_visible: await page!.getByTestId('auth.login').isVisible(),
      credential_removed: !existsSync(tokenPath()),
      pending_notice_absent: await page!.getByTestId('session.retry-logout').count() === 0 });

  const old = await request('GET', '/v1/me', undefined, current);
  const still = await request('GET', '/v1/me', undefined, second);
  const audit = dbOne<{ actor_id: string; target_id: string }>(
    "SELECT actor_id,target_id FROM audit WHERE action='logout' ORDER BY occurred_at DESC,id DESC LIMIT 1");
  await step(3, 'Compare both real sessions and read-only logout audit', 'service',
    { first_status: 401, second_status: 200, audit_delta: 1, actor_target_self: true },
    { first_status: old.status, second_status: still.status, audit_delta: countAudit('logout') - before,
      actor_target_self: audit.actor_id === '00000000-0000-4000-8000-000000000002' && audit.actor_id === audit.target_id });

  await restart();
  await step(4, 'Restart original profile after completed online logout', 'ui',
    { login_visible: true, no_pending_logout: true, no_saved_credential: true },
    { login_visible: await page!.getByTestId('auth.login').isVisible(),
      no_pending_logout: await page!.getByTestId('session.retry-logout').count() === 0,
      no_saved_credential: !existsSync(tokenPath()) });
});

test('TC-TM001-SESSION-09', async () => {
  await memberReady();
  const old = savedToken();
  await serviceControl('offline', '/v1/auth/logout');
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('session.retry-logout')).toBeVisible();
  await step(1, 'owned服务断线时经App UI退出并观察待撤销状态', 'ui',
    { localCredentialDeleted: true, loginVisible: true, pendingVisible: true, noVerifiedIdentity: true },
    { localCredentialDeleted: !existsSync(tokenPath()),
      loginVisible: await page!.getByTestId('auth.login').isVisible(),
      pendingVisible: await page!.getByTestId('session.retry-logout').isVisible(),
      noVerifiedIdentity: await page!.getByTestId('session.verified').count() === 0 });
  const originalServer = await page!.getByTestId('auth.server').inputValue();
  const target = await ownedNoEgressTarget();
  try {
    await page!.getByTestId('configuration.open').click();
    const apiInput = page!.getByTestId('configuration.api-url');
    await expect(apiInput).toBeDisabled();
    let fillRejected = false;
    try { await apiInput.fill(target.url, { timeout: 600 }); }
    catch { fillRejected = true; }
    const inputUnchanged = await apiInput.inputValue() === originalServer;
    const apiEditDisabled = await apiInput.isDisabled();
    const resetDefaults = page!.getByTestId('configuration.reset-defaults');
    await expect(resetDefaults).toBeDisabled();
    const resetDisabled = await resetDefaults.isDisabled();
    await page!.getByTestId('configuration.cancel').click();
    const settings = JSON.parse(readFileSync(join(c.profile_path, 'settings.json'), 'utf8')) as { server?: string };
    await step(2, '待撤销期间从真实配置UI尝试编辑owned目标并确认恢复默认禁用', 'ui',
      { unchangedOrigin: c.service_url, pendingStillVisible: true, apiEditDisabled: true, resetDisabled: true,
        fillRejected: true, inputUnchanged: true, settingsUnchanged: true,
        noNewOriginRequest: true, noTokenToTarget: true },
      { unchangedOrigin: await page!.getByTestId('auth.server').inputValue(),
        pendingStillVisible: await page!.getByTestId('session.retry-logout').isVisible(),
        apiEditDisabled, resetDisabled, fillRejected, inputUnchanged,
        settingsUnchanged: settings.server === c.service_url,
        noNewOriginRequest: target.requests.length === 0,
        noTokenToTarget: target.requests.every(request => !request.hasAuthorization) });
  } finally { await target.close(); }
  await serviceControl('normal');
  const beforeRetry = (await transportRequests()).filter(row => row.route === '/v1/auth/logout' && row.status === 204).length;
  await page!.getByTestId('session.retry-logout').click();
  await expect(page!.getByTestId('session.retry-logout')).toHaveCount(0);
  const afterRetry = (await transportRequests()).filter(row => row.route === '/v1/auth/logout' && row.status === 204).length;
  await step(3, '同地址恢复后只用UI重试原token撤销', 'service',
    { realLogoutCompleted: true, pendingCleared: true, noCredentialRewrite: true },
    { realLogoutCompleted: afterRetry === beforeRetry + 1,
      pendingCleared: await page!.getByTestId('session.retry-logout').count() === 0,
      noCredentialRewrite: !existsSync(tokenPath()) });
  const revoked = await request('GET', '/v1/me', undefined, old);
  await page!.getByTestId('configuration.open').click();
  const editable = await page!.getByTestId('configuration.api-url').isEnabled();
  await page!.getByTestId('configuration.cancel').click();
  await step(4, '独立核对旧会话已401并重新允许设置服务地址', 'service',
    { oldMe: 401, configEditable: true, noSavedCredential: true, stillLogin: true },
    { oldMe: revoked.status, configEditable: editable,
      noSavedCredential: !existsSync(tokenPath()), stillLogin: await page!.getByTestId('auth.login').isVisible() });
});

test('TC-TM001-SESSION-10', async () => {
  await memberReady();
  const original = savedToken();
  await close();
  const beforeCredentialProbes = meCount();
  const credential = tokenPath();
  const credentialDir = dirname(credential);
  unlinkSync(credential);
  const sentinel = join(c.profile_path, 'owned-credential-sentinel.txt');
  writeFileSync(sentinel, original, { flag: 'wx', mode: 0o600 });
  const sentinelHash = digestFile(sentinel);
  const variants: Array<{ name: string; prepare: () => void; cleanup: () => void }> = [
    { name: 'symlink', prepare: () => symlinkSync(sentinel, credential), cleanup: () => unlinkSync(credential) },
    { name: 'hardlink', prepare: () => linkSync(sentinel, credential), cleanup: () => unlinkSync(credential) },
    { name: 'wide-mode', prepare: () => { writeFileSync(credential, original, { flag: 'wx', mode: 0o600 }); chmodSync(credential, 0o644); },
      cleanup: () => unlinkSync(credential) },
    { name: 'wide-directory', prepare: () => chmodSync(credentialDir, 0o755),
      cleanup: () => chmodSync(credentialDir, 0o700) },
  ];
  const results: Array<{ variant: string; rejected: boolean; noVerified: boolean; prompt: boolean;
    sentinelUnchanged: boolean; noUnknownDeletion: boolean }> = [];
  for (const variant of variants) {
    variant.prepare();
    try {
      await launch();
      await expect(page!.getByTestId('auth.error')).toContainText('unsafe_storage');
      const error = await page!.getByTestId('auth.error').textContent() ?? '';
      results.push({ variant: variant.name, rejected: error.includes('unsafe_storage'),
        noVerified: await page!.getByTestId('session.verified').count() === 0,
        prompt: error.includes('重新登录'), sentinelUnchanged: digestFile(sentinel) === sentinelHash,
        noUnknownDeletion: existsSync(sentinel) });
      await close();
    } finally {
      if (app) await close();
      variant.cleanup();
    }
  }
  const ownerScript = join(process.cwd(), '../../scripts/granular_credential_owner_fixture.py');
  const ownerImage = join(output!, 'credential-owner-fixture.dmg');
  const ownerRecord = join(output!, 'credential-owner-fixture.json');
  let otherUidObserved = false;
  let ownerPatchVerified = false;
  let ownerMountDetached = false;
  try {
    const raw = execFileSync(c.python_executable ?? 'python3', [ownerScript, 'prepare',
      '--profile', c.profile_path, '--origin', c.service_url,
      '--token-source', sentinel, '--image', ownerImage, '--record', ownerRecord],
      {encoding: 'utf8', timeout: 90_000, env: childEnvironment()});
    const fixture = JSON.parse(raw) as {phase: string; observed_owner_uid: number; patch_span_bytes: number;
      image_sha256_before: string; image_sha256_after: string; device: string};
    const otherUidFile = lstatSync(credential);
    otherUidObserved = fixture.phase === 'mounted' && fixture.observed_owner_uid === 0 &&
      otherUidFile.uid === 0 && (otherUidFile.mode & 0o777) === 0o600 && otherUidFile.nlink === 1;
    ownerPatchVerified = fixture.patch_span_bytes === 4 &&
      /^[a-f0-9]{64}$/.test(fixture.image_sha256_before) &&
      /^[a-f0-9]{64}$/.test(fixture.image_sha256_after) &&
      fixture.image_sha256_before !== fixture.image_sha256_after && /^\/dev\/disk\d+(?:s\d+)?$/.test(fixture.device);
    await launch();
    await expect(page!.getByTestId('auth.error')).toContainText('unsafe_storage');
    const error = await page!.getByTestId('auth.error').textContent() ?? '';
    results.push({variant: 'other-uid', rejected: error.includes('unsafe_storage'),
      noVerified: await page!.getByTestId('session.verified').count() === 0,
      prompt: error.includes('重新登录'), sentinelUnchanged: digestFile(sentinel) === sentinelHash,
      noUnknownDeletion: existsSync(sentinel)});
    await close();
  } finally {
    if (app) await close();
    if (existsSync(ownerRecord) && existsSync(ownerImage)) {
      const raw = execFileSync(c.python_executable ?? 'python3', [ownerScript, 'detach', '--record', ownerRecord],
        {encoding: 'utf8', timeout: 45_000, env: childEnvironment()});
      const detached = JSON.parse(raw) as {phase: string; device: string | null};
      ownerMountDetached = detached.phase === 'detached' && detached.device === null && !existsSync(credential);
    }
  }
  await step(1, '在私有profile构造五种异常凭据对象并记录哨兵及其他UID镜像', 'filesystem',
    { fiveVariants: true, sentinelOwned: true, sentinelHashPresent: true, otherUidReal: true, ownerPatchVerified: true },
    { fiveVariants: results.length === 5,
      sentinelOwned: lstatSync(sentinel).uid === process.getuid?.(),
      sentinelHashPresent: /^[a-f0-9]{64}$/.test(sentinelHash),
      otherUidReal: otherUidObserved, ownerPatchVerified });
  await step(2, '每种异常对象由已安装App正常启动触发真实凭据读取', 'ui',
    { allRejected: true, noVerifiedIdentity: true, promptToRelogin: true },
    { allRejected: results.every(item => item.rejected),
      noVerifiedIdentity: results.every(item => item.noVerified),
      promptToRelogin: results.every(item => item.prompt) }, true);
  await step(3, '核对owned哨兵未变、无缓存登录且本次其他UID镜像已卸载', 'filesystem',
    { sentinelUnchanged: true, noUnknownDeletion: true, noCredentialObject: true,
      noNewMe200: true, otherUidUnmounted: true },
    { sentinelUnchanged: results.every(item => item.sentinelUnchanged) && digestFile(sentinel) === sentinelHash,
      noUnknownDeletion: results.every(item => item.noUnknownDeletion),
      noCredentialObject: !existsSync(credential),
      noNewMe200: meCount() === beforeCredentialProbes,
      otherUidUnmounted: ownerMountDetached });
  await launch();
  await login('test-alice', NEW_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const renewed = savedToken();
  await restart();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(4, '仅移除本例故障对象后经UI重登并正常恢复安全持久会话', 'ui',
    { reloginVerified: true, restartVerified: true, opaqueCredential: true, sentinelPreserved: true },
    { reloginVerified: await page!.getByTestId('session.username').textContent() === 'test-alice',
      restartVerified: await page!.getByTestId('session.verified').isVisible(),
      opaqueCredential: /^[A-Za-z0-9_-]{43}$/.test(renewed) && savedToken() === renewed,
      sentinelPreserved: digestFile(sentinel) === sentinelHash });
});

async function admin02(variant: 'EMPTY' | 'SHORT' | 'LONG'): Promise<void> {
  const bobOld = await apiToken('test-bob', BOB_PASSWORD);
  await adminReady();
  const beforeUser = dbOne<{ password_hash: string; credential_version: number; must_change_password: number }>(
    "SELECT password_hash,credential_version,must_change_password FROM users WHERE username='test-bob'");
  const beforeAudit = countAudit('password_reset');
  const invalid = variant === 'EMPTY' ? '' : variant === 'SHORT' ? '12345678901' : 'X'.repeat(129);
  await page!.getByTestId('admin.reset.test-bob').click();
  await page!.getByTestId('admin.temporary-password').fill(invalid);
  const confirm = page!.getByTestId('admin.reset.confirm');
  await expect(confirm).toBeDisabled();
  let invalidActionBlocked = false;
  try { await confirm.click({ timeout: 600 }); }
  catch { invalidActionBlocked = await confirm.isDisabled(); }
  const validation = page!.getByTestId('admin.reset.validation');
  await expect(validation).toBeVisible();
  const error = (await validation.textContent())?.trim() ?? '';
  const expectedError = variant === 'LONG' ? '临时密码最多支持 128 位' : '临时密码至少需要 12 位';
  await step(1, `Try ${variant.toLowerCase()} temporary password through the real UI`, 'ui',
    { variant, rejected: true, invalidActionBlocked: true, validationErrorVisible: true, error: expectedError, no_reset_success: true },
    { variant, rejected: await confirm.isDisabled(), invalidActionBlocked, validationErrorVisible: await validation.isVisible(), error,
      no_reset_success: await page!.getByTestId('admin.status').count() === 0 });
  await page!.getByRole('dialog', { name: '重置成员密码' }).press('Escape');

  const oldSession = await request('GET', '/v1/me', undefined, bobOld);
  const oldPassword = await request('POST', '/v1/auth/login', { username: 'test-bob', password: BOB_PASSWORD });
  const afterUser = dbOne<{ password_hash: string; credential_version: number; must_change_password: number }>(
    "SELECT password_hash,credential_version,must_change_password FROM users WHERE username='test-bob'");
  await step(2, 'Read owned DB and real service after rejected reset inputs', 'service',
    { old_session: 200, old_password: 200, user_unchanged: true },
    { old_session: oldSession.status, old_password: oldPassword.status,
      user_unchanged: JSON.stringify(afterUser) === JSON.stringify(beforeUser) });

  await step(3, 'Compare successful reset audit count with the before snapshot', 'filesystem',
    { reset_audit_delta: 0 }, { reset_audit_delta: countAudit('password_reset') - beforeAudit });

  await resetBob();
  const revoked = await request('GET', '/v1/me', undefined, bobOld);
  await step(4, 'Use a valid synthetic reset as a positive control', 'service',
    { ui_success: true, old_session: 401, reset_audit_delta: 1 },
    { ui_success: (await page!.getByTestId('admin.status').textContent())?.includes('password_reset') ?? false,
      old_session: revoked.status, reset_audit_delta: countAudit('password_reset') - beforeAudit });
}
test('TC-TM001-ADMIN-02#EMPTY', async () => { await admin02('EMPTY'); });
test('TC-TM001-ADMIN-02#SHORT', async () => { await admin02('SHORT'); });
test('TC-TM001-ADMIN-02#LONG', async () => { await admin02('LONG'); });

test('TC-TM001-ADMIN-03', async () => {
  await launchPeer(); await configure(); await login('test-bob', BOB_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await changePassword(BOB_PASSWORD, 'TEST-ONLY-Bob-New-42!');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const bobOld = peerToken();
  const bobSecond = await apiToken('test-bob', 'TEST-ONLY-Bob-New-42!');
  const bobApp = app!, bobPage = page!;
  let bobClosed = false;
  app = null; page = null; tracing = false;
  try {
    await adminReady();
    const aliceBefore = dbOne<{ is_active: number }>("SELECT is_active FROM users WHERE username='test-alice'");
    await page!.getByTestId('admin.disable.test-bob').click();
    await expect(page!.getByTestId('admin.state.test-bob')).toContainText('已停用');
    await step(1, '管理员界面停用bob并只读核对目标状态', 'ui',
      { disabledUI: true, disabledDB: 0, aliceUnchanged: true },
      { disabledUI: (await page!.getByTestId('admin.state.test-bob').textContent())?.includes('已停用') === true,
        disabledDB: dbOne<{ is_active: number }>("SELECT is_active FROM users WHERE username='test-bob'").is_active,
        aliceUnchanged: dbOne<{ is_active: number }>("SELECT is_active FROM users WHERE username='test-alice'").is_active === aliceBefore.is_active });
    const oldStatuses = await Promise.all([bobOld, bobSecond].map(token => request('GET', '/v1/me', undefined, token)));
    const loginResult = await request('POST', '/v1/auth/login', { username: 'test-bob', password: 'TEST-ONLY-Bob-New-42!' });
    await step(2, '两条旧会话与正确密码均被真实服务拒绝', 'service',
      { bothOld401: true, disabledLogin403: true, disabledCode: 'account_disabled', noBobSessions: true },
      { bothOld401: oldStatuses.every(item => item.status === 401),
        disabledLogin403: loginResult.status === 403, disabledCode: loginResult.body.error?.code,
        noBobSessions: dbOne<{ n: number }>("SELECT count(*) AS n FROM sessions WHERE user_id='00000000-0000-4000-8000-000000000003'").n === 0 });
    await bobPage.getByTestId('session.refresh').click();
    await expect(bobPage.getByTestId('auth.login')).toBeVisible();
    const refreshRejected = await bobPage.getByTestId('session.verified').count() === 0;
    await bobApp.context().tracing.stop({ path: join(output!, 'trace-peer-before-restart.zip') });
    await bobApp.close();
    bobClosed = true;
    await close();
    await launchPeer();
    await expect(page!.getByTestId('auth.login')).toBeVisible();
    await step(3, 'bob App刷新后失去身份，重启也不恢复已停用账号', 'ui',
      { refreshRejected: true, restartLoginVisible: true, noSavedCredential: true,
        noVerifiedIdentity: true },
      { refreshRejected, restartLoginVisible: await page!.getByTestId('auth.login').isVisible(),
        noSavedCredential: !existsSync(peerTokenPath()),
        noVerifiedIdentity: await page!.getByTestId('session.verified').count() === 0 });
    const audit = dbOne<{ actor_id: string; target_id: string }>(
      "SELECT actor_id,target_id FROM audit WHERE action='account_disabled' ORDER BY occurred_at DESC,id DESC LIMIT 1");
    const auditText = JSON.stringify(audit) + readFileSync(required(c.service_log_path, 'service_log_path'), 'utf8');
    await step(4, '只读核对停用审计actor/target且无凭据外泄', 'filesystem',
      { actorTargetCorrect: true, noCredentialInAuditOrLog: true },
      { actorTargetCorrect: audit.actor_id === ADMIN_ID && audit.target_id === BOB_ID,
        noCredentialInAuditOrLog: ![bobOld, bobSecond, 'TEST-ONLY-Bob-New-42!'].some(secret => auditText.includes(secret)) });
  } finally {
    if (!bobClosed) {
      try { await bobApp.context().tracing.stop({ path: join(output!, 'trace-peer-failure.zip') }); } catch { /* prior trace retained */ }
      try { await bobApp.close(); } catch { /* owned runner cleanup */ }
    }
  }
});

test('TC-TM001-ADMIN-01', async () => {
  await launchPeer(); await configure(); await login('test-bob', BOB_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await changePassword(BOB_PASSWORD, 'TEST-ONLY-Bob-New-42!');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const firstBob = peerToken();
  const secondBob = await apiToken('test-bob', 'TEST-ONLY-Bob-New-42!');
  const aliceBefore = dbOne<{ credential_version: number }>("SELECT credential_version FROM users WHERE username='test-alice'");
  await close();
  await adminReady();
  const adminToken = savedToken();
  await resetBob();
  const bobAfter = dbOne<{ id: string; must_change_password: number }>("SELECT id,must_change_password FROM users WHERE username='test-bob'");
  await step(1, '真实管理员界面重置bob且只影响目标UUID', 'ui',
    { targetBob: true, uiReset: true, forcedFlag: 1, aliceUnchanged: true },
    { targetBob: bobAfter.id === BOB_ID,
      uiReset: (await page!.getByTestId('admin.status').textContent())?.includes('password_reset') === true,
      forcedFlag: bobAfter.must_change_password,
      aliceUnchanged: dbOne<{ credential_version: number }>("SELECT credential_version FROM users WHERE username='test-alice'").credential_version === aliceBefore.credential_version });
  const priorStatuses = await Promise.all([firstBob, secondBob].map(token => request('GET', '/v1/me', undefined, token)));
  const passwordStatus = await request('POST', '/v1/auth/login', { username: 'test-bob', password: 'TEST-ONLY-Bob-New-42!' });
  await step(2, '两条旧会话与原密码均被真实服务撤销', 'service',
    { bothOld401: true, oldPassword401: true, remainingBobSessions: 0 },
    { bothOld401: priorStatuses.every(item => item.status === 401), oldPassword401: passwordStatus.status === 401,
      remainingBobSessions: dbOne<{ n: number }>("SELECT count(*) AS n FROM sessions WHERE user_id='00000000-0000-4000-8000-000000000003'").n });
  await close(); await launchPeer();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await step(3, '保存旧token的bob App重启后不能恢复登录', 'ui',
    { returnedToLogin: true, oldCredentialRemoved: true, noCachedIdentity: true },
    { returnedToLogin: await page!.getByTestId('auth.login').isVisible(),
      oldCredentialRemoved: !existsSync(peerTokenPath()),
      noCachedIdentity: await page!.getByTestId('session.verified').count() === 0 });
  await login('test-bob', RESET_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  const forced = await page!.getByTestId('password.new').isVisible();
  const adminHidden = await page!.getByTestId('admin.accounts').count() === 0;
  await changePassword(RESET_PASSWORD, 'TEST-ONLY-Bob-Final-42!');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(4, 'UI用临时密码强制改密后才恢复bob身份', 'ui',
    { forced: true, adminHidden: true, identity: 'test-bob', forcedCleared: true },
    { forced, adminHidden, identity: await page!.getByTestId('session.username').textContent(),
      forcedCleared: dbOne<{ must_change_password: number }>("SELECT must_change_password FROM users WHERE username='test-bob'").must_change_password === 0 });
  const audit = dbOne<{ actor_id: string; target_id: string }>(
    "SELECT actor_id,target_id FROM audit WHERE action='password_reset' ORDER BY occurred_at DESC,id DESC LIMIT 1");
  await step(5, '读只读审计并核对其他用户与管理员原会话仍有效', 'service',
    { actorTargetCorrect: true, aliceUnchanged: true, adminStill200: true, bobNew200: true },
    { actorTargetCorrect: audit.actor_id === ADMIN_ID && audit.target_id === BOB_ID,
      aliceUnchanged: dbOne<{ credential_version: number }>("SELECT credential_version FROM users WHERE username='test-alice'").credential_version === aliceBefore.credential_version,
      adminStill200: (await request('GET', '/v1/me', undefined, adminToken)).status === 200,
      bobNew200: (await request('GET', '/v1/me', undefined, peerToken())).status === 200 });
});

test('TC-TM001-ADMIN-05#SINGLE', async () => {
  if (c.fixture_kind !== 'auth_accounts') throw new Error('Single-admin D-A42 fixture is required');
  await adminReady();
  const first = savedToken();
  const selfButton = page!.getByTestId('admin.disable.test-admin');
  const offered = await selfButton.isVisible();
  await selfButton.click();
  await expect(page!.getByTestId('auth.error')).toContainText('admin_protected');
  const selfApi = await request('POST', `/v1/admin/users/${ADMIN_ID}/disable`, undefined, first);
  await step(1, '管理员UI及真实API都不能成功停用自身', 'ui',
    { uiControlVisible: true, uiRejected: true, apiStatus: 409, apiCode: 'admin_protected' },
    { uiControlVisible: offered,
      uiRejected: (await page!.getByTestId('auth.error').textContent())?.includes('admin_protected') === true,
      apiStatus: selfApi.status, apiCode: selfApi.body.error?.code });
  const before = dbOne<{ n: number }>("SELECT count(*) AS n FROM users WHERE role='admin' AND is_active=1");
  await step(2, '只读核对拒绝后仍有活动管理员和有效当前会话', 'filesystem',
    { activeAdmins: 1, firstSession200: true, selfDisableAudit: 0 },
    { activeAdmins: before.n,
      firstSession200: (await request('GET', '/v1/me', undefined, first)).status === 200,
      selfDisableAudit: dbOne<{ n: number }>("SELECT count(*) AS n FROM audit WHERE action='account_disabled' AND actor_id=target_id").n });
});

test('TC-TM001-ADMIN-05#CONCURRENT', async () => {
  if (c.fixture_kind !== 'two_admin_accounts') throw new Error('Two-admin isolated SQL fixture is required');
  await adminReady();
  const first = savedToken();
  const initialSecond = await apiToken('test-admin-two', 'TEST-ONLY-admin-two-42!');
  const changeSecond = await request('POST', '/v1/auth/change-password',
    { current_password: 'TEST-ONLY-admin-two-42!', new_password: 'TEST-ONLY-Admin-Two-New-42!' }, initialSecond);
  if (changeSecond.status !== 200 || typeof changeSecond.body.access_token !== 'string')
    throw new Error('Second seeded administrator could not finish forced change through real service');
  const second = changeSecond.body.access_token as string;
  const secondId = '00000000-0000-4000-8000-000000000006';
  const [firstResult, secondResult] = await Promise.all([
    request('POST', `/v1/admin/users/${secondId}/disable`, undefined, first),
    request('POST', `/v1/admin/users/${ADMIN_ID}/disable`, undefined, second),
  ]);
  await step(3, '两个真实管理员token同时向服务申请停用对方', 'service',
    { oneSucceeded: true, oneRejected: true, activeAdmins: 1 },
    { oneSucceeded: [firstResult.status, secondResult.status].filter(status => status === 200).length === 1,
      oneRejected: [firstResult, secondResult].filter(item =>
        (item.status === 401 && item.body.error?.code === 'invalid_session') ||
        (item.status === 409 && item.body.error?.code === 'admin_protected')).length === 1,
      activeAdmins: dbOne<{ n: number }>("SELECT count(*) AS n FROM users WHERE role='admin' AND is_active=1").n });
  const remaining = dbOne<{ username: string }>("SELECT username FROM users WHERE role='admin' AND is_active=1");
  const password = remaining.username === 'test-admin' ? NEW_PASSWORD : 'TEST-ONLY-Admin-Two-New-42!';
  const fresh = await request('POST', '/v1/auth/login', { username: remaining.username, password });
  const audits = dbRows<{ actor_id: string; target_id: string }>("SELECT actor_id,target_id FROM audit WHERE action='account_disabled'");
  const firstMe = await request('GET', '/v1/me', undefined, first);
  const secondMe = await request('GET', '/v1/me', undefined, second);
  await step(4, '核对最终单一活动管理员仍能登录且审计只记录已提交事务', 'service',
    { remainingAdminLogin200: true, exactlyOneCommittedAudit: true, remainingAdminCount: 1,
      auditMatchesSuccess: true, winningSession200: true, losingSession401: true },
    { remainingAdminLogin200: fresh.status === 200,
      exactlyOneCommittedAudit: audits.length === 1,
      remainingAdminCount: dbOne<{ n: number }>("SELECT count(*) AS n FROM users WHERE role='admin' AND is_active=1").n,
      auditMatchesSuccess: audits.length === 1 && (
        firstResult.status === 200 ? audits[0]!.actor_id === ADMIN_ID && audits[0]!.target_id === secondId :
          audits[0]!.actor_id === secondId && audits[0]!.target_id === ADMIN_ID),
      winningSession200: firstResult.status === 200 ? firstMe.status === 200 : secondMe.status === 200,
      losingSession401: firstResult.status === 200 ? secondMe.status === 401 : firstMe.status === 401 });
});

test('TC-TM001-ADMIN-04', async () => {
  const bobOld = await apiToken('test-bob', BOB_PASSWORD);
  await adminReady();
  await page!.getByTestId('admin.disable.test-bob').click();
  await expect(page!.getByTestId('admin.state.test-bob')).toContainText('已停用');
  await page!.getByTestId('admin.enable.test-bob').click();
  await expect(page!.getByTestId('admin.state.test-bob')).toContainText('已启用');
  const enabled = dbOne<{ is_active: number }>("SELECT is_active FROM users WHERE username='test-bob'");
  await step(1, 'Reenable the member through the real administrator UI after a real disable', 'ui',
    { ui_enabled: true, db_active: 1 },
    { ui_enabled: (await page!.getByTestId('admin.state.test-bob').textContent())?.includes('已启用') ?? false,
      db_active: enabled.is_active });

  const old = await request('GET', '/v1/me', undefined, bobOld);
  await step(2, 'Request real identity with the pre-disable session', 'service',
    { old_status: 401 }, { old_status: old.status });

  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await login('test-bob', BOB_PASSWORD);
  await expect(page!.getByTestId('password.new')).toBeVisible();
  const forced = await page!.getByTestId('password.new').isVisible();
  await changePassword(BOB_PASSWORD, 'TEST-ONLY-Bob-New-42!');
  const newest = savedToken();
  const newMe = await request('GET', '/v1/me', undefined, newest);
  await step(3, 'Login anew through the App and honor remaining first-password requirement', 'ui',
    { forced_change: true, new_status: 200, new_identity: 'test-bob' },
    { forced_change: forced, new_status: newMe.status,
      new_identity: await page!.getByTestId('session.username').textContent() });

  const action = dbOne<{ actor_id: string; target_id: string }>(
    "SELECT actor_id,target_id FROM audit WHERE action='account_enabled' ORDER BY occurred_at DESC,id DESC LIMIT 1");
  const oldAgain = await request('GET', '/v1/me', undefined, bobOld);
  const current = await request('GET', '/v1/me', undefined, newest);
  await step(4, 'Read enabled-account audit and compare old and new sessions', 'service',
    { correct_actor_target: true, old_status: 401, new_status: 200 },
    { correct_actor_target: action.actor_id === ADMIN_ID && action.target_id === BOB_ID,
      old_status: oldAgain.status, new_status: current.status });
});

test('TC-TM001-ADMIN-06', async () => {
  await adminReady();
  const adminToken = savedToken();
  const started = Date.now();
  await resetBob();
  await page!.getByTestId('admin.disable.test-bob').click();
  await expect(page!.getByTestId('admin.state.test-bob')).toContainText('已停用');
  await page!.getByTestId('admin.enable.test-bob').click();
  await expect(page!.getByTestId('admin.state.test-bob')).toContainText('已启用');
  const ended = Date.now();
  await page!.getByTestId('admin.audit').click();
  for (const action of ['password_reset', 'account_disabled', 'account_enabled'])
    await expect(page!.getByTestId(`audit.action.${action}`).first()).toBeVisible();
  await step(1, 'Perform reset, disable, and enable; then open real administrator audit UI', 'ui',
    { three_actions_visible: true },
    { three_actions_visible: (await Promise.all(['password_reset', 'account_disabled', 'account_enabled']
      .map(action => page!.getByTestId(`audit.action.${action}`).first().isVisible()))).every(Boolean) });

  const auditResponse = await request('GET', '/v1/admin/audit', undefined, adminToken);
  const actions = new Set(['password_reset', 'account_disabled', 'account_enabled']);
  const apiRows = (auditResponse.body.events as Array<{ action: string; actor_id: string; target_id: string; occurred_at: string }>).
    filter(row => actions.has(row.action) && row.target_id === BOB_ID);
  const dbAudit = dbRows<{ action: string; actor_id: string; target_id: string; occurred_at: number }>(
    "SELECT action,actor_id,target_id,occurred_at FROM audit WHERE target_id='00000000-0000-4000-8000-000000000003' AND action IN ('password_reset','account_disabled','account_enabled')");
  const lower = Math.floor(started / 1000) - 1, upper = Math.floor(ended / 1000) + 1;
  await step(2, 'Cross-check authenticated audit API and read-only DB actor/target/time', 'service',
    { status: 200, three_db_actions: true, three_api_actions: true, correct_identity: true, time_bounded: true },
    { status: auditResponse.status,
      three_db_actions: actions.size === dbAudit.length && dbAudit.every(row => actions.has(row.action)),
      three_api_actions: actions.size === apiRows.length && apiRows.every(row => actions.has(row.action)),
      correct_identity: dbAudit.every(row => row.actor_id === ADMIN_ID && row.target_id === BOB_ID)
        && apiRows.every(row => row.actor_id === ADMIN_ID && row.target_id === BOB_ID),
      time_bounded: dbAudit.every(row => row.occurred_at >= lower && row.occurred_at <= upper) });

  const inspected = JSON.stringify(auditResponse.body) + '\n' + await page!.locator('body').innerText() + '\n'
    + (c.service_log_path ? readFileSync(c.service_log_path, 'utf8') : '');
  await step(3, 'Search only in memory for synthetic credentials in audit, UI, and owned service log', 'service',
    { contains_password_or_token: false },
    { contains_password_or_token: [ADMIN_PASSWORD, NEW_PASSWORD, RESET_PASSWORD, BOB_PASSWORD, adminToken]
      .some(secret => inspected.includes(secret)) });

  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await login('test-bob', RESET_PASSWORD);
  await changePassword(RESET_PASSWORD, 'TEST-ONLY-Bob-New-42!');
  const memberToken = savedToken();
  const forbidden = await request('GET', '/v1/admin/audit', undefined, memberToken);
  await step(4, 'Authenticate as member and verify API and UI both deny audit access', 'ui',
    { api_status: 403, audit_button_absent: true },
    { api_status: forbidden.status, audit_button_absent: await page!.getByTestId('admin.audit').count() === 0 });
});

test('TC-TM001-BOOTSTRAP-01', async () => {
  const original = required(c.bootstrap_original_path, 'bootstrap_original_path');
  const comparison = required(c.comparison_database_path, 'comparison_database_path');
  const sqlPath = required(c.bootstrap_seed_sql_path, 'bootstrap_seed_sql_path');
  if (c.bootstrap_exit_code === undefined) throw new Error('Actual bootstrap exit status is not provided');
  const sql = readFileSync(sqlPath, 'utf8');
  await step(1, 'Inspect actual isolated first-boot exit and generated SQL without exposing a password hash', 'filesystem',
    { exit_code: 0, sql_present: true, no_plaintext_default: true, hashed_password_statement: true },
    { exit_code: c.bootstrap_exit_code, sql_present: sql.length > 100,
      no_plaintext_default: !sql.includes('123456'), hashed_password_statement: sql.includes('$argon2') });

  const schema = dbOne<{ version_num: string }>('SELECT version_num FROM alembic_version', original);
  const owner = dbOne<{ environment: string }>('SELECT environment FROM tokenmeter_seed_owner', original);
  const productionUsers = dbRows<{ id: string; username: string; role: string; is_active: number; must_change_password: number }>(
    'SELECT id,username,role,is_active,must_change_password FROM users ORDER BY username', original);
  await step(2, 'Read production-style schema, owner, and preloaded identities without reading secrets', 'filesystem',
    { schema: '0001', owner: 'production', users: [{ id_suffix: '0005', username: 'admin', role: 'admin', active: 1, forced: 1 }] },
    { schema: schema.version_num, owner: owner.environment,
      users: productionUsers.map(user => ({ id_suffix: user.id.slice(-4), username: user.username, role: user.role,
        active: user.is_active, forced: user.must_change_password })) });

  const testOwner = dbOne<{ environment: string }>('SELECT environment FROM tokenmeter_seed_owner', comparison);
  const testUsers = dbRows<{ username: string }>('SELECT username FROM users ORDER BY username', comparison);
  await step(3, 'Compare separately generated synthetic test and production-style SQLite files', 'filesystem',
    { paths_distinct: true, owners_distinct: true, test_owner: 'test', test_users: 4, no_test_user_in_production: true },
    { paths_distinct: original !== comparison, owners_distinct: owner.environment !== testOwner.environment,
      test_owner: testOwner.environment, test_users: testUsers.length,
      no_test_user_in_production: productionUsers.every(user => !user.username.startsWith('test-')) });

  await launch(); await configure(); await login('admin', '123456');
  await expect(page!.getByTestId('password.new')).toBeVisible();
  const secondLogin = await request('POST', '/v1/auth/login', { username: 'admin', password: '123456' });
  await step(4, 'Authenticate against the real restored SQLite service using the initial synthetic administrator', 'service',
    { second_login_status: 200, forced_change: true, username: 'admin' },
    { second_login_status: secondLogin.status,
      forced_change: await page!.getByTestId('password.new').isVisible(),
      username: await page!.getByTestId('session.username').textContent() });
});

test('TC-TM001-BOOTSTRAP-02', async () => {
  await launch(); await configure(); await login('admin', '123456');
  await expect(page!.getByTestId('password.new')).toBeVisible();
  const initialToken = savedToken();
  await step(1, 'Login with the seeded administrator through the real App UI', 'ui',
    { forced_change: true, admin_panel_absent: true, identity: 'admin' },
    { forced_change: await page!.getByTestId('password.new').isVisible(),
      admin_panel_absent: await page!.getByTestId('admin.accounts').count() === 0,
      identity: await page!.getByTestId('session.username').textContent() });

  const preUsers = await request('GET', '/v1/admin/users', undefined, initialToken);
  const preAudit = await request('GET', '/v1/admin/audit', undefined, initialToken);
  await step(2, 'Check both privileged endpoints using the real pre-change session', 'service',
    { users_status: 403, audit_status: 403, both_require_password_change: true },
    { users_status: preUsers.status, audit_status: preAudit.status,
      both_require_password_change: preUsers.body.error?.code === 'password_change_required'
        && preAudit.body.error?.code === 'password_change_required' });

  await changePassword('123456', PRODUCTION_NEW_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const changed = dbOne<{ must_change_password: number }>("SELECT must_change_password FROM users WHERE username='admin'");
  await step(3, 'Change initial password in App and confirm administrator controls become available', 'ui',
    { verified: true, admin_panel_visible: true, forced_flag: 0 },
    { verified: await page!.getByTestId('session.verified').isVisible(),
      admin_panel_visible: await page!.getByTestId('admin.accounts').isVisible(), forced_flag: changed.must_change_password });

  const oldMe = await request('GET', '/v1/me', undefined, initialToken);
  const oldPassword = await request('POST', '/v1/auth/login', { username: 'admin', password: '123456' });
  await page!.getByTestId('admin.accounts').click();
  const names = await page!.locator('[data-testid^="admin.state."]').evaluateAll(nodes =>
    nodes.map(node => node.getAttribute('data-testid')?.slice('admin.state.'.length)));
  await step(4, 'Reject initial session and password; list only the seeded administrator', 'service',
    { old_session: 401, old_password: 401, names: ['admin'] },
    { old_session: oldMe.status, old_password: oldPassword.status, names });

  await restart();
  await expect(page!.getByTestId('session.username')).toHaveText('admin');
  const restored = await page!.getByTestId('session.verified').isVisible();
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
  await login('admin', PRODUCTION_NEW_PASSWORD);
  await expect(page!.getByTestId('session.username')).toHaveText('admin');
  await step(5, 'Restart and relogin with the new administrator password', 'ui',
    { restored_verified: true, relogin_verified: true, forced_form_absent: true },
    { restored_verified: restored, relogin_verified: await page!.getByTestId('session.verified').isVisible(),
      forced_form_absent: await page!.getByTestId('password.new').count() === 0 });
});

test('TC-TM001-BOOTSTRAP-03', async () => {
  const root = required(c.bootstrap_root, 'bootstrap_root');
  const python = required(c.python_executable, 'python_executable');
  const seed = required(c.bootstrap_seed_sql_path, 'bootstrap_seed_sql_path');
  const comparison = required(c.comparison_database_path, 'comparison_database_path');
  if (c.database_path !== c.bootstrap_original_path) throw new Error('This TC must use the original owned production-style SQLite');
  if (!existsSync(python)) throw new Error('Runner-provided private Python executable is missing');
  const runPython = (code: string, args: string[], input?: string): number => {
    try { execFileSync(python, ['-c', code, ...args], { cwd: join(process.cwd(), '../..'), input,
      encoding: 'utf8', timeout: 60_000, maxBuffer: 1024 * 1024 }); return 0; }
    catch (error) {
      if (typeof (error as { status?: unknown }).status !== 'number') throw error;
      return (error as { status: number }).status;
    }
  };
  const snapshot = (database = c.database_path): string => JSON.stringify({
    users: dbRows<{ id: string; username: string; password_hash: string; credential_version: number; must_change_password: number }>(
      'SELECT id,username,password_hash,credential_version,must_change_password FROM users ORDER BY id', database),
    audit: dbRows<{ action: string; actor_id: string | null; target_id: string | null }>(
      "SELECT action,actor_id,target_id FROM audit WHERE action <> 'login' ORDER BY id", database),
  });
  await launch(); await configure(); await login('admin', '123456');
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await changePassword('123456', PRODUCTION_NEW_PASSWORD);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const beforeRestart = snapshot();
  const serviceRestart = await restartBackend();
  await restart();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const oldPassword = await request('POST', '/v1/auth/login', { username: 'admin', password: '123456' });
  const newPassword = await request('POST', '/v1/auth/login', { username: 'admin', password: PRODUCTION_NEW_PASSWORD });
  await step(1, '原生产风格库重启真实服务和App后不重置管理员改密状态', 'service',
    { ownedRestart: true, dataUnchanged: true, oldPassword401: true,
      newPassword200: true, restoredUI: true },
    { ownedRestart: serviceRestart.old_pid !== serviceRestart.new_pid && serviceRestart.same_origin && serviceRestart.health === 200,
      dataUnchanged: snapshot() === beforeRestart, oldPassword401: oldPassword.status === 401,
      newPassword200: newPassword.status === 200,
      restoredUI: await page!.getByTestId('session.verified').isVisible() });

  const beforeRepeat = snapshot();
  const initializeExit = runPython('from pathlib import Path; from scripts.bootstrap_sqlite import initialize_production; import sys; initialize_production(Path(sys.argv[1]))', [root]);
  await step(2, '在已存在的owned production.db再次调用真实首次初始化程序', 'filesystem',
    { rejected: true, exactRowsRetained: true },
    { rejected: initializeExit !== 0, exactRowsRetained: snapshot() === beforeRepeat });

  const replay = 'import sqlite3,sys; from pathlib import Path; db=sqlite3.connect(sys.argv[1]); db.executescript(Path(sys.argv[2]).read_text()); db.close()';
  const beforeProductionReplay = snapshot();
  const beforeWrongEnvironment = snapshot(comparison);
  const productionExit = runPython(replay, [c.database_path, seed]);
  const wrongEnvironmentExit = runPython(replay, [comparison, seed]);
  await step(3, '对非空生产库和错误environment测试库分别重放首次seed.sql', 'filesystem',
    { productionRejected: true, wrongEnvironmentRejected: true,
      productionRollback: true, comparisonRollback: true },
    { productionRejected: productionExit !== 0, wrongEnvironmentRejected: wrongEnvironmentExit !== 0,
      productionRollback: snapshot() === beforeProductionReplay,
      comparisonRollback: snapshot(comparison) === beforeWrongEnvironment });

  const extraId = '00000000-0000-4000-8000-000000000007';
  const provisionInput = JSON.stringify([{ id: extraId, username: 'test-extra',
    password: 'TEST-ONLY-Extra-42!', role: 'member', is_active: true }]);
  const provisionExit = runPython(
    'import json,sys; from server.tokenmeter_server.provision import provision; assert provision("sqlite:///"+sys.argv[1],json.load(sys.stdin))==1',
    [c.database_path], provisionInput);
  if (provisionExit !== 0) throw new Error('Owned extra-member provisioning program failed');
  const extraBefore = snapshot();
  const secondRestart = await restartBackend();
  const rejectAgain = runPython('from pathlib import Path; from scripts.bootstrap_sqlite import initialize_production; import sys; initialize_production(Path(sys.argv[1]))', [root]);
  await restart();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const memberLogin = await request('POST', '/v1/auth/login', { username: 'test-extra', password: 'TEST-ONLY-Extra-42!' });
  const adminLogin = await request('POST', '/v1/auth/login', { username: 'admin', password: PRODUCTION_NEW_PASSWORD });
  await step(4, '新增合成成员后再重启和拒绝首建，所有实际账号保持', 'service',
    { provisionedMember: true, repeatRejected: true, noOverwrite: true,
      memberLogin200: true, changedAdmin200: true, ownedRestart: true },
    { provisionedMember: dbOne<{ id: string }>("SELECT id FROM users WHERE username='test-extra'").id === extraId,
      repeatRejected: rejectAgain !== 0, noOverwrite: snapshot() === extraBefore,
      memberLogin200: memberLogin.status === 200, changedAdmin200: adminLogin.status === 200,
      ownedRestart: secondRestart.old_pid !== secondRestart.new_pid && secondRestart.health === 200 });
});

test('TC-TM001-BOOTSTRAP-04', async () => {
  const original = required(c.bootstrap_original_path, 'bootstrap_original_path');
  const backup = required(c.bootstrap_backup_path, 'bootstrap_backup_path');
  const restored = required(c.bootstrap_restored_path, 'bootstrap_restored_path');
  const beforeOriginal = digestFile(original), beforeBackup = digestFile(backup);
  await step(1, 'Use three distinct owned paths produced by actual SQLite backup and restore', 'filesystem',
    { distinct_paths: true, three_files: true },
    { distinct_paths: new Set([original, backup, restored]).size === 3,
      three_files: [original, backup, restored].every(path => existsSync(path) && lstatSync(path).isFile()) });

  const tables = ['alembic_version', 'tokenmeter_seed_owner', 'users', 'sessions', 'audit', 'login_buckets'];
  const snapshots = [backup, restored].map(database => {
    const handle = new DatabaseSync(database, { readOnly: true });
    try {
      const integrity = (handle.prepare('PRAGMA integrity_check').get() as { integrity_check: string }).integrity_check;
      const names = (handle.prepare("SELECT name FROM sqlite_master WHERE type='table'").all() as Array<{ name: string }>).
        map(row => row.name);
      const content = tables.map(table => JSON.stringify(handle.prepare(`SELECT * FROM ${table} ORDER BY rowid`).all()));
      return { integrity, complete: tables.every(table => names.includes(table)), content };
    } finally { handle.close(); }
  });
  const schema = dbOne<{ version_num: string }>('SELECT version_num FROM alembic_version', restored);
  await step(2, 'Independently read backup and restored schemas and rows without logging sensitive columns', 'filesystem',
    { both_integrity_ok: true, required_tables: true, same_rows: true, schema: '0001', sessions_empty: true },
    { both_integrity_ok: snapshots.every(item => item.integrity === 'ok'),
      required_tables: snapshots.every(item => item.complete),
      same_rows: JSON.stringify(snapshots[0]?.content) === JSON.stringify(snapshots[1]?.content),
      schema: schema.version_num,
      sessions_empty: dbOne<{ n: number }>('SELECT count(*) AS n FROM sessions', restored).n === 0 });

  await launch(); await configure(); await login('admin', '123456');
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await changePassword('123456', PRODUCTION_NEW_PASSWORD);
  await expect(page!.getByTestId('session.username')).toHaveText('admin');
  const running = dbOne<{ must_change_password: number }>("SELECT must_change_password FROM users WHERE username='admin'", restored);
  const archived = dbOne<{ must_change_password: number }>("SELECT must_change_password FROM users WHERE username='admin'", backup);
  await step(3, 'Connect the DMG-installed App to the service bound to restored SQLite and change password', 'service',
    { identity: 'admin', running_forced_flag: 0, backup_forced_flag: 1 },
    { identity: await page!.getByTestId('session.username').textContent(),
      running_forced_flag: running.must_change_password, backup_forced_flag: archived.must_change_password });

  const archiveUnchanged = digestFile(original) === beforeOriginal && digestFile(backup) === beforeBackup;
  const runningAfter = dbOne<{ must_change_password: number }>("SELECT must_change_password FROM users WHERE username='admin'", restored);
  await step(4, 'Compare archived copies with the live restored database after App writes', 'filesystem',
    { archived_bytes_unchanged: true, running_changed: true },
    { archived_bytes_unchanged: archiveUnchanged, running_changed: runningAfter.must_change_password === 0 });

  const reread = [backup, restored].every(path =>
    dbOne<{ integrity_check: string }>('PRAGMA integrity_check', path).integrity_check === 'ok');
  await step(5, 'Reread retained backup and restored originals for independent gate verification', 'filesystem',
    { archive_digest_matches_initial: true, both_readable: true },
    { archive_digest_matches_initial: digestFile(backup) === beforeBackup, both_readable: reread });
});
