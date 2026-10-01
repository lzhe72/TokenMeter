import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {chmodSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {collectClaudeUsage} from '../src/main/collection/claude-event.ts';
import {commitClaudePreparedBatch, type ClaudeScanStorePort} from '../src/main/collection/claude-storage.ts';
import {claudeCandidateFromSource, claudeRootKey} from '../src/main/collection/claude-source.ts';
import {UsageStore} from '../src/main/collection/usage-store.ts';

const CASE = 'TC-TM004-CORE-05';
const raw = readFileSync(join(import.meta.dirname, '../../../tests/fixtures/tm004-storage-port-slice.json'));
assert.equal(createHash('sha256').update(raw).digest('hex'),
  '6e8603354ca0e6c3e2678074b2951b052fa2e34325e1ca02e5e0304cc8c7861a');
const fixture = JSON.parse(raw.toString('utf8')) as {
  source_id: string; other_source_id: string; principal_key: string; secret_hex: string;
  key_derivation: {root_key: string}; expected_scope_keys: string[];
  files: Array<{file_identity_digest: string; source_key_and_file_identity: string;
    committed_byte_offset: number; prefix_mac: string; call: {
      canonical_call_id: string; session_id: string; agent_id: string | null; turn_id: string;
      input_tokens: number; output_tokens: number; model_id: string};
    diagnostic_codes: string[]}>;
};
const secret = Buffer.from(fixture.secret_hex, 'hex');
const scanId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const tokens = ['a'.repeat(32), 'b'.repeat(32), 'c'.repeat(32)];
const stamp = '2026-10-01T00:00:00Z';
const line = (row: unknown): string => JSON.stringify(row) + '\n';
function assistant(index: number, sidechain: boolean, agentId: string | null) {
  const item = fixture.files[index];
  return {type: 'assistant', version: '2.1.126', uuid: 'synthetic-row-' + index,
    sessionId: item.call.session_id, isSidechain: sidechain, timestamp: stamp,
    ...(agentId ? {agentId} : {}),
    message: {role: 'assistant', id: item.call.canonical_call_id, model: item.call.model_id,
      usage: {input_tokens: item.call.input_tokens, output_tokens: item.call.output_tokens}}};
}
function padded(text: string, length: number): Buffer {
  const bytes = Buffer.byteLength(text);
  assert.ok(bytes <= length, 'synthetic input ' + bytes + ' must fit fixed cursor offset ' + length);
  assert.ok(text.endsWith('\n'));
  return Buffer.from(text.slice(0, -1) + ' '.repeat(length - bytes) + '\n');
}
const parent = {type: 'user', version: '2.1.126', sessionId: 'session-01',
  isSidechain: false, timestamp: stamp, message: {role: 'user', content: [{type: 'tool_result'}]},
  toolUseResult: {agentId: 'agent-01'}};
const bytes = [
  padded(line(assistant(0, false, null)) + 'not-json\n',
    fixture.files[0].committed_byte_offset),
  padded(line(assistant(1, true, 'agent-01')) + line({type: 'assistant', version: '2.1.127'}),
    fixture.files[1].committed_byte_offset),
  padded(line(parent) + line(assistant(2, true, null)), fixture.files[2].committed_byte_offset),
];

type Trace = {begin: number; next: number; cancel: number; guard: number; commit: number};
function access(mode: 'complete'|'incomplete'|'revoked', trace: Trace) {
  return {
    async beginCandidateScan(sourceId: string) {
      trace.begin++;
      assert.equal(sourceId, fixture.source_id);
      return {scanId, complete: mode !== 'incomplete', candidates: fixture.files.map((item, index) => ({
        relativeName: 'synthetic-' + index + '.jsonl', size: bytes[index].length,
        candidateToken: tokens[index], fileIdentityDigest: item.file_identity_digest}))};
    },
    async nextCandidatePage(_value: string) {
      trace.next++;
      throw new Error('synthetic_page_interrupted');
    },
    async readCandidateChunk(value: string, token: string, offset: number, maxBytes: number) {
      assert.equal(value, scanId);
      const index = tokens.indexOf(token);
      assert.notEqual(index, -1);
      return bytes[index].subarray(offset, offset + maxBytes);
    },
    async commitGuard(value: string) {
      trace.guard++;
      assert.equal(value, scanId);
      return () => { if (mode === 'revoked') throw new Error('source_operation_stale'); };
    },
    async cancelScan(value: string) { trace.cancel++; assert.equal(value, scanId); },
  };
}
function ownedRoot(): string {
  const root = mkdtempSync(join(tmpdir(), 'tm004-core05-'));
  chmodSync(root, 0o700);
  return realpathSync(root);
}
function state(path: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try {
    const events = db.prepare('SELECT source_scope_key,model_id,input_tokens,output_tokens FROM usage_event').all();
    const cursors = db.prepare('SELECT source_key,file_identity,committed_byte_offset FROM source_cursor').all();
    const diagnostics = db.prepare('SELECT source_key,code FROM collection_diagnostic').all();
    const coverage = db.prepare('SELECT missing_before,scan_incomplete FROM coverage').all();
    const marker = db.prepare('SELECT key_marker FROM identity_key_state').all();
    return {events, cursors, diagnostics, coverage, marker};
  } finally { db.close(); }
}
function empty(actual: ReturnType<typeof state>): void {
  assert.equal(actual.events.length, 0);
  assert.equal(actual.cursors.length, 0);
  assert.equal(actual.diagnostics.length, 0);
  assert.equal(actual.coverage.length, 0);
  assert.equal(actual.marker.length, 0);
}
async function collect(store: UsageStore, trace: Trace, mode: 'complete'|'incomplete'|'revoked') {
  return collectClaudeUsage(access(mode, trace), fixture.source_id, secret,
    async fileIdentity => store.loadCursor(fixture.principal_key, fileIdentity, secret),
    (batch, guard) => {
      trace.commit++;
      return commitClaudePreparedBatch(store, fixture.principal_key, fixture.source_id,
        secret, batch, guard);
    });
}
function freshTrace(): Trace { return {begin: 0, next: 0, cancel: 0, guard: 0, commit: 0}; }

test(CASE + ' three-file generation is atomic and replay-safe in isolated SQLite', async t => {
  const owner = ownedRoot();
  try {
    assert.equal(claudeRootKey(fixture.source_id, secret), fixture.key_derivation.root_key);
    assert.notEqual(claudeRootKey(fixture.other_source_id, secret), fixture.key_derivation.root_key);
    for (const [index, item] of fixture.files.entries()) {
      const identity = claudeCandidateFromSource(access('complete', freshTrace()), scanId,
        fixture.source_id, {relativeName: 'synthetic-' + index + '.jsonl',
          size: bytes[index].length, candidateToken: tokens[index],
          fileIdentityDigest: item.file_identity_digest}, secret).fileIdentity;
      assert.equal(identity, item.source_key_and_file_identity);
    }
    t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 1,
      actual: {root_key_matches_fixture: true, file_keys_match_fixture: 3,
        other_source_changes_root_key: true}}));

    const prepared = await collectClaudeUsage(access('complete', freshTrace()),
      fixture.source_id, secret, async () => null, (batch, guard) => { guard(); return batch; });
    assert.equal(prepared.files.length, 3);
    for (const [index, item] of fixture.files.entries()) {
      const file = prepared.files[index];
      assert.equal(file.sourceKey, item.source_key_and_file_identity);
      assert.equal(file.cursor.committedByteOffset, item.committed_byte_offset);
      assert.deepEqual(file.events.map(event => event.canonicalCallId), [item.call.canonical_call_id]);
      assert.deepEqual(file.diagnostics.map(diagnostic => diagnostic.code).sort(),
        [...item.diagnostic_codes].sort());
    }
    assert.equal(prepared.files[2].events[0].modelId, null);
    assert.equal(prepared.coverage.scanIncomplete, true);
    let mapped: Parameters<ClaudeScanStorePort['commitScanBatch']>[0] | null = null;
    const fakeStore: ClaudeScanStorePort = {commitScanBatch(batch) {
      mapped = batch; batch.guard();
      return {inserted: 3, duplicate: 0, conflict: 0};
    }};
    assert.deepEqual(commitClaudePreparedBatch(fakeStore, fixture.principal_key,
      fixture.source_id, secret, prepared, () => {}),
    {inserted: 3, duplicate: 0, conflict: 0});
    assert.ok(mapped);
    const mappedFiles = (mapped as Parameters<ClaudeScanStorePort['commitScanBatch']>[0]).files;
    assert.deepEqual(mappedFiles.map(file => file.events[0].turnId),
      fixture.files.map(file => file.call.turn_id));
    assert.deepEqual(mappedFiles.map(file => file.committedByteOffset), [410, 510, 610]);
    t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 2,
      actual: {files: prepared.files.length, accepted_calls: prepared.events.length,
        diagnostics_by_file: prepared.files.map(file => file.diagnostics.map(item => item.code)),
        cursor_offsets: mappedFiles.map(file => file.committedByteOffset),
        scope_surrogates_match_fixture: true, invalid_model_id_null: true,
        scan_incomplete: prepared.coverage.scanIncomplete}}));

    const faults: Array<{variant: string; begin: number; cancel: number;
      commit: number; entire_generation_absent: boolean}> = [];
    for (const mode of ['incomplete', 'cursor_failure', 'revoked'] as const) {
      const path = join(owner, mode, 'usage.sqlite');
      const store = new UsageStore(path);
      const trace = freshTrace();
      try {
        if (mode === 'cursor_failure') {
          const db = new DatabaseSync(path);
          try { db.exec("CREATE TRIGGER fail_second_cursor BEFORE INSERT ON source_cursor " +
            "WHEN (SELECT COUNT(*) FROM source_cursor)=1 BEGIN SELECT RAISE(ABORT,'second_cursor_fail'); END;"); }
          finally { db.close(); }
        }
        await assert.rejects(collect(store, trace,
          mode === 'cursor_failure' ? 'complete' : mode));
        assert.equal(trace.cancel, 1);
        assert.equal(trace.commit, mode === 'cursor_failure' ? 1 : 0);
      } finally { store.close(); }
      empty(state(path));
      faults.push({variant: mode, begin: trace.begin, cancel: trace.cancel,
        commit: trace.commit, entire_generation_absent: true});
    }
    t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 3,
      actual: {faults, every_generation_absent: true}}));
    const path = join(owner, 'complete', 'usage.sqlite');
    const store = new UsageStore(path);
    const trace = freshTrace();
    try {
      assert.deepEqual(await collect(store, trace, 'complete'),
        {inserted: 3, duplicate: 0, conflict: 0});
      assert.deepEqual(trace, {begin: 1, next: 0, cancel: 1, guard: 1, commit: 1});
      let actual = state(path);
      assert.equal(actual.events.length, 3);
      assert.equal(actual.events.reduce((n, row) => n + Number(row.input_tokens), 0), 350);
      assert.equal(actual.events.reduce((n, row) => n + Number(row.output_tokens), 0), 35);
      assert.deepEqual(actual.cursors.map(row => Number(row.committed_byte_offset)).sort((a,b) => a-b),
        [410, 510, 610]);
      assert.deepEqual(actual.events.map(row => String(row.source_scope_key)).sort(),
        [...fixture.expected_scope_keys].sort());
      assert.deepEqual(actual.diagnostics.map(row => String(row.code)).sort(),
        fixture.files.flatMap(file => file.diagnostic_codes).sort());
      assert.deepEqual(actual.coverage.map(row => Number(row.scan_incomplete)), [1]);
      assert.equal(actual.marker.length, 1);
      const persisted = JSON.stringify(actual);
      for (const sentinel of ['session-01', 'agent-01', 'msg-m', 'msg-s', 'msg-q',
        'SYNTHETIC-PROMPT-SENTINEL', '/synthetic/private/source.jsonl'])
        assert.equal(persisted.includes(sentinel), false);
      assert.deepEqual(await collect(store, freshTrace(), 'complete'),
        {inserted: 0, duplicate: 0, conflict: 0});
      actual = state(path);
      assert.equal(actual.events.length, 3);
      assert.deepEqual(actual.coverage.map(row => Number(row.scan_incomplete)), [1]);
      t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 4,
        actual: {calls: actual.events.length, input_tokens: 350, output_tokens: 35,
        total_tokens: 385, cursor_offsets: [410, 510, 610],
        diagnostics: actual.diagnostics.length, scan_incomplete: 1,
        replay_inserted: 0, private_values_in_db: false}}));
    } finally { store.close(); }
  } finally {
    rmSync(owner, {recursive: true});
    assert.equal(existsSync(owner), false);
    t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: CASE, owned_root_removed: true}));
  }
});
