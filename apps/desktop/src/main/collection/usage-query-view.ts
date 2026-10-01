import {localDayUtcBounds} from '../../shared/usage-date.ts';
import {UsageReadSnapshot} from './usage-snapshot.ts';
import type {SnapshotDetail} from './usage-snapshot.ts';

export type QueryState = 'partial' | 'missing';
export type QuerySummary = {
  calls: number; inputTokens: number; outputTokens: number;
  knownTokens: number; totalTokens: null; state: QueryState;
  cachedInput: {knownTokens: number; unknownRows: number};
  cacheWriteInput: {knownTokens: number; unknownRows: number};
  reasoningOutput: {knownTokens: number; unknownRows: number};
};
export type QueryView = {
  summary: QuerySummary;
  sources: Array<{source: 'codex' | 'claude_code'; knownTokens: number}>;
  models: Array<{modelId: string | null; knownTokens: number}>;
  details: SnapshotDetail[];
  trend: Array<{localDay: string; state: QueryState; knownTokens: number; totalTokens: null}>;
};

function checkedSum(left: number, right: number): number {
  const total = left + right;
  if (!Number.isSafeInteger(total)) throw new Error('invalid_usage_database');
  return total;
}

/** A caller-owned read transaction keeps all view sections on one SQLite version. */
export class UsageQueryView {
  private readonly snapshot: UsageReadSnapshot;
  private readonly localDay: string;

  constructor(path: string, principalKey: string, timezone: string, localDay: string) {
    const bounds = localDayUtcBounds(timezone, localDay);
    this.snapshot = new UsageReadSnapshot(path, principalKey,
      bounds.startUtc, bounds.endExclusiveUtc);
    this.localDay = localDay;
  }

  begin(): void { this.snapshot.begin(); }
  end(): void { this.snapshot.end(); }
  close(): void { this.snapshot.close(); }

  read(): QueryView {
    const counts = this.snapshot.summary();
    const details = this.snapshot.details();
    const sources = new Map<'codex' | 'claude_code', number>();
    const models = new Map<string | null, number>();
    for (const detail of details) {
      const amount = checkedSum(detail.inputTokens, detail.outputTokens);
      sources.set(detail.source, checkedSum(sources.get(detail.source) ?? 0, amount));
      models.set(detail.modelId, checkedSum(models.get(detail.modelId) ?? 0, amount));
    }
    if (details.length !== counts.calls ||
        [...sources.values()].reduce(checkedSum, 0) !== counts.totalTokens ||
        [...models.values()].reduce(checkedSum, 0) !== counts.totalTokens)
      throw new Error('inconsistent_usage_snapshot');
    // Scan metadata does not establish full coverage for an arbitrary civil day.
    const state: QueryState = counts.calls === 0 ? 'missing' : 'partial';
    const summary: QuerySummary = {
      calls: counts.calls, inputTokens: counts.inputTokens,
      outputTokens: counts.outputTokens, knownTokens: counts.totalTokens,
      totalTokens: null, state, cachedInput: counts.cachedInput,
      cacheWriteInput: counts.cacheWriteInput, reasoningOutput: counts.reasoningOutput,
    };
    return {summary,
      sources: [...sources].map(([source, knownTokens]) => ({source, knownTokens})),
      models: [...models].map(([modelId, knownTokens]) => ({modelId, knownTokens})),
      details,
      trend: [{localDay: this.localDay, state,
        knownTokens: counts.totalTokens, totalTokens: null}],
    };
  }
}
