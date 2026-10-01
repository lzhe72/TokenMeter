import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, realpathSync, chmodSync, rmSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createServer } from 'node:http';
import { Accounts, request } from '../src/main/accounts.ts';
import { CredentialStore } from '../src/main/storage.ts';
import { validateUpdateURL } from '../src/main/updater.ts';

const defaults = {api_url: 'http://127.0.0.1:49176', update_feed_url: 'http://127.0.0.1:49177/version.json'};
const user = {id: '12345', username: 'unit_member', role: 'member', is_active: true, must_change_password: false};
const token = 'Z'.repeat(43);
function directory(): string { const dir = realpathSync(mkdtempSync(join(tmpdir(), 'tm-account-unit-'))); chmodSync(dir, 0o700); return dir; }
test('configuration validates both fields before one atomic persistence', () => {
  const dir = directory();
  try {
    const store = new Accounts(dir, defaults, validateUpdateURL, () => {});
    store.saveConfiguration({server: 'https://team.example', feed: 'https://updates.example/version.json'}, true);
    const original = readFileSync(join(dir, 'settings.json'), 'utf8');
    assert.throws(() => store.saveConfiguration({server: 'https://other.example', feed: 'http://external.example/version.json'}, true));
    assert.equal(store.server, 'https://team.example'); assert.equal(readFileSync(join(dir, 'settings.json'), 'utf8'), original);
    const reopened = new Accounts(dir, defaults, validateUpdateURL, () => {}); assert.equal(reopened.server, store.server);
    store.setAutomaticLogin(false);
    store.resetConfiguration(true); assert.equal(store.server, defaults.api_url); assert.equal(store.feed, defaults.update_feed_url);
    assert.deepEqual(JSON.parse(readFileSync(join(dir, 'settings.json'), 'utf8')), {automaticLogin: false});
    const futureDefaults = {api_url: 'http://127.0.0.1:59176', update_feed_url: 'http://127.0.0.1:59177/version.json'};
    const afterUpgrade = new Accounts(dir, futureDefaults, validateUpdateURL, () => {});
    assert.equal(afterUpgrade.server, futureDefaults.api_url); assert.equal(afterUpgrade.feed, futureDefaults.update_feed_url);
    assert.equal(afterUpgrade.automaticLogin, false);
  } finally { rmSync(dir, {recursive: true, force: true}); }
});
test('failed restore can retry only with the same origin and a new verified identity response', async () => {
  const dir = directory(); let failIdentity = true; let identityRequests = 0;
  const service = createServer((req, res) => {
    identityRequests++;
    assert.equal(req.url, '/v1/me'); assert.equal(req.headers.authorization, `Bearer ${token}`);
    res.setHeader('Content-Type', 'application/json');
    if (failIdentity) { res.statusCode = 503; res.end(JSON.stringify({error: {code: 'service_unavailable'}})); }
    else res.end(JSON.stringify(user));
  });
  await new Promise<void>(resolve => service.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${(service.address() as {port: number}).port}`;
  try {
    const store = new Accounts(dir, {...defaults, api_url: origin}, validateUpdateURL, () => {});
    new CredentialStore(dir, origin).write(token);
    await store.restore();
    assert.equal(store.account, null); assert.equal(store.identityVerified, false);
    assert.equal(store.canRetryRestore, true); assert.equal(identityRequests, 1);
    failIdentity = false; await store.refresh();
    assert.deepEqual(store.account, user); assert.equal(store.identityVerified, true);
    assert.equal(store.canRetryRestore, false); assert.equal(identityRequests, 2);
    const changed = new Accounts(dir, {...defaults, api_url: origin}, validateUpdateURL, () => {});
    failIdentity = true; await changed.restore(); assert.equal(changed.canRetryRestore, true);
    changed.saveConfiguration({server: 'https://other.example', feed: defaults.update_feed_url}, true);
    assert.equal(changed.canRetryRestore, false);
    assert.equal(new CredentialStore(dir, origin).read(), token);
  } finally { await new Promise<void>(resolve => service.close(() => resolve())); rmSync(dir, {recursive: true, force: true}); }
});
test('auto-login off never restores persisted credentials', async () => {
  const dir = directory();
  try {
    const store = new Accounts(dir, defaults, validateUpdateURL, () => {});
    store.setAutomaticLogin(false); new CredentialStore(dir, defaults.api_url).write(token);
    await store.restore(); assert.equal(store.account, null); assert.equal(store.error, null);
  } finally { rmSync(dir, {recursive: true, force: true}); }
});
test('invalid temporary passwords fail before an admin request is sent', async () => {
  const dir = directory(); let managementRequests = 0;
  const service = createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/v1/auth/login') { res.end(JSON.stringify({access_token: token, user})); return; }
    managementRequests++; res.end(JSON.stringify(user));
  });
  await new Promise<void>(resolve => service.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${(service.address() as {port: number}).port}`;
  try {
    const store = new Accounts(dir, {...defaults, api_url: origin}, validateUpdateURL, () => {});
    await store.login({server: origin, username: user.username, password: 'unit-password', automaticLogin: false});
    for (const temporaryPassword of ['', 'x'.repeat(11), 'x'.repeat(129)]) {
      await assert.rejects(() => store.manageUser({userId: user.id, action: 'reset-password', temporaryPassword}),
        (error: unknown) => (error as {code?: string}).code === 'invalid_password');
    }
    assert.equal(managementRequests, 0);
  } finally { await new Promise<void>(resolve => service.close(() => resolve())); rmSync(dir, {recursive: true, force: true}); }
});
test('logout clears persistence before response, locks origin on failure, and retries revocation', async () => {
  const dir = directory(); let logoutFails = true; let origin = ''; let observedCleared = false;
  const server = createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/v1/auth/login') { res.end(JSON.stringify({access_token: token, user})); return; }
    assert.equal(req.headers.authorization, `Bearer ${token}`);
    if (req.url === '/v1/auth/logout') {
      observedCleared = new CredentialStore(dir, origin).read() === null;
      if (logoutFails) { res.statusCode = 503; res.end(JSON.stringify({error:{code:'service_unavailable'}})); }
      else { res.statusCode = 204; res.end(); }
      return;
    }
    res.end(JSON.stringify(user));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${(server.address() as {port:number}).port}`;
  try {
    const store = new Accounts(dir, { ...defaults, api_url: origin }, validateUpdateURL, () => {});
    await store.login({server: origin, username: user.username, password: 'unit-password', automaticLogin: true});
    assert.equal(store.account?.username, user.username); assert.equal(new CredentialStore(dir, origin).read(), token);
    assert.equal(JSON.stringify(store).includes(token), false);
    assert.throws(() => store.resetConfiguration(true), /请退出登录/);
    await store.logout(); assert.equal(observedCleared, true); assert.equal(store.account, null); assert.equal(store.pendingLogout, true);
    assert.throws(() => store.saveConfiguration({server: 'https://other.example', feed: defaults.update_feed_url}, true));
    assert.throws(() => store.resetConfiguration(true), /请退出登录/);
    logoutFails = false; await store.retryLogout(); assert.equal(store.pendingLogout, false); assert.equal(store.canConfigureServer, true);
    assert.throws(() => store.resetConfiguration(false), /更新进行中/);
  } finally { await new Promise<void>((resolve, reject) => server.close(e => e ? reject(e) : resolve())); rmSync(dir, {recursive: true, force: true}); }
});
test('authentication refuses redirects before sending token to destination', async () => {
  let destinationRequests = 0;
  const destination = createServer((_req, res) => { destinationRequests++; res.end('{}'); });
  await new Promise<void>(resolve => destination.listen(0, '127.0.0.1', resolve));
  const source = createServer((_req, res) => { res.writeHead(302, {Location: `http://127.0.0.1:${(destination.address() as {port:number}).port}/stolen`}); res.end(); });
  await new Promise<void>(resolve => source.listen(0, '127.0.0.1', resolve));
  try { await assert.rejects(request(`http://127.0.0.1:${(source.address() as {port:number}).port}`, 'GET', '/v1/me', token), /认证请求拒绝重定向/); assert.equal(destinationRequests, 0); }
  finally { await Promise.all([source, destination].map(server => new Promise<void>(resolve => server.close(() => resolve())))); }
});
