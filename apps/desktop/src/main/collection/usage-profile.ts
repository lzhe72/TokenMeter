import {randomBytes as systemRandomBytes} from 'node:crypto';
import {existsSync} from 'node:fs';
import {join} from 'node:path';
import {privateDirectory, privateRead, privateWrite} from '../storage.ts';
import {usagePrincipalKey} from './usage-identity.ts';
import {UsageStore} from './usage-store.ts';

export type IdentityCipher = {
  isEncryptionAvailable(): boolean;
  encryptString(value: string): Buffer;
  decryptString(value: Buffer): string;
};
export type UsageProfile = {
  readonly secret: Buffer;
  readonly store: UsageStore;
  principalKey(origin: string, accountId: string): string;
  close(): void;
};

type Ports = {cipher: IdentityCipher; randomBytes(): Buffer};

function decodedCiphertext(text: string): Buffer {
  try {
    const value: unknown = JSON.parse(text);
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error();
    const item = value as Record<string, unknown>;
    if (Object.keys(item).sort().join(',') !== 'ciphertext,schema_version' ||
        item.schema_version !== 1 || typeof item.ciphertext !== 'string' ||
        !/^[A-Za-z0-9+/]+={0,2}$/.test(item.ciphertext)) throw Error();
    const bytes = Buffer.from(item.ciphertext, 'base64');
    if (!bytes.length || bytes.toString('base64') !== item.ciphertext) throw Error();
    return bytes;
  } catch { throw new Error('identity_secret_corrupt'); }
}

/** Main-process only. The caller supplies Electron safeStorage; tests inject an owned cipher. */
export function openUsageProfile(root: string, ports: Ports): UsageProfile {
  const directory = privateDirectory(join(privateDirectory(root), 'collection'));
  const recordPath = join(directory, 'identity-secret-v1.json');
  const databasePath = join(directory, 'usage-v1.sqlite');
  let record: string | null;
  try { record = privateRead(recordPath); }
  catch { throw new Error('identity_secret_corrupt'); }

  // Existing events, cursors, or a marker may never be assigned a new key.
  if (record === null && existsSync(databasePath)) {
    const existing = new UsageStore(databasePath);
    try { if (existing.hasPersistedIdentity()) throw new Error('identity_secret_unavailable'); }
    finally { existing.close(); }
  }
  let available = false;
  try { available = ports.cipher.isEncryptionAvailable(); } catch { /* unavailable */ }
  if (!available) throw new Error('identity_secret_unavailable');

  let secret: Buffer;
  if (record === null) {
    const generated = ports.randomBytes();
    if (!Buffer.isBuffer(generated) || generated.length !== 32) throw new Error('identity_secret_unavailable');
    secret = Buffer.from(generated);
    let ciphertext: Buffer;
    try { ciphertext = ports.cipher.encryptString(secret.toString('hex')); }
    catch { throw new Error('identity_secret_unavailable'); }
    if (!Buffer.isBuffer(ciphertext) || ciphertext.length < 1) throw new Error('identity_secret_unavailable');
    privateWrite(recordPath, JSON.stringify({schema_version: 1, ciphertext: ciphertext.toString('base64')}));
  } else {
    const ciphertext = decodedCiphertext(record);
    let plaintext: string;
    try { plaintext = ports.cipher.decryptString(ciphertext); }
    catch { throw new Error('identity_secret_corrupt'); }
    if (typeof plaintext !== 'string' || !/^[a-f0-9]{64}$/.test(plaintext))
      throw new Error('identity_secret_corrupt');
    secret = Buffer.from(plaintext, 'hex');
  }
  const store = new UsageStore(databasePath);
  try { store.assertIdentitySecret(secret); }
  catch (error) { store.close(); throw error; }
  return {secret, store,
    principalKey: (origin, accountId) => usagePrincipalKey(secret, origin, accountId),
    close: () => {store.close(); secret.fill(0);}};
}

export const productionUsageRandomBytes = (): Buffer => systemRandomBytes(32);
