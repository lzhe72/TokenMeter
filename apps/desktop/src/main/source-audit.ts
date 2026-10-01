import { constants, closeSync, fsyncSync, fstatSync, openSync, readFileSync, writeSync } from 'node:fs';
import { createHmac } from 'node:crypto';
import { join } from 'node:path';
import { privateDirectory } from './storage.ts';
import { ClientError } from './validation.ts';

export type SourceAuditEvent = {
  operation: 'picker_open' | 'picker_result' | 'root_open' | 'enumerate' | 'metadata' | 'open_read' | 'reject' | 'cancel' | 'preview_complete';
  decision: 'allowed' | 'denied';
  reason?: string;
  tool: 'codex' | 'claude_code';
  generation: number;
  rootDev?: string;
  rootIno?: string;
  relativeName?: string;
  inspectedEntries?: number;
  candidateCount?: number;
};

export class SourceAudit {
  readonly #fd: number;
  readonly #key: Buffer;
  #sequence = 0;
  #closed = false;
  constructor(profile: string, nonceHex: string) {
    if (!/^[0-9a-f]{64}$/i.test(nonceHex)) throw new ClientError('invalid_source_audit_nonce', '来源审计标识无效');
    this.#key = Buffer.from(nonceHex, 'hex');
    const path = join(privateDirectory(profile), 'source-access-audit.jsonl');
    this.#fd = openSync(path, constants.O_RDWR | constants.O_CREAT | constants.O_APPEND | constants.O_NOFOLLOW, 0o600);
    try {
      const stat = fstatSync(this.#fd);
      if (!stat.isFile() || stat.nlink !== 1 || stat.uid !== process.getuid?.() ||
          (stat.mode & 0o777) !== 0o600 || stat.size > 64 * 1024 * 1024)
        throw new ClientError('unsafe_source_audit', '来源审计文件不安全');
      const previous = readFileSync(this.#fd, 'utf8');
      if (previous && !previous.endsWith('\n')) throw new ClientError('invalid_source_audit', '来源审计记录不完整');
      let sequence = 0;
      for (const line of previous.split('\n')) {
        if (!line) continue;
        let item: Record<string, unknown>;
        try { item = JSON.parse(line); }
        catch { throw new ClientError('invalid_source_audit', '来源审计记录无效'); }
        if (item.schema_version !== 1 || item.sequence !== ++sequence ||
            typeof item.operation !== 'string' || typeof item.decision !== 'string')
          throw new ClientError('invalid_source_audit', '来源审计顺序无效');
      }
      this.#sequence = sequence;
    } catch (error) { closeSync(this.#fd); throw error; }
  }
  #digest(value: string): string { return createHmac('sha256', this.#key).update(value).digest('hex'); }
  record(event: SourceAuditEvent): void {
    if (this.#closed) throw new ClientError('source_audit_closed', '来源审计已关闭');
    const operations = ['picker_open', 'picker_result', 'root_open', 'enumerate', 'metadata', 'open_read', 'reject', 'cancel', 'preview_complete'];
    if (!operations.includes(event.operation) || !['allowed', 'denied'].includes(event.decision) ||
        !['codex', 'claude_code'].includes(event.tool) || !Number.isSafeInteger(event.generation) || event.generation < 0 ||
        (event.reason !== undefined && !/^[a-z_]{1,60}$/.test(event.reason)) ||
        ((event.rootDev === undefined) !== (event.rootIno === undefined)) ||
        (event.rootDev !== undefined && !/^[0-9]{1,32}$/.test(event.rootDev)) ||
        (event.rootIno !== undefined && !/^[0-9]{1,32}$/.test(event.rootIno)) ||
        (event.relativeName !== undefined && (typeof event.relativeName !== 'string' || event.relativeName.includes('\0'))) ||
        (event.operation === 'preview_complete' && (event.decision !== 'allowed' ||
          !Number.isSafeInteger(event.inspectedEntries) || event.inspectedEntries! < 0 || event.inspectedEntries! > 5000 ||
          !Number.isSafeInteger(event.candidateCount) || event.candidateCount! < 0 || event.candidateCount! > 1000)) ||
        (event.operation !== 'preview_complete' && (event.inspectedEntries !== undefined || event.candidateCount !== undefined)))
      throw new ClientError('invalid_source_audit_event', '来源审计事件无效');
    const item = {
      schema_version: 1,
      sequence: this.#sequence + 1,
      operation: event.operation,
      decision: event.decision,
      ...(event.reason === undefined ? {} : {reason: event.reason}),
      tool: event.tool,
      generation: event.generation,
      root_digest: event.rootDev === undefined ? null : this.#digest(`${event.rootDev}:${event.rootIno}`),
      entry_digest: event.relativeName === undefined ? null : this.#digest(event.relativeName),
      ...(event.operation === 'preview_complete' ? {
        inspected_entries: event.inspectedEntries, candidate_count: event.candidateCount
      } : {})
    };
    const bytes = Buffer.from(`${JSON.stringify(item)}\n`, 'utf8');
    for (let offset = 0; offset < bytes.length;) offset += writeSync(this.#fd, bytes, offset, bytes.length - offset);
    this.#sequence++;
  }
  close(): void {
    if (this.#closed) return;
    this.#closed = true;
    try { fsyncSync(this.#fd); } finally { closeSync(this.#fd); }
  }
}
