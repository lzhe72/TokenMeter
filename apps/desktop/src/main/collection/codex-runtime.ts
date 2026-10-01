import type {SourceAccess} from '../source-access.ts';
import type {UsageProfile} from './usage-profile.ts';
import {collectCodex} from './codex-collector.ts';

export type CollectionIdentity = {origin: string; accountId: string | null; verified: boolean};
export type CodexRuntime = {
  access: SourceAccess;
  profile: UsageProfile;
  getIdentity(): CollectionIdentity;
  stagingBudgetBytes: number;
};

/** Main-process source-ID adapter; fixed CORE-09 covers this entry before product IPC. */
export async function runCodexCollection(sourceId: string, runtime: CodexRuntime): Promise<void> {
  const identity = runtime.getIdentity();
  if (!identity.verified || typeof identity.accountId !== 'string' || !identity.accountId)
    throw new Error('invalid_principal');
  await collectCodex({sourceId, access: runtime.access, store: runtime.profile.store,
    secret: runtime.profile.secret, stagingBudgetBytes: runtime.stagingBudgetBytes,
    principal: () => {
      const current = runtime.getIdentity();
      if (!current.verified || typeof current.accountId !== 'string' ||
          current.origin !== identity.origin || current.accountId !== identity.accountId)
        return {verified: false, key: ''};
      return {verified: true, key: runtime.profile.principalKey(current.origin, current.accountId)};
    }});
}
