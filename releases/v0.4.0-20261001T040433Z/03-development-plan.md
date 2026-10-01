# v0.4.0-20261001T040433Z — 技术设计与开发计划（draft）

## 技术设计：SOP-004

依据：[需求](01-requirements.md)、[任务](02-breakdown.md)、[全局架构](../../docs/architecture/README.md)、[Claude 官方目录](https://code.claude.com/docs/en/claude-directory)、[官方用量语义](https://code.claude.com/docs/en/agent-sdk/cost-tracking)。来源数据实际 schema 尚未被确认，以下是接入目标及拒绝规则；字段名、版本支持和 fork 判定须由版本化 raw 证据冻结后才能作为实现合同。

### 已提交的有限解析器切片

开发分支报告提交 `f2c3972` 已加入纯内存 `claude-format.ts` 与11项固定单元检查；文档会话只读核实源码文件及桌面36/36、治理452/452原始日志尾部。该切片只接受已在隔离2.1.126原件证实的主会话、原样复制fork、同ID双内容块和可核实单层Agent父子关系；完整LF、未知/非法诊断、冲突保留及0/0歧义在模块中实现。改写UUID、fork-context-ref、嵌套Agent和有效零仍无足够原生证据。TM-002目录能力、TM-003 HMAC/SQLite、真实App UI/IPC及逐TC产品E2E尚未接入，整版仍draft，不把单元结果写成产品PASS。Git对象库暂不可见，完整提交对象/tree待读回。

### 数据流和接口边界

真实 UI 通过 TM-002 原生目录面板选择 Claude 根目录 → TM-002 App 层限制读取范围并报告撤销/失权 → Electron 主进程限域枚举会话/子代理 JSONL → TM-004 增量读取与来源解析 → TM-003 规范事件/本地 SQLite 唯一约束 → TM-003 诊断聚合 → 真实 UI 显示可信用量和覆盖状态。用户已明确 App 可持久保存所选目录的必要私有 locator，TM-002 正在固定隐私例外、跨重启恢复和接口；接入前按其稳定提交复核。不能把 App 层约束称为 macOS 沙盒/TCC 持久授权。服务端同步仍以 TM-007 的白名单接口为后续任务；不得直接上传原始日志。本版不得打开开发者默认 `~/.claude` 生成测试数据。

TM-003 已提交 `dbcaa5e` 的**共同草稿身份合同**为 `{source, source_scope_key, source_event_key, occurred_at_utc, model_id|null, input_tokens, output_tokens, cached_input_tokens|null, cache_write_input_tokens|null, reasoning_output_tokens|null, source_version, identity_scheme_version}`；总量仅为 input+output，缓存写入/读取和推理是子项，不再相加。`source` 固定枚举 `codex` / `claude_code`；`source_event_key = HMAC-SHA256(local_secret, length_prefix(["usage-identity-v1", source, provider_call_scope, canonical_call_id]))`，长度前缀逐个 UTF-8 字段编码；Codex 使用 `provider-response` + 原生 `payload.response_id`，Claude 使用 `provider-message` + 原生 `assistant.message.id`。身份方案版本不随 CLI build 改，`source_version` 单独记录已核验来源版本；`principal_key` 另按已验证账号隔离，客户端 SQLite 草稿主键 `(principal_key,source,source_event_key)`。`source_scope_key` 是会话/线程/agentId 等来源归属的不可逆摘要，**不进入唯一调用键**：同一 Claude 响应的两内容块与 fork 复制父记录仍只计一次，两个工具的同字面 ID 因 source 域不同必须各计一次。TM-004 另维护可验证的父/子/项目归属映射，但不保存原生 ID 或完整路径。跨 Agent/会话同 ID 且无连续块或复制关系、或同 ID 用量/模型冲突时保留首个可信事件、记 `unverified_inheritance`/`identity_conflict` 并标覆盖不完整，不能静默重复或覆盖。仅可核实身份、非负用量可进入 SQLite；缺 ID/usage 不生成数值0。TM-003 的设计提交已稳定可读，实际 schema/程序和产品接口尚未实现；接入前仍须按其最终实现复核。IPC 只能返回汇总与受限诊断，不允许 renderer 传任意路径或获取 JSONL 行。

TM-002 UI 候选预览上限为1000文件、5000目录项、2秒，**不能充当采集全量列表**。其独立采集能力草案为 `beginCandidateScan` → `nextCandidatePage`（每页最多256个、opaque cursor、candidates、complete/incomplete reason）→ `openCandidateReadOnly(candidateToken)` → `cancelScan`；每次分页/打开重验授权、主体、根 dev/ino、文件边界和撤销世代。TM-004 只通过该能力在同一主体、同一授权根下续扫主会话与子代理；页间失权或账号切换立刻停扫。仅当所有页面/必要深度已读、文件完整行与游标提交完成且无阻断诊断时，才可声明本次范围覆盖完成。预览截断、内部 continuation 尚未耗尽、深层子代理未访问或扫描超时都使 TM-003 `coverage.scan_incomplete=1`，UI 显示历史不完整；不能把 UI 预览数当源总数。以上 API 名称/页合同仍是 TM-002 草稿，稳定提交前不写产品依赖实现。

### 已安装 2.1.126 的候选来源字段

只读二进制检查（摘要和偏移见需求文档）给出两种 fork 线索：复制记录可带 `forkedFrom.sessionId/messageUuid`，子代理继承上下文可用 `fork-context-ref` 的 `parentSessionId/parentLastUuid` 指向父会话。本机2.1.126 原生探针实际确认 `--resume ... --fork-session` 会建立新 `sessionId`，将父会话 UUID、`message.id`、usage 逐条复制，再追加新调用；复制记录**没有** `forkedFrom`。因此不能将该静态字段设为识别所有 fork 的必填字段；在可证实的跨文件相同调用身份和父链下，继承行仅作历史，新增行才计数。对于 UUID 改写和 `fork-context-ref`，当前没有原生样本；只有父消息存在、来源可追溯且链可达时才可证明继承。缺父文件、缺目标 UUID、标记与实际内容冲突均进入未确定诊断。不能把所有 fork 都当作完整历史副本，也不能只凭改写 UUID 认为是新调用。原生 Agent 子文件位于父会话目录下，带 `agentId`、`isSidechain=true`，与父文件同 `sessionId`；主/子身份不能只用 `sessionId`。子代理路径可能嵌套，扫描仍须受 TM-002 App 限域；`.meta.json` 不提供已验证的项目归属。此探针不替代真实安装 App E2E，字段在其他版本不得自动继承支持。

### 解析、增量和幂等

#### 已打开句柄的独立reader切片

本切片由调用方提供**已获得且已核验的只读 FileHandle**、合成稳定文件身份、前次完整LF游标和32字节本地秘密；reader不接受路径、不负责授权或打开来源。固定 `tests/fixtures/tm004-reader-core-slice.json` 从隔离Claude 2.1.126投影行派生746字节完整assistant行（13/7=20）。单次读取上限1MiB，只有最后一个完整LF及以前的字节可进入解析与游标；半行/读限保留`scanIncomplete`和诊断，不把未提交尾字节算成调用。游标携带完整LF后字节偏移与 `HMAC-SHA256(secret, 从文件起点到该偏移的原始字节)`，不持久化明文前缀或无密钥SHA。若短于游标、身份不符或前缀MAC不符，从0重扫并报`cursor_reset`；重扫仅是reader输出，TM-003事件唯一键和同事务提交才提供跨运行幂等。读取期间文件变化、秘密不可用/长度错误、越界输入须拒绝且不交付新游标。完整LF内非法UTF-8可按已确定诊断推进该行偏移，未知2.1.127结构只给诊断；两者不得制造可信调用或零用量。输出不得带原始路径、正文、秘密。

TM-002已提交的`SourceCandidate.fileIdentityDigest`从根与文件dev/ino派生，不包含size/mtime，普通追加和同inode前缀改写均不改变它。TM-004将`sourceId`和该稳定摘要以`claude-file-v1`长度前缀域作本机HMAC，得到64hex文件`sourceKey/fileIdentity`；另以独立`claude-root-v1`域从`sourceId`产生64hex `rootKey`，不直接将未加密的候选摘要或相对名写入用量库。`TC-TM004-CORE-02`核对普通追加沿原游标续读，同inode/同size/同mtime前缀改写仍由keyed prefixMAC触发重扫。真实文件打开、每次授权/边界重验、SQLite event+cursor原子事务和coverage缺口判定仍受TM-002/003依赖，全部产品TC保留BLOCKED。

#### 主进程触发端口的独立切片

`TC-TM004-CORE-04`仅让主进程接收`sourceId`，从注入的已验证账号快照查授权源，通过注入的TM-002扫描端口取得候选，再在账号/授权世代/取消状态的提交守卫下调用注入的同步提交端口。请求中路径字段、无效主体或sourceId必须在扫描前拒绝；扫描中主体变化、撤权或取消须取消扫描且不提交；成功只返回数字汇总、覆盖状态和受限诊断。固定输入为[合成端口fixture](../../tests/fixtures/tm004-trigger-core-slice.json)，不使用真实账号、Keychain、日志、SQLite、IPC或App。此模块顺序检查不能证明真实权限/事务或产品E2E；稳定TM-002/003接口整合后仍按原产品TC复核。

该触发端口的错误码固定为：请求额外路径字段或sourceId格式错误`invalid_collection_request`，账号未验证/停用/须改密`collection_unavailable`，合法但不属当前主体的sourceId`source_not_authorized`，预先或途中取消`collection_cancelled`，扫描中换账号/撤权`collection_stale`。成功只返回`summary`数值及`diagnostics:[{code,count}]`，空诊断为`[]`；失败绝不返回缓冲的调用、游标或原生身份。切片程序必须逐一断言该映射，不自行选码。

`TC-TM004-CORE-05`在独立隔离SQLite上验证来源与存储适配：同一根的三个文件各自`sourceKey=fileIdentity`，按`claude-file-v1`域从`sourceId`和TM-002 dev/ino摘要导出；`rootKey`只按独立`claude-root-v1`域从`sourceId`导出。每文件的已接受事件、诊断和游标必须保留其来源键，待所有页稳定且守卫通过后，调用TM-003 `commitScanBatch`**一次**同步提交，失败整代回滚。Claude JSONL无Codex的原生turn字段，主调用使用`claude-main-v1`、可证实Agent使用`claude-agent-v1:<agentId>`、缺agent的sidechain使用`claude-unverified-v1:<canonicalCallId>`作为仅供scope HMAC的代号；`source_event_key`仍仅按provider-message原生调用ID的独立HMAC，代号不参与唯一调用键，也不直接入库。缺agent父归属诊断保持覆盖不完整，不能据scope代号猜项目。固定fixture是合成解析后记录，不是厂商原件；真实数据来源、App/IPC/服务与产品E2E仍受原20条TC约束。

入库前对Codex与Claude的`model_id`采用共同有界标识规则`^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`；不合规则设`null`并产生`invalid_model_id`及覆盖缺口，不能把模型字段直接当可信路径/正文。`CORE-05`的c文件使用合成prompt/路径哨兵作固定负例，核对SQLite及WAL无哨兵；真实安装App的隐私TC仍需另验。

只处理最后一个换行已写完且能完整解析的事件。对末尾半行保留读取偏移前状态，补写后重新尝试；文件缩短、更换或移动时按文件身份与内容来源核对重新扫描，但已提交事件唯一约束保持。SQLite 单事务提交事件键、用量及游标，崩溃后重扫必须幂等。跨文件复制、主/子代理引用及 fork 历史去重不能仅靠行号或会话消息 ID；原生2.1.126双 text 内容块证实同一次 API 响应可写成两条 assistant 行，保留相同 `message.id` 与完整 usage 31/9，唯一调用应只计一次40。父 Agent tool_result 的 `<usage>total_tokens: 25</usage>` 是子代理19/6摘要，不得再次入账。会话 ID 也不能单独标识调用，子代理与父文件可共用它；应联合真实来源、agentId及已证明的调用身份设计唯一性，跨 fork 改写 ID 的规则仍待原件。无法证明是新调用时隔离诊断，不能增加可信汇总，也不能悄悄丢掉待核实条目。

子代理文件只在 raw 可证实的父会话关系下归属父项目；模型仍按其真实调用独立计。项目目录的完整绝对路径不入库，持久化可用受限相对标识或不可逆摘要；缺父关系显示未归属，不猜项目。授权撤销或文件失权立即停扫并显示读取受阻；保留已计量历史与游标，重新授权后按唯一键补采，绝不因失败写入成功零值。

### 版本、错误与隐私

建立 `supported_raw_versions` 表，仅列通过原始生成或官方版本化样本和安装App检验的精确版本/结构组合。未知结构、缺usage、负数或非整数、缺模型/时间、JSON错误各有诊断码与数量；不会把未知当零或推断正文。畸形合成 API 完全省略 usage 时，2.1.126 CLI **仍会在 JSONL 补出 0/0**；采集器无法单凭该行区分“真实已知零”与“上游缺失后被归零”。因此有效零调用的证明和版本支持要另有独立来源；本轮不能把 0/0 raw 作为已验证有效零 fixture。每次扫描限制单行大小、文件数、时间和取消入口；超限或失权安全停止并保留事务一致性。诊断不含提示词、代码、密钥、原始完整路径。源文件严格只读，不修改 Claude 配置、日志或缓存。

### 迁移、恢复与兼容

TM-003 SQLite schema 尚未提交，不能现在决定是否需 SOP-016 迁移。其现阶段设计为首次建立 `usage_event`（TM-002 前序版无历史用量），引入显式 `source/source_scope_key/source_event_key` 可在首次建表完成；若 TM-003 在 TM-004 前已稳定发布旧 `response_key` 表，必须依 SOP-016 先备份、转换/映射旧键、核对每主体每来源调用数及总量、验证中断/重复与恢复，再读写新表。未来身份方案升级同样不得仅更换 HMAC 域而使旧事件重扫双计。接入前逐列比较事件/游标/诊断表；0.3→0.4 自动更新必须验证授权、游标、账号和既有统计保留。尚无实际上一稳定包，按真实发布状态决定升级输入；不使用未发布 0.3 文件假称稳定版。

## 实施计划：SOP-005

1. 继续本版 `TASK-TM004-DATA` 的原始证据调查；已用隔离 CLI 2.1.126 + 合成回环 API 得到主、单层子代理、复制历史 fork 和重复内容块原件，命令及 SHA 见本机 `.local/ci/tm004-claude-2.1.126-research/evidence-manifest.json` 与 `followup-evidence-manifest.json`。补齐改写 ID、`fork-context-ref`、嵌套子代理、有效零及半写入等缺口；支持列表仍 `baseline_pending`。TM-002/003 提供稳定提交及接口后核对并更新本设计。
2. 按 [逐项用例](04-test-plan.md)完成每项 TASK→TC 输入、有序动作、独立预期和 reset；`TASK-TM004-DATA/E2E` 建立仓库固定测试与真实安装 App 绑定。只有文档完整经 SOP-008 baseline 后，才可开展依赖设计的测试与产品实现。
3. 依次接 `SOURCE`（TM-002）、`PARSER`、`LINEAGE`、`INCREMENTAL`（TM-003）、`DIAGNOSTIC`；先取得对应可复现红测，再改实现。所有读取在主进程，renderer 仅展示状态；不在服务端或测试脚本旁路导入规范化事件。
4. 对 schema 变化执行 SOP-016；SOP-013 构建、治理/服务/桌面单元检查；SOP-014 最终安装 App 的 TM-004 全部细TC与 TM-001/002/003 全回归；SOP-017/018 之后由总控按 SOP-019 集成/推送。失败保留原件，SOP-015 修复后新run重测。

| 范围 | 拟改位置 | 局部检查 | 当前状态 |
| --- | --- | --- | --- |
| SOURCE/PARSER/LINEAGE/INCREMENTAL | `apps/desktop` 主进程来源适配器及 TM-003 存储接口 | 原始fixture驱动的解析/事务测试和真实App重扫 | BLOCKED：依赖及raw缺失 |
| DIAGNOSTIC | preload受限IPC、React诊断视图 | 缺字段/失权真实UI断言 | BLOCKED：接口缺失 |
| DATA/E2E | `tests/` 原始fixture与 `apps/desktop/e2e` 固定Playwright用例 | 每TC按编号单独可跑、逐步报告 | BLOCKED：安装执行器及raw缺失 |
| RELEASE | 本版档案、矩阵、总表、Changelog | structure→baseline→完整门禁 | 仅草稿编制中 |

本分支只改 TM-004 拥有文件和本版文档；对共享接口先核对依赖分支后再整合，不覆盖其他需求工作树。当前分支的基点仍没有 Electron 工程；TM-001 另有干净候选 `3467dc1`，只读核对表明其 `apps/desktop/src/main/index.ts` 在 `tokenmeter:invoke` 校验发送窗口、主 frame 和自有页面，preload 的 `Bridge`/`Snapshot` 定义在 `src/shared/types.ts`，主进程模块可在 `src/main/collection/` 加入但必须沿用同级安全校验。其 `scripts/run_test_case.py` 已存在，然而 `scripts/granular_e2e.py` 的 case 解析仅接受 `TC-TM001-*` 并只映射 TM-001 Playwright spec；本版20条 TC 在候选中全部**不可执行**。后续应在总控整合后的真实基线上扩展固定用例目录、调度、证据与门禁，不能仅把 TM-004 ID 写入 manifest 当作绑定完成。该候选未运行最终 DMG 产品 E2E，且 TM-002/003 接口未稳定，不能声称 TM-004 GUI 验收可运行。下一步：[测试计划](04-test-plan.md)。
