import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash, randomBytes} from 'node:crypto';
import {chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync,
  rmSync, utimesSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {SourceAccess, type SourceAccessAudit} from '../src/main/source-access.ts';
import {handleSourceIpcMethod} from '../src/main/source-ipc.ts';
import {SourceStore, type SourceCipher, type SourceTool} from '../src/main/source-store.ts';
import {ClientError} from '../src/main/validation.ts';

class TestCipher implements SourceCipher {
  async isAsyncEncryptionAvailable(): Promise<boolean> { return true; }
  async encryptStringAsync(): Promise<Buffer> { throw new Error('unexpected_encryption'); }
  async decryptStringAsync(): Promise<{result: string; shouldReEncrypt: boolean}> {
    throw new Error('unexpected_decryption');
  }
}

function sha256(path: string): string { return createHash('sha256').update(readFileSync(path)).digest('hex'); }
type Variant = 'ABSOLUTE' | 'FILE_URL' | 'DOTDOT';

for (const variant of ['ABSOLUTE', 'FILE_URL', 'DOTDOT'] as const satisfies readonly Variant[]) {
  test(`TC-TM002-SECURITY-01#${variant} rejects a renderer path at the production source IPC dispatcher`, async () => {
    const root = `/tmp/t2-${randomBytes(4).toString('hex')}`;
    mkdirSync(root, {mode: 0o700});
    const owner = join(root, 'owner.json');
    writeFileSync(owner, JSON.stringify({case_id: `TC-TM002-SECURITY-01#${variant}`}),
      {flag: 'wx', mode: 0o600});
    // SourceStore rejects a profile beneath world-writable /tmp. Keep the IPC
    // attack strings short while placing private state under the user's owned temp.
    const profileRoot = realpathSync(mkdtempSync(join(tmpdir(), 'tm002-ipc-profile-')));
    chmodSync(profileRoot, 0o700);
    const a = join(root, 'A'); const b = join(root, 'B'); const profile = join(profileRoot, 'profile');
    const bFile = join(b, 'b.jsonl');
    const aFile = join(a, 'a.jsonl');
    const audit: SourceAccessAudit[] = [];
    let pickerCalls = 0, helperCalls = 0;
    let selectedTool: SourceTool | null = null;
    try {
      mkdirSync(a, {mode: 0o700});
      mkdirSync(b, {mode: 0o700});
      mkdirSync(profile, {mode: 0o700});
      writeFileSync(aFile, '{"private":"PRIVATE_A1"}\n', {flag: 'wx', mode: 0o600});
      writeFileSync(bFile, '{"private":"PRIVATE_B1"}\n', {flag: 'wx', mode: 0o600});
      utimesSync(aFile, 1790812800, 1790812800);
      utimesSync(bFile, 1790812800, 1790812800);
      const originalA = sha256(aFile), originalB = sha256(bFile);
      const injected = variant === 'ABSOLUTE' ? bFile : variant === 'FILE_URL' ?
        pathToFileURL(bFile).href : '../B/b.jsonl';
      assert.ok(injected.length <= 64);
      const access = new SourceAccess({
        store: new SourceStore(profile, new TestCipher()),
        getIdentity: () => ({origin: 'http://127.0.0.1:59431', accountId: 'alice-id', verified: true, epoch: 1}),
        chooseDirectory: async () => { pickerCalls++; throw new Error('unexpected_picker'); },
        openHelper: async () => { helperCalls++; throw new Error('unexpected_helper'); },
        onChange: () => {}, onAudit: event => audit.push(event)
      });
      try {
        await access.syncIdentity();
        assert.equal(access.snapshot().codex.confirmed, null);
        assert.equal(access.snapshot().codex.pending, null);
        await assert.rejects(
          handleSourceIpcMethod('previewSource', {selectionId: injected}, access,
            tool => { selectedTool = tool; }),
          cause => cause instanceof ClientError && cause.code === 'invalid_selection' &&
            !cause.message.includes(injected) && !cause.message.includes(bFile)
        );
        assert.equal(selectedTool, null);
        assert.equal(pickerCalls, 0);
        assert.equal(helperCalls, 0);
        assert.deepEqual(audit, []);
        for (const tool of ['codex', 'claude_code'] as const) {
          assert.equal(access.snapshot()[tool].confirmed, null);
          assert.equal(access.snapshot()[tool].pending, null);
          assert.deepEqual(access.snapshot()[tool].candidates, []);
        }
        const records = join(profile, 'sources');
        assert.equal(existsSync(records) ? readdirSync(records).filter(name => name.endsWith('.json')).length : 0, 0);
        assert.equal(sha256(aFile), originalA);
        assert.equal(sha256(bFile), originalB);
        console.log(`TM002_IPC_EVIDENCE case=TC-TM002-SECURITY-01#${variant} code=invalid_selection` +
          ` picker=0 helper=0 source_audit=0 records=0 a_sha256=${originalA} b_sha256=${originalB}`);
      } finally {
        access.dispose();
      }
    } finally {
      assert.equal(JSON.parse(readFileSync(owner, 'utf8')).case_id,
        `TC-TM002-SECURITY-01#${variant}`);
      rmSync(root, {recursive: true, force: true});
      rmSync(profileRoot, {recursive: true, force: true});
    }
  });
}
