import { test } from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdtempSync, readFileSync, realpathSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { keychainApplicationName, resolveProfile } from '../src/main/storage.ts';

test('TC-TM002-STORE-02 derives a distinct stable App name for each explicit test profile', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm002-keychain-name-'))); chmodSync(root, 0o700);
  try {
    const defaultPath = join(root, 'TokenMeter');
    const first = keychainApplicationName(join(root, 'run-a'), defaultPath);
    const second = keychainApplicationName(join(root, 'run-b'), defaultPath);
    assert.equal(keychainApplicationName(defaultPath, defaultPath), 'TokenMeter');
    assert.match(first, /^TokenMeter-Test-[a-f0-9]{24}$/);
    assert.equal(first, keychainApplicationName(join(root, 'run-a'), defaultPath));
    assert.notEqual(first, second);
    assert.notEqual(first, 'TokenMeter');
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-EVIDENCE-01#COMPLETE binds source audit nonce to owned runtime sidecar across relaunch', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm002-source-runtime-'))); chmodSync(root, 0o700);
  const app = join(root, 'TokenMeter.app'); const profile = join(root, 'profile'); const nonce = '34'.repeat(32);
  try {
    const first = resolveProfile({appPath: app, defaultPath: join(root, 'default'),
      argv: [`--user-data-dir=${profile}`, `--diagnostic-source-audit-nonce=${nonce}`]});
    assert.equal(first, profile);
    const sidecar = JSON.parse(readFileSync(join(root, 'TokenMeter.runtime.json'), 'utf8'));
    assert.equal(sidecar.diagnostic_source_audit_nonce, nonce);
    assert.equal(resolveProfile({appPath: app, defaultPath: join(root, 'default'), argv: []}), profile);
    assert.throws(() => resolveProfile({appPath: app, defaultPath: join(root, 'default'),
      argv: [`--user-data-dir=${profile}`, `--diagnostic-source-audit-nonce=${'56'.repeat(32)}`]}));
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-EVIDENCE-01#WRONG_PACKAGE refuses free audit nonce without owned profile', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm002-source-runtime-'))); chmodSync(root, 0o700);
  const app = join(root, 'TokenMeter.app'); const nonce = 'ab'.repeat(32);
  try {
    assert.throws(() => resolveProfile({appPath: app, defaultPath: join(root, 'default'),
      argv: [`--diagnostic-source-audit-nonce=${nonce}`]}));
    assert.throws(() => resolveProfile({appPath: app, defaultPath: join(root, 'default'),
      argv: [`--user-data-dir=${join(root, 'profile')}`, '--diagnostic-source-audit-nonce=bad']}));
  } finally { rmSync(root, {recursive: true, force: true}); }
});
