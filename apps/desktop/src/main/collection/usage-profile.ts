import type {UsageStore} from './usage-store.ts';

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

/** Boundary reserved for TC-TM003-CORE-08; implementation follows its failing baseline. */
export function openUsageProfile(_root: string, _ports: {cipher: IdentityCipher; randomBytes(): Buffer}): UsageProfile {
  throw new Error('identity_profile_not_implemented');
}
