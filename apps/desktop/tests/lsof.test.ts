import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseLsofPaths } from '../e2e/lsof.ts';

test('lsof -Fn keeps every named open file while omitting unnamed records', () => {
  const output = 'p123\nfcwd\nn/owned/profile/settings.json\nf1\nn\nf2\nn/usr/lib/libSystem.B.dylib\nn/owned/profile/name with spaces\n';
  assert.deepEqual(parseLsofPaths(output), [
    '/owned/profile/settings.json',
    '/usr/lib/libSystem.B.dylib',
    '/owned/profile/name with spaces'
  ]);
  assert.deepEqual(parseLsofPaths('p123\r\nfcwd\r\nn\r\n'), []);
});
