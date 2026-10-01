// Export one immutable, local-only workbook from an existing product E2E run.
// This program reads evidence. It never starts the App or changes test outcomes.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const requireBundled = createRequire(path.join(projectRoot, '.local/workbook/loader.cjs'));
let Workbook, SpreadsheetFile;
try {
  ({Workbook, SpreadsheetFile} = await import(requireBundled.resolve('@oai/artifact-tool')));
} catch (error) {
  throw new Error(`Bundled spreadsheet runtime is unavailable; follow the spreadsheet workspace dependency setup: ${error.message}`);
}

const args = process.argv.slice(2);
function option(name) {
  const at = args.indexOf(name);
  if (at < 0 || at + 1 >= args.length || args[at + 1].startsWith('--')) throw new Error(`Required argument ${name} is missing`);
  return args[at + 1];
}
if (args.length !== 4 || !args.includes('--report') || !args.includes('--output')) {
  throw new Error('Usage: node scripts/export_test_result.mjs --report <raw result.json> --output <new per-run directory>');
}
const reportPath = path.resolve(option('--report'));
const outputDir = path.resolve(option('--output'));
const reportRoot = path.dirname(reportPath);
const reportRootReal = await fs.realpath(reportRoot);
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileHash = async file => sha(await fs.readFile(file));
const reportBytes = await fs.readFile(reportPath);
const report = JSON.parse(reportBytes.toString('utf8'));
if (path.basename(reportPath) !== 'result.json') throw new Error('The report must be the original result.json');
if (!/^[A-Za-z0-9][A-Za-z0-9_-]{1,100}$/.test(report.run_id || '')) throw new Error('Invalid run_id in result.json');
if (!Array.isArray(report.expected_cases) || new Set(report.expected_cases).size !== report.expected_cases.length) throw new Error('Invalid expected case set');
if (!['PASS', 'FAIL', 'BLOCKED'].includes(report.state)) throw new Error('Invalid run state');

const sourceHashes = {[reportPath]: sha(reportBytes)};
const evidence = [];
async function ownedFile(relative) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative)) throw new Error(`Invalid evidence path: ${relative}`);
  const target = path.resolve(reportRoot, relative);
  if (target === reportRoot || !target.startsWith(reportRoot + path.sep)) throw new Error(`Evidence escapes run directory: ${relative}`);
  let actual;
  try { actual = await fs.realpath(target); } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  if (!actual.startsWith(reportRootReal + path.sep)) throw new Error(`Evidence resolves outside run directory: ${relative}`);
  const stat = await fs.lstat(target);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error(`Evidence is not a regular owned file: ${relative}`);
  return target;
}
async function readEvidence(relative, role, expectedSha = null, expectedBytes = null) {
  const target = await ownedFile(relative);
  if (!target) {
    evidence.push({role, path: relative, status: '缺失', expectedSha, actualSha: null, expectedBytes, actualBytes: null});
    return null;
  }
  const bytes = await fs.readFile(target);
  const actualSha = sha(bytes);
  sourceHashes[target] = actualSha;
  const state = expectedSha && actualSha !== expectedSha || expectedBytes != null && bytes.length !== expectedBytes ? '摘要不符' : '已核对';
  evidence.push({role, path: relative, status: state, expectedSha, actualSha, expectedBytes, actualBytes: bytes.length});
  return bytes;
}

const suiteMap = new Map((report.suites || []).map(suite => [suite.case_id, suite]));
const caseRows = [];
const stepRows = [];
const rawRequests = [];
const playwrightErrors = [];
for (const caseId of report.expected_cases) {
  if (!/^E2E-TM\d{3}-\d{3}$/.test(caseId)) throw new Error(`Invalid case ID: ${caseId}`);
  const suite = suiteMap.get(caseId);
  const caseDir = caseId;
  const playwrightRelative = suite?.playwright_json?.path || `${caseDir}/playwright.json`;
  const eventRelative = suite?.events?.path || `${caseDir}/events.jsonl`;
  const playwrightBytes = await readEvidence(playwrightRelative, `${caseId} Playwright JSON`, suite?.playwright_json?.sha256, suite?.playwright_json?.bytes);
  const eventBytes = await readEvidence(eventRelative, `${caseId} 逐步断言`, suite?.events?.sha256, suite?.events?.bytes);
  let attempts = [];
  if (playwrightBytes) {
    const raw = JSON.parse(playwrightBytes.toString('utf8'));
    for (const group of raw.suites || []) for (const spec of group.specs || []) for (const test of spec.tests || []) {
      for (const attempt of test.results || []) {
        attempts.push(attempt.status);
        for (const failure of attempt.errors || []) if (failure?.message) playwrightErrors.push({caseId, message: failure.message});
      }
    }
  }
  let failures = 0;
  if (eventBytes) {
    for (const [index, line] of eventBytes.toString('utf8').split(/\r?\n/).filter(Boolean).entries()) {
      const event = JSON.parse(line);
      if (event.run_id !== report.run_id || event.case_id !== caseId) throw new Error(`Event run/case mismatch in ${eventRelative}:${index + 1}`);
      if (event.passed === false) failures += 1;
      stepRows.push({caseId, line: index + 1, ...event, rawPath: `${eventRelative}:${index + 1}`});
    }
  }
  const state = suite?.state || (attempts.includes('failed') ? 'FAIL' : attempts.includes('passed') ? 'UNREPORTED' : 'BLOCKED');
  if (suite?.state === 'PASS' && (attempts.length !== 1 || attempts[0] !== 'passed' || failures)) throw new Error(`PASS suite conflicts with original evidence: ${caseId}`);
  caseRows.push({caseId, state, attempts: attempts.length, rawStatuses: attempts.join(', ') || '无', stepCount: stepRows.filter(step => step.caseId === caseId).length, failedSteps: failures,
    startedAt: suite?.started_at || '', finishedAt: suite?.finished_at || '', cleanup: suite?.cleanup_completed ?? false,
    playwrightPath: playwrightRelative, eventsPath: eventRelative, failure: (suite?.failures || []).join('\n') || playwrightErrors.filter(e => e.caseId === caseId).map(e => e.message.split('\n')[0]).join('\n')});
  for (const [field, label] of [['service_audit', '服务请求'], ['database_summary', 'SQLite 核对'], ['fixture_manifest', '造数清单'], ['sql', '造数 SQL']]) {
    const descriptor = suite?.[field];
    if (descriptor?.path) await readEvidence(descriptor.path, `${caseId} ${label}`, descriptor.sha256, descriptor.bytes);
  }
}

const updateCase = report.expected_cases.find(id => id === 'E2E-TM001-004');
let updateRequests = null;
if (updateCase) {
  const relative = `${updateCase}/update-requests.json`;
  const bytes = await readEvidence(relative, `${updateCase} 更新源请求`);
  if (bytes) {
    updateRequests = JSON.parse(bytes.toString('utf8'));
    if (updateRequests.run_id !== report.run_id || updateRequests.case_id !== updateCase) throw new Error('Update request identity mismatch');
    for (const request of updateRequests.requests || []) rawRequests.push(request);
  }
  for (const name of ['upgrade-result.json', 'upgrade-process.json']) {
    const relative = `${updateCase}/${name}`;
    await readEvidence(relative, `${updateCase} ${name}`);
  }
}

let followup = null;
if (updateCase) {
  const relative = `${updateCase}/cleanup-followup.json`;
  const target = await ownedFile(relative);
  if (target) {
    const bytes = await readEvidence(relative, `${updateCase} 事后归属清理`);
    followup = JSON.parse(bytes.toString('utf8'));
    if (followup.run_id !== report.run_id || followup.original_result_state !== report.state) throw new Error('Post-failure cleanup does not belong to this run');
  }
}

const workbookName = `TokenMeter测试结果-${report.run_id}.xlsx`;
const workbookPath = path.join(outputDir, workbookName);
const sidecarPath = path.join(outputDir, 'source-digests.json');
const verificationPath = path.join(outputDir, 'verification.json');
const fingerprint = sha(Buffer.from(JSON.stringify(Object.entries(sourceHashes).sort(([a], [b]) => a.localeCompare(b))), 'utf8'));
try {
  const existing = JSON.parse(await fs.readFile(sidecarPath, 'utf8'));
  const verification = JSON.parse(await fs.readFile(verificationPath, 'utf8'));
  const existingHash = await fileHash(workbookPath);
  const workbookStat = await fs.stat(workbookPath);
  if (existing.run_id !== report.run_id || existing.source_fingerprint !== fingerprint || existing.workbook_sha256 !== existingHash ||
      verification.state !== 'PASS' || verification.run_id !== report.run_id ||
      verification.source_report?.sha256 !== sourceHashes[reportPath] ||
      verification.workbook?.sha256 !== existingHash || verification.workbook?.bytes !== workbookStat.size) {
    throw new Error('An existing run workbook has different source evidence or contents; refusing to overwrite it');
  }
  console.log(JSON.stringify({...verification, export_status: 'VERIFIED_UNCHANGED'}));
  process.exit(0);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
  try { await fs.access(workbookPath); throw new Error('Workbook exists without matching source manifest; refusing overwrite'); }
  catch (accessError) { if (accessError.code !== 'ENOENT') throw accessError; }
}

function safe(value) {
  if (value === null || value === undefined) return '';
  let text = typeof value === 'string' ? value : JSON.stringify(value);
  text = text.replaceAll('123456', '[生产初始凭据：见本机配置]')
    .replace(/Bearer\s+[A-Za-z0-9._~-]+/gi, 'Bearer [已脱敏]')
    .replace(/-----BEGIN [^-]+-----[\s\S]*?-----END [^-]+-----/g, '[已脱敏密钥]');
  // artifact-tool otherwise converts ISO strings to Excel date serials with General display.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(text)) text += ' UTC';
  return /^[=+@]/.test(text) ? `'${text}` : text;
}
const wb = Workbook.create();
const summaryRows = [
  ['运行批次', report.run_id, '原始 result.json'],
  ['运行总状态', report.state, '完整运行结论；不能由单个 PASS 场景覆盖'],
  ['聚合场景尝试', report.executed_cases, '该运行尚无新精细 TC 的逐项结果'],
  ['聚合场景通过', report.passed_cases, '只有原始 suite 和 Playwright 一致才计入'],
  ['聚合场景失败/阻断', (report.executed_cases || 0) - (report.passed_cases || 0), '见场景结果和缺失证据'],
  ['发行资格', report.release_eligible ? '有' : '无', '开发包或失败运行不能发布'],
  ['运行范围', report.scope, '六个旧聚合场景；新 TC 仍未执行'],
  ['版本编号', report.release_id, ''],
  ['开始时间 UTC', report.started_at, ''],
  ['结束时间 UTC', report.finished_at, ''],
  ['源码提交', report.source_commit, ''],
  ['工作树改动', report.working_tree_dirty ? '有' : '无', ''],
  ['候选树', report.candidate_tree, ''],
  ['DMG SHA-256', report.package?.dmg_sha256, '原始报告绑定'],
  ['App 树 SHA-256', report.package?.app_tree_sha256, '原始报告绑定'],
  ['包清单 SHA-256', report.package?.manifest_sha256, '原始报告绑定'],
  ['原包安装来源', report.package?.installed_source, ''],
  ['原包构建号', report.package?.build, ''],
  ['macOS / 架构', `${report.host?.macos || '未知'} / ${report.host?.architecture || '未知'}`, '本次实际机器'],
  ['执行时清理', report.cleanup_completed ? '全部完成' : '未全部完成', JSON.stringify(report.cleanup || {})],
  ['事后归属清理', followup ? '有单独记录' : '无', followup ? `${updateCase}/cleanup-followup.json；不改写原 FAIL` : ''],
  ['事后观察到的构建号', followup?.observed_app_build_after_update || '', '来自单独清理报告；不等于升级用例 PASS'],
  ['事后清理资源', followup ? `App 停止=${followup.owned_app_running === false}；ShipIt 缓存不存在=${followup.shipit_cache_absent === true}；Job 不存在=${followup.shipit_job_absent === true}；CDP 已释放=${followup.cdp_port_released === true}；私有工作区已清理=${followup.private_root_removed === true}` : '', '原始运行 cleanup_completed 仍为 FAIL 状态'],
  ['原始汇总错误', report.error || '无', '原始错误保留；失败先看 Playwright 断言'],
  ['结果 JSON SHA-256', sourceHashes[reportPath], reportPath],
  ['证据源指纹', fingerprint, '再次导出只验证同一源，不覆盖变化'],
];

const sheets = [];
function addTable(name, title, headers, rows, widths, freeze = true) {
  const sh = wb.worksheets.add(name); sh.showGridLines = false;
  sh.getRange('A2').values = [[title]];
  sh.getRange('A2').format.font = {name: 'Arial', size: 15, bold: true, color: '#183153'};
  const matrix = [headers, ...rows.map(row => row.map(v => typeof v === 'number' || typeof v === 'boolean' ? v : safe(v)))];
  const grid = sh.getRangeByIndexes(3, 0, matrix.length, headers.length);
  grid.values = matrix;
  grid.format.font = {name: 'Arial', size: 10, color: '#243247'};
  grid.format.verticalAlignment = 'center'; grid.format.wrapText = true;
  grid.format.rowHeight = 32;
  const head = sh.getRangeByIndexes(3, 0, 1, headers.length);
  head.format.fill = '#234C78'; head.format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
  head.format.horizontalAlignment = 'center'; head.format.rowHeight = 32;
  widths.forEach((width, i) => sh.getRangeByIndexes(0, i, matrix.length + 3, 1).format.columnWidth = width);
  if (rows.length) {
    for (let i = 0; i < rows.length; i++) {
      if (i % 2) sh.getRangeByIndexes(i + 4, 0, 1, headers.length).format.fill = '#F3F6FA';
      const max = Math.max(...rows[i].map((value, col) => {
        const chars = String(value ?? '').length;
        return Math.ceil(chars / Math.max(10, widths[col] * 0.75));
      }));
      sh.getRangeByIndexes(i + 4, 0, 1, headers.length).format.rowHeight = Math.min(160, Math.max(30, max * 14 + 10));
    }
    if (freeze) sh.freezePanes.freezeRows(4);
  }
  sheets.push({name, rows: rows.length, columns: headers.length});
  return sh;
}

const overview = addTable('00运行概览', 'TokenMeter 测试结果', ['项目', '实测或绑定值', '说明'], summaryRows, [31, 78, 97], false);
overview.tabColor = '#234C78';
overview.getRange('B6').format.fill = report.state === 'PASS' ? '#E8F2E9' : '#FDE8E7';
overview.getRange('B6').format.font = {name: 'Arial', size: 11, bold: true, color: report.state === 'PASS' ? '#206B3A' : '#9A201B'};

addTable('01场景结果', '六组聚合场景的实际结果',
  ['场景编号', '状态', '原始尝试数', 'Playwright 状态', '记录步骤', '失败步骤', '开始 UTC', '结束 UTC', '执行时清理', '失败或阻断原因', 'Playwright 原件', '步骤原件'],
  caseRows.map(c => [c.caseId, c.state, c.attempts, c.rawStatuses, c.stepCount, c.failedSteps, c.startedAt, c.finishedAt, c.cleanup ? '完成' : '未完成/未汇总', c.failure, c.playwrightPath, c.eventsPath]),
  [27, 16, 17, 22, 16, 15, 30, 30, 24, 92, 58, 55]);

addTable('02逐步实测', '原始断言步骤（不等于新增 TC 的执行）',
  ['场景编号', '原始行', '时间 UTC', '步骤标识', '观察来源', '界面标识', '预期', '实测', '通过', '原始证据'],
  stepRows.map(e => [e.caseId, e.line, e.timestamp, e.step, e.source, e.testid, e.expected, e.actual, e.passed, e.rawPath]),
  [27, 12, 31, 36, 17, 38, 100, 100, 12, 67]);

addTable('03更新请求', '004 同机更新源的原始请求',
  ['序号', '阶段', '时间 UTC', '方法', '路由', 'HTTP', '实发字节', '响应 SHA-256', '源地址'],
  rawRequests.map((r, i) => [i + 1, r.stage, r.time, r.method, r.route, r.status, r.bytes_sent, r.body_sha256, updateRequests?.origin]),
  [10, 18, 31, 12, 37, 12, 18, 70, 44]);

const evidenceRows = evidence.map((item, i) => [i + 1, item.role, item.status, item.path, item.expectedSha || '', item.actualSha || '', item.expectedBytes ?? '', item.actualBytes ?? '']);
evidenceRows.push([evidenceRows.length + 1, '原始运行汇总', '已核对', reportPath, sourceHashes[reportPath], sourceHashes[reportPath], reportBytes.length, reportBytes.length]);
addTable('04证据与缺口', '证据完整性及事后清理',
  ['序号', '证据', '状态', '原始路径', '期望摘要', '实际摘要', '期望字节', '实际字节'], evidenceRows,
  [10, 42, 16, 85, 69, 69, 18, 18]);

wb.recalculate();
const inspection = await wb.inspect({kind: 'table', range: '00运行概览!A4:C12', include: 'values,formulas', tableMaxRows: 9, tableMaxCols: 3, maxChars: 2800});
const errors = await wb.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: {useRegex: true, maxResults: 100}, maxChars: 2500});
if (errors.ndjson.split('\n').filter(Boolean).some(line => JSON.parse(line).kind === 'match')) throw new Error('Workbook formula error');
const previewDir = path.join(projectRoot, '.local/workbook/test-result-previews', report.run_id);
await fs.mkdir(previewDir, {recursive: true, mode: 0o700});
await fs.writeFile(path.join(previewDir, 'inspection.ndjson'), inspection.ndjson);
for (const sheet of sheets) {
  const preview = await wb.render({sheetName: sheet.name, range: `A1:${String.fromCharCode(64 + Math.min(4, sheet.columns))}${Math.min(8, sheet.rows + 4)}`, scale: 1.2, format: 'png'});
  await fs.writeFile(path.join(previewDir, `${sheet.name}.png`), new Uint8Array(await preview.arrayBuffer()));
}

await fs.mkdir(outputDir, {recursive: true, mode: 0o700});
const tempPath = path.join(outputDir, `.${workbookName}.${process.pid}.tmp`);
try {
  const xlsx = await SpreadsheetFile.exportXlsx(wb);
  await xlsx.save(tempPath);
  await fs.chmod(tempPath, 0o600);
  await fs.link(tempPath, workbookPath); // Fails if a run result already exists.
} finally {
  await fs.rm(tempPath, {force: true});
  await fs.rm(`${tempPath}.inspect.ndjson`, {force: true});
}
const workbookSha = await fileHash(workbookPath);
const workbookStat = await fs.stat(workbookPath);
const sourceManifest = {schema_version: 1, run_id: report.run_id, source_fingerprint: fingerprint, source_hashes: sourceHashes,
  workbook: workbookName, workbook_sha256: workbookSha, run_state: report.state, release_eligible: report.release_eligible === true,
  cases: caseRows.length, steps: stepRows.length, sheets};
try { await fs.writeFile(sidecarPath, JSON.stringify(sourceManifest, null, 2) + '\n', {flag: 'wx', mode: 0o600}); }
catch (error) { throw new Error(`Workbook saved but source manifest could not be created; keep the workbook untouched: ${error.message}`); }
const verification = {schema_version: 1, state: 'PASS', export_status: 'EXPORTED', run_id: report.run_id,
  source_report: {path: reportPath, sha256: sourceHashes[reportPath]},
  workbook: {path: workbookName, sha256: workbookSha, bytes: workbookStat.size},
  source_fingerprint: fingerprint, run_state: report.state, release_eligible: report.release_eligible === true,
  cases: caseRows.length, steps: stepRows.length, update_requests: rawRequests.length, sheets};
try { await fs.writeFile(verificationPath, JSON.stringify(verification, null, 2) + '\n', {flag: 'wx', mode: 0o600}); }
catch (error) { throw new Error(`Workbook saved but verification receipt could not be created; keep the workbook untouched: ${error.message}`); }
console.log(JSON.stringify(verification));
