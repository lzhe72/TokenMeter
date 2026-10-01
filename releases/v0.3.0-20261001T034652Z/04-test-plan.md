# REQ-TM003 · 测试计划

**release_id：** `v0.3.0-20261001T034652Z`　**状态：** draft；基础原生日志样例已由隔离 CLI 生成，测试数据与产品程序尚未建立，产品结果 unexecuted/BLOCKED。

依据[需求](01-requirements.md)、[TASK](02-breakdown.md)、[技术设计](03-development-plan.md)、[测试策略](../../docs/testing/strategy.md)和[执行规范](../../docs/testing/execution.md)。完整逐 TC 的输入、有序动作、逐步 UI/DB 预期、数据与清理列在[TM-003 详细用例](../../docs/testing/cases/03-TM-003-codex-collection.md)，本文件固定执行合同与场景映射；根[全部用例](../../TEST_CASES.md)、`tests/test_cases.json`、`tests/feature_matrix.json`及`tests/acceptance.json`须使用相同稳定 ID。

## 运行集合和追踪

| AC / E2E 场景组 | 本版必测产品 TC | 另需基础 TC | 独立数值预期 |
| --- | --- | --- | --- |
| `AC-TM003-001` / `E2E-TM003-001` | `TC-TM003-PARSE-01`, `TC-TM003-SCAN-01`, `TC-TM003-STORE-01`, `TC-TM003-UI-01` | `TC-TM003-SOURCE-01`, `TC-TM003-DATA-01` | A=110，A+B+C=660，cached=120；重扫/重启/移动仍唯一3条 |
| `AC-TM003-002` / `E2E-TM003-002` | `TC-TM003-PARSE-02`, `TC-TM003-MODEL-01`, `TC-TM003-DEDUP-01`, `TC-TM003-BRANCH-01`, `TC-TM003-PRIVACY-01` | `TC-TM003-SOURCE-02`, `TC-TM003-NAMESPACE-01`, `TC-TM003-STORE-01` | 可信 100/10+50/5+30/3+20/2=220；累计与重复不另加；跨来源同字面 ID 不误去重，矛盾/未知诊断；身份密钥不可用保留已提交 A=110 并停采集，恢复原密钥后只补 B 至330 |
| `AC-TM003-003` / `E2E-TM003-003` | `TC-TM003-SCAN-02`, `TC-TM003-SCAN-03`, `TC-TM003-WINDOW-01`, `TC-TM003-COVERAGE-OVERFLOW-01`, `TC-TM003-UI-02` | `TC-TM003-DATA-02` | 半行前110，完成后165，截断后新C一次入库为495；首次30天窗只计29天前事件，31天前不计；删除源后已采集量保留且缺历史可见；1000个预览候选后仍有 A 时最终读到110，未完成前覆盖不完整 |
| `AC-TM003-004` / `E2E-TM003-004` | `TC-TM003-BOUNDARY-01`, `TC-TM003-AUTH-01`, `TC-TM003-AUTH-02`, `TC-TM003-ISOLATION-01` | TM-002 自身授权 TC | 失效前330，失效期间330，恢复后660，重放A为0新增；切换 origin+account.id 后无旧主体数据 |
| 跨 AC 及交付 | `TC-TM003-MIGRATE-01` | `TC-TM003-E2E-01`, `TC-TM003-E2E-02`, `TC-TM003-GOV-01` | 数据、原件、候选与包身份精确一致；前序无采集表，升级后首次 A=110，账号/授权不变 |

开发阶段按本次变更范围运行已基线固定的 TM-003 TC 与相关已交付功能回归，逐项保留真实结果；无授权依赖的 CORE 辅助 TC 可先独立开发和验证，不给产品 TC 填 PASS。用户另行启动正式对外发布后，最终候选的产品集合才是上述 TM-003 产品 TC 加所有当时已交付功能 TM-001/002 的全部必测 TC 与变体。四个 TM-003 E2E 场景组作为补充入口保留，不以组 PASS 代替组内逐 TC。正式完整回归从最终 DMG 安装 App，贯通 UI→受限 IPC→主进程读取→客户端 SQLite，并带真实 FastAPI 与隔离服务端 SQLite 验证已交付账号功能。

## 固定数据与预期

### 可先实现的无授权模块切片

`TC-TM003-CORE-01/02/03` 分别把完整 LF 增量、非法/无身份诊断、来源域身份去重与冲突固定为私有合成输入、逐步预期和临时 SQLite 只读核验，详细步骤见[同 ID 用例](../../docs/testing/cases/03-TM-003-codex-collection.md#无授权依赖的解析与身份开发切片)。切片只依赖已核验的 Codex 0.158.0-alpha.2.1 字段、固定 seed/T0 与公开 identity-v1 测试向量；不调用 TM-002 目录能力、产品 profile/Keychain、App UI 或生产服务。产品 `TC-TM003-PARSE-01/PARSE-02/DEDUP-01` 与 `SOURCE-02` 保留原完整输入、逐步 UI/DB 判据和 BLOCKED 状态，辅助模块 TC 不能替代它们。模块程序尚未绑定，三个辅助 TC 目前 unexecuted；代码与真实测试证据到位后按本切片固定 ID 作开发回归，正式发行阶段再按完整候选清单验收。

下一独立模块切片 `TC-TM003-CORE-04/05` 的输入固定在[storage/cursor fixture](../../tests/fixtures/tm003-core-storage-cursor.json)：header+A完整LF偏移410字节，补B后750，补C后1090；A/B/C可信总量依次110/330/660。CORE-04用本例拥有的空SQLite，公开key1/key2，先提交A；仅在本例库建`BEFORE INSERT/UPDATE ON source_cursor`的`RAISE(ABORT)`触发器注入游标落库失败，核验B事件/诊断/游标/覆盖全回滚，去掉触发器重试B后全提交，再用不同有效32字节密钥验证拒绝且旧行不变。CORE-05使用测试持有的文件句柄与明确稳定的合成身份；半行不推进、普通追加只消费新LF，即使可变digest改变也不能重置；同长度/同mtime前缀改写使keyed prefixMAC不匹配，必须重扫、原可信事件按同ID去重不删，覆盖标缺口；截短同理。逐步判据、只读SQL和重置见[详细用例](../../docs/testing/cases/03-TM-003-codex-collection.md#无授权依赖的存储与游标开发切片)。这两条只可判纯模块，不包含TM-002能力、Keychain、真实App/UI/服务，产品`STORE-01/SCAN-02/SCAN-03`仍未执行；具体程序绑定先为null，SOP-008只针对该新切片独立核对。

`TC-TM003-CORE-06`单独固定[跨文件generation fixture](../../tests/fixtures/tm003-core-generation.json)：第一页file-a为header+A完整410字节、`complete=false`；末页file-b为header+B完整410字节、`complete=true`；两文件各自SHA、身份与期望总量`(count,input,output,cached,total)=(2,300,30,60,330)`预先冻结。固定同一代际三种路径：未到末页不得落任何事件/游标或声称完整；本例SQLite第二游标写入触发器使整代回滚；末页正文已验证后模拟撤权令guard拒绝且同步提交调用0次；仅稳定完整代际一次提交两个事件/两个游标/完整覆盖。逐步数据/清理见[详细用例](../../docs/testing/cases/03-TM-003-codex-collection.md#tc-tm003-core-06--多文件代际一次提交与全回滚)。该辅助TC不触达TM-002真实授权、Keychain、App/IPC/服务，原`COVERAGE-OVERFLOW-01`与产品STORE/SCAN仍BLOCKED。

`TC-TM003-CORE-07`固定[主进程fixture](../../tests/fixtures/tm003-main-collector-slice.json)：假TM-002来源能力真实形状的分页/分块接口，公开HMAC root/file向量，两页各410字节、假读端每次最多返128字节，必须循环至声明size。五步独立检查不合格主体/来源/采集权限先拒绝、末页前不提交、完整双文件一次提交330、提前EOF/读异常/注入1024字节预算超限零提交，以及末页后撤权/换账号使守卫拒绝；成功库重扫仍330。每故障变体新owner库，程序绑定和运行当前为空。它只测主进程假端口+真实隔离UsageStore，不声称TM-002真实OS授权、App/IPC、任意大日志或产品E2E；逐步判据见[详细用例](../../docs/testing/cases/03-TM-003-codex-collection.md#tc-tm003-core-07--主进程采集编排与能力失效)。

`TC-TM003-CORE-08/09/10`按[私有密钥与主进程闭环fixture](../../tests/fixtures/tm003-product-loop-slice.json)和[详细逐步用例](../../docs/testing/cases/03-TM-003-codex-collection.md#主进程身份真实来源适配与受限-ipc-开发切片)冻结为三个相互依赖的辅助`source_check`：CORE-08检验同profile密文密钥/主体键、重启与缺/坏/错键拒绝；CORE-09检验真实SourceAccess类+合成helper到UsageStore的确认/撤销/换主体及A/B=330；CORE-10检验主窗口sender、仅sourceId输入、白名单刷新/重复/停读/换主体状态。各例使用独立owner 0700/0600文件和只读DB旁证；现已绑定固定程序、套件与重置，新绑定候选待重跑，历史九批次原件归属各自旧提交，机器用例`execution_status=unexecuted`。这三例不证明真实系统目录选择、Keychain item隔离、安装App/IPC、任意大日志或TM-005双来源统计；产品`AUTH/UI/ISOLATION/STORE/SCAN`原TC继续独立BLOCKED，正式门禁NOT_RUN。执行顺序CORE08→09→10，TM-003独占共享主入口；TM-004仅交Claude adapter，TM-005只读统计/UI。

`codex_raw` 数据集计划固定种子 303；每次运行准备阶段由固定程序取一次 UTC 秒 `T0`，记录在 owner/expected 收据且该运行后续步骤不再读时钟；样例事件时间取 `T0-1天`，同 seed+T0 重建字节相同，由 `TASK-TM003-FIXTURE` 的版本化程序在 TM-002 草稿候选限制（根深度0、最多8层目录/1000文件/5000目录项/2秒）内创建本轮拥有的 0700 根 A、`sessions/YYYY/MM/DD/*.jsonl` 来源与同层 symlink 越界负例、未授权根 B、独立 profile、只读对照 expected、源字节摘要、owner 收据。原生来源样例需记录 `cli_version`/schema 和官方对应源；不含用户提示词/代码/真实路径。A/B/C 为不同 `response_id`：input/output/cached 分别 100/10/20、200/20/40、300/30/60，`total_tokens` 分别 110/220/330。样例中的 `thread_token_usage` 为累计对照，不另加到总数。第二组为逐响应 100/10、50/5、30/3、20/2，不把 100/10→150/15 的累计快照算成 250/25。

SOP-004 已产生一份独立原件：`codex-cli 0.158.0-alpha.2.1` 在 `.local/tm003-native-probe/20261001T054930Z-96270/` 的新 HOME 内自行写出 rollout，原件 SHA-256 为 `3b30cfa81c0c29a80f1bfc1de5bf823db01a9a85636e41ec58dfdd00f0436d08`；仅核实一条 100/10/cached20/cache write0/reasoning2 的响应。上述 A/B/C 和 cache write 5/10/15 等已由研究程序**按原生形状衍生**，不是 CLI 原件观测值，也尚未作为正式 SOP-010 fixture 交付；必须保留原件与改写字段的区分。

随后 `.local/tm003-lifecycle-probe/20261001T060101Z-1879/` 又取得真实 CLI 恢复、普通 fork、无用量完成的三个原件及失败/通过两轮证据：恢复根累计165，fork 子响应增量22、子记录 thread 累计187，无用量完成无逐响应记录且累计事件 `info=null`。`scripts/tm003_fixture_research.py` 只以这些原件的已核字段为模板生成**明确标记为衍生**的研究数据；固定 seed303、T0=`2026-10-01T06:00:00Z` 的两轮最终输出 `.local/tm003-fixture-research/20261001T063703Z-15669/` 与 `20261001T063737Z-15929/` 文件和 expected 摘要一致。它们不证明 cache write 5/10/15、缺字段、负值等由 CLI 原生发出，也未完成测试拥有的重置与 App/TC 绑定；子代理落盘仍无实证。SOP-008/009 未通过时数据状态保持 BLOCKED。

研究程序、原件哈希、衍生数据两轮摘要与受影响 TC 的**研究映射**固定在[TM-003 研究证据清单](../../tests/tm003_research_evidence.json)；该映射独立于正式 `test_programs` / `data_program`，所有这些正式绑定仍为 `null`，不得由研究 PASS 自动改为用例 PASS。

共享身份来源用固定合成标准事件测试纯身份/存储合同，不将尚未交付的 Claude 产品解析当 TM-003 E2E；`TC-TM003-NAMESPACE-01` 使用 TM-004 已提交的[公开身份向量](../../tests/fixtures/tm004/identity-v1-vectors.json)精确核对前像/HMAC（仅测试 key，不进入产品 profile），再以两条接受事件 total143 和不明重用/矛盾诊断作独立预期。参考脚本与治理3项通过只说明向量自洽，正式身份模块、key恢复和SQLite仍须按本例与真实App另验。超预览上限用例需另生成 1001 个候选且把 A 放末端；TM-002 目前只接受设计合同：`beginCandidateScan` / 每页最多256项的 `nextCandidatePage` / `openCandidateReadOnly(candidateToken)` / `cancelScan`，opaque cursor 以及 complete/incomplete、撤销/身份切换失效，每次主进程重验主体、授权和根边界。跨页目录 dev/ino/mtime/ctime 变动、撤销或切换身份须使旧 generation 的所有暂定页及暂存解析/同步结果回滚；最终 `complete` 仅证明候选目录树，仍逐文件验证正文稳定和完整。该 API/暂停/目录变动 fixture 未落地前 `TC-TM003-COVERAGE-OVERFLOW-01` 仍 BLOCKED，不从 UI 预览截断结果推断完整覆盖。TM-003 的重启/失效/重新确认 TC 只经 TM-002 能力读取；测试前还须取得 TM-002 私有加密 locator、macOS 系统密钥 item 与生产 item 隔离、精确 owner 清理及密钥不可用/密文损坏停读的固定证据，不向 renderer 或测试报告注入/输出完整路径或密文。缺这些证据时相关产品 TC 保持 BLOCKED。

SQL 不直接向产品 `usage_event` 造数。数据库准备只用新的私有空客户端库；账号用 TM-001 固定合成测试用户的独立服务库。每步只读核验拟用 `SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(COALESCE(cached_input_tokens,0)) FROM usage_event WHERE principal_key=?`；缓存值在该配方无独立预期的步骤另以 `SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens) FROM usage_event WHERE principal_key=?` 核对，不用省略号冒充第四列断言，同时按 `(principal_key,source,source_event_key)` 唯一约束与 `source_cursor.committed_byte_offset` 检查；若 cached 未知，另查 `cached_input_tokens IS NULL`，不能把 `COALESCE` 的零误称已知。输入 SQL 与预期值由数据程序硬编码，不调用生产解析器。原始日志、库和报告只能位于本轮私有根，清理只作用于带 owner 收据的目录。

## 自动化绑定与环境

SOP-010 先交付真实来源核验、`codex_raw` 固定生成/重置/归属程序；SOP-011 将详细 TC 固化到 `apps/desktop/e2e/` Playwright 用例和 `scripts/run_test_case.py --case-id <具体用例编号>` 入口，记录每步实测及原件。当前 `test_programs=[]`、`test_data_program=null`、各新 TC `binding=null`，不可填写未来命令为已可执行。现有 `scripts/granular_e2e.py`、`scripts/granular_gate.py`、`scripts/local_gate.py` 及变体清单仍固定 TM-001 的 78 父/38 变体/6 补充集合；SOP-011/014 必须把 TM-003 逐 TC 的运行、原始步骤证据和目标加历史全集合同扩入执行器与最终门禁，并固定负测证明缺本版任一例/步或 release 不匹配必拒绝。只修治理 fixture 的当前版本引用不能代替这项产品门禁扩展。数据和程序齐全后才改 ready。红测必须实际启动已构建 App 并在预期行为上确定性失败；若 TM-002 接口、原生样例或 GUI 资源未到位，则依赖产品 TC 为 BLOCKED，不写假 FAIL。

每例先验证登录/授权状态、动态独占端口和测试库归属。真实 UI 选择 A 并确认；任何测试不得扫描真实 `~/.codex` 或 `~/.claude`、用户现有 App、49176 服务、生产 SQLite 或默认凭据。授权撤销只针对测试拥有根，按 TM-002 稳定 fixture 完成；不能直接改数据库或伪造 TM-002 状态冒充真实失效。E2E 不 mock 主进程/IPC/采集结果。测试代码与数据冻结并按 SHA 绑定候选；原始 Playwright JSON、trace、逐步断言、只读 DB、源摘要、进程/包身份和清理结果按 run_id 保留本机。每次实际运行另外生成 `TokenMeter测试结果-<run_id>.xlsx`；总表只登记摘要和入口。

## 判定与阻塞

确定性行为不符为 FAIL；归属/重置 fixture、自动化绑定或逐步可执行判据缺失使依赖它的 TC 为 BLOCKED；最终包或环境缺失阻断正式发行检查。任何 FAIL/BLOCKED、跳过、零例、重试取绿、清理失败或证据与候选不匹配均不得宣称对应功能 PASS；正式发行门禁遇到这些情况则整体阻断。新跑定向 TC 不覆盖历史失败；开发期修复后运行目标与受影响的已交付功能固定 TC，正式发行时对同一最终候选运行跨需求完整回归。当前已知前置：TM-001 的 c291 最终包门禁 FAIL，后续修复候选仍有失败或环境阻断；TM-002 实现与固定程序在独立树推进，但产品 E2E 受 AX/测试账号和 Keychain 隔离阻断；基础 Codex 0.158 原生日志及衍生研究数据虽已取得但未完成 SOP-010 数据交付，TM-003 客户端集成与产品绑定尚未完成。独立模块切片可先推进，产品 E2E 不能提前宣称通过。
