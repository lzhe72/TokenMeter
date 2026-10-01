import type {SourceAccess} from '../source-access.ts';
import type {UsageStore} from './usage-store.ts';
import type {ClaudeTriggerAccount, ClaudeTriggerResult} from './claude-trigger.ts';

export type ClaudeRuntime = {
  access: SourceAccess;
  store: UsageStore;
  secret: Buffer;
  account(): ClaudeTriggerAccount | null;
};

/** Connects a confirmed Claude source to its private usage database. */
export async function runClaudeCollection(
  _sourceId: string, _runtime: ClaudeRuntime,
): Promise<ClaudeTriggerResult> {
  throw new Error('claude_runtime_unimplemented');
}
