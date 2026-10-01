import type { ClaudeCall, ClaudeDiagnostic } from './claude-format.ts';
import type { ClaudeFileCursor } from './claude-reader.ts';
import {commitClaudeSource, type ClaudeScanPlan, type GuardedClaudeSourceScanAccess} from './claude-scan.ts';

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

export interface ClaudePreparedBatch {
  events: ClaudeUsageProposal[];
  diagnostics: ClaudeDiagnostic[];
  cursors: ClaudeFileCursor[];
  coverage: {scanIncomplete: boolean; candidateCount: number};
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

/** This batch retains raw IDs only in main-process memory until TM-003 HMAC insertion. */
export function prepareClaudeBatch(plan: ClaudeScanPlan): ClaudePreparedBatch {
  return {
    events: plan.calls.map(claudeUsageProposal),
    diagnostics: plan.diagnostics,
    cursors: plan.cursors,
    coverage: {scanIncomplete: plan.scanIncomplete, candidateCount: plan.candidateCount},
  };
}

/** A TM-003 synchronous SQLite adapter is supplied as commitSync after source authorization. */
export async function collectClaudeUsage<T>(
  access: GuardedClaudeSourceScanAccess, sourceId: string, secret: Buffer,
  loadCursor: (fileIdentity: string) => Promise<ClaudeFileCursor | null>,
  commitSync: (batch: ClaudePreparedBatch, guard: () => void) => T,
): Promise<T> {
  return commitClaudeSource(access, sourceId, secret, loadCursor,
    (plan, guard) => commitSync(prepareClaudeBatch(plan), guard));
}
