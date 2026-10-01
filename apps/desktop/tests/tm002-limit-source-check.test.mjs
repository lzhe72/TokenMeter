// TC-TM002-LIMIT-01 source_check: one production C preview invocation plus
// its exact stdout, adapter counters, and owned scratch cleanup witness.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {chmodSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const sha = value => createHash('sha256').update(value).digest('hex');

test('TC-TM002-LIMIT-01 source_check records the 2001 ms production C boundary once', () => {
  const scratch = realpathSync(mkdtempSync(join(tmpdir(), 'tokenmeter-tm002-source-check-limit-')));
  chmodSync(scratch, 0o700);
  const harness = fileURLToPath(new URL('./tm002-limit-harness.c', import.meta.url));
  const production = fileURLToPath(new URL('../native/source-helper.c', import.meta.url));
  const binary = join(scratch, 'tm002-limit-harness');
  let observed;
  try {
    const compile = spawnSync('/usr/bin/clang', [
      '-std=c11', '-D_DARWIN_C_SOURCE', '-O2', '-Wall', '-Wextra', '-Werror',
      '-fstack-protector-strong', '-o', binary, harness,
    ], {encoding: 'utf8'});
    assert.equal(compile.status, 0, compile.stderr || compile.error?.message);
    assert.equal(existsSync(binary), true);
    const result = spawnSync(binary, [], {encoding: 'utf8'});
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}\n${result.error?.message ?? ''}`);
    const lines = result.stdout.trimEnd().split('\n');
    assert.equal(lines.length, 5, result.stdout);
    for (const [index, operation] of ['enumerated', 'metadata'].entries()) {
      const match = new RegExp(`^AUDIT ${operation} candidate ([A-Za-z0-9+/=]+) \\d+ 101$`).exec(lines[index]);
      assert.ok(match, lines[index]);
      assert.equal(Buffer.from(match[1], 'base64').toString('utf8'), 'A1.jsonl');
    }
    assert.equal(lines[2], 'PREVIEW timeout 1 1');
    const item = /^ITEM ([A-Za-z0-9+/=]+) (\d+) (\d+) (\d+) ([a-f0-9]{64}) (-)$/.exec(lines[3]);
    assert.ok(item, lines[3]);
    assert.equal(Buffer.from(item[1], 'base64').toString('utf8'), 'A1.jsonl');
    assert.deepEqual(item.slice(2, 5), ['25', '1700000000', '123456789']);
    assert.equal(lines[4], 'END');
    const counters = 'HARNESS clock=3 open=2 openat=0 read=0 fstat=4 dup=2 close=4 fdopendir=1 readdir=1 fstatat=1 closedir=1 unexpected=0 names=2';
    assert.equal(result.stderr.trim(), counters);
    observed = {case_id: 'TC-TM002-LIMIT-01', input_sha256: sha(readFileSync(harness)),
      algorithm_sha256: sha(readFileSync(production)), stdout_lines: lines,
      stderr: result.stderr.trim(), exit_code: result.status};
  } finally {
    rmSync(scratch, {recursive: true, force: true});
  }
  assert.equal(existsSync(scratch), false);
  console.log('TM002_LIMIT_ACTUAL ' + JSON.stringify({...observed, scratch_removed: true}));
});
