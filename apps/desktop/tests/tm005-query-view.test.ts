import {test} from 'node:test';
import type {TestContext} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {chmodSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {fileURLToPath} from 'node:url';
import {UsageStore} from '../src/main/collection/usage-store.ts';
import {sourceEventKey} from '../src/main/collection/usage-identity.ts';
import {UsageQueryView} from '../src/main/collection/usage-query-view.ts';

const caseId = 'TC-TM005-CORE-06';
function fixedFixture(name: string, expectedSha: string): any {
  const bytes = readFileSync(fileURLToPath(new URL(`../../../tests/fixtures/${name}`, import.meta.url)));
  assert.equal(createHash('sha256').update(bytes).digest('hex'), expectedSha);
  return JSON.parse(bytes.toString('utf8'));
}
const fixture = fixedFixture('tm005-query-view-slice.json',
  'aa0a16255152d04510c076f5b0eeab34195869c8f7a2873953d208bf1454df41');
const base = fixedFixture('tm005-sqlite-snapshot-slice.json', fixture.base_fixture_sha256);
assert.equal(fixture.fixture_id, 'tm005-query-view-v1');

function seed(store: UsageStore, row: any): void {
  const spec = base.seed_contract;
  const result = store.commitBatch({
    principalKey: row.principal === 'selected' ? base.principal_key : base.other_principal_key,
    secret: Buffer.from(base.secret_hex, 'hex'), source: row.source,
    sourceKey: spec.source_key[row.source], rootKey: spec.root_key[row.source],
    fileIdentity: spec.file_identity[row.source], committedByteOffset: spec.committed_byte_offset,
    prefixMac: spec.prefix_mac, diagnostics: [],
    coverage: {missingBefore: spec.coverage.missing_before,
      scanIncomplete: spec.coverage.scan_incomplete},
    events: [{source: row.source, providerCallScope: spec.provider_call_scope[row.source],
      canonicalCallId: row.canonical_call_id, sessionId: spec.session_id, turnId: spec.turn_id,
      occurredAtUtc: row.occurred_at_utc, sourceVersion: spec.source_version[row.source],
      modelId: row.model_id, usage: {inputTokens: row.input_tokens,
        outputTokens: row.output_tokens, totalTokens: row.input_tokens + row.output_tokens,
        cachedInputTokens: row.cached_input_tokens,
        cacheWriteInputTokens: row.cache_write_input_tokens,
        reasoningOutputTokens: row.reasoning_output_tokens}}],
  });
  assert.deepEqual(result, {inserted: 1, duplicate: 0, conflict: 0});
}
function ids(details: Array<{sourceEventKey: string}>): string[] {
  const candidates = [...base.events, base.concurrent_new_event, ...fixture.collision_additions];
  return details.map(detail => {
    const row = candidates.find(row => sourceEventKey(Buffer.from(base.secret_hex, 'hex'),
      row.source, base.seed_contract.provider_call_scope[row.source], row.canonical_call_id) ===
      detail.sourceEventKey);
    assert.ok(row);
    return row.id;
  }).sort();
}
function step(t: TestContext, index: number, actual: Record<string, unknown>): void {
  t.diagnostic(JSON.stringify({case_id: caseId, kind: 'step', step: index, actual}));
}
function ownedStore(t: TestContext, label: string, cleanup: {count: number}):
    {root: string; path: string; store: UsageStore} {
  const created = mkdtempSync(join(tmpdir(), `tm005-query-${label}-`));
  chmodSync(created, 0o700);
  const root = realpathSync(created);
  writeFileSync(join(root, '.owner'), caseId, {mode: 0o600});
  const path = join(root, 'usage.sqlite');
  const store = new UsageStore(path);
  for (const row of base.events) seed(store, row);
  const wal = new DatabaseSync(path);
  assert.equal(wal.prepare('PRAGMA journal_mode=WAL').get()?.journal_mode, 'wal');
  wal.close();
  t.after(() => {
    store.close();
    assert.equal(readFileSync(join(root, '.owner'), 'utf8'), caseId);
    rmSync(root, {recursive: true, force: false});
    assert.equal(existsSync(root), false);
    cleanup.count++;
    if (cleanup.count === 2)
      t.diagnostic(JSON.stringify({case_id: caseId, kind: 'cleanup', owned_root_removed: true}));
  });
  return {root, path, store};
}

test('TC-TM005-CORE-06: dual-source same-snapshot query view', t => {
  const cleanup = {count: 0};
  const main = ownedStore(t, 'main', cleanup);
  const collision = ownedStore(t, 'models', cleanup);
  const before = new DatabaseSync(main.path, {readOnly: true});
  const physical = before.prepare('SELECT principal_key, COUNT(*) AS n FROM usage_event GROUP BY principal_key ORDER BY principal_key')
    .all().map(row => ({principal: row.principal_key, count: row.n}));
  const changesBefore = Number(before.prepare('PRAGMA data_version').get()?.data_version);
  before.close();
  assert.deepEqual(physical, [{principal: base.principal_key, count: 4},
    {principal: base.other_principal_key, count: 1}]);
  const query = new UsageQueryView(main.path, base.principal_key, fixture.timezone,
    fixture.selected_local_day);
  try {
    query.begin();
    const first = query.read();
    assert.deepEqual(ids(first.details), fixture.base_expected.ids);
    assert.deepEqual(first.summary, {calls: 2, inputTokens: 300, outputTokens: 30,
      knownTokens: 330, totalTokens: null, state: 'partial',
      cachedInput: {knownTokens: 20, unknownRows: 1},
      cacheWriteInput: {knownTokens: 0, unknownRows: 2},
      reasoningOutput: {knownTokens: 2, unknownRows: 1}});
    assert.deepEqual(first.sources, fixture.base_expected.sources.map((x: any) =>
      ({source: x.source, knownTokens: x.known_tokens})));
    step(t, 1, {physical, ids: ids(first.details), summary: first.summary,
      sources: first.sources, changesBefore});

    assert.deepEqual(first.models, fixture.base_expected.models.map((x: any) =>
      ({modelId: x.model_id, knownTokens: x.known_tokens})));
    assert.deepEqual(first.trend, fixture.base_expected.trend.map((x: any) =>
      ({localDay: x.local_day, state: x.state, knownTokens: x.known_tokens,
        totalTokens: x.total_tokens})));
    assert.deepEqual(first.details.map((x: any) => Object.keys(x).sort()),
      [['inputTokens', 'modelId', 'occurredAtUtc', 'outputTokens', 'source', 'sourceEventKey'],
        ['inputTokens', 'modelId', 'occurredAtUtc', 'outputTokens', 'source', 'sourceEventKey']]);
    const serialized = JSON.stringify(first);
    for (const row of base.events)
      assert.equal(serialized.includes(row.canonical_call_id), false);
    assert.equal(serialized.includes(base.secret_hex), false);
    assert.equal(serialized.includes(main.root), false);
    step(t, 2, {models: first.models, trend: first.trend,
      cachedInput: first.summary.cachedInput, cacheWriteInput: first.summary.cacheWriteInput,
      reasoningOutput: first.summary.reasoningOutput, privateOutput: true});

    seed(main.store, base.concurrent_new_event);
    const old = query.read();
    assert.deepEqual(ids(old.details), fixture.concurrent_expected.first_snapshot_ids);
    assert.equal(old.summary.knownTokens, fixture.concurrent_expected.first_known_tokens);
    assert.deepEqual(old, first);
    query.end();
    query.begin();
    const next = query.read();
    assert.deepEqual(ids(next.details), fixture.concurrent_expected.next_snapshot_ids);
    assert.deepEqual({calls: next.summary.calls, inputTokens: next.summary.inputTokens,
      outputTokens: next.summary.outputTokens, knownTokens: next.summary.knownTokens,
      totalTokens: next.summary.totalTokens, state: next.summary.state},
    {calls: 3, inputTokens: 350, outputTokens: 35, knownTokens: 385,
      totalTokens: null, state: 'partial'});
    assert.deepEqual(next.sources, [{source: 'codex', knownTokens: 165},
      {source: 'claude_code', knownTokens: 220}]);
    step(t, 3, {oldIds: ids(old.details), oldKnown: old.summary.knownTokens,
      nextIds: ids(next.details), nextSummary: next.summary, nextSources: next.sources});
  } finally { query.close(); }

  seed(collision.store, fixture.collision_additions[0]);
  seed(collision.store, fixture.collision_additions[1]);
  const modelQuery = new UsageQueryView(collision.path, base.principal_key, fixture.timezone,
    fixture.selected_local_day);
  try {
    modelQuery.begin();
    const view = modelQuery.read();
    assert.deepEqual(ids(view.details), fixture.collision_expected.ids);
    assert.deepEqual({calls: view.summary.calls, inputTokens: view.summary.inputTokens,
      outputTokens: view.summary.outputTokens, knownTokens: view.summary.knownTokens,
      totalTokens: view.summary.totalTokens, state: view.summary.state},
    {calls: 4, inputTokens: 370, outputTokens: 37, knownTokens: 407,
      totalTokens: null, state: 'partial'});
    assert.deepEqual(view.sources, fixture.collision_expected.sources.map((x: any) =>
      ({source: x.source, knownTokens: x.known_tokens})));
    assert.deepEqual(view.models, fixture.collision_expected.models.map((x: any) =>
      ({modelId: x.model_id, knownTokens: x.known_tokens})));
    step(t, 4, {ids: ids(view.details), summary: view.summary,
      sources: view.sources, models: view.models});
  } finally { modelQuery.close(); }

  const emptyQuery = new UsageQueryView(collision.path, base.principal_key, fixture.timezone,
    fixture.empty_day.local_day);
  try {
    emptyQuery.begin();
    const empty = emptyQuery.read();
    assert.deepEqual(empty.summary, {calls: 0, inputTokens: 0, outputTokens: 0,
      knownTokens: 0, totalTokens: null, state: 'missing',
      cachedInput: {knownTokens: 0, unknownRows: 0},
      cacheWriteInput: {knownTokens: 0, unknownRows: 0},
      reasoningOutput: {knownTokens: 0, unknownRows: 0}});
    assert.deepEqual(empty.details, []);
    assert.deepEqual(empty.trend, [{localDay: fixture.empty_day.local_day,
      state: 'missing', knownTokens: 0, totalTokens: null}]);
    const check = new DatabaseSync(collision.path, {readOnly: true});
    const rows = Number(check.prepare('SELECT COUNT(*) AS n FROM usage_event').get()?.n);
    check.close();
    assert.equal(rows, 7);
    step(t, 5, {emptySummary: empty.summary, rows, readOnly: true,
      ownedRoots: 2, privacy: true});
  } finally { emptyQuery.close(); }
});
