import type {SourceAccess} from '../source-access.ts';
import type {UsageStore} from './usage-store.ts';
import type {ClaudeTriggerAccount, ClaudeTriggerResult} from './claude-trigger.ts';
import {triggerClaudeCollection} from './claude-trigger.ts';
import {commitClaudePreparedBatch} from './claude-storage.ts';

export type ClaudeRuntime = {
  access: SourceAccess;
  store: UsageStore;
  secret: Buffer;
  account(): ClaudeTriggerAccount | null;
};

/** Connects a confirmed Claude source to its private usage database. */
export async function runClaudeCollection(
  sourceId: string, runtime: ClaudeRuntime,
): Promise<ClaudeTriggerResult> {
  const principalKey = runtime.account()?.principalKey ?? '';
  return triggerClaudeCollection({sourceId}, {
    account: () => runtime.account(),
    sourceFor: candidatePrincipal => {
      if (runtime.account()?.principalKey !== candidatePrincipal) return null;
      const source = runtime.access.snapshot().claude_code.confirmed;
      return source?.collectAllowed && source.status === 'confirmed_enabled' ? source.sourceId : null;
    },
    access: runtime.access,
    secret: runtime.secret,
    loadCursor: async fileIdentity => runtime.store.loadCursor(principalKey, fileIdentity, runtime.secret),
    commitSync: (batch, guard) => {
      commitClaudePreparedBatch(runtime.store, principalKey, sourceId, runtime.secret, batch, guard);
    },
  });
}
