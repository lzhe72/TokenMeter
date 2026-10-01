import { join } from 'node:path';
import { CredentialStore, privateRead, privateWrite } from './storage.ts';
import { ClientError, canonicalOrigin, record, string, boolean } from './validation.ts';
import type { Account, Audit } from '../shared/types.ts';

type Settings = {server: string; feed: string; automaticLogin: boolean};
function account(value: unknown): Account {
  const data = record(value);
  if (typeof data.is_active !== 'boolean' || typeof data.must_change_password !== 'boolean' || !['admin', 'member'].includes(String(data.role))) throw new ClientError('invalid_response', '服务返回的账号信息无效');
  return {id: string(data.id, 128), username: string(data.username, 64), role: String(data.role), is_active: data.is_active, must_change_password: data.must_change_password};
}
export async function request(origin: string, method: string, path: string, token?: string, body?: object): Promise<unknown> {
  let response: Response;
  try { response = await fetch(`${origin}${path}`, {method, headers: {'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {})}, ...(body ? {body: JSON.stringify(body)} : {}), redirect: 'manual', signal: AbortSignal.timeout(15000)}); }
  catch { throw new ClientError('network_unavailable', '无法连接服务，请检查地址和网络后重试'); }
  if (response.status >= 300 && response.status < 400) throw new ClientError('redirect_rejected', '认证请求拒绝重定向');
  if (response.status === 204) return null;
  const reader = response.body?.getReader(); const parts: Uint8Array[] = []; let bytes = 0;
  if (reader) while (true) { const part = await reader.read(); if (part.done) break; bytes += part.value.length; if (bytes > 1048576) { await reader.cancel(); throw new ClientError('invalid_response', '服务响应过大'); } parts.push(part.value); }
  let data: unknown; try { data = JSON.parse(Buffer.concat(parts).toString('utf8')); } catch { throw new ClientError('invalid_response', '服务返回格式无效'); }
  if (!response.ok) {
    const raw = record(data).error; const code = raw && typeof raw === 'object' ? (raw as Record<string, unknown>).code : undefined;
    const allowed = ['invalid_credentials', 'account_disabled', 'rate_limited', 'invalid_session', 'forbidden', 'password_change_required', 'password_unchanged', 'admin_protected', 'validation_error', 'not_found'];
    throw new ClientError(typeof code === 'string' && allowed.includes(code) ? code : 'server_error', '操作未完成，请检查输入或服务状态');
  }
  return data;
}
export class Accounts {
  server: string; feed: string; automaticLogin: boolean;
  account: Account | null = null; users: Account[] = []; audit: Audit[] = [];
  busy = false; identityVerified = false; lastIdentityCheck = ''; pendingLogout = false;
  error: string | null = null; passwordStatus: string | null = null; adminStatus: string | null = null;
  readonly defaultServer: string; readonly defaultFeed: string;
  #profile: string; #settingsPath: string; #token: string | null = null;
  #pending: {origin: string; token: string} | null = null;
  #changed: () => void; #validateFeed: (value: string) => URL;
  constructor(profile: string, defaults: {api_url: string; update_feed_url: string}, validateFeed: (value: string) => URL, changed: () => void) {
    this.#profile = profile; this.#changed = changed; this.#validateFeed = validateFeed; this.#settingsPath = join(profile, 'settings.json');
    this.defaultServer = canonicalOrigin(defaults.api_url); this.defaultFeed = validateFeed(defaults.update_feed_url).href;
    const stored = privateRead(this.#settingsPath); const settings = stored ? record(JSON.parse(stored)) : {};
    this.server = settings.server === undefined ? this.defaultServer : canonicalOrigin(settings.server);
    this.feed = settings.feed === undefined ? this.defaultFeed : validateFeed(string(settings.feed)).href;
    this.automaticLogin = settings.automaticLogin === undefined ? true : boolean(settings.automaticLogin);
  }
  get canConfigureServer(): boolean { return !this.busy && !this.account && !this.pendingLogout; }
  get canRetryRestore(): boolean { return this.automaticLogin && !!this.#token && !this.account && !this.busy && !this.pendingLogout; }
  #credentials(origin = this.server): CredentialStore { return new CredentialStore(this.#profile, origin); }
  #save(settings: Settings): void {
    const overrides = {
      ...(settings.server !== this.defaultServer ? {server: settings.server} : {}),
      ...(settings.feed !== this.defaultFeed ? {feed: settings.feed} : {}),
      ...(settings.automaticLogin !== true ? {automaticLogin: settings.automaticLogin} : {})
    };
    privateWrite(this.#settingsPath, JSON.stringify(overrides));
    this.server = settings.server; this.feed = settings.feed; this.automaticLogin = settings.automaticLogin;
  }
  #clear(): void { this.account = null; this.#token = null; this.users = []; this.audit = []; this.identityVerified = false; this.lastIdentityCheck = ''; }
  #authenticated(): string { if (!this.#token || !this.account) throw new ClientError('invalid_session', '请先登录'); return this.#token; }
  fail(error: unknown): void { const code = error instanceof ClientError ? error.code : (error as {code?: unknown})?.code; this.error = typeof code === 'string' && /^[a-z_]{3,60}$/.test(code) ? code : 'operation_failed'; this.#changed(); }
  async #perform(action: () => Promise<void>): Promise<void> {
    if (this.busy) { this.fail(new ClientError('operation_busy', '操作进行中')); return; }
    this.busy = true; this.error = null; this.#changed();
    try { await action(); }
    catch (error) { if (error instanceof ClientError && ['invalid_session', 'account_disabled'].includes(error.code)) { try { this.#credentials().clear(); } finally { this.#clear(); } } this.fail(error); }
    finally { this.busy = false; this.#changed(); }
  }
  async #accept(value: unknown): Promise<void> {
    const session = record(value); const token = string(session.access_token, 128); const user = account(session.user);
    if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw new ClientError('invalid_response', '会话格式无效');
    try { if (this.automaticLogin) this.#credentials().write(token); else this.#credentials().clear(); }
    catch (error) { try { await request(this.server, 'POST', '/v1/auth/logout', token); } catch {} throw error; }
    this.#token = token; this.account = user; this.identityVerified = true; this.lastIdentityCheck = new Date().toISOString();
  }
  async #identity(): Promise<void> {
    this.identityVerified = false; this.#changed();
    if (!this.#token) return;
    this.account = account(await request(this.server, 'GET', '/v1/me', this.#token));
    this.identityVerified = true; this.lastIdentityCheck = new Date().toISOString();
  }
  async restore(): Promise<void> { await this.#perform(async () => { this.#token = this.automaticLogin ? this.#credentials().read() : null; if (this.#token) await this.#identity(); }); }
  async login(input: unknown): Promise<void> {
    const data = record(input); const server = canonicalOrigin(data.server); const username = string(data.username, 64); const password = string(data.password, 128); const automaticLogin = boolean(data.automaticLogin);
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$/.test(username)) throw new ClientError('invalid_username', '账号格式不正确');
    if (!this.canConfigureServer) throw new ClientError('server_configuration_locked', '请先退出登录');
    this.#save({server, feed: this.feed, automaticLogin});
    await this.#perform(async () => { this.#clear(); await this.#accept(await request(server, 'POST', '/v1/auth/login', undefined, {username, password})); });
  }
  async changePassword(input: unknown): Promise<void> {
    const data = record(input); const current = string(data.currentPassword, 128); const next = string(data.newPassword, 128);
    if (next.length < 12) throw new ClientError('invalid_password', '新密码至少需要12位');
    this.passwordStatus = null;
    await this.#perform(async () => { await this.#accept(await request(this.server, 'POST', '/v1/auth/change-password', this.#authenticated(), {current_password: current, new_password: next})); this.passwordStatus = '密码已更新；旧会话已撤销'; });
  }
  async refresh(): Promise<void> { await this.#perform(() => this.#identity()); }
  async logout(): Promise<void> {
    await this.#perform(async () => {
      const token = this.#authenticated(); const origin = this.server; this.#credentials().clear(); this.#clear(); this.#pending = null; this.pendingLogout = false;
      try { await request(origin, 'POST', '/v1/auth/logout', token); }
      catch (error) { if (!(error instanceof ClientError && ['invalid_session', 'account_disabled'].includes(error.code))) { this.#pending = {origin, token}; this.pendingLogout = true; this.error = 'logout_unconfirmed'; } }
    });
  }
  async retryLogout(): Promise<void> {
    await this.#perform(async () => { if (!this.#pending) return; const {origin, token} = this.#pending;
      try { await request(origin, 'POST', '/v1/auth/logout', token); }
      catch (error) { if (!(error instanceof ClientError && ['invalid_session', 'account_disabled'].includes(error.code))) throw error; }
      this.#pending = null; this.pendingLogout = false;
    });
  }
  async listUsers(): Promise<void> { await this.#perform(async () => { const data = record(await request(this.server, 'GET', '/v1/admin/users', this.#authenticated())); if (!Array.isArray(data.users)) throw new ClientError('invalid_response', '账号列表无效'); this.users = data.users.map(account); }); }
  async manageUser(input: unknown): Promise<void> {
    const data = record(input); const id = string(data.userId, 128); const action = string(data.action, 32);
    if (!/^[a-zA-Z0-9-]+$/.test(id) || !['enable', 'disable', 'reset-password'].includes(action)) throw new ClientError('invalid_input', '管理操作无效');
    let body: {temporary_password: string} | undefined;
    if (action === 'reset-password') {
      const password = data.temporaryPassword;
      if (typeof password !== 'string' || password.length < 12 || password.length > 128)
        throw new ClientError('invalid_password', '临时密码需要12至128位');
      body = {temporary_password: password};
    }
    await this.#perform(async () => {
      const updated = account(await request(this.server, 'POST', `/v1/admin/users/${id}/${action}`, this.#authenticated(), body));
      if (updated.id === this.account?.id && action === 'reset-password') { try { this.#credentials().clear(); } finally { this.#clear(); } }
      else this.users = this.users.map(user => user.id === updated.id ? updated : user);
      this.adminStatus = action === 'reset-password' ? 'password_reset' : `account_${action === 'disable' ? 'disabled' : 'enabled'}`;
    });
  }
  async listAudit(): Promise<void> { await this.#perform(async () => {
    const data = record(await request(this.server, 'GET', '/v1/admin/audit', this.#authenticated()));
    if (!Array.isArray(data.events)) throw new ClientError('invalid_response', '审计列表无效');
    this.audit = data.events.map(value => { const item = record(value); return {id: string(item.id, 128), action: string(item.action, 128), actor_id: item.actor_id === null ? null : string(item.actor_id, 128), target_id: item.target_id === null ? null : string(item.target_id, 128), occurred_at: string(item.occurred_at, 128)}; });
  }); }
  saveConfiguration(input: unknown, canConfigureFeed: boolean): void {
    const data = record(input); const server = canonicalOrigin(data.server); const feed = this.#validateFeed(string(data.feed)).href;
    if (!this.canConfigureServer && server !== this.server) throw new ClientError('server_configuration_locked', '切换服务前请退出登录');
    if (!canConfigureFeed && feed !== this.feed) throw new ClientError('update_configuration_locked', '更新进行中');
    const changedOrigin = server !== this.server;
    this.#save({server, feed, automaticLogin: this.automaticLogin});
    if (changedOrigin) this.#clear();
    this.error = null; this.#changed();
  }
  resetConfiguration(canConfigureFeed: boolean): void {
    if (!this.canConfigureServer) throw new ClientError('server_configuration_locked', '切换服务前请退出登录');
    if (!canConfigureFeed) throw new ClientError('update_configuration_locked', '更新进行中');
    this.saveConfiguration({server: this.defaultServer, feed: this.defaultFeed}, canConfigureFeed);
  }
  setAutomaticLogin(value: unknown): void {
    const enabled = boolean(value); if (this.busy) throw new ClientError('operation_busy', '操作进行中');
    if (enabled && this.#token) this.#credentials().write(this.#token); else if (!enabled) this.#credentials().clear();
    this.#save({server: this.server, feed: this.feed, automaticLogin: enabled}); this.#changed();
  }
}
