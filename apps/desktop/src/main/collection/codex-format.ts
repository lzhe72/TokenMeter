export interface CodexUsage {
  inputTokens: number;
  outputTokens: number;
  cachedInputTokens: number | null;
  cacheWriteInputTokens: number | null;
  reasoningOutputTokens: number | null;
  totalTokens: number;
}

export interface CodexUsageEvent {
  source: 'codex';
  responseId: string;
  sessionId: string;
  turnId: string;
  occurredAtUtc: string;
  sourceVersion: string;
  modelId: string | null;
  usage: CodexUsage;
}

export interface CollectionDiagnostic { code: string }
export interface CodexScanResult {
  events: CodexUsageEvent[];
  diagnostics: CollectionDiagnostic[];
  committedByteOffset: number;
}

const VERIFIED_VERSION = '0.158.0-alpha.2.1';
const decoder = new TextDecoder('utf-8', { fatal: true });

function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}
function nonempty(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value);
}
function number(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value); }
function optionalNumber(value: unknown): number | null | undefined {
  if (value === undefined || value === null) return null;
  return number(value) && value >= 0 ? value : undefined;
}
function utc(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(value) &&
    !Number.isNaN(Date.parse(value));
}

function completeLines(bytes: Buffer): Array<{line: Buffer; end: number}> {
  const lines: Array<{line: Buffer; end: number}> = [];
  let start = 0;
  for (let i = 0; i < bytes.length; i++) {
    if (bytes[i] === 0x0a) {
      lines.push({line: bytes.subarray(start, i), end: i + 1});
      start = i + 1;
    }
  }
  return lines;
}

/** Parse complete LF-delimited records only. The caller owns byte cursor persistence. */
export function scanCodexFile(bytes: Buffer, committedByteOffset: number): CodexScanResult {
  if (!Buffer.isBuffer(bytes) || !Number.isSafeInteger(committedByteOffset) || committedByteOffset < 0 || committedByteOffset > bytes.length)
    throw new Error('invalid_source_cursor');
  const allLines = completeLines(bytes);
  const result: CodexScanResult = {events: [], diagnostics: [], committedByteOffset};
  let version: string | null = null;
  for (const {line} of allLines) {
    try {
      const record = object(JSON.parse(decoder.decode(line)));
      if (record?.type === 'session_meta') {
        const payload = object(record.payload);
        if (nonempty(payload?.cli_version)) { version = payload.cli_version; break; }
      }
    } catch { /* The first complete valid session header remains authoritative. */ }
  }
  if (version !== VERIFIED_VERSION) {
    if (allLines.some(item => item.end > committedByteOffset)) result.diagnostics.push({code: 'unsupported_source_version'});
    result.committedByteOffset = allLines.at(-1)?.end ?? committedByteOffset;
    return result;
  }
  for (const {line, end} of allLines) {
    if (end <= committedByteOffset) continue;
    result.committedByteOffset = end;
    let record: Record<string, unknown> | null;
    try { record = object(JSON.parse(decoder.decode(line))); }
    catch { result.diagnostics.push({code: 'invalid_record'}); continue; }
    if (!record) { result.diagnostics.push({code: 'invalid_record'}); continue; }
    const payload = object(record.payload);
    if (record.type === 'event_msg' && payload?.type === 'token_count') {
      result.diagnostics.push({code: payload.info === null ? 'missing_usage' : 'unverified_cumulative'});
      continue;
    }
    if (record.type !== 'token_usage_record') continue;
    if (!payload || !nonempty(payload.response_id)) { result.diagnostics.push({code: 'missing_response_id'}); continue; }
    if (!utc(record.timestamp)) { result.diagnostics.push({code: 'invalid_timestamp'}); continue; }
    if (!nonempty(payload.session_id) || !nonempty(payload.turn_id)) {
      result.diagnostics.push({code: 'missing_scope'}); continue;
    }
    const usage = object(payload.usage);
    if (!usage) { result.diagnostics.push({code: 'missing_usage'}); continue; }
    if (!number(usage.input_tokens) || usage.input_tokens < 0) {
      result.diagnostics.push({code: 'negative_input'}); continue;
    }
    if (!number(usage.output_tokens) || usage.output_tokens < 0) {
      result.diagnostics.push({code: 'invalid_output'}); continue;
    }
    const cached = optionalNumber(usage.cached_input_tokens);
    if (cached === undefined || (cached !== null && cached > usage.input_tokens)) {
      result.diagnostics.push({code: 'invalid_cached'}); continue;
    }
    const cacheWrite = optionalNumber(usage.cache_write_input_tokens);
    const reasoning = optionalNumber(usage.reasoning_output_tokens);
    if (cacheWrite === undefined || reasoning === undefined) {
      result.diagnostics.push({code: 'invalid_usage_subitem'}); continue;
    }
    const total = usage.input_tokens + usage.output_tokens;
    if (!Number.isSafeInteger(total) || !number(usage.total_tokens) || usage.total_tokens !== total) {
      result.diagnostics.push({code: 'invalid_total'}); continue;
    }
    result.events.push({
      source: 'codex', responseId: payload.response_id, sessionId: payload.session_id,
      turnId: payload.turn_id, occurredAtUtc: record.timestamp, sourceVersion: version,
      modelId: nonempty(payload.model_id) ? payload.model_id : null,
      usage: {inputTokens: usage.input_tokens, outputTokens: usage.output_tokens,
        cachedInputTokens: cached, cacheWriteInputTokens: cacheWrite,
        reasoningOutputTokens: reasoning, totalTokens: total},
    });
  }
  return result;
}
