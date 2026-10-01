import {createHmac} from 'node:crypto';
import {scanCodexFile} from './codex-format.ts';

export type CodexCursor = {fileIdentity: string; committedByteOffset: number; prefixMac: string};

/** Initial binding for fixed cursor tests; reset behavior is implemented after the red run. */
export function scanCodexIncremental(bytes: Buffer, cursor: CodexCursor | null,
  fileIdentity: string, secret: Buffer) {
  const parsed = scanCodexFile(bytes, cursor?.committedByteOffset ?? 0);
  const prefixMac = createHmac('sha256', secret).update('usage-prefix-v1\0')
    .update(bytes.subarray(0, parsed.committedByteOffset)).digest('hex');
  return {...parsed, fileIdentity, prefixMac, reset: false, missingBefore: false};
}
