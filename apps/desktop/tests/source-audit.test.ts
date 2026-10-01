import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { chmodSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SourceAudit } from '../src/main/source-audit.ts';

const nonce = 'a1'.repeat(32);
function profile(): string { const value = realpathSync(mkdtempSync(join(tmpdir(), 'tm002-source-audit-'))); chmodSync(value, 0o700); return value; }
function digest(value: string): string { return createHmac('sha256', Buffer.from(nonce, 'hex')).update(value).digest('hex'); }

test('TC-TM002-EVIDENCE-01#COMPLETE writes only owned HMAC audit facts', () => {
  const root = profile(); const path = join(root, 'source-access-audit.jsonl');
  try {
    const audit = new SourceAudit(root, nonce);
    audit.record({operation: 'enumerate', decision: 'allowed', tool: 'codex', generation: 4,
      rootDev: '19', rootIno: '27', relativeName: 'private-project/secret.jsonl'});
    audit.record({operation: 'reject', decision: 'denied', reason: 'symlink', tool: 'codex', generation: 4,
      rootDev: '19', rootIno: '27', relativeName: 'escape.jsonl'});
    audit.record({operation: 'picker_open', decision: 'allowed', tool: 'codex', generation: 4});
    audit.record({operation: 'picker_result', decision: 'denied', reason: 'canceled', tool: 'codex', generation: 4});
    audit.record({operation: 'preview_complete', decision: 'allowed', reason: 'entry_limit', tool: 'codex', generation: 4,
      rootDev: '19', rootIno: '27', inspectedEntries: 5000, candidateCount: 7});
    audit.close();
    assert.equal(statSync(path).mode & 0o777, 0o600);
    const raw = readFileSync(path, 'utf8');
    assert.equal(raw.includes('private-project'), false);
    assert.equal(raw.includes('escape.jsonl'), false);
    assert.equal(raw.includes(root), false);
    const events = raw.trim().split('\n').map(line => JSON.parse(line));
    assert.equal(events.length, 5);
    assert.deepEqual(events.map(event => event.sequence), [1, 2, 3, 4, 5]);
    assert.equal(events[0].root_digest, digest('19:27'));
    assert.equal(events[0].entry_digest, digest('private-project/secret.jsonl'));
    assert.equal(events[1].entry_digest, digest('escape.jsonl'));
    assert.equal(events[1].reason, 'symlink');
    assert.equal(events[2].root_digest, null);
    assert.equal(events[3].reason, 'canceled');
    assert.deepEqual([events[4].inspected_entries, events[4].candidate_count, events[4].reason], [5000, 7, 'entry_limit']);
  } finally { rmSync(root, {recursive: true, force: true}); }
});

test('TC-TM002-EVIDENCE-01#RESTART appends a continuous owned sequence and rejects damaged history', () => {
  const root = profile();
  try {
    assert.throws(() => new SourceAudit(root, 'not-hex'));
    const first = new SourceAudit(root, nonce);
    first.record({operation: 'picker_open', decision: 'allowed', tool: 'codex', generation: 1});
    first.close();
    const second = new SourceAudit(root, nonce);
    second.record({operation: 'picker_result', decision: 'denied', reason: 'canceled', tool: 'codex', generation: 1});
    second.close();
    const path = join(root, 'source-access-audit.jsonl');
    assert.deepEqual(readFileSync(path, 'utf8').trim().split('\n').map(line => JSON.parse(line).sequence), [1, 2]);
    writeFileSync(path, '{"schema_version":1,"sequence":3}', {mode: 0o600});
    assert.throws(() => new SourceAudit(root, nonce), {code: 'invalid_source_audit'});
  } finally { rmSync(root, {recursive: true, force: true}); }
});
