import type {SourceAccess} from '../source-access.ts';
import type {UsageProfile} from './usage-profile.ts';

export type CollectionIdentity = {origin: string; accountId: string | null; verified: boolean};
export type CodexRuntime = {
  access: SourceAccess;
  profile: UsageProfile;
  getIdentity(): CollectionIdentity;
  stagingBudgetBytes: number;
};

/** Main-process source-ID adapter; fixed CORE-09 covers this entry before product IPC. */
export async function runCodexCollection(_sourceId: string, _runtime: CodexRuntime): Promise<void> {
  throw new Error('codex_runtime_not_implemented');
}
