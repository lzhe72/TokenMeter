/** Validate the update archive; let Electron/Squirrel own replacement and restart. */
import type { App, AutoUpdater } from 'electron';
import { createHash, createPublicKey, randomBytes, verify } from 'node:crypto';
import { execFile } from 'node:child_process';
import { createReadStream } from 'node:fs';
import * as fs from 'node:fs/promises';
import * as http from 'node:http';
import * as path from 'node:path';
import { promisify } from 'node:util';

const execute = promisify(execFile);
const MAX_ARCHIVE = 512 * 1024 * 1024;
const MAX_UNPACKED = 2 * 1024 * 1024 * 1024;
export interface BuildInfo {
  release_id: string; candidate_sha: string; version: string; build: string; bundle_id: string;
  api_url: string; update_feed_url: string; update_public_key: string; certificate_sha256: string;
}
export interface UpdaterSnapshot {
  phase: 'idle' | 'checking' | 'available' | 'current' | 'downloading' | 'verifying' | 'ready' | 'installing' | 'error';
  canCheck: boolean; canConfigure: boolean; status: string; errorCode: string | null;
  availableBuild: string | null; availableVersion: string | null;
}
export interface UpdateMetadata {
  schema_version: number; version: string; build: string; url: string; sha256: string;
  bytes: number; ed25519_signature: string;
}
export interface Updater { snapshot(): UpdaterSnapshot; check(): Promise<void>; install(): Promise<void>; cancel(): void }
export class UpdateError extends Error {
  readonly code: string;
  constructor(code: string) { super(code); this.name = 'UpdateError'; this.code = code; }
}
function reject(code: string): never { throw new UpdateError(code); }
function canonicalBase64(value: unknown, bytes: number): value is string {
  return typeof value === 'string' && Buffer.from(value, 'base64').length === bytes && Buffer.from(value, 'base64').toString('base64') === value;
}
export function validateUpdateURL(value: string): URL {
  if (typeof value !== 'string' || value.length > 2048 || value.trim() !== value || /[\\\s\u0000-\u001f?#]/.test(value)) reject('update_source_rejected');
  let url: URL; try { url = new URL(value); } catch { return reject('update_source_rejected'); }
  if (url.username || url.password || url.search || url.hash || !url.hostname || !['http:', 'https:'].includes(url.protocol)) reject('update_source_rejected');
  if (url.protocol === 'http:') {
    const authority = value.match(/^http:\/\/([^/]+)/)?.[1];
    if (!authority || !/^(127\.0\.0\.1|localhost|\[::1\])(?::[1-9][0-9]{0,4})?$/.test(authority)) reject('update_source_rejected');
  }
  if (url.port && (+url.port < 1 || +url.port > 65535)) reject('update_source_rejected');
  return url;
}
export function compareVersions(left: string, right: string): number {
  if (![left, right].every(value => /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/.test(value))) reject('update_metadata_invalid');
  const a = left.split('.').map(BigInt), b = right.split('.').map(BigInt);
  for (let i = 0; i < 3; i++) { if (a[i]! > b[i]!) return 1; if (a[i]! < b[i]!) return -1; }
  return 0;
}
export function validateMetadata(input: unknown, current: Pick<BuildInfo, 'version' | 'build'>, requireNew = true): UpdateMetadata {
  if (!input || typeof input !== 'object') reject('update_metadata_invalid');
  const item = input as UpdateMetadata;
  if (item.schema_version !== 1 || typeof item.version !== 'string' || typeof item.build !== 'string' || !/^[1-9][0-9]{0,9}$/.test(item.build)
    || typeof item.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(item.sha256) || !Number.isSafeInteger(item.bytes) || item.bytes < 1 || item.bytes > MAX_ARCHIVE
    || !canonicalBase64(item.ed25519_signature, 64)) reject('update_metadata_invalid');
  const comparison = compareVersions(item.version, current.version);
  if (requireNew && (comparison <= 0 || BigInt(item.build) <= BigInt(current.build))) reject('update_metadata_invalid');
  validateUpdateURL(item.url);
  return { schema_version: 1, version: item.version, build: item.build, url: item.url, sha256: item.sha256, bytes: item.bytes, ed25519_signature: item.ed25519_signature };
}
export function verifyArchiveBytes(bytes: Buffer, item: UpdateMetadata, publicKey: string): void {
  if (bytes.length !== item.bytes || createHash('sha256').update(bytes).digest('hex') !== item.sha256) reject('update_integrity_failed');
  if (!canonicalBase64(publicKey, 32) || !canonicalBase64(item.ed25519_signature, 64)) reject('update_signature_rejected');
  const key = createPublicKey({ key: Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), Buffer.from(publicKey, 'base64')]), format: 'der', type: 'spki' });
  if (!verify(null, bytes, key, Buffer.from(item.ed25519_signature, 'base64'))) reject('update_signature_rejected');
}
export function validateArchiveEntry(name: string): string {
  const parts = name.replace(/\/$/, '').split('/');
  if (name.length > 2048 || name.includes('\\') || /[\u0000-\u001f]/.test(name) || parts.some(part => !part || part === '.' || part === '..')
    || !['TokenMeter.app', '__MACOSX'].includes(parts[0]!)) reject('update_bundle_invalid');
  return name;
}
export async function fetchLimited(address: string, limit: number, signal: AbortSignal): Promise<Buffer | null> {
  let url = validateUpdateURL(address);
  for (let redirects = 0; redirects < 6; redirects++) {
    const response = await fetch(url, { signal: AbortSignal.any([signal, AbortSignal.timeout(60_000)]), redirect: 'manual', headers: { 'Accept-Encoding': 'identity' } });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      await response.body?.cancel();
      const location = response.headers.get('location');
      if (!location) reject('update_transport_rejected');
      try { url = validateUpdateURL(new URL(location, url).toString()); } catch { reject('update_transport_rejected'); }
      continue;
    }
    if (response.status === 204) { await response.body?.cancel(); return null; }
    if (response.status !== 200 || !response.body) { await response.body?.cancel(); reject('update_download_failed'); }
    const advertised = response.headers.get('content-length');
    if (advertised && (!/^[0-9]+$/.test(advertised) || +advertised > limit)) { await response.body.cancel(); reject('update_integrity_failed'); }
    const chunks: Buffer[] = []; let size = 0;
    for await (const chunk of response.body) {
      size += chunk.length;
      if (size > limit) { reject('update_integrity_failed'); }
      chunks.push(Buffer.from(chunk));
    }
    return Buffer.concat(chunks);
  }
  return reject('update_transport_rejected');
}

/** Enumerate the signed ZIP before ditto: reject traversal and symlink-parent writes. */
export async function inspectZip(archive: string): Promise<void> {
  // yauzl is a pinned mature ZIP parser. Only bounded link text is read here.
  const yauzl = await import('yauzl' as string) as any;
  await new Promise<void>((resolve, rejectPromise) => {
    yauzl.open(archive, { lazyEntries: true, validateEntrySizes: true, strictFileNames: true }, (error: Error | null, zip: any) => {
      if (error || !zip) { rejectPromise(new UpdateError('update_bundle_invalid')); return; }
      const names = new Set<string>(), links = new Set<string>(); let total = 0, count = 0; let stopped = false;
      const fail = () => { if (!stopped) { stopped = true; zip.close(); rejectPromise(new UpdateError('update_bundle_invalid')); } };
      zip.on('error', fail);
      zip.on('entry', (entry: any) => {
        try {
          const name = validateArchiveEntry(entry.fileName), normalized = name.replace(/\/$/, '');
          const mode = (entry.externalFileAttributes >>> 16) & 0xffff;
          if (++count > 100_000 || names.has(normalized) || entry.generalPurposeBitFlag & 1 || (total += entry.uncompressedSize) > MAX_UNPACKED) return fail();
          names.add(normalized);
          const kind = mode & 0xf000;
          if (kind !== 0 && ![0x8000, 0x4000, 0xa000].includes(kind)) return fail();
          if (kind !== 0xa000) { zip.readEntry(); return; }
          if (entry.uncompressedSize > 4096) return fail();
          links.add(normalized);
          zip.openReadStream(entry, (readError: Error | null, stream: NodeJS.ReadableStream) => {
            if (readError) return fail();
            const chunks: Buffer[] = []; let length = 0;
            stream.on('data', (chunk: Buffer) => { length += chunk.length; if (length > 4096) fail(); else chunks.push(chunk); });
            stream.on('error', fail);
            stream.on('end', () => {
              const target = Buffer.concat(chunks).toString('utf8');
              const destination = path.posix.normalize(path.posix.join(path.posix.dirname(normalized), target));
              if (path.posix.isAbsolute(target) || target.includes('\\') || /[\u0000-\u001f]/.test(target) || !destination.startsWith('TokenMeter.app/')) return fail();
              if (!stopped) zip.readEntry();
            });
          });
        } catch { fail(); }
      });
      zip.on('end', () => {
        for (const name of names) {
          let parent = path.posix.dirname(name);
          while (parent !== '.') { if (links.has(parent)) return fail(); parent = path.posix.dirname(parent); }
        }
        if (!names.has('TokenMeter.app/Contents/Info.plist')) return fail();
        if (!stopped) { stopped = true; resolve(); }
      });
      zip.readEntry();
    });
  });
}
async function command(executable: string, args: string[]): Promise<string> {
  try { const result = await execute(executable, args, { timeout: 60_000, maxBuffer: 2 * 1024 * 1024 }); return result.stdout + result.stderr; }
  catch { return reject('update_bundle_invalid'); }
}
export async function verifyCodeRequirement(bundle: string, requirement: string): Promise<void> {
  // codesign treats an unprefixed value as a requirements file path.
  await command('/usr/bin/codesign', ['--verify', '--deep', '--strict', '-R', '=' + requirement, bundle]);
}
async function verifyBundle(archive: string, work: string, item: UpdateMetadata, build: BuildInfo, executable: string): Promise<void> {
  await inspectZip(archive);
  const extracted = path.join(work, 'extracted'); await fs.mkdir(extracted, { mode: 0o700 });
  await command('/usr/bin/ditto', ['-x', '-k', archive, extracted]);
  const bundle = path.join(extracted, 'TokenMeter.app');
  const info = JSON.parse(await command('/usr/bin/plutil', ['-convert', 'json', '-o', '-', path.join(bundle, 'Contents/Info.plist')])) as Record<string, unknown>;
  if (info.CFBundleIdentifier !== build.bundle_id || info.CFBundleShortVersionString !== item.version || String(info.CFBundleVersion) !== item.build) reject('update_bundle_invalid');
  await command('/usr/bin/codesign', ['--verify', '--deep', '--strict', bundle]);
  const currentApp = path.resolve(executable, '../../..');
  if (!currentApp.endsWith('/TokenMeter.app')) reject('update_bundle_invalid');
  const output = await command('/usr/bin/codesign', ['-d', '-r-', currentApp]);
  const requirement = output.split('\n').find(line => line.startsWith('designated => '))?.slice('designated => '.length);
  if (!requirement || !requirement.includes('certificate')) reject('update_bundle_invalid');
  await verifyCodeRequirement(bundle, requirement);
  const prefix = path.join(work, 'certificate-');
  await command('/usr/bin/codesign', ['--display', '--extract-certificates=' + prefix, bundle]);
  if (createHash('sha256').update(await fs.readFile(prefix + '0')).digest('hex') !== build.certificate_sha256) reject('update_bundle_invalid');
  const resource = JSON.parse(await fs.readFile(path.join(bundle, 'Contents/Resources/release-config.json'), 'utf8')) as BuildInfo;
  if (resource.version !== item.version || resource.build !== item.build || resource.bundle_id !== build.bundle_id
    || resource.update_public_key !== build.update_public_key || resource.certificate_sha256 !== build.certificate_sha256) reject('update_bundle_invalid');
}

async function nativeInstall(updater: AutoUpdater, archive: string, item: UpdateMetadata, change: (phase: UpdaterSnapshot['phase']) => void): Promise<void> {
  const nonce = randomBytes(24).toString('hex'); let port = 0;
  const server = http.createServer((request, response) => {
    if (request.method !== 'GET' || request.headers.host !== `127.0.0.1:${port}` || request.socket.remoteAddress !== '127.0.0.1') { response.writeHead(403).end(); return; }
    if (request.url === `/${nonce}/feed`) {
      response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      response.end(JSON.stringify({ url: `http://127.0.0.1:${port}/${nonce}/archive.zip`, name: item.version, notes: 'TokenMeter internal update', pub_date: new Date().toISOString() }));
    } else if (request.url === `/${nonce}/archive.zip`) {
      response.writeHead(200, { 'Content-Type': 'application/zip', 'Content-Length': item.bytes, 'Cache-Control': 'no-store' });
      const stream = createReadStream(archive); stream.on('error', () => response.destroy()); stream.pipe(response);
    } else response.writeHead(404).end();
  });
  await new Promise<void>((resolve, rejectPromise) => { server.once('error', rejectPromise); server.listen(0, '127.0.0.1', () => resolve()); });
  port = (server.address() as { port: number }).port;
  try {
    await new Promise<void>((resolve, rejectPromise) => {
      const cleanup = () => { clearTimeout(timer); updater.off('error', failed); updater.off('update-not-available', absent); updater.off('update-downloaded', downloaded); };
      const failed = () => { cleanup(); rejectPromise(new UpdateError('update_native_failed')); };
      const absent = () => failed();
      const downloaded = () => { cleanup(); change('ready'); resolve(); };
      const timer = setTimeout(failed, 180_000);
      updater.once('error', failed); updater.once('update-not-available', absent); updater.once('update-downloaded', downloaded);
      try { updater.setFeedURL({ url: `http://127.0.0.1:${port}/${nonce}/feed` }); updater.checkForUpdates(); } catch { failed(); }
    });
  } finally {
    server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
  }
}
async function removePrivateUpdateWork(work: string, profilePath: string): Promise<void> {
  if (path.dirname(work) !== profilePath || !path.basename(work).startsWith('update-')) reject('update_cleanup_failed');
  // Electron's patched fs treats app.asar as a virtual directory. A recursive
  // rm then leaves the real .asar file behind and fails with ENOTEMPTY.
  const originalFs = require('original-fs') as typeof import('node:fs');
  await originalFs.promises.rm(work, { recursive: true, force: true });
  try {
    await originalFs.promises.lstat(work);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
    throw error;
  }
  reject('update_cleanup_failed');
}
export function createUpdater(options: { app: App; profilePath: string; buildInfo: BuildInfo; getFeed(): string; onChange(): void }): Updater {
  const { app, profilePath, buildInfo, getFeed, onChange } = options;
  let state: UpdaterSnapshot = { phase: 'idle', canCheck: true, canConfigure: true, status: '尚未检查更新', errorCode: null, availableBuild: null, availableVersion: null };
  let metadata: UpdateMetadata | null = null, controller: AbortController | null = null, handedOff = false, checkedFeed: string | null = null;
  function change(phase: UpdaterSnapshot['phase'], errorCode: string | null = null): void {
    const busy = ['checking', 'downloading', 'verifying', 'ready', 'installing'].includes(phase);
    state = { ...state, phase, canCheck: !busy && !handedOff, canConfigure: !busy && !handedOff, errorCode,
      status: errorCode ?? ({ idle: '尚未检查更新', checking: '正在检查更新', available: '发现新版本', current: '当前已是最新版本', downloading: '正在下载更新', verifying: '正在验证更新签名', ready: '更新验证完成', installing: '正在安装并重新启动', error: '更新失败' }[phase]) };
    onChange();
  }
  return {
    snapshot: () => ({ ...state }),
    async check() {
      if (!state.canCheck) return;
      controller = new AbortController(); metadata = null; checkedFeed = getFeed();
      state.availableVersion = null; state.availableBuild = null; change('checking');
      try {
        const bytes = await fetchLimited(checkedFeed, 64 * 1024, controller.signal);
        if (bytes === null) { change('current'); return; }
        let item: unknown; try { item = JSON.parse(bytes.toString('utf8')); } catch { reject('update_metadata_invalid'); }
        const advertised = validateMetadata(item, buildInfo, false);
        if (compareVersions(advertised.version, buildInfo.version) <= 0 && BigInt(advertised.build) <= BigInt(buildInfo.build)) { change('current'); return; }
        metadata = validateMetadata(advertised, buildInfo); state.availableVersion = metadata.version; state.availableBuild = metadata.build; change('available');
      } catch (error) { change('error', error instanceof UpdateError ? error.code : controller.signal.aborted ? 'update_cancelled' : 'update_download_failed'); }
      finally { controller = null; }
    },
    async install() {
      if (state.phase !== 'available' || !metadata || handedOff) return;
      if (checkedFeed !== getFeed()) { metadata = null; change('error', 'update_metadata_invalid'); return; }
      if (!app.isPackaged || process.platform !== 'darwin') { change('error', 'update_unavailable'); return; }
      const item = metadata; controller = new AbortController(); let work: string | null = null;
      let nativeUpdater: AutoUpdater | null = null, terminalError: string | null = null;
      change('downloading');
      try {
        const bytes = await fetchLimited(item.url, item.bytes, controller.signal);
        if (!bytes) reject('update_download_failed');
        verifyArchiveBytes(bytes, item, buildInfo.update_public_key); change('verifying');
        work = await fs.mkdtemp(path.join(profilePath, 'update-')); await fs.chmod(work, 0o700);
        const archive = path.join(work, 'verified.zip'); await fs.writeFile(archive, bytes, { mode: 0o600, flag: 'wx' });
        await verifyBundle(archive, work, item, buildInfo, app.getPath('exe'));
        if (controller.signal.aborted) reject('update_cancelled');
        nativeUpdater = (require('electron') as { autoUpdater: AutoUpdater }).autoUpdater;
        handedOff = true;
        await nativeInstall(nativeUpdater, archive, item, phase => change(phase));
      } catch (error) {
        terminalError = error instanceof UpdateError ? error.code : controller?.signal.aborted ? 'update_cancelled' : 'update_download_failed';
      } finally {
        controller = null;
        if (work) {
          try { await removePrivateUpdateWork(work, profilePath); }
          catch (error) {
            console.error('TokenMeter update_cleanup_failed', (error as NodeJS.ErrnoException).code ?? 'unknown');
            terminalError = 'update_cleanup_failed';
          }
        }
      }
      if (terminalError) { change('error', terminalError); return; }
      if (!nativeUpdater) { change('error', 'update_native_failed'); return; }
      change('installing');
      // Squirrel owns a verified private copy; scratch has been removed before exit.
      const readyUpdater = nativeUpdater;
      setTimeout(() => readyUpdater.quitAndInstall(), 250);
    },
    cancel() { if (!handedOff) controller?.abort(); },
  };
}
