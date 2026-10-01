// Render the source-checked per-run TC model. Product conclusions come only
// from granular_test_result.py and the original run files, never this workbook.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const bundled = createRequire(path.join(root, '.local/workbook/loader.cjs'));
const {Workbook, SpreadsheetFile} = await import(bundled.resolve('@oai/artifact-tool'));
const args = process.argv.slice(2);
function option(name) {
  const index = args.indexOf(name);
  if (index < 0 || index + 1 >= args.length) throw new Error(`Missing ${name}`);
  return args[index + 1];
}
if (args.length !== 4 || !args.includes('--model') || !args.includes('--output')) {
  throw new Error('Usage: node scripts/export_granular_test_result.mjs --model <granular-source.json> --output <new directory>');
}
const modelPath = path.resolve(option('--model'));
const outputDir = path.resolve(option('--output'));
if (path.dirname(modelPath) !== outputDir || path.basename(modelPath) !== 'granular-source.json') {
  throw new Error('Model must belong to this new output directory');
}
const modelBytes = await fs.readFile(modelPath);
const model = JSON.parse(modelBytes.toString('utf8'));
if (model.schema_version !== 1 || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(model.run_id)) {
  throw new Error('Invalid granular source model');
}
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileHash = async file => sha(await fs.readFile(file));
function cell(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  let result = typeof value === 'string' ? value : JSON.stringify(value);
  result = result.replaceAll('123456', '[生产初始凭据：见本机配置]')
    .replace(/Bearer\s+[A-Za-z0-9._~-]+/gi, 'Bearer [已脱敏]')
    .replace(/-----BEGIN [^-]+-----[\s\S]*?-----END [^-]+-----/g, '[已脱敏密钥]');
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(result)) result += ' UTC';
  return /^[=+@]/.test(result) ? `'${result}` : result;
}

const workbook = Workbook.create();
const sheets = [];
function addTable(name, title, headers, rows, widths, statusColumn = -1) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.getRange('A2').values = [[title]];
  sheet.getRange('A2').format.font = {name: 'Arial', size: 15, bold: true, color: '#183153'};
  const matrix = [headers, ...rows.map(row => row.map(cell))];
  const grid = sheet.getRangeByIndexes(3, 0, matrix.length, headers.length);
  grid.values = matrix;
  grid.format.font = {name: 'Arial', size: 10, color: '#243247'};
  grid.format.verticalAlignment = 'center';
  grid.format.wrapText = true;
  const header = sheet.getRangeByIndexes(3, 0, 1, headers.length);
  header.format.fill = '#234C78';
  header.format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
  header.format.horizontalAlignment = 'center';
  header.format.rowHeight = 31;
  widths.forEach((width, index) => sheet.getRangeByIndexes(0, index, Math.max(5, matrix.length + 3), 1).format.columnWidth = width);
  rows.forEach((row, index) => {
    const line = sheet.getRangeByIndexes(index + 4, 0, 1, headers.length);
    if (index % 2) line.format.fill = '#F3F6FA';
    const length = Math.max(...row.map((value, col) => Math.ceil(String(value ?? '').length / Math.max(12, widths[col] * .85))));
    line.format.rowHeight = Math.min(110, Math.max(29, length * 14 + 8));
    if (statusColumn >= 0) {
      const state = String(row[statusColumn] ?? '');
      const point = sheet.getRangeByIndexes(index + 4, statusColumn, 1, 1);
      if (state === 'FAIL') {
        point.format.fill = '#FCE8E7'; point.format.font = {name: 'Arial', size: 10, bold: true, color: '#9A201B'};
      } else if (state === 'BLOCKED') {
        point.format.fill = '#FFF1D6'; point.format.font = {name: 'Arial', size: 10, bold: true, color: '#8B5A00'};
      }
    }
  });
  if (rows.length > 10) sheet.freezePanes.freezeRows(4);
  sheets.push({name, rows: rows.length, columns: headers.length});
  return sheet;
}

const counts = model.tc_counts;
const packageMatch = !model.aggregate_run_id ? '未附聚合场景原件'
  : model.aggregate_run_id === model.run_id ? '聚合与逐 TC 源于同一批次'
  : (model.candidate_sha && model.aggregate_candidate_sha && model.candidate_sha === model.aggregate_candidate_sha &&
     model.package_dmg_sha256 && model.package_dmg_sha256 === model.aggregate_dmg_sha256
      ? '候选源码与 DMG 摘要一致' : '两个运行的候选或 DMG 未核对为同一件');
const summaryRows = [
  ['逐 TC 批次', model.run_id, '本次 result.json；细化 TC 结论仅从逐 TC 原始记录取得'],
  ['本批次原始状态', model.product_state, '保留本次执行器结论'],
  ['父产品批次', model.parent_run_id || '不适用', model.parent_report_sha256 || '独立辅助单例会核对父原件 SHA-256'],
  ['逐 TC PASS', counts.PASS, '仅计完整步骤和本次证据'],
  ['逐 TC FAIL', counts.FAIL, '保留原始失败及原因'],
  ['逐 TC BLOCKED', counts.BLOCKED, '缺独立记录、证据或未定基线'],
  ['本次纳入 TM-001 父 TC', model.cases.length, '完整批次为 78；定向批次仅列目标父 TC'],
  ['本次产品父 TC', `${model.product_tc_counts.PASS} PASS / ${model.product_tc_counts.FAIL} FAIL / ${model.product_tc_counts.BLOCKED} BLOCKED`, '完整批次为 67 条；不含辅助 TC'],
  ['本次辅助父 TC', `${model.auxiliary_tc_counts.PASS} PASS / ${model.auxiliary_tc_counts.FAIL} FAIL / ${model.auxiliary_tc_counts.BLOCKED} BLOCKED`, '完整批次为 11 条；另见 08辅助用例'],
  ['参数变体总数', model.variants.length, '各变体独立显示在 02参数变体；父用例必须全变体通过'],
  ['参数变体 PASS', model.variant_counts.PASS, '只有本次步骤和证据完整才计入'],
  ['参数变体 FAIL / BLOCKED', `${model.variant_counts.FAIL} / ${model.variant_counts.BLOCKED}`, ''],
  ['未来功能用例', model.future.length, '本版不适用，另见 06未来功能'],
  ['本次范围外 TM-001', model.out_of_scope.length, '定向运行没有执行；另见 10范围外用例'],
  ['版本编号', model.release_id, ''],
  ['逐 TC 运行范围', model.scope, ''],
  ['逐 TC 候选源码', model.candidate_sha, ''],
  ['逐 TC DMG SHA-256', model.package_dmg_sha256, ''],
  ['逐 TC 开始 UTC', model.started_at, ''],
  ['逐 TC 结束 UTC', model.finished_at, ''],
  ['聚合场景批次', model.aggregate_run_id || '未提供', '六组场景单独列于 04聚合场景；不回填逐 TC'],
  ['聚合场景原始状态', model.aggregate_product_state || '未提供', ''],
  ['聚合场景候选源码', model.aggregate_candidate_sha, ''],
  ['聚合场景 DMG SHA-256', model.aggregate_dmg_sha256, ''],
  ['两批次原件关系', packageMatch, '如不同，结果各自对应原件'],
  ['辅助用例批次', model.auxiliary_run_id || '未提供', '11 条辅助 TC 另见 08辅助用例'],
  ['辅助批次原始状态', model.auxiliary_product_state || '未提供', ''],
  ['辅助原件关联', model.auxiliary_bound ? '已核对' : '未绑定', model.auxiliary_binding_reason],
  ['辅助运行开始 UTC', model.auxiliary_started_at, ''],
  ['辅助运行结束 UTC', model.auxiliary_finished_at, ''],
  ['独立复核状态', model.audit_state || '未提供', '逐例只可将本次 PASS 降为 FAIL 或 BLOCKED'],
  ['独立复核条数', model.audit.length, '逐例详情与原始证据见 11独立复核'],
  ['基础检查记录', model.checks.length, '实际检查逐项列于 05基础检查'],
  ['已核对的截图', model.evidence.filter(e => e.role.endsWith(' screenshots') && e.state === '已核对').length,
    '原件列于 07证据来源；选取关键截图展示在 09截图预览'],
  ['报表导出结果', 'PASS', '只表示结果表已生成，不改变产品或发布资格'],
];
const overview = addTable('00运行概览', 'TokenMeter 逐例测试结果', ['项目', '本次值', '说明'], summaryRows, [31, 82, 91]);
overview.tabColor = '#234C78';

addTable('01逐例结果', 'TM-001 逐条用例',
  ['TC 编号', '用例', '任务', 'AC', '类型', '设计状态', '原始状态', '本表判定', '判定批次', '辅助判定', '原因', '输入', '前置条件', '预期', 'DB 准备', 'DB 预期变化', 'DB 核对', '重置', '本次证据', '设计来源', '绑定代码', '复现命令', '独立复核原声称', '独立复核判定', '独立复核原因'],
  model.cases.map(c => [c.id, c.title, c.tasks, c.ac, c.type, c.design, c.reported_state, c.state,
    c.result_run_id, c.auxiliary_state, c.reason, c.input, c.preconditions, c.expected, c.db_prepare,
    c.db_changes, c.db_verify, c.reset, c.evidence, c.source, c.binding_code, c.replay_command,
    c.audit_claim, c.audit_state, c.audit_reason]),
  [31, 40, 33, 28, 17, 18, 17, 17, 40, 17, 72, 58, 70, 82, 70, 70, 70, 58, 69, 65, 67, 120, 23, 23, 80], 7);

addTable('02参数变体', '声明变体的独立结果',
  ['变体编号', '父 TC', '参数输入', '预期来源', '数据夹具', '父 TC 步骤', '原始状态', '本表判定', '原因', '本次证据', '绑定代码', '复现命令'],
  model.variants.map(v => [v.id, v.parent_id, v.input, v.expected, v.fixture, v.steps,
    v.reported_state, v.state, v.reason, v.evidence, v.binding_code, v.replay_command]),
  [36, 31, 70, 83, 27, 19, 17, 17, 75, 70, 67, 120], 7);

addTable('03逐步记录', '逐步设计与本次实际观察',
  ['TC 编号', '执行批次', '步骤', '设计动作', '界面预期', 'API/DB 预期', '设计完整预期', '本次执行动作', '本次断言预期', '本次实际', '判定', '本次原始证据'],
  model.steps.map(s => [s.tc_id, s.run_id, s.step, s.action, s.expected_ui, s.expected_db, s.expected,
    s.runtime_action, s.runtime_expected, s.actual, s.state, s.evidence]),
  [31, 39, 10, 65, 72, 72, 88, 70, 75, 80, 16, 72], 10);

addTable('04聚合场景', '六组 E2E 场景原始结果',
  ['运行批次', '场景编号', '原始状态', '失败或阻断原因', '开始 UTC', '结束 UTC', '执行时清理', '事件原件', '原件核对', '事件条数'],
  model.suites.map(s => [model.aggregate_run_id, s.id, s.state, s.reason, s.started, s.finished,
    s.cleanup === true ? '完成' : s.cleanup === false ? '未完成' : '未记录', s.events, s.evidence_state, s.event_count]),
  [47, 28, 17, 87, 31, 31, 21, 63, 25, 15], 2);

addTable('05基础检查', model.checks.length ? '本次基础检查' : '本次未提供基础检查原件',
  ['检查编号', '命令', '范围', '状态', '通过数', '总数', '退出码', '证据', '说明'],
  model.checks.map(c => [c.id, c.command, c.scope, c.state, c.passed, c.total, c.exit_code, c.evidence, c.note]),
  [28, 83, 46, 17, 15, 15, 15, 73, 78], 3);

addTable('06未来功能', '未来功能用例（本次不适用）',
  ['用例编号', '功能', '用例', '设计状态', '本次状态'],
  model.future.map(c => [c.id, c.feature, c.title, c.design, c.state]),
  [31, 17, 68, 23, 27]);

const sourceRows = model.source_files.map(e => [e.role, e.path, '已读取', e.sha256, '打开原件']);
const evidenceRows = model.evidence.map(e => [e.role, e.path, e.state, e.sha256, e.link ? '打开原件' : '缺失']);
const evidenceSheet = addTable('07证据来源', '本次原始来源与摘要',
  ['来源', '相对路径或名称', '核对状态', 'SHA-256', '本地链接'], [...sourceRows, ...evidenceRows],
  [47, 87, 27, 72, 20], 2);
const linked = [...model.source_files, ...model.evidence];
function addEvidenceLinks() {
  linked.forEach((e, index) => {
    if (!e.link) return;
    if (/[\x00-\x1f]/.test(e.link)) throw new Error('Evidence link contains control characters');
    evidenceSheet.getRangeByIndexes(index + 4, 4, 1, 1).format.font = {name: 'Arial', size: 10,
      color: '#176DB3', underline: 'single'};
  });
}

addTable('08辅助用例', model.auxiliary_run_id ? '辅助 11 TC 原始判定与主批次绑定' : '未提供辅助用例原件',
  ['TC 编号', '辅助批次', '原始状态', '证据判定', '主批次绑定', '绑定说明', '逐例原因', '本次证据', '绑定代码', '复现命令'],
  model.auxiliary.map(c => [c.id, c.run_id, c.reported_state, c.state, c.binding,
    c.binding_reason, c.reason, c.evidence, c.binding_code, c.replay_command]),
  [31, 42, 17, 17, 24, 80, 82, 75, 67, 120], 3);

const screenshotItems = model.evidence.filter(e => e.role.endsWith(' screenshots') && e.state === '已核对' && e.link);
const chosen = [];
const seenGroups = new Set();
const screenshotGroup = e => e.role.split(' ')[0].replace(/^(TC-TM001-[A-Z]+)-.*$/, '$1');
for (const item of screenshotItems) {
  const group = screenshotGroup(item);
  if (seenGroups.has(group)) continue;
  chosen.push(item); seenGroups.add(group);
  if (chosen.length === 12) break;
}
for (const item of screenshotItems) {
  if (chosen.length === 12) break;
  if (!chosen.includes(item)) chosen.push(item);
}
const previewRows = chosen.length ? chosen.map(e => [e.role.split(' ')[0], e.path, e.sha256,
  '待绘制', '原件见 07证据来源', '']) : [['本次没有已核对截图', '', '', '无预览', '', '']];
const screenshotSheet = addTable('09截图预览', '关键截图预览（完整清单见 07证据来源）',
  ['TC / 场景', '原件路径', 'SHA-256', '预览状态', '索引', '图像'], previewRows,
  [36, 83, 72, 27, 36, 36], 3);
for (let index = 0; index < chosen.length; index++) {
  const item = chosen[index];
  const file = path.resolve(outputDir, item.link);
  const bytes = await fs.readFile(file);
  if (sha(bytes) !== item.sha256 || !bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    throw new Error(`Verified screenshot changed or is not PNG: ${item.path}`);
  }
  screenshotSheet.getRangeByIndexes(index + 4, 3, 1, 1).values = [['已内嵌缩略图']];
  screenshotSheet.getRangeByIndexes(index + 4, 0, 1, 6).format.rowHeight = 115;
  screenshotSheet.images.add({dataUrl: `data:image/png;base64,${bytes.toString('base64')}`,
    anchor: {from: {row: index + 4, col: 5}, extent: {widthPx: 175, heightPx: 95}}});
}

addTable('10范围外用例', model.out_of_scope.length ? '本次定向运行没有执行的 TM-001 用例' : '完整批次没有范围外 TM-001 用例',
  ['用例编号', '用例', '本次范围状态'],
  model.out_of_scope.map(c => [c.id, c.title, c.state]),
  [31, 70, 38]);

addTable('11独立复核', model.audit.length ? '独立固定代码复核：仅将原 PASS 降级' : '本次未提供独立复核原件',
  ['TC 编号', '主原始状态', '复核原声称', '复核证据判定', '复核原因', '逐项原始证据', '原测试代码 SHA-256', '复核代码 SHA-256'],
  model.audit.map(c => [c.id, c.original_state, c.audit_claim, c.state, c.reason, c.evidence,
    c.test_code_sha256, c.auditor_code_sha256]),
  [33, 18, 19, 19, 100, 100, 73, 73], 3);

workbook.recalculate();
const inspection = await workbook.inspect({kind: 'table', range: '00运行概览!A4:C11', include: 'values,formulas',
  tableMaxRows: 8, tableMaxCols: 3, maxChars: 3000});
if (!inspection.ndjson.includes(model.run_id) || !inspection.ndjson.includes(String(model.cases.length))) {
  throw new Error('Workbook overview does not reflect the source model');
}
const errors = await workbook.inspect({kind: 'match',
  searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
  options: {useRegex: true, maxResults: 100}, maxChars: 1500});
if (errors.ndjson.split('\n').filter(Boolean).some(line => JSON.parse(line).kind === 'match')) {
  throw new Error('Workbook formula error');
}
const previewDir = path.join(outputDir, 'previews');
await fs.mkdir(previewDir, {mode: 0o700});
for (const sheet of sheets) {
  const end = String.fromCharCode(64 + Math.min(6, sheet.columns));
  const image = await workbook.render({sheetName: sheet.name, range: `A1:${end}${Math.min(9, sheet.rows + 4)}`,
    scale: 1.2, format: 'png'});
  await fs.writeFile(path.join(previewDir, `${sheet.name}.png`), new Uint8Array(await image.arrayBuffer()), {flag: 'wx', mode: 0o600});
}
addEvidenceLinks();
const workbookName = `TokenMeter测试结果-${model.run_id}.xlsx`;
const finalPath = path.join(outputDir, workbookName);
const temporary = path.join(outputDir, `.${workbookName}.${process.pid}.tmp`);
try {
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(temporary);
  await fs.chmod(temporary, 0o600);
  await fs.link(temporary, finalPath);
} finally {
  await fs.rm(temporary, {force: true});
  await fs.rm(`${temporary}.inspect.ndjson`, {force: true});
}
const linkReceipt = JSON.parse(execFileSync('python3', [path.join(root, 'scripts/finalize_granular_links.py'),
  '--workbook', finalPath, '--model', modelPath], {encoding: 'utf8'}));
if (linkReceipt.state !== 'PASS' || linkReceipt.links !== linked.filter(e => e.link).length) {
  throw new Error('Native evidence links failed readback');
}
const workbookSha = await fileHash(finalPath);
const workbookSize = (await fs.stat(finalPath)).size;
const receipt = {schema_version: 1, scope: 'granular_test_result_excel', state: 'PASS', run_id: model.run_id,
  product_state: model.product_state, parent_run_id: model.parent_run_id,
  aggregate_run_id: model.aggregate_run_id,
  tc_counts: model.tc_counts, variant_counts: model.variant_counts,
  future_count: model.future.length, suite_count: model.suites.length,
  check_count: model.checks.length, audit_count: model.audit.length,
  out_of_scope_count: model.out_of_scope.length, source_model_sha256: sha(modelBytes),
  workbook: {path: workbookName, sha256: workbookSha, bytes: workbookSize}, sheets};
await fs.writeFile(path.join(outputDir, 'verification.json'), JSON.stringify(receipt, null, 2) + '\n',
  {flag: 'wx', mode: 0o600});
console.log(JSON.stringify(receipt));
