import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, open, readFile, rm, stat, truncate, utimes, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash, createHmac } from 'node:crypto';
import { readClaudeCandidate, readClaudeFile } from '../src/main/collection/claude-reader.ts';
import { claudeCandidateFromSource } from '../src/main/collection/claude-source.ts';

const testSecret = Buffer.alloc(32, 0x42);
const mainFixture = join(import.meta.dirname, '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-main.jsonl');
const assistant = async (): Promise<Record<string, unknown>> => {
  const fixture = await readFile(mainFixture);
  assert.equal(createHash('sha256').update(fixture).digest('hex'), '2b484c185cf0ba333a85c53eb4953f13ddd2e40b6ab95167ca353a8454588ffe');
  const rows = fixture.toString('utf8').split('\n').filter(Boolean).map(line => JSON.parse(line) as Record<string, unknown>);
  return rows.find(row => row.type === 'assistant')!;
};
const fixedLine = async (): Promise<string> => {
  const line = `${JSON.stringify(await assistant())}\n`;
  assert.equal(Buffer.byteLength(line), 746);
  assert.equal(createHash('sha256').update(line).digest('hex'), 'cefd7dbe966383874d5b0f587c41089ecfbd8150a980a8b9ca701e4df4c9855f');
  return line;
};
const count = (diagnostics: readonly {code: string}[], code: string): number =>
  diagnostics.filter(item => item.code === code).length;

test('TC-TM004-CORE-01: half-line remains pending, completion commits one call and cursor', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'tm004-reader-'));
  const file = join(directory, 'synthetic.jsonl');
  const line = await fixedLine();
  const midpoint = Math.floor(line.length / 2);
  await writeFile(file, line.slice(0, midpoint), {mode: 0o600});
  const handle = await open(file, 'r');
  try {
    const partial = await readClaudeFile(handle, 'synthetic-file-a', null, testSecret);
    assert.equal(partial.calls.length, 0);
    assert.equal(partial.cursor.committedByteOffset, 0);
    assert.equal(partial.scanIncomplete, true);
    await writeFile(file, line, {mode: 0o600});
    const complete = await readClaudeFile(handle, 'synthetic-file-a', partial.cursor, testSecret);
    assert.equal(complete.calls.length, 1);
    assert.equal(complete.calls[0].inputTokens + complete.calls[0].outputTokens, 20);
    assert.equal(complete.cursor.committedByteOffset, Buffer.byteLength(line));
    assert.equal(complete.cursor.prefixMac, createHmac('sha256', testSecret).update(line).digest('hex'));
    assert.equal(complete.scanIncomplete, false);
    const repeated = await readClaudeFile(handle, 'synthetic-file-a', complete.cursor, testSecret);
    assert.equal(repeated.calls.length, 0);
    assert.equal(repeated.cursor.committedByteOffset, complete.cursor.committedByteOffset);
  } finally { await handle.close(); await rm(directory, {recursive: true}); }
});

test('TC-TM004-CORE-02: same-length prefix rewrite forces replay from zero despite restored mtime', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'tm004-reader-'));
  const file = join(directory, 'synthetic.jsonl');
  const original = await assistant();
  const firstLine = await fixedLine();
  await writeFile(file, firstLine, {mode: 0o600});
  const handle = await open(file, 'r');
  try {
    const fixedTime = new Date('2026-10-01T00:00:00.000Z');
    await utimes(file, fixedTime, fixedTime);
    const first = await readClaudeFile(handle, 'synthetic-file-a', null, testSecret);
    assert.equal(first.calls.length, 1);
    const before = await stat(file);
    const changed = structuredClone(original);
    (changed.message as Record<string, unknown>).id = 'msg_tm004_synthetic_main_002';
    const changedLine = `${JSON.stringify(changed)}\n`;
    assert.equal(Buffer.byteLength(changedLine), Buffer.byteLength(firstLine));
    await writeFile(file, changedLine, {mode: 0o600});
    await utimes(file, before.atime, before.mtime);
    assert.equal((await stat(file)).size, before.size);
    assert.equal((await stat(file)).mtimeMs, before.mtimeMs);
    const second = await readClaudeFile(handle, 'synthetic-file-a', first.cursor, testSecret);
    assert.equal(second.calls.length, 1);
    assert.equal(count(second.diagnostics, 'cursor_reset'), 1);
    assert.equal(second.calls[0].canonicalCallId, 'msg_tm004_synthetic_main_002');
  } finally { await handle.close(); await rm(directory, {recursive: true}); }
});

test('TC-TM004-CORE-02: append resumes without reset; truncate or identity change resets', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'tm004-reader-'));
  const file = join(directory, 'synthetic.jsonl');
  const firstLine = await fixedLine();
  const second = await assistant();
  (second.message as Record<string, unknown>).id = 'msg_tm004_synthetic_main_002';
  const secondLine = `${JSON.stringify(second)}\n`;
  await writeFile(file, firstLine, {mode: 0o600});
  const handle = await open(file, 'r');
  try {
    const first = await readClaudeFile(handle, 'synthetic-file-a', null, testSecret);
    await writeFile(file, firstLine + secondLine, {mode: 0o600});
    const appended = await readClaudeFile(handle, 'synthetic-file-a', first.cursor, testSecret);
    assert.deepEqual(appended.calls.map(call => call.canonicalCallId), ['msg_tm004_synthetic_main_002']);
    assert.equal(count(appended.diagnostics, 'cursor_reset'), 0);
    assert.equal(appended.cursor.committedByteOffset, Buffer.byteLength(firstLine + secondLine));
    await truncate(file, Buffer.byteLength(firstLine));
    const truncated = await readClaudeFile(handle, 'synthetic-file-a', appended.cursor, testSecret);
    assert.equal(count(truncated.diagnostics, 'cursor_reset'), 1);
    assert.equal(truncated.cursor.committedByteOffset, 746);
    assert.deepEqual(truncated.calls.map(call => call.canonicalCallId), ['msg_tm004_synthetic_main_001']);
    const identityChanged = await readClaudeFile(handle, 'synthetic-file-b', first.cursor, testSecret);
    assert.equal(count(identityChanged.diagnostics, 'cursor_reset'), 1);
    assert.equal(identityChanged.calls.length, 1);
  } finally { await handle.close(); await rm(directory, {recursive: true}); }
});

test('TC-TM004-CORE-02: missing secret or changed source yields no commit result', async () => {
  const bytes = Buffer.from(await fixedLine());
  const candidate = {
    fileIdentity: 'synthetic-file-a', size: bytes.length,
    async readAt(offset: number, maxBytes: number) { return bytes.subarray(offset, offset + maxBytes); },
    async assertCurrent() {},
  };
  await assert.rejects(readClaudeCandidate(candidate, null, Buffer.alloc(0)), /claude_reader_invalid_input/);
  await assert.rejects(readClaudeCandidate(candidate, null, Buffer.alloc(31)), /claude_reader_invalid_input/);
  let checks = 0;
  await assert.rejects(readClaudeCandidate({
    ...candidate,
    async assertCurrent() { if (++checks === 2) throw new Error('claude_source_changed'); },
  }, null, testSecret), /claude_source_changed/);
  assert.equal(checks, 2);
});

test('TC-TM004-CORE-03: bad UTF-8 and unknown version advance only complete lines', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'tm004-reader-'));
  const file = join(directory, 'synthetic.jsonl');
  const unknown = await assistant(); unknown.version = '2.1.127';
  const valid = await fixedLine();
  const bytes = Buffer.concat([Buffer.from([0xff, 0x0a]), Buffer.from(`${JSON.stringify(unknown)}\n${valid}`)]);
  await writeFile(file, bytes, {mode: 0o600});
  const handle = await open(file, 'r');
  try {
    const result = await readClaudeFile(handle, 'synthetic-file-a', null, testSecret);
    assert.equal(result.calls.length, 1);
    assert.equal(count(result.diagnostics, 'invalid_utf8'), 1);
    assert.equal(count(result.diagnostics, 'unsupported_version'), 1);
    assert.equal(result.cursor.committedByteOffset, bytes.length);
    assert.equal(result.cursor.prefixMac, createHmac('sha256', testSecret).update(bytes).digest('hex'));
    assert.equal(result.scanIncomplete, false);
    assert.equal((await readClaudeFile(handle, 'synthetic-file-a', result.cursor, testSecret)).calls.length, 0);
    assert.doesNotMatch(JSON.stringify(result), /synthetic\.jsonl/);
    await writeFile(file, Buffer.concat([bytes, Buffer.from([0xff])]), {mode: 0o600});
    const tail = await readClaudeFile(handle, 'synthetic-file-a', result.cursor, testSecret);
    assert.equal(tail.calls.length, 0);
    assert.equal(tail.cursor.committedByteOffset, bytes.length);
    assert.equal(tail.scanIncomplete, true);
    assert.equal(count(tail.diagnostics, 'invalid_utf8'), 0);
    await writeFile(file, Buffer.concat([bytes, Buffer.from([0xff, 0x0a])]), {mode: 0o600});
    const tailComplete = await readClaudeFile(handle, 'synthetic-file-a', tail.cursor, testSecret);
    assert.equal(tailComplete.calls.length, 0);
    assert.equal(count(tailComplete.diagnostics, 'invalid_utf8'), 1);
    assert.equal(tailComplete.cursor.committedByteOffset, bytes.length + 2);
  } finally { await handle.close(); await rm(directory, {recursive: true}); }
});

test('TC-TM004-CORE-01: bounded read resumes at the next full line', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'tm004-reader-'));
  const file = join(directory, 'synthetic.jsonl');
  const second = await assistant();
  (second.message as Record<string, unknown>).id = 'msg_synthetic_second_call';
  const firstLine = await fixedLine();
  const secondLine = `${JSON.stringify(second)}\n`;
  await writeFile(file, firstLine + secondLine, {mode: 0o600});
  const handle = await open(file, 'r');
  try {
    const limit = 754;
    const initial = await readClaudeFile(handle, 'synthetic-file-a', null, testSecret, limit);
    assert.equal(initial.calls.length, 1);
    assert.equal(initial.cursor.committedByteOffset, Buffer.byteLength(firstLine));
    assert.equal(initial.scanIncomplete, true);
    assert.equal(count(initial.diagnostics, 'read_limit'), 1);
    const resumed = await readClaudeFile(handle, 'synthetic-file-a', initial.cursor, testSecret);
    assert.equal(resumed.calls.length, 1);
    assert.equal(resumed.calls[0].canonicalCallId, 'msg_synthetic_second_call');
    assert.equal(resumed.cursor.committedByteOffset, Buffer.byteLength(firstLine + secondLine));
    assert.equal(resumed.scanIncomplete, false);
  } finally { await handle.close(); await rm(directory, {recursive: true}); }
});

test('TC-TM004-SOURCE-04 module boundary: opaque candidate reads bounded chunks without a path', async () => {
  const line = Buffer.from(`${JSON.stringify(await assistant())}\n`);
  let checked = 0;
  const result = await readClaudeCandidate({
    fileIdentity: 'opaque-candidate-a', size: line.length,
    async readAt(offset, maxBytes) {
      assert.ok(maxBytes > 0 && maxBytes <= 65536);
      return line.subarray(offset, offset + maxBytes);
    },
    async assertCurrent() { checked++; },
  }, null, testSecret);
  assert.equal(result.calls.length, 1);
  assert.equal(result.cursor.committedByteOffset, line.length);
  assert.ok(checked >= 2);
  assert.doesNotMatch(JSON.stringify(result), /private\/project|synthetic\.jsonl/);
});

test('TC-TM004-SOURCE-01 module boundary: TM-002 token gates every byte read', async () => {
  const bytes = Buffer.from(`${JSON.stringify(await assistant())}\n`);
  const scanId = '00000000-0000-4000-8000-000000000001';
  const sourceId = '00000000-0000-4000-8000-000000000002';
  const candidateToken = 'a'.repeat(32);
  const requests: Array<{scan: string; token: string; offset: number; maxBytes: number}> = [];
  const capability = claudeCandidateFromSource({
    async readCandidateChunk(scan, token, offset, maxBytes) {
      requests.push({scan, token, offset, maxBytes});
      return bytes.subarray(offset, offset + maxBytes);
    },
  }, scanId, sourceId, {relativeName: 'project/subagents/agent-1.jsonl',
    size: bytes.length, candidateToken, fileIdentityDigest: 'b'.repeat(64)}, testSecret);
  const observed = await readClaudeCandidate(capability, null, testSecret);
  assert.equal(observed.calls.length, 1);
  assert.ok(requests.length >= 3);
  assert.ok(requests.every(item => item.scan === scanId && item.token === candidateToken
    && item.maxBytes > 0 && item.maxBytes <= 65536));
  assert.match(observed.cursor.fileIdentity, /^[0-9a-f]{64}$/);
  assert.doesNotMatch(JSON.stringify(observed), /project\/subagents|00000000-0000-4000-8000-000000000002|aaaa/);
});

test('TC-TM004-INCREMENTAL-02 module: stable inode digest survives append and rename, replacement resets', () => {
  const access = {async readCandidateChunk() { return Buffer.alloc(0); }};
  const scanId = '00000000-0000-4000-8000-000000000001';
  const sourceId = '00000000-0000-4000-8000-000000000002';
  const candidateToken = 'a'.repeat(32);
  const original = claudeCandidateFromSource(access, scanId, sourceId,
    {relativeName: 'project/first.jsonl', size: 20, candidateToken, fileIdentityDigest: 'b'.repeat(64)}, testSecret);
  const appendedAndRenamed = claudeCandidateFromSource(access, scanId, sourceId,
    {relativeName: 'project/renamed.jsonl', size: 40, candidateToken, fileIdentityDigest: 'b'.repeat(64)}, testSecret);
  const replacement = claudeCandidateFromSource(access, scanId, sourceId,
    {relativeName: 'project/first.jsonl', size: 20, candidateToken, fileIdentityDigest: 'c'.repeat(64)}, testSecret);
  assert.equal(original.fileIdentity, appendedAndRenamed.fileIdentity);
  assert.notEqual(original.fileIdentity, replacement.fileIdentity);
});
