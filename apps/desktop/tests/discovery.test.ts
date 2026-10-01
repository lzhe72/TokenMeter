import { test } from 'node:test';
import assert from 'node:assert/strict';
import { UpdateDiscovery } from '../src/main/discovery.ts';
test('automatic discovery waits for verified, changed credentials and idle updater', () => {
  const policy = new UpdateDiscovery(); const state = {server:'http://127.0.0.1:40000', feed:'http://127.0.0.1:40001/version.json', account:{id:'member',must_change_password:false}, identityVerified:true, canCheck:true};
  assert.equal(policy.shouldCheck({...state, account:null}), false);
  assert.equal(policy.shouldCheck({...state, identityVerified:false}), false);
  assert.equal(policy.shouldCheck({...state, account:{...state.account,must_change_password:true}}), false);
  assert.equal(policy.shouldCheck({...state, canCheck:false}), false);
  assert.equal(policy.shouldCheck(state), true); assert.equal(policy.shouldCheck(state), false);
  assert.equal(policy.shouldCheck({...state, feed:'http://127.0.0.1:40002/version.json'}), true);
  assert.equal(policy.shouldCheck({...state, account:null}), false);
  assert.equal(policy.shouldCheck(state), true);
});
