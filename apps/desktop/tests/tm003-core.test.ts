import { test } from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync, appendFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { scanCodexFile } from '../src/main/collection/codex-format.ts';
import { sourceEventKey } from '../src/main/collection/usage-identity.ts';
import { UsageStore } from '../src/main/collection/usage-store.ts';

const T0 = '2026-10-01T06:00:00Z';
const VERSION = '0.158.0-alpha.2.1';
const TEST_SECRET = Buffer.from('000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f', 'hex');
const PRINCIPAL = 'a'.repeat(64);

type Json = Record<string, unknown>;
function line(value: Json): Buffer { return Buffer.from(JSON.stringify(value) + '\n', 'utf8'); }
function metadata(version = VERSION): Buffer {
  return line({timestamp: T0, type: 'session_meta', payload: {id: 'tm003-core-session', cli_version: version}});
}
function usage(id: string, input: number, output: number, cached: number, overrides: Json = {}): Buffer {
  return line({timestamp: T0, type: 'token_usage_record', payload: {
    response_id: id,
    session_id: 'tm003-core-session',
    turn_id: 'tm003-core-turn',
    usage: {input_tokens: input, output_tokens: output, cached_input_tokens: cached,
      cache_write_input_tokens: 0, reasoning_output_tokens: 0, total_tokens: input + output},
    ...overrides,
    turn_token_usage: {input_tokens: input, output_tokens: output, total_tokens: input + output},
    thread_token_usage: {input_tokens: input, output_tokens: output, total_tokens: input + output},
  }});
}
function cumulative(info: Json | null): Buffer {
  return line({timestamp: T0, type: 'event_msg', payload: {type: 'token_count', info, rate_limits: null}});
}
function ownedRoot(): string {
  const root = mkdtempSync(join(tmpdir(), 'tm003-core-'));
  chmodSync(root, 0o700);
  return realpathSync(root);
}
function numbers(events: Array<{usage: {inputTokens: number; outputTokens: number; cachedInputTokens: number | null}}>) {
  return {
    count: events.length,
    input: events.reduce((sum, event) => sum + event.usage.inputTokens, 0),
    output: events.reduce((sum, event) => sum + event.usage.outputTokens, 0),
    cached: events.reduce((sum, event) => sum + (event.usage.cachedInputTokens ?? 0), 0),
  };
}

test('TC-TM003-CORE-01 complete LF lines advance the byte cursor without adding cumulative snapshots', () => {
  const root = ownedRoot(); const file = join(root, 'rollout.jsonl');
  try {
    const first = Buffer.concat([metadata(), usage('response-A', 100, 10, 20)]);
    writeFileSync(file, first, {mode: 0o600});
    const stage1 = scanCodexFile(readFileSync(file), 0);
    assert.deepEqual(numbers(stage1.events), {count: 1, input: 100, output: 10, cached: 20});
    assert.equal(stage1.committedByteOffset, first.length);

    const second = usage('response-B', 200, 20, 40);
    const half = Math.floor(second.length / 2);
    appendFileSync(file, second.subarray(0, half));
    const stage2 = scanCodexFile(readFileSync(file), stage1.committedByteOffset);
    assert.deepEqual(stage2.events, []);
    assert.equal(stage2.committedByteOffset, first.length);

    const third = usage('response-C', 300, 30, 60);
    const snapshot = cumulative({total_token_usage: {input_tokens: 600, output_tokens: 60, total_tokens: 660}});
    appendFileSync(file, Buffer.concat([second.subarray(half), third, snapshot]));
    const complete = readFileSync(file);
    const stage3 = scanCodexFile(complete, stage2.committedByteOffset);
    assert.deepEqual(numbers([...stage1.events, ...stage3.events]), {count: 3, input: 600, output: 60, cached: 120});
    assert.equal(stage3.committedByteOffset, complete.length);
    const rescan = scanCodexFile(complete, stage3.committedByteOffset);
    assert.deepEqual(rescan.events, []);
    assert.equal(rescan.committedByteOffset, complete.length);
    assert.equal(statSync(file).mode & 0o777, 0o600);
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM003-CORE-02 cumulative, missing and invalid usage stay diagnostic', () => {
  const root = ownedRoot(); const file = join(root, 'rollout.jsonl');
  try {
    const stage1Bytes = Buffer.concat([metadata(),
      cumulative({total_token_usage: {input_tokens: 100, output_tokens: 10, total_tokens: 110}}),
      cumulative(null)]);
    writeFileSync(file, stage1Bytes, {mode: 0o600});
    const stage1 = scanCodexFile(readFileSync(file), 0);
    assert.deepEqual(stage1.events, []);
    assert.deepEqual(stage1.diagnostics.map(item => item.code), ['unverified_cumulative', 'missing_usage']);

    const valid = usage('valid-A', 100, 10, 20);
    const missing = usage('missing', 100, 10, 20, {usage: undefined});
    const negative = usage('negative', -1, 10, 0);
    const badCache = usage('bad-cache', 100, 10, 111);
    const badTotal = usage('bad-total', 100, 10, 20, {usage: {
      input_tokens: 100, output_tokens: 10, cached_input_tokens: 20, total_tokens: 111,
    }});
    appendFileSync(file, Buffer.concat([valid, missing, negative, badCache, badTotal]));
    const stage2 = scanCodexFile(readFileSync(file), stage1.committedByteOffset);
    assert.deepEqual(numbers(stage2.events), {count: 1, input: 100, output: 10, cached: 20});
    assert.deepEqual(stage2.diagnostics.map(item => item.code),
      ['missing_usage', 'negative_input', 'invalid_cached', 'invalid_total']);

    const unsupported = Buffer.concat([metadata('0.999.0-unknown'), usage('unsupported', 100, 10, 20)]);
    const stage3 = scanCodexFile(unsupported, 0);
    assert.deepEqual(stage3.events, []);
    assert.deepEqual(stage3.diagnostics.map(item => item.code), ['unsupported_source_version']);
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM003-CORE-03 identity v1 and SQLite preserve first event across replay and conflict', () => {
  const root = ownedRoot(); const database = join(root, 'usage.sqlite');
  try {
    const key = sourceEventKey(TEST_SECRET, 'codex', 'provider-response', 'shared-call-01');
    assert.equal(key, 'afd67bd0cad0227b3e7b5ac132bb9b3ed492073983b9c16a0c9cc24dd3008051');
    assert.equal(sourceEventKey(TEST_SECRET, 'claude_code', 'provider-message', 'shared-call-01'),
      'bf222a85ab2209f72ff82c21b7172c9315448b3e1d5bf4503a3c76b30c46cad1');
    const store = new UsageStore(database);
    try {
      function event(id: string, input: number, output: number) {
        const parsed = scanCodexFile(Buffer.concat([metadata(), usage(id, input, output, 20)]), 0);
        assert.equal(parsed.events.length, 1);
        return parsed.events[0];
      }
      assert.equal(store.record(PRINCIPAL, TEST_SECRET, event('shared-call-01', 100, 10)), 'inserted');
      assert.deepEqual(store.summary(PRINCIPAL), {count: 1, input: 100, output: 10, cached: 20, total: 110});
      assert.equal(store.record(PRINCIPAL, TEST_SECRET, event('shared-call-01', 100, 10)), 'duplicate');
      assert.equal(store.record(PRINCIPAL, TEST_SECRET, event('shared-call-02', 100, 10)), 'inserted');
      assert.deepEqual(store.summary(PRINCIPAL), {count: 2, input: 200, output: 20, cached: 40, total: 220});
      assert.equal(store.record(PRINCIPAL, TEST_SECRET, event('shared-call-01', 999, 99)), 'conflict');
      assert.deepEqual(store.summary(PRINCIPAL), {count: 2, input: 200, output: 20, cached: 40, total: 220});
      assert.deepEqual(store.diagnostics(PRINCIPAL), [{code: 'identity_conflict', count: 1}]);
    } finally { store.close(); }
    const readonly = new DatabaseSync(database, {readOnly: true});
    try {
      assert.deepEqual(readonly.prepare('SELECT source_event_key FROM usage_event ORDER BY source_event_key').all()
        .map(row => row.source_event_key).includes(key), true);
      assert.equal(readonly.prepare('SELECT COUNT(*) AS n FROM usage_event').get()?.n, 2);
      assert.equal(readonly.prepare('SELECT COUNT(*) AS n FROM collection_diagnostic WHERE code = ?').get('identity_conflict')?.n, 1);
    } finally { readonly.close(); }
    assert.equal(readFileSync(database).includes(Buffer.from('shared-call-01')), false);
    assert.equal(statSync(database).mode & 0o777, 0o600);
  } finally { rmSync(root, {recursive: true, force: true}); }
});
