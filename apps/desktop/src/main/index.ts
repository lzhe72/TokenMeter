import { app, BrowserWindow, Menu, protocol, ipcMain, session, nativeTheme } from 'electron';
import { readFileSync, realpathSync, existsSync } from 'node:fs';
import { dirname, join, resolve, extname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { Accounts } from './accounts';
import { UpdateDiscovery } from './discovery';
import { privateDirectory, privateRead, resolveProfile } from './storage';
import { ClientError, record, string } from './validation';
import { createUpdater, validateUpdateURL } from './updater';
import type { BuildInfo, Updater } from './updater';
import type { Snapshot } from '../shared/types';

const UI = 'tokenmeter://app/index.html';
protocol.registerSchemesAsPrivileged([{scheme: 'tokenmeter', privileges: {standard: true, secure: true, supportFetchAPI: true, corsEnabled: false}}]);
let window: BrowserWindow | null = null;
let accounts: Accounts;
let updater: Updater;
let buildInfo: BuildInfo;
const discovery = new UpdateDiscovery();
function snapshot(): Snapshot {
  return {version: buildInfo.version, build: buildInfo.build, server: accounts.server, defaultServer: accounts.defaultServer,
    feed: accounts.feed, defaultFeed: accounts.defaultFeed, automaticLogin: accounts.automaticLogin,
    account: accounts.account, users: accounts.users, audit: accounts.audit, busy: accounts.busy,
    identityVerified: accounts.identityVerified, lastIdentityCheck: accounts.lastIdentityCheck, pendingLogout: accounts.pendingLogout,
    error: accounts.error, passwordStatus: accounts.passwordStatus, adminStatus: accounts.adminStatus,
    canConfigureServer: accounts.canConfigureServer, canRetryRestore: accounts.canRetryRestore, updates: updater.snapshot()};
}
function changed(): void {
  if (!accounts || !updater) return;
  if (discovery.shouldCheck({server: accounts.server, feed: accounts.feed, account: accounts.account, identityVerified: accounts.identityVerified, canCheck: updater.snapshot().canCheck})) void updater.check().catch(error => accounts.fail(error));
  if (window && !window.isDestroyed()) window.webContents.send('tokenmeter:state', snapshot());
}
function startup(): void {
  app.setName('TokenMeter');
  const appPath = app.isPackaged ? resolve(process.execPath, '../../..') : realpathSync(app.getAppPath());
  const defaultPath = join(app.getPath('appData'), 'TokenMeter');
  const profilePath = resolveProfile({appPath, defaultPath, argv: process.argv});
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
  const configPath = app.isPackaged ? join(process.resourcesPath, 'release-config.json') : resolve(app.getAppPath(), '../../releases/v0.1.0-20260929T074814Z/local-release.json');
  const config = record(JSON.parse(readFileSync(configPath, 'utf8')));
  buildInfo = Object.fromEntries(['release_id','candidate_sha','version','build','bundle_id','api_url','update_feed_url','update_public_key','certificate_sha256'].map(key => [key, string(config[key] ?? (key === 'candidate_sha' && !app.isPackaged ? 'development' : undefined), 256)])) as unknown as BuildInfo;
  accounts = new Accounts(profilePath, buildInfo, validateUpdateURL, changed);
  updater = createUpdater({app, profilePath, buildInfo, getFeed: () => accounts.feed, onChange: changed});
  if (!app.requestSingleInstanceLock()) { app.exit(0); return; }
  app.on('second-instance', () => { window?.show(); window?.focus(); });
  app.whenReady().then(async () => {
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
      try {
        switch (method) {
          case 'snapshot': break;
          case 'login': await accounts.login(input); break;
          case 'changePassword': await accounts.changePassword(input); break;
          case 'logout': await accounts.logout(); break;
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
          default: throw new ClientError('invalid_operation', '操作无效');
        }
      } catch (error) { accounts.fail(error); }
      changed(); return snapshot();
    });
    await window.loadURL(UI);
    await accounts.restore();
  }).catch(() => { console.error('TokenMeter startup_failed'); app.exit(1); });
  app.on('window-all-closed', () => app.quit());
}
try { startup(); } catch (error) { console.error(`TokenMeter ${error instanceof ClientError ? error.code : 'startup_failed'}`); app.exit(1); }
