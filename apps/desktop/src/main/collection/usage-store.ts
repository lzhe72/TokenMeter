import { constants, closeSync, existsSync, lstatSync, openSync } from 'node:fs';
import { dirname } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { privateDirectory } from '../storage.ts';
import type { CodexUsageEvent } from './codex-format.ts';
import { sourceEventKey, sourceScopeKey } from './usage-identity.ts';

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
        code TEXT NOT NULL, occurred_at_utc TEXT NOT NULL, count INTEGER NOT NULL CHECK(count > 0));`);
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

  close(): void { this.db.close(); }
}
