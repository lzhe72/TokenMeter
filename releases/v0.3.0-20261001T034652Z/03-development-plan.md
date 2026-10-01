# REQ-TM003 · 技术设计与开发计划

**release_id：** `v0.3.0-20261001T034652Z`　**状态：** draft；本节技术设计按 SOP-004 先于下方 SOP-005 实施计划编制。

输入：[需求](01-requirements.md)、[任务](02-breakdown.md)、[全局架构](../../docs/architecture/README.md)、[Electron 本机合同](../../docs/architecture/01-electron-local.md)及[来源证据](01-requirements.md#来源核验及支持条件)。

## SOP-004 技术设计

### 数据流与模块边界

React 只调用受限 preload 的 `collection:getState` / `collection:refresh`，不得提交任意路径。Electron 主进程只通过 TM-002 的已确认来源只读能力取得当前可读状态与受限枚举/打开入口，且每次扫描前校验已验证的规范化 origin+account.id；具体能力可由原生选择器或后续 OS 沙盒授权实现，本版不固定其机制。主进程在该能力范围内解析完整 JSONL 行。候选事件经身份和字段校验后，在同一 SQLite 事务内插入去重事件、诊断和读取游标。UI 从主进程聚合只读状态，绝不读取原始日志或源文件路径。服务端本版不接收采集数据；TM-007 才定义同步 API。

建议新模块置于 `apps/desktop/src/main/collection/`：`codex-format.ts` 只解析来源结构；`source-reader.ts` 管完整行及根边界；`usage-store.ts` 管 SQLite、事务和 schema；`collector.ts` 管调度和授权状态；`collection-ipc.ts` 管窗口/来源验证。TM-002 授权模块保留其文件所有权；本版通过可替换的窄能力接口适配，不在两个会话同时改其实现。用户已确定 macOS 原生目录选择器、App 私有保存所选目录、由 App 强制限制后续读取的非 MAS 路线；用户已认可必要的当前用户私有可解析 locator；按 SOP-004，该 locator 只能由 TM-002 在当前用户私有来源配置中用 macOS 系统密钥保护能力加密保存，目录0700、文件0600，无明文回退；解密失败/密钥不可用须停读并要求重选，App 内撤销删除密文，完整路径与密文不得进入用量库、同步、日志、报告或 Git。具体字段及重启恢复行为待 TM-002 稳定合同确认；TM-003 只消费其已确认只读能力，不自行持久化 locator。接口至少交付已验证主体键、已确认只读来源能力、失效/撤销/切换身份通知与重新确认后的新能力；renderer 不能传任意绝对路径，TM-002 候选阶段只在明确深度与数量上限内递归列普通 `.jsonl` 的相对名称/大小/mtime，不交正文也不证明格式被 TM-003 支持；TM-003 在已确认能力内独立解析经版本验证的原生结构，样例固定于 `sessions/YYYY/MM/DD/*.jsonl`：TM-002 草稿以所选根为深度0，最多深入8层目录、1000文件、5000目录项、2秒，四层子目录在范围内；候选超限时“不完整”，TM-003 不把预览数量或“不完整”状态解释为历史覆盖完成。上述仍待 TM-002 稳定接口/fixture 核验。React 卡片与 preload 桥只新增 TM-003 所需字段。

### 来源合同与计量

首批拟支持的可计量来源是 Codex rollout `session_meta` + `token_usage_record`；隔离来源研究已取得本机 `0.158.0-alpha.2.1` 的原生样例，正式 SOP-010 数据交付仍待门禁。该版本记录器把每行写成含 UTC `timestamp`、`type` 和 `payload` 的 LF 结尾 JSONL。每个记录的 `payload.response_id` 是去重主键来源，`payload.usage` 是该响应增量；`turn_token_usage` / `thread_token_usage` 是累计核对值，不能再相加。`event_msg.token_count.info.total_token_usage` 同样是快照；只有此结构而没有稳定响应身份时显示 `unverified_cumulative`，不生成可信成功事件。`rate_limits` 无用量且 `info=null` 时记 `missing_usage` 诊断，不生成零值用量事件。未核验版本不自动扩展兼容范围。

同版本官方实现进一步证明：`response.completed` 的 `usage` 被写为单次记录，turn/thread 字段由状态逐次相加；完成事件没有用量时不写该记录。官方 app-server 的历史用量 fixture 只有 `event_msg.token_count`，故只能覆盖“不可信累计快照”负例，不能充当正例。隔离 CLI 原件已验证恢复时同一根文件追加新逐响应记录，普通 `exec fork` 的子文件仅有新响应，但新记录的 `thread_token_usage` 可延续父线程累计：父 A100/10+B50/5 后为150/15，子 C20/2 的 `usage` 为20/2，`thread_token_usage` 为170/17；只对 `usage` 计量。无用量完成会写 `event_msg.token_count.info=null`，不写逐响应记录。官方子代理 fork 代码清除继承记录，但子代理实际落盘仍未核验；`session_meta.source` 可能承载含 `parent_thread_id` 的 `SessionSource::SubAgent(SubAgentSource::ThreadSpawn)`，不据普通 CLI fork 推定子代理兼容。所有来源只处理必要字段，忽略并不保存原始 session meta 中的 `cwd` 等敏感值。

`input_tokens` 与 `output_tokens` 必须是安全整数且非负，`total_tokens` 若存在须等于两者之和，否则诊断 `invalid_total`；`cached_input_tokens` 与 `cache_write_input_tokens` 如存在必须分别处于 `[0,input]`，`reasoning_output_tokens` 如存在处于 `[0,output]`。缺可计量字段时诊断 `missing_usage`；不是 0。缓存写入若来源字段存在则单列，未见字段为 unknown。两次不同 `response_id` 即使数字相同也分别计量；相同 ID 且用量相同不重复，相同 ID 却用量不同记 `identity_conflict`，不改已可信事件。模型从可证明同一 turn 的原生上下文取得，否则记未知模型标识，不擅自取最近行。所有时间要求可解析 UTC；不合格时间诊断并不计入时间聚合。

分支使用 `session_meta.id`、`forked_from_id` 与逐响应 ID。隔离的普通 CLI fork 原件没有复制父逐响应记录，但保留父累计在子记录 `thread_token_usage` 中；子代理只能按源码草稿推断，待单独原件验证。即使原生文件搬移、恢复重放或研究 fixture 人为复制父记录，DB 唯一约束仍阻止相同响应重复。若遇到无法确认响应身份的继承结构，诊断 `unverified_inheritance`；不以相似 token 数推断相同响应。父源缺失时已验证的新响应仍可保留自身用量，历史覆盖标为不完整。

与 TM-004 冻结的规范事件身份 v1：`source` 明确为 `codex` 或 `claude_code`，`source_event_key=HMAC-SHA256(local_secret, length_prefix(["usage-identity-v1", source, provider_call_scope, canonical_call_id]))`；四个字段各先以严格 UTF-8 编码、前置无符号 uint32 大端**字节**长度，再按顺序串接作为 HMAC-SHA256 消息；`local_secret` 是本例私有 profile 中持久保存的32字节随机值，结果为64位小写十六进制。原生 ID 只按指定字段提取并核验为非空有效 Unicode 字符串，不做 trim、casefold、NFC/NFD 或替换字符重编码；不成对 surrogate、超过 uint32 字节长度、错误 source/scope 配对均拒绝并诊断。身份方案版本不随 CLI build 更新。固定公开测试密钥、五条前像/摘要见[共享身份向量](../../tests/fixtures/tm004/identity-v1-vectors.json)；独立核验程序位于上游 TM-004 提交，尚未并入本树，正式固定测试绑定待本切片实现，来源是 TM-004 干净提交 `d6c90e35d9018459602dbc1851c3e7deecace454`；公开测试密钥不得进入产品 profile。Codex 的 scope=`provider-response`、call ID=`token_usage_record.payload.response_id`；Claude 的 scope=`provider-message`、call ID=`assistant.message.id`。`session/thread/agentId` 的不可逆归属键可辅助核对，但不进入唯一键：Claude 同响应双内容块和普通 fork 复制同 ID/usage 属已证实重复；Codex 同 ID 的恢复重放亦只计一次。不同来源的相同字面 ID 必须产生不同键。同来源同 ID 在不同 Agent/会话出现且无证据证明复制时保留首可信事件、诊断 `unverified_inheritance` 并标覆盖不完整；用量或模型不一致时诊断 `identity_conflict`，不覆写首事件。缺 ID 不计量。Claude 子代理、改写 UUID 等未证实变体不声明已支持；原始 ID 不落库。

### SQLite、隐私与迁移

使用 Electron 44 所带 Node 24 的 `node:sqlite`，仅在主进程打开独立客户端库；Electron 44 的 [Node 版本](https://www.electronjs.org/blog/electron-44-0)与 Node 24 的 [`node:sqlite` 文档](https://nodejs.org/download/release/latest-v24.x/docs/api/sqlite.html)是选择依据，真实包中需先做启动探针。数据库路径须在经 TM-001 验证的私有 `userData` 下，0700 父目录、0600 文件，拒绝 symlink/其他 UID，不与服务端 `database/test` 或 `database/production` 共用。

拟定 schema v1：`usage_event(principal_key, source, source_event_key, source_scope_key, session_key, occurred_at_utc, model_id NULL, input_tokens, output_tokens, cached_input_tokens NULL, cache_write_input_tokens NULL, reasoning_output_tokens NULL, source_version, identity_scheme_version, created_at_utc, PRIMARY KEY(principal_key,source,source_event_key))`；`source_cursor(principal_key, source_key, root_key, file_identity, committed_byte_offset, size, mtime_ns, updated_at_utc, PRIMARY KEY(principal_key,source_key))`；`collection_diagnostic(id, principal_key, source_key, code, occurred_at_utc, count)`；`coverage(principal_key, root_key, earliest_verified_at_utc NULL, missing_before INTEGER, scan_incomplete INTEGER, last_scan_at_utc NULL, PRIMARY KEY(principal_key,root_key))`。`principal_key` 为已验证规范化 origin+account.id 的本机 HMAC 身份；`source_event_key/source_scope_key/session_key/root_key/source_key` 为本机随机密钥下的 HMAC-SHA256 摘要；密钥只在私有 profile，原始路径不存库。`source_scope_key` 仅作归属与跨 scope 冲突诊断，不作唯一键。诊断只留代码、数量和不可逆源身份，不留错误原文。事务和唯一约束同时覆盖事件及游标；失败回滚，下次重扫。

SQLite schema 由 `PRAGMA user_version` 驱动；从上一稳定 TM-002 版升级时首次创建客户端采集表，源版没有可信采集事件，验收核对账号/授权保留及首次 A 采集，不能虚构旧版用量。本版在首次建表前固定跨来源身份域，没有历史 `response_key` 事件需要迁移。未来若身份方案版本改变，必须迁移或映射既有 `source_event_key`，防止同一旧日志重扫生成新键并双计；不能仅改 HMAC 输入。若本机 `local_secret` 丢失、损坏或与已有事件键不符，停止该主体采集并要求恢复原密钥或经可核验迁移，不生成新密钥重扫旧日志；已落库事件保持只读可见而覆盖标不完整。升级前复制到本轮拥有的私有备份并验证能打开。中断后旧库可恢复；不迁移用户服务端生产库。后续 schema 升级须保留已采集事件；删除源文件不删除事件。历史覆盖只声明最早可证明的事件和源文件状态，早于边界显示未知/缺失。90 天本地保留规则属于长期合同；清理程序不得删除未确认同步的数据，TM-007 前没有上传确认，故本轮不做常规用量过期删除。

### 扫描、权限与故障

只通过 TM-002 已确认来源能力枚举；每次扫描及每次打开文件前重新校验能力和已验证主体，不接受 renderer 传入路径。TM-002 UI 候选预览的1000文件/5000项/2秒上限不构成全量历史证明；TM-002 已接受但尚未实现的草稿接口为 `beginCandidateScan`、每页最多256项的 `nextCandidatePage`（opaque cursor、相对名/文件身份、complete/incomplete）、`openCandidateReadOnly(candidateToken)` 与 `cancelScan`；正式采集需经同一已确认主进程能力续扫，逐次重验 origin/account、collectAllowed、根 dev/ino、撤销世代及相对边界，撤销/换身份/失效立即令游标作废。每页在最终 `complete=true` 前均为暂定；跨页发现任一目录 dev/ino/mtime/ctime 改变、撤销或主体切换时，丢弃该 generation 的全部页和暂存解析/同步结果，从新 generation 的第1页重新扫描，不能续扫旧 cursor。TM-002 的 `complete` 只证明候选目录树复核，TM-003 仍须独立证实每个日志正文完整读取且稳定后，才能提交本轮事件、游标及覆盖状态。页未完整消费或接口只交截断预览时 `coverage.scan_incomplete=1`，不能声称源历史扫描完成；预览上限后仍有日志的产品 TC 必须读到该日志才可 PASS。根边界与越界 symlink 检查由能力实现和采集器双重执行，失效时停止所有属该主体的扫描。首次扫描按原生事件 UTC 时间应用最近 30 天窗口，缺失或无效时间只诊断，不能借文件名/mtime 推定事件时间；窗口基于扫描开始时固定的 UTC 当前值，运行中不移动边界。单文件按字节只提交以 LF 结束的完整行，UTF-8/JSON 错误记诊断并前进至该已完整行末；未闭合尾行留在游标之外。若文件身份、大小或前缀校验与游标不符，从 0 重读并依靠来源域内的调用身份去重。重命名不改变事件身份。文件 watcher 触发、30 秒补扫与手动刷新共用串行扫描锁；退出取消下一次调度并关闭库。

授权失效、撤销、退出或已验证 origin/account.id 切换时立即关闭句柄、停止对应主体 watcher/补扫并撤销缓存的能力；界面按新主体显示其独立状态。新的确认通知经 TM-002 合同取得新能力再补扫，旧主体事件与游标不混入新主体。文件读取 EACCES、权限撤销、磁盘满、SQLite 损坏都留下结构化诊断，不宣称成功；失败不推进游标。离线网络不影响本地采集。本版不上传、也不请求服务端统计。

### IPC、界面及可验证观察面

状态结构仅含 `trusted_input/output/total/cached_read/cache_write/reasoning_output`、`unique_responses`、`last_scan_at_utc`、`coverage_start_utc`、`history_incomplete`、授权状态、诊断代码及数量。未知 cached 以 `null` 显示“未知”，不能伪装 0。renderer 无 Node/文件/SQLite 权限，主进程核验 IPC 来源窗口。产品 E2E 可通过 UI 观察总量和诊断、通过测试拥有的 profile SQLite 做只读旁证；不加测试专用 IPC 成功旁路。

## SOP-005 开发计划与交接

先行模块切片限定为 `TASK-TM003-SOURCE` 中的已核验来源形状、`TASK-TM003-PARSE` 的完整 LF 行解析/数值诊断，以及 `TASK-TM003-IDENTITY` 的公开测试密钥身份函数与测试拥有 SQLite 去重入口。固定辅助判据为 `TC-TM003-CORE-01/02/03`，详见[测试计划](04-test-plan.md#可先实现的无授权模块切片)。输入只来自本版私有合成 fixture 和公开向量；模块边界不消费 TM-002 授权接口、不访问产品 profile/Keychain、不启动真实 App 或服务。对应产品 `PARSE-01/PARSE-02/DEDUP-01` 等仍须在 TM-002 交接后独立红测、集成与包级验收；模块切片的代码/测试结果不能给它们填 PASS。整版当前仍 draft，局部开发就绪记录以 06 的固定 ID、依赖隔离和实际检查为准。

任务列表以[02-breakdown](02-breakdown.md)为唯一编号来源；每个 TASK 的具体 TC、数据、步骤和独立预期在[04-test-plan](04-test-plan.md)及[逐 TC 详表](../../docs/testing/cases/03-TM-003-codex-collection.md)。编制顺序：SOURCE 与独立核验 → FIXTURE/预期 → SOP-006/007 → SOP-008 基线 → SOP-009 环境 → SOP-010/011 固定测试与业务失败基线 → PARSE/IDENTITY/STORE/SCAN → TM-002 接口到位后 AUTH/UI/E2E → SOP-013/014 全回归 → SOP-016 迁移、017/018 包门禁 → 019/020/022。源码任务在未取得业务红测前只能标准备，不标产品完成。

固定 `scripts/tm003_native_probe.py` 已作为 SOP-004 来源研究程序运行：使用本机 `codex-cli 0.158.0-alpha.2.1`、独占 loopback Responses SSE、合成 provider key、私有 HOME / `CODEX_HOME` / 空白 cwd，禁用用户配置/规则、插件/更新与遥测。第一轮附带外部代理 CONNECT 被本机代理拒绝，仍判 BLOCKED；后两轮仅观察到本地模型 POST，CLI 自写的原生 rollout 带声明版本、逐响应用量及 SHA，结果 `SOURCE_PROBE_PASS`。其原件与程序输入/退出码在需求文档所指 `.local` 私有目录；该结论只证明基础格式，不是 SOP-010 完整数据交付。固定研究程序现已派生同 seed+T0 的 A/B/C fixture、独立 expected 与归属证据，并明确标成“原生形状衍生测试数据”，没有把改写后的 JSONL 称为 CLI 原件。正式 SOP-010 尚缺已通过的前置门禁、数据重置与逐 TC 绑定；子代理仍需真实落盘证据，无法触发则相应用例保持 BLOCKED。

独立 `scripts/tm003_lifecycle_probe.py` 又取得恢复、普通 CLI fork、无用量完成的原件；初次 fork 累计预期错误时保留 BLOCKED 原件，随后按实测累计语义修订断言并在新私有目录重跑通过。`scripts/tm003_fixture_research.py` 验证这些原件摘要后生成固定 seed303+T0 的 A/B/C、分支、独立会话、重复文件、累计-only、无用量与人为缺字段/非法数值样例及**独立硬编码 expected**；输出明确标为衍生研究数据，未改写 CLI 原件。`.local/tm003-fixture-research/20261001T063737Z-15929/` 与前一同输入运行的文件和 expected 摘要一致，但 SOP-008/009 尚未完成，因此尚不能标 SOP-010 数据或任一 TC ready。子代理原生运行、测试拥有的重置与安装 App 绑定仍待办。

本干净分支以 TM-001 候选 `3467dc143b2e2fc71f51515f483f0ecff8637947` 为父提交，只移植 TM-003 自有变更；其最终产品门禁尚待完成。TM-002 需交接稳定 SHA、确认根只读接口、失效/恢复通知与隔离授权 fixture；未取得时不修改其所属文件。新客户端库与解析模块可独立准备；对 TM-001 登录、更新及 TM-002 授权的修改须先做差异审查，并在同一候选上全量回归。

局部验证用固定来源格式/SQLite 测试检查解析、事务、隐私；产品行为仅以安装后 Electron App、真实 TM-001 服务、TM-002 授权、隔离客户端 SQLite 的逐 TC Playwright E2E 判定。现有 TM-001 专用 runner/变体 manifest/最终门禁尚不能执行本版逐 TC 集合；SOP-011/014 须扩展按 case release 读取的入口、每步原件与同候选全集合同，并固定缺例/错 release 负测，否则本版产品状态 BLOCKED。迁移依 SOP-016 做备份、恢复、中断和重复执行；没有已发布 0.2 包时只能记录干净安装及缺稳定升级起点，发布资格仍受 SOP-007/017 约束。Changelog、矩阵、总表和状态随本版事实同步，报告不能早于被测候选提交。

当前独立模块准备可以继续；TM-001 最终产品门禁、TM-002 稳定源码、SOP-008/009/010 前置与独占 GUI 时段仍是产品集成阻塞。恢复入口为本版 06 记录与本干净工作树 `.local/tm003-clean-base/` 检查收据；不能把旧快照的 E2E 结果借给新候选。
