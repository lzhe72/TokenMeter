import { DatabaseSync } from 'node:sqlite';

type ChildCount = {knownTokens: number; unknownRows: number};
export type SnapshotSummary = {
  calls: number; inputTokens: number; outputTokens: number; totalTokens: number;
  cachedInput: ChildCount; cacheWriteInput: ChildCount; reasoningOutput: ChildCount;
};
export type SnapshotDetail = {
  sourceEventKey: string; source: 'codex' | 'claude_code'; modelId: string | null;
  occurredAtUtc: string; inputTokens: number; outputTokens: number;
};

const utcPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/;
function validUtc(value: string): boolean {
  if (typeof value !== 'string' || !utcPattern.test(value)) return false;
  const millis = Date.parse(value);
  return Number.isFinite(millis) && new Date(millis).toISOString() ===
    (value.includes('.') ? value : value.replace('Z', '.000Z'));
}
function number(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0)
    throw new Error('invalid_usage_database');
  return value;
}
function safeModel(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value !== 'string' || !/^[A-Za-z0-9._-]{1,80}$/.test(value))
    throw new Error('invalid_model_id');
  return value;
}

/** One principal and UTC window on a caller-owned, read-only SQLite connection. */
export class UsageReadSnapshot {
  private readonly db: DatabaseSync;
  private active = false;
  private readonly parameters: [string, string, string];

  constructor(path: string, principalKey: string, startUtc: string, endExclusiveUtc: string) {
    if (!/^[a-f0-9]{64}$/.test(principalKey)) throw new Error('invalid_principal_key');
    if (!validUtc(startUtc) || !validUtc(endExclusiveUtc) || startUtc >= endExclusiveUtc)
      throw new Error('invalid_range');
    const normalized = (value: string): string =>
      value.includes('.') ? value : value.replace('Z', '.000Z');
    this.parameters = [principalKey, normalized(startUtc), normalized(endExclusiveUtc)];
    this.db = new DatabaseSync(path, {readOnly: true});
  }
  private ensureActive(): void {
    if (!this.active) throw new Error('snapshot_not_active');
  }
  begin(): void {
    if (this.active) throw new Error('snapshot_already_active');
    this.db.exec('BEGIN');
    this.active = true;
  }
  end(): void {
    this.ensureActive();
    this.db.exec('ROLLBACK');
    this.active = false;
  }
  close(): void {
    if (this.active) this.end();
    this.db.close();
  }
  private selectedRows(): Array<Record<string, unknown>> {
    this.ensureActive();
    return this.db.prepare(`SELECT source_event_key, source, model_id, occurred_at_utc,
      input_tokens, output_tokens, cached_input_tokens, cache_write_input_tokens,
      reasoning_output_tokens FROM usage_event
      WHERE principal_key = ?
        AND strftime('%Y-%m-%dT%H:%M:%fZ', occurred_at_utc) >= ?
        AND strftime('%Y-%m-%dT%H:%M:%fZ', occurred_at_utc) < ?
      ORDER BY occurred_at_utc, source, source_event_key`).all(...this.parameters);
  }
  private totals(): {rows: Array<Record<string, unknown>>; summary: SnapshotSummary} {
    const rows = this.selectedRows();
    const summary: SnapshotSummary = {calls: rows.length, inputTokens: 0, outputTokens: 0,
      totalTokens: 0, cachedInput: {knownTokens: 0, unknownRows: 0},
      cacheWriteInput: {knownTokens: 0, unknownRows: 0},
      reasoningOutput: {knownTokens: 0, unknownRows: 0}};
    for (const row of rows) {
      summary.inputTokens += number(row.input_tokens);
      summary.outputTokens += number(row.output_tokens);
      for (const [column, field] of [
        ['cached_input_tokens', 'cachedInput'],
        ['cache_write_input_tokens', 'cacheWriteInput'],
        ['reasoning_output_tokens', 'reasoningOutput'],
      ] as const) {
        if (row[column] === null) summary[field].unknownRows++;
        else summary[field].knownTokens += number(row[column]);
      }
    }
    summary.totalTokens = summary.inputTokens + summary.outputTokens;
    if (![summary.inputTokens, summary.outputTokens, summary.totalTokens,
      summary.cachedInput.knownTokens, summary.cacheWriteInput.knownTokens,
      summary.reasoningOutput.knownTokens].every(Number.isSafeInteger))
      throw new Error('invalid_usage_database');
    return {rows, summary};
  }
  summary(): SnapshotSummary { return this.totals().summary; }
  sources(): Record<string, number> {
    const result: Record<string, number> = {};
    for (const row of this.selectedRows()) {
      if (row.source !== 'codex' && row.source !== 'claude_code') throw new Error('invalid_source');
      const source = row.source;
      result[source] = (result[source] ?? 0) + number(row.input_tokens) + number(row.output_tokens);
      if (!Number.isSafeInteger(result[source])) throw new Error('invalid_usage_database');
    }
    return result;
  }
  models(): Record<string, number> {
    const result = new Map<string, number>();
    for (const row of this.selectedRows()) {
      const model = safeModel(row.model_id) ?? 'unknown_model';
      const total = (result.get(model) ?? 0) + number(row.input_tokens) + number(row.output_tokens);
      if (!Number.isSafeInteger(total)) throw new Error('invalid_usage_database');
      result.set(model, total);
    }
    return Object.fromEntries(result);
  }
  details(): SnapshotDetail[] {
    return this.selectedRows().map(row => {
      if (typeof row.source_event_key !== 'string' || !/^[a-f0-9]{64}$/.test(row.source_event_key) ||
          (row.source !== 'codex' && row.source !== 'claude_code') || !validUtc(String(row.occurred_at_utc)))
        throw new Error('invalid_usage_database');
      return {sourceEventKey: row.source_event_key, source: row.source,
        modelId: safeModel(row.model_id), occurredAtUtc: String(row.occurred_at_utc),
        inputTokens: number(row.input_tokens), outputTokens: number(row.output_tokens)};
    });
  }
  intervalPoint(): {calls: number; totalTokens: number} {
    const {summary} = this.totals();
    return {calls: summary.calls, totalTokens: summary.totalTokens};
  }
  emptyDayState(startUtc: string, endExclusiveUtc: string): {
    status: 'missing'; knownTokens: 0; totalTokens: null;
  } {
    this.ensureActive();
    if (!validUtc(startUtc) || !validUtc(endExclusiveUtc) || startUtc >= endExclusiveUtc)
      throw new Error('invalid_range');
    const row = this.db.prepare(`SELECT COUNT(*) AS calls FROM usage_event
      WHERE principal_key = ?
        AND strftime('%Y-%m-%dT%H:%M:%fZ', occurred_at_utc) >= ?
        AND strftime('%Y-%m-%dT%H:%M:%fZ', occurred_at_utc) < ?`)
      .get(this.parameters[0], startUtc.includes('.') ? startUtc : startUtc.replace('Z', '.000Z'),
        endExclusiveUtc.includes('.') ? endExclusiveUtc : endExclusiveUtc.replace('Z', '.000Z'));
    if (number(row?.calls) !== 0) throw new Error('day_not_empty');
    // Existing coverage rows describe scan state, not proof of an arbitrary day.
    return {status: 'missing', knownTokens: 0, totalTokens: null};
  }
}
