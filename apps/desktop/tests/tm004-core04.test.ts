import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {triggerClaudeCollection, type ClaudeTriggerAccount,
  type ClaudeTriggerPorts} from '../src/main/collection/claude-trigger.ts';

const CASE = 'TC-TM004-CORE-04';
const raw = readFileSync(join(import.meta.dirname, '../../../tests/fixtures/tm004-trigger-core-slice.json'));
assert.equal(createHash('sha256').update(raw).digest('hex'),
  'c8402563de1307dc644c6d91eefe5c9e0284700bbadbdd56d0196a951d17405b');
const fixture = JSON.parse(raw.toString('utf8')) as {
  source_id: string; account: {principal_key: string; verified: boolean; active: boolean;
    must_change_password: boolean};
  expected_errors: Record<string, string>;
  expected_success_result: unknown;
  synthetic_private_sentinels: string[];
};
const secret = Buffer.alloc(32, 0x42);
const scanId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const token = 'b'.repeat(32);
const digest = 'c'.repeat(64);
const row = Buffer.from(JSON.stringify({type: 'assistant', version: '2.1.126',
  uuid: 'synthetic-row-m', sessionId: 'synthetic-session-m', isSidechain: false,
  timestamp: '2026-10-01T00:00:00Z', message: {role: 'assistant', id: 'synthetic-call-m',
    model: 'claude-sonnet-4-6', content: fixture.synthetic_private_sentinels[0],
    usage: {input_tokens: 100, output_tokens: 10}},
  localPath: fixture.synthetic_private_sentinels[2], key: fixture.synthetic_private_sentinels[1]}) + '\n');
type Trace = {begin: number; guard: number; cancel: number; commit: number};

function fake(barrier = false): {ports: ClaudeTriggerPorts; trace: Trace;
  setAccount(value: ClaudeTriggerAccount): void; revoke(): void;
  began: Promise<void>; release(): void} {
  let account: ClaudeTriggerAccount = {principalKey: fixture.account.principal_key, epoch: 1,
    verified: fixture.account.verified, active: fixture.account.active,
    mustChangePassword: fixture.account.must_change_password};
  let owned = true;
  let opened = false;
  let release!: () => void;
  let signalBegan!: () => void;
  const resumed = new Promise<void>(resolve => { release = resolve; });
  const began = new Promise<void>(resolve => { signalBegan = resolve; });
  const trace = {begin: 0, guard: 0, cancel: 0, commit: 0};
  const ports: ClaudeTriggerPorts = {
    account: () => account,
    sourceFor: principal => owned && principal === fixture.account.principal_key ? fixture.source_id : null,
    secret,
    loadCursor: async () => null,
    commitSync(batch, guard) {
      trace.commit++;
      guard();
      assert.equal(batch.events.length, 1);
      assert.equal(batch.events[0].usage.inputTokens, 100);
      assert.equal(batch.events[0].usage.outputTokens, 10);
      assert.equal(batch.cursors.length, 1);
    },
    access: {
      async beginCandidateScan(sourceId) {
        trace.begin++;
        assert.equal(sourceId, fixture.source_id);
        signalBegan();
        return {scanId, complete: true, candidates: [{relativeName: 'synthetic.jsonl',
          size: row.length, candidateToken: token, fileIdentityDigest: digest}]};
      },
      async nextCandidatePage() { throw new Error('unexpected_page'); },
      async readCandidateChunk(value, candidateToken, offset, maxBytes) {
        assert.equal(value, scanId);
        assert.equal(candidateToken, token);
        if (barrier && !opened) { opened = true; await resumed; }
        return row.subarray(offset, offset + maxBytes);
      },
      async commitGuard(value) {
        trace.guard++;
        assert.equal(value, scanId);
        if (!owned) throw new Error('source_operation_stale');
        return () => { if (!owned) throw new Error('source_operation_stale'); };
      },
      async cancelScan(value) { trace.cancel++; assert.equal(value, scanId); },
    },
  };
  return {ports, trace, setAccount(value) { account = value; }, revoke() { owned = false; },
    began, release};
}

async function rejected(request: unknown, setup: (state: ReturnType<typeof fake>) => void,
                        code: string, signal?: AbortSignal): Promise<void> {
  const state = fake();
  setup(state);
  await assert.rejects(triggerClaudeCollection(request, state.ports, signal),
    error => error instanceof Error && error.message === code);
  assert.equal(state.trace.begin, 0);
  assert.equal(state.trace.commit, 0);
}

test(`${CASE} authorized main-process trigger and transaction barrier`, async t => {
  const request = {sourceId: fixture.source_id};
  await rejected({...request, rootPath: '/synthetic/forbidden'}, () => {},
    fixture.expected_errors.extra_path_field);
  await rejected({...request, relativeName: '../forbidden.jsonl'}, () => {},
    fixture.expected_errors.extra_path_field);
  await rejected({sourceId: 'not-a-uuid'}, () => {}, fixture.expected_errors.malformed_source_id);
  for (const [stateName, change] of [
    ['unverified_account', {verified: false}], ['disabled_account', {active: false}],
    ['must_change_password', {mustChangePassword: true}],
  ] as const) {
    await rejected(request, state => state.setAccount({...state.ports.account()!, ...change}),
      fixture.expected_errors[stateName]);
  }
  await rejected({sourceId: '99999999-2222-4333-8444-555555555555'}, () => {},
    fixture.expected_errors.foreign_source_id);
  const preCancelled = new AbortController(); preCancelled.abort();
  await rejected(request, () => {}, fixture.expected_errors.cancel_before_scan, preCancelled.signal);
  t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 1,
    actual: {variants: 8, begin_candidate_scan: 0, commit_sync: 0}}));

  for (const [event, code] of [
    ['account_switch', fixture.expected_errors.account_switch_during_scan],
    ['authorization_revoked', fixture.expected_errors.authorization_revoked_during_scan],
    ['cancel_requested', fixture.expected_errors.cancel_during_scan],
  ] as const) {
    const state = fake(true);
    const controller = new AbortController();
    const running = triggerClaudeCollection(request, state.ports, controller.signal);
    await state.began;
    if (event === 'account_switch') state.setAccount({...state.ports.account()!,
      principalKey: 'synthetic-principal-b', epoch: 2});
    else if (event === 'authorization_revoked') state.revoke();
    else controller.abort();
    state.release();
    await assert.rejects(running, error => error instanceof Error && error.message === code);
    assert.equal(state.trace.begin, 1);
    assert.equal(state.trace.cancel, 1);
    assert.equal(state.trace.commit, 0);
  }
  t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 2,
    actual: {barrier_events: 3, cancel_scan_each: 1, commit_sync_each: 0}}));

  const healthy = fake();
  const result = await triggerClaudeCollection(request, healthy.ports);
  assert.deepEqual(result, fixture.expected_success_result);
  assert.deepEqual(healthy.trace, {begin: 1, guard: 1, cancel: 1, commit: 1});
  const output = JSON.stringify(result);
  for (const sentinel of [...fixture.synthetic_private_sentinels,
    'synthetic-session-m', 'synthetic-call-m', 'synthetic-row-m'])
    assert.equal(output.includes(sentinel), false);
  assert.deepEqual(result.diagnostics, []);
  t.diagnostic(JSON.stringify({kind: 'step', case_id: CASE, step: 3,
    actual: {summary: result.summary, diagnostics: result.diagnostics, commit_sync: healthy.trace.commit,
      private_sentinels_in_return: false}}));
  t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: CASE, memory_reset_complete: true}));
});
