import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, chmodSync, readFileSync, writeFileSync, statSync, symlinkSync, linkSync, rmSync, realpathSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { canonicalOrigin } from '../src/main/validation.ts';
import { CredentialStore, resolveProfile } from '../src/main/storage.ts';
import { Accounts } from '../src/main/accounts.ts';
import { validateUpdateURL } from '../src/main/updater.ts';
test('API origin admits exact loopback HTTP and canonicalizes HTTPS', () => {
  assert.equal(canonicalOrigin('http://127.0.0.1:49176/'), 'http://127.0.0.1:49176');
  assert.equal(canonicalOrigin('https://EXAMPLE.com:443'), 'https://example.com');
  for (const url of ['http://example.com', 'http://127.1', 'http://2130706433', 'http://localhost:', 'https://u:p@host', 'https://host/path', 'https://host?a=b', 'https://host#f']) assert.throws(() => canonicalOrigin(url), url);
});
test('diagnostic port requires explicit profile and stays bound to the installed app', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm-diagnostic-'))); chmodSync(root, 0o700);
  try {
    const appPath = join(root, 'TokenMeter.app'); const defaultPath = join(root, 'default'); const profile = join(root, 'profile');
    for (const argv of [['--diagnostic-cdp-port=32000'], [`--user-data-dir=${profile}`, '--diagnostic-cdp-port=0'], [`--user-data-dir=${profile}`, '--diagnostic-cdp-port=65536'], [`--user-data-dir=${profile}`, '--diagnostic-cdp-port=80']]) assert.throws(() => resolveProfile({appPath, defaultPath, argv}));
    resolveProfile({appPath, defaultPath, argv: [`--user-data-dir=${profile}`, '--diagnostic-cdp-port=32000']});
    const sidecar = join(root, 'TokenMeter.runtime.json'); const data = JSON.parse(readFileSync(sidecar, 'utf8'));
    assert.equal(data.diagnostic_cdp_port, 32000); assert.equal(resolveProfile({appPath, defaultPath, argv: []}), profile);
    assert.throws(() => resolveProfile({appPath: join(root, 'Other.app'), defaultPath, argv: []}));
    writeFileSync(sidecar, JSON.stringify({...data, diagnostic_cdp_port: '32000'})); assert.throws(() => resolveProfile({appPath, defaultPath, argv: []}));
    writeFileSync(sidecar, JSON.stringify(data)); chmodSync(sidecar, 0o644); assert.throws(() => resolveProfile({appPath, defaultPath, argv: []}));
  } finally { rmSync(root, {recursive: true, force: true}); }
});
test('credential files are private, origin-separated and reject symlinks/hardlinks', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm-credentials-'))); chmodSync(root, 0o700);
  try {
    const a = new CredentialStore(root, 'https://a.example'); const b = new CredentialStore(root, 'https://b.example');
    a.write('A'.repeat(43)); assert.equal(a.read(), 'A'.repeat(43)); assert.equal(b.read(), null);
    assert.equal(statSync(a.path).mode & 0o777, 0o600);
    assert.equal(readFileSync(a.path, 'utf8'), 'A'.repeat(43));
    linkSync(a.path, join(root, 'hardlink')); assert.throws(() => a.read()); rmSync(join(root, 'hardlink'));
    a.clear(); symlinkSync('/etc/hosts', a.path); assert.throws(() => a.read()); assert.throws(() => a.write('B'.repeat(43)));
  } finally { rmSync(root, { recursive: true, force: true }); }
});
test('unsafe saved credential never restores an identity or changes an owned sentinel', async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm-credential-restore-'))); chmodSync(root, 0o700);
  const origin = 'http://127.0.0.1:49176'; const saved = 'S'.repeat(43);
  try {
    const credential = new CredentialStore(root, origin);
    const sentinel = join(root, 'sentinel.txt'); writeFileSync(sentinel, saved, {mode: 0o600});
    symlinkSync(sentinel, credential.path);
    const accounts = new Accounts(root, {api_url: origin, update_feed_url: 'http://127.0.0.1:49177/version.json'}, validateUpdateURL, () => {});
    await accounts.restore();
    assert.equal(accounts.error, 'unsafe_storage'); assert.equal(accounts.account, null);
    assert.equal(accounts.identityVerified, false); assert.equal(accounts.canRetryRestore, false);
    assert.equal(readFileSync(sentinel, 'utf8'), saved);
    assert.throws(() => credential.read());
  } finally { rmSync(root, {recursive: true, force: true}); }
});
test('portable profile survives relaunch and refuses corrupted ownership record', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm-profile-'))); chmodSync(root, 0o700);
  try {
    const profile = join(root, 'profile'); const app = join(root, 'TokenMeter.app');
    const first = resolveProfile({ appPath: app, defaultPath: join(root, 'default'), argv: [`--user-data-dir=${profile}`] });
    assert.equal(resolveProfile({ appPath: app, defaultPath: join(root, 'default'), argv: [] }), first);
    chmodSync(join(root, 'TokenMeter.runtime.json'), 0o644);
    assert.throws(() => resolveProfile({ appPath: app, defaultPath: join(root, 'default'), argv: [] }));
  } finally { rmSync(root, { recursive: true, force: true }); }
});
