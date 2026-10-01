# TM-005 逐 TC 设计草案

**release_id：** `v0.5.0-20261001T034729Z`
**需求/功能：** `REQ-TM005` / `TM-005`。
**状态：** draft / baseline_pending；全部 unexecuted，自动程序绑定均为 `null`。本文件按 SOP-006 编制，不能当作可运行测试或产品 PASS。

## 共用前置、数据与记录

产品级 TC 属于 `product_e2e`，必须从本轮 DMG 安装后的 Electron App 经真实 IPC、两来源采集器、客户端隔离 SQLite 和真实隔离 FastAPI/服务 SQLite 执行。每例使用本轮拥有的独立 `--user-data-dir`、安装位置、Codex/Claude Code 授权目录、合成账号和动态独占回环端口；服务地址由真实配置 UI 设置。先由 SOP-010 造数并只读核查 schema/初态；用量只能由两类**经验证版本的原生日志**进入产品库，不能直接 SQL 插入标准化事件证明采集。测试操作与断言由仓库固定 Playwright Electron 代码按 TC ID 执行，保存每步预期/实测、源/DB 摘要、trace、截图和拥有资源的清理结果。原生日志字段、客户端表名、只读 SQL、UI test ID 与程序路径在 TM-003/004 稳定交接后填写。

若 TM-002/003/004 的来源 locator 调用 macOS `safeStorage`，依新 SOP-009/010/014 先用同一最终 DMG 的原生探针证明测试 Keychain item 的实际 service/account 或等效身份与正式 App 分离、运行前不存在，并记录本次创建与精确清理的归属证据；单独 `--user-data-dir` 不满足这一前提。任何身份不明、预存或可能触及正式 item 的场景保持 BLOCKED，不能为了本版统计验收跳过上游隔离门禁。

数值 oracle 为[独立语义文件](../../tests/fixtures/tm005-semantic-expected.json)，种子 42；它只描述规范化语义，`raw_log_compatibility_verified=false`。真正 E2E 生成器应把 2026-09-29 上海自然日锚点整体平移整数天到运行当日，再将每条语义事件映射为受支持版本的 Codex/Claude Code 原生日志。固定时钟不改系统时间：输入、期望、锚点与原始字节摘要必须在启动 App 前固定；如跨过上海自然日边界，整次运行 BLOCKED 并另建 run_id。UTC 改时区检查使用明确自定义 UTC 日期，避免把当前 UTC“今天”误当上海“今天”。这套生成/重置程序尚未实现，不能声称已有 `date_ranges` 程序可完成映射。

本版登录一个合成成员账号，所有本机原始事件归其所有，以验证个人本机统计；TM-007 才验收跨设备/团队同步。对于状态 TC，源扫描器必须给出可核实的覆盖区间，单纯“查询为空”不能算完整覆盖。预期中的“0”只用于已证实完整覆盖且没有调用的区间。费用数值不在 TM-005 验收范围，价格不明不能改变 Token 计数。

## `E2E-TM005-001` / `AC-TM005-001` · 范围、趋势、明细和模型

### TC-TM005-CONTRACT-01 · 两来源重复事件不增量

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** seed42 事件中 Codex `today-gpt` 和 Claude Code `today-sonnet` 各一原生事件，另各有同源重复读取；全部绑定同一合成账号。**类型：** product_e2e。

1. 从空客户端库在 App 授权两目录并等待采集；UI 应显示两个来源已读取，DB 只读记录应有两条可信事件，总量 3300。
2. 复制/重放两条原生事件并在 App 点刷新；UI 总量仍 3300，DB 的唯一来源事件身份仍为两条，诊断不能误报新用量。
3. 退出并由同一已安装 App 重启后再刷新；总量和身份仍不变。只清理由本例创建的文件与进程。

**缺口：** 两采集器的稳定身份、复制语义、只读 SQL/test ID 与程序绑定；当前不能执行。

### TC-TM005-CONTRACT-02 · 未知字段不伪造零

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** 一条 Codex 缺 output、另一条 Claude Code 缺 input 的受支持原生记录，另有两条可信调用各 110 token。**类型：** product_e2e。

1. 从空库经 App 采集两条可信调用；卡片显示已知总量 220，DB 有两条可信事件。
2. 追加两条缺字段记录并刷新；UI 显示相应未知诊断，完整总量不能把未知字段当 0。可信 220 不被覆盖，DB 的 unknown 状态与来源可只读辨认。
3. 重扫与重启；可信 220 和两条未知状态保持，不能变成成功零用量。

**缺口：** 两来源真正可构造的缺字段原生样例、未知字段产品合同、SQL/test ID 与程序绑定。

### TC-TM005-CONTRACT-03 · Claude fork 复制历史与新增调用

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** 使用 TM-004 最终锁定的 Claude Code 2.1.126 自写原始 fork fixture：父会话可信调用 M=100/10，fork 文件复制父历史并新增可信调用 N=50/5；已固定的来源样本复制父 UUID、`message.id`、usage，却没有 `forkedFrom`。**类型：** product_e2e；`E2E-TM005-001`。

1. 在 App 授权本例 Claude 根并采集父会话 M；统计明细仅 M 一次，总量 110，DB 有一个可信来源调用身份。
2. 由已验证 CLI 操作生成/写入上述固定 fork 原生日志后经 App 刷新；UI/DB 恰有 M、N 两个可信调用，total=165。复制的父历史不另入账，缺 `forkedFrom` 本身不构成新调用证明。
3. 重扫 fork/父文件并重启 App；可信事件身份及 165 保持。若最终来源合同不能证明本例固定 fixture 的复制和新增关系，本例在运行前保持 BLOCKED，不能临场改写为另一预期或手填 PASS。

**缺口：** TM-004 最终 raw fixture、可证明的继承/调用身份、诊断/数据库字段与固定程序。现有观察不足以锁定第 2 步可执行判据，因此该 TC 为 `baseline_pending`/unexecuted。

### TC-TM005-CONTRACT-04 · Claude 父会话与子代理独立用量

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** TM-004 最终锁定的 Claude Code 2.1.126 自写主会话与 `subagents/agent-*.jsonl` fixture；设计数字为父调用 M=100/10、子代理调用 S=200/20，两者各有独立 usage。已固定的来源样本中子文件带 `agentId`、`isSidechain=true`，与父文件同 `sessionId`。**类型：** product_e2e；`E2E-TM005-001`。

1. App 授权本例 Claude 根并采集父会话；只有父调用 M 入账，UI/DB 显示可信 110 及父来源身份。
2. 子代理原生日志完整写入并由 App 采集；UI/DB 恰有 M、S 两个可信调用，total=330。父会话对子代理的引用不能另加 220；父子同 `sessionId` 也不能把子代理的真实调用消掉。
3. 重扫主/子文件、刷新并重启；两个唯一身份与 330 保持，模型维度分别保留实际模型标识。若最终 raw 无法证明该父子关系或独立调用，本例在运行前保持 BLOCKED，不临场更换结果判据。

**缺口：** TM-004 原始 JSONL/摘要、父子身份与项目归属冻结合同、可执行 SQL/test ID 和固定程序。阶段探针已生成原件，但本例尚未绑定，状态 `baseline_pending`/unexecuted。

### TC-TM005-CONTRACT-05 · Codex 逐响应与缓存子项

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** TM-003 阶段隔离原生 Codex `0.158.0-alpha.2.1` rollout 形状：一条 `token_usage_record`，`response_id=tm003-native-probe-response-1`，input100、cached read20、cache write0、output10、reasoning2、total110；原始 JSONL SHA-256 `3b30cfa81c0c29a80f1bfc1de5bf823db01a9a85636e41ec58dfdd00f0436d08`。**类型：** product_e2e；`E2E-TM005-001`。

1. 由 TM-003 最终固定数据程序在本例拥有的 Codex 根生成受支持原生日志，从安装后的 App 授权并采集；UI 和只读 DB 恰有一个可信逐响应身份，input100、output10、total110。
2. UI 缓存读20、缓存写0、推理输出2作为已知子项分别显示，不再加到 total；同一 rollout 内 turn/thread 累计快照不能生成第二个 110 调用。
3. 重扫、刷新、重启后仍为一个身份/110；原生日志原件或派生 fixture 的摘要与运行记录一致。

**缺口：** 目前只有 `SOURCE_PROBE_PASS` 的来源形状证据；TM-003 解析、唯一约束、App IPC/UI、SQL、可重复 raw fixture/重置及固定 Playwright 程序尚未交付。本例仍为 `baseline_pending`/unexecuted，不能以来源探针代替产品 PASS。

### TC-TM005-CONTRACT-06 · Codex fork 的累计快照不当增量

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** 上游最终固定的 Codex exec fork 原生日志；设计数字为父响应 A=100/10、B=200/20，fork 新文件仅新响应 C=300/30，C 行的 `thread_token_usage` 为 A+B+C 累计 660。**类型：** product_e2e；`E2E-TM005-001`。

1. App 采集父日志 A/B；UI 与 DB 应有两个可信响应身份，total 330。
2. App 读取仅含 C 的 fork 新文件；可信身份增至三个，total 660。C 的逐响应 330 只加一次，`thread_token_usage=660` 不另加为第四个调用或在本步加 660。
3. 重扫父/fork 文件并重启；仍三个身份/660。若上游 fork 身份/解析证据不完整，记录未确定诊断，不按累计值补造事件。

**缺口：** 当前固定来源探针因原断言不符为 BLOCKED；设计数字尚非其已验证原件。TM-003 最终 raw fixture、响应身份、数据库/诊断字段和固定 App 程序交付后再锁定预期。

### TC-TM005-CONTRACT-07 · Claude 同消息多行不重复

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** TM-004 提交 `dda5ccb` 所记录的 Claude Code 2.1.126 原生日志形状：一个 API 消息的双 text 块对应两条 `assistant` JSONL，`message.id` 相同且每行都带完整 usage input31/output9。**类型：** product_e2e；`E2E-TM005-001`。

1. App 采集该消息；UI/DB 只出现一个可信调用身份，input31/output9/total40，而不是两行求和的 80。
2. 刷新、重扫并重启；仍一个调用/40，明细不出现第二个相同消息。

**缺口：** 同 `message.id` 的来源真实调用语义及冲突处理须 TM-004 最终合同确定；当前只是阶段原生观察，尚无产品绑定。

### TC-TM005-CONTRACT-08 · 两来源原生 ID 碰撞与同源重放

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** 隔离 Codex 与 Claude 原生日志各有不同的真实调用，却故意使其来源原生调用 ID 同为 `shared-native-id-1`；设计用量 Codex A=100/10、Claude B=200/20。再重放 Claude B 的相同原生记录。**类型：** product_e2e；`E2E-TM005-001`。

1. App 经两授权根先采集 Codex A；UI/只读 SQLite 有一个可信调用，total 110，记录 `source=codex` 与 `source_event_key` 的不泄露表示。
2. App 再采集同原生 ID 的 Claude B；UI/SQLite 应有两个不同来源的可信调用，total 330。不能因跨来源 ID 碰撞压掉 B，也不能把 A 改写为 B。
3. 重放 B 并刷新/重启；仍两个可信调用/330，同一 Claude 调用未重复。SQLite 旁证须同时检查两个来源身份、各自 token 和唯一键，而非仅检查总量。

**缺口：** TM-003/004 已给出来源限定 HMAC 身份草稿，但稳定实现/迁移和产品 E2E 尚未交付；原生日志可控 ID 映射、准确列名/只读 SQL 和固定 App 程序仍待上游交接。上述数字是独立设计输入，当前 `baseline_pending`/unexecuted。

### TC-TM005-CONTRACT-09 · Claude 同 ID 继承关系无法证明

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** 同一合成账号下两条 Claude Agent/会话原始记录都用 `assistant.message.id=shared-claude-id-1`、相同模型和 input100/output10；首调用 A 已可信，第二条 B 位于另一 Agent/会话，缺少能证明复制或独立新调用的父链/来源证据。相同用量/模型使本例只检验继承不确定性，不与 `identity_conflict` 混合。**类型：** product_e2e；`E2E-TM005-001`。

1. App 采集 A；UI/SQLite 有一个可信 Claude 调用，已知部分 110。
2. 追加 B 并刷新；不能静默把 B 视为 A 的已证复制，也不能武断另加 110。UI 显示统计不完整、已知部分仍 110；诊断 `unverified_inheritance`，覆盖状态不完整。SQLite 保留 A 的可信键/值及不含原始 ID/完整路径的诊断代码、数量和来源归属旁证，不要求持久化 B 原文。
3. 重扫/重启后诊断与已知部分保持；若 TM-004 最终合同找到可证复制/独立身份，先修本用例输入与预期并重新基线，不在运行时临时选答案。

**缺口：** 上游共享 HMAC 身份及 `source_scope_key` 已冻结为设计输入，实际实现、第二条原生日志、诊断旁证、DB 只读 SQL 和固定产品程序仍待交付。

### TC-TM005-CONTRACT-10 · 同 ID 用量或模型冲突

**TASK：** `TASK-TM005-EVENT-CONTRACT`。**输入：** Claude 同 `assistant.message.id=conflict-claude-id-1` 的首可信调用 A=100/10、模型 `model-a`；两个稳定变体 `TC-TM005-CONTRACT-10#USAGE`（后续同 ID usage 改为 200/20）与 `TC-TM005-CONTRACT-10#MODEL`（后续同 ID 用量仍 100/10、模型改为 `model-b`）。**类型：** product_e2e；`E2E-TM005-001`。

- `TC-TM005-CONTRACT-10#USAGE`：从独立空库导入 A，再导入同 ID、同模型但 200/20 的行；预期 `identity_conflict`，可信统计仍为 A 的 110。
- `TC-TM005-CONTRACT-10#MODEL`：从独立空库导入 A，再导入同 ID、100/10 但模型为 `model-b` 的行；预期 `identity_conflict`，可信统计仍为 A 的 110 且模型为 `model-a`。

1. 每个变体从独立空客户端库采集 A；UI/SQLite 为一个可信事件、total110、模型 `model-a`。
2. 追加对应矛盾行并刷新；`identity_conflict` 诊断出现，A 的用量和模型保持，已知部分 110，不新增/覆盖可信事件，不把统计标为完整。
3. 重扫/重启；冲突诊断和首可信值保持。两个变体分别保存原始结果；不得用一个变体通过覆盖另一变体。

**缺口：** 最终原生可构造冲突数据、冲突状态/覆盖合同、两个变体的逐项程序绑定、SQL 和固定 Playwright 入口。

### TC-TM005-RANGE-01 · 今天

**TASK：** `TASK-TM005-RANGE-QUERY`、`TASK-TM005-UI`。**输入：** seed42 全部 13 行映射为两来源原生事件，1 行为 `today-gpt` 原样重复；上海日锚点与运行日一致。**类型：** product_e2e。

1. 经 App 采集后选“今天”；卡片应显示唯一 5 次、input 15000、output 1500、total 16500、cached read 1700、reasoning 170，子项不再加到 total。规范化语义样例没有 cache write 字段；若最终 raw 映射也没有可核实字段，该子项应显示未知而非 0。
2. 检查趋势今天点为 16500，明细 ID 集合恰为 `today-gpt/sonnet/qwen/glm/unknown` 的五项；每条来源、模型、UTC 时间与原生日志对应，不显示重复行。
3. 只读 DB 核对今天半开 UTC 范围内五个唯一可信身份及各字段合计；源集合、UI、DB 相同。

**缺口：** 原生映射、运行日平移程序、查询 schema、UI/test ID 与自动绑定。

### TC-TM005-RANGE-02 · 昨天

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 同一批原生数据；`yesterday` 在上海日界前 1 秒。**类型：** product_e2e。

1. 选“昨天”；卡片仅 1 次，input 100、output 10、total 110，cache 20、reasoning 2。
2. 趋势该日点 110、明细仅 `yesterday`；`today-gpt` 的上海 00:00 边界事件不能出现在此日。
3. 只读 DB 查询该当地日换算的 UTC 半开区间，仅返回 `yesterday`；确认筛选没有写用量表。

### TC-TM005-RANGE-03 · 近 7 天

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 上海当地 09-23 至 29 日语义窗口整体平移到运行日。**类型：** product_e2e。

1. 选“近 7 天”；卡片 7 次、total 17380，左边界 `day7` 包含。
2. 趋势非空日仅为窗口内 `day7=770`、`yesterday=110`、`today=16500`；明细恰为今天五项加 `yesterday/day7`。其余日期的显示状态按覆盖证明判，不从缺事件推断 0。
3. 只读 DB 对比 7 个唯一事件身份及 17380；重复 `today-gpt` 不入账。

### TC-TM005-RANGE-04 · 近 15 天

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 上海当地 09-15 至 29 日语义窗口。**类型：** product_e2e。

1. 选“近 15 天”；卡片 10 次、total 27830，`day15` 在左边界包含。
2. 趋势非空日为 `day15=1650`、`custom-start=2200`、`custom-end=6600`、`day7=770`、`yesterday=110`、`today=16500`；明细为这 10 个唯一事件。
3. 只读 DB 核对半开区间/10 个身份/27830；不把 `day30` 提前包含。

### TC-TM005-RANGE-05 · 近 30 天

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 上海当地 08-31 至 09-29 日语义窗口。**类型：** product_e2e。

1. 选“近 30 天”；卡片 11 次、total 31130，`day30` 在左边界包含，前 1 秒的 `outside30` 排除。
2. 趋势增加 `day30=3300` 点；明细为近 15 天十项加 `day30`，没有 `outside30`。
3. 只读 DB 核对 11 个身份/31130；刷新后仍一致。

### TC-TM005-RANGE-06 · 自定义半开日期

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 上海当地 09-20 至 21 日语义窗口，结束上界为 09-22 00:00。**类型：** product_e2e。

1. 在 UI 输入整体平移后的起止日并应用；卡片 1 次、input 2000、output 200、total 2200。
2. 趋势只有 `custom-start=2200` 非空点，明细仅该事件；`custom-end` 在排除上界，不能出现。
3. DB 只读查询 `[start,end)`；预期仅返回唯一 `custom-start`，查询不写入用量。

### TC-TM005-RANGE-09 · 起日大于止日

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 上海语义锚点平移后的起日 09-22、止日 09-20；此前已选“今天”显示 16500。**类型：** product_e2e。

1. 在自定义日期表单输入倒置范围并应用；UI 显示可识别的日期范围错误，不发起新查询，原卡片/趋势/明细仍对应今天 16500/五项。
2. 只读 DB 核对用量与设置，再恢复有效范围查询；预期倒置范围没有写入，有效范围仍显示 2200，前次错误不污染状态。

**缺口：** 错误文案/代码、查询观察器与 UI test ID，依赖交付后基线确定。

### TC-TM005-RANGE-10 · 空起日与空止日

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 两个独立变体 `TC-TM005-RANGE-10#START_EMPTY`（起日空、止日 09-21）和 `TC-TM005-RANGE-10#END_EMPTY`（起日 09-20、止日空）；此前已选今天 16500。**类型：** product_e2e。

- `TC-TM005-RANGE-10#START_EMPTY`：保持止日 09-21，清空起日并应用；预期拒绝查询，今天卡片仍为 16500、五条明细不变。
- `TC-TM005-RANGE-10#END_EMPTY`：保持起日 09-20，清空止日并应用；预期拒绝查询，今天卡片仍为 16500、五条明细不变。

1. 每个变体独立从今天结果开始，清空指定字段并应用；表单拒绝，保留原卡片 16500、今天趋势和五条明细。
2. 分别核对没有发起查询或写 DB；补齐字段后自定义有效窗口显示 2200。两个变体分别记录原始结果，不以其中一个通过代替另一个。

**缺口：** 表单/查询观察器和独立变体自动绑定，依赖交付后基线确定。

### TC-TM005-RANGE-08 · 刷新重启保持

**TASK：** `TASK-TM005-RANGE-QUERY`、`TASK-TM005-UI`。**输入：** seed42 双来源全量与近 30 天选择。**类型：** product_e2e。

1. 选择近 30 天并记录 UI/DB 初态；预期明细 11 项、total 31130，来源身份和覆盖状态与本例原始输入一致。
2. App 内刷新并重扫两个来源；UI 与 DB 均不增量，仍 11 项/31130。
3. 退出、重启安装后的同一 App/profile 并恢复筛选；UI 与 DB 仍 11 项/31130，授权状态和账号身份未串换。

### TC-TM005-MODEL-01 · 模型维度

**TASK：** `TASK-TM005-UI`。**输入：** 今天五项，两个来源至少各一项，模型名保持来源可识别标识。**类型：** product_e2e。

1. 选今天和模型维度；行值应为 `gpt-5=1100`、`sonnet-test=2200`、`qwen-test=3300`、`glm-test=4400`、`unknown-model=5500`，合计 16500。
2. 选 `unknown-model`；明细只含 `today-unknown`，Token 5500 有效，价格未知不显示为免费或 0 用量。
3. 刷新并重启 App 后再次查询模型维度；预期分组与明细仍与来源身份及只读 DB 一致。

### TC-TM005-MODEL-02 · 真实未知模型仍计用量

**TASK：** `TASK-TM005-UI`（依赖 `TASK-TM005-EVENT-CONTRACT` 的 `model_id=null` 事件）。**输入：** 以 2026-09-29 上海当地日为语义锚点并随运行日整体平移的两条独立可信调用：Codex A 于锚点 `2026-09-29T01:00:00Z`，input100/output10，无法从同一 turn 核实模型，规范事件 `model_id=null`；Claude B 于 `2026-09-29T02:00:00Z`，input200/output20、模型 `sonnet-test`。这与 `MODEL-01` 中字面名称为 `unknown-model` 的已知模型不同。**类型：** product_e2e；`E2E-TM005-001`。

1. App 从两类已验证原生日志采集 A/B 后选该日；卡片显示两次、已知 total330，明细分别保留来源与用量，A 不因模型未知而丢失。
2. 模型分组出现“未知模型”110 与 `sonnet-test`220，两组合计330；只读 SQLite 核对同一快照两条可信身份、A 的 `model_id IS NULL`、B 的模型及各自 input/output。
3. 刷新并重启 App 后查询同一日期；预期仍为两次/330，未知模型不被擅自改为最近一行模型，也不被标成零费用或零用量。

**缺口：** TM-003 对 `model_id=null` 的最终事件/诊断合同、可生成原生日志、UI 标识、SQL 与固定程序均待交付；设计预期已固定，运行前条件不满足即 BLOCKED。

## `E2E-TM005-002` / `AC-TM005-002` · 时区与数据三态

### TC-TM005-RANGE-07 · 时区与月界

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 上海 09-28 15:59:59Z/16:00:00Z 与 UTC 08-30 15:59:59Z/16:00:00Z 四个语义边界事件，整体平移整数天。**类型：** product_e2e。

1. 团队时区为 Asia/Shanghai 时，上海昨天仅 `yesterday=110`，今天含 `today-gpt=1100`；近 30 天含 `day30=3300`，排除 `outside30=11000`。
2. 经真实时区设置 UI 改为 UTC，用明确自定义 UTC 日期查询边界；09-28 UTC 同含 `yesterday` 与 `today-gpt`，total 1210；08-30 UTC 同含 `outside30/day30`，total 14300。事件 UTC 时间及 DB 源身份不变。
3. 重启后 UTC 设置保留；再查询 UTC 近 30 天对应自定义窗口，total 27830，两个 08-30 事件均排除。只有显示分桶变动，DB 事件数仍 12 唯一。

**缺口：** 团队时区设置入口及持久化合同、raw 时间字段、只读 SQL；不能用 renderer 本地时区替代团队设置。

### TC-TM005-RANGE-11 · 夏令时当地日长度

**TASK：** `TASK-TM005-RANGE-QUERY`。**输入：** 两个独立稳定变体 `TC-TM005-RANGE-11#SPRING` 与 `TC-TM005-RANGE-11#FALL`，团队时区经真实 UI 设为 `America/New_York`。春季 2026-03-08 的 UTC 半开界为 `[2026-03-08T05:00:00Z,2026-03-09T04:00:00Z)`；四个固定事件为边界前 `S0`（04:59:59Z，Codex 5/1）、起界 `S1`（05:00:00Z，Codex 9/1）、末界前 `S2`（次日03:59:59Z，Claude 18/2）、排除上界 `S3`（次日04:00:00Z，Claude 27/3）。秋季 2026-11-01 的界为 `[2026-11-01T04:00:00Z,2026-11-02T05:00:00Z)`；四个固定事件为 `F0`（03:59:59Z，Codex 5/1）、`F1`（04:00:00Z，Codex 36/4）、`F2`（次日04:59:59Z，Claude 45/5）、`F3`（次日05:00:00Z，Claude 54/6）。数值均为 input/output Token。**类型：** product_e2e；`E2E-TM005-002`。

- `TC-TM005-RANGE-11#SPRING`：以纽约 2026-03-08 为当地日，导入 `S0`–`S3`；预期仅含 `S1/S2` 两次、合计 30 Token，UTC 窗口长 23 小时。
- `TC-TM005-RANGE-11#FALL`：以纽约 2026-11-01 为当地日，导入 `F0`–`F3`；预期仅含 `F1/F2` 两次、合计 90 Token，UTC 窗口长 25 小时。

1. 各变体从独立空库、已验证双来源原生日志和相同登录身份开始；UI 选对应自定义当地日，春季仅 `S1/S2` 两次/30，秋季仅 `F1/F2` 两次/90，`S0/S3/F0/F3` 不在对应当日明细或趋势点。
2. 只读 SQLite 以明确 UTC 半开界核对两个源事件身份及 input+output 合计；春季窗口为 23 小时、秋季为 25 小时，不能使用固定 86400 秒上界。
3. 重启后时区与两变体结果分别保持；每个变体单独报告，不以其中一个结果覆盖另一个。

**缺口：** 来源时间可控原生日志、团队时区设置、IANA 转换实现、SQL 和两个稳定变体的固定 Playwright 绑定。TM-003 设计首次仅采最近 30 天；按当前真实时钟，固定的 2026-03/11 转换日不能同时进入采集窗口，也不能将它们平移整数天而保留同一 DST 日界。需先在 SOP-004/006 确定不改系统时间的可验证测试时钟/导入窗口机制或另一个真正可执行的产品判据；条件未满足时本 TC 为 BLOCKED。

### TC-TM005-STATE-01 · 无覆盖是缺失

**TASK：** `TASK-TM005-COVERAGE`。**输入：** 两来源均没有可证明覆盖的指定历史日，且没有可信事件。**类型：** product_e2e。

1. 从本例隔离库经 App 授权仅含近期日志的目录，打开早于已证实覆盖起点的自定义历史日；预期进入该日查询但尚不能凭空明细推断完整 0，DB 不新增用量事件。
2. UI 显示缺失/不可确认，不能显示完整 0；趋势点/明细状态与卡片一致。DB 只读证明没有该日可信事件，且覆盖记录并未声称完整。
3. 刷新后仍为缺失；空结果不能生成新零用量事件。

### TC-TM005-STATE-02 · 已覆盖零调用

**TASK：** `TASK-TM005-COVERAGE`。**输入：** 两来源对某完整当地日均有可核实、连续成功的覆盖证明，实际无调用。**类型：** product_e2e。

1. 在隔离 App 取得并核验两来源覆盖证明后选该日；UI 明确 0 次、0 Token，趋势该日为真实 0，明细为空。
2. DB 只读核对覆盖区间完整、事件数 0；无任何合成“零调用事件”。重启后状态仍为已覆盖零。

**缺口：** TM-003/004 目前均未定义可证明完整空日的来源事实/持久合同。若供应商日志无法证明，需按 SOP-002 调整 `AC-TM005-002` 的零值验收输入，不得靠测试直接写覆盖表冒充。

### TC-TM005-STATE-03 · 字段未知

**TASK：** `TASK-TM005-COVERAGE`。**输入：** 一条受支持原生会话有时间/模型但缺可信 usage，另有正常可信调用 110。**类型：** product_e2e。

1. App 先采集正常调用；预期 UI 与 DB 显示已知 110。
2. 追加缺 usage 原生事件并刷新；UI 显示不完整/未知诊断，不能把它当作 0 或把合计称为完整 110；DB 记录 unknown 原因且原正常事件不变。
3. 重扫并重启 App；预期未知诊断仍在，未因去重而被隐藏。

### TC-TM005-STATE-04 · 三态持久化

**TASK：** `TASK-TM005-COVERAGE`。**输入：** 分别预置上述无覆盖、完整空日、未知字段三种可核实源状态。**类型：** product_e2e。

1. 在 App 依次选择三日；每个日期分别显示缺失、0、未知，保存 UI/只读 DB 的各自状态。
2. 退出重启并改变团队时区后按新当地日重查；覆盖按 UTC 区间换算，三种状态不能互换或丢失。

### TC-TM005-STATE-05 · Claude 数值零与上游缺 usage 的歧义

**TASK：** `TASK-TM005-COVERAGE`。**输入：** TM-004 的两种受控 API 响应设计：显式报告零 usage 与整体省略 usage；Claude Code 2.1.126 原生阶段探针已发现后一种仍使 CLI 写出数值 0/0 usage。**类型：** product_e2e；`E2E-TM005-002`。

1. 分别由最终固定的原生数据程序生成两类日志，记录原始字节摘要与可观察字段；若两类 raw 不能区分，测试应把区别判据标为 BLOCKED，不能凭 API fixture 的隐藏输入让 App “识别”日志看不到的状态。
2. App 读取省略 usage 所得数值零日志；没有额外可核实证据时 UI/DB 应保持未知或未确定，不能显示“已证明完整零用量”。已知可信事件的合计不被该 0 改成完整。
3. 只有 TM-004 最终合同证明可区分显式零时，才对该变体单独断言真实零；重扫/重启不能把未知提升为零。

**缺口：** TM-004 尚未冻结零值来源判定和产品诊断合同；此例 `baseline_pending`/unexecuted，可能需要 SOP-002/004 修订可判定的真实零输入。

### TC-TM005-STATE-06 · 全量扫描分页与撤权时的覆盖

**TASK：** `TASK-TM005-COVERAGE`。**输入：** 本例拥有的 Claude 授权根含至少 1025 个候选文件、跨至少 5 个计划中的采集页；第一页含可信调用 A=100/10，后页另含可信调用 B=200/20。另有预览截断、页间撤权两个独立稳定变体。**类型：** product_e2e；`E2E-TM005-002`。

1. 从已安装 App 经 TM-002 真实 UI 授权根；预览即使只列前 1000 文件也不能使 TM-005 宣称全量覆盖。采集分页未完成时，UI 仅显示已知部分（A 若已被可信采集则为 110）及 `history_incomplete`，不显示完整 110 或空日 0；SQLite 只读旁证记录 continuation/诊断和已提交可信事件。
2. 正常变体继续到所有页面、必要深度与完整行/游标提交；若 TM-004 最终合同确认全部可信，UI/DB 合计 A+B=330，覆盖状态按真实证明更新，不遗漏第 1025 个及后续文件。
3. 撤权变体在两页之间撤销本例授权；扫描立刻停止，后页 B 不得读取，UI 保持已知部分 110 与不完整/失权提示，SQLite 不写完整覆盖或成功零。重授权后的补扫单独执行，最终值仍须 TM-004 身份/分页合同核定。

**缺口：** TM-002 `beginCandidateScan`/`nextCandidatePage` 等独立分页接口仍是草稿，TM-004 全量扫描和页间撤权程序未交付；本例原生文件生成、预览/continuation 观察器、SQL/重置与固定 Playwright 绑定均为 `baseline_pending`。至少1025文件/5页为输入设计，不能以当前预览或人工浏览代替产品 E2E。

## 数据与执行器检查（不冒充产品 E2E）

### TC-TM005-DATA-01 · 生成/重置可复现

**TASK：** `TASK-TM005-DATA`。**类型：** governance。**输入：** 同 seed42、同日锚点及两来源已验证版本，两个独立 run_id。

1. 调用计划中的 raw 生成器两次，核对受支持格式、事件身份、原始字节摘要与独立 expected 相同（run_id 标记可不同）；不得读取真实 `~/.codex` 或 `~/.claude`。
2. 只在已核对 owner marker、目录成员和摘要后调用重置；两个本例私有目录被清理，外部文件不动。程序不存在时为 BLOCKED。

### TC-TM005-DATA-02 · 独立预期与边界

**TASK：** `TASK-TM005-DATA`。**类型：** governance。**输入：** [语义 oracle](../../tests/fixtures/tm005-semantic-expected.json)和最终 raw 映射计划。

1. 在产品启动前运行固定语义 oracle 检查；预期 seed42 语义样例 13 行/12 唯一，双来源事件集合及平移后的上海/UTC半开区间与预存摘要一致；原生映射未就绪时本例仍 BLOCKED。
2. 对照原始字节与独立预期中的模型/字段、覆盖与 unknown 状态；缺原生日志/覆盖样例不得标可执行。该检查不能代替产品查询。

### TC-TM005-E2E-01 · 精确集合与最终安装包

**TASK：** `TASK-TM005-E2E`。**类型：** governance gate。**输入：** 固定候选 SHA、最终 DMG 与上述所有 TC 及此前已交付功能集合。

1. 门禁从 DMG 安装的正式 App 逐 TC 运行，核对实际安装包摘要、独立输入/预期、原始结果与全部清理；任一 FAIL/BLOCKED/零例/跳过/重试取绿均阻断。
2. 核对 TM-001→TM-004 的适用完整 E2E 及迁移/升级结果；只有本机机器门禁原始复核 PASS 才可签发本版通行证。当前无程序/包/原件，状态 BLOCKED。

## 基线缺口

所有产品级 TC 尚缺稳定的 Codex/Claude Code 原生日志映射、覆盖证明、客户端 schema/只读 SQL、完整逐步数据准备/重置程序、UI `data-testid` 和固定 Playwright 绑定。`TC-TM005-RANGE-10` 的两个空字段变体必须分别执行。若 TM-003/004 交付后字段/语义与本设计不同，先按 SOP-002/004 修订需求/设计及 oracle，再执行 SOP-008；不能修改预期使错误实现通过。实际输入/动作/预期和产品状态以当时提交和原始报告为准。

## 无原生日志依赖的纯统计辅助TC

以下三条只约束纯函数开发切片。共同输入为固定[合成fixture](../../tests/fixtures/tm005-core-slice.json)，`principal_key=synthetic-p1`、`Asia/Shanghai`当地日2026-09-29、UTC半开界 `2026-09-28T16:00:00Z` 至 `2026-09-29T16:00:00Z`。每例从新内存输入开始，调用待SOP-011固定的模块入口；不接用户日志、TM-002授权、产品Keychain、SQLite、IPC、服务或DMG。DB操作不适用，固定程序须比对JSON fixture摘要、各步返回和输入未被修改，结束只清理本例拥有的临时对象。未绑定程序时记录unexecuted，不以静态oracle脚本结果代替模块测试。

### TC-TM005-CORE-01 · 双来源可信事件与半开日汇总

**TASK：** `TASK-TM005-EVENT-CONTRACT`、`TASK-TM005-RANGE-QUERY`。**AC：** `AC-TM005-001`。**类型：** 辅助模块。**输入：** fixture 的A/B、另一主体C、界前D、排除上界E五条合成可信事件；身份键已由调用方保证来源限定且唯一，非原生调用ID。

1. 把fixture已给的固定UTC半开界`[2026-09-28T16:00:00Z,2026-09-29T16:00:00Z)`与主体传给纯统计函数，断言仅选择A/B两条、UTC上界排除E、前界排除D、跨主体排除C；输入数组及键不变。本例不验证IANA当地日转UTC。
2. 断言 input300、output30、已知total330、来源Codex110/Claude Code220、未知模型110/`sonnet-test`220；缓存读已知20但B为null所以该子项状态部分未知，缓存写整体未知，推理已知2但B未知；三个子项均不另加到330。
3. 分别把测试副本的source改为其他值、input改为负数、缓存读设为大于input及UTC时刻改为非法文本，逐个断言拒绝且无完整零/有效汇总输出；原fixture不改。无产品DB写入，旧产品`CONTRACT-01`/`RANGE-01`仍未通过。

### TC-TM005-CORE-02 · 未知用量诊断不补零

**TASK：** `TASK-TM005-EVENT-CONTRACT`、`TASK-TM005-COVERAGE`。**AC：** `AC-TM005-002`。**类型：** 辅助模块。**输入：** 同一A/B已知330、fixture 的Claude Code `missing_usage` 诊断及合成双来源complete覆盖假设。

1. 不带诊断运行A/B，核对已知330且没有因 `model_id=null` 丢掉A；未知模型分组110，来源两组仍分别110/220。
2. 加入同范围诊断后运行，断言 `status=partial`、`known_tokens=330`、`total_tokens=null`；诊断本身不产生调用或零Token，模型与来源的已知小计不变。
3. 只留该未知诊断、移除A/B运行，断言 `status=unknown`、`known_tokens=0`、`total_tokens=null`，不能把零个可信事件写成已确认零调用。产品`CONTRACT-02`、`STATE-03/05`仍需原生来源证明。

### TC-TM005-CORE-03 · 声明式覆盖状态代数

**TASK：** `TASK-TM005-COVERAGE`。**AC：** `AC-TM005-002`。**类型：** 辅助模块。**输入：** fixture 的五行 `coverage_algebra`；`complete` 仅是测试传入的合成假设，`product_coverage_proven=false`。

1. 两来源complete且无事件/诊断，断言 `complete/known0/total0`；清空事件但不给覆盖事实，断言不得自行推为complete。
2. 一来源missing且无可信事件，断言 `missing/known0/total null`；一来源missing且可信110，断言 `partial/known110/total null`。
3. 两来源complete、有可信110并有未知诊断，断言 `partial/known110/total null`；仅未知诊断无可信事件，断言 `unknown/known0/total null`。不读真实来源、不生成覆盖证明，产品`STATE-02/04/06`仍BLOCKED。

## 日期与双来源物理快照辅助TC

这两条新辅助用例各自独立：`CORE-04`只调用IANA当地日转换纯函数；`CORE-05`只查询本例拥有的合成双来源SQLite。它们的输入与逐步预期分别由[日期fixture](../../tests/fixtures/tm005-iana-core-slice.json)和[快照fixture](../../tests/fixtures/tm005-sqlite-snapshot-slice.json)固定，程序绑定当前为`null`、执行`unexecuted`。不得将纯日期函数或SQL种子结果移作安装App/原生日志产品TC的PASS。

### TC-TM005-CORE-04 · IANA当地日半开UTC界

**TASK：** `TASK-TM005-RANGE-QUERY`；**AC：** `AC-TM005-001`；**类型：** 辅助模块。**输入：** fixture的上海、UTC和纽约春/秋四个当地日，以及三个无效时区/日期。每一步从原fixture只读输入调用同一纯转换入口，不调整系统时钟；无数据库操作，结束丢弃本例内存对象并保存模块报告。

1. 分别转换`Asia/Shanghai`和`UTC`的2026-09-29：前者`[2026-09-28T16:00:00Z,2026-09-29T16:00:00Z)`，后者`[2026-09-29T00:00:00Z,2026-09-30T00:00:00Z)`，均24小时；时区变化不得改写传入事件UTC时刻。
2. 转换`America/New_York`的2026-03-08与2026-11-01：春日`[2026-03-08T05:00:00Z,2026-03-09T04:00:00Z)`恰23小时，秋日`[2026-11-01T04:00:00Z,2026-11-02T05:00:00Z)`恰25小时。每个fixture的`before`排除、`at_start`和`before_end`纳入、`at_end`排除；不能将当地日固定加24小时。
3. 非法IANA区`Mars/Olympus_Mons`给`invalid_timezone`，不存在的`2026-02-30`和非规范`2026-9-29`给`invalid_local_day`，不输出可查询的默认UTC范围或成功零。原产品`RANGE-07/11`仍需原生时间数据、App界面、固定时钟/导入窗及安装包E2E。

### TC-TM005-CORE-05 · 双来源隔离SQLite同窗只读快照

**TASK：** `TASK-TM005-EVENT-CONTRACT`、`TASK-TM005-RANGE-QUERY`；**AC：** `AC-TM005-001/002`；**类型：** 辅助模块。**输入：** fixture A/B为当前合成主体的Codex100/10与Claude Code200/20，C为另一主体，D在下界之前，E恰在排除上界，F仅供第二快照；所有记录只由本例固定准备程序经TM-003`UsageStore.commitBatch`写入本例0700目录/0600 SQLite，启用WAL以允许并发读快照。读端以当前主体和fixture给定UTC半开界查询实际物理`usage_event`；不解析厂商日志、不调用App/服务，不从`coverage`表推断任意空日完整。每故障变体重建自有空库，关闭连接后核对owner marker并只清理本例目录；保留原始SQL结果和模块报告。

1. 固定准备程序插入A–E并只读核对当前主体四事件与另一主体C；以`BEGIN`建立读事务，第一次查询选出的标签只为A/B，调用2、input300/output30/total330。C、D、E分别因主体或半开界排除，且查询过程零写入。
2. 在**同一读事务**依次取来源汇总`codex=110,claude_code=220`、模型分组`unknown_model=110,sonnet-test=220`、明细A/B和逐日点330；缓存读已知20但B为null，须同时返回未知行数1，缓存写/推理未知同理不得`COALESCE`成完整零或另加到总量。所有视图来自同一事件集合和UTC窗口，只返回HMAC键、数值和受限模型标识。
3. 第一读事务取得初始快照后，另一连接按固定准备程序提交F50/5；第一事务的后续来源/模型/明细/逐日仍为A/B、330。结束后新开读事务才见A/B/F三调用、input350/output35/total385、`codex=165,claude_code=220`。若环境无法让WAL并发提交，记录BLOCKED而不是修改一致性预期。
4. 对同库另查一个无事件当地日，既有`coverage`仅有`missing_before/scan_incomplete/last_scan_at_utc`，不能据空集合或本例种子声称双来源连续完整覆盖；返回无覆盖证明/未知而非产品已确认零。只读核对库/WAL与输出无合成原生ID、路径、正文或秘密；本例SQL种子不作为产品`STATE-02/04`的原生日志/真实授权旁证，产品`CONTRACT/RANGE/MODEL`亦未通过。

## 双来源查询视图独立辅助切片

`CORE-06`只冻结自包含查询适配器，使用真实`UsageStore.commitBatch`物理库与同一`UsageReadSnapshot`只读事务，不修改共享`main/index.ts`、preload/共享类型或现有renderer入口。固定[CORE05物理库种子](../../tests/fixtures/tm005-sqlite-snapshot-slice.json)及[本切片新增预期](../../tests/fixtures/tm005-query-view-slice.json)分别标明原始A–F与新增G/H；G是字面合法模型名`unknown_model`，H是99字符、含冒号且符合上游允许`^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`的Claude模型。`modelId:null`未知组须和字面名G分开；不能沿用旧查询的单个`unknown_model`字符串键。仅查本例0700目录中的0600 SQLite，真实原生日志、App/IPC/React、服务、Keychain和产品覆盖证明仍缺。

### TC-TM005-CORE-06 · 同快照双来源查询视图与模型身份

**TASK：** `TASK-TM005-RANGE-QUERY`；**AC：** `AC-TM005-001/002`；**类型：** `source_check`辅助模块。**输入：** 固定`Asia/Shanghai`当地2026-09-29对应UTC半开`[2026-09-28T16:00:00Z,2026-09-29T16:00:00Z)`；CORE05的A/B当前主体、C异主体、D界前、E排除上界、F并发写，以及独立G/H模型边界。每组从本例新建owner库或固定基线副本开始，事件仅经真实`UsageStore.commitBatch`提交，WAL供并发快照；查询不写库。

1. 准备A–E并只读确认五行与来源/主体键，查询适配器在同一只读事务内取主视图。只选当前主体A/B两行，calls2、input300/output30、可信已知330；来源Codex110、Claude Code220；`state=partial,knownTokens=330,totalTokens=null`，因为现有coverage只存`missing_before/scan_incomplete/last_scan_at_utc`，不能证明当地日完整。C、D、E各按主体或半开界排除，查询零写入。
2. 在步骤1的同一事务读模型、明细、趋势和子项：模型数组以`modelId:null`未知110和`sonnet-test`220分组，明细只含A/B的HMAC键、来源、UTC、受限模型和数字；当地09-29趋势点`partial/known330/total null`。cached read已知20且未知行1；cache write已知0/未知2，reasoning已知2/未知1，均不得补零或再加到总量。输出不含原生ID、路径、正文、secret或密文，四视图来自同一事件集合。
3. 保持步骤1读事务不结束，由另一连接提交F50/5：第一事务再次查询仍只见A/B、330及相同来源/模型/明细/趋势；结束该事务后新开事务才见A/B/F三调用、input350/output35/known385、Codex165/Claude220，状态仍partial、total null。WAL并发条件缺失时BLOCKED，不改预期。
4. 在独立A–E基线库提交G30/3与H40/4，再查同一当地日：四行A/B/G/H、input370/output37、已知407但总额仍null；来源Codex110/Claude297；模型必须为四个互异`modelId`：null110、`sonnet-test`220、字面`unknown_model`33、fixture中99字符含冒号标识44。H原值保留，不因旧80字符/无冒号过滤器拒绝；非法模型仍由入库合同拒绝/诊断，不合并到未知组。
5. 另查当地2026-10-01空日（UTC`[2026-09-30T16:00:00Z,2026-10-01T16:00:00Z)`）：`state=missing,knownTokens=0,totalTokens=null`，不得出现“已完整零”成功状态；只读核对库/WAL与查询输出的允许字段、连接和owner清理。真实产品RANGE/MODEL/STATE用例仍需要已安装App、真实服务、原生双来源日志、隔离SQLite及Keychain归属证明。

**DB/重置：** 只由`UsageStore`写入本例独占SQLite，查询适配器在同一事务只读`usage_event`，并发版本各建独立owner库副本；逐步保存SQL行集/哈希、事务边界和原始模块报告。关闭所有句柄、核对owner marker后清理本例库及WAL，不访问生产库。**程序准备：** SOP-011固定测试与suite/重置绑定尚未提交，机器目录`binding=null`、实际`unexecuted`；产品E2E与发行未通过。
