# v0.1.0-20260929T074814Z — 全量回归缺陷修复计划

## 目标与输入

用户2026-10-01要求全部已开发功能的必测用例通过。当前版本尚未正式发布，继续同一版本候选，不生成新发布编号。本计划沿用原需求与验收标准，不删除用例、不把FAIL/BLOCKED改为预期成功。

输入：[需求](01-requirements.md)、[具体任务](02-breakdown.md)、[开发计划](03-development-plan.md)、[测试计划](04-test-plan.md)、[原始结果索引](07-test-results.md)、[用例集合](../../TEST_CASES.md)。按SOP-015保存失败基线，SOP-008检查本计划，SOP-011/012实现固定回归与修复，SOP-013/014构建并执行完整回归，SOP-022归档。

完整基线为`local-343e54113b0b442383e80f137013014b`及其辅助、独立审计；78父用例62 PASS/9 FAIL/7 BLOCKED。原始结果保留。PASSWORD05、ADMIN03、UI01的测试程序问题已在后续独立批次修复验证，仍纳入本轮完整回归。

## 缺陷、任务与固定验收

各行沿用该TC在`tests/test_cases.json`中的TASK/AC关系；BUG编号用于本轮定位，不替换原稳定ID。

| BUG | 原用例 | 实际差距 | 修复与必须保留的验收 |
| --- | --- | --- | --- |
| BUG-TM001-001 | SESSION-04 | 自动登录连接失败后没有真实UI重试入口 | 显示可重试入口，点击后发起新的真实/me；15秒超时、不沿用缓存身份、迟到响应规则不变 |
| BUG-TM001-002 | SESSION-10 | 异常凭据被拒绝，但没有明确重新登录提示 | 保持拒读、归属检查和哨兵不变；提示重新登录，不擅自改文件权限 |
| BUG-TM001-003 | ADMIN-02 | 空/短密码仅禁用按钮，没有明确校验错误 | 显示可见错误，不能发送成功重置、改数据库或新增成功审计；合法重置仍有效 |
| BUG-TM001-004 | CONFIG-05 | 恢复默认把旧默认值写成用户覆盖 | 原子删除server/feed覆盖键，保留自动登录偏好；重启从本版内置值读取 |
| BUG-TM001-005 | CONFIG-06 | 登录后总恢复按钮没有锁定 | UI和主进程共同限制登录/待退出/忙态恢复；更新下载、验证及安装期间不能改源 |
| BUG-TM001-006 | UPDATE-05 | 五个身份校验拒绝路径残留临时目录 | 定位真实删除错误，确认本次临时目录清理后才发布终态/退出；不扩大删除范围，不放宽签名/身份断言 |
| BUG-TM001-007 | CONFIG-01/05 | 缺少启动及恢复默认窗口的默认服务零请求证据 | 固定观察器在业务执行前开始，记录真实网络调用，证明未向用户默认服务认证/写入；不得请求或占用默认端口 |
| BUG-TM001-008 | CONFIG-02 | 合法API地址逐值保存回读不足 | 每个预定输入分别核对UI与settings.json；非法输入逐项不落盘/不发请求 |
| BUG-TM001-009 | CONFIG-03 | 改密完成同步及重启后B服务身份确认不足 | 等待实际新凭据和改密完成，再以请求时间、origin、凭据摘要核对重启后新的非probe /me 200 |
| BUG-TM001-010 | CONFIG-04 | 合法更新地址逐值保存回读不足 | 每个合法值保存及重启回读；非法值拒绝、不替换公钥、不落盘 |
| BUG-TM001-011 | UPDATE-01/04 | 缺安装确认前、坏签名拒绝后的原生交接观察 | 固定观察真实autoUpdater方法调用与真实网络活动；未确认/校验失败时交接次数为0 |
| BUG-TM001-012 | UPDATE-07 | 先筛选路径再判断无用户目录，证据不完整 | 保存新进程完整lsof文件列表，再检查隔离profile使用及无标准用户profile |
| BUG-TM001-013 | E2E-TM001-003 | 管理员补充E2E只对撤销后会话留下`/v1/me` 401，门禁缺有效身份的200旁证 | 固定脚本在管理操作前重启真实App，核对自动恢复后的管理员身份与角色，再用保存的令牌核对真实`/v1/me` 200及账号；保留旧401断言和门禁强校验 |
| BUG-TM001-014 | E2E-TM001-004 | `lsof -Fn`偶发无名称`n`行，测试采集器把它记成空路径，门禁拒绝完整打开文件列表 | 两处固定采集器仅忽略无名称记录，保留全部具名文件；解析单测覆盖空名称、其他路径和含空格路径，004的原profile/无默认profile断言不变 |

## 修复设计与文件边界

1. 账号/设置实现：`accounts.ts`、`storage.ts`、renderer、共享Snapshot/preload及基础测试。离线恢复复用真实refresh；错误提示来自真实失败；settings稀疏保存覆盖，主进程和UI共同锁定。根整合`main/index.ts`快照字段。
2. 更新实现：`updater.ts`及其基础测试；先复现解包后的真实清理问题，再修复本次目录的删除和终态顺序。更新失败保留当前App，成功仍交真实Squirrel安装并自主重启。
3. 配置测试：`granular-config.spec.ts`与独立审计规则。逐值UI/文件回读，重启前后真实服务请求分段，固定DOM观察记录下载/验证/ready/安装阶段的锁态。
4. 更新测试：`granular-update.spec.ts`及`granular-update-validation.spec.ts`；完整lsof、网络和原生交接观察，不注入成功响应、不手动启动高版本替代更新。
5. 共享执行器：根维护`granular_e2e.py`、`local_e2e.py`、账号E2E及独立观察器。CONFIG06获得本次owned ShipIt、CDP端口和可释放的真实下载fixture。其余agent不得并行修改共享文件或运行GUI。

## 独立观察器合同

- 观察代码固化在测试目录并冻结SHA。安装包内容不改动，通过独占Node inspector端口在业务首个语句前暂停，先安装观察器再恢复；Playwright继续驱动真实安装App。
- 记录网络请求及原生更新器调用，全部委托原函数、原参数、原返回值，不替换业务响应、不改变认证状态。观察覆盖不足或启动时间无法证明时仍BLOCKED。
- 原件包含run_id、TC、PID、启动/安装观察器时间、方法、目标origin和路径、交接方法，不记录密码、token、请求正文。只写本次0700证据目录。
- 使用真实owned服务的正控制证明观察器能看到请求；原生交接观察同有效升级的实际调用旁证核对。系统全接口计数和间歇lsof不能单独证明零短连接。
- CONFIG06只释放测试源已挂起的原始ZIP传输，不替换App状态。升级后只连接自主启动的新进程。

## 验证顺序与完成条件

1. 保留已有六项产品FAIL及七项证据BLOCKED；新增观察器先以固定组件测试验证记录/委托/缺失阻断，不把组件检查称为产品E2E。
2. 完成本次代码后运行文档基线、治理、服务端、桌面单元与类型/构建检查；必要局部探针使用新run，保留每次失败，不无理由重复全量。
3. 从新候选重新构建DMG与真实受控升级ZIP；旧包不能验证新产品修复。先针对修复点验证，再冻结所有测试程序执行完整产品与辅助集合。
4. 本轮完整集合仍为78个TM-001父用例（67产品、11辅助）、38个已声明参数变体，另保留六组补充回归。后续功能31个规划场景没有开发，不伪造已测试。
5. 任意FAIL/BLOCKED、漏例、跳过、零例、重试取绿、无有效断言、证据与源码/包不一致均不算完成。父用例与参数变体分别统计，不相加冒充实际执行次数。
6. 原始报告、独立审计和每次结果Excel另存；总表只更新批次索引和最近证据归属。所有必测代码通过后才能报告目标完成；正式发布仍另需最终候选门禁。

当前是修复计划，尚未获得本轮新包全量PASS。实际根因、命令、退出码及报告在[执行记录](06-iteration-record.md)和[实际结果](07-test-results.md)追加。

## 本轮实施进度（2026-10-01，产品证据复核中）

原完整批次和定向批次的FAIL/BLOCKED仍是历史事实；以下记录代码与固定测试程序的修订，不将基础检查或新包构建写成产品验收通过。

| 范围 | 已确认根因与落地修复 |
| --- | --- |
| BUG-TM001-001/002 | 自动恢复失败后快照缺少可重试状态，凭据拒读错误缺少明确的重新登录指引。现由主进程快照给出真实重试入口，重试重新请求 `/v1/me`；异常凭据继续拒读并提示重新登录，服务地址变化时清除旧内存token。SESSION-10增加自建HFS+镜像的非当前UID合成凭据固定程序：只改镜像中目标文件的UID字段，核对镜像前后摘要、真实`stat.uid`和挂载归属，执行后卸载；不修改用户凭据或系统文件。 |
| BUG-TM001-003/004/005 | 管理员空/短临时密码原先只有禁用按钮，现界面给出明确校验错误，主进程也拒绝非法重置；设置原先把内置默认地址固化成覆盖，现只保存非默认覆盖，恢复默认删除地址覆盖并保留自动登录偏好；总恢复原先在已登录状态仍可点击，现界面和主进程同时锁定登录、待退出及更新忙态。 |
| BUG-TM001-006 | 真实ZIP在普通Node递归删除成功，在Electron补丁版`fs`下，`app.asar`被当作虚拟目录，实际文件留在`Contents/Resources`，删除报`ENOTEMPTY`。诊断原件为`.local/ci/updater-cleanup-diagnostic-20261001T004930Z/`。清理改用Electron的`original-fs`，仅删除本次profile直属的`update-*`私有目录，并在终态/安装交接前验证目录不存在；失败仍阻断，原身份校验不放宽。 |
| BUG-TM001-007至012 | CONFIG逐值保存、重启回读、服务切换身份及忙态观察已写成固定Playwright动作与断言；真实网络/原生更新器观察器在业务入口前安装，调用仍委托原函数，记录本次run/PID和调用，不替换响应。UPDATE-07保存未过滤的`lsof`列表后再判断profile。观察器的负控制、组件测试与真实App结果分层记录；缺观察窗口仍阻断。 |

基础检查收据`.local/ci/fixes-basic-20261001T0125Z/receipt.json`：文档基线、质量追踪均退出0；治理388项、服务端55项、完整桌面单元25项通过。更新器定向7项单测、观察器4项单测和桌面/更新E2E TypeScript检查另见`.local/ci/updater-fix-static-20261001T010408Z/receipt.json`与`.local/ci/update-observer-freeze-20261001T012045Z/receipt.json`。这些检查均不是产品E2E。

新开发候选DMG已构建，包清单`.local/ci/electron-package-fixes-20261001T0114Z/package-manifest.json`记录macOS 15 Intel、内部签名、候选/更新App及各产物摘要，且`release_eligible=false`。新包完整精细、辅助和六组原始产品检查及联合逐例复核已结束，结论见下文；干净正式包、通行证和发布门禁仍未完成。

## 本轮完整回归及测试脚本修正（2026-10-01）

首个新包完整精细批次`local-571dd63bfe5b4d90a95ed9c70d80de07`已结束为FAIL，`cleanup_completed=true`、`release_eligible=false`。原始116行是104 PASS/1 FAIL/11 BLOCKED；11条BLOCKED是尚待独立执行的辅助用例占位。独立审计`.local/ci/local-571dd63bfe5b4d90a95ed9c70d80de07-audit/audit.json`为PASS，未提升原始FAIL；审阅模型中78父TC为66 PASS/1 FAIL/11 BLOCKED，38变体全部PASS。首批Excel及回读记录在`.local/test-results/local-571dd63bfe5b4d90a95ed9c70d80de07-reviewed/`；其产品结论仍是FAIL。

唯一确定性FAIL为`TC-TM001-SESSION-09`。原始Playwright证据显示测试脚本在退出待确认时点击`configuration.reset-defaults`，按钮已按CONFIG-06修复后的既定策略禁用，点击等待30秒后超时。SESSION-09步骤2和CONFIG-06步骤2都要求总恢复在待退出期间锁定；此处属于测试动作与既定合同冲突，并非要把产品按钮改成可点击。固定脚本已将错误点击和错误文案期待改为明确断言按钮禁用，仍保留API不可编辑、设置不变、无新origin/token请求、恢复服务后的真实撤销及旧token 401。原失败原件不修改。

定点新批次`local-4a8815e9d61e4b4bbdd41f7a2f897c52`只执行SESSION-09：四步真实App/服务检查全部PASS、清理完成；原件`.local/ci/local-4a8815e9d61e4b4bbdd41f7a2f897c52/result.json`，独立Excel在`.local/test-results/local-4a8815e9d61e4b4bbdd41f7a2f897c52-reviewed/`，回读PASS。定点成功不构成78父TC、38变体及辅助集合的完整验收。

修正SESSION-09脚本后的第二次完整精细批次`local-f47f8257607c48458cc52b886d281d70`已结束为FAIL，`cleanup_completed=false`。原始116行103 PASS/1 FAIL/12 BLOCKED；审阅模型78父TC 65 PASS/1 FAIL/12 BLOCKED、38变体全部PASS。UPDATE-07五步Playwright断言全部PASS，但owned ShipIt和本次私有目录清理失败，runner正确将该TC判为FAIL并阻断后续UPDATE-08；另11条仍是待独立执行的辅助占位。审计`.local/ci/local-f47f8257607c48458cc52b886d281d70-audit/audit.json`与独立Excel回读均PASS，只证明旁证和表格一致，不改变产品FAIL。原件`.local/ci/local-f47f8257607c48458cc52b886d281d70/result.json`与`.local/test-results/local-f47f8257607c48458cc52b886d281d70-reviewed/`均保留。

本轮新发现清理执行器缺陷：诊断指向已确认属于本run的空ByHost偏好文件；`defaults -currentHost read`显示该域不存在，当前清理流程据此未能完成owner状态确认。修正程序正在进行，尚无修正后GUI结果。核实资源归属并安全清理前，不启动下一次GUI；清理断言不得放宽。随后以新run验证、重新执行完整精细和辅助/六组回归，才能重新判断发布资格。

首次针对不存在ByHost域的代码修正已通过固定治理检查（`.local/ci/shipit-absent-domain-governance-20261001T0445Z/receipt.json`），但新定点`local-c8e31657d5e4428584a6f316936113e1`仍为FAIL、`cleanup_completed=false`：UPDATE-07的五步真实App/升级断言PASS，ShipIt/私有资源清理FAIL；UPDATE-08按安全规则BLOCKED。原始报告在`.local/ci/local-c8e31657d5e4428584a6f316936113e1/result.json`，独立Excel与回读在`.local/test-results/local-c8e31657d5e4428584a6f316936113e1-reviewed/`，`product_state=FAIL`。归属预检`.local/ci/local-c8e31657d5e4428584a6f316936113e1-cleanup-followup-01/pre-cleanup.json`只核对本次残留的owner，不证明已清理，也不改变原run。即时升级后的ShipIt异步收尾可能造成时间差，因此继续实现有界、核对owner的稳定等待与诊断；当时安全清理前暂停GUI测试。

随后新定点`local-70e531d3092c4cbea30160117c379287`因误用系统Python且缺`alembic`，UPDATE-07/08均BLOCKED，`cleanup_completed=true`。原始`.local/ci/local-70e531d3092c4cbea30160117c379287/result.json`不改写；独立审计PASS、结果Excel回读PASS但`product_state=BLOCKED`，见同ID的`-audit/audit.json`和`.local/test-results/<run_id>-reviewed/`。该批未验证产品行为。改用项目venv的新定点`local-b6627e4379c64386bfc1a535fb432c16`两例原始均PASS，逐例ShipIt和私有资源清理true、`cleanup_completed=true`；原始报告、同ID独立审计和Excel均留存，审计与回读PASS、`product_state=PASS`。定向结果仅说明UPDATE-07/08在该包与输入下通过，不追改先前完整FAIL，也不满足全部78父TC、38变体及辅助场景的发布门禁。

新的完整精细回归`local-534748ff47cb44229183a6bd878c1674`已结束，原始`.local/ci/local-534748ff47cb44229183a6bd878c1674/result.json`为**BLOCKED**、`cleanup_completed=true`：116条结果105 PASS/0 FAIL/11辅助占位BLOCKED；95个实际Playwright入口全部PASS，另10条父TC由变体推导PASS。11条占位没有在主runner执行步骤，不能改写该原始状态。独立辅助批次`aux-818fe55e1e8940e4a3196b9d03b76563`的11条固定检查均PASS、清理完成；六组补充E2E批次`local-5197628d58ac4136b004b87da438220c`为6/6 PASS、清理完成，含本机升级004。原件分别在`.local/ci/<run_id>/result.json`，六组独立Excel在`.local/test-results/local-5197628d58ac4136b004b87da438220c/TokenMeter测试结果-local-5197628d58ac4136b004b87da438220c.xlsx`，三批不互相覆盖。

主run独立证据审计v1`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit/audit.json`保留**BLOCKED**，当时唯一`PASSWORD-05`提示peer fixture源码与已审阅绑定不一致。重新核对固定绑定的审计v2`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit-v2/audit.json`为12/12 PASS。联合逐例复核Excel`.local/test-results/local-534748ff47cb44229183a6bd878c1674-reviewed/TokenMeter测试结果-local-534748ff47cb44229183a6bd878c1674.xlsx`和同目录`verification.json`导出/回读PASS，绑定辅助11/11及六组6/6原件后，78父TC、38变体均PASS。原主run的`state=BLOCKED`与`verification.json`的`product_state=BLOCKED`仍准确保留11条辅助占位的原始事实；复核表没有修改这些原件。目标的开发包联合逐例复核已通过，但该包`release_eligible=false`，仍须冻结干净候选、验证最终DMG并执行正式门禁；任一必需项失败或阻断仍保持本版未发布、无通行证。

根[项目总表](../../TokenMeter项目总表.xlsx)当前为11个Sheet、109条用例及12条批次索引；SOP基线合并后重新导出的SHA-256为`ef94e5e15c1c6c0b4fe4a0ae8d550728c54ad502e317262b7dc02ffba41c8ae3`，`.local/workbook/verification.json`与`python3 scripts/verify_project_workbook.py`回读同一文件为PASS。第12条是上述联合复核PASS索引，主raw的BLOCKED及正式门禁未过仍以各自原件为准。

## 最终候选门禁程序与待完成项（2026-10-01）

已将完整精细主runner、辅助11例、独立审计12项、六组补充E2E和逐例Excel接入同一候选门禁。机器从各自原始结果复算78条父TC及38条变体的最终状态，保留主报告11条辅助占位的原始BLOCKED；占位必须逐条映射至真实辅助PASS，不能以修改主报告或旧运行结果放行。归档程序再次核对结果与副本、候选SHA/tree和DMG摘要；缺失、篡改与伪造映射有固定负测。固定Playwright注册核对95/95通过，基础构建/单元/服务检查通过，均只证明程序准备就绪。

SOP-018修订12已明确精细集合及最终结果复算合同。本版下一步是完成整合树治理回归、冻结干净提交，并从其最终DMG执行**新的**完整门禁。正式run未生成前保持未发布、无通行证；即使文档、测试程序和开发包联合复核通过，也不能提前把结果标为正式产品PASS。最新证据与检查命令见[06执行记录](06-iteration-record.md)。

### 首次干净候选门禁失败与修正（2026-10-01）

干净候选`3467dc143b2e2fc71f51515f483f0ecff8637947`的门禁原件位于`.local/gates/tm001-final-gate-3467dc1-20261001T0730Z/`，最终`gate.json`为**FAIL**、错误`No actual identity verification`，没有通行证。精细主批次95个实际Playwright入口全部PASS，辅助11/11、独立审计12/12、补充六组6/6分别PASS；主批次11个辅助占位仍保留原始BLOCKED，结果Excel已导出并回读PASS。这些分项不能替代最终门禁。

补充用例`E2E-TM001-003`虽完成管理员UI操作，原脚本只对被重置或停用的成员旧令牌请求`/v1/me`，均按预期返回401，未在管理员有效会话上留下200证据。按`BUG-TM001-013`补充真实App重启和身份恢复，并用保存的令牌核对真实服务的账号、角色。继续只读核验还发现004的`lsof`文件列表有空名称，按`BUG-TM001-014`修正固定采集器并增加解析单测。门禁条件不放宽，原始FAIL不改写。此变更需要新提交、新DMG与完整回归，当前仍无发布资格。
