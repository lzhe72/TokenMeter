import { constants, lstatSync, fstatSync, mkdirSync, openSync, closeSync, readFileSync, writeFileSync, renameSync, unlinkSync, realpathSync, existsSync } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { dirname, isAbsolute, join, normalize, resolve } from 'node:path';
import { ClientError } from './validation.ts';

function unsafe(): never { throw new ClientError('unsafe_storage', '数据目录或文件权限不安全，操作已停止'); }
export function privateDirectory(path: string): string {
  if (!isAbsolute(path) || normalize(path) !== path) unsafe();
  if (!existsSync(path)) {
    const parent = dirname(path); if (!existsSync(parent)) privateDirectory(parent);
    if (realpathSync(parent) !== parent) unsafe();
    mkdirSync(path, { mode: 0o700 });
  }
  const stat = lstatSync(path);
  if (stat.isSymbolicLink() || !stat.isDirectory() || stat.uid !== process.getuid?.() || (stat.mode & 0o777) !== 0o700 || realpathSync(path) !== path) unsafe();
  return path;
}
function existsEntry(path: string): boolean { try { lstatSync(path); return true; } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false; throw error; } }
export function privateRead(path: string): string | null {
  if (!existsEntry(path)) return null;
  const s = lstatSync(path);
  if (!s.isFile() || s.isSymbolicLink() || s.nlink !== 1 || s.uid !== process.getuid?.() || (s.mode & 0o777) !== 0o600 || s.size > 65536) unsafe();
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const opened = fstatSync(fd);
    if (opened.dev !== s.dev || opened.ino !== s.ino || !opened.isFile() || opened.nlink !== 1 || opened.uid !== process.getuid?.() || (opened.mode & 0o777) !== 0o600 || opened.size > 65536) unsafe();
    return readFileSync(fd, 'utf8');
  } finally { closeSync(fd); }
}
export function privateWrite(path: string, text: string): void {
  privateRead(path);
  const temp = join(dirname(path), `.${randomUUID()}.tmp`);
  const fd = openSync(temp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
  try { writeFileSync(fd, text, 'utf8'); } finally { closeSync(fd); }
  try { renameSync(temp, path); } catch (error) { unlinkSync(temp); throw error; }
}
export class CredentialStore {
  path: string;
  constructor(profile: string, origin: string) {
    const dir = privateDirectory(join(privateDirectory(profile), 'credentials'));
    this.path = join(dir, `${createHash('sha256').update(origin).digest('hex')}.token`);
  }
  read(): string | null { const token = privateRead(this.path); if (token !== null && !/^[A-Za-z0-9_-]{43}$/.test(token)) unsafe(); return token; }
  write(token: string): void { if (!/^[A-Za-z0-9_-]{43}$/.test(token)) unsafe(); privateWrite(this.path, token); }
  clear(): void { if (privateRead(this.path) !== null) unlinkSync(this.path); }
}
export function resolveProfile({ appPath, defaultPath, argv }: {appPath: string; defaultPath: string; argv: string[]}): string {
  const path = resolve(appPath);
  const canonicalApp = existsSync(path) ? realpathSync(path) : join(realpathSync(dirname(path)), path.split('/').at(-1)!);
  if (path !== canonicalApp) unsafe();
  const options = argv.flatMap((arg, i) => arg.startsWith('--user-data-dir=') ? [arg.slice(16)] : arg === '--user-data-dir' ? [argv[i + 1]] : []);
  if (options.length > 1 || (options.length && (!options[0] || !isAbsolute(options[0])))) unsafe();
  const ports = argv.filter(arg => arg.startsWith('--diagnostic-cdp-port=')).map(arg => arg.slice(22));
  if (ports.length > 1 || (ports.length && (!options.length || !/^[1-9][0-9]{3,4}$/.test(ports[0]) || +ports[0] > 65535 || +ports[0] < 1024))) unsafe();
  const sidecar = join(dirname(canonicalApp), 'TokenMeter.runtime.json');
  const existing = privateRead(sidecar);
  if (existing !== null) {
    let data: Record<string, unknown>; try { data = JSON.parse(existing); } catch { unsafe(); }
    if (!data || data.schema_version !== 1 || data.app_path !== canonicalApp || typeof data.profile_path !== 'string') unsafe();
    if (data.diagnostic_cdp_port !== undefined && (!Number.isInteger(data.diagnostic_cdp_port) || Number(data.diagnostic_cdp_port) < 1024 || Number(data.diagnostic_cdp_port) > 65535)) unsafe();
    if (ports.length && Number(ports[0]) !== data.diagnostic_cdp_port) unsafe();
    const profile = privateDirectory(data.profile_path);
    if (options.length && options[0] !== profile) unsafe();
    return profile;
  }
  const profile = privateDirectory(options[0] ?? defaultPath);
  if (options.length) privateWrite(sidecar, JSON.stringify({ schema_version: 1, app_path: canonicalApp, profile_path: profile, ...(ports.length ? {diagnostic_cdp_port: Number(ports[0])} : {}) }));
  return profile;
}
