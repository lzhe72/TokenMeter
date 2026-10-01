#!/usr/bin/env node
// Fixed TM-002 product E2E export. The input is an original granular_permissions
// result, never a TM-001 aggregate or a source_check report.
import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const requireBundled = createRequire(path.join(projectRoot, '.local/workbook/loader.cjs'));
let FileBlob, SpreadsheetFile, Workbook;
try {
  ({FileBlob, SpreadsheetFile, Workbook} = await import(requireBundled.resolve('@oai/artifact-tool')));
} catch (error) {
  throw new Error(`Bundled spreadsheet runtime is unavailable: ${error.message}`);
}

const RELEASE = 'v0.2.0-20261001T034118Z';
const RUN = /^local-[0-9a-f]{32}$/;
const HEX40 = /^[0-9a-f]{40}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const TC = /^TC-TM002-[A-Z]+-[0-9]{2}(?:#[A-Z0-9_]+)?$/;
const STATES = new Set(['PASS', 'FAIL', 'BLOCKED']);
const SCOPES = new Set([
  'tm002_granular_development_package', 'tm002_granular_final_package',
  'tm002_granular_targeted_development_probe', 'tm002_granular_targeted_final_probe',
]);
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const assert = (condition, message) => {if (!condition) throw new Error(message);};
const args = process.argv.slice(2);
function option(name) {
  const at = args.indexOf(name);
  assert(at >= 0 && at + 1 < args.length && !args[at + 1].startsWith('--'), `Missing ${name}`);
  return args[at + 1];
}
const reportPath = path.resolve(option('--report'));
const outputDir = path.resolve(option('--output'));
assert(path.basename(reportPath) === 'result.json', 'TM-002 product source must be result.json');

async function noLinks(target) {
  let current = path.resolve(target);
  while (true) {
    try {
      const info = await fs.lstat(current);
      assert(!info.isSymbolicLink(), `Linked path is forbidden: ${current}`);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
}
async function readOwned(target) {
  await noLinks(target);
  const handle = await fs.open(target, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const before = await handle.stat();
    assert(before.isFile(), `Evidence is not a regular file: ${target}`);
    const bytes = await handle.readFile();
    const after = await handle.stat();
    const visible = await fs.lstat(target);
    const identity = x => `${x.dev}:${x.ino}:${x.size}:${x.mtimeMs}`;
    assert(identity(before) === identity(after) && identity(after) === identity(visible),
      `Evidence changed while being read: ${target}`);
    return bytes;
  } finally { await handle.close(); }
}
const sourceBytes = await readOwned(reportPath);
const report = JSON.parse(sourceBytes.toString('utf8'));
assert(report && typeof report === 'object' && !Array.isArray(report), 'TM-002 report is not an object');
assert(report.schema_version === 1 && report.release_id === RELEASE && SCOPES.has(report.scope),
  'Report is not a TM-002 product E2E original');
assert(RUN.test(report.run_id) && STATES.has(report.state), 'Report run ID or state is invalid');
assert(HEX40.test(report.source_commit), 'Product candidate SHA is invalid');
if (report.candidate_tree !== undefined) assert(HEX40.test(report.candidate_tree), 'Candidate tree is invalid');
if (report.package !== undefined) {
  for (const key of ['manifest_sha256', 'dmg_sha256', 'app_tree_sha256'])
    assert(HEX64.test(report.package[key]), `Product package ${key} is invalid`);
}
assert(report.release_eligible === false, 'Product E2E alone cannot claim release eligibility');
assert(typeof report.cleanup_completed === 'boolean', 'Product cleanup conclusion is missing');
assert(Array.isArray(report.expected_cases) && report.expected_cases.length > 0 &&
  Array.isArray(report.tc_results) && report.tc_results.length === report.expected_cases.length,
  'Product expected and actual TC lists differ');
const unique = new Set(report.expected_cases);
assert(unique.size === report.expected_cases.length && [...unique].every(id => TC.test(id)),
  'Product TC list contains duplicate or non-TM002 IDs');
assert(report.expected_cases.every((id, i) => report.tc_results[i]?.case_id === id),
  'Product TC result order or identity differs from its frozen list');
if (report.preflight !== undefined) {
  assert(['FAIL', 'BLOCKED'].includes(report.preflight.state) &&
    typeof report.preflight.reason === 'string' && report.preflight.reason,
    'Product preflight lacks an actual block/failure reason');
}

const sourceHashes = {[reportPath]: sha(sourceBytes)};
const evidenceRows = [];
const evidenceMap = new Map();
async function descriptor(value, role, owner = '') {
  assert(value && typeof value === 'object' && !Array.isArray(value) &&
    typeof value.path === 'string' && !path.isAbsolute(value.path) &&
    value.path !== '' && !value.path.split('/').includes('..') && HEX64.test(value.sha256) &&
    Number.isSafeInteger(value.bytes) && value.bytes >= 0, `Invalid ${role} descriptor`);
  const absolute = path.resolve(path.dirname(reportPath), value.path);
  assert(absolute.startsWith(path.dirname(reportPath) + path.sep), `Escaping ${role} evidence`);
  const bytes = await readOwned(absolute);
  assert(bytes.length === value.bytes && sha(bytes) === value.sha256, `Changed or missing ${role} evidence: ${value.path}`);
  const previous = evidenceMap.get(value.path);
  if (previous) assert(previous.sha256 === value.sha256 && previous.bytes === value.bytes,
    `Conflicting evidence descriptor: ${value.path}`);
  else {
    evidenceMap.set(value.path, value);
    evidenceRows.push([owner, role, value.path, value.sha256, value.bytes]);
    sourceHashes[absolute] = value.sha256;
  }
  return bytes;
}

assert(Array.isArray(report.test_code_snapshot) && report.test_code_snapshot.length > 0 &&
  report.test_inputs_sha256 && typeof report.test_inputs_sha256 === 'object',
  'Frozen test code snapshots or input hashes are missing');
const snapshotInputs = new Set();
for (const item of report.test_code_snapshot) {
  assert(item.path?.startsWith('test-code/'), 'Frozen code snapshot path is invalid');
  const input = item.path.slice('test-code/'.length);
  assert(report.test_inputs_sha256[input] === item.sha256 && !snapshotInputs.has(input),
    `Frozen test code input mismatch: ${input}`);
  snapshotInputs.add(input);
  await descriptor(item, '测试代码快照');
}
assert(Object.keys(report.test_inputs_sha256).length === snapshotInputs.size,
  'Frozen test code digest set differs from its snapshots');
assert(snapshotInputs.has('scripts/granular_permissions.py') &&
  snapshotInputs.has('apps/desktop/e2e/granular-permissions.spec.ts') &&
  snapshotInputs.has('tests/test_cases.json'), 'Fixed product runner, desktop TC, or catalog snapshot is missing');

const tcRows = [];
const stepRows = [];
const cleanupRows = [];
for (const item of report.tc_results) {
  assert(STATES.has(item.state) && typeof item.reason === 'string', `TC state/reason invalid: ${item.case_id}`);
  const variantParent = item.case_id.includes('#') ? item.case_id.split('#')[0] : null;
  assert(item.parent_id === variantParent,
    `TC parent/variant identity invalid: ${item.case_id}`);
  assert(Array.isArray(item.step_results) && item.evidence && typeof item.evidence === 'object' &&
    item.cleanup && typeof item.cleanup.completed === 'boolean',
    `TC steps/evidence/cleanup malformed: ${item.case_id}`);
  if (report.preflight) {
    assert(item.state === 'BLOCKED' && item.step_results.length === 0 &&
      item.started_at == null && item.finished_at == null,
      'Preflight block was given product steps or a completed TC status');
  }
  if (item.state === 'PASS') assert(item.cleanup.completed, `Passing TC has incomplete cleanup: ${item.case_id}`);
  const isDerived = item.parent_id == null && item.step_results.length === 0 &&
    item.reason === 'Derived from all fixed variant originals';
  if (item.state === 'PASS' && !isDerived) assert(item.step_results.length > 0,
    `Passing TC has no actual product steps: ${item.case_id}`);
  if (item.step_results.length > 0) assert(item.evidence.events,
    `Product TC steps have no independent event log: ${item.case_id}`);
  for (const [role, value] of Object.entries(item.evidence)) {
    if (Array.isArray(value)) for (const part of value) await descriptor(part, role, item.case_id);
    else {
      const bytes = await descriptor(value, role, item.case_id);
      if (role === 'structure_audit' && item.state === 'PASS') {
        const audit = JSON.parse(bytes.toString('utf8'));
        assert(audit.state === 'PASS' && audit.case_id === item.case_id &&
          audit.scope === 'tm002_evidence_structure_only' && audit.release_eligible === false,
          `Passing TC has no passing independent structure audit: ${item.case_id}`);
      }
    }
  }
  if (item.step_results.length > 0) {
    const eventBytes = await readOwned(path.resolve(path.dirname(reportPath), item.evidence.events.path));
    const events = eventBytes.toString('utf8').trim().split('\n').map(line => JSON.parse(line));
    assert(JSON.stringify(events) === JSON.stringify(item.step_results),
      `TC step results differ from original event log: ${item.case_id}`);
  }
  for (const event of item.step_results) {
    assert(event.run_id === report.run_id && event.case_id === item.case_id &&
      Number.isSafeInteger(event.step) && event.step > 0 &&
      typeof event.action === 'string' && typeof event.source === 'string' &&
      typeof event.timestamp === 'string' && typeof event.passed === 'boolean' &&
      Object.hasOwn(event, 'expected') && Object.hasOwn(event, 'actual') &&
      event.evidence && typeof event.evidence === 'object',
      `TC step identity or actual comparison missing: ${item.case_id}`);
    assert(event.passed === (JSON.stringify(event.expected) === JSON.stringify(event.actual)),
      `TC step PASS flag contradicts actual comparison: ${item.case_id}`);
    if (item.state === 'PASS') assert(event.passed, `Passing TC has a failed actual step: ${item.case_id}`);
    const screenshot = event.evidence.screenshot;
    if (screenshot != null) {
      assert(typeof screenshot === 'string' && !screenshot.includes('/') && !screenshot.includes('..') &&
        item.evidence.screenshots?.some(row => row.path === `${item.case_id.replaceAll('#', '--')}/${screenshot}`),
        `TC step screenshot is not in verified evidence: ${item.case_id}`);
    }
    stepRows.push([item.case_id, event.step, event.timestamp, event.action, event.source,
      event.expected, event.actual, event.passed ? 'PASS' : 'FAIL',
      screenshot ? `${item.case_id.replaceAll('#', '--')}/${screenshot}` : '无截图']);
  }
  tcRows.push([item.case_id, item.parent_id ? '变体' : '父用例', item.parent_id || '',
    item.state, item.reason, item.started_at || '未启动', item.finished_at || '未完成',
    item.step_results.length, Object.values(item.evidence).flat().length,
    item.cleanup.completed ? '完成' : '未完成', (item.task_ids || []).join(', '), (item.ac_ids || []).join(', ')]);
  cleanupRows.push([item.case_id, item.state, item.cleanup.completed ? '完成' : '未完成',
    item.cleanup, item.evidence.source_expected?.path || '无', item.evidence.seed_sql?.path || '无',
    item.evidence.database_before?.path || '无', item.evidence.database_after?.path || '无',
    item.evidence.keychain_preflight?.path || '无', item.evidence.keychain_cleanup?.path || '无']);
}
if (report.evidence_audit) {
  const bytes = await descriptor(report.evidence_audit, '整批证据审计');
  if (report.state === 'PASS') {
    const audit = JSON.parse(bytes.toString('utf8'));
    assert(audit.state === 'PASS' && audit.scope === 'tm002_evidence_structure_only' &&
      audit.release_eligible === false, 'Passing report has no passing independent structure audit');
  }
}
const allPassed = report.tc_results.every(row => row.state === 'PASS');
const anyFailed = report.tc_results.some(row => row.state === 'FAIL') || report.preflight?.state === 'FAIL';
const derivedState = allPassed && report.cleanup_completed ? 'PASS' : anyFailed ? 'FAIL' : 'BLOCKED';
assert(report.state === derivedState, 'Product report summary contradicts its individual TC results');
if (report.state === 'PASS') assert(report.evidence_audit && report.package && report.candidate_tree,
  'Passing product report lacks final independent audit or candidate identity');
const fingerprint = sha(Buffer.from(JSON.stringify(Object.entries(sourceHashes).sort(([a], [b]) => a.localeCompare(b)))));
const outputName = `TokenMeter测试结果-${report.run_id}.xlsx`;
const workbookPath = path.join(outputDir, outputName);
const sourcePath = path.join(outputDir, 'tm002-product-source-digests.json');
const verificationPath = path.join(outputDir, 'tm002-product-verification.json');
await noLinks(outputDir);
await fs.mkdir(outputDir, {recursive: true, mode: 0o700});
const present = await Promise.all([workbookPath, sourcePath, verificationPath].map(async p => {
  try { await fs.lstat(p); return true; } catch (e) { if (e.code === 'ENOENT') return false; throw e; }
}));
assert(present.every(Boolean) || present.every(value => !value),
  'Partial TM-002 export exists; refusing to replace any artifact');

async function readback(expectedSha) {
  const book = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
  const visible = value => value == null ? '' : value;
  const ids = book.worksheets.getItem('01逐TC').getRangeByIndexes(4, 0, tcRows.length, 4).values;
  assert(JSON.stringify(ids.map(row => row.slice(0, 4).map(visible))) ===
    JSON.stringify(tcRows.map(row => row.slice(0, 4))), 'XLSX TC/variant/status readback differs');
  if (stepRows.length) {
    const steps = book.worksheets.getItem('02逐步实测').getRangeByIndexes(4, 0, stepRows.length, 2).values;
    assert(JSON.stringify(steps) === JSON.stringify(stepRows.map(row => row.slice(0, 2))),
      'XLSX actual step readback differs');
  }
  const hashes = book.worksheets.getItem('03证据索引').getRangeByIndexes(4, 0, evidenceRows.length, 5).values;
  assert(JSON.stringify(hashes.map(row => row.slice(0, 5).map(visible))) ===
    JSON.stringify(evidenceRows), 'XLSX evidence descriptor readback differs');
  const run = book.worksheets.getItem('00运行概览').getRange('B5:B7').values.flat();
  assert(run[0] === report.run_id && run[1] === report.state && run[2] === expectedSha,
    'XLSX summary identity or original hash differs');
}

if (present.every(Boolean)) {
  const source = JSON.parse((await readOwned(sourcePath)).toString('utf8'));
  const verification = JSON.parse((await readOwned(verificationPath)).toString('utf8'));
  const bytes = await readOwned(workbookPath);
  assert(source.fingerprint === fingerprint && source.report_sha256 === sourceHashes[reportPath] &&
    JSON.stringify(source.source_hashes) === JSON.stringify(sourceHashes) &&
    verification.schema_version === 1 && verification.state === 'PASS' &&
    verification.run_id === report.run_id &&
    verification.source_fingerprint === fingerprint &&
    verification.source_manifest?.path === path.basename(sourcePath) &&
    verification.source_manifest?.sha256 === sha(await readOwned(sourcePath)) &&
    verification.source_report?.sha256 === sourceHashes[reportPath] &&
    verification.source_report?.path === reportPath &&
    verification.workbook?.sha256 === sha(bytes) && verification.workbook?.bytes === bytes.length,
    'Existing TM-002 workbook or source fingerprint differs; refusing overwrite');
  await readback(sourceHashes[reportPath]);
  console.log(JSON.stringify({...verification, export_status: 'VERIFIED_UNCHANGED'}));
  process.exit(0);
}

function display(value) {
  if (value == null) return '';
  const raw = typeof value === 'string' ? value : JSON.stringify(value);
  let redacted = raw.replace(/\/Users\/[^\s"']+/g, '[本机路径]')
    .replace(/\/private\/var\/[^\s"']+/g, '[本机路径]')
    .replace(/Bearer\s+[A-Za-z0-9._~-]+/gi, 'Bearer [已脱敏]')
    .replace(/TEST-ONLY-[A-Za-z0-9._~-]+|PRIVATE_[A-Za-z0-9._~-]+/g, '[合成密钥已脱敏]');
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(redacted)) redacted += ' UTC';
  return /^[=+@-]/.test(redacted) ? `'${redacted}` : redacted;
}
const book = Workbook.create();
function addSheet(name, title, header, rows, widths) {
  const sheet = book.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.getRange('A2').values = [[title]];
  sheet.getRange('A2').format.font = {name: 'Arial', size: 14, bold: true, color: '#203B5B'};
  const matrix = [header, ...rows.map(row => row.map(value =>
    typeof value === 'number' ? value : display(value)))];
  const grid = sheet.getRangeByIndexes(3, 0, matrix.length, header.length);
  grid.values = matrix;
  grid.format.font = {name: 'Arial', size: 10, color: '#233047'};
  grid.format.verticalAlignment = 'center';
  grid.format.wrapText = true;
  grid.format.rowHeight = 29;
  const heading = sheet.getRangeByIndexes(3, 0, 1, header.length);
  heading.format.fill = '#24486D';
  heading.format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
  heading.format.horizontalAlignment = 'center';
  heading.format.rowHeight = 30;
  widths.forEach((width, index) => sheet.getRangeByIndexes(0, index, Math.max(5, matrix.length + 3), 1).format.columnWidth = width);
  for (let i = 0; i < rows.length; i++) {
    const lineCount = Math.max(...matrix[i + 1].map((value, col) =>
      Math.ceil(String(value ?? '').length / Math.max(12, widths[col] * 0.72))));
    const row = sheet.getRangeByIndexes(i + 4, 0, 1, header.length);
    row.format.rowHeight = Math.min(210, Math.max(29, lineCount * 15 + 8));
    if (i % 2) row.format.fill = '#F3F6FA';
  }
  if (rows.length > 15) sheet.freezePanes.freezeRows(4);
  return sheet;
}
const counts = state => report.tc_results.filter(row => row.state === state).length;
const parents = report.tc_results.filter(row => !row.parent_id);
const variants = report.tc_results.filter(row => row.parent_id);
const overviewRows = [
  ['运行编号', report.run_id, '来自原始 result.json'],
  ['产品结论', report.state, '独立产品 E2E；Excel 不是测试通过证明'],
  ['原始报告 SHA-256', sourceHashes[reportPath], '同批次原件绑定'],
  ['执行类型', 'product_e2e', '不混入 source_check'],
  ['执行范围', report.scope, '定向与全功能分别记录'],
  ['版本编号', report.release_id, ''],
  ['候选提交', report.source_commit, ''],
  ['候选树', report.candidate_tree || '前置阶段未取得', ''],
  ['父 TC 数量', parents.length, '与变体分别统计'],
  ['变体数量', variants.length, '与父 TC 分别统计'],
  ['PASS / FAIL / BLOCKED', `${counts('PASS')} / ${counts('FAIL')} / ${counts('BLOCKED')}`, '逐 TC 原始状态'],
  ['实际产品步骤', stepRows.length, stepRows.length ? '见 02逐步实测' : '无产品步骤；前置阻断或未独立执行'],
  ['前置状态', report.preflight?.state || '已进入用例执行', report.preflight?.reason || ''],
  ['整批清理', report.cleanup_completed ? '完成' : '未完成', ''],
  ['包来源', report.package?.installed_source || '前置阶段未取得', ''],
  ['DMG SHA-256', report.package?.dmg_sha256 || '前置阶段未取得', ''],
  ['App 树 SHA-256', report.package?.app_tree_sha256 || '前置阶段未取得', ''],
  ['macOS / 架构', `${report.host?.macos || '未取得'} / ${report.host?.architecture || '未取得'}`, '本次实际机器'],
  ['开始 UTC', report.started_at || '未记录', ''],
  ['结束 UTC', report.finished_at || '未记录', ''],
  ['发行资格', report.release_eligible ? '报告声明可发行' : '无', '开发包不授予发行资格'],
  ['证据源指纹', fingerprint, '再次导出只验证，不覆盖'],
];
const summary = addSheet('00运行概览', 'TM002 产品测试结果', ['项目', '原始值', '说明'], overviewRows, [27, 79, 96]);
summary.tabColor = '#24486D';
addSheet('01逐TC', '逐 TC 与固定变体',
  ['TC 编号', '类型', '父 TC', '状态', '实际原因', '开始 UTC', '结束 UTC', '实测步骤数', '证据数', '清理', 'TASK', 'AC'],
  tcRows, [48, 13, 42, 15, 84, 31, 31, 15, 12, 14, 42, 25]);
addSheet('02逐步实测', '原始事件中的实际步骤',
  ['TC 编号', '步骤', '时间 UTC', '实际动作', '观察来源', '预期', '实测', '断言', '截图证据'],
  stepRows, [48, 10, 32, 75, 28, 90, 90, 12, 70]);
addSheet('03证据索引', '已核对的原件及 SHA-256',
  ['TC 编号', '证据类型', '运行目录相对路径', 'SHA-256', '字节数'],
  evidenceRows, [48, 28, 92, 69, 16]);
addSheet('04数据清理', '逐 TC 数据与资源清理',
  ['TC 编号', '状态', '资源清理', '原始清理详情', '源预期', 'SQL 造数', 'DB 前', 'DB 后', 'Keychain 前', 'Keychain 清理'],
  cleanupRows, [48, 14, 15, 88, 65, 65, 65, 65, 65, 65]);
book.recalculate();
const check = await book.inspect({kind: 'table', range: '00运行概览!A4:C13', include: 'values,formulas',
  tableMaxRows: 10, tableMaxCols: 3, maxChars: 3500});
const formulaErrors = await book.inspect({kind: 'match',
  searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
  options: {useRegex: true, maxResults: 100}, maxChars: 1200});
assert(!formulaErrors.ndjson.split('\n').filter(Boolean).some(line => JSON.parse(line).kind === 'match'),
  'Workbook contains formula errors');
const previewDir = path.join(projectRoot, '.local', 'workbook',
  'tm002-product-previews', report.run_id);
await fs.mkdir(previewDir, {recursive: true, mode: 0o700});
await fs.writeFile(path.join(previewDir, 'inspection.ndjson'), check.ndjson);
for (const name of ['00运行概览', '01逐TC', '02逐步实测']) {
  const preview = await book.render({sheetName: name, range: name === '00运行概览' ? 'A1:C12' :
    name === '01逐TC' ? 'A1:E8' : 'A1:I5', scale: 1.2, format: 'png'});
  await fs.writeFile(path.join(previewDir, `${name}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const temporary = path.join(outputDir, `.${outputName}.${process.pid}.tmp`);
try {
  const xlsx = await SpreadsheetFile.exportXlsx(book);
  await xlsx.save(temporary);
  await fs.chmod(temporary, 0o600);
  await fs.link(temporary, workbookPath); // Existing output is never replaced.
} finally {
  await fs.rm(temporary, {force: true});
  await fs.rm(`${temporary}.inspect.ndjson`, {force: true});
}
await readback(sourceHashes[reportPath]);
const workbookBytes = await readOwned(workbookPath);
const sourceManifest = {schema_version: 1, run_id: report.run_id, report_sha256: sourceHashes[reportPath],
  fingerprint, source_hashes: sourceHashes, workbook: outputName, workbook_sha256: sha(workbookBytes),
  rows: {tc: tcRows.length, steps: stepRows.length, evidence: evidenceRows.length}};
const manifestBytes = Buffer.from(JSON.stringify(sourceManifest, null, 2) + '\n');
await fs.writeFile(sourcePath, manifestBytes, {flag: 'wx', mode: 0o600});
const verification = {schema_version: 1, state: 'PASS', export_status: 'EXPORTED', run_id: report.run_id,
  execution_type: 'product_e2e', product_state: report.state,
  source_report: {path: reportPath, sha256: sourceHashes[reportPath]},
  source_manifest: {path: path.basename(sourcePath), sha256: sha(manifestBytes)},
  workbook: {path: outputName, sha256: sha(workbookBytes), bytes: workbookBytes.length},
  source_fingerprint: fingerprint, rows: sourceManifest.rows};
await fs.writeFile(verificationPath, JSON.stringify(verification, null, 2) + '\n', {flag: 'wx', mode: 0o600});
assert(sha(await readOwned(reportPath)) === sourceHashes[reportPath], 'Original report changed during export');
console.log(JSON.stringify(verification));
