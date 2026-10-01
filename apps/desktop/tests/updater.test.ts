import { strict as assert } from 'node:assert';
import { createHash, generateKeyPairSync, sign } from 'node:crypto';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { execFileSync } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import * as path from 'node:path';
import { validateUpdateURL, validateMetadata, verifyArchiveBytes, validateArchiveEntry, compareVersions, fetchLimited, inspectZip, verifyCodeRequirement } from '../src/main/updater.ts';

test('real codesign checks a requirement expression and rejects a mismatched identifier', async () => {
  const work = await mkdtemp(path.join(tmpdir(), 'tokenmeter-requirement-unit-'));
  try {
    const source = path.join(work, 'fixture.c'), executable = path.join(work, 'fixture');
    await writeFile(source, 'int main(void) { return 0; }\n');
    execFileSync('/usr/bin/clang', [source, '-o', executable]);
    execFileSync('/usr/bin/codesign', ['--force', '--sign', '-', '--identifier', 'org.tokenmeter.requirement-unit', '--timestamp=none', executable]);
    await verifyCodeRequirement(executable, 'identifier "org.tokenmeter.requirement-unit"');
    await assert.rejects(verifyCodeRequirement(executable, 'identifier "org.tokenmeter.other"'), /update_bundle_invalid/);
  } finally { await rm(work, { recursive: true, force: true }); }
});

test('update addresses reject external HTTP, credentials and ambiguous loopback spellings', () => {
  assert.equal(validateUpdateURL('http://127.0.0.1:49177/version.json').hostname, '127.0.0.1');
  assert.equal(validateUpdateURL('https://updates.example.com/version.json').protocol, 'https:');
  for (const url of ['http://example.com/a', 'file:///tmp/a', 'http://127.1/a', 'http://2130706433/a', 'http://user@127.0.0.1/a', 'http://127.0.0.1/a?q=x', 'http://127.0.0.1/a#x', 'http://127.0.0.1/a?', 'http://127.0.0.1/a#']) {
    assert.throws(() => validateUpdateURL(url), /update_source_rejected/);
  }
});

test('metadata requires bounded archive and strictly increasing actual version/build', () => {
  const metadata = { schema_version: 1, version: '0.1.1', build: '101', url: 'http://127.0.0.1/update.zip', sha256: 'a'.repeat(64), bytes: 200, ed25519_signature: Buffer.alloc(64).toString('base64') };
  assert.equal(validateMetadata(metadata, { version: '0.1.0', build: '100' }).build, '101');
  for (const changes of [{ bytes: 0 }, { bytes: 1024 ** 3 }, { bytes: true }, { version: '0.1.0' }, { build: '100' }, { ed25519_signature: 'bad' }, { url: 'http://evil.invalid/a' }]) {
    assert.throws(() => validateMetadata({ ...metadata, ...changes }, { version: '0.1.0', build: '100' }));
  }
  assert.equal(compareVersions('0.10.0', '0.2.0'), 1);
});

test('archive checks original bytes against digest, size and pinned Ed25519 key', () => {
  const key = generateKeyPairSync('ed25519');
  const other = generateKeyPairSync('ed25519');
  const bytes = Buffer.from('actual archive bytes');
  const publicKey = (key.publicKey.export({ type: 'spki', format: 'der' }) as Buffer).subarray(-32).toString('base64');
  const metadata = { schema_version: 1, version: '0.1.1', build: '101', url: 'http://127.0.0.1/update.zip', sha256: createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length, ed25519_signature: sign(null, bytes, key.privateKey).toString('base64') };
  verifyArchiveBytes(bytes, metadata, publicKey);
  assert.throws(() => verifyArchiveBytes(Buffer.from('changed archive bytes'), metadata, publicKey));
  assert.throws(() => verifyArchiveBytes(bytes, { ...metadata, ed25519_signature: sign(null, bytes, other.privateKey).toString('base64') }, publicKey), /update_signature_rejected/);
});

test('ZIP paths cannot escape, introduce siblings or traverse link entries', () => {
  assert.equal(validateArchiveEntry('TokenMeter.app/Contents/Info.plist'), 'TokenMeter.app/Contents/Info.plist');
  for (const name of ['../secret', '/TokenMeter.app/a', 'TokenMeter.app/../secret', 'TokenMeter.app\\a', 'other.app/Contents/a', 'TokenMeter.app//a']) {
    assert.throws(() => validateArchiveEntry(name), /update_bundle_invalid/);
  }
});

test('real HTTP reader refuses unsafe redirects and oversized bodies before handoff', async () => {
  const requests: string[] = [];
  const server = createServer((request, response) => {
    requests.push(request.url ?? '');
    if (request.url === '/redirect') { response.writeHead(302, { Location: 'http://updates.invalid/payload.zip' }); response.end(); }
    else { response.writeHead(200, { 'Content-Length': 10 }); response.end('1234567890'); }
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = (server.address() as { port: number }).port;
  try {
    await assert.rejects(fetchLimited(`http://127.0.0.1:${port}/redirect`, 100, new AbortController().signal), /update_transport_rejected/);
    await assert.rejects(fetchLimited(`http://127.0.0.1:${port}/large`, 5, new AbortController().signal), /update_integrity_failed/);
    assert.deepEqual(requests, ['/redirect', '/large']);
    assert.equal((await fetchLimited(`http://127.0.0.1:${port}/valid`, 10, new AbortController().signal))?.toString(), '1234567890');
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
});

test('real ZIP parser rejects writes beneath a symlink and out-of-bundle link targets', async () => {
  const work = await mkdtemp(path.join(tmpdir(), 'tokenmeter-zip-unit-'));
  try {
    for (const mode of ['valid', 'link-parent', 'escape']) {
      const archive = path.join(work, mode + '.zip');
      execFileSync('python3', ['-c', [
        'import zipfile,sys',
        'with zipfile.ZipFile(sys.argv[1],"w") as z:',
        ' z.writestr("TokenMeter.app/Contents/Info.plist", "fixture")',
        ' if sys.argv[2]!="valid":',
        '  i=zipfile.ZipInfo("TokenMeter.app/Contents/link");i.create_system=3;i.external_attr=(0o120777<<16)',
        '  z.writestr(i, "../Resources" if sys.argv[2]=="link-parent" else "/tmp/foreign")',
        '  if sys.argv[2]=="link-parent": z.writestr("TokenMeter.app/Contents/link/payload", "escape")',
      ].join('\n'), archive, mode]);
      if (mode === 'valid') await inspectZip(archive);
      else await assert.rejects(inspectZip(archive), /update_bundle_invalid/);
    }
  } finally { await rm(work, { recursive: true, force: true }); }
});
