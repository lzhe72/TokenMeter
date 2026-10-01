import type { UpdaterSnapshot } from '../main/updater';
import type { SourceAccessSnapshot } from '../main/source-access';
import type { SourceTool } from '../main/source-store';
export type { SourceTool, SourceAccessSnapshot };
export type Account = { id: string; username: string; role: string; is_active: boolean; must_change_password: boolean };
export type Audit = { id: string; action: string; actor_id: string | null; target_id: string | null; occurred_at: string };
export type Snapshot = {
  version: string; build: string; server: string; defaultServer: string; feed: string; defaultFeed: string;
  automaticLogin: boolean; account: Account | null; users: Account[]; audit: Audit[];
  busy: boolean; identityVerified: boolean; lastIdentityCheck: string; pendingLogout: boolean;
  error: string | null; passwordStatus: string | null; adminStatus: string | null;
  canConfigureServer: boolean; canRetryRestore: boolean; updates: UpdaterSnapshot;
  sourcesReady: boolean; sources: SourceAccessSnapshot;
  sourceErrors: Record<SourceTool, string | null>;
};
export type Bridge = {
  snapshot(): Promise<Snapshot>; onState(callback: (state: Snapshot) => void): () => void;
  onOpenConfiguration(callback: () => void): () => void;
  login(input: {server: string; username: string; password: string; automaticLogin: boolean}): Promise<Snapshot>;
  changePassword(input: {currentPassword: string; newPassword: string}): Promise<Snapshot>;
  logout(): Promise<Snapshot>; retryLogout(): Promise<Snapshot>; refresh(): Promise<Snapshot>;
  listUsers(): Promise<Snapshot>; listAudit(): Promise<Snapshot>;
  manageUser(input: {userId: string; action: 'enable'|'disable'|'reset-password'; temporaryPassword?: string}): Promise<Snapshot>;
  saveConfiguration(input: {server: string; feed: string}): Promise<Snapshot>;
  resetConfiguration(): Promise<Snapshot>; setAutomaticLogin(value: boolean): Promise<Snapshot>;
  checkUpdates(): Promise<Snapshot>; installUpdate(): Promise<Snapshot>; cancelUpdate(): Promise<Snapshot>;
  chooseSource(input: {tool: SourceTool}): Promise<Snapshot>;
  previewSource(input: {selectionId: string}): Promise<Snapshot>;
  confirmSource(input: {selectionId: string; collectAllowed: boolean; syncIntent: boolean}): Promise<Snapshot>;
  updateSourceConsent(input: {sourceId: string; collectAllowed: boolean; syncIntent: boolean}): Promise<Snapshot>;
  refreshSource(input: {sourceId: string}): Promise<Snapshot>;
  revokeSource(input: {sourceId: string}): Promise<Snapshot>;
};
declare global { interface Window { tokenmeter: Bridge } }
