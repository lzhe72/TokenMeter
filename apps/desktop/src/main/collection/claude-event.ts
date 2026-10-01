import type { ClaudeCall } from './claude-format.ts';

export interface ClaudeUsageProposal {
  source: 'claude_code';
  providerCallScope: 'provider-message';
  canonicalCallId: string;
  sessionId: string;
  agentId: string | null;
  occurredAtUtc: string;
  modelId: string | null;
  sourceVersion: '2.1.126';
  usage: {
    inputTokens: number;
    outputTokens: number;
    cachedInputTokens: number | null;
    cacheWriteInputTokens: number | null;
    reasoningOutputTokens: null;
    totalTokens: number;
  };
}

/** Raw identity remains in memory for TM-003 HMAC; this object must not be serialized to SQLite or IPC. */
export function claudeUsageProposal(call: ClaudeCall): ClaudeUsageProposal {
  const totalTokens = call.inputTokens + call.outputTokens;
  if (!Number.isSafeInteger(totalTokens)) throw new Error('claude_invalid_total');
  return {
    source: 'claude_code', providerCallScope: 'provider-message',
    canonicalCallId: call.canonicalCallId, sessionId: call.sessionId,
    agentId: call.agentId, occurredAtUtc: call.occurredAtUtc,
    modelId: call.model, sourceVersion: call.sourceVersion,
    usage: {
      inputTokens: call.inputTokens, outputTokens: call.outputTokens,
      cachedInputTokens: call.cachedReadInputTokens,
      cacheWriteInputTokens: call.cachedWriteInputTokens,
      reasoningOutputTokens: null, totalTokens,
    },
  };
}
