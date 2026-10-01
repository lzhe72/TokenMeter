/** TM-002: one frozen product TC/variant per installed Electron invocation. */
import { test, expect, _electron as electron, type ElectronApplication, type Page } from '@playwright/test';
import { createHash, createHmac } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { appendFileSync, chmodSync, copyFileSync, existsSync, lstatSync, readFileSync,
  readdirSync, renameSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

type Tool = 'codex' | 'claude_code';
type Candidate = {relative_name: string; bytes: number; mtime_utc: string; sha256?: string; root?: string};
type Expected = {case_id: string; tool: Tool; preview: {candidates: Candidate[]; complete: boolean;
  incomplete_reason: string | null}; files: Candidate[]; symlinks: Array<{relative_name: string; kind: string}>};
type Context = {run_id: string; candidate_sha: string; case_id: string; app_path: string; profile_path: string;
  service_url: string; service_control_url: string; service_control_token: string; database_path: string;
  secondary_service_url?: string | null; secondary_database_path?: string | null;
  identity_control_url?: string | null; identity_control_token?: string | null;
  source_a: string; source_b: string; source_expected_path: string;
  source_audit_nonce_hex: string; source_audit_path: string; picker_driver_path: string;
  source_fixture_script: string; source_owner_id: string; python_executable: string};
type AuditEvent = {schema_version: number; sequence: number; operation: string; decision: string;
  reason?: string; tool: Tool; generation: number; root_digest?: string; entry_digest?: string;
  inspected_entries?: number; candidate_count?: number};

const input = process.env.TM_E2E_CONTEXT;
const output = process.env.TM_E2E_CASE_OUTPUT;
if (!input || !output) throw new Error('Owned TM-002 context and output are required');
const c = JSON.parse(readFileSync(input, 'utf8')) as Context;
const expected = JSON.parse(readFileSync(c.source_expected_path, 'utf8')) as Expected;
const executable = join(c.app_path, 'Contents/MacOS/TokenMeter');
const eventsPath = join(output, 'events.jsonl');
const ALICE_PASSWORD = 'TEST-ONLY-alice-42!';
const BOB_PASSWORD = 'TEST-ONLY-bob-42!';
const CHANGED_PASSWORD = 'TEST-ONLY-Changed-42!';
const A1 = 'sessions/2026/10/01/a-01.jsonl';
const A2 = 'sessions/2026/10/01/a-02.jsonl';
const AN = 'sessions/2026/10/01/a-new.jsonl';
const B1 = 'sessions/2026/10/01/b-01.jsonl';
let app: ElectronApplication | null = null;
let page: Page | null = null;
let traceOpen = false;
let traceIndex = 0;
let pickerIndex = 0;

function sha(data: string | Buffer): string { return createHash('sha256').update(data).digest('hex'); }
function sourcePath(label: 'A' | 'B'): string { return label === 'A' ? c.source_a : c.source_b; }
function hmac(value: string): string {
  return createHmac('sha256', Buffer.from(c.source_audit_nonce_hex, 'hex')).update(value).digest('hex');
}
function rootDigest(label: 'A' | 'B'): string {
  let item;
  try { item = statSync(sourcePath(label), {bigint: true}); }
  catch { throw new Error('Owned synthetic source root is absent'); }
  return hmac(`${item.dev}:${item.ino}`);
}
function ownedEnv(): Record<string, string> {
  return Object.fromEntries(Object.entries(process.env)
    .filter((entry): entry is [string, string] => entry[1] !== undefined)
    .filter(([key]) => !key.startsWith('TM_E2E_') && !key.startsWith('TM_INTERNAL_') &&
      !key.includes('TOKEN') && !key.includes('SIGNING')));
}
async function launch(): Promise<void> {
  if (!existsSync(executable)) throw new Error('Final installed App executable is absent');
  app = await electron.launch({executablePath: executable,
    args: [`--user-data-dir=${c.profile_path}`, `--diagnostic-source-audit-nonce=${c.source_audit_nonce_hex}`],
    env: ownedEnv(), chromiumSandbox: true, timeout: 60_000});
  page = await app.firstWindow();
  await expect(page.getByTestId('app.build')).toBeVisible();
  await app.context().tracing.start({screenshots: true, snapshots: true, sources: false});
  traceOpen = true;
}
async function close(): Promise<void> {
  if (!app) return;
  if (traceOpen) {
    await app.context().tracing.stop({path: join(output!, `trace-${String(++traceIndex).padStart(2, '0')}.zip`)});
    traceOpen = false;
  }
  await app.close();
  app = null; page = null;
}
async function restart(): Promise<void> { await close(); await launch(); }
async function configure(url = c.service_url): Promise<void> {
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(url);
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('auth.server')).toHaveValue(url);
}
async function login(username: string, password: string, initial: boolean): Promise<void> {
  await page!.getByTestId('auth.username').fill(username);
  await page!.getByTestId('auth.password').fill(password);
  await page!.getByTestId('auth.login').click();
  if (initial) {
    await expect(page!.getByTestId('password.new')).toBeVisible();
    await page!.getByTestId('password.current').fill(password);
    await page!.getByTestId('password.new').fill(CHANGED_PASSWORD);
    await page!.getByTestId('password.confirm').fill(CHANGED_PASSWORD);
    await page!.getByTestId('password.submit').click();
  }
  await expect(page!.getByTestId('session.username')).toHaveText(username);
  await expect(page!.getByTestId('session.verified')).toBeVisible();
}
async function aliceReady(): Promise<void> {
  await launch(); await configure(); await login('test-alice', ALICE_PASSWORD, true);
}
async function logout(): Promise<void> {
  await page!.getByTestId('session.logout').click();
  await expect(page!.getByTestId('auth.login')).toBeVisible();
}
function testId(name: string, tool: Tool = 'codex'): string { return `source.${name}.${tool}`; }
async function sourceState(tool: Tool = 'codex'): Promise<string> {
  const value = await page!.getByTestId(testId('status', tool)).getAttribute('data-state');
  if (!value) throw new Error('Product source state attribute is absent');
  return value;
}
async function consent(collect: boolean, sync: boolean, tool: Tool = 'codex'): Promise<void> {
  const collectInput = page!.getByTestId(testId('collect', tool));
  const syncInput = page!.getByTestId(testId('sync', tool));
  if (collect) await collectInput.check(); else await collectInput.uncheck();
  if (sync) await syncInput.check(); else await syncInput.uncheck();
  await expect(collectInput).toBeChecked({checked: collect});
  await expect(syncInput).toBeChecked({checked: sync});
}
async function checkConsent(collect: boolean, sync: boolean, tool: Tool = 'codex'): Promise<boolean> {
  return (await page!.getByTestId(testId('collect', tool)).isChecked()) === collect &&
    (await page!.getByTestId(testId('sync', tool)).isChecked()) === sync;
}
async function openPicker(tool: Tool = 'codex'): Promise<void> {
  const opened = readAudit().filter(item => item.operation === 'picker_open').length;
  await page!.getByTestId(testId('choose', tool)).click();
  await expect.poll(() => readAudit().filter(item => item.operation === 'picker_open').length).toBe(opened + 1);
}
async function finishPickerSelect(label: 'A' | 'B', tool: Tool = 'codex'):
  Promise<{operation: string; selection_label: string}> {
  const evidenceFile = join(output!, `picker-${String(++pickerIndex).padStart(2, '0')}.json`);
  try {
    execFileSync('swift', [c.picker_driver_path, 'select', '--pid', String(app!.process().pid),
      '--path', sourcePath(label), '--event', evidenceFile], {timeout: 60_000, stdio: 'pipe'});
  } catch { throw new Error('Real native picker selection failed; private command omitted'); }
  const event = JSON.parse(readFileSync(evidenceFile, 'utf8')) as {operation: string;
    selection_label: string; selection_path_sha256: string; real_ax_action: boolean};
  expect(event).toMatchObject({operation: 'select', selection_label: label, real_ax_action: true,
    selection_path_sha256: sha(sourcePath(label))});
  await expect.poll(() => readAudit().filter(item => item.operation === 'picker_result').length).toBe(pickerIndex);
  const appResult = readAudit().filter(item => item.operation === 'picker_result').at(-1);
  expect(appResult).toMatchObject({reason: 'selected', tool, root_digest: rootDigest(label)});
  await expect(page!.getByTestId(testId('pending', tool))).toBeVisible();
  return event;
}
async function choose(label: 'A' | 'B', tool: Tool = 'codex'):
  Promise<{operation: string; selection_label: string}> {
  await openPicker(tool);
  return finishPickerSelect(label, tool);
}
async function finishPickerCancel(): Promise<void> {
  const evidenceFile = join(output!, `picker-${String(++pickerIndex).padStart(2, '0')}.json`);
  try {
    execFileSync('swift', [c.picker_driver_path, 'cancel', '--pid', String(app!.process().pid),
      '--event', evidenceFile], {timeout: 60_000, stdio: 'pipe'});
  } catch { throw new Error('Real native picker cancellation failed; private command omitted'); }
  const event = JSON.parse(readFileSync(evidenceFile, 'utf8')) as {operation: string; real_ax_action: boolean};
  expect(event).toMatchObject({operation: 'cancel', real_ax_action: true});
  await expect.poll(() => readAudit().filter(item => item.operation === 'picker_result').length).toBe(pickerIndex);
  const appResult = readAudit().filter(item => item.operation === 'picker_result').at(-1);
  expect(appResult).toMatchObject({reason: 'canceled', root_digest: null});
}
async function cancelPicker(tool: Tool = 'codex'): Promise<void> {
  await openPicker(tool);
  await finishPickerCancel();
}
async function confirm(collect = true, sync = false, tool: Tool = 'codex'): Promise<void> {
  await consent(collect, sync, tool);
  await page!.getByTestId(testId('confirm', tool)).click();
  await expect(page!.getByTestId(testId('confirmed', tool))).toBeVisible();
  await expect.poll(() => sourceState(tool)).toBe(collect ? 'confirmed_enabled' : 'confirmed_paused');
}
async function chooseAndConfirm(label: 'A' | 'B' = 'A', collect = true,
                                sync = false, tool: Tool = 'codex'): Promise<void> {
  await choose(label, tool); await confirm(collect, sync, tool);
}
function fileExpected(label: 'A' | 'B', withNew = false): Candidate[] {
  const candidates = expected.files.filter(item => item.root === label && item.relative_name.endsWith('.jsonl'));
  if (withNew) candidates.push({relative_name: label === 'A' ? AN : 'sessions/2026/10/01/b-new.jsonl',
    bytes: 28, mtime_utc: '2026-10-01T00:00:00Z'});
  return candidates.sort((a, b) => Buffer.compare(Buffer.from(a.relative_name), Buffer.from(b.relative_name)));
}
function candidatesDigest(rows: Candidate[]): string {
  return sha(JSON.stringify(rows.map(({relative_name, bytes, mtime_utc}) =>
    [relative_name, bytes, Date.parse(mtime_utc)])));
}
async function candidates(tool: Tool, wanted: Candidate[], complete = true, reason: string | null = null): Promise<dict> {
  const completeness = page!.getByTestId(testId('completeness', tool));
  await expect(completeness).toBeVisible();
  await expect(page!.getByTestId(testId('candidate', tool))).toHaveCount(wanted.length);
  const rows = await page!.getByTestId(testId('candidate', tool)).evaluateAll(elements => elements.map(element => ({
    relative_name: element.getAttribute('data-relative-name') ?? '',
    bytes: Number(element.getAttribute('data-size-bytes')),
    mtime_utc: element.getAttribute('data-mtime-utc') ?? ''
  })));
  const normalized = rows;
  const desired = [...wanted].sort((a, b) => Buffer.compare(Buffer.from(a.relative_name), Buffer.from(b.relative_name)));
  expect(candidatesDigest(normalized)).toBe(candidatesDigest(desired));
  await expect(completeness).toHaveAttribute('data-complete', String(complete));
  if (!complete) await expect(completeness).toHaveAttribute('data-reason', reason!);
  return {count: normalized.length, collection_sha256: candidatesDigest(normalized),
    sizes: normalized.map(item => item.bytes), mtime_epoch_ms: normalized.map(item => Date.parse(item.mtime_utc)), complete,
    incomplete_reason: complete ? null : reason};
}
type dict = Record<string, unknown>;
async function preview(tool: Tool = 'codex', wanted = expected.preview.candidates,
                       complete = expected.preview.complete, reason = expected.preview.incomplete_reason): Promise<dict> {
  await page!.getByTestId(testId('preview', tool)).click();
  return candidates(tool, wanted, complete, reason);
}
async function refresh(tool: Tool = 'codex', wanted = fileExpected('A'), complete = true,
                       reason: string | null = null): Promise<dict> {
  await page!.getByTestId(testId('refresh', tool)).click();
  return candidates(tool, wanted, complete, reason);
}
function sourceFiles(): string[] {
  const directory = join(c.profile_path, 'sources');
  if (!existsSync(directory)) return [];
  const mode = lstatSync(directory).mode & 0o777;
  expect(mode).toBe(0o700);
  return readdirSync(directory).filter(name => name.endsWith('.json')).map(name => join(directory, name));
}
function sourceRecordSummary(tool: Tool = 'codex'): dict | null {
  const matches = sourceFiles().filter(path => {
    let item: {tool?: string};
    try { item = JSON.parse(readFileSync(path, 'utf8')) as {tool?: string}; }
    catch { throw new Error('Private source record is malformed'); }
    return item.tool === tool;
  });
  if (matches.length === 0) return null;
  if (matches.length !== 1) throw new Error('More than one confirmed source record for one tool');
  const path = matches[0];
  const stat = lstatSync(path);
  expect(stat.isFile() && !stat.isSymbolicLink() && stat.nlink === 1).toBe(true);
  expect(stat.mode & 0o777).toBe(0o600);
  const bytes = readFileSync(path);
  expect(bytes.includes(Buffer.from(c.source_a))).toBe(false);
  expect(bytes.includes(Buffer.from(c.source_b))).toBe(false);
  let item: {tool: Tool; state: string; collect_allowed: boolean;
    sync_intent: boolean; ciphertext: string; identity_hash: string; root_dev: string; root_ino: string};
  try { item = JSON.parse(bytes.toString('utf8')) as typeof item; }
  catch { throw new Error('Private source record is malformed'); }
  expect(item.tool).toBe(tool);
  expect(typeof item.ciphertext === 'string' && item.ciphertext.length > 4).toBe(true);
  return {state: item.state, collect_allowed: item.collect_allowed, sync_intent: item.sync_intent,
    record_sha256: sha(bytes), ciphertext_sha256: sha(item.ciphertext), identity_hash: item.identity_hash,
    root_digest: hmac(`${item.root_dev}:${item.root_ino}`)};
}
function databaseCounts(): dict {
  const db = new DatabaseSync(c.database_path, {readOnly: true});
  try { return {users: Number((db.prepare('SELECT count(*) AS n FROM users').get() as {n: number}).n),
    sessions: Number((db.prepare('SELECT count(*) AS n FROM sessions').get() as {n: number}).n),
    audit: Number((db.prepare('SELECT count(*) AS n FROM audit').get() as {n: number}).n)}; }
  finally { db.close(); }
}
async function transport(): Promise<Array<{method: string; route: string; status?: number; probe?: boolean}>> {
  const response = await fetch(c.service_control_url, {headers: {Authorization: `Bearer ${c.service_control_token}`}});
  expect(response.status).toBe(200);
  const value = await response.json() as {requests: Array<{method: string; route: string; status?: number; probe?: boolean}>};
  return value.requests;
}
async function noSourceNetwork(since: number): Promise<boolean> {
  const rows = (await transport()).slice(since).filter(row => !row.probe);
  return rows.every(row => (row.method === 'GET' && row.route === '/v1/me') ||
    (row.method === 'POST' && ['/v1/auth/login', '/v1/auth/logout', '/v1/auth/change-password'].includes(row.route)));
}
function readAudit(): AuditEvent[] {
  if (!existsSync(c.source_audit_path)) throw new Error('Owned App source audit is absent');
  let rows: AuditEvent[];
  try { rows = readFileSync(c.source_audit_path, 'utf8').split('\n').filter(Boolean)
    .map(line => JSON.parse(line) as AuditEvent); }
  catch { throw new Error('Owned App source audit is malformed'); }
  for (const [index, row] of rows.entries()) {
    expect(row.schema_version).toBe(1);
    expect(row.sequence).toBe(index + 1);
    expect(['root_open', 'enumerate', 'metadata', 'open_read', 'reject', 'cancel', 'preview_complete',
      'picker_open', 'picker_result']).toContain(row.operation);
    expect(['allowed', 'denied']).toContain(row.decision);
    const raw = JSON.stringify(row);
    if (raw.includes(c.source_a) || raw.includes(c.source_b) || raw.includes('PRIVATE_') ||
        raw.includes(A1) || raw.includes(B1)) throw new Error('Product source audit exposed a private name or path');
  }
  return rows;
}
function auditWindow(start: number, allowed: Array<'A' | 'B'>, requireMetadata = false): dict {
  const rows = readAudit().slice(start);
  const roots = new Set(allowed.map(rootDigest));
  const access = rows.filter(row => ['root_open', 'enumerate', 'metadata', 'open_read'].includes(row.operation)
    && row.decision === 'allowed');
  expect(access.every(row => row.root_digest && roots.has(row.root_digest))).toBe(true);
  expect(access.some(row => row.operation === 'open_read')).toBe(false);
  if (requireMetadata) expect(access.some(row => row.operation === 'enumerate' || row.operation === 'metadata')).toBe(true);
  return {events: rows.length, allowed_access: access.length,
    metadata_seen: access.some(row => row.operation === 'enumerate' || row.operation === 'metadata'),
    body_read_count: access.filter(row => row.operation === 'open_read').length,
    outside_allowed_count: access.filter(row => !row.root_digest || !roots.has(row.root_digest)).length};
}
function assertNoSourceAccess(start: number): dict {
  const rows = readAudit().slice(start);
  const access = rows.filter(row => ['root_open', 'enumerate', 'metadata', 'open_read'].includes(row.operation)
    && row.decision === 'allowed');
  expect(access).toHaveLength(0);
  return {events: rows.length, allowed_access: 0};
}
function uiNoLeak(): Promise<boolean> {
  return page!.locator('body').innerText().then(body => !body.includes(c.source_a) && !body.includes(c.source_b)
    && !body.includes('PRIVATE_A1') && !body.includes('PRIVATE_A2') && !body.includes('PRIVATE_B1'));
}
function mutate(action: 'append-new' | 'append-a' | 'deny-a' | 'restore-a' | 'replace-a-inode'): void {
  let value: string;
  try {
    value = execFileSync(c.python_executable, [c.source_fixture_script, action,
      '--owner-root', dirname(c.source_a), '--owner-id', c.source_owner_id], {encoding: 'utf8', timeout: 30_000});
  } catch { throw new Error('Owned source fixture mutation failed; private command omitted'); }
  const result = JSON.parse(value) as {action: string; owner_verified: boolean; case_id: string};
  expect(result).toEqual({action, owner_verified: true, case_id: c.case_id});
}
function originalFilesUnchanged(): boolean {
  return expected.files.every(file => {
    const target = join(sourcePath(file.root as 'A' | 'B'), file.relative_name);
    if (!existsSync(target) || !file.sha256) return false;
    return sha(readFileSync(target)) === file.sha256;
  });
}
async function identityControl(action: 'arm' | 'release' | 'status'): Promise<dict> {
  if (!c.identity_control_url || !c.identity_control_token) throw new Error('Real identity barrier is absent');
  const response = await fetch(`${c.identity_control_url}/${action}`, {
    method: action === 'status' ? 'GET' : 'POST',
    headers: {Authorization: `Bearer ${c.identity_control_token}`}});
  expect(response.status).toBe(200);
  return response.json() as Promise<dict>;
}
function blockCase(reason: string): never {
  writeFileSync(join(output!, 'coverage-blocked.json'), JSON.stringify({reason}) + '\n',
    {flag: 'wx', mode: 0o600});
  throw new Error(reason);
}
async function invalidateA(): Promise<void> {
  await chooseAndConfirm();
  await refresh();
  mutate('deny-a');
  let denied = false;
  try { readdirSync(c.source_a); }
  catch (error) { denied = (error as NodeJS.ErrnoException).code === 'EACCES'; }
  if (!denied) {
    mutate('restore-a');
    blockCase('Owned POSIX denial could not be reproduced under this UID');
  }
  await page!.getByTestId(testId('refresh')).click();
  await expect.poll(() => sourceState()).toBe('needs_reselect');
  await expect(page!.getByTestId(testId('refresh'))).toBeDisabled();
}
async function capturedIdentity(): Promise<dict> {
  await expect.poll(async () => (await identityControl('status')).captured, {timeout: 20_000}).toBe(true);
  const value = await identityControl('status');
  const observation = value.observation as dict;
  expect(observation.status).toBe(200);
  expect(observation.account_id).toBe('00000000-0000-4000-8000-000000000002');
  expect(String(observation.body_sha256)).toMatch(/^[a-f0-9]{64}$/);
  return observation;
}
function corruptOwnedLocator(): dict {
  const records = sourceFiles();
  if (records.length !== 1) throw new Error('One owned source record is required for the fixed corruption');
  const recordPath = records[0];
  const details = lstatSync(recordPath);
  if (!details.isFile() || details.isSymbolicLink() || details.nlink !== 1 ||
      (details.mode & 0o777) !== 0o600 || details.uid !== process.getuid!())
    throw new Error('Owned ciphertext record identity or mode differs');
  const original = readFileSync(recordPath);
  const value = JSON.parse(original.toString('utf8')) as dict;
  if (value.schema_version !== 1 || value.tool !== 'codex' ||
      typeof value.ciphertext !== 'string' || value.state !== 'confirmed')
    throw new Error('Owned ciphertext record schema differs');
  const changed = {...value, ciphertext: 'AAEC'};
  const temporary = `${recordPath}.tm002-corrupt-next`;
  if (existsSync(temporary)) throw new Error('Owned atomic corruption target already exists');
  writeFileSync(temporary, JSON.stringify(changed), {flag: 'wx', mode: 0o600});
  renameSync(temporary, recordPath);
  const actual = JSON.parse(readFileSync(recordPath, 'utf8')) as dict;
  expect(sha(JSON.stringify(actual))).toBe(sha(JSON.stringify(changed)));
  return {before_sha256: sha(original), after_sha256: sha(readFileSync(recordPath)),
    only_ciphertext_changed: Object.keys(value).every(key => key === 'ciphertext' || value[key] === actual[key])};
}
async function step(number: number, action: string, source: string, expectedValue: unknown, actualValue: unknown): Promise<void> {
  const passed = JSON.stringify(expectedValue) === JSON.stringify(actualValue);
  let screenshot: string | null = null;
  if (page && !page.isClosed()) {
    screenshot = `TC-step-${String(number).padStart(2, '0')}.png`;
    await page.screenshot({path: join(output!, screenshot)});
  }
  const event = {run_id: c.run_id, case_id: c.case_id, step: number, action,
    source, expected: expectedValue, actual: actualValue, passed,
    timestamp: new Date().toISOString(), evidence: {screenshot}};
  const raw = JSON.stringify(event);
  if (raw.includes(c.source_a) || raw.includes(c.source_b) || raw.includes('PRIVATE_') || raw.includes('TEST-ONLY-'))
    throw new Error('Step evidence would contain a forbidden path or synthetic secret');
  appendFileSync(eventsPath, raw + '\n', {mode: 0o600});
  expect(actualValue, `${c.case_id} step ${number}: ${action}`).toEqual(expectedValue);
}

test.beforeEach(async ({}, info) => {
  if (info.title !== c.case_id || expected.case_id !== c.case_id) throw new Error('Fixed TC and fixture differ');
});
test.afterEach(async () => {
  try { if (page && !page.isClosed()) await page.screenshot({path: join(output!, 'final.png')}); } catch { /* preserve first failure */ }
  try { await close(); } catch { /* runner checks process ownership and cleanup */ }
});

test('TC-TM002-SELECT-01', async () => {
  await aliceReady();
  const net = (await transport()).length;
  const fs = readAudit().length;
  await openPicker();
  await step(1, '打开真实 Codex 目录面板', 'ui/native',
    {source_record: false, source_access: 0, network: true},
    {source_record: sourceRecordSummary() !== null, source_access: assertNoSourceAccess(fs).allowed_access,
      network: await noSourceNetwork(net)});
  await finishPickerSelect('A');
  await step(2, '原生面板选择本例 A', 'native/ui',
    {state: 'pending', picker_count: 1, no_private_leak: true, outside_access: 0},
    {state: await sourceState(), picker_count: pickerIndex, no_private_leak: await uiNoLeak(),
      outside_access: auditWindow(fs, ['A']).outside_allowed_count});
  await step(3, '暂选尚未建立确认来源', 'filesystem/service',
    {record: false, originals_unchanged: true, network: true},
    {record: sourceRecordSummary() !== null, originals_unchanged: originalFilesUnchanged(),
      network: await noSourceNetwork(net)});
});

test('TC-TM002-SELECT-02#FIRST_CANCEL', async () => {
  await aliceReady();
  const fs = readAudit().length;
  const net = (await transport()).length;
  await openPicker();
  await step(1, '打开真实 Codex 目录面板', 'ui/native',
    {state: 'none', source_record: false},
    {state: await sourceState(), source_record: sourceRecordSummary() !== null});
  await finishPickerCancel();
  await step(2, '系统取消不创建来源', 'native/ui',
    {state: 'none', source_access: 0, source_record: false, network: true},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access,
      source_record: sourceRecordSummary() !== null, network: await noSourceNetwork(net)});
  await restart();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(3, '重启并经真实身份核对仍无来源', 'ui/filesystem/service',
    {state: 'none', source_record: false, source_access: 0},
    {state: await sourceState(), source_record: sourceRecordSummary() !== null,
      source_access: assertNoSourceAccess(fs).allowed_access});
});

test('TC-TM002-SELECT-02#CONFIRMED_CANCEL', async () => {
  await aliceReady(); await chooseAndConfirm();
  const first = await refresh();
  const old = sourceRecordSummary();
  const fs = readAudit().length;
  const net = (await transport()).length;
  await step(1, '真实确认 A 后显式刷新', 'ui/filesystem',
    {state: 'confirmed_enabled', count: 2, digest: candidatesDigest(fileExpected('A'))},
    {state: await sourceState(), count: first.count, digest: first.collection_sha256});
  await cancelPicker();
  const afterCancel = sourceRecordSummary();
  await step(2, '更换来源面板取消保留 A', 'native/ui/filesystem',
    {state: 'confirmed_enabled', same_record: true, b_access: 0, network: true},
    {state: await sourceState(), same_record: old?.record_sha256 === afterCancel?.record_sha256,
      b_access: auditWindow(fs, ['A']).outside_allowed_count, network: await noSourceNetwork(net)});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  const restored = await refresh();
  await step(3, '重启后旧 A 仍是唯一来源', 'ui/filesystem/service',
    {state: 'confirmed_enabled', count: 2, same_identity_root: true, outside_access: 0},
    {state: await sourceState(), count: restored.count,
      same_identity_root: old?.identity_hash === sourceRecordSummary()?.identity_hash &&
        old?.root_digest === sourceRecordSummary()?.root_digest,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count});
});

test('TC-TM002-SELECT-02#REPLACE_CONFIRMED', async () => {
  await aliceReady(); await chooseAndConfirm();
  const first = await refresh();
  const old = sourceRecordSummary();
  await step(1, '确认 A 并锁定旧来源/候选', 'ui/filesystem',
    {state: 'confirmed_enabled', count: 2, record: true},
    {state: await sourceState(), count: first.count, record: old !== null});
  const beforeB = readAudit().length;
  await choose('B');
  await step(2, '真实选择 B 但尚未提交', 'native/ui/filesystem',
    {state: 'pending', old_record_same: true, b_body_reads: 0},
    {state: await sourceState(), old_record_same: old?.record_sha256 === sourceRecordSummary()?.record_sha256,
      b_body_reads: auditWindow(beforeB, ['A', 'B']).body_read_count});
  const commitBoundary = readAudit().length;
  await confirm();
  const updated = sourceRecordSummary();
  await step(3, '原子确认 B 撤销旧 A 能力', 'ui/filesystem',
    {state: 'confirmed_enabled', changed_record: true, root_b: rootDigest('B'), a_late_access: 0},
    {state: await sourceState(), changed_record: old?.record_sha256 !== updated?.record_sha256,
      root_b: updated?.root_digest,
      a_late_access: readAudit().slice(commitBoundary).filter(row => row.decision === 'allowed' &&
        row.root_digest === rootDigest('A') && ['enumerate', 'metadata', 'open_read'].includes(row.operation)).length});
  const refreshed = await refresh('codex', fileExpected('B'));
  await step(4, '刷新只列 B1', 'ui/filesystem',
    {count: 1, digest: candidatesDigest(fileExpected('B')), outside_access: 0},
    {count: refreshed.count, digest: refreshed.collection_sha256,
      outside_access: auditWindow(commitBoundary, ['B'], true).outside_allowed_count});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  const restored = await refresh('codex', fileExpected('B'));
  await step(5, '重启仍只恢复 B', 'ui/filesystem/service',
    {state: 'confirmed_enabled', count: 1, root_b: rootDigest('B'), originals_unchanged: true},
    {state: await sourceState(), count: restored.count,
      root_b: sourceRecordSummary()?.root_digest, originals_unchanged: originalFilesUnchanged()});
});

test('TC-TM002-SELECT-04', async () => {
  await aliceReady();
  await choose('A', 'claude_code');
  await step(1, 'Claude Code 真实面板选择 A', 'native/ui',
    {state: 'pending', tool: 'claude_code', picker_count: 1},
    {state: await sourceState('claude_code'), tool: expected.tool, picker_count: pickerIndex});
  const previewed = await preview('claude_code');
  await step(2, '仅列 Claude A 语法候选元数据', 'ui/filesystem',
    {count: 1, digest: candidatesDigest(expected.preview.candidates), no_leak: true},
    {count: previewed.count, digest: previewed.collection_sha256, no_leak: await uiNoLeak()});
  await confirm(true, false, 'claude_code');
  await step(3, '默认同步关闭且来源加密确认', 'ui/filesystem',
    {state: 'confirmed_enabled', consent: true, record: true},
    {state: await sourceState('claude_code'), consent: await checkConsent(true, false, 'claude_code'),
      record: sourceRecordSummary('claude_code') !== null});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  const restored = await refresh('claude_code', fileExpected('A'));
  await step(4, '同身份重启恢复 Claude 来源', 'ui/filesystem/service',
    {state: 'confirmed_enabled', count: 1, outside_access: 0},
    {state: await sourceState('claude_code'), count: restored.count,
      outside_access: auditWindow(0, ['A'], true).outside_allowed_count});
});

test('TC-TM002-PREVIEW-01', async () => {
  await aliceReady(); await choose('A');
  const fs = readAudit().length;
  const net = (await transport()).length;
  const shown = await preview();
  await step(1, '显式预览只列 A 两个候选', 'ui/filesystem',
    {count: 2, digest: candidatesDigest(expected.preview.candidates)},
    {count: shown.count, digest: shown.collection_sha256});
  await step(2, '候选元数据与无正文泄漏', 'ui/filesystem',
    {sizes: [25, 25], mtime: 1790812800000, no_leak: true, body_reads: 0},
    {sizes: shown.sizes, mtime: (shown.mtime_epoch_ms as number[])[0], no_leak: await uiNoLeak(),
      body_reads: auditWindow(fs, ['A'], true).body_read_count});
  await step(3, '预览不落盘且不改服务/源文件', 'filesystem/service',
    {record: false, originals_unchanged: true, network: true},
    {record: sourceRecordSummary() !== null, originals_unchanged: originalFilesUnchanged(),
      network: await noSourceNetwork(net)});
});

test('TC-TM002-PREVIEW-02', async () => {
  await aliceReady(); await choose('A');
  await step(1, '仅含非候选文件的 A 待确认', 'native/ui',
    {state: 'pending', fixture_candidate_count: 0},
    {state: await sourceState(), fixture_candidate_count: expected.preview.candidates.length});
  const shown = await preview();
  await step(2, '完整零候选与读失败区分', 'ui/filesystem',
    {count: 0, complete: true, no_leak: true},
    {count: shown.count, complete: shown.complete, no_leak: await uiNoLeak()});
  await confirm();
  const refreshed = await refresh('codex', []);
  await step(3, '空目录也能明确确认并刷新', 'ui/filesystem',
    {state: 'confirmed_enabled', count: 0, complete: true, record: true},
    {state: await sourceState(), count: refreshed.count, complete: refreshed.complete,
      record: sourceRecordSummary() !== null});
});

test('TC-TM002-PREVIEW-03', async () => {
  await aliceReady(); await choose('A');
  const fs = readAudit().length;
  const shown = await preview();
  await step(1, '真实链接同层预览只列 A1/A2', 'ui/filesystem',
    {count: 2, digest: candidatesDigest(expected.preview.candidates)},
    {count: shown.count, digest: shown.collection_sha256});
  const rows = readAudit().slice(fs);
  const rejected = new Set(rows.filter(row => row.operation === 'reject' && row.decision === 'denied')
    .map(row => row.entry_digest));
  await step(2, '文件和目录 symlink 均被实际遇到并拒绝', 'filesystem',
    {rejected_links: 2, outside_access: 0, body_reads: 0, no_leak: true},
    {rejected_links: expected.symlinks.filter(item => rejected.has(hmac(item.relative_name))).length,
      outside_access: auditWindow(fs, ['A']).outside_allowed_count,
      body_reads: auditWindow(fs, ['A']).body_read_count, no_leak: await uiNoLeak()});
  await confirm();
  const refreshed = await refresh();
  await step(3, '确认后刷新仍拒绝逸出', 'ui/filesystem',
    {count: 2, digest: candidatesDigest(fileExpected('A')), unchanged: true},
    {count: refreshed.count, digest: refreshed.collection_sha256, unchanged: originalFilesUnchanged()});
});

async function runPreviewLimit(): Promise<void> {
  await aliceReady(); await choose('A');
  await step(1, '真实面板选择上限专用 A', 'native/ui',
    {state: 'pending', picker_count: 1},
    {state: await sourceState(), picker_count: pickerIndex});
  const fs = readAudit().length;
  const shown = await preview('codex', expected.preview.candidates, false, expected.preview.incomplete_reason);
  await step(2, '按独立清单显示已核验候选并标不完整', 'ui/filesystem',
    {count: expected.preview.candidates.length,
      digest: candidatesDigest(expected.preview.candidates), complete: false,
      reason: expected.preview.incomplete_reason},
    {count: shown.count, digest: shown.collection_sha256,
      complete: shown.complete, reason: shown.incomplete_reason});
  const completion = readAudit().slice(fs).filter(row => row.operation === 'preview_complete').at(-1);
  await step(3, '枚举实际计数在本版上限内且未确认/越界', 'filesystem/service',
    {record: false, outside_access: 0, body_reads: 0,
      inspected_within_limit: true, candidate_count: expected.preview.candidates.length,
      root_a: rootDigest('A'), reason: expected.preview.incomplete_reason},
    {record: sourceRecordSummary() !== null,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count,
      body_reads: auditWindow(fs, ['A']).body_read_count,
      inspected_within_limit: typeof completion?.inspected_entries === 'number' &&
        completion.inspected_entries <= 5000,
      candidate_count: completion?.candidate_count, root_a: completion?.root_digest,
      reason: completion?.reason});
}
test('TC-TM002-PREVIEW-04#CANDIDATES_1001', runPreviewLimit);
test('TC-TM002-PREVIEW-04#ENTRIES_5001', runPreviewLimit);
test('TC-TM002-PREVIEW-04#DEPTH_9', runPreviewLimit);

test('TC-TM002-CONSENT-01', async () => {
  await aliceReady(); await choose('A'); await preview();
  const fs = readAudit().length;
  const net = (await transport()).length;
  await step(1, '显式预览结束但尚未确认', 'ui/filesystem',
    {state: 'pending', record: false},
    {state: await sourceState(), record: sourceRecordSummary() !== null});
  mutate('append-new');
  await page!.waitForTimeout(35_000);
  await step(2, '新增 A/B 后 35 秒无后台补扫', 'filesystem/ui/service',
    {source_access: 0, pending: true, network: true},
    {source_access: assertNoSourceAccess(fs).allowed_access,
      pending: (await sourceState()) === 'pending', network: await noSourceNetwork(net)});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(3, '未确认暂选不跨重启', 'ui/filesystem/service',
    {state: 'none', record: false, source_access: 0},
    {state: await sourceState(), record: sourceRecordSummary() !== null,
      source_access: assertNoSourceAccess(fs).allowed_access});
});

test('TC-TM002-CONSENT-02', async () => {
  await aliceReady(); await choose('A');
  const net = (await transport()).length;
  await consent(true, false);
  await step(1, '默认未来同步关闭且未落来源', 'ui/filesystem',
    {consent: true, record: false},
    {consent: await checkConsent(true, false), record: sourceRecordSummary() !== null});
  await page!.getByTestId(testId('confirm')).click();
  await expect(page!.getByTestId(testId('confirmed'))).toBeVisible();
  const record = sourceRecordSummary();
  await step(2, '确认后仅本地保存 true/false 和 A', 'ui/filesystem/service',
    {state: 'confirmed_enabled', collect: true, sync: false, root_a: rootDigest('A'), network: true},
    {state: await sourceState(), collect: record?.collect_allowed, sync: record?.sync_intent,
      root_a: record?.root_digest, network: await noSourceNetwork(net)});
  mutate('append-new');
  const fs = readAudit().length;
  const shown = await refresh('codex', fileExpected('A', true));
  await step(3, '显式刷新只增加 A 的新候选', 'ui/filesystem/service',
    {count: 3, digest: candidatesDigest(fileExpected('A', true)), outside_access: 0,
      body_reads: 0, network: true},
    {count: shown.count, digest: shown.collection_sha256,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count,
      body_reads: auditWindow(fs, ['A']).body_read_count, network: await noSourceNetwork(net)});
});

async function runPausedConsent(sync: boolean): Promise<void> {
  await aliceReady(); await choose('A');
  const net = (await transport()).length;
  await confirm(false, sync);
  const record = sourceRecordSummary();
  await step(1, '两项意愿独立确认且采集暂停', 'ui/filesystem',
    {state: 'confirmed_paused', collect: false, sync, record: true},
    {state: await sourceState(), collect: record?.collect_allowed,
      sync: record?.sync_intent, record: record !== null});
  const fs = readAudit().length;
  mutate('append-new');
  await expect(page!.getByTestId(testId('refresh'))).toBeDisabled();
  await step(2, '暂停态新增文件不读取也不上传', 'ui/filesystem/service',
    {refresh_disabled: true, source_access: 0, network: true},
    {refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(),
      source_access: assertNoSourceAccess(fs).allowed_access, network: await noSourceNetwork(net)});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(3, '重启仍保留独立意愿但不读', 'ui/filesystem/service',
    {state: 'confirmed_paused', consent: true, source_access: 0},
    {state: await sourceState(), consent: await checkConsent(false, sync),
      source_access: assertNoSourceAccess(fs).allowed_access});
}
test('TC-TM002-CONSENT-03#FALSE_TRUE', async () => runPausedConsent(true));
test('TC-TM002-CONSENT-03#FALSE_FALSE', async () => runPausedConsent(false));

test('TC-TM002-CONSENT-04#BOTH_TRUE', async () => {
  await aliceReady(); await chooseAndConfirm('A', true, true);
  const net = (await transport()).length;
  const record = sourceRecordSummary();
  await step(1, '两意愿 true 仍只本地保存', 'ui/filesystem/service',
    {state: 'confirmed_enabled', collect: true, sync: true, network: true},
    {state: await sourceState(), collect: record?.collect_allowed, sync: record?.sync_intent,
      network: await noSourceNetwork(net)});
  const shown = await refresh();
  await step(2, '刷新候选无同步上传', 'ui/filesystem/service',
    {count: 2, digest: candidatesDigest(fileExpected('A')), network: true},
    {count: shown.count, digest: shown.collection_sha256, network: await noSourceNetwork(net)});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  const restored = await refresh();
  await step(3, '重启仍为 true/true 且零上传', 'ui/filesystem/service',
    {state: 'confirmed_enabled', consent: true, count: 2, network: true},
    {state: await sourceState(), consent: await checkConsent(true, true), count: restored.count,
      network: await noSourceNetwork(net)});
});

test('TC-TM002-CONSENT-04#TURN_SYNC_OFF', async () => {
  await aliceReady(); await chooseAndConfirm('A', true, true);
  const first = await refresh();
  const old = sourceRecordSummary();
  const net = (await transport()).length;
  await step(1, '先确认 A 的 true/true', 'ui/filesystem',
    {state: 'confirmed_enabled', count: 2, consent: true},
    {state: await sourceState(), count: first.count, consent: await checkConsent(true, true)});
  const fs = readAudit().length;
  await page!.getByTestId(testId('sync')).uncheck();
  await expect.poll(() => sourceRecordSummary()?.sync_intent).toBe(false);
  const updated = sourceRecordSummary();
  await step(2, 'UI 单独关闭未来同步', 'ui/filesystem/service',
    {state: 'confirmed_enabled', collect: true, sync: false, same_root: true,
      source_access: 0, network: true},
    {state: await sourceState(), collect: updated?.collect_allowed, sync: updated?.sync_intent,
      same_root: old?.root_digest === updated?.root_digest,
      source_access: assertNoSourceAccess(fs).allowed_access, network: await noSourceNetwork(net)});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  const shown = await refresh();
  await step(3, '重启保留 true/false 与原 A', 'ui/filesystem/service',
    {consent: true, count: 2, same_root: true, network: true},
    {consent: await checkConsent(true, false), count: shown.count,
      same_root: old?.root_digest === sourceRecordSummary()?.root_digest,
      network: await noSourceNetwork(net)});
});

test('TC-TM002-CONSENT-04#TURN_COLLECT_OFF_ON', async () => {
  await aliceReady(); await chooseAndConfirm();
  const first = await refresh();
  const old = sourceRecordSummary();
  await step(1, 'A 启用态及旧代际', 'ui/filesystem',
    {state: 'confirmed_enabled', count: 2, root_a: rootDigest('A')},
    {state: await sourceState(), count: first.count, root_a: old?.root_digest});
  const fs = readAudit().length;
  await page!.getByTestId(testId('collect')).uncheck();
  await expect.poll(() => sourceState()).toBe('confirmed_paused');
  const paused = sourceRecordSummary();
  await step(2, '关闭采集原子转为 false/false', 'ui/filesystem',
    {state: 'confirmed_paused', collect: false, sync: false, same_root: true,
      source_access: 0},
    {state: await sourceState(), collect: paused?.collect_allowed, sync: paused?.sync_intent,
      same_root: old?.root_digest === paused?.root_digest,
      source_access: assertNoSourceAccess(fs).allowed_access});
  await expect(page!.getByTestId(testId('refresh'))).toBeDisabled();
  await step(3, '暂停页拒旧刷新且不显示完整零候选', 'ui/filesystem',
    {refresh_disabled: true, source_access: 0, state: 'confirmed_paused'},
    {refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(),
      source_access: assertNoSourceAccess(fs).allowed_access, state: await sourceState()});
  await page!.getByTestId(testId('collect')).check();
  await expect.poll(() => sourceState()).toBe('confirmed_enabled');
  const restored = await refresh();
  await step(4, '明确重开后复核 A 并新代际刷新', 'ui/filesystem',
    {state: 'confirmed_enabled', consent: true, count: 2, outside_access: 0},
    {state: await sourceState(), consent: await checkConsent(true, false), count: restored.count,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  const again = await refresh();
  await step(5, '重启继续同一 A true/false', 'ui/filesystem/service',
    {state: 'confirmed_enabled', consent: true, count: 2, same_root: true},
    {state: await sourceState(), consent: await checkConsent(true, false), count: again.count,
      same_root: old?.root_digest === sourceRecordSummary()?.root_digest});
});

test('TC-TM002-STATE-01#NORMAL_RESTORE', async () => {
  await aliceReady(); await chooseAndConfirm();
  const record = sourceRecordSummary();
  await close(); await identityControl('arm');
  await step(1, '确认态私有记录完整并武装真实 /v1/me 屏障', 'filesystem/service',
    {record: true, root_a: rootDigest('A'), originals_unchanged: true},
    {record: record !== null, root_a: record?.root_digest, originals_unchanged: originalFilesUnchanged()});
  const fs = readAudit().length;
  await launch();
  const captured = await capturedIdentity();
  const sourceVisible = await page!.getByTestId(testId('status')).count();
  const premature = sourceVisible > 0 && (await sourceState()) === 'confirmed_enabled';
  await step(2, '真实服务响应已取得但未交给 App 时不可读 A', 'ui/filesystem/service',
    {captured: true, premature_readable: false, source_access: 0},
    {captured: captured.status === 200, premature_readable: premature,
      source_access: assertNoSourceAccess(fs).allowed_access});
  await identityControl('release');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const shown = await refresh();
  await step(3, '真实 /v1/me 交付 Alice 后才恢复 A', 'ui/filesystem/service',
    {state: 'confirmed_enabled', consent: true, count: 2, outside_access: 0},
    {state: await sourceState(), consent: await checkConsent(true, false), count: shown.count,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count});
});

test('TC-TM002-STATE-01#CORRUPT_LOCATOR', async () => {
  await aliceReady(); await chooseAndConfirm();
  const shown = await refresh();
  await close();
  const corruption = corruptOwnedLocator();
  await step(1, '只损坏本例 0600 密文字段', 'filesystem',
    {count_before: 2, only_ciphertext_changed: true, digest_changed: true,
      originals_unchanged: true},
    {count_before: shown.count, only_ciphertext_changed: corruption.only_ciphertext_changed,
      digest_changed: corruption.before_sha256 !== corruption.after_sha256,
      originals_unchanged: originalFilesUnchanged()});
  await identityControl('arm');
  const fs = readAudit().length;
  await launch(); const captured = await capturedIdentity();
  const sourceVisible = await page!.getByTestId(testId('status')).count();
  const premature = sourceVisible > 0 && (await sourceState()) === 'confirmed_enabled';
  await step(2, '真实身份响应屏障期间旧 A 不可读', 'ui/filesystem/service',
    {captured: true, premature_readable: false, source_access: 0},
    {captured: captured.status === 200, premature_readable: premature,
      source_access: assertNoSourceAccess(fs).allowed_access});
  await identityControl('release');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(3, '解密失败后停读并要求重选', 'ui/filesystem/service',
    {state: 'needs_reselect', refresh_disabled: true, source_access: 0},
    {state: await sourceState(), refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(),
      source_access: assertNoSourceAccess(fs).allowed_access});
  await cancelPicker(); await restart();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(4, '原生取消与重启均不复活损坏来源', 'native/ui/filesystem',
    {state: 'needs_reselect', source_access: 0},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
});

test('TC-TM002-STATE-02', async () => {
  await aliceReady(); await chooseAndConfirm(); await refresh();
  const fs = readAudit().length;
  await logout();
  await step(1, 'Alice 真实退出即卸载来源能力', 'ui/filesystem/service',
    {login_visible: true, source_access: 0},
    {login_visible: await page!.getByTestId('auth.login').isVisible(),
      source_access: assertNoSourceAccess(fs).allowed_access});
  await login('test-bob', BOB_PASSWORD, true);
  await step(2, '同 origin Bob 无 Alice 的来源', 'ui/filesystem/service',
    {username: 'test-bob', state: 'none', source_access: 0},
    {username: (await page!.getByTestId('session.username').textContent())?.trim(),
      state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
  await logout(); await login('test-alice', CHANGED_PASSWORD, false);
  const shown = await refresh();
  await step(3, '重新验证 Alice 才恢复 A', 'ui/filesystem/service',
    {username: 'test-alice', state: 'confirmed_enabled', count: 2, outside_access: 0},
    {username: (await page!.getByTestId('session.username').textContent())?.trim(),
      state: await sourceState(), count: shown.count,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count});
});

test('TC-TM002-STATE-03', async () => {
  if (!c.secondary_service_url) throw new Error('Second owned origin is missing');
  await aliceReady(); await chooseAndConfirm(); await refresh();
  const fs = readAudit().length;
  await logout(); await configure(c.secondary_service_url);
  await login('test-alice', 'TEST-ONLY-alice-43!', true);
  await step(1, '切换 S2 后同 ID Alice 没有 S1 来源', 'ui/filesystem/service',
    {state: 'none', source_access: 0},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
  await step(2, 'S2 来源页无 S1 刷新能力', 'ui/filesystem',
    {state: 'none', refresh_disabled: true, source_access: 0},
    {state: await sourceState(), refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(),
      source_access: assertNoSourceAccess(fs).allowed_access});
  await logout(); await configure(c.service_url);
  await login('test-alice', CHANGED_PASSWORD, false);
  const shown = await refresh();
  await step(3, '回 S1 且真实验证后恢复 A', 'ui/filesystem/service',
    {state: 'confirmed_enabled', count: 2, outside_access: 0},
    {state: await sourceState(), count: shown.count,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count});
});

test('TC-TM002-SELECT-03', async () => {
  await aliceReady(); await invalidateA();
  const fs = readAudit().length;
  await step(1, 'A 真拒读后进入需重新选择', 'ui/filesystem',
    {state: 'needs_reselect', refresh_disabled: true, source_access: 0},
    {state: await sourceState(), refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(),
      source_access: assertNoSourceAccess(fs).allowed_access});
  await cancelPicker();
  await step(2, '重选原生面板取消仍停读', 'native/ui/filesystem',
    {state: 'needs_reselect', source_access: 0},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
  await step(3, '受控刷新仍不可用且不复活旧授权', 'ui/filesystem',
    {refresh_disabled: true, state: 'needs_reselect', source_access: 0},
    {refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(),
      state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
  mutate('restore-a');
});

test('TC-TM002-ACCESS-01', async () => {
  await aliceReady(); await chooseAndConfirm(); await refresh();
  const before = sourceRecordSummary();
  const fs = readAudit().length;
  await page!.getByTestId(testId('revoke')).click();
  await page!.getByTestId(testId('revoke.confirm')).click();
  await expect.poll(() => sourceState()).toBe('none');
  await step(1, '用户二次确认撤销并删除旧密文来源', 'ui/filesystem',
    {state: 'none', prior_record: true, record: false, source_access: 0},
    {state: await sourceState(), prior_record: before !== null,
      record: sourceRecordSummary() !== null, source_access: assertNoSourceAccess(fs).allowed_access});
  mutate('append-a');
  await page!.waitForTimeout(35_000);
  await step(2, '撤销后新增文件不重启扫描', 'ui/filesystem',
    {state: 'none', source_access: 0, refresh_disabled: true},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access,
      refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled()});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(3, '重启后旧来源和读取能力仍不存在', 'ui/filesystem/service',
    {state: 'none', record: false, source_access: 0, originals_unchanged: true},
    {state: await sourceState(), record: sourceRecordSummary() !== null,
      source_access: assertNoSourceAccess(fs).allowed_access,
      originals_unchanged: originalFilesUnchanged()});
});

test('TC-TM002-ACCESS-02', async () => {
  await aliceReady(); await chooseAndConfirm();
  const first = await refresh();
  await step(1, 'A 初始 0700 可受控刷新', 'ui/filesystem',
    {count: 2, root_mode: 0o700},
    {count: first.count, root_mode: lstatSync(c.source_a).mode & 0o777});
  mutate('deny-a');
  let denied = false;
  try { readdirSync(c.source_a); }
  catch (error) { denied = (error as NodeJS.ErrnoException).code === 'EACCES'; }
  if (!denied) { mutate('restore-a'); blockCase('Owned POSIX denial could not be reproduced'); }
  await page!.getByTestId(testId('refresh')).click();
  await expect.poll(() => sourceState()).toBe('needs_reselect');
  const fs = readAudit().length;
  await step(2, '真实拒读使来源失效而非完整零文件', 'ui/filesystem',
    {os_denied: true, state: 'needs_reselect', refresh_disabled: true, app_alive: true},
    {os_denied: denied, state: await sourceState(),
      refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(), app_alive: !page!.isClosed()});
  mutate('restore-a'); mutate('append-a');
  await step(3, 'POSIX 权限恢复本身不复活旧 App 来源', 'ui/filesystem',
    {state: 'needs_reselect', source_access: 0, root_mode: 0o700},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access,
      root_mode: lstatSync(c.source_a).mode & 0o777});
});

test('TC-TM002-ACCESS-03', async () => {
  await aliceReady(); await chooseAndConfirm();
  const first = await refresh();
  const original = statSync(c.source_a, {bigint: true});
  await step(1, '旧 A 设备/inode 与候选固定', 'ui/filesystem',
    {count: 2, root_matches_record: true},
    {count: first.count, root_matches_record: sourceRecordSummary()?.root_digest === rootDigest('A')});
  mutate('replace-a-inode');
  const current = statSync(c.source_a, {bigint: true});
  const inodeDifferent = original.dev !== current.dev || original.ino !== current.ino;
  await page!.getByTestId(testId('refresh')).click();
  await expect.poll(() => sourceState()).toBe('needs_reselect');
  const fs = readAudit().length;
  await step(2, '同路径新 inode 不能继承旧来源能力', 'ui/filesystem',
    {inode_different: true, state: 'needs_reselect', refresh_disabled: true},
    {inode_different: inodeDifferent, state: await sourceState(),
      refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled()});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(3, '重启仍不追踪新 A 或 A-original', 'ui/filesystem/service',
    {state: 'needs_reselect', source_access: 0},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
});

test('TC-TM002-ACCESS-04', async () => {
  await aliceReady(); await invalidateA(); mutate('restore-a');
  const fs = readAudit().length;
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  await step(1, '真实失效记录跨重启仍需重选', 'ui/filesystem/service',
    {state: 'needs_reselect', source_access: 0},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
  await cancelPicker();
  await step(2, '重启后原生面板取消仍不恢复', 'native/ui/filesystem',
    {state: 'needs_reselect', source_access: 0},
    {state: await sourceState(), source_access: assertNoSourceAccess(fs).allowed_access});
  mutate('append-a');
  await step(3, '新 A 文件不被旧 locator 刷新', 'ui/filesystem',
    {state: 'needs_reselect', refresh_disabled: true, source_access: 0},
    {state: await sourceState(), refresh_disabled: await page!.getByTestId(testId('refresh')).isDisabled(),
      source_access: assertNoSourceAccess(fs).allowed_access});
});

test('TC-TM002-ACCESS-05', async () => {
  await aliceReady(); await invalidateA(); mutate('restore-a'); mutate('append-a');
  const old = sourceRecordSummary();
  await choose('A');
  const shown = await preview('codex', fileExpected('A', true));
  await step(1, '失效后重新真实选择 A 仍仅待确认', 'native/ui/filesystem',
    {state: 'pending', count: 3, old_record_preserved: true},
    {state: await sourceState(), count: shown.count,
      old_record_preserved: old?.record_sha256 === sourceRecordSummary()?.record_sha256});
  await confirm();
  await step(2, '明确再次确认建立新的 A 能力', 'ui/filesystem',
    {state: 'confirmed_enabled', consent: true, record: true},
    {state: await sourceState(), consent: await checkConsent(true, false),
      record: sourceRecordSummary() !== null});
  const fs = readAudit().length;
  const refreshed = await refresh('codex', fileExpected('A', true));
  await step(3, '刷新恰列 A1/A2/AN 且 B 零访问', 'ui/filesystem',
    {count: 3, digest: candidatesDigest(fileExpected('A', true)), outside_access: 0,
      body_reads: 0},
    {count: refreshed.count, digest: refreshed.collection_sha256,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count,
      body_reads: auditWindow(fs, ['A']).body_read_count});
  await restart(); await expect(page!.getByTestId('session.verified')).toBeVisible();
  const again = await refresh('codex', fileExpected('A', true));
  await step(4, '重启经身份验证继续读取新确认 A', 'ui/filesystem/service',
    {state: 'confirmed_enabled', count: 3, outside_access: 0},
    {state: await sourceState(), count: again.count,
      outside_access: auditWindow(fs, ['A'], true).outside_allowed_count});
});
