import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { chmodSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SourceStore, type ConfirmedSource, type SourceCipher, type SourceIdentity } from '../src/main/source-store.ts';
import { privateWrite } from '../src/main/storage.ts';

class TestCipher implements SourceCipher {
  available = true;
  decryptFails = false;
  private plaintext = new Map<string, string>();
  async isAsyncEncryptionAvailable(): Promise<boolean> { return this.available; }
  async encryptStringAsync(value: string): Promise<Buffer> {
    if (!this.available) throw new Error('key_unavailable');
    const token = Buffer.from(`cipher:${randomUUID()}`);
    this.plaintext.set(token.toString('base64'), value);
    return token;
  }
  async decryptStringAsync(value: Buffer): Promise<{ result: string; shouldReEncrypt: boolean }> {
    if (!this.available || this.decryptFails) throw new Error('key_unavailable');
    const result = this.plaintext.get(value.toString('base64'));
    if (!result) throw new Error('unknown_ciphertext');
    return { result, shouldReEncrypt: false };
  }
}

const alice: SourceIdentity = {origin: 'http://127.0.0.1:59431', accountId: 'alice-id'};
const bob: SourceIdentity = {origin: 'http://127.0.0.1:59431', accountId: 'bob-id'};
function sample(rootPath: string, tool: ConfirmedSource['tool'] = 'codex'): ConfirmedSource {
  return {sourceId: randomUUID(), tool, rootPath, rootDev: '17', rootIno: '29', collectAllowed: true, syncIntent: false};
}
function profile(): string {
  const path = realpathSync(mkdtempSync(join(tmpdir(), 'tm002-source-store-')));
  chmodSync(path, 0o700);
  return path;
}

test('TC-TM002-STORE-01 encrypted locator is private and isolated by origin, account and tool', async () => {
  const root = profile(); const cipher = new TestCipher(); const store = new SourceStore(root, cipher);
  const source = sample(join(root, 'A'));
  try {
    await store.commit(alice, source);
    const sourcesDir = join(root, 'sources');
    assert.equal(statSync(sourcesDir).mode & 0o777, 0o700);
    const files = readdirSync(sourcesDir); assert.equal(files.length, 1);
    const file = join(sourcesDir, files[0]);
    assert.equal(statSync(file).mode & 0o777, 0o600);
    assert.equal(readFileSync(file, 'utf8').includes(source.rootPath), false);
    assert.deepEqual(await store.load(alice, 'codex'), {kind: 'ready', source});
    assert.deepEqual(await store.load(bob, 'codex'), {kind: 'none'});
    assert.deepEqual(await store.load({...alice, origin: 'http://127.0.0.1:59432'}, 'codex'), {kind: 'none'});
    assert.deepEqual(await store.load(alice, 'claude_code'), {kind: 'none'});
    store.revoke(alice, 'codex');
    assert.deepEqual(await store.load(alice, 'codex'), {kind: 'none'});
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-STORE-01#WRITE_FAIL_KEEP_OLD leaves healthy A untouched when B atomic write fails', async () => {
  const root = profile(); const cipher = new TestCipher(); let fail = false;
  const store = new SourceStore(root, cipher, (path, text) => { if (fail) throw new Error('synthetic_write_failure'); privateWrite(path, text); });
  const a = sample(join(root, 'A')); const b = sample(join(root, 'B'));
  try {
    await store.commit(alice, a);
    const file = join(root, 'sources', readdirSync(join(root, 'sources'))[0]);
    const original = readFileSync(file);
    fail = true;
    await assert.rejects(store.commit(alice, b), /synthetic_write_failure/);
    assert.deepEqual(readFileSync(file), original);
    assert.deepEqual(await store.load(alice, 'codex'), {kind: 'ready', source: a});
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-STORE-01#KEY_UNAVAILABLE and #DECRYPT_FAIL fail closed without exposing locator', async () => {
  const root = profile(); const cipher = new TestCipher(); const store = new SourceStore(root, cipher);
  const source = sample(join(root, 'A'));
  try {
    await store.commit(alice, source);
    cipher.available = false;
    assert.equal((await store.load(alice, 'codex')).kind, 'needs_reselect');
    await assert.rejects(store.commit(alice, sample(join(root, 'B'))));
    cipher.available = true; cipher.decryptFails = true;
    const recovered = await store.load(alice, 'codex');
    assert.equal(recovered.kind, 'needs_reselect');
    assert.equal(JSON.stringify(recovered).includes(source.rootPath), false);
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-STATE-01#CORRUPT_LOCATOR requires reselect and remains revocable', async () => {
  const root = profile(); const cipher = new TestCipher(); const store = new SourceStore(root, cipher);
  try {
    await store.commit(alice, sample(join(root, 'A')));
    const file = join(root, 'sources', readdirSync(join(root, 'sources'))[0]);
    const data = JSON.parse(readFileSync(file, 'utf8'));
    data.ciphertext = 'not base64';
    writeFileSync(file, JSON.stringify(data));
    assert.equal((await store.load(alice, 'codex')).kind, 'needs_reselect');
    store.revoke(alice, 'codex');
    assert.deepEqual(await store.load(alice, 'codex'), {kind: 'none'});
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-ACCESS-04 invalid root stays disabled after restart and ignores stale source ID', async () => {
  const root = profile(); const cipher = new TestCipher(); const store = new SourceStore(root, cipher);
  const source = sample(join(root, 'A'));
  try {
    await store.commit(alice, source);
    assert.throws(() => store.markNeedsReselect(alice, 'codex', randomUUID(), 'root_changed'));
    assert.deepEqual(await store.load(alice, 'codex'), {kind: 'ready', source});
    assert.equal(store.markNeedsReselect(alice, 'codex', source.sourceId, 'root_changed'), 'latched');
    const restarted = new SourceStore(root, cipher);
    const status = await restarted.load(alice, 'codex');
    assert.deepEqual(status, {kind: 'needs_reselect', reason: 'root_changed', sourceId: source.sourceId});
    assert.equal(JSON.stringify(status).includes(source.rootPath), false);
    restarted.revoke(alice, 'codex');
    assert.deepEqual(await restarted.load(alice, 'codex'), {kind: 'none'});
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-ACCESS-04 failed invalidation write removes only its owned record', async () => {
  const root = profile(); const cipher = new TestCipher(); let fail = false;
  const store = new SourceStore(root, cipher, (path, text) => { if (fail) throw new Error('synthetic_write_failure'); privateWrite(path, text); });
  const source = sample(join(root, 'A'));
  try {
    await store.commit(alice, source); fail = true;
    assert.equal(store.markNeedsReselect(alice, 'codex', source.sourceId, 'access_denied'), 'removed');
    assert.deepEqual(await new SourceStore(root, cipher).load(alice, 'codex'), {kind: 'none'});
  } finally { rmSync(root, {recursive: true, force: true}); }
});
