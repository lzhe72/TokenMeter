import { createHmac } from 'node:crypto';
import type { ClaudeCandidateReader } from './claude-reader.ts';

export interface ConfirmedClaudeSourceAccess {
  readCandidateChunk(scanId: string, candidateToken: string, offset: number, maxBytes: number): Promise<Buffer>;
}

export interface ConfirmedClaudeCandidate {
  relativeName: string;
  size: number;
  candidateToken: string;
  fileIdentityDigest: string;
}

/** Keyed root scope; no path or raw source digest is stored. */
export function claudeRootKey(sourceId: string, secret: Buffer): string {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuid.test(sourceId) || !Buffer.isBuffer(secret) || secret.length !== 32)
    throw new Error('claude_source_invalid');
  const mac = createHmac('sha256', secret);
  for (const bytes of [Buffer.from('claude-root-v1', 'utf8'), Buffer.from(sourceId, 'utf8')]) {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(bytes.length);
    mac.update(length).update(bytes);
  }
  return mac.digest('hex');
}

/** Adapts a confirmed TM-002 scan token; no renderer path or direct filesystem open. */
export function claudeCandidateFromSource(
  access: ConfirmedClaudeSourceAccess, scanId: string, sourceId: string,
  candidate: ConfirmedClaudeCandidate, secret: Buffer,
): ClaudeCandidateReader {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const token = /^[0-9a-f]{32}$/;
  const digest = /^[0-9a-f]{64}$/;
  const name = candidate?.relativeName;
  if (!uuid.test(scanId) || !uuid.test(sourceId) || !token.test(candidate?.candidateToken)
      || !digest.test(candidate?.fileIdentityDigest)
      || typeof name !== 'string' || name.length < 1 || name.length > 4096
      || !name.endsWith('.jsonl') || name.startsWith('/') || name.includes('\\')
      || /[\x00-\x1f\x7f]/.test(name) || name.split('/').some(part => !part || part === '.' || part === '..')
      || Buffer.from(name, 'utf8').toString('utf8') !== name
      || !Number.isSafeInteger(candidate.size) || candidate.size < 0
      || !Buffer.isBuffer(secret) || secret.length !== 32)
    throw new Error('claude_candidate_invalid');
  const mac = createHmac('sha256', secret);
  for (const bytes of [Buffer.from('claude-file-v1', 'utf8'), Buffer.from(sourceId, 'utf8'),
    Buffer.from(candidate.fileIdentityDigest, 'hex')]) {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(bytes.length);
    mac.update(length).update(bytes);
  }
  const fileIdentity = mac.digest('hex');
  const candidateToken = candidate.candidateToken;
  return {
    fileIdentity, size: candidate.size,
    readAt(offset, maxBytes) {
      if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(maxBytes)
          || maxBytes < 1 || maxBytes > 65536) throw new Error('claude_candidate_invalid');
      return access.readCandidateChunk(scanId, candidateToken, offset, maxBytes);
    },
    async assertCurrent() { await access.readCandidateChunk(scanId, candidateToken, 0, 1); },
  };
}
