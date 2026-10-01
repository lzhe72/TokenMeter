import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {commitClaudePreparedBatch, type ClaudeScanStorePort} from '../src/main/collection/claude-storage.ts';
import type {ClaudePreparedBatch, ClaudeUsageProposal} from '../src/main/collection/claude-event.ts';

const CASE = 'TC-TM004-CORE-05';
const raw = readFileSync(join(import.meta.dirname, '../../../tests/fixtures/tm004-storage-port-slice.json'));
assert.equal(createHash('sha256').update(raw).digest('hex'),
  '6e8603354ca0e6c3e2678074b2951b052fa2e34325e1ca02e5e0304cc8c7861a');
const fixture = JSON.parse(raw.toString('utf8')) as {
  source_id: string; principal_key: string; secret_hex: string;
  key_derivation: {root_key: string};
  files: Array<{source_key_and_file_identity: string; committed_byte_offset: number;
    prefix_mac: string; call: {canonical_call_id: string; session_id: string;
      agent_id: string | null; turn_id: string; input_tokens: number; output_tokens: number;
      model_id: string}; diagnostic_codes: string[]}>;
};

test(CASE + ' mapped generation calls the atomic store port once', t => {
  const secret = Buffer.from(fixture.secret_hex, 'hex');
  let commits = 0;
  let guards = 0;
  let received: Parameters<ClaudeScanStorePort['commitScanBatch']>[0] | null = null;
  const store: ClaudeScanStorePort = {commitScanBatch(batch) {
    commits++; received = batch; batch.guard();
    return {inserted: 3, duplicate: 0, conflict: 0};
  }};
  const batch: ClaudePreparedBatch = {
    events: [], diagnostics: [], cursors: [], coverage: {scanIncomplete: true, candidateCount: 3},
    files: fixture.files.map((item, index) => {
      const event: ClaudeUsageProposal & {isSidechain: boolean;
        attribution: 'main'|'parent_verified'|'unverified_parent'} = {
        source: 'claude_code', providerCallScope: 'provider-message',
        canonicalCallId: item.call.canonical_call_id, sessionId: item.call.session_id,
        agentId: item.call.agent_id, isSidechain: index > 0,
        attribution: index === 0 ? 'main' : index === 1 ? 'parent_verified' : 'unverified_parent',
        occurredAtUtc: '2026-10-01T00:00:00Z', sourceVersion: '2.1.126',
        modelId: index === 2 ? null : item.call.model_id,
        usage: {inputTokens: item.call.input_tokens, outputTokens: item.call.output_tokens,
          cachedInputTokens: null, cacheWriteInputTokens: null, reasoningOutputTokens: null,
          totalTokens: item.call.input_tokens + item.call.output_tokens},
      };
      return {sourceKey: item.source_key_and_file_identity,
        fileIdentity: item.source_key_and_file_identity,
        events: [event], diagnostics: item.diagnostic_codes.map(code => ({code: code as
          ClaudePreparedBatch['diagnostics'][number]['code'], count: 1})),
        cursor: {fileIdentity: item.source_key_and_file_identity,
          committedByteOffset: item.committed_byte_offset, prefixMac: item.prefix_mac}};
    }),
  };
  const result = commitClaudePreparedBatch(store, fixture.principal_key, fixture.source_id,
    secret, batch, () => { guards++; });
  assert.deepEqual(result, {inserted: 3, duplicate: 0, conflict: 0});
  assert.equal(commits, 1);
  assert.equal(guards, 1);
  assert.ok(received);
  const mapped = received as Parameters<ClaudeScanStorePort['commitScanBatch']>[0];
  assert.equal(mapped.rootKey, fixture.key_derivation.root_key);
  assert.equal(mapped.source, 'claude_code');
  assert.deepEqual(mapped.coverage, {missingBefore: false, scanIncomplete: true});
  for (const [index, item] of fixture.files.entries()) {
    const file = mapped.files[index];
    assert.equal(file.sourceKey, item.source_key_and_file_identity);
    assert.equal(file.fileIdentity, item.source_key_and_file_identity);
    assert.equal(file.committedByteOffset, item.committed_byte_offset);
    assert.equal(file.prefixMac, item.prefix_mac);
    assert.deepEqual(file.diagnostics.map(value => value.code), item.diagnostic_codes);
    assert.equal(file.events.length, 1);
    assert.equal(file.events[0].turnId, item.call.turn_id);
    assert.equal(file.events[0].modelId, index === 2 ? null : item.call.model_id);
  }
  t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 2,
    atomic_commit_port_calls: commits, guard_calls: guards,
    offsets: mapped.files.map(file => file.committedByteOffset),
    turn_scopes: mapped.files.map(file => file.events[0].turnId)}));
});
