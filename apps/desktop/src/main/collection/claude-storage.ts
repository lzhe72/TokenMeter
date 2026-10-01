import type {ClaudePreparedBatch, ClaudeUsageProposal} from './claude-event.ts';
import {claudeRootKey} from './claude-source.ts';

export interface ClaudeScanStorePort {
  commitScanBatch(batch: {
    principalKey: string; secret: Buffer; source: 'claude_code'; rootKey: string;
    files: Array<{sourceKey: string; fileIdentity: string; committedByteOffset: number;
      prefixMac: string; events: Array<{
        source: 'claude_code'; providerCallScope: 'provider-message';
        canonicalCallId: string; sessionId: string; turnId: string;
        occurredAtUtc: string; modelId: string | null; sourceVersion: string;
        usage: ClaudePreparedBatch['events'][number]['usage'];
      }>; diagnostics: Array<{code: string}>}>;
    coverage: {missingBefore: boolean; scanIncomplete: boolean}; guard: () => void;
  }): {inserted: number; duplicate: number; conflict: number};
}

function scope(event: ClaudeUsageProposal): string {
  if (!event.isSidechain) return 'claude-main-v1';
  if (event.attribution === 'parent_verified' && event.agentId)
    return 'claude-agent-v1:' + event.agentId;
  return 'claude-unverified-v1:' + event.canonicalCallId;
}

/** Raw Claude identifiers exist only in this synchronous in-memory store call for HMAC. */
export function commitClaudePreparedBatch(
  store: ClaudeScanStorePort, principalKey: string, sourceId: string, secret: Buffer,
  batch: ClaudePreparedBatch, guard: () => void,
): {inserted: number; duplicate: number; conflict: number} {
  const rootKey = claudeRootKey(sourceId, secret);
  if (!Array.isArray(batch.files) || batch.files.length === 0) throw new Error('claude_batch_invalid');
  if (!batch.coverage.scanIncomplete && batch.events.length === 0
      && batch.diagnostics.length === 0 && batch.files.every(file => !file.changed)) {
    guard();
    return {inserted: 0, duplicate: 0, conflict: 0};
  }
  const files = batch.files.map(file => {
    if (file.sourceKey !== file.fileIdentity || file.cursor.fileIdentity !== file.fileIdentity)
      throw new Error('claude_batch_invalid');
    return {
      sourceKey: file.sourceKey, fileIdentity: file.fileIdentity,
      committedByteOffset: file.cursor.committedByteOffset, prefixMac: file.cursor.prefixMac,
      events: file.events.map(event => {
        if (event.source !== 'claude_code' || event.providerCallScope !== 'provider-message'
            || (event.modelId !== null
              && !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(event.modelId)))
          throw new Error('claude_batch_invalid');
        return {source: 'claude_code' as const, providerCallScope: 'provider-message' as const,
          canonicalCallId: event.canonicalCallId, sessionId: event.sessionId,
          turnId: scope(event), occurredAtUtc: event.occurredAtUtc,
          modelId: event.modelId, sourceVersion: event.sourceVersion, usage: event.usage};
      }),
      diagnostics: file.diagnostics.flatMap(item => {
        if (!Number.isSafeInteger(item.count) || item.count < 1 || item.count > 10000)
          throw new Error('claude_batch_invalid');
        return Array.from({length: item.count}, () => ({code: item.code}));
      }),
    };
  });
  return store.commitScanBatch({principalKey, secret, source: 'claude_code', rootKey, files,
    coverage: {missingBefore: false, scanIncomplete: batch.coverage.scanIncomplete}, guard});
}
