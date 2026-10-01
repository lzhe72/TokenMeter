# 03 · TM-003 Codex 采集：逐 TASK 测试用例

**release_id：** `v0.3.0-20261001T034652Z`　**需求：** `REQ-TM003`　**设计状态：** draft。程序绑定均为 `null`、实际执行均为 `unexecuted`；不得把规划数字或基础检查记为产品 PASS。

本版[需求](../../../releases/v0.3.0-20261001T034652Z/01-requirements.md)、[任务](../../../releases/v0.3.0-20261001T034652Z/02-breakdown.md)和[测试计划](../../../releases/v0.3.0-20261001T034652Z/04-test-plan.md)给出独立预期。四个稳定组 `E2E-TM003-001` 至 `004` 保留，以下每个 `TC-` 独立判定。执行按 SOP-009→010→011→013→014；数据库迁移另按 SOP-016；最终包按 SOP-017/018。SOP-004 隔离来源探针已有基础、恢复、普通 fork 与无用量原件，衍生研究数据可重建；TM-001/002 稳定交接、正式 SOP-010 数据与重置、TM-003 固定产品测试程序和 UI 均未完成，依赖项准确为 **BLOCKED**。

## 共用输入、数据及只读核验

- `R-BASE`：固定种子 303；数据程序在每次运行准备阶段只取一次当前 UTC 秒作为 `T0` 并写入 owner/expected 收据，之后该运行各步不再读时钟。A/B/C 的事件时间为 `T0-1天` 加 0/1/2 秒，保证重新运行仍位于首次 30 天窗口内；同一 seed+T0 生成相同字节摘要。仅在本次拥有的 0700 私有根创建 A（待授权 Codex rollout）和 B（未授权）；A 的原生形状文件位于 `sessions/YYYY/MM/DD/*.jsonl`，由固定程序在 TM-002 草稿候选限制（根深度0、最多8层目录/1000文件/5000目录项/2秒）内生成；相对名称/大小/mtime 仅用于候选预览，超限“不完整”不能当历史覆盖完成，独立 profile、客户端 SQLite、动态独占回环 FastAPI/服务端 SQLite、合成成员账号。由真实 UI 登录、选择 A、确认采集；不使用真实 `~/.codex`、`~/.claude`、49176 用户服务、生产库、默认凭据或现有 App。每例先清空自己创建的库/游标，再按该例生成固定原生 JSONL，末尾只含 LF 完整行时才可入库。
- 来源约束：`.local/tm003-native-probe/20261001T054930Z-96270/` 留有一条基础 CLI 自写原件；`.local/tm003-lifecycle-probe/20261001T060101Z-1879/` 留有同版真实恢复、普通 fork 与无用量原件及摘要。普通 fork 子文件只含新响应，`thread_token_usage` 却延续父累计；无用量完成没有逐响应记录，`event_msg.token_count.info=null`。子代理仍未实测。研究程序 `scripts/tm003_fixture_research.py` 已按原件字段派生 seed303+T0 的 1010 个私有 JSONL（其中1001个为超预览上限候选） 和独立 expected，字节可重建，但明确不是 CLI 自写原件，也不是正式 SOP-010 数据交付；本版所有 TC 的 `data_program=null`、执行状态 unexecuted。A/B/C 是派生的不同 response ID 的 `usage`：100/10/20、200/20/40、300/30/60，cache write 为5/10/15、reasoning output 为3/6/9，均是 input/output 子项；总量 110/220/330，合并 660/cached read120/cache write30/reasoning output18。另一配方增量 100/10、50/5、30/3、20/2，可信总量 220。expected 是独立硬编码值，不能调用产品解析器生成。
- 只读 SQL 观察面：`Q_SUM(P) = SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(cached_input_tokens) FROM usage_event WHERE principal_key=?`；`Q_IO(P) = SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens) FROM usage_event WHERE principal_key=?`；`Q_SUB(P) = SELECT SUM(cache_write_input_tokens), SUM(reasoning_output_tokens) FROM usage_event WHERE principal_key=?`；`Q_NULL(P) = SELECT COUNT(*) FROM usage_event WHERE principal_key=? AND cached_input_tokens IS NULL`；`Q_CURSOR(P,S) = SELECT committed_byte_offset FROM source_cursor WHERE principal_key=? AND source_key=?`；`Q_DIAG(P) = SELECT code, count FROM collection_diagnostic WHERE principal_key=?`；`Q_SCHEMA = PRAGMA user_version`。以下简写 Q_SUM/Q_IO/Q_SUB/Q_NULL/Q_CURSOR/Q_DIAG 均绑定当前已验证主体 P；跨账号用例显式传各主体键。SQL 只在拥有的客户端 SQLite 上执行，不直接写 `usage_event`。`SUM` 的 NULL 与数字 0 必须区分。每例具体 DB 准备/变更/核验见下表；未建表前 SQL 是设计，不是已执行命令。
- 结果入口：SOP-014 的固定单例 `scripts/run_test_case.py --case-id <TC-ID> --package-manifest <本轮实际包清单>` 待绑定；开发包显式 `--development`。逐步原始 JSON/trace/只读 DB/源摘要及清理证据按新 run_id 保存在 `.local`，另生成同 run_id 独立结果 Excel。截图只作诊断，不由目测判 PASS。

## E2E-TM003-001 · 增量、重扫、重启及移动

**验收：** `AC-TM003-001`。本组列出来源、数据、解析、补扫、存储与 UI 子 TC；组本身只汇总，不替代逐项判定。

**前置/数据：** 使用共用 `R-BASE` 和 A/B/C 独立 expected；正式数据/重置及上一版授权能力尚待 SOP-010/011 绑定。

**步骤：**
1. 经真实 App 登录、确认本例 A 根，再按下表逐项追加完整原生响应行并触发采集。
2. 对同一已确认根重扫、重启与移动文件，逐项核对 UI、客户端 SQLite 只读查询和文件摘要。
3. 对未知来源、密钥不可用与恢复等子 TC 使用各自独立运行和故障 fixture，不合并推断结果。

**独立预期：** A/B/C 为唯一三响应，可信 input600、output60、total660、cached read120、cache write30、reasoning output18；重扫、重启和同根移动不重复，未知或越界来源不计入可信总量。具体每步与 DB 判据见下表和同 ID 逐项段落。

**绑定/证据/状态：** `draft`、`unexecuted`，产品程序绑定为 `null`；需最终安装包 UI/IPC、主进程来源审计、只读 SQLite 与逐 TC 原件，缺项 BLOCKED。

| TC / TASK / 类型 | 实际输入、前置及有序动作→逐步预期 | DB 准备→变更→只读核验；数据/重置 | 绑定与状态 |
| --- | --- | --- | --- |
| `TC-TM003-SOURCE-01` / `TASK-TM003-SOURCE` / source_check | 1. 对照本版声明的 CLI build、官方结构与 `sessions/YYYY/MM/DD/*.jsonl` 受控原生样例→TM-002 预览只给相对名称/大小/mtime，TM-003 独立核实样例有 `session_meta.id`、`token_usage_record.payload.response_id/usage`，版本和 SHA 有记录。2. 换一个未声明 build→该 build 不列为已支持，显示 `unsupported_source_version`。 | 无 DB 写入；核对来源清单版本、摘要与私有样例归属。数据：受控来源样例；每次新隔离根重建。 | `null`；planned/unexecuted；已有单次原生基础原件，缺本 TC 固定检查/拒绝程序与产品绑定。 |
| `TC-TM003-DATA-01` / `TASK-TM003-FIXTURE` / data_check | 1. 在 `sessions/YYYY/MM/DD/*.jsonl` 以 seed303 与本次已记录的 T0 生成 A/B/C 原生形状记录→同一 seed+T0 重建时相对位置与字节摘要固定且三 ID 不同。2. 独立读取 expected 文件→A=110、A+B+C=660、cached=120，第二配方=220；没有调用产品解析器。 | 准备新私有根，不写用量表；只核对文件 SHA、expected 和 owner。重置删除仅本例拥有的根后同种子重建。 | `null`；planned/unexecuted；研究程序及重复性证据已有，缺正式 SOP-010 归属/重置与本 TC 绑定。 |
| `TC-TM003-PARSE-01` / `TASK-TM003-PARSE` / product_e2e | `R-BASE`。1. 仅追加 A 完整行并从 UI 刷新→卡片 input100/output10/total110/cached read20/cache write5/reasoning3、唯一1。2. 追加 B/C 后刷新→input600/output60/total660/cached read120/cache write30/reasoning18、唯一3；累计字段不额外加。 | 空客户端库→插入 A 后1行，再插 B/C 后3行；`Q_SUM=(3,600,60,120)`，`Q_SUB=(30,18)`、`Q_NULL=0`；重置私有库。 | `null`；planned/unexecuted；缺 App UI/IPC/解析绑定。 |
| `TC-TM003-SCAN-01` / `TASK-TM003-SCAN` / product_e2e | `R-BASE`、A/B/C。1. 三次分批追加并等 watcher 或30秒补扫→每批总量110/330/660。2. 手动刷新同文件并重启 App→仍660。3. 同一授权根内移动文件并刷新→仍唯一3、660。 | 空库→只增加3事件；每步 `Q_SUM` 为 `(1,100,10,20)`、`(2,300,30,60)`、`(3,600,60,120)`，重扫/重启/移动不变；核对 `Q_CURSOR` 完整行字节边界。 | `null`；planned/unexecuted；缺 watcher/包级测试。 |
| `TC-TM003-STORE-01` / `TASK-TM003-STORE` / product_e2e | `R-BASE`、A/B 与本例拥有的私有 usage 身份密钥。1. 完整 A 刷新→110。2. 仅本例 App 退出/重启→仍110。3. 追加同 ID 同用量 A→仍110、唯一1。4. 经 owner 与生产隔离核验，仅使本例 usage 身份密钥不可读取，追加完整 B=200/20/cached40 并从真实 App 刷新→保留110、停采集，显示 `identity_secret_unavailable` 和覆盖不完整。5. 恢复本例原密钥、重启同一已安装 App 并刷新→只补 B，total330、唯一2，A 键不变；密钥原文不得进入报告。 | 私有空库→A 一事件及游标同事务；密钥不可用时 `Q_SUM=(1,100,10,20)`、游标不前进、覆盖不完整；恢复原密钥后 `Q_SUM=(2,300,30,60)`，A 的 `source_event_key` 不变、B 一事件、游标至完整 B 行尾；不直接写产品库。仅本例 fixture 暂使密钥不可读并恢复，按 owner 清理。 | `null`；planned/unexecuted；缺 SQLite/真实 App 绑定和本例密钥隔离、不可用/恢复固定 fixture；不能证明只操作本例密钥时第4/5步 BLOCKED。 |
| `TC-TM003-UI-01` / `TASK-TM003-UI` / product_e2e | `R-BASE`、A/B/C。1. 采集前查看卡片→显示尚无可证明历史/等待采集，不能显示已知0。2. 采集后→可信 input600、output60、total660、cached read120、cache write30、reasoning output18、唯一3、UTC最后采集时间。3. 插入一个缺 `cached_input_tokens` 的非 0.158 完整行→可信总量仍660，显示缺字段诊断，不把未知 cached 当0。 | 空库→前三条 `Q_SUM=(3,600,60,120)`；无新事件，`Q_SUM`保持三条；`Q_DIAG`出现缺字段，UI 区分未知来源。 | `null`；planned/unexecuted；缺卡片/IPC。 |

## E2E-TM003-002 · 累计、重复、分支及未知

**验收：** `AC-TM003-002`。本组逐项检查逐响应身份、累计快照、普通 fork、重复、跨来源身份与未知诊断。

**前置/数据：** 使用共用 `R-BASE`，固定 100/10、50/5、30/3、20/2 响应与独立 expected；每项以新的隔离根和客户端库重建。

**步骤：**
1. 通过真实 App 逐项导入有稳定 `response_id` 的完整 `usage`，再加入累计快照和普通 fork 子文件。
2. 分别重放已计身份、写入矛盾身份与未知/无身份记录，读取 UI 诊断和只读 DB 事件键。
3. 对跨来源同字面原生调用 ID、身份密钥失效和恢复运行各自固定子 TC，保存来源域与文件摘要。

**独立预期：** 示例可信总量 220；累计快照、继承历史与重复不额外计量，矛盾身份和不可核实格式保留诊断且不污染可信值。密钥不可用时停采集、保留旧事件；各子 TC 的独立数值与 DB 判据见下表。

**绑定/证据/状态：** `draft`、`unexecuted`，程序绑定 `null`；需最终 App、身份/来源审计、只读 SQLite 和独立运行原件，缺项 BLOCKED。

| TC / TASK / 类型 | 实际输入、前置及有序动作→逐步预期 | DB 准备→变更→只读核验；数据/重置 | 绑定与状态 |
| --- | --- | --- | --- |
| `TC-TM003-SOURCE-02` / `TASK-TM003-SOURCE` / source_check | 1. 输入只有 `event_msg.token_count.info.total_token_usage=100/10` 且无 `response_id`→诊断 `unverified_cumulative`、可信事件0。2. 加 rate-limit-only 的 `info=null`→诊断 `missing_usage`，不生成0值用量事件。 | 新库→`Q_SUM`无事件；`Q_DIAG`分别含 `unverified_cumulative` 与 `missing_usage`；仅测试拥有根。 | `null`；planned/unexecuted；两种形状已有原生 CLI 原件，缺产品解析/诊断检查绑定。 |
| `TC-TM003-PARSE-02` / `TASK-TM003-PARSE` / product_e2e | `R-BASE`。1. 完整合法 100/10 行→110。2. 依次追加缺 `usage`、负 input、cached 111>input100、矛盾 total111 四个不同 ID 完整行→UI 可信总量仍110，每项显示独立诊断，不能作为0值成功事件。 | 空库→仅合法1行；`Q_SUM=(1,100,10,20)`；`Q_DIAG`四种错误各≥1；重置私有库。 | `null`；planned/unexecuted；缺原生输入与诊断 UI。 |
| `TC-TM003-MODEL-01` / `TASK-TM003-PARSE` / product_e2e | `R-BASE`。1. 在有同一 `turn_id` 的原生 `turn_context` 声明 `gpt-6-sol` 并追加 ID-m 10/1→UI 总量11，DB模型为 `gpt-6-sol`。2. 对新 turn 声明来源未知但实际原样标识 `model-x` 并追加 ID-n 10/1→UI 总量22，DB保留 `model-x`，不得改成0或空字符串。3. 追加找不到同 turn 上下文的 ID-o 10/1→UI 总量33，DB模型为 NULL 且显示模型未知诊断。 | 空库→最终 `Q_IO=(3,30,3)`；只读查询三个模型字段依次为 `gpt-6-sol`、`model-x`、NULL；不插入模型维度造数。 | `null`；planned/unexecuted；缺 turn 绑定与 App。 |
| `TC-TM003-DEDUP-01` / `TASK-TM003-IDENTITY` / product_e2e | `R-BASE`。1. 追加 ID-a 100/10→110。2. 重放 ID-a 完全相同记录→仍110。3. 追加 ID-b 同样100/10→220且唯一2。4. 再写 ID-a 999/99→仍220并有 `identity_conflict`。 | 空库→最终 `Q_SUM=(2,200,20,40)`；冲突不覆盖原行；读 `Q_DIAG`。 | `null`；planned/unexecuted；缺身份落库与真实刷新。 |
| `TC-TM003-BRANCH-01` / `TASK-TM003-IDENTITY` / product_e2e | `R-BASE`。1. 主会话按 `usage` 写 100/10、50/5，而累计快照从100/10到150/15→可信165。2. 独立新会话写30/3→198。3. 普通 CLI fork 形状的子文件带 `forked_from_id`，只含新响应20/2、`thread_token_usage` 为父累计加 C 的170/17→可信220、唯一4；另在独立文件重放父 A 响应→仍220，重放是人为负例，不称为原生 fork 继承。4. 写无响应身份的累计回退和未知结构→仍220，显示 `unverified_cumulative` / `unknown_format`。 | 空库→最终 `Q_IO=(4,200,20)`；output20、total220；cached 按固定各项另核；`Q_DIAG`有两类，重放不新增事件。 | `null`；planned/unexecuted；已有原生 fork 与衍生研究数据，缺 TM-002 来源能力和安装 App 绑定。 |
| `TC-TM003-NAMESPACE-01` / `TASK-TM003-IDENTITY` / source_check | 固定合成标准事件和[已提交公开身份向量](../../../tests/fixtures/tm004/identity-v1-vectors.json)中的32字节测试 key，仅用于独立身份 oracle，绝不写入产品 profile；Codex `provider-response`、Claude `provider-message` 的原生 ID 字面都为 `shared-call-01`，cached 分别为20、0。1. 分别输入 Codex 100/10 和 Claude 30/3→显式 `source`、不同域键，两条可信事件 total143，键分别为 `afd67bd0cad0227b3e7b5ac132bb9b3ed492073983b9c16a0c9cc24dd3008051` 与 `bf222a85ab2209f72ff82c21b7172c9315448b3e1d5bf4503a3c76b30c46cad1`。2. 同 Codex ID/usage 重放→键相同、仍两条143。3. Claude 另一 Agent 同 ID/usage 但无可证实复制链→不当新调用，诊断 `unverified_inheritance`、覆盖不完整，仍143；Agent 归属摘要不同也不进唯一键。4. 同 Codex ID 用量改为 999/99 或模型不一致→`identity_conflict`，首事件不覆写，仍两条143。 | 独立私有 schema→经正式身份/存储入口最终2事件，来源分别 codex/claude_code；`source_event_key` 精确等于上述向量，`Q_SUM=(2,130,13,20)`，诊断含两类且 coverage 不完整；不以手写 SQL 代替事件入口。测试结束只清理本例拥有库。 | `null`；planned/unexecuted；公开向量参考程序已通过，仍缺正式身份模块、私有库绑定及该合成跨来源检查程序；不把 Claude 产品采集列为 TM-003 已交付。 |
| `TC-TM003-PRIVACY-01` / `TASK-TM003-STORE` / product_e2e | `R-BASE` 中只放合法 A=100/10/cached20。1. 在不会参与用量的原生文本字段中放固定合成哨兵 `TM003_SECRET_SENTINEL`、代码片段和合成绝对路径→有效用量仍只按 `usage` 计。2. 退出 App，对拥有的 SQLite、WAL 与采集报告做字节扫描→均不含哨兵/原始路径/原始 JSONL。 | 新库→仅白名单事件字段、HMAC 身份；`Q_SUM`与合法用量一致；重置私有根。 | `null`；planned/unexecuted；缺安全存储与固定扫描程序。 |

## E2E-TM003-003 · 半行、源清理与历史覆盖

**验收：** `AC-TM003-003`。本组覆盖半行、首次 30 天窗口、源清理、候选上限与分页失效。

**前置/数据：** 使用本例拥有的隔离根、固定 `T0`、29/31 天事件和 1001 个可排序候选；每个子 TC 单独重建数据和预期。

**步骤：**
1. 经真实 App 确认来源，先写未闭合半行，再补全并刷新，核对完整行游标与可信总量。
2. 在独立运行中导入 29/31 天事件和无效 UTC 时间，再删除本例源文件，核对历史覆盖提示与既有事件。
3. 在 1001 候选场景逐页续扫并分别触发页间撤权、目录变动，核对旧 generation 拒绝与重新扫描。

**独立预期：** 半行不消费，补全后 A/B total165 且重启不重计；只计窗口内事件，源清理不删除已采事件。预览截断不等于扫描完成，第 1001 个候选可信用量仍可见；撤权或目录变动使旧页暂存结果失效。每例数值与 DB 操作见下表。

**绑定/证据/状态：** `draft`、`unexecuted`，程序绑定 `null`；缺内部分页、真实 App、原始页/文件审计和隔离 SQLite 原件时 BLOCKED。

| TC / TASK / 类型 | 实际输入、前置及有序动作→逐步预期 | DB 准备→变更→只读核验；数据/重置 | 绑定与状态 |
| --- | --- | --- | --- |
| `TC-TM003-DATA-02` / `TASK-TM003-FIXTURE` / data_check | 1. 数据程序向拥有的文件只写 B JSONL 前半字节且无 LF→文件确实不含完整 B 行。2. 同程序补写余字节与 LF→恰好一条完整 B。3. 清理仅 owner 收据中的源文件→其他根、App 和服务不受影响。 | 无产品库写入；按字节摘要、LF 数和 owner 核对；重置只删本例根。 | `null`；planned/unexecuted；缺字节级程序。 |
| `TC-TM003-SCAN-02` / `TASK-TM003-SCAN` / product_e2e | `R-BASE`。1. 完整 A=100/10 后刷新→total110、唯一1。2. 只追加 B=50/5 半行并刷新→仍110、游标停在 A 的 LF 后。3. 补齐 B 和 LF 后刷新，再重启→total165、唯一2，B 只计一次。 | 空库→`Q_SUM=(1,100,10,20)`，半行时同值，补全后 `Q_IO=(2,150,15)`；`Q_CURSOR`先停于 A 完整字节，再到 B 完整字节。 | `null`；planned/unexecuted；缺真实扫描入口。 |
| `TC-TM003-SCAN-03` / `TASK-TM003-SCAN` / product_e2e | `R-BASE`。1. 完整 A=100/10 与 B=50/5 入库→total165、唯一2。2. 仅对本例源文件截断为完整 A 并刷新→已采集 B 不丢，仍165，游标重置到当前 A 的 LF。3. 追加新 ID-C=300/30 完整行并刷新、重启→total495、唯一3，A不重计。 | 空库→`Q_IO` 先 `(2,150,15)`，截断后不变，最后 `(3,450,45)`；`Q_CURSOR`按新文件完整字节更新，不越过未闭合行。 | `null`；planned/unexecuted；缺文件替换归属 fixture 与 App。 |
| `TC-TM003-WINDOW-01` / `TASK-TM003-SCAN` / product_e2e | 本例私有根在首次确认前放 ID-old=`T0-31天` 900/90 和 ID-new=`T0-29天` 100/10，均为完整行。1. 经真实 UI 首次确认并刷新→只计 ID-new，total110、唯一1；界面标明更早历史不在本次覆盖窗口。2. 追加 ID-next=`T0-1天` 50/5 后刷新→total165、唯一2。3. 追加 ID-bad 无效 UTC 时间 200/20 完整行→仍165、唯一2，显示 `invalid_time` 诊断。 | 新库→初次 `Q_SUM=(1,100,10,20)`，追加后 `Q_IO=(2,150,15)`，无效时间后同值；只读响应键不含 ID-old/ID-bad，`Q_DIAG` 有 `invalid_time`；重置仅本例拥有根。 | `null`；planned/unexecuted；缺 30 天窗口和 UTC 校验自动化。 |
| `TC-TM003-COVERAGE-OVERFLOW-01` / `TASK-TM003-SCAN` / product_e2e | 本例 0700 授权根初始含 1001 个可排序的 `sessions/YYYY/MM/DD/*.jsonl`，前1000个无可信用量、最后第1001个含 A=100/10/cached20；总项数低于5000，另有未授权根 B=900/90。1. 真实 UI 预览 A→显示候选上限截断/不完整，B 不出现。2. 经 UI 确认并让 TM-002 内部分页在第1页后暂停→覆盖仍不完整，尚无新事件。3. 继续到 complete 并独立读完稳定正文→末端 A 被计一次，UI total110、唯一1、覆盖可标本次已扫描完整；B 始终不可读。4. 新扫描第1页后撤销授权，旧 cursor/token 均被拒绝，UI 保留既有110、覆盖不完整，须重新确认。5. 真实 UI 重新确认后，新扫描第1页后由本例 fixture 在 A 根新增一个无可信用量的普通 JSONL，旧 generation 的 cursor/token 拒绝、暂定页/暂存结果回滚；新 generation 从头扫描，读完稳定正文前仍不完整。 | 新库→预览/中间页 `Q_SUM` 无事件且 `coverage.scan_incomplete=1`；完成后 `Q_SUM=(1,100,10,20)`、`coverage.scan_incomplete=0`；撤销和目录变动后已提交 A 保留、`scan_incomplete=1`，旧 generation 游标/token 失效；不跨授权根、不直接向事件表造数。重置仅本例拥有的初始1001文件、第5步新增文件、两根与库。 | `null`；planned/unexecuted；缺 TM-002 已确认能力下的可续扫内部分页/暂停/撤销/目录变动 fixture 和最终 App 绑定；仅有截断预览时本例 BLOCKED。 |
| `TC-TM003-UI-02` / `TASK-TM003-UI` / product_e2e | `R-BASE`、完整 A/B。1. 导入后→UI total165 且覆盖起点为最早可信事件时间。2. 删除仅本例拥有的源文件后刷新/重启→仍165；源缺失与更早历史不可证明的提示可见，不能显示历史0。 | 空库→保留2事件、`Q_IO=(2,150,15)`；`coverage.missing_before=1` 或等价状态；不删事件。 | `null`；planned/unexecuted；缺覆盖 UI/清理程序。 |

## E2E-TM003-004 · 权限边界与重新授权

**验收：** `AC-TM003-004`。本组逐项检查授权根、失效停读、重新确认补扫及 origin/account.id 隔离。

**前置/数据：** 本例自有 A/B 根、合成账号和两个动态隔离服务；上一版 TM-002 已确认能力与真实面板驱动须先具备。

**步骤：**
1. 经真实 App 对 A 选择并确认，尝试 B 与越界链接，核对主进程读取范围和客户端可信事件。
2. 使本例来源失效，追加新响应后刷新，再经真实面板重新确认同根并补扫。
3. 依次切换 O1/U1、O1/U2、O2/同 ID 成员，分别读取 UI 与隔离库主体键和游标。

**独立预期：** 失效或身份切换立即停读；恢复前 A/B total330，补入 C 并重放 A 后唯一3、total660，刷新重启不重计。未授权 B、越界链接及其他 origin/account 的事件不得混看；具体逐步预期见下表。

**绑定/证据/状态：** `draft`、`unexecuted`，程序绑定 `null`；需最终 App、原生重新选择、身份切换和真实文件/SQLite 审计，缺项 BLOCKED。

| TC / TASK / 类型 | 实际输入、前置及有序动作→逐步预期 | DB 准备→变更→只读核验；数据/重置 | 绑定与状态 |
| --- | --- | --- | --- |
| `TC-TM003-BOUNDARY-01` / `TASK-TM003-SCAN` / product_e2e | 测试拥有 A/B，B 内有 ID-x=900/90，A 的 `sessions/YYYY/MM/DD/` 同层有 symlink `escape.jsonl` 指向 B。1. 仅通过真实 UI 选 A 并确认→A 的可信事件可读。2. 手动刷新与30秒补扫→B 和越界 symlink 不被读，UI 无 x 用量。 | 空库→只出现 A 的 response key；`Q_SUM`不含990；B 的文件摘要前后不变。 | `null`；planned/unexecuted；缺 TM-002 真实授权与边界扫描。 |
| `TC-TM003-AUTH-01` / `TASK-TM003-AUTH` / product_e2e | A 含 A=100/10。1. 打开授权预览但不确认→持续扫描不启动、客户端无事件。2. 确认后→110。3. TM-002 fixture 仅使 A 授权失效，再追加 B=200/20 并刷新→卡片显示需重新授权，仍110，A 不被继续读取。 | 新库→确认前0事件；确认后 `Q_SUM=(1,100,10,20)`；失效后不变，游标不前进。 | `null`；planned/unexecuted；缺 TM-002 接口/撤销 fixture。 |
| `TC-TM003-AUTH-02` / `TASK-TM003-AUTH` / product_e2e | A 已通过真实 UI 授权且含 A=100/10、B=200/20。1. 采集后→330、唯一2。2. 失效期间追加 C=300/30 与重放 A→仍330。3. 从真实 UI 重新授权同根并确认→660、唯一3。4. 刷新并重启→仍660。 | 空库→`Q_SUM`依次 `(2,300,30,60)`、同值、`(3,600,60,120)`、同值；重复 A 不插入。 | `null`；planned/unexecuted；缺联合权限/日志 fixture。 |
| `TC-TM003-ISOLATION-01` / `TASK-TM003-AUTH` / product_e2e | 两个隔离真实服务 O1/O2；O1 上合成成员 U1/U2，O2 上合成 U1b（账号 ID 与 U1 相同），根 A 含固定 ID-a=100/10。1. 登录 O1/U1、真实 UI 确认 A 并刷新→U1 total110。2. 退出 U1 并登录 O1/U2，确认前→无可读来源，卡片显示尚无可信历史/待确认，不显 U1 的110。3. U2 经真实 UI 另行确认 A 并刷新→U2 自己 total110；U1 事件仍独立。4. 退出并通过真实配置 UI 切换到 O2，登录 U1b，确认前→无可读来源、不显 O1 的110。5. 返回 O1/U1，按 TM-002 状态恢复或真实重新确认 A 后刷新→U1仍唯一1、total110，未因 U2 的采集重计。 | 新库→主体键分别为 HMAC(O1,U1)、HMAC(O1,U2)、HMAC(O2,U1b)；`Q_SUM(P1)=(1,100,10,20)`、`Q_SUM(P2)=(1,100,10,20)`、`Q_SUM(P3)`无行，`source_cursor` 仅 P1/P2 各自所属行；各转换点不得继续用旧能力读。仅清理本例拥有 profile/根/两服务。 | `null`；planned/unexecuted；缺 TM-002 已确认来源能力、身份切换通知及双服务 fixture。 |

## 迁移、执行器与发布追踪

| TC / TASK / 类型 | 实际输入、前置及有序动作→逐步预期 | DB 准备→变更→只读核验；数据/重置 | 绑定与状态 |
| --- | --- | --- | --- |
| `TC-TM003-MIGRATE-01` / `TASK-TM003-MIGRATE` / product_e2e | 上一实际稳定版 TM-002 私有 profile，包含合成账号、已确认授权根与原有 schema；该版尚无采集事件，若无稳定版包则 BLOCKED。1. 在本轮隔离根备份并验证可恢复→旧 schema、账号/授权状态有摘要且无 `usage_event`。2. 经 App 内真实更新到候选→新 schema 建立，账号/授权保留，卡片显示尚无可信历史；向已授权根追加固定 A=100/10 后刷新→唯一1、total110。3. 在另一拥有副本注入迁移中断并重试→中断可检测，恢复旧 profile 后重试可得相同账号/授权与唯一 A，不重复计。 | 只在隔离副本造旧状态；源库只读核对旧 schema、账号/授权记录与无用量表；更新后 `Q_SCHEMA` 为目标版本、`Q_SUM` 先无行、采集 A 后为 `(1,100,10,20)`，账号/授权记录不变；不接触生产库。 | `null`；planned/unexecuted；缺上一稳定包与迁移程序。 |
| `TC-TM003-E2E-01` / `TASK-TM003-E2E` / governance | 1. 用固定单例入口指定一个 TM-003 TC→新 run_id，逐步原件和 SQL/源摘要齐全。2. 对 TM-001 已交付集合加 TM-003 全部目标 TC/四组补充运行→逐 TC/变体与场景组均有独立原件、零缺例/跳过/重试，门禁集合不再固定只含 TM-001。3. 故意移除副本报告一步→审计判 BLOCKED。4. 在副本移除一条 TM-003 TC 或把变体清单 release 设成 TM-001→跨版本门禁拒绝该副本，不生成通行证。 | 使用测试拥有的独立库，审计只读原件；不生成假 PASS。 | `null`；planned/unexecuted；缺程序和包。 |
| `TC-TM003-E2E-02` / `TASK-TM003-E2E` / product_e2e | 1. 从最终候选 DMG 复制并安装 App→记录原件/安装路径与哈希。2. 用 Playwright executablePath 启动→真实 UI/IPC/采集/服务/SQLite 全链且 TM-001/002/003 应测集合精确相等。3. 退出并按 owner 清理→无遗留进程/端口/私有目录。 | 每例隔离客户端/服务库；最终 DB 与逐 TC 预期相符；包、源码、测试摘要一致。 | `null`；planned/unexecuted；缺最终 DMG 和集成链。 |
| `TC-TM003-GOV-01` / `TASK-TM003-RELEASE` / governance | 1. 核对 manifest/需求→TASK→TC/AC、数据能力、Changelog、总表→零孤立或空预期。2. 运行 structure/baseline/quality 与总表回读→全部真实返回0才记录文档基线。3. 用候选原始报告门禁→任一 FAIL/BLOCKED 拒绝通行证。 | 对数据库不适用；使用机器清单、结果 Excel 与原件摘要，不代写产品库。 | `null`；planned/unexecuted；缺本版完整程序。 |

## 产品逐步观察面

以下观察面与上方同 ID 的输入、动作、独立总量预期共同构成逐步判据；`不适用` 均说明本步不观察该层的原因。数据库查询只对本例拥有的隔离库只读执行，文件检查只涉及 owner 收据列出的路径。

| TC | 步 | UI 预期 | API/数据库/进程预期 | 文件/来源预期 |
| --- | --- | --- | --- | --- |
| TC-TM003-PARSE-01 | 1 | 卡片显示 input100/output10/total110、cached read20、cache write5、reasoning3、唯一1 | Q_SUM=(1,100,10,20)，Q_SUB=(5,3)，Q_NULL=0 | 授权根中 A 的 token_usage_record 完整行以 LF 结束，源字节 SHA 与本例 owner 收据一致 |
| TC-TM003-PARSE-01 | 2 | 卡片显示 input600/output60/total660、cached read120、cache write30、reasoning18、唯一3 | Q_SUM=(3,600,60,120)，Q_SUB=(30,18)，Q_NULL=0；累计快照不入事件表 | 授权根中 A/B/C 三条完整逐响应行的摘要与 owner 收据一致，原始文件未被 App 改写 |
| TC-TM003-SCAN-01 | 1 | 每次补扫后卡片 total 依次110、330、660，唯一响应依次1、2、3 | 每批 Q_SUM 依次 (1,100,10,20)、(2,300,30,60)、(3,600,60,120)；Q_CURSOR 每次停在末条 LF 后 | 本例源文件三次追加的完整行数依次1、2、3，字节摘要与各阶段 owner 收据一致 |
| TC-TM003-SCAN-01 | 2 | 手动刷新及重启后卡片仍 total660、唯一3 | Q_SUM 仍 (3,600,60,120)，Q_CURSOR 不越过第三条完整行 | 刷新和重启前后源文件 SHA-256 不变，App 不改写日志 |
| TC-TM003-SCAN-01 | 3 | 同根移动并刷新后卡片仍 total660、唯一3 | Q_SUM 仍 (3,600,60,120)，移动后的游标只在授权根内，响应键集合不变 | 原位置不再有该文件，新位置在同一已授权根内，移动前后文件 SHA-256 相同 |
| TC-TM003-STORE-01 | 1 | 卡片 total110、唯一1 | Q_SUM=(1,100,10,20)；事件和 Q_CURSOR 在同一已提交状态 | A 完整行以 LF 结束，源 SHA 与本例 owner 收据一致 |
| TC-TM003-STORE-01 | 2 | 重启后卡片恢复 total110、唯一1 | Q_SUM=(1,100,10,20)，Q_CURSOR 保留 A 的完整行边界 | 重启前后源文件 SHA-256 不变，私有客户端 SQLite 文件仍可打开 |
| TC-TM003-STORE-01 | 3 | 重复同 ID 的 A 后卡片仍 total110、唯一1 | Q_SUM=(1,100,10,20)，同 ID 仅一事件，Q_CURSOR 前进到第二条完整行尾 | 本例源文件新增一条完整重复 A 行，首条原始字节不变 |
| TC-TM003-STORE-01 | 4 | 卡片保留 total110、唯一1，显示 identity_secret_unavailable 与覆盖不完整；B 不显示 | Q_SUM=(1,100,10,20)，Q_CURSOR 不越过重复 A 行，coverage.scan_incomplete=1；密钥错误不作零值 | 只操作本例身份密钥项/文件，owner/摘要收据不含密钥；A 原始行不变，B 已追加完整 LF；生产密钥项未访问 |
| TC-TM003-STORE-01 | 5 | 卡片 total330、唯一2，诊断解除；稳定正文扫描完成后覆盖完整 | Q_SUM=(2,300,30,60)，原 A source_event_key 不变、B 新增一次，Q_CURSOR 至 B 行尾，coverage.scan_incomplete=0 | 本例原密钥摘要与准备收据一致，A/B 完整 LF/摘要与 owner 收据一致；生产 profile 与密钥项摘要不变 |
| TC-TM003-UI-01 | 1 | 采集前卡片显示等待采集/尚无可证明历史，不显示已知0 | usage_event 无行；coverage 不得表示已完成可信扫描 | 本例授权源尚无完整可计量用量行，未创建伪造的零用量记录 |
| TC-TM003-UI-01 | 2 | 卡片显示 input600/output60/total660、cached read120、cache write30、reasoning18、唯一3及 UTC 最后采集时间 | Q_SUM=(3,600,60,120)，Q_SUB=(30,18)，Q_NULL=0；last_scan_at_utc 为有效 UTC | A/B/C 三条 LF 完整行的源摘要与本例 owner 收据一致 |
| TC-TM003-UI-01 | 3 | 卡片可信 total 仍660，显示缺字段/不支持来源诊断；未知 cached 不显示成0 | Q_SUM 仍 (3,600,60,120)，无第四可信事件；Q_DIAG 记录缺字段或不支持版本 | 额外一条缺 cached_input_tokens 的完整行来自显式非支持版本测试文件；原 A/B/C 源字节不变 |
| TC-TM003-PARSE-02 | 1 | 卡片 total110、唯一1 | Q_SUM=(1,100,10,20) | 合法 A 完整行以 LF 结束，源 SHA 与 owner 收据一致 |
| TC-TM003-PARSE-02 | 2 | 卡片仍 total110、唯一1，分别显示 missing_usage、negative_input、invalid_cached、invalid_total 诊断 | Q_SUM 仍 (1,100,10,20)；四种 Q_DIAG 各至少1；无对应四个新事件 | 源文件另有四条不同 ID 的 LF 完整负例行，字节摘要与生成收据一致且原 A 未改写 |
| TC-TM003-MODEL-01 | 1 | 卡片 total11、唯一1，模型显示 gpt-6-sol | Q_IO=(1,10,1)；ID-m 的 model_id 为 gpt-6-sol | 原生形状 turn_context 与 ID-m 的 token_usage_record 具有相同 turn_id，完整行与摘要固定 |
| TC-TM003-MODEL-01 | 2 | 卡片 total22、唯一2，模型显示原样 model-x | Q_IO=(2,20,2)；ID-n 的 model_id 原样为 model-x | 新 turn_context 的 model 字段为 model-x，ID-n 同 turn_id；两行以 LF 结束 |
| TC-TM003-MODEL-01 | 3 | 卡片 total33、唯一3，第三个模型标为未知 | Q_IO=(3,30,3)；ID-o 的 model_id IS NULL；Q_DIAG 含 unknown_model | ID-o 完整逐响应行存在，但源文件没有与其 turn_id 匹配的 turn_context |
| TC-TM003-DEDUP-01 | 1 | 卡片 total110、唯一1 | Q_SUM=(1,100,10,20) | ID-a 的首条完整原生日志行及摘要固定 |
| TC-TM003-DEDUP-01 | 2 | 卡片仍 total110、唯一1 | Q_SUM 仍 (1,100,10,20)，ID-a 仅一事件 | 第二条 ID-a 原始用量/模型与首条相同，均为完整行 |
| TC-TM003-DEDUP-01 | 3 | 卡片 total220、唯一2 | Q_SUM=(2,200,20,40)，事件键含 ID-a 与 ID-b 的两个不可逆摘要 | ID-b 是第三条完整行，数值同 ID-a 而 response_id 不同 |
| TC-TM003-DEDUP-01 | 4 | 卡片仍 total220、唯一2，并显示 identity_conflict | Q_SUM 仍 (2,200,20,40)，ID-a 首事件不覆写；Q_DIAG 含 identity_conflict | 第四条完整行复用 ID-a，但 usage 明确为 999/99；前三条原始字节不变 |
| TC-TM003-BRANCH-01 | 1 | 卡片可信 total165、唯一2 | Q_IO=(2,150,15)；累计 token_count 快照不另入事件表 | 主会话文件有 A/B 两条逐响应完整行与100/10、150/15累计快照，SHA 与收据一致 |
| TC-TM003-BRANCH-01 | 2 | 卡片可信 total198、唯一3 | Q_IO=(3,180,18)，独立新会话 ID 只新增30/3 | 新会话源文件与主文件不同，含一条30/3的完整逐响应行 |
| TC-TM003-BRANCH-01 | 3 | 卡片可信 total220、唯一4，重放父 A 后仍220 | Q_IO=(4,200,20)；fork C 只新增20/2，重放 A 不新增键 | fork 子文件仅有新 C 逐响应行、forked_from_id 指父且 thread 累计170/17；另一个文件的人为父 A 重放明确标为负例 |
| TC-TM003-BRANCH-01 | 4 | 卡片仍 total220、唯一4，显示 unverified_cumulative 与 unknown_format | Q_IO 仍 (4,200,20)；Q_DIAG 同时含两种诊断 | 额外完整行仅有无身份累计回退或未知结构，未包含可计量 response_id/usage |
| TC-TM003-PRIVACY-01 | 1 | 卡片只显示合法 A 的 total110、唯一1，不展示哨兵文本/代码/完整路径 | Q_SUM=(1,100,10,20)；usage_event 只保留白名单用量与不可逆键，文本哨兵字段不入库 | 本例 A=100/10 完整行的非用量文本字段包含固定合成哨兵、代码片段和合成路径；仅测试拥有源含这些原文 |
| TC-TM003-PRIVACY-01 | 2 | 不适用：App 已退出，本步读取 SQLite/WAL/报告字节而不操作 UI | SQLite/WAL/采集报告的受控字节扫描均不含哨兵、代码片段或完整路径；Q_SUM 仍 (1,100,10,20) | 仅检查本例拥有的 SQLite、WAL 和报告文件；扫描输入文件摘要留证，不扫描真实用户目录 |
| TC-TM003-SCAN-02 | 1 | 卡片 total110、唯一1 | Q_SUM=(1,100,10,20)；Q_CURSOR 停在 A 的 LF 后 | 源文件只有 A 一条 LF 完整行，SHA 与 owner 收据一致 |
| TC-TM003-SCAN-02 | 2 | 卡片仍 total110、唯一1，不出现 B 用量 | Q_SUM 仍 (1,100,10,20)；Q_CURSOR 仍在 A 的 LF 后 | B 仅写前半字节且没有 LF；源文件末端 SHA/长度与半行阶段收据一致 |
| TC-TM003-SCAN-02 | 3 | 补齐和重启后卡片 total165、唯一2 | Q_IO=(2,150,15)；Q_CURSOR 前进至 B 的 LF 后；B 仅一事件 | B 余字节与 LF 已追加，源文件恰有 A/B 两条完整行且摘要与完成阶段收据一致 |
| TC-TM003-SCAN-03 | 1 | 卡片 total165、唯一2 | Q_IO=(2,150,15)；Q_CURSOR 在 B 完整行尾 | 源文件 A/B 两条 LF 完整行，摘要与 owner 收据一致 |
| TC-TM003-SCAN-03 | 2 | 卡片仍 total165、唯一2，已采集 B 不消失 | Q_IO 仍 (2,150,15)；Q_CURSOR 重置到当前 A 的 LF 后 | 仅本例源文件被截断为 A 一条完整行，B 字节已从源文件移除；其他拥有文件摘要不变 |
| TC-TM003-SCAN-03 | 3 | 刷新和重启后卡片 total495、唯一3 | Q_IO=(3,450,45)；A/B/C 各一事件，Q_CURSOR 在新 C 完整行尾 | 截断后的 A 行后新增 ID-C=300/30 完整行；A 源字节与截断阶段相同 |
| TC-TM003-WINDOW-01 | 1 | 只计 ID-new：total110、唯一1；显示更早历史不在覆盖窗口 | Q_SUM=(1,100,10,20)，响应键不含 ID-old | 首次确认前源文件有 ID-old=T0-31天 与 ID-new=T0-29天 两条 LF 完整行；时间字段与本次 T0 收据一致 |
| TC-TM003-WINDOW-01 | 2 | total165、唯一2 | Q_IO=(2,150,15) | 同一拥有根新增 ID-next=T0-1天 完整行，旧两行原始字节不变 |
| TC-TM003-WINDOW-01 | 3 | 仍 total165、唯一2，显示 invalid_time 诊断 | Q_SUM 不变；Q_DIAG 有 invalid_time，响应键不含 ID-bad | 源文件新增 ID-bad 无效 UTC 时间的完整行；前三行原始字节不变 |
| TC-TM003-COVERAGE-OVERFLOW-01 | 1 | 预览明确候选上限与覆盖不完整；B 不出现 | Q_SUM 无可信事件；coverage.scan_incomplete=1 | 已授权 A 根恰有1001个可排序普通 JSONL，前1000个无可信用量、第1001个含 A=100/10；未授权 B 独立且摘要不变 |
| TC-TM003-COVERAGE-OVERFLOW-01 | 2 | 覆盖仍不完整，不报告全量完成 | Q_SUM 无可信事件；coverage.scan_incomplete=1 | 暂停时1001个候选文件的数量与 SHA 未变；第1页最多256个相对名称，末端 A 尚未打开 |
| TC-TM003-COVERAGE-OVERFLOW-01 | 3 | total110、唯一1，覆盖可标本次扫描完整；B 始终不可读 | Q_SUM=(1,100,10,20)；coverage.scan_incomplete=0 | 第1001个 A 文件 SHA 与 owner 收据一致；候选页 complete 且该文件正文完整 LF、读前后身份/大小/mtime 稳定；B 文件 SHA 不变且未被打开 |
| TC-TM003-COVERAGE-OVERFLOW-01 | 4 | UI 仍110、唯一1，覆盖不完整，必须重新确认 | 旧 cursor/token 均拒绝；Q_SUM=(1,100,10,20)；coverage.scan_incomplete=1 | 撤销后源文件不变，旧 cursor/candidateToken 只作拒绝请求；无源文件被旧能力继续打开 |
| TC-TM003-COVERAGE-OVERFLOW-01 | 5 | 目录变动后仍 total110、唯一1；覆盖不完整，新一代读完正文前不报告完成 | 旧 generation cursor/token 拒绝，暂存事件/游标回滚；Q_SUM=(1,100,10,20)，coverage.scan_incomplete=1；新 generation 从头扫描 | A 根由1001变为1002个普通 JSONL，新文件归本例所有且无可信用量；变动前后目录身份/mtime/ctime 与文件摘要留原件，旧能力无后续打开记录 |
| TC-TM003-UI-02 | 1 | 卡片 total165、唯一2，并显示最早可信事件的 UTC 覆盖起点 | Q_IO=(2,150,15)；coverage.earliest_verified_at_utc 等于本例最早可信事件时间 | 本例源文件包含 A/B 两条 LF 完整行，摘要与 owner 收据一致 |
| TC-TM003-UI-02 | 2 | 刷新和重启后卡片仍 total165、唯一2，并显示源缺失及更早历史未核实 | Q_IO 仍 (2,150,15)；coverage.missing_before=1 或等价缺口状态 | 仅本例拥有的源文件已删除；非本例文件与目录 SHA/归属不变 |
| TC-TM003-BOUNDARY-01 | 1 | 选择并确认 A 后卡片只显示 A 中可信用量，不显示 B 的 ID-x | usage_event 只有 A 响应键；B 的 ID-x 不入库 | 真实系统选择器只选 A；A 根含越界 symlink，未授权 B 内 ID-x=900/90 文件 SHA 与准备收据一致 |
| TC-TM003-BOUNDARY-01 | 2 | 刷新与30秒补扫后卡片仍无 B 的 990 token | Q_SUM 不含 B 的 900/90，Q_DIAG 可记录越界拒绝但无 ID-x 事件 | 越界 symlink 仍指向 B，B 文件 SHA 前后相同；测试读请求证据不含 B 打开记录 |
| TC-TM003-AUTH-01 | 1 | 预览显示候选但状态仍待确认，卡片无已采集可信量 | usage_event 无行、source_cursor 无已提交采集游标 | A 有 A=100/10 完整行但只作为候选预览，文件 SHA 与准备收据一致 |
| TC-TM003-AUTH-01 | 2 | 确认后卡片 total110、唯一1 | Q_SUM=(1,100,10,20)；游标提交到 A 完整行尾 | A 原始 SHA 与确认前一致；App 只读该授权根 |
| TC-TM003-AUTH-01 | 3 | 卡片显示需要重新授权，仍 total110、唯一1 | Q_SUM 仍 (1,100,10,20)，Q_CURSOR 不越过 A 完整行 | 失效后 A 中已追加 B=200/20 完整行，但本轮读取证据无 B 打开/消费；源 SHA 与追加收据一致 |
| TC-TM003-AUTH-02 | 1 | 卡片 total330、唯一2 | Q_SUM=(2,300,30,60) | A 根已含 A/B 两条完整行，摘要与 owner 收据一致 |
| TC-TM003-AUTH-02 | 2 | 失效期间卡片仍 total330、唯一2，并显示待重新授权 | Q_SUM 仍 (2,300,30,60)，Q_CURSOR 不越过失效前 B 行尾 | 失效期间 A 根追加 C=300/30 和重复 A 两条完整行，读取证据无新行被旧能力打开 |
| TC-TM003-AUTH-02 | 3 | 真实重新确认后卡片 total660、唯一3 | Q_SUM=(3,600,60,120)；C 新增一次、重复 A 不新增 | 源文件仍含 A/B/C/重复 A 四条完整行，App 只在新能力下只读该根 |
| TC-TM003-AUTH-02 | 4 | 刷新和重启后卡片仍 total660、唯一3 | Q_SUM 仍 (3,600,60,120)，无第二 A 或 C 事件 | 重启前后源文件 SHA-256 不变，已确认私有 locator 可恢复或按 TM-002 合同要求真实重选 |
| TC-TM003-ISOLATION-01 | 1 | U1 卡片 total110、唯一1 | Q_SUM(P1)=(1,100,10,20) | A 根固定 ID-a=100/10 完整行，SHA 与本例 owner 收据一致；P1 的确认仅指向该根 |
| TC-TM003-ISOLATION-01 | 2 | 无可读来源，显示尚无可信历史/待确认；不显 U1 的110 | Q_SUM(P2) 无行；P1 原行保留，P1 游标未前进 | A 源文件 SHA 不变；U2 未取得 A 的已确认能力，旧 U1 句柄关闭 |
| TC-TM003-ISOLATION-01 | 3 | U2 自己 total110、唯一1 | Q_SUM(P2)=(1,100,10,20)，Q_SUM(P1)不变；两主体游标独立 | 同一 A 文件 SHA 不变；U2 经真实选择器另行确认后才可打开该文件 |
| TC-TM003-ISOLATION-01 | 4 | 无可读来源，不显 O1 的110 | Q_SUM(P3) 无行，P1/P2不变；无 P3 游标 | O2 登录阶段 A 文件 SHA 不变；P3 未取得任何来源能力，原 O1 句柄关闭 |
| TC-TM003-ISOLATION-01 | 5 | U1仍 total110、唯一1 | Q_SUM(P1)仍 (1,100,10,20)，无第二 ID-a；P2不变 | 回到 O1/U1 后 A 文件 SHA 不变；只复用或真实重选 P1 所属授权根，不打开其他主体根 |
| TC-TM003-MIGRATE-01 | 1 | 不适用；备份阶段不启动候选 UI | 旧 schema、账号/授权记录摘要与无 usage_event 的结果独立留存 | 上一稳定版私有 profile 与备份副本 SHA 分别留证；备份位于本例 0700 根，生产 profile 未触碰 |
| TC-TM003-MIGRATE-01 | 2 | 更新后先显示尚无可信历史；刷新后唯一1、total110 | 目标 Q_SCHEMA 成立；账号/授权记录不变；Q_SUM 从无行到 (1,100,10,20) | 已安装候选 App/升级源摘要与 manifest 一致；授权根只新增 A=100/10 完整行，旧 profile 备份 SHA 不变 |
| TC-TM003-MIGRATE-01 | 3 | 恢复后授权状态一致、唯一 A 且 total110 | 中断记录可查；恢复账号/授权一致，Q_SUM=(1,100,10,20) 且无重复响应 | 中断副本与恢复副本各自独立；恢复使用第1步已核 SHA 的备份，最终 profile 文件可打开且源 A 未被重复改写 |
| TC-TM003-E2E-02 | 1 | 不适用：此步仅安装最终候选包，尚未启动 App UI | 不适用：安装阶段不启动客户端或服务、不访问数据库 | DMG 原件、复制的 App 和安装位置均在本例拥有目录；记录包 SHA、签名/路径及候选 manifest 一致 |
| TC-TM003-E2E-02 | 2 | Playwright 启动的是安装后 Electron App，目标 TM-003 与已交付 TM-001/002 逐 TC 的真实 UI 断言均通过 | 目标加历史每条 TC/变体/步骤的服务与隔离 SQLite 旁证齐全，集合与 manifest 精确相等，无缺例/跳过/重试 | App executablePath 指向从该 DMG 安装的二进制，包/源码/测试摘要与本次原始 trace/报告引用一致 |
| TC-TM003-E2E-02 | 3 | 不适用：App 已退出，清理阶段不再操作 UI | 本例进程与动态端口均已停止，独立服务/客户端库清理仅按 owner 收据；原始报告保留 | 本例拥有的临时安装/profile/源目录按 owner 清理；原始报告与包证据仍在不可覆盖的本地 run 目录 |

## 无授权依赖的解析与身份开发切片

以下三个辅助 TC 只检查私有合成字节、纯解析结果和本例拥有的临时 SQLite；不启动 App、不调用 TM-002 目录能力或产品 profile/Keychain。它们把 `TC-TM003-PARSE-01/PARSE-02/DEDUP-01` 的输入与独立预期固定为可先编写的模块测试，不能代填对应产品 TC 的 UI、IPC、授权、正式存储或最终包结果。数据使用 seed303、固定 `T0=2026-10-01T06:00:00Z`、官方已核验的 `0.158.0-alpha.2.1` 原生字段形状；每例新建测试拥有的 0700 临时根，固定 expected 在测试源码内显式声明，原始研究文件不作为程序绑定。测试结束仅清理 owner 收据所列文件。当前同树程序与运行入口已绑定；既有模块运行仍归属各自原候选，绑定变更后的整合候选须另起 run。

| TC / TASK / 类型 | 输入与有序动作 | 每步独立预期及 DB 操作 | 绑定与状态 |
| --- | --- | --- | --- |
| `TC-TM003-CORE-01` / `TASK-TM003-PARSE` / source_check | 1. 在私有文件写 A=100/10/cached20 的完整 `token_usage_record` LF 行并调用模块解析入口。2. 只追加 B=200/20/cached40 的前半字节、无 LF，再解析。3. 补齐 B 与 LF，追加 C=300/30/cached60 与仅含累计快照的两条完整 LF 行，再解析并复扫。 | 1. 返回 A 一事件、`input=100/output=10/total=110/cached=20`，完成偏移恰在 A 的 LF 后。2. 仍只有 A，完成偏移不跨半行。3. 仅 A/B/C 三个不同响应，`input=600/output=60/total=660/cached=120`；累计快照与复扫不增量，完成偏移在累计快照行的 LF 后。无产品 DB 写入；只核对解析输出、源字节摘要和临时文件长度，重置为本例新根。 | `tm003-core.test.ts` / `tm003-core`；原候选模块PASS，整合候选待新run；产品 PARSE-01/SCAN-02 仍BLOCKED。 |
| `TC-TM003-CORE-02` / `TASK-TM003-SOURCE`, `TASK-TM003-PARSE` / source_check | 1. 输入只有无响应 ID 的累计100/10与 `info=null` rate-limit 行。2. 输入合法 A，再分别输入缺 `usage`、负 input、cached111>input100、total111 四条不同 ID 的完整 LF 行。3. 输入未知 build 的完整记录。 | 1. 零可信事件，分别诊断 `unverified_cumulative`、`missing_usage`，不生成零值事件。2. 只有 A=110 一事件；四条负例依次产生 `missing_usage`、`negative_input`、`invalid_cached`、`invalid_total`，不覆写 A。3. 零新增事件、`unsupported_source_version`。无产品 DB 写入；独立枚举事件和诊断代码/数量，重置为本例新根。 | `tm003-core.test.ts` / `tm003-core`；原候选模块PASS，整合候选待新run；产品 SOURCE-02/PARSE-02 仍BLOCKED。 |
| `TC-TM003-CORE-03` / `TASK-TM003-IDENTITY` / source_check | 1. 用公开身份向量的32字节测试 key，经正式身份函数处理 `codex/provider-response/shared-call-01` 的 A=100/10/cached20，并写入本例临时 SQLite。2. 同 ID、同 usage 重放；再写不同 ID `shared-call-02`、相同 usage。3. 同 `shared-call-01` 写999/99冲突值；另用相同字面 `shared-call-01` 但 `claude_code/provider-message` 求键。 | 1. 一个可信事件、total110，键精确为 `afd67bd0cad0227b3e7b5ac132bb9b3ed492073983b9c16a0c9cc24dd3008051`。2. 重放后仍一个事件；新 ID 后两个事件，`input=200/output=20/cached=40/total=220`。3. 首事件不变、诊断 `identity_conflict`；跨来源键精确为 `bf222a85ab2209f72ff82c21b7172c9315448b3e1d5bf4503a3c76b30c46cad1`，不在本例产品库中添加 Claude 事件。DB 准备是测试拥有的空 SQLite；只通过正式模块 API 插入，不直接 SQL 造事件；只读核对唯一约束、两行总量和诊断，结束只清理本例 DB。 | `tm003-core.test.ts` / `tm003-core`；原候选模块PASS，整合候选待新run；产品 DEDUP-01/NAMESPACE-01 仍BLOCKED。 |

## 无授权依赖的存储与游标开发切片

固定输入为[tm003-core-storage-cursor.json](../../../tests/fixtures/tm003-core-storage-cursor.json)，seed303、已核验Codex版本、公开测试密钥`000102…1f`与另一有效密钥`202122…3f`。fixture的header+A、header+A+B、header+A+B+C完整LF长度分别为410、750、1090字节，原始字节及SHA在fixture；A/B/C分别为100/10/cached20、200/20/cached40、300/30/cached60。每例使用新建的0700 owner根、0600临时客户端SQLite，不读取TM-002已授权根、真实profile、Keychain或服务。输入事件只由该fixture的正式解析模块产生，测试不得直接SQL造`usage_event`；测试SQL仅可注入本例库的失败触发器和只读核对。每一步运行前程序固定预期和断言，输出`source_check`逐步结果与清理原件；CORE-04/05当前分别绑定`tm003-core45.test.ts`同一suite，原候选模块PASS，整合候选待新run。

### TC-TM003-CORE-04 · 同步批次原子提交与密钥标记

**TASK：** `TASK-TM003-STORE`。**AC：** `AC-TM003-002`, `AC-TM003-003`。**类型：** `source_check`。**输入：** fixture的header、A/B两条完整LF，两个明确不同的有效32字节测试密钥；本例空库。模块批次须在同一同步SQLite事务里写可信事件、诊断、`source_cursor`、`coverage`及首次密钥标记；批次不得返回未提交成功状态后再异步补写游标。

| 步骤 | 固定动作 | 每步预期、DB只读判据 |
| --- | --- | --- |
| 1 | 用key1解析并提交header+A，`source_cursor`定位410字节及其keyed prefixMAC，覆盖暂记`scan_incomplete=1`。 | `usage_event`只一条A；只读`COUNT/SUM(input)/SUM(output)/SUM(cached)`为`(1,100,10,20)`、total110；诊断0；游标410、前缀MAC非空、`identity_key_state`为key1标记，覆盖不完整。关闭重开同库后读值相同。 |
| 2 | 只在本例库创建分别针对`source_cursor` INSERT和UPDATE的`BEFORE`触发器，触发`RAISE(ABORT,'cursor_fail')`；用key1提交B=200/20/cached40、一个固定`invalid_record`诊断、游标750及覆盖完成。 | 批次返回失败而非部分PASS；`usage_event`仍仅A、总量110、诊断仍0、游标仍410及原prefixMAC、`coverage.scan_incomplete=1`、密钥标记未变；关闭重开后仍相同。触发器仅属本例故障注入，不进入产品库。 |
| 3 | 删除本例两个触发器，重试同一B批次。 | B只新增一次；只读`(COUNT,input,output,cached)=(2,300,30,60)`、total330、`invalid_record`诊断恰1、游标750及新prefixMAC、`scan_incomplete=0`；重启同库不重计。 |
| 4 | 使用不同且有效的key2尝试重新打开/提交同一A及C；不得重建空库或借无效key长度拒绝。 | 明确返回密钥标记不匹配并停止采集；既有A/B两行、total330、诊断1、游标750、覆盖与key1标记逐项不变；不生成key2新事件键，不把停采集写成已知零。 |

**DB与重置：** 准备空owner SQLite；测试触发器只为步骤2创建和步骤3删除，不直接插入业务行。每步只读`usage_event`按本例主体求数量及四项SUM、`collection_diagnostic`按代码求数、`source_cursor.committed_byte_offset/prefix_mac`、`coverage.scan_incomplete`和`identity_key_state.key_marker`；精确主体/源键由固定测试向量生成，不保留原路径。步骤4后只清理本例拥有的文件与库，保存原始报告；产品`STORE-01`、身份恢复与App E2E仍BLOCKED。

### TC-TM003-CORE-05 · 追加、半行、前缀改写与截短游标

**TASK：** `TASK-TM003-SCAN`、`TASK-TM003-STORE`。**AC：** `AC-TM003-001`, `AC-TM003-003`。**类型：** `source_check`。**输入：** 同fixture的header/A/B/C及将A行`padding`从`0`换为`1`的同长度改写，测试持有的已打开文件句柄、同一合成稳定文件身份和独立的可变快照digest。稳定身份在本模块由测试固定，不推断TM-002生产digest合同。

| 步骤 | 固定动作 | 每步预期、DB只读判据 |
| --- | --- | --- |
| 1 | 写header+A完整LF并用key1扫描/同步提交。 | 只一条A、total110、游标410；保存对410字节的keyed prefixMAC及稳定身份；输出不含原始路径/正文/密钥。 |
| 2 | 原句柄只追加B的前半行而不写LF；故意更新可变快照digest，保持稳定身份。 | B不提交，`COUNT=1`、total110、游标仍410；已提交410字节prefixMAC相同，不能因可变digest变化报`cursor_reset`。 |
| 3 | 补齐B并写LF，随后追加C完整LF，保持稳定身份、再次改变可变digest。 | 只消费从410字节开始的B/C完整行；游标1090、`(COUNT,input,output,cached)=(3,600,60,120)`、total660；A不重计，无`cursor_reset`。 |
| 4 | 在已读前缀把A行无业务意义的`padding`字节`0`原地改为`1`，保持文件长度1090和mtime不变，稳定身份仍相同；重新扫描。 | fixture改写后SHA与原SHA不同、长度相同；keyed prefixMAC不符，必须报`cursor_reset`并从0重扫。A/B/C同原生ID与用量只各保留一条，total仍660；旧可信行不删，`coverage.missing_before=1`或同义持久缺口状态，不能声称历史完整。 |
| 5 | 将同一本例文件截短到header+A的410字节，再扫描。 | 当前长度小于游标，重新从0扫描并保持三条历史可信事件、total660；游标回到410、覆盖缺口继续为真，不将缺失的B/C写0或删除。 |

**DB与重置：** 所有事件只经正式模块同步入口写测试拥有的SQLite；只读核对按`(principal_key,source,source_event_key)`唯一三行、总量、`source_cursor`偏移及prefixMAC、`coverage`缺口/完成状态、重置诊断，不直接造数。步骤4同长度/同mtime改写专门证明只凭mtime/size或可变快照digest均不能代替已提交前缀MAC；步骤2/3反证普通追加不是历史改写。结束仅清理本例owner根/库。TM-002能力、真实授权、App及产品`SCAN-02/03`仍BLOCKED。

### TC-TM003-CORE-06 · 多文件代际一次提交与全回滚

当前同树绑定：`tm003-core06.test.ts` / `tm003-core06`；原候选模块PASS，整合候选待新run。

**TASK：** `TASK-TM003-SCAN`、`TASK-TM003-STORE`。**AC：** `AC-TM003-001`, `AC-TM003-003`。**类型：** `source_check`。**输入：** 固定[tm003-core-generation.json](../../../tests/fixtures/tm003-core-generation.json)引用同源原始行：合成file-a=`header+A`与file-b=`header+B`各410字节，分别SHA预置；两页属于同一generation，第1页`complete=false`只交file-a，末页`complete=true`交file-b。仅使用本例已打开合成句柄/假scan capability、固定公开key1、owner 0700根/0600空SQLite。两个文件都先有可信A/B的解析候选，但不能逐文件提交；每次独立试验从新空库/代际开始。

| 步骤 | 固定动作 | 每步预期、DB只读判据 |
| --- | --- | --- |
| 1 | 读取第1页file-a并验证完整LF、来源版本、字节SHA，但让末页尚未到达；检查库和暂存态。 | 模块可暂存A=100/10/cached20，`commitScanBatch`调用0次；`usage_event/source_cursor/collection_diagnostic/coverage`四表均无本代际行，不能把`complete=false`宣称历史完整。暂存只保留在本例内存，取消即清空。 |
| 2 | 从新空库重建同一两页并验证两个文件正文稳定，末页`complete=true`；仅在本例库安装`source_cursor`第二次INSERT时`RAISE(ABORT,'second_cursor_fail')`触发器，guard通过后调用一次同步`commitScanBatch`。 | 批次明确失败；事务回滚两个事件、两个游标、诊断、覆盖与首次密钥标记，五处本代际行/标记均为0/不存在；关闭重开库仍全空，不能留下第一文件A或`scan_incomplete=0`。故障注入只在owner库，删除触发器后再试。 |
| 3 | 再从新空库生成完整稳定两页；在file-b正文SHA校验后、guard/事务前由假capability发出撤权或cancel，并请求结束扫描。 | guard拒绝或取消，`cancelScan`被调用，`commitScanBatch`调用0次；A/B暂存被清空，事件/两个游标/诊断/覆盖/密钥标记均未提交。此模拟仅验证模块边界，不宣称TM-002真实OS授权。 |
| 4 | 另起新空库/代际，保持两文件字节/身份不变，两页均完成，末页`complete=true`、正文复核和guard均通过；同步提交一次，再重启同库重扫同一代际。 | 只新增A/B两条，`(COUNT,input,output,cached,total)=(2,300,30,60,330)`；file-a/file-b各一游标410及对应prefixMAC，`coverage.scan_incomplete=0`仅此时出现；重启重扫不重复，`commitScanBatch`成功一次，没有原始路径/正文/密钥输出。 |

**DB与重置：** 每种失败/成功路径各用新owner库，绝不直接SQL造事件。步骤2允许仅在本例库创建失败触发器，步骤3仅注入假能力失权，均按owner清理；只读核对`usage_event`唯一键/聚合、`source_cursor`两行和偏移、`collection_diagnostic`、`coverage`及`identity_key_state`。原始run/失败和清理证据保留。真正跨页TM-002能力、已授权root、App/IPC/服务与产品`COVERAGE-OVERFLOW-01/SCAN/STORE`仍需独立E2E。

### TC-TM003-CORE-07 · 主进程采集编排与能力失效

**TASK：** `TASK-TM003-SCAN`、`TASK-TM003-STORE`。**AC：** `AC-TM003-001/003`。**类型：** `source_check`。**输入：** [固定主进程fixture](../../../tests/fixtures/tm003-main-collector-slice.json)引用CORE-06两份各410字节的原始行，公开测试密钥、已验证主体与已确认`sourceId`；假的TM-002 `SourceAccess`只暴露正式`beginCandidateScan`、`nextCandidatePage`、`readCandidateChunk`、`commitGuard`、`cancelScan`端口，存储则用本例0700根/0600 SQLite和真实`UsageStore`。每条故障路径独立重建空库，仅读核`usage_event/source_cursor/collection_diagnostic/coverage`；结束按owner清理并保留原始模块报告。输入在实现前固定；当前绑定`tm003-core07.test.ts`/`tm003-core07`，原候选模块PASS，整合候选待新run。

| 步骤 | 固定动作 | 独立预期及DB检查 |
| --- | --- | --- |
| 1 | 分别用非本主体来源ID、未验证主体、已确认但`collectAllowed=false`的假端口调用`collectCodex(sourceId)`。 | 进入扫描前明确拒绝，`beginCandidateScan/commitScanBatch`均0次，库中无本代际行；renderer不能传路径、账号或密钥替代`sourceId`。每变体为独立新库，拒绝不冒充已确认零。 |
| 2 | 合法主体/来源下读取第一页file-a（`complete=false`），按假端口最多每次返128字节读满410并比对SHA；未见末页时只读库。再读末页file-b（`complete=true`），也循环读满并比对；以公开密钥和fixture字段求root/file HMAC键，取同步`commitGuard`，执行一次整代提交，最后`cancelScan`。 | 首页面库四表无本代际行。两文件完整稳定、守卫通过后才有A/B两事件、input300/output30/cached60/total330、两游标各410、`scan_incomplete=0`；`commitScanBatch`恰1次、结束关闭scan。HMAC键精确等于fixture向量；usage库/WAL/结果不含相对路径、原生ID、私密哨兵或密钥。 |
| 3 | 从新库逐个注入file-b提前EOF、读异常，以及元数据为1025字节但本例暂存预算1024字节；每次都已暂存file-a后才触发。 | 三次均取消scan、丢弃整代、提交0次；四表无本代际行且不显示完整覆盖。单次`readCandidateChunk`请求≤65536字节；提前EOF不得拼接不完整正文，预算超限在分配完整Buffer前拒绝，不能截断为1024字节再提交。1024只是本模块的注入预算，产品任意大文件处理合同仍待流式/有界方案与真实E2E。 |
| 4 | 两份正文已读满、末页`complete=true`后，分别在`commitGuard`前模拟撤权和主体切换。 | 每次守卫拒绝、`cancelScan`恰1次、同步提交0次，A/B、游标、覆盖均不存在；旧主体的暂存不得转到新主体。此步仅是假能力故障，不证明真实OS授权或Keychain隔离。 |
| 5 | 对步骤2成功库重启同一模块，以同主体/来源/文件身份重扫同代际。 | 稳定HMAC来源键和事件身份不变，A/B各一、total330、两个游标仍410，无重复计数或原始路径落库；本轮扫描仍须完整读取、守卫和关闭。 |

**切片边界：** 当前`CodexGeneration.stage`接收完整Buffer，本辅助例只验证固定小文件和预算超限安全失败；不能据此称真实大日志可完整采集。产品`SOURCE/SCAN/STORE`的真实主进程、IPC、已安装App、TM-002系统能力与Keychain生命周期仍须独立固定TC和原件；不把模块5步PASS移作产品PASS。

## 主进程身份、真实来源适配与受限 IPC 开发切片

固定输入为[tm003-product-loop-slice.json](../../../tests/fixtures/tm003-product-loop-slice.json)及其引用的 CORE-07 两文件原生形状 fixture。公开测试密钥只在本例 owner 根与可替换加密端口中使用；生产入口必须从系统随机源新建32字节密钥，使用与 TM-002 来源 locator 同等级的 macOS 系统密钥保护端口加密后写当前用户私有 profile，不能落明文或从固定向量导入。三个辅助 TC 依次属于 `TASK-TM003-SECRET`、`TASK-TM003-WIRING`、`TASK-TM003-IPC`，只验证源代码边界、真实 `SourceAccess` 类的受控合成 helper、真实 `UsageStore` 与受限处理函数。它们不驱动已安装 Electron App、真实系统目录选择器或真实 Keychain，因此对应产品 `STORE-01/AUTH-01/AUTH-02/UI-01/UI-02/ISOLATION-01` 仍须独立执行。

### TC-TM003-CORE-08 · 私有身份密钥持久性与拒绝重键

**TASK：** `TASK-TM003-SECRET`。**AC：** `AC-TM003-002/004`。**类型：** `source_check`。**输入：** 本例0700 profile、0600空 `collection/usage-v1.sqlite`、公开测试密钥 `00..1f` 作为注入随机源唯一返回值、可替换的加/解密端口、三组规范化 origin+account.id 与预先冻结的 HMAC principal 向量。产品默认仍用系统随机源与系统密钥端口，测试注入不能通过 renderer 调用。

| 步骤 | 固定动作 | 逐步预期与只读 DB 判据 |
| --- | --- | --- |
| 1 | 在空 owner profile 中以可用加密端口初始化密钥，求三组 principal 键。 | 随机源仅调用一次、32字节密钥仅在内存；密文记录0600/目录0700，无明文 key。三键逐字节等于 fixture；同账号不同 origin 和同 origin 不同账号各有不同键。尚无事件/游标/覆盖写入。 |
| 2 | 用第一主体经正式 `UsageStore` 提交 fixture A=110，关闭密钥端口与库，再用同 profile 重开并重放 A。 | 重开只解密原密文、不生成新密钥；第一 principal 键和 `identity_key_state` 标记不变；`usage_event` 始终一行、total110、游标不重计，第二/第三主体只读零行但状态为未核实而非产品已知零。 |
| 3 | 分别在独立复制的本例已有事件库中删除密文记录和损坏密文，再初始化。 | 两者均返回固定 `identity_secret_unavailable`/`identity_secret_corrupt` 停采集，随机源零调用，不创建新密文、不改事件、游标、覆盖或密钥标记；旧 A 仍可由只读库核对。 |
| 4 | 恢复原密文后让加密端口不可用，再换成另一有效32字节密钥尝试打开原库。 | 密钥不可用时停采集，不能明文回退；不同有效密钥被 marker 拒绝，A仍一行/110，记录和报告无密钥、密文、完整路径或原生日志正文。 |

**DB与重置：** 本例只通过正式 store 写 A；故障变体各使用自有复制库，不直接 SQL 造事件。以只读 SQL 核对 `usage_event`、`source_cursor`、`coverage` 与 `identity_key_state` 前后行数/摘要；关闭连接后按 owner 收据只删本例目录。密文文件的权限、内容排除测试公开明文值及重启未重键须由固定程序断言。实际 macOS Keychain item 身份/隔离另由产品 E2E 核验。

### TC-TM003-CORE-09 · 已确认来源到本机库的主进程适配

**TASK：** `TASK-TM003-WIRING`。**AC：** `AC-TM003-001/003/004`。**类型：** `source_check`。**输入：** 同 fixture 的第一主体、确定的 `sourceId`、真实 `SourceAccess` 对象与本例合成目录/helper、CORE-07 两文件各410字节；密钥与库由 CORE-08 合同创建。候选页和正文由 TM-002 正式能力方法返回，适配器只接收 `sourceId`，不传路径、账号或密钥。

| 步骤 | 固定动作 | 逐步预期与只读 DB 判据 |
| --- | --- | --- |
| 1 | 未经确认直接触发 Codex 采集，再通过 SourceAccess 的选择/预览/确认方法建立本例来源。 | 确认前 `beginCandidateScan/readCandidateChunk/commitScanBatch` 均0次、库空；确认记录只属第一主体，候选元数据不包含正文。 |
| 2 | 以已确认 sourceId 调用主进程适配器，读取两个完整文件并在末页守卫通过后落库；关闭重开库/来源后重扫。 | 完成前库空；完成后A/B两事件、input300/output30/cached60/total330、各游标410、覆盖仅在全代完成后标记；重启重扫仍两行/330，无原始路径/原生ID落库。 |
| 3 | 从独立成功库开始新代际，在 file-b 后由 SourceAccess 撤销来源再尝试提交。 | 旧代际被取消，守卫拒绝、提交0次；已提交A/B仍两行/330，原成功代际的coverage行保持原值，本次运行状态须标采集不可用/不完整且不能称新代际完成；旧 sourceId 不再可读。 |
| 4 | 切到 fixture 的第二主体后尝试旧 sourceId，再为第二主体确认独立来源并扫描。 | 旧 sourceId 在读取前拒绝、第一主体数据不出现在第二主体查询；第二主体成功扫描后各主体各两行/330，HMAC主体键不同，不能共享游标/来源能力。 |

**DB与重置：** 每个故障路径独立 owner 库；只通过真实 `SourceAccess` 与 `UsageStore` 写入，测试 helper 只提供受控字节和系统选择器替身。逐步只读核对主体/来源唯一键、事件聚合、游标、覆盖和提交调用数；仅删除本例拥有目录。合成 helper 不证明真实 macOS 授权、任意大日志流式采集、Keychain 或产品 UI。

### TC-TM003-CORE-10 · 主窗口 IPC 与刷新状态隔离

**TASK：** `TASK-TM003-IPC`。**AC：** `AC-TM003-001/004`。**类型：** `source_check`。**输入：** CORE-09 成功库、第一主体及已确认 sourceId；可注入的主窗口 sender/frame 检查端口与正式 collection handler，固定第二主体。仅允许 `collection:getState` 无参数及 `collection:refresh` 精确 `{sourceId}`；返回结构采用已提交可信事件/诊断/覆盖，不把未知 cached 或覆盖缺口合成零。

| 步骤 | 固定动作 | 逐步预期与只读 DB 判据 |
| --- | --- | --- |
| 1 | 分别用非主窗口 sender、子 frame、路径/账号/密钥多余字段和未确认 sourceId 调用 handler。 | 全部拒绝，采集/DB调用0次；不接受任意路径或由 renderer 指定 principal/secret，不返回旧主体状态。 |
| 2 | 主窗口按固定 sourceId 刷新并取 state。 | 只触发第一主体 Codex 采集一次，返回两事件的 input300/output30/total330、cached已知60、覆盖与诊断代码/数量；库仍两行，序列化状态无密钥、密文、路径、原生ID或正文。 |
| 3 | 同主体再刷新并取 state，随后将来源暂停/撤销。 | 重扫仍两行/330；暂停/撤销后刷新拒绝、旧可信330只对第一主体保留可见且标采集不可用/覆盖不完整，不能报新已知零。 |
| 4 | 切换第二主体后由旧 sender/sourceId 取 state/刷新。 | 旧来源被拒绝，第二主体 state 为缺失/未核实且无第一主体330；第一主体持久事件不删除，按主体只读核对隔离。 |

**DB与重置：** handler 测试使用固定主窗口端口替身，不启动真实 Electron；只读核对 `usage_event`/`coverage`，每变体本例 owner profile，清理仅本例目录。真实 `ipcMain` 注册、preload/React 调用、已安装 App 的 sender 约束和 UI 观察仍由原产品 TC 及包级 E2E 独立验证。

**切片边界：** CORE-08/09/10 的输入、异常和数值在实现前固定，现已绑定同树 `tm003-core08/09/10` 固定程序、owner 重置和逐步报告。旧代码候选 `2d2f70d` 的七套独立 source_check 共10/10例、39步PASS；后续 `3c07fe7` 的CORE08/09各自四步PASS，原始报告及独立Excel保留为九个不同批次。机器目录在本文档候选中保持 `execution_status=unexecuted`，这些历史原件只归属各自被测提交；新绑定后的整合候选仍需按套件重跑。TM-002 的真实目录选择/加密 locator、Keychain item 独立归属，以及任意大文件有界读取仍是产品路径阻断；TM-004 只消费共享密钥/存储适配，不修改 `index.ts` 或 collection IPC；TM-005 只负责同库只读统计查询与 React 统计页，不以本模块状态代替完整双来源统计。

## 当前执行合同

每个 TC 的输入、步骤和 expected 已在此固定；程序绑定须保留来源版本、具体文件 SHA/SQL 与稳定选择器，不得为适配已有代码改弱独立预期。当前CORE-01～10由`tests/source_check_suites.json`和`scripts/run_source_check.mjs`绑定，命令为`node scripts/run_source_check.mjs --suite <suite> --run-id <新唯一UTC时间>`，每例在对应测试文件内创建并清理owner根。`AC-TM003-001` 至 `004`、四个 E2E 组和全部具体 TC 双向保持。`tests/feature_matrix.json` 的产品目标仍为 planned、`tests/datasets.json` 的 `codex_raw` 仍为 planned，产品 E2E 的实际结论只能是 BLOCKED；完成文档结构或单元测试不能改变这一事实。

## 稳定 TC 定位

以下标题供机器清单精确回链；各 TC 的完整输入、逐步预期与数据库操作在上方同 ID 行。

### TC-TM003-SOURCE-01

详见上方 `TC-TM003-SOURCE-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-DATA-01

详见上方 `TC-TM003-DATA-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-PARSE-01

详见上方 `TC-TM003-PARSE-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-SCAN-01

详见上方 `TC-TM003-SCAN-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-STORE-01

详见上方 `TC-TM003-STORE-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-UI-01

详见上方 `TC-TM003-UI-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-SOURCE-02

详见上方 `TC-TM003-SOURCE-02` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-PARSE-02

详见上方 `TC-TM003-PARSE-02` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-MODEL-01

详见上方 `TC-TM003-MODEL-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-DEDUP-01

详见上方 `TC-TM003-DEDUP-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-BRANCH-01

详见上方 `TC-TM003-BRANCH-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-NAMESPACE-01

详见上方 `TC-TM003-NAMESPACE-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-PRIVACY-01

详见上方 `TC-TM003-PRIVACY-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-DATA-02

详见上方 `TC-TM003-DATA-02` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-SCAN-02

详见上方 `TC-TM003-SCAN-02` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-SCAN-03

详见上方 `TC-TM003-SCAN-03` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-WINDOW-01

详见上方 `TC-TM003-WINDOW-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-COVERAGE-OVERFLOW-01

详见上方 `TC-TM003-COVERAGE-OVERFLOW-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-UI-02

详见上方 `TC-TM003-UI-02` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-BOUNDARY-01

详见上方 `TC-TM003-BOUNDARY-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-AUTH-01

详见上方 `TC-TM003-AUTH-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-AUTH-02

详见上方 `TC-TM003-AUTH-02` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-ISOLATION-01

详见上方 `TC-TM003-ISOLATION-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-MIGRATE-01

详见上方 `TC-TM003-MIGRATE-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-E2E-01

详见上方 `TC-TM003-E2E-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-E2E-02

详见上方 `TC-TM003-E2E-02` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-GOV-01

详见上方 `TC-TM003-GOV-01` 行；本条独立判定，不能由所属场景组代填。

### TC-TM003-CORE-01

详见“无授权依赖的解析与身份开发切片”同 ID 行；本条只证明模块合同，不能代填产品 TC。

### TC-TM003-CORE-02

详见“无授权依赖的解析与身份开发切片”同 ID 行；本条只证明模块合同，不能代填产品 TC。

### TC-TM003-CORE-03

详见“无授权依赖的解析与身份开发切片”同 ID 行；本条只证明模块合同，不能代填产品 TC。
