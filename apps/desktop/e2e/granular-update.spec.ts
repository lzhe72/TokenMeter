/** Independent installed-App UPDATE cases. Each invocation binds one catalog TC. */
import { test, expect, chromium, type Browser, type ElectronApplication, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { appendFileSync, existsSync, lstatSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { launchObserved, observations as mainObservations } from './main-observer';

type Context = {
  run_id: string; candidate_sha: string; case_id: string; app_path: string; profile_path: string;
  service_url: string; service_log_path: string; update_url: string | null;
  update_control_url: string | null; update_control_token: string | null; update_nonce: string | null;
  forbidden_target_url?: string; forbidden_target_observations_url?: string; forbidden_target_token?: string;
  cdp_port: number | null; expected_upgrade_build: string;
  expected_app_tree_sha256: string; expected_update_tree_sha256: string;
};
type RequestObservation = { stage: string; method: string; route: string; status: number;
  bytes_sent: number; body_sha256: string; time: string };
type UpdateMetadata = { schema_version: number; version: string; build: string; url: string;
  sha256: string; bytes: number; ed25519_signature: string };
type BuildConfig = { version: string; build: string; bundle_id: string; api_url: string;
  update_feed_url: string; update_public_key: string; certificate_sha256: string };
const contextPath = process.env.TM_E2E_CONTEXT;
const output = process.env.TM_E2E_CASE_OUTPUT;
if (!contextPath || !output) throw new Error('Owned granular context and output are required');
const c = JSON.parse(readFileSync(contextPath, 'utf8')) as Context;
const binary = join(c.app_path, 'Contents/MacOS/TokenMeter');
const eventPath = join(output, 'events.jsonl');
const INITIAL_PASSWORD = 'TEST-ONLY-alice-42!';
const CHANGED_PASSWORD = 'TEST-ONLY-Changed-42!';
let app: ElectronApplication | null = null;
let page: Page | null = null;
let reconnected: Browser | null = null;
let tracing = false;
let traceNumber = 0;
let runnerLaunches = 0;

test.setTimeout(360_000);

function required<T>(value: T | null | undefined, name: string): T {
  if (value == null || value === '') throw new Error(`${name} has no owned runner fixture`);
  return value;
}
function sha256(bytes: Buffer | string): string { return createHash('sha256').update(bytes).digest('hex'); }
function fileSha(path: string): string { return sha256(readFileSync(path)); }
function originalTreeHash(): string {
  // The package manifest uses this same path/content/symlink algorithm. Re-scan the installed files.
  const root = resolve(process.cwd(), '../..');
  return execFileSync('python3', ['-c',
    'from pathlib import Path; from scripts.package_release_dmg import tree_sha256; import sys; print(tree_sha256(Path(sys.argv[1])))',
    c.app_path], { cwd: root, encoding: 'utf8', timeout: 120_000 }).trim();
}
function buildVersion(): { version: string; build: string } {
  const plist = join(c.app_path, 'Contents/Info.plist');
  return {
    version: execFileSync('/usr/bin/plutil', ['-extract', 'CFBundleShortVersionString', 'raw', plist], { encoding: 'utf8' }).trim(),
    build: execFileSync('/usr/bin/plutil', ['-extract', 'CFBundleVersion', 'raw', plist], { encoding: 'utf8' }).trim(),
  };
}
function buildConfig(): BuildConfig {
  return JSON.parse(readFileSync(join(c.app_path, 'Contents/Resources/release-config.json'), 'utf8')) as BuildConfig;
}
function childEnvironment(): Record<string,string> {
  return Object.fromEntries(Object.entries(process.env).filter((entry):entry is [string,string]=>entry[1]!==undefined).filter(([key]) =>
    !key.startsWith('TM_E2E_') && !key.startsWith('TM_INTERNAL_') && !key.includes('SIGNING') && !key.includes('TOKEN')));
}
async function launch(diagnostic = false): Promise<void> {
  if (!existsSync(binary)) throw new Error('Installed final-DMG App executable is missing');
  const args = [`--user-data-dir=${c.profile_path}`];
  if (diagnostic) args.push(`--diagnostic-cdp-port=${required(c.cdp_port, 'cdp_port')}`);
  app = await launchObserved({ executablePath: binary, args, env: childEnvironment(),
    chromiumSandbox: true, timeout: 60_000 }, {run_id: c.run_id, case_id: c.case_id, output: output!});
  runnerLaunches++;
  page = await app.firstWindow();
  await expect(page.getByTestId('app.build')).toContainText('build 100');
  await app.context().tracing.start({ screenshots: true, snapshots: true, sources: false });
  tracing = true;
}
async function stopTrace(): Promise<void> {
  if (app && tracing) {
    await app.context().tracing.stop({ path: join(output!, `trace-${String(++traceNumber).padStart(2, '0')}.zip`) });
    tracing = false;
  }
}
async function close(): Promise<void> {
  if (app) { await stopTrace(); await app.close(); app = null; page = null; }
}
async function step(index: number, action: string, source: 'ui' | 'service' | 'filesystem' | 'process' | 'runner',
  expected: unknown, actual: unknown): Promise<void> {
  let screenshot: string | null = null;
  if (page && !page.isClosed()) {
    screenshot = `TC-step-${String(index).padStart(2, '0')}.png`;
    await page.screenshot({ path: join(output!, screenshot) });
  }
  const passed = JSON.stringify(expected) === JSON.stringify(actual);
  appendFileSync(eventPath, JSON.stringify({ run_id: c.run_id, case_id: c.case_id, step: index,
    action, source, expected, actual, passed, timestamp: new Date().toISOString(), screenshot }) + '\n', { mode: 0o600 });
  expect(actual, `${c.case_id} step ${index}: ${action}`).toEqual(expected);
}
async function configureOwned(): Promise<void> {
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(c.service_url);
  await page!.getByTestId('configuration.update-url').fill(required(c.update_url, 'update_url'));
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('configuration.status')).toContainText('配置已保存');
  await expect(page!.getByTestId('auth.server')).toHaveValue(c.service_url);
}
async function memberReady(): Promise<void> {
  await page!.getByTestId('auth.username').fill('test-alice');
  await page!.getByTestId('auth.password').fill(INITIAL_PASSWORD);
  await page!.getByTestId('auth.login').click();
  await expect(page!.getByTestId('password.new')).toBeVisible();
  await page!.getByTestId('password.current').fill(INITIAL_PASSWORD);
  await page!.getByTestId('password.new').fill(CHANGED_PASSWORD);
  await page!.getByTestId('password.confirm').fill(CHANGED_PASSWORD);
  await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('session.username')).toHaveText('test-alice');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await expect(page!.getByTestId('updates.status')).toContainText('当前已是最新版本');
}
function ownedPids(): number[] {
  return execFileSync('/bin/ps', ['-axo', 'pid=,command='], { encoding: 'utf8' }).split('\n')
    .map(line => line.trim().match(/^(\d+)\s+(.*)$/))
    .filter((match): match is RegExpMatchArray => Boolean(match && match[2]!.startsWith(binary)))
    .map(match => Number(match[1]));
}
async function waitForAutonomousPid(oldPid: number, priorLaunches: number): Promise<number> {
  const end = Date.now() + 180_000;
  while (Date.now() < end) {
    const pids = ownedPids();
    if (!pids.includes(oldPid) && pids.length === 1 && pids[0] !== oldPid && runnerLaunches === priorLaunches)
      return pids[0]!;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error('Native updater did not autonomously replace the owned App process');
}
async function control(stage: 'forbidden' | 'redirect' | 'redirect-allowed' | 'redirect-multi' | 'invalid' | 'valid'): Promise<void> {
  const response = await fetch(required(c.update_control_url, 'update_control_url') + '/' + stage,
    { method: 'POST', headers: { Authorization: 'Bearer ' + required(c.update_control_token, 'update_control_token') } });
  if (response.status !== 200) throw new Error(`Owned update source refused stage ${stage}`);
  const body = await response.json() as { stage: string; nonce: string };
  if (body.stage !== stage || body.nonce !== c.update_nonce) throw new Error('Owned update source stage or nonce differs');
}
async function observations(): Promise<RequestObservation[]> {
  const response = await fetch(new URL('/observations', required(c.update_url, 'update_url')),
    { headers: { Authorization: 'Bearer ' + required(c.update_control_token, 'update_control_token') } });
  if (response.status !== 200) throw new Error('Owned update observations unavailable');
  const body = await response.json() as { nonce: string; requests: RequestObservation[] };
  if (body.nonce !== c.update_nonce) throw new Error('Owned update source nonce differs');
  return body.requests;
}
async function metadata(): Promise<UpdateMetadata> {
  const response = await fetch(required(c.update_url, 'update_url'));
  if (response.status !== 200) throw new Error('Owned staged metadata unavailable');
  return response.json() as Promise<UpdateMetadata>;
}
async function deniedTarget(): Promise<Array<{ route: string; probe: boolean; time: string }>> {
  const response = await fetch(required(c.forbidden_target_observations_url, 'forbidden_target_observations_url'),
    { headers: { Authorization: 'Bearer ' + required(c.forbidden_target_token, 'forbidden_target_token') } });
  if (response.status !== 200) throw new Error('Owned denied-target observations unavailable');
  const body = await response.json() as { requests: Array<{ route: string; probe: boolean; time: string }> };
  if (!Array.isArray(body.requests)) throw new Error('Owned denied-target request log is malformed');
  return body.requests;
}
function credentialPath(): string {
  return join(c.profile_path, 'credentials', sha256(c.service_url) + '.token');
}
function savedToken(): string {
  const token = readFileSync(credentialPath(), 'utf8');
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw new Error('Real App did not save an opaque session');
  return token;
}
async function me(token: string): Promise<number> {
  const response = await fetch(c.service_url + '/v1/me', { headers: { Authorization: 'Bearer ' + token } });
  await response.body?.cancel();
  return response.status;
}
function meLogCount(): number {
  const log = readFileSync(c.service_log_path, 'utf8');
  return [...log.matchAll(/"GET \/v1\/me HTTP\/[0-9.]+" 200/g)].length;
}
function runtimePath(): string { return join(dirname(c.app_path), 'TokenMeter.runtime.json'); }
function runtimeDetails(): { digest: string; mode: number; profile: string; port: number } {
  const path = runtimePath();
  const raw = readFileSync(path);
  const value = JSON.parse(raw.toString('utf8')) as { profile_path: string; diagnostic_cdp_port: number };
  return { digest: sha256(raw), mode: lstatSync(path).mode & 0o777,
    profile: value.profile_path, port: value.diagnostic_cdp_port };
}
function temporaryDownloadEntries(): string[] {
  return readdirSync(c.profile_path).filter(name => name.startsWith('update-'));
}
function openedFilePaths(pid: number): string[] {
  const result = execFileSync('/usr/sbin/lsof', ['-nP', '-p', String(pid), '-Fn'],
    { encoding: 'utf8', timeout: 10_000, maxBuffer: 4 * 1024 * 1024 });
  return result.split('\n').filter(line => line.startsWith('n')).map(line => line.slice(1));
}
async function attachPhaseObserver(): Promise<string[]> {
  const history: string[] = [];
  await page!.exposeFunction('tmRecordUpdatePhase', (text: string) => { history.push(text); });
  await page!.evaluate(() => {
    const node = document.querySelector('[data-testid="updates.status"]');
    if (!node) throw new Error('Real update status element missing');
    const report = () => void (window as unknown as { tmRecordUpdatePhase: (value: string) => Promise<void> })
      .tmRecordUpdatePhase(node.textContent ?? '');
    new MutationObserver(report).observe(node, { subtree: true, characterData: true, childList: true });
    report();
  });
  return history;
}
function productRequests(rows: RequestObservation[], stage: 'invalid' | 'valid' | 'forbidden'): {
  metadata: RequestObservation[]; archive: RequestObservation[] } {
  return { metadata: rows.filter(row => row.stage === stage && row.method === 'GET' && row.route === '/version.json' && row.status === 200),
    archive: rows.filter(row => row.stage === stage && row.method === 'GET' && row.route === '/update.zip' && row.status === 200) };
}
async function reconnectAutonomous(): Promise<Page> {
  const endpoint = `http://127.0.0.1:${required(c.cdp_port, 'cdp_port')}`;
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try { reconnected = await chromium.connectOverCDP(endpoint, { timeout: 2000 }); break; }
    catch { await new Promise(resolve => setTimeout(resolve, 300)); }
  }
  if (!reconnected) throw new Error('Autonomously restarted App did not expose owned loopback CDP');
  const renderer = reconnected.contexts()[0]?.pages().find(item => item.url().startsWith('tokenmeter://app/'));
  if (!renderer) throw new Error('Reconnected owned process has no real TokenMeter renderer');
  page = renderer;
  return renderer;
}
type Upgrade = { oldPid: number; newPid: number; launchesAtHandoff: number;
  before: RequestObservation[]; after: RequestObservation[]; meta: UpdateMetadata;
  phaseHistory: string[]; startedAt: string; replacedAt: string };
async function nativeUpgrade(): Promise<Upgrade> {
  const oldPid = required(app?.process().pid, 'old App PID');
  const phaseHistory = await attachPhaseObserver();
  await control('valid');
  const meta = await metadata();
  const before = await observations();
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  await expect(page!.getByTestId('updates.status')).toContainText('v0.1.1');
  await stopTrace(); // Squirrel will close the old renderer before Playwright can stop tracing.
  const launchesAtHandoff = runnerLaunches;
  const startedAt = new Date().toISOString();
  await page!.getByTestId('updates.install').click();
  const newPid = await waitForAutonomousPid(oldPid, launchesAtHandoff);
  const replacedAt = new Date().toISOString();
  app = null; page = null;
  const after = await observations();
  await reconnectAutonomous();
  const evidence = { run_id: c.run_id, case_id: c.case_id, old_pid: oldPid, new_pid: newPid,
    runner_launches_before_handoff: launchesAtHandoff, runner_launches_after_handoff: runnerLaunches,
    started_at: startedAt, replaced_at: replacedAt, observed_phases: phaseHistory,
    installed_executable: binary, owned_app_pids: ownedPids() };
  writeFileSync(join(output!, 'upgrade-process.json'), JSON.stringify(evidence, null, 2) + '\n', { mode: 0o600 });
  return { oldPid, newPid, launchesAtHandoff, before, after, meta,
    phaseHistory, startedAt, replacedAt };
}

test.beforeEach(async ({}, info) => {
  if (info.title !== c.case_id) throw new Error('Runner TC identity differs from Playwright test');
  if (!c.update_url || !c.update_control_url || !c.update_control_token || !c.update_nonce)
    throw new Error('Owned same-machine update fixture is missing');
});
test.afterEach(async () => {
  try { if (page && !page.isClosed()) await page.screenshot({ path: join(output!, 'final.png') }); }
  catch { /* Preserve the original failure; the runner validates screenshots. */ }
  try { await close(); } catch { /* The runner owns final process cleanup. */ }
  try { await reconnected?.close(); } catch { /* CDP disconnection is not an App relaunch. */ }
});

test('TC-TM001-UPDATE-01', async () => {
  await launch();
  await expect(page!.getByTestId('auth.server')).toHaveValue('http://127.0.0.1:49176');
  await page!.getByTestId('configuration.open').click();
  const defaultFeed = await page!.getByTestId('configuration.update-url').inputValue();
  await page!.getByTestId('configuration.cancel').click();
  await configureOwned();
  const beforeLogin = await observations();
  await step(1, '未登录核对内置地址并经真实配置UI切换owned更新源', 'ui',
    { defaultApi: true, defaultFeed: true, unauthenticated: true, noPrematureCheck: true },
    { defaultApi: true, defaultFeed: defaultFeed === 'http://127.0.0.1:49177/version.json',
      unauthenticated: await page!.getByTestId('auth.login').isVisible(),
      noPrematureCheck: beforeLogin.every(row => row.route !== '/version.json') });

  await memberReady();
  const oldPid = required(app?.process().pid, 'old App PID');
  const oldTree = originalTreeHash();
  const idle = await observations();
  await step(2, '登录与改密后由真实App自动读取idle清单', 'service',
    { autoCurrent: true, idleRequest: true, noArchive: true, verified: true },
    { autoCurrent: (await page!.getByTestId('updates.status').textContent())?.includes('当前已是最新版本') === true,
      idleRequest: idle.some(row => row.stage === 'current' && row.route === '/version.json' && row.status === 204),
      noArchive: idle.every(row => row.route !== '/update.zip'),
      verified: await page!.getByTestId('session.verified').isVisible() });

  await control('valid');
  const beforeCheck = await observations();
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  const checked = await observations();
  await step(3, '同一更新源改为build101后只点击检查更新', 'ui',
    { versionOffered: true, build100: true, validMetadataRead: true, noArchive: true },
    { versionOffered: (await page!.getByTestId('updates.status').textContent())?.includes('v0.1.1') === true,
      build100: (await page!.getByTestId('app.build').textContent())?.includes('build 100') === true,
      validMetadataRead: checked.slice(beforeCheck.length).some(row => row.stage === 'valid' && row.route === '/version.json' && row.status === 200),
      noArchive: checked.every(row => row.route !== '/update.zip') });

  const noNativeCache = temporaryDownloadEntries().length === 0;
  const observed = mainObservations(output!);
  const updateOrigin = new URL(required(c.update_url, 'update_url')).origin;
  const allowedOrigins = new Set([new URL(c.service_url).origin, updateOrigin]);
  const observedRequests = observed.filter(row => row.kind === 'request');
  const observedNative = observed.filter(row => row.kind === 'native-updater');
  await step(4, '安装确认前核对源请求、进程和原App树', 'process',
    { noArchive: true, noNativeCache: true, oldProcessOnly: true, oldAppTree: true, installStillRequiresClick: true,
      observerBeforeEntry: true, observedEgressOnlyOwned: true, observedMetadataOnly: true, nativeHandoffCount: 0 },
    { noArchive: (await observations()).every(row => row.route !== '/update.zip'),
      noNativeCache, oldProcessOnly: JSON.stringify(ownedPids()) === JSON.stringify([oldPid]),
      oldAppTree: originalTreeHash() === oldTree && oldTree === c.expected_app_tree_sha256,
      installStillRequiresClick: await page!.getByTestId('updates.install').isVisible(),
      observerBeforeEntry: observed[0]?.kind === 'installed-before-entry' && observed[0]?.pid === oldPid &&
        observed.every(row => row.run_id === c.run_id && row.case_id === c.case_id && row.pid === oldPid),
      observedEgressOnlyOwned: observedRequests.every(row => allowedOrigins.has(row.origin ?? '')),
      observedMetadataOnly: observedRequests.some(row => row.origin === updateOrigin && row.path === '/version.json') &&
        observedRequests.filter(row => row.origin === updateOrigin).every(row => row.path === '/version.json'),
      nativeHandoffCount: observedNative.length });
});

test('TC-TM001-UPDATE-02', async () => {
  await launch(); await configureOwned(); await memberReady();
  const oldPid = required(app?.process().pid, 'old App PID');
  const oldTree = originalTreeHash();
  const initialTarget = await deniedTarget();
  await control('forbidden');
  const before = await observations();
  const meta = await metadata(); // Prove the offered URL points to the owned reachable non-loopback target.
  const afterProbe = await observations();
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_source_rejected');
  const source = await observations();
  await step(1, '保存原App基线并点击检查非回环HTTP下载清单', 'ui',
    { originalBuild: '100', sourceRejected: true, ownedTarget: true },
    { originalBuild: buildVersion().build,
      sourceRejected: (await page!.getByTestId('updates.status').textContent())?.includes('update_source_rejected') === true,
      ownedTarget: meta.url === c.forbidden_target_url && new URL(meta.url).hostname !== '127.0.0.1' });
  const product = productRequests(source.slice(afterProbe.length), 'forbidden');
  const target = await deniedTarget();
  await step(2, '对照本机清单请求与独立可达目标的零下载记录', 'service',
    { sourceManifestRead: true, targetProbeReached: true, targetProductRequests: 0, noArchiveFromSource: true },
    { sourceManifestRead: product.metadata.length >= 1 && afterProbe.length > before.length,
      targetProbeReached: initialTarget.some(row => row.route === '/probe' && row.probe),
      targetProductRequests: target.filter(row => !row.probe).length,
      noArchiveFromSource: product.archive.length === 0 });
  await step(3, '核对拒绝前后进程、安装内容及真实身份仍保持', 'process',
    { samePid: true, sameTree: true, oldBuild: true, sessionVerified: true, noTemporaryArchive: true },
    { samePid: JSON.stringify(ownedPids()) === JSON.stringify([oldPid]),
      sameTree: originalTreeHash() === oldTree && oldTree === c.expected_app_tree_sha256,
      oldBuild: buildVersion().build === '100',
      sessionVerified: await me(savedToken()) === 200 && await page!.getByTestId('session.verified').isVisible(),
      noTemporaryArchive: temporaryDownloadEntries().length === 0 });
});

test('TC-TM001-UPDATE-03', async () => {
  await launch(); await configureOwned(); await memberReady();
  const oldPid = required(app?.process().pid, 'old App PID');
  const oldTree = originalTreeHash();
  const targetBefore = await deniedTarget();
  await control('redirect');
  const sourceBefore = await observations();
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  await page!.getByTestId('updates.install').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_transport_rejected');
  const afterRedirect = await observations();
  const product = afterRedirect.slice(sourceBefore.length);
  await step(1, '真实UI检查并安装本机302清单', 'service',
    { localManifest: true, localRedirect: true, noLocalArchive: true },
    { localManifest: product.some(row => row.stage === 'redirect' && row.route === '/version.json' && row.status === 200),
      localRedirect: product.some(row => row.stage === 'redirect' && row.route === '/redirect.zip' && row.status === 302),
      noLocalArchive: !product.some(row => row.stage === 'redirect' && row.route === '/update.zip') });
  await step(2, '302目标被客户端在跟随前拒绝', 'ui',
    { transportRejected: true, noPrematureAppExit: true },
    { transportRejected: (await page!.getByTestId('updates.status').textContent())?.includes('update_transport_rejected') === true,
      noPrematureAppExit: JSON.stringify(ownedPids()) === JSON.stringify([oldPid]) });
  const targetAfter = await deniedTarget();
  await step(3, '独立目标零请求且原生更新没有替换App', 'process',
    { targetReachable: true, targetProductRequests: 0, oldBuild: true, sameTree: true, noNativeArchive: true },
    { targetReachable: targetBefore.some(row => row.probe && row.route === '/probe'),
      targetProductRequests: targetAfter.filter(row => !row.probe).length,
      oldBuild: buildVersion().build === '100',
      sameTree: originalTreeHash() === oldTree && oldTree === c.expected_app_tree_sha256,
      noNativeArchive: temporaryDownloadEntries().length === 0 });

  // Allowed hop is a control: the real App must download the complete ZIP and
  // reach the deliberately bad signature. Then a two-hop chain must stop at
  // the first forbidden destination, without touching the independent target.
  await control('redirect-allowed');
  const allowedBefore = await observations();
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  await page!.getByTestId('updates.install').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_signature_rejected');
  const allowedSignatureRejected = (await page!.getByTestId('updates.status').textContent())?.includes('update_signature_rejected') === true;
  const allowedAfter = await observations();
  const allowed = allowedAfter.slice(allowedBefore.length);
  await control('redirect-multi');
  const multiBefore = await observations();
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  await page!.getByTestId('updates.install').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_transport_rejected');
  const multi = (await observations()).slice(multiBefore.length);
  const finalTarget = await deniedTarget();
  await step(4, '合法回环跳转完成下载，双跳在非法目标前停止', 'service',
    { allowedHop302: true, allowedArchive200: true, allowedSignatureRejected: true,
      firstHop302: true, secondHop302: true, deniedTargetRequests: 0,
      oldAppUnchanged: true },
    { allowedHop302: allowed.some(row => row.stage === 'redirect-allowed' && row.route === '/redirect-allowed.zip' && row.status === 302),
      allowedArchive200: allowed.some(row => row.stage === 'redirect-allowed' && row.route === '/update.zip' && row.status === 200 && row.bytes_sent > 0),
      allowedSignatureRejected,
      firstHop302: multi.some(row => row.stage === 'redirect-multi' && row.route === '/redirect-first.zip' && row.status === 302),
      secondHop302: multi.some(row => row.stage === 'redirect-multi' && row.route === '/redirect.zip' && row.status === 302),
      deniedTargetRequests: finalTarget.filter(row => !row.probe).length,
      oldAppUnchanged: buildVersion().build === '100' && originalTreeHash() === oldTree &&
        JSON.stringify(ownedPids()) === JSON.stringify([oldPid]) });
});

test('TC-TM001-UPDATE-04', async () => {
  await launch(); await configureOwned(); await memberReady();
  const oldPid = required(app?.process().pid, 'old App PID');
  const oldTree = originalTreeHash();
  const originalConfig = buildConfig();
  await control('invalid');
  const before = await observations();
  const meta = await metadata(); // Independent reference; product request is counted after this probe.
  const afterProbe = await observations();
  await page!.getByTestId('updates.check').click();
  await expect(page!.getByTestId('updates.install')).toBeVisible();
  await page!.getByTestId('updates.install').click();
  await expect(page!.getByTestId('updates.status')).toContainText('update_signature_rejected');
  const after = await observations();
  const product = productRequests(after.slice(afterProbe.length), 'invalid');
  const archive = product.archive[0];
  await step(1, '真实UI确认安装并核对完整ZIP传输与独立元数据', 'service',
    { sourceReady: true, productMetadata: true, archiveCount: 1, completeBytes: true, matchingSha: true },
    { sourceReady: afterProbe.slice(before.length).some(row => row.stage === 'invalid' && row.route === '/version.json' && row.status === 200),
      productMetadata: product.metadata.length >= 1, archiveCount: product.archive.length,
      completeBytes: archive?.bytes_sent === meta.bytes && meta.bytes > 0,
      matchingSha: archive?.body_sha256 === meta.sha256 && /^[a-f0-9]{64}$/.test(meta.sha256) });
  await step(2, '观察Ed25519拒绝与安装包内固定公钥', 'ui',
    { signatureRejected: true, keyUnchanged: true, build100: true },
    { signatureRejected: (await page!.getByTestId('updates.status').textContent())?.includes('update_signature_rejected') === true,
      keyUnchanged: buildConfig().update_public_key === originalConfig.update_public_key,
      build100: (await page!.getByTestId('app.build').textContent())?.includes('build 100') === true });
  await step(3, '拒绝后核对无Squirrel替换与原App、会话不变', 'process',
    { samePid: true, sameTree: true, oldBuild: true, verifiedSession: true,
      observerBeforeEntry: true, nativeHandoffCount: 0 },
    { samePid: JSON.stringify(ownedPids()) === JSON.stringify([oldPid]),
      sameTree: originalTreeHash() === oldTree && oldTree === c.expected_app_tree_sha256,
      oldBuild: buildVersion().build === '100',
      verifiedSession: await me(savedToken()) === 200 && await page!.getByTestId('session.verified').isVisible(),
      observerBeforeEntry: mainObservations(output!)[0]?.kind === 'installed-before-entry' &&
        mainObservations(output!)[0]?.pid === oldPid,
      nativeHandoffCount: mainObservations(output!).filter(row => row.kind === 'native-updater').length });
  await step(4, '保留源摘要与请求证据并核对临时下载已清理', 'filesystem',
    { temporaryDownloads: 0, noHigherApp: true, sourceEvidence: true, noPrivateKeyInEvents: true },
    { temporaryDownloads: temporaryDownloadEntries().length,
      noHigherApp: buildVersion().build === '100',
      sourceEvidence: archive?.body_sha256 === meta.sha256 && archive?.bytes_sent === meta.bytes,
      noPrivateKeyInEvents: !readFileSync(eventPath, 'utf8').includes('PRIVATE KEY') });
});

test('TC-TM001-UPDATE-06', async () => {
  await launch(true); await configureOwned(); await memberReady();
  const oldTree = originalTreeHash();
  const oldConfig = buildConfig();
  const upgrade = await nativeUpgrade();
  const product = productRequests(upgrade.after.slice(upgrade.before.length), 'valid');
  const archive = product.archive[0];
  const installed = buildVersion();
  const actualTree = originalTreeHash();
  const actualConfig = buildConfig();
  const phaseText = upgrade.phaseHistory.join('\n');
  await step(1, '真实UI确认安装并核对下载、验证、原生交接前条件', 'service',
    { metadataRead: true, completeArchive: true, matchingSha: true, validVersion: true,
      verifiedPhase: true, nativeResult: true },
    { metadataRead: product.metadata.length >= 1,
      completeArchive: product.archive.length === 1 && archive?.bytes_sent === upgrade.meta.bytes,
      matchingSha: archive?.body_sha256 === upgrade.meta.sha256,
      validVersion: upgrade.meta.version === '0.1.1' && upgrade.meta.build === c.expected_upgrade_build,
      verifiedPhase: phaseText.includes('正在验证更新签名') || phaseText.includes('更新验证完成') || phaseText.includes('正在安装并重新启动'),
      nativeResult: installed.build === c.expected_upgrade_build && actualTree === c.expected_update_tree_sha256 });
  await step(2, '只观察Squirrel自主退出旧PID并产生唯一新PID', 'process',
    { oldExited: true, oneNewPid: true, noTestRelaunch: true },
    { oldExited: !ownedPids().includes(upgrade.oldPid),
      oneNewPid: JSON.stringify(ownedPids()) === JSON.stringify([upgrade.newPid]) && upgrade.newPid !== upgrade.oldPid,
      noTestRelaunch: runnerLaunches === upgrade.launchesAtHandoff });
  await step(3, '外部核对owned安装路径、Info版本、实际App树与签名配置', 'filesystem',
    { sameOwnedPath: true, version: '0.1.1', build: c.expected_upgrade_build,
      installedTree: true, sameBundle: true, sameUpdateKey: true, oldTreeCorrect: true },
    { sameOwnedPath: ownedPids().length === 1 && existsSync(binary),
      version: installed.version, build: installed.build,
      installedTree: actualTree === c.expected_update_tree_sha256,
      sameBundle: actualConfig.bundle_id === oldConfig.bundle_id && actualConfig.bundle_id.length > 0,
      sameUpdateKey: actualConfig.update_public_key === oldConfig.update_public_key && actualConfig.update_public_key.length > 0,
      oldTreeCorrect: oldTree === c.expected_app_tree_sha256 });
  await expect(page!.getByTestId('app.build')).toContainText('build 101');
  await step(4, '只重连已有新进程并读取真实UI版本', 'ui',
    { displayed101: true, runningOwnedPid: true, noTestRelaunch: true },
    { displayed101: (await page!.getByTestId('app.build').textContent())?.includes('build 101') === true,
      runningOwnedPid: ownedPids()[0] === upgrade.newPid,
      noTestRelaunch: runnerLaunches === upgrade.launchesAtHandoff });
  await step(5, '核对同一源请求、完整包、旧新进程和安装时间线', 'process',
    { sameSource: true, archiveOnce: true, orderedPids: true, finalTree: true,
      nativeFeedObserved: true, nativeCheckObserved: true, nativeInstallObserved: true },
    { sameSource: upgrade.after.slice(upgrade.before.length).every(row => row.stage === 'valid'),
      archiveOnce: product.archive.length === 1,
      orderedPids: Date.parse(upgrade.startedAt) <= Date.parse(upgrade.replacedAt) && upgrade.oldPid !== upgrade.newPid,
      finalTree: originalTreeHash() === c.expected_update_tree_sha256,
      nativeFeedObserved: mainObservations(output!).some(row => row.kind === 'native-updater' && row.method === 'setFeedURL'),
      nativeCheckObserved: mainObservations(output!).some(row => row.kind === 'native-updater' && row.method === 'checkForUpdates'),
      nativeInstallObserved: mainObservations(output!).some(row => row.kind === 'native-updater' && row.method === 'quitAndInstall') });
  writeFileSync(join(output!, 'upgrade-result.json'), JSON.stringify({ run_id: c.run_id, case_id: c.case_id,
    old_pid: upgrade.oldPid, new_pid: upgrade.newPid, old_build: '100', new_build: installed.build,
    old_tree_sha256: oldTree, new_tree_sha256: actualTree, source_request_count: product.metadata.length,
    source_archive_count: product.archive.length, runner_launches_after_handoff: runnerLaunches - upgrade.launchesAtHandoff }, null, 2) + '\n', { mode: 0o600 });
});

test('TC-TM001-UPDATE-07', async () => {
  await launch(true); await configureOwned();
  const autoLoginBefore = await page!.getByTestId('auth.automatic-login').isChecked();
  await memberReady();
  const profileBefore = await app!.evaluate(({ app: electronApp }) => electronApp.getPath('userData'));
  const runtimeBefore = runtimeDetails();
  const tokenBefore = savedToken();
  const fingerprintBefore = sha256(tokenBefore);
  const configBefore = buildConfig();
  const countBefore = meLogCount();
  await page!.getByTestId('configuration.open').click();
  const apiBefore = await page!.getByTestId('configuration.api-url').inputValue();
  const feedBefore = await page!.getByTestId('configuration.update-url').inputValue();
  await page!.getByTestId('configuration.cancel').click();
  await step(1, '升级前记录真实userData、runtime、手动地址与会话指纹', 'filesystem',
    { ownedProfile: true, runtimeMode: 0o600, runtimeProfile: true,
      configuredApi: true, configuredFeed: true, tokenShape: true, automaticLogin: true },
    { ownedProfile: profileBefore === c.profile_path && c.profile_path !== join(process.env.HOME ?? '', 'Library/Application Support/TokenMeter'),
      runtimeMode: runtimeBefore.mode, runtimeProfile: runtimeBefore.profile === c.profile_path && runtimeBefore.port === c.cdp_port,
      configuredApi: apiBefore === c.service_url && configBefore.api_url !== c.service_url,
      configuredFeed: feedBefore === c.update_url && configBefore.update_feed_url !== c.update_url,
      tokenShape: /^[a-f0-9]{64}$/.test(fingerprintBefore), automaticLogin: autoLoginBefore });
  const upgrade = await nativeUpgrade();
  const runtimeAfter = runtimeDetails();
  await step(2, 'Squirrel自主重启后只重连新进程并核对runtime及profile归属', 'process',
    { autonomous: true, sameRuntime: true, sameProfile: true, sameMode: true, noUserProfile: true },
    { autonomous: upgrade.oldPid !== upgrade.newPid && !ownedPids().includes(upgrade.oldPid) && runnerLaunches === upgrade.launchesAtHandoff,
      sameRuntime: runtimeAfter.digest === runtimeBefore.digest,
      sameProfile: runtimeAfter.profile === profileBefore,
      sameMode: runtimeAfter.mode === 0o600,
      noUserProfile: runtimeAfter.profile === c.profile_path });
  await expect(page!.getByTestId('session.username')).toHaveText('test-alice');
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const countAfter = meLogCount();
  await step(3, '不输入密码，等待服务A真实me成功后确认新UI alice身份', 'service',
    { newMe200: true, verifiedAlice: true, sameToken: true },
    { newMe200: countAfter > countBefore,
      verifiedAlice: await page!.getByTestId('session.username').textContent() === 'test-alice' && await page!.getByTestId('session.verified').isVisible(),
      sameToken: sha256(savedToken()) === fingerprintBefore && await me(tokenBefore) === 200 });
  const beforeRefresh = meLogCount();
  await page!.getByTestId('session.refresh').click();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  await page!.getByTestId('configuration.open').click();
  const apiAfter = await page!.getByTestId('configuration.api-url').inputValue();
  const feedAfter = await page!.getByTestId('configuration.update-url').inputValue();
  const configAfter = buildConfig();
  await step(4, '刷新身份并通过配置UI核对地址、自动登录与固定公钥', 'ui',
    { refreshedMe200: true, apiOverride: c.service_url, feedOverride: c.update_url,
      automaticLogin: true, samePublicKey: true },
    { refreshedMe200: meLogCount() > beforeRefresh,
      apiOverride: apiAfter, feedOverride: feedAfter,
      automaticLogin: existsSync(credentialPath()),
      samePublicKey: configAfter.update_public_key === configBefore.update_public_key });
  await page!.getByTestId('configuration.cancel').click();
  const opened = openedFilePaths(upgrade.newPid);
  const defaultProfile = join(required(process.env.HOME, 'HOME'), 'Library/Application Support/TokenMeter');
  const profileFiles = opened.filter(name => name.startsWith(c.profile_path + '/'));
  const defaultProfileFiles = opened.filter(name => name === defaultProfile || name.startsWith(defaultProfile + '/'));
  writeFileSync(join(output!, 'process-open-files.json'), JSON.stringify({run_id: c.run_id,
    case_id: c.case_id, pid: upgrade.newPid, observed_at: new Date().toISOString(),
    all_open_paths: opened, owned_profile_paths: profileFiles,
    default_profile: defaultProfile, default_profile_paths: defaultProfileFiles}, null, 2) + '\n', {mode: 0o600});
  await step(5, '从新PID的打开文件核对真实profile及origin凭据位置', 'process',
    { newPidOwnsProfile: true, originCredentialOwned: true, noUserProfile: true },
    { newPidOwnsProfile: profileFiles.length > 0,
      originCredentialOwned: existsSync(credentialPath()) && (lstatSync(credentialPath()).mode & 0o777) === 0o600,
      noUserProfile: c.profile_path !== defaultProfile && defaultProfileFiles.length === 0 });
  writeFileSync(join(output!, 'upgrade-result.json'), JSON.stringify({ run_id: c.run_id, case_id: c.case_id,
    old_pid: upgrade.oldPid, new_pid: upgrade.newPid, profile_before_matches_owned: profileBefore === c.profile_path,
    runtime_digest_before: runtimeBefore.digest, runtime_digest_after: runtimeAfter.digest,
    token_fingerprint_before: fingerprintBefore, token_fingerprint_after: sha256(savedToken()),
    me_success_before: countBefore, me_success_after: meLogCount(), profile_open_file_count: profileFiles.length,
    all_open_file_count: opened.length, default_profile_open_file_count: defaultProfileFiles.length,
    process_open_files: 'process-open-files.json' }, null, 2) + '\n', { mode: 0o600 });
});

test('TC-TM001-UPDATE-08', async()=>{
  const owned=JSON.parse(readFileSync(contextPath!,'utf8')) as {shipit_cache_path:string;shipit_negative_probe_path:string};
  const negative=JSON.parse(readFileSync(owned.shipit_negative_probe_path,'utf8')) as {passed:boolean;results:{blocked:boolean;unchanged:boolean}[]};
  await launch(true);await configureOwned();await memberReady();
  await step(1,'未知缓存/job/ByHost的独立隔离负例均阻断且原件不变','runner',
    {count:3,blockedAndUnchanged:true},{count:negative.results.length,blockedAndUnchanged:negative.passed&&negative.results.every(r=>r.blocked&&r.unchanged)});
  const marker=JSON.parse(readFileSync(join(owned.shipit_cache_path,'.tokenmeter-owner.json'),'utf8'));
  const health=await fetch(new URL('/health',c.update_url!));const nonce=await health.text();
  await step(2,'真实更新源nonce及缓存owner与本轮匹配','filesystem',
    {owner:true,privateMode:true,nonce:true,loopback:true},
    {owner:marker.run_id===c.run_id&&marker.owner==='tokenmeter-local-e2e',privateMode:(lstatSync(owned.shipit_cache_path).mode&0o777)===0o700,nonce:nonce===c.update_nonce,loopback:new URL(c.update_url!).hostname==='127.0.0.1'});
  for(const stage of ['forbidden','redirect','invalid'] as const){
    await control(stage);await page!.getByTestId('updates.check').click();
    if(stage!=='forbidden'){await expect(page!.getByTestId('updates.install')).toBeVisible();await page!.getByTestId('updates.install').click();}
    const rejected={forbidden:'update_source_rejected',redirect:'update_transport_rejected',invalid:'update_signature_rejected'};
    await expect(page!.getByTestId('updates.status')).toContainText(rejected[stage]);
  }
  await nativeUpgrade();
  const state=JSON.parse(readFileSync(join(owned.shipit_cache_path,'ShipItState.plist'),'utf8')) as {targetBundleURL:string};
  const target=decodeURIComponent(new URL(state.targetBundleURL).pathname).replace(/\/$/,'');
  await step(3,'四阶段结束后真实ShipIt目标精确归属本轮安装','filesystem',
    {ownerMatches:true,targetMatches:true,upgraded:true},
    {ownerMatches:marker.run_id===c.run_id,targetMatches:target===c.app_path,upgraded:buildVersion().build==='101'});
  // Steps 4 and 5 are recorded by the runner after terminating and cleaning the
  // very process executing this case. They cannot be certified from inside it.
});
