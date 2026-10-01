import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { scanClaudeSource, type ClaudeSourceScanAccess } from '../src/main/collection/claude-scan.ts';

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
