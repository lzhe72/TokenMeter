import {test} from 'node:test';
import assert from 'node:assert/strict';
import {appendFileSync, chmodSync, closeSync, existsSync, ftruncateSync, futimesSync, mkdtempSync,
  openSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync, writeSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {scanCodexIncremental} from '../src/main/collection/codex-incremental.ts';
import {UsageStore} from '../src/main/collection/usage-store.ts';

const ID4 = 'TC-TM003-CORE-04';
const ID5 = 'TC-TM003-CORE-05';
const PRINCIPAL = 'a'.repeat(64);
const SOURCE_KEY = 'b'.repeat(64);
const ROOT_KEY = 'c'.repeat(64);
const FILE_ID = 'd'.repeat(64);
const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-storage-cursor.json', import.meta.url), 'utf8'));
const key1 = Buffer.from(fixture.test_keys.first_hex, 'hex');
const key2 = Buffer.from(fixture.test_keys.different_valid_hex, 'hex');
const lines = fixture.raw_lines;
const bytes = (...items: string[]): Buffer => Buffer.from(items.join(''), 'utf8');
const sha = (value: Buffer): string => createHash('sha256').update(value).digest('hex');
const report = (t: {diagnostic(message: string): void}, id: string, step: number, actual: object): void =>
  t.diagnostic(JSON.stringify({kind: 'step', case_id: id, step, actual}));
function root(): string { const path = mkdtempSync(join(tmpdir(), 'tm003-core45-')); chmodSync(path, 0o700); return realpathSync(path); }
function cleanup(t: {diagnostic(message: string): void}, id: string, path: string): void {
  rmSync(path, {recursive: true, force: true}); assert.equal(existsSync(path), false);
  t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: id, owned_root_removed: true}));
}
function dbRead(path: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try {
    const usage = db.prepare(`SELECT COUNT(*) AS count, COALESCE(SUM(input_tokens),0) AS input,
      COALESCE(SUM(output_tokens),0) AS output, COALESCE(SUM(cached_input_tokens),0) AS cached
      FROM usage_event WHERE principal_key=?`).get(PRINCIPAL)!;
    const cursor = db.prepare('SELECT committed_byte_offset, prefix_mac FROM source_cursor WHERE principal_key=? AND source_key=?')
      .get(PRINCIPAL, SOURCE_KEY);
    const coverage = db.prepare('SELECT missing_before, scan_incomplete FROM coverage WHERE principal_key=? AND root_key=?')
      .get(PRINCIPAL, ROOT_KEY);
    const marker = db.prepare('SELECT key_marker FROM identity_key_state').get();
    const diagnostics = db.prepare('SELECT code, SUM(count) AS count FROM collection_diagnostic GROUP BY code ORDER BY code').all();
    return {usage: {count: Number(usage.count), input: Number(usage.input), output: Number(usage.output),
      cached: Number(usage.cached)}, cursor: cursor && {offset: Number(cursor.committed_byte_offset),
      mac: String(cursor.prefix_mac)}, coverage: coverage && {missingBefore: Number(coverage.missing_before),
      scanIncomplete: Number(coverage.scan_incomplete)}, marker: marker?.key_marker,
      diagnostics: diagnostics.map(row => ({code: row.code, count: Number(row.count)}))};
  } finally { db.close(); }
}
function commit(store: UsageStore, scan: ReturnType<typeof scanCodexIncremental>, secret = key1,
  scanIncomplete = false): void {
  store.commitBatch({principalKey: PRINCIPAL, secret, source: 'codex', sourceKey: SOURCE_KEY,
    rootKey: ROOT_KEY, fileIdentity: FILE_ID, committedByteOffset: scan.committedByteOffset,
    prefixMac: scan.prefixMac, events: scan.events, diagnostics: scan.diagnostics,
    coverage: {missingBefore: scan.missingBefore, scanIncomplete}});
}

test('TC-TM003-CORE-04 synchronous batch is atomic and refuses a different valid identity key', t => {
  const owner = root(); const path = join(owner, 'usage.sqlite');
  try {
    const a = bytes(lines.header, lines.a);
    const ab = bytes(lines.header, lines.a, lines.b);
    assert.equal(a.length, 410); assert.equal(ab.length, 750);
    assert.equal(sha(a), fixture.expected.sha256_header_a);
    let store = new UsageStore(path);
    const first = scanCodexIncremental(a, null, FILE_ID, key1);
    commit(store, first, key1, true); store.close();
    let state = dbRead(path);
    assert.deepEqual(state.usage, {count: 1, input: 100, output: 10, cached: 20});
    assert.equal(state.cursor?.offset, 410); assert.match(state.cursor?.mac ?? '', /^[a-f0-9]{64}$/);
    assert.deepEqual(state.coverage, {missingBefore: 0, scanIncomplete: 1});
    assert.match(String(state.marker), /^[a-f0-9]{64}$/); assert.deepEqual(state.diagnostics, []);
    report(t, ID4, 1, {usage: state.usage, cursor: state.cursor, coverage: state.coverage,
      marker_present: true, diagnostics: state.diagnostics});

    const db = new DatabaseSync(path);
    try { db.exec(`CREATE TRIGGER fail_cursor_insert BEFORE INSERT ON source_cursor BEGIN SELECT RAISE(ABORT,'cursor_fail'); END;
      CREATE TRIGGER fail_cursor_update BEFORE UPDATE ON source_cursor BEGIN SELECT RAISE(ABORT,'cursor_fail'); END;`); }
    finally { db.close(); }
    store = new UsageStore(path);
    const second = scanCodexIncremental(ab, store.loadCursor(PRINCIPAL, SOURCE_KEY, key1), FILE_ID, key1);
    second.diagnostics.push({code: 'invalid_record'});
    assert.throws(() => commit(store, second), /cursor_fail/); store.close();
    assert.deepEqual(dbRead(path), state);
    report(t, ID4, 2, {batch_failed: true, rolled_back: true, usage: state.usage,
      cursor: state.cursor, coverage: state.coverage, diagnostics: state.diagnostics});

    const db2 = new DatabaseSync(path);
    try { db2.exec('DROP TRIGGER fail_cursor_insert; DROP TRIGGER fail_cursor_update;'); }
    finally { db2.close(); }
    store = new UsageStore(path); commit(store, second); store.close();
    state = dbRead(path);
    assert.deepEqual(state.usage, {count: 2, input: 300, output: 30, cached: 60});
    assert.equal(state.cursor?.offset, 750); assert.notEqual(state.cursor?.mac, first.prefixMac);
    assert.deepEqual(state.coverage, {missingBefore: 0, scanIncomplete: 0});
    assert.deepEqual(state.diagnostics, [{code: 'invalid_record', count: 1}]);
    report(t, ID4, 3, {usage: state.usage, cursor: state.cursor, coverage: state.coverage,
      diagnostics: state.diagnostics});

    store = new UsageStore(path);
    assert.throws(() => store.loadCursor(PRINCIPAL, SOURCE_KEY, key2), /identity_secret_mismatch/);
    const wrong = scanCodexIncremental(bytes(lines.header, lines.a, lines.b, lines.c), null, FILE_ID, key2);
    assert.throws(() => commit(store, wrong, key2), /identity_secret_mismatch/); store.close();
    assert.deepEqual(dbRead(path), state);
    report(t, ID4, 4, {different_valid_key_rejected: true, retained: state.usage,
      cursor: state.cursor, coverage: state.coverage, diagnostics: state.diagnostics});
  } finally { cleanup(t, ID4, owner); }
});

test('TC-TM003-CORE-05 LF cursor continues append and resets on prefix rewrite or truncation', t => {
  const owner = root(); const path = join(owner, 'usage.sqlite'); const file = join(owner, 'rollout.jsonl');
  const full = bytes(lines.header, lines.a, lines.b, lines.c);
  const rewritten = bytes(lines.header, lines.a_same_length_rewrite, lines.b, lines.c);
  assert.equal(full.length, 1090); assert.equal(rewritten.length, full.length);
  assert.equal(sha(full), fixture.expected.sha256_all);
  assert.equal(sha(rewritten), fixture.expected.sha256_rewritten_all);
  const fd = openSync(file, 'w+', 0o600);
  let store: UsageStore | null = null;
  try {
    store = new UsageStore(path);
    const a = bytes(lines.header, lines.a);
    writeFileSync(fd, a);
    let scan = scanCodexIncremental(readFileSync(file), null, FILE_ID, key1);
    commit(store, scan); let state = dbRead(path);
    assert.deepEqual(state.usage, {count: 1, input: 100, output: 10, cached: 20});
    assert.equal(state.cursor?.offset, 410); assert.equal(state.cursor?.mac, scan.prefixMac);
    report(t, ID5, 1, {source_sha256: sha(a), usage: state.usage, cursor: state.cursor,
      stable_file_identity: FILE_ID});

    const half = Math.floor(Buffer.byteLength(lines.b) / 2);
    appendFileSync(file, Buffer.from(lines.b).subarray(0, half));
    scan = scanCodexIncremental(readFileSync(file), store.loadCursor(PRINCIPAL, SOURCE_KEY, key1), FILE_ID, key1);
    assert.equal(scan.reset, false); commit(store, scan, key1, true); state = dbRead(path);
    assert.equal(state.cursor?.offset, 410); assert.equal(state.cursor?.mac, scan.prefixMac);
    assert.deepEqual(state.usage, {count: 1, input: 100, output: 10, cached: 20});
    assert.equal(state.diagnostics.some(item => item.code === 'cursor_reset'), false);
    report(t, ID5, 2, {mutable_snapshot_digest: 'changed-1', usage: state.usage,
      cursor: state.cursor, reset: scan.reset});

    appendFileSync(file, Buffer.concat([Buffer.from(lines.b).subarray(half), Buffer.from(lines.c)]));
    scan = scanCodexIncremental(readFileSync(file), store.loadCursor(PRINCIPAL, SOURCE_KEY, key1), FILE_ID, key1);
    assert.equal(scan.reset, false); commit(store, scan); state = dbRead(path);
    assert.deepEqual(state.usage, {count: 3, input: 600, output: 60, cached: 120});
    assert.equal(state.cursor?.offset, 1090); assert.deepEqual(state.diagnostics, []);
    report(t, ID5, 3, {mutable_snapshot_digest: 'changed-2', usage: state.usage,
      cursor: state.cursor, reset: scan.reset});

    futimesSync(fd, 1760000000, 1760000000);
    const before = statSync(file);
    assert.equal(writeSync(fd, rewritten, 0, rewritten.length, 0), rewritten.length);
    futimesSync(fd, before.atime, before.mtime);
    assert.equal(statSync(file).size, before.size); assert.equal(statSync(file).mtimeMs, before.mtimeMs);
    scan = scanCodexIncremental(readFileSync(file), store.loadCursor(PRINCIPAL, SOURCE_KEY, key1), FILE_ID, key1);
    assert.equal(scan.reset, true); commit(store, scan); state = dbRead(path);
    assert.deepEqual(state.usage, {count: 3, input: 600, output: 60, cached: 120});
    assert.equal(state.coverage?.missingBefore, 1);
    assert.deepEqual(state.diagnostics, [{code: 'cursor_reset', count: 1}]);
    report(t, ID5, 4, {original_sha256: sha(full), rewritten_sha256: sha(rewritten),
      source_bytes: rewritten.length, usage: state.usage, cursor: state.cursor,
      coverage: state.coverage, diagnostics: state.diagnostics});

    ftruncateSync(fd, a.length);
    scan = scanCodexIncremental(readFileSync(file), store.loadCursor(PRINCIPAL, SOURCE_KEY, key1), FILE_ID, key1);
    assert.equal(scan.reset, true); commit(store, scan); state = dbRead(path);
    assert.deepEqual(state.usage, {count: 3, input: 600, output: 60, cached: 120});
    assert.equal(state.cursor?.offset, 410); assert.equal(state.coverage?.missingBefore, 1);
    assert.deepEqual(state.diagnostics, [{code: 'cursor_reset', count: 2}]);
    report(t, ID5, 5, {source_bytes: statSync(file).size, usage: state.usage,
      cursor: state.cursor, coverage: state.coverage, diagnostics: state.diagnostics});
  } finally { store?.close(); closeSync(fd); cleanup(t, ID5, owner); }
});
