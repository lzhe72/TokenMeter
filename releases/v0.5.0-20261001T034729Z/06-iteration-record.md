# TM-005 执行记录

## 2026-10-02 · IANA与双来源SQLite辅助输入

总控和TM-005开发会话要求在继续产品链路前先固定下一独立TASK/TC切片。文档会话按SOP-002–008、024增加`TC-TM005-CORE-04/05`：CORE04以固定上海/UTC/纽约春秋IANA当地日及无效输入验证UTC半开界、23/25小时和严格错误；CORE05使用TM-003已提交`UsageStore`接口只在本例隔离SQLite种入合成Codex/Claude事件，验证当前主体/半开UTC界、同一读事务中来源/模型/明细/日点一致，WAL另一连接提交前后旧快照330/新快照385。实际TM-003`coverage`表只有`missing_before/scan_incomplete/last_scan_at_utc`等字段，无法证明任意完整空日；该产品判据及原32父TC/6变体保留draft/BLOCKED。两条辅助TC程序绑定null、实际未运行，不使用原生日志或安装App。输入见03/03a/04/04a、两份新fixture、manifest与机器用例；干净输入提交及SOP-008收据待随后记录。

编制检查`check_docs.py --mode structure`退出0（134份登记文档、1254链接）、用例目录232例/739步生成并回读、根Excel11 Sheet/232父+42变体/274行/18批次回读PASS，SHA-256 `20c539a9ab8137ce4022f4e0bd2fb8b0d60ebd09c5929ab1cf4391a3cef0bc94`。首次生成目录因新增说明把`E2E-TM005-001/002`来源标题各后移2行而FAIL，已将机器来源行由21/38更正为23/40并在新运行PASS；不改产品预期或旧结果。以上只是文档/总表一致性，不是模块或产品PASS。

## 2026-10-02 · CORE-01 UTC界输入纠错

开发会话指出已提交纯统计实现由调用方直接传`start_utc/end_exclusive_utc`，原CORE-01“按当地日调用”措辞可能误导为同函数负责IANA换算。核对冻结fixture同时给出`timezone/local_day`与UTC界后，文档会话明确CORE-01只按固定UTC半开界筛选、输入主体及事件；`Asia/Shanghai`当地日到UTC、纽约春秋23/25小时日界另设固定辅助TC，不把现有模块3/3当日期转换PASS。原32条产品TC/6变体及RANGE-11真实App判据不变；03a、04a、机器目录和总表随本纠错重新核对，旧SOP-008切片收据只对应此前文本，新内容需新的切片收据。

文档干净提交`e96ff005b69b99aafb7acc471f49b8171411e171`已纳入这项澄清；本地`.local/docs-checks/20261002-document-realtime-sync/`对该树运行structure、当前0.2 baseline、quality、治理477/477、用例225/712、总表15批次回读和diff检查均退出0。针对CORE三例的独立SOP-008切片复核另见`.local/docs-checks/20261002-tm005-core-slice-utc-corrected/receipt.json`；只确认固定UTC界纯统计部分，整版0.5仍draft，IANA换算和产品E2E未运行。

代码会话随后提交`69d2ccff5dd65d5dd07c11dca6c2f14e79b5953a`（tree`7513406143b056ba4d1dfc9cb9fb01d39c2631c9`）的结构化CORE步骤证据；原始`.local/tm005-core-structured-20261001T171140Z/summary.json`和`core.txt`报告三例每例三步、`memory_only`清理事实、桌面29/29及build退出0，产品E2E执行0。该候选尚无支持`memory_only`的共享runner合并与新run独立Excel，模块Excel和总表批次登记保持BLOCKED；不把内存重置写成目录删除。

## 2026-10-02 · 固定模块程序原件交接

TM-005开发工作树干净提交`6a0f6f44096b04052ce5a0d1d4ff8939a421abd1`、tree`a7f9c40036df81f98c2cf247eb03df25833b5531`中，`apps/desktop/tests/tm005-core.test.ts`按`TC-TM005-CORE-01/02/03`各有固定Node入口。原始`.local/tm005-core-postcommit-20261001T162401Z/{summary.json,core.txt,desktop_tests.txt,build.txt}`显示fixture摘要与文档冻结值一致、CORE3/3逐步PASS、桌面29/29和build退出0；此前预期红测3/3失败原件在`.local/tm005-core-red-20261002/`，未被绿测覆盖。代码尚未进入本文档工作树，机器binding保持null；原32条产品TC/6变体、双来源真实SQLite/IPC/App及产品E2E仍未执行。按SOP会话新提交`4cca918`，模块独立结果Excel须用固定`source_check`导出器从原始逐TC字段生成；现行产品导出器不适用，模块Excel和总表批次登记BLOCKED，正式发行NOT_RUN。模块结果可作为后续独立切片的实现证据，不能写为整版0.5或产品PASS。

## 2026-10-02 · SOP-008 纯统计独立切片就绪

对固定输入提交 `061c759a9dbe52e15a5fb06ca1b1451a61e65c55`（tree `44b201503b85f480d8d5d2e9ae3a031aa5002487`）逐项核对 `TC-TM005-CORE-01/02/03`：CORE-01 的A/B筛选、半开时界、主体隔离、330总数与非法值拒绝；CORE-02 的已知330、未知诊断后partial、仅诊断时unknown且总数为null；CORE-03 的complete/missing/partial/unknown声明式代数。三例均有固定合成输入、顺序步骤与逐步独立预期、无需产品DB的验证和重置方式。`TASK-TM005-EVENT-CONTRACT/RANGE-QUERY/COVERAGE` 的纯函数部分可独立实现；TM-003/004 原生日志、来源身份、授权、真实覆盖事实、SQLite、IPC和App均在此切片之外，相关未决决定不改变本切片已固定的合成输入预期。若上游合同将来改变该纯函数输入，撤销本判定并重新核对。

收据 `.local/docs-checks/20261002-tm005-core-slice/receipt.json` 保存八份输入SHA-256、提交、逐项语义边界及命令日志：structure退出0，治理457/457退出0，工作簿回读退出0，diff检查退出0。独立切片判定 `development_slice_ready`；原32条产品父TC、6个变体继续draft/unexecuted且绑定null，三条CORE程序也尚未绑定/执行。0.5整版 `baseline` 与 `quality_gate check` **NOT_RUN**；模块运行、真实产品E2E、正式发行均 `NOT_RUN`。根项目总表本次回读为11 Sheet、222父TC、41变体、263用例行、13个旧历史批次，SHA-256 `4a596813f2fa99fd1473bbaacd743341f9d2ef01e3546f779327e41705b11e65`；这是固定输入与状态索引，不是产品测试报告。

## 2026-10-01 · 新仓库纯统计开发切片编制

总控在新仓库 `/Users/lz/文档/git/TokenMeter` 恢复 TM-001 Electron 源码及当前0.2文档总表，原记录中“当前工作树缺 Electron 源码”只描述旧分支当时基点。TM-005开发会话在新分支交接纯静态 oracle 检查；它核对预先归一化的合成算术，不接原生日志、客户端SQLite、IPC或App，不授予产品TC PASS。文档会话按新SOP-008修订5，将 `TASK-TM005-EVENT-CONTRACT/RANGE-QUERY/COVERAGE` 的纯函数部分拆为 `CORE-01/02/03` 三条辅助模块TC，冻结 `tests/fixtures/tm005-core-slice.json` 的双来源可信合成事件、unknown诊断及声明式coverage状态代数。原32条产品父TC和6变体保持draft/unexecuted且绑定null；合成complete标签不证明真实连续空日覆盖。整版0.5 baseline、产品E2E和正式发行仍NOT_RUN/BLOCKED。

SOP-024编制检查：`python3 scripts/check_docs.py --mode structure` 退出0（134文档、1211链接），`python3 -m unittest discover -s tests/governance -p 'test_*.py'` 退出0（457/457），`git diff --check`退出0；`python3 scripts/verify_project_workbook.py`退出0，根总表11 Sheet、222父TC、41变体、263用例行、13个原有历史批次，SHA-256 `d0bcb363a618930453b1a9cd399382132133e7b6c6d9b2671072358e21949f07`。这些是文档/治理检查，没有运行CORE模块程序或产品E2E。固定输入摘要：合成fixture `2dad1a42bc3051c8a1f820d12211c832522ba46586c3b84e00ebcd3b708470e9`，逐TC文档 `9e0fb9933801df891284b4294c95dc3933e5ea4783053d3412b5fa3dba4f3cbd`，机器用例 `cd748133c90d0d83c2d6e6d242d996fe3aeb7227b2600bb69ff954d7d777f3fc`。SOP-008独立切片的内容/依赖判定与提交SHA另记下一条；此处仅固定编制输入。

## 文档会话接管机器用例与语义oracle（2026-10-01）

文档会话从TM-005源工作树接管01–06、03a/04a、32条细TC和6个固定变体；原语义oracle `tests/fixtures/tm005-semantic-expected.json` 以相同SHA-256 `a1a054e704e44cd409ce2a24bc163003c34c39f9b6cfeaf08090e10a35f375b1`复制。六个变体补有序动作、逐步预期和文件只读预期；两条聚合E2E的来源行修正为当前详细文档19/36行。TM-005代码提交`4bb7afe490e1193fb0f7cf7c4e6dee11d7d58022`新增语义oracle检查与治理负测，只证明规范化算术，不证明双来源原生日志或产品E2E。本版固定产品程序、原生数据与上一0.4稳定包仍缺，执行保持BLOCKED。

**release_id：** `v0.5.0-20261001T034729Z`
**状态：** draft / baseline_pending；产品 E2E 未执行，发布资格：无。

## 2026-10-01 · SOP-001/002/003/004/005/006/007/024 草案

- 输入：用户交办 `REQ-TM005`，仓库已提交基线 `6e80dd12d60ee5dad641bca030445a2153a269c9`，主工作区未提交 TM-001 Electron 回归状态，现有产品约定、矩阵与 `scripts/test_data.py`。
- 隔离：本分支工作树 `/Users/lz/.codex/worktrees/tm005-usage/TokenMeter`；未修改 TM-001 主工作区，也未启动 GUI 测试或占用其服务/进程。
- 事实：TM-005 既有 `depends_on=[TM-003, TM-004]`；二者 planned。标准化 date_ranges 样例不等于原生日志或产品导入，当前已提交基线没有 Electron 源码/客户端用量库。测试与产品结论均不得登记 PASS。
- 决策待用户：本轮保持 Codex+Claude Code 并加入 TM-004 依赖工作，或正式修订为仅 Codex。问询已在本会话发出；答复前需求、任务与 TC 只作草案。
- 输出：本目录 01–05 草案和版本清单；无产品实现、无发布产物。下一步依据答复修订范围，再完成逐 TC/数据/SQL/固定程序设计与 SOP-008 基线。依赖采集链路和可运行 Electron 工程仍需取得。
- SOP-024 结构校验：初次及状态页更新后两次执行 `python3 scripts/check_docs.py --mode structure`，退出码均为 0；最终 `documentation_structure_only=PASS`，92 份登记文档、620 条链接。`git diff --check` 退出码 0。该结果不构成 SOP-008 基线或产品 E2E 通过。

## 2026-10-01 · 总控集成边界

总控会话要求本需求保持独立分支/工作树，交接最终分支名、提交 SHA、版本、变更、原始证据及 FAIL/BLOCKED；由总控复核并整合本地 master、统一推送远端 master。本会话不自行合并或推送 master。总控所列 TM-001→TM-002→TM-003→TM-005 是当前协调顺序，不替代尚待用户决定的 TM-004 依赖，也不使未提交的 TM-001 工作树快照成为可合并提交。

## 2026-10-01 · 双来源范围确定

用户新增独立 TM-004 Claude Code 采集会话；总控明确本轮 TM-005 保持原有 Codex + Claude Code 双来源验收，不缩为仅 Codex。TM-004 升为正式前置依赖。上述协调顺序据此改为 TM-001→TM-002→TM-003→TM-004→TM-005；两来源稳定提交和原始产品证据未交接前，TM-005 的 raw fixture、E2E 绑定、实现与发布门禁仍为 BLOCKED。此前问询已由此决定回答，保留历史记录不覆盖。

根据该决定补充[逐 TC 设计草案](04a-test-cases.md)及[独立规范化语义 oracle](../../tests/fixtures/tm005-semantic-expected.json)。它们包含双来源、日期/模型、上海与 UTC 边界、无覆盖/零/未知状态和测试隔离要求；尚无任何原生日志兼容或产品执行证据。完整覆盖证明、两来源稳定 schema、可执行 SQL 和固定程序仍需在 TM-003/004 交接后确定，文档保持 draft。

SOP-024 修订检查：`python3 scripts/check_docs.py --mode structure` 退出 0，93 份登记文档、626 条链接；`git diff --check` 退出 0。`python3 -m json.tool tests/fixtures/tm005-semantic-expected.json` 退出 0。对静态 oracle 与现有标准化 `scripts/test_data.py` 行作独立只读算术核对：12 个唯一事件、上海六个范围及八个非空日、UTC 两个显式事件范围和近 7/30 天汇总均一致。该核对只证明规范化样例内部一致，不证明 Codex/Claude 原生日志、覆盖状态或 App E2E。

双来源 `tests/acceptance.json` 已登记数据能力需求，`tests/feature_matrix.json` 的 TM-005 两场景改用 planned `tm005_raw_both`、`data_program=null`，`tests/datasets.json` 登记计划能力；现有 `date_ranges` 继续只提供标准化语义，不伪称可运行原生采集。manifest 记录 22 条需求→任务→TC/场景追踪。首次结构检查因 04 测试计划中第二个 E2E ID 写成缩写而 FAIL；修成完整 `E2E-TM005-002` 后新运行 PASS，未覆盖原 FAIL。

本次本地原始检查目录 `.local/tm005-plan-check-20261001T041339Z/`：`structure.json` 对应 `python3 scripts/check_docs.py --mode structure` 退出 0、93 文档/629 链接；`diff-check.txt` 对应 `git diff --check` 退出 0；`quality.json` 对应诊断性 `python3 scripts/quality_gate.py check` 退出 1。质量结果只有当前版本七份 draft 文档的基线状态错误，准确反映原生数据/schema/逐 TC 程序缺口；不将其修改为 baselined 或当作产品失败。SOP-008 正式基线尚未开始。

追加日期无效输入 TC 后，新收据 `.local/tm005-plan-check-20261001T041609Z/structure.json` 为 structure 退出 0、93 文档/632 链接；同目录 `diff-check.txt` 对应 `git diff --check` 退出 0。以上均属文档草案与格式检查，没有业务用例执行。

此分支的已提交起点不含 `TEST_CASES.md`、`tests/test_cases.json`、`TokenMeter项目总表.xlsx`、`docs/standards/test-cases.md` 或 Electron `apps/desktop/`；这些均只存在于仍在修改的 TM-001 主工作树。为遵守不带入未提交 TM-001 快照的集成要求，本草案只在版本 04/04a、验收/矩阵/数据清单登记追踪，根用例清单、项目总表和固定测试程序须在 TM-001 稳定提交进入本分支后同步。未同步前不得执行 SOP-008 基线或声称“功能/测试/数据/规范同轮完成”。

暂存全部草案后，首次 `git diff --cached --check` 因新版本文档标题行的 Markdown 尾随空格退出 2；已删去尾随空格并重新暂存，复查退出 0。之后再次执行 structure，退出 0、93 文档/632 链接。首次格式失败不作为产品缺陷或产品 E2E 结果。

## 2026-10-01 · TM-004 草稿事实与来源无关设计

总控报告 TM-004 阶段提交 `2b04dc9` 仅是规划草稿。随后在本工作树只读核对 `git cat-file -t 2b04dc9` 返回 `commit`，`git show --stat --oneline 2b04dc9` 仅列 12 份文档/清单改动，无采集代码或固定产品测试；阅读其 03 技术设计确认共享事件字段也被标为 TM-003 草稿。TM-004 因此不能视为 TM-005 已可用依赖。新增[03a 来源无关统计合同](03a-statistics-contract.md)明确账号归属、unknown/coverage 四态、UTC 半开日界、同一只读快照、受限 IPC 与迁移恢复，全部为待上游稳定接口核定的设计，不声称已实现。

静态 oracle 追加五种两来源覆盖/未知组合；每种均标 `raw_fixture_status=not_built`。本轮 `python3 scripts/check_docs.py --mode structure` 退出 0、94 文档/635 链接，JSON 语法检查和 `git diff --check` 均退出 0。尚未运行产品测试，质量基线仍因上述真实缺项保持 draft。

本轮原始检查留在 `.local/tm005-plan-check-20261001T042520Z/`：`structure.json`、`oracle-valid.json` 与 `diff-check.txt` 对应上述三个退出 0 的命令。`oracle-valid.json` 只是 JSON 语法回读，不是原生日志或产品结果。

补充本记录链接后再次执行 structure，退出 0、94 文档/636 链接；暂存差异的 `git diff --cached --check` 退出 0。

## 2026-10-01 · Claude fork 阶段观察

总控转来 TM-004 隔离回环 Claude Code 2.1.126 实测事实：CLI 自写主会话与 `--fork-session` JSONL，fork 文件复制父会话两条消息并追加新消息；本次 raw 没有 `forkedFrom`。本会话未取得最终 raw fixture/合同，不能把静态二进制中的 `forkedFrom` 路径写成必有条件。已在 03a 明确 TM-005 只消费上游可信唯一调用/诊断，新增 `TC-TM005-CONTRACT-03` 与语义 fork oracle；M110 + 新 N55 得 165 仅在 TM-004 最终链路能证明继承时成为可执行预期，否则必须诊断不确定并保持 baseline_pending。TM-005 双来源范围、产品未执行状态及依赖阻塞均不变。

SOP-024 本次结构与格式收据位于 `.local/tm005-plan-check-20261001T055121Z/`：`structure.json` 为 PASS、94 文档/636 链接、退出 0；`diff-check.txt` 对应 `git diff --check` 退出 0。静态 oracle 的 JSON 语法检查退出 0。它们不证明 fork 解析或产品 E2E。

总控又报告 TM-004 隔离回环子代理探针：Claude Code 2.1.126 的 CLI 自写 `subagents/agent-*.jsonl`，父会话与子代理各有独立 usage；TM-004 保存了 raw JSONL、固定响应、请求记录和 SHA，正在更新文档。本会话尚未取得最终原件/合同，故把此事实与 fork 复制历史分开写入 03a，并增加 `TC-TM005-CONTRACT-04` 及子代理语义 oracle。设计数字 M110 + S220 = 330 只在最终身份可信时成立；不能把父引用当第三次调用，也不能以 fork 历史的去重规则吞掉真实子代理调用。两条新 TC 均未执行，TM-005 仍无产品 PASS。

总控报告 TM-003 提交 `fecd35c5bba967773e3d535ada02f7522989ef02` 固定 Codex `0.158.0-alpha.2.1` 隔离原生来源探针。只读 `git show --stat` 证实提交含 `scripts/tm003_native_probe.py` 与来源文档；设计说明把 `token_usage_record` 定为逐响应增量、turn/thread 用量定为累计快照。阶段原件 `.local/tm003-native-probe/20261001T054930Z-96270/result.json`（在 TM-003 工作树）为 `SOURCE_PROBE_PASS`，记录单条 response_id `tm003-native-probe-response-1`，input100/cached20/cache_write0/output10/reasoning2/total110；原始 JSONL SHA-256 为 `3b30cfa81c0c29a80f1bfc1de5bf823db01a9a85636e41ec58dfdd00f0436d08`。该探针不是解析/去重/产品 E2E。新增 `TC-TM005-CONTRACT-05` 和静态 oracle 约束子项不重复相加，仍待 TM-003 最终可执行链路。

TM-004 又将隔离原生 Claude 2.1.126 研究固定为提交 `d0108814802e549e669e5500927afa5fedc65df7`；只读 `git show --stat` 核对该提交仍为文档/研究记录。总控指出原始清单在 TM-004 工作树 `.local/ci/tm004-claude-2.1.126-research/evidence-manifest.json`。已提交设计明确 fork 复制父 UUID/`message.id`/usage 但样本无 `forkedFrom`，子代理 `agentId/isSidechain` 与父同 `sessionId`；本版 03a 和两条 Claude TC 已据此更正来源边界，但最终统计身份/数字仍以 TM-004 采集合同与产品 E2E 为准。

本次设计检查原件 `.local/tm005-plan-check-20261001T060000Z/structure.json` 为 structure PASS、94 文档/636 链接，`diff-check.txt` 对应 `git diff --check` 退出 0，静态 oracle JSON 语法检查退出 0。上述均不改变文档 draft、产品 unexecuted 或发布资格。

## 2026-10-01 · 累计 fork、重复消息和零值歧义

总控转来三项上游阶段观察：TM-003 exec fork 新文件仅有新响应 C，但 C 的 `thread_token_usage` 是继承 A+B+C 的累计；该固定来源探针按原断言 BLOCKED。TM-004 一次 API 消息可能写成两条相同 `message.id`/完整 usage 的 assistant JSONL；合成 API 省略 usage 时 CLI 仍可写数值零 usage。已分别新增 `TC-TM005-CONTRACT-06`（只加 C 逐响应用量）、`TC-TM005-CONTRACT-07`（同调用多行只计一次）及 `TC-TM005-STATE-05`（无证明的零值保持未知），并在 03a 与静态 oracle 明确阶段边界。设计数字只在上游最终身份/未知值合同和真实 App 链路交付后锁定；特别是可见 raw 若无法区分显式零与缺失，就不能由 TM-005 凭空区分。未把 BLOCKED 探针或日志零字段当产品 PASS。

SOP-024 检查收据 `.local/tm005-plan-check-20261001T061052Z/structure.json` 为 PASS、94 文档/636 链接，`diff-check.txt` 对应 `git diff --check` 退出 0；静态 oracle JSON 语法检查退出 0。当前目标数据集和产品程序仍未就绪，SOP-008 基线及产品 E2E 不执行。

## 2026-10-01 · 跨来源原生 ID 碰撞

总控跨分支接口审核指出 TM-003 拟议 `(principal_key,response_key)` 主键与 TM-004 草稿 `source/source_event_key` 的命名空间风险：Codex 与 Claude 不同真实调用可能使用相同原生 ID，不能误去重；同一 Claude 调用重复又不能重复计量。03a 补充来源限定唯一性合同，新增 `TC-TM005-CONTRACT-08` 和静态 oracle 的 A110+B220=330、同源重放不增断言，要求只读 SQLite 同时核对两来源身份/用量。该数字为计划输入，最终键、原生日志映射及 SQL 仍待 TM-003/004 冻结；没有产品执行结果。

本次结构和格式收据 `.local/tm005-plan-check-20261001T062500Z/structure.json` 为 PASS、94 文档/636 链接，`diff-check.txt` 对应 `git diff --check` 退出 0；静态 oracle JSON 语法检查退出 0。文档仍为 draft，未运行产品 E2E。

## 2026-10-01 · 上游共享身份草稿

总控转来 TM-003/004 共享身份**草稿**：`source_event_key=HMAC-SHA256(local_secret,length_prefix(["usage-identity-v1",source,provider_call_scope,canonical_call_id]))`；Codex 的 scope/ID 是 `provider-response`/`token_usage_record.payload.response_id`，Claude 是 `provider-message`/`assistant.message.id`，source 分别 `codex`/`claude_code`。agentId/session/thread 只做不可逆归属及冲突诊断；拟 schema `source,source_event_key,source_scope_key`，PK `(principal_key,source,source_event_key)`。可证复制同 ID/usage 去重；跨 Agent/会话无法证实复制关系时诊断 `unverified_inheritance`、覆盖不完整；同 ID usage/model 冲突诊断 `identity_conflict`、保留首可信值。03a、`TC-TM005-CONTRACT-08` 已据此细化，新增 `TC-TM005-CONTRACT-09/10` 及两个稳定冲突变体，并同步验收数据能力与静态 oracle。此身份合同尚无上游稳定源码和产品 E2E，本版不能把草稿写成已实施或把未确定碰撞默计为 0。

首次诊断性 `python3 scripts/quality_gate.py check` 退出 1：除了八份本版文档正确保持 draft，还发现测试计划把 `TC-TM005-CONTRACT-10#USAGE/MODEL` 缩写，造成 `-USAGE` 变体追踪缺失。没有删用例；已在 04 写出两个完整 ID，并在 manifest 各加追踪。再次运行后 traceability 错误消失，仍因真实 draft 基线状态退出 1。新原始收据在 `.local/tm005-plan-check-20261001T063714Z/`：structure PASS、94 文档/637 链接、退出 0；quality FAIL、退出 1，错误仅为八份 draft 文档；`diff-check.txt` 退出 0。数据和程序缺项未被放宽，SOP-008 正式基线仍未开始。

## 2026-10-01 · Claude 第二阶段数值与分页覆盖

总控转来 TM-004 第二阶段提交 `dda5ccb`，本会话只读 `git show --stat` 和其 03 设计，确认文档记录原生 Claude Code 2.1.126 双 text 块两条 assistant 行各 31/9、唯一调用40；合成 API 省略 usage 时 CLI raw 仍写 0/0。把 `TC-TM005-CONTRACT-07` 的设计数字由 100/10=110 更正为已观察的 31/9=40，`TC-TM005-STATE-05` 明确 0/0 不能证明真零；静态 oracle 同步。TM-004 原始清单在其工作树 `.local/ci/tm004-claude-2.1.126-research/{followup-evidence-manifest,branch-evidence-manifest}.json`，本分支不复制原件或冒充产品结果。该版 fork/Agent 样本仍无 `fork-context-ref`，改写 UUID 的原生证明 BLOCKED，03a 保留此边界。

同一提交指出 TM-002 的预览上限（1000文件/5000目录项/2秒）不能替代完整采集，拟独立分页每页最多256条；TM-002 分页 API 尚未实现。03a 增加覆盖约束，新增 `TC-TM005-STATE-06`，设计至少1025文件/5页、预览截断、续页与页间撤权的 known-partial/`history_incomplete` 断言；只有全部页面/深度/行/游标实际完成才能判断覆盖。数值 A110+B220=330 是计划输入，SQL 和产品程序尚未绑定，状态 `baseline_pending`。

本次 SOP-024 原始收据在 `.local/tm005-plan-check-20261001T064819Z/`：structure PASS、94 文档/637 链接、退出 0；quality FAIL、退出 1，错误仍仅是八份本版文档 draft 基线状态；`diff-check.txt` 对应 `git diff --check` 退出 0，静态 oracle JSON 语法检查退出 0。没有为取绿把文档提前标为 baselined。

## 2026-10-01 · SOP 整合基线移植

总控通知规范 PR #4 已进入本地及远端 master：`f3b29f6b4203fe22ae8a40533e775291253bb7b3`、tree `7022baa4d2665978295ffa47bb334b492c0f0ea2`。先提交旧分支最近的 Claude 双行/分页草案为 `e76f4ac`；旧七次 TM-005 提交完整保留在 `codex/v0.5.0-20261001T034729Z/usage-statistics-pre-sop`。随后从新 master 重建原名 TM-005 工作分支，仅移植本功能版本档案、详细用例和静态 oracle，并把共享验收、矩阵、数据、目录、状态和 Changelog 中的 TM-005 条目按 ID 重新加入；没有带入旧 Swift 文件、旧工作流或 TM-001 未提交快照。

已读取新基线的 SOP 索引、SOP-006/024 和用例规范。新 master 包含用例与项目总表规范，却仍缺根 `TEST_CASES.md`、`tests/test_cases.json`、`TokenMeter项目总表.xlsx` 和 Electron `apps/desktop/`。本分支详细用例索引只列 TM-005，明确不能代表全项目覆盖；根清单、Excel、固定程序及安装后 E2E 继续等待上游稳定提交。TM-003 最新 `dbcaa5e` 仍是来源研究及派生 fixture，其五项治理/环境错误和产品 E2E BLOCKED 不被采纳为本功能产品 PASS。SOP-008、实现和发布门禁保持 BLOCKED。

移植后的 SOP-024 检查收据 `.local/tm005-plan-check-20261001T065727Z/`：`check_docs.py --mode structure` 退出 0、84 文档/474 链接；`quality_gate.py check` 退出 1，16 条错误全部为本分支 10 份草案文档要求 baselined，没有 traceability 错误；静态 oracle JSON 语法及 `git diff --check` 退出 0。诊断性质量失败符合未完成基线状态，不通过改写文档状态消除。

## 2026-10-01 · TM-001 干净候选接口只读核对

总控通知 TM-001 将其功能分支与 SOP master 合并为干净候选 `3467dc143b2e2fc71f51515f483f0ecff8637947`（parents `44e3844`、`f3b29f6`）。其独立树的文档结构/基线/追踪前检与治理 426/426 已报告通过，原件位于该树 `.local/ci/tm001-merge-preflight-20261001T0716Z/`；尚无最终 DMG 产品 E2E 或发布门禁，本分支不把它标为稳定已交付功能。

本会话只读 `git show`/`git ls-tree` 核对该提交：`apps/desktop/`、根 `TEST_CASES.md`、`tests/test_cases.json`、`scripts/run_test_case.py`、项目总表和精细 Playwright 文件已进入 TM-001 候选；`src/shared/types.ts`、`src/preload/index.ts` 与 `src/main/index.ts` 构成固定业务 Bridge、`tokenmeter:invoke` 和逐方法校验分发。当前 Bridge 只提供账号、配置、更新，`apps/desktop/src` 中未见用量/统计持久化或 IPC。已在 03 开发计划记录 TM-005 后续扩展点，保持主进程读库与 renderer 隔离；未复制或合并候选源码。TM-002/003/004 采集合同和 TM-005 原生 fixture/TC 绑定仍未完成，SOP-008 与产品验收继续 BLOCKED。

本次 SOP-024 收据 `.local/tm005-interface-check-20261001T072410Z/`：structure 退出 0、84 文档/474 链接；quality 退出 1，错误仍仅为 16 条草案基线状态；`git diff --check` 退出 0。未运行 TM-001 候选产品测试或把其前检结果记作 TM-005 E2E。

TM-004 后续提醒 TM-001 候选的执行器仍只绑定本功能。再对 `3467dc1` 只读 `git grep` 和 `git show` 核对：`scripts/granular_e2e.py` 仅接受 `TC-TM001-*` 正则、从 `tests/test_cases.json` 仅取 `feature_id=TM-001`；候选目录中 `TC-TM005-*` 数量为 0。已在 03/04 明确本版须扩展固定目录、逐 TC 程序及精确集合门禁。现有 TM-001 runner 不能作为 TM-005 双来源产品 E2E 能力，实际执行仍为 unexecuted/BLOCKED。

SOP-024 收据 `.local/tm005-runner-check-20261001T072830Z/`：structure 退出 0、84 文档/474 链接；quality 退出 1，错误仍仅为草案文档基线状态；`git diff --check` 退出 0。

## 2026-10-01 · SOP PR #5 的来源凭据隔离前提

总控通知纯规范 PR #5 已合入远端 master `be10d117`，tree `09ce28c`。本会话只读比对 `f3b29f6..be10d11`：SOP-006/009/010/014 增加 TM-002/003/004 `safeStorage` 最终包实际 Keychain item 身份、与正式 App 分离、创建前空态和仅清理本次精确 item 的机器证据；`--user-data-dir` 不能证明 Keychain 隔离。TM-005 本身仍为双来源统计消费者，已在 04/04a 增加上游来源选择和 E2E 的依赖前提。当前分支未合并新 master，且上游原生探针/采集合同仍未交付；测试计划保持 draft，质量失败与产品 BLOCKED 不改写。

SOP-024 收据 `.local/tm005-sop5-check-20261001T074713Z/`：structure 退出 0、84 文档/474 链接；quality 退出 1，错误仍仅为草案基线状态；`git diff --check` 退出 0。该记录只是设计前提更新，没有运行 Keychain 探针或产品用例。

## 2026-10-01 · SOP-008 前的逐项内容审查

本分支已把远端规范 master `be10d117` 无冲突合入独立工作树，合并提交 `0450281`；暂存差异检查和 `check_docs.py --mode structure` 均退出 0，84 文档/474 链接。没有向本地或远端 master 写入 TM-005 内容。只读核对 TM-003 `clean-base` 与 TM-004 `05a9cd8`，双方冻结的**设计字段**为 `principal_key/source/source_event_key/source_scope_key/occurred_at_utc/model_id/input_tokens/output_tokens/cached_input_tokens/cache_write_input_tokens/reasoning_output_tokens/source_version/identity_scheme_version`，唯一键 `(principal_key,source,source_event_key)`，来源枚举 `codex`/`claude_code`，身份域 `usage-identity-v1`。03a 已与此对齐；实际表、解析、IPC 和产品用例仍未提交，不能把设计冻结写作产品接口 PASS。

审查发现旧 `TC-TM005-CONTRACT-09` 用同 ID 但不同用量，会同时触发 `identity_conflict`，无法单独判断 `unverified_inheritance`；已把第二条固定为相同用量/模型但跨 Agent 无可证复制关系，预期仅已知 110 与继承不明诊断，不要求落库原始 B。`CONTRACT-10-USAGE/MODEL` 继续单独验两种冲突。`CONTRACT-03/04` 改为固定正例预期，若最终原件不支持则运行前 BLOCKED，不能临场切换断言。静态 oracle 的来源枚举改为 `claude_code`，另手工列出今天/近30天的双来源小计、真未知模型和纽约夏令时 23/25 小时日界；新增 `MODEL-02` 与 `RANGE-11-SPRING/FALL` 设计用例。manifest 已登记全部 32 条父 TC、6 个稳定变体和两个 E2E 场景组，自动绑定仍为 null。

诊断性 `quality_gate.py check` 目前报告 16 条草案状态错误，落在下列 10 个活动文档（其中版本六份文件各有 catalog 与 release 两条要求）；逐项解除条件如下。保持 draft 是真实结果，不能只改状态取绿：

| 活动文档 | 当前可完成内容 | 仍阻断 SOP-008 的外部事实/程序 |
| --- | --- | --- |
| `01-requirements.md` | 双来源、计量、日期、隐私和真零/未知验收规则已固定 | `STATE-02` 的双来源完整空日可证明事实尚无来源/覆盖合同；若不可证明须先修订需求 |
| `02-breakdown.md` | 六个稳定 TASK 均有输入/产出、依赖与 TC | TM-003/004 物理事件/覆盖表及 TM-002 读取能力未稳定，具体文件/迁移完成条件待核 |
| `03-development-plan.md` 与 `03a-statistics-contract.md` | 来源域身份、事务查询、IANA 日界、拟议只读 SQL 和隔离边界已写明 | 实际 schema/IPC、连续覆盖证明、账号切换及 `safeStorage` 最终包隔离原件未交付 |
| `04-test-plan.md` 与 `04a-test-cases.md` | 双来源数值、边界、重复/冲突/分页及逐步预期已有设计 | 原生日志生成/重置、逐步 UI/test ID/只读 SQL、固定 Playwright 绑定及 DST 测试时钟/窗口方案缺失；跨版本导出器修复候选尚未集成本分支及总清单 |
| `05-release-plan.md` | 本机平台、候选→升级、原包门禁、隔离迁移/恢复及本地归档顺序已列 | 上一实际稳定签名包、最终 DMG、迁移恢复和完整产品原件尚不存在 |
| `06-iteration-record.md` | 每轮实际命令、退出码和阻断已记录 | 版本仍在编制；SOP-008、产品结果、通行证均无原件 |
| `docs/testing/cases/05-TM-005-usage-statistics.md` | 两个 E2E 场景组及输入、动作、预期、缺项已登记 | 逐 TC 的原生数据、SQL、程序和测试结果未绑定 |
| `docs/testing/cases/README.md` | 本分支仅列 TM-005，未声称全项目覆盖 | TM-001/002/003/004 的详细文件、根 `TEST_CASES.md` 与项目总表尚未进入本分支；导出器跨版本修复待交付 |

TM-003/004 的身份是设计可读，不是已稳定的 `usage_event` 运行时；TM-003 现拟的 `coverage` 仅有最早可信时间、缺历史和扫描不完整等字段，尚不能证明任意完整空日双来源连续覆盖。03a 的只读 SQL 仍标不可执行，`STATE-02/04` 保持真实外部阻断。总控已接手共享导出器跨版本/多段 TC ID 修复；本分支不删或改短稳定 ID 来迁就旧导出器。TM-001 当前固定 runner/gate 只证明其 78 父 TC、38 变体及六组补充；TM-005 须在 TM-003/004 的 TC/数据/接口稳定后扩展精确集合并加入缺例、错源、跳过等负测，不能仅改 TM-001 gate fixture 取绿。

新增纽约 DST 变体后又核对 TM-003 首次 30 天采集窗口：固定的 2026-03-08 与 2026-11-01 无法在当前真实时钟同时被产品初采，任意平移日期也会改变真实 DST 转换。04a 已固定每个边界前/内/上界事件与 30/90 Token 独立预期，同时明确无测试时钟/导入窗口合同前运行 BLOCKED；不能直接向 SQLite 插入旧事件或调系统时钟冒充原生日志产品链路。04a 另将 `MODEL-01` 的字面 `unknown-model` 与真正 `model_id=null` 区分，新增 `MODEL-02` 设计为已知用量330中未知模型110、已知模型220，仍待上游原生日志映射。

本次内容审查的原始收据 `.local/tm005-design-check-20261001T081506Z/`：`check_docs.py --mode structure` 退出 0、84 文档/475 链接；`quality_gate.py check` 退出 1，16 条错误仍仅为上述 10 份文档的 draft 基线状态；静态 oracle JSON 语法、`git diff --check` 退出 0；固定治理 `python3 -m unittest discover -s tests/governance -p 'test_*.py'` 实跑 198 项全过、退出 0。治理和静态审查均不能替代双来源真实 App E2E，本轮未运行产品或签发通行证。

**诊断口径更正：** 本记录较早几处将 `quality_gate.py check` 的草案失败描述为“没有 traceability 错误”。该命令在文档基线失败时按代码提前返回，只报告文档错误，根本没有执行 `validate_manifest`；因此那些语句不能证明追踪检查通过。随后单独调用仓库固定的 `quality_gate.validate_manifest(ROOT)`，诊断返回 `errors=[]`、features 12/cases 37/implemented 0/bindings 6，但它只覆盖当前分支已有目录，不等于完整跨版本用例导出或产品 E2E。

## 2026-10-01 · 共享导出器变体编号对齐

只读核对 TM-002 分支候选提交 `f7b83ed` 的 `scripts/export_test_cases.py`：它接受多段或带数字的父 TC ID，变体要求父 ID 后接 `#` 和稳定后缀，并按用例所在 release/TASK 及详细文档交叉验证。该提交尚未进入本分支，不能把工具候选测试结果当本分支通过。TM-005 六个变体的设计 ID 已改为 `#USAGE`、`#MODEL`、`#START_EMPTY`、`#END_EMPTY`、`#SPRING`、`#FALL`，并在详细用例各自列出固定输入和独立预期；manifest、测试计划与静态 oracle 同步。这是目录兼容性修订，不改变需求或宣称产品已执行。共享导出器及 TM-001 根目录集成后，再生成机器目录、同步总表并做正式基线校验。

首次本分支检查收据 `.local/tm005-variant-check-20261001T083522Z/` 保存了真实失败：`check_docs.py --mode structure` 退出 1，恰有六条 `release.traceability[*].test: valid test ID required`；`quality_gate.py check` 退出 1，同六条加原有 16 条草案基线错误。原因是 `scripts/release_contract.py` 的测试 ID 正则只接受连字符段，而[用例规范](../../docs/standards/test-cases.md)已明确支持 `TC-ID#变体`。单独 `validate_manifest` 返回 `errors=[]`、features 12/cases 37/implemented 0/bindings 6；静态 oracle JSON 与 diff 检查退出 0。该失败不是产品失败，也不能忽略结构错误继续基线。

先在 `tests/governance/test_check_docs.py` 增加可重复的变体追踪正例、文档 ID 不匹配和小写后缀反例；修改前定向运行 `test_stable_variant_traceability_requires_exact_document_id` 退出 1，正例确实被旧正则拒绝。随后只扩展 `scripts/release_contract.py` 的 test ID 模式，保留严格的来源文档与缺失追踪判据。修复后 `.local/tm005-variant-fix-20261001T083900Z/`：structure PASS、84 文档/475 链接、退出 0；quality 退出 1，仅余 16 条真实 draft 基线错误；独立追踪诊断 `errors=[]`，上述计数不变；治理测试 199/199 PASS、退出 0；静态 oracle JSON 和 `git diff --check` 退出 0。此处为治理工具与草案兼容修复，TM-005 正式基线、产品 E2E、DMG 与通行证仍 BLOCKED。

同步状态页与 Changelog 后又保存 `.local/tm005-variant-final-20261001T084300Z/`：structure PASS、84 文档/476 链接、退出 0；quality 仍仅为上述 16 条 draft 错误、退出 1；`git diff --check` 退出 0。此收据仍非文档基线或产品通过证明。

## 2026-10-01 · 根机器目录、项目总表与固定阻断预检

总控交办共享目录和总表对齐。本工作树曾尝试合入共享候选 `442af3f`，发现它还携带整套 TM-001 产品源码和流程；已执行 `git merge --abort`，回到干净的 `8342946` 后只选取目录导出器及其所需的历史用例设计、项目登记和总表工具。当前分支没有接入 `apps/desktop/` 产品源码或 TM-001 的完整执行流程。为使历史详细文档的链接可核，另选取其纯文档、`scripts/local_e2e.py` 与旧版发布记录；该脚本没有在本分支作为 TM-005 产品入口执行。TM-004 设计提交 `d6c90e3` 的固定 identity-v1 向量、生成脚本和治理负测也被选择性接入，03a 明确精确 UTF-8 字节、四字段长度前缀与来源域；它仍是设计合同，不是解析器的产品证据。

在 `tests/test_cases.json` 中登记 TM-005 的 32 条父 TC 与 6 个 `#` 变体，全部标 `baseline_pending`、`unexecuted`、`binding=null`、`evidence=null`。目录共 141 条父级记录、440 个步骤，根 `TEST_CASES.md` 由固定导出器生成。`docs/project-register.json` 新增六项功能点、六项任务和本版本草案，保留 12 次 TM-001 历史批次但不移作 TM-005 运行结果。项目总表 11 Sheet、141 条父级用例和 6 条独立变体行，经生成后回读；当前 TM-005 完整回归栏为“未执行”。历史报告本机路径只作为旧批次回读依赖，不代表本轮产品执行。

新增 `scripts/check_tm005_bindings.py` 固定校验详细文档与机器目录的 ID、版本、来源、无证据 PASS 和绑定缺口；固定负测证明删去变体、错版本或无证据 PASS 会被拒绝。独立语义负测直接计算已知 Token 子项、真未知模型与纽约春秋日界，不调用待开发产品查询。首次完整检查收据 `.local/tm005-catalog-check-20261001T094137Z/`：structure 退出 0，103 文档/831 链接；baseline 和 quality 均退出 1，准确报告 16 条活动草案基线错误；项目总表回读 PASS（SHA-256 `0a1d0f3a6929bba08f115b15eb921018727378e50849d2a5ee50011ddcd67a5d`）；绑定预检退出 2/BLOCKED、32 父例/6 变体/38 缺绑定；治理测试 238/238 PASS；`git diff --check` 退出 0。

该次目录检查也真实 FAIL：新增详细说明使 `E2E-TM005-001/002` 的来源标题从第 17/34 行移到 19/36 行，机器目录仍保留旧行号。已修正两个来源行并重新生成根清单；修复后的独立复查另存下一收据。上述治理和总表结果只证明设计资料内部一致；两来源原生数据、真实 SQLite/IPC、安装包 Playwright E2E、完整回归和 SOP-017/018 仍未执行，文档基线与发布资格均 BLOCKED。

修复后收据 `.local/tm005-catalog-final-20261001T094336Z/`：structure 退出 0，目录导出器 `--check` 退出 0，项目总表回读退出 0，`git diff --check` 退出 0；绑定预检仍按设计退出 2/BLOCKED。单独调用 `quality_gate.validate_manifest(ROOT)` 返回零错误、features 12/cases 37/implemented 0/test_bindings 6；这项诊断不绕过完整 quality gate 的 16 条 draft 错误，也不表示任何产品用例已执行。

## 2026-10-02 · CORE-04/05 辅助切片输入与核准

在已登记的32条产品父TC和6个变体之外，固定`TC-TM005-CORE-04`三步IANA半开日界与`TC-TM005-CORE-05`四步双来源SQLite只读快照，分别关联`TASK-TM005-RANGE-QUERY`及`TASK-TM005-EVENT-CONTRACT`。输入为`tests/fixtures/tm005-iana-core-slice.json`和`tests/fixtures/tm005-sqlite-snapshot-slice.json`；后者仅用本例拥有的合成库，经TM-003`UsageStore.commitBatch`种子、WAL读事务和另一连接提交验证同窗一致性。审查TM-003实际`coverage`物理字段后修正03a旧拟议表述：现有表无法证明任意历史完整空日，产品真零仍待上游来源事实。

最初新增详细章节使E2E-TM005-001/002机器目录来源行偏移，导出检查真实失败；已修正至23/40行，保留该失败于本机检查输出。冻结输入提交`986e0d382f5dbb09025460f5b041a0089797f213`、tree`ac5d73e5b697bc25ee9d8468dd1cc73345ff3318`。SOP-008收据`.local/docs-checks/20261002-tm005-iana-sqlite-slice/receipt.json`逐文件保存SHA：structure退出0、治理477/477、机器目录232父/739步CURRENT、总表11 Sheet/232父/42变体/274行/18批次回读PASS（SHA-256 `20c539a9ab8137ce4022f4e0bd2fb8b0d60ebd09c5929ab1cf4391a3cef0bc94`）、diff检查退出0，语义审查判仅两条辅助用例`development_slice_ready`。程序绑定仍null、执行`unexecuted`；整版0.5基线及quality未运行，真实App/原生日志产品E2E与正式门禁均NOT_RUN。

开发分支干净代码提交`259cf7688691d472837d59a8c1ae50e14b591410`（tree`d37d42feee7e5bd23f6f566cde83d4fa6801d090`）对冻结用例目录SHA-256 `674ec561de00f23696f0c93817172e400d47c61b3d3a927c23562249179fc162`执行两次独立`source_check`：`CORE-04` run`tm005-core04-20261001T193346Z` 1/1、三步、memory清理PASS，报告SHA-256 `a18c85a50cf6aaf6be3fa61e1a908046cca74efe26168e02ba4c831a9ef3cb43`、Excel SHA-256 `bc84e9c10cedcd0648baca10f6ce57e02baf9bc68ee94148bd143f4dcaaf7c8d`；`CORE-05` run`tm005-core05-20261001T193346Z` 1/1、四步、owner清理PASS，报告SHA-256 `7ad5e3ac7971df64ec204b1917331db5be78ce559b870f533ff18925fc79af83`、Excel SHA-256 `033d2660f8b466ae6b68751b67b4bd792d5eac0ec21909d99ff3eeb8e8455906`。两份verification回读PASS；CORE05最初临时路径前置失败及之后有效红测失败各自保留在开发树原件，均未改写。代码分支普通推送退出0、GitHub refs/commit API读回同SHA/tree；Git `ls-remote`当时443连接失败，不写成Git传输读回PASS。该源码检查点及两次模块PASS不说明程序已在本文档树集成：`tests/test_cases.json`绑定仍null，待总控同树整合后复核。原32条产品TC、安装App E2E和正式发行仍NOT_RUN。
