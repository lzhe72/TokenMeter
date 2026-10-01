import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { summarizeUsage, coverageStatus } from '../src/shared/usage-statistics.ts';
import type { CoverageFacts, TrustedUsageEvent, UsageDiagnostic, UsageRequest } from '../src/shared/usage-statistics.ts';

const fixturePath = fileURLToPath(new URL('../../../tests/fixtures/tm005-core-slice.json', import.meta.url));
const fixtureBytes = readFileSync(fixturePath);
assert.equal(createHash('sha256').update(fixtureBytes).digest('hex'),
  '2dad1a42bc3051c8a1f820d12211c832522ba46586c3b84e00ebcd3b708470e9');
const fixture = JSON.parse(fixtureBytes.toString('utf8'));
assert.equal(fixture.fixture_id, 'tm005-core-slice-v1');
assert.equal(fixture.product_coverage_proven, false);

function freezeDeep<T>(value: T): T {
  if (value && typeof value === 'object') {
    for (const child of Object.values(value)) freezeDeep(child);
    Object.freeze(value);
  }
  return value;
}

function input(events: TrustedUsageEvent[] = fixture.trusted_events, diagnostics: UsageDiagnostic[] = [],
               coverage: CoverageFacts | null = {codex: 'complete', claude_code: 'complete'}): UsageRequest {
  return freezeDeep({principalKey: fixture.principal_key, startUtc: fixture.start_utc,
    endExclusiveUtc: fixture.end_exclusive_utc, events: structuredClone(events),
    diagnostics: structuredClone(diagnostics), coverage: structuredClone(coverage)});
}

test('TC-TM005-CORE-01: two sources, local day bounds, subtotals, and invalid inputs', () => {
  const request = input();
  const before = structuredClone(request);
  const summary = summarizeUsage(request);
  assert.deepEqual(summary.selectedEventIds, ['A', 'B']);
  assert.deepEqual({calls: summary.trustedCalls, input: summary.inputTokens,
    output: summary.outputTokens, known: summary.knownTokens},
    {calls: 2, input: 300, output: 30, known: 330});
  assert.deepEqual(summary.sourceTotals, {codex: 110, claude_code: 220});
  assert.deepEqual(summary.modelTotals, {unknown_model: 110, 'sonnet-test': 220});
  assert.deepEqual(summary.cachedInput, {knownTokens: 20, status: 'partial_unknown'});
  assert.deepEqual(summary.cacheWriteInput, {knownTokens: 0, status: 'unknown'});
  assert.deepEqual(summary.reasoningOutput, {knownTokens: 2, status: 'partial_unknown'});
  assert.deepEqual(request, before);
  for (const mutate of [
    (event: any) => { event.source = 'other'; },
    (event: any) => { event.input_tokens = -1; },
    (event: any) => { event.cached_input_tokens = 101; },
    (event: any) => { event.occurred_at_utc = 'not-a-date'; },
  ]) {
    const changed = structuredClone(fixture.trusted_events);
    mutate(changed[0]);
    assert.throws(() => summarizeUsage(input(changed)), /invalid/i);
  }
});

test('TC-TM005-CORE-02: unknown usage diagnostic never becomes zero', () => {
  const events = fixture.trusted_events.slice(0, 2);
  const baseline = summarizeUsage(input(events));
  assert.deepEqual({status: baseline.status, known: baseline.knownTokens, total: baseline.totalTokens},
    {status: 'complete', known: 330, total: 330});
  assert.deepEqual(baseline.sourceTotals, {codex: 110, claude_code: 220});
  assert.deepEqual(baseline.modelTotals, {unknown_model: 110, 'sonnet-test': 220});
  const withUnknown = summarizeUsage(input(events, [fixture.unknown_diagnostic]));
  assert.deepEqual({status: withUnknown.status, known: withUnknown.knownTokens,
    total: withUnknown.totalTokens, calls: withUnknown.trustedCalls},
    {status: 'partial', known: 330, total: null, calls: 2});
  assert.deepEqual(withUnknown.sourceTotals, baseline.sourceTotals);
  assert.deepEqual(withUnknown.modelTotals, baseline.modelTotals);
  const unknownOnly = summarizeUsage(input([], [fixture.unknown_diagnostic]));
  assert.deepEqual({status: unknownOnly.status, known: unknownOnly.knownTokens,
    total: unknownOnly.totalTokens, calls: unknownOnly.trustedCalls},
    {status: 'unknown', known: 0, total: null, calls: 0});
});

test('TC-TM005-CORE-03: declared coverage algebra and absent proof', () => {
  for (const row of fixture.coverage_algebra) {
    const actual = coverageStatus({codex: row.codex, claude_code: row.claude_code},
      row.trusted_tokens.reduce((sum: number, n: number) => sum + n, 0),
      row.trusted_tokens.length, row.unknown_count);
    assert.deepEqual(actual, {status: row.status, knownTokens: row.known_tokens,
      totalTokens: row.total_tokens}, row.id);
  }
  assert.deepEqual(coverageStatus(null, 0, 0, 0),
    {status: 'missing', knownTokens: 0, totalTokens: null});
});
