import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {claudeCandidateFromSource, claudeRootKey} from '../src/main/collection/claude-source.ts';
import {collectClaudeUsage} from '../src/main/collection/claude-event.ts';

const CASE = 'TC-TM004-CORE-05';
const raw = readFileSync(join(import.meta.dirname, '../../../tests/fixtures/tm004-storage-port-slice.json'));
assert.equal(createHash('sha256').update(raw).digest('hex'),
  '6e8603354ca0e6c3e2678074b2951b052fa2e34325e1ca02e5e0304cc8c7861a');
const fixture = JSON.parse(raw.toString('utf8')) as {
  source_id: string; other_source_id: string; secret_hex: string;
  key_derivation: {root_key: string};
  files: Array<{file_identity_digest: string; source_key_and_file_identity: string;
    committed_byte_offset: number; prefix_mac: string;
    call: {canonical_call_id: string; session_id: string; agent_id: string | null;
      turn_id: string; input_tokens: number; output_tokens: number; model_id: string};
    diagnostic_codes: string[]}>;
  model_id_rule: {accepted_pattern: string; invalid_value_result: null; invalid_diagnostic: string};
};
const secret = Buffer.from(fixture.secret_hex, 'hex');
const scanId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const stamp = '2026-10-01T00:00:00Z';
const line = (row: unknown): string => JSON.stringify(row) + '\n';
function assistant(index: number, sidechain: boolean, agentId: string | null): Record<string, unknown> {
  const item = fixture.files[index];
  return {type: 'assistant', version: '2.1.126', uuid: `row-${index}`,
    sessionId: item.call.session_id, isSidechain: sidechain,
    ...(agentId ? {agentId} : {}), timestamp: stamp,
    message: {role: 'assistant', id: item.call.canonical_call_id,
      model: item.call.model_id, usage: {input_tokens: item.call.input_tokens,
        output_tokens: item.call.output_tokens}}};
}
const parent = {type: 'user', version: '2.1.126', sessionId: 'session-01',
  isSidechain: false, timestamp: stamp, message: {role: 'user', content: [{type: 'tool_result'}]},
  toolUseResult: {agentId: 'agent-01'}};
const files = [
  Buffer.from(line(parent) + line(assistant(0, false, null)) + 'not-json\n'),
  Buffer.from(line(assistant(1, true, 'agent-01')) + line({...assistant(1, true, 'agent-01'),
    version: '2.1.127', uuid: 'unsupported-row'})),
  Buffer.from(line(assistant(2, true, null))),
];
const tokens = ['a'.repeat(32), 'b'.repeat(32), 'c'.repeat(32)];

test(`${CASE} fixed root and file identity vectors`, t => {
  assert.equal(claudeRootKey(fixture.source_id, secret), fixture.key_derivation.root_key);
  assert.notEqual(claudeRootKey(fixture.other_source_id, secret), fixture.key_derivation.root_key);
  for (const [index, item] of fixture.files.entries()) {
    const identity = claudeCandidateFromSource({async readCandidateChunk() { return Buffer.alloc(0); }},
      scanId, fixture.source_id, {relativeName: `synthetic-${index}.jsonl`, size: files[index].length,
        candidateToken: tokens[index], fileIdentityDigest: item.file_identity_digest}, secret).fileIdentity;
    assert.equal(identity, item.source_key_and_file_identity);
  }
  const changed = claudeCandidateFromSource({async readCandidateChunk() { return Buffer.alloc(0); }},
    scanId, fixture.other_source_id, {relativeName: 'synthetic-0.jsonl', size: files[0].length,
      candidateToken: tokens[0], fileIdentityDigest: fixture.files[0].file_identity_digest}, secret).fileIdentity;
  assert.notEqual(changed, fixture.files[0].source_key_and_file_identity);
  t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 1,
    root_key: fixture.key_derivation.root_key, file_keys: fixture.files.map(item => item.source_key_and_file_identity)}));
});

test(`${CASE} accepted events and diagnostics retain their file owner`, async t => {
  let commits = 0;
  const batch = await collectClaudeUsage({
    async beginCandidateScan(sourceId) {
      assert.equal(sourceId, fixture.source_id);
      return {scanId, complete: true, candidates: fixture.files.map((item, index) => ({
        relativeName: `synthetic-${index}.jsonl`, size: files[index].length,
        candidateToken: tokens[index], fileIdentityDigest: item.file_identity_digest}))};
    },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk(value, token, offset, maxBytes) {
      assert.equal(value, scanId);
      const index = tokens.indexOf(token);
      assert.notEqual(index, -1);
      return files[index].subarray(offset, offset + maxBytes);
    },
    async commitGuard(value) { assert.equal(value, scanId); return () => {}; },
    async cancelScan(value) { assert.equal(value, scanId); },
  }, fixture.source_id, secret, async () => null, (prepared, guard) => {
    commits++; guard(); return prepared;
  });
  assert.equal(commits, 1);
  const owned = batch as typeof batch & {files: Array<{
    sourceKey: string; fileIdentity: string; events: typeof batch.events;
    diagnostics: typeof batch.diagnostics; cursor: typeof batch.cursors[number]}>};
  assert.equal(owned.files.length, 3);
  for (const [index, item] of fixture.files.entries()) {
    const file = owned.files[index];
    assert.equal(file.sourceKey, item.source_key_and_file_identity);
    assert.equal(file.fileIdentity, item.source_key_and_file_identity);
    assert.deepEqual(file.events.map(event => event.canonicalCallId), [item.call.canonical_call_id]);
    assert.deepEqual(file.diagnostics.map(diagnostic => diagnostic.code).sort(),
      [...item.diagnostic_codes].sort());
    assert.equal(file.cursor.fileIdentity, item.source_key_and_file_identity);
  }
  assert.equal(owned.files[2].events[0].modelId, fixture.model_id_rule.invalid_value_result);
  assert.equal(batch.coverage.scanIncomplete, true);
  t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 2,
    files: owned.files.length, calls: owned.files.map(file => file.events.length),
    diagnostics: owned.files.map(file => file.diagnostics.map(item => item.code)),
    scan_incomplete: batch.coverage.scanIncomplete, commit_port_calls: commits}));
});
