import { test } from 'node:test';
import assert from 'node:assert/strict';
import { claudeUsageProposal, collectClaudeUsage } from '../src/main/collection/claude-event.ts';
import type { ClaudeCall } from '../src/main/collection/claude-format.ts';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import type {GuardedClaudeSourceScanAccess} from '../src/main/collection/claude-scan.ts';

test('TC-TM004-PARSER-01 module: cache is a child count and never inflates total', () => {
  const call: ClaudeCall = {
    canonicalCallId: 'msg-synthetic-cache', rowUuid: 'row-synthetic', sessionId: 'session-synthetic',
    agentId: 'agent-synthetic', isSidechain: true, attribution: 'parent_verified',
    occurredAtUtc: '2026-10-01T00:00:00.000Z', model: 'claude-sonnet-4-6',
    inputTokens: 100, outputTokens: 10, cachedReadInputTokens: 20, cachedWriteInputTokens: 5,
    sourceVersion: '2.1.126',
  };
  const event = claudeUsageProposal(call);
  assert.equal(event.source, 'claude_code');
  assert.equal(event.providerCallScope, 'provider-message');
  assert.equal(event.canonicalCallId, call.canonicalCallId);
  assert.equal(event.agentId, call.agentId);
  assert.deepEqual(event.usage, {inputTokens: 100, outputTokens: 10, cachedInputTokens: 20,
    cacheWriteInputTokens: 5, reasoningOutputTokens: null, totalTokens: 110});
  assert.doesNotMatch(JSON.stringify(event), /row-synthetic/);
});

test('TC-TM004-DIAG-01 module: absent cache fields remain unknown', () => {
  const call: ClaudeCall = {
    canonicalCallId: 'msg-synthetic-unknown-cache', rowUuid: 'row-synthetic', sessionId: 'session-synthetic',
    agentId: null, isSidechain: false, attribution: 'main',
    occurredAtUtc: '2026-10-01T00:00:00.000Z', model: null,
    inputTokens: 13, outputTokens: 7, cachedReadInputTokens: null, cachedWriteInputTokens: null,
    sourceVersion: '2.1.126',
  };
  const event = claudeUsageProposal(call);
  assert.equal(event.usage.totalTokens, 20);
  assert.equal(event.usage.cachedInputTokens, null);
  assert.equal(event.usage.cacheWriteInputTokens, null);
  assert.equal(event.modelId, null);
});

test('TM004 collection module boundary: guarded source reaches synchronous batch adapter', async () => {
  const fixture = join(import.meta.dirname,
    '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-main.jsonl');
  const raw = readFileSync(fixture, 'utf8').split('\n').filter(Boolean)
    .map(line => JSON.parse(line) as Record<string, unknown>).find(row => row.type === 'assistant')!;
  const bytes = Buffer.from(JSON.stringify(raw) + '\n');
  const scanId = '00000000-0000-4000-8000-000000000001';
  const sourceId = '00000000-0000-4000-8000-000000000002';
  const secret = Buffer.alloc(32, 0x42);
  let guardCalls = 0, canceled = false, committed = false;
  const access: GuardedClaudeSourceScanAccess = {
    async beginCandidateScan() { return {scanId, complete: true, candidates: [{
      relativeName: 'project/session.jsonl', size: bytes.length,
      candidateToken: 'a'.repeat(32), fileIdentityDigest: 'b'.repeat(64),
    }]}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk(_scan, _token, offset, maxBytes) { return bytes.subarray(offset, offset + maxBytes); },
    async commitGuard() { return () => { guardCalls++; assert.equal(canceled, false); }; },
    cancelScan() { canceled = true; },
  };
  const receipt = await collectClaudeUsage(access, sourceId, secret, async () => null, (batch, guard) => {
    committed = true;
    assert.equal(guardCalls, 1);
    assert.equal(canceled, false);
    assert.equal(batch.events.length, 1);
    assert.deepEqual(batch.events[0].usage, {inputTokens: 13, outputTokens: 7,
      cachedInputTokens: 0, cacheWriteInputTokens: 0, reasoningOutputTokens: null, totalTokens: 20});
    assert.equal(batch.cursors.length, 1);
    assert.equal(batch.cursors[0].committedByteOffset, bytes.length);
    assert.deepEqual(batch.coverage, {scanIncomplete: false, candidateCount: 1});
    assert.equal(JSON.stringify(batch).includes('project/session.jsonl'), false);
    guard();
    return {accepted: batch.events.length};
  });
  assert.deepEqual(receipt, {accepted: 1});
  assert.equal(guardCalls, 2);
  assert.equal(committed, true);
  assert.equal(canceled, true);
});
