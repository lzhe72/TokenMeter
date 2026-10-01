# TM-005 统计读取合同草案

**release_id：** `v0.5.0-20261001T034729Z`
**状态：** draft / baseline_pending。逻辑合同供 TM-003/004 交接核对；实际表、字段与原生日志版本尚未锁定。

## 无原生日志依赖的纯统计开发切片

下一辅助边界分两层：`CORE-04`将IANA当地日变为UTC半开界，与已给界的`CORE-01`分别验证；固定纽约春/秋实际23/25小时，非法日期/区不产生默认零。`CORE-05`在本例拥有的合成TM-003 SQLite上，以当前`usage_event`物理列和一份只读事务查询Codex/Claude两来源；同一快照的卡片/来源/模型/明细/日点要对同一事件集合，另连接提交后只在**下一**读事务可见。现有`coverage`缺连续历史区间证明，空日不得声明产品完整零。固定fixture与逐步判据见[04a](04a-test-cases.md#日期与双来源物理快照辅助tc)；两例均不触及原生日志、真实App/服务、产品授权及产品E2E。

本节只冻结 `TASK-TM005-EVENT-CONTRACT`、`TASK-TM005-RANGE-QUERY`、`TASK-TM005-COVERAGE` 中独立的纯函数部分及 `TC-TM005-CORE-01/02/03`。输入不是来源原生日志或产品 SQLite 行，而是固定 `tests/fixtures/tm005-core-slice.json` 中的合成 `TrustedUsageEvent`：`principal_key`、`source=codex|claude_code`、不含原生ID的测试 `source_event_key`、UTC时间、`model_id|null`、非负整数 input/output 与可为 null 的缓存读/写、推理子项。CORE-01的范围输入由调用方直接给出fixture固定`start_utc/end_exclusive_utc`，不在该统计函数中把`timezone/local_day`换算为UTC；IANA当地日及夏令时换算另设辅助TC，产品RANGE-11仍待真实App E2E。输入事件已经由调用方判为可信且在 `(principal_key,source,source_event_key)` 上唯一；模块只做统计，不重新推断上游身份或继承。只接收固定两个来源；未知来源、负数、子项超出总项或不合法UTC时刻应拒绝，不能默认为0。

在固定主体 `synthetic-p1` 和 `Asia/Shanghai` 的 `2026-09-29` 半开当地日中，A（Codex 100/10、未知模型）与 B（Claude Code 200/20、`sonnet-test`）的可信已知合计为330，来源分别110/220，模型分别 `unknown_model=110`/`sonnet-test=220`；另一主体 C=10 必须排除。A 的缓存读20、推理2是 input/output 的子项，不加到330；B 的缓存读和两来源缓存写为 null 时，相应子项输出保持未知而非0。固定当地日 UTC 界为 `2026-09-28T16:00:00Z` 至 `2026-09-29T16:00:00Z`，边界外事件不得纳入。

`UsageDiagnostic` 只含主体、来源、UTC时间和 `missing_usage` 等代码，不携带伪造Token。与 A/B 同范围的一个未知用量诊断使状态为 `partial`、`known_tokens=330`、`total_tokens=null`；只留未知诊断且无可信事件为 `unknown`，不能写零。`CoverageFact` 在此切片是**测试程序显式给出的合成假设**，两个来源分别标 `complete` 或 `missing`；模块不得自己把空事件列表变成完整覆盖。两来源合成 complete 且无事件/诊断时可输出 `complete/0`；任一来源 missing 且无可信事件时输出 `missing/null`；有可信110时输出 `partial/known110/total null`。这只验证状态代数，完全不证明真实来源任意连续空日可覆盖，`TC-TM005-STATE-02/04/06` 仍需上游持久证据、真实App与固定产品程序。

切片的非目标：读取TM-002授权根、解析TM-003/004原生日志、创建或迁移客户端SQLite、驱动 Electron IPC/UI、证明 `safeStorage` Keychain 隔离或真实日期覆盖、把静态 oracle 当产品PASS。`CORE-01/02/03` 的程序绑定当前为空，实际运行unexecuted；SOP-008仅对这三条及其固定 fixture 做独立内容核对，整版文档继续draft。若上游最终事件字段或身份口径改变并影响纯函数输入，先撤销切片就绪并修订固定TC。

## 输入边界

TM-005 同时读取 TM-003 Codex 和 TM-004 Claude Code 已去重、已持久化的结果。两分支已对齐的**设计字段**为 `principal_key`、`source`（`codex` / `claude_code`）、`source_event_key`、`source_scope_key`、`occurred_at_utc`、`model_id|null`、`input_tokens`、`output_tokens`、`cached_input_tokens|null`、`cache_write_input_tokens|null`、`reasoning_output_tokens|null`、`source_version`、`identity_scheme_version`；实际 SQLite/IPC 尚未交付。当前登录账号的已验证归属、UTC 时间、安全非负整数 input/output、三个缓存/推理子项的已知/未知状态和必要诊断均须可核对。缓存读取及写入是 input 的子项，推理是 output 的子项；已知值各须处于对应总项的 `[0,input]` 或 `[0,output]` 范围。任一缺失子项保持 `null`/未知，不能拿 0 代替。模型未知可为 `model_id=null`，用量若可信仍须计入未知模型组。不能仅凭文本相同或文件名去重；无法核实去重或字段含义的记录保留诊断，不纳入可信完整合计，也不能伪造为 0。

客户端查询不接收原始日志路径、提示词、回复、代码或密钥，也不从 renderer 接收 SQL。来源目录只在授权与采集边界可见；统计记录和 IPC 输出只包含必要归属、模型、时间、用量、状态和不泄露路径的来源标记。本版不上传统计到服务端；TM-007 才处理跨设备/团队同步。

## 覆盖事实与数值状态

“没有事件”与“已确认零调用”是不同事实。每来源需要明确、可核验的覆盖区间，至少记录授权根的匿名 ID、UTC 起止、扫描/观察成功状态、连续性和证明依据。默认覆盖状态为未知；任何扫描错误、失权、未知格式、源文件被删或观察间断都不能扩展完整覆盖。完整日只有两个来源均可证明覆盖该日整段 UTC 区间，且该日没有未知用量/未解决诊断时才能展示 0。若上游无法提供这种证明，`TC-TM005-STATE-02` 保持 BLOCKED，先返回 SOP-002/004 修订可实现的验收输入；不得通过写入测试覆盖标记来放行。

TM-004 提交 `dda5ccb` 细化了另一层覆盖前提：TM-002 候选预览的 1000 文件/5000 目录项/2 秒上限只是 UI 预览，不能充当完整采集列表；拟议独立分页扫描每页最多 256 个，页间仍须校验授权主体、根身份和撤销状态。只有所有页面、必要深度、完整行及游标提交都完成且无阻断诊断，才能声称本次范围覆盖完成。预览截断、continuation 尚未耗尽、深层子代理漏扫、超时或页间撤权均使覆盖不完整，不能把暂未见事件显示为 0。TM-002 分页接口尚未实现；`TC-TM005-STATE-06` 仅为等待上游稳定扫描合同的统计集成草案。

统计输出区分下列状态：

| 状态 | 判据 | 界面与数值 |
| --- | --- | --- |
| `complete` | 两来源覆盖完整且范围内所有入账调用字段可信 | 显示完整数字；无调用时可以显示 0 |
| `partial` | 有可信调用，但任一来源覆盖不完整、存在未知字段或诊断 | 显示“已知部分”数字及不完整提示；不能把该值称为完整总量 |
| `missing` | 无可信调用且覆盖无法证明 | 显示缺失/暂无可确认数据，不显示 0 |
| `unknown` | 范围内有无法核实的用量，且不能构成完整数字 | 显示未知原因；可并列显示已知部分，不把未知补 0 |

同一范围卡片、趋势、明细和模型维度使用一个 SQLite 只读事务快照，避免扫描在查询中途提交造成互不相等的 UI。已知调用合计只按 `input + output`；缓存读取、缓存写入和推理单独显示。任一 token 字段 `null`/unknown 时不使用 SQL `COALESCE(...,0)` 生成“完整”零；一个缺失的子项不使已知 input/output 的总量消失，但该子项必须显示未知。金额与价格版本在 TM-006 验收，不参与本版 token 完整性判断。重复源事件由上游唯一约束或等价事务保证，统计查询不得再把重复行相加。

## 日期、时区与查询合同

事件只存 UTC。时区配置采用有效 IANA 标识，默认 `Asia/Shanghai`；按当前身份/单团队设置显示。每次查询先将本地日 `start 00:00` 与 `end_exclusive 00:00` 分别按所选时区换算为 UTC instant，再作 `occurred_at >= start_utc AND occurred_at < end_utc`。不能把结束界写成 `23:59:59`，不能用固定 86400 秒递增日界；遇到夏令时仍取相邻当地午夜。今天/昨天/近 7/15/30 天由同一参考 UTC 时刻在该时区对应的当地日期计算；近 N 天包含今天。自定义结束日由 UI 转成下一当地日的排除上界。前端不得自行按操作系统时区重新过滤主进程结果。

同一事件集合必须驱动全部输出：`summary`（input/output/total/cache/reasoning、可信事件数、状态）、`trend[]`（每当地日的数字与状态）、`details[]`（事件身份、来源、时间、模型和字段状态）、`models[]`（原始可识别模型分组、未知模型单独保留）。查询参数必须是限定枚举/日期/IANA 时区，不接受任意路径、SQL 或任意 URL。倒置或空自定义范围在 UI 与主进程双层拒绝，不修改上次有效结果或持久数据。时区切换只改变分桶，不重写 UTC 事件或其去重身份。

## IPC、持久化与恢复

主进程应提供限定业务方法（名称在已有 Electron Bridge 合并时确定）取得上述统计快照并保存时区偏好；preload 只透传结构化结果，renderer 不接触客户端 SQLite 文件。主进程验证窗口/主 frame、账号身份、日期长度和时区，并在登出/账号切换后停止旧身份结果进入新会话。一次 refresh/restart 可重查同一稳定数据，但不能触发重复入账。API 服务仍只用于真实登录身份；团队统计权限与上传属于 TM-007。

若 TM-005 新增客户端表或索引，按 SOP-016 先用 TM-003/004 实际旧 schema 的隔离副本备份并验证可恢复，再做事务化迁移；核对事件身份数、UTC 时间、token 合计、unknown/coverage 状态及身份隔离，测试中断、重跑和不兼容版本。失败不继续写损坏库，不访问用户生产库。表/迁移版本、SQL 和可执行入口待上游稳定提交后锁定。

拟议只读旁证基于两分支设计中的 `usage_event`，供实际 schema 交付后逐列核定，当前**不可执行**。查询参数均由本例已验证合成 `principal_key` 与独立计算的 UTC 半开界提供，不从 App 查询结果反算：

```sql
SELECT source, COUNT(*) AS calls, SUM(input_tokens) AS input_total,
       SUM(output_tokens) AS output_total,
       SUM(CASE WHEN cached_input_tokens IS NULL THEN 1 ELSE 0 END) AS cache_read_unknown,
       SUM(CASE WHEN cache_write_input_tokens IS NULL THEN 1 ELSE 0 END) AS cache_write_unknown,
       SUM(CASE WHEN reasoning_output_tokens IS NULL THEN 1 ELSE 0 END) AS reasoning_unknown
FROM usage_event
WHERE principal_key = :principal_key
  AND occurred_at_utc >= :start_utc AND occurred_at_utc < :end_utc
GROUP BY source;
```

逐条旁证另核对 `source/source_event_key/source_scope_key/model_id/occurred_at_utc/input_tokens/output_tokens` 与唯一约束 `(principal_key,source,source_event_key)`；冲突诊断只核代码/数量及不可逆来源归属，不要求保存第二条原生 ID、完整路径或内容。TM-003已提交`UsageStore`的实际`coverage`表含`principal_key,root_key,missing_before,scan_incomplete,last_scan_at_utc`，**没有连续历史区间证明**，不足以证明任意完整空日被两个来源连续覆盖。诊断表的扫描写入时间也不是原始事件发生时间，不能据此给任意历史日分配未知状态。因此 `STATE-02/04` 的真零及逐日诊断判据仍需 TM-003/004 给出来源事实及可读持久合同；若无法给出，先按 SOP-002/004 修订验收，不能只改 SQL 或人工写覆盖行取绿。

## 交接判据

TM-003/004 需各自交付稳定提交、已验证原生日志版本、事件身份/模型/时间/用量语义、partial/unknown 诊断及扫描覆盖证明。TM-005 根据实际合同核定物理 schema、只读 SQL、fixture 映射和 Playwright `data-testid`，再补齐测试计划、根用例清单与项目总表，执行 SOP-008。仅有上游规划草稿、标准化语义样例或构建成功不满足此判据。

已只读核对 TM-004 草稿提交 `2b04dc9`：它引用 TM-003 的草稿事件字段 `{source, source_event_key, occurred_at_utc, model_id|null, input_tokens, output_tokens, cached_input_tokens|null, reasoning_output_tokens|null}`，并把会话/子代理关系留在 TM-004 映射层。该提交只改文档，没有可运行采集实现；本合同只把这组字段作为待核对输入，不把字段名或覆盖语义当作已交付接口。

TM-004 后续在隔离回环的 Claude Code 2.1.126 实测中，由 CLI 自写的 `--fork-session` 文件复制了父会话两条消息并追加新消息，而该次原始记录没有 `forkedFrom`。这是总控提供的阶段观察，尚非最终可发布合同。TM-005 的统计查询只接收 TM-004 已判定的唯一调用与未确定诊断；不能要求 `forkedFrom` 必有，不能以复制消息的新 UUID 或文件路径直接判为新调用，也不能在查询层猜测父子链。若最终证据不能证明继承身份，相关记录保持未确定，不进入完整合计。`TC-TM005-CONTRACT-03` 待 TM-004 最终 raw fixture、去重身份和诊断结果冻结后锁定数字断言。

另一次隔离回环子代理探针由 CLI 自写 `subagents/agent-*.jsonl`，父会话与子代理各有独立 usage 记录。它与 fork 复制历史是不同风险：子代理实际调用应按自身可信身份入账一次，父会话若仅引用子代理不能再把子代理用量加一次；fork 继承的旧调用则不再入账。TM-005 不以父子文件路径或消息数量决定用量，分别由 `TC-TM005-CONTRACT-04` 和 `TC-TM005-CONTRACT-03` 验证最终 TM-004 输出。当前记录属于总控转交的阶段证据说明，原始 JSONL 摘要/最终身份合同尚待 TM-004 交接，不能据此宣称产品通过。

TM-004 已把上述隔离原生 Claude 2.1.126 研究固定于提交 `d0108814802e549e669e5500927afa5fedc65df7`；总控给出的原始清单位于其工作树 `.local/ci/tm004-claude-2.1.126-research/evidence-manifest.json`。只读核对该提交的设计说明：fork 复制父 UUID、`message.id` 和 usage，并建立新 `sessionId`，该样本无 `forkedFrom`；Agent 子文件有 `agentId`、`isSidechain=true`，**与父文件同 `sessionId`**。因此 TM-005 不能把 `sessionId` 单独当唯一调用身份，不能把“子文件使用相同 sessionId”误判为复制历史；同样不能把 `forkedFrom` 当必有字段。上述仅固定来源观察，TM-004 解析/去重和产品 E2E 仍 BLOCKED，最终唯一身份及数字仍由其交付合同冻结。

TM-003 阶段提交 `fecd35c5bba967773e3d535ada02f7522989ef02` 提供隔离原生 Codex `0.158.0-alpha.2.1` 来源探针。总控给出的单条 CLI 自写 `token_usage_record` 使用 `response_id=tm003-native-probe-response-1`，input 100、cached read 20、cache write 0、output 10、reasoning 2、total 110；原始 JSONL SHA-256 为 `3b30cfa81c0c29a80f1bfc1de5bf823db01a9a85636e41ec58dfdd00f0436d08`。已只读核对该提交的设计：`token_usage_record` 为逐响应增量，turn/thread token usage 是累计核对值，不能再次相加；缓存读/写和推理输出为子项。`TC-TM005-CONTRACT-05` 将此作为原生输入形状的独立数字预期，但只有最终 TM-003 解析、存储、身份和真实 App 链路交付后才可执行。`SOURCE_PROBE_PASS` 仅验证日志形状，不代表 TM-003 或 TM-005 产品通过。

后续 TM-003 阶段探针又观察到 Codex exec fork **新文件只含新响应 C**，而 C 的 `thread_token_usage` 可继承父线程 A+B+C 的累计值。该固定探针按原断言为 BLOCKED，尚不能宣称兼容通过。统计只能从 TM-003 最终确认的逐响应 C usage 增加 C，不能把 fork 文件的线程累计快照当新增调用。`TC-TM005-CONTRACT-06` 以设计数字 A110、B220、C330 约束“fork 后总量 660 而非另加累计 660”；实际 raw 身份、版本和可执行断言待上游冻结。

TM-004 隔离 Claude Code 2.1.126 原生证据现由提交 `dda5ccb` 记录：一次 API 消息的双 text 块写成两条 `assistant` JSONL，两行相同 `message.id` 且各带完整 usage 31/9，唯一调用为 40，逐行求和会误得 80。另在合成 API 整体省略 usage 时，CLI 仍写 0/0，因此日志里的“0”**不能单独证明供应方报告了真实零用量**。`TC-TM005-CONTRACT-07` 用 31/9 样例核对同一调用两行只入账一次；`TC-TM005-STATE-05` 将 0/0 歧义保持 unknown/未确定，除非 TM-004 最终合同给出额外可核实依据。若显式零与缺失在可见原生日志中完全同形，产品不能凭该日志区分两者，不能把测试零字段写成完整零。该提交和原始研究证据仍不替代 TM-004 安装 App 产品 E2E。

跨分支接口审核曾发现旧 `(principal_key,response_key)` 草稿可能把两个来源的相同原生 ID 误去重；后续共享设计已改为来源限定身份。两个来源若给出同一字面原生 ID，其不同真实调用仍各计一次；同来源同一真实调用重放只计一次。TM-005 只查询上游可信唯一事件，不在展示层补救错误身份。`TC-TM005-CONTRACT-08` 用跨来源 ID 碰撞与同来源重放验证统计和只读 SQLite 的两个来源、两条唯一键及 token；程序须在实际上游 schema 交付后绑定。

TM-003 `clean-base` 设计与 TM-004 `05a9cd8` 文档已共同冻结**设计输入**：`source_event_key = HMAC-SHA256(local_secret, length_prefix(["usage-identity-v1", source, provider_call_scope, canonical_call_id]))`。各 UTF-8 字段单独长度前缀；`source` 枚举 `codex` / `claude_code`；Codex `provider_call_scope=provider-response`、ID=`token_usage_record.payload.response_id`；Claude `provider_call_scope=provider-message`、ID=`assistant.message.id`。`identity_scheme_version` 固定身份方案，`source_version` 单独表示已核验 CLI 版本；agentId/session/thread 只作为不可逆 `source_scope_key` 等归属与冲突诊断，不进入唯一键。拟议唯一约束为 `PRIMARY KEY(principal_key,source,source_event_key)`，`local_secret` 不进 renderer/报告。设计冻结不等于 SQLite 表、迁移或产品 E2E 已实现；TM-005 待实际上游交付后逐列核对。

TM-004 设计候选 `d6c90e35` 又用[固定字节向量](../../tests/fixtures/tm004/identity-v1-vectors.json)明确：四个 UTF-8 字段依上述顺序分别附无符号 32 位**大端**字节长度，再串接为 HMAC-SHA256 的输入，结果为小写十六进制；原生调用 ID 原样使用，不做 trim、大小写折叠或 Unicode 正规化。测试向量使用公开固定 32 字节密钥，包含相同原生 ID 的 Codex/Claude 不同键，以及 Claude 组合/分解 Unicode 的不同键；生产密钥不得复用此公开值。TM-004 开发分支另有参考向量校验程序 `scripts/tm004_identity_vectors.py` 和治理测试，用于核对设计接口；该代码尚未集成到本文档工作树，不表示 TM-003/004 已实现该算法或 TM-005 已通过数据库/桌面产品验证。

已证实同一次 Claude API 消息的双内容块及普通 fork 可证明复制同 `message.id`/usage 时去重；跨 Agent/会话同 ID 而缺可证复制关系时不能默默当旧调用，须诊断 `unverified_inheritance`、保持覆盖不完整；同 ID 的 usage 或模型不一致则诊断 `identity_conflict` 并保留首个可信事件。`TC-TM005-CONTRACT-09/10` 分别验这些失败路径。TM-004 的 fork/Agent 原生样本仍没有 `fork-context-ref`，改写 UUID 的继承证明 BLOCKED；不能把二进制静态线索写成已验证能力。对无法核实的新旧身份只保留已知部分，不能把未确定事件当作 0 或完整总量。TM-003/004 最终合同可能调整列名/迁移，届时先修设计和独立预期再基线。
