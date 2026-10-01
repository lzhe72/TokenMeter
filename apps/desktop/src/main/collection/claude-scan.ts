import {sameClaudeUsage, type ClaudeCall, type ClaudeDiagnostic} from './claude-format.ts';
import { readClaudeCandidate, type ClaudeFileCursor } from './claude-reader.ts';
import { claudeCandidateFromSource, type ConfirmedClaudeCandidate, type ConfirmedClaudeSourceAccess } from './claude-source.ts';

export interface ClaudeScanPage {
  candidates: ConfirmedClaudeCandidate[];
  complete: boolean;
  incompleteReason?: 'time_slice';
}

export interface ClaudeSourceScanAccess extends ConfirmedClaudeSourceAccess {
  beginCandidateScan(sourceId: string): Promise<ClaudeScanPage & {scanId: string}>;
  nextCandidatePage(scanId: string): Promise<ClaudeScanPage>;
  cancelScan(scanId: string): void | Promise<void>;
}

export interface GuardedClaudeSourceScanAccess extends ClaudeSourceScanAccess {
  commitGuard(scanId: string): Promise<() => void>;
}

export interface ClaudeScanPlan {
  calls: ClaudeCall[];
  diagnostics: ClaudeDiagnostic[];
  cursors: ClaudeFileCursor[];
  scanIncomplete: boolean;
  candidateCount: number;
}

/** Keeps the confirmed TM-002 scan lease open through the caller's final operation. */
async function withClaudeScanLease<T>(
  access: ClaudeSourceScanAccess, sourceId: string, secret: Buffer,
  loadCursor: (fileIdentity: string) => Promise<ClaudeFileCursor | null>,
  finish: (plan: ClaudeScanPlan, scanId: string) => Promise<T> | T,
): Promise<T> {
  const calls: ClaudeCall[] = [];
  const diagnostics: ClaudeDiagnostic[] = [];
  const byCallId = new Map<string, ClaudeCall>();
  const agentParents = new Map<string, Set<string>>();
  const cursors: ClaudeFileCursor[] = [];
  const seen = new Set<string>();
  let scanId: string | null = null;
  let candidateCount = 0;
  let scanIncomplete = false;
  try {
    const first = await access.beginCandidateScan(sourceId);
    scanId = first.scanId;
    let page: ClaudeScanPage = first;
    for (let pageNumber = 0; pageNumber < 1024; pageNumber++) {
      if (candidateCount + page.candidates.length > 10_000) throw new Error('claude_scan_limit');
      for (const candidate of page.candidates) {
        const readable = claudeCandidateFromSource(access, scanId, sourceId, candidate, secret);
        if (seen.has(readable.fileIdentity)) throw new Error('claude_scan_duplicate_candidate');
        seen.add(readable.fileIdentity);
        candidateCount++;
        let cursor = await loadCursor(readable.fileIdentity);
        for (let pass = 0; pass < 1024; pass++) {
          const oldOffset = cursor?.committedByteOffset ?? 0;
          const read = await readClaudeCandidate(readable, cursor, secret);
          for (const evidence of read.parentEvidence) {
            const sessions = agentParents.get(evidence.agentId) ?? new Set<string>();
            sessions.add(evidence.sessionId);
            agentParents.set(evidence.agentId, sessions);
          }
          for (const call of read.calls) {
            const prior = byCallId.get(call.canonicalCallId);
            if (prior) {
              if (!sameClaudeUsage(prior, call)) diagnostics.push({code: 'identity_conflict', count: 1});
              else if (prior.rowUuid !== call.rowUuid &&
                  (prior.sessionId !== call.sessionId || prior.agentId !== call.agentId))
                diagnostics.push({code: 'unverified_inheritance', count: 1});
            } else {
              byCallId.set(call.canonicalCallId, call);
              calls.push(call);
            }
          }
          diagnostics.push(...read.diagnostics.filter(item => item.code !== 'read_limit' &&
            item.code !== 'incomplete_tail' && item.code !== 'unverified_parent'));
          cursor = read.cursor;
          if (!read.scanIncomplete) break;
          if (read.cursor.committedByteOffset <= oldOffset ||
              !read.diagnostics.some(item => item.code === 'read_limit')) {
            scanIncomplete = true;
            if (read.diagnostics.some(item => item.code === 'read_limit'))
              diagnostics.push({code: 'read_limit', count: 1});
            diagnostics.push({code: 'incomplete_tail', count: 1});
            break;
          }
          if (pass === 1023) throw new Error('claude_scan_limit');
        }
        if (!cursor) throw new Error('claude_scan_failed');
        cursors.push(cursor);
      }
      if (page.complete) {
        for (const call of calls) {
          if (!call.isSidechain) continue;
          const sessions = call.agentId ? agentParents.get(call.agentId) : undefined;
          if (sessions?.size === 1 && sessions.has(call.sessionId)) call.attribution = 'parent_verified';
          else {
            call.attribution = 'unverified_parent';
            diagnostics.push({code: 'unverified_parent', count: 1});
          }
        }
        return await finish({calls, diagnostics, cursors, scanIncomplete, candidateCount}, scanId);
      }
      page = await access.nextCandidatePage(scanId);
    }
    throw new Error('claude_scan_limit');
  } catch (error) {
    if (error instanceof Error && ['claude_read_failed', 'claude_source_changed',
        'claude_scan_limit', 'claude_scan_duplicate_candidate'].includes(error.message)) throw error;
    throw new Error('claude_scan_failed');
  } finally {
    if (scanId) await access.cancelScan(scanId);
  }
}

/** A read-only scan result. It is no longer authorized for a later SQLite commit. */
export async function scanClaudeSource(
  access: ClaudeSourceScanAccess, sourceId: string, secret: Buffer,
  loadCursor: (fileIdentity: string) => Promise<ClaudeFileCursor | null>,
): Promise<ClaudeScanPlan> {
  return withClaudeScanLease(access, sourceId, secret, loadCursor, plan => plan);
}

/** The commit callback must run a synchronous atomic SQLite transaction with no await. */
export async function commitClaudeSource<T>(
  access: GuardedClaudeSourceScanAccess, sourceId: string, secret: Buffer,
  loadCursor: (fileIdentity: string) => Promise<ClaudeFileCursor | null>,
  commitSync: (plan: ClaudeScanPlan) => T,
): Promise<T> {
  return withClaudeScanLease(access, sourceId, secret, loadCursor, async (plan, scanId) => {
    const guard = await access.commitGuard(scanId);
    guard();
    const result = commitSync(plan);
    if (result !== null && typeof result === 'object' && 'then' in result)
      throw new Error('claude_async_commit');
    return result;
  });
}
