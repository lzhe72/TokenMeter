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
  pauseNextEncrypt: null | {entered(): void; wait: Promise<void>} = null;
  readonly values = new Map<string, string>();
  async isAsyncEncryptionAvailable(): Promise<boolean> { return this.available; }
  async encryptStringAsync(value: string): Promise<Buffer> {
    const pause = this.pauseNextEncrypt;
    this.pauseNextEncrypt = null;
    if (pause) { pause.entered(); await pause.wait; }
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
  exitBarrier: null | {entered(): void; wait: Promise<void>} = null;
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
  async waitForExit(): Promise<void> {
    if (!this.closed) throw new Error('helper_not_closed');
    const barrier = this.exitBarrier;
    if (barrier) { barrier.entered(); await barrier.wait; }
  }
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
  let nextOpenBarrier: FakeHelper['previewBarrier'] = null;
  let changeListener: null | (() => void) = null;
  let identityListener: null | (() => void) = null;
  const opened: FakeHelper[] = [];
  const audit: SourceAccessAudit[] = [];
  const access = new SourceAccess({store, getIdentity: () => { identityListener?.(); return identity; },
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
      const openBarrier = nextOpenBarrier;
      nextOpenBarrier = null;
      if (openBarrier) { openBarrier.entered(); await openBarrier.wait; }
      return helper;
    }, onChange: () => changeListener?.(), onAudit: event => audit.push(event)});
  return {profile, a, b, cipher, store, access, opened, audit,
    setIdentity(value: SourceAccessIdentity) { identity = value; },
    replaceRootA() { inoA = '45'; },
    select(value: string) { chosen = value; },
    setPicker(value: typeof picker) { picker = value; },
    setNextPreviewBarrier(value: FakeHelper['previewBarrier']) { nextPreviewBarrier = value; },
    setNextOpenBarrier(value: FakeHelper['previewBarrier']) { nextOpenBarrier = value; },
    onChange(value: typeof changeListener) { changeListener = value; },
    onIdentity(value: typeof identityListener) { identityListener = value; },
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

test('TC-TM002-SECURITY-01#REPLACE_EXIT_BARRIER keeps A committed until its reader exits', async () => {
  const f = fixture();
  try {
    const sourceA = await confirmA(f);
    const scan = await f.access.beginCandidateScan(sourceA);
    const oldReader = f.opened.at(-1);
    assert.ok(oldReader);
    f.select(f.b);
    await f.access.choose('codex');
    const pendingB = f.access.snapshot().codex.pending?.selectionId;
    assert.ok(pendingB);
    let reached!: () => void; let release!: () => void;
    const entered = new Promise<void>(resolve => { reached = resolve; });
    const wait = new Promise<void>(resolve => { release = resolve; });
    oldReader.exitBarrier = {entered: reached, wait};
    let committed = false;
    const replacement = f.access.confirm(pendingB, true, false).then(() => { committed = true; });
    await entered;
    assert.equal(oldReader.closed, true);
    assert.equal(committed, false);
    assert.equal(f.access.snapshot().codex.confirmed?.sourceId, sourceA);
    const storedBefore = await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex');
    assert.equal(storedBefore.kind, 'ready');
    if (storedBefore.kind === 'ready') assert.equal(storedBefore.source.sourceId, sourceA);
    release(); await replacement;
    assert.equal(committed, true);
    assert.notEqual(f.access.snapshot().codex.confirmed?.sourceId, sourceA);
    await assert.rejects(f.access.nextCandidatePage(scan.scanId), (cause: unknown) =>
      cause instanceof ClientError && cause.code === 'invalid_scan');
  } finally { f.cleanup(); }
});

test('TC-TM002-SECURITY-01#OVERLAPPING_STOP_BARRIER does not finish revoke before a prior stop exits', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    await f.access.beginCandidateScan(sourceId);
    const oldReader = f.opened.at(-1);
    assert.ok(oldReader);
    let entered!: () => void; let release!: () => void;
    const stopping = new Promise<void>(resolve => { entered = resolve; });
    const exitWait = new Promise<void>(resolve => { release = resolve; });
    oldReader.exitBarrier = {entered, wait: exitWait};
    const consentResult = f.access.updateConsent(sourceId, false, false).then(() => null, cause => cause);
    await stopping;
    assert.equal(oldReader.closed, true);
    let revokedLocally!: () => void;
    const localRevocation = new Promise<void>(resolve => { revokedLocally = resolve; });
    f.onChange(() => {
      if (f.access.snapshot().codex.confirmed === null) revokedLocally();
    });
    let completed = false;
    const revocation = f.access.revoke(sourceId).then(() => { completed = true; });
    await localRevocation;
    await new Promise<void>(resolve => setImmediate(resolve));
    assert.equal(completed, false);
    release();
    await revocation;
    assert.equal(completed, true);
    const cause = await consentResult;
    assert.equal(cause instanceof ClientError, true);
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex'),
      {kind: 'none'});
  } finally { f.cleanup(); }
});

test('TC-TM002-SECURITY-01#IDENTITY_STOP_BARRIER waits for an earlier retiring reader', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    await f.access.beginCandidateScan(sourceId);
    const oldReader = f.opened.at(-1);
    assert.ok(oldReader);
    let entered!: () => void; let release!: () => void;
    const stopping = new Promise<void>(resolve => { entered = resolve; });
    const exitWait = new Promise<void>(resolve => { release = resolve; });
    oldReader.exitBarrier = {entered, wait: exitWait};
    const consentResult = f.access.updateConsent(sourceId, false, false).then(() => null, cause => cause);
    await stopping;
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'bob-id', verified: true, epoch: 2});
    let switched = false;
    const switching = f.access.syncIdentity().then(() => { switched = true; });
    await new Promise<void>(resolve => setImmediate(resolve));
    assert.equal(switched, false);
    assert.equal(f.access.snapshot().codex.confirmed, null);
    release();
    await switching;
    assert.equal(switched, true);
    assert.equal((await consentResult) instanceof ClientError, true);
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'bob-id'}, 'codex'),
      {kind: 'none'});
  } finally { f.cleanup(); }
});

test('TC-TM002-SECURITY-01#REPLACEMENT_OWNER keeps a new identity replacement locked', async () => {
  const f = fixture();
  let releaseOld = () => {}; let releaseNew = () => {};
  try {
    await confirmA(f);
    f.select(f.b); await f.access.choose('codex');
    const oldPending = f.access.snapshot().codex.pending?.selectionId;
    assert.ok(oldPending);
    let oldEntered!: () => void;
    const oldEncrypting = new Promise<void>(resolve => { oldEntered = resolve; });
    const oldGate = new Promise<void>(resolve => { releaseOld = resolve; });
    f.cipher.pauseNextEncrypt = {entered: oldEntered, wait: oldGate};
    const oldResult = f.access.confirm(oldPending, true, false).then(() => null, cause => cause);
    await oldEncrypting;
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'bob-id', verified: true, epoch: 2});
    await f.access.syncIdentity();
    await f.access.choose('codex');
    const bobPending = f.access.snapshot().codex.pending?.selectionId;
    const bobHelper = f.opened.at(-1);
    assert.ok(bobPending); assert.ok(bobHelper);
    let bobEntered!: () => void;
    const bobStopping = new Promise<void>(resolve => { bobEntered = resolve; });
    const bobGate = new Promise<void>(resolve => { releaseNew = resolve; });
    bobHelper.exitBarrier = {entered: bobEntered, wait: bobGate};
    const bobResult = f.access.confirm(bobPending, true, false).then(() => null, cause => cause);
    await bobStopping;
    releaseOld();
    const stale = await oldResult;
    assert.equal(stale instanceof ClientError && stale.code === 'source_operation_stale', true);
    await assert.rejects(f.access.choose('codex'), (cause: unknown) =>
      cause instanceof ClientError && cause.code === 'operation_busy');
    releaseNew();
    assert.equal(await bobResult, null);
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'confirmed_enabled');
  } finally { releaseOld(); releaseNew(); f.cleanup(); }
});

test('TC-TM002-SECURITY-01#UPDATE_OWNER keeps a new identity consent update locked', async () => {
  const f = fixture();
  let releaseOld = () => {}; let releaseNew = () => {};
  try {
    const aliceSourceId = await confirmA(f);
    const bobSourceId = randomUUID();
    await f.store.commit({origin: 'http://127.0.0.1:59431', accountId: 'bob-id'},
      {sourceId: bobSourceId, tool: 'codex', rootPath: f.b, rootDev: '17', rootIno: '30',
        collectAllowed: true, syncIntent: false});
    let oldEntered!: () => void;
    const oldEncrypting = new Promise<void>(resolve => { oldEntered = resolve; });
    const oldGate = new Promise<void>(resolve => { releaseOld = resolve; });
    f.cipher.pauseNextEncrypt = {entered: oldEntered, wait: oldGate};
    const oldResult = f.access.updateConsent(aliceSourceId, true, true).then(() => null, cause => cause);
    await oldEncrypting;
    f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'bob-id', verified: true, epoch: 2});
    await f.access.syncIdentity();
    assert.equal(f.access.snapshot().codex.confirmed?.sourceId, bobSourceId);
    let bobEntered!: () => void;
    const bobEncrypting = new Promise<void>(resolve => { bobEntered = resolve; });
    const bobGate = new Promise<void>(resolve => { releaseNew = resolve; });
    f.cipher.pauseNextEncrypt = {entered: bobEntered, wait: bobGate};
    const bobResult = f.access.updateConsent(bobSourceId, true, true).then(() => null, cause => cause);
    await bobEncrypting;
    releaseOld();
    const stale = await oldResult;
    assert.equal(stale instanceof ClientError && stale.code === 'source_operation_stale', true);
    await assert.rejects(f.access.choose('codex'), (cause: unknown) =>
      cause instanceof ClientError && cause.code === 'operation_busy');
    releaseNew();
    assert.equal(await bobResult, null);
    assert.equal(f.access.snapshot().codex.confirmed?.sourceId, bobSourceId);
    assert.equal(f.access.snapshot().codex.confirmed?.syncIntent, true);
  } finally { releaseOld(); releaseNew(); f.cleanup(); }
});

test('TC-TM002-CONSENT-03#PENDING_EXIT_BARRIER stops an in-flight preview before paused consent commits', async () => {
  const f = fixture();
  try {
    await f.access.syncIdentity();
    await f.access.choose('codex');
    const pending = f.access.snapshot().codex.pending?.selectionId;
    assert.ok(pending);
    const pendingHelper = f.opened.at(-1);
    assert.ok(pendingHelper);
    let previewReached!: () => void; let releasePreview!: () => void;
    const previewEntered = new Promise<void>(resolve => { previewReached = resolve; });
    const previewWait = new Promise<void>(resolve => { releasePreview = resolve; });
    pendingHelper.previewBarrier = {entered: previewReached, wait: previewWait};
    const previewResult = f.access.preview(pending).then(() => null, cause => cause);
    await previewEntered;
    let exitReached!: () => void; let releaseExit!: () => void;
    const exitEntered = new Promise<void>(resolve => { exitReached = resolve; });
    const exitWait = new Promise<void>(resolve => { releaseExit = resolve; });
    pendingHelper.exitBarrier = {entered: exitReached, wait: exitWait};
    let confirmed = false;
    const confirmation = f.access.confirm(pending, false, false).then(() => { confirmed = true; });
    await exitEntered;
    assert.equal(pendingHelper.closed, true);
    assert.equal(confirmed, false);
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex'),
      {kind: 'none'});
    releaseExit(); await confirmation;
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'confirmed_paused');
    releasePreview();
    const cause = await previewResult;
    assert.equal(cause instanceof ClientError && cause.code === 'source_operation_stale', true);
    assert.deepEqual(f.audit.filter(event => event.operation === 'enumerate'), []);
  } finally { f.cleanup(); }
});

test('TC-TM002-CONSENT-04#UPDATE_REPLACE_SERIAL keeps A update and B confirmation from racing', async () => {
  const f = fixture();
  try {
    const sourceA = await confirmA(f);
    const scan = await f.access.beginCandidateScan(sourceA);
    const oldReader = f.opened.at(-1);
    assert.ok(oldReader);
    f.select(f.b); await f.access.choose('codex');
    const pendingB = f.access.snapshot().codex.pending?.selectionId;
    assert.ok(pendingB);
    let reached!: () => void; let release!: () => void;
    const entered = new Promise<void>(resolve => { reached = resolve; });
    const wait = new Promise<void>(resolve => { release = resolve; });
    oldReader.exitBarrier = {entered: reached, wait};
    const update = f.access.updateConsent(sourceA, true, true);
    await entered;
    await assert.rejects(f.access.confirm(pendingB, true, false), (cause: unknown) =>
      cause instanceof ClientError && cause.code === 'operation_busy');
    assert.equal(f.access.snapshot().codex.confirmed?.sourceId, sourceA);
    const storedBefore = await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex');
    assert.equal(storedBefore.kind, 'ready');
    if (storedBefore.kind === 'ready') assert.equal(storedBefore.source.sourceId, sourceA);
    release(); await update;
    assert.equal(f.access.snapshot().codex.confirmed?.status, 'confirmed_enabled');
    assert.equal(f.access.snapshot().codex.confirmed?.syncIntent, true);
    await assert.rejects(f.access.nextCandidatePage(scan.scanId));
    assert.equal(f.access.snapshot().codex.pending?.selectionId, pendingB);
    await f.access.confirm(pendingB, true, false);
    const sourceB = f.access.snapshot().codex.confirmed?.sourceId;
    assert.ok(sourceB); assert.notEqual(sourceB, sourceA);
    const storedAfter = await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex');
    assert.equal(storedAfter.kind, 'ready');
    if (storedAfter.kind === 'ready') assert.equal(storedAfter.source.sourceId, sourceB);
  } finally { f.cleanup(); }
});

test('TC-TM002-SECURITY-01#REVOKE_OPEN_BARRIER waits for an in-flight reader to close', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    let openReached!: () => void; let releaseOpen!: () => void;
    const opening = new Promise<void>(resolve => { openReached = resolve; });
    const openWait = new Promise<void>(resolve => { releaseOpen = resolve; });
    f.setNextOpenBarrier({entered: openReached, wait: openWait});
    const scan = f.access.beginCandidateScan(sourceId);
    const scanResult = scan.then(() => null, cause => cause);
    await opening;
    const openingReader = f.opened.at(-1);
    assert.ok(openingReader);
    let revokedLocally!: () => void;
    const localRevocation = new Promise<void>(resolve => { revokedLocally = resolve; });
    f.onChange(() => {
      if (f.access.snapshot().codex.confirmed === null) revokedLocally();
    });
    let revoked = false;
    const revocation = f.access.revoke(sourceId).then(() => { revoked = true; });
    await localRevocation;
    assert.equal(revoked, false);
    assert.equal(f.access.snapshot().codex.confirmed, null);
    releaseOpen();
    await revocation;
    assert.equal(openingReader.closed, true);
    assert.equal(revoked, true);
    const cause = await scanResult;
    assert.equal(cause instanceof ClientError && cause.code === 'source_operation_stale', true);
    assert.deepEqual(await f.store.load({origin: 'http://127.0.0.1:59431', accountId: 'alice-id'}, 'codex'),
      {kind: 'none'});
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

test('TC-TM002-ACCESS-06#COMMIT_GUARD invalidates synchronous commit after revoke or scan close', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    const first = await f.access.beginCandidateScan(sourceId);
    const guard = await f.access.commitGuard(first.scanId);
    assert.doesNotThrow(guard);
    await f.access.cancelScan(first.scanId);
    assert.throws(guard, (cause: unknown) =>
      cause instanceof ClientError && cause.code === 'source_operation_stale');
    const second = await f.access.beginCandidateScan(sourceId);
    const revokedGuard = await f.access.commitGuard(second.scanId);
    await f.access.revoke(sourceId);
    assert.throws(revokedGuard, (cause: unknown) =>
      cause instanceof ClientError && cause.code === 'source_operation_stale');
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

test('TC-TM002-SECURITY-01#SWITCH_BEFORE_OPEN cannot start an old-root helper after invalidation', async () => {
  const f = fixture();
  try {
    const sourceId = await confirmA(f);
    const openedBefore = f.opened.length;
    const originalLoad = f.store.load.bind(f.store);
    let armSwitch = false;
    let switched: Promise<void> | null = null;
    f.store.load = async (identity, tool) => {
      const record = await originalLoad(identity, tool);
      if (identity.accountId === 'alice-id' && tool === 'codex') armSwitch = true;
      return record;
    };
    f.onIdentity(() => {
      if (!armSwitch) return;
      armSwitch = false;
      queueMicrotask(() => {
        f.setIdentity({origin: 'http://127.0.0.1:59431', accountId: 'bob-id', verified: true, epoch: 2});
        switched = f.access.syncIdentity();
      });
    });
    await assert.rejects(f.access.refresh(sourceId), (cause: unknown) =>
      cause instanceof ClientError && cause.code === 'source_operation_stale');
    if (switched) await switched;
    assert.equal(f.opened.length, openedBefore);
    assert.equal(f.access.snapshot().codex.confirmed, null);
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
