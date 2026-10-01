import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { collectClaudeJsonl } from '../src/main/collection/claude-format.ts';

const fixtureRoot = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../../tests/fixtures/tm004/native-2.1.126-projection');
const fixture = (name: string): string => readFileSync(resolve(fixtureRoot, name), 'utf8');
const assistant = (name: string): Record<string, unknown> => fixture(name).split('\n').filter(Boolean)
  .map(line => JSON.parse(line) as Record<string, unknown>).find(row => row.type === 'assistant')!;
const counts = (data: ReturnType<typeof collectClaudeJsonl>, code: string): number =>
  data.diagnostics.filter(item => item.code === code).length;

test('TC-TM004-PARSER-03: native two-block message and Agent summary each count once', () => {
  const twoBlocks = collectClaudeJsonl([fixture('raw-multiblock.jsonl')]);
  assert.deepEqual(twoBlocks.totals, {calls: 1, inputTokens: 31, outputTokens: 9, totalTokens: 40});
  assert.equal(twoBlocks.diagnostics.length, 0);
  const agent = collectClaudeJsonl([fixture('raw-agent-parent.jsonl'), fixture('raw-agent-sub.jsonl')]);
  assert.deepEqual(agent.totals, {calls: 3, inputTokens: 59, outputTokens: 18, totalTokens: 77});
  assert.equal(agent.calls.filter(call => call.isSidechain).length, 1);
  assert.equal(agent.calls.find(call => call.isSidechain)?.attribution, 'parent_verified');
  assert.equal(agent.diagnostics.length, 0);
});

test('TC-TM004-LINEAGE-02 supported variant: native copied fork retains one original call', () => {
  const observed = collectClaudeJsonl([fixture('raw-main.jsonl'), fixture('raw-fork.jsonl')]);
  assert.deepEqual(observed.totals, {calls: 2, inputTokens: 26, outputTokens: 14, totalTokens: 40});
  assert.equal(observed.diagnostics.length, 0);
});

test('TC-TM004-DIAG-01 supported boundary: native 0/0 remains unknown', () => {
  const zero = collectClaudeJsonl([fixture('raw-missing-usage.jsonl')]);
  assert.deepEqual(zero.totals, {calls: 0, inputTokens: 0, outputTokens: 0, totalTokens: 0});
  assert.equal(counts(zero, 'ambiguous_zero'), 1);
  assert.equal(zero.calls.length, 0);
});

test('TC-TM004-PARSER-02 fault injection: missing usage and unknown version are diagnostics', () => {
  const missing = assistant('raw-main.jsonl');
  delete (missing.message as Record<string, unknown>).usage;
  const version = structuredClone(assistant('raw-main.jsonl'));
  version.version = '2.1.127';
  const observed = collectClaudeJsonl([`${JSON.stringify(missing)}\n${JSON.stringify(version)}\n`]);
  assert.equal(observed.totals.calls, 0);
  assert.equal(counts(observed, 'missing_usage'), 1);
  assert.equal(counts(observed, 'unsupported_version'), 1);
});

test('TC-TM004-LINEAGE-05 fault injection: ambiguous reuse and conflict retain first trusted event', () => {
  const original = assistant('raw-main.jsonl');
  const uncertain = structuredClone(original);
  uncertain.sessionId = 'synthetic-other-session'; uncertain.uuid = 'synthetic-other-uuid';
  const conflict = structuredClone(original);
  conflict.uuid = 'synthetic-conflict-uuid';
  (conflict.message as {usage: {input_tokens: number}}).usage.input_tokens = 14;
  const observed = collectClaudeJsonl([`${JSON.stringify(original)}\n${JSON.stringify(uncertain)}\n${JSON.stringify(conflict)}\n`]);
  assert.deepEqual(observed.totals, {calls: 1, inputTokens: 13, outputTokens: 7, totalTokens: 20});
  assert.equal(counts(observed, 'unverified_inheritance'), 1);
  assert.equal(counts(observed, 'identity_conflict'), 1);
});

test('TC-TM004-LINEAGE-01: orphan sidechain keeps usage but has unknown parent', () => {
  const orphan = collectClaudeJsonl([fixture('raw-agent-sub.jsonl')]);
  assert.deepEqual(orphan.totals, {calls: 1, inputTokens: 19, outputTokens: 6, totalTokens: 25});
  assert.equal(orphan.calls[0].attribution, 'unverified_parent');
  assert.equal(counts(orphan, 'unverified_parent'), 1);
});

test('TC-TM004-LINEAGE-01 fault injection: an unknown-version parent summary cannot verify attribution', () => {
  const parent = fixture('raw-agent-parent.jsonl').split('\n').filter(Boolean)
    .map(line => JSON.parse(line) as Record<string, unknown>);
  const summary = parent.find(row => row.type === 'user' && row.toolUseResult);
  assert.ok(summary);
  summary.version = '2.1.127';
  const observed = collectClaudeJsonl([`${parent.map(row => JSON.stringify(row)).join('\n')}\n`,
                                       fixture('raw-agent-sub.jsonl')]);
  assert.equal(observed.calls.find(call => call.isSidechain)?.attribution, 'unverified_parent');
  assert.equal(counts(observed, 'unverified_parent'), 1);
});

test('TC-TM004-INCREMENTAL-01 parser boundary: complete LF only, malformed lines diagnosed', () => {
  const row = assistant('raw-main.jsonl');
  const whole = JSON.stringify(row);
  const partial = collectClaudeJsonl([whole]);
  assert.equal(partial.totals.calls, 0);
  assert.equal(counts(partial, 'incomplete_tail'), 1);
  const complete = collectClaudeJsonl([`${whole}\n`]);
  assert.equal(complete.totals.totalTokens, 20);
  const invalid = collectClaudeJsonl(['{bad-json}\n']);
  assert.equal(counts(invalid, 'invalid_json'), 1);
});

test('TC-TM004-PARSER-02 fault injection: invalid UTC date and ill-formed call ID are rejected', () => {
  const impossibleDate = assistant('raw-main.jsonl');
  impossibleDate.timestamp = '2026-02-30T01:02:03Z';
  const illFormedId = structuredClone(assistant('raw-main.jsonl'));
  (illFormedId.message as Record<string, unknown>).id = 'msg-\ud800';
  const observed = collectClaudeJsonl([`${JSON.stringify(impossibleDate)}\n${JSON.stringify(illFormedId)}\n`]);
  assert.equal(observed.totals.calls, 0);
  assert.equal(counts(observed, 'invalid_timestamp'), 1);
  assert.equal(counts(observed, 'invalid_structure'), 1);
});

test('TC-TM004-LINEAGE-01 fault injection: missing sidechain marker cannot imply main attribution', () => {
  const row = assistant('raw-agent-sub.jsonl');
  delete row.isSidechain;
  const observed = collectClaudeJsonl([`${JSON.stringify(row)}\n`]);
  assert.equal(observed.totals.calls, 0);
  assert.equal(counts(observed, 'invalid_structure'), 1);
});

test('TC-TM004-DIAG-02 parser privacy: prompt, reply and path do not enter results', () => {
  const row = assistant('raw-main.jsonl');
  row.cwd = '/synthetic/private/project-sentinel';
  (row.message as Record<string, unknown>).content = [{type: 'text', text: 'private-prompt-reply-sentinel'}];
  const observed = collectClaudeJsonl([`${JSON.stringify(row)}\n`]);
  assert.equal(observed.totals.calls, 1);
  assert.doesNotMatch(JSON.stringify(observed), /private-prompt-reply-sentinel|project-sentinel/);
});
