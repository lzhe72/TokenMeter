import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash, createHmac} from 'node:crypto';
import {chmodSync, copyFileSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {DatabaseSync} from 'node:sqlite';
import {SourceAccess, type SourceAccessAudit, type SourceAccessIdentity,
  type SourceHelperLike, type SourcePreview} from '../src/main/source-access.ts';
import {SourceStore, type SourceCipher} from '../src/main/source-store.ts';
import {UsageStore} from '../src/main/collection/usage-store.ts';
import {runClaudeCollection} from '../src/main/collection/claude-runtime.ts';

const ID = 'TC-TM004-CORE-06';
const repo = fileURLToPath(new URL('../../../', import.meta.url));
const fixture = JSON.parse(readFileSync(join(repo, 'tests/fixtures/tm004-sourceaccess-store-slice.json'), 'utf8'));
const secret = Buffer.from(fixture.secret_hex, 'hex');
type FileSpec = {label: string; relative_name: string; fixture_path: string; sha256: string; bytes: number;
  file_identity_digest: string; reference_source_key: string};
const specs = fixture.files as FileSpec[];
const tokens = specs.map((_, index) => String(index + 1).repeat(32));
const original = new Map(specs.map(spec => [spec.label, readFileSync(join(repo, spec.fixture_path))]));
const origin = 'http://127.0.0.1:59371';
const principal = fixture.principal_key as string;

function hash(bytes: Buffer): string { return createHash('sha256').update(bytes).digest('hex'); }
function referenceKey(domain: string, sourceId: string, digest?: string): string {
  const mac = createHmac('sha256', secret);
  const fields = [Buffer.from(domain), Buffer.from(sourceId), ...(digest ? [Buffer.from(digest, 'hex')] : [])];
  for (const value of fields) {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(value.length);
    mac.update(length).update(value);
  }
  return mac.digest('hex');
}
function diagnostic(t: {diagnostic(message: string): void}, step: number, actual: object): void {
  t.diagnostic(JSON.stringify({kind: 'step', case_id: ID, step, actual}));
}

class Cipher implements SourceCipher {
  async isAsyncEncryptionAvailable(): Promise<boolean> { return true; }
  async encryptStringAsync(value: string): Promise<Buffer> { return Buffer.from(`synthetic-cipher:${value}`); }
  async decryptStringAsync(value: Buffer): Promise<{result: string; shouldReEncrypt: boolean}> {
    const text = value.toString();
    if (!text.startsWith('synthetic-cipher:')) throw new Error('synthetic_cipher_rejected');
    return {result: text.slice('synthetic-cipher:'.length), shouldReEncrypt: false};
  }
}
type Counts = {begins: number; pages: number; reads: number; maxReturned: number;
  commits: number; scannedClosed: number};

class Helper implements SourceHelperLike {
  readonly rootIdentity = {dev: '17', ino: '29'};
  readonly harness: Harness;
  closed = false;
  begun = false;
  constructor(harness: Harness) { this.harness = harness; }
  async preview(): Promise<SourcePreview> {
    if (this.closed) throw new Error('helper_closed');
    return {candidates: specs.map((spec, index) => this.harness.candidate(index)),
      incomplete: false, inspectedEntries: specs.length};
  }
  async beginCandidateScan() {
    if (this.closed) throw new Error('helper_closed');
    this.begun = true;
    this.harness.counts.begins++;
    return {candidates: [0, 1].map(index => ({...this.harness.candidate(index), candidateToken: tokens[index]})),
      complete: false};
  }
  async nextCandidatePage() {
    if (this.closed) throw new Error('helper_closed');
    this.harness.counts.pages++;
    const barrier = this.harness.afterFirstPage;
    this.harness.afterFirstPage = null;
    if (barrier) await barrier();
    return {candidates: [2, 3].map(index => ({...this.harness.candidate(index), candidateToken: tokens[index]})),
      complete: true};
  }
  async readCandidateChunk(token: string, offset: number, maxBytes: number): Promise<Buffer> {
    if (this.closed) throw new Error('helper_closed');
    const index = tokens.indexOf(token);
    if (index < 0 || !Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(maxBytes)
        || maxBytes < 1 || maxBytes > 65536) throw new Error('invalid_synthetic_read');
    this.harness.counts.reads++;
    if (this.harness.earlyEof && index === 3 && offset >= fixture.helper_max_chunk_bytes)
      return Buffer.alloc(0);
    const body = this.harness.data.get(specs[index].label)!;
    const chunk = body.subarray(offset, offset + Math.min(maxBytes, fixture.helper_max_chunk_bytes));
    this.harness.counts.maxReturned = Math.max(this.harness.counts.maxReturned, chunk.length);
    return chunk;
  }
  close(): void {
    if (!this.closed && this.begun) this.harness.counts.scannedClosed++;
    this.closed = true;
  }
  async waitForExit(): Promise<void> { assert.equal(this.closed, true); }
}

class Harness {
  readonly owner: string;
  readonly profile: string;
  readonly rootPath: string;
  readonly dbPath: string;
  readonly data: Map<string, Buffer>;
  readonly counts: Counts = {begins: 0, pages: 0, reads: 0, maxReturned: 0, commits: 0, scannedClosed: 0};
  readonly audits: SourceAccessAudit[] = [];
  readonly helpers: Helper[] = [];
  readonly sourceStore: SourceStore;
  sourceId: string | null = null;
  access!: SourceAccess;
  store!: UsageStore;
  afterFirstPage: (() => Promise<void>) | null = null;
  earlyEof = false;
  accountId = 'first-synthetic-account';
  principalKey = principal;
  epoch = 1;
  verified = true;
  active = true;
  constructor(copyFrom?: Harness) {
    this.owner = mkdtempSync(join(realpathSync(tmpdir()), 'tm004-core06-'));
    chmodSync(this.owner, 0o700);
    writeFileSync(join(this.owner, 'owner.marker'), ID, {mode: 0o600});
    this.profile = join(this.owner, 'profile');
    mkdirSync(this.profile, {mode: 0o700});
    this.rootPath = copyFrom?.rootPath ?? join(this.owner, 'synthetic-root');
    if (!copyFrom) mkdirSync(this.rootPath, {mode: 0o700});
    this.dbPath = join(this.owner, 'collection', 'usage.sqlite');
    mkdirSync(join(this.owner, 'collection'), {mode: 0o700});
    this.data = new Map([...(copyFrom?.data ?? original)].map(([name, body]) => [name, Buffer.from(body)]));
    if (copyFrom) {
      cpSync(join(copyFrom.profile, 'sources'), join(this.profile, 'sources'), {recursive: true});
      chmodSync(join(this.profile, 'sources'), 0o700);
      copyFileSync(copyFrom.dbPath, this.dbPath);
      chmodSync(this.dbPath, 0o600);
      this.sourceId = copyFrom.sourceId;
      this.accountId = copyFrom.accountId;
      this.principalKey = copyFrom.principalKey;
      this.epoch = copyFrom.epoch;
    }
    this.sourceStore = new SourceStore(this.profile, new Cipher());
    this.openStore();
    this.openAccess();
  }
  candidate(index: number) {
    const spec = specs[index];
    return {relativeName: spec.relative_name, size: this.data.get(spec.label)!.length,
      mtimeMs: Date.parse('2026-10-01T00:00:00Z'), fileIdentityDigest: spec.file_identity_digest};
  }
  private openStore(): void {
    this.store = new UsageStore(this.dbPath);
    const commit = this.store.commitScanBatch.bind(this.store);
    this.store.commitScanBatch = batch => { this.counts.commits++; return commit(batch); };
  }
  private openAccess(): void {
    this.access = new SourceAccess({store: this.sourceStore,
      getIdentity: (): SourceAccessIdentity => ({origin, accountId: this.accountId,
        verified: this.verified && this.active, epoch: this.epoch}),
      chooseDirectory: async () => ({canceled: false, rootPath: this.rootPath}),
      openHelper: async (path, options) => {
        assert.equal(path, this.rootPath);
        if (options?.expectedRoot) assert.deepEqual(options.expectedRoot, {dev: '17', ino: '29'});
        const helper = new Helper(this); this.helpers.push(helper); return helper;
      }, onChange: () => {}, onAudit: event => { this.audits.push(event); }});
  }
  async confirm(): Promise<string> {
    await this.access.syncIdentity();
    await this.access.choose('claude_code');
    const pending = this.access.snapshot().claude_code.pending?.selectionId;
    assert.ok(pending);
    await this.access.preview(pending);
    assert.equal(this.access.snapshot().claude_code.pending?.candidates.length, 4);
    await this.access.confirm(pending, true, false);
    const sourceId = this.access.snapshot().claude_code.confirmed?.sourceId;
    assert.ok(sourceId);
    this.sourceId = sourceId;
    return sourceId;
  }
  async run(sourceId = this.sourceId!): Promise<unknown> {
    return runClaudeCollection(sourceId, {access: this.access, store: this.store, secret,
      account: () => ({principalKey: this.principalKey, epoch: this.epoch,
        verified: this.verified, active: this.active, mustChangePassword: false})});
  }
  async restart(): Promise<void> {
    this.close();
    this.openStore(); this.openAccess();
    await this.access.syncIdentity();
  }
  close(): void { this.access.dispose(); this.store.close(); }
  cleanup(): void {
    assert.equal(readFileSync(join(this.owner, 'owner.marker'), 'utf8'), ID);
    rmSync(this.owner, {recursive: true, force: true});
    assert.equal(existsSync(this.owner), false);
  }
}

function state(path: string) {
  const db = new DatabaseSync(path, {readOnly: true});
  try {
    const total = db.prepare(`SELECT COUNT(*) calls, COALESCE(SUM(input_tokens),0) input,
      COALESCE(SUM(output_tokens),0) output FROM usage_event WHERE source='claude_code'`).get()!;
    return {calls: Number(total.calls), input: Number(total.input), output: Number(total.output),
      cursors: db.prepare(`SELECT source_key, root_key, file_identity, committed_byte_offset, prefix_mac
        FROM source_cursor ORDER BY source_key`).all().map(row => ({sourceKey: String(row.source_key),
          rootKey: String(row.root_key), fileIdentity: String(row.file_identity),
          offset: Number(row.committed_byte_offset), prefixMac: String(row.prefix_mac)})),
      coverage: db.prepare('SELECT root_key, missing_before, scan_incomplete FROM coverage').all()
        .map(row => ({rootKey: String(row.root_key), missingBefore: Number(row.missing_before),
          scanIncomplete: Number(row.scan_incomplete)})),
      diagnostics: db.prepare('SELECT code, COUNT(*) count FROM collection_diagnostic GROUP BY code ORDER BY code').all()
        .map(row => ({code: String(row.code), count: Number(row.count)})),
      marker: db.prepare('SELECT key_marker FROM identity_key_state').get()?.key_marker ?? null};
  } finally { db.close(); }
}
function privateDatabase(harness: Harness, returned?: unknown): void {
  assert.equal(statSync(harness.owner).mode & 0o777, 0o700);
  assert.equal(statSync(harness.profile).mode & 0o777, 0o700);
  assert.equal(statSync(harness.dbPath).mode & 0o777, 0o600);
  const bytes = [harness.dbPath, `${harness.dbPath}-wal`, `${harness.dbPath}-shm`]
    .filter(existsSync).map(file => readFileSync(file).toString('utf8')).join('\n');
  const rawIds = specs.flatMap(spec => readFileSync(join(repo, spec.fixture_path), 'utf8')
    .trim().split('\n').map(line => JSON.parse(line)).flatMap(row =>
      [row.uuid, row.parentUuid, row.sessionId, row.agentId, row.message?.id]));
  for (const value of [...rawIds, ...specs.map(spec => spec.relative_name), harness.rootPath,
    harness.sourceId, fixture.append.new_call_id, fixture.secret_hex])
    if (typeof value === 'string' && value.length >= 8) {
      assert.equal(bytes.includes(value), false, value);
      if (returned !== undefined) assert.equal(JSON.stringify(returned).includes(value), false, value);
    }
}
function expectedKeys(sourceId: string): string[] {
  return specs.map(spec => referenceKey('claude-file-v1', sourceId, spec.file_identity_digest)).sort();
}
function checkCursors(harness: Harness, sourceId: string, offsets: number[]): void {
  const actual = state(harness.dbPath);
  const rootKey = referenceKey('claude-root-v1', sourceId);
  assert.deepEqual(actual.cursors.map(row => row.sourceKey).sort(), expectedKeys(sourceId));
  for (const [index, spec] of specs.entries()) {
    const key = referenceKey('claude-file-v1', sourceId, spec.file_identity_digest);
    const cursor = actual.cursors.find(row => row.sourceKey === key);
    assert.ok(cursor);
    assert.equal(cursor.rootKey, rootKey);
    assert.equal(cursor.fileIdentity, key);
    assert.equal(cursor.offset, offsets[index]);
  }
  assert.deepEqual(actual.coverage, [{rootKey, missingBefore: 0, scanIncomplete: 0}]);
}

test('TC-TM004-CORE-06 confirmed Claude SourceAccess commits owned SQLite generations', async t => {
  const owners: Harness[] = [];
  const main = new Harness(); owners.push(main);
  let mainOpen = true;
  try {
    assert.equal(secret.length, 32);
    for (const spec of specs) {
      const bytes = original.get(spec.label)!;
      assert.equal(bytes.length, spec.bytes);
      assert.equal(hash(bytes), spec.sha256);
      assert.equal(referenceKey('claude-file-v1', fixture.reference_source_id, spec.file_identity_digest),
        spec.reference_source_key);
    }
    assert.equal(referenceKey('claude-root-v1', fixture.reference_source_id), fixture.reference_root_key);
    const before = state(main.dbPath);
    await assert.rejects(main.run(fixture.unconfirmed_source_id), /source_not_authorized/);
    assert.deepEqual([main.counts.begins, main.counts.reads, main.counts.commits], [0, 0, 0]);
    assert.equal(before.calls, 0); assert.equal(before.cursors.length, 0);
    const sourceId = await main.confirm();
    assert.match(sourceId, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    assert.equal(main.access.snapshot().claude_code.confirmed?.collectAllowed, true);
    assert.equal(state(main.dbPath).calls, 0);
    diagnostic(t, 1, {unconfirmed_rejected: true, preconfirm_begin: 0, preconfirm_reads: 0,
      preconfirm_commits: 0, confirmed_source_id: sourceId,
      reference_root_key: fixture.reference_root_key, expected_file_keys: expectedKeys(sourceId), db_empty: true});

    const first = await main.run(sourceId) as {summary: {callCount: number; inputTokens: number;
      outputTokens: number; totalTokens: number; scanIncomplete: boolean}};
    const initial = state(main.dbPath);
    assert.deepEqual([first.summary.callCount, first.summary.inputTokens,
      first.summary.outputTokens, first.summary.totalTokens, first.summary.scanIncomplete],
      [5, 85, 32, 117, false]);
    assert.deepEqual([initial.calls, initial.input, initial.output], [5, 85, 32]);
    assert.deepEqual([main.counts.begins, main.counts.pages, main.counts.commits], [1, 1, 1]);
    assert.ok(main.counts.reads > 4);
    assert.ok(main.counts.maxReturned <= fixture.helper_max_chunk_bytes);
    checkCursors(main, sourceId, specs.map(spec => spec.bytes));
    assert.equal(initial.diagnostics.some(item => item.code === 'unverified_parent'), false);
    privateDatabase(main, first);
    diagnostic(t, 2, {calls: initial.calls, input: initial.input, output: initial.output,
      total: initial.input + initial.output, cursors: initial.cursors.length,
      commits: main.counts.commits, pages: main.counts.pages,
      max_returned_bytes: main.counts.maxReturned, coverage: initial.coverage,
      copied_fork_counted_once: true, agent_parent_verified: true, privacy_sentinels_absent: true});

    await main.restart();
    assert.equal(main.access.snapshot().claude_code.confirmed?.sourceId, sourceId);
    assert.equal(main.counts.begins, 1);
    await main.run(sourceId);
    const replay = state(main.dbPath);
    assert.deepEqual([replay.calls, replay.input, replay.output], [5, 85, 32]);
    assert.deepEqual(replay.cursors, initial.cursors);
    assert.deepEqual(replay.coverage, initial.coverage);
    assert.equal(main.counts.commits, 1);
    diagnostic(t, 3, {source_id_preserved: true, calls: replay.calls, total: replay.input + replay.output,
      cursor_count: replay.cursors.length, new_commits: 0, coverage_preserved: true});

    const append = readFileSync(join(repo, fixture.append.fixture_path));
    assert.equal(hash(append), fixture.append.sha256);
    assert.equal(append.length, fixture.append.bytes);
    main.data.set('main', Buffer.concat([main.data.get('main')!, append]));
    await main.run(sourceId);
    const appended = state(main.dbPath);
    assert.deepEqual([appended.calls, appended.input, appended.output], [6, 135, 37]);
    assert.equal(main.counts.commits, 2);
    checkCursors(main, sourceId, specs.map(spec => spec.bytes + (spec.label === 'main' ? append.length : 0)));
    assert.equal(appended.diagnostics.some(item => item.code === 'cursor_reset'), false);
    await main.run(sourceId);
    assert.deepEqual(state(main.dbPath), appended);
    assert.equal(main.counts.commits, 2);
    privateDatabase(main);
    diagnostic(t, 4, {calls: appended.calls, input: appended.input, output: appended.output,
      total: appended.input + appended.output, new_calls: 1, main_offset: specs[0].bytes + append.length,
      other_offsets_unchanged: true, cursor_reset: false, replay_new_commits: 0});

    main.close(); mainOpen = false;
    for (const mode of fixture.negative_barriers as string[]) {
      const fault = new Harness(main); owners.push(fault);
      await fault.access.syncIdentity();
      assert.equal(fault.access.snapshot().claude_code.confirmed?.sourceId, sourceId);
      const beforeFault = state(fault.dbPath);
      if (mode === 'revoke_after_first_page') fault.afterFirstPage = async () => fault.access.revoke(sourceId);
      else if (mode === 'switch_principal_after_first_page') fault.afterFirstPage = async () => {
        fault.accountId = 'second-synthetic-account'; fault.principalKey = '5'.repeat(64); fault.epoch++;
        await fault.access.syncIdentity();
      };
      else if (mode === 'early_eof_in_agent_sub') fault.earlyEof = true;
      else assert.fail(`Unexpected frozen fault: ${mode}`);
      await assert.rejects(fault.run(sourceId));
      assert.equal(fault.counts.commits, 0);
      assert.ok(fault.counts.scannedClosed >= 1);
      assert.ok(fault.audits.some(event => event.operation === 'cancel' && event.tool === 'claude_code'));
      if (mode !== 'early_eof_in_agent_sub') assert.ok(fault.audits.some(event =>
        event.operation === 'cancel' && event.reason === 'capability_invalidated'));
      assert.deepEqual(state(fault.dbPath), beforeFault);
      if (mode === 'switch_principal_after_first_page') {
        const db = new DatabaseSync(fault.dbPath, {readOnly: true});
        try { assert.equal(Number(db.prepare('SELECT COUNT(*) n FROM usage_event WHERE principal_key=?')
          .get(fault.principalKey)!.n), 0); } finally { db.close(); }
      }
      privateDatabase(fault);
      fault.close();
    }
    diagnostic(t, 5, {faults: fixture.negative_barriers, commit_calls_each: 0,
      scan_closed_each: true, old_calls_each: 6, old_total_each: 172,
      cursors_and_coverage_unchanged_each: true, second_principal_events: 0,
      source_audit_cancel_each: true, owner_cleanup_pending: true});
  } finally {
    if (mainOpen) main.close();
    for (const owner of owners.reverse()) owner.cleanup();
    t.diagnostic(JSON.stringify({kind: 'cleanup', case_id: ID, owned_root_removed: true}));
  }
});
