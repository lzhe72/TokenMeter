import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {chmodSync, mkdtempSync, readFileSync, realpathSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

function sha256(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex');
}

test('TC-TM002-LIMIT-01 stops the production preview algorithm at the injected 2001 ms boundary', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'tokenmeter-tm002-limit-')));
  chmodSync(root, 0o700);
  const harness = fileURLToPath(new URL('./tm002-limit-harness.c', import.meta.url));
  const production = fileURLToPath(new URL('../native/source-helper.c', import.meta.url));
  const binary = join(root, 'tm002-limit-harness');
  try {
    const compile = spawnSync('/usr/bin/clang', [
      '-std=c11', '-D_DARWIN_C_SOURCE', '-O2', '-Wall', '-Wextra', '-Werror',
      '-fstack-protector-strong', '-o', binary, harness
    ], {encoding: 'utf8'});
    assert.equal(compile.status, 0, compile.stderr);
    const result = spawnSync(binary, [], {encoding: 'utf8'});
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    const lines = result.stdout.trimEnd().split('\n');
    assert.equal(lines.length, 5, result.stdout);
    assert.match(lines[0], /^AUDIT enumerated candidate [A-Za-z0-9+/=]+ \d+ 101$/);
    assert.match(lines[1], /^AUDIT metadata candidate [A-Za-z0-9+/=]+ \d+ 101$/);
    assert.equal(Buffer.from(lines[0].split(' ')[3], 'base64').toString('utf8'), 'A1.jsonl');
    assert.equal(Buffer.from(lines[1].split(' ')[3], 'base64').toString('utf8'), 'A1.jsonl');
    assert.equal(lines[2], 'PREVIEW timeout 1 1');
    const item = /^ITEM ([A-Za-z0-9+/=]+) (\d+) (\d+) (\d+) ([a-f0-9]{64}) (-)$/.exec(lines[3]);
    assert.ok(item, lines[3]);
    assert.equal(Buffer.from(item[1], 'base64').toString('utf8'), 'A1.jsonl');
    assert.equal(item[2], '25');
    assert.equal(item[3], '1700000000');
    assert.equal(item[4], '123456789');
    assert.equal(lines[4], 'END');
    assert.equal(result.stderr.trim(),
      'HARNESS clock=3 open=2 openat=0 read=0 fstat=4 dup=2 close=4 fdopendir=1 readdir=1 fstatat=1 closedir=1 unexpected=0 names=2');
    console.log(`TM002_LIMIT_EVIDENCE input_sha256=${sha256(readFileSync(harness))}` +
      ` algorithm_sha256=${sha256(readFileSync(production))} output_sha256=${sha256(result.stdout)}`);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});
