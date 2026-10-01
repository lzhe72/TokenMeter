/** Claude Code 2.1.126 JSONL parser slice. Pure in-memory stage before TM-003 storage. */

export type ClaudeDiagnosticCode =
  | 'invalid_json' | 'incomplete_tail' | 'unsupported_version' | 'missing_usage'
  | 'invalid_usage' | 'ambiguous_zero' | 'identity_conflict'
  | 'unverified_inheritance' | 'unverified_parent' | 'invalid_timestamp' | 'invalid_structure'
  | 'invalid_utf8' | 'cursor_reset' | 'read_limit';

export interface ClaudeDiagnostic { code: ClaudeDiagnosticCode; count: number }

export interface ClaudeCall {
  canonicalCallId: string;
  rowUuid: string;
  sessionId: string;
  agentId: string | null;
  isSidechain: boolean;
  attribution: 'main' | 'parent_verified' | 'unverified_parent';
  occurredAtUtc: string;
  model: string | null;
  inputTokens: number;
  outputTokens: number;
  cachedReadInputTokens: number | null;
  cachedWriteInputTokens: number | null;
  sourceVersion: '2.1.126';
}

export interface ClaudeCollection {
  calls: ClaudeCall[];
  diagnostics: ClaudeDiagnostic[];
  totals: {calls: number; inputTokens: number; outputTokens: number; totalTokens: number};
}

type RecordValue = Record<string, unknown>;
const isRecord = (value: unknown): value is RecordValue =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const safeToken = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const optionalToken = (value: unknown): number | null | undefined =>
  value === undefined ? null : safeToken(value) ? value : undefined;
function nonempty(value: unknown): value is string {
  if (typeof value !== 'string' || value.length === 0) return false;
  for (let index = 0; index < value.length; index++) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(++index);
      if (!(next >= 0xdc00 && next <= 0xdfff)) return false;
    } else if (code >= 0xdc00 && code <= 0xdfff) return false;
  }
  return true;
}
const utcTimestamp = (value: unknown): value is string =>
  typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(value)
  && Number.isFinite(Date.parse(value))
  && new Date(Date.parse(value)).toISOString().slice(0, 19) === value.slice(0, 19);

function sameUsage(a: ClaudeCall, b: ClaudeCall): boolean {
  return a.model === b.model && a.inputTokens === b.inputTokens && a.outputTokens === b.outputTokens
    && a.cachedReadInputTokens === b.cachedReadInputTokens && a.cachedWriteInputTokens === b.cachedWriteInputTokens;
}

/** Accepts only complete LF-terminated rows. The caller never passes prompt or path to storage. */
export function collectClaudeJsonl(files: readonly string[]): ClaudeCollection {
  const calls: ClaudeCall[] = [];
  const diagnostics: ClaudeDiagnostic[] = [];
  const byCallId = new Map<string, ClaudeCall>();
  const agentParents = new Map<string, Set<string>>();
  const totals = {calls: 0, inputTokens: 0, outputTokens: 0, totalTokens: 0};
  const diagnose = (code: ClaudeDiagnosticCode): void => { diagnostics.push({code, count: 1}); };

  for (const file of files) {
    const lastLf = file.lastIndexOf('\n');
    const complete = lastLf < 0 ? '' : file.slice(0, lastLf + 1);
    if (lastLf < file.length - 1) diagnose('incomplete_tail');
    for (const text of complete.split('\n')) {
      if (!text) continue;
      let row: unknown;
      try { row = JSON.parse(text.endsWith('\r') ? text.slice(0, -1) : text); }
      catch { diagnose('invalid_json'); continue; }
      if (!isRecord(row)) { diagnose('invalid_structure'); continue; }
      if (row.type === 'user' && row.version === '2.1.126' && utcTimestamp(row.timestamp)
          && isRecord(row.message) && row.message.role === 'user'
          && Array.isArray(row.message.content) && row.message.content.some(
            block => isRecord(block) && block.type === 'tool_result')
          && isRecord(row.toolUseResult) && nonempty(row.toolUseResult.agentId)
          && row.isSidechain === false && nonempty(row.sessionId)) {
        const sessions = agentParents.get(row.toolUseResult.agentId) ?? new Set<string>();
        sessions.add(row.sessionId);
        agentParents.set(row.toolUseResult.agentId, sessions);
      }
      if (row.type !== 'assistant') continue;
      if (row.version !== '2.1.126') { diagnose('unsupported_version'); continue; }
      if (!isRecord(row.message) || row.message.role !== 'assistant' || !nonempty(row.message.id)
          || !nonempty(row.uuid) || !nonempty(row.sessionId)
          || typeof row.isSidechain !== 'boolean') {
        diagnose('invalid_structure'); continue;
      }
      if (!utcTimestamp(row.timestamp)) { diagnose('invalid_timestamp'); continue; }
      if (!isRecord(row.message.usage)) { diagnose('missing_usage'); continue; }
      const usage = row.message.usage;
      const cachedRead = optionalToken(usage.cache_read_input_tokens);
      const cachedWrite = optionalToken(usage.cache_creation_input_tokens);
      if (!safeToken(usage.input_tokens) || !safeToken(usage.output_tokens)
          || cachedRead === undefined || cachedWrite === undefined) {
        diagnose('invalid_usage'); continue;
      }
      if (usage.input_tokens === 0 && usage.output_tokens === 0) {
        diagnose('ambiguous_zero'); continue;
      }
      const candidate: ClaudeCall = {
        canonicalCallId: row.message.id, rowUuid: row.uuid, sessionId: row.sessionId,
        agentId: nonempty(row.agentId) ? row.agentId : null,
        isSidechain: row.isSidechain === true, attribution: 'main',
        occurredAtUtc: row.timestamp,
        model: nonempty(row.message.model) ? row.message.model : null,
        inputTokens: usage.input_tokens, outputTokens: usage.output_tokens,
        cachedReadInputTokens: cachedRead, cachedWriteInputTokens: cachedWrite,
        sourceVersion: '2.1.126',
      };
      const prior = byCallId.get(candidate.canonicalCallId);
      if (prior) {
        if (!sameUsage(prior, candidate)) diagnose('identity_conflict');
        else if (prior.rowUuid !== candidate.rowUuid &&
                 (prior.sessionId !== candidate.sessionId || prior.agentId !== candidate.agentId))
          diagnose('unverified_inheritance');
        continue;
      }
      const nextInput = totals.inputTokens + candidate.inputTokens;
      const nextOutput = totals.outputTokens + candidate.outputTokens;
      if (!Number.isSafeInteger(nextInput) || !Number.isSafeInteger(nextOutput)
          || !Number.isSafeInteger(nextInput + nextOutput)) {
        diagnose('invalid_usage'); continue;
      }
      byCallId.set(candidate.canonicalCallId, candidate);
      calls.push(candidate);
      totals.calls++; totals.inputTokens = nextInput; totals.outputTokens = nextOutput;
      totals.totalTokens = nextInput + nextOutput;
    }
  }

  for (const call of calls) {
    if (!call.isSidechain) continue;
    const sessions = call.agentId ? agentParents.get(call.agentId) : undefined;
    if (sessions?.size === 1 && sessions.has(call.sessionId)) call.attribution = 'parent_verified';
    else { call.attribution = 'unverified_parent'; diagnose('unverified_parent'); }
  }
  return {calls, diagnostics, totals};
}
