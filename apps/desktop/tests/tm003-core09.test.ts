import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chmodSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {SourceAccess, type SourceAccessIdentity, type SourceHelperLike} from '../src/main/source-access.ts';
import {SourceStore} from '../src/main/source-store.ts';
import {openUsageProfile} from '../src/main/collection/usage-profile.ts';
import {runCodexCollection} from '../src/main/collection/codex-runtime.ts';

const ID = 'TC-TM003-CORE-09';
const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-product-loop-slice.json', import.meta.url), 'utf8'));
const collector = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-main-collector-slice.json', import.meta.url), 'utf8'));
const lines = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-storage-cursor.json', import.meta.url), 'utf8')).raw_lines;
const bodies = [Buffer.from(lines.header + lines.a), Buffer.from(lines.header + lines.b)];
const sourceIds = [fixture.confirmed_source_id, '22222222-3333-4444-8555-666666666666'];
const tokens = ['a'.repeat(32), 'b'.repeat(32)];
function step(t: {diagnostic(message: string): void}, n: number, actual: object) {
  t.diagnostic(JSON.stringify({kind: 'step', case_id: ID, step: n, actual}));
}
function dbState(path: string, principal?: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try { const rows = db.prepare(`SELECT principal_key, COUNT(*) n, SUM(input_tokens) input,
    SUM(output_tokens) output, SUM(cached_input_tokens) cached FROM usage_event GROUP BY principal_key`).all();
    const cursors = db.prepare('SELECT principal_key, committed_byte_offset FROM source_cursor').all();
    const coverage = db.prepare('SELECT principal_key, root_key, scan_incomplete FROM coverage').all();
    return {rows, cursors, coverage, selected: principal ? rows.find(row => row.principal_key === principal) : null};
  } finally { db.close(); }
}
class Helper implements SourceHelperLike {
  rootIdentity = {dev: '17', ino: '29'};
  closed = false;
  onFinalRead: (() => void) | null = null;
  onNextPage: (() => void) | null = null;
  counts: {begin: number; read: number};
  constructor(counts: {begin: number; read: number}) { this.counts = counts; }
  async preview() { return {candidates: collector.files.map((f: {file_identity_digest: string}, i: number) =>
    ({relativeName: `synthetic/file-${i}.jsonl`, size: 410, mtimeMs: 1760000000000,
      fileIdentityDigest: f.file_identity_digest})), incomplete: false, inspectedEntries: 2}; }
  async beginCandidateScan() { this.counts.begin++; return {candidates: [this.candidate(0)], complete: false}; }
  async nextCandidatePage() { this.onNextPage?.(); return {candidates: [this.candidate(1)], complete: true}; }
  candidate(i: number) { return {candidateToken: tokens[i], relativeName: `synthetic/file-${i}.jsonl`,
    size: 410, mtimeMs: 1760000000000, fileIdentityDigest: collector.files[i].file_identity_digest}; }
  async readCandidateChunk(token: string, offset: number, maxBytes: number) {
    this.counts.read++; const i = tokens.indexOf(token); assert.ok(i >= 0);
    const part = bodies[i].subarray(offset, offset + Math.min(maxBytes, 128));
    if (i === 1 && offset + part.length >= 410) { const callback = this.onFinalRead; this.onFinalRead = null; callback?.(); }
    return part;
  }
  close() { this.closed = true; }
  async waitForExit() { assert.equal(this.closed, true); }
}
function harness(root: string, initialIdIndex = 0) {
  const sourceRoot = join(root, 'source'); mkdirSync(sourceRoot, {mode: 0o700, recursive: true});
  let identity: SourceAccessIdentity = {origin: fixture.identities[0].origin,
    accountId: fixture.identities[0].account_id, verified: true, epoch: 1};
  let nextId = initialIdIndex; const counts = {begin: 0, read: 0, commit: 0};
  let nextFinalRead: (() => void) | null = null;
  let firstPageEmpty = false;
  const cipher = {isAsyncEncryptionAvailable: async () => true,
    encryptStringAsync: async (v: string) => Buffer.from(`cipher:${v}`),
    decryptStringAsync: async (b: Buffer) => ({result: b.toString().slice(7), shouldReEncrypt: false})};
  const access = new SourceAccess({store: new SourceStore(root, cipher), getIdentity: () => identity,
    chooseDirectory: async () => ({canceled: false, rootPath: sourceRoot}),
    openHelper: async (_path, options) => { assert.deepEqual(options?.expectedRoot ?? {dev:'17',ino:'29'}, {dev:'17',ino:'29'});
      const h = new Helper(counts); h.onFinalRead = nextFinalRead; nextFinalRead = null;
      h.onNextPage = () => { if (initialIdIndex === 0 && counts.begin === 1) {
        assert.equal(dbState(join(root, 'collection', 'usage-v1.sqlite')).rows.length, 0);
        firstPageEmpty = true;
      }};
      helpers.push(h); return h; },
    createSourceId: () => sourceIds[nextId++], onChange: () => {}});
  const helpers: Helper[] = [];
  const profile = openUsageProfile(root, {cipher: {isEncryptionAvailable: () => true,
    encryptString: v => Buffer.from(`cipher:${v}`), decryptString: b => b.toString().slice(7)},
    randomBytes: () => Buffer.from(fixture.public_test_key_hex, 'hex')});
  const runtime = {access, profile, getIdentity: () => identity, stagingBudgetBytes: collector.fixture_staging_budget_bytes};
  const original = profile.store.commitScanBatch.bind(profile.store);
  profile.store.commitScanBatch = batch => { counts.commit++; return original(batch); };
  async function confirm() { await access.syncIdentity(); await access.choose('codex');
    const selected = access.snapshot().codex.pending?.selectionId; assert.ok(selected);
    await access.preview(selected); await access.confirm(selected, true, false);
    const id = access.snapshot().codex.confirmed?.sourceId; assert.ok(id); return id; }
  return {access, profile, runtime, counts, helpers, confirm,
    get firstPageEmpty() { return firstPageEmpty; },
    armFinalRead(callback: () => void) { nextFinalRead = callback; },
    switchSubject() { identity = {origin: fixture.identities[2].origin,
      accountId: fixture.identities[2].account_id, verified: true, epoch: 2}; },
    close() { access.dispose(); profile.close(); }};
}

test('TC-TM003-CORE-09 confirmed SourceAccess scans atomically by principal', async t => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm003-core09-'))); chmodSync(root, 0o700);
  try {
    let h = harness(root); const path = join(root, fixture.sqlite_file);
    try {
      await assert.rejects(runCodexCollection(fixture.unconfirmed_source_id, h.runtime), /source_access_denied/);
      assert.deepEqual([h.counts.begin, h.counts.read, h.counts.commit, dbState(path).rows.length], [0,0,0,0]);
      const source = await h.confirm(); assert.equal(source, fixture.confirmed_source_id);
      assert.equal(h.access.snapshot().codex.pending, null);
      step(t, 1, {before_confirm_begin: 0, before_confirm_read: 0, before_confirm_commit: 0,
        before_confirm_events: 0, confirmed_source_id: source, pending_cleared: true});

      await runCodexCollection(source, h.runtime);
      assert.equal(h.firstPageEmpty, true);
      const principal = h.profile.principalKey(fixture.identities[0].origin, fixture.identities[0].account_id);
      const first = dbState(path, principal);
      assert.deepEqual([first.rows.length, Number(first.selected?.n), Number(first.selected?.input),
        Number(first.selected?.output), Number(first.selected?.cached)], [1,2,300,30,60]);
      assert.deepEqual(first.cursors.map(row => Number(row.committed_byte_offset)).sort(), [410,410]);
      assert.deepEqual(first.coverage.map(row => Number(row.scan_incomplete)), [0]);
      h.close(); h = harness(root, 1); await h.access.syncIdentity();
      assert.equal(h.access.snapshot().codex.confirmed?.sourceId, source);
      await runCodexCollection(source, h.runtime);
      assert.equal(Number(dbState(path, principal).selected?.n), 2);
      assert.equal(h.counts.commit, 1);
      const bytes = readFileSync(path).toString('utf8');
      for (const forbidden of [source, ...collector.files.map((f: {file_identity_digest: string}) => f.file_identity_digest),
        '/Users/private/source-a.jsonl']) assert.equal(bytes.includes(forbidden), false);
      step(t, 2, {events: 2, input: 300, output: 30, cached: 60, total: 330,
        cursor_offsets: [410,410], coverage_complete: true, replay_events: 2, commit_calls: 2,
        source_and_profile_reopened: true, first_page_db_empty: true});

      const failureRoot = join(root, 'failure-copy'); mkdirSync(failureRoot, {mode: 0o700});
      cpSync(join(root, 'collection'), join(failureRoot, 'collection'), {recursive: true});
      cpSync(join(root, 'sources'), join(failureRoot, 'sources'), {recursive: true});
      for (const directory of ['collection', 'sources']) {
        const path = join(failureRoot, directory); chmodSync(path, 0o700);
        for (const name of readdirSync(path)) chmodSync(join(path, name), 0o600);
      }
      const failure = harness(failureRoot, 1); const failurePath = join(failureRoot, fixture.sqlite_file);
      try {
        await failure.access.syncIdentity();
        assert.equal(failure.access.snapshot().codex.confirmed?.sourceId, source);
        let revoked: Promise<void> | null = null;
        // Trigger revocation from the copied owner helper after the second file's final chunk.
        failure.armFinalRead(() => { revoked = failure.access.revoke(source); });
        const pending = runCodexCollection(source, failure.runtime);
        await assert.rejects(pending, (error: unknown) =>
          ['source_operation_stale', 'source_access_denied', 'invalid_scan'].includes((error as {code?: string})?.code ?? ''));
        if (revoked) await revoked;
        assert.equal(failure.counts.commit, 0);
        const after = dbState(failurePath, principal);
        assert.deepEqual(after.coverage, first.coverage);
        assert.equal(Number(after.selected?.n), 2);
        await assert.rejects(runCodexCollection(source, failure.runtime), /source_access_denied/);
      } finally { failure.close(); }
      assert.deepEqual(dbState(path, principal).coverage, first.coverage);
      step(t, 3, {old_events: 2, old_total: 330, revoked_commit_calls: 0,
        old_coverage_unchanged: true, source_unreadable: true, run_state: 'unavailable',
        independent_owner_copy: true});

      h.switchSubject(); await h.access.syncIdentity();
      await assert.rejects(runCodexCollection(source, h.runtime), /source_access_denied/);
      const second = h.profile.principalKey(fixture.identities[2].origin, fixture.identities[2].account_id);
      assert.notEqual(second, principal); assert.equal(dbState(path, second).selected, undefined);
      const secondSource = await h.confirm(); await runCodexCollection(secondSource, h.runtime);
      const final = dbState(path);
      assert.equal(final.rows.length, 2);
      assert.deepEqual(final.rows.map(row => Number(row.n)).sort(), [2,2]);
      assert.deepEqual(final.cursors.map(row => Number(row.committed_byte_offset)).sort(), [410,410,410,410]);
      step(t, 4, {old_source_rejected: true, distinct_principals: 2, events_each: 2,
        total_each: 330, cursors_each: 2});
    } finally { h.close(); }
  } finally { rmSync(root, {recursive: true, force: true}); assert.equal(existsSync(root), false);
    t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: ID, owned_root_removed: true})); }
});
