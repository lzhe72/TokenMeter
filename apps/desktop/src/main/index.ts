import { app, BrowserWindow, Menu, protocol, ipcMain, session, nativeTheme, dialog, safeStorage } from 'electron';
import { readFileSync, realpathSync, existsSync } from 'node:fs';
import { dirname, join, resolve, extname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { Accounts } from './accounts';
import { UpdateDiscovery } from './discovery';
import { keychainApplicationName, privateDirectory, privateRead, resolveProfile } from './storage';
import { ClientError, record, string, boolean } from './validation';
import { createUpdater, validateUpdateURL } from './updater';
import type { BuildInfo, Updater } from './updater';
import type { Snapshot } from '../shared/types';
import { SourceAccess } from './source-access';
import type { SourceTool } from './source-store';
import { SourceStore } from './source-store';
import { SourceHelper } from './source-helper';
import { SourceAudit } from './source-audit';

const UI = 'tokenmeter://app/index.html';
protocol.registerSchemesAsPrivileged([{scheme: 'tokenmeter', privileges: {standard: true, secure: true, supportFetchAPI: true, corsEnabled: false}}]);
let window: BrowserWindow | null = null;
let accounts: Accounts;
let updater: Updater;
let buildInfo: BuildInfo;
let sourceAccess: SourceAccess | null = null;
let sourceAudit: SourceAudit | null = null;
let sourceEpoch = 0;
let sourceIdentityKey = '';
let sourcesReady = false;
let sourceSuspended = false;
const sourceErrors: Record<SourceTool, string | null> = {codex: null, claude_code: null};
const discovery = new UpdateDiscovery();
function sourceIdentityFingerprint(): string {
  return JSON.stringify([accounts.server, accounts.account?.id ?? null,
    accounts.identityVerified && !accounts.account?.must_change_password && !!accounts.account?.is_active && !sourceSuspended]);
}
function sourceErrorCode(error: unknown): string {
  const code = error instanceof ClientError ? error.code : (error as {code?: unknown})?.code;
  return typeof code === 'string' && /^[a-z_]{3,60}$/.test(code) ? code : 'source_unavailable';
}
function snapshot(): Snapshot {
  return {version: buildInfo.version, build: buildInfo.build, server: accounts.server, defaultServer: accounts.defaultServer,
    feed: accounts.feed, defaultFeed: accounts.defaultFeed, automaticLogin: accounts.automaticLogin,
    account: accounts.account, users: accounts.users, audit: accounts.audit, busy: accounts.busy,
    identityVerified: accounts.identityVerified, lastIdentityCheck: accounts.lastIdentityCheck, pendingLogout: accounts.pendingLogout,
    error: accounts.error, passwordStatus: accounts.passwordStatus, adminStatus: accounts.adminStatus,
    canConfigureServer: accounts.canConfigureServer, canRetryRestore: accounts.canRetryRestore, updates: updater.snapshot(),
    sources: sourceAccess?.snapshot() ?? {codex: {confirmed: null, pending: null, candidates: [], incomplete: false},
      claude_code: {confirmed: null, pending: null, candidates: [], incomplete: false}},
    sourcesReady, sourceErrors: {...sourceErrors}};
}
function pushSnapshot(): void {
  if (window && !window.isDestroyed()) window.webContents.send('tokenmeter:state', snapshot());
}
function changed(): void {
  if (!accounts || !updater) return;
  if (sourceAccess) {
    const next = sourceIdentityFingerprint();
    if (next !== sourceIdentityKey) {
      sourceIdentityKey = next; sourceEpoch++; sourcesReady = false;
      sourceErrors.codex = null; sourceErrors.claude_code = null;
      const epoch = sourceEpoch;
      void sourceAccess.syncIdentity().then(() => {
        if (sourceEpoch === epoch) {
          sourcesReady = accounts.identityVerified && !!accounts.account &&
            !accounts.account.must_change_password && accounts.account.is_active && !sourceSuspended;
          pushSnapshot();
        }
      }).catch(error => { if (sourceEpoch === epoch) { sourcesReady = false; accounts.fail(error); } });
    }
  }
  if (discovery.shouldCheck({server: accounts.server, feed: accounts.feed, account: accounts.account, identityVerified: accounts.identityVerified, canCheck: updater.snapshot().canCheck})) void updater.check().catch(error => accounts.fail(error));
  pushSnapshot();
}
function startup(): void {
  app.setName('TokenMeter');
  const appPath = app.isPackaged ? resolve(process.execPath, '../../..') : realpathSync(app.getAppPath());
  const defaultPath = join(app.getPath('appData'), 'TokenMeter');
  const profilePath = resolveProfile({appPath, defaultPath, argv: process.argv});
  app.setName(keychainApplicationName(profilePath, defaultPath));
  app.setPath('userData', profilePath);
  app.setPath('sessionData', privateDirectory(join(profilePath, 'chromium')));
  app.setAppLogsPath(privateDirectory(join(profilePath, 'logs')));
  const runtime = privateRead(join(dirname(appPath), 'TokenMeter.runtime.json'));
  if (runtime) {
    const port = record(JSON.parse(runtime)).diagnostic_cdp_port;
    if (port !== undefined) {
      const probe = spawnSync('/usr/sbin/lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-t'], {encoding: 'utf8'});
      if (probe.error || probe.status !== 1 || probe.stdout.trim() || probe.stderr.trim()) throw new ClientError('diagnostic_port_unavailable', '诊断端口不可用');
      app.commandLine.appendSwitch('remote-debugging-address', '127.0.0.1');
      app.commandLine.appendSwitch('remote-debugging-port', String(port));
    }
  }
  let configPath: string;
  if (app.isPackaged) configPath = join(process.resourcesPath, 'release-config.json');
  else {
    const releaseRoot = resolve(app.getAppPath(), '../../releases');
    const current = record(JSON.parse(readFileSync(join(releaseRoot, 'current.json'), 'utf8')));
    const releaseId = string(current.release_id, 80);
    if (!/^v[0-9]+\.[0-9]+\.[0-9]+-[0-9]{8}T[0-9]{6}Z$/.test(releaseId))
      throw new ClientError('invalid_release_config', '当前版本配置无效');
    configPath = join(releaseRoot, releaseId, 'local-release.json');
  }
  const config = record(JSON.parse(readFileSync(configPath, 'utf8')));
  buildInfo = Object.fromEntries(['release_id','candidate_sha','version','build','bundle_id','api_url','update_feed_url','update_public_key','certificate_sha256'].map(key => [key, string(config[key] ?? (key === 'candidate_sha' && !app.isPackaged ? 'development' : undefined), 256)])) as unknown as BuildInfo;
  accounts = new Accounts(profilePath, buildInfo, validateUpdateURL, changed);
  updater = createUpdater({app, profilePath, buildInfo, getFeed: () => accounts.feed, onChange: changed});
  if (!app.requestSingleInstanceLock()) { app.exit(0); return; }
  app.on('second-instance', () => { window?.show(); window?.focus(); });
  app.whenReady().then(async () => {
    if (runtime) {
      const nonce = record(JSON.parse(runtime)).diagnostic_source_audit_nonce;
      if (nonce !== undefined) sourceAudit = new SourceAudit(profilePath, string(nonce, 64));
    }
    sourceAccess = new SourceAccess({
      store: new SourceStore(profilePath, safeStorage),
      getIdentity: () => ({origin: accounts.server, accountId: accounts.account?.id ?? null,
        verified: accounts.identityVerified && !!accounts.account?.is_active &&
          !accounts.account?.must_change_password && !sourceSuspended, epoch: sourceEpoch}),
      chooseDirectory: async () => {
        if (!window || window.isDestroyed()) throw new ClientError('picker_unavailable', '目录选择器不可用');
        const result = await dialog.showOpenDialog(window, {title: '选择日志目录',
          properties: ['openDirectory', 'dontAddToRecent']});
        return result.canceled ? {canceled: true} : {canceled: false, rootPath: result.filePaths[0]};
      },
      openHelper: (path, options) => SourceHelper.open(path, {
        ...options, ...(!app.isPackaged ? {binaryPath: join(app.getAppPath(), '.local', 'source-helper')} : {})}),
      onChange: pushSnapshot,
      onAudit: event => sourceAudit?.record(event)
    });
    const renderer = resolve(__dirname, '../renderer');
    protocol.handle('tokenmeter', request => {
      const url = new URL(request.url);
      if (url.hostname !== 'app' || request.method !== 'GET' || url.search || url.hash) return new Response(null, {status: 403});
      let name: string; try { name = decodeURIComponent(url.pathname); } catch { return new Response(null, {status: 400}); }
      const file = resolve(renderer, '.' + name);
      if (!file.startsWith(renderer + '/') || !existsSync(file) || realpathSync(file) !== file) return new Response(null, {status: 404});
      const types: Record<string, string> = {'.html': 'text/html', '.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml'};
      try { return new Response(readFileSync(file), {headers: {'Content-Type': types[extname(file)] ?? 'application/octet-stream', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"}}); }
      catch { return new Response(null, {status: 404}); }
    });
    session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
    session.defaultSession.setPermissionCheckHandler(() => false);
    window = new BrowserWindow({width: 1080, height: 800, minWidth: 760, minHeight: 640, title: '账号与设备', backgroundColor: nativeTheme.shouldUseDarkColors ? '#1e1e1e' : '#f5f5f7', webPreferences: {preload: join(__dirname, '../preload/index.cjs'), sandbox: true, contextIsolation: true, nodeIntegration: false, webSecurity: true, webviewTag: false}});
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      {label:'TokenMeter', submenu:[{role:'about'}, {type:'separator'}, {label:'服务配置…', accelerator:'Command+,', click:() => window?.webContents.send('tokenmeter:open-configuration')}, {type:'separator'}, {role:'hide'}, {role:'hideOthers'}, {role:'unhide'}, {type:'separator'}, {role:'quit'}]},
      {role:'editMenu'}, {label:'显示', submenu:[{role:'resetZoom'}, {role:'zoomIn'}, {role:'zoomOut'}, {type:'separator'}, {role:'togglefullscreen'}]}, {role:'windowMenu'}
    ]));
    window.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
    window.webContents.on('will-navigate', (event, url) => { if (url !== UI) event.preventDefault(); });
    window.webContents.on('will-attach-webview', event => event.preventDefault());
    ipcMain.handle('tokenmeter:invoke', async (event, method: unknown, input: unknown) => {
      if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || event.senderFrame.url !== UI) throw new Error('ipc_sender_rejected');
      const sourceMethod = typeof method === 'string' && ['chooseSource', 'previewSource', 'confirmSource',
        'updateSourceConsent', 'refreshSource', 'revokeSource'].includes(method);
      let sourceTool: SourceTool | null = null;
      try {
        switch (method) {
          case 'snapshot': break;
          case 'login': await accounts.login(input); break;
          case 'changePassword': sourceSuspended = true; changed();
            try { await accounts.changePassword(input); } finally { sourceSuspended = false; changed(); } break;
          case 'logout': sourceSuspended = true; changed();
            try { await accounts.logout(); } finally { sourceSuspended = false; changed(); } break;
          case 'retryLogout': await accounts.retryLogout(); break;
          case 'refresh': await accounts.refresh(); break;
          case 'listUsers': await accounts.listUsers(); break;
          case 'listAudit': await accounts.listAudit(); break;
          case 'manageUser': await accounts.manageUser(input); break;
          case 'saveConfiguration': accounts.saveConfiguration(input, updater.snapshot().canConfigure); break;
          case 'resetConfiguration': accounts.resetConfiguration(updater.snapshot().canConfigure); break;
          case 'setAutomaticLogin': accounts.setAutomaticLogin(input); break;
          case 'checkUpdates': await updater.check(); break;
          case 'installUpdate': await updater.install(); break;
          case 'cancelUpdate': updater.cancel(); break;
          case 'chooseSource': {
            const data = record(input); sourceTool = string(data.tool, 32) as SourceTool;
            if (!['codex', 'claude_code'].includes(sourceTool)) throw new ClientError('invalid_source_tool', '来源类型无效');
            await sourceAccess!.choose(sourceTool); sourceErrors[sourceTool] = null; break;
          }
          case 'previewSource': {
            const data = record(input); const selectionId = string(data.selectionId, 64);
            sourceTool = (['codex', 'claude_code'] as SourceTool[]).find(tool => sourceAccess!.snapshot()[tool].pending?.selectionId === selectionId) ?? null;
            await sourceAccess!.preview(selectionId); if (sourceTool) sourceErrors[sourceTool] = null; break;
          }
          case 'confirmSource': {
            const data = record(input); const selectionId = string(data.selectionId, 64);
            sourceTool = (['codex', 'claude_code'] as SourceTool[]).find(tool => sourceAccess!.snapshot()[tool].pending?.selectionId === selectionId) ?? null;
            await sourceAccess!.confirm(selectionId, boolean(data.collectAllowed), boolean(data.syncIntent));
            if (sourceTool) sourceErrors[sourceTool] = null; break;
          }
          case 'updateSourceConsent': {
            const data = record(input); const sourceId = string(data.sourceId, 64);
            sourceTool = (['codex', 'claude_code'] as SourceTool[]).find(tool => sourceAccess!.snapshot()[tool].confirmed?.sourceId === sourceId) ?? null;
            await sourceAccess!.updateConsent(sourceId, boolean(data.collectAllowed), boolean(data.syncIntent));
            if (sourceTool) sourceErrors[sourceTool] = null; break;
          }
          case 'refreshSource': {
            const sourceId = string(record(input).sourceId, 64);
            sourceTool = (['codex', 'claude_code'] as SourceTool[]).find(tool => sourceAccess!.snapshot()[tool].confirmed?.sourceId === sourceId) ?? null;
            await sourceAccess!.refresh(sourceId); if (sourceTool) sourceErrors[sourceTool] = null; break;
          }
          case 'revokeSource': {
            const sourceId = string(record(input).sourceId, 64);
            sourceTool = (['codex', 'claude_code'] as SourceTool[]).find(tool => sourceAccess!.snapshot()[tool].confirmed?.sourceId === sourceId) ?? null;
            await sourceAccess!.revoke(sourceId); if (sourceTool) sourceErrors[sourceTool] = null; break;
          }
          default: throw new ClientError('invalid_operation', '操作无效');
        }
      } catch (error) {
        if (sourceMethod && sourceTool) sourceErrors[sourceTool] = sourceErrorCode(error);
        else accounts.fail(error);
      }
      if (sourceMethod) pushSnapshot(); else changed();
      return snapshot();
    });
    await window.loadURL(UI);
    await accounts.restore();
  }).catch(() => { console.error('TokenMeter startup_failed'); app.exit(1); });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', () => { sourceAccess?.dispose(); sourceAudit?.close(); });
}
try { startup(); } catch (error) { console.error(`TokenMeter ${error instanceof ClientError ? error.code : 'startup_failed'}`); app.exit(1); }
