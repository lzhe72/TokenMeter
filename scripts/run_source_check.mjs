#!/usr/bin/env node
// Run a fixed source_check suite and preserve its original TAP and per-step diagnostics.
import {spawnSync, execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const registryPath = path.join(root, 'tests/source_check_suites.json');
const registryBytes = await fs.readFile(registryPath);
const registry = JSON.parse(registryBytes.toString('utf8'));
const args = process.argv.slice(2);
function option(name) {
  const at = args.indexOf(name);
  if (at < 0 || at + 1 >= args.length) throw new Error(`Missing ${name}`);
  return args[at + 1];
}
if (args.length !== 4 || !args.includes('--suite') || !args.includes('--run-id'))
  throw new Error('Usage: node scripts/run_source_check.mjs --suite tm003-core --run-id <unique id>');
const suiteName = option('--suite');
const runId = option('--run-id');
const suite = registry.suites?.[suiteName];
if (registry.schema_version !== 1 || !suite || !/^[a-z0-9][A-Za-z0-9-]{7,100}$/.test(runId) ||
    !/^tm\d{3}-core(?:\d{2})?$/.test(suiteName) || !/^v\d+\.\d+\.\d+-\d{8}T\d{6}Z$/.test(suite.release_id) ||
    !/^apps\/desktop\/tests\/[a-z0-9-]+\.test\.ts$/.test(suite.file) ||
    !Array.isArray(suite.cases) || suite.cases.length < 1 || new Set(suite.cases).size !== suite.cases.length ||
    suite.cases.some(id => !/^TC-TM\d{3}-CORE-\d{2}$/.test(id)) ||
    !['owned_root', 'memory_only'].includes(suite.reset_kind)) throw new Error('Invalid fixed suite or run ID');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const git = (...argv) => execFileSync('git', argv, {cwd: root, encoding: 'utf8'}).trim();
if (git('status', '--porcelain')) throw new Error('Source tree must be clean before the run');
const commit = git('rev-parse', 'HEAD');
const tree = git('rev-parse', 'HEAD^{tree}');
const testPath = path.join(root, suite.file);
const catalogPath = path.join(root, 'tests/test_cases.json');
const runnerPath = fileURLToPath(import.meta.url);
const testBytes = await fs.readFile(testPath);
const catalogBytes = await fs.readFile(catalogPath);
const runnerBytes = await fs.readFile(runnerPath);
const catalog = JSON.parse(catalogBytes.toString('utf8'));
const designs = new Map(catalog.cases.filter(item => suite.cases.includes(item.id)).map(item => [item.id, item]));
if (designs.size !== suite.cases.length || suite.cases.some(id => designs.get(id)?.type !== 'source_check' ||
    designs.get(id)?.release_id !== suite.release_id || designs.get(id)?.steps.length < 1 ||
    designs.get(id)?.steps.length > 20))
  throw new Error('Fixed source_check case design is missing or changed');

const base = path.join(root, '.local/source-check-runs');
const local = path.join(root, '.local');
await fs.mkdir(local, {recursive: true, mode: 0o700});
const localStat = await fs.lstat(local);
if (!localStat.isDirectory() || localStat.isSymbolicLink() || localStat.uid !== process.getuid?.() ||
    (localStat.mode & 0o077) !== 0 || await fs.realpath(local) !== local)
  throw new Error('Unsafe local evidence root');
await fs.mkdir(base, {recursive: true, mode: 0o700});
const baseStat = await fs.lstat(base);
if (!baseStat.isDirectory() || baseStat.isSymbolicLink() || baseStat.uid !== process.getuid?.() ||
    (baseStat.mode & 0o077) !== 0 || await fs.realpath(base) !== base)
  throw new Error('Unsafe source_check run root');
const runDir = path.join(base, runId);
await fs.mkdir(runDir, {mode: 0o700}); // Never overwrite or erase another run.
const started = new Date().toISOString();
const argv = ['--experimental-strip-types', '--test', '--test-reporter=tap', suite.file];
const processResult = spawnSync(process.execPath, argv, {cwd: root, encoding: 'utf8', timeout: 120000, maxBuffer: 16 * 1024 * 1024});
const stdout = processResult.stdout ?? '';
const stderr = processResult.stderr ?? '';
await fs.writeFile(path.join(runDir, 'raw-test.tap'), stdout, {flag: 'wx', mode: 0o600});
await fs.writeFile(path.join(runDir, 'stderr.txt'), stderr, {flag: 'wx', mode: 0o600});
const finished = new Date().toISOString();
const sourceStable = sha(await fs.readFile(testPath)) === sha(testBytes) &&
  sha(await fs.readFile(catalogPath)) === sha(catalogBytes) &&
  sha(await fs.readFile(registryPath)) === sha(registryBytes) &&
  sha(await fs.readFile(runnerPath)) === sha(runnerBytes) && !git('status', '--porcelain') &&
  git('rev-parse', 'HEAD') === commit;

const caseStates = new Map();
const actualSteps = new Map(suite.cases.map(id => [id, new Map()]));
const cleanup = new Map();
const counts = {};
const parseErrors = [];
for (const line of stdout.split(/\r?\n/)) {
  const result = /^(ok|not ok) \d+ - (TC-[A-Z0-9-]+)\b/.exec(line);
  if (result) {
    if (caseStates.has(result[2]) || !suite.cases.includes(result[2])) parseErrors.push('duplicate_or_unknown_case');
    else caseStates.set(result[2], result[1] === 'ok' ? 'PASS' : 'FAIL');
  }
  const count = /^# (tests|pass|fail|skipped|todo|cancelled) (\d+)$/.exec(line);
  if (count) counts[count[1]] = Number(count[2]);
  if (!line.startsWith('# {')) continue;
  let item;
  try { item = JSON.parse(line.slice(2)); }
  catch { parseErrors.push('invalid_step_json'); continue; }
  if (!suite.cases.includes(item.case_id)) { parseErrors.push('unknown_diagnostic_case'); continue; }
  if (item.kind === 'step' && Number.isInteger(item.step) && item.step >= 1 &&
      item.step <= designs.get(item.case_id).steps.length &&
      item.actual && typeof item.actual === 'object' && !Array.isArray(item.actual)) {
    if (actualSteps.get(item.case_id).has(item.step)) parseErrors.push('duplicate_step');
    else actualSteps.get(item.case_id).set(item.step, item.actual);
  } else if (item.kind === 'cleanup' &&
      ((suite.reset_kind === 'owned_root' && item.owned_root_removed === true && item.memory_reset_complete === undefined) ||
       (suite.reset_kind === 'memory_only' && item.owned_root_removed === undefined &&
        (item.memory_reset_complete === true ||
         (item.resource_scope === 'memory_only' && item.external_resources_created === false))))) {
    if (cleanup.has(item.case_id)) parseErrors.push('duplicate_cleanup');
    else cleanup.set(item.case_id, true);
  } else parseErrors.push('invalid_step_or_cleanup');
}
const cases = suite.cases.map(id => {
  const design = designs.get(id);
  const steps = design.steps.map(step => ({step: step.step, action: step.action, expected: step.expected,
    actual: actualSteps.get(id).get(step.step) ?? null}));
  const state = caseStates.get(id) === 'FAIL' ? 'FAIL' : caseStates.get(id) === 'PASS' &&
    steps.every(step => step.actual !== null) && cleanup.get(id) === true ? 'PASS' : 'BLOCKED';
  return {case_id: id, state, steps, cleanup: cleanup.get(id) === true ? 'PASS' : 'BLOCKED'};
});
const complete = sourceStable && parseErrors.length === 0 && processResult.status === 0 &&
  !processResult.error && counts.tests === suite.cases.length && counts.pass === suite.cases.length &&
  counts.fail === 0 && counts.skipped === 0 && counts.todo === 0 && counts.cancelled === 0 &&
  cases.every(item => item.state === 'PASS');
const report = {
  schema_version: 1, execution_type: 'source_check', run_id: runId, suite: suiteName,
  reset_kind: suite.reset_kind, release_id: suite.release_id, candidate_commit: commit, candidate_tree: tree,
  started_at_utc: started, finished_at_utc: finished,
  environment: {platform: process.platform, architecture: process.arch, node: process.version, os_release: os.release()},
  source: {test_file: suite.file, test_sha256: sha(testBytes), case_catalog: 'tests/test_cases.json',
    case_catalog_sha256: sha(catalogBytes), runner: 'scripts/run_source_check.mjs', runner_sha256: sha(runnerBytes),
    suite_registry: 'tests/source_check_suites.json', suite_registry_sha256: sha(registryBytes)},
  command: ['node', ...argv],
  raw: {tap: {path: 'raw-test.tap', sha256: sha(Buffer.from(stdout)), bytes: Buffer.byteLength(stdout)},
    stderr: {path: 'stderr.txt', sha256: sha(Buffer.from(stderr)), bytes: Buffer.byteLength(stderr)}},
  exit_code: processResult.status, signal: processResult.signal,
  counts, expected_cases: suite.cases, cases, source_stable: sourceStable,
  parse_errors: parseErrors, state: complete ? 'PASS' : cases.some(item => item.state === 'FAIL') ? 'FAIL' : 'BLOCKED',
  product_e2e: 'NOT_RUN', release_gate: 'NOT_RUN',
};
await fs.writeFile(path.join(runDir, 'report.json'), JSON.stringify(report, null, 2) + '\n', {flag: 'wx', mode: 0o600});
console.log(JSON.stringify({run_id: runId, state: report.state, cases: cases.map(item => [item.case_id, item.state]),
  report: path.relative(root, path.join(runDir, 'report.json'))}));
if (!complete) process.exitCode = 1;
