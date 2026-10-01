// Export one immutable TM-002 source_check report. This reads the original
// module-test evidence; it never runs a test or changes a test conclusion.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const requireBundled = createRequire(path.join(root, '.local/workbook/loader.cjs'));
const {Workbook, SpreadsheetFile} = await import(requireBundled.resolve('@oai/artifact-tool'));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fail = message => { throw new Error(message); };
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const digest = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const gitId = value => typeof value === 'string' && /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(value);
const safeId = value => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value) && value !== '..';
const states = new Set(['PASS', 'FAIL', 'BLOCKED']);
const parents = new Map([['LIMIT', 1], ['STORE', 3], ['ACCESS', 3], ['SECURITY', 7],
  ['DATA', 1], ['CATALOG', 3], ['EVIDENCE', 7]]);
const fixedIds = [
  'TC-TM002-LIMIT-01',
  ...['KEY_UNAVAILABLE', 'DECRYPT_FAIL', 'WRITE_FAIL_KEEP_OLD'].map(value => `TC-TM002-STORE-01#${value}`),
  ...['PAGE_COMPLETION', 'REVOKE_CURSOR', 'TREE_CHANGED'].map(value => `TC-TM002-ACCESS-06#${value}`),
  ...['ABSOLUTE', 'FILE_URL', 'DOTDOT', 'TOKEN', 'STALE_SELECTION', 'REVOKE_DURING_REFRESH',
    'SWITCH_DURING_REFRESH'].map(value => `TC-TM002-SECURITY-01#${value}`),
  'TC-TM002-DATA-01',
  ...['VALID', 'MISSING_TASK', 'WRONG_RELEASE'].map(value => `TC-TM002-CATALOG-01#${value}`),
  ...['COMPLETE', 'MISSING_STEP', 'MISSING_PICKER', 'MISSING_CHOOSER_WITNESS', 'MISSING_FS',
    'WRONG_PACKAGE', 'FAILED_CLEANUP'].map(value => `TC-TM002-EVIDENCE-01#${value}`),
];
const fixedSet = new Set(fixedIds);

const args = process.argv.slice(2);
if (args.length !== 4 || new Set(args.filter(arg => arg.startsWith('--'))).size !== 2 ||
    !args.includes('--report') || !args.includes('--output')) {
  fail('Usage: node scripts/export_tm002_source_check.mjs --report <absolute source-check.json> --output <new directory>');
}
function option(name) {
  const index = args.indexOf(name);
  if (index < 0 || index + 1 >= args.length || args[index + 1].startsWith('--')) fail(`Missing ${name}`);
  return args[index + 1];
}
const reportArg = option('--report');
const outputArg = option('--output');
if (!path.isAbsolute(reportArg) || path.basename(reportArg) !== 'source-check.json') fail('Report must be an absolute source-check.json path');
if (!path.isAbsolute(outputArg)) fail('Output must be an absolute directory path');
const reportPath = path.normalize(reportArg);
const outputDir = path.normalize(outputArg);
const runDir = path.dirname(reportPath);
if (outputDir === runDir || outputDir.startsWith(runDir + path.sep) || runDir.startsWith(outputDir + path.sep)) {
  fail('Output must be separate from the original report directory');
}

async function noSymlinkAncestors(target) {
  let current = target;
  while (true) {
    try {
      const stat = await fs.lstat(current);
      if (stat.isSymbolicLink()) fail(`Symlink in protected path: ${current}`);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
}
async function stableRead(target) {
  await noSymlinkAncestors(target);
  const before = await fs.lstat(target);
  if (!before.isFile() || before.isSymbolicLink()) fail(`Not a regular evidence file: ${target}`);
  const bytes = await fs.readFile(target);
  const after = await fs.lstat(target);
  if (before.dev !== after.dev || before.ino !== after.ino || before.size !== after.size ||
      before.mtimeMs !== after.mtimeMs || bytes.length !== after.size) fail(`Evidence changed while being read: ${target}`);
  return bytes;
}
function relativePath(value, label) {
  if (typeof value !== 'string' || !value || value.includes('\\') || value.includes('\0') ||
      path.isAbsolute(value) || value.split('/').some(part => !part || part === '.' || part === '..')) {
    fail(`Invalid ${label} path: ${value}`);
  }
  return value;
}
function requireText(value, label) {
  if (typeof value !== 'string' || !value.trim()) fail(`Missing ${label}`);
  return value;
}
function git(...arguments_) {
  return execFileSync('git', arguments_, {cwd: root, encoding: 'utf8', maxBuffer: 24 * 1024 * 1024}).trim();
}
function gitBytes(revision, relative) {
  return execFileSync('git', ['show', `${revision}:${relative}`], {cwd: root, maxBuffer: 24 * 1024 * 1024});
}

const reportBytes = await stableRead(reportPath);
const runStat = await fs.stat(runDir);
if (!runStat.isDirectory() || runStat.uid !== process.getuid() || (runStat.mode & 0o777) !== 0o700) {
  fail('Original source_check run directory must be owned by the current UID with mode 0700');
}
const report = JSON.parse(reportBytes.toString('utf8'));
if (!isObject(report) || report.schema_version !== 1 || report.execution_type !== 'source_check') fail('Expected schema_version=1 source_check report');
if (!safeId(report.run_id) || !safeId(report.release_id)) fail('Invalid run_id or release_id');
if (path.basename(runDir) !== report.run_id) fail('Report run_id does not match its immutable run directory');
if (!gitId(report.candidate_sha) || !gitId(report.candidate_tree) ||
    git('rev-parse', `${report.candidate_sha}^{tree}`) !== report.candidate_tree) fail('Candidate commit/tree mismatch');
if (!Array.isArray(report.expected_ids) || report.expected_ids.length !== 25 || !Array.isArray(report.results) || report.results.length !== 25) {
  fail('TM-002 source_check must retain all 25 fixed IDs and results');
}
if (!isObject(report.environment) || ['os', 'architecture', 'node', 'python', 'started_at', 'finished_at']
  .some(key => typeof report.environment[key] !== 'string' || !report.environment[key])) fail('Missing execution environment');
if (report.product_e2e_state !== 'NOT_RUN' || report.release_eligible !== false) fail('Module check cannot claim product E2E or release eligibility');

const sourceFiles = new Map([[reportPath, {path: reportPath, sha256: sha(reportBytes), bytes: reportBytes.length, role: 'source-check report'}]]);
function recorded(pathname, bytes, role) {
  const found = sourceFiles.get(pathname);
  const entry = {path: pathname, sha256: sha(bytes), bytes: bytes.length, role};
  if (found && (found.sha256 !== entry.sha256 || found.bytes !== entry.bytes)) fail(`Conflicting evidence descriptor: ${pathname}`);
  if (!found) sourceFiles.set(pathname, entry);
  return entry;
}
for (const [role, descriptor, requiredPath] of [['catalog', report.catalog, 'tests/test_cases.json'],
  ['runner', report.runner, 'scripts/tm002_source_check.py']]) {
  if (!isObject(descriptor) || descriptor.path !== requiredPath || !digest(descriptor.sha256)) fail(`Invalid ${role} descriptor`);
  const bytes = gitBytes(report.candidate_sha, requiredPath);
  if (sha(bytes) !== descriptor.sha256) fail(`${role} differs from candidate commit`);
  recorded(`${report.candidate_sha}:${requiredPath}`, bytes, role);
}

function parentOf(id) {
  const match = /^TC-TM002-(LIMIT-01|STORE-01|ACCESS-06|SECURITY-01|DATA-01|CATALOG-01|EVIDENCE-01)(?:#([A-Z0-9_]+))?$/.exec(id);
  if (!match) fail(`Invalid TM-002 fixed ID: ${id}`);
  return {parentId: id.split('#')[0], group: match[1].split('-')[0]};
}
const expectedSet = new Set(report.expected_ids);
if (expectedSet.size !== 25) fail('Duplicate expected ID');
if (fixedSet.size !== 25 || [...expectedSet].some(id => !fixedSet.has(id))) fail('Expected IDs differ from the frozen 25-ID TM-002 source_check set');
const groupCounts = Object.fromEntries([...parents.keys()].map(group => [group, 0]));
for (const id of report.expected_ids) groupCounts[parentOf(id).group]++;
for (const [group, count] of parents) if (groupCounts[group] !== count) fail(`Incomplete ${group} fixed ID group`);
const resultSet = new Set();
const evidenceRows = [];
const stepRows = [];
const bindingRows = [];
const resultRows = [];
const logsByPath = new Map();
let limitMarkerPath = null;
for (const result of report.results) {
  if (!isObject(result) || !expectedSet.has(result.id) || resultSet.has(result.id)) fail(`Unknown or duplicate result ID: ${result?.id}`);
  resultSet.add(result.id);
  const {parentId} = parentOf(result.id);
  if (result.parent_id !== parentId || !states.has(result.test_state) || !states.has(result.state)) fail(`ID, parent or state mismatch: ${result.id}`);
  if (result.state === 'PASS' && result.test_state !== 'PASS') fail(`PASS lacks a passing fixed test: ${result.id}`);
  requireText(result.reason, `${result.id} reason`);
  requireText(result.input, `${result.id} input`);
  requireText(result.expected, `${result.id} expected`);
  if (!Array.isArray(result.actual_assertions) || result.actual_assertions.some(value => typeof value !== 'string' || !value.trim())) {
    fail(`Invalid actual assertions: ${result.id}`);
  }
  if (result.state === 'PASS' && result.actual_assertions.length === 0) fail(`PASS lacks actual assertions: ${result.id}`);
  if (!isObject(result.binding) || !digest(result.binding.code_sha256) ||
      typeof result.binding.test_name !== 'string' || !result.binding.test_name.trim() ||
      !Array.isArray(result.binding.command) || !result.binding.command.length ||
      result.binding.command.some(part => typeof part !== 'string' || !part)) fail(`Invalid fixed binding: ${result.id}`);
  const codePath = relativePath(result.binding.file, `${result.id} binding`);
  const codeBytes = gitBytes(report.candidate_sha, codePath);
  if (sha(codeBytes) !== result.binding.code_sha256) fail(`Binding code SHA differs from candidate: ${result.id}`);
  recorded(`${report.candidate_sha}:${codePath}`, codeBytes, 'fixed test code');
  const extraSources = result.binding.sources === undefined ? [] : result.binding.sources;
  if (!Array.isArray(extraSources)) fail(`Invalid direct-source bindings: ${result.id}`);
  const extraPaths = new Set();
  const extraSha = new Map();
  const sourceBindings = [];
  for (const source of extraSources) {
    if (!isObject(source) || !digest(source.sha256)) fail(`Invalid direct-source descriptor: ${result.id}`);
    const sourcePath = relativePath(source.file, `${result.id} direct source`);
    if (extraPaths.has(sourcePath)) fail(`Duplicate direct-source binding: ${result.id} ${sourcePath}`);
    extraPaths.add(sourcePath);
    extraSha.set(sourcePath, source.sha256);
    const sourceBytes = gitBytes(report.candidate_sha, sourcePath);
    if (sha(sourceBytes) !== source.sha256) fail(`Direct source differs from candidate: ${result.id} ${sourcePath}`);
    recorded(`${report.candidate_sha}:${sourcePath}`, sourceBytes, 'direct C source');
    sourceBindings.push(`${sourcePath}\nSHA-256 ${source.sha256}`);
    evidenceRows.push([result.id, '直接输入源码', sourcePath, source.sha256, sourceBytes.length, '已核对']);
  }
  if (result.id === 'TC-TM002-LIMIT-01' && (extraPaths.size !== 2 ||
      !extraPaths.has('apps/desktop/tests/tm002-limit-harness.c') ||
      !extraPaths.has('apps/desktop/native/source-helper.c'))) {
    fail('LIMIT-01 must bind both direct C source inputs from the candidate');
  }
  if (!Array.isArray(result.logs) || result.logs.length === 0) fail(`Missing raw logs: ${result.id}`);
  const ownLogs = new Map();
  for (const log of result.logs) {
    if (!isObject(log) || !digest(log.sha256) || !Number.isSafeInteger(log.bytes) || log.bytes < 0) fail(`Invalid log descriptor: ${result.id}`);
    const relative = relativePath(log.path, `${result.id} log`);
    if (ownLogs.has(relative)) fail(`Duplicate log in ${result.id}: ${relative}`);
    const full = path.resolve(runDir, relative);
    if (!full.startsWith(runDir + path.sep)) fail(`Log escapes run: ${relative}`);
    const bytes = logsByPath.get(relative)?.bytes ?? await stableRead(full);
    if (bytes.length !== log.bytes || sha(bytes) !== log.sha256) fail(`Raw log SHA/length mismatch: ${result.id} ${relative}`);
    logsByPath.set(relative, {bytes, sha256: log.sha256});
    recorded(full, bytes, 'raw test log');
    ownLogs.set(relative, bytes);
    evidenceRows.push([result.id, '原始命令日志', relative, log.sha256, log.bytes, '已核对']);
  }
  const rawText = [...ownLogs.values()].map(bytes => bytes.toString('utf8')).join('\n');
  if (result.id === 'TC-TM002-LIMIT-01') {
    const markers = [...ownLogs].flatMap(([relative, bytes]) => bytes.toString('utf8').split(/\r?\n/)
      .map(line => /^#\s+TM002_LIMIT_ACTUAL (.+)$/.exec(line))
      .filter(Boolean).map(match => ({path: relative, payload: match[1]})));
    if (result.state === 'PASS' && markers.length !== 1) {
      fail('LIMIT-01 must have one unique TAP actual marker when evidence passes');
    }
    // A failed or blocked C run may leave a partial marker. Its raw log and
    // reason remain exportable; only PASS asserts a complete marker.
    if (result.state === 'PASS') {
      let marker;
      try { marker = JSON.parse(markers[0].payload); }
      catch { fail('LIMIT-01 TAP actual marker is invalid JSON'); }
      const lines = marker?.stdout_lines;
      const frozenName = Buffer.from('A1.jsonl').toString('base64').replace(/=+$/, '');
      const isFrozenName = encoded => encoded?.replace(/=+$/, '') === frozenName;
      const audit = (line, operation) => {
        const match = new RegExp(`^AUDIT ${operation} candidate ([A-Za-z0-9+/]+={0,2}) \\d+ 101$`).exec(line);
        return match && isFrozenName(match[1]);
      };
      const item = /^ITEM ([A-Za-z0-9+/]+={0,2}) 25 1700000000 123456789 [0-9a-f]{64} -$/;
      const itemMatch = Array.isArray(lines) && typeof lines[3] === 'string' ? item.exec(lines[3]) : null;
      const counters = 'HARNESS clock=3 open=2 openat=0 read=0 fstat=4 dup=2 close=4 fdopendir=1 readdir=1 fstatat=1 closedir=1 unexpected=0 names=2';
      if (!isObject(marker) || marker.case_id !== result.id ||
          marker.input_sha256 !== extraSha.get('apps/desktop/tests/tm002-limit-harness.c') ||
          marker.algorithm_sha256 !== extraSha.get('apps/desktop/native/source-helper.c') ||
          !Array.isArray(lines) || lines.length !== 5 ||
          !audit(lines[0], 'enumerated') || !audit(lines[1], 'metadata') ||
          lines[2] !== 'PREVIEW timeout 1 1' || !itemMatch || !isFrozenName(itemMatch[1]) || lines[4] !== 'END' ||
          marker.stderr !== counters || marker.exit_code !== 0 || marker.scratch_removed !== true) {
        fail('LIMIT-01 TAP actual marker conflicts with fixed C input/output and cleanup');
      }
      limitMarkerPath = markers[0].path;
    }
  }
  const exactName = result.binding.test_name;
  const tapLine = rawText.split(/\r?\n/).filter(line => /^(?:ok|not ok)\s+\d+\s+-\s+/.test(line) &&
    line.replace(/^(?:ok|not ok)\s+\d+\s+-\s+/, '') === exactName);
  const unittestLine = rawText.split(/\r?\n/).filter(line => line.startsWith(`${exactName} (`) && /\s+\.\.\.\s+(?:ok|FAIL|ERROR|skipped .+)$/.test(line));
  if (tapLine.length + unittestLine.length > 1) fail(`Duplicate raw single-test result: ${result.id}`);
  if (result.test_state === 'PASS' && !(tapLine[0]?.startsWith('ok ') || unittestLine[0]?.endsWith('... ok'))) {
    fail(`Reported PASS lacks exact raw TAP/unittest success: ${result.id}`);
  }
  if (result.test_state === 'FAIL' && !(tapLine[0]?.startsWith('not ok ') || /\.\.\. (?:FAIL|ERROR)$/.test(unittestLine[0] || ''))) {
    fail(`Reported FAIL lacks exact raw TAP/unittest failure: ${result.id}`);
  }
  if (!Array.isArray(result.steps)) fail(`Invalid steps: ${result.id}`);
  const stepNumbers = new Set();
  for (const step of result.steps) {
    if (!isObject(step) || !Number.isSafeInteger(step.number) || step.number < 1 || stepNumbers.has(step.number) ||
        !states.has(step.state)) fail(`Invalid or duplicate step: ${result.id}`);
    stepNumbers.add(step.number);
    for (const key of ['action', 'expected', 'actual', 'evidence']) requireText(step[key], `${result.id} step ${step.number} ${key}`);
    if (![...ownLogs.keys()].some(relative => step.evidence.includes(relative))) fail(`Step has no bound raw-log path: ${result.id} #${step.number}`);
    stepRows.push([result.id, step.number, step.action, step.expected, step.actual, step.state, step.evidence]);
  }
  if (result.state === 'PASS' && (result.steps.length === 0 || result.steps.some(step => step.state !== 'PASS'))) {
    fail(`PASS lacks complete passing steps: ${result.id}`);
  }
  if (result.id === 'TC-TM002-LIMIT-01' && result.state === 'PASS' && result.steps.length !== 3) {
    fail('LIMIT-01 PASS must retain the three fixed step observations');
  }
  if (!isObject(result.cleanup) || !states.has(result.cleanup.state) ||
      typeof result.cleanup.mode !== 'string' || !result.cleanup.mode.trim() ||
      typeof result.cleanup.evidence !== 'string' || !result.cleanup.evidence.trim()) fail(`Missing cleanup result: ${result.id}`);
  if (result.state === 'PASS' && (result.cleanup.state !== 'PASS' ||
      ![...ownLogs.keys()].some(relative => result.cleanup.evidence.includes(relative)))) fail(`PASS lacks verified cleanup evidence: ${result.id}`);
  if (result.data_reset === null || result.data_reset === undefined ||
      (typeof result.data_reset === 'string' && !result.data_reset.trim())) fail(`Missing data/reset record: ${result.id}`);
  resultRows.push([resultRows.length + 1, result.id, result.parent_id, result.test_state, result.state,
    result.reason, result.input, result.expected, result.actual_assertions.join('\n'), result.steps.length]);
  bindingRows.push([result.id, codePath, exactName, result.binding.code_sha256, sourceBindings.join('\n\n'),
    result.binding.command.join(' '), typeof result.data_reset === 'string' ? result.data_reset : JSON.stringify(result.data_reset),
    result.cleanup.mode, result.cleanup.state, result.cleanup.evidence]);
}
if (resultSet.size !== expectedSet.size) fail('Missing fixed result ID');
if (report.expected_ids.some((id, index) => report.results[index]?.id !== id)) fail('Result order differs from the frozen expected ID list');
const counts = Object.fromEntries([...states].map(state => [state, report.results.filter(result => result.state === state).length]));
const testCounts = Object.fromEntries([...states].map(state => [state, report.results.filter(result => result.test_state === state).length]));
if (report.test_counts !== undefined && (!isObject(report.test_counts) ||
    [...states].some(state => report.test_counts[state] !== testCounts[state]) ||
    Object.keys(report.test_counts).length !== 3)) fail('Source-check test_counts differ from fixed single-test states');
if (!isObject(report.counts) || [...states].some(state => report.counts[state] !== counts[state]) ||
    Object.keys(report.counts).length !== 3) fail('Source-check counts differ from result states');
const overall = counts.FAIL ? 'FAIL' : counts.BLOCKED ? 'BLOCKED' : 'PASS';
if (report.state !== overall) fail('Source-check overall state differs from result states');
if (!Array.isArray(report.commands) || report.commands.length === 0) fail('Missing command manifest');
for (const command of report.commands) {
  if (!isObject(command) || !Array.isArray(command.command) || !Number.isInteger(command.exit_code) && command.exit_code !== null ||
      !isObject(command.stdout) || !isObject(command.stderr)) fail('Invalid raw command manifest');
  for (const descriptor of [command.stdout, command.stderr]) {
    if (!logsByPath.has(descriptor.path) || descriptor.sha256 !== logsByPath.get(descriptor.path).sha256 ||
        descriptor.bytes !== logsByPath.get(descriptor.path).bytes.length) fail('Command manifest refers to unverified log');
  }
}
for (const result of report.results) {
  const command = report.commands.find(item => JSON.stringify(item.command) === JSON.stringify(result.binding.command));
  if (!command || result.logs.every(log => log.path !== command.stdout.path && log.path !== command.stderr.path)) {
    fail(`Fixed binding command is not tied to its raw logs: ${result.id}`);
  }
  if (result.state === 'PASS' && (command.exit_code !== 0 || command.timeout !== false)) {
    fail(`Reported evidence PASS has failed or incomplete command: ${result.id}`);
  }
  if (result.id === 'TC-TM002-LIMIT-01' && result.state === 'PASS' && limitMarkerPath !== command.stdout.path) {
    fail('LIMIT-01 TAP actual marker is not in the bound command stdout');
  }
}

const sourceFingerprint = sha(Buffer.from(JSON.stringify([...sourceFiles.values()]
  .map(item => [item.path, item.sha256, item.bytes]).sort((a, b) => a[0].localeCompare(b[0])))));
const workbookName = `TokenMeter测试结果-${report.run_id}.xlsx`;
const workbookPath = path.join(outputDir, workbookName);
const verificationPath = path.join(outputDir, 'verification.json');
await noSymlinkAncestors(outputDir);

// Read the saved XLSX ZIP/XML independently of the in-memory workbook.
const readbackCode = String.raw`
import json, re, sys, zipfile, xml.etree.ElementTree as ET
ns = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(sys.argv[1]) as z:
    names = [s.attrib['name'] for s in ET.fromstring(z.read('xl/workbook.xml')).find('x:sheets',ns)]
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
            shared.append(''.join(t.text or '' for t in si.findall('.//x:t',ns)))
    result={}
    for n,name in enumerate(names,1):
        root=ET.fromstring(z.read(f'xl/worksheets/sheet{n}.xml'))
        rows=[]
        for row in root.findall('.//x:sheetData/x:row',ns):
            if int(row.attrib['r']) < 5: continue
            cells={}
            for cell in row.findall('x:c',ns):
                col=re.match(r'[A-Z]+',cell.attrib['r']).group()
                kind=cell.attrib.get('t')
                if kind=='inlineStr': value=''.join(t.text or '' for t in cell.findall('.//x:t',ns))
                else:
                    v=cell.find('x:v',ns); value='' if v is None else v.text or ''
                    if kind=='s': value=shared[int(value)]
                cells[col]=value
            if cells: rows.append(cells)
        result[name]=rows
print(json.dumps(result,ensure_ascii=False))
`;
function readback() {
  const raw = execFileSync('python3', ['-c', readbackCode, workbookPath], {encoding: 'utf8', maxBuffer: 24 * 1024 * 1024});
  const rows = JSON.parse(raw);
  const expectedSheets = ['00批次概况', '01逐项结果', '02逐步记录', '03证据索引', '04绑定与清理'];
  if (JSON.stringify(Object.keys(rows)) !== JSON.stringify(expectedSheets)) fail('Saved workbook sheet list differs');
  const ids = rows['01逐项结果'].map(row => row.B);
  const workbookStates = rows['01逐项结果'].map(row => row.E);
  if (JSON.stringify(ids) !== JSON.stringify(report.expected_ids) ||
      JSON.stringify(workbookStates) !== JSON.stringify(report.results.map(result => result.state))) fail('Saved workbook ID/state readback differs');
  if (rows['01逐项结果'].length !== resultRows.length || rows['02逐步记录'].length !== stepRows.length ||
      rows['03证据索引'].length !== evidenceRows.length || rows['04绑定与清理'].length !== bindingRows.length ||
      JSON.stringify(rows['04绑定与清理'].map(row => row.A)) !== JSON.stringify(report.expected_ids)) fail('Saved workbook row counts or binding IDs differ');
  return {result_rows: ids.length, step_rows: rows['02逐步记录'].length,
    evidence_rows: rows['03证据索引'].length, binding_rows: rows['04绑定与清理'].length,
    ids, states: Object.fromEntries(ids.map((id, index) => [id, workbookStates[index]]))};
}
async function verifyExisting() {
  const raw = await stableRead(verificationPath);
  const existing = JSON.parse(raw.toString('utf8'));
  const workbookBytes = await stableRead(workbookPath);
  if (existing.state !== 'PASS' || existing.execution_type !== 'source_check' || existing.run_id !== report.run_id ||
      existing.candidate_sha !== report.candidate_sha || existing.candidate_tree !== report.candidate_tree ||
      JSON.stringify(existing.expected_ids) !== JSON.stringify(report.expected_ids) ||
      existing.source_fingerprint !== sourceFingerprint || existing.source_report?.path !== reportPath ||
      existing.source_report?.sha256 !== sha(reportBytes) || existing.workbook?.path !== workbookName ||
      existing.workbook?.sha256 !== sha(workbookBytes) || existing.workbook?.bytes !== workbookBytes.length) {
    fail('Existing output belongs to different source evidence or changed workbook; refusing overwrite');
  }
  const check = readback();
  if (JSON.stringify(check) !== JSON.stringify(existing.readback)) fail('Existing workbook readback differs from receipt');
  return {...existing, export_status: 'VERIFIED_UNCHANGED'};
}
try {
  const entry = await fs.lstat(outputDir);
  if (!entry.isDirectory() || entry.isSymbolicLink() || entry.uid !== process.getuid() || (entry.mode & 0o777) !== 0o700) {
    fail('Existing output must be an owned directory with mode 0700');
  }
  let existing;
  try { existing = await verifyExisting(); }
  catch (error) { fail(`Existing output cannot be verified and will not be overwritten: ${error.message}`); }
  console.log(JSON.stringify(existing));
  process.exit(0);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

function safeCell(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  let result = String(value).replaceAll('123456', '[已脱敏初始凭据]')
    .replace(/Bearer\s+[A-Za-z0-9._~-]+/gi, 'Bearer [已脱敏]')
    .replace(/-----BEGIN [^-]+-----[\s\S]*?-----END [^-]+-----/g, '[已脱敏密钥]');
  if (/^\s*[=+@]/.test(result)) result = `'${result}`;
  if (/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(result)) result += ' UTC';
  return result;
}
const workbook = Workbook.create();
const sheetInfo = [];
function addSheet(name, title, headers, rows, widths, stateColumn = -1) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.getRange('A2').values = [[title]];
  sheet.getRange('A2').format.font = {name: 'Arial', size: 15, bold: true, color: '#183153'};
  const matrix = [headers, ...rows.map(row => row.map(safeCell))];
  const grid = sheet.getRangeByIndexes(3, 0, matrix.length, headers.length);
  grid.values = matrix;
  grid.format.font = {name: 'Arial', size: 10, color: '#243247'};
  grid.format.verticalAlignment = 'center';
  grid.format.wrapText = true;
  const heading = sheet.getRangeByIndexes(3, 0, 1, headers.length);
  heading.format.fill = '#234C78';
  heading.format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
  heading.format.rowHeight = 32;
  heading.format.horizontalAlignment = 'center';
  widths.forEach((width, index) => sheet.getRangeByIndexes(0, index, Math.max(5, matrix.length + 3), 1).format.columnWidth = width);
  rows.forEach((row, index) => {
    const line = sheet.getRangeByIndexes(index + 4, 0, 1, headers.length);
    if (index % 2) line.format.fill = '#F3F6FA';
    const lines = Math.max(...row.map((value, col) => String(value ?? '').split('\n')
      .reduce((sum, part) => sum + Math.max(1, Math.ceil(part.length / Math.max(12, widths[col] * .8))), 0)));
    line.format.rowHeight = Math.min(210, Math.max(30, lines * 15 + 8));
    if (stateColumn >= 0) {
      const state = row[stateColumn];
      const point = sheet.getRangeByIndexes(index + 4, stateColumn, 1, 1);
      if (state === 'FAIL') {
        point.format.fill = '#FCE8E7'; point.format.font = {name: 'Arial', size: 10, bold: true, color: '#9A201B'};
      } else if (state === 'BLOCKED') {
        point.format.fill = '#FFF1D6'; point.format.font = {name: 'Arial', size: 10, bold: true, color: '#8B5A00'};
      } else if (state === 'PASS') {
        point.format.fill = '#E8F2E9'; point.format.font = {name: 'Arial', size: 10, bold: true, color: '#206B3A'};
      }
    }
  });
  if (rows.length > 8) sheet.freezePanes.freezeRows(4);
  sheetInfo.push({name, rows: rows.length, columns: headers.length});
  return sheet;
}

const summary = [
  ['批次 ID', report.run_id, '原始 source-check.json；一次运行一份结果表'],
  ['执行类型', report.execution_type, '固定模块检查；产品 E2E 未运行'],
  ['模块证据结论', report.state, 'FAIL/BLOCKED 保留，不由导出器重算为 PASS'],
  ['固定 ID 总数', report.expected_ids.length, '7 个父 TC 下共 25 个固定单例/变体'],
  ['固定单例 PASS', testCounts.PASS, '原始 TAP/unittest 精确单例行；不等于证据完整'],
  ['固定单例 FAIL', testCounts.FAIL, '原始 TAP/unittest 精确失败行'],
  ['固定单例 BLOCKED', testCounts.BLOCKED, '原始单例行未取得或无法归属'],
  ['证据 PASS', counts.PASS, '真实单例和逐步/清理证据均完整'],
  ['证据 FAIL', counts.FAIL, '原始失败保留'],
  ['证据 BLOCKED', counts.BLOCKED, '缺逐步实测、清理证据或基线项'],
  ['产品 E2E', report.product_e2e_state, '此表不授予产品验收或发行资格'],
  ['发行资格', '无', '模块 source_check 与正式发布门禁分开'],
  ['版本', report.release_id, ''],
  ['候选提交', report.candidate_sha, '已与 Git tree 和固定源码哈希核对'],
  ['候选树', report.candidate_tree, ''],
  ['运行系统', report.environment.os, report.environment.architecture],
  ['Node', report.environment.node, '实际运行时'],
  ['Python', report.environment.python, '实际运行时'],
  ['开始 UTC', report.environment.started_at, ''],
  ['结束 UTC', report.environment.finished_at, ''],
  ['报告 SHA-256', sha(reportBytes), reportPath],
  ['证据指纹', sourceFingerprint, '报告、原始日志与候选源码摘要'],
];
addSheet('00批次概况', 'TokenMeter TM-002 固定模块测试结果', ['项目', '原始值或核对值', '说明'], summary, [30, 91, 105]);
addSheet('01逐项结果', '逐 TC/变体：固定单例与证据结论分开',
  ['序号', 'TC/变体 ID', '父 TC', '固定单例', '证据结论', '原因', '输入', '预期', '实际断言', '步骤数'],
  resultRows, [9, 44, 35, 15, 16, 91, 97, 97, 113, 12], 4);
addSheet('02逐步记录', '原始逐步实测；BLOCKED 行明确显示缺口',
  ['TC/变体 ID', '步号', '动作', '预期', '实测', '步骤状态', '原件位置'],
  stepRows, [44, 9, 91, 101, 101, 16, 94], 5);
addSheet('03证据索引', '原始命令日志与直接源码输入的 SHA-256',
  ['TC/变体 ID', '证据角色', '相对路径', 'SHA-256', '字节', '校验'],
  evidenceRows, [44, 22, 94, 70, 16, 15]);
addSheet('04绑定与清理', '固定源码、单例命令、数据重置与清理',
  ['TC/变体 ID', '固定源码', '单例名称', '源码 SHA-256', '直接输入源码及 SHA-256', '原始命令', '数据/重置', '清理方式', '清理状态', '清理证据'],
  bindingRows, [44, 75, 100, 70, 95, 112, 97, 25, 16, 103], 8);

workbook.recalculate();
// artifact-tool announces its inspection sidecar on stdout. Keep stdout as a
// single machine-readable receipt for the caller while still inspecting.
const originalLog = console.log;
const originalWrite = process.stdout.write;
let inspection, errors;
try {
  console.log = () => {};
  process.stdout.write = (...arguments_) => process.stderr.write(...arguments_);
  inspection = await workbook.inspect({kind: 'table', range: '01逐项结果!A4:E6',
    include: 'values,formulas', tableMaxRows: 3, tableMaxCols: 5, maxChars: 100000});
  errors = await workbook.inspect({kind: 'match',
    searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
    options: {useRegex: true, maxResults: 100}, maxChars: 3000});
} finally {
  console.log = originalLog;
  process.stdout.write = originalWrite;
}
if (!inspection.ndjson.includes(report.expected_ids[0])) fail('Artifact-tool inspection did not find the first fixed ID');
if (errors.ndjson.split('\n').filter(Boolean).some(line => JSON.parse(line).kind === 'match')) fail('Workbook formula error');

await fs.mkdir(outputDir, {mode: 0o700});
await fs.chmod(outputDir, 0o700);
const temporary = path.join(outputDir, `.${workbookName}.${process.pid}.tmp`);
try {
  const writer = process.stdout.write;
  try {
    process.stdout.write = (...arguments_) => process.stderr.write(...arguments_);
    const output = await SpreadsheetFile.exportXlsx(workbook);
    await output.save(temporary);
  } finally {
    process.stdout.write = writer;
  }
  await fs.chmod(temporary, 0o600);
  await fs.link(temporary, workbookPath);
} finally {
  await fs.rm(temporary, {force: true});
  await fs.rm(`${temporary}.inspect.ndjson`, {force: true});
}
const check = readback();
const workbookBytes = await stableRead(workbookPath);
if (sha(await stableRead(reportPath)) !== sha(reportBytes)) fail('Original source-check report changed during export');
for (const [relative, item] of logsByPath) if (sha(await stableRead(path.resolve(runDir, relative))) !== item.sha256) {
  fail(`Raw log changed during export: ${relative}`);
}
const receipt = {schema_version: 1, scope: 'tm002_source_check_excel', state: 'PASS',
  execution_type: 'source_check', run_id: report.run_id, release_id: report.release_id,
  candidate_sha: report.candidate_sha, candidate_tree: report.candidate_tree,
  expected_ids: report.expected_ids,
  source_report: {path: reportPath, sha256: sha(reportBytes), bytes: reportBytes.length},
  source_fingerprint: sourceFingerprint, counts, test_counts: testCounts, readback: check,
  workbook: {path: workbookName, sha256: sha(workbookBytes), bytes: workbookBytes.length}, sheets: sheetInfo};
await fs.writeFile(verificationPath, JSON.stringify(receipt, null, 2) + '\n', {flag: 'wx', mode: 0o600});
console.log(JSON.stringify(receipt));
