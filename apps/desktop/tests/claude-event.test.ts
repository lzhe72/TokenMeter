import { test } from 'node:test';
import assert from 'node:assert/strict';
import { claudeUsageProposal } from '../src/main/collection/claude-event.ts';
import type { ClaudeCall } from '../src/main/collection/claude-format.ts';

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
