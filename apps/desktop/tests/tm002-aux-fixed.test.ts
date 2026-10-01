import {after, before, test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash, randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync,
  writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {SourceAccess, type SourceAccessAudit} from '../src/main/source-access.ts';
import {SourceHelper} from '../src/main/source-helper.ts';
import {SourceStore, type SourceCipher} from '../src/main/source-store.ts';
import {ClientError} from '../src/main/validation.ts';

const owned = realpathSync(mkdtempSync(join(tmpdir(), 'tokenmeter-tm002-aux-')));
chmodSync(owned, 0o700);
const helperBinary = join(owned, 'source-helper');
const buildScript = fileURLToPath(new URL('../native/build-source-helper.sh', import.meta.url));
before(() => execFileSync('/bin/sh', [buildScript, helperBinary], {stdio: 'pipe'}));
after(() => rmSync(owned, {recursive: true, force: true}));

class TestCipher implements SourceCipher {
  readonly values = new Map<string, string>();
  async isAsyncEncryptionAvailable(): Promise<boolean> { return true; }
  async encryptStringAsync(value: string): Promise<Buffer> {
    const token = Buffer.from(`owned:${randomUUID()}`);
    this.values.set(token.toString('base64'), value);
    return token;
  }
  async decryptStringAsync(token: Buffer): Promise<{result: string; shouldReEncrypt: boolean}> {
    const result = this.values.get(token.toString('base64'));
    if (result === undefined) throw new Error('unexpected_test_ciphertext');
    return {result, shouldReEncrypt: false};
  }
}

function digest(data: Buffer): string { return createHash('sha256').update(data).digest('hex'); }
function add(root: string, relative: string): void {
  const path = join(root, relative);
  writeFileSync(path, '{}\n', {flag: 'wx', mode: 0o600});
}

test('TC-TM002-ACCESS-06#REVOKE_CURSOR rejects the old page after a real 1201-file source is revoked', async () => {
  const profile = join(owned, 'revoke-cursor-' + randomUUID());
  mkdirSync(profile, {mode: 0o700});
  const a = join(profile, 'A'); const b = join(profile, 'B');
  mkdirSync(a, {mode: 0o700}); mkdirSync(b, {mode: 0o700});
  add(a, 'a.jsonl');
  mkdirSync(join(a, 'a'), {mode: 0o700}); add(a, 'a/x.jsonl');
  const names = ['a.jsonl', 'a/x.jsonl'];
  for (let index = 0; index < 1199; index++) {
    const relative = `p-${String(index).padStart(4, '0')}.jsonl`;
    add(a, relative); names.push(relative);
  }
  add(b, 'b-01.jsonl');
  assert.equal(names.length, 1201);
  const beforeA = names.map(name => digest(readFileSync(join(a, name))));
  const beforeB = digest(readFileSync(join(b, 'b-01.jsonl')));
  const audit: SourceAccessAudit[] = [];
  const access = new SourceAccess({
    store: new SourceStore(profile, new TestCipher()),
    getIdentity: () => ({origin: 'http://127.0.0.1:59431', accountId: 'alice-id', verified: true, epoch: 1}),
    chooseDirectory: async () => ({canceled: false, rootPath: a}),
    openHelper: (path, options) => SourceHelper.open(path, {...options, binaryPath: helperBinary}),
    onChange: () => {}, onAudit: event => audit.push(event)
  });
  try {
    await access.syncIdentity(); await access.choose('codex');
    const selectionId = access.snapshot().codex.pending?.selectionId;
    assert.ok(selectionId);
    await access.confirm(selectionId, true, false);
    const sourceId = access.snapshot().codex.confirmed?.sourceId;
    assert.ok(sourceId);
    const page = await access.beginCandidateScan(sourceId);
    assert.deepEqual(page.candidates.map(item => item.relativeName), names.slice(0, 256));
    assert.equal(page.complete, false);
    assert.equal(page.candidates.length, 256);
    assert.match(page.scanId, /^[0-9a-f-]{36}$/i);
    assert.equal(readdirSync(join(profile, 'sources')).filter(name => name.endsWith('.json')).length, 1);

    await access.revoke(sourceId);
    const boundary = audit.length;
    assert.equal(access.snapshot().codex.confirmed, null);
    assert.deepEqual(access.snapshot().codex.candidates, []);
    assert.equal(readdirSync(join(profile, 'sources')).filter(name => name.endsWith('.json')).length, 0);
    const invalidated = (cause: unknown): boolean => cause instanceof ClientError &&
      ['invalid_scan', 'source_operation_stale'].includes(cause.code);
    await assert.rejects(access.nextCandidatePage(page.scanId), invalidated);
    await assert.rejects(access.nextCandidatePage(page.scanId), invalidated);
    assert.equal(audit.slice(boundary).filter(item => ['root_open', 'enumerate', 'metadata', 'open_read'].includes(item.operation)).length, 0);
    assert.equal(audit.filter(item => item.operation === 'open_read').length, 0);
    assert.equal(audit.filter(item => item.operation === 'enumerate' && item.tool === 'claude_code').length, 0);
    assert.deepEqual(names.map(name => digest(readFileSync(join(a, name)))), beforeA);
    assert.equal(digest(readFileSync(join(b, 'b-01.jsonl'))), beforeB);
    assert.equal(existsSync(join(profile, 'sources')), true);
  } finally {
    access.dispose();
    rmSync(profile, {recursive: true, force: true});
  }
});
