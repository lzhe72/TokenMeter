import { constants, closeSync, existsSync, lstatSync, openSync } from 'node:fs';
import { dirname } from 'node:path';
import {createHmac, timingSafeEqual} from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { privateDirectory } from '../storage.ts';
import type { CodexUsageEvent } from './codex-format.ts';
import { sourceEventKey, sourceScopeKey } from './usage-identity.ts';

export type UsageSource = 'codex' | 'claude_code';
export type NormalizedUsageEvent = {
  source: UsageSource; providerCallScope: 'provider-response' | 'provider-message';
  canonicalCallId: string; sessionId: string; turnId: string;
  occurredAtUtc: string; sourceVersion: string; modelId: string | null;
  usage: CodexUsageEvent['usage'];
};
export type UsageBatch = {
  principalKey: string; secret: Buffer; source: UsageSource; sourceKey: string; rootKey: string;
  fileIdentity: string; committedByteOffset: number; prefixMac: string;
  events: Array<CodexUsageEvent | NormalizedUsageEvent>;
  diagnostics: Array<{code: string}>;
  coverage: {missingBefore: boolean; scanIncomplete: boolean};
  guard?: () => void;
};
export type UsageCursor = {fileIdentity: string; committedByteOffset: number; prefixMac: string};
export type UsageScanBatch = Pick<UsageBatch, 'principalKey'|'secret'|'source'|'rootKey'|'coverage'|'guard'> & {
  files: Array<Pick<UsageBatch, 'sourceKey'|'fileIdentity'|'committedByteOffset'|'prefixMac'|'events'|'diagnostics'>>;
};

function marker(secret: Buffer): string {
  if (!Buffer.isBuffer(secret) || secret.length !== 32) throw new Error('identity_secret_unavailable');
  return createHmac('sha256', secret).update('usage-identity-key-v1').digest('hex');
}
function hex64(value: string, code: string): void {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) throw new Error(code);
}
function safeCode(value: string): void {
  if (typeof value !== 'string' || !/^[a-z_]{3,60}$/.test(value)) throw new Error('invalid_diagnostic');
}
function normalized(event: CodexUsageEvent | NormalizedUsageEvent): NormalizedUsageEvent {
  if ('canonicalCallId' in event) return event;
  return {source: 'codex', providerCallScope: 'provider-response', canonicalCallId: event.responseId,
    sessionId: event.sessionId, turnId: event.turnId, occurredAtUtc: event.occurredAtUtc,
    sourceVersion: event.sourceVersion, modelId: event.modelId, usage: event.usage};
}

function assertPrivateFile(path: string): void {
  const stat = lstatSync(path);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1 ||
      stat.uid !== process.getuid?.() || (stat.mode & 0o777) !== 0o600)
    throw new Error('unsafe_usage_database');
}

function hexKey(value: string): void {
  if (!/^[a-f0-9]{64}$/.test(value)) throw new Error('invalid_principal_key');
}

export class UsageStore {
  private readonly db: DatabaseSync;
  private inScanBatch = false;

  constructor(path: string) {
    privateDirectory(dirname(path));
    if (!existsSync(path)) {
      const fd = openSync(path, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600);
      closeSync(fd);
    }
    assertPrivateFile(path);
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA foreign_keys = ON;
      CREATE TABLE IF NOT EXISTS usage_event (
        principal_key TEXT NOT NULL, source TEXT NOT NULL, source_event_key TEXT NOT NULL,
        source_scope_key TEXT NOT NULL, session_key TEXT NOT NULL,
        occurred_at_utc TEXT NOT NULL, model_id TEXT,
        input_tokens INTEGER NOT NULL CHECK(input_tokens >= 0),
        output_tokens INTEGER NOT NULL CHECK(output_tokens >= 0),
        cached_input_tokens INTEGER CHECK(cached_input_tokens >= 0),
        cache_write_input_tokens INTEGER CHECK(cache_write_input_tokens >= 0),
        reasoning_output_tokens INTEGER CHECK(reasoning_output_tokens >= 0),
        source_version TEXT NOT NULL, identity_scheme_version INTEGER NOT NULL,
        created_at_utc TEXT NOT NULL,
        PRIMARY KEY(principal_key, source, source_event_key));
      CREATE TABLE IF NOT EXISTS collection_diagnostic (
        id INTEGER PRIMARY KEY, principal_key TEXT NOT NULL, source_key TEXT NOT NULL,
        code TEXT NOT NULL, occurred_at_utc TEXT NOT NULL, count INTEGER NOT NULL CHECK(count > 0));
      CREATE TABLE IF NOT EXISTS source_cursor (
        principal_key TEXT NOT NULL, source_key TEXT NOT NULL, root_key TEXT NOT NULL,
        file_identity TEXT NOT NULL, committed_byte_offset INTEGER NOT NULL CHECK(committed_byte_offset >= 0),
        prefix_mac TEXT NOT NULL, updated_at_utc TEXT NOT NULL,
        PRIMARY KEY(principal_key, source_key));
      CREATE TABLE IF NOT EXISTS coverage (
        principal_key TEXT NOT NULL, root_key TEXT NOT NULL,
        missing_before INTEGER NOT NULL CHECK(missing_before IN (0,1)),
        scan_incomplete INTEGER NOT NULL CHECK(scan_incomplete IN (0,1)),
        last_scan_at_utc TEXT NOT NULL,
        PRIMARY KEY(principal_key, root_key));
      CREATE TABLE IF NOT EXISTS identity_key_state (
        id INTEGER PRIMARY KEY CHECK(id = 1), key_marker TEXT NOT NULL,
        identity_scheme_version INTEGER NOT NULL CHECK(identity_scheme_version = 1));`);
  }

  private checkMarker(secret: Buffer, create: boolean): void {
    const wanted = marker(secret);
    const row = this.db.prepare('SELECT key_marker FROM identity_key_state WHERE id = 1').get();
    if (row) {
      const actual = String(row.key_marker);
      if (!/^[a-f0-9]{64}$/.test(actual) || !timingSafeEqual(Buffer.from(actual, 'hex'), Buffer.from(wanted, 'hex')))
        throw new Error('identity_secret_mismatch');
      return;
    }
    const existing = this.db.prepare('SELECT (SELECT COUNT(*) FROM usage_event) AS events, (SELECT COUNT(*) FROM source_cursor) AS cursors').get()!;
    if (Number(existing.events) || Number(existing.cursors)) throw new Error('identity_secret_unavailable');
    if (create) this.db.prepare('INSERT INTO identity_key_state(id,key_marker,identity_scheme_version) VALUES (1,?,1)')
      .run(wanted);
  }

  /** Refuse a replacement key before any scanner can read or write this database. */
  assertIdentitySecret(secret: Buffer): void { this.checkMarker(secret, false); }

  hasPersistedIdentity(): boolean {
    const row = this.db.prepare(`SELECT
      (SELECT COUNT(*) FROM identity_key_state) AS markers,
      (SELECT COUNT(*) FROM usage_event) AS events,
      (SELECT COUNT(*) FROM source_cursor) AS cursors,
      (SELECT COUNT(*) FROM coverage) AS coverages`).get()!;
    return [row.markers, row.events, row.cursors, row.coverages].some(value => Number(value) > 0);
  }

  loadCursor(principalKey: string, sourceKey: string, secret: Buffer): UsageCursor | null {
    hexKey(principalKey); hex64(sourceKey, 'invalid_source_key'); this.checkMarker(secret, false);
    const row = this.db.prepare(`SELECT file_identity, committed_byte_offset, prefix_mac
      FROM source_cursor WHERE principal_key = ? AND source_key = ?`).get(principalKey, sourceKey);
    return row ? {fileIdentity: String(row.file_identity), committedByteOffset: Number(row.committed_byte_offset),
      prefixMac: String(row.prefix_mac)} : null;
  }

  /** Synchronous by design: an authorization guard can run immediately before COMMIT. */
  commitBatch(batch: UsageBatch): {inserted: number; duplicate: number; conflict: number} {
    const {principalKey, secret, source, sourceKey, rootKey, fileIdentity, committedByteOffset, prefixMac} = batch;
    hexKey(principalKey); hex64(sourceKey, 'invalid_source_key'); hex64(rootKey, 'invalid_root_key');
    hex64(fileIdentity, 'invalid_file_identity'); hex64(prefixMac, 'invalid_prefix_mac');
    if (source !== 'codex' && source !== 'claude_code') throw new Error('unsupported_source');
    if (!Number.isSafeInteger(committedByteOffset) || committedByteOffset < 0 ||
        !Array.isArray(batch.events) || !Array.isArray(batch.diagnostics) ||
        typeof batch.coverage?.missingBefore !== 'boolean' || typeof batch.coverage?.scanIncomplete !== 'boolean')
      throw new Error('invalid_usage_batch');
    const now = new Date().toISOString();
    const result = {inserted: 0, duplicate: 0, conflict: 0};
    if (!this.inScanBatch) this.db.exec('BEGIN IMMEDIATE');
    try {
      this.checkMarker(secret, true);
      for (const value of batch.events) {
        const event = normalized(value);
        if (event.source !== source || (source === 'codex' && event.providerCallScope !== 'provider-response') ||
            (source === 'claude_code' && event.providerCallScope !== 'provider-message')) throw new Error('invalid_usage_event');
        const key = sourceEventKey(secret, source, event.providerCallScope, event.canonicalCallId);
        const scope = sourceScopeKey(secret, source, event.sessionId, event.turnId);
        const session = sourceScopeKey(secret, source, event.sessionId, 'session');
        const usage = event.usage;
        const existing = this.db.prepare(`SELECT source_scope_key, model_id, input_tokens, output_tokens,
          cached_input_tokens, cache_write_input_tokens, reasoning_output_tokens
          FROM usage_event WHERE principal_key=? AND source=? AND source_event_key=?`)
          .get(principalKey, source, key);
        if (existing) {
          const same = existing.model_id === event.modelId && existing.input_tokens === usage.inputTokens &&
            existing.output_tokens === usage.outputTokens && existing.cached_input_tokens === usage.cachedInputTokens &&
            existing.cache_write_input_tokens === usage.cacheWriteInputTokens &&
            existing.reasoning_output_tokens === usage.reasoningOutputTokens;
          if (same) result.duplicate++;
          else {
            result.conflict++;
            this.db.prepare(`INSERT INTO collection_diagnostic
              (principal_key, source_key, code, occurred_at_utc, count) VALUES (?,?,?,?,1)`)
              .run(principalKey, sourceKey, 'identity_conflict', now);
          }
          continue;
        }
        this.db.prepare(`INSERT INTO usage_event
          (principal_key,source,source_event_key,source_scope_key,session_key,occurred_at_utc,
           model_id,input_tokens,output_tokens,cached_input_tokens,cache_write_input_tokens,
           reasoning_output_tokens,source_version,identity_scheme_version,created_at_utc)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)`).run(principalKey, source, key, scope, session,
          event.occurredAtUtc, event.modelId, usage.inputTokens, usage.outputTokens,
          usage.cachedInputTokens, usage.cacheWriteInputTokens, usage.reasoningOutputTokens,
          event.sourceVersion, now);
        result.inserted++;
      }
      for (const diagnostic of batch.diagnostics) {
        safeCode(diagnostic.code);
        this.db.prepare(`INSERT INTO collection_diagnostic
          (principal_key,source_key,code,occurred_at_utc,count) VALUES (?,?,?,?,1)`)
          .run(principalKey, sourceKey, diagnostic.code, now);
      }
      this.db.prepare(`INSERT INTO source_cursor
        (principal_key,source_key,root_key,file_identity,committed_byte_offset,prefix_mac,updated_at_utc)
        VALUES (?,?,?,?,?,?,?) ON CONFLICT(principal_key,source_key) DO UPDATE SET
        root_key=excluded.root_key,file_identity=excluded.file_identity,
        committed_byte_offset=excluded.committed_byte_offset,prefix_mac=excluded.prefix_mac,
        updated_at_utc=excluded.updated_at_utc`).run(principalKey, sourceKey, rootKey,
          fileIdentity, committedByteOffset, prefixMac, now);
      this.db.prepare(`INSERT INTO coverage (principal_key,root_key,missing_before,scan_incomplete,last_scan_at_utc)
        VALUES (?,?,?,?,?) ON CONFLICT(principal_key,root_key) DO UPDATE SET
        missing_before=MAX(coverage.missing_before,excluded.missing_before),
        scan_incomplete=excluded.scan_incomplete,last_scan_at_utc=excluded.last_scan_at_utc`)
        .run(principalKey, rootKey, batch.coverage.missingBefore ? 1 : 0,
          batch.coverage.scanIncomplete ? 1 : 0, now);
      batch.guard?.();
      if (!this.inScanBatch) this.db.exec('COMMIT');
      return result;
    } catch (error) { if (!this.inScanBatch) this.db.exec('ROLLBACK'); throw error; }
  }

  /** One generation is one SQLite transaction, including every file cursor and coverage. */
  commitScanBatch(batch: UsageScanBatch): {inserted: number; duplicate: number; conflict: number} {
    if (this.inScanBatch || !Array.isArray(batch.files) || batch.files.length === 0 ||
        new Set(batch.files.map(file => file.sourceKey)).size !== batch.files.length)
      throw new Error('invalid_scan_batch');
    const result = {inserted: 0, duplicate: 0, conflict: 0};
    this.db.exec('BEGIN IMMEDIATE');
    this.inScanBatch = true;
    try {
      for (const file of batch.files) {
        const current = this.commitBatch({principalKey: batch.principalKey, secret: batch.secret,
          source: batch.source, rootKey: batch.rootKey, coverage: batch.coverage,
          sourceKey: file.sourceKey, fileIdentity: file.fileIdentity,
          committedByteOffset: file.committedByteOffset, prefixMac: file.prefixMac,
          events: file.events, diagnostics: file.diagnostics});
        result.inserted += current.inserted; result.duplicate += current.duplicate;
        result.conflict += current.conflict;
      }
      batch.guard?.();
      this.db.exec('COMMIT');
      return result;
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
    finally { this.inScanBatch = false; }
  }

  record(principalKey: string, secret: Buffer, event: CodexUsageEvent): 'inserted' | 'duplicate' | 'conflict' {
    hexKey(principalKey);
    if (event.source !== 'codex') throw new Error('unsupported_source');
    const key = sourceEventKey(secret, 'codex', 'provider-response', event.responseId);
    const scope = sourceScopeKey(secret, 'codex', event.sessionId, event.turnId);
    const session = sourceScopeKey(secret, 'codex', event.sessionId, 'session');
    const usage = event.usage;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.checkMarker(secret, true);
      const existing = this.db.prepare(`SELECT source_scope_key, model_id, input_tokens, output_tokens,
        cached_input_tokens, cache_write_input_tokens, reasoning_output_tokens
        FROM usage_event WHERE principal_key = ? AND source = ? AND source_event_key = ?`)
        .get(principalKey, 'codex', key);
      if (existing) {
        const same = existing.model_id === event.modelId && existing.input_tokens === usage.inputTokens &&
          existing.output_tokens === usage.outputTokens && existing.cached_input_tokens === usage.cachedInputTokens &&
          existing.cache_write_input_tokens === usage.cacheWriteInputTokens &&
          existing.reasoning_output_tokens === usage.reasoningOutputTokens;
        if (!same) {
          this.db.prepare(`INSERT INTO collection_diagnostic
            (principal_key, source_key, code, occurred_at_utc, count) VALUES (?, ?, ?, ?, 1)`)
            .run(principalKey, scope, 'identity_conflict', new Date().toISOString());
        }
        this.db.exec('COMMIT');
        return same ? 'duplicate' : 'conflict';
      }
      this.db.prepare(`INSERT INTO usage_event
        (principal_key, source, source_event_key, source_scope_key, session_key, occurred_at_utc,
         model_id, input_tokens, output_tokens, cached_input_tokens, cache_write_input_tokens,
         reasoning_output_tokens, source_version, identity_scheme_version, created_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)`).run(
        principalKey, 'codex', key, scope, session, event.occurredAtUtc,
        event.modelId, usage.inputTokens, usage.outputTokens, usage.cachedInputTokens,
        usage.cacheWriteInputTokens, usage.reasoningOutputTokens, event.sourceVersion, new Date().toISOString());
      this.db.exec('COMMIT');
      return 'inserted';
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  summary(principalKey: string): {count: number; input: number; output: number; cached: number; total: number} {
    hexKey(principalKey);
    const row = this.db.prepare(`SELECT COUNT(*) AS count, COALESCE(SUM(input_tokens), 0) AS input,
      COALESCE(SUM(output_tokens), 0) AS output,
      COALESCE(SUM(cached_input_tokens), 0) AS cached,
      COALESCE(SUM(input_tokens + output_tokens), 0) AS total
      FROM usage_event WHERE principal_key = ?`).get(principalKey)!;
    return {count: Number(row.count), input: Number(row.input), output: Number(row.output),
      cached: Number(row.cached), total: Number(row.total)};
  }

  diagnostics(principalKey: string): Array<{code: string; count: number}> {
    hexKey(principalKey);
    return this.db.prepare(`SELECT code, SUM(count) AS count FROM collection_diagnostic
      WHERE principal_key = ? GROUP BY code ORDER BY code`).all(principalKey)
      .map(row => ({code: String(row.code), count: Number(row.count)}));
  }

  /** Sanitized Codex state. A missing row stays unknown to the caller. */
  codexState(principalKey: string, rootKey: string | null): {
    usage: null | {calls: number; inputTokens: number; outputTokens: number; totalTokens: number;
      cachedInput: {knownTokens: number; unknownRows: number}};
    coverage: {complete: boolean; missingBefore: boolean; scanIncomplete: boolean};
    diagnostics: Array<{code: string; count: number}>;
  } {
    hexKey(principalKey);
    if (rootKey !== null) hex64(rootKey, 'invalid_root_key');
    const row = this.db.prepare(`SELECT COUNT(*) calls, COALESCE(SUM(input_tokens),0) input,
      COALESCE(SUM(output_tokens),0) output, COALESCE(SUM(cached_input_tokens),0) cached,
      SUM(CASE WHEN cached_input_tokens IS NULL THEN 1 ELSE 0 END) unknown_cached
      FROM usage_event WHERE principal_key=? AND source='codex'`).get(principalKey)!;
    const calls = Number(row.calls), input = Number(row.input), output = Number(row.output);
    const cached = Number(row.cached), unknown = Number(row.unknown_cached ?? 0);
    if (![calls,input,output,cached,unknown,input + output].every(Number.isSafeInteger))
      throw new Error('invalid_usage_database');
    const coverage = rootKey === null ? undefined : this.db.prepare(`SELECT missing_before, scan_incomplete
      FROM coverage WHERE principal_key=? AND root_key=?`).get(principalKey, rootKey);
    const missingBefore = coverage ? Boolean(coverage.missing_before) : true;
    const scanIncomplete = coverage ? Boolean(coverage.scan_incomplete) : true;
    return {usage: calls ? {calls, inputTokens: input, outputTokens: output, totalTokens: input + output,
      cachedInput: {knownTokens: cached, unknownRows: unknown}} : null,
      coverage: {complete: !!coverage && !missingBefore && !scanIncomplete,
        missingBefore, scanIncomplete}, diagnostics: this.diagnostics(principalKey)};
  }

  close(): void { this.db.close(); }
}
