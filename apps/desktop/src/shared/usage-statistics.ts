/** Pure usage statistics over already trusted, source-scoped events. */

export type UsageSource = 'codex' | 'claude_code';
export type CoverageState = 'complete' | 'missing';
export type SummaryState = 'complete' | 'partial' | 'missing' | 'unknown';
export type SubtotalState = 'complete' | 'partial_unknown' | 'unknown';

export interface TrustedUsageEvent {
  id?: string;
  principal_key: string;
  source: UsageSource;
  source_event_key: string;
  occurred_at_utc: string;
  model_id: string | null;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number | null;
  cache_write_input_tokens: number | null;
  reasoning_output_tokens: number | null;
}

export interface UsageDiagnostic {
  principal_key: string;
  source: UsageSource;
  occurred_at_utc: string;
  code: string;
}

export type CoverageFacts = Record<UsageSource, CoverageState>;

export interface UsageRequest {
  principalKey: string;
  startUtc: string;
  endExclusiveUtc: string;
  events: readonly TrustedUsageEvent[];
  diagnostics: readonly UsageDiagnostic[];
  coverage: CoverageFacts | null;
}

export interface CoverageResult {
  status: SummaryState;
  knownTokens: number;
  totalTokens: number | null;
}

export interface UsageSummary extends CoverageResult {
  selectedEventIds: string[];
  trustedCalls: number;
  inputTokens: number;
  outputTokens: number;
  sourceTotals: Record<string, number>;
  modelTotals: Record<string, number>;
  cachedInput: {knownTokens: number; status: SubtotalState};
  cacheWriteInput: {knownTokens: number; status: SubtotalState};
  reasoningOutput: {knownTokens: number; status: SubtotalState};
}

function invalid(field: string): never { throw new Error('invalid ' + field); }

function nonempty(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.length === 0) invalid(field);
  return value;
}

function source(value: unknown): UsageSource {
  if (value !== 'codex' && value !== 'claude_code') invalid('source');
  return value;
}

function utc(value: unknown, field: string): number {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) invalid(field);
  const millis = Date.parse(value);
  if (!Number.isFinite(millis) || new Date(millis).toISOString() !==
      (value.includes('.') ? value : value.replace('Z', '.000Z'))) invalid(field);
  return millis;
}

function tokens(value: unknown, field: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) invalid(field);
  return value as number;
}

function childTokens(value: unknown, parent: number, field: string): number | null {
  if (value === null) return null;
  const count = tokens(value, field);
  if (count > parent) invalid(field);
  return count;
}

function checkedSum(a: number, b: number): number {
  const sum = a + b;
  if (!Number.isSafeInteger(sum)) invalid('token total overflow');
  return sum;
}

function validateEvent(event: TrustedUsageEvent): number {
  if (!event || typeof event !== 'object') invalid('event');
  nonempty(event.principal_key, 'principal_key');
  source(event.source);
  nonempty(event.source_event_key, 'source_event_key');
  if (event.id !== undefined) nonempty(event.id, 'id');
  if (event.model_id !== null) nonempty(event.model_id, 'model_id');
  const at = utc(event.occurred_at_utc, 'occurred_at_utc');
  const input = tokens(event.input_tokens, 'input_tokens');
  const output = tokens(event.output_tokens, 'output_tokens');
  childTokens(event.cached_input_tokens, input, 'cached_input_tokens');
  childTokens(event.cache_write_input_tokens, input, 'cache_write_input_tokens');
  childTokens(event.reasoning_output_tokens, output, 'reasoning_output_tokens');
  checkedSum(input, output);
  return at;
}

function validateDiagnostic(diagnostic: UsageDiagnostic): number {
  if (!diagnostic || typeof diagnostic !== 'object') invalid('diagnostic');
  nonempty(diagnostic.principal_key, 'principal_key');
  source(diagnostic.source);
  nonempty(diagnostic.code, 'diagnostic code');
  return utc(diagnostic.occurred_at_utc, 'diagnostic occurred_at_utc');
}

/** Coverage facts are declarations from the caller, never inferred from empty events. */
export function coverageStatus(coverage: CoverageFacts | null, knownTokens: number,
                               trustedCalls: number, unknownCount: number): CoverageResult {
  tokens(knownTokens, 'knownTokens');
  tokens(trustedCalls, 'trustedCalls');
  tokens(unknownCount, 'unknownCount');
  if (trustedCalls === 0 && knownTokens !== 0) invalid('knownTokens without trusted calls');
  if (coverage !== null && (coverage?.codex !== 'complete' && coverage?.codex !== 'missing' ||
      coverage?.claude_code !== 'complete' && coverage?.claude_code !== 'missing')) invalid('coverage');
  if (trustedCalls > 0) {
    const complete = coverage?.codex === 'complete' && coverage.claude_code === 'complete' && unknownCount === 0;
    return {status: complete ? 'complete' : 'partial', knownTokens, totalTokens: complete ? knownTokens : null};
  }
  if (unknownCount > 0) return {status: 'unknown', knownTokens: 0, totalTokens: null};
  if (coverage?.codex === 'complete' && coverage.claude_code === 'complete')
    return {status: 'complete', knownTokens: 0, totalTokens: 0};
  return {status: 'missing', knownTokens: 0, totalTokens: null};
}

function subtotal(values: readonly (number | null)[]): {knownTokens: number; status: SubtotalState} {
  let knownTokens = 0;
  let knownCount = 0;
  for (const value of values) {
    if (value === null) continue;
    knownTokens = checkedSum(knownTokens, value);
    knownCount++;
  }
  return {knownTokens, status: values.length > 0 && knownCount === values.length ? 'complete' :
    knownCount === 0 ? 'unknown' : 'partial_unknown'};
}

export function summarizeUsage(request: UsageRequest): UsageSummary {
  if (!request || typeof request !== 'object') invalid('request');
  const principal = nonempty(request.principalKey, 'principalKey');
  const start = utc(request.startUtc, 'startUtc');
  const end = utc(request.endExclusiveUtc, 'endExclusiveUtc');
  if (start >= end) invalid('range');
  if (!Array.isArray(request.events) || !Array.isArray(request.diagnostics)) invalid('arrays');
  const selected: TrustedUsageEvent[] = [];
  const identities = new Set<string>();
  for (const event of request.events) {
    const at = validateEvent(event);
    const identity = JSON.stringify([event.principal_key, event.source, event.source_event_key]);
    if (identities.has(identity)) invalid('duplicate trusted identity');
    identities.add(identity);
    if (event.principal_key === principal && at >= start && at < end) selected.push(event);
  }
  let unknownCount = 0;
  for (const diagnostic of request.diagnostics) {
    const at = validateDiagnostic(diagnostic);
    if (diagnostic.principal_key === principal && at >= start && at < end) unknownCount++;
  }
  let inputTokens = 0;
  let outputTokens = 0;
  const sourceTotals = new Map<string, number>();
  const modelTotals = new Map<string, number>();
  for (const event of selected) {
    const amount = checkedSum(event.input_tokens, event.output_tokens);
    inputTokens = checkedSum(inputTokens, event.input_tokens);
    outputTokens = checkedSum(outputTokens, event.output_tokens);
    sourceTotals.set(event.source, checkedSum(sourceTotals.get(event.source) ?? 0, amount));
    const model = event.model_id ?? 'unknown_model';
    modelTotals.set(model, checkedSum(modelTotals.get(model) ?? 0, amount));
  }
  const knownTokens = checkedSum(inputTokens, outputTokens);
  return {
    ...coverageStatus(request.coverage, knownTokens, selected.length, unknownCount),
    selectedEventIds: selected.map(event => event.id ?? event.source_event_key),
    trustedCalls: selected.length, inputTokens, outputTokens,
    sourceTotals: Object.fromEntries(sourceTotals), modelTotals: Object.fromEntries(modelTotals),
    cachedInput: subtotal(selected.map(event => event.cached_input_tokens)),
    cacheWriteInput: subtotal(selected.map(event => event.cache_write_input_tokens)),
    reasoningOutput: subtotal(selected.map(event => event.reasoning_output_tokens)),
  };
}
