import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, renameSync, rmSync, symlinkSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { SourceHelper, SourceHelperError, type SourceAuditEvent } from '../src/main/source-helper.ts';

const fixedMtime = new Date('2026-10-01T00:00:00Z');
const owned = realpathSync(mkdtempSync(join(tmpdir(), 'tokenmeter-source-helper-')));
chmodSync(owned, 0o700);
const binary = join(owned, 'source-helper');
const buildScript = fileURLToPath(new URL('../native/build-source-helper.sh', import.meta.url));
let nextFixture = 0;
function fixture(): string {
  const path = join(owned, `fixture-${++nextFixture}`);
  mkdirSync(path, { mode: 0o700 });
  return path;
}
function addFile(root: string, relative: string, text = '{}\n'): void {
  const path = join(root, relative);
  writeFileSync(path, text, { mode: 0o600 });
  utimesSync(path, fixedMtime, fixedMtime);
}
before(() => execFileSync('/bin/sh', [buildScript, binary], { stdio: 'pipe' }));
after(() => rmSync(owned, { recursive: true, force: true }));

test('TC-TM002-PREVIEW-01/02/03: native preview enumerates only ordinary jsonl metadata below its root', async () => {
  const root = fixture();
  const nested = join(root, 'sessions'); mkdirSync(nested, { mode: 0o700 });
  addFile(root, 'a.jsonl', 'PRIVATE_A\n');
  addFile(nested, 'b.jsonl', 'PRIVATE_B\n');
  addFile(root, 'ignore.txt', 'ignored');
  const outside = fixture(); addFile(outside, 'out.jsonl', 'PRIVATE_OUTSIDE\n');
  symlinkSync(join(outside, 'out.jsonl'), join(root, 'link.jsonl'));
  symlinkSync(outside, join(root, 'escape'));
  execFileSync('/usr/bin/mkfifo', [join(root, 'pipe.jsonl')]);
  const audit: SourceAuditEvent[] = [];
  const helper = await SourceHelper.open(root, { binaryPath: binary, onAudit: event => audit.push(event) });
  try {
    const result = await helper.preview();
    assert.deepEqual(result.candidates.map(item => item.relativeName), ['a.jsonl', 'sessions/b.jsonl']);
    assert.equal(result.incomplete, false);
    assert.equal(result.candidates[0].size, 10);
    assert.equal(result.candidates[0].mtimeMs, fixedMtime.getTime());
    assert.equal(JSON.stringify(result).includes(root), false);
    assert.equal(JSON.stringify(result).includes('PRIVATE_'), false);
    assert.deepEqual(audit.flatMap(event => event.action === 'enumerated' ? [event.relativeName] : []).sort(), ['a.jsonl', 'sessions/b.jsonl']);
    assert.deepEqual(audit.flatMap(event => event.action === 'metadata' ? [event.relativeName] : []).sort(), ['a.jsonl', 'sessions/b.jsonl']);
    assert.deepEqual(audit.flatMap(event => event.action === 'rejected' ? [[event.kind, event.relativeName]] : []).sort(),
      [['non_regular', 'pipe.jsonl'], ['symlink', 'escape'], ['symlink', 'link.jsonl']]);
    assert.equal(audit.filter(event => event.action === 'open_read').length, 0);
    assert.equal(audit.every(event => event.rootIdentity.dev === helper.rootIdentity.dev && event.rootIdentity.ino === helper.rootIdentity.ino), true);
    assert.equal(JSON.stringify(audit).includes(root), false);
  } finally { helper.close(); }
  assert.equal(readFileSync(join(outside, 'out.jsonl'), 'utf8'), 'PRIVATE_OUTSIDE\n');
  const observerFailure = await SourceHelper.open(root, {
    binaryPath: binary,
    onAudit: () => { throw new Error('observer failure'); },
  });
  try {
    assert.deepEqual((await observerFailure.preview()).candidates.map(item => item.relativeName), ['a.jsonl', 'sessions/b.jsonl']);
  } finally { observerFailure.close(); }
});

test('TC-TM002-PREVIEW-04#CANDIDATES_1001: first 1000 are chosen after UTF-8 sorting', async () => {
  const root = fixture();
  for (let i = 1000; i >= 0; i--) addFile(root, `c-${String(i).padStart(4, '0')}.jsonl`);
  const helper = await SourceHelper.open(root, { binaryPath: binary });
  try {
    const result = await helper.preview();
    assert.equal(result.incomplete, true);
    assert.equal(result.reason, 'candidate_limit');
    assert.equal(result.candidates.length, 1000);
    assert.equal(result.candidates[0].relativeName, 'c-0000.jsonl');
    assert.equal(result.candidates.at(-1)?.relativeName, 'c-0999.jsonl');
  } finally { helper.close(); }
});

test('TC-TM002-PREVIEW-04#ENTRIES_5001 and #DEPTH_9: preview reports incomplete scope', async () => {
  const root = fixture();
  for (let i = 5000; i >= 0; i--) addFile(root, `n-${String(i).padStart(4, '0')}.txt`);
  const helper = await SourceHelper.open(root, { binaryPath: binary });
  try {
    const result = await helper.preview();
    assert.equal(result.incomplete, true);
    assert.equal(result.reason, 'entry_limit');
    assert.equal(result.inspectedEntries, 5000);
    assert.deepEqual(result.candidates, []);
  } finally { helper.close(); }
  const depthRoot = fixture(); let current = depthRoot;
  for (let i = 1; i <= 7; i++) { current = join(current, `d${i}`); mkdirSync(current, { mode: 0o700 }); }
  addFile(current, 'at8.jsonl');
  current = join(current, 'd8'); mkdirSync(current, { mode: 0o700 }); addFile(current, 'at9.jsonl');
  const depthHelper = await SourceHelper.open(depthRoot, { binaryPath: binary });
  try {
    const result = await depthHelper.preview();
    assert.deepEqual(result.candidates.map(item => item.relativeName), ['d1/d2/d3/d4/d5/d6/d7/at8.jsonl']);
    assert.equal(result.incomplete, true);
    assert.equal(result.reason, 'depth_limit');
  } finally { depthHelper.close(); }
});

function populatePages(root: string): string[] {
  addFile(root, 'a.jsonl'); mkdirSync(join(root, 'a'), { mode: 0o700 }); addFile(join(root, 'a'), 'x.jsonl');
  const names = ['a.jsonl', 'a/x.jsonl'];
  for (let i = 0; i < 1199; i++) { const name = `p-${String(i).padStart(4, '0')}.jsonl`; addFile(root, name); names.push(name); }
  return names;
}
test('TC-TM002-ACCESS-06#PAGE_COMPLETION: 1201 native candidates span five ordered pages', async () => {
  const root = fixture(); const expected = populatePages(root);
  const helper = await SourceHelper.open(root, { binaryPath: binary });
  try {
    let page = await helper.beginCandidateScan(); const seen: string[] = []; const sizes: number[] = [];
    for (;;) {
      sizes.push(page.candidates.length);
      assert.equal(page.candidates.length <= 256, true);
      seen.push(...page.candidates.map(item => item.relativeName));
      if (page.complete) break;
      page = await helper.nextCandidatePage();
    }
    assert.deepEqual(sizes, [256, 256, 256, 256, 177]);
    assert.deepEqual(seen, expected);
    assert.equal(page.complete, true);
  } finally { helper.close(); }
});

test('TC-TM002-ACCESS-06#TREE_CHANGED: an insertion invalidates the old page before any result', async () => {
  const root = fixture(); const original = populatePages(root);
  const helper = await SourceHelper.open(root, { binaryPath: binary });
  try {
    const first = await helper.beginCandidateScan();
    assert.deepEqual(first.candidates.map(item => item.relativeName), original.slice(0, 256));
    addFile(root, 'p-0000a.jsonl');
    await assert.rejects(helper.nextCandidatePage(), (error: unknown) => error instanceof SourceHelperError && error.code === 'tree_changed');
    const expected = [...original.slice(0, 3), 'p-0000a.jsonl', ...original.slice(3)];
    let page = await helper.beginCandidateScan(); const seen: string[] = []; const sizes: number[] = [];
    for (;;) { sizes.push(page.candidates.length); seen.push(...page.candidates.map(item => item.relativeName)); if (page.complete) break; page = await helper.nextCandidatePage(); }
    assert.deepEqual(sizes, [256, 256, 256, 256, 178]);
    assert.deepEqual(seen, expected);
  } finally { helper.close(); }
});

test('TC-TM002-ACCESS-03: root inode replacement invalidates the held capability', async () => {
  const root = fixture(); addFile(root, 'one.jsonl');
  const helper = await SourceHelper.open(root, { binaryPath: binary });
  try {
    await helper.beginCandidateScan();
    renameSync(root, `${root}-old`); mkdirSync(root, { mode: 0o700 }); addFile(root, 'new.jsonl');
    await assert.rejects(helper.beginCandidateScan(), (error: unknown) => error instanceof SourceHelperError && error.code === 'root_changed');
  } finally { helper.close(); rmSync(`${root}-old`, { recursive: true, force: true }); }
});

test('TC-TM002-ACCESS-03: C rejects a stale expected root at open and returns the held identity', async () => {
  const root = fixture(); addFile(root, 'one.jsonl');
  const first = await SourceHelper.open(root, { binaryPath: binary });
  const expectedRoot = first.rootIdentity;
  assert.match(expectedRoot.dev, /^\d+$/);
  assert.match(expectedRoot.ino, /^\d+$/);
  first.close();
  const verified = await SourceHelper.open(root, { binaryPath: binary, expectedRoot });
  assert.deepEqual(verified.rootIdentity, expectedRoot);
  verified.close();
  await assert.rejects(
    SourceHelper.open(root, { binaryPath: binary, expectedRoot: { ...expectedRoot, ino: (BigInt(expectedRoot.ino) + 1n).toString() } }),
    (error: unknown) => error instanceof SourceHelperError && error.code === 'root_changed',
  );
});

test('TC-TM002-ACCESS-06#TREE_CHANGED: change in a visited child directory invalidates later pages', async () => {
  const root = fixture(); populatePages(root);
  const helper = await SourceHelper.open(root, { binaryPath: binary });
  try {
    const page = await helper.beginCandidateScan();
    assert.match(page.candidates[0].fileIdentityDigest, /^[a-f0-9]{64}$/);
    addFile(join(root, 'a'), 'z.jsonl');
    await assert.rejects(helper.nextCandidatePage(), (error: unknown) => error instanceof SourceHelperError && error.code === 'tree_changed');
  } finally { helper.close(); }
});

test('TC-TM002-ACCESS-01: closing a capability blocks queued and future operations', async () => {
  const root = fixture(); addFile(root, 'a.jsonl');
  const helper = await SourceHelper.open(root, { binaryPath: binary });
  const pending = helper.beginCandidateScan();
  helper.close();
  await assert.rejects(pending, (error: unknown) => error instanceof SourceHelperError);
  await assert.rejects(helper.preview(), (error: unknown) => error instanceof SourceHelperError);
  await assert.rejects(helper.nextCandidatePage(), (error: unknown) => error instanceof SourceHelperError);
});

test('TC-TM002-ACCESS-01: an unresponsive helper is terminated before a source operation can hang', async () => {
  const root = fixture(); addFile(root, 'a.jsonl');
  const silent = join(owned, 'silent-helper');
  writeFileSync(silent, '#!/bin/sh\nexec sleep 10\n', {mode: 0o700});
  chmodSync(silent, 0o700);
  await assert.rejects(SourceHelper.open(root, {binaryPath: silent, timeoutMs: 300}),
    (error: unknown) => error instanceof SourceHelperError && error.code === 'helper_timeout');

  const stalled = join(owned, 'stalled-helper');
  writeFileSync(stalled,
    '#!/usr/bin/env node\nprocess.stdin.once("data", () => { process.stdout.write("OK 1 1\\n"); process.stdin.resume(); });\n',
    {mode: 0o700});
  chmodSync(stalled, 0o700);
  const helper = await SourceHelper.open(root, {binaryPath: stalled, timeoutMs: 2000});
  try {
    await assert.rejects(helper.preview(),
      (error: unknown) => error instanceof SourceHelperError && error.code === 'helper_timeout');
    await assert.rejects(helper.preview(),
      (error: unknown) => error instanceof SourceHelperError && error.code === 'invalid_scan');
  } finally { helper.close(); }
});

test('TC-TM002-ACCESS-06: bounded private read rejects forged token and replaced target', async () => {
  const root = fixture(); addFile(root, 'a.jsonl', 'private-body\n');
  const audit: SourceAuditEvent[] = [];
  const helper = await SourceHelper.open(root, { binaryPath: binary, onAudit: event => audit.push(event) });
  try {
    const page = await helper.beginCandidateScan(); const token = page.candidates[0].candidateToken;
    assert.equal((await helper.readCandidateChunk(token, 0, 4)).toString(), 'priv');
    assert.deepEqual(audit.flatMap(event => event.action === 'open_read' ? [event.relativeName] : []), ['a.jsonl']);
    await assert.rejects(helper.readCandidateChunk('00'.repeat(16), 0, 4), (error: unknown) => error instanceof SourceHelperError && error.code === 'invalid_token');
    const outside = fixture(); addFile(outside, 'target.jsonl', 'NOT_ALLOWED\n');
    rmSync(join(root, 'a.jsonl')); symlinkSync(join(outside, 'target.jsonl'), join(root, 'a.jsonl'));
    await assert.rejects(helper.readCandidateChunk(token, 0, 4));
  } finally { helper.close(); }
});
