import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {chmodSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {SourceAccess, type SourceAccessAudit, type SourceAccessIdentity, type SourceHelperLike, type SourcePreview} from '../src/main/source-access.ts';
import type {SourceAuditEvent} from '../src/main/source-helper.ts';
import {SourceStore, type SourceCipher} from '../src/main/source-store.ts';
import {privateWrite} from '../src/main/storage.ts';
import {ClientError} from '../src/main/validation.ts';

const candidate = {relativeName: 'sessions/2026/10/01/a-01.jsonl', size: 25,
  mtimeMs: Date.parse('2026-10-01T00:00:00Z'), fileIdentityDigest: 'a'.repeat(64)};
const publicCandidate = {relativeName: candidate.relativeName, size: candidate.size, mtimeMs: candidate.mtimeMs};

class Cipher implements SourceCipher {
  available = true;
  readonly values = new Map<string, string>();
  async isAsyncEncryptionAvailable(): Promise<boolean> { return this.available; }
  async encryptStringAsync(value: string): Promise<Buffer> {
    if (!this.available) throw new Error('key_unavailable');
    const token = Buffer.from(`cipher:${randomUUID()}`);
    this.values.set(token.toString('base64'), value);
    return token;
  }
  async decryptStringAsync(value: Buffer): Promise<{result: string; shouldReEncrypt: boolean}> {
    if (!this.available) throw new Error('key_unavailable');
    const result = this.values.get(value.toString('base64'));
    if (!result) throw new Error('corrupt_ciphertext');
    return {result, shouldReEncrypt: false};
  }
}

class FakeHelper implements SourceHelperLike {
  readonly rootIdentity: {dev: string; ino: string};
  readonly rootPath: string;
  readonly audit?: (event: SourceAuditEvent) => void;
  closed = false;
  previewBarrier: null | {entered(): void; wait: Promise<void>} = null;
  constructor(rootPath: string, ino: string, audit?: (event: SourceAuditEvent) => void) {
    this.rootPath = rootPath; this.rootIdentity = {dev: '17', ino}; this.audit = audit;
  }
  async preview(): Promise<SourcePreview> {
    if (this.closed) throw new ClientError('invalid_scan', '已关闭');
    const barrier = this.previewBarrier;
    if (barrier) { barrier.entered(); await barrier.wait; }
    if (this.closed) throw new ClientError('invalid_scan', '已关闭');
    this.audit?.({action: 'enumerated', kind: 'candidate', relativeName: candidate.relativeName,
      rootIdentity: this.rootIdentity, targetIdentity: {dev: '17', ino: '31'}});
    return {candidates: [candidate], incomplete: false, inspectedEntries: 1};
  }
  async beginCandidateScan() {
    if (this.closed) throw new ClientError('invalid_scan', '已关闭');
    return {candidates: [{...candidate, candidateToken: 'a'.repeat(32)}], complete: false};
  }
  async nextCandidatePage() {
    if (this.closed) throw new ClientError('invalid_scan', '已关闭');
    return {candidates: [], complete: true};
  }
  async readCandidateChunk(token: string, _offset: number, _maxBytes: number): Promise<Buffer> {
    if (this.closed || token !== 'a'.repeat(32)) throw new ClientError('invalid_token', '令牌无效');
    return Buffer.from('fixture');
  }
  close(): void { this.closed = true; }
}

function fixture() {
  const profile = realpathSync(mkdtempSync(join(tmpdir(), 'tm002-source-access-')));
  chmodSync(profile, 0o700);
  const a = join(profile, 'A'); const b = join(profile, 'B');
  mkdirSync(a, {mode: 0o700}); mkdirSync(b, {mode: 0o700});
  const cipher = new Cipher();
  let failWrite = false;
  const store = new SourceStore(profile, cipher, (path, text) => {
    if (failWrite) throw new Error('synthetic_atomic_write_failure');
    privateWrite(path, text);
  });
  let identity: SourceAccessIdentity = {origin: 'http://127.0.0.1:59431', accountId: 'alice-id', verified: true, epoch: 1};
  let chosen = a;
  let inoA = '29';
  let picker: null | (() => Promise<{canceled: boolean; rootPath?: string}>) = null;
  let nextPreviewBarrier: FakeHelper['previewBarrier'] = null;
  const opened: FakeHelper[] = [];
  const audit: SourceAccessAudit[] = [];
  const access = new SourceAccess({store, getIdentity: () => identity,
    chooseDirectory: async () => picker ? picker() : {canceled: false, rootPath: chosen},
    openHelper: async (path, options) => {
      const rootIdentity = {dev: '17', ino: path === a ? inoA : '30'};
      if (options?.expectedRoot && (options.expectedRoot.dev !== rootIdentity.dev || options.expectedRoot.ino !== rootIdentity.ino))
        throw new ClientError('root_changed', '根身份已改变');
      options?.onAudit?.({action: 'root_open', rootIdentity});
      const helper = new FakeHelper(path, rootIdentity.ino, options?.onAudit);
      helper.previewBarrier = nextPreviewBarrier;
      nextPreviewBarrier = null;
      opened.push(helper);
      return helper;
    }, onChange: () => {}, onAudit: event => audit.push(event)});
  return {profile, a, b, cipher, store, access, opened, audit,
    setIdentity(value: SourceAccessIdentity) { identity = value; },
    replaceRootA() { inoA = '45'; },
    select(value: string) { chosen = value; },
    setPicker(value: typeof picker) { picker = value; },
    setNextPreviewBarrier(value: FakeHelper['previewBarrier']) { nextPreviewBarrier = value; },
    failWrites(value: boolean) { failWrite = value; },
    cleanup() { access.dispose(); rmSync(profile, {recursive: true, force: true}); }};
}

async function confirmA(f: ReturnType<typeof fixture>): Promise<string> {
  await f.access.syncIdentity();
  await f.access.choose('codex');
  const selectionId = f.access.snapshot().codex.pending?.selectionId;
  assert.ok(selectionId);
  await f.access.confirm(selectionId, true, false);
  const sourceId = f.access.snapshot().codex.confirmed?.sourceId;
  assert.ok(sourceId);
  return sourceId;
}

test('TC-TM002-SECURITY-01#STALE_SELECTION rejects old native picker result after identity epoch changes', async () => {
  const f = fixture();
  try {
    await f.access.syncIdentity();
    let entered!: () => void;
    const pickerEntered = new Promise<void>(resolve => { entered = resolve; });
    let release!: (result: {canceled: boolean; rootPath?: string}) => void;
    f.setPicker(() => { entered(); return new Promise(resolve => { release = resolve; }); });
    const pending = f.access.choose('codex');
    await pickerEntered;
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'bob-id', verified: true, epoch: 2});
    await f.access.syncIdentity();
    release({canceled: false, rootPath: f.a});
    await assert.rejects(pending, (error: unknown) => error instanceof ClientError && error.code === 'source_operation_stale');
    assert.equal(f.access.snapshot().codex.pending, null);
    assert.equal(f.access.snapshot().codex.confirmed, null);
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'bob-id'}, 'codex'), {kind: 'none'});
    assert.equal(f.opened.length, 0);
    assert.deepEqual(f.audit.map(event => [event.operation, event.decision, event.reason]),
      [['picker_open', 'allowed', undefined], ['picker_result', 'denied', 'stale']]);
  } finally { f.cleanup(); }
});

test('TC-TM002-STORE-01#WRITE_FAIL_KEEP_OLD keeps A while B is pending or atomic replacement fails', async () => {
  const f = fixture();
  try {
    const sourceA = await confirmA(f);
    await f.access.refresh(sourceA);
    assert.deepEqual(f.access.snapshot().codex.candidates, [publicCandidate]);
    const file = join(f.profile, 'sources', readdirSync(join(f.profile, 'sources'))[0]);
    const original = readFileSync(file);
    f.select(f.b);
    await f.access.choose('codex');
    const pendingB = f.access.snapshot().codex.pending?.selectionId;
    assert.ok(pendingB);
    assert.equal(f.access.snapshot().codex.pending?.label, '已选择目录');
    assert.equal(f.access.snapshot().codex.confirmed?.sourceId, sourceA);
    f.failWrites(true);
    await assert.rejects(f.access.confirm(pendingB, true, false), /synthetic_atomic_write_failure/);
    assert.equal(f.access.snapshot().codex.confirmed?.sourceId, sourceA);
    assert.deepEqual(readFileSync(file), original);
    await f.access.refresh(sourceA);
    assert.deepEqual(f.access.snapshot().codex.candidates, [publicCandidate]);
    assert.equal(f.audit.some(event => event.operation === 'enumerate' &&
      event.decision === 'allowed' && event.relativeName === candidate.relativeName), true);
    f.failWrites(false);
    await f.access.confirm(pendingB, true, false);
    assert.notEqual(f.access.snapshot().codex.confirmed?.sourceId, sourceA);
    assert.equal((await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex')).kind, 'ready');
    assert.equal(JSON.stringify(f.access.snapshot()).includes(f.profile), false);
    assert.equal(JSON.stringify(f.access.snapshot()).includes('fileIdentityDigest'), false);
    assert.equal(JSON.stringify(f.audit).includes(f.profile), false);
  } finally { f.cleanup(); }
});

test('TC-TM002-SECURITY-01#REVOKE_DURING_REFRESH discards result and closes old helper', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    let reached!: () => void; let release!: () => void;
    const entered = new Promise<void>(resolve => { reached = resolve; });
    const wait = new Promise<void>(resolve => { release = resolve; });
    f.setNextPreviewBarrier({entered: reached, wait});
    const refresh = f.access.refresh(sourceId);
    await entered;
    await f.access.revoke(sourceId);
    release();
    await assert.rejects(refresh, (error: unknown) => error instanceof ClientError);
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex'), {kind: 'none'});
    assert.equal(f.opened.every(helper => helper.closed), true);
    assert.deepEqual(f.access.snapshot().codex.candidates, []);
  } finally { f.cleanup(); }
});

test('TC-TM002-CONSENT-03#FALSE_TRUE persists independent choices and invalidates scan', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    const scan = await f.access.beginCandidateScan(sourceId);
    await f.access.updateConsent(sourceId, false, true);
    const confirmed = f.access.snapshot().codex.confirmed;
    assert.ok(confirmed);
    assert.deepEqual({status: confirmed.status, collectAllowed: confirmed.collectAllowed,
                      syncIntent: confirmed.syncIntent},
                     {status: 'confirmed_paused', collectAllowed: false, syncIntent: true});
    await assert.rejects(f.access.nextCandidatePage(scan.scanId), (error: unknown) => error instanceof ClientError);
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) => error instanceof ClientError);
    const stored = await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex');
    assert.equal(stored.kind, 'ready');
    if (stored.kind === 'ready') assert.deepEqual([stored.source.collectAllowed, stored.source.syncIntent], [false, true]);
  } finally { f.cleanup(); }
});

test('TC-TM002-CONSENT-03#FALSE_FALSE confirms a paused source without scanning', async () => {
  const f = fixture();
  try {
    await f.access.syncIdentity();
    await f.access.choose('codex');
    const selectionId = f.access.snapshot().codex.pending?.selectionId;
    assert.ok(selectionId);
    await f.access.confirm(selectionId, false, false);
    const confirmed = f.access.snapshot().codex.confirmed;
    assert.ok(confirmed);
    assert.deepEqual([confirmed.status, confirmed.collectAllowed, confirmed.syncIntent],
      ['confirmed_paused', false, false]);
    await assert.rejects(f.access.refresh(confirmed.sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
    assert.deepEqual(f.access.snapshot().codex.candidates, []);
  } finally { f.cleanup(); }
});

test('TC-TM002-CONSENT-04#TURN_COLLECT_OFF_ON requires a new root check before resuming', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    await f.access.refresh(sourceId);
    assert.deepEqual(f.access.snapshot().codex.candidates, [publicCandidate]);
    const beforePause = f.opened.length;
    await f.access.updateConsent(sourceId, false, false);
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'confirmed_paused');
    assert.deepEqual(f.access.snapshot().codex.candidates, []);
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
    assert.equal(f.opened.length, beforePause);
    await f.access.updateConsent(sourceId, true, false);
    assert.equal(f.opened.length, beforePause + 1);
    assert.equal(f.opened.at(-1)?.closed, true);
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'confirmed_enabled');
    await f.access.refresh(sourceId);
    assert.deepEqual(f.access.snapshot().codex.candidates, [publicCandidate]);
  } finally { f.cleanup(); }
});

test('TC-TM002-SECURITY-01#SWITCH_DURING_REFRESH discards Alice result after switching to Bob', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    let reached!: () => void; let release!: () => void;
    const entered = new Promise<void>(resolve => { reached = resolve; });
    const wait = new Promise<void>(resolve => { release = resolve; });
    f.setNextPreviewBarrier({entered: reached, wait});
    const refresh = f.access.refresh(sourceId);
    await entered;
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'bob-id', verified: true, epoch: 2});
    await f.access.syncIdentity();
    release();
    await assert.rejects(refresh, (error: unknown) => error instanceof ClientError);
    assert.equal(f.access.snapshot().codex.confirmed, null);
    assert.deepEqual(f.access.snapshot().codex.candidates, []);
    assert.equal(f.opened.every(helper => helper.closed), true);
    assert.equal((await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex')).kind, 'ready');
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'bob-id'}, 'codex'), {kind: 'none'});
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
  } finally { f.cleanup(); }
});

test('TC-TM002-ACCESS-03 state machine latches changed root identity across restart', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    await f.access.refresh(sourceId);
    f.replaceRootA();
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'root_changed');
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'needs_reselect');
    assert.deepEqual(f.access.snapshot().codex.candidates, []);
    assert.equal((await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex')).kind,
      'needs_reselect');
    const opened = f.opened.length;
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'alice-id', verified: true, epoch: 2});
    await f.access.syncIdentity();
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'needs_reselect');
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
    assert.equal(f.opened.length, opened);
  } finally { f.cleanup(); }
});

test('TC-TM002-STORE-01#KEY_UNAVAILABLE persists a stop-reading latch', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    f.cipher.available = false;
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'needs_reselect');
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'alice-id', verified: true, epoch: 2});
    await f.access.syncIdentity();
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'needs_reselect');
    assert.equal((await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex')).kind,
      'needs_reselect');
    f.cipher.available = true;
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'alice-id', verified: true, epoch: 3});
    await f.access.syncIdentity();
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'needs_reselect');
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
    assert.equal(f.opened.length, 2);
  } finally { f.cleanup(); }
});

test('TC-TM002-STORE-01#DECRYPT_FAIL rejects a formerly healthy locator without fallback', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    f.cipher.values.clear();
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'alice-id', verified: true, epoch: 2});
    await f.access.syncIdentity();
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'needs_reselect');
    assert.equal((await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex')).kind,
      'needs_reselect');
    await assert.rejects(f.access.refresh(sourceId), (error: unknown) =>
      error instanceof ClientError && error.code === 'source_access_denied');
    assert.equal(f.opened.length, 2);
  } finally { f.cleanup(); }
});

test('TC-TM002-SECURITY-01#TOKEN rejects a fabricated selection handle', async () => {
  const f = fixture();
  try {
    await f.access.syncIdentity();
    const forged = '00000000-0000-4000-8000-000000000099';
    await assert.rejects(f.access.preview(forged), (error: unknown) =>
      error instanceof ClientError && error.code === 'invalid_selection');
    await assert.rejects(f.access.confirm(forged, true, false), (error: unknown) =>
      error instanceof ClientError && error.code === 'invalid_selection');
    assert.equal(f.opened.length, 0);
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex'),
      {kind: 'none'});
  } finally { f.cleanup(); }
});
