# v0.2.0-20261001T034118Z — 技术设计与开发计划（草稿）

**doc_id：** `DOC-RELEASES-V0-2-0-20261001T034118Z-DEVELOPMENT-PLAN`　**状态：** `draft`　**适用：** `REQ-TM002` / `TM-002`。本文件先按 [SOP-004](../../sop/SOP-004-technical-design.md)设计，再按 [SOP-005](../../sop/SOP-005-development-plan.md)安排实施；文档修改遵循 [SOP-024](../../sop/SOP-024-document-change.md)。授权与加密 locator 边界已确定，仍需将逐条用例、机器清单和版本追踪核对一致并通过 SOP-008，才形成开发基线。

## 输入与当前实现事实

- [本版需求与功能点](01-requirements.md)、[具体任务](02-breakdown.md)、[产品验收定义](../../docs/product/README.md)、[当前 Electron 架构](../../docs/architecture/README.md)及[本机执行合同](../../docs/architecture/01-electron-local.md)是行为输入；[TM-002 详细用例](../../docs/testing/cases/02-TM-002-permissions.md)已按 [SOP-006 测试计划](../../sop/SOP-006-test-plan.md)拆成每项 TASK 的固定 TC，机器清单和总表须与其逐项回读。
- 当前 `apps/desktop/src/main/index.ts` 只接受来自主窗口主 frame 的 `tokenmeter:invoke`；`src/preload/index.ts` 暴露列举的业务方法，renderer 无 Node/任意文件访问。`Accounts` 在 `src/main/accounts.ts` 以规范化服务 origin 管理会话，经真实登录或 `/v1/me` 设置 `account.id` 和 `identityVerified`；退出、无效会话、切换服务会清除身份。现有 `src/main/storage.ts` 提供私有目录/文件归属和原子写基础，但未保存来源目录。服务端没有 TM-002 接口，客户端尚无来源模块或客户端用量 SQLite。
- `TM-001` 的干净源码候选已纳入本工作树，但尚无该候选最终包的正式门禁 PASS；旧设计工作树中的未提交源码快照没有移入本候选。不能把历史 Swift 结果、开发包联合复核或此计划当作本版产品通过。实施和最后回归须重新确认上游稳定提交、原始报告与候选树。

## SOP-004：技术设计

### 数据流、模块与信任边界

`已验证的服务 origin + account.id + 工具类型` → 主进程打开 macOS 原生目录面板 → **暂选、只驻内存**的来源根 → 主进程只读候选元数据预览 → 用户分别确认采集和未来同步意愿 → 受保护的本机来源记录 → 主进程受限访问服务 → 后续 `TM-003/004` 来源适配器。同一三元组至多一个已确认根；选择新根期间原根及其意愿仍有效，只有新 locator 加密与原子持久提交成功才替换，并立即取消旧根扫描。`TM-002` 不解析正文、不计算用量、不建立上传队列，也不向服务端发送目录或意愿；`TM-007` 才验证同步行为。

| 边界 | 本版合同 |
| --- | --- |
| renderer / preload | 只能传工具类型、暂选令牌、来源 ID 和布尔意愿；不得传任意绝对路径、`file://` URL 或目录句柄。返回状态只含工具、授权状态、意愿、候选**相对**名称/大小/修改时间及安全错误码；不含完整本机路径、locator、日志正文或 token。`src/shared/types.ts` 明确返回类型。 |
| 主进程选择器 | 仅在 `identityVerified === true`、当前会话与窗口仍有效时调用 `dialog.showOpenDialog` 的原生目录选择。一次选择只接受一个目录；取消与面板错误分别处理，旧已确认来源不变。选择结果由主进程持有，不从 renderer 回传路径。暂选与 origin/account/tool 及当前会话绑定；登录、退出、换账号/服务、身份失效时丢弃暂选。 |
| 来源访问服务 | `apps/desktop/src/main/source-access.ts` 拟封装 `select/preview/confirm/updateConsent/refresh/revoke` 与仅主进程可调用的内部分页扫描/只读打开能力；未来适配器只能取得绑定身份、工具及来源 ID 的能力，不能绕过它读取绝对路径。每页与打开前重新检查当前真实身份、确认/采集状态、根及文件身份、目录树版本；撤销、关闭采集、原子换根或失效使旧任务及游标失效并拒绝后续结果。 |
| 本地存储 | 拟置于现有隔离 profile 的独立 `sources/` 私有记录，按规范化服务 origin、经服务验证的真实 `account.id` 与工具类型隔离，三元组至多一个已确认根；只有确认态写入，暂选/取消/预览不持久化。沿用 0700/0600、当前 UID、拒绝符号链接/硬链接及原子写；目录路径仅由主进程在系统密钥可用时用 `safeStorage.encryptStringAsync` 加密并以密文写入 0600 记录，解密仅限已验证身份；新根加密失败时不确认新根，系统密钥整体不可用或旧记录不可解密时旧来源也停读；新根已加密而私有记录写入失败则保留健康旧记录与能力，不回退明文。撤销（包括 `needs_reselect`）删除该记录。不写入 `settings.json`、服务端、用量库、报告、日志或 Git。测试 profile 还须与正式 App 的系统密钥服务项隔离，隔离关系由最终包受控探针核对后才能运行用例。 |
| 服务端与数据 | 本版不改 FastAPI API、服务端 SQLite 或用量 schema，不调用上传接口；同步意愿只是本机未来行为输入。新本地来源记录须有 schema 版本和不兼容时的安全拒绝/恢复设计；若最终选择需要 schema 或存量数据迁移，再按 [SOP-016](../../sop/SOP-016-database-migration.md)补设计与验证。 |

拟定的 renderer 桥接方法为 `chooseSource({tool})`、`previewSource({selectionId})`、`confirmSource({selectionId, collectAllowed, syncIntent})`、`updateSourceConsent({sourceId, collectAllowed, syncIntent})`、`refreshSource({sourceId})`、`revokeSource({sourceId})`；全部走现有主 frame IPC 白名单并返回更新后的脱敏 `Snapshot`。`tool` 只允许 `codex` / `claude_code`，`selectionId` 是本次主进程生成的不可猜测短期引用；重启与身份改变即失效。`updateSourceConsent` 仅作用于当前经验证的 origin/account/tool/sourceId，两个布尔值作为一次原子记录更新；保存失败保留原值，关闭采集须在响应前取消旧扫描及未提交的刷新结果，重新开启须复核当前身份和根。具体方法名在逐 TC 与实现合同核对时可同步调整，但**不增加 renderer 任意路径读取方法**。`syncIntent` 默认 `false`，两项意愿分开持久化；`syncIntent=true` 仍不能在本版触发上传。

内部适配器能力由主进程从当前 `Accounts` 验证身份取得，不接受 renderer 提供 origin/account/path。它提供 `beginCandidateScan(sourceId)`、`nextCandidatePage(scanId)`、`openCandidateReadOnly(scanId, candidateToken)`、`cancelScan(scanId)`；每页至多 256 条，返回安全相对名、文件身份摘要、不可猜测候选令牌、续扫游标以及 `complete`/`incompleteReason`。游标只留主进程内存，绑定 origin、account.id、工具类型、来源 ID、根 dev/ino、每个已遍历目录的 dev/ino/mtime/ctime（纳秒）快照与撤销世代。helper 持有根目录 FD，逐级 no-follow 打开并按相对名称 UTF-8 字节序遍历；每页以及宣告 `complete=true` 前，都从受控根安全重开并逐一复核所有已遍历目录快照。任何变化、无法复核或新插入的早排序候选都必须使旧游标 invalid 且覆盖 incomplete，禁止把旧页与新树续页拼成完整集合。只有穷尽整棵经最终复核的稳定候选树才允许 `complete=true`；单页时间片耗尽仅交还可续游标，撤销、关闭采集、原子换根、换身份、根/目录树变化、错误或游标过期均不得转写为“零个”或“完整覆盖”。`openCandidateReadOnly(scanId, candidateToken)` 仅在当前有效扫描中由 helper 复核令牌、身份、根与目标文件 dev/ino，然后经有界分块、可取消的私有只读流将原始字节交给主进程适配器；绝不交给 renderer、诊断、日志或报告。TM-002 自身不调用该能力读取正文；解析和用量统计归属 `TM-003/004`。主进程不得以绝对路径检查替代 helper 的描述符相对访问。

本版目录访问设计采用随 App 打包、同 UID 运行并签名的最小 C helper。主进程只通过私有 stdin 首帧交付已选根；helper 用 `open(O_RDONLY|O_DIRECTORY|O_NOFOLLOW_ANY|O_CLOEXEC)` 打开根并持有其 FD，锁定 dev/ino，逐级以 `fdopendir`、`openat`、`fstatat(AT_SYMLINK_NOFOLLOW)` 和 no-follow 选项枚举、打开只读普通文件，拒绝中间目录或目标文件在检查/打开间替换为链接。内部无预算分页扫描须完整取得当前目录的安全名称列表，按文件名原字节、目录名追加 `/` 后的字节排序，再推进深度优先遍历，使 `a.jsonl` 排在 `a/x.jsonl` 前，整页满足完整相对名称 UTF-8 字节序。UI 预览只在该目录能于 5000 目录项、2 秒等预算内穷尽时采用完整排序；预算先到即安全停止，排序并显示已经核验的部分，明确标 incomplete，不声称它们是全树排序后的前 1000 项。每页及完成前安全重开复核根和所有已遍历目录的 dev/ino/mtime/ctime（纳秒），检测变化或不可复核即废弃旧游标。控制 stdout 仅输出相对名、元数据和安全错误码，stderr 不打印完整路径；后续适配器的正文只经主进程私有有界流交付，不经 renderer、诊断或控制 stdout。构建程序须把 helper 纳入最终包架构、签名、摘要及安装后实测，缺 helper 或校验不符不得退回绝对路径扫描。

隔离回归 profile 的运行时 App 名称必须由其规范化 profile 标识确定性派生并在 `safeStorage` 首次调用前设置；默认正式 profile 仍使用 `TokenMeter`。运行时名称与异步 `safeStorage` 实际 Keychain service/account 的对应关系仍待原生实测，不能从同步加密源码推定。同一最终 DMG 在首次调用异步 `safeStorage` 前，必须取得其实际目标 item 身份与签名访问边界的受控证据，确认本例测试 item 此前不存在、service/account 与正式 App 项不同，再使用仅匹配本例测试名称的精确元数据探针核对调用后的状态。探针不得查询、修改或删除正式 `TokenMeter` 的密钥项；若无法证明隔离或首次调用前目标项不存在，依赖密钥的产品 TC 保持 BLOCKED。

### 状态转换和读取规则

| 状态 | 进入条件与可见状态 | 允许的文件操作和转移 |
| --- | --- | --- |
| `none` | 该 origin/account/tool 无已确认来源；显示需要选择 | 可打开原生面板；首次选择取消保持原态。 |
| `selected_unconfirmed` | 面板返回可访问根；主进程内存中暂选，UI 可看候选元数据；可与同一三元组的旧确认态并存 | 暂选根只允许显式预览，不监听、不定时刷新、不读正文、不持久化；取消/退出/切换身份清除暂选。已有确认根在新选择完成前保持原能力与意愿。 |
| `confirmed_paused` | 用户确认目录或更新意愿后 `collectAllowed=false`；同步意愿另存 | 立即取消旧扫描、未提交刷新和后续读取；显示已确认但暂停，受控刷新与适配器读取均拒绝；再次明确开启采集并复核身份/根后才进入下一态。 |
| `confirmed_enabled` | 用户确认或更新采集意愿为 true，根和身份当前有效 | 允许显式候选元数据刷新；后续适配器的只读能力可在本态使用。每次操作须验证身份/根/相对路径，不因保存记录而自动信任。 |
| `needs_reselect` | 根不可读、身份信息不符、locator 失效或根被替换 | 停止/取消来源访问并显示需重新选择；重启仍保持停读。只有新一次原生选择加明确确认可恢复；取消不能复活旧授权；用户仍可主动撤销并删除旧密文。 |

`confirmSource` 对同一 origin/account/tool 的新根先完成加密，再原子持久替换唯一旧记录；提交成功才换根并递增撤销/替换世代，旧扫描与候选令牌立即失效。选择取消或预览失败保留旧确认态。新根加密成功后，若当前用户私有记录的临时写入或原子 rename 单点失败，且旧来源已在本会话安全恢复并仍能验证系统密钥，则旧记录、意愿与读取能力保持，不留下半确认新根；新根加密失败只保证新根不生效，不承诺旧能力可继续。系统密钥提供者整体不可用或旧 locator 解密失败时，旧来源也须停读并要求重选。`revoke` 从任一确认态及 `needs_reselect` 清除该三元组的 locator 和意愿，回到 `none`；其他账号/工具来源不受影响。退出或切换账号只卸载内存能力、关闭正在使用的只读句柄并丢弃暂选，保留原账号已确认的受保护记录；重新登录后必须经真实 `/v1/me` 验证相同 origin 与 `account.id` 才能尝试恢复。若自动登录关闭或启动离线，显示未登录/未验证状态，不读取本机来源。状态变更使用单一主进程序列号/取消信号，使旧异步预览或刷新在撤销、关闭采集、换根、换身份后不得提交结果；错误不把未知/未读显示成“零个文件”。

UI 候选预览只在选择后的显式预览或确认采集后的显式刷新发生。从所选根递归识别非符号链接的普通 `*.jsonl`，只返回相对名称、`size`、`mtime` 和是否截断；不打开/解析正文。所选根为深度 0，最多深入 8 层目录、展示 1000 个候选、检查 5000 个目录项、耗时 2 秒；达到任一上限显示“不完整”与具体错误码，不以空列表掩盖。候选按相对名称的 UTF-8 字节序排列；在 `1001` 个候选且其目录项可完整读取时，必须先按该顺序确定前 `1000` 个并标记不完整，不能取 `readdir` 偶然先返回的 `1000` 个再排序。目录项或时间预算先到时，只能展示已安全核验且已排序的部分结果并标明不完整，不得声称全树最小 `1000` 个。**这些上限只约束 UI 预览，不能当作 TM-003/004 完整采集的上限或历史覆盖完成证据。**内部扫描使用上段可续扫能力，逐页耗尽后才报告完整；扫描失败或被取消保持覆盖不完整。这个语法候选规则覆盖本轮 `sessions/YYYY/MM/DD/*.jsonl` 和 `projects/sample/*.jsonl` 合成形状，但**不能宣称格式兼容或来源版本受支持**，后者由 `TM-003/004` 的原生日志样例独立验收。helper 逐级拒绝符号链接、非普通文件和根外路径；测试中逸出链接必须置于枚举实际会遇到的层级，并用审计证明确实拒绝。根的规范路径、设备/文件身份在选择及每次刷新时核对；检测变化或访问拒绝立即转 `needs_reselect`。

候选名称可能包含用户名或项目线索，因此仅在当前账号 UI 显示，不送服务端、不写诊断或逐步证据原文；E2E 仅使用合成名称并记录允许/拒绝集合摘要。主进程操作原始日志始终只读，不调用写入或修改其他工具配置。目录失效、I/O 错误、超时、预览取消分别给安全状态/错误；App 的登录、配置和账号页面仍可用。无后台来源扫描由本版启动；后续采集节奏和正文处理在 `TM-003/004` 另行验收。

### 设计决定与仍待完成的基线项

1. **授权模型已定。** 用户选择非 MAS 本地 DMG 中的真实 macOS 原生目录面板、App 内明确同意与主进程目录 allowlist；App 撤销或访问失效后停读，重新经面板选择并确认。产品 E2E 必须驱动真实面板、审计实际来源访问与停止；不得把它称作 App Sandbox 的逐目录 security-scoped grant 或 TCC 撤销。此决定已在[本版需求](01-requirements.md#已确认的授权模型与本地存储边界)、产品验收定义及 SOP-002/004/006 同步。
2. **持久 locator 方案与隐私规范已定。** 用户要求 App 跨重启保存所选目录；主进程以 Electron `safeStorage.encryptStringAsync` 将规范化路径加密，密文仅存当前用户 0700/0600 的 `sources/` 记录。系统密钥不可用、解密失败或旧格式不兼容均进入 `needs_reselect`，不回退明文；撤销即删除密文。此 locator 不授予 OS 沙盒权限，绝不进入同步字段或原始证据。SOP 会话已按 SOP-000 将有限私有存储例外和隔离回归前的密钥项证据门槛写入规范；仍须以同一最终签名 DMG 验证异步密钥提供者、首次调用前测试项不存在、签名访问边界、正式项隔离及升级后解密行为。
3. **逐条设计已形成，机器同步与程序待完成。** [详细用例](../../docs/testing/cases/02-TM-002-permissions.md)已写 28 条父 TC 与 35 个稳定变体，其中 20 条父 TC 属安装后产品 E2E、8 条为辅助检查；`tests/test_cases.json`、`TEST_CASES.md`、版本 manifest 和总表须与该集合逐项回读后才可称为设计同步。SOP-006/008 尚须复核每个 TC 的输入、预期、SQL/不适用理由、重置和逐步证据。`program_bindings_status=planned` 表示 SOP-011 固定程序尚不存在，不能声称可执行或产品通过；设计基线可在程序实现前形成。

## SOP-005：分阶段实施顺序

下表逐项承接 [02-breakdown 的九项具体 TASK](02-breakdown.md)。TC 栏使用已设计的稳定 ID 前缀；[本版测试计划](04-test-plan.md)和[详细用例](../../docs/testing/cases/02-TM-002-permissions.md)已有逐条草稿，机器目录、版本 manifest 与总表仍须完成同源核对及 SOP-008 语义基线复核。所有阶段保留输入、原始输出、退出码和下一步于 [06-iteration-record](06-iteration-record.md)。

| 顺序 / TASK | 输入、文件所有权与实施动作 | 产出与局部完成条件 | 验证与 SOP / TC 组 |
| --- | --- | --- | --- |
| 0，设计决定 | 已定原生面板 + App 受限读取及加密私有 locator，SOP-002/004/006 已同步；核对 `01/02/03/04/05`、产品验收、目录和 Changelog | 关键行为与规范一致；前后版本及理由可追踪，尚不等于文档基线通过 | SOP-000/002/003/004/005/024；文档结构检查 |
| 1，基线与骨架 | SOP-006 同步九任务的逐条 TC/数据至机器目录和总表；SOP-007 发布预案；SOP-008 检查。SOP-009 核对 TM-001 稳定源码、Electron 可运行工程和受控隔离 profile | 文档 baseline/质量检查实际通过，真实 App/服务/测试入口可运行；缺项仅阻断依赖任务 | SOP-006/007/008/009；`TC-TM002-*` 逐条核对，不能以结构 PASS 代替基线 |
| 2，`TASK-TM002-DATA` | `scripts/` 的本轮隔离 fixture：合成账号与动态回环服务、A/B 根、候选/非候选、符号链接逸出、替换/不可读和取消状态；只清理 owner 标记资源 | 输入/expected/重置程序在测试前固定；从不读取真实 `~/.codex` / `~/.claude`、生产库或既有 App | SOP-010/011；`TC-TM002-DATA-*`，组件级确定性负测及真实 E2E 数据摘要 |
| 3，`TASK-TM002-CATALOG` | 修订 `tests/test_cases.json`、`scripts/export_test_cases.py` 与治理检查，以每条 TC 自身 release 关联其具体 TASK；保留 TM-001 原用例归属 | 本版与前版 TC 共存、缺 TASK/错 release 使检查失败；总表可按稳定 ID 导出回读 | SOP-006/011；`TC-TM002-CATALOG-*`，structure/治理负测 |
| 4，`TASK-TM002-RUNNER` | `apps/desktop/e2e/`、本机 runner/gate：固定代码驱动安装后 App、真实原生选择器、动态隔离 FastAPI/SQLite、逐步预期和失效 fixture；同一最终 DMG 的异步系统密钥首次调用前核对目标 item 不存在及签名访问边界 | 所有必测 TC 可按 ID 单独及完整运行；原生面板、系统密钥隔离或实际读取审计不能验证时为 `BLOCKED`，不以 UI stub 或截图替代 | SOP-011/014；`TC-TM002-EVIDENCE-*`，先得到有效业务失败基线 |
| 5，`TASK-TM002-PICKER` | `src/main/index.ts` 与拟新增 `source-access.ts`、`src/preload/index.ts`、`src/shared/types.ts`、引导 UI：仅主进程原生选根和身份/窗口校验 | 取消保持状态；renderer 无路径入口；身份改变后暂选无效 | SOP-012/013；`TC-TM002-SELECT-*` |
| 6，`TASK-TM002-PREVIEW` | 随包签名的同 UID C helper、主进程预览桥接、UI 列表及安全错误；目录描述符相对 no-follow 访问，按 UTF-8 字节序选择候选 | 只读选中 A 的候选元数据；B、逸出链接、正文与持续读取均不出现；到数量/深度/时间上限显示不完整；1001 候选例输出字节序前 1000 | SOP-012/013；`TC-TM002-PREVIEW-*`、`TC-TM002-LIMIT-*` |
| 7，`TASK-TM002-CONSENT` | 主进程状态机与 UI 的两项独立意愿；`updateSourceConsent` 对已确认来源按身份/来源原子更新，关闭采集取消旧扫描、重开前复核身份和根 | 确认、更新、取消与两项意愿准确；采集暂停后零读取，本版无上传 | SOP-012/013；`TC-TM002-CONSENT-*` |
| 8，`TASK-TM002-STORE` | 仅按已决定 locator 方案实现受保护来源记录、版本与身份恢复；同一 origin/account/tool 唯一根、加密与持久提交成功后原子替换；不得将 raw path 放入普通设置/报告 | 重启经真实 `/v1/me` 只恢复对应身份/工具；取消或新根加密成功后的记录原子写入失败保留健康旧根；系统密钥不可用则旧根停读，未确认根不落盘，损坏/不安全记录拒绝读取 | SOP-012/013；`TC-TM002-STATE-*`、`TC-TM002-STORE-*`；若有 schema 迁移补 SOP-016 |
| 9，`TASK-TM002-ACCESS` | 主进程来源能力、helper 根/文件复核、撤销与失效取消、重新选择恢复；给 TM-003/004 固定每页不超过 256 项的只读扫描/打开能力 | 确认后受控元数据刷新可观察；1201 个候选五页穷尽后才完整，关闭采集/撤销/换根/换身份/树变化拒绝旧游标；`needs_reselect` 可撤销，失效后仅重选确认恢复 | SOP-012/013；`TC-TM002-ACCESS-*`、`TC-TM002-SECURITY-*` |
| 10，`TASK-TM002-DELIVERY` | 本需求固定 TC 与此前已交付 TM-001 全量安装后回归，随后最终 DMG、上一稳定包升级、本机父门禁/归档 | 每条必测 TC 原始结果及独立 Excel 均在同一锁定候选/包上为 PASS，清理完成；否则 FAIL/BLOCKED、无通行证 | SOP-013/014/017/018/019/020/022；`TC-TM002-DELIVERY-*` |

DATA、CATALOG、RUNNER 的设计可并行，但实际业务红测要等可运行骨架和已定 TC；PICKER → PREVIEW → CONSENT → STORE → ACCESS 按接口依赖顺序集成。测试程序、数据、断言及预期须先于对应业务实现固定；缺环境时只做可独立核验的准备，不将空跑或组件测试算产品 E2E。每次代码、测试、数据或门禁变化按适用 SOP 重跑目标及此前交付功能的完整集合，失败原件不覆盖。

## 文件所有权、集成与恢复入口

- `TM-002` 需求分支负责本版 `releases/v0.2.0-20261001T034118Z/`、来源模块、其 UI/IPC 与本版 fixture/TC；更改 TM-001 共享 `index.ts`、`accounts.ts`、`types.ts`、preload 或本机门禁前先基于其稳定提交核对接口和原始测试。并行工作只分配不同文件，合入者处理共享文件冲突并重跑绑定候选。当前文件分工是计划，不表示这些产品代码已实现。
- 给 `TM-003/004` 的交接合同是：经 `/v1/me` 验证的身份键、确认且允许采集的来源 ID、主进程内部分页候选与只读文件能力、穷尽后才完整的覆盖状态、失效与重新选择通知；不交出持久 locator、renderer 任意路径入口或服务端上传能力。下游在固定合同和本需求稳定源码提交前不得依赖本工作树快照，也不得把 UI 的 1000 项预览上限当作完整采集上限。本版选定非 MAS 原生面板与 App 受限读取，后续版本若迁移沙盒须独立设计更新器和打包。
- `program_bindings_status` 目前为 `planned`，`test_programs=[]`、`test_data_program=null`；只有固定 TC、数据程序、真实 runner 路径存在且可按 ID 启动时才更新为 `ready`，`ready` 仍不表示测试 PASS。主表、功能矩阵、`TEST_CASES.md`、`tests/acceptance.json`、`docs/catalog.json`、Changelog 和版本 manifest 在相应源事实变化时同轮更新并回读；此文档不能代替它们。
- 恢复顺序：读 [状态页](../../docs/status.md)与 [06-iteration-record](06-iteration-record.md) 的最新原始证据 → 检查本分支/上游 SHA、工作树及已确定授权边界 → 核对 28 条父 TC、35 个变体与机器清单/总表 → `python3 scripts/check_docs.py --mode structure` → 全部计划完整后由 SOP-008 执行 baseline/质量检查 → 依阶段准备数据/红测/实现/完整回归。当前只形成设计草稿，未执行本版产品 E2E、DMG 或发布。

## 退出条件

SOP-004/005 的**草稿输出**是有模块边界、数据/状态/失败路径、九项 TASK 的顺序与验证入口。逐条用例已形成，但机器清单/总表同步、SOP-006 语义复核与 SOP-008 基线尚未有完整通过证据；结构检查仅验证文档合同，不证明功能完成或发布资格。依赖基线的产品实现须在这些检查通过后按 SOP-009–012 推进。
