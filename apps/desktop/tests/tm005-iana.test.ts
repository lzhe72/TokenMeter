import { test } from 'node:test';
import type { TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { localDayUtcBounds } from '../src/shared/usage-date.ts';

const caseId = 'TC-TM005-CORE-04';
const fixtureBytes = readFileSync(fileURLToPath(
  new URL('../../../tests/fixtures/tm005-iana-core-slice.json', import.meta.url)));
const fixtureSha256 = createHash('sha256').update(fixtureBytes).digest('hex');
assert.equal(fixtureSha256, '0f82b75e06c1ed008f3b02fde98fdc982fc30fbc5cff66771f63793e40bdb401');
const fixture = JSON.parse(fixtureBytes.toString('utf8'));
assert.equal(fixture.fixture_id, 'tm005-iana-day-v1');
assert.equal(fixture.product_time_window_proven, false);

function step(t: TestContext, number: number, actual: Record<string, unknown>): void {
  t.diagnostic(JSON.stringify({case_id: caseId, kind: 'step', step: number, actual}));
}

test('TC-TM005-CORE-04: IANA civil day UTC bounds and DST', t => {
  const original = structuredClone(fixture);
  const standard: Record<string, unknown> = {};
  for (const day of fixture.valid_days.slice(0, 2)) {
    const actual = localDayUtcBounds(day.timezone, day.local_day);
    assert.deepEqual(actual, {startUtc: day.start_utc,
      endExclusiveUtc: day.end_exclusive_utc, durationHours: day.duration_hours});
    standard[day.timezone] = actual;
  }
  step(t, 1, {fixtureSha256, bounds: standard});

  const dst: Record<string, unknown> = {};
  for (const day of fixture.valid_days.slice(2)) {
    const actual = localDayUtcBounds(day.timezone, day.local_day);
    assert.deepEqual(actual, {startUtc: day.start_utc,
      endExclusiveUtc: day.end_exclusive_utc, durationHours: day.duration_hours});
    const boundaries = fixture.boundary_events.find((entry: {timezone: string; local_day: string}) =>
      entry.timezone === day.timezone && entry.local_day === day.local_day);
    assert.ok(boundaries);
    const selected = ['before', 'at_start', 'before_end', 'at_end'].filter(key =>
      boundaries[key] >= actual.startUtc && boundaries[key] < actual.endExclusiveUtc);
    assert.deepEqual(selected, ['at_start', 'before_end']);
    dst[day.local_day] = {bounds: actual, selected};
  }
  step(t, 2, {dst});

  const rejected: Record<string, string> = {};
  for (const row of fixture.invalid_inputs) {
    assert.throws(() => localDayUtcBounds(row.timezone, row.local_day),
      (error: unknown) => error instanceof Error && error.message === row.error);
    rejected[row.timezone + ':' + row.local_day] = row.error;
  }
  assert.deepEqual(fixture, original);
  step(t, 3, {rejected, unchangedInput: true});
  t.diagnostic(JSON.stringify({case_id: caseId, kind: 'cleanup',
    resource_scope: 'memory_only', external_resources_created: false}));
});
