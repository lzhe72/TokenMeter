import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chmodSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {openUsageProfile} from '../src/main/collection/usage-profile.ts';
import {createCollectionHandler} from '../src/main/collection/collection-ipc.ts';
import type {CodexRuntime} from '../src/main/collection/codex-runtime.ts';
import type {SourceAccess} from '../src/main/source-access.ts';

const ID = 'TC-TM003-CORE-10';
const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-product-loop-slice.json', import.meta.url), 'utf8'));
const files = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-main-collector-slice.json', import.meta.url), 'utf8')).files;
const lines = JSON.parse(readFileSync(new URL('../../../tests/fixtures/tm003-core-storage-cursor.json', import.meta.url), 'utf8')).raw_lines;
const bodies = [Buffer.from(lines.header + lines.a), Buffer.from(lines.header + lines.b)];
const source = fixture.confirmed_source_id as string, unknown = fixture.unconfirmed_source_id as string;
const url = 'tokenmeter://app/index.html';
function step(t: {diagnostic(message: string): void}, n: number, actual: object) {
  t.diagnostic(JSON.stringify({kind: 'step', case_id: ID, step: n, actual}));
}
function state(path: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try { return {events: db.prepare('SELECT principal_key, COUNT(*) n, SUM(input_tokens+output_tokens) total FROM usage_event GROUP BY principal_key').all(),
    coverage: db.prepare('SELECT principal_key, root_key, missing_before, scan_incomplete FROM coverage ORDER BY principal_key').all()}; }
  finally { db.close(); }
}

test('TC-TM003-CORE-10 main-frame collection IPC limits input and isolates state', async t => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tm003-core10-'))); chmodSync(root, 0o700);
  const profile = openUsageProfile(root, {cipher: {isEncryptionAvailable: () => true,
    encryptString: value => Buffer.from(`cipher:${value}`), decryptString: value => value.toString().slice(7)},
    randomBytes: () => Buffer.from(fixture.public_test_key_hex, 'hex')});
  const dbPath = join(root, fixture.sqlite_file);
  let active = 0; let mode: 'enabled'|'paused'|'revoked' = 'enabled';
  let sender: object = {id: 'main-1'}, frame: object = {url};
  const counters = {begin: 0, read: 0, commit: 0};
  const tokens = ['a'.repeat(32), 'b'.repeat(32)];
  const access = {
    snapshot: () => ({codex: {confirmed: active === 0 && mode !== 'revoked'
      ? {sourceId: source, status: mode === 'enabled' ? 'confirmed_enabled' : 'confirmed_paused',
        collectAllowed: mode === 'enabled', syncIntent: false} : null,
      pending: null, candidates: [], incomplete: false},
      claude_code: {confirmed: null, pending: null, candidates: [], incomplete: false}}),
    beginCandidateScan: async () => {counters.begin++; return {scanId: '33333333-4444-4555-8666-777777777777',
      candidates: [candidate(0)], complete: false};},
    nextCandidatePage: async () => ({candidates: [candidate(1)], complete: true}),
    readCandidateChunk: async (_scan: string, token: string, offset: number, max: number) => {
      counters.read++; const i = tokens.indexOf(token); assert.ok(i >= 0);
      return bodies[i].subarray(offset, offset + Math.min(max, 128));},
    commitGuard: async () => () => {if (mode !== 'enabled' || active !== 0) throw new Error('source_operation_stale');},
    cancelScan: async () => {},
  } as unknown as SourceAccess;
  function candidate(i: number) { return {candidateToken: tokens[i], relativeName: `private/file-${i}.jsonl`,
    size: 410, mtimeMs: 1760000000000, fileIdentityDigest: files[i].file_identity_digest}; }
  const runtime: CodexRuntime = {access, profile, stagingBudgetBytes: 1024,
    getIdentity: () => ({origin: fixture.identities[active].origin,
      accountId: fixture.identities[active].account_id, verified: true})};
  const original = profile.store.commitScanBatch.bind(profile.store);
  profile.store.commitScanBatch = batch => {counters.commit++; return original(batch);};
  const handler = createCollectionHandler({runtime: () => runtime, mainSender: () => sender,
    mainFrame: () => frame, mainUrl: url});
  const event = () => ({sender, senderFrame: frame as {url: string}});
  try {
    const foreign = {sender: {id: 'foreign'}, senderFrame: frame as {url: string}};
    const subframe = {sender, senderFrame: {url}};
    for (const [e, method, input] of [
      [foreign, 'collection:getState', undefined], [subframe, 'collection:getState', undefined],
      [event(), 'collection:getState', {path: '/private'}],
      [event(), 'collection:refresh', {sourceId: source, path: '/private'}],
      [event(), 'collection:refresh', {sourceId: source, accountId: 'other'}],
      [event(), 'collection:refresh', {sourceId: source, secret: 'unsafe'}],
      [event(), 'collection:refresh', {sourceId: unknown}],
    ] as Array<[ReturnType<typeof event>, string, unknown]>)
      await assert.rejects(handler(e, method, input), /ipc_sender_rejected|invalid_collection_input|source_access_denied/);
    assert.deepEqual([counters.begin, counters.read, counters.commit, state(dbPath).events.length], [0,0,0,0]);
    step(t, 1, {rejected_variants: 7, scan_calls: 0, read_calls: 0, commit_calls: 0, events: 0});

    await handler(event(), 'collection:refresh', {sourceId: source});
    const current = await handler(event(), 'collection:getState') as Record<string, any>;
    assert.deepEqual([current.usage.calls, current.usage.inputTokens, current.usage.outputTokens,
      current.usage.totalTokens, current.usage.cachedInput.knownTokens], [2,300,30,330,60]);
    assert.equal(current.coverage.complete, true); assert.equal(current.diagnostics.length, 0);
    assert.equal(state(dbPath).events.length, 1);
    const serialized = JSON.stringify(current);
    for (const forbidden of [source, fixture.public_test_key_hex, '/private', files[0].file_identity_digest,
      lines.a, 'cipher:']) assert.equal(serialized.includes(forbidden), false);
    step(t, 2, {calls: 2, input: 300, output: 30, total: 330, cached_known: 60,
      coverage_complete: true, diagnostics: 0, events: 2, private_data_absent: true});

    const beforeCoverage = state(dbPath).coverage;
    await handler(event(), 'collection:refresh', {sourceId: source});
    assert.equal((await handler(event(), 'collection:getState') as Record<string, any>).usage.totalTokens, 330);
    mode = 'paused';
    await assert.rejects(handler(event(), 'collection:refresh', {sourceId: source}), /source_access_denied/);
    const paused = await handler(event(), 'collection:getState') as Record<string, any>;
    assert.equal(paused.usage.totalTokens, 330); assert.equal(paused.status, 'unavailable');
    assert.equal(paused.coverage.complete, false);
    mode = 'revoked';
    await assert.rejects(handler(event(), 'collection:refresh', {sourceId: source}), /source_access_denied/);
    assert.deepEqual(state(dbPath).coverage, beforeCoverage);
    step(t, 3, {replay_total: 330, paused_refresh_rejected: true, revoked_refresh_rejected: true,
      old_trusted_total_visible: 330, run_status: paused.status, old_coverage_unchanged: true});

    const oldEvent = event(); active = 2; sender = {id: 'main-2'}; frame = {url};
    await assert.rejects(handler(oldEvent, 'collection:getState'), /ipc_sender_rejected/);
    await assert.rejects(handler(event(), 'collection:refresh', {sourceId: source}), /source_access_denied/);
    const second = await handler(event(), 'collection:getState') as Record<string, any>;
    assert.equal(second.status, 'unverified'); assert.equal(second.usage, null);
    assert.deepEqual([state(dbPath).events.length, Number(state(dbPath).events[0].total)], [1,330]);
    step(t, 4, {old_sender_rejected: true, old_source_rejected: true,
      second_subject_status: second.status, second_usage: null, first_subject_total_retained: 330});
  } finally { profile.close(); rmSync(root, {recursive: true, force: true}); assert.equal(existsSync(root), false);
    t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: ID, owned_root_removed: true})); }
});
