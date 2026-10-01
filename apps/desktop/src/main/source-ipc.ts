import type {SourceAccess} from './source-access.ts';
import type {SourceTool} from './source-store.ts';
import {boolean, ClientError, record, string} from './validation.ts';

export const SOURCE_METHODS = ['chooseSource', 'previewSource', 'confirmSource',
  'updateSourceConsent', 'refreshSource', 'revokeSource'] as const;
export type SourceMethod = typeof SOURCE_METHODS[number];

export function isSourceMethod(value: unknown): value is SourceMethod {
  return typeof value === 'string' && (SOURCE_METHODS as readonly string[]).includes(value);
}

function selectionId(input: unknown): string {
  const value = record(input).selectionId;
  if (typeof value !== 'string' || value.length > 4096) throw new ClientError('invalid_selection', '选择已失效');
  return value;
}

function toolForPending(access: SourceAccess, id: string): SourceTool | null {
  return (['codex', 'claude_code'] as SourceTool[]).find(tool => access.snapshot()[tool].pending?.selectionId === id) ?? null;
}
function toolForConfirmed(access: SourceAccess, id: string): SourceTool | null {
  return (['codex', 'claude_code'] as SourceTool[]).find(tool => access.snapshot()[tool].confirmed?.sourceId === id) ?? null;
}

// The same dispatcher is used by the Electron IPC handler and fixed security tests.
// Renderer input never supplies a directory or a file read path.
export async function handleSourceIpcMethod(method: SourceMethod, input: unknown,
                                            access: SourceAccess,
                                            onTool: (tool: SourceTool | null) => void): Promise<void> {
  switch (method) {
    case 'chooseSource': {
      const tool = string(record(input).tool, 32) as SourceTool;
      if (tool !== 'codex' && tool !== 'claude_code') throw new ClientError('invalid_source_tool', '来源类型无效');
      onTool(tool);
      await access.choose(tool);
      return;
    }
    case 'previewSource': {
      const id = selectionId(input);
      onTool(toolForPending(access, id));
      await access.preview(id);
      return;
    }
    case 'confirmSource': {
      const data = record(input), id = selectionId(input);
      onTool(toolForPending(access, id));
      await access.confirm(id, boolean(data.collectAllowed), boolean(data.syncIntent));
      return;
    }
    case 'updateSourceConsent': {
      const data = record(input), id = string(data.sourceId, 64);
      onTool(toolForConfirmed(access, id));
      await access.updateConsent(id, boolean(data.collectAllowed), boolean(data.syncIntent));
      return;
    }
    case 'refreshSource': {
      const id = string(record(input).sourceId, 64);
      onTool(toolForConfirmed(access, id));
      await access.refresh(id);
      return;
    }
    case 'revokeSource': {
      const id = string(record(input).sourceId, 64);
      onTool(toolForConfirmed(access, id));
      await access.revoke(id);
      return;
    }
  }
}
