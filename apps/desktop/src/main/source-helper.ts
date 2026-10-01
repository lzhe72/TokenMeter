import { spawn, type ChildProcess } from 'node:child_process';
import { lstatSync } from 'node:fs';
import { join } from 'node:path';
import { createInterface, type Interface } from 'node:readline';
import type { Readable } from 'node:stream';

export type RootIdentity = { dev: string; ino: string };
export type SourceCandidate = {
  relativeName: string;
  size: number;
  mtimeMs: number;
  fileIdentityDigest: string;
};
export type ScannedCandidate = SourceCandidate & { candidateToken: string };
export type PreviewReason = 'candidate_limit' | 'entry_limit' | 'depth_limit' | 'timeout';
export type SourcePreview = {
  candidates: SourceCandidate[];
  incomplete: boolean;
  reason?: PreviewReason;
  inspectedEntries: number;
};
export type CandidatePage = {
  candidates: ScannedCandidate[];
  complete: boolean;
  incompleteReason?: 'time_slice';
};
export type SourceAuditEvent =
  | { action: 'root_open'; rootIdentity: RootIdentity }
  | {
      action: 'enumerated' | 'metadata' | 'open_read' | 'rejected';
      kind: 'candidate' | 'symlink' | 'non_regular' | 'depth_limit';
      relativeName: string;
      rootIdentity: RootIdentity;
      targetIdentity: RootIdentity;
    };

export class SourceHelperError extends Error {
  readonly code: string;
  constructor(code: string) {
    super(code);
    this.name = 'SourceHelperError';
    this.code = code;
  }
}

class LineReader {
  private readonly lines: string[] = [];
  private readonly waiting: Array<{ resolve: (line: string) => void; reject: (error: Error) => void }> = [];
  private readonly interface: Interface;
  private ended = false;
  private auditHandler: ((line: string) => void) | null = null;

  constructor(stream: Readable) {
    this.interface = createInterface({ input: stream, crlfDelay: Infinity });
    this.interface.on('line', line => {
      if (line.length > 120000 || this.lines.length > 1024) { this.close(); return; }
      if (line.startsWith('AUDIT ')) {
        try { if (!this.auditHandler) protocolError(); this.auditHandler(line); }
        catch { this.close(); }
        return;
      }
      const waiter = this.waiting.shift();
      if (waiter) waiter.resolve(line);
      else this.lines.push(line);
    });
    this.interface.on('close', () => this.close());
  }

  setAuditHandler(handler: (line: string) => void): void { this.auditHandler = handler; }

  next(): Promise<string> {
    const existing = this.lines.shift();
    if (existing !== undefined) return Promise.resolve(existing);
    if (this.ended) return Promise.reject(new SourceHelperError('helper_exited'));
    return new Promise((resolve, reject) => this.waiting.push({ resolve, reject }));
  }

  close(): void {
    if (this.ended) return;
    this.ended = true;
    this.interface.close();
    for (const waiter of this.waiting.splice(0)) waiter.reject(new SourceHelperError('helper_exited'));
    this.lines.length = 0;
  }
}

class ByteReader {
  private chunks: Buffer[] = [];
  private waiting: Array<{ resolve: (chunk: Buffer) => void; reject: (error: Error) => void }> = [];
  private ended = false;

  private readonly stream: Readable;
  constructor(stream: Readable) {
    this.stream = stream;
    stream.on('data', (chunk: Buffer) => {
      const waiter = this.waiting.shift();
      if (waiter) waiter.resolve(chunk);
      else this.chunks.push(chunk);
    });
    stream.on('end', () => this.close());
    stream.on('close', () => this.close());
    stream.on('error', () => this.close());
  }

  private next(): Promise<Buffer> {
    const existing = this.chunks.shift();
    if (existing !== undefined) return Promise.resolve(existing);
    if (this.ended) return Promise.reject(new SourceHelperError('helper_exited'));
    return new Promise((resolve, reject) => this.waiting.push({ resolve, reject }));
  }

  async exact(length: number): Promise<Buffer> {
    if (length === 0) return Buffer.alloc(0);
    const parts: Buffer[] = [];
    let remaining = length;
    while (remaining > 0) {
      const chunk = await this.next();
      if (chunk.length > remaining) {
        parts.push(chunk.subarray(0, remaining));
        this.chunks.unshift(chunk.subarray(remaining));
        remaining = 0;
      } else {
        parts.push(chunk);
        remaining -= chunk.length;
      }
    }
    return Buffer.concat(parts, length);
  }

  close(): void {
    if (this.ended) return;
    this.ended = true;
    this.stream.destroy();
    for (const waiter of this.waiting.splice(0)) waiter.reject(new SourceHelperError('helper_exited'));
    this.chunks = [];
  }
}

function protocolError(): never { throw new SourceHelperError('protocol_error'); }
const HELPER_TIMEOUT_MS = 15_000;
function bounded<T>(operation: Promise<T>, onTimeout: () => void, timeoutMs: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      reject(new SourceHelperError('helper_timeout'));
      onTimeout();
    }, timeoutMs);
  });
  return Promise.race([operation, timeout]).finally(() => { if (timer) clearTimeout(timer); });
}
function parsePositiveInteger(text: string): number {
  if (!/^(0|[1-9]\d*)$/.test(text)) protocolError();
  const value = Number(text);
  if (!Number.isSafeInteger(value)) protocolError();
  return value;
}
function parseSignedInteger(text: string): number {
  if (!/^-?(0|[1-9]\d*)$/.test(text)) protocolError();
  const value = Number(text);
  if (!Number.isSafeInteger(value)) protocolError();
  return value;
}
function decodeRelativeName(encoded: string): string {
  if (!/^[A-Za-z0-9_-]+$/.test(encoded)) protocolError();
  let relativeName: string;
  try { relativeName = new TextDecoder('utf-8', { fatal: true }).decode(Buffer.from(encoded, 'base64url')); }
  catch { protocolError(); }
  if (!relativeName || relativeName.startsWith('/') || relativeName.includes('\0') ||
      relativeName.split('/').some(part => !part || part === '.' || part === '..')) protocolError();
  return relativeName;
}
function parseCandidate(line: string, scan: false): SourceCandidate;
function parseCandidate(line: string, scan: true): ScannedCandidate;
function parseCandidate(line: string, scan: boolean): SourceCandidate | ScannedCandidate {
  const parts = line.split(' ');
  if (parts.length !== 7 || parts[0] !== 'ITEM' ||
      !/^[a-f0-9]{64}$/.test(parts[5]) || (scan ? !/^[a-f0-9]{32}$/.test(parts[6]) : parts[6] !== '-')) protocolError();
  const relativeName = decodeRelativeName(parts[1]);
  const size = parsePositiveInteger(parts[2]);
  const seconds = parseSignedInteger(parts[3]);
  const nanos = parsePositiveInteger(parts[4]);
  if (nanos >= 1_000_000_000) protocolError();
  const base = { relativeName, size, mtimeMs: seconds * 1000 + Math.floor(nanos / 1_000_000), fileIdentityDigest: parts[5] };
  if (!Number.isSafeInteger(base.mtimeMs)) protocolError();
  return scan ? { ...base, candidateToken: parts[6] } : base;
}

function parseAuditLine(line: string, rootIdentity: RootIdentity): SourceAuditEvent {
  const parts = line.split(' ');
  if (parts.length !== 6 || parts[0] !== 'AUDIT' || !/^\d+$/.test(parts[4]) || !/^\d+$/.test(parts[5])) protocolError();
  const action = parts[1], kind = parts[2];
  if (!['enumerated', 'metadata', 'open_read', 'rejected'].includes(action) ||
      (action === 'rejected' ? !['symlink', 'non_regular', 'depth_limit'].includes(kind) : kind !== 'candidate')) protocolError();
  return {
    action: action as 'enumerated' | 'metadata' | 'open_read' | 'rejected',
    kind: kind as 'candidate' | 'symlink' | 'non_regular' | 'depth_limit',
    relativeName: decodeRelativeName(parts[3]),
    rootIdentity,
    targetIdentity: { dev: parts[4], ino: parts[5] },
  };
}

function defaultBinaryPath(): string {
  const resources = process.resourcesPath;
  if (!resources) throw new SourceHelperError('helper_unavailable');
  return join(resources, '..', 'Helpers', 'source-helper');
}

export class SourceHelper {
  readonly rootIdentity: RootIdentity;
  private readonly lines: LineReader;
  private readonly body: ByteReader;
  private pending: Promise<unknown> = Promise.resolve();
  private closed = false;
  private readonly child: ChildProcess;
  private readonly timeoutMs: number;
  private readonly exitPromise: Promise<void>;

  private constructor(child: ChildProcess, identity: RootIdentity, lines: LineReader, timeoutMs: number) {
    this.child = child;
    this.rootIdentity = identity;
    this.lines = lines;
    this.body = new ByteReader(child.stdio[3] as Readable);
    this.timeoutMs = timeoutMs;
    this.exitPromise = new Promise(resolve => {
      if (child.exitCode !== null || child.signalCode !== null) { resolve(); return; }
      child.once('exit', () => resolve());
    });
  }

  static async open(rootPath: string, options: {
    binaryPath?: string;
    expectedRoot?: RootIdentity;
    onAudit?: (event: SourceAuditEvent) => void;
    timeoutMs?: number;
  } = {}): Promise<SourceHelper> {
    const binaryPath = options.binaryPath ?? defaultBinaryPath();
    try {
      const metadata = lstatSync(binaryPath);
      if (!metadata.isFile() || metadata.isSymbolicLink()) throw new Error();
    } catch { throw new SourceHelperError('helper_unavailable'); }
    const pathBytes = Buffer.from(rootPath, 'utf8');
    if (pathBytes.length === 0 || pathBytes.length > 4096 || pathBytes.includes(0)) throw new SourceHelperError('invalid_root');
    const expected = options.expectedRoot;
    let expectedBytes = Buffer.alloc(0);
    if (expected) {
      try {
        if (!/^\d+$/.test(expected.dev) || !/^\d+$/.test(expected.ino)) throw new Error();
        const dev = BigInt(expected.dev), ino = BigInt(expected.ino);
        if (dev < 0n || ino < 0n || dev > 0xffffffffffffffffn || ino > 0xffffffffffffffffn) throw new Error();
        expectedBytes = Buffer.alloc(16);
        expectedBytes.writeBigUInt64BE(dev, 0); expectedBytes.writeBigUInt64BE(ino, 8);
      } catch { throw new SourceHelperError('invalid_root_identity'); }
    }
    const timeoutMs = options.timeoutMs ?? HELPER_TIMEOUT_MS;
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > HELPER_TIMEOUT_MS) {
      throw new SourceHelperError('invalid_request');
    }
    const child = spawn(binaryPath, [], { stdio: ['pipe', 'pipe', 'ignore', 'pipe'], windowsHide: true });
    child.on('error', () => {});
    child.stdin?.on('error', () => {});
    const exited = new Promise<void>(resolve => {
      if (child.exitCode !== null || child.signalCode !== null) { resolve(); return; }
      child.once('exit', () => resolve());
      child.once('error', () => resolve());
    });
    const lines = new LineReader(child.stdout as Readable);
    const header = Buffer.alloc(4);
    header.writeUInt32BE(pathBytes.length, 0);
    const init = Buffer.concat([header, pathBytes, Buffer.from([expected ? 1 : 0]), expectedBytes]);
    try {
      const reply = await bounded((async () => {
        await new Promise<void>((resolve, reject) => child.stdin!.write(init, error => error ? reject(error) : resolve()));
        return lines.next();
      })(), () => { lines.close(); child.kill('SIGKILL'); }, timeoutMs);
      if (reply.startsWith('ERR ')) throw new SourceHelperError(reply.slice(4));
      const parts = reply.split(' ');
      if (parts.length !== 3 || parts[0] !== 'OK' || !/^\d+$/.test(parts[1]) || !/^\d+$/.test(parts[2])) protocolError();
      const identity = { dev: parts[1], ino: parts[2] };
      lines.setAuditHandler(line => {
        const event = parseAuditLine(line, identity);
        try { options.onAudit?.(event); } catch { /* Observer failure cannot grant or deny access. */ }
      });
      const helper = new SourceHelper(child, identity, lines, timeoutMs);
      try { options.onAudit?.({ action: 'root_open', rootIdentity: identity }); }
      catch { /* Observer failure cannot grant or deny access. */ }
      return helper;
    } catch (error) {
      lines.close(); child.kill('SIGKILL');
      await bounded(exited, () => child.kill('SIGKILL'), timeoutMs);
      if (error instanceof SourceHelperError) throw error;
      throw new SourceHelperError('helper_unavailable');
    }
  }

  private async command(text: string): Promise<string> {
    if (this.closed) throw new SourceHelperError('invalid_scan');
    try { await new Promise<void>((resolve, reject) => this.child.stdin!.write(text + '\n', error => error ? reject(error) : resolve())); }
    catch { throw new SourceHelperError('helper_exited'); }
    const reply = await this.lines.next();
    if (reply.startsWith('ERR ')) throw new SourceHelperError(reply.slice(4));
    return reply;
  }

  private serial<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.pending.then(() => bounded(operation(), () => this.close(), this.timeoutMs));
    this.pending = result.then(() => undefined, () => undefined);
    return result;
  }

  async preview(): Promise<SourcePreview> {
    return this.serial(async () => {
      const header = (await this.command('P')).split(' ');
      if (header.length !== 4 || header[0] !== 'PREVIEW') protocolError();
      const reason = header[1];
      if (!['complete', 'candidate_limit', 'entry_limit', 'depth_limit', 'timeout'].includes(reason)) protocolError();
      const inspectedEntries = parsePositiveInteger(header[2]);
      const count = parsePositiveInteger(header[3]);
      if (count > 1000 || inspectedEntries > 5000) protocolError();
      const candidates: SourceCandidate[] = [];
      for (let i = 0; i < count; i++) candidates.push(parseCandidate(await this.lines.next(), false));
      if (await this.lines.next() !== 'END') protocolError();
      return {
        candidates, incomplete: reason !== 'complete',
        ...(reason !== 'complete' ? { reason: reason as PreviewReason } : {}),
        inspectedEntries,
      };
    });
  }

  private async page(command: 'B' | 'N'): Promise<CandidatePage> {
    const header = (await this.command(command)).split(' ');
    if (header.length !== 4 || header[0] !== 'PAGE' || !['0', '1'].includes(header[1]) ||
        (header[1] === '1' ? header[3] !== 'complete' : !['continue', 'time_slice'].includes(header[3]))) protocolError();
    const count = parsePositiveInteger(header[2]);
    if (count > 256 || (count === 0 && header[3] === 'continue')) protocolError();
    const candidates: ScannedCandidate[] = [];
    for (let i = 0; i < count; i++) candidates.push(parseCandidate(await this.lines.next(), true));
    if (await this.lines.next() !== 'END') protocolError();
    return { candidates, complete: header[1] === '1', ...(header[3] === 'time_slice' ? { incompleteReason: 'time_slice' as const } : {}) };
  }

  beginCandidateScan(): Promise<CandidatePage> { return this.serial(() => this.page('B')); }
  nextCandidatePage(): Promise<CandidatePage> { return this.serial(() => this.page('N')); }

  readCandidateChunk(candidateToken: string, offset: number, maxBytes: number): Promise<Buffer> {
    return this.serial(async () => {
      if (!/^[a-f0-9]{32}$/.test(candidateToken)) throw new SourceHelperError('invalid_token');
      if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(maxBytes) || maxBytes < 0 || maxBytes > 65536) {
        throw new SourceHelperError('invalid_request');
      }
      const header = (await this.command('R ' + candidateToken + ' ' + offset + ' ' + maxBytes)).split(' ');
      if (header.length !== 2 || header[0] !== 'READ') protocolError();
      const length = parsePositiveInteger(header[1]);
      if (length > maxBytes) protocolError();
      return this.body.exact(length);
    });
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.lines.close();
    this.body.close();
    this.child.stdin?.destroy();
    this.child.kill('SIGKILL');
  }

  waitForExit(): Promise<void> {
    if (!this.closed) throw new SourceHelperError('invalid_scan');
    return bounded(this.exitPromise, () => this.child.kill('SIGKILL'), this.timeoutMs);
  }
}
