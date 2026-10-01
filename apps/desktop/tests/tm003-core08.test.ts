import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {scanCodexFile} from '../src/main/collection/codex-format.ts';
import {openUsageProfile} from '../src/main/collection/usage-profile.ts';

const ID = 'TC-TM003-CORE-08';
const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-product-loop-slice.json', import.meta.url), 'utf8'));
const lines = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-storage-cursor.json', import.meta.url), 'utf8')).raw_lines;
const publicKey = Buffer.from(fixture.public_test_key_hex, 'hex');
const SOURCE = 'a'.repeat(64), ROOT = 'b'.repeat(64), FILE = 'c'.repeat(64), MAC = 'd'.repeat(64);
function owner() { const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm003-core08-'))); chmodSync(root, 0o700); return root; }
function step(t: {diagnostic(message: string): void}, n: number, actual: object) {
  t.diagnostic(JSON.stringify({kind: 'step', case_id: ID, step: n, actual}));
}
function cipher(available = true) {
  return {isEncryptionAvailable: () => available,
    encryptString: (s: string) => Buffer.from(`test-cipher:${s}`, 'utf8'),
    decryptString: (b: Buffer) => { const s = b.toString('utf8');
      if (!s.startsWith('test-cipher:')) throw new Error('cipher_invalid'); return s.slice(12); }};
}
function random() { let calls = 0; return {generate: () => { calls++; return Buffer.from(publicKey); }, get calls() { return calls; }}; }
function state(path: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try { const u = db.prepare('SELECT COUNT(*) n, COALESCE(SUM(input_tokens+output_tokens),0) total FROM usage_event').get()!;
    return {events: Number(u.n), total: Number(u.total), cursors: Number(db.prepare('SELECT COUNT(*) n FROM source_cursor').get()!.n),
      coverage: Number(db.prepare('SELECT COUNT(*) n FROM coverage').get()!.n),
      marker: db.prepare('SELECT key_marker FROM identity_key_state').get()?.key_marker ?? null}; }
  finally { db.close(); }
}
function snapshotBytes(path: string) { return readFileSync(path); }

test('TC-TM003-CORE-08 owner profile protects and preserves one identity secret', t => {
  const root = owner();
  try {
    const rng = random();
    const profile = openUsageProfile(root, {cipher: cipher(), randomBytes: rng.generate});
    const secretPath = join(root, fixture.secret_file), dbPath = join(root, fixture.sqlite_file);
    try {
      assert.equal(rng.calls, 1); assert.equal(statSync(join(root, 'collection')).mode & 0o777, 0o700);
      assert.equal(statSync(secretPath).mode & 0o777, 0o600); assert.equal(statSync(dbPath).mode & 0o777, 0o600);
      assert.equal(readFileSync(secretPath).includes(publicKey), false);
      for (const value of fixture.identities)
        assert.equal(profile.principalKey(value.origin, value.account_id), value.principal_key);
      const initial = state(dbPath); assert.deepEqual([initial.events, initial.cursors, initial.coverage], [0,0,0]);
      step(t, 1, {random_calls: rng.calls, principal_vectors: fixture.identities.length,
        secret_file_mode: '0600', directory_mode: '0700', events: initial.events, cursors: initial.cursors,
        coverage: initial.coverage, plaintext_absent: true});

      const a = scanCodexFile(Buffer.from(lines.header + lines.a), 0).events[0];
      assert.ok(a); assert.equal(a.usage.totalTokens, 110);
      const principal = profile.principalKey(fixture.identities[0].origin, fixture.identities[0].account_id);
      profile.store.commitBatch({principalKey: principal, secret: profile.secret, source: 'codex',
        sourceKey: SOURCE, rootKey: ROOT, fileIdentity: FILE, committedByteOffset: 410, prefixMac: MAC,
        events: [a], diagnostics: [], coverage: {missingBefore: false, scanIncomplete: false}});
    } finally { profile.close(); }
    const first = state(dbPath), ciphertext = snapshotBytes(secretPath);
    assert.deepEqual([first.events, first.total, first.cursors, first.coverage], [1,110,1,1]); assert.ok(first.marker);
    const reopenedRandom = random();
    const reopened = openUsageProfile(root, {cipher: cipher(), randomBytes: reopenedRandom.generate});
    try {
      assert.equal(reopenedRandom.calls, 0);
      assert.equal(reopened.principalKey(fixture.identities[0].origin, fixture.identities[0].account_id), fixture.identities[0].principal_key);
      const a = scanCodexFile(Buffer.from(lines.header + lines.a), 0).events[0];
      reopened.store.commitBatch({principalKey: fixture.identities[0].principal_key, secret: reopened.secret,
        source: 'codex', sourceKey: SOURCE, rootKey: ROOT, fileIdentity: FILE, committedByteOffset: 410,
        prefixMac: MAC, events: [a], diagnostics: [], coverage: {missingBefore: false, scanIncomplete: false}});
      for (const other of fixture.identities.slice(1)) {
        assert.equal(reopened.store.summary(other.principal_key).count, 0);
        assert.equal(reopened.store.codexState(other.principal_key, null).usage, null);
      }
    } finally { reopened.close(); }
    const replay = state(dbPath);
    assert.deepEqual([replay.events, replay.total, replay.cursors, replay.marker], [1,110,1,first.marker]);
    assert.deepEqual(snapshotBytes(secretPath), ciphertext);
    step(t, 2, {reopen_random_calls: reopenedRandom.calls, events: replay.events, total: replay.total,
      cursors: replay.cursors, marker_unchanged: true, other_subjects_unverified: 2});

    for (const variant of ['missing', 'corrupt'] as const) {
      const copy = join(root, variant); const collection = join(copy, 'collection');
      mkdirSync(copy, {mode: 0o700}); mkdirSync(collection, {mode: 0o700});
      copyFileSync(dbPath, join(collection, 'usage-v1.sqlite')); chmodSync(join(collection, 'usage-v1.sqlite'), 0o600);
      if (variant === 'corrupt') writeFileSync(join(collection, 'identity-secret-v1.json'), '{bad', {mode: 0o600});
      const prior = snapshotBytes(join(collection, 'usage-v1.sqlite')); const noRandom = random();
      assert.throws(() => openUsageProfile(copy, {cipher: cipher(), randomBytes: noRandom.generate}),
        new RegExp(variant === 'missing' ? 'identity_secret_unavailable' : 'identity_secret_corrupt'));
      assert.equal(noRandom.calls, 0); assert.deepEqual(snapshotBytes(join(collection, 'usage-v1.sqlite')), prior);
      assert.equal(existsSync(join(collection, 'identity-secret-v1.json')), variant === 'corrupt');
      assert.deepEqual([state(join(collection, 'usage-v1.sqlite')).events, state(join(collection, 'usage-v1.sqlite')).total], [1,110]);
    }
    step(t, 3, {missing_code: 'identity_secret_unavailable', corrupt_code: 'identity_secret_corrupt',
      random_calls_each: 0, prior_events_each: 1, prior_total_each: 110, db_unchanged_each: true});

    const unavailableRandom = random();
    const priorDb = snapshotBytes(dbPath);
    assert.throws(() => openUsageProfile(root, {cipher: cipher(false), randomBytes: unavailableRandom.generate}),
      /identity_secret_unavailable/);
    assert.equal(unavailableRandom.calls, 0);
    assert.throws(() => openUsageProfile(root, {cipher: {isEncryptionAvailable: () => true,
      encryptString: (s: string) => Buffer.from(s), decryptString: () => Buffer.alloc(32, 0x20).toString('hex')},
      randomBytes: () => { throw new Error('unexpected_random'); }}), /identity_secret_mismatch/);
    assert.deepEqual(snapshotBytes(secretPath), ciphertext);
    assert.deepEqual(snapshotBytes(dbPath), priorDb);
    assert.deepEqual([state(dbPath).events, state(dbPath).total], [1,110]);
    assert.equal(snapshotBytes(dbPath).includes(publicKey), false);
    step(t, 4, {encryption_unavailable_code: 'identity_secret_unavailable', wrong_key_code: 'identity_secret_mismatch',
      random_calls: unavailableRandom.calls, events: 1, total: 110, plaintext_absent: true});
  } finally {
    rmSync(root, {recursive: true, force: true}); assert.equal(existsSync(root), false);
    t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: ID, owned_root_removed: true}));
  }
});
