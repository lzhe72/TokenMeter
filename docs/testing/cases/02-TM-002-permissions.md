# 02 · TM-002 首次授权：逐条测试用例（已基线）

需求 REQ-TM002；release_id v0.2.0-20261001T034118Z；功能 TM-002。本文按 SOP-006 将本轮 28 条父 TC 与 35 个稳定参数变体逐项回链到版本计划的具体 TASK；`tests/test_cases.json` 与本文保持双向覆盖，版本计划摘要由本轮整合复核。E2E-TM002-001 与 E2E-TM002-002 是场景组，组内 TC 分别判定。本文为已基线的测试设计：产品代码、fixture、固定自动化、运行报告和 PASS 证据尚不存在。

## 基线状态与共同合同

- 设计状态：所有产品 TC 为 baselined，SOP-000 私有加密 locator 例外和系统授权语义已经由 SOP 会话经 PR #4/#5 同步至 SOP-002/004/006，本版 SOP-008 语义基线已完成；固定程序尚未绑定。授权模型已确定：真实 macOS 原生目录选择器供用户选根，App 持久保存已确认的来源，主进程按服务 origin、已验证 account.id、工具类型、当前状态与所选根维护并强制检查读取 allowlist；App 内撤销立即移除该来源的读取能力。本文“授权/撤销”均指这套 App 来源范围控制，不断言 macOS 沙盒级 security-scoped grant、TCC 撤销或非沙盒 App 的系统逐目录隔离。候选规则固定为选中根内递归普通 .jsonl 文件，不声称厂商正文解析兼容。
- 执行状态：全部 not_run。产品 TC 的计划绑定为 apps/desktop/e2e/granular-permissions.spec.ts、scripts/granular_permissions.py、scripts/run_test_case.py --case-id <TC-ID> --package-manifest <实际包清单>；这些 TM-002 绑定均尚未实现，automated_test=null、data_program=null。上述为计划文件和接口名称，不是当前可执行命令。辅助 TC 的具体测试文件见各例，亦均未绑定。
- 产品执行面：当前本机 macOS 15 Intel；本轮最终 DMG 安装后的 Electron App，真实主进程/IPC、原生 dialog.showOpenDialog、真实隔离 FastAPI 与 SQLite。系统 sheet 由固定 OS UI 自动化操作，observer 只记录原生调用与结果并原样委托，不 stub 返回值。缺 GUI 权限或无法驱动原生面板时，相关 TC 为 BLOCKED。任何截图只用于定位，机器断言决定结果。
- 隔离身份：每例全新 0700 profile、服务 S1、动态独占回环端口与 SQLite；用 tests/server/fixtures.py seed=42 的合成 Alice（id 00000000-0000-4000-8000-000000000002）和 Bob（id 00000000-0000-4000-8000-000000000003）。首次改密经 TM-001 真实 UI 完成。S2 用另一个本例独占端口与 SQLite，账号 id 可以相同，但服务 origin 不同。绝不访问 49176 现有服务、用户生产库、真实工具目录、既有 App 或默认凭据。
- 隔离文件：每例程序新建所有权标记和 0700 根，根下 A 与 B 各为 0700；除 SELECT-04 的 Claude 专用 A，以及 SELECT-02#REPLACE_CONFIRMED 先选 Codex A 再真实选择 Codex B 外，只选择 Codex A，B 始终未选择。候选规则为选中根内递归普通 .jsonl 文件：根深度 0、直接子文件深度 1，最多深度 8、最多 1000 候选、最多检查 5000 目录项、枚举时限 2 秒；遇任一上限须显示“不完整”，不能把未知/截断当作完整的 0 个候选。符号链接和非普通文件不跟随、不计作候选；目录项计数包含遍历遇到的所有项目（含 symlink），候选计数只包含安全核验后的普通 .jsonl。候选以相对选中根的路径按 UTF-8 字节字典序升序展示；达到 1000 候选上限时显示此前 1000 条并标“不完整”。固定程序从输入清单独立算出排序与截断集合，不从 App 结果生成 expected。
- Codex A 的 A1=sessions/2026/10/01/a-01.jsonl、A2=sessions/2026/10/01/a-02.jsonl，各 25 字节、mtime=2026-10-01T00:00:00Z，精确 UTF-8 行分别为 {"private":"PRIVATE_A1"} 与 {"private":"PRIVATE_A2"} 加换行；同层 ignore.txt 内容为 not-a-jsonl 加换行，共 12 字节。B1=sessions/2026/10/01/b-01.jsonl 在 B 内，25 字节，行 {"private":"PRIVATE_B1"} 加换行。A 的同层文件 symlink sessions/2026/10/01/link-out.jsonl 指向 B1；同层目录 symlink sessions/2026/10/01/escape 指向 B 的 sessions/2026/10/01，因递归规则会被枚举器遇到，须以 lstat 识别并拒绝。后续 AN=sessions/2026/10/01/a-new.jsonl 与 BN=sessions/2026/10/01/b-new.jsonl，各 28 字节，分别包含 PRIVATE_A_NEW/PRIVATE_B_NEW。预览与刷新集合的独立 expected 一律使用上述相对选中根的完整路径 A1/A2/AN/B1/BN，短代号不作为 UI 文案。PREVIEW-02 有意只生成 ignore.txt、不生成 symlink。
- SELECT-04 使用另一独占 A，工具类型 claude_code，C1=projects/sample/claude-01.jsonl，31 字节、同一固定 mtime，精确 UTF-8 行 {"private":"PRIVATE_CLAUDE_1"} 加换行；未选 B 含 projects/sample/claude-b-01.jsonl，31 字节，精确 UTF-8 行 {"private":"PRIVATE_CLAUDE_B"} 加换行。C1 仅验证 .jsonl 语法候选与目录范围，不代表已支持 Claude Code 某个真实日志版本、子代理、解析或用量。全部 fixture 正文只供泄漏检测，不生成 Token expected；独立 expected 在产品运行前固定，不调用产品枚举函数。
- 审计：主进程 observer 必须覆盖实际使用的同步、回调、promise 和任何原生读取通道，记录 TC、步骤、时间、A/B 标签、相对名称、元数据/打开/读取/监听操作及结果。只记录合成名称或摘要；不记录完整本机路径、正文、token。固定自动化还须观察真实 showOpenDialog 的调用与返回、主进程对来源 allowlist 的建立/拒绝/撤销/失效判定及随后实际文件访问，并用独立 A/B 清单核对；renderer 传入的路径或伪造 selectionId 不能绕开主进程检查。observer 没覆盖实际读取通道或范围判定时，“未读 B”“确认前不读”“失效后停读”均为 BLOCKED，不能靠 UI 缺项或 App 自报状态替代。原生 picker 的调用、取消和 A/B 标签另存固定观察记录。
- 文件状态记号：除 SELECT-02#REPLACE_CONFIRMED 外，F0=未对 A/B 执行文件系统访问，也没有来源 locator 落盘；FR=选择后只校验 A 根的元数据，不枚举候选/读正文/监听，不访问 B、不持久化；FP=只对已选 A 做显式预览所需 readdir/lstat/stat，文件正文 open/read/watch 为零，B 全操作为零，暂选仅驻内存；FE=仅对已确认 A 做显式元数据刷新，正文 open/read 为零、B 全操作为零；FS=来源已暂停/撤销/失效，后续刷新和定时/监听访问 A/B 均为零。替换变体逐步单独标明当前根：原 A 的 FE 在新 B 原子确认提交前可用；提交后仅新 B 可按 FE 访问，旧 A 停读。每步仍须核对实测时间窗口、候选集合和结果。
- 网络/DB 记号：ND0=该步没有 TM-002 服务 API 或上传请求；隔离服务 SQLite 无 TM-002 schema/业务写入，来源 locator、候选名、原始路径、正文和意愿不入服务端。NDA=只允许该步明确发起的 TM-001 登录、退出或 /v1/me 请求，以及对应 sessions/audit 既有副作用；除此之外遵守 ND0。数据库准备与只读核对使用隔离库：先由 TM-001 fixture 导入四个合成 users，查询 SELECT id, username, role, is_active FROM users WHERE id IN ('00000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000003') 核实 Alice/Bob；对每例记录 sessions/audit 初末快照，仅按 NDA 解释认证变化。TM-002 没有业务造数 SQL，也不直接写库；选择/预览/确认等步骤的 DB 操作为“不适用”，原因是来源状态只在受保护本机配置中。不得为测试直接写 App 来源确认状态；仅 STATE-01#CORRUPT_LOCATOR 可在关闭 App 并验证 owner/UID/0600/普通文件及无链接后，按固定损坏配方改本例已由真实 UI 生成的密文字段，以验证安全失败。
- 私有配置：未确认时本机来源记录不存在；确认后 App 持久保存已选来源，且只在本例 profile 私有 sources 记录中出现 origin/account/tool 归属、采集意愿、未来同步意愿及最终批准的 locator；同一三元组至多一个确认根，换根先加密、原子持久提交，成功后才切换能力并使旧扫描/游标失效。仅新 B 加密已成功、旧 A 密文仍可解且身份/根健康，而本例私有记录原子写入失败时，保留旧 A 确认态、意愿和原密文；系统密钥不可用或旧密文解密失败则停读需重选。重启恢复须由已验证身份触发。locator 仅由主进程以 Electron safeStorage 加密规范化目录路径并存密文，绝不回退明文；App 内撤销删除密文。目录 0700、文件 0600、当前 uid、拒绝链接并原子写；逐步报告只记脱敏状态和文件摘要，不抄 locator。服务端、普通设置、诊断、测试表和 Git 不保存完整路径。
- Keychain 测试隔离门槛：凡需建立或恢复私有密文的产品 TC/变体，在同一最终签名 DMG 的异步 `safeStorage` 首次调用前，以本例规范化隔离 profile 确定运行时 App 名称，并由受控原生证据确认目标测试 Keychain item 的实际 service/account 身份及签名访问边界、此前不存在且与正式 `TokenMeter` 项分离；首次调用后只对该测试名称作精确元数据探针。目标项预存、身份或签名边界不明、无法证实隔离时，该变体 BLOCKED，不尝试访问、删除或改写正式项，也不以源码推测或同步 API 结果代替原生证据。密钥测试 item 只有本例创建且身份可复核时才可按 owner 清理；不明时保留并 BLOCKED。STORE-01 的受控适配器安全负测不充当此产品级原生证明。
- 重置与清理配方 R：每条产品 TC/变体独占 run_id，准备前确认目标不存在，建立 owner marker、输入清单与 expected 摘要；结束先关闭本例 App、服务和只属于本例的文件句柄，恢复 A/B 的 0700 权限，核对 owner marker/文件集合/路径无链接逸出，只删除本次拥有的 profile、A/B、隔离 DB 和安装位置；Keychain 测试 item 按上段的原生身份与本例创建证据作精确清理。若所有权、权限恢复或清理失败，保留失败原件并判 BLOCKED/FAIL，不触碰其他资源。不得用 tccutil reset 修改用户或现有 App 的 TCC 状态。
- 证据配方 E：每步保存实际动作、独立 expected、实测比较、时间、真实 UI/原生面板事件、主进程文件访问审计、网络摘要、只读 DB/私有配置检查摘要与必要 Playwright trace；一次运行还需候选 SHA/tree、最终包摘要、平台、fixture/测试源码摘要、清理结果。每个 run_id 输出独立原始目录和 TokenMeter测试结果-<run_id>.xlsx，失败与 BLOCKED 也留原件，不回填或覆盖。本文所有 TC 的运行证据入口目前为 null。
- 预期依据统一为本版 01-requirements.md“已确定的行为方向”、03-development-plan.md“状态转换和读取规则”及产品约定 AC-TM002-001/002；原生面板加 App 主进程 allowlist、原子换根、私有加密 locator 已按需求确定，SOP 会话经 PR #4/#5 完成规范同步，本版 SOP-008 语义基线已完成；候选规则按本文件的 .jsonl 元数据合同验收。SOP 路线：SOP-006 设计，SOP-010 造数/重置，SOP-011 固定程序，SOP-014 产品执行，最终包和放行另按 SOP-017/018。每条用例单独生成结果，不以场景组 PASS 代替。

## E2E-TM002-001 · 选择、预览、意愿与恢复

**验收：** `AC-TM002-001`；本场景由下列 SELECT-01/02/04、PREVIEW-01/02/03/04、CONSENT-01/02/03/04、STATE-01/02/03 逐条判定。真实原生面板选择、确认后持久来源与主进程读取 allowlist 均须有独立产品证据；不声明沙盒或 TCC 授权。

**前置/数据：** 使用共同合同的 `system_permissions` 合成 A/B、S1/S2 隔离账号与每例独占 profile；fixture、固定原生面板驱动和文件读取审计均待 SOP-010/011 绑定。

**步骤：**

1. 经真实登录和身份验证，从 App 打开系统目录面板，选择或取消本例 A；SELECT-02#REPLACE_CONFIRMED 另在已确认 A 后真实选择并确认 B，各 TC 分别检查暂选、取消、替换及未确认状态。
2. 仅在明确预览时核对 A 候选、非候选、B 与符号链接边界；确认前新增文件并观察持续读取是否为零。
3. 按各 TC 的独立采集/未来同步意愿确认或暂停，检查本机记录、刷新范围与网络零上传。
4. 重启、切换账号或服务 origin 后，依实际验证身份检查状态恢复与读取隔离。

**独立预期：** 下列每条 TC 的逐步预期、合成候选清单与读取审计必须全部成立；除 SELECT-02#REPLACE_CONFIRMED 原子确认 B 后仅 B 可受控读取外，未选 B 不被 App 读取；确认前无持续采集，确认态只随正确 origin 与 account.id 恢复。汇总步骤不代替任何一条 TC 的单独结果。

**绑定/证据/状态：** `planned`；本组自动化与数据程序为 null，实际执行 `not_run`。原生面板、主进程 allowlist 判定、文件访问、网络、DB 和私有配置证据按共同配方 E 保存；固定绑定缺失时保持 BLOCKED。

### TC-TM002-SELECT-01 — 首次从原生面板选择 A

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PICKER / E2E-TM002-001；层级 product_e2e。
- 前置与输入：全新 profile、S1 的 Alice 已真实登录且经身份验证；A/B 如共同 fixture，尚无已确认来源。实际输入为工具 codex、原生目录面板中的 A。
- 数据/SQL/重置：R；账号 SQL 及只读核对见共同 ND 定义；TM-002 不写服务 DB。独立 expected 为“暂选 A、确认记录仍无”。
- 步骤：
  1. 从首次引导点击“选择 Codex 目录”。UI 出现等待系统选择状态；observer 见原生 showOpenDialog 被调用一次。文件 F0；网络/DB ND0。
  2. 在真实 macOS 目录面板中选本例 A 并确认。UI 进入待确认/可预览状态，只显示 A 的安全标签，不显示绝对路径；observer 记录面板未取消且选择标签 A。文件 FR；网络/DB ND0。
  3. 检查尚未点产品确认。UI 没有“已授权采集”状态；主进程尚未建立已确认来源的读取 allowlist，私有已确认 sources 记录不存在，B 无访问，A 原始文件 SHA256 与初始清单一致；网络/DB ND0。
- 完成/证据/绑定：三个步骤均满足，E 需含原生面板调用及真实选中证据、暂选/未落盘、FS 审计。计划绑定为共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-SELECT-02 — 面板取消保留当前来源状态

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PICKER / E2E-TM002-001；层级 product_e2e。
- 前置与输入：三个稳定变体各自使用全新 profile 与已验证 S1 Alice。`TC-TM002-SELECT-02#FIRST_CANCEL` 初态无来源；`#CONFIRMED_CANCEL` 初态为 Alice 已从真实面板选定并确认 A、采集=true/未来同步=false，可受控刷新 {A1,A2}，随后再次打开工具 codex 的原生面板并点系统“取消”；`#REPLACE_CONFIRMED` 先在同一 S1/Alice/codex 三元组确认 A，再从真实面板选择 B 并明确确认新根。
- 数据/SQL/重置：三个变体各自独立使用 R、共同账号 SQL 与本例 A/B，私有密文变体先满足共同 Keychain 原生隔离门槛；TM-002 无业务 DB 操作。`#FIRST_CANCEL` expected 为 none，`#CONFIRMED_CANCEL` expected 为原 A 的确认态、意愿、密文记录与根身份不变；`#REPLACE_CONFIRMED` expected 在新 B 原子确认成功后唯一已确认根为 B、候选仅 `sessions/2026/10/01/b-01.jsonl`，旧 A 来源能力/扫描与未提交结果立刻失效。各变体分别保存独立 run_id、私有记录和 A/B 根身份的脱敏摘要、前后审计与清理结果。
- `#FIRST_CANCEL` 固定步骤：
  1. 点击“选择 Codex 目录”。UI 保持当前引导、等待面板；observer 见 showOpenDialog 一次。文件 F0；网络/DB ND0。
  2. 点击原生面板的“取消”按钮。UI 返回需要选择，不显示候选/成功授权，也不崩溃；observer 见 canceled=true、空选中集合。文件 F0；网络/DB ND0。
  3. 退出并重启同 profile，经 /v1/me 恢复 Alice。UI 仍为无来源；没有 sources 记录、A/B 文件操作或隐式扫描；网络/DB NDA 仅允许 /v1/me。
- `TC-TM002-SELECT-02#CONFIRMED_CANCEL` 固定步骤：
  1. 先在本例 profile 通过真实面板确认 A 的 true/false，显式刷新核对 {A1,A2}，记录已确认来源、密文摘要及根身份。UI 显示 A 已确认；文件 FE 只读 A 元数据，B 零访问；网络/DB ND0。
  2. 点击“更换来源”唤起真实 macOS 面板，然后点击原生“取消”。observer 记录本次 showOpenDialog 与 canceled=true、空选中集合；UI 继续显示旧 A 的 confirmed_enabled/true/false，不产生暂选 B；私有记录与步骤 1 摘要相同，取消动作不触发新文件读取且 B 零访问，旧 A 的受控刷新能力仍在；网络/DB ND0。
  3. 退出重启并经真实 /v1/me 恢复 Alice，再显式刷新。UI 仍为旧 A 的 true/false 且候选恰为 {A1,A2}；密文归属与根身份未变，文件 FE 仅 A 元数据、B 零访问；网络/DB NDA 仅允许身份验证。
- `TC-TM002-SELECT-02#REPLACE_CONFIRMED` 固定步骤：
  1. 在本例 profile 经真实面板确认 A 的采集=true/未来同步=false，显式刷新，固定 UI expected 为 `{sessions/2026/10/01/a-01.jsonl,sessions/2026/10/01/a-02.jsonl}`；记录旧扫描代际、加密记录与 A 根身份的脱敏摘要。UI 显示 A confirmed_enabled；文件 FE 只读 A 元数据、B 零访问；网络/DB ND0。
  2. 点击“更换来源”，固定系统 UI 自动化从真实 macOS 面板选择本例 B，尚不点产品确认。UI 显示 B 待确认且旧 A 仍为已确认来源；observer 见 showOpenDialog 返回 B，主进程只校验 B 根元数据、不枚举 B1/读正文，旧 A 密文记录及能力未改；网络/DB ND0。
  3. 明确确认 B 的采集=true/未来同步=false。UI 只显示 B confirmed_enabled，不再显示 A 为当前来源；主进程先加密并原子持久替换该三元组唯一 `sources/` 记录，再切换到 B 根身份并使旧 A 扫描、游标、读取能力与未提交刷新结果失效。以提交成功的审计时间为界，其后 A 的 readdir/stat/open/read/watch 均为零；B 尚无正文读取，原始 A/B SHA256 均不变；网络/DB ND0。
  4. 点产品“刷新候选”，并核对主进程旧 A 扫描代际已失效。UI 候选恰为 `{sessions/2026/10/01/b-01.jsonl}`，不含 A1/A2；文件 FE 仅 B 元数据，旧 A 的扫描或未提交结果不能复活且不再访问 A，B 正文 open/read=0；网络/DB ND0。
  5. 退出重启本例同一安装后 App，经真实 `/v1/me` 验证 Alice 后显式刷新。UI 恢复唯一 B、true/false，候选仍恰为 B1；密文记录归属与 B 根身份保持不变，旧 A 不复活且重启后 A 全操作为零，文件 FE 仅 B 元数据；网络/DB NDA 只允许身份验证，无上传。
- 完成/证据/绑定：`#FIRST_CANCEL`、`#CONFIRMED_CANCEL` 与 `#REPLACE_CONFIRMED` 均为必跑变体；各自保存原生面板真实返回、逐步 UI、主进程范围/代际判定、A/B 访问时间分界、私有记录前后摘要、隔离 Keychain 原生证明及清理。取消不等于撤销旧来源；替换只有原子提交成功才撤销旧能力。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-SELECT-04 — Claude Code 来源选择、预览、确认与恢复

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PICKER、TASK-TM002-PREVIEW、TASK-TM002-CONSENT、TASK-TM002-STORE / E2E-TM002-001；层级 product_e2e。
- 前置与输入：全新 profile，S1 Alice 真实登录并已验证身份；独占 Claude A 只含 C1=projects/sample/claude-01.jsonl（31 B、固定 mtime）与非候选 projects/sample/readme.txt（内容 README 加换行，共 7 B），未选 B 含 projects/sample/claude-b-01.jsonl（31 B、标记 PRIVATE_CLAUDE_B）。工具输入为 claude_code，采集=true，未来同步意愿保留默认 false；两个根均为本例合成数据。
- 数据/SQL/重置：R；共同账号 SQL 只准备 Alice/Bob，TM-002 无业务 DB 写入。独立 expected 为预览集合 {C1}、确认态 true/false、重启后相同来源；只验证递归 .jsonl 元数据候选，不验证 Claude Code 原始日志解析或用量。
- 步骤：
  1. 在来源 UI 选择工具 claude_code，点击选择目录，固定系统 UI 自动化从真实 macOS 面板选择 Claude A。UI 进入待确认；observer 见 showOpenDialog 一次并返回 A 标签；文件 FR、B 零访问，网络/DB ND0。
  2. 点击显式预览。UI 候选集合恰为 {C1}，相对路径 projects/sample/claude-01.jsonl、大小 31 B 和固定 mtime 与独立清单一致，不出现 B 的候选、完整根路径或 PRIVATE_CLAUDE_1/B；文件 FP 且正文 open/read=0，B 全操作=0；网络/DB ND0。
  3. 不触碰默认 false 的未来同步开关，只开启采集并明确确认。UI 显示 claude_code 来源 confirmed_enabled 与 true/false；私有 sources 记录首次写入 S1/Alice/claude_code 的确认态，B 与服务 DB 不变；文件仅允许确认后的 FE，网络/DB ND0。
  4. 退出重启同 profile，等待真实 /v1/me 验证 Alice 后打开来源并刷新。UI 仍显示 claude_code、true/false，候选集合恰为 {C1}；文件 FE 只读 Claude A 元数据、B 零访问，不上传正文、路径或用量；网络/DB NDA 仅允许 /v1/me。
- 完成/证据/绑定：四步各自记录原生面板、相对候选、默认意愿、私有状态摘要、重启进程与 FS/网络审计；C1 的“语法候选”不转写为 Claude 兼容 PASS。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-PREVIEW-01 — 只显示 A 的候选元数据

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PREVIEW / E2E-TM002-001；层级 product_e2e。
- 前置与输入：S1 Alice 真实面板暂选 A，尚未确认；A 有相对路径 A1/A2 与 sessions/2026/10/01/ignore.txt，B 有 B1。递归 .jsonl 规则使 A1/A2 为候选，B1 与 ignore.txt 不在候选中。
- 数据/SQL/重置：R；共同账号 SQL；TM-002 无业务 DB 操作。独立清单恰有两个候选，相对路径 A1 和 A2，大小均 25 B、mtime=2026-10-01T00:00:00Z；显示格式未定时按可访问元数据值比较。
- 步骤：
  1. 点击“预览”。UI 出现两个候选条目，无 b-01/ignore；文件 FP 只允许 A 的显式元数据枚举；网络/DB ND0。
  2. 逐项读取 UI 可访问名称、大小、时间。两个候选的相对名/大小/时间与独立清单一致，既不显示绝对根路径，也不显示 PRIVATE_A1/PRIVATE_A2/PRIVATE_B1；文件正文 open/read 为零；网络/DB ND0。
  3. 检查私有来源记录与服务。仍无已确认 sources 记录，无 B 访问，A/B 文件 SHA256 不变；网络/DB ND0。
- 完成/证据/绑定：集合、元数据、隐私和零正文读取均成立；E 保存候选集合摘要、UI 属性和 FS 访问。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-PREVIEW-02 — 非候选文件不充当日志

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PREVIEW / E2E-TM002-001；层级 product_e2e。
- 前置与输入：S1 Alice 选 A；本例 A 只生成 sessions/2026/10/01/ignore.txt（12 B），不生成 A1/A2、文件 symlink 或目录 symlink；B 仍有 B1。所有变化仅作用于运行 App 前的本例自有 fixture。
- 数据/SQL/重置：R；共同账号 SQL；TM-002 无业务 DB 操作。独立 expected 候选集合为空；符合候选规则的文件为零时仍须允许确认已选目录，以等待后续文件。
- 步骤：
  1. 真实面板选 A。UI 为待确认；文件 FR 只允许选中 A 的根元数据校验，B 零访问；网络/DB ND0。
  2. 点击“预览”。UI 显示“0 个候选文件”空态并与读取失败区分；ignore.txt 与 B1 均不列入，未出现 PRIVATE_B1；文件 FP，无正文读取；网络/DB ND0。
  3. 设置采集=true、同步=false 并确认。UI 显示已确认且当前无候选，明确区别于权限错误；受控刷新返回完整空集合，来源记录仅在确认后出现；文件 FE，网络/DB ND0。
- 完成/证据/绑定：空候选不伪造成错误或零用量；E 保存空集合、确认与无正文读取。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-PREVIEW-03 — 符号链接不能逸出选中根

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PREVIEW / E2E-TM002-001；层级 product_e2e。
- 前置与输入：S1 Alice 选 A；A 中同层文件 symlink sessions/2026/10/01/link-out.jsonl 与目录 symlink sessions/2026/10/01/escape 指向本例 B；A1/A2 仍存在。
- 数据/SQL/重置：R；共同账号 SQL；TM-002 无业务 DB 操作。独立 expected 只含 A 的两个普通文件，拒绝 symlink 与 B。
- 步骤：
  1. 真实面板选 A 并点击“预览”。UI 候选集合恰为 {A1,A2}；文件 FP 允许对 A 内链接做 lstat，但不得跟随进入 B，也不得打开目标正文；网络/DB ND0。
  2. 检查集合与访问审计。UI 不含 sessions/2026/10/01/link-out.jsonl、sessions/2026/10/01/escape/b-01.jsonl 或 B1；B 的 stat/readdir/open/read 均为零，PRIVATE_B1 未出现在 UI/报告；网络/DB ND0。
  3. 确认采集=true、同步=false 并手动刷新。UI 候选集合仍恰为 {A1,A2}；文件 FE，B 零访问，原始文件字节不变；网络/DB ND0。
- 完成/证据/绑定：预览与确认后刷新都拒绝逸出；E 保存链接 fixture 摘要和 B 零访问证据。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-PREVIEW-04 — 枚举上限与“不完整”提示

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PREVIEW / E2E-TM002-001；层级 product_e2e。三个真实目录固定变体均保留父 TC 身份并独立记录，不能只运行一个较易变体；2 秒期限另由辅助 TC-TM002-LIMIT-01 验证，不属于本产品 E2E 的变体。
- 前置与输入：每个变体各用全新 S1 Alice、A/B、profile 和 run_id，真实面板选 A；A 的具体合成树由下述变体替代普通 A1/A2，B 保留未选 B1。CANDIDATES_1001 与 ENTRIES_5001 的独立预探针须证明深度未超限、正常枚举可在 2 秒内完成，才能归因于数量上限；否则该变体 BLOCKED。只操作本例自有根；上限固定为深度 8、最多 1000 候选、最多 5000 目录项、2 秒。所有预期清单在运行前固定；不借产品输出生成答案。
- 数据/SQL/重置：每变体使用 R 与共同账号 SQL；TM-002 无业务 DB 操作。每条变体都有独立 fixture manifest/expected/清理和原始结果；真实测试路径为计划中的共同产品 spec，automated_test=null。
- TC-TM002-PREVIEW-04#CANDIDATES_1001：A 根直接放 c-0000.jsonl 至 c-1000.jsonl 共 1001 个普通文件，各内容为固定 3 B 的一行空 JSON 加换行，mtime 固定；无 symlink 或其他候选。①真实面板选 A，UI 待确认、文件 FR、网络/DB ND0。②点击预览，UI 按相对路径 UTF-8 字节字典序恰好显示 {c-0000.jsonl,…,c-0999.jsonl} 这 1000 条、计数 1000 且状态明确“不完整”；c-1000.jsonl 不显示，不得显示“0 个”或“完整”，不能重复或出现 B1；文件 FP、无正文读取，网络/DB ND0。③保存 UI/审计摘要，确认 1001 个输入与 1000 个输出的独立比较及截断原因，未确认来源仍不落盘；网络/DB ND0。
- TC-TM002-PREVIEW-04#ENTRIES_5001：A 根直接放 n-0000.txt 至 n-5000.txt 共 5001 个非候选普通文件，无 .jsonl 或 symlink。①真实面板选 A，UI 待确认、文件 FR、网络/DB ND0。②点击预览，枚举至最多 5000 目录项即停止，候选列表可为空但必须标“不完整/尚未检查全部项目”，不得把空集合称为完整的 0 个日志；文件 FP、B 零访问，网络/DB ND0。③审计显示已检查项数不超过 5000、输入清单为 5001 且未持久确认；网络/DB ND0。
- TC-TM002-PREVIEW-04#DEPTH_9：A 中 d1/d2/d3/d4/d5/d6/d7/at8.jsonl 位于相对文件深度 8，d1/d2/d3/d4/d5/d6/d7/d8/at9.jsonl 位于深度 9，各是固定 3 B 普通文件，无 symlink。①真实面板选 A，文件 FR、网络/DB ND0。②点击预览，UI 只可显示深度 8 的相对路径 d1/d2/d3/d4/d5/d6/d7/at8.jsonl，并明确“不完整/深度截断”；深度 9 文件不显示且不打开正文，B 零访问，文件 FP；网络/DB ND0。③审计证明下一级被深度限制拒绝、来源仍未确认；网络/DB ND0。
- 完成/证据/绑定：三个产品变体分别保存原生选择、输入数量/相对路径摘要、逐步 UI 与文件审计、上限原因及清理；候选规则、App 授权模型及私有加密 locator 已定，SOP-000 经 PR #4/#5 同步完成，本版 SOP-008 语义基线已完成。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-CONSENT-01 — 预览不启动持续读取

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-CONSENT / E2E-TM002-001；层级 product_e2e。
- 前置与输入：S1 Alice 已通过真实面板暂选 A 并完成一次显式预览，尚未确认；随后固定 fixture 向 A 写 a-new、B 写 b-new，观察窗口为至少一个本版约定的后台补扫周期（当前设计明确 TM-002 无后台扫描）。
- 数据/SQL/重置：R；共同账号 SQL；TM-002 无业务 DB 操作。独立 expected：确认前无 watcher、定时重枚举或持久来源记录；已完成的那次显式预览不算持续读取。
- 步骤：
  1. 记录显式预览完成时间和 observer 序号。UI 仍为待确认；其后文件访问应停止于 FP 的显式动作，私有 sources 记录为空；网络/DB ND0。
  2. 由本例 fixture 分别新增 a-new.jsonl 与 b-new.jsonl，不点刷新/确认，并等待固定 35 秒观察窗口，以覆盖产品长期约定的 30 秒补扫周期。UI 不自动新增 AN 或显示采集完成；该窗口内 A/B readdir/stat/open/read/watch 均为零；网络/DB ND0。
  3. 退出并重启 App，经 /v1/me 恢复 Alice。UI 回到无来源，a-new 不自动预览；A/B 无后台读取，未确认暂选未持久化；网络/DB NDA。
- 完成/证据/绑定：时间窗口和重启均无确认前读取；E 保存文件写入时间、观察窗口、零访问及未落盘证据。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-CONSENT-02 — 采集开启、未来同步关闭

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-CONSENT / E2E-TM002-001；层级 product_e2e。
- 前置与输入：S1 Alice 真实面板选 A；采集开关=true，未来同步意愿=false；确认后才由 fixture 写 a-new/b-new。
- 数据/SQL/重置：R；共同账号 SQL；TM-002 无业务 DB 操作。独立 expected 为 confirmed_enabled、true/false、候选只增加 A 的 a-new。
- 步骤：
  1. 在待确认 UI 先观察未来同步开关默认=false，只设置采集=true 而不触碰同步开关。UI 两个控件值分别为 true/false；尚无确认记录，文件仅 FP 的显式预览，网络/DB ND0。
  2. 点击明确确认。UI 显示已确认且采集开启、同步关闭；私有来源记录第一次出现且两布尔值分别为 true/false，主进程只为 S1/Alice/codex 的 A 建立已确认读取 allowlist，证明默认同步=false 未被确认流程改写，A 文件未改；网络/DB ND0。
  3. fixture 新增 a-new/b-new，点“刷新候选”。UI 候选集合恰为 {A1,A2,AN}，每条相对路径各一次，B 不出现；主进程 allowlist 决策只允许 A，文件 FE 仅 A 元数据访问，正文零读取；无上传请求，网络/DB ND0。
- 完成/证据/绑定：确认门禁、两意愿和访问范围均成立；E 保存配置脱敏摘要、刷新集合与网络零上传。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-CONSENT-03 — 采集关闭时两种未来同步意愿独立保存

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-CONSENT / E2E-TM002-001；层级 product_e2e。
- 前置与输入：两个变体各自使用全新 profile、已验证 S1 Alice，并通过真实面板选 A。`TC-TM002-CONSENT-03#FALSE_TRUE` 输入采集=false、未来同步=true；`TC-TM002-CONSENT-03#FALSE_FALSE` 输入采集=false、未来同步=false。两项意愿独立，两个组合的预期态均为 confirmed_paused，不能把其中之一当作错误输入。
- 数据/SQL/重置：每变体独立使用 R、共同账号 SQL 和 A/B；TM-002 无业务 DB 操作。独立 expected 分别为已确认暂停且 false/true、已确认暂停且 false/false，均未读、未上传，私有密文来源仅在确认后存在。
- 每个变体的固定步骤：
  1. 在待确认 UI 将采集设 false、未来同步设为本变体指定布尔值并明确确认。UI 显示已确认但采集暂停，两个开关分别为该输入；私有记录保存该变体的 false/true 或 false/false，不建立刷新能力，文件 FS，网络/DB ND0。
  2. fixture 新增 a-new/b-new，在来源页检查刷新控件不可用，不点击不存在的刷新动作。UI 保持暂停、不把“未读”显示为 0 候选；主进程来源能力仍为暂停，A/B 均无后续访问、无上传，文件 FS；网络/DB ND0。受限接口拒绝调用由辅助安全用例单独验证，不以本例直接 IPC 代替真实 UI。
  3. 退出重启并经真实 /v1/me 恢复 Alice。UI 仍为已确认暂停且显示本变体的两个布尔值；不自动读取 A/B，也不上传；文件 FS，网络/DB NDA。
- 完成/证据/绑定：`#FALSE_TRUE` 与 `#FALSE_FALSE` 必须各自产生逐步原始结果、私有记录摘要、零访问/上传证据和独立清理；不能借一变体结果代替另一变体。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-CONSENT-04 — 两意愿均开启，本版仍不上传

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-CONSENT / E2E-TM002-001；层级 product_e2e。
- `TC-TM002-CONSENT-04#BOTH_TRUE` 前置与输入：独立全新 profile 中 S1 Alice 真实面板选 A；采集=true、未来同步意愿=true；TM-007 上传功能尚未交付。
- `#BOTH_TRUE` 数据/SQL/重置：独立使用 R、共同账号 SQL 与本例 A/B，TM-002 无业务 DB 操作；expected 为 confirmed_enabled、true/true，但服务端无来源或用量写入。本变体有独立 run_id 和清理。
- `#BOTH_TRUE` 固定步骤：
  1. 设置两项开关为 true 并确认。UI 同时显示采集开启与未来同步意愿开启；私有记录为 true/true，A 原文不变；网络/DB ND0。
  2. 点“刷新候选”。UI 候选集合恰为 {A1,A2}，文件 FE；网络只允许 TM-001 认证流量，绝无用量、目录、路径或意愿上传；服务库无 TM-002 业务写入，ND0。
  3. 退出重启并经 /v1/me 恢复。UI 仍为 true/true，受控刷新集合恰为 {A1,A2} 且只读 A 元数据，B 零访问；网络/DB NDA，仍无上传。
- `#BOTH_TRUE` 完成/证据/绑定：未来意愿不被误当本版同步命令；E 保存网络观察、只读 DB 快照与恢复状态。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

- `TC-TM002-CONSENT-04#TURN_SYNC_OFF` 前置与输入：另用全新 profile、真实 S1 Alice 与面板选 A，先明确确认采集=true/未来同步=true 并显式刷新 {A1,A2}；再通过产品 UI 将未来同步从 true 关闭为 false，保持采集=true。本变体不从父例的运行继承记录。
- `#TURN_SYNC_OFF` 数据/SQL/重置：独立使用 R 与共同账号 SQL，TM-002 无业务 DB 操作；expected 为同一已确认 A、true/false，来源密文仍存在且根身份不变，不上传。
- `#TURN_SYNC_OFF` 固定步骤：
  1. 真实确认 A 的 true/true，显式刷新核对 {A1,A2} 并记录密文摘要。UI 为 confirmed_enabled；文件 FE 只读 A 元数据、B 零访问；网络/DB ND0。
  2. 在 UI 关闭未来同步并保存，保持采集开。UI 为已确认 A 的 true/false；本机来源记录保留可解密到同一 A 的 locator、根身份及采集意愿，仅未来同步意愿改变；若因密钥轮换重新加密，不要求密文字节相同；该设置动作不触发文件扫描或上传，旧 A 的受控刷新能力仍在；网络/DB ND0。
  3. 退出重启并经真实 /v1/me 验证 Alice，再显式刷新。UI 恢复 A 的 true/false，候选恰为 {A1,A2}；密文记录仍在且归属相同，文件 FE 仅 A、B 零访问；网络/DB NDA，仍无上传。
- `#TURN_SYNC_OFF` 完成/证据/绑定：单独保存两次意愿状态、私有记录前后摘要、原生选择、刷新及网络审计与清理；计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

- `TC-TM002-CONSENT-04#TURN_COLLECT_OFF_ON` 前置与输入：另用独立全新 profile/run_id、已验证 S1 Alice，经真实面板确认 A 的采集=true/未来同步=false；使用产品来源页的 `updateSourceConsent` UI 先把采集改 false、保持未来同步=false，再由用户明确改回采集=true/未来同步=false，不继承其它变体状态。本例预先固定 A1/A2/B1 清单、原密文/根身份的脱敏摘要与两次完整布尔组合。
- `#TURN_COLLECT_OFF_ON` 数据/SQL/重置：R、共同账号 SQL、本例独立 A/B 与 Keychain 隔离原生证明；TM-002 无业务 DB 写入。第一次意愿记录只能原子变为 false/false 且 confirmed_paused，第二次只能原子变回 true/false 且 confirmed_enabled；来源密文仍指同一 A、根身份不变，设置动作本身不扫描或上传。每次保存均按主进程提交时间核对完整布尔对，不允许中间单字段状态；重置只清理本 run_id 拥有的资源。
- `#TURN_COLLECT_OFF_ON` 固定步骤：
  1. 经真实面板确认 A 的 true/false，显式刷新。UI 为 confirmed_enabled、true/false，候选恰为 `{sessions/2026/10/01/a-01.jsonl,sessions/2026/10/01/a-02.jsonl}`；主进程记录当前来源/扫描代际，文件 FE 只读 A 元数据、B 零访问；网络/DB ND0。
  2. 在产品 UI 关闭采集并保存，同时保持未来同步=false。UI 立即显示 confirmed_paused、false/false，刷新控件不可用；`updateSourceConsent` 一次原子提交完整布尔对，旧扫描与未提交结果的代际失效，旧刷新请求被拒绝，提交后 A/B readdir/stat/open/read/watch 为零，密文记录归属与 A 根身份不变；网络/DB ND0，无上传。
  3. 在暂停页检查无法点击刷新，且由固定主进程审计核对旧扫描代号/游标被拒绝，不能把“未读”写成完整的 0 个候选。UI 仍显示已确认但暂停、false/false；A/B 后续访问零，旧结果不提交到 UI；网络/DB ND0。
  4. 用户再次从产品 UI 明确开启采集并保存，未来同步仍 false，然后显式点刷新。UI 原子转为 confirmed_enabled、true/false，候选仍恰为 A1/A2；主进程重新核验当前 S1/Alice、A 根身份后才给新代际读取能力，文件 FE 只读 A 元数据、B 零访问；该设置与刷新都无上传，网络/DB ND0。
  5. 退出重启并经真实 `/v1/me` 验证 Alice 后打开来源页、显式刷新。UI 恢复同一 A、true/false，候选恰为 A1/A2；私有记录仅保存最终原子布尔对与原 A locator，B 全操作零；网络/DB NDA，仅允许身份验证且无上传。
- `#TURN_COLLECT_OFF_ON` 完成/证据/绑定：独立保存两次 `updateSourceConsent` UI 操作的逐步原始结果、完整布尔对前后摘要、代际/旧扫描拒绝、A/B 时间分界、无上传、重启和清理；缺真实主进程旧扫描失效审计为 BLOCKED，不以开关截图代替。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-STATE-01 — 同账号重启的正常恢复与损坏密文停读

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-STORE / E2E-TM002-001；层级 product_e2e。
- 前置与输入：两个变体各自独占全新 profile/run_id，使用同一候选最终 DMG 的真实安装后 App，通过原生面板为 S1 Alice 确认 A，采集=true、未来同步=false，TM-001 自动登录开启；每个变体先独立取得共同合同要求的测试 Keychain item 原生隔离证明。`TC-TM002-STATE-01#NORMAL_RESTORE` 保留健康密文；`TC-TM002-STATE-01#CORRUPT_LOCATOR` 仅在退出 App 并校验本例记录所有权后，按固定配方损坏私有密文字段。S1 的本例隔离代理设置可控 `/v1/me` 响应屏障：先取得真实 FastAPI 响应并保留状态/主体摘要，释放后原样转发，不伪造认证。
- 数据/SQL/重置：两变体各自使用 R、共同账号 SQL 和本例 A/B；TM-002 无业务 DB 操作。身份键 expected 为规范化 S1 origin 与 Alice id。`#CORRUPT_LOCATOR` 的唯一故障注入在本例 0700 profile 的 0600 普通 `sources/` 记录，先核对 owner marker、当前 UID、无符号/硬链接、位于本例 profile 下、schema 与原始摘要；将唯一 locator 密文字段替换为预先固定的 Base64 `AAEC`（3 字节 `00 01 02`），其他归属/意愿/根身份字段保持，原子写回 0600。若模式、字段或所有权不符，先 BLOCKED 且不写入；不改服务 DB、正式 profile 或 Keychain。仅报告状态和记录摘要，不报告真实密文或 locator；各自按 R 清理。
- `#NORMAL_RESTORE` 固定步骤：
  1. 记录确认后的 UI 状态与私有 sources 摘要，正常退出 App，并在下次启动前武装本例 /v1/me 响应屏障。UI 进程退出；来源记录存在且归属 S1/Alice，目录/文件权限符合合同，A/B 内容 SHA256 不变；网络/DB ND0。
  2. 使用同一私有 profile 重启安装后 App，在 /v1/me 未完成前观察。隔离服务屏障已截住真实 FastAPI /v1/me 响应且尚未放行时，UI 不提前展示可读取 A 的已验证态；主进程未重建可用的来源 allowlist，文件 FS，无来源访问；网络/DB NDA 只允许该身份验证请求。
  3. 测试释放隔离服务屏障，原样转发真实 /v1/me 的 200 响应且确认 account.id 为 Alice 后，观察状态并点刷新。UI 恢复 A、true/false 且非 B；主进程仅重建 S1/Alice 的 A 范围，文件 FE 只枚举 A，B 零访问；网络/DB NDA，无上传。
- `TC-TM002-STATE-01#CORRUPT_LOCATOR` 固定步骤：
  1. 经真实面板确认 A 的 true/false，显式刷新并核对候选恰为 `{sessions/2026/10/01/a-01.jsonl,sessions/2026/10/01/a-02.jsonl}`，正常退出 App 后完成上述本例记录校验与固定密文损坏。UI 进程退出；损坏前 0600 密文记录确由本次运行生成，损坏后只有该测试密文字段变化、A/B 原文 SHA256 不变；文件 FE 仅发生在退出前，之后 A/B 零访问；网络/DB ND0。
  2. 武装本例真实 `/v1/me` 响应屏障，以同一最终 DMG 的安装后 App 和同一私有 profile 重启。真实响应尚未交付时 UI 不显示 A 的可读取确认态；主进程不建立 A/B 来源能力，A/B readdir/stat/open/read/watch 均为零；网络/DB NDA 只允许该身份请求。
  3. 释放屏障并原样交付真实 `/v1/me` 的 Alice 200 响应，打开来源页。UI 显示 `needs_reselect`/需重新选择，采集刷新不可用，不展示旧 A 候选或“完整 0 个”；主进程拒绝损坏密文、不回退明文/缓存、旧 A allowlist 不恢复，A/B 后续访问零；私有记录只能作为无可用能力的损坏原件保留或按安全策略清除，绝不能恢复确认态；网络/DB NDA，无上传。
  4. 点击“重新选择”并在真实原生面板点系统“取消”，再退出重启且经真实 `/v1/me` 验证 Alice。UI 仍需重新选择，不复活旧 A；observer 记录真实 canceled=true、空选中集合，主进程无可用来源能力，A/B 全操作零；网络/DB NDA 仅允许身份验证。保存损坏前后状态/密文摘要、原生面板、主进程停读与诊断无路径/密文证据。
- 完成/证据/绑定：`#NORMAL_RESTORE` 与 `#CORRUPT_LOCATOR` 均为必跑且独立 run_id；正常密文只在真实身份验证后恢复，故意损坏的密文始终停读需重选。E 保存同一最终包摘要、Keychain 测试项隔离原生证明、进程重启、真实 `/v1/me`、私有记录所有权/模式/前后脱敏摘要、A/B 审计和各自清理；STORE-01 的适配器结果不能代替本产品路径。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-STATE-02 — 同服务账号隔离

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-STORE / E2E-TM002-001；层级 product_e2e。
- 前置与输入：S1 Alice 已确认 A，true/false；S1 Bob 是 fixture 的另一个有效成员，尚无来源。
- 数据/SQL/重置：R；共同账号 SQL 验 Alice/Bob id；账号切换造成的 sessions/audit 变化按 NDA，TM-002 无业务 DB 操作。
- 步骤：
  1. Alice 查看 A 后通过真实 UI 退出。UI 返回登录；来源页不再可访问且后续刷新被拒绝；文件 FS；网络/DB NDA 允许 logout。
  2. Bob 通过真实 UI 登录 S1 并打开来源页；该无来源状态没有可用“刷新候选”动作，不点击不存在的刷新控件。UI 显示 Bob 无来源，A 名称、意愿与候选不可见；主进程没有 Bob 可用的 Alice 来源能力，文件 FS，A/B 无访问；网络/DB NDA 允许 login/me。
  3. Bob 退出、Alice 重新登录并经 /v1/me 验证。UI 只恢复 Alice 的 A 与 true/false；文件 FE 仅 Alice 主动刷新 A 后出现，B 无访问；网络/DB NDA。
- 完成/证据/绑定：同 origin 的真实账号 id 决定来源可见和读取；E 保存登录身份、状态切换、后续刷新拒绝和 FS 审计。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-STATE-03 — 同账号不同服务 origin 隔离

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-STORE / E2E-TM002-001；层级 product_e2e。
- 前置与输入：S1 Alice 已确认 A，true/false；S2 为另一个动态独占回环服务与 SQLite，可登录同 id Alice，但无来源。服务地址只经 TM-001 真实配置 UI 改动。
- 数据/SQL/重置：R；两个隔离库分别按共同账号 SQL 核验；配置与登录副作用按 NDA，TM-002 无业务 DB 操作。
- 步骤：
  1. 在 UI 将服务从 S1 改为 S2，并在 S2 真实登录 Alice。UI 不显示 S1 的 A/意愿；来源内存能力卸载，文件 FS，A/B 无访问；网络/DB NDA 仅目标 S2 认证。
  2. 打开来源页并尝试刷新。UI 显示 S2 无来源且无法刷新 S1 的 A；主进程拒绝将 S1/Alice 的 allowlist 用于 S2/Alice，文件 FS，无 A/B 访问；网络/DB ND0。
  3. 在 UI 改回 S1 并真实登录 Alice，经 /v1/me 验证后刷新。UI 恢复 S1 的 A/true/false，文件 FE 仅 A；S2 的库与本地来源记录不接收 S1 路径或候选；网络/DB NDA。
- 完成/证据/绑定：同 account.id 也不能跨 origin 复用授权；E 保存两个服务来源的脱敏身份/请求、配置和 FS 审计。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

## E2E-TM002-002 · 撤销、失效与重新选择

**验收：** `AC-TM002-002`；本场景由下列 SELECT-03、ACCESS-01/02/03/04/05 逐条判定。产品预期为 App 主进程撤销/失效来源能力并停止读取；POSIX 拒读用于构造目录不可访问条件，不断言 TCC 撤销。

**前置/数据：** 使用共同合同的独占合成 A/B、已验证 S1 Alice 和仅本例拥有的目录；失效通过自有 A 的拒读或 inode 替换产生，最终恢复权限并按 owner marker 清理。

**步骤：**

1. 在干净或已确认来源态，通过真实 UI 撤销、真实 POSIX 拒读或同路径 inode 替换分别形成下列 TC 的独立失效输入。
2. 触发受控刷新，核对错误状态、停止读取及 App 的登录和配置可用性；重启或恢复文件权限不能自行复活旧来源。
3. 通过真实系统目录面板分别取消或重新选择 A，并按各 TC 检查取消后停读、重新明确确认后的元数据读取与持久状态。

**独立预期：** App 不崩溃；撤销/失效后不持续读取，也不把未知当作零个候选。只有新一次真实选择加确认恢复，B 始终不被 App 读取。每个 TC 的独立拒读/根身份/面板/审计判据单独成立。

**绑定/证据/状态：** `planned`；本组自动化与数据程序为 null，实际执行 `not_run`。预期证据为原生面板、主进程 allowlist 撤销/失效判定、权限或 inode 探针、文件审计、UI、网络与清理原件；固定绑定缺失时保持 BLOCKED。

### TC-TM002-SELECT-03 — 失效后选择面板取消

- 追踪：REQ-TM002 / AC-TM002-002 / TASK-TM002-PICKER / E2E-TM002-002；层级 product_e2e。
- 前置与输入：S1 Alice 已确认 A，采集=true/同步=false；由本例 fixture 使 A 拒读并通过受控刷新进入 needs_reselect；本例保留 A 权限拒绝状态直到观察完成。输入为重新选择面板取消。
- 数据/SQL/重置：R 最终恢复 A 0700；共同账号 SQL，TM-002 无业务 DB 操作；expected 为 needs_reselect。
- 步骤：
  1. 验证失效初态。UI 显示需重新选择而非“0 个文件”；刷新已停止，后续文件 FS；网络/DB ND0。
  2. 点击“重新选择”，在原生面板取消。observer 见真实调用及 canceled=true；UI 返回需重新选择，不显示恢复成功；文件 FS；网络/DB ND0。
  3. 触发手动刷新。UI 仍需重新选择且拒绝刷新；旧 locator 不被重新信任，A/B 无文件访问；网络/DB ND0。
- 完成/证据/绑定：取消不能复活失效来源；E 保存失效前提、面板取消和 FS 时间窗口。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-ACCESS-01 — 用户主动撤销来源

- 追踪：REQ-TM002 / AC-TM002-002 / TASK-TM002-ACCESS / E2E-TM002-002；层级 product_e2e。
- 前置与输入：S1 Alice 已确认 A，true/false，能够受控刷新；记录 A/B 内容 SHA256。输入为 UI“移除来源”确认，以此撤销 App 对 A 的来源 allowlist 记录。
- 数据/SQL/重置：R；共同账号 SQL；TM-002 无业务 DB 操作。独立 expected 为 none、旧 locator 被清除。
- 步骤：
  1. 在 UI 点击移除 A 并确认。UI 变为需要选择；主进程立即撤销 A 的 allowlist 能力，后续刷新被拒绝，私有记录清除该来源 locator/意愿；文件 FS；网络/DB ND0。
  2. fixture 向 A 新增 a-new，尝试刷新并等待观察窗口。UI 不恢复旧来源、不显示 a-new；主进程拒绝原来源的刷新请求，A/B 无文件读取/监听，文件 FS；网络/DB ND0。
  3. 正常退出重启，经 /v1/me 恢复 Alice。UI 仍无来源；A/B 内容除 fixture 新增项外保持原样，旧 locator 不复活；文件 FS；网络/DB NDA。
- 完成/证据/绑定：撤销跨启动有效且不改写用户文件；E 保存 UI、配置删除、零访问与文件哈希。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-ACCESS-02 — POSIX 拒读后停止访问

- 追踪：REQ-TM002 / AC-TM002-002 / TASK-TM002-ACCESS / E2E-TM002-002；层级 product_e2e。此例用测试自有目录的 POSIX 拒读触发 App 来源失效，不主张系统级目录授权撤销。
- 前置与输入：S1 Alice 已确认 A，true/false；fixture 确认 A 初始 0700，可正常刷新；随后将自有 A chmod 000，并先以同 uid 的独立探针确认 readdir 被 OS 拒绝。若无法造成真实拒读，例为 BLOCKED。
- 数据/SQL/重置：R 必须在 finally 恢复 A 0700 并核对 owner marker；共同账号 SQL，TM-002 无业务 DB 操作。expected 为 needs_reselect。
- 步骤：
  1. 受控刷新 A，UI 候选集合恰为 {A1,A2}；文件 FE 仅 A 元数据，B 无访问；网络/DB ND0。
  2. fixture chmod 000 且探针确认拒读，点“刷新候选”。UI 显示需重新选择/访问失效而非“0 个文件”，登录及配置页仍响应；访问尝试得到明确拒绝，主进程标记来源失效并撤销读取能力，停止后续刷新，B 零访问；网络/DB ND0。
  3. fixture 先恢复 0700，再新增 a-new，但不经 picker 重选；再次点刷新/等待窗口。UI 仍需重新选择，不显示 a-new；文件 FS，A/B 后续访问为零；网络/DB ND0。
- 完成/证据/绑定：恢复 POSIX 权限本身不复活应用授权；E 保存 chmod 前后模式、独立拒读探针、App 状态和 FS 审计；清理恢复失败直接阻断。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-ACCESS-03 — 同路径新 inode 不继承旧授权

- 追踪：REQ-TM002 / AC-TM002-002 / TASK-TM002-ACCESS / E2E-TM002-002；层级 product_e2e。
- 前置与输入：S1 Alice 已确认 A，true/false，记录根设备号与 inode；fixture 仅在自有 runRoot 中把原 A 重命名为 A-old，并在原 A 路径新建不同 inode 目录及 a-new；原 A-old 仍有 A1/A2。
- 数据/SQL/重置：R 清理时分别按 owner marker 验 A-new/A-old，不能跟随链接；共同账号 SQL，TM-002 无业务 DB 操作。独立 expected 为旧根身份失效、needs_reselect。
- 步骤：
  1. 在确认态受控刷新原 A。UI 候选集合恰为 {A1,A2}；文件 FE，B 无访问；网络/DB ND0。
  2. fixture 重命名原 A、新建同路径不同 inode A，先用独立 stat 证明 dev/inode 不同，再点刷新。UI 显示需重新选择，不能把新 A 的 a-new 当作既有 App 来源授权；主进程发现根身份不符后标记来源失效并撤销原 allowlist 能力，新/旧 A 均不得有候选正文读取；网络/DB ND0。
  3. 再次尝试刷新并退出重启。UI 仍需重新选择，既不显示新 A 的 a-new，也不自行追踪旧 A-old；后续文件 FS；网络/DB NDA 仅允许 /v1/me。
- 完成/证据/绑定：路径复用不转移来源能力；E 保存脱敏 dev/inode 比较、UI 状态、FS 访问和安全清理。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-ACCESS-04 — 重启后取消重新选择仍停读

- 追踪：REQ-TM002 / AC-TM002-002 / TASK-TM002-ACCESS / E2E-TM002-002；层级 product_e2e。
- 前置与输入：S1 Alice 已确认 A 后由本例 chmod 000 真实拒读，刷新进入 needs_reselect；fixture 随后恢复 A 0700，重启 App。与 SELECT-03 的即时取消不同，本例验证失效状态持久化与重启后的取消。
- 数据/SQL/重置：R；共同账号 SQL，TM-002 无业务 DB 操作。expected 为重启后 needs_reselect，取消后仍需重新选择。
- 步骤：
  1. 恢复 A 权限并正常重启，经 /v1/me 验证 Alice。UI 仍显示需重新选择，没有自动候选；A/B 无来源读取，文件 FS；网络/DB NDA。
  2. 打开真实“重新选择”系统面板并取消。observer 记录 canceled=true；UI 仍需重新选择，旧来源不启用；文件 FS；网络/DB ND0。
  3. fixture 新增 a-new，点刷新。UI 拒绝旧来源刷新，不显示 a-new；A/B 后续访问为零，文件 FS；网络/DB ND0。
- 完成/证据/绑定：失效记录跨启动、取消不复活；E 保存真实面板、/v1/me、FS 观察和清理。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

### TC-TM002-ACCESS-05 — 真实重新选择并确认后恢复

- 追踪：REQ-TM002 / AC-TM002-002 / TASK-TM002-ACCESS / E2E-TM002-002；层级 product_e2e。
- 前置与输入：S1 Alice 曾确认 A，随后 chmod 000 拒读进入 needs_reselect；本例 fixture 恢复 A 0700 并新增 a-new，B 仍有 b-01；不直接改私有来源记录。
- 数据/SQL/重置：R；共同账号 SQL；TM-002 无业务 DB 操作。独立 expected 为新确认后候选集合 {A1,A2,AN} 每条相对路径各一次，B 零。
- 步骤：
  1. 失效态点击重新选择，由真实 macOS 面板再次选 A。observer 记录新的面板调用/选中 A；UI 仅进入待确认预览，尚未恢复采集；文件 FP，B 零访问；网络/DB ND0。
  2. 明确设置采集=true、同步=false 并点击确认。UI 转 confirmed_enabled；私有来源记录更新为本次新 locator 与 true/false，旧失效能力不再可用；文件只允许确认后的 FE；网络/DB ND0。
  3. 点受控刷新。UI 候选集合恰为 {A1,A2,AN}，每条相对路径各一次，未列 B；文件 FE 仅 A 元数据，无正文打开/读取或 B 访问；网络/DB ND0。
  4. 退出重启并经 /v1/me 验证，再刷新。UI 仍为 confirmed_enabled 且候选集合恰为 {A1,A2,AN}，每条相对路径各一次；文件 FE，B 无访问；网络/DB NDA。
- 完成/证据/绑定：新的真实选择与确认是唯一恢复入口；本例不验 TM-003/004 的用量去重。E 保存两次进程状态、面板、配置摘要、候选集合和 FS 审计。计划绑定共同产品 spec；automated_test=null，状态 baselined/planned/not_run。

## 辅助用例：安全、数据、目录与交付

### TC-TM002-LIMIT-01 — 2 秒枚举期限的固定时钟边界

- 追踪：REQ-TM002 / AC-TM002-001 / TASK-TM002-PREVIEW；层级 unit，辅助产品 E2E，不属于 E2E-TM002-001 的安装包场景，也不替代 PREVIEW-04 三个真实目录变体。
- 前置与输入：仅在版本化单元测试中调用同一候选枚举算法，注入固定可控的单调时钟和只返回合成元数据的 FS adapter。根 A 的 adapter 按顺序提供普通相对候选 A1、A2；时钟读取序列固定为开始 0 ms、完成 A1 时 1999 ms、尝试 A2 前 2001 ms。最大枚举期限=2000 ms，深度8/1000候选/5000目录项均未触及；不调用原生面板、不启动安装后 App，也不访问用户文件。
- 数据/SQL/重置：输入 A1/A2 与时间序列写在固定测试源码；仅内存 adapter，无服务/SQLite/本机来源记录，SQL 不适用。每例新建测试结果目录并清理本例所有的内存状态；模拟 adapter 不代替原生面板与 App 主进程范围控制的产品证据。
- 步骤：
  1. 用固定单调时钟与 FS adapter 调用候选枚举。UI 不适用，原因是单元边界测试；adapter 首项为 A1，内容 open/read 为零，无网络/DB 操作。
  2. 在 1999 ms 接受 A1 的安全元数据；下一次检查已到 2001 ms。结果只含相对路径 A1、25 B 与固定 mtime；A2 未进入结果，返回 incomplete=true、reason=timeout，不返回“完整 0 个”，无网络/DB 操作。
  3. 核对时钟调用次序、adapter 调用次数、输入/输出摘要与未读正文；无真实 A/B、服务或 DB 副作用。此结果只证明算法对 2 秒期限的反应，不能冒充真实 macOS 目录或最终包 E2E。
- 完成/证据/绑定：固定源码与原始单元结果须能按 TC-TM002-LIMIT-01 重复执行；计划文件 apps/desktop/tests/source-access.limits.test.ts，automated_test=null。状态 baselined/planned/not_run；PREVIEW-04 的真实目录变体仍各自承担最终包门禁。

### TC-TM002-STORE-01 — 密文恢复或原子写入失败的安全状态

- 追踪：REQ-TM002 / AC-TM002-001、AC-TM002-002 / TASK-TM002-STORE；层级 security_unit，辅助产品 E2E，不能代替 STATE-01 的真实重启与身份恢复。
- 前置与输入：三个稳定变体各自使用全新测试自有 0700 profile、0600 `sources/` 记录、合成 S1/Alice 身份和 A/B 根；测试适配器只在本例内向真实来源存储/访问代码注入受控的 `safeStorage` 结果，不访问真实用户 Keychain。记录预置符合 schema 的不透明密文、origin/account.id 与根身份摘要，不含可供回退的明文路径。`TC-TM002-STORE-01#KEY_UNAVAILABLE` 令异步密钥能力检查返回不可用；`TC-TM002-STORE-01#DECRYPT_FAIL` 令能力可用但对 A 密文的解密 Promise 以固定错误拒绝；`TC-TM002-STORE-01#WRITE_FAIL_KEEP_OLD` 先安全恢复已确认健康 A 的 true/false，并成功为同三元组新 B 加密，随后仅对本例私有 `sources/` 原子写入阶段注入固定 temp write/rename 失败。
- 数据/SQL/重置：各变体独立使用 R 的自有 A/B 与 profile、固定密文测试值和独立 run_id；没有登录服务或 SQLite，SQL 不适用，因为只测试本机存储边界。前两变体 expected 为 `needs_reselect` 或等价安全停读错误、来源能力未建立、A/B 后续访问零；新 B 原子写入失败变体在旧 A 密文仍可解且身份/根健康时，expected 为旧 A 来源、意愿、旧密文字节摘要及刷新能力均保持，新 B 绝不确认，B 无候选访问。全部不得明文回退，只按 owner marker 清理本例记录。
- `#KEY_UNAVAILABLE` 固定步骤：
  1. 核对预置密文记录为 0600、归属 S1/Alice，测试适配器报告 Keychain 加密能力不可用。UI 不适用，原因是存储单元测试；A/B 未访问、无网络/DB 操作。
  2. 调用真实来源存储代码的恢复入口。返回安全错误/需重新选择，不解密或信任记录、不建立读取能力；不能尝试从普通设置、日志或记录字段取明文目录路径；A/B readdir/stat/open/read/watch 为零，无网络/DB 操作。
  3. 在同一不可用条件下尝试确认新暂选 A。不得写入明文或弱化密文记录，也不得将来源标为已确认；对原记录的保留或安全清理由版本化存储合同决定，但不得产生可读取能力；保存脱敏错误码和文件摘要，无网络/DB 操作。
- `#DECRYPT_FAIL` 固定步骤：
  1. 核对同样的独立密文输入，令加密能力检查成功、`decryptStringAsync` 对此记录以固定错误拒绝。UI 不适用；A/B 未访问，无网络/DB 操作。
  2. 调用真实来源存储代码的恢复入口。返回安全错误/需重新选择，不以密文字节、原路径缓存或明文备用字段推断目录；不建立读取能力，A/B 后续访问零，无网络/DB 操作。
  3. 再请求受控刷新并检查本例配置/审计。刷新被拒绝且不能报告“完整 0 个候选”；记录、诊断与原始结果只含状态、错误码和摘要，不含路径、明文或密文值；无网络/DB 操作。
- `TC-TM002-STORE-01#WRITE_FAIL_KEEP_OLD` 固定步骤：
  1. 以本例有效的 S1/Alice/codex 0600 密文记录安全恢复旧 A、采集=true/未来同步=false，显式受控刷新并核对 `{sessions/2026/10/01/a-01.jsonl,sessions/2026/10/01/a-02.jsonl}`；记录旧密文原始字节 SHA256、来源 ID、A 根身份和能力代际。UI 不适用，原因是存储/状态机单元测试；仅 A 元数据读取，B 零访问，无网络/DB 操作。
  2. 由受控选择 provider 提供本例 B 的暂选结果（不经 renderer 传路径），调用同一三元组的真实 `confirmSource`，观察 `encryptStringAsync` 对 B 成功；仅对本例私有 `sources/` 的原子 temp write/rename 阶段注入固定失败。UI 不适用；返回写入错误，提交未发生，旧 A 的来源 ID、true/false、能力与 0600 密文记录原始字节 SHA256 完全不变，失败临时文件不得成为可恢复记录；B 仅允许选择时的根元数据校验，不建立 B 确认或候选读取能力，A/B 正文零读取；无网络/DB 操作。
  3. 再对旧 A 请求受控刷新。UI 不适用；候选仍恰为 A1/A2，文件仅 A 元数据、B readdir/open/read/watch 为零，新 B 不生效；旧密文字节摘要、A 根身份与意愿仍与步骤 1 一致，未留下明文或半确认 B；保存拒绝码、前后摘要和 A/B 访问时间序列，无网络/DB 操作。
- 完成/证据/绑定：三个变体各自保存注入点、调用顺序、状态/能力断言、0600 原密文摘要、访问分界、无明文回退及清理；只有 B 加密成功后本例私有记录写入失败且旧 A 仍健康时才保留旧 A，Keychain 不可用或旧密文解密失败必须停读需重选。本辅助例不代替 STATE-01 的真实包、Keychain 和身份恢复证据。计划文件 apps/desktop/tests/source-store.security.test.ts，automated_test=null；状态 baselined/planned/not_run。

### TC-TM002-ACCESS-06 — 内部分页游标完整性与失效

- 追踪：REQ-TM002 / AC-TM002-001、AC-TM002-002 / TASK-TM002-ACCESS；层级 unit，辅助来源访问能力，不是安装包 E2E，也不放宽 UI 预览最多 1000 候选的上限。
- 前置与输入：三个稳定变体各自用 R 生成真实 A 根内普通 `a.jsonl`、目录 `a/` 下的普通 `a/x.jsonl`，以及根内 `p-0000.jsonl` 至 `p-1198.jsonl` 共 1199 个普通 p-* 文件，候选总数恰为 1201；每个候选固定 3 B、同一 mtime，`a/` 为本例自有 0700 目录，B 的 B1 未选择。独立 expected 按完整相对路径的 UTF-8 字节序为 `a.jsonl`、`a/x.jsonl`、随后全部 p-* 升序；`.`(0x2e) 小于 `/(0x2f)`，即使根目录项原始名称排序把 `a/` 放在 `a.jsonl` 前，候选结果仍须先给 `a.jsonl`。已确认的合成 S1/Alice/codex 来源只指向本例 A，采集=true，内部只读分页 `pageSize=256`，游标绑定来源 ID、身份、根身份和目录树版本。`#PAGE_COMPLETION` 与 `#TREE_CHANGED` 均须在本例真实文件系统上运行生产 C helper 与主进程分页，不能用 FS adapter 自报版本代替；`#REVOKE_CURSOR` 用同一生产分页状态机和受控撤销时序。三变体均不调用原生面板、renderer 或安装后 UI，故只属辅助测试；UI 预览仍最多显示 1000 条并标不完整。
- 数据/SQL/重置：每变体独立建立 owner marker、上述 1201 文件输入清单、预先按完整相对路径计算的逐页 expected 与原始结果：第一页 `a.jsonl,a/x.jsonl,p-0000.jsonl…p-0253.jsonl`，第二页 p-0254…p-0509，第三页 p-0510…p-0765，第四页 p-0766…p-1021，第五页 p-1022…p-1198，页数 256/256/256/256/177。`#TREE_CHANGED` 另预先固定新增普通文件 `p-0000a.jsonl`（3 B，同一 mtime），新树中字节序位于 `p-0000.jsonl` 与 `p-0001.jsonl` 之间，即总序第 4 位；新树共 1202 条、五页 256/256/256/256/178。无服务/SQLite，SQL 不适用。只读元数据，不打开正文；仅清理本例自有 A/B/profile 和新增文件，未读/失效不得记录为完整空集。
- `TC-TM002-ACCESS-06#PAGE_COMPLETION` 固定步骤：
  1. 以 S1/Alice 来源 ID 经生产 C helper/主进程在真实 A 根请求第一页。UI 不适用，原因是内部单元能力；按完整相对路径排序返回 `a.jsonl,a/x.jsonl,p-0000.jsonl…p-0253.jsonl` 共 256 条及受限游标，`complete=false`；不得按根目录项 `a/`、`a.jsonl` 的原始顺序先给 `a/x.jsonl`。只读 A 元数据且 B 零访问；无网络/DB 操作。
  2. 顺序提交每页返回的游标，直至结束。第 2 页恰为 p-0254…p-0509，第 3 页 p-0510…p-0765，第 4 页 p-0766…p-1021，各 256 条；第 5 页 p-1022…p-1198 共 177 条。单页均不超过 256，前四页 `complete=false`，只有第五页 `complete=true` 且无后续游标；不打开正文、B 零访问，无网络/DB 操作。
  3. 将五页完整相对名合并与事先固定的 1201 条清单逐项比较，`a.jsonl` 必须先于 `a/x.jsonl`，其后 p-* 各恰好一次且顺序一致；结果明确标记内部完整遍历，不能据此把 UI 的 1000 条预览标完整；保存页数、计数、完整相对名排序比较/摘要、游标摘要与文件审计，无网络/DB 操作。
- `TC-TM002-ACCESS-06#REVOKE_CURSOR` 固定步骤：
  1. 从独立 1201 输入请求第一页并取得按完整相对路径排序的 `a.jsonl,a/x.jsonl,p-0000.jsonl…p-0253.jsonl` 共 256 条和游标。UI 不适用；仅 A 元数据访问，B 零访问；无网络/DB 操作。
  2. 通过受限来源状态机撤销该来源，再用旧游标请求第二页。记录/能力立即清除，旧游标被拒绝为失效；撤销后 A/B 后续访问零，不返回余页或 `complete=true`；无网络/DB 操作。
  3. 核对第一页以外无结果提交、旧游标重试仍拒绝，报告为已撤销/不完整而非“完整 256 条”；密文记录已删除，原始 A/B 未改，保存状态与访问时间序列，无网络/DB 操作。
- `TC-TM002-ACCESS-06#TREE_CHANGED` 固定步骤：
  1. 在本例已确认的真实 A 根上用生产 C helper/主进程分页请求第一页。UI 不适用，原因是辅助内部能力测试；返回 `a.jsonl,a/x.jsonl,p-0000.jsonl…p-0253.jsonl` 共 256 条、`complete=false` 和绑定真实树状态的旧游标；根目录项原始顺序不能颠倒前两条完整相对名，仅 A 元数据访问，B 零访问；无网络/DB 操作。
  2. 首页面完成后由本例 fixture 向已遍历的真实 A 根原子加入普通 `p-0000a.jsonl`，核对输入清单从 1201 变 1202，随后仍经生产 C helper/主进程提交旧游标。UI 不适用；旧游标返回树已变化的 `invalid/incomplete`，不得返回下一页或 `complete=true`，也不得把旧第一页与新树后续结果拼接；判据取自真实目录变化与 helper/主进程结果，不能从可控 adapter 自报版本生成 expected。B 零访问、正文零读取；无网络/DB 操作。
  3. 废弃旧扫描并从新树开启全新内部扫描，依次提交新游标至穷尽。UI 不适用；五页候选分别 256/256/256/256/178，按完整相对路径 UTF-8 字节序与预先固定的 1202 条清单逐项相同，前两条为 `a.jsonl,a/x.jsonl`，`p-0000a.jsonl` 恰好在总序第 4 位，全部无重漏，前四页 `complete=false`，仅第五页 `complete=true` 且无后续游标；B 零访问、正文 open/read=0；无网络/DB 操作。保存旧游标拒绝、新旧清单、真实 helper 与主进程审计及新增文件的本例清理结果。
- 完成/证据/绑定：三变体各自记录固定输入、逐页独立 expected、游标身份/版本与撤销或变更时序；`#TREE_CHANGED` 缺真实生产 C helper、真实目录变更或新树 1202 条完整遍历则保持绑定待补，不能以 adapter 自报版本或旧游标结果放宽判据。本例不代替最终安装 App 的 E2E。计划文件 apps/desktop/tests/source-access.pages.test.ts，automated_test=null；状态 baselined/planned/not_run。

### TC-TM002-SECURITY-01 — renderer 不能传任意路径

- 追踪：REQ-TM002 / AC-TM002-001、AC-TM002-002 / TASK-TM002-ACCESS；层级 security_unit，辅助产品 E2E，不代替原生面板与 App 主进程 allowlist 的产品证据。
- 前置与输入：固定主进程 `tokenmeter:invoke` 业务IPC handler/来源服务测试环境；已验证 S1 Alice，无待确认选择；本例独占并标记短根 `R=/tmp/t2-<8位十六进制>`，自有 `R/A/a.jsonl`、未授权 `R/B/b.jsonl`，路径字串长度事前断言≤64。`TC-TM002-SECURITY-01#ABSOLUTE` 调用 `previewSource({selectionId: R+'/B/b.jsonl'})`；`TC-TM002-SECURITY-01#FILE_URL` 调用 `previewSource({selectionId: pathToFileURL(R+'/B/b.jsonl').href})`；`TC-TM002-SECURITY-01#DOTDOT` 调用 `previewSource({selectionId:'../B/b.jsonl'})`；`TC-TM002-SECURITY-01#TOKEN` 调用 `previewSource({selectionId:'00000000-0000-4000-8000-000000000099'})`。前三个输入不是UUID，第四个为未签发UUID；各自固定预期为返回snapshot的`error='invalid_selection'`（没有未处理异常）、无pending/confirmed来源变化、B的metadata/open/read均0。`chooseSource({tool,rootPath})`会忽略额外`rootPath`并启动选择器，不能用于这三个安全拒绝变体。三个受控竞态变体仍为`TC-TM002-SECURITY-01#STALE_SELECTION`、`TC-TM002-SECURITY-01#REVOKE_DURING_REFRESH`和`TC-TM002-SECURITY-01#SWITCH_DURING_REFRESH`；全部只用本例合成身份和目录，不含用户目录，竞态通过Promise屏障驱动同一主进程代码，不把受控选择结果或adapter当真实原生面板产品证据。
- 数据/SQL/重置：七变体各自使用新 run_id、R 与独立 A/B/profile；仅内存 handler、受控异步屏障和隔离文件，没有服务或 DB 调用，SQL 不适用。四个恶意参数的 expected 为拒绝且 B 零访问、无来源确认；三个竞态的 expected 分别为过期选择不提交、撤销或换身份后旧刷新结果不提交，并以操作前后时间序列判读文件访问。
- 四个恶意参数变体的固定步骤：
  1. 建立已验证 Alice/窗口、记录 A/B 审计基线。测试 UI 不适用，原因是本例为主进程参数安全层；A/B 文件未被读取，无网络/DB 操作。
  2. 在同一已验证主frame调用`tokenmeter:invoke('previewSource',{selectionId:<该变体固定字串>})`。返回snapshot的`error='invalid_selection'`，不返回内容、绝对路径或 locator；不存在 renderer 任意文件读取 API，A/B open/read=0、B 元数据访问=0，pending/confirmed不变；无网络/DB 操作。
  3. 只读检查本例 sources 记录与审计。四变体均未确认来源、未修改 A/B 字节；原始结果按变体 ID 分别写入，报告只记变体名和错误码，不记实际路径或 token；无网络/DB 操作。
- `#STALE_SELECTION` 固定输入/步骤：初态 S1/Alice 已验证、无来源；受控选择 provider 将 A 的选择结果停在 Promise 屏障，不经 renderer 提交路径。①发起选择并在结果未返回时将身份切至本例 S1/Bob，确认旧选择的会话代号失效；UI 不适用，原因是竞态单元测试，尚无 sources 记录、A/B 未枚举，无网络/DB 操作。②释放旧 Alice 选择的 A 结果；主进程按当前身份/代号拒绝过期结果，不为 Bob 建立暂选或已确认 A，也不返回 locator/绝对路径，B 零访问；无网络/DB 操作。③核对 Bob 与 Alice 本例私有记录均无新增来源，A/B 未被读取、旧选择结果已丢弃并单独保存时序证据；无网络/DB 操作。
- `#REVOKE_DURING_REFRESH` 固定输入/步骤：初态 S1/Alice 已确认 A、true/false；受控 FS adapter 将刷新停在首个 A 元数据读取后、结果提交前。①启动受控刷新，记录停点与允许的撤销前 A 元数据读取；UI 不适用，B 零访问、正文零读取，无网络/DB 操作。②调用同一来源状态机撤销 A，然后释放屏障；密文记录删除、读取能力立即失效，旧刷新 Promise 不能提交候选或 `complete=true`，撤销后的 A/B readdir/stat/open/read/watch 均为零；无网络/DB 操作。③重试旧刷新请求须拒绝，保留撤销前与撤销后分界的审计、私有记录删除证据及 A/B 原文哈希；无网络/DB 操作。
- `#SWITCH_DURING_REFRESH` 固定输入/步骤：初态 S1/Alice 已确认 A、true/false；受控 FS adapter 将刷新停在首个 A 元数据读取后、结果提交前；S1/Bob 为同服务不同账号。①启动 Alice 刷新，记录停点与身份代号；UI 不适用，只有切换前 A 元数据读取、B 零访问，无网络/DB 操作。②在屏障停点卸载 Alice 能力并切至 Bob，再释放旧 Promise；旧结果不得交给 Bob 或写入其状态，Bob 无来源，切换后 A/B 后续访问零、正文零读取；无网络/DB 操作。③Bob 请求旧 Alice 来源 ID 的刷新被拒绝，Alice 的密文记录保留但不授予 Bob；保存前后身份与访问时序的脱敏摘要、A/B 原文哈希；无网络/DB 操作。
- 完成/证据/绑定：#ABSOLUTE/#FILE_URL/#DOTDOT/#TOKEN/#STALE_SELECTION/#REVOKE_DURING_REFRESH/#SWITCH_DURING_REFRESH 七个变体分别有固定输入、逐步原始结果、操作分界与独立清理；竞态单元结果不能代替真实系统面板/安装包 E2E。计划文件 apps/desktop/tests/source-access.security.test.ts，automated_test=null。状态 baselined/planned/not_run。

### TC-TM002-DATA-01 — fixture 仅操作自有根

- 追踪：REQ-TM002 / AC-TM002-001、AC-TM002-002 / TASK-TM002-DATA；层级 governance_unit，非产品 E2E。
- 前置与输入：新的 run_id、自有 0700 临时根；生成参数 seed=42、mtime=2026-10-01T00:00:00Z；另准备一个无 owner marker 的隔离拒绝样本，不在用户目录。
- 数据/SQL/重置：只写自有 fixture A/B 和 expected manifest；无服务/DB，SQL 不适用，因为数据是本地权限/文件状态。重置按 R，拒绝样本由测试自身单独清理。
- 步骤：
  1. 运行计划中的生成器。输出初始 A/B 文件集合、25/12 B 固定字节、28 B 新增文件配方、链接、mtime、owner marker、expected 与 SHA256；文件与目录模式符合合同，无网络/DB 操作。
  2. 对自有 A 做 chmod 000、恢复 0700，再做 A→A-old/新 A 替换。独立 stat 和拒读探针产生预定状态；B 与初始文件内容未改，无网络/DB 操作。
  3. 对无 marker 根调用重置须拒绝；对有 marker 的本例根调用重置应只清理本例所有物。拒绝样本不受生成器清理，用户根不被触碰；无网络/DB 操作。
- 完成/证据/绑定：两次同 seed 的新 run_id 得相同相对 manifest/expected 摘要（run_id 字段除外）；计划脚本 scripts/granular_permissions.py 与 tests/governance/test_granular_permissions.py，automated_test=null。证据为原始 manifest、mode/stat/哈希与清理日志。状态 baselined/planned/not_run。

### TC-TM002-CATALOG-01 — 各版本 TC 归属不能串线

- 追踪：REQ-TM002 / AC-TM002-001、AC-TM002-002 / TASK-TM002-CATALOG；层级 governance_unit，非产品 E2E。
- 前置与输入：本例私有目录中的 catalog 临时复制品包含 TC-TM001-LOGIN-01（归属 v0.1.0-20260929T074814Z 的原 TASK）和 TC-TM002-SELECT-01（归属 v0.2.0-20261001T034118Z/TASK-TM002-PICKER）。固定变体 TC-TM002-CATALOG-01#VALID 保留这两个正确映射；TC-TM002-CATALOG-01#MISSING_TASK 只删除 TC-TM002-SELECT-01 的 task_ids 字段；TC-TM002-CATALOG-01#WRONG_RELEASE 只把 TC-TM002-SELECT-01 的 release_id 错误写成 v0.1.0-20260929T074814Z。每变体单独从原始有效样本复制，不叠加变更。
- 数据/SQL/重置：只改自有临时副本，不改源 catalog；无服务/DB，SQL 不适用。每变体按 owner marker 清理独立副本。
- 每个变体的固定步骤：
  1. 核对临时副本 SHA 与该变体输入。UI 不适用，原因是治理检查；无 App 文件访问、网络或 DB 操作。
  2. 执行固定 catalog 治理检查。#VALID 退出码 0 且两个 TC 映射均正确；#MISSING_TASK 按 TC-TM002-SELECT-01 报缺 TASK 且非 0；#WRONG_RELEASE 按同 ID 报 release/TASK 归属冲突且非 0；无网络/DB 操作。
  3. 核对源 catalog SHA 未变、没有 TC 被静默删除，分别保存命令、退出码和该变体原始输出；无网络/DB 操作。
- 完成/证据/绑定：#VALID/#MISSING_TASK/#WRONG_RELEASE 各自独立结果；计划文件 tests/governance/test_tm002_catalog.py、scripts/export_test_cases.py，automated_test=null。状态 baselined/planned/not_run。

### TC-TM002-EVIDENCE-01 — 缺原生/文件审计不得放行

- 追踪：REQ-TM002 / AC-TM002-001、AC-TM002-002 / TASK-TM002-RUNNER；层级 governance_unit，非产品 E2E。
- 前置与输入：固定程序只在本例私有目录生成合成原始报告及隔离副本，绝不改真实产品报告。稳定变体 TC-TM002-EVIDENCE-01#COMPLETE 为结构完整的合成输入；TC-TM002-EVIDENCE-01#MISSING_STEP 只删除步骤 2 的逐步事件；TC-TM002-EVIDENCE-01#MISSING_PICKER 只删除唯一的真实面板事件；TC-TM002-EVIDENCE-01#MISSING_FS 只删除该 TC 的来源访问审计；TC-TM002-EVIDENCE-01#WRONG_PACKAGE 将 package manifest SHA256 改为 64 个字符 0；TC-TM002-EVIDENCE-01#FAILED_CLEANUP 将 cleanup.completed 改为 false。各变体从同一完整合成母版单独构造，不叠加。
- 数据/SQL/重置：只生成自有报告副本；无服务/DB，SQL 不适用。按 owner marker 独立清理，真实报告不可写。
- 每个变体的固定步骤：
  1. 读取本变体输入并核对原始母版和变体 SHA。UI 不适用，原因是证据复核；无 App 文件访问、网络或 DB 操作。
  2. 独立复核器读取本变体。#COMPLETE 仅结构核对通过且 release_eligible=false，不能签产品通行证；#MISSING_STEP、#MISSING_PICKER、#MISSING_FS、#WRONG_PACKAGE、#FAILED_CLEANUP 均分别返回非 PASS 与对应缺项原因，缺 FS 时 UI 无 B 不可补证；无网络/DB 操作。
  3. 核对输入原件未覆盖、首次失败和复核输出按变体单独保留；无网络/DB 操作。
- 完成/证据/绑定：六个变体各自有输入、期望、退出码与原始复核输出；计划文件 tests/governance/test_tm002_evidence.py 与本机 gate，automated_test=null。状态 baselined/planned/not_run。

### TC-TM002-DELIVERY-01 — 最终包、升级与全量回归门禁

- 追踪：REQ-TM002 / AC-TM002-001、AC-TM002-002 / TASK-TM002-DELIVERY；层级 delivery_gate，辅助最终产品验收，不代替任一产品 TC。
- 前置与输入：已锁定候选 SHA/tree、0.2.0 最终 DMG 原件/清单、上一0.1本机正式稳定DMG及其SOP-018通行证、SOP-020 schema 2 `release-index.json`（`milestone_sha/tree`、`master_tip_sha`、`remote_source_state=PENDING`、原DMG/manifest/passport摘要）、签名、同机隔离签名更新源与每例隔离服务；若没有这些前置或真实升级入口，本例为 BLOCKED，不能用开发/候选包、受控101或同源码测试高版冒充。远端源码登记与Tag可待最终统一办理。TM-001 全部已交付 TC 和 TM-002 产品 TC 的固定清单在运行前确定。
- 数据/SQL/重置：每个产品 TC 由 R 独立准备账号/DB/来源，门禁只读原始摘要并核对其 SQL/数据引用；本门禁自身无业务 SQL 写入。所有包、服务、安装目录只清理本次获得所有权的资源。
- 步骤：
  1. 从最终 DMG 安装并运行固定完整集合。UI、原生面板、真实服务和隔离 DB 由各产品 TC 操作；原始记录须包含全部目标 TC 及 TM-001 回归的唯一尝试、逐步断言和清理，无漏例/跳过/重试取绿；网络/DB 按各产品 TC。
  2. 由固定消费者先只读核对上一0.1本机稳定原包的schema 2归档/通行证/来源身份与实际摘要，负测拒绝旧schema、候选包、错误里程碑或摘要；再从该原包安装，经 App 自主检查/安装 0.2.0 候选并重启。UI 显示新版本与保留的 TM-001 合成账号/配置，经真实 `/v1/me` 复核身份；包签名、摘要和运行中进程版本与清单一致。0.1 没有 TM-002 来源记录，0.2 初态必须为 `none`；随后真实面板选择 A、确认意愿、重启恢复本版密文来源。网络/DB 只按更新与认证的已定合同发生。
  3. 独立父门禁先复读候选/包/测试源码、TM-001 全部原件、除本例外的 TM-002 其余 27 条父 TC 与 35 个变体原件、升级、平台和清理，再从这些实际结果计算本例状态。本例不能作为父门禁启动前须已 PASS 的输入；计算前为 BLOCKED。只有其他各项和本例自身包/升级/证据核验均 PASS，才记本例 PASS 并签发本机通行证；任一缺项、失败、跳过或摘要不匹配给 FAIL/BLOCKED 且无正式原名 DMG；本步骤无业务 DB 写入。
- 完成/证据/绑定：正式包原件、上一0.1本机稳定原包及schema 2归档/通行证/来源身份与负测、其他 27 条 TM-002 父 TC、35 个变体、TM-001 全量原件及最终签名/升级证据全部一致，父门禁独立派生本例结果。计划绑定 SOP-014/017/018 的本机 runner/gate，automated_test=null；证据为原始包/升级/回归/独立 gate 结果及每 run_id Excel，状态 baselined/planned/not_run。

## 追踪与退出条件

本文件 28 个稳定父 TC 的 TASK 映射为：PICKER 4、PREVIEW 5（含辅助 LIMIT-01）、CONSENT 4、STORE 4（含辅助 STORE-01）、ACCESS 7（含辅助 SECURITY-01、ACCESS-06）、DATA 1、CATALOG 1、RUNNER 1、DELIVERY 1。SELECT-01/02/04、PREVIEW-01 至 04、CONSENT、STATE 属 E2E-TM002-001；SELECT-03 与 ACCESS-01 至 05 属 E2E-TM002-002；其余 8 个辅助 TC 不作为产品 E2E PASS 计数。35 个稳定变体分别为：SELECT-02 的 3 个、PREVIEW-04 的 3 个、CONSENT-03 的 2 个、CONSENT-04 的 3 个、STATE-01 的 2 个、STORE-01 的 3 个、ACCESS-06 的 3 个、SECURITY-01 的 7 个、CATALOG-01 的 3 个、EVIDENCE-01 的 6 个。父 TC 的所有已声明变体均必跑、逐变体独立记录；没有 `#ID` 的父路径照常单独判定。每个 TC 的独立行与变体已同步至 tests/test_cases.json；生成索引、矩阵、版本计划及项目总表由本轮整合继续复核，不把设计行冒充已执行结果。

授权模型已确定为原生目录选择器 + App 持久来源 + 主进程读取 allowlist。SOP-000 私有加密 locator 例外已按 PR #4/#5 同步；SOP-008 逐例语义复核已完成。厂商来源版本与正文解析在 TM-003/004 验收，并把以上“计划”绑定改为实际固定程序与可执行判据。数据和程序就绪仍不等于运行通过；缺原生面板自动化、Keychain 测试项隔离原生证明、主进程范围判定与实际文件访问审计、最终包或任一必测 TC 结果，均按 SOP-014/018 保持 BLOCKED。
