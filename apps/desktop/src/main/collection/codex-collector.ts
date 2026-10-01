import type {SourceAccess} from '../source-access.ts';
import type {UsageStore} from './usage-store.ts';

export type CodexCollectionAccess = Pick<SourceAccess,
  'snapshot'|'beginCandidateScan'|'nextCandidatePage'|'readCandidateChunk'|'commitGuard'|'cancelScan'>;
export type CodexCollectionInput = {
  sourceId: string;
  access: CodexCollectionAccess;
  store: UsageStore;
  secret: Buffer;
  principal(): {verified: boolean; key: string};
  stagingBudgetBytes: number;
};

export async function collectCodex(_input: CodexCollectionInput): Promise<void> {
  throw new Error('collector_not_implemented');
}
