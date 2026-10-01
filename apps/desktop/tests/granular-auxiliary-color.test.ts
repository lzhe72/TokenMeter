import assert from 'node:assert/strict';
import test from 'node:test';
import {contrastRatio} from '../e2e/granular-auxiliary-color.ts';

test('short #fff and full #ffffff have the same high contrast against the App light text', () => {
  const short = contrastRatio('#202024', '#fff');
  assert.equal(short, contrastRatio('#202024', '#ffffff'));
  assert.ok(short >= 4.5);
});

test('the App dark text and surface meet the same contrast rule', () => {
  assert.ok(contrastRatio('#f1f1f3', '#2b2b2e') >= 4.5);
  assert.throws(() => contrastRatio('#202024', 'white'), /Unsupported CSS color/);
});
