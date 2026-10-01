import {createHmac} from 'node:crypto';
import type {SourceAccess, SourcePage} from '../source-access.ts';
import type {UsageStore} from './usage-store.ts';
import {CodexGeneration} from './codex-generation.ts';

export type CodexCollectionAccess = Pick<SourceAccess,
  'snapshot'|'beginCandidateScan'|'nextCandidatePage'|'readCandidateChunk'|'commitGuard'|'cancelScan'>;
export type CodexCollectionInput = {
  sourceId: string;
  access: CodexCollectionAccess;
  store: UsageStore;
  secret: Buffer;
  principal(): {verified: boolean; key: string};
  stagingBudgetBytes: number;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HEX64 = /^[a-f0-9]{64}$/;
const TOKEN = /^[a-f0-9]{32}$/;
const READ_BYTES = 65536;

/** Domain-separated local keys; native source IDs and file digests never enter SQLite. */
function locationKey(secret: Buffer, fields: string[]): string {
  const hmac = createHmac('sha256', secret);
  for (const field of fields) {
    const bytes = Buffer.from(field, 'utf8');
    const length = Buffer.alloc(4);
    length.writeUInt32BE(bytes.length);
    hmac.update(length).update(bytes);
  }
  return hmac.digest('hex');
}

function checkCandidate(value: {candidateToken: string; relativeName: string; size: number;
  fileIdentityDigest: string}): void {
  if (!TOKEN.test(value.candidateToken) || !Number.isSafeInteger(value.size) || value.size < 0 ||
      !HEX64.test(value.fileIdentityDigest) || typeof value.relativeName !== 'string' ||
      !value.relativeName || value.relativeName.length > 4096 ||
      value.relativeName.startsWith('/') || value.relativeName.includes('\\') ||
      /[\x00-\x1f\x7f]/.test(value.relativeName) ||
      value.relativeName.split('/').some(part => !part || part === '.' || part === '..'))
    throw new Error('invalid_source_metadata');
}

/** One bounded file body. Short reads are normal; premature EOF aborts the entire generation. */
async function readBody(input: CodexCollectionInput, scanId: string, token: string,
  size: number): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let offset = 0;
  while (offset < size) {
    const request = Math.min(READ_BYTES, size - offset);
    const chunk = await input.access.readCandidateChunk(scanId, token, offset, request);
    if (!Buffer.isBuffer(chunk) || chunk.length > request) throw new Error('invalid_source_read');
    if (!chunk.length) throw new Error('source_read_incomplete');
    chunks.push(chunk);
    offset += chunk.length;
  }
  return Buffer.concat(chunks, size);
}

export async function collectCodex(input: CodexCollectionInput): Promise<void> {
  if (!Buffer.isBuffer(input.secret) || input.secret.length !== 32) throw new Error('identity_secret_unavailable');
  if (!Number.isSafeInteger(input.stagingBudgetBytes) || input.stagingBudgetBytes < 1)
    throw new Error('invalid_staging_budget');
  const principal = input.principal();
  if (!principal?.verified || !HEX64.test(principal.key)) throw new Error('invalid_principal');
  const confirmed = input.access.snapshot().codex.confirmed;
  if (!UUID.test(input.sourceId) ||
      confirmed?.sourceId !== input.sourceId || confirmed?.status !== 'confirmed_enabled' ||
      !confirmed.collectAllowed)
    throw new Error('source_access_denied');

  const rootKey = locationKey(input.secret, ['codex-root-v1', input.sourceId]);
  const first = await input.access.beginCandidateScan(input.sourceId);
  const scanId = first.scanId;
  if (!UUID.test(scanId)) throw new Error('invalid_scan');
  let commitGuard: () => void = () => { throw new Error('source_operation_stale'); };
  const staged = new CodexGeneration({store: input.store, principalKey: principal.key,
    secret: input.secret, rootKey, guard: () => commitGuard(), onCancel: () => {}});
  const files: Array<{token: string; size: number}> = [];
  let totalBytes = 0;
  try {
    let page: SourcePage = first;
    for (;;) {
      if (!Array.isArray(page.candidates) || page.candidates.length > 256 ||
          typeof page.complete !== 'boolean') throw new Error('invalid_source_metadata');
      for (const candidate of page.candidates) {
        checkCandidate(candidate);
        if (candidate.size > input.stagingBudgetBytes - totalBytes)
          throw new Error('staging_budget_exceeded');
        totalBytes += candidate.size;
        const sourceKey = locationKey(input.secret,
          ['codex-file-v1', input.sourceId, candidate.fileIdentityDigest]);
        const bytes = await readBody(input, scanId, candidate.candidateToken, candidate.size);
        staged.stage({sourceKey, fileIdentity: sourceKey, bytes});
        files.push({token: candidate.candidateToken, size: candidate.size});
      }
      staged.pageComplete(page.complete);
      if (page.complete) break;
      page = await input.access.nextCandidatePage(scanId);
    }
    // Each probe revalidates the helper's file and directory snapshot after the final page.
    for (const file of files) {
      const tail = await input.access.readCandidateChunk(scanId, file.token, file.size, 1);
      if (!Buffer.isBuffer(tail) || tail.length !== 0) throw new Error('source_read_incomplete');
    }
    commitGuard = await input.access.commitGuard(scanId);
    if (!staged.finish()) throw new Error('source_scan_incomplete');
  } catch (error) { staged.cancel(); throw error; }
  finally { await input.access.cancelScan(scanId); }
}
