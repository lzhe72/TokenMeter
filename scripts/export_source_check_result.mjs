#!/usr/bin/env node
// Export one immutable module-test workbook from a fixed source_check report.
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const args = process.argv.slice(2);
function option(name) {
  const at = args.indexOf(name);
  if (at < 0 || at + 1 >= args.length) throw new Error(`Missing ${name}`);
  return args[at + 1];
}
if (args.length !== 4 || !args.includes('--report') || !args.includes('--output'))
  throw new Error('Usage: node scripts/export_source_check_result.mjs --report <report.json> --output <new directory>');
const reportPath = path.resolve(option('--report'));
const outputDir = path.resolve(option('--output'));
const runBase = path.join(root, '.local/source-check-runs');
const outputBase = path.join(root, '.local/test-results');
if (path.basename(reportPath) !== 'report.json' || !reportPath.startsWith(runBase + path.sep) ||
    path.dirname(path.dirname(reportPath)) !== runBase || path.dirname(outputDir) !== outputBase)
  throw new Error('Report or output path is outside the fixed local run roots');
if (await fs.realpath(root) !== root) throw new Error('Worktree path must be canonical');
async function privateDirectory(pathname) {
  const stat = await fs.lstat(pathname);
  if (!stat.isDirectory() || stat.isSymbolicLink() || stat.uid !== process.getuid?.() ||
      (stat.mode & 0o077) !== 0 || await fs.realpath(pathname) !== pathname)
    throw new Error(`Unsafe local evidence directory: ${pathname}`);
}
await privateDirectory(path.join(root, '.local'));
await privateDirectory(runBase);
await privateDirectory(path.dirname(reportPath));
async function regular(pathname) {
  const stat = await fs.lstat(pathname);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('Evidence is not a regular file');
  return fs.readFile(pathname);
}
const reportBytes = await regular(reportPath);
const report = JSON.parse(reportBytes.toString('utf8'));
const runDir = path.dirname(reportPath);
if (report.schema_version !== 1 || report.execution_type !== 'source_check' ||
    !/^[a-z0-9][a-z0-9-]{7,100}$/.test(report.run_id) || path.basename(runDir) !== report.run_id ||
    path.basename(outputDir) !== report.run_id || !['PASS', 'FAIL', 'BLOCKED'].includes(report.state) ||
    report.product_e2e !== 'NOT_RUN' || report.release_gate !== 'NOT_RUN' ||
    !/^[0-9a-f]{40}$/.test(report.candidate_commit) || !/^[0-9a-f]{40}$/.test(report.candidate_tree))
  throw new Error('Invalid source_check report identity or execution type');
const committedTree = execFileSync('git', ['rev-parse', `${report.candidate_commit}^{tree}`], {cwd: root, encoding: 'utf8'}).trim();
if (committedTree !== report.candidate_tree) throw new Error('Candidate tree differs from report');
const expected = report.expected_cases;
const cases = report.cases;
if (!Array.isArray(expected) || !expected.length || new Set(expected).size !== expected.length ||
    expected.some(id => !/^TC-TM\d{3}-CORE-\d{2}$/.test(id)) || !Array.isArray(cases) ||
    cases.length !== expected.length || cases.some((item, i) => item.case_id !== expected[i]))
  throw new Error('Duplicate or mismatched module case ID');
const committedFile = relative => {
  if (!/^[A-Za-z0-9_./-]+$/.test(relative) || relative.startsWith('/') || relative.split('/').includes('..'))
    throw new Error('Invalid committed source path');
  return execFileSync('git', ['show', `${report.candidate_commit}:${relative}`], {cwd: root, maxBuffer: 16 * 1024 * 1024});
};
if (sha(committedFile(report.source?.test_file)) !== report.source?.test_sha256 ||
    sha(committedFile(report.source?.case_catalog)) !== report.source?.case_catalog_sha256 ||
    sha(committedFile(report.source?.runner)) !== report.source?.runner_sha256)
  throw new Error('Committed test or design differs from report');
const design = JSON.parse(committedFile(report.source.case_catalog).toString('utf8'));
const designMap = new Map(design.cases.filter(item => expected.includes(item.id)).map(item => [item.id, item]));
if (designMap.size !== expected.length || expected.some(id => designMap.get(id)?.type !== 'source_check' ||
    designMap.get(id)?.release_id !== report.release_id)) throw new Error('Case design is not the stated source_check release');
const evidence = [];
for (const [role, descriptor] of Object.entries(report.raw ?? {})) {
  if (!['tap', 'stderr'].includes(role) || !['raw-test.tap', 'stderr.txt'].includes(descriptor?.path) ||
      !/^[0-9a-f]{64}$/.test(descriptor?.sha256) || !Number.isSafeInteger(descriptor?.bytes))
    throw new Error('Invalid raw evidence descriptor');
  const bytes = await regular(path.join(runDir, descriptor.path));
  if (sha(bytes) !== descriptor.sha256 || bytes.length !== descriptor.bytes) throw new Error('Raw evidence digest mismatch');
  evidence.push({role, path: descriptor.path, sha256: descriptor.sha256, bytes: bytes.length});
}
if (evidence.length !== 2) throw new Error('Missing TAP or stderr evidence');
const tap = (await regular(path.join(runDir, 'raw-test.tap'))).toString('utf8');
const states = new Map();
const steps = new Map(expected.map(id => [id, new Map()]));
const cleanup = new Set();
const counts = {};
for (const line of tap.split(/\r?\n/)) {
  const item = /^(ok|not ok) \d+ - (TC-[A-Z0-9-]+)\b/.exec(line);
  if (item) {
    if (states.has(item[2]) || !expected.includes(item[2])) throw new Error('TAP has duplicate or unknown case');
    states.set(item[2], item[1] === 'ok' ? 'PASS' : 'FAIL');
  }
  const count = /^# (tests|pass|fail|skipped|todo|cancelled) (\d+)$/.exec(line);
  if (count) counts[count[1]] = Number(count[2]);
  if (!line.startsWith('# {')) continue;
  const entry = JSON.parse(line.slice(2));
  if (!expected.includes(entry.case_id)) throw new Error('TAP has unknown diagnostic case');
  if (entry.kind === 'step' && Number.isInteger(entry.step) && entry.actual &&
      typeof entry.actual === 'object' && !Array.isArray(entry.actual)) {
    if (steps.get(entry.case_id).has(entry.step)) throw new Error('TAP has duplicate step');
    steps.get(entry.case_id).set(entry.step, entry.actual);
  } else if (entry.kind === 'cleanup' && entry.owned_root_removed === true) {
    if (cleanup.has(entry.case_id)) throw new Error('TAP has duplicate cleanup');
    cleanup.add(entry.case_id);
  } else throw new Error('TAP has invalid diagnostic');
}
if (JSON.stringify(counts) !== JSON.stringify(report.counts) ||
    counts.tests !== expected.length || counts.skipped !== 0 || counts.todo !== 0 || counts.cancelled !== 0)
  throw new Error('TAP counts differ or include skipped tests');
for (const item of cases) {
  const designCase = designMap.get(item.case_id);
  if (!Array.isArray(item.steps) || item.steps.length !== designCase.steps.length ||
      item.steps.some((step, i) => step.step !== designCase.steps[i].step ||
        step.action !== designCase.steps[i].action || step.expected !== designCase.steps[i].expected ||
        JSON.stringify(step.actual) !== JSON.stringify(steps.get(item.case_id).get(step.step) ?? null)))
    throw new Error(`Step source mismatch: ${item.case_id}`);
  const actualState = states.get(item.case_id) === 'FAIL' ? 'FAIL' : states.get(item.case_id) === 'PASS' &&
    item.steps.every(step => step.actual !== null) && cleanup.has(item.case_id) ? 'PASS' : 'BLOCKED';
  if (item.state !== actualState || item.cleanup !== (cleanup.has(item.case_id) ? 'PASS' : 'BLOCKED'))
    throw new Error(`Case outcome differs from TAP: ${item.case_id}`);
}
const pass = cases.every(item => item.state === 'PASS') && report.exit_code === 0 && report.source_stable === true &&
  counts.pass === expected.length && counts.fail === 0 && report.parse_errors?.length === 0;
if (report.state !== (pass ? 'PASS' : cases.some(item => item.state === 'FAIL') ? 'FAIL' : 'BLOCKED'))
  throw new Error('Run result contradicts verified case evidence');

const sourceFingerprint = sha(Buffer.from(JSON.stringify({report: sha(reportBytes), evidence, candidate: report.candidate_commit})));
const workbookName = `TokenMeter测试结果-${report.run_id}.xlsx`;
const workbookPath = path.join(outputDir, workbookName);
const verificationPath = path.join(outputDir, 'verification.json');
let existing;
try { existing = JSON.parse(await fs.readFile(verificationPath, 'utf8')); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
if (existing) {
  const workbook = await regular(workbookPath);
  if (existing.source_fingerprint !== sourceFingerprint || existing.workbook_sha256 !== sha(workbook) ||
      existing.run_id !== report.run_id || existing.state !== 'PASS') throw new Error('Existing result differs; refusing overwrite');
  console.log(JSON.stringify({...existing, export_status: 'VERIFIED_UNCHANGED'}));
  process.exit(0);
}
try { await fs.lstat(outputDir); throw new Error('Output directory already exists without valid verification'); }
catch (error) { if (error.code !== 'ENOENT') throw error; }

const requireBundled = createRequire(path.join(root, '.local/workbook/loader.cjs'));
const {Workbook, SpreadsheetFile, FileBlob} = await import(requireBundled.resolve('@oai/artifact-tool'));
const wb = Workbook.create();
function safe(value) {
  const text = value == null ? '' : typeof value === 'string' ? value : JSON.stringify(value);
  return /^[=+@]/.test(text) ? `'${text}` : text;
}
function sheet(name, title, headers, rows, widths) {
  const sh = wb.worksheets.add(name);
  sh.showGridLines = false;
  sh.getRange('A2').values = [[title]];
  sh.getRange('A2').format.font = {name: 'Arial', size: 15, bold: true, color: '#183153'};
  const matrix = [headers, ...rows.map(row => row.map(value => typeof value === 'number' ? value : safe(value)))];
  const area = sh.getRangeByIndexes(3, 0, matrix.length, headers.length);
  area.values = matrix;
  area.format.font = {name: 'Arial', size: 10, color: '#243247'};
  area.format.verticalAlignment = 'center';
  area.format.wrapText = true;
  area.format.rowHeight = 34;
  const head = sh.getRangeByIndexes(3, 0, 1, headers.length);
  head.format.fill = '#234C78';
  head.format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
  head.format.horizontalAlignment = 'center';
  widths.forEach((width, i) => sh.getRangeByIndexes(0, i, matrix.length + 3, 1).format.columnWidth = width);
  if (rows.length > 10) sh.freezePanes.freezeRows(4);
  return sh;
}
const overview = [
  ['批次', report.run_id], ['执行类型', 'source_check'], ['结果', report.state],
  ['版本', report.release_id], ['被测提交', report.candidate_commit], ['被测树', report.candidate_tree],
  ['开始 UTC', report.started_at_utc], ['结束 UTC', report.finished_at_utc],
  ['平台', `${report.environment.platform} ${report.environment.architecture} ${report.environment.os_release}`],
  ['Node', report.environment.node], ['用例数', cases.length], ['通过', cases.filter(item => item.state === 'PASS').length],
  ['产品 E2E', 'NOT_RUN'], ['发行门禁', 'NOT_RUN'], ['原报告 SHA-256', sha(reportBytes)],
];
sheet('00运行概览', 'TokenMeter 模块检查结果', ['项目', '实际值'], overview, [28, 90]);
sheet('01逐例结果', '固定 TC 运行结果',
  ['TC', '设计标题', '类型', '状态', '步骤数', '清理', '固定测试程序', 'TAP 原件'],
  cases.map(item => [item.case_id, designMap.get(item.case_id).title, 'source_check', item.state,
    item.steps.length, item.cleanup, report.source.test_file, 'raw-test.tap']),
  [27, 38, 18, 16, 14, 16, 52, 25]);
sheet('02逐步实测', '逐步预期与实际断言',
  ['TC', '步骤', '固定动作', '预期', '实测', '状态', '原始原件'],
  cases.flatMap(item => item.steps.map(step => [item.case_id, step.step, step.action, step.expected,
    step.actual === null ? '缺失' : JSON.stringify(step.actual), step.actual === null ? 'BLOCKED' : item.state,
    'raw-test.tap'])),
  [27, 10, 54, 82, 94, 16, 24]);
sheet('03证据与清理', '原件及清理', ['项目', '路径或状态', 'SHA-256', '字节'], [
  ['固定程序', report.source.test_file, report.source.test_sha256, ''],
  ['固定运行器', report.source.runner, report.source.runner_sha256, ''],
  ['用例目录', report.source.case_catalog, report.source.case_catalog_sha256, ''],
  ['原始报告', path.relative(root, reportPath), sha(reportBytes), reportBytes.length],
  ...evidence.map(item => [item.role, item.path, item.sha256, item.bytes]),
  ...cases.map(item => [`${item.case_id} 清理`, item.cleanup, '', '']),
], [34, 80, 70, 16]);
wb.recalculate();
const scanned = await wb.inspect({kind: 'region', sheetId: '01逐例结果', range: 'A4:H7', maxChars: 4000});
if (!expected.every(id => scanned.ndjson.includes(id))) throw new Error('Workbook case preview lost a fixed ID');
await fs.mkdir(outputBase, {recursive: true, mode: 0o700});
await privateDirectory(outputBase);
await fs.mkdir(outputDir, {mode: 0o700});
const preview = await wb.render({sheetName: '01逐例结果', range: 'A2:H7', scale: 1, format: 'png'});
await fs.writeFile(path.join(outputDir, 'preview.png'), new Uint8Array(await preview.arrayBuffer()), {flag: 'wx', mode: 0o600});
const exported = await SpreadsheetFile.exportXlsx(wb);
await exported.save(workbookPath);
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const ids = reopened.worksheets.getItem('01逐例结果').getRange(`A5:A${4 + cases.length}`).values.flat();
const statuses = reopened.worksheets.getItem('01逐例结果').getRange(`D5:D${4 + cases.length}`).values.flat();
if (JSON.stringify(ids) !== JSON.stringify(expected) || JSON.stringify(statuses) !== JSON.stringify(cases.map(item => item.state)))
  throw new Error('Exported workbook did not round-trip fixed IDs and states');
const expectedSteps = cases.reduce((n, item) => n + item.steps.length, 0);
const stepIds = reopened.worksheets.getItem('02逐步实测').getRange(`A5:A${4 + expectedSteps}`).values.flat();
if (stepIds.length !== expectedSteps) throw new Error('Exported step count changed');
const workbookBytes = await regular(workbookPath);
const verification = {schema_version: 1, execution_type: 'source_check', state: 'PASS',
  run_id: report.run_id, source_fingerprint: sourceFingerprint, report_sha256: sha(reportBytes),
  workbook: workbookName, workbook_sha256: sha(workbookBytes), workbook_bytes: workbookBytes.length,
  cases: expected, statuses, step_count: stepIds.length, product_e2e: 'NOT_RUN'};
await fs.writeFile(verificationPath, JSON.stringify(verification, null, 2) + '\n', {flag: 'wx', mode: 0o600});
console.log(JSON.stringify(verification));
