// Project workbook: source records remain traceable; this never runs product tests.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// SOP setup links this directory to the Codex bundled node_modules. No repo dependencies.
const runtimeRequire = createRequire(path.join(root, '.local/workbook/loader.cjs'));
const {Workbook, SpreadsheetFile} = await import(runtimeRequire.resolve('@oai/artifact-tool'));
const read = async name => JSON.parse(await fs.readFile(path.join(root, name), 'utf8'));
const context = await read('docs/project-register.json');
const catalog = await read('tests/test_cases.json');
const cases = catalog.cases;
const expandedCases = cases.flatMap(parent => [
  {case: parent, variant: null},
  ...(parent.variants || []).map(variant => ({case: parent, variant})),
]);
const latestRun=(context.test_runs || []).at(-1);
const currentRelease=context.metadata.release_id;
const fullRun=(context.test_runs || []).find(r=>r.run_id===context.metadata.observed_run_id && r.release_id===currentRelease);
const latestCaseStates=context.latest_case_states || {};
if (!Array.isArray(cases) || new Set(cases.map(c => c.id)).size !== cases.length) throw Error('Invalid case IDs');
const wb = Workbook.create();
const out = path.join(root, '.local/workbook');
await fs.mkdir(out, {recursive: true});
const plain = value => {
  if (value === null || value === undefined) return '未提供';
  if (Array.isArray(value)) return value.map(plain).join('\n');
  if (typeof value === 'object') return Object.entries(value).map(([k,v]) => `${k}：${plain(v)}`).join('\n');
  return String(value).replaceAll('`', '');
};
const cell = value => {
  if(value instanceof Date || typeof value === 'number' || typeof value === 'boolean')return value;
  const text=plain(value);return /^[=+@]/.test(text) ? "'"+text : text;
};
const states = {designed:'已设计', baseline_pending:'预期待明确', planned:'未来规划', unexecuted:'未执行', not_run:'未执行'};
const state = v => states[v] || v;
const kind = v => ({normal:'正向',negative:'负向',boundary:'边界',security:'安全/权限',fault:'故障',product_e2e:'产品E2E',source_check:'模块检查',security_unit:'安全单元',governance_unit:'治理检查',delivery_gate:'交付门禁',unit:'单元'})[v] || v;
const isAuxiliaryCase = c => /TC-TM001-(UI|CATALOG|RECORDS|GATE)-/.test(c.id) || ['source_check','security_unit','governance_unit','delivery_gate','unit'].includes(c.type);
const source = c => `${c.source?.path || c.source || ''}${c.source?.line ? ':'+c.source.line : ''}`;
const expected = c => c.overall_expected || [...new Set(c.steps.map(s => s.expected))].join('\n');
const databaseSummary = c => {
  const db = c.db_operations || {};
  return [db.prepare && `准备：${plain(db.prepare)}`,
    (db.expected_changes || db.expected_change) && `变化：${plain(db.expected_changes || db.expected_change)}`,
    db.verification && `核验：${plain(db.verification)}`,
    !db.verification && db.read_only_checks?.length && `只读核验：${db.read_only_checks.map(q=>q.id).join('、')}`,
  ].filter(Boolean).join('\n') || '见用例来源；尚未细化';
};
const sheetInfo = [];
function chunks(text, size=600) {
  const s = plain(text); const parts=[];
  for(let n=0;n<s.length;n+=size) parts.push(s.slice(n,n+size));
  return parts.length ? parts : ['不适用'];
}
function table(name, title, headers, rows, widths, options={}) {
  const sh = wb.worksheets.add(name);
  sh.showGridLines=false;
  sh.getRangeByIndexes(1,0,1,1).values=[[title]];
  sh.getRangeByIndexes(1,0,1,1).format.font={name:'Arial',size:15,bold:true,color:'#183153'};
  const clean = rows.map(row=>row.map(cell));
  const all=[headers,...clean];
  const range=sh.getRangeByIndexes(3,0,all.length,headers.length);
  range.values=all;
  range.format.font={name:'Arial',size:11,color:'#243247'};
  range.format.verticalAlignment='top';range.format.wrapText=true;
  range.format.rowHeight=30;
  widths.forEach((w,i)=>sh.getRangeByIndexes(0,i,Math.max(5,all.length+3),1).format.columnWidth=w);
  headers.forEach((h,j)=>{if(h==='时间'||h==='立项时间')sh.getRangeByIndexes(4,j,Math.max(1,clean.length),1).setNumberFormat('yyyy-mm-dd hh:mm:ss');});
  const head=sh.getRangeByIndexes(3,0,1,headers.length);
  head.format.fill='#234C78';head.format.font={name:'Arial',size:11,bold:true,color:'#FFFFFF'};
  head.format.horizontalAlignment='center';head.format.verticalAlignment='center';head.format.rowHeight=32;
  for(let i=0;i<clean.length;i++) {
    const row=sh.getRangeByIndexes(i+4,0,1,headers.length);
    if(i%2===1)row.format.fill='#F2F6FB';
    let maxLines=1;
    clean[i].forEach((v,j)=>{
      const approxChars=Math.max(8,(widths[j]||35)*0.78);
      const lines=String(v).split('\n').reduce((sum,s)=>sum+Math.max(1,Math.ceil([...s].reduce((n,ch)=>n+(ch.charCodeAt(0)>255?1.85:1),0)/approxChars)),0);
      maxLines=Math.max(maxLines,lines);
    });
    row.format.rowHeight=Math.min(409,Math.max(32,maxLines*15+12));
  }
  if(clean.length){
    const t=sh.tables.add(`A4:${String.fromCharCode(64+headers.length)}${all.length+3}`,true,`TMTable${sheetInfo.length+1}`);t.showFilterButton=true;t.style='TableStyleLight1';
    sh.freezePanes.freezeRows(4);
    sh.freezePanes.freezeColumns(options.freeze ?? 1);
    for(let j=0;j<headers.length;j++)if(/状态|结果/.test(headers[j])) {
      const r=sh.getRangeByIndexes(4,j,clean.length,1);
      r.conditionalFormats.add('containsText',{text:'FAIL',format:{fill:'#FDE8E7',font:{color:'#9A201B',bold:true}}});
      r.conditionalFormats.add('containsText',{text:'预期待明确',format:{fill:'#FFF2CD',font:{color:'#754E00'}}});
      r.conditionalFormats.add('containsText',{text:'未执行',format:{fill:'#FFF6DF',font:{color:'#754E00'}}});
    }
  }
  sheetInfo.push({name,rows:clean.length,columns:headers.length});
  return sh;
}

const labels={id:'编号',requirement_id:'需求编号',feature_id:'功能编号',acceptance_id:'验收编号',ac_ids:'验收编号',task_ids:'任务编号',title:'名称',name:'名称',description:'内容',status:'状态',scope:'范围',source:'依据',source_line:'来源行',priority:'优先级',acceptance:'验收要求',criterion:'验收条件',depends_on:'依赖',dependencies:'依赖',input:'输入',inputs:'输入',output:'产出及完成条件',outputs:'产出',completion:'完成条件',level:'层级',feature_point_id:'功能点编号',parent_feature_id:'父功能',version:'版本',release_id:'发布编号',state:'状态',trigger:'触发条件',prerequisites:'前提',sop:'SOP',next:'下一步',ac_id:'验收编号',acceptance_ids:'验收编号',acceptance_count:'验收数量',data_requirements:'数据要求',task_id:'任务编号',output_and_done:'产出及完成条件',historical_test_mapping:'历史场景映射',sop_id:'SOP编号',purpose:'目的与范围',ordered_operations:'有序操作',success_failure:'成功失败判据',exception_recovery:'异常恢复',evidence_location:'证据位置',next_step:'下一步',created_at:'立项时间',kind:'版本类型',feature_ids:'功能范围',manifest_state:'登记状态',distribution_profile:'分发方式',asset_storage:'产物存储',github_release:'GitHub发布',actual_state:'实际状态',remote_code_saved:'远端功能分支代码',local_product_state:'本机产品与稳定包',remote_master_state:'远端master',tag_state:'源码Tag',historical_evidence:'历史证据',status_source:'状态依据',ret_id:'复盘编号',implementation:'落地结果',line:'原始行',source_type:'观察来源',ui_testid:'界面标识',passed:'断言通过',raw_source:'原始证据',revision:'修订',question:'问题',problem:'问题',decision:'决策过程',solution:'解决方案',result:'落地结果',lesson:'经验借鉴',lessons:'经验借鉴',actual_result:'实际结果',case_id:'场景编号',step:'步骤',expected:'预期',actual:'实测',event_at:'时间',timestamp:'时间',evidence:'证据',missing:'缺项',case_type:'类型',publication:'发布状态',git:'Git记录',release_eligible:'发布资格',action:'动作',occurred_at:'时间',notes:'说明',run_id:'运行批次'};
function objects(name,title,records) {
  if(!Array.isArray(records)||!records.length)throw Error(`Missing source ${name}`);
  const keys=[...new Set(records.flatMap(r=>Object.keys(r)))];
  const rows=[];
  // Long narrative is split into continuation rows without discarding any text.
  for(const original of records){
    const record={...original};
    for(const key of ['created_at','timestamp'])if(record[key] && Number.isFinite(Date.parse(record[key])))record[key]=new Date(record[key]);
    const translations={main:'主功能',feature_point:'本轮功能点',concrete_task:'具体任务',concrete:'具体任务',specific:'具体任务',product_feature:'产品功能',design_baseline:'规范基线',historical_group:'历史分组',baselined:'已基线',planned:'规划中',not_published:'未发布',in_progress:'开发中'};
    for(const key of ['level','status','manifest_state','kind'])if(translations[record[key]])record[key]=translations[record[key]];
    const parts=keys.map(k=>chunks(record[k],650));
    const count=Math.max(...parts.map(p=>p.length));
    for(let i=0;i<count;i++)rows.push(keys.map((k,j)=>i===0?(record[k] instanceof Date||typeof record[k]==='number'||typeof record[k]==='boolean'?record[k]:parts[j][0]):parts[j][i] || (j===0?`${plain(record[k])}（续${i}）`:'')));
  }
  const widths=keys.map(k=>/^(id|.*_id|run_id|release_id)$/.test(k)?43:/source|evidence|description|criterion|problem|decision|solution|result|lesson|output|completion|scope|input|note/.test(k)?85:45);
  return table(name,title,keys.map(k=>labels[k]||k),rows,widths);
}

const overview = table('00项目总览','TokenMeter 项目总览',['项目','当前值','说明'],[
 ['当前版本',currentRelease,'未发布；版本状态见07发布版本'],
 ['需求数量',0,'01需求清单中的产品需求'],
 ['验收条件',0,'02验收条件，稳定AC编号'],
 ['已登记用例',0,'父用例与具有稳定 ID 的变体各占一行；含未来概要场景'],
 ['测试批次',0,'06测试批次，每次运行一行，记录独立结果Excel位置'],
 ['细化产品用例',expandedCases.filter(({case: c})=>!c.aggregate_planned&&!isAuxiliaryCase(c)).length,'逐条结果按运行批次记录；稳定变体独立列出'],
 ['界面与治理检查',expandedCases.filter(({case: c})=>isAuxiliaryCase(c)).length,'辅助检查不能替代产品E2E；稳定变体独立列出'],
 ['未来概要场景',cases.filter(c=>c.aggregate_planned).length,'进入对应功能需求阶段后继续细化'],
 ['预期待明确',expandedCases.filter(({case: c})=>c.design_status==='baseline_pending').length,'在05测试用例筛选此状态'],
 ['最近完整回归',fullRun?.state || '未执行',fullRun?.summary || '尚无完整运行记录'],
 ['工作顺序','需求 → 功能点 → 开发任务 → 测试用例 → 开发 → 测试结果 → 发布','先形成任务和用例基线，再实现；不按已有代码反推预期'],
 ['更新方式','本地工作簿随Git版本维护','保留稳定编号与实际批次；没有向腾讯在线表格写入'],
 ['查询用例','05测试用例：一例一行','汇总功能、任务、输入、预期、DB操作、类型和状态；详细设计按来源查阅'],
 ['查询结果','06测试批次 → 独立测试结果Excel','每次运行单独保存逐例、逐步实测和证据，不覆盖历史批次'],
 ['查询版本','07发布版本','DMG及原始证据留本机；Git保存代码、文档和此工作簿'],
 ['最近登记批次',latestRun?.state || '未执行',`${latestRun?.execution_type || '未标明类型'} · ${latestRun?.scope || ''}：${latestRun?.summary || '尚无实际运行记录'}；是否覆盖完整产品回归以批次范围和原始证据为准。`],
 ['用例执行状态','各用例最近一次有效证据','可能来自不同批次；05测试用例的状态汇总不能当作一次完整回归通过。'],
], [37,77,100]);
overview.tabColor='#234C78';
overview.getRange('B5:B19').format.horizontalAlignment='left';
objects('01需求清单','需求清单',context.requirements);
objects('02验收条件','验收条件',context.acceptance_criteria);
objects('03功能点','功能与功能点',context.features);
objects('04开发任务','具体开发任务及历史分组',[...context.development_tasks].sort((a,b)=>Number(a.level==='historical_group')-Number(b.level==='historical_group')));

const caseRows=expandedCases.map(({case: c, variant: v})=>{
  const id=v?.id || c.id;
  return [c.feature_id,id,v ? `${c.title} · 变体` : c.title,plain(c.task_ids)||'待拆解',kind(c.type),v?.input || c.input,v?.expected || expected(c),databaseSummary(c),state(c.design_status),state(latestCaseStates[id] || v?.execution_status || c.execution_status),c.aggregate_planned?'未来概要':v?'细化变体':'细化用例',source(c),context.latest_case_runs?.[id] || '尚未执行',c.release_id || catalog.release_id];
});
table('05测试用例','测试用例汇总 · 一例一行',['功能编号','用例编号','测试点','开发任务','类型','输入','预期结果','DB操作摘要','设计状态','执行状态','范围','详细设计依据','最近结果批次','归属版本'],caseRows,[18,41,46,55,26,85,120,100,23,20,22,85,65,52],{freeze:2});

const runs=context.test_runs || [];
const runRows=runs.map(r=>[r.run_id,r.release_id,r.execution_type,r.scope,r.state,r.included_cases ?? (r.passed_cases+r.failed_cases+(r.blocked_cases||0)),r.passed_cases,r.failed_cases,r.blocked_cases ?? 0,r.source_commit,r.release_eligible?'是':'否',r.summary,r.result_workbook,r.product_e2e_state || (r.execution_type==='source_check'?'NOT_RUN':r.state)]);
const runSheet=table('06测试批次','测试批次索引 · 模块与产品结果分别计数',['运行批次','版本','执行类型','范围','结果','父用例/场景数','通过数','失败数','阻塞数','候选提交','发布资格','批次摘要','独立结果Excel（本机）','产品E2E状态'],runRows,[55,52,24,43,18,22,14,14,14,55,16,95,95,22]);
for(let i=0;i<runs.length;i++) {
  const relative=runs[i].result_workbook;
  const absolute=path.resolve(root,relative);
  if(!absolute.startsWith(root+path.sep))throw Error('Result workbook must stay inside repository local storage');
  await fs.access(absolute);
  // The renderer does not support HYPERLINK; retain a readable portable path.
  runSheet.getRangeByIndexes(i+4,12,1,1).values=[[relative]];
}
objects('07发布版本','版本与实际发布状态',context.versions);
objects('08问题复盘','问题、决策与经验',context.retrospectives);
objects('09执行SOP','SOP索引 · 执行前完整读取独立文件',context.sops.map(s=>({sop_id:s.sop_id,name:s.name,trigger:s.trigger,prerequisites:s.prerequisites,outputs:s.outputs,status:s.status,revision:s.revision,source:s.source})));
const policies=[
 ['产品范围','macOS团队模型用量工具；首版TM-001先交付账号、配置与最小更新器，采集统计后续迭代。'],
 ['当前技术路线','Electron / React / TypeScript / Vite / electron-vite；FastAPI / SQLite；Playwright Electron；electron-builder。旧SwiftUI/XCUITest结果仅历史。'],
 ['测试与发布环境','当前本机macOS15 Intel；不要求完整Xcode；其他平台未验证。GitHub Actions仅在用户明确要求多环境时启动。'],
 ['默认服务','API 127.0.0.1:49176；更新源127.0.0.1:49177/version.json；App配置页可修改，测试用自己的动态端口。'],
 ['数据隔离','测试与生产SQLite分目录；回归只用合成账号与隔离副本。只操作本次拥有进程、目录和服务。'],
 ['用例数据简称','D42 / D-A42：seed42独立四账号库。A=test-admin（管理员），L=test-alice、B=test-bob（成员），D=test-disabled（停用成员）；均初始需改密。D-A43为独立seed43服务；P-NEW/P-RESET分别为用例中规定的合成新密码/重置密码。详细造数及SQL按TC来源查阅。'],
 ['认证','服务端根据用户名查账号并校验密码哈希。App不直接连SQLite比较明文密码。自动登录保存受保护token，恢复身份须真实调用/me。'],
 ['数据采集边界','只读授权日志；不采集对话/代码/密钥/完整本机路径。UTC存储，团队默认Asia/Shanghai。'],
 ['发布条件','最终包全部必测TC通过且证据一致、门禁PASS才发行。当前开发包测试和辅助检查均不能作为正式发布通行证。'],
 ['固定测试代码','每条TC预先固化输入、动作、预期和断言，AI只调用固定测试程序；不由AI临场点击或看图判定通过。代码路径、独立命令及本批次摘要在结果Excel追踪。'],
 ['版本命名','vMAJOR.MINOR.PATCH-YYYYMMDDTHHMMSSZ；贯穿需求、任务、用例、Changelog、通行证和Git tag。'],
 ['Git与资产','此xlsx随相关源码/文档提交；DMG、更新包、数据库和原始报告/通行证仅本地归档，不发布GitHub Release资产。'],
 ['测试记录','总表只保留用例汇总及测试批次索引；每次运行以run_id建立独立测试结果Excel，包含动作、预期、实测、失败、证据和清理，历史文件不覆盖。'],
 ['维护顺序','先改需求/任务/用例及结果依据，再更新结构化登记与此工作簿，核对后随Git版本提交。历史报告不改写。'],
 ['统一查看入口','本文件包含所有已登记产品需求、用例与版本的当前快照；原始证据仍可按编号追踪。未来功能概要不等于已细化或已实现。'],
];
table('10项目约定','项目约定与维护方式',['主题','约定'],policies,[35,145]);

overview.getRange('B6').formulas=[[`=COUNTA('01需求清单'!A5:A${(context.requirements?.length||0)+4})`]];
overview.getRange('B7').formulas=[[`=COUNTA('02验收条件'!A5:A${(context.acceptance_criteria?.length||0)+4})`]];
overview.getRange('B8').formulas=[[`=COUNTA('05测试用例'!B5:B${expandedCases.length+4})`]];
overview.getRange('B9').formulas=[[`=COUNTA('06测试批次'!A5:A${Math.max(5,runs.length+4)})`]];
wb.recalculate();
const inspect=await wb.inspect({kind:'table',range:'00项目总览!A4:C21',include:'values,formulas',tableMaxRows:18,tableMaxCols:3,maxChars:7000});
await fs.writeFile(path.join(out,'overview-inspection.ndjson'),inspect.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:4000});
await fs.writeFile(path.join(out,'formula-scan.ndjson'),errors.ndjson);
if(errors.ndjson.split('\n').filter(Boolean).some(line=>JSON.parse(line).kind==='match'))throw Error('Spreadsheet formula error; see formula-scan.ndjson');
for(const info of sheetInfo){
 const preview=await wb.render({sheetName:info.name,range:`A1:${info.columns>=4?'D':'C'}${Math.min(8,info.rows+4)}`,scale:1.3,format:'png'});
 await fs.writeFile(path.join(out,info.name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
for(const [name,range] of [['case-summary-detail','E4:J7'],['run-workbook-link','J4:N5']]){
 const preview=await wb.render({sheetName:name.startsWith('case')?'05测试用例':'06测试批次',range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const sourceStatusPreview=await wb.render({sheetName:'07发布版本',range:'N4:Q8',scale:1.3,format:'png'});
await fs.writeFile(path.join(out,'version-source-and-product-status.png'),new Uint8Array(await sourceStatusPreview.arrayBuffer()));
const statusPreview=await wb.render({sheetName:'00项目总览',range:'A13:C21',scale:1.3,format:'png'});
await fs.writeFile(path.join(out,'overview-current-status.png'),new Uint8Array(await statusPreview.arrayBuffer()));
const retrospectiveRows=sheetInfo.find(info=>info.name==='08问题复盘')?.rows || 0;
if(retrospectiveRows){
 const end=retrospectiveRows+4;
 const start=Math.max(4,end-4);
 const preview=await wb.render({sheetName:'08问题复盘',range:`A${start}:D${end}`,scale:1.3,format:'png'});
 await fs.writeFile(path.join(out,'retrospective-latest.png'),new Uint8Array(await preview.arrayBuffer()));
}
const target=path.join(root,'TokenMeter项目总表.xlsx');
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(target);
try{await fs.rename(target+'.inspect.ndjson',path.join(out,'xlsx.inspect.ndjson'));}catch(error){if(error.code!=='ENOENT')throw error;}
const bytes=await fs.readFile(target);
await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({file:target,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),parent_cases:cases.length,variant_cases:expandedCases.length-cases.length,case_rows:expandedCases.length,runs:runs.length,sheets:sheetInfo,product_tests_executed:false},null,2));
console.log(JSON.stringify({file:target,parent_cases:cases.length,variant_cases:expandedCases.length-cases.length,case_rows:expandedCases.length,runs:runs.length,sheets:sheetInfo.length,bytes:bytes.length}));
