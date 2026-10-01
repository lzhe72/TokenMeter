import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { commitClaudeSource, scanClaudeSource, type ClaudeSourceScanAccess,
  type GuardedClaudeSourceScanAccess } from '../src/main/collection/claude-scan.ts';

const sourceId = '00000000-0000-4000-8000-000000000002';
const scanId = '00000000-0000-4000-8000-000000000001';
const secret = Buffer.alloc(32, 0x42);
const fixture = join(import.meta.dirname, '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-main.jsonl');
const row = JSON.parse(readFileSync(fixture, 'utf8').split('\n').find(line => line.includes('"type":"assistant"'))!) as Record<string, unknown>;
const firstLine = Buffer.from(`${JSON.stringify(row)}\n`);
const second = structuredClone(row);
(second.message as Record<string, unknown>).id = 'msg_synthetic_last_page';
const lastLine = Buffer.from(`${JSON.stringify(second)}\n`);

test('TC-TM004-SOURCE-04 module: all 1025 candidate pages are consumed before coverage completes', async () => {
  const candidates = Array.from({length: 1025}, (_, index) => ({
    relativeName: `project/session-${index}.jsonl`,
    size: index === 0 ? firstLine.length : index === 1024 ? lastLine.length : 0,
    candidateToken: index.toString(16).padStart(32, '0'),
    fileIdentityDigest: index.toString(16).padStart(64, '0'),
  }));
  let pageIndex = 0, canceled = 0;
  const page = () => {
    const start = pageIndex++ * 256;
    return {candidates: candidates.slice(start, start + 256), complete: start + 256 >= candidates.length};
  };
  const access: ClaudeSourceScanAccess = {
    async beginCandidateScan(id) { assert.equal(id, sourceId); return {...page(), scanId}; },
    async nextCandidatePage(id) { assert.equal(id, scanId); return page(); },
    async readCandidateChunk(id, token, offset, maxBytes) {
      assert.equal(id, scanId); assert.ok(maxBytes <= 65536);
      const index = Number.parseInt(token, 16);
      const bytes = index === 0 ? firstLine : index === 1024 ? lastLine : Buffer.alloc(0);
      return bytes.subarray(offset, offset + maxBytes);
    },
    cancelScan(id) { assert.equal(id, scanId); canceled++; },
  };
  const observed = await scanClaudeSource(access, sourceId, secret, async () => null);
  assert.equal(observed.candidateCount, 1025);
  assert.equal(observed.scanIncomplete, false);
  assert.equal(observed.calls.length, 2);
  assert.equal(observed.calls.find(call => call.canonicalCallId === 'msg_synthetic_last_page')?.inputTokens, 13);
  assert.equal(observed.cursors.length, 1025);
  assert.equal(pageIndex, 5);
  assert.equal(canceled, 1);
});

test('TC-TM004-SOURCE-02 module: revocation during read discards the scan plan', async () => {
  let canceled = 0;
  const access: ClaudeSourceScanAccess = {
    async beginCandidateScan() { return {scanId, complete: true, candidates: [{relativeName: 'project/session.jsonl',
      size: firstLine.length, candidateToken: 'a'.repeat(32), fileIdentityDigest: 'b'.repeat(64)}]}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk() { throw new Error('source_access_denied private/path'); },
    cancelScan() { canceled++; },
  };
  await assert.rejects(scanClaudeSource(access, sourceId, secret, async () => null), /claude_read_failed/);
  assert.equal(canceled, 1);
});

test('TM004 guarded module boundary: synchronous commit runs before scan lease closes', async () => {
  const order: string[] = [];
  const access: GuardedClaudeSourceScanAccess = {
    async beginCandidateScan() { order.push('begin'); return {scanId, complete: true, candidates: [{
      relativeName: 'project/session.jsonl', size: firstLine.length,
      candidateToken: 'a'.repeat(32), fileIdentityDigest: 'b'.repeat(64)}]}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk(_scan, _token, offset, maxBytes) {
      order.push('read'); return firstLine.subarray(offset, offset + maxBytes);
    },
    async commitGuard(id) { assert.equal(id, scanId); order.push('get-guard');
      return () => { order.push('guard'); assert.equal(order.includes('cancel'), false); }; },
    cancelScan() { order.push('cancel'); },
  };
  const result = await commitClaudeSource(access, sourceId, secret, async () => null, plan => {
    order.push('commit');
    assert.equal(order.includes('guard'), true);
    assert.equal(order.includes('cancel'), false);
    assert.equal(plan.calls.length, 1);
    assert.equal(plan.cursors.length, 1);
    return plan.calls[0].inputTokens + plan.calls[0].outputTokens;
  });
  assert.equal(result, 20);
  assert.deepEqual(order.slice(-4), ['get-guard', 'guard', 'commit', 'cancel']);
});

test('TM004 guarded module boundary: revoked lease cannot invoke SQLite commit', async () => {
  let commits = 0, cancels = 0;
  const access: GuardedClaudeSourceScanAccess = {
    async beginCandidateScan() { return {scanId, complete: true, candidates: []}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk() { throw new Error('unexpected_read'); },
    async commitGuard() { return () => { throw new Error('source_operation_stale'); }; },
    cancelScan() { cancels++; },
  };
  await assert.rejects(commitClaudeSource(access, sourceId, secret, async () => null,
    () => { commits++; }), /claude_scan_failed/);
  assert.equal(commits, 0);
  assert.equal(cancels, 1);
});

test('TM004 lineage module boundary: parent evidence in another candidate verifies child Agent', async () => {
  const parent = readFileSync(join(import.meta.dirname,
    '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-agent-parent.jsonl'));
  const child = readFileSync(join(import.meta.dirname,
    '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-agent-sub.jsonl'));
  const files = [child, parent]; // Child arrives first to prove order does not grant attribution.
  const access: ClaudeSourceScanAccess = {
    async beginCandidateScan() { return {scanId, complete: true, candidates: files.map((bytes, index) => ({
      relativeName: `project/session-${index}.jsonl`, size: bytes.length,
      candidateToken: String(index).padStart(32, '0'), fileIdentityDigest: String(index).padStart(64, '0'),
    }))}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk(_scan, token, offset, maxBytes) {
      return files[Number(token)]!.subarray(offset, offset + maxBytes);
    },
    cancelScan() {},
  };
  const plan = await scanClaudeSource(access, sourceId, secret, async () => null);
  assert.equal(plan.calls.length, 3);
  assert.equal(plan.calls.find(call => call.isSidechain)?.attribution, 'parent_verified');
  assert.equal(plan.diagnostics.filter(item => item.code === 'unverified_parent').length, 0);
});

test('TM004 lineage module boundary: copied fork call across candidate files is counted once', async () => {
  const main = readFileSync(join(import.meta.dirname,
    '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-main.jsonl'));
  const fork = readFileSync(join(import.meta.dirname,
    '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-fork.jsonl'));
  const files = [main, fork];
  const access: ClaudeSourceScanAccess = {
    async beginCandidateScan() { return {scanId, complete: true, candidates: files.map((bytes, index) => ({
      relativeName: `project/session-${index}.jsonl`, size: bytes.length,
      candidateToken: String(index).padStart(32, '0'), fileIdentityDigest: String(index).padStart(64, '0'),
    }))}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk(_scan, token, offset, maxBytes) {
      return files[Number(token)]!.subarray(offset, offset + maxBytes);
    },
    cancelScan() {},
  };
  const plan = await scanClaudeSource(access, sourceId, secret, async () => null);
  assert.equal(plan.calls.length, 2);
  assert.equal(plan.calls.reduce((sum, call) => sum + call.inputTokens + call.outputTokens, 0), 40);
});

test('TM004 lineage module boundary: parent evidence after a read limit verifies earlier child', async () => {
  const parent = readFileSync(join(import.meta.dirname,
    '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-agent-parent.jsonl'));
  const child = readFileSync(join(import.meta.dirname,
    '../../../tests/fixtures/tm004/native-2.1.126-projection/raw-agent-sub.jsonl'));
  const bytes = Buffer.concat([child, ...Array.from({length: 1500}, () => firstLine), parent]);
  assert.ok(bytes.length > 1024 * 1024);
  const access: ClaudeSourceScanAccess = {
    async beginCandidateScan() { return {scanId, complete: true, candidates: [{
      relativeName: 'project/session.jsonl', size: bytes.length,
      candidateToken: 'a'.repeat(32), fileIdentityDigest: 'b'.repeat(64),
    }]}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk(_scan, _token, offset, maxBytes) {
      return bytes.subarray(offset, offset + maxBytes);
    },
    cancelScan() {},
  };
  const plan = await scanClaudeSource(access, sourceId, secret, async () => null);
  assert.equal(plan.scanIncomplete, false);
  assert.equal(plan.calls.length, 4);
  assert.equal(plan.calls.find(call => call.isSidechain)?.attribution, 'parent_verified');
  assert.equal(plan.diagnostics.filter(item => item.code === 'unverified_parent').length, 0);
  assert.equal(plan.cursors[0].committedByteOffset, bytes.length);
});

test('TM004 scan module boundary: oversized row leaves coverage incomplete with a read-limit diagnosis', async () => {
  const bytes = Buffer.alloc(1024 * 1024 + 1, 0x78);
  const access: ClaudeSourceScanAccess = {
    async beginCandidateScan() { return {scanId, complete: true, candidates: [{
      relativeName: 'project/session.jsonl', size: bytes.length,
      candidateToken: 'a'.repeat(32), fileIdentityDigest: 'b'.repeat(64),
    }]}; },
    async nextCandidatePage() { throw new Error('unexpected_page'); },
    async readCandidateChunk(_scan, _token, offset, maxBytes) {
      return bytes.subarray(offset, offset + maxBytes);
    },
    cancelScan() {},
  };
  const plan = await scanClaudeSource(access, sourceId, secret, async () => null);
  assert.equal(plan.calls.length, 0);
  assert.equal(plan.cursors[0].committedByteOffset, 0);
  assert.equal(plan.scanIncomplete, true);
  assert.ok(plan.diagnostics.some(item => item.code === 'read_limit'));
});
