import {createHmac} from 'node:crypto';
import {scanCodexFile} from './codex-format.ts';

export type CodexCursor = {fileIdentity: string; committedByteOffset: number; prefixMac: string};

function mac(secret: Buffer, bytes: Buffer): string {
  if (!Buffer.isBuffer(secret) || secret.length !== 32) throw new Error('identity_secret_unavailable');
  return createHmac('sha256', secret).update('usage-prefix-v1\0')
    .update(bytes).digest('hex');
}

/** Consume only complete LF records and bind the saved cursor to their exact byte prefix. */
export function scanCodexIncremental(bytes: Buffer, cursor: CodexCursor | null,
  fileIdentity: string, secret: Buffer) {
  if (!Buffer.isBuffer(bytes) || !/^[a-f0-9]{64}$/.test(fileIdentity)) throw new Error('invalid_source_metadata');
  const reset = !!cursor && (cursor.fileIdentity !== fileIdentity ||
    cursor.committedByteOffset > bytes.length ||
    mac(secret, bytes.subarray(0, cursor.committedByteOffset)) !== cursor.prefixMac);
  const parsed = scanCodexFile(bytes, !reset && cursor ? cursor.committedByteOffset : 0);
  const prefixMac = mac(secret, bytes.subarray(0, parsed.committedByteOffset));
  return {...parsed, diagnostics: [...(reset ? [{code: 'cursor_reset'}] : []), ...parsed.diagnostics],
    fileIdentity, prefixMac, reset, missingBefore: reset};
}
