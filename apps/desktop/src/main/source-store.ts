import { createHash } from 'node:crypto';
import { isAbsolute, join, normalize } from 'node:path';
import { unlinkSync } from 'node:fs';
import { privateDirectory, privateRead, privateWrite } from './storage.ts';
import { canonicalOrigin, ClientError } from './validation.ts';

export type SourceTool = 'codex' | 'claude_code';
export type SourceIdentity = { origin: string; accountId: string };
export type ConfirmedSource = {
  sourceId: string;
  tool: SourceTool;
  rootPath: string;
  rootDev: string;
  rootIno: string;
  collectAllowed: boolean;
  syncIntent: boolean;
};
export type StoredSource =
  | { kind: 'none' }
  | { kind: 'ready'; source: ConfirmedSource }
  | { kind: 'needs_reselect'; reason: string; sourceId: string | null };

export type SourceCipher = {
  isAsyncEncryptionAvailable(): Promise<boolean>;
  encryptStringAsync(value: string): Promise<Buffer>;
  decryptStringAsync(value: Buffer): Promise<{ result: string; shouldReEncrypt: boolean }>;
};

type DiskSource = {
  schema_version: 1;
  identity_hash: string;
  source_id: string;
  tool: SourceTool;
  root_dev: string;
  root_ino: string;
  collect_allowed: boolean;
  sync_intent: boolean;
  ciphertext: string;
  state: 'confirmed' | 'needs_reselect';
  disable_reason?: string;
};

const SOURCE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const FILE_ID = /^[0-9]{1,32}$/;
const DISABLE_REASONS = new Set(['root_changed', 'access_denied', 'tree_changed', 'unsafe_root', 'source_unavailable']);
function validTool(value: unknown): value is SourceTool { return value === 'codex' || value === 'claude_code'; }
function validSource(source: ConfirmedSource): boolean {
  return (!!source && typeof source === 'object' && SOURCE_ID.test(source.sourceId) && validTool(source.tool) &&
    typeof source.rootPath === 'string' && source.rootPath.length > 0 && source.rootPath.length <= 4096 &&
    isAbsolute(source.rootPath) && normalize(source.rootPath) === source.rootPath && !source.rootPath.includes('\0') &&
    FILE_ID.test(source.rootDev) && FILE_ID.test(source.rootIno) &&
    typeof source.collectAllowed === 'boolean' && typeof source.syncIntent === 'boolean');
}

export class SourceStore {
  readonly #profile: string;
  readonly #cipher: SourceCipher;
  readonly #writeRecord: (path: string, text: string) => void;
  constructor(profile: string, cipher: SourceCipher, writeRecord: (path: string, text: string) => void = privateWrite) {
    this.#profile = profile;
    this.#cipher = cipher;
    this.#writeRecord = writeRecord;
  }
  async #available(): Promise<boolean> {
    try { return await this.#cipher.isAsyncEncryptionAvailable(); }
    catch { return false; }
  }
  #path(identity: SourceIdentity, tool: SourceTool): {path: string; hash: string} {
    if (!validTool(tool) || typeof identity.accountId !== 'string' || !identity.accountId || identity.accountId.length > 128)
      throw new ClientError('invalid_source_identity', '来源身份无效');
    const origin = canonicalOrigin(identity.origin);
    const hash = createHash('sha256').update(JSON.stringify([origin, identity.accountId, tool])).digest('hex');
    return {path: join(privateDirectory(join(privateDirectory(this.#profile), 'sources')), `${hash}.json`), hash};
  }
  async load(identity: SourceIdentity, tool: SourceTool): Promise<StoredSource> {
    const {path, hash} = this.#path(identity, tool);
    let raw: string | null;
    try { raw = privateRead(path); }
    catch { return {kind: 'needs_reselect', reason: 'unsafe_record', sourceId: null}; }
    if (raw === null) return {kind: 'none'};
    let data: unknown;
    try { data = JSON.parse(raw); }
    catch { return {kind: 'needs_reselect', reason: 'corrupt_record', sourceId: null}; }
    const item = data as Partial<DiskSource> | null;
    const sourceId = typeof item?.source_id === 'string' && SOURCE_ID.test(item.source_id) ? item.source_id : null;
    if (!item || item.schema_version !== 1 || item.identity_hash !== hash || item.tool !== tool ||
      !sourceId || typeof item.root_dev !== 'string' || !FILE_ID.test(item.root_dev) ||
      typeof item.root_ino !== 'string' || !FILE_ID.test(item.root_ino) ||
      typeof item.collect_allowed !== 'boolean' || typeof item.sync_intent !== 'boolean' ||
      typeof item.ciphertext !== 'string' || item.ciphertext.length < 4 || item.ciphertext.length > 32768 ||
      (item.state !== 'confirmed' && item.state !== 'needs_reselect') ||
      (item.state === 'needs_reselect' && !DISABLE_REASONS.has(item.disable_reason ?? '')) ||
      !/^[A-Za-z0-9+/]+={0,2}$/.test(item.ciphertext))
      return {kind: 'needs_reselect', reason: 'corrupt_record', sourceId};
    const bytes = Buffer.from(item.ciphertext, 'base64');
    if (!bytes.length || bytes.toString('base64') !== item.ciphertext)
      return {kind: 'needs_reselect', reason: 'corrupt_record', sourceId};
    if (item.state === 'needs_reselect')
      return {kind: 'needs_reselect', reason: item.disable_reason!, sourceId};
    if (!await this.#available()) return {kind: 'needs_reselect', reason: 'key_unavailable', sourceId};
    try {
      const decrypted = await this.#cipher.decryptStringAsync(bytes);
      const source: ConfirmedSource = {
        sourceId, tool, rootPath: decrypted.result, rootDev: item.root_dev,
        rootIno: item.root_ino, collectAllowed: item.collect_allowed, syncIntent: item.sync_intent
      };
      if (!validSource(source)) return {kind: 'needs_reselect', reason: 'corrupt_locator', sourceId};
      if (decrypted.shouldReEncrypt) await this.commit(identity, source);
      return {kind: 'ready', source};
    } catch { return {kind: 'needs_reselect', reason: 'decrypt_failed', sourceId}; }
  }
  async commit(identity: SourceIdentity, source: ConfirmedSource, stillCurrent: () => boolean = () => true): Promise<void> {
    if (!validSource(source)) throw new ClientError('invalid_source_record', '来源记录无效');
    const {path, hash} = this.#path(identity, source.tool);
    if (!await this.#available()) throw new ClientError('source_key_unavailable', '本机密钥暂不可用');
    let ciphertext: Buffer;
    try { ciphertext = await this.#cipher.encryptStringAsync(source.rootPath); }
    catch { throw new ClientError('source_key_unavailable', '本机密钥暂不可用'); }
    if (!stillCurrent()) throw new ClientError('source_operation_stale', '来源操作已失效');
    if (!Buffer.isBuffer(ciphertext) || !ciphertext.length || ciphertext.length > 24576)
      throw new ClientError('source_key_unavailable', '本机密钥暂不可用');
    const item: DiskSource = {
      schema_version: 1, identity_hash: hash, source_id: source.sourceId, tool: source.tool,
      root_dev: source.rootDev, root_ino: source.rootIno,
      collect_allowed: source.collectAllowed, sync_intent: source.syncIntent,
      ciphertext: ciphertext.toString('base64'), state: 'confirmed'
    };
    this.#writeRecord(path, JSON.stringify(item));
  }
  markNeedsReselect(identity: SourceIdentity, tool: SourceTool, sourceId: string, reason: string): 'latched' | 'removed' {
    if (!DISABLE_REASONS.has(reason)) throw new ClientError('invalid_source_reason', '来源失效原因无效');
    const {path, hash} = this.#path(identity, tool);
    const raw = privateRead(path);
    if (raw === null) throw new ClientError('source_operation_stale', '来源操作已失效');
    let data: Partial<DiskSource> | null;
    try { data = JSON.parse(raw) as Partial<DiskSource> | null; }
    catch { throw new ClientError('source_operation_stale', '来源操作已失效'); }
    if (!data || data.schema_version !== 1 || data.identity_hash !== hash || data.tool !== tool ||
        data.source_id !== sourceId || !SOURCE_ID.test(sourceId))
      throw new ClientError('source_operation_stale', '来源操作已失效');
    const updated = {...data, state: 'needs_reselect', disable_reason: reason};
    try { this.#writeRecord(path, JSON.stringify(updated)); return 'latched'; }
    catch {
      try {
        const current = privateRead(path);
        if (current !== raw) throw new Error('source_record_changed');
        unlinkSync(path);
        return 'removed';
      } catch { throw new ClientError('source_invalidation_failed', '来源失效记录无法安全保存'); }
    }
  }
  revoke(identity: SourceIdentity, tool: SourceTool): void {
    const {path} = this.#path(identity, tool);
    if (privateRead(path) !== null) unlinkSync(path);
  }
}
