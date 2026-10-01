import {collectClaudeUsage, type ClaudePreparedBatch} from './claude-event.ts';
import type {ClaudeFileCursor} from './claude-reader.ts';
import type {GuardedClaudeSourceScanAccess} from './claude-scan.ts';

export interface ClaudeTriggerAccount {
  principalKey: string;
  epoch: number;
  verified: boolean;
  active: boolean;
  mustChangePassword: boolean;
}

export interface ClaudeTriggerPorts {
  account(): ClaudeTriggerAccount | null;
  sourceFor(principalKey: string): string | null;
  access: GuardedClaudeSourceScanAccess;
  secret: Buffer;
  loadCursor(fileIdentity: string): Promise<ClaudeFileCursor | null>;
  commitSync(batch: ClaudePreparedBatch, guard: () => void): void;
}

export interface ClaudeTriggerResult {
  summary: {callCount: number; inputTokens: number; outputTokens: number;
    totalTokens: number; scanIncomplete: boolean};
  diagnostics: Array<{code: string; count: number}>;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function available(account: ClaudeTriggerAccount | null): account is ClaudeTriggerAccount {
  return !!account && typeof account.principalKey === 'string' && account.principalKey.length > 0
    && Number.isSafeInteger(account.epoch) && account.verified === true && account.active === true
    && account.mustChangePassword === false;
}
function requestSourceId(request: unknown): string {
  if (request === null || typeof request !== 'object' || Array.isArray(request)
      || ![Object.prototype, null].includes(Object.getPrototypeOf(request)))
    throw new Error('invalid_collection_request');
  const keys = Object.keys(request);
  if (keys.length !== 1 || keys[0] !== 'sourceId') throw new Error('invalid_collection_request');
  const sourceId = (request as {sourceId: unknown}).sourceId;
  if (typeof sourceId !== 'string' || !UUID.test(sourceId))
    throw new Error('invalid_collection_request');
  return sourceId;
}

/** Main-process-only injected boundary; callers provide neither paths nor account identity. */
export async function triggerClaudeCollection(
  request: unknown, ports: ClaudeTriggerPorts, signal?: AbortSignal,
): Promise<ClaudeTriggerResult> {
  const sourceId = requestSourceId(request);
  if (signal?.aborted) throw new Error('collection_cancelled');
  const initial = ports.account();
  if (!available(initial)) throw new Error('collection_unavailable');
  if (ports.sourceFor(initial.principalKey) !== sourceId)
    throw new Error('source_not_authorized');
  const current = (): void => {
    if (signal?.aborted) throw new Error('collection_cancelled');
    const now = ports.account();
    if (!available(now) || now.principalKey !== initial.principalKey || now.epoch !== initial.epoch
        || ports.sourceFor(now.principalKey) !== sourceId)
      throw new Error('collection_stale');
  };
  try {
    return await collectClaudeUsage(ports.access, sourceId, ports.secret,
      fileIdentity => ports.loadCursor(fileIdentity), (batch, guard) => {
        current();
        let inputTokens = 0;
        let outputTokens = 0;
        for (const event of batch.events) {
          inputTokens += event.usage.inputTokens;
          outputTokens += event.usage.outputTokens;
          if (!Number.isSafeInteger(inputTokens) || !Number.isSafeInteger(outputTokens)
              || !Number.isSafeInteger(inputTokens + outputTokens))
            throw new Error('collection_failed');
        }
        const result: ClaudeTriggerResult = {
          summary: {callCount: batch.events.length, inputTokens, outputTokens,
            totalTokens: inputTokens + outputTokens, scanIncomplete: batch.coverage.scanIncomplete},
          diagnostics: batch.diagnostics.map(item => ({code: item.code, count: item.count})),
        };
        const committed: unknown = ports.commitSync(batch, () => { current(); guard(); });
        if (committed !== null && typeof committed === 'object' && 'then' in committed)
          throw new Error('collection_failed');
        return result;
      });
  } catch (error) {
    if (signal?.aborted) throw new Error('collection_cancelled');
    const now = ports.account();
    if (!available(now) || now.principalKey !== initial.principalKey || now.epoch !== initial.epoch
        || ports.sourceFor(now.principalKey) !== sourceId)
      throw new Error('collection_stale');
    if (error instanceof Error && error.message === 'collection_stale') throw error;
    throw new Error('collection_failed');
  }
}
