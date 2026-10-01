import type { FileHandle } from 'node:fs/promises';
import { createHmac } from 'node:crypto';
import { collectClaudeJsonl, type ClaudeCall, type ClaudeDiagnostic } from './claude-format.ts';

export interface ClaudeFileCursor {
  fileIdentity: string;
  committedByteOffset: number;
  prefixMac: string;
}

export interface ClaudeFileRead {
  calls: ClaudeCall[];
  diagnostics: ClaudeDiagnostic[];
  cursor: ClaudeFileCursor;
  scanIncomplete: boolean;
}

/** A TM-002 confirmed candidate is identified only by opaque metadata and a bounded byte reader. */
export interface ClaudeCandidateReader {
  fileIdentity: string;
  size: number;
  readAt(offset: number, maxBytes: number): Promise<Buffer>;
  assertCurrent(): Promise<void>;
}

const MAC_PATTERN = /^[0-9a-f]{64}$/;
const MAX_READ_BYTES = 1024 * 1024;
const HASH_CHUNK_BYTES = 64 * 1024;

async function readExact(candidate: ClaudeCandidateReader, position: number, size: number): Promise<Buffer> {
  const output = Buffer.alloc(size);
  let filled = 0;
  while (filled < size) {
    const requested = Math.min(HASH_CHUNK_BYTES, size - filled);
    const chunk = await candidate.readAt(position + filled, requested);
    if (!Buffer.isBuffer(chunk) || chunk.length === 0 || chunk.length > requested)
      throw new Error('claude_source_changed');
    chunk.copy(output, filled);
    filled += chunk.length;
  }
  return output;
}

async function prefixMac(candidate: ClaudeCandidateReader, secret: Buffer, length: number): Promise<string> {
  const mac = createHmac('sha256', secret);
  for (let position = 0; position < length; position += HASH_CHUNK_BYTES) {
    mac.update(await readExact(candidate, position, Math.min(HASH_CHUNK_BYTES, length - position)));
  }
  return mac.digest('hex');
}

/** The caller must obtain this byte capability from a confirmed TM-002 source scan. */
export async function readClaudeCandidate(
  candidate: ClaudeCandidateReader, previous: ClaudeFileCursor | null, secret: Buffer,
  maxReadBytes = MAX_READ_BYTES,
): Promise<ClaudeFileRead> {
  const fileIdentity = candidate.fileIdentity;
  if (!fileIdentity || fileIdentity.includes('/') || !Buffer.isBuffer(secret) || secret.length !== 32
      || !Number.isSafeInteger(candidate.size) || candidate.size < 0 || !Number.isSafeInteger(maxReadBytes)
      || maxReadBytes < 1 || maxReadBytes > MAX_READ_BYTES) throw new Error('claude_reader_invalid_input');
  try {
    await candidate.assertCurrent();
    const size = candidate.size;
    const diagnostics: ClaudeDiagnostic[] = [];
    let start = 0;
    let resumed = false;
    if (previous) {
      const canResume = previous.fileIdentity === fileIdentity
        && Number.isSafeInteger(previous.committedByteOffset)
        && previous.committedByteOffset >= 0 && previous.committedByteOffset <= size
        && MAC_PATTERN.test(previous.prefixMac);
      if (canResume) {
        if (await prefixMac(candidate, secret, previous.committedByteOffset) === previous.prefixMac) {
          start = previous.committedByteOffset;
          resumed = true;
        }
      }
      if (!resumed) diagnostics.push({code: 'cursor_reset', count: 1});
    }
    const length = Math.min(maxReadBytes, size - start);
    const data = await readExact(candidate, start, length);
    const lastLf = data.lastIndexOf(0x0a);
    const completeLength = lastLf + 1;
    const lines: string[] = [];
    const decoder = new TextDecoder('utf-8', {fatal: true});
    for (let lineStart = 0; lineStart < completeLength;) {
      const lineEnd = data.indexOf(0x0a, lineStart);
      try { lines.push(`${decoder.decode(data.subarray(lineStart, lineEnd))}\n`); }
      catch { diagnostics.push({code: 'invalid_utf8', count: 1}); }
      lineStart = lineEnd + 1;
    }
    const parsed = collectClaudeJsonl(lines);
    const committedByteOffset = start + completeLength;
    if (completeLength < data.length) diagnostics.push({code: 'incomplete_tail', count: 1});
    if (start + data.length < size) diagnostics.push({code: 'read_limit', count: 1});
    const committedPrefixMac = await prefixMac(candidate, secret, committedByteOffset);
    await candidate.assertCurrent();
    return {
      calls: parsed.calls,
      diagnostics: [...diagnostics, ...parsed.diagnostics],
      cursor: {fileIdentity, committedByteOffset, prefixMac: committedPrefixMac},
      scanIncomplete: committedByteOffset < size,
    };
  } catch (error) {
    if (error instanceof Error && (error.message === 'claude_source_changed' || error.message === 'claude_reader_invalid_source')) throw error;
    throw new Error('claude_read_failed');
  }
}

/** Fixture adapter; product collection uses readClaudeCandidate with TM-002 tokens. */
export async function readClaudeFile(
  handle: FileHandle, fileIdentity: string, previous: ClaudeFileCursor | null,
  secret: Buffer, maxReadBytes = MAX_READ_BYTES,
): Promise<ClaudeFileRead> {
  try {
    const before = await handle.stat();
    if (!before.isFile() || !Number.isSafeInteger(before.size)) throw new Error('claude_reader_invalid_source');
    return await readClaudeCandidate({
      fileIdentity, size: before.size,
      async readAt(offset, requested) {
        const output = Buffer.alloc(requested);
        const {bytesRead} = await handle.read(output, 0, requested, offset);
        return output.subarray(0, bytesRead);
      },
      async assertCurrent() {
        const after = await handle.stat();
        if (after.size !== before.size || after.mtimeMs !== before.mtimeMs || after.ctimeMs !== before.ctimeMs
            || after.dev !== before.dev || after.ino !== before.ino) throw new Error('claude_source_changed');
      },
    }, previous, secret, maxReadBytes);
  } catch (error) {
    if (error instanceof Error && (error.message === 'claude_source_changed' || error.message === 'claude_reader_invalid_source')) throw error;
    throw new Error('claude_read_failed');
  }
}
