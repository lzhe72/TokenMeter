# 当前状态

## 0.1 本地 master 门禁与源码检查点（2026-10-01）

本地 `master` 固定候选 `c2911bc65d55579fcf71e5ba11db87357a01a5e4`、tree `d4555b207b50e7cbe313b54ba9bfec1b7fdccb54` 的首次最终包门禁已于 2026-10-01 12:02:59Z 结束为 **FAIL**。总控整合树原件 `.local/gates/tm001-master-gate-c2911bc-20261001T113036Z/{gate.json,granular/result.json}` 为 `release_eligible=false`，精细原始 116 项 91 PASS/14 FAIL/11 BLOCKED；UPDATE-05 父项及 13 个变体缺私有签名输入。TM-001 开发会话确认执行器把该输入写死在旧 worktree 的 `.local`，新整合树缺目录，变体在启动 App 前失败；正在改为显式必填 `--key-dir`，检查目录及祖先路径安全、归属/权限、原ZIP Ed25519重签名与p12公有证书指纹，并向精细及单例runner透传。SOP-009/010/014/018/019已修订；实现是否完整符合新规则仍须以固定代码和实际负测核对，私有路径不得进报告。新run中公开候选包自身不一致为完整性FAIL；有效包缺私有输入为前置BLOCKED，预检通过不等于产品PASS；原c291 FAIL保留。修复尚未交付新固定候选，完整门禁仍须重跑；0.1 无正式稳定包，0.2 真实升级继续 BLOCKED。

文档会话为本次 run `local-0512d4fc44544eba97f9d1ae79cbfc37` 用固定程序生成独立结果 Excel（78 父 TC 66 PASS/1 FAIL/11 BLOCKED，38 变体 25 PASS/13 FAIL），报告生成 PASS 不改变产品 FAIL。根项目总表已追加为第 13 批，当前版本仍是 0.1；TM-002 的未来设计草稿不纳入本版门禁。SOP-019 修订 12 允许需求独立 worktree 的干净 WIP/候选提交快进保存到远端同名功能分支，总控可选单一 integration 镜像；每次须记录Git客户端绝对路径/版本，HTTP 400或超时后先读回远端精确ref/SHA/tree，无法读回为`remote_code_saved=unknown`。远端读回尚未由本次文档工作核实。本机产品/稳定发行、远端 `master` 和 Tag 分别记录；本分支未改 c291 被测树，也未产生新产品 PASS。

TM-001开发会话交接称代码提交`883bf567b16d57527acdb887537699a082c53c97`的独立定向run `local-67f0e7832e284f2d8986b03c0da716b3`有14/14项PASS、`cleanup=true`，原件在其worktree的`.local/ci/<run_id>/result.json`；这不是最终全量门禁。SOP会话另指出该实现仍需补私有`--key-dir`祖先路径检查和普通报告/输出中的完整路径脱敏；须待新代码、负测、新包与本地master完整门禁，不能以定向结果宣布0.1通过。

## TM-002 文档设计与0.1稳定包前置（2026-10-01）

当前版本指针暂为 `v0.1.0-20260929T074814Z`，供0.1固定里程碑执行最终门禁；TM-002档案已预登记。TM-002 已按三个功能点、九项 TASK 编制28条父TC和35个固定变体，并将详细规格、独立验收、机器用例与根项目总表同源核对；当前TM-002保持draft/baseline_pending，0.1严格基线和总表回读的实际结论见TM-002 06记录。计划中的原生面板、私有加密来源 locator、主进程受限读取和测试 Keychain 隔离仍缺固定数据/程序与最终包实测；当前还没有独立macOS测试账号或经原生证明的进程专属Keychain命名空间，依赖密钥的用例及SOP-009第5步保持BLOCKED，TM-002 产品 E2E 为 `NOT_RUN`，发布资格为否。

0.2的真实升级必须从 TM-001 在本地 `master` 固定0.1里程碑后，经同树最终包全量产品E2E、SOP-018门禁PASS和SOP-020本机归档取得的正式稳定0.1原包开始；远端源码登记与Tag可在全部目标版本后统一办理。独立 `d2db551` 候选虽有门禁PASS，本地 `4bdeb13` 整合树（已纳入里程碑归档校验代码）尚无同树产品门禁或稳定原包，故不能作为0.2升级源。旧失败原件和12次历史总表批次保留。

## 会话与文档交接（2026-10-01）

用户指定[“文档”会话](project-sessions.md)统一编写所有非 SOP 文档，**包括项目总表与每批测试结果 Excel**，随开发进度和原始证据持续更新；“SOP”会话维护 `sop/`；开发总控整合本地 `master`，需求会话继续实现与固定测试。已通知开发总控、SOP、TM-001 和 TM-002。TM-003/004/005 的独立开发分支已有文档草稿或已提交改动，正在由文档会话核对接管；草稿、缺产品绑定与产品 E2E 的阻断不因本次会话归口解除。跨版本门禁与本机稳定里程碑的 SOP-only 提交 `afee30d`、`090d808` 已由总控纳入本地 `master` `c6729ea`；本会话正在把对应非SOP规范、版本档案和总表整合成独立文档候选，最终整合后仍需检查产品里程碑。TM-001 旧 `3467dc1` 门禁 FAIL 原件保留；修复后独立候选 `d2db551` 的本机门禁原件已为 PASS、生成通行证，但总控最终 `master` 整合树仍须重新执行适用门禁，不能把分支结果写成正式发布。

## TM-001 独立候选门禁通过，最终整合待验（2026-10-01）

只读核对 `.local/gates/tm001-final-gate-d2db551-20261001T0904Z/gate.json`：候选 `d2db5514e3dde2abb0b039f6188ae82f1ba3d53e`、tree `3854696e6212aa68aeccfdc720add187a4f92759`、DMG SHA-256 `acc86a9f04ed19fe91f1b63481988d615f5d81680602eed1305b3896bb284492`。该独立候选门禁 `state=PASS`、`release_eligible=true`，主精细116行中105 PASS/11辅助占位BLOCKED；独立辅助11/11、审计12/12、补充六组6/6均PASS；规范化最终结果78父TC与38变体全PASS。同目录机器通行证已生成；逐例 Excel 位于 `granular-reviewed/TokenMeter测试结果-local-1ab724d58a804b56aafd05af7606803e.xlsx`。该 Excel 是本次门禁原件，不覆盖旧 FAIL 或给最终整合树授予资格。原件归档、总控整合后的完整回归与正式分发仍待核实；根总表在这些步骤完成后以独立文档提交登记本批次和被测SHA。

## TM-001 首次干净候选门禁失败（2026-10-01）

固定候选`3467dc143b2e2fc71f51515f483f0ecff8637947`的本机正式门禁已运行结束，原件`.local/gates/tm001-final-gate-3467dc1-20261001T0730Z/gate.json`为**FAIL**、`release_eligible=false`，没有通行证或正式DMG。精细主批次95个实际Playwright入口PASS、辅助11/11、审计12/12、补充六组6/6各自PASS，逐例Excel已导出并回读PASS；门禁仍因003组缺有效`/v1/me` 200而拒绝。只读核验还发现004组完整`lsof`列表中有一个空名称。原件保留。现已在固定测试中补真实App恢复身份、服务账号/角色断言及空名称解析回归；下一步冻结新候选、重建DMG并完整重测，当前**不可发布**。细节见[本版测试结果](../releases/v0.1.0-20260929T074814Z/07-test-results.md)和[修复记录](../releases/v0.1.0-20260929T074814Z/09-regression-fixes.md)。

## TM-001 最终候选门禁准备（首次运行前记录）

同一候选的本机门禁程序已接入：`scripts/local_gate.py`顺序调用完整精细主批次、11条辅助固定检查、独立证据审计和六组补充E2E，再从原始证据推导`final-product-result.json`中的78条父TC与38条变体最终状态，导出并核对同批次独立Excel。主批次的11条辅助占位仍保留原始BLOCKED；只有对应辅助原件真实PASS、全部其他结果PASS，且候选、DMG、原件与归档摘要一致时，机器才可生成正式通行证。`scripts/local_release.py`还会从原件复核最终结果与归档副本。治理负测覆盖缺失或篡改证据、伪造占位映射及错误的主runner退出码。当前这套程序尚未在**干净、已提交的最终候选DMG**上完成正式执行，因此TM-001仍未发布、无通行证；旧开发包联合复核不能移作本轮正式PASS。

准备阶段实测：固定Playwright注册核对`.local/ci/final-registration-20261001T0526Z.json`为95/95 PASS，仅证明入口存在；Electron桌面单元25/25、服务端55项、桌面构建均通过；本机视觉辅助批次`.local/ci/hig-visual-c759e9f93b2f40cf9f72a40d438ca3f2/visual-checks.json`记录10张界面图与12项布局/键盘检查，清理记录为true。这些不是最终包E2E。完整治理、文档检查和总表回读结果在[本版执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)登记。SOP-014修订23、SOP-018修订12已明确主run辅助占位与最终结果复算合同；当前合并树的完整治理及最终候选产品门禁仍待实跑和原始收据。

## 本轮修复执行中（2026-10-01）

用户要求全部已开发功能的必测用例通过。已按[修复计划](../releases/v0.1.0-20260929T074814Z/09-regression-fixes.md)完成六项产品修复及固定测试观察器；基础检查为394治理、55服务、25桌面单元通过。新开发DMG原件在`.local/ci/electron-package-fixes-20261001T0114Z/`，它仍是未发布开发包。

本包首个完整精细回归`local-571dd63bfe5b4d90a95ed9c70d80de07`已结束为**FAIL**，清理完成、发布资格为否。原始116条结果为104 PASS/1 FAIL/11 BLOCKED；11条BLOCKED是尚未执行独立辅助程序的占位。按父TC与参数变体分别统计，独立审阅表记录78父TC为66 PASS/1 FAIL/11 BLOCKED、38变体全部PASS；独立证据审计为PASS，但不改变SESSION-09的原始FAIL或辅助占位。原件在`.local/ci/local-571dd63bfe5b4d90a95ed9c70d80de07/result.json`；逐步证据Excel在`.local/test-results/local-571dd63bfe5b4d90a95ed9c70d80de07-reviewed/TokenMeter测试结果-local-571dd63bfe5b4d90a95ed9c70d80de07.xlsx`，其导出/回读PASS只证明表格一致，`product_state=FAIL`。

SESSION-09的确定性失败来自测试脚本在退出待确认时点击了已被正确禁用的“恢复默认”按钮，30秒后超时。既定用例要求该操作锁定；CONFIG-06也要求待退出时总恢复禁用。保留原失败，修正固定脚本为明确断言按钮禁用，同时继续检查API不可编辑、配置不变、无新服务请求和真实撤销。新单例`local-4a8815e9d61e4b4bbdd41f7a2f897c52`四步全部PASS、清理完成，独立Excel在`.local/test-results/local-4a8815e9d61e4b4bbdd41f7a2f897c52-reviewed/TokenMeter测试结果-local-4a8815e9d61e4b4bbdd41f7a2f897c52.xlsx`；它不覆盖首个完整回归FAIL。

修订测试代码后的第二次完整精细回归`local-f47f8257607c48458cc52b886d281d70`已结束为**FAIL**，`cleanup_completed=false`、`release_eligible=false`。原始116条结果为103 PASS/1 FAIL/12 BLOCKED；其中UPDATE-08因前例资源未清理而安全阻断，另11条仍是独立辅助程序占位。审阅模型为78父TC 65 PASS/1 FAIL/12 BLOCKED、38变体全部PASS。UPDATE-07的五步Playwright真实升级及身份/配置断言均PASS，但其owned ShipIt/私有资源清理失败，所以父TC必须保持FAIL。独立审计`.local/ci/local-f47f8257607c48458cc52b886d281d70-audit/audit.json`为PASS；原始报告`.local/ci/local-f47f8257607c48458cc52b886d281d70/result.json`和逐步Excel`.local/test-results/local-f47f8257607c48458cc52b886d281d70-reviewed/TokenMeter测试结果-local-f47f8257607c48458cc52b886d281d70.xlsx`均保留，Excel回读PASS、产品结论FAIL。

清理诊断指向本轮创建的空ByHost偏好文件：`defaults -currentHost read`报告该域不存在，当前清理合同因此未完成。修复程序仍在进行，不能把Playwright五步PASS或审计PASS写成UPDATE-07通过；**在核实资源归属并完成安全清理前不再启动GUI测试**。随后须新run验证清理，再执行完整精细回归、11辅助用例、六组补充场景、审计与同批次Excel。此前定向`local-2b3be14c180e463eb884d50c55ff1ada`为14父TC 12 PASS/2 FAIL、16变体PASS；后续`local-87321b477c044b5fa39a2bfa9bcda9a1`两条修正用例及审计PASS。各批原件保留，不能合并局部PASS冒充全量通过。

首次针对“域不存在”的清理代码修正通过固定治理检查（`.local/ci/shipit-absent-domain-governance-20261001T0445Z/receipt.json`），但新定点`local-c8e31657d5e4428584a6f316936113e1`仍为**FAIL**、`cleanup_completed=false`：UPDATE-07的五步Playwright均PASS，ShipIt/私有目录清理仍失败；UPDATE-08因前例残留而BLOCKED。本次原始报告为`.local/ci/local-c8e31657d5e4428584a6f316936113e1/result.json`，独立Excel在`.local/test-results/local-c8e31657d5e4428584a6f316936113e1-reviewed/TokenMeter测试结果-local-c8e31657d5e4428584a6f316936113e1.xlsx`，回读PASS但`product_state=FAIL`。失败后的归属预检`.local/ci/local-c8e31657d5e4428584a6f316936113e1-cleanup-followup-01/pre-cleanup.json`记录本轮私有根、ShipIt缓存和空偏好文件的owner核对；这不是清理完成证明。该批次怀疑即时升级后的ShipIt异步收尾存在时间差，因此先核对归属并安全清理，再实施有界稳定等待与诊断。

后续UPDATE-07/08定向`local-70e531d3092c4cbea30160117c379287`因误用系统Python、缺少`alembic`，两例均**BLOCKED**，`cleanup_completed=true`；审计PASS及独立Excel回读PASS只证明原件和表格一致，`product_state=BLOCKED`。改用项目venv的全新定向`local-b6627e4379c64386bfc1a535fb432c16`两例原始结果均**PASS**，本轮ShipIt及私有资源清理为true，`cleanup_completed=true`；独立审计和结果Excel回读均PASS，`product_state=PASS`。两次原始报告分别在对应`.local/ci/<run_id>/result.json`，Excel分别在`.local/test-results/<run_id>-reviewed/TokenMeter测试结果-<run_id>.xlsx`。定向PASS不覆盖此前全量FAIL。

同一未发布开发包的新完整精细回归`local-534748ff47cb44229183a6bd878c1674`已落盘：原始`state=BLOCKED`，116条结果为105 PASS/0 FAIL/11 BLOCKED，11条均为需由独立辅助程序执行的占位；95个实际Playwright入口全部PASS，另外10条父TC由变体结果推导，`cleanup_completed=true`。原件为`.local/ci/local-534748ff47cb44229183a6bd878c1674/result.json`。随后独立辅助批次`aux-818fe55e1e8940e4a3196b9d03b76563`的11条固定检查全部PASS、清理完成，原件在`.local/ci/aux-818fe55e1e8940e4a3196b9d03b76563/result.json`；六组补充产品E2E批次`local-5197628d58ac4136b004b87da438220c`为6/6 PASS、清理完成，原件在`.local/ci/local-5197628d58ac4136b004b87da438220c/result.json`，独立结果Excel在`.local/test-results/local-5197628d58ac4136b004b87da438220c/TokenMeter测试结果-local-5197628d58ac4136b004b87da438220c.xlsx`。三份原始结论各自保留，不把辅助或聚合场景回填成主run原始PASS。

独立证据审计v1原件`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit/audit.json`保持**BLOCKED**：当时唯一`PASSWORD-05`的peer fixture源码与已审阅绑定不一致。重新核对固定绑定后的审计v2原件`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit-v2/audit.json`为12/12 PASS，未修改v1或主run原始状态。

联合逐例复核表`.local/test-results/local-534748ff47cb44229183a6bd878c1674-reviewed/TokenMeter测试结果-local-534748ff47cb44229183a6bd878c1674.xlsx`及同目录`verification.json`已导出、回读PASS；它绑定主run、11条辅助、审计v2和六组补充原件，模型中78条父TC、38条变体、11条辅助与六组场景均PASS。`verification.json`仍明确`product_state=BLOCKED`，对应主run保留的11条辅助占位，表格归档PASS不改写该原始状态。当前证据说明开发包的联合逐例复核通过；干净正式包与发布门禁尚未通过，无通行证或正式发布。

## 修复前完整回归结论（2026-10-01，原件保留）

`v0.1.0-20260929T074814Z`仍未发布，无正式通行证。dev07六个聚合场景组的历史原件为五组PASS、004升级FAIL，汇总缺升级资产；不能证明精细TC通过。首轮精细全量`local-7feea03dd72e4eddba0651cede8fd23d`为BLOCKED（109条预期、16条PASS、93条BLOCKED），原件和独立Excel均保留。新全量`local-343e54113b0b442383e80f137013014b`已结束为**FAIL**，`release_eligible=false`、`cleanup_completed=true`。其原始`result.json`在`.local/ci/local-343e54113b0b442383e80f137013014b/`，记录78条父TC为57 PASS/8 FAIL/13 BLOCKED，38条变体为31 PASS/7 FAIL。另运行11条辅助固定检查得10 PASS/1 FAIL；独立证据审计把五条原始PASS降为BLOCKED。合并后的结果模型为78条父TC **62 PASS/9 FAIL/7 BLOCKED**，38条变体**31 PASS/7 FAIL**。这些是按原件与审计调整后的结论，不能改写主run原始计数。

当前执行链为：**需求→功能点→具体TASK→逐项TC/变体、输入、动作、预期、DB操作→基线→固定代码实现→逐TC执行和记录**。本轮`tests/test_cases.json`有78条TM-001父TC（67产品、11辅助），均已具固定程序；另31条为后续功能规划。`tests/granular_login_variants.json`登记25条认证参数变体，`tests/granular_update_variants.json`登记13条UPDATE-05负例变体，合计38条；首轮BLOCKED批次仍以当时31条变体的代码快照解释。证书差异和DR差异已通过固定组件身份层检查，但新全量真实App测试在最终临时目录清理断言失败，不能记为产品PASS。原有六条待定产品预期已按用户决定细化；补充文档不追认为先于历史代码存在。

测试必须由仓库中固定、按TC编号可重复执行的程序完成；Codex只调用程序并分析原始结果，不以临时手工操作、截图目测或手填表格判PASS。独立入口为`scripts/run_test_case.py --case-id <TC-ID>`，完整集合使用`--all`，均需显式`--package-manifest <本轮包清单>`；开发包另加`--development`。命令会创建新run_id和隔离目录，输入、动作、断言及判定来自版本化代码。`scripts/granular_e2e.py`保存逐步事件、Playwright原件、SQL/DB旁证、trace和截图；父TC由其全部声明变体的实际结果推导。任何FAIL/BLOCKED、缺步骤或清理失败继续阻断发布。

覆盖缺口也由固定代码留下`coverage-blocked.json`，机器在用例其他断言通过时将其判为BLOCKED：CONFIG-01/05尚缺默认服务启动前的网络观察，CONFIG-06尚缺验证和原生安装阶段忙态观察，UPDATE-04尚缺零原生交接观察。若用例已有确定性断言失败，保留FAIL优先；这四项不能凭现有局部断言放行。

独立审计原件`.local/ci/local-343e54113b0b442383e80f137013014b-audit/audit.json`还将CONFIG-02/03/04、UPDATE-01/07的原始PASS降为BLOCKED，原因包括逐值保存回读、新进程`/me`、安装确认前外连/交接，以及未经筛选的`lsof`证据缺失。辅助原件`.local/ci/aux-local-343e54113b0b442383e80f137013014b-01/result.json`为10 PASS/1 FAIL；UI-01的测试脚本颜色`#fff`解析已修，新单例`aux-ui01-local-343e54113b0b442383e80f137013014b-02`真实PASS，独立Excel另存，不改旧FAIL或主审阅表。定向复测`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed/result.json`有16条结果行（3父TC加13变体），其中15个Playwright执行入口；机器结果10 PASS/6 FAIL、清理完成。PASSWORD-05第二App前置与ADMIN-03收尾脚本缺陷修复后分别真实PASS；UPDATE-05父TC及五条Info/代码身份变体仍FAIL。`cleanup-observation.json`对INFO_VERSION/INFO_BUILD约20秒采样仍见临时目录残留，属于待修产品清理问题。定向结果不替换完整回归原件。

目标新审计`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed-audit-peer-v3/audit.json`为PASS，独立核对PASSWORD-05第二App peer及两个旧会话401、ADMIN-03四步证据；目标审阅表`.local/test-results/local-877830fb340a4d12b4e29cf76fa422ed-reviewed/TokenMeter测试结果-local-877830fb340a4d12b4e29cf76fa422ed.xlsx`已回读PASS、产品FAIL，3父TC为2 PASS/1 FAIL，13变体8 PASS/5 FAIL。它确认两条脚本缺陷的定向修复，不改变UPDATE-05产品清理失败或主全量FAIL。

用户统一查看入口为仓库根[TokenMeter项目总表.xlsx](../TokenMeter项目总表.xlsx)，按明确指令随Git版本提交。当前主表已重新导出为11个Sheet、109条用例摘要及12次测试批次；`.local/workbook/verification.json`登记SHA-256 `ef94e5e15c1c6c0b4fe4a0ae8d550728c54ad502e317262b7dc02ffba41c8ae3`，`python3 scripts/verify_project_workbook.py`对当前文件回读PASS、零错误，`product_tests_executed=false`。`05测试用例`汇总功能、输入、预期、DB操作、类型及状态；`06测试批次`只汇总12次运行及各自独立结果Excel入口，逐步实际结果仍在独立表。主run原始BLOCKED与联合复核表`.local/test-results/local-534748ff47cb44229183a6bd878c1674-reviewed/TokenMeter测试结果-local-534748ff47cb44229183a6bd878c1674.xlsx`的78父TC、38变体全PASS分别记录，主表回读不授予正式发布资格。完整设计保存在[用例JSON](../tests/test_cases.json)和[详细用例文档](testing/cases/README.md)，不因主表展示范围缩减而删除真实用例或执行证据。腾讯在线方案未写入，已取消。仓库导航：[全部用例索引](../TEST_CASES.md)、[本版全流程](../releases/v0.1.0-20260929T074814Z/README.md)。

每次实际测试单独输出`TokenMeter测试结果-<run_id>.xlsx`并留在本机。新版全量审阅表已生成于`.local/test-results/local-343e54113b0b442383e80f137013014b-reviewed/TokenMeter测试结果-local-343e54113b0b442383e80f137013014b.xlsx`；同目录`verification.json`为Excel回读PASS、`product_state=FAIL`，记录78父TC 62/9/7与38变体31/7/0。UI-01新单例表另存于`.local/test-results/aux-ui01-local-343e54113b0b442383e80f137013014b-02-reviewed/TokenMeter测试结果-aux-ui01-local-343e54113b0b442383e80f137013014b-02.xlsx`，本次仅1例PASS。导出PASS不授予产品通过，也不改主审阅表。首轮BLOCKED和dev07历史批次各有独立结果Excel；详见[07结果](../releases/v0.1.0-20260929T074814Z/07-test-results.md)。

`scripts/local_e2e.py`已接入结果自动导出，原JSON保持不变，导出失败返回非零；相关runner工具11项、桥接18项检查通过。补导历史运行不构成新的App测试；若导出失败可保留原收据，在全新目录补导，无需重跑产品。候选测试期间只写本地忽略目录，待执行和门禁结束后再更新Git跟踪的主表和摘要，保留原被测SHA。

## 保留的dev07开发运行

- 原件：`.local/ci/e2e-dev-probe-07/`；run_id=`local-a1b2c3d4e5f60718293a4b5c6d7e8f94`，2026-09-30 11:22:02–11:24:17 UTC。
- 包：`.local/ci/electron-package-probe-06/package-manifest.json`，DMG摘要`09f0854cefc7584e1cc77e911d92cf1024a826d407e24241bb38cef11d35a529`。`scope=development`，`working_tree_dirty=true`，不能当作已锁定的正式候选。
- 可见副本：[根dmg目录](../dmg/README.md)下`v0.1.0-20260929T074814Z/TokenMeter-v0.1.0-20260929T074814Z-DEVELOPMENT-NOT-RELEASED.dmg`，与开发原件SHA-256相同。正式DMG尚未生成；今后构建的开发/候选包标记未发布，门禁PASS后才在同版本目录放正式原名包。
- 001/002/003/005/006的原始Playwright结果通过；004观察到自主新PID和runtime绑定，但`new_process_profile_files`期望true、实测false。即时lsof没有证明新进程正使用隔离profile文件，完整升级/恢复断言未完成。
- 原汇总为FAIL，六次尝试只写入前五个suite，并报`Evidence is absent or outside the owned output`；升级结果/进程资产缺失，原`cleanup_completed=false`。
- 后续`E2E-TM001-004/cleanup-followup.json`独立记录仅本轮资源的清理及隔离安装中观察到build101。它不修改原FAIL、不补造缺失报告，也不证明后续身份恢复成功。

详细候选、摘要、逐组结果及证据范围见[07测试结果](../releases/v0.1.0-20260929T074814Z/07-test-results.md)；未发布条件见[08发布记录](../releases/v0.1.0-20260929T074814Z/08-release-record.md)。

## 已建立与尚缺

已建立Electron/React/TypeScript客户端、FastAPI/SQLite、SQL造数、electron-builder本机签名DMG、Playwright场景组、原件校验门禁及本地归档程序。构建、组件、治理与HIG辅助检查的既有结果记录在[06执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)；这些结果不是完整产品验收。

新增[01a登录/改密](testing/cases/01a-TM-001-login-scenarios.md)、[01b会话/管理/配置/更新](testing/cases/01b-TM-001-session-admin-release-scenarios.md)、[01c交付检查](testing/cases/01c-TM-001-delivery-checks.md)用于补齐任务级用例。67条产品父TC、38条参数/负例变体及11条辅助TC已有固定程序；完整结果按主raw、辅助和审计原件联合判定。本轮首次新包运行的父TC为66 PASS/1 FAIL/11辅助占位BLOCKED；第二次为65 PASS/1 FAIL/12 BLOCKED，38变体两批均PASS。新完整精细原件105 PASS/0 FAIL/11辅助占位BLOCKED；辅助11/11、六组6/6及审计v2的12/12另有独立PASS原件，联合逐例复核为78父TC与38变体全PASS。原主run仍BLOCKED，干净包门禁与通行证未完成。TM-002–012继续planned，不因TM-001已有程序进入实现。

此前`python3 scripts/check_docs.py --mode structure`返回PASS：102份登记文档、890条链接，101份baselined、1份superseded；这只证明当时结构和引用检查。基础收据还记录严格基线、质量、治理、服务和桌面单元结果，均不能替代逐TC产品E2E。当前开发包的联合逐例复核已完成；仍须以最终干净候选重新核对包与测试证据并执行正式发布门禁，三批原始运行不得改写。

下一步依次为：锁定干净候选并执行最终DMG安装/升级及发布门禁→仅在门禁PASS后签发通行证与正式发行。若任一必要项FAIL/BLOCKED，保留原件按SOP-015定位，不能提前本地正式发布。

## 当前运行边界

- 默认本机完成开发、测试、打包和发布，当前实测范围macOS15.7.4 Intel；其他架构/系统未验证，无需完整Xcode。Actions完整测试仅在用户明确要求多环境时运行。
- 默认API `http://127.0.0.1:49176`、更新清单 `http://127.0.0.1:49177/version.json`；测试另用拥有的动态回环服务和独立profile，不对默认生产服务登录或造数。
- 用户已有App、49176服务与`database/production/production.db`不参与回归。生产首建约定admin/123456并强制改密；回归用`database/test/test.db`或逐例私有合成库，见[数据库说明](../database/README.md)。
- DMG、更新包、原始报告和通行证只保存在本机。Git保留源码、文档、PR与版本追踪，不创建GitHub Release安装包资产。无正式门禁PASS时不分发开发包、不更新稳定源、不创建正式Tag。

## 保留的历史事实

[CI36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502)在macOS15.7.9 Apple Silicon/Intel分别完成旧SwiftUI/XCUITest六例与父门禁PASS；[PR#2](https://github.com/lzhe72/TokenMeter/pull/2)已合并master至`e011857443b503c2bfafcb9cd1c9e6d52f5ff5f2`。该历史源码树为`2b723f41d96256e962cf04ed9105dfb1e2985739`，不代表当前Electron候选、最终DMG或精细TC已验证。

此前受保护CI、双架构内部发行和Sparkle appcast是迁移前方案；现由用户确认的本机Electron流程取代。历史公网DNS、Keychain、签名及原始结果问题，以及开发包失败、用例总表和DMG入口问题，保存在06和[两日31例复盘](retrospectives/2026-09-29--2026-09-30-tokenmeter.md)，不改写旧失败。接手先读[SOP总索引](../sop/README.md)。
