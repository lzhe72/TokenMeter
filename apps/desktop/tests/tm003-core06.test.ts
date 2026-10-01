import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chmodSync, closeSync, existsSync, mkdtempSync, openSync, readFileSync, realpathSync,
  rmSync, statSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {CodexGeneration} from '../src/main/collection/codex-generation.ts';
import {UsageStore} from '../src/main/collection/usage-store.ts';

const ID = 'TC-TM003-CORE-06';
const PRINCIPAL = 'a'.repeat(64);
const ROOT_KEY = 'f'.repeat(64);
const SOURCE_A = 'b'.repeat(64);
const SOURCE_B = 'c'.repeat(64);
const FILE_A = 'd'.repeat(64);
const FILE_B = 'e'.repeat(64);
const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-generation.json', import.meta.url), 'utf8'));
const raw = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-storage-cursor.json', import.meta.url), 'utf8'));
const secret = Buffer.from(raw.test_keys.first_hex, 'hex');
const inputA = Buffer.from(raw.raw_lines.header + raw.raw_lines.a, 'utf8');
const inputB = Buffer.from(raw.raw_lines.header + raw.raw_lines.b, 'utf8');
function ownedRoot(): string { const p = mkdtempSync(join(tmpdir(), 'tm003-core06-')); chmodSync(p, 0o700); return realpathSync(p); }
function step(t: {diagnostic(message: string): void}, number: number, actual: object): void {
  t.diagnostic(JSON.stringify({kind: 'step', case_id: ID, step: number, actual}));
}
function readState(path: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try {
    const usage = db.prepare(`SELECT COUNT(*) AS count, COALESCE(SUM(input_tokens),0) AS input,
      COALESCE(SUM(output_tokens),0) AS output, COALESCE(SUM(cached_input_tokens),0) AS cached
      FROM usage_event`).get()!;
    const cursors = db.prepare('SELECT source_key, committed_byte_offset, prefix_mac FROM source_cursor ORDER BY source_key').all();
    return {usage: {count: Number(usage.count), input: Number(usage.input), output: Number(usage.output),
      cached: Number(usage.cached)}, cursors: cursors.map(row => ({key: row.source_key,
      offset: Number(row.committed_byte_offset), mac: row.prefix_mac})),
      diagnostics: Number(db.prepare('SELECT COUNT(*) AS n FROM collection_diagnostic').get()!.n),
      coverage: db.prepare('SELECT missing_before, scan_incomplete FROM coverage').all(),
      marker: db.prepare('SELECT key_marker FROM identity_key_state').get()?.key_marker ?? null};
  } finally { db.close(); }
}
function candidate(root: string, label: 'a'|'b') {
  const data = label === 'a' ? inputA : inputB;
  const file = join(root, `file-${label}.jsonl`);
  writeFileSync(file, data, {mode: 0o600});
  const fd = openSync(file, 'r');
  try {
    const actual = readFileSync(fd);
    assert.equal(statSync(file).mode & 0o777, 0o600);
    const expected = fixture.source_files.find((item: {synthetic_file_id: string}) => item.synthetic_file_id === `file-${label}`);
    assert.equal(actual.length, expected.size_bytes);
    assert.equal(createHash('sha256').update(actual).digest('hex'), expected.sha256);
    return {sourceKey: label === 'a' ? SOURCE_A : SOURCE_B,
      fileIdentity: label === 'a' ? FILE_A : FILE_B, bytes: actual};
  } finally { closeSync(fd); }
}
function start(root: string, guard: () => void = () => {}, onCancel: () => void = () => {}) {
  const path = join(root, 'usage.sqlite');
  const store = new UsageStore(path);
  const generation = new CodexGeneration({store, principalKey: PRINCIPAL, secret, rootKey: ROOT_KEY,
    guard, onCancel});
  return {path, store, generation};
}

test('TC-TM003-CORE-06 a complete two-page generation commits all files once or none', t => {
  const owner = ownedRoot();
  try {
    assert.deepEqual(fixture.scan_pages.map((page: {complete: boolean}) => page.complete), [false, true]);
    {
      const runRoot = join(owner, 'pending');
      const pending = start(runRoot);
      try {
        pending.generation.stage(candidate(runRoot, 'a'));
        pending.generation.pageComplete(false);
        assert.equal(pending.generation.finish(), false);
        const state = readState(pending.path);
        assert.deepEqual(state.usage, {count: 0, input: 0, output: 0, cached: 0});
        assert.equal(state.cursors.length, 0); assert.equal(state.diagnostics, 0);
        assert.equal(state.coverage.length, 0); assert.equal(state.marker, null);
        step(t, 1, {first_page_complete: false, staged_events: 1, commit_calls: 0,
          usage: state.usage, cursors: state.cursors.length, coverage: state.coverage.length});
      } finally { pending.store.close(); }
    }
    {
      const runRoot = join(owner, 'cursor-failure');
      const failed = start(runRoot);
      try {
        failed.generation.stage(candidate(runRoot, 'a'));
        failed.generation.pageComplete(false);
        failed.generation.stage(candidate(runRoot, 'b'));
        failed.generation.pageComplete(true);
        const db = new DatabaseSync(failed.path);
        try { db.exec(`CREATE TRIGGER fail_second_cursor BEFORE INSERT ON source_cursor
          WHEN (SELECT COUNT(*) FROM source_cursor)=1 BEGIN SELECT RAISE(ABORT,'second_cursor_fail'); END;`); }
        finally { db.close(); }
        assert.throws(() => failed.generation.finish(), /second_cursor_fail/);
      } finally { failed.store.close(); }
      const state = readState(failed.path);
      assert.deepEqual(state.usage, {count: 0, input: 0, output: 0, cached: 0});
      assert.equal(state.cursors.length, 0); assert.equal(state.diagnostics, 0);
      assert.equal(state.coverage.length, 0); assert.equal(state.marker, null);
      step(t, 2, {second_cursor_failed: true, entire_generation_rolled_back: true,
        usage: state.usage, cursors: state.cursors.length, diagnostics: state.diagnostics,
        coverage: state.coverage.length, key_marker_present: false});
    }
    {
      const runRoot = join(owner, 'revoked');
      let cancelled = 0; let guardAllowed = true; let commits = 0;
      const revoked = start(runRoot, () => { if (!guardAllowed) throw new Error('source_revoked'); },
        () => { cancelled++; });
      const original = revoked.store.commitScanBatch?.bind(revoked.store);
      if (original) revoked.store.commitScanBatch = ((batch: Parameters<NonNullable<typeof original>>[0]) => {
        commits++; return original(batch);
      }) as typeof revoked.store.commitScanBatch;
      try {
        revoked.generation.stage(candidate(runRoot, 'a'));
        revoked.generation.pageComplete(false);
        revoked.generation.stage(candidate(runRoot, 'b'));
        revoked.generation.pageComplete(true);
        guardAllowed = false;
        revoked.generation.cancel();
        assert.equal(revoked.generation.finish(), false);
        assert.equal(cancelled, 1); assert.equal(commits, 0);
        const state = readState(revoked.path);
        assert.equal(state.usage.count, 0); assert.equal(state.cursors.length, 0);
        assert.equal(state.coverage.length, 0); assert.equal(state.marker, null);
        step(t, 3, {revoked_before_commit: true, cancel_calls: cancelled, commit_calls: commits,
          usage: state.usage, cursors: state.cursors.length, coverage: state.coverage.length});
      } finally { revoked.store.close(); }
    }
    {
      const runRoot = join(owner, 'complete');
      const complete = start(runRoot);
      try {
        complete.generation.stage(candidate(runRoot, 'a'));
        complete.generation.pageComplete(false);
        complete.generation.stage(candidate(runRoot, 'b'));
        complete.generation.pageComplete(true);
        assert.equal(complete.generation.finish(), true);
      } finally { complete.store.close(); }
      let state = readState(complete.path);
      assert.deepEqual(state.usage, {count: 2, input: 300, output: 30, cached: 60});
      assert.deepEqual(state.cursors.map(item => [item.key, item.offset]), [[SOURCE_A, 410], [SOURCE_B, 410]]);
      assert.ok(state.cursors.every(item => /^[a-f0-9]{64}$/.test(String(item.mac))));
      assert.equal(state.coverage.length, 1); assert.equal(state.coverage[0].scan_incomplete, 0);
      assert.match(String(state.marker), /^[a-f0-9]{64}$/);
      const repeated = start(runRoot);
      try {
        repeated.generation.stage(candidate(runRoot, 'a'));
        repeated.generation.stage(candidate(runRoot, 'b'));
        repeated.generation.pageComplete(true);
        assert.equal(repeated.generation.finish(), true);
      } finally { repeated.store.close(); }
      state = readState(complete.path);
      assert.deepEqual(state.usage, {count: 2, input: 300, output: 30, cached: 60});
      step(t, 4, {usage: {...state.usage, total: 330}, cursor_count: state.cursors.length,
        cursor_offsets: state.cursors.map(item => item.offset), scan_incomplete: state.coverage[0].scan_incomplete,
        replay_unique: true});
    }
  } finally {
    rmSync(owner, {recursive: true, force: true}); assert.equal(existsSync(owner), false);
    t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: ID, owned_root_removed: true}));
  }
});
