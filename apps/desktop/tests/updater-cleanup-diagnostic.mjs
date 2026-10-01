/** Repeat the real update ZIP extraction and scratch cleanup without launching the App. */
import {execFile} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import * as fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve, join} from 'node:path';
import {performance} from 'node:perf_hooks';
import {promisify} from 'node:util';

const run = promisify(execFile);

function argumentsFor(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    if (!argv[index]?.startsWith('--') || !argv[index + 1] || values.has(argv[index])) {
      throw new Error('Expected unique --archive, --sha256, --output and optional --filesystem pairs');
    }
    values.set(argv[index], argv[index + 1]);
  }
  if ((values.size !== 3 && values.size !== 4) || !values.has('--archive') || !values.has('--sha256') || !values.has('--output')
    || [...values.keys()].some(key => !['--archive', '--sha256', '--output', '--filesystem'].includes(key))) {
    throw new Error('Expected --archive, --sha256 and --output');
  }
  const sha256 = values.get('--sha256');
  if (!/^[a-f0-9]{64}$/.test(sha256)) throw new Error('Archive SHA-256 must be lowercase hex');
  const filesystem = values.get('--filesystem') ?? 'node';
  if (!['node', 'original'].includes(filesystem)) throw new Error('Filesystem must be node or original');
  return {archive: resolve(values.get('--archive')), expectedSha256: sha256, output: resolve(values.get('--output')), filesystem};
}

async function digestFile(file) {
  const digest = createHash('sha256');
  for await (const chunk of createReadStream(file)) digest.update(chunk);
  return digest.digest('hex');
}

async function exists(file) {
  try { await fs.lstat(file); return true; }
  catch (error) { if (error?.code === 'ENOENT') return false; throw error; }
}

async function main() {
  const {archive, expectedSha256, output, filesystem} = argumentsFor(process.argv.slice(2));
  const archiveStat = await fs.lstat(archive);
  if (!archiveStat.isFile() || archiveStat.isSymbolicLink()) throw new Error('Archive must be a regular owned file');
  const actualSha256 = await digestFile(archive);
  if (actualSha256 !== expectedSha256) throw new Error('Archive SHA-256 mismatch');
  const parent = await fs.lstat(resolve(output, '..'));
  if (!parent.isDirectory() || parent.isSymbolicLink()) throw new Error('Output parent is not a real directory');
  await fs.mkdir(output, {mode: 0o700});
  await fs.chmod(output, 0o700);
  const work = join(output, 'work');
  const extracted = join(work, 'extracted');
  const report = {
    schema_version: 1,
    kind: 'real_zip_cleanup_component_diagnostic',
    archive: {path: archive, sha256: actualSha256, bytes: archiveStat.size},
    runtime: {node: process.versions.node, electron: process.versions.electron ?? null, filesystem,
      electron_run_as_node: process.env.ELECTRON_RUN_AS_NODE === '1'},
    extraction_ms: null,
    cleanup_ms: null,
    extracted_app_present: false,
    cleanup_error: null,
    work_remaining: null,
    top_level_remaining: [],
    state: 'FAIL',
  };
  try {
    await fs.mkdir(work, {mode: 0o700});
    await fs.mkdir(extracted, {mode: 0o700});
    const extractStart = performance.now();
    await run('/usr/bin/ditto', ['-x', '-k', archive, extracted], {timeout: 120_000, maxBuffer: 1024 * 1024});
    report.extraction_ms = Math.round(performance.now() - extractStart);
    report.extracted_app_present = await exists(join(extracted, 'TokenMeter.app', 'Contents', 'Info.plist'));
    if (!report.extracted_app_present) throw new Error('Extracted App Info.plist missing');
    const cleanupStart = performance.now();
    const removingFs = filesystem === 'original'
      ? createRequire(import.meta.url)('original-fs').promises
      : fs;
    try { await removingFs.rm(work, {recursive: true, force: true}); }
    catch (error) { report.cleanup_error = {code: error?.code ?? null, message: String(error?.message ?? error)}; }
    report.cleanup_ms = Math.round(performance.now() - cleanupStart);
    report.work_remaining = await exists(work);
    report.top_level_remaining = report.work_remaining ? await fs.readdir(work) : [];
    report.state = !report.cleanup_error && !report.work_remaining ? 'PASS' : 'FAIL';
  } catch (error) {
    report.cleanup_error ??= {code: error?.code ?? null, message: String(error?.message ?? error)};
    report.work_remaining = await exists(work);
    report.top_level_remaining = report.work_remaining ? await fs.readdir(work) : [];
  }
  const file = join(output, 'result.json');
  await fs.writeFile(file, JSON.stringify(report, null, 2) + '\n', {mode: 0o600, flag: 'wx'});
  process.stdout.write(JSON.stringify({state: report.state, result: file, cleanup_ms: report.cleanup_ms,
    cleanup_error: report.cleanup_error, work_remaining: report.work_remaining}) + '\n');
  if (report.state !== 'PASS') process.exitCode = 1;
}

main().catch(error => {
  process.stderr.write(`${error?.code ?? 'ERROR'}: ${error?.message ?? error}\n`);
  process.exitCode = 1;
});
