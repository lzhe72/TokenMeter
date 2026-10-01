import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {collectCodex} from '../src/main/collection/codex-collector.ts';
import type {CodexCollectionAccess} from '../src/main/collection/codex-collector.ts';
import {UsageStore} from '../src/main/collection/usage-store.ts';

const ID = 'TC-TM003-CORE-07';
const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-main-collector-slice.json', import.meta.url), 'utf8'));
const generation = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-generation.json', import.meta.url), 'utf8'));
const lines = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-storage-cursor.json', import.meta.url), 'utf8')).raw_lines;
const secret = Buffer.from(fixture.public_test_secret_hex, 'hex');
const payloads = [Buffer.from(lines.header + lines.a), Buffer.from(lines.header + lines.b)];
const tokens = ['a'.repeat(32), 'b'.repeat(32)];
const source = fixture.source_id as string;
type Mode = 'normal'|'early_eof'|'read_throw'|'oversize'|'revoke'|'switch';
type Principal = {verified: boolean; key: string};

function state(path: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try {
    const row = db.prepare(`SELECT COUNT(*) AS count, COALESCE(SUM(input_tokens),0) AS input,
      COALESCE(SUM(output_tokens),0) AS output, COALESCE(SUM(cached_input_tokens),0) AS cached
      FROM usage_event`).get()!;
    return {
      count: Number(row.count), input: Number(row.input), output: Number(row.output), cached: Number(row.cached),
      cursors: db.prepare('SELECT source_key, root_key, file_identity, committed_byte_offset FROM source_cursor ORDER BY source_key').all()
        .map(row => ({source_key: String(row.source_key), root_key: String(row.root_key),
          file_identity: String(row.file_identity), committed_byte_offset: Number(row.committed_byte_offset)})),
      diagnostics: Number(db.prepare('SELECT COUNT(*) AS n FROM collection_diagnostic').get()!.n),
      coverage: db.prepare('SELECT root_key, scan_incomplete FROM coverage').all()
        .map(row => ({root_key: String(row.root_key), scan_incomplete: Number(row.scan_incomplete)})),
      marker: db.prepare('SELECT key_marker FROM identity_key_state').get()?.key_marker ?? null,
    };
  } finally { db.close(); }
}
function empty(path: string): void {
  const current = state(path);
  assert.equal(current.count, 0); assert.equal(current.cursors.length, 0);
  assert.equal(current.diagnostics, 0); assert.equal(current.coverage.length, 0);
  assert.equal(current.marker, null);
}
function step(t: {diagnostic(message: string): void}, number: number, actual: object): void {
  t.diagnostic(JSON.stringify({kind: 'step', case_id: ID, step: number, actual}));
}
function candidate(index: number, mode: Mode) {
  return {candidateToken: tokens[index], relativeName: `PRIVATE-SECRET-CORE07/PRIVATE-PROMPT-CORE07/Users/private/source-a.jsonl`,
    size: index === 1 && mode === 'oversize' ? fixture.oversize_candidate_bytes : payloads[index].length,
    mtimeMs: 1760000000000, fileIdentityDigest: fixture.files[index].file_identity_digest};
}
function fake(path: string, mode: Mode = 'normal', principal: Principal = {verified: true, key: fixture.verified_principal_key},
  collectAllowed = true, expectEmptyFirstPage = true) {
  const counts = {begin: 0, next: 0, reads: 0, maxRequest: 0, guard: 0, cancel: 0, commits: 0};
  let revoked = false;
  let firstPageEmpty = false;
  const scanId = '00000000-0000-4000-8000-000000000707';
  const access = {
    snapshot: () => ({codex: {confirmed: {sourceId: source, status: collectAllowed && !revoked ? 'confirmed_enabled' : 'confirmed_paused',
      collectAllowed: collectAllowed && !revoked, syncIntent: false}, pending: null, candidates: [], incomplete: false},
      claude_code: {confirmed: null, pending: null, candidates: [], incomplete: false}}),
    beginCandidateScan: async (_sourceId: string) => { counts.begin++; return {scanId,
      candidates: [candidate(0, mode)], complete: false}; },
    nextCandidatePage: async (_scanId: string) => {
      counts.next++;
      if (expectEmptyFirstPage) empty(path);
      else assert.equal(state(path).count, 2);
      firstPageEmpty = expectEmptyFirstPage;
      return {candidates: [candidate(1, mode)], complete: true};
    },
    readCandidateChunk: async (_scanId: string, token: string, offset: number, maximum: number) => {
      counts.reads++; counts.maxRequest = Math.max(counts.maxRequest, maximum);
      assert.ok(maximum > 0 && maximum <= fixture.max_read_request_bytes);
      const index = tokens.indexOf(token); assert.ok(index >= 0);
      if (index === 1 && mode === 'read_throw') throw new Error('read_failure');
      if (index === 1 && mode === 'early_eof' && offset >= 128) return Buffer.alloc(0);
      const result = payloads[index].subarray(offset, offset + Math.min(maximum, fixture.files[index].read_return_chunk_bytes));
      if (index === 1 && offset + result.length >= payloads[index].length) {
        if (mode === 'revoke') revoked = true;
        if (mode === 'switch') principal.key = '2'.repeat(64);
      }
      return result;
    },
    commitGuard: async (_scanId: string) => {
      counts.guard++;
      if (revoked || principal.key !== fixture.verified_principal_key) throw new Error('source_operation_stale');
      return () => { if (revoked || principal.key !== fixture.verified_principal_key) throw new Error('source_operation_stale'); };
    },
    cancelScan: async (_scanId: string) => { counts.cancel++; },
  } as unknown as CodexCollectionAccess;
  const store = new UsageStore(path);
  const original = store.commitScanBatch.bind(store);
  store.commitScanBatch = batch => { counts.commits++; return original(batch); };
  return {access, store, counts, principal, get firstPageEmpty() { return firstPageEmpty; }};
}
function ownedCase(owner: string, name: string): string {
  const dir = join(owner, name); mkdirSync(dir, {mode: 0o700}); chmodSync(dir, 0o700);
  return join(dir, 'usage.sqlite');
}
function privacy(path: string): void {
  const bytes = [path, `${path}-wal`, `${path}-shm`].filter(existsSync).map(item => readFileSync(item).toString('utf8')).join('\n');
  for (const sentinel of fixture.privacy_sentinels) assert.equal(bytes.includes(sentinel), false);
  assert.equal(bytes.includes(fixture.files[0].file_identity_digest), false);
  assert.equal(bytes.includes(fixture.files[1].file_identity_digest), false);
}

test('TC-TM003-CORE-07 main collector stages every bounded page and aborts stale generations', async t => {
  const owner = realpathSync(mkdtempSync(join(tmpdir(), 'tm003-core07-'))); chmodSync(owner, 0o700);
  try {
    assert.deepEqual(payloads.map(value => value.length), [410, 410]);
    for (let i = 0; i < 2; i++)
      assert.equal(createHash('sha256').update(payloads[i]).digest('hex'), generation.source_files[i].sha256);

    const refusals = [
      {name: 'foreign-source', sourceId: '00000000-0000-4000-8000-000000000999', verified: true, consent: true},
      {name: 'unverified', sourceId: source, verified: false, consent: true},
      {name: 'paused', sourceId: source, verified: true, consent: false},
    ];
    for (const item of refusals) {
      const path = ownedCase(owner, item.name);
      const run = fake(path, 'normal', {verified: item.verified, key: fixture.verified_principal_key}, item.consent);
      try {
        await assert.rejects(collectCodex({sourceId: item.sourceId, access: run.access, store: run.store,
          secret, principal: () => run.principal, stagingBudgetBytes: fixture.fixture_staging_budget_bytes}),
        /source_access_denied|invalid_principal/);
        assert.equal(run.counts.begin, 0); assert.equal(run.counts.commits, 0); empty(path);
      } finally { run.store.close(); }
    }
    step(t, 1, {rejected_variants: refusals.map(item => item.name), begin_calls: 0, commit_calls: 0, db_empty: true});

    const successPath = ownedCase(owner, 'success');
    const success = fake(successPath);
    try {
      await collectCodex({sourceId: source, access: success.access, store: success.store,
        secret, principal: () => success.principal, stagingBudgetBytes: fixture.fixture_staging_budget_bytes});
      assert.equal(success.firstPageEmpty, true);
      assert.deepEqual({commits: success.counts.commits, cancel: success.counts.cancel}, {commits: 1, cancel: 1});
      assert.ok(success.counts.reads > 2); assert.ok(success.counts.maxRequest <= fixture.max_read_request_bytes);
    } finally { success.store.close(); }
    let committed = state(successPath);
    assert.deepEqual([committed.count, committed.input, committed.output, committed.cached], [2, 300, 30, 60]);
    assert.deepEqual(committed.cursors.map(row => row.source_key), fixture.files.map((file: {source_key_hex: string}) => file.source_key_hex).sort());
    assert.ok(committed.cursors.every(row => row.root_key === fixture.root_key_hex &&
      row.file_identity === row.source_key && row.committed_byte_offset === 410));
    assert.deepEqual(committed.coverage, [{root_key: fixture.root_key_hex, scan_incomplete: 0}]);
    privacy(successPath);
    step(t, 2, {first_page_db_empty: true, events: committed.count, total: committed.input + committed.output,
      cursor_count: committed.cursors.length, root_key: committed.coverage[0].root_key,
      source_keys: committed.cursors.map(row => row.source_key), scan_incomplete: 0,
      commit_calls: success.counts.commits, cancel_calls: success.counts.cancel,
      max_read_request: success.counts.maxRequest, privacy_sentinels_absent: true});

    const faults: Mode[] = ['early_eof', 'read_throw', 'oversize'];
    for (const mode of faults) {
      const path = ownedCase(owner, mode);
      const run = fake(path, mode);
      try {
        await assert.rejects(collectCodex({sourceId: source, access: run.access, store: run.store,
          secret, principal: () => run.principal, stagingBudgetBytes: fixture.fixture_staging_budget_bytes}),
        /source_read_incomplete|read_failure|staging_budget_exceeded/);
        assert.equal(run.counts.commits, 0); assert.equal(run.counts.cancel, 1);
        assert.ok(run.counts.maxRequest <= fixture.max_read_request_bytes); empty(path);
      } finally { run.store.close(); }
    }
    step(t, 3, {faults, commit_calls_each: 0, cancel_calls_each: 1, db_empty_each: true,
      max_request_bytes: fixture.max_read_request_bytes});

    for (const mode of ['revoke', 'switch'] as Mode[]) {
      const path = ownedCase(owner, mode);
      const run = fake(path, mode);
      try {
        await assert.rejects(collectCodex({sourceId: source, access: run.access, store: run.store,
          secret, principal: () => run.principal, stagingBudgetBytes: fixture.fixture_staging_budget_bytes}),
        /source_operation_stale/);
        assert.equal(run.counts.guard, 1); assert.equal(run.counts.commits, 0);
        assert.equal(run.counts.cancel, 1); empty(path);
      } finally { run.store.close(); }
    }
    step(t, 4, {stale_variants: ['revoke', 'switch'], guard_calls_each: 1,
      commit_calls_each: 0, cancel_calls_each: 1, db_empty_each: true});

    const replay = fake(successPath, 'normal', {verified: true, key: fixture.verified_principal_key}, true, false);
    try {
      await collectCodex({sourceId: source, access: replay.access, store: replay.store,
        secret, principal: () => replay.principal, stagingBudgetBytes: fixture.fixture_staging_budget_bytes});
      assert.equal(replay.counts.guard, 1); assert.equal(replay.counts.commits, 1);
      assert.equal(replay.counts.cancel, 1);
    } finally { replay.store.close(); }
    committed = state(successPath);
    assert.deepEqual([committed.count, committed.input + committed.output, committed.cursors.length], [2, 330, 2]);
    privacy(successPath);
    step(t, 5, {events: committed.count, total: committed.input + committed.output,
      cursor_count: committed.cursors.length, guard_calls: replay.counts.guard,
      commit_calls: replay.counts.commits, cancel_calls: replay.counts.cancel,
      privacy_sentinels_absent: true});
  } finally {
    rmSync(owner, {recursive: true, force: true}); assert.equal(existsSync(owner), false);
    t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: ID, owned_root_removed: true}));
  }
});
