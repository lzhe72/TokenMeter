# v0.1.0-20260929T074814Z — 实际测试结果

本文按 SOP-014/018/022/024 汇总已保存的真实原件和当前执行结果。它是结果索引，不是手写通过报告。dev07六个聚合场景组属于历史运行，不能回填新增精细TC。首轮精细全量`local-7feea03dd72e4eddba0651cede8fd23d`为BLOCKED；新版全量`local-343e54113b0b442383e80f137013014b`为FAIL。两轮原件均保留，后续定向及新包运行不改写它们。

## UPDATE-05定向探针：PASS，仅限709d候选（2026-10-02回读）

原始`.local/ci/local-65796d0033704e3988cd7174dec93c81/result.json`绑定被测提交`709d21253a0f88bc703a431cbf3adba3df17e508`、tree`6309bb70540407d90c8b059b4faef15879e691f9`、`scope=granular_targeted_probe`、`release_eligible=false`：`TC-TM001-UPDATE-05`父例1 PASS及13固定变体全部PASS，26逐步记录、清理完成；77条其他TM-001父TC明确范围外。本次不是该候选全部功能回归，也不覆盖此前本地主仓库c291最终包门禁FAIL。

后置导出器代码修复`de081a67734316381d598929ddd5a7814de7e264`从上述原报告生成`.local/test-results/local-65796d0033704e3988cd7174dec93c81/TokenMeter测试结果-local-65796d0033704e3988cd7174dec93c81.xlsx`，SHA-256`579dbfde25149265a97ab12bf85846b5e128d62cf4f94df7ff03b376eda16c16`；`verification.json`回读12 Sheet、父1/1及变体13/13、26步骤、77范围外，`excel-export.json`绑定原报告SHA-256`63068b93a6959fee58acbeb00dde9d6da062726df9b8de6aa0dd757b63403e48`。该修复没有重跑App或改变被测709d包。早期两次导出FAIL原件保留；本次只按SOP-024在根总表新增定向批次索引，正式发行仍NOT_RUN。

## 修复后独立候选门禁：PASS（2026-10-01）

只读核对 `.local/gates/tm001-final-gate-d2db551-20261001T0904Z/gate.json`：候选 `d2db5514e3dde2abb0b039f6188ae82f1ba3d53e`，tree `3854696e6212aa68aeccfdc720add187a4f92759`，被测 DMG SHA-256 `acc86a9f04ed19fe91f1b63481988d615f5d81680602eed1305b3896bb284492`、151500334 字节。门禁 `state=PASS`、`release_eligible=true`，执行约 2882 秒；主精细 116 行为 105 PASS、11 条辅助占位 BLOCKED，95 个实际 Playwright 入口全部完成。独立辅助 11/11、审计 12/12、补充六组 6/6 均 PASS；机器 `final-product-result.json` 规范化 78 父 TC、38 变体全部 PASS。主原件的 11 条占位未改写。

同目录通行证 `v0.1.0-20260929T074814Z.passport.json` SHA-256 为 `193bf39ca6bd2aed5a802f817ba5aa7bcfdaeeb442e272f1d843e381c941de53`；独立结果 Excel `granular-reviewed/TokenMeter测试结果-local-1ab724d58a804b56aafd05af7606803e.xlsx` SHA-256 为 `131a5e4038d5d4a11825e934484ec4e2c895819681bd8f189fbcf2b45e9d76d4`。E2E-003 的 service audit 有有效 `/v1/me` 200，E2E-004 的 `lsof` 有 125 个具名路径、零空项。原 DMG 位于 `.local/ci/tm001-final-package-d2db551-20261001T0857Z/`；根 `dmg/<release_id>/` 的同摘要副本文件名含 `CANDIDATE-NOT-RELEASED`，只是便捷入口。**此 PASS 只适用于上述独立候选**；总控最终 `master` 整合树、归档与正式分发仍须按 SOP-019/020 完成，不能把本分支门禁转写成最终发行通过。旧 `3467dc1` FAIL 见下节，未覆盖。

## 首次干净候选门禁：FAIL（2026-10-01）

候选`3467dc143b2e2fc71f51515f483f0ecff8637947`、DMG SHA-256 `e310a0aa5f05cc08930b4a2f57453c51a564ca16e5f3d756c65e25443ef1ac4d`的原始门禁位于`.local/gates/tm001-final-gate-3467dc1-20261001T0730Z/`。`gate.json`记录**FAIL**、`release_eligible=false`、错误`No actual identity verification`；没有通行证或`final-product-result.json`。精细主批次`local-2330ba0350354fbab6a7329f49512eec`的95个实际Playwright入口全部PASS，116条原始结果为105 PASS/0 FAIL/11辅助占位BLOCKED；辅助`aux-4697bca3e45e4671bb33484c659c0b03`为11/11 PASS，独立审计12/12 PASS，补充`local-82b058cbee2b4051a786eb15e19c53ef`为6/6 PASS。独立逐例Excel`granular-reviewed/TokenMeter测试结果-local-2330ba0350354fbab6a7329f49512eec.xlsx`及`verification.json`导出/回读PASS，但保留主原件的BLOCKED，不构成发布资格。

补充场景`E2E-TM001-003`缺少有效管理员会话的真实`/v1/me` 200；另在已失败报告上进行的只读逐项校验发现`E2E-TM001-004`的`lsof`采集结果含空名称，发布核验也会拒绝。原始请求与进程原件不改写。固定测试随后增加真实App重启恢复身份、管理员会话账号/角色断言，并让`lsof`解析忽略无名称行；修复后候选的实际结果见上节。

## 首次门禁前的待执行记录（历史）

本机最终门禁代码已将精细主批次、独立辅助11例、证据审计12项和补充六组的原始结果编排为同一候选验证，并另生成由机器复算的`final-product-result.json`及独立逐例Excel。以下段落保留首次门禁前的判断：当时开发包联合复核仍以`local-534748ff47cb44229183a6bd878c1674`等原件为依据，尚无干净候选完整门禁 PASS 或正式通行证。后来 `d2db551` 独立候选产生的新原件已在本页首节单独登记；旧开发包结果不能复制为它的证据。

## 当前新包回归结果（2026-10-01）

同一未发布开发包见`.local/ci/electron-package-fixes-20261001T0114Z/package-manifest.json`。首次完整精细回归`local-571dd63bfe5b4d90a95ed9c70d80de07`的原件`.local/ci/local-571dd63bfe5b4d90a95ed9c70d80de07/result.json`记`state=FAIL`、`cleanup_completed=true`、`release_eligible=false`：116个原始结果条目为104 PASS/1 FAIL/11 BLOCKED。11条BLOCKED是独立辅助程序尚未执行的占位，不能算已测通过。38条变体全部PASS，审阅模型将78父TC列为66 PASS/1 FAIL/11 BLOCKED；父TC与变体分开计数。独立证据审计`.local/ci/local-571dd63bfe5b4d90a95ed9c70d80de07-audit/audit.json`为PASS，没有改变SESSION-09失败。逐步结果和证据Excel是`.local/test-results/local-571dd63bfe5b4d90a95ed9c70d80de07-reviewed/TokenMeter测试结果-local-571dd63bfe5b4d90a95ed9c70d80de07.xlsx`；`verification.json`的导出状态PASS、产品状态FAIL，不能据表格回读放行。

`TC-TM001-SESSION-09`在第2步等待点击被禁用的“恢复默认”按钮30秒而失败，原件见该run下`TC-TM001-SESSION-09/playwright.log`和`playwright.json`。既定SESSION-09与CONFIG-06验收要求待退出时总恢复锁定，产品禁用按钮符合规则。固定测试脚本已改为断言按钮禁用，保留配置不变、无新服务请求、在线重试撤销及旧会话401的独立检查；原运行和Excel均保留。新定点批次`local-4a8815e9d61e4b4bbdd41f7a2f897c52`仅该TC四步PASS、清理完成，原件`.local/ci/local-4a8815e9d61e4b4bbdd41f7a2f897c52/result.json`，独立Excel`.local/test-results/local-4a8815e9d61e4b4bbdd41f7a2f897c52-reviewed/TokenMeter测试结果-local-4a8815e9d61e4b4bbdd41f7a2f897c52.xlsx`。该单例结论不能替换首批全量FAIL。

修订SESSION-09脚本后的第二次完整精细回归`local-f47f8257607c48458cc52b886d281d70`已结束为FAIL，`cleanup_completed=false`、`release_eligible=false`。原始报告`.local/ci/local-f47f8257607c48458cc52b886d281d70/result.json`的116条结果为103 PASS/1 FAIL/12 BLOCKED：唯一FAIL是UPDATE-07的owned资源清理；UPDATE-08因前一例清理未完成而阻断；其余11条BLOCKED是独立辅助程序占位。按审阅模型，78父TC为65 PASS/1 FAIL/12 BLOCKED，38参数变体全部PASS。UPDATE-07的`playwright.log/json`和`events.jsonl`明确记录真实升级、身份/配置与新PID文件归属五步全部PASS，但runner仍以`shipit=false`、`private=false`判该TC清理FAIL，不能把业务步骤PASS升级为整例PASS。

独立证据审计`.local/ci/local-f47f8257607c48458cc52b886d281d70-audit/audit.json`为PASS，只核对相应旁证，不改变清理FAIL及后续BLOCKED。逐步结果Excel在`.local/test-results/local-f47f8257607c48458cc52b886d281d70-reviewed/TokenMeter测试结果-local-f47f8257607c48458cc52b886d281d70.xlsx`；同目录`verification.json`为导出/回读PASS、`product_state=FAIL`。首次完整FAIL、SESSION-09定点PASS与本次清理FAIL各自独立保留。

第二次全量后的诊断指向本轮生成的空ByHost偏好文件：`defaults -currentHost read`报告域不存在。针对该返回值的固定清理代码修正已通过治理检查（`.local/ci/shipit-absent-domain-governance-20261001T0445Z/receipt.json`），但这只验证清理规则的固定测试。

新定点`local-c8e31657d5e4428584a6f316936113e1`实际执行UPDATE-07/08，同一开发包的原始`.local/ci/local-c8e31657d5e4428584a6f316936113e1/result.json`仍为FAIL、`cleanup_completed=false`、`release_eligible=false`。UPDATE-07五步Playwright全部PASS，但`shipit=false`和`private=false`，故整例FAIL；UPDATE-08因前例资源未清理而BLOCKED。独立Excel`.local/test-results/local-c8e31657d5e4428584a6f316936113e1-reviewed/TokenMeter测试结果-local-c8e31657d5e4428584a6f316936113e1.xlsx`已生成，`verification.json`为导出/回读PASS、`product_state=FAIL`，仅覆盖这两例。失败后归属预检`.local/ci/local-c8e31657d5e4428584a6f316936113e1-cleanup-followup-01/pre-cleanup.json`确认本次私有根和ShipIt状态的owner、空偏好文件及无存活安装App进程；该预检不等于清理完成，也不覆盖原FAIL。

即时升级后的ShipIt异步收尾可能解释首次规则修正仍未解决的时间差，因此继续实现有界、核对owner的稳定等待及额外诊断。当时在安全清理前暂停下一次GUI，随后产生以下独立定向原件；此前FAIL原件不改写。

`local-70e531d3092c4cbea30160117c379287`误用系统Python，在准备阶段因缺少`alembic`使UPDATE-07/08均为BLOCKED，`cleanup_completed=true`。原始`.local/ci/local-70e531d3092c4cbea30160117c379287/result.json`、独立审计`.local/ci/local-70e531d3092c4cbea30160117c379287-audit/audit.json`及逐步Excel`.local/test-results/local-70e531d3092c4cbea30160117c379287-reviewed/TokenMeter测试结果-local-70e531d3092c4cbea30160117c379287.xlsx`分别保留。审计和Excel回读均PASS，表格的`product_state=BLOCKED`，不构成产品通过。

`local-b6627e4379c64386bfc1a535fb432c16`改用项目venv，在同一开发包上重新执行固定UPDATE-07/08，两例原始结果均PASS，ShipIt及私有资源等逐例清理字段全true，`cleanup_completed=true`。原始`.local/ci/local-b6627e4379c64386bfc1a535fb432c16/result.json`、独立审计`.local/ci/local-b6627e4379c64386bfc1a535fb432c16-audit/audit.json`及结果Excel`.local/test-results/local-b6627e4379c64386bfc1a535fb432c16-reviewed/TokenMeter测试结果-local-b6627e4379c64386bfc1a535fb432c16.xlsx`分别保存；审计与Excel回读均PASS，表格的`product_state=PASS`。这是两例的定向结论，原始`release_eligible=false`；此前完整回归FAIL仍保持。

新完整精细批次`local-534748ff47cb44229183a6bd878c1674`使用同一未发布开发包和项目venv执行，原始`.local/ci/local-534748ff47cb44229183a6bd878c1674/result.json`的`state=BLOCKED`、`release_eligible=false`、`cleanup_completed=true`。116条结果为105 PASS/0 FAIL/11 BLOCKED：95个真实Playwright入口均PASS，10个父TC由已执行的参数变体推导PASS；11条BLOCKED只是在主runner中保留给独立辅助程序的占位，`step_results`为空，不能把它们改写成主run已执行PASS。UPDATE-07/08在本次完整运行中各自PASS且清理完成。逐例原始证据、测试代码摘要和清理字段均保存在该run目录。

独立辅助批次`aux-818fe55e1e8940e4a3196b9d03b76563`的原始`.local/ci/aux-818fe55e1e8940e4a3196b9d03b76563/result.json`为11 PASS/0 FAIL/0 BLOCKED，`cleanup_completed=true`。六组补充E2E的原始`.local/ci/local-5197628d58ac4136b004b87da438220c/result.json`为6/6 PASS、`cleanup_completed=true`，包含升级004的真实App断言和本轮ShipIt阶段诊断/空ByHost偏好副本摘要；独立结果Excel为`.local/test-results/local-5197628d58ac4136b004b87da438220c/TokenMeter测试结果-local-5197628d58ac4136b004b87da438220c.xlsx`。两批均在前一批退出后串行执行；辅助与聚合结论不能覆盖主run的原始BLOCKED。

主run独立证据审计v1`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit/audit.json`保留**BLOCKED**，当时唯一问题是`TC-TM001-PASSWORD-05`的peer fixture源码与已审阅绑定不一致。重新核对固定绑定后，审计v2`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit-v2/audit.json`为12/12 PASS；v1和主run原始报告没有改写。

联合逐例复核表`.local/test-results/local-534748ff47cb44229183a6bd878c1674-reviewed/TokenMeter测试结果-local-534748ff47cb44229183a6bd878c1674.xlsx`与同目录`verification.json`已导出并回读PASS。固定合并模型绑定同一候选的主run、辅助11例、审计v2和六组补充原件：78条父TC（67产品、11辅助）全PASS，38条参数变体全PASS，六组场景全PASS。`granular-source.json`记录`auxiliary_bound=true`及候选、包、时间关联；`verification.json`记录78/0/0父TC、38/0/0变体、12条审计及六组PASS，同时保留`product_state=BLOCKED`，因为主run原始11条辅助占位仍是BLOCKED。Excel的`state=PASS`只证明合并归档及回读通过，不能替代正式候选门禁。当前开发包的联合逐例复核全通过，但干净正式包、通行证及Git发布尚未完成，本版保持未发布。

## 1. 此前结论（保留历史原件）

- 本机 Electron 开发包运行 `e2e-dev-probe-07`：六组实际尝试，001/002/003/005/006 五组 PASS，004 FAIL；原始汇总为 `state=FAIL`、`passed_cases=5`、`release_eligible=false`。
- 使用 development 包和脏工作树，未锁定正式干净候选；即使五组通过也不具备发布资格。
- 004的新进程已被观察到，但即时 `lsof` 检查没有观察到预期profile文件，`new_process_profile_files` 断言失败；随后升级汇总证据缺失，不能将实际替换到101或后续清理解释为整个升级通过。
- 此处的五组PASS仅是dev07原件结果。当前固定代码覆盖67条产品父TC、11条辅助TC和38条变体。新版全量原始父TC为57 PASS/8 FAIL/13 BLOCKED，变体31 PASS/7 FAIL；辅助独立运行10 PASS/1 FAIL，证据审计再把五条原始PASS降为BLOCKED。联合结果模型为78条父TC 62 PASS/9 FAIL/7 BLOCKED，38条变体31 PASS/7 FAIL。开发包及脏工作树未锁定正式候选，无发布资格。

### 首轮精细全量批次：BLOCKED，保留原件

运行ID为`local-7feea03dd72e4eddba0651cede8fd23d`，原始目录为`.local/ci/local-7feea03dd72e4eddba0651cede8fd23d/`。`result.json`记录109条预期TC、16条PASS、93条BLOCKED，`release_eligible=false`、`cleanup_completed=true`，结束于2026-09-30 15:52:37 UTC。旧批次测试代码快照登记18条认证变体和13条更新变体；执行在LOGIN-17#A准备阶段因私有路径中的`#`被SQLite URI解释而中断，其余未执行条目保持BLOCKED。后续修复需新run重测，不能改写旧结果。该批次独立结果Excel位于`.local/test-results/local-7feea03dd72e4eddba0651cede8fd23d/TokenMeter测试结果-local-7feea03dd72e4eddba0651cede8fd23d.xlsx`。父TC只能由所有已声明变体的真实结果推导，不能由聚合场景代填。

固定入口为`python3 scripts/run_test_case.py --all --package-manifest <本轮包清单> --development`；单例复现用`--case-id <TC-ID>`替换`--all`，每次均生成新run_id。实际固定输入、动作、断言和判定由版本化的`scripts/granular_e2e.py`与`apps/desktop/e2e/granular-*.spec.ts`执行，Codex只调用命令并分析原始证据。新版回归应重新核对`result.json`、逐步事件、Playwright JSON、trace、DB/服务审计、清理结果和独立Excel；未完成时不能宣称产品PASS或签发通行证。

### 新版全量、辅助与证据审计：FAIL

新版原始目录为`.local/ci/local-343e54113b0b442383e80f137013014b/`；`result.json`记`state=FAIL`、`release_eligible=false`、`cleanup_completed=true`，结束于2026-09-30 17:00:15 UTC。启动前95个产品独立入口注册及全部granular TypeScript编译通过，但只属准备检查。原始116个条目由78父TC和38变体组成：父TC 57 PASS/8 FAIL/13 BLOCKED；变体31 PASS/7 FAIL。

11条辅助固定检查原件在`.local/ci/aux-local-343e54113b0b442383e80f137013014b-01/result.json`，记录10 PASS/1 FAIL、清理完成；UI-01失败来自测试脚本的`#fff`颜色解析。纯函数修复后，独立单例`aux-ui01-local-343e54113b0b442383e80f137013014b-02`真实PASS、清理完成，其独立Excel见下节；新run不改旧辅助FAIL。独立审计`.local/ci/local-343e54113b0b442383e80f137013014b-audit/audit.json`将原始PASS的CONFIG-02/03/04、UPDATE-01/07降为BLOCKED，审计未提升原始FAIL。当前主审阅模型仍为78父TC 62 PASS/9 FAIL/7 BLOCKED，38变体31 PASS/7 FAIL；后续新证据须另行复核并产出新版本模型，原始`result.json`维持原计数。

固定代码对已知覆盖缺口写入`coverage-blocked.json`：CONFIG-01/05缺默认服务启动前网络观察，CONFIG-06缺验证与原生安装阶段忙态观察，UPDATE-04缺零原生交接观察。其他断言通过时机器判BLOCKED；确定性断言失败则保留FAIL优先。审计另指出逐值配置保存回读、新进程`/me`、安装确认前零外连/交接和未经筛选的进程文件观察缺失。完整逐TC原件、服务/DB旁证与清理结果须按各自run查看，不能靠汇总数判断某项功能已通过。

定向复测`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed/result.json`有16条结果行：3条父TC加13条变体，其中UPDATE-05父TC由变体推导，实际Playwright执行入口为15个。机器结果10 PASS/6 FAIL、清理完成；PASSWORD-05第二App前置和ADMIN-03收尾脚本缺陷已修，两个父TC各获新run PASS。UPDATE-05父TC及INFO_VERSION、INFO_BUILD、BUNDLE_ID、CERT_MISMATCH、DR_MISMATCH五条变体仍FAIL。固定`cleanup-observation.json`对Info两例约20秒采样仍见本例临时目录残留，属于待修产品清理问题。定向PASS不替换全量FAIL，修复后须另起完整回归。

目标独立证据审计`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed-audit-peer-v3/audit.json`为PASS，核对PASSWORD-05第二App peer、两个旧会话401及ADMIN-03完整四步。先前v2审计快照保留为历史，不作为本次最终引用。审计PASS不提升UPDATE-05的确定性FAIL。

### 独立测试结果Excel

新版全量审阅表为`.local/test-results/local-343e54113b0b442383e80f137013014b-reviewed/TokenMeter测试结果-local-343e54113b0b442383e80f137013014b.xlsx`；同目录`verification.json`经回读为`state=PASS`、`product_state=FAIL`，登记78父TC 62 PASS/9 FAIL/7 BLOCKED与38变体31 PASS/7 FAIL/0 BLOCKED。该PASS只证明Excel从主raw、辅助和审计原件导出并核对，绝非产品门禁PASS。后续定向运行和UI-01新单例须作为新的独立结果保留，不能在此表中改写主全量。

UI-01修复后独立单例Excel为`.local/test-results/aux-ui01-local-343e54113b0b442383e80f137013014b-02-reviewed/TokenMeter测试结果-aux-ui01-local-343e54113b0b442383e80f137013014b-02.xlsx`，该次1 PASS、其余77条父TC范围外；报告的7张截图与53条链接属于该次固定用例的证据。它不覆盖原辅助运行的1 FAIL，也不改写上述主审阅表。

目标定向审阅表为`.local/test-results/local-877830fb340a4d12b4e29cf76fa422ed-reviewed/TokenMeter测试结果-local-877830fb340a4d12b4e29cf76fa422ed.xlsx`。同目录`verification.json`回读`state=PASS`、`product_state=FAIL`，登记3父TC 2 PASS/1 FAIL/0 BLOCKED与13变体8 PASS/5 FAIL/0 BLOCKED，并引用上述v3独立审计；它是新的定向结果，不改主全量表。

每次执行单独输出`.local/test-results/<run_id>/TokenMeter测试结果-<run_id>.xlsx`，保存该次逐例结果、步骤实测、失败、清理及原始证据索引。本次dev07的当前可读文件为`.local/test-results/local-a1b2c3d4e5f60718293a4b5c6d7e8f94/revisions/02/TokenMeter测试结果-local-a1b2c3d4e5f60718293a4b5c6d7e8f94.xlsx`。当前状态：**已生成，桥接校验与回读通过**；含5个Sheet、6个历史场景组、131条事件、14条更新请求、37条证据/缺口记录。这次整理只读取已有原件，不新跑测试、不补造缺失断言，不将原FAIL改成PASS。

根[项目总表](../../TokenMeter项目总表.xlsx)本次文档更新后重新导出为11个Sheet、109条用例摘要、12条历史测试批次和38个复盘案例；`.local/workbook/verification.json`登记文件SHA-256 `fa2b4efc47bed36caa67a4c011fdee2968ec36e4764510713bb2af1e9f4c076e`。对该SHA的`python3 scripts/verify_project_workbook.py`回读PASS、零错误，且明确`product_tests_executed=false`；此前SHA `ef94e5e15c1c6c0b4fe4a0ae8d550728c54ad502e317262b7dc02ffba41c8ae3`及旧`.local/workbook/readback.json`是历史收据。`05测试用例`只为用例摘要，`06测试批次`仍汇总旧12个run及各自独立Excel入口；`d2db551` 新门禁结果在原件归档后才作为新批次写入。主run原始BLOCKED与联合复核78父TC、38变体全PASS分别登记，不能用总表更新改写raw或发通行证。逐步事件、逐例结果及SQL详情保留在独立报告，352条设计步骤继续由`tests/test_cases.json`与用例文档保存。

独立导出收据`.local/ci/e2e-dev-probe-07/excel-export-b3c021927550bda4.json`记录`scope=test_result_excel_export`、`state=PASS`和`product_state=FAIL`；修订结果目录中的`verification.json`记录回读清单。源`result.json`的SHA256为`0d165916cee6ed516b142c4c26bc54ec161ea2a5be52fee60e311d101ddfc9d3`，当前可读Excel的SHA256为`2d476b47d1136916ac02ba3a063ea8c4db42b6881ac58f986b8c744f10726032`。原始报告没有修改，表格没有填补缺失升级证据。初次导出的Excel将ISO时间显示为日期序号，原文件及收据保留在原路径；修订02把时间列保存为可读的UTC文本，是同一次运行的显示修正，并非新测试。

`scripts/local_e2e.py`已接入自动导出，导出失败非零返回，收据与产品结论分开保存。定向工具检查runner11项、桥接18项通过，日志分别为`.local/planning/local-e2e-workbook-check.log`和`test-result-export-green.log`；不是新一次App测试。失败补导使用全新目录并保留原收据，无需重跑产品。候选执行期间不修改Git跟踪总表，执行和门禁结束后再更新摘要，继续关联原被测SHA。

## 2. 本次开发运行身份

| 字段 | 原件中的值 |
| --- | --- |
| release_id | `v0.1.0-20260929T074814Z` |
| run_id | `local-a1b2c3d4e5f60718293a4b5c6d7e8f94` |
| 原始目录 | `.local/ci/e2e-dev-probe-07/` |
| 执行范围 | runner为`development_package`；package为`development` |
| 候选标识 | `6e80dd12d60ee5dad641bca030445a2153a269c9`，`working_tree_dirty=true`；不代表该commit独立包含全部被测改动 |
| 源码树记录 | `771d2b637593e2e5140fb52de6ef76a62d2cf632`，须与dirty标志一起解释 |
| 实际平台 | 本机macOS15.7.4、x86_64；无arm64新客户端验收结论 |
| 时间（UTC） | `2026-09-30T11:22:02.779752Z` 至 `2026-09-30T11:24:17.173474Z` |
| 包清单 | `.local/ci/electron-package-probe-06/package-manifest.json` |
| DMG SHA256 | `09f0854cefc7584e1cc77e911d92cf1024a826d407e24241bb38cef11d35a529` |
| 原候选App树摘要 | `f68fc22b572adad39ca81ffbdccb65e6321cac9bc340808d6b361f4f7bf0aeef` |
| 清单摘要 | `a8c812d80fb4deb197364c82e33fc86af7231cf4aab6909d89718c75f6ee06f8` |

原DMG来源并不改变development资格；`installed_source=final_dmg`只说明从该镜像安装，不代表它已通过正式发布门禁。

## 3. 六个场景组的原始结果

| 场景组 | 实际范围 | Playwright原始结果 | 证据入口 |
| --- | --- | --- | --- |
| E2E-TM001-001 | 首次改密、自动登录/关闭、退出 | PASS，expected=1、unexpected=0、skip=0 | `E2E-TM001-001/playwright.json`、`events.jsonl`、trace/截图及服务/DB旁证 |
| E2E-TM001-002 | 错密、停用账号、成员权限 | PASS，expected=1、unexpected=0、skip=0 | `E2E-TM001-002/`同类原件 |
| E2E-TM001-003 | 管理员操作、审计及失效会话恢复拒绝 | PASS，expected=1、unexpected=0、skip=0 | `E2E-TM001-003/`同类原件 |
| E2E-TM001-005 | 合成生产首建、备份恢复及App首登 | PASS，expected=1、unexpected=0、skip=0 | `E2E-TM001-005/restore-state.json`、原SQLite副本及Playwright原件 |
| E2E-TM001-006 | 默认地址、双服务隔离、配置保存/恢复 | PASS，expected=1、unexpected=0、skip=0 | `E2E-TM001-006/`两份fixture/服务与Playwright原件 |
| E2E-TM001-004 | 四阶段拒绝/升级、自主新进程及profile | FAIL，expected=0、unexpected=1、skip=0、retry=0 | `E2E-TM001-004/playwright.json`、`events.jsonl`、`update-requests.json`、trace及失败截图 |

以上路径均相对本次原始目录。每组通过仅证明其**当时实际编写并运行的断言**。例如离线退出、完整输入变体、精确审计字段和全部会话撤销等新增精细要求，不能仅从组名推定已测。

### 3.1 004失败与汇总缺口

原始事件记录：自动发现、非法下载URL拒绝、非法重定向拒绝、坏签名拒绝以及`self_relaunch`均产生已通过断言。`runtime_unchanged`及`runtime_profile_after`也通过。随后在`2026-09-30T11:24:14.285Z`，`new_process_profile_files`预期true、实际false，测试立即失败。它只说明当时的观察未满足预期，**不能无证据断言只是观察时机问题，也不能据此断言整个升级没有发生**。

失败后未生成完整`upgrade-result.json`/`upgrade-process.json`；runner汇总报`Evidence is absent or outside the owned output`。原`result.json`因此虽然记录`executed_cases=6`，`suites`仅包含前五组，并记录`cleanup_completed=false`（installs/profiles/shipit未完成）。这些缺失本身也阻断发布，不能补写成功资产或改写原报告。

### 3.2 后续清理是独立事件

`.local/ci/e2e-dev-probe-07/E2E-TM001-004/cleanup-followup.json`记录`scope=post_failure_owned_cleanup`、`original_result_state=FAIL`、`release_eligible=false`。后续检查在本例隔离安装中观察到build101、runtime绑定profile；确认自有App已停止、ShipIt缓存/job不存在、CDP端口释放、新生成空ByHost状态及私有根已按归属清理。

这份记录补充资源处理结果，不改变原失败、原始清理字段或缺失升级证据；它不证明新App已完成界面、真实`/v1/me`恢复和全部升级断言。

## 3.3 本地 master 首次最终包门禁 FAIL（2026-10-01，后续独立批次）

总控在独立整合树对固定候选 `c2911bc65d55579fcf71e5ba11db87357a01a5e4`、tree `d4555b207b50e7cbe313b54ba9bfec1b7fdccb54` 运行正式包门禁；原件 `.local/gates/tm001-master-gate-c2911bc-20261001T113036Z/{gate.json,granular/result.json}` 为 FAIL、`release_eligible=false`。精细原始 116 项 91 PASS/14 FAIL/11 BLOCKED；UPDATE-05 父项及其 13 个变体因签名输入不可用失败。11 个 BLOCKED 是辅助程序占位，不能因其他独立候选的旧辅助结果而填成通过。

本次 run `local-0512d4fc44544eba97f9d1ae79cbfc37` 的独立结果 Excel `TokenMeter测试结果-local-0512d4fc44544eba97f9d1ae79cbfc37.xlsx`按固定程序从原件导出，摘要 SHA-256 `d57cc4827cfae8e7076a77f1ebfe3c9e21900346b5a4e1cc5f6e9232e3b50a62`；78 父 TC 为 66 PASS/1 FAIL/11 BLOCKED，38 变体为 25 PASS/13 FAIL。报表生成 PASS 只证明逐例记录一致，产品仍 FAIL；本地正式稳定包、通行证和 SOP-020 归档均不存在。TM-001 开发会话已收到 SOP-015 修复交接，新候选需完整重跑。

## 4. 精细用例的固定代码与执行缺口

### 2026-10-02 · 709d 登录定向五例

候选`709d21253a0f88bc703a431cbf3adba3df17e508`（tree`6309bb70540407d90c8b059b4faef15879e691f9`）从SHA-256 `c2f079452746d86397bb395450c4e46cec3e26a9eaa71217ca22dbfbb45257fb`的原DMG安装真实App，对`TASK-TM001-LOGIN-AUTH`固定`LOGIN-01/02/03/04/08`执行独立run`local-2aa05fb7b2754289a1d77b9ef89bd321`：五父例PASS、零FAIL/BLOCKED、11步，`cleanup_completed=true`。原报告`.local/ci/local-2aa05fb7b2754289a1d77b9ef89bd321/result.json` SHA-256 `2b27d3c2a6582d679a204166bacb0b033580928c7e6904b01b0d6a3d64301f40`；固定后置导出的独立结果Excel在同run的`.local/test-results/`，SHA-256 `35bb159ff87c81726f002134264bdb8a7a2d92d3ba3da57783e0cbc7ca29d47a`，verification回读PASS。前一次误带`--development`的run`local-7ce07b71ca1240de93c16a437ab7e292`在包清单预检时五例BLOCKED、App未启动，其原件仍独立保留，不并入这五个PASS。709d其余TM-001固定父例未运行；旧`c2911bc`完整门禁FAIL和正式发行NOT_RUN保持。

同一709d候选另有独立`TASK-TM001-LOGIN-SESSION` run`local-1d7d9238f9fd4d389e27cad990a6cb97`，固定`LOGIN-10/11/12/13/14/15`六父例、14步全部PASS、零FAIL/BLOCKED、清理完成。原报告SHA-256 `b4c5cc8c3c0b9ef4ad6d2e4a965cc665952142424af50b207f50aa513e7f9e45`，独立结果Excel SHA-256 `c53f52fc2e7f961e433121934e211f1f1cd917ce6d34c6dc37d6a4ef27715bdb`，verification回读PASS。两个run分别保留，不拼接为一次完整回归；709d未测的其他父例及旧完整门禁FAIL不变。

同包的`TASK-TM001-LOGIN-VALIDATION`另有run`local-5e076fa3d05b4d949877333a3b5339e0`：`LOGIN-05/06/07/09/17/18/19/20/21/22`十父例及17/18/19/22下12个固定变体，共22报告行PASS、36步、清理完成；其中4个父例由变体结果派生，18个是真实App执行。原报告SHA-256 `addde7aa03203f15ef8aa5b480714b5408024618c207a7032c1be9f8560085ea`，独立Excel SHA-256 `495242667704e4639a8a8389646afcfc96d28d79f991881df4d0bbef66f8669b`，verification回读PASS。`TASK-TM001-LOGIN-RATE`的`LOGIN-16`另一次run`local-09f2c4fd672848a9a68ba851a5d7b3c9`为一父例/三步真实App PASS、清理完成；原报告SHA-256 `f3793197707de6e877e80ad6e542a8131b8ccd226bd0ff7ca615fdffba34cbb2`，独立Excel SHA-256 `654629131838f9f937f4f0c6ed44e6ece9373792f9313ccd2dad368088ddb0c4`，verification回读PASS。四个登录任务在709d候选分别定向覆盖了22父例与12变体；TM-001其余功能、完整门禁及正式发行均不能由四批单独PASS推定。

`TASK-TM001-CHANGE-PASSWORD`另一次`local-64cdbd1050d84763928c0b6a7f30e2c3`覆盖`PASSWORD-01..11`十一父例和09/11下六变体：17报告行PASS、32步、清理完成，其中15次真实App执行、两父例由变体派生。原报告SHA-256 `687c5b5ebaa6f2a2befd85fe794c0aa3d69b47b8d125e739f3cf2387503f2282`，独立Excel SHA-256 `bc69c4011029b3d25e2a3047a0e9272c77f1d8ec0a7b75d2c491753306250418`，verification回读PASS；独立审计`.local/ci/local-64cdbd1050d84763928c0b6a7f30e2c3-audit/audit.json` SHA-256 `3aa2f3aee06aab191f974899825e84dda3099583aa857fb435f63ac1248792fb`仅核`PASSWORD-05`并PASS，不是12项完整审计。该批只证明709d候选改密功能定向范围；其他TM-001功能、旧完整门禁与正式发行不变。

`TASK-TM001-SESSION`另一次`local-ff24478631134a96bd7d40f2bbc5e254`覆盖`SESSION-01..10`十父例及`SESSION-05#RESET/#DISABLE`两变体：12报告行PASS、44步、清理完成；SESSION-05父例由两变体派生，其余11行为真实App执行。原报告SHA-256 `ef87c7d73190c398e8bdaf92eba94b18b57413ee0804296af938af64d320670f`、独立Excel SHA-256 `887fbc4bda8d617928a0f1b4d27f880046bb6e6ac39e5aadc9420625535093f2`，verification回读PASS；审计SHA-256 `ee5af01b0b3d0512caa63b9c3d60726f0ed2a136344c1617441816acd6deb58e`仅核`SESSION-04`并PASS，不是完整审计。该批仅为同一709d候选会话功能定向；其他功能与完整发行门禁状态不变。

[登录与改密01a](../../docs/testing/cases/01a-TM-001-login-scenarios.md)、[会话/管理/配置/升级01b](../../docs/testing/cases/01b-TM-001-session-admin-release-scenarios.md)、[交付检查01c](../../docs/testing/cases/01c-TM-001-delivery-checks.md)中的TC/变体均为本轮需求阶段基线修订。原代码先于这些精细条目存在，不能追认为先设计后开发已经完成。

- `tests/test_cases.json`当前有78条本版TC：67条产品父TC具备逐编号Playwright程序，另11条交付、目录和门禁辅助TC具备固定程序并已在独立批次执行。其余31条属于后续功能规划，不能纳入本版通过数。
- `tests/granular_login_variants.json`当前登记25条认证变体；`tests/granular_update_variants.json`登记13条UPDATE-05负例，均已绑定本机受控fixture与固定测试。证书差异和DR差异两条已通过固定非GUI组件检查，仍须跑正式App E2E。此前6条产品待决验收预期已按用户决定细化；不能再概称全部精细TC预期未定。
- `scripts/run_test_case.py`支持`--case-id`及`--all`，每例使用新隔离SQLite、App profile和对应fixture；`scripts/granular_e2e.py`检查精确ID、全部应有步骤、单次Playwright尝试、原始证据和清理。程序存在只说明可执行范围，最终结果必须取自本轮机器原件。
- 首轮全量BLOCKED，新全量和定向复测FAIL；审计指出的覆盖缺口、UPDATE-05产品清理残留及任何实际FAIL仍阻断完整发布门禁。逐次结果单独输出Excel，主表只登记批次摘要，不把设计或编程完成记为测试PASS。
- 全量用例入口见[根目录TEST_CASES](../../TEST_CASES.md)；需求至发布顺序见[本版本导航](README.md)。

## 5. 历史证据和阅读入口

SwiftUI/XCUITest的[CI36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502)曾在macOS15双架构各六例及父门禁PASS，并随[PR#2](https://github.com/lzhe72/TokenMeter/pull/2)合并。它只适用于当时Swift候选，不能替代当前Electron/App包/新增TC验收。构建、签名、视觉和治理组件检查同样不是产品全覆盖结论，详细历史见[06执行记录](06-iteration-record.md)。

用户统一查看入口为仓库根[TokenMeter项目总表.xlsx](../../TokenMeter项目总表.xlsx)，按用户要求随Git版本提交。主表保存任务和用例摘要、测试批次摘要及独立结果Excel入口；每次实际执行的明细单独成表，只保存在本机。完整用例设计见[tests/test_cases.json](../../tests/test_cases.json)与详细文档，不能把设计行标为通过。原始DMG/trace/数据库等执行证据仍只保存在本机。此前腾讯在线方案未写入，已停止同步。正式发行状态见[08发布记录](08-release-record.md)。
