import { createHmac } from 'node:crypto';

export type UsageSource = 'codex' | 'claude_code';
export type ProviderCallScope = 'provider-response' | 'provider-message';

function strictUtf8(value: string): Buffer {
  if (typeof value !== 'string' || value.length === 0) throw new Error('invalid_identity_field');
  for (let i = 0; i < value.length; i++) {
    const unit = value.charCodeAt(i);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(++i);
      if (!(next >= 0xdc00 && next <= 0xdfff)) throw new Error('invalid_identity_unicode');
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      throw new Error('invalid_identity_unicode');
    }
  }
  const bytes = Buffer.from(value, 'utf8');
  if (bytes.length > 0xffffffff) throw new Error('identity_field_too_long');
  return bytes;
}

/** Version one uses byte lengths, including the domain string, before HMAC-SHA256. */
export function sourceEventKey(secret: Buffer, source: UsageSource, scope: ProviderCallScope, callId: string): string {
  if (!Buffer.isBuffer(secret) || secret.length !== 32) throw new Error('invalid_identity_secret');
  if (!((source === 'codex' && scope === 'provider-response') ||
        (source === 'claude_code' && scope === 'provider-message'))) throw new Error('invalid_source_scope');
  const parts = ['usage-identity-v1', source, scope, callId].map(strictUtf8);
  const hmac = createHmac('sha256', secret);
  for (const part of parts) {
    const length = Buffer.allocUnsafe(4);
    length.writeUInt32BE(part.length);
    hmac.update(length).update(part);
  }
  return hmac.digest('hex');
}

/** Local attribution only; this value never participates in the call uniqueness key. */
export function sourceScopeKey(secret: Buffer, source: UsageSource, sessionId: string, turnId: string): string {
  if (!Buffer.isBuffer(secret) || secret.length !== 32) throw new Error('invalid_identity_secret');
  const fields = ['usage-scope-v1', source, sessionId, turnId].map(strictUtf8);
  const hmac = createHmac('sha256', secret);
  for (const field of fields) {
    const length = Buffer.allocUnsafe(4);
    length.writeUInt32BE(field.length);
    hmac.update(length).update(field);
  }
  return hmac.digest('hex');
}
