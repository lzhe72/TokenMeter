# v0.2.0-20261001T034118Z — 测试计划（已基线）

本计划按 SOP-006 为[具体任务](02-breakdown.md)分配稳定 TC。目标是安装后真实 Electron App、真实隔离认证服务与 SQLite、真实 macOS 目录面板。用户已确定原生面板 + App 强制来源范围，不验沙盒级持久授权；跨重启目录 locator 仅以系统密钥保护的密文保存在当前用户私有记录。SOP-002/004/006 已同步这一有限私有存储边界，逐条用例、机器清单及总表已完成一致性复核和 SOP-008 设计基线。开发工作树已有部分固定程序，具体数量与结果见[执行记录](06-iteration-record.md)；本页设计基线并不证明本工作树程序就绪或产品通过。旧 `E2E-TM002-001/002` 保留为场景组，组内每条 TC 独立判定。开发期按本功能固定TC回归；与已交付功能的跨需求完整最终包回归留待用户启动正式发行。

## 执行集合与前置

- 升级源固定验真：在 0.2.0 最终包运行前，以固定程序只读核对上一0.1本机稳定原包的 schema 2 `release-index.json`、SOP-018通行证、归档/DMG/manifest摘要、`milestone_sha/tree` 与本地`master`祖先、`master_tip_sha`和`remote_source_state=PENDING`；旧 schema、开发/候选包、错误里程碑或摘要必须由固定负测拒绝。缺程序或任何原件则`TC-TM002-DELIVERY-01`为BLOCKED，不手工认定升级源。
- 目标平台：当前本机 macOS 15 Intel。TM-002 全部产品 TC、TM-001 已交付功能的全部细化 TC 和六组补充场景均需同一最终候选重新执行；TM-001 独立 `d2db551` 候选门禁 PASS，但本地 `master` 整合树尚未通过同树完整门禁或形成稳定0.1原包；0.2.0 不能借用其旧候选结果。
- 每例由固定程序建立新的 0700 私有 profile、动态独占回环 FastAPI/隔离 SQLite、合成账号、专用来源 A/B 与独立 expected。通过真实登录界面指向本例服务。测试 profile 的运行时 App 名称拟按其规范化路径稳定派生，正式 profile 仍为 `TokenMeter`；这是待验证设计。须在同一最终 DMG 的异步 `safeStorage` 首次调用前取得实际目标 Keychain item 身份和签名访问边界证据，确认本例测试 item 此前不存在且与正式 App 项分离，再用仅匹配本例测试名称的精确元数据探针核对调用后状态；不得查询、修改或删除正式项。未证实隔离时依赖密钥的用例为 BLOCKED。不得扫描用户 `~/.codex`、`~/.claude` 或操作用户 App、49176 服务、生产库与默认凭据。
- 目录选择由真实 `dialog.showOpenDialog` 启动，固定系统 UI 自动化驱动原生面板；observer 只记录调用、取消和来源标签，原方法照常执行。Playwright 的 DOM/IPC stub 或直接注入目录路径不构成产品 E2E。环境缺少系统 UI 自动化权限则相关 TC 为 BLOCKED。
- 独立来源读取审计须覆盖实际主进程与随包同 UID C helper 的读取通道。helper 从私有 stdin 首帧取得受控根，以 `open(O_RDONLY|O_DIRECTORY|O_NOFOLLOW_ANY|O_CLOEXEC)`、`fdopendir`、目录描述符相对 `openat`/`fstatat(AT_SYMLINK_NOFOLLOW)` 和 no-follow 打开；控制 stdout 只返回相对名/元数据/安全错误码，stderr 不含路径。测试需在最终安装包中核对 helper 架构、签名、摘要及拒绝 symlink 竞态的固定用例；内部分页负测还须在第一页后真实插入一个按字节序落在已返回范围内的候选，核对目录 dev/ino/mtime/ctime 纳秒快照于下一页复核时失效旧游标，不能继续拼页或宣称完整。`openCandidateReadOnly` 只许 helper 复核令牌/身份/目标 dev+ino 后以有界私有流向主进程适配器供字节，不向 renderer/日志/报告；TM-002 产品预览不得调用它。缺失或不符不退回绝对路径扫描。审计记录 TC/步骤、来源标签 A/B、相对候选名、操作、时间和结果，不记录绝对路径、正文或密钥；未覆盖的读取通道不能仅凭 UI 未显示 B 判 PASS。测试代码与审计器均需固定治理负测。

## 合成数据与独立预期

`system_permissions` 数据程序待 SOP-010 实现。每例独占根内的 A/B 为程序创建且可清理的目录；已定 UI 预览规则是在所选根内递归检查非符号链接普通 `.jsonl`，选中根深度 0、最多 8 层、1000 候选、5000 目录项和 2 秒，超限标明“不完整”，不能当作解析器兼容证明。候选按相对名 UTF-8 字节序排序：`CANDIDATES_1001` 的 1001 个输入均在其他预算内，须显示 `c-0000` 至 `c-0999`，不能把 `readdir` 返回的前 1000 个事后排序。目录项或时间预算先到时只显示已安全核验且排序的部分，并标明不完整，不声称全树前 1000。供 TM-003/004 使用的内部扫描另按最多 256 项一页续扫；只有稳定树穷尽才可宣称完整。Codex 合成路径为 `sessions/2026/10/01/*.jsonl`；Claude Code 合成路径为 `projects/sample/*.jsonl`。A 内候选 `a-01.jsonl`、`a-02.jsonl` 有固定字节数和 mtime，正文包含仅供泄漏拒绝检查的合成标记 `PRIVATE_A1/PRIVATE_A2`；同层 `ignore.txt` 非候选。B 内 `b-01.jsonl` 含 `PRIVATE_B1`；除 `SELECT-02#REPLACE_CONFIRMED` 通过真实面板明确选择 B 以验证原子换根外，其余产品 E2E 变体均不选择 B；辅助 `STORE-01#WRITE_FAIL_KEEP_OLD` 仅以受控 provider 暂选 B，不经原生面板。A 内另有指向 B 的文件/目录符号链接，**必须放在枚举会遇到的候选层级**；测试审计要证明枚举确实遇到并拒绝该链接，不能以 glob 未匹配冒充边界防护。后续通过新 `a-new.jsonl`/`b-new.jsonl` 观察确认前与失效后读取范围。预期候选集合由测试清单在运行前固定，不调用产品枚举逻辑生成。`STORE-01#WRITE_FAIL_KEEP_OLD` 在已安全恢复健康 A 且系统密钥仍可验证的独占状态下先成功加密新 B locator，再仅对本例私有记录的临时写入或原子 rename 注入一次失败，核对旧 A、旧意愿及旧密文摘要均不变；密钥提供者整体不可用或旧密文解密失败另按停读需重选判定；`CONSENT-04#TURN_COLLECT_OFF_ON` 通过真实 UI 更新已确认来源的两项布尔值，关闭采集即使旧扫描失效，重开前复核身份/根。以上仅是既定测试输入与预期，固定程序待 SOP-011 实现。TM-002 不解析正文、不产生用量 expected。

目录访问失效只作用于测试自有根：程序可对 A 临时 `chmod 000`、重命名原 A 并在旧路径新建不同 inode，最后按所有权收尾。它们检验 App 的失效处理，不能冒充 macOS TCC 授权撤销。原生面板真实选择与 App 内撤销分别有观察证据；缺固定面板驱动或实际文件访问审计时对应产品 TC 为 BLOCKED。

## TASK → TC 设计清单

下表列出[详细用例基线](../../docs/testing/cases/02-TM-002-permissions.md)的 28 条父 TC，其中 20 条属于安装后产品 E2E、8 条为辅助检查；36 个稳定变体须逐一运行和记录，不能只运行父 ID 的摘要。机器清单、版本追踪和项目总表已完成同源核对及语义基线复核。每条 TC 的固定程序、数据生成/重置与真实结果尚不存在；表格摘要不能代替逐条规格。

| TC | TASK | 场景组 | 独立判据 |
| --- | --- | --- | --- |
| `TC-TM002-SELECT-01` | PICKER | 001 | 干净登录后从原生面板选 A，UI 进入待确认；未写已确认 locator。 |
| `TC-TM002-SELECT-02` | PICKER | 001 | 首次面板取消仍无来源；已确认 A 后再次取消保留原态；另从健康 A 选择新根并成功确认，仅在原子提交后替换 A 且旧扫描失效。三变体分别判定。 |
| `TC-TM002-SELECT-03` | PICKER | 002 | 失效后面板取消仍需重新选择，不复活旧状态。 |
| `TC-TM002-SELECT-04` | PICKER | 001 | 用 Claude Code 工具类型真实选根，预览 `projects/sample/*.jsonl` 语法候选、确认并经身份验证后重启恢复；不宣称内容可解析。 |
| `TC-TM002-PREVIEW-01` | PREVIEW | 001 | 预览仅列 A 的两个既定候选相对名与元数据；无正文标记和 B。 |
| `TC-TM002-PREVIEW-02` | PREVIEW | 001 | 仅非候选文件时为 0 候选；允许确认空目录以等待未来日志。 |
| `TC-TM002-PREVIEW-03` | PREVIEW | 001 | 指向 B 的文件和目录符号链接不列入候选、无 B 读取。 |
| `TC-TM002-PREVIEW-04` | PREVIEW | 001 | 真实目录超出 1000 候选、5000 项或深度 8 时分别显示不完整，已列集合仍限 A，不能把截断说成完整。 |
| `TC-TM002-LIMIT-01` | PREVIEW | 辅助 | 固定可控时钟与只读文件系统适配器触发 2 秒截止，返回不完整；单元验证不代替最终 App 产品 E2E。 |
| `TC-TM002-CONSENT-01` | CONSENT | 001 | 只预览未确认，追加 A/B 后无后台枚举、监听或持久授权。 |
| `TC-TM002-CONSENT-02` | CONSENT | 001 | 采集开、同步关确认；手动刷新只见 A 新文件，本地两意愿分别 true/false，网络无上传。 |
| `TC-TM002-CONSENT-03` | CONSENT | 001 | 采集关闭时未来同步意愿 false/true 两变体均可保存；来源暂停采集，刷新被拒绝且无读取/上传。 |
| `TC-TM002-CONSENT-04` | CONSENT | 001 | 两意愿均开并确认仍无上传、重启恢复；经 UI 单独关闭同步保持采集；经 UI 关闭采集立即停读/取消旧扫描，再开启后复核根并恢复。三变体分别判定。 |
| `TC-TM002-STATE-01` | STORE | 001 | 正常密文在 `/v1/me` 验证同账号后重启恢复 A 与两意愿；损坏密文则停读需重选，两个产品变体分别判定。 |
| `TC-TM002-STATE-02` | STORE | 001 | 同 origin 从 Alice 换 Bob，Bob 看不到且不读取 A；返 Alice 才恢复。 |
| `TC-TM002-STATE-03` | STORE | 001 | 同账号切到隔离 origin S2 不显示 S1 的 A；切回 S1 恢复。 |
| `TC-TM002-STORE-01` | STORE | 辅助 | 系统密钥不可用或密文解密失败均停读需重选；另验新根加密成功但私有记录临时写入或原子 rename 失败时保持健康旧 A 与意愿，私有记录不含明文路径。三变体分别判定。 |
| `TC-TM002-ACCESS-01` | ACCESS | 002 | UI 撤销 A 后刷新/重启均不再读取；原目录字节不变。 |
| `TC-TM002-ACCESS-02` | ACCESS | 002 | A 拒读后受控刷新显示需重选、App 保持响应；恢复文件权限不自动复活。 |
| `TC-TM002-ACCESS-03` | ACCESS | 002 | A 路径被不同 inode 替换后旧 locator 失效；新旧目录均不得被当作原授权。 |
| `TC-TM002-ACCESS-04` | ACCESS | 002 | 失效后重新选择取消仍停止读取。 |
| `TC-TM002-ACCESS-05` | ACCESS | 002 | 恢复 A 后由真实面板重新选择并明确确认，刷新和重启均可见新增候选一次。 |
| `TC-TM002-ACCESS-06` | ACCESS | 辅助 | 内部能力对稳定的 1201 个候选按 256/256/256/256/177 五页穷尽；UI 预览仍标 1000 上限不完整，撤销或首页后在早排序位置真实插入候选分别使旧游标失效、覆盖不完整。 |
| `TC-TM002-SECURITY-01` | ACCESS | 辅助 | `previewSource.selectionId`的绝对路径、file URL、`../`及未签发UUID返回`invalid_selection`且不读B；不代替产品 E2E。 |
| `TC-TM002-DATA-01` | DATA | 辅助 | fixture 只创建、改变、恢复并清理自己拥有的根；manifest/预期/摘要可重复。 |
| `TC-TM002-CATALOG-01` | CATALOG | 辅助 | 0.1.0、0.2.0 TC 的 TASK 均按各自 release 校验，错误归属时检查失败。 |
| `TC-TM002-EVIDENCE-01` | RUNNER | 辅助 | 每条产品 TC 的原始操作、独立预期、文件审计、安装包和清理证据缺一即 FAIL/BLOCKED。 |
| `TC-TM002-DELIVERY-01` | DELIVERY | 父门禁派生辅助 | 固定父门禁先核对最终包、上一schema 2稳定归档原包与真实升级、TM-001 与除本例外的 TM-002 全部原件，再计算本例状态；本例不能预填 PASS 作为门禁启动前提。 |

`SELECT-01/02/04`、`PREVIEW-01` 至 `PREVIEW-04`、`CONSENT`、`STATE` 属 `E2E-TM002-001`；`SELECT-03` 与 `ACCESS-01` 至 `ACCESS-05` 属 `E2E-TM002-002`；`STORE-01`、`ACCESS-06`、`LIMIT-01` 等 8 条辅助 TC 分别验证加密恢复失败、分页契约、预览边界、数据、目录、安全和门禁，不作为产品 E2E 计数。36 个稳定变体分别分配给 SELECT-02（3）、PREVIEW-04（3）、CONSENT-03（2）、CONSENT-04（3）、STATE-01（2）、STORE-01（3）、ACCESS-06（3）、SECURITY-01（7）、CATALOG-01（3）、EVIDENCE-01（7）；有变体的父 ID 不替代其变体实际运行。每个 TASK 至少一条 TC。稳定 TC 须与[详细用例基线](../../docs/testing/cases/02-TM-002-permissions.md)、机器目录、验收清单、场景矩阵、数据集和项目总表双向核对；场景矩阵只登记两组 E2E ID，不将每条 TC 当新场景组。

## 数据库、网络与输出边界

TM-002 本身不修改服务端 schema 或用量表。测试准备通过 TM-001 的隔离账号 SQL 完成；预期服务端变化只有登录/会话审计等既有副作用，TM-002 的选择/预览/刷新不向服务器上传任何用量、日志正文或路径。读取证据主要来自本机受保护配置和文件访问审计。最终每个 run_id 输出独立原始结果和 `TokenMeter测试结果-<run_id>.xlsx`，项目总表只登记批次摘要；所有失败、BLOCKED、未执行原样保留。

## 2026-10-02 · 固定辅助程序绑定

`LIMIT-01`、`STORE-01`、`ACCESS-06`、`SECURITY-01`、`DATA-01`、`CATALOG-01`、`EVIDENCE-01`七父共25个精确独立ID已在`tests/test_cases.json`逐项绑定固定程序/测试名/runner/重置与命令，见[详细用例的绑定表](../../docs/testing/cases/02-TM-002-permissions.md)。运行入口`scripts/tm002_source_check.py`只检查辅助模块，逐步实测或清理缺失仍判BLOCKED；程序存在不表示本候选已执行。原产品21父及其产品变体、真实原生面板/Keychain/安装App E2E和发行门禁均独立保持未通过。
