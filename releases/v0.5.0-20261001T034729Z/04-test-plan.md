# TM-005 测试计划草案

**release_id：** `v0.5.0-20261001T034729Z`
**状态：** draft / baseline_pending；所有下列 TC 未执行。

纯统计开发切片另固定 `TC-TM005-CORE-01/02/03` 三条辅助模块TC，输入/独立预期由 [core fixture](../../tests/fixtures/tm005-core-slice.json) 与[04a逐步用例](04a-test-cases.md#无原生日志依赖的纯统计辅助tc)共同给出。只使用已可信的双来源合成事件和声明式覆盖事实，不调用授权、原生日志、产品数据库或App；相应TASK/TC可按SOP-008单独核对，原32条产品父TC及6变体继续draft/unexecuted。完整0.5 baseline、产品E2E和发行门禁未执行。

新增独立`CORE-04/05`：日期模块使用[固定IANA日界](../../tests/fixtures/tm005-iana-core-slice.json)核对上海/UTC/纽约23与25小时半开界及无效输入；快照模块使用[合成SQLite数据](../../tests/fixtures/tm005-sqlite-snapshot-slice.json)经TM-003提交接口在本例私有库造数，仅按当前主体/双来源/固定UTC界做同事务只读统计，WAL另一连接提交前后分别核对330/385。两例的DB操作、重置、逐步独立预期与产品非目标见[04a](04a-test-cases.md#日期与双来源物理快照辅助tc)。程序绑定为null、实际未运行；不证明双来源原生日志采集、任意完整空日覆盖、IPC/UI或产品E2E。

逐 TC 的输入、有序动作、逐步 UI/DB 预期、类型、数据与缺口见[04a 逐 TC 草案](04a-test-cases.md)。以下是任务级摘要；两处均属设计，程序未绑定。

## 独立输入与已知预期

沿用 `scripts/test_data.py` 的 seed 42、参考时钟 `2026-09-29T04:00:00Z` 和 `Asia/Shanghai`，并保存[手工枚举的独立语义 oracle](../../tests/fixtures/tm005-semantic-expected.json)。其 13 行标准化样例含 1 行重复，共 12 个唯一事件；它既不是 Codex/Claude 原生日志，也没有导入产品。基础预期：今天 5 事件、input 15000、output 1500、cached read 1700、reasoning 170、total 16500；昨天 110；近 7/15/30 天分别 17380/27830/31130；自定义 2026-09-20 至 21 日为 2200。缓存和推理为子项；规范化样例没有 cache write 字段，该子项为未知，不能补 0。今天按来源的独立已知总量为 `codex=9900`、`claude_code=6600`；近 30 天分别为 14630/16500。费用字段属于 TM-006，本版不验收价格。

原生日志映射、UTC 时区 oracle、逐日趋势/明细事件集合、已覆盖零调用、无覆盖、未知字段和跨身份隔离样例尚未建立。预计 raw fixture 必须来自明确声明的实际版本，并由独立预期文件人工核算；生成程序不得调用产品解析/查询。SQL 仅用于创建隔离账号、只读核验客户端/服务端真实结果和安全重置，不能直接插入用量表替代原始采集。依 SOP-010/011 固化后才可运行 E2E。

TM-001 候选 `3467dc1` 虽已有 `scripts/run_test_case.py`、`scripts/granular_e2e.py` 和精细 Playwright 入口，当前执行器目录只含 `TM-001`，`granular_e2e.py` 的 ID 正则与目录筛选也只接受 `TC-TM001-*`。本版每条 `TC-TM005-*` 必须先进入固定总清单、数据生成/重置和安装后 App 测试绑定，并由门禁复核精确 TC 集合；不能把 TM-001 程序存在当成本版可执行判据。

远端 SOP PR #5 `be10d117` 明确：TM-002/003/004 若用 `safeStorage` 保存来源 locator，最终包的测试 Keychain item 必须有实际身份、与正式 App 分离及本次创建/清理的原生证据。TM-005 两来源 E2E 消费这些上游能力，测试前需核对同一最终包的隔离原件；缺失时只阻断依赖场景，不以独立 profile 代替 Keychain 证明。详细共用前置见 04a。

现有标准化样例可先手工列出范围的事件集合，供后续原生日志映射核对：

| 范围 | 唯一事件 ID（重复 `today-gpt` 不再计入） | total |
| --- | --- | ---: |
| 今天 | `today-gpt`, `today-sonnet`, `today-qwen`, `today-glm`, `today-unknown` | 16500 |
| 昨天 | `yesterday` | 110 |
| 近 7 天 | 今天五项、`yesterday`, `day7` | 17380 |
| 近 15 天 | 近 7 天七项、`custom-start`, `custom-end`, `day15` | 27830 |
| 近 30 天 | 近 15 天十项、`day30` | 31130 |
| 自定义 09-20 至 21 | `custom-start` | 2200 |

今天按模型的独立总量为 `gpt-5=1100`、`sonnet-test=2200`、`qwen-test=3300`、`glm-test=4400`、`unknown-model=5500`；五项相加 16500。若把团队时区改为 UTC，固定时钟的 UTC 今天含 `today-sonnet/qwen/glm/unknown`，total 为 15400；UTC 昨天含 `today-gpt` 与 `yesterday`，total 为 1210；UTC 近 7 天不含 UTC 09-22 16:00 的 `day7`，total 为 16610。UTC 近 30 天从 08-31 开始，08-30 的 `day30` 与 `outside30` 均排除，total 为 27830。这些是根据列出的事件时间和 token 明算的**规范化样例预期**，不是原生日志或产品运行结果。

## 逐任务 TC 草案及待细化点

| TC | TASK | 已确定输入/动作/预期 | 待补以形成基线 |
| --- | --- | --- | --- |
| `TC-TM005-CONTRACT-01` | `TASK-TM005-EVENT-CONTRACT` | 重复源事件重扫、刷新、重启；可信事件数与总量不增加 | 原生事件身份和 DB 只读 SQL |
| `TC-TM005-CONTRACT-02` | `TASK-TM005-EVENT-CONTRACT` | 缺 input/output 或不可核实来源；标未知且不伪造 0 | 原生缺字段样例、诊断码 |
| `TC-TM005-CONTRACT-03` | `TASK-TM005-EVENT-CONTRACT` | Claude fork 复制父历史且实际 raw 可不含 `forkedFrom`；最终可信用量只计真实新调用 | TM-004 最终 fork 身份/诊断合同及 raw fixture |
| `TC-TM005-CONTRACT-04` | `TASK-TM005-EVENT-CONTRACT` | Claude 父会话和子代理各有独立 usage；各真实调用计一次，父引用不重计子调用 | TM-004 最终子代理归属/身份合同及 raw fixture |
| `TC-TM005-CONTRACT-05` | `TASK-TM005-EVENT-CONTRACT` | Codex 原生逐响应 100+10=110；缓存读20/写0、推理2及累计快照不重复相加 | TM-003 最终解析/存储合同及原生 fixture |
| `TC-TM005-CONTRACT-06` | `TASK-TM005-EVENT-CONTRACT` | Codex exec fork 仅新响应 C 入账；继承父线程 A+B+C 累计快照不另加 | TM-003 最终 fork raw 身份与修正后来源探针 |
| `TC-TM005-CONTRACT-07` | `TASK-TM005-EVENT-CONTRACT` | Claude 同一 API 消息两条 assistant 行各带 31/9，只计一次 40 | TM-004 最终调用身份与原生 fixture |
| `TC-TM005-CONTRACT-08` | `TASK-TM005-EVENT-CONTRACT` | Codex 与 Claude 原生 ID 碰撞仍各计一次；同来源重放不增加 | TM-003/004 最终键命名空间和 SQLite 唯一约束 |
| `TC-TM005-CONTRACT-09` | `TASK-TM005-EVENT-CONTRACT` | Claude 跨 Agent/会话同 ID 但无可证复制关系：不默计为旧调用，诊断继承不确定且覆盖不完整 | 最终 `unverified_inheritance` 判据、归属与 DB 合同 |
| `TC-TM005-CONTRACT-10` | `TASK-TM005-EVENT-CONTRACT` | 同来源同 ID 的 usage 或模型矛盾：`TC-TM005-CONTRACT-10#USAGE` 与 `TC-TM005-CONTRACT-10#MODEL` 两变体分别保留首可信事件并记录冲突 | 最终 `identity_conflict` 合同与原生 fixture |
| `TC-TM005-DATA-01` | `TASK-TM005-DATA` | 固定 seed/时钟重复生成得到相同 oracle，所有资源限私有目录 | raw 映射、摘要与清理程序 |
| `TC-TM005-DATA-02` | `TASK-TM005-DATA` | UTC/Shanghai 边界和三态数据有独立 expected | 新 fixture 及逐事件 oracle |
| `TC-TM005-RANGE-01` | `TASK-TM005-RANGE-QUERY` | 今天 2026-09-29：5 事件、15000+1500=16500，缓存 1700、推理 170 | UI/IPC/DB 每步断言及事件集合 |
| `TC-TM005-RANGE-02` | `TASK-TM005-RANGE-QUERY` | 昨天 2026-09-28：1 事件、110 | 同上 |
| `TC-TM005-RANGE-03` | `TASK-TM005-RANGE-QUERY` | 近 7 天（09-23 至 29）：17380 | 每日趋势和明细集合 |
| `TC-TM005-RANGE-04` | `TASK-TM005-RANGE-QUERY` | 近 15 天（09-15 至 29）：27830 | 每日趋势和明细集合 |
| `TC-TM005-RANGE-05` | `TASK-TM005-RANGE-QUERY` | 近 30 天（08-31 至 09-29）：31130 | 每日趋势和明细集合 |
| `TC-TM005-RANGE-06` | `TASK-TM005-RANGE-QUERY` | 自定义当地 09-20 至 21：`custom-start` 包含、`custom-end` 排除、2200 | 日期输入和无效范围的独立用例 |
| `TC-TM005-RANGE-07` | `TASK-TM005-RANGE-QUERY` | Shanghai 下 15:59:59Z 属前日，16:00:00Z 属次日；UTC 下同属 UTC 日期 | 两时区逐点 oracle |
| `TC-TM005-RANGE-08` | `TASK-TM005-RANGE-QUERY` | 重扫、刷新、重启与时区切换后事件集合不变，分桶按新时区变化 | 程序动作与持久证据 |
| `TC-TM005-RANGE-09` | `TASK-TM005-RANGE-QUERY` | 自定义起日大于止日时拒绝应用，原筛选结果不变 | 表单错误合同/UI test ID |
| `TC-TM005-RANGE-10` | `TASK-TM005-RANGE-QUERY` | `TC-TM005-RANGE-10#START_EMPTY` 与 `TC-TM005-RANGE-10#END_EMPTY` 分别拒绝空起日/止日，原筛选结果不变 | 两项稳定变体及表单绑定 |
| `TC-TM005-RANGE-11` | `TASK-TM005-RANGE-QUERY` | `TC-TM005-RANGE-11#SPRING` 与 `TC-TM005-RANGE-11#FALL` 分别核对纽约 23/25 小时当地日、UTC 半开边界与 30/90 Token | 两类原生时间 fixture、时区 UI、TM-003 30 天导入窗的可验证测试时钟/窗口方案及变体绑定 |
| `TC-TM005-STATE-01` | `TASK-TM005-COVERAGE` | 无日志覆盖日期显示缺失，不显示 0 | 覆盖证明 fixture/DB |
| `TC-TM005-STATE-02` | `TASK-TM005-COVERAGE` | 已证明完整覆盖且无调用日期显示 0 | 覆盖证明 fixture/DB |
| `TC-TM005-STATE-03` | `TASK-TM005-COVERAGE` | 有记录但字段未知显示未知，已知部分不污染 | 原生未知 usage fixture |
| `TC-TM005-STATE-04` | `TASK-TM005-COVERAGE` | 三态在重启及改时区后仍正确 | 实际持久化与 UI 断言 |
| `TC-TM005-STATE-05` | `TASK-TM005-COVERAGE` | Claude raw 数值零也可能源于上游缺 usage；无额外证明时不能标真实零 | TM-004 最终未知/真零可判定合同 |
| `TC-TM005-STATE-06` | `TASK-TM005-COVERAGE` | 预览截断、分页未完或页间撤权时覆盖不完整；已有可信部分不冒充全量/零 | TM-002 分页接口、TM-004 全量扫描与撤权合同 |
| `TC-TM005-MODEL-01` | `TASK-TM005-UI` | 模型维度与同一范围的事件集合合计一致，未知模型保留标识 | 来源范围、模型原生映射 |
| `TC-TM005-MODEL-02` | `TASK-TM005-UI`（依赖事件合同） | 模型字段真实未知 `null` 仍计入可信用量；未知模型110+已知模型220=330 | 原生缺模型 fixture、受限 IPC/SQL 与 UI 绑定 |
| `TC-TM005-E2E-01` | `TASK-TM005-E2E` | 安装包逐 TC 执行、原始结果和清理完整，完整回归精确集合 | 固定程序与最终候选包 |

以上产品部分仍为设计草案，尚不满足每步 UI/API/DB 预期和可执行绑定。原32条产品父TC、6个变体与新增5条辅助模块TC进入 `tests/test_cases.json`、根 `TEST_CASES.md` 及项目总表；`python3 scripts/check_tm005_bindings.py` 在TM-005开发分支的固定预检核对原产品集合并如实报告38个产品绑定缺失，不能把辅助模块绑定算作产品补齐。原稳定场景组 `E2E-TM005-001` 与 `E2E-TM005-002` 继续保留，且必须同时包含 Codex 和 Claude Code 的真实采集输入；待依赖 schema 稳定后补齐数据清单、逐项程序绑定和真实产品结果。新CORE程序同样未绑定/执行，不得记录 PASS。

## CORE-06查询视图辅助输入

`TASK-TM005-RANGE-QUERY`的`TC-TM005-CORE-06`固定5步：真实UsageStore种A–E→同事务双来源330/partial→模型null/未知子项和当地日点→WAL并发F新旧快照330/385→独立G/H的字面`unknown_model`与合法99字符冒号模型分组407→空日missing/null及隐私清理。详细逐步预期和数据/SQL/重置见[04a](04a-test-cases.md)及[fixture](../../tests/fixtures/tm005-query-view-slice.json)；程序绑定、实际结果均为空。其输出未通过共享IPC/React或安装App，原产品RANGE/MODEL/STATE子集仍按原TC另验。
