import { test } from 'node:test';
import type { TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { chmodSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';
import { UsageStore } from '../src/main/collection/usage-store.ts';
import { sourceEventKey } from '../src/main/collection/usage-identity.ts';
import { UsageReadSnapshot } from '../src/main/collection/usage-snapshot.ts';

const caseId = 'TC-TM005-CORE-05';
const fixtureBytes = readFileSync(fileURLToPath(
  new URL('../../../tests/fixtures/tm005-sqlite-snapshot-slice.json', import.meta.url)));
const fixtureSha256 = createHash('sha256').update(fixtureBytes).digest('hex');
assert.equal(fixtureSha256, '0fe6af3120e41b1b3cb6633a6507a265b0eef086901357c6c370058177232f12');
const fixture = JSON.parse(fixtureBytes.toString('utf8'));
assert.equal(fixture.fixture_id, 'tm005-sqlite-snapshot-v1');

type SeedEvent = typeof fixture.events[number];
function labelKey(row: SeedEvent): string {
  return sourceEventKey(Buffer.from(fixture.secret_hex, 'hex'), row.source,
    fixture.seed_contract.provider_call_scope[row.source], row.canonical_call_id);
}
function seed(store: UsageStore, row: SeedEvent): void {
  const spec = fixture.seed_contract;
  const result = store.commitBatch({
    principalKey: row.principal === 'selected' ? fixture.principal_key : fixture.other_principal_key,
    secret: Buffer.from(fixture.secret_hex, 'hex'), source: row.source,
    sourceKey: spec.source_key[row.source], rootKey: spec.root_key[row.source],
    fileIdentity: spec.file_identity[row.source], committedByteOffset: spec.committed_byte_offset,
    prefixMac: spec.prefix_mac, diagnostics: [],
    coverage: {missingBefore: spec.coverage.missing_before,
      scanIncomplete: spec.coverage.scan_incomplete},
    events: [{source: row.source, providerCallScope: spec.provider_call_scope[row.source],
      canonicalCallId: row.canonical_call_id, sessionId: spec.session_id, turnId: spec.turn_id,
      occurredAtUtc: row.occurred_at_utc, sourceVersion: spec.source_version[row.source],
      modelId: row.model_id, usage: {inputTokens: row.input_tokens, outputTokens: row.output_tokens,
        totalTokens: row.input_tokens + row.output_tokens,
        cachedInputTokens: row.cached_input_tokens, cacheWriteInputTokens: row.cache_write_input_tokens,
        reasoningOutputTokens: row.reasoning_output_tokens}}],
  });
  assert.deepEqual(result, {inserted: 1, duplicate: 0, conflict: 0});
}
function step(t: TestContext, number: number, actual: Record<string, unknown>): void {
  t.diagnostic(JSON.stringify({case_id: caseId, kind: 'step', step: number, actual}));
}
function ids(rows: Array<{sourceEventKey: string}>): string[] {
  return rows.map(row => {
    const matching = [...fixture.events, fixture.concurrent_new_event].find(
      (candidate: SeedEvent) => labelKey(candidate) === row.sourceEventKey);
    assert.ok(matching);
    return matching.id;
  }).sort();
}

test('TC-TM005-CORE-05: dual-source SQLite consistent read snapshot', t => {
  const createdRoot = mkdtempSync(join(tmpdir(), 'tm005-sqlite-'));
  chmodSync(createdRoot, 0o700);
  const root = realpathSync(createdRoot);
  const owner = join(root, '.owner');
  writeFileSync(owner, caseId, {mode: 0o600});
  const path = join(root, 'usage.sqlite');
  let writer: UsageStore | undefined;
  let reader: UsageReadSnapshot | undefined;
  try {
    writer = new UsageStore(path);
    for (const row of fixture.events) seed(writer, row);
    const setup = new DatabaseSync(path);
    assert.equal(setup.prepare('PRAGMA journal_mode=WAL').get()?.journal_mode, 'wal');
    setup.close();
    assert.equal(statSync(root).mode & 0o777, 0o700);
    assert.equal(statSync(path).mode & 0o777, 0o600);

    reader = new UsageReadSnapshot(path, fixture.principal_key,
      fixture.start_utc, fixture.end_exclusive_utc);
    reader.begin();
    const initial = reader.summary() as {calls: number; inputTokens: number;
      outputTokens: number; totalTokens: number};
    assert.deepEqual({calls: initial.calls, inputTokens: initial.inputTokens,
      outputTokens: initial.outputTokens, totalTokens: initial.totalTokens},
    {calls: 2, inputTokens: 300, outputTokens: 30, totalTokens: 330});
    const physical = new DatabaseSync(path, {readOnly: true});
    const principals = physical.prepare('SELECT principal_key, COUNT(*) AS calls FROM usage_event GROUP BY principal_key ORDER BY principal_key')
      .all().map(row => ({principalKey: String(row.principal_key), calls: Number(row.calls)}));
    physical.close();
    assert.deepEqual(principals, [{principalKey: fixture.principal_key, calls: 4},
      {principalKey: fixture.other_principal_key, calls: 1}]);
    const firstIds = ids(reader.details() as Array<{sourceEventKey: string}>);
    assert.deepEqual(firstIds, fixture.first_snapshot.ids);
    step(t, 1, {fixtureSha256, physicalPrincipals: principals, firstSnapshot: initial,
      selectedIds: firstIds});

    const sources = reader.sources() as Record<string, number>;
    const models = reader.models() as Record<string, number>;
    const details = reader.details() as Array<{sourceEventKey: string}>;
    const point = reader.intervalPoint();
    assert.deepEqual(sources, fixture.first_snapshot.source_totals);
    assert.deepEqual(models, fixture.first_snapshot.model_totals);
    assert.deepEqual(ids(details), fixture.first_snapshot.ids);
    assert.deepEqual(point, {calls: 2, totalTokens: 330});
    assert.deepEqual((initial as any).cachedInput,
      {knownTokens: fixture.first_snapshot.cached_input_known_tokens,
        unknownRows: fixture.first_snapshot.cached_input_unknown_rows});
    assert.deepEqual((initial as any).cacheWriteInput, {knownTokens: 0, unknownRows: 2});
    assert.deepEqual((initial as any).reasoningOutput, {knownTokens: 2, unknownRows: 1});
    step(t, 2, {sourceTotals: sources, modelTotals: models, detailIds: ids(details),
      intervalPoint: point, cachedInput: (initial as any).cachedInput,
      cacheWriteInput: (initial as any).cacheWriteInput,
      reasoningOutput: (initial as any).reasoningOutput});

    seed(writer, fixture.concurrent_new_event);
    const oldSources = reader.sources();
    const oldModels = reader.models();
    const oldIds = ids(reader.details() as Array<{sourceEventKey: string}>);
    const oldPoint = reader.intervalPoint();
    assert.deepEqual(oldSources, fixture.first_snapshot.source_totals);
    assert.deepEqual(oldModels, fixture.first_snapshot.model_totals);
    assert.deepEqual(oldIds, fixture.first_snapshot.ids);
    assert.deepEqual(oldPoint, {calls: 2, totalTokens: 330});
    reader.end();
    reader.begin();
    const next = reader.summary() as {calls: number; inputTokens: number;
      outputTokens: number; totalTokens: number};
    assert.deepEqual({calls: next.calls, inputTokens: next.inputTokens,
      outputTokens: next.outputTokens, totalTokens: next.totalTokens},
    {calls: fixture.next_snapshot.calls, inputTokens: fixture.next_snapshot.input_tokens,
      outputTokens: fixture.next_snapshot.output_tokens,
      totalTokens: fixture.next_snapshot.total_tokens});
    const nextIds = ids(reader.details() as Array<{sourceEventKey: string}>);
    const nextSources = reader.sources();
    assert.deepEqual(nextIds, fixture.next_snapshot.ids);
    assert.deepEqual(nextSources, fixture.next_snapshot.source_totals);
    step(t, 3, {oldSources, oldModels, oldIds, oldPoint, nextSnapshot: next,
      nextIds, nextSources});

    const empty = reader.emptyDayState('2026-09-30T16:00:00Z', '2026-10-01T16:00:00Z');
    assert.deepEqual(empty, {status: 'missing', knownTokens: 0, totalTokens: null});
    const serialized = JSON.stringify({initial, sources, models, details, point, next, empty});
    for (const rawId of fixture.events.map((row: SeedEvent) => row.canonical_call_id))
      assert.equal(serialized.includes(rawId), false);
    assert.equal(serialized.includes(fixture.secret_hex), false);
    assert.equal(serialized.includes(root), false);
    const physicalAfter = new DatabaseSync(path, {readOnly: true});
    const coverageRows = physicalAfter.prepare('SELECT COUNT(*) AS n FROM coverage').get();
    const totalRows = physicalAfter.prepare('SELECT COUNT(*) AS n FROM usage_event').get();
    physicalAfter.close();
    assert.equal(Number(coverageRows?.n), 3);
    assert.equal(Number(totalRows?.n), 6);
    step(t, 4, {emptyDay: empty, coverageRows: Number(coverageRows?.n),
      usageRows: Number(totalRows?.n), privateOutput: true});
  } finally {
    try { reader?.close(); } finally { writer?.close(); }
    assert.equal(readFileSync(owner, 'utf8'), caseId);
    rmSync(root, {recursive: true, force: false});
    assert.equal(existsSync(root), false);
    t.diagnostic(JSON.stringify({case_id: caseId, kind: 'cleanup', owned_root_removed: true}));
  }
});
