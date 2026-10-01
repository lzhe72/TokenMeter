import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash, createHmac} from 'node:crypto';
import {chmodSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync, truncateSync, utimesSync} from 'node:fs';
import {open} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {readClaudeCandidate, readClaudeFile} from '../src/main/collection/claude-reader.ts';

const CORE01 = 'TC-TM004-CORE-01';
const CORE02 = 'TC-TM004-CORE-02';
const CORE03 = 'TC-TM004-CORE-03';
const secret = Buffer.alloc(32, 0x42);
const identity = 'synthetic-file-a';
const fixture = join(import.meta.dirname, '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-main.jsonl');
const sha = (bytes: Buffer | string): string => createHash('sha256').update(bytes).digest('hex');
const mac = (bytes: Buffer | string): string => createHmac('sha256', secret).update(bytes).digest('hex');
function sourceLine(): {row: Record<string, unknown>; line: Buffer} {
  const bytes = readFileSync(fixture);
  assert.equal(sha(bytes), '2b484c185cf0ba333a85c53eb4953f13ddd2e40b6ab95167ca353a8454588ffe');
  const row = bytes.toString('utf8').split('\n').filter(Boolean).map(line => JSON.parse(line) as Record<string, unknown>)
    .find(item => item.type === 'assistant')!;
  const line = Buffer.from(JSON.stringify(row) + '\n');
  assert.equal(line.length, 746);
  assert.equal(sha(line), 'cefd7dbe966383874d5b0f587c41089ecfbd8150a980a8b9ca701e4df4c9855f');
  return {row, line};
}
function secondLine(row: Record<string, unknown>): Buffer {
  const next = structuredClone(row);
  (next.message as Record<string, unknown>).id = 'msg_tm004_synthetic_main_002';
  return Buffer.from(JSON.stringify(next) + '\n');
}
function ownedRoot(): string {
  const root = mkdtempSync(join(tmpdir(), 'tm004-core-'));
  chmodSync(root, 0o700);
  return realpathSync(root);
}
type Diagnostic = {diagnostic(message: string): void};
function step(t: Diagnostic, caseId: string, index: number, actual: Record<string, unknown>): void {
  t.diagnostic(JSON.stringify({kind: 'step', case_id: caseId, step: index, actual}));
}
function cleanup(t: Diagnostic, caseId: string, root: string): void {
  rmSync(root, {recursive: true});
  assert.equal(existsSync(root), false);
  t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: caseId, owned_root_removed: true}));
}
const codes = (items: readonly {code: string}[]): string[] => items.map(item => item.code);

test('TC-TM004-CORE-01 complete LF, half-line and bounded continuation', async t => {
  const root = ownedRoot(); const file = join(root, 'synthetic.jsonl');
  const {row, line} = sourceLine(); const next = secondLine(row);
  let handle: Awaited<ReturnType<typeof open>> | null = null;
  try {
    const half = Math.floor(line.length / 2);
    writeFileSync(file, line.subarray(0, half), {mode: 0o600});
    handle = await open(file, 'r');
    const partial = await readClaudeFile(handle, identity, null, secret);
    assert.equal(partial.calls.length, 0);
    assert.equal(partial.cursor.committedByteOffset, 0);
    assert.equal(partial.scanIncomplete, true);
    step(t, CORE01, 1, {source_bytes: half, source_sha256: sha(line.subarray(0, half)),
      calls: 0, committed_byte_offset: 0, scan_incomplete: partial.scanIncomplete});

    writeFileSync(file, line, {mode: 0o600});
    const complete = await readClaudeFile(handle, identity, partial.cursor, secret);
    assert.equal(complete.calls.length, 1);
    assert.equal(complete.calls[0].inputTokens, 13);
    assert.equal(complete.calls[0].outputTokens, 7);
    assert.equal(complete.cursor.committedByteOffset, 746);
    assert.equal(complete.cursor.prefixMac, mac(line));
    assert.equal(complete.scanIncomplete, false);
    const repeated = await readClaudeFile(handle, identity, complete.cursor, secret);
    assert.equal(repeated.calls.length, 0);
    assert.deepEqual(repeated.cursor, complete.cursor);
    step(t, CORE01, 2, {source_bytes: 746, source_sha256: sha(line), calls: 1,
      input: 13, output: 7, total: 20, committed_byte_offset: 746,
      prefix_mac: complete.cursor.prefixMac, repeated_calls: 0, scan_incomplete: false});

    writeFileSync(file, Buffer.concat([line, next]), {mode: 0o600});
    const limited = await readClaudeFile(handle, identity, null, secret, 754);
    assert.equal(limited.calls.length, 1);
    assert.equal(limited.cursor.committedByteOffset, 746);
    assert.deepEqual(codes(limited.diagnostics), ['incomplete_tail', 'read_limit']);
    assert.equal(limited.scanIncomplete, true);
    const resumed = await readClaudeFile(handle, identity, limited.cursor, secret);
    assert.deepEqual(resumed.calls.map(call => call.canonicalCallId), ['msg_tm004_synthetic_main_002']);
    assert.equal(resumed.cursor.committedByteOffset, line.length + next.length);
    assert.equal(resumed.scanIncomplete, false);
    assert.equal(statSync(file).mode & 0o777, 0o600);
    step(t, CORE01, 3, {source_bytes: line.length + next.length,
      source_sha256: sha(Buffer.concat([line, next])), first_read_limit: 754,
      first_calls: 1, first_offset: 746, first_diagnostics: codes(limited.diagnostics),
      resumed_calls: 1, resumed_offset: resumed.cursor.committedByteOffset, scan_incomplete: false});
  } finally { await handle?.close(); cleanup(t, CORE01, root); }
});

test('TC-TM004-CORE-02 keyed prefix, source changes and secret failures', async t => {
  const root = ownedRoot(); const file = join(root, 'synthetic.jsonl');
  const {row, line} = sourceLine(); const next = secondLine(row);
  writeFileSync(file, line, {mode: 0o600});
  let handle: Awaited<ReturnType<typeof open>> | null = null;
  try {
    handle = await open(file, 'r');
    const first = await readClaudeFile(handle, identity, null, secret);
    writeFileSync(file, Buffer.concat([line, next]), {mode: 0o600});
    const appended = await readClaudeFile(handle, identity, first.cursor, secret);
    assert.deepEqual(appended.calls.map(call => call.canonicalCallId), ['msg_tm004_synthetic_main_002']);
    assert.equal(appended.cursor.committedByteOffset, line.length + next.length);
    assert.equal(codes(appended.diagnostics).includes('cursor_reset'), false);
    step(t, CORE02, 1, {initial_offset: 746, initial_prefix_mac: mac(line),
      appended_bytes: next.length, resumed_calls: 1, resumed_offset: appended.cursor.committedByteOffset,
      cursor_resets: 0});

    writeFileSync(file, line, {mode: 0o600});
    const fixedTime = new Date('2026-10-01T00:00:00.000Z');
    utimesSync(file, fixedTime, fixedTime);
    const before = statSync(file);
    writeFileSync(file, next, {mode: 0o600});
    utimesSync(file, fixedTime, fixedTime);
    assert.equal(next.length, line.length);
    assert.equal(statSync(file).mtimeMs, before.mtimeMs);
    const rewritten = await readClaudeFile(handle, identity, first.cursor, secret);
    assert.equal(codes(rewritten.diagnostics).includes('cursor_reset'), true);
    assert.deepEqual(rewritten.calls.map(call => call.canonicalCallId), ['msg_tm004_synthetic_main_002']);
    writeFileSync(file, Buffer.concat([line, next]), {mode: 0o600});
    const both = await readClaudeFile(handle, identity, null, secret);
    truncateSync(file, line.length);
    const truncated = await readClaudeFile(handle, identity, both.cursor, secret);
    assert.equal(codes(truncated.diagnostics).includes('cursor_reset'), true);
    const differentIdentity = await readClaudeFile(handle, 'synthetic-file-b', first.cursor, secret);
    assert.equal(codes(differentIdentity.diagnostics).includes('cursor_reset'), true);
    step(t, CORE02, 2, {same_size: true, restored_mtime: true,
      rewrite_resets: 1, rewrite_calls: 1, truncated_resets: 1,
      truncated_offset: truncated.cursor.committedByteOffset, changed_identity_resets: 1});

    await assert.rejects(readClaudeFile(handle, identity, null, Buffer.alloc(0)), /claude_read_failed/);
    await assert.rejects(readClaudeFile(handle, identity, null, Buffer.alloc(31)), /claude_read_failed/);
    let checks = 0;
    await assert.rejects(readClaudeCandidate({fileIdentity: identity, size: line.length,
      async readAt(offset, maxBytes) { return line.subarray(offset, offset + maxBytes); },
      async assertCurrent() { if (++checks === 2) throw new Error('claude_source_changed'); },
    }, null, secret), /claude_source_changed/);
    assert.equal(checks, 2);
    step(t, CORE02, 3, {missing_secret: 'error', short_secret: 'error',
      changed_source: 'error', commit_result: 'none'});
  } finally { await handle?.close(); cleanup(t, CORE02, root); }
});

test('TC-TM004-CORE-03 invalid UTF-8 and unknown version stay diagnostic', async t => {
  const root = ownedRoot(); const file = join(root, 'synthetic.jsonl');
  const {row, line} = sourceLine();
  const unknown = structuredClone(row); unknown.version = '2.1.127';
  const all = Buffer.concat([Buffer.from([0xff, 0x0a]), Buffer.from(JSON.stringify(unknown) + '\n'), line]);
  writeFileSync(file, all, {mode: 0o600});
  let handle: Awaited<ReturnType<typeof open>> | null = null;
  try {
    handle = await open(file, 'r');
    const initial = await readClaudeFile(handle, identity, null, secret);
    assert.equal(initial.calls.length, 1);
    assert.equal(initial.calls[0].inputTokens + initial.calls[0].outputTokens, 20);
    assert.deepEqual(codes(initial.diagnostics), ['invalid_utf8', 'unsupported_version']);
    step(t, CORE03, 1, {source_bytes: all.length, source_sha256: sha(all),
      calls: 1, input: 13, output: 7, total: 20, diagnostics: codes(initial.diagnostics)});

    assert.equal(initial.cursor.committedByteOffset, all.length);
    assert.equal(initial.cursor.prefixMac, mac(all));
    assert.equal(initial.scanIncomplete, false);
    const repeated = await readClaudeFile(handle, identity, initial.cursor, secret);
    assert.equal(repeated.calls.length, 0);
    const output = JSON.stringify(initial);
    assert.equal(output.includes(file), false);
    assert.equal(output.includes(JSON.stringify(row)), false);
    assert.equal(output.includes(secret.toString('hex')), false);
    step(t, CORE03, 2, {committed_byte_offset: all.length, prefix_mac: initial.cursor.prefixMac,
      scan_incomplete: false, repeated_calls: 0, contains_path_or_raw_or_secret: false});

    writeFileSync(file, Buffer.concat([all, Buffer.from([0xff])]), {mode: 0o600});
    const partial = await readClaudeFile(handle, identity, initial.cursor, secret);
    assert.equal(partial.cursor.committedByteOffset, all.length);
    assert.equal(partial.scanIncomplete, true);
    assert.equal(codes(partial.diagnostics).includes('invalid_utf8'), false);
    writeFileSync(file, Buffer.concat([all, Buffer.from([0xff, 0x0a])]), {mode: 0o600});
    const complete = await readClaudeFile(handle, identity, partial.cursor, secret);
    assert.equal(complete.calls.length, 0);
    assert.deepEqual(codes(complete.diagnostics), ['invalid_utf8']);
    assert.equal(complete.cursor.committedByteOffset, all.length + 2);
    step(t, CORE03, 3, {partial_offset: partial.cursor.committedByteOffset,
      partial_incomplete: true, completed_offset: complete.cursor.committedByteOffset,
      completed_calls: 0, completed_diagnostics: codes(complete.diagnostics)});
  } finally { await handle?.close(); cleanup(t, CORE03, root); }
});
