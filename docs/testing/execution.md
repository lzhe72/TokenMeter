# 测试执行参考

先读取 [SOP 总索引](../../sop/README.md)，并按任务执行 [SOP-010 数据](../../sop/SOP-010-test-data.md)、[SOP-011 测试实现](../../sop/SOP-011-test-implementation.md)、[SOP-014 原生 E2E](../../sop/SOP-014-e2e.md) 或 [SOP-018 门禁](../../sop/SOP-018-release-gate.md)。本页补充数据格式与命令说明，独立 SOP 是执行依据。

## 1. 使用范围与当前限制

本 SOP 约束每次产品迭代和发布。默认由 Codex 自动执行：构建 → 隔离数据/账号初始化 → 原生 UI 与真实服务/数据库回归 → 收集原始结果 → 机器判定 → 失败修复后完整重跑。

每次测试计划和执行记录顶部必须带同一 `release_id`，格式及分配规则见[统一版本规范](../standards/versioning.md)。该标识关联需求、功能拆分、开发计划、测试计划、发布说明、Changelog 和最终 Git 发布；每次测试仍分配独立的 `run_id`。

TM-001 已进入 App、服务端与原生 E2E 联调，实际验收状态见[当前状态](../status.md)。执行器已接入 `xcodebuild` 和原始 `xcresult` 复核；源码存在不证明原生用例通过。缺完整 Xcode、GUI 或有效结果时为 **BLOCKED**；基础工具自检和文档检查不能替代产品验收。

### 当前可执行入口

在仓库根目录分别执行以下命令，Codex 必须读取退出码和输出：

```sh
python3 scripts/check_docs.py --mode structure
python3 scripts/check_docs.py --mode baseline
python3 -m unittest discover -s tests/governance -p 'test_*.py'
python3 scripts/quality_gate.py check
python3 scripts/test_data.py generate --run-id demo --seed 42
python3 scripts/e2e.py --phase iteration
python3 scripts/quality_gate.py iteration
python3 scripts/e2e.py --phase release
python3 scripts/quality_gate.py release
python3 scripts/test_data.py reset --run-id demo
```

- governance 测试和 `check` 只校验仓库规则与辅助程序，不是产品 E2E。
- 数据生成产物位于 `.local/test-runs/demo/`：`users.json`、`usage.jsonl`、`prices.json`、`expected.json`、`manifest.json` 和所有权标记 `.tokenmeter-fixture.json`。
- 种子 42 创建 `test-admin`、`test-alice`、`test-bob`、`test-disabled` 的合成账号资料，密码保存在生成的测试文件中；此时尚未导入任何实际 App/服务端用户库。
- `manifest.json` 标记 `fixture_kind=normalized-test-spec`，固定参考时间为 `2026-09-29T04:00:00Z`、时区 `Asia/Shanghai`，并记录文件 SHA256。这些数据不能验证真实 Codex/Claude 日志解析。
- `generate` 拒绝覆盖已存在的运行目录；`reset` 只清理固定根目录下有有效所有权标记的对应数据，不清理产品库、系统授权或 Keychain。完整产品重置入口仍须实现。
- TM-001 账号由 `tests/server/fixtures.py` 生成并由原生 runner 通过真实 CLI 导入逐例隔离库，详见 SOP-010。生成账号 JSON 与原生 UI 验收分别记录。
- 本机可用 `scripts/bootstrap_sqlite.py init-test --run-id <唯一ID>` 生成 `database/test/test.db` 和可执行的 `database/test/seed.sql`；`verify` 只读核对双库。实际生产库只在首次初始化时预置管理员，005 原生场景对临时根调用同一初始化程序，不会连接用户的 `database/production/production.db`。完整命令见[数据库说明](../../database/README.md)。
- `e2e.py` 调用真实原生 runner；`iteration`/`release` 不允许用任意外部 PASS 报告放行。缺环境返回 BLOCKED；实际断言失败为 FAIL；所有必测原生结果和证据一致才可能得到迭代 PASS。正式发布条件仍单独检查。

`quality_gate.py` 和 `e2e.py` 的退出码为 `0=PASS`、`1=FAIL`、`2=BLOCKED`；`check` 的 PASS 仅代表基础规范检查通过。E2E 每次生成独立的 `.local/e2e/<run-id>/result.json`，命令输出其绝对路径。`quality_gate.py iteration` 和 `release` 在检查元数据后会自动调用 E2E；单独调用 `e2e.py` 用于诊断，不需要为正式门禁重复执行。

机器清单中 `planned` 功能允许 `automated_test` 为 `null`；其数据集仍为 `planned` 时，`data_program` 也可为 `null`。数据集一旦为 `available`，对应场景必须绑定真实生成程序。进入 `in_progress` 或 `implemented` 前，全部场景必须绑定真实数据程序、测试入口和可用数据集。清单通过校验不代表用例已执行，发布证据要求见[发布规范](../standards/release.md)。

编制中的文档使用 structure；全部计划完成后由 SOP-008 检查 baseline。版本计划可将程序绑定显式标为 planned；SOP-009 先准备工程骨架，010/011 再实现数据与测试，绑定就绪后改为 ready。每个已填写路径必须存在，规划项用空绑定表达，不写虚构文件。独立验收清单与规格/用例双向检查；数据集的能力必须覆盖场景要求。当前 pricing 仅覆盖基础 USD，历史价格/多币种/订阅依赖 planned 的 pricing_extended。

### 本机开发与远端原生验收

用户已授权本机用于开发、运行回环服务和安装预览 App。本机现只有 Command Line Tools，不能运行 XCUITest；无需为了继续开发而在本机安装 Xcode。当前原生迭代验收由 `.github/workflows/quality.yml` 在 GitHub 托管的 `macos-15` 与 `macos-15-intel` 上选择 Xcode 16.4，对同一候选自动调用 `python3 scripts/quality_gate.py iteration`。每个平台各自在其 Mac 上构建真实 App，初始化逐例隔离的 FastAPI/SQLite，执行完整原生用例，并上传 `xcresult`、日志、fixture 摘要及候选 SHA。CI 中的 `127.0.0.1:49176` 指该 runner 自身，不是用户本机服务或 `database/production/production.db`。

第006例在每台 runner 上先独占默认端口49176，再使用第二套临时端口/SQLite；端口已占用时不得连接已有服务，须 BLOCKED。第004例的 Quick Tunnel、临时 Keychain 和签名更新 fixture 只允许专用 GitHub Mac CI。远端完整六例通过可作为该候选的开发迭代原生证据，但不能填作本机已执行；正式发布还需最终签名公证包、安装后的全量原生回归及完整支持矩阵。本机只有 Command Line Tools 时，本机原生运行仍为 BLOCKED，服务端测试和预览安装分别按实际结果记录。

若将来需要本机原生重跑，先在本机安装并首次启动完整 Xcode 16.4，由用户通过系统界面完成必要组件、许可和 Apple 登录；用 `xcode-select -p` 确认选择完整 Xcode 后才运行 `xcodebuild -version`。第004例 CI 专用 fixture 不能仅靠设置 GitHub 环境变量搬到本机；本机没有独立程序和证据时仍不执行该例。

### 自动执行环境前提

专用 Mac 或 Mac 虚拟机必须有已登录桌面、受支持的 macOS/架构、Xcode 和 UI 自动化权限；发布环境还需真实签名、公证、更新服务和隔离的本版目标数据库。v0.1.0 使用 SQLite。管理员提供凭据和机器初始授权后，Codex 通过程序执行场景、断言结果和判定门禁。缺环境时记录具体原因；用户口头确认、人工截图或手工通过报告不能解除阻断。

TM-001第004例的CI专用源使用临时公开`https://<随机>.trycloudflare.com`访问本机签名更新fixture，`cloudflared`以本次CA池验证本机HTTPS，App以系统TLS验证公开HTTPS并由Sparkle验证EdDSA包。需先验证固定版本的`cloudflared`与SHA256，再运行`python3 scripts/native_environment.py`。拿到同一隧道域名后，在共享的最多180秒窗口内先用Cloudflare和Google的HTTPS DNS查询核对公开A记录；两方就绪后，用窗口剩余时间通过Mac正常系统DNS和TLS请求核对状态及来源，记录诊断后才标记READY。DNS答复只用于决定何时开始系统探测，不将返回IP注入App或curl；任一阶段到期仍不可用记BLOCKED，不重建隧道或关闭TLS。该准备等待不重试App产品用例，探针READY只说明环境可用。Quick Tunnel是开发测试服务且不保证可用；不得以安装系统信任或跳过004解除阻断。证据只保存脱敏请求及产物摘要，不保存临时私钥或账号数据。详见SOP-009/010。

若只诊断签名和HTTPS环境，可手动触发`quality.yml`并将`environment_probe_only`设为`true`；两架构只执行`native_environment.py`，检查与工件名称为`environment-diagnostic`，报告中产品用例数为0且无合并、发布资格。不生成预览DMG。默认值`false`、PR和push始终走完整六例产品门禁；诊断READY后仍须以同一待合并候选取得两架构真实E2E原始证据。

## 2. 准备与数据生成

1. 核对 `release_id` 及对应版本计划，检查工作区和提交 SHA；需求、计划与 Changelog 等源文档先纳入候选提交，发布时工作区不得夹带未记录修改。
2. 从候选版本锁定应执行集合：本次目标功能/修复的全部场景，加上所有此前已交付功能的完整回归；每项都要有 fixture、期望值和 SOP 关联。无关的未来 `planned` 功能不阻塞本次版本；不能把目标功能改为 `planned` 或调整版本号逃避测试。
3. 使用独立测试环境，核对测试目录/数据库标记。确认没有连接生产服务、员工日志或真实账号。
4. 使用仓库数据生成程序，以固定种子和参考时间创建管理员、普通成员、停用用户、多设备和项目数据。将场景需要的账号导入真实测试服务，不能以绕过认证的方式模拟登录。
5. 保存生成器版本、参数、数据摘要和期望结果。所有临时密码使用测试环境专用值，不上传生产凭据。
6. 若数据缺少某个场景、来源日志未确认版本兼容，或重置程序无法安全定位目标，停止并记录 BLOCKED。

生成器必须支持从空环境构造数据和重复运行。场景执行前使用重置程序恢复指定初始状态；重置必须同时处理本地数据库、服务端测试数据库、读取游标、上传队列和相关测试凭据。任何无法复现的手工修改，都必须补入程序后才能作为正式测试数据。

## 3. 迭代 E2E

1. 构建候选 App 和服务端，记录各自产物摘要及版本。
2. 先执行必要的静态检查、单元和集成测试；任一步骤失败都停止验收。
3. 在支持的测试矩阵中创建隔离环境，启动真实服务端和数据库，检查健康状态。
4. 使用原生 UI 自动化启动 App，执行本次应执行集合对应的真实产品链路。完整产品链路包含首次登录、日志授权、采集、同步及统计；早期功能版本只要求已交付与本次目标能力。
5. 执行集合中的全部 E2E，包括此前已交付功能和故障场景；本次目标功能还需验证其独立预期值。脚本返回逐场景结果和非零失败退出码。
6. 对集合中涉及的 UI、导出、数据库核对权限和总量；采集/同步功能交付后持续验证重复扫描不重计、断网补传结果一致。
7. 自动收集原始结果、日志、环境信息和截图。应执行集合中任一场景缺结果、被跳过、只有人工点验或无法执行，记录 BLOCKED。
8. 通过门禁程序验证覆盖和证据绑定。只有完整 PASS 的候选允许进入下一阶段；不得手工修改报告。

规范化 fixture 的自检仅验证数据合同。日志采集测试必须将受支持版本的原始日志放入授权目录，由待测 App 真实读取；同步测试必须经过真实服务端认证与上传接口。

## 开发构建与最终安装包的边界

macOS实际运行的是.app；开发阶段可由Xcode构建并由XCUITest直接启动.app，不需要DMG。运行在远端Mac时，本机不会显示该窗口；记录实际Mac环境、构建路径、用例结果和原生截图。DMG是面向用户的分发容器，开发构建通过不能证明其安装流程通过。

正式发布必须从最终签名、公证DMG安装，再对安装后的.app执行完整原生回归，并绑定DMG与.app各自摘要。缺DMG或其安装测试时只能记录开发测试结果，发布保持BLOCKED。

## 4. 发布与安装升级

1. 固定 `release_id`、候选提交、版本、同标识的 Changelog 标题、App/服务端产物摘要及 fixture 摘要。
2. 完成签名、公证、更新包签名，保存校验结果。产品 E2E 与安装升级必须针对此候选产物建立证据链。
3. 在所有已声明支持的 Mac 系统/架构组合执行全新安装，以及本次应执行集合的全部原生产品 E2E。
4. 自 0.2.0 起安装上一公开稳定版并用程序生成旧版本数据；从 App UI 自动执行真实更新，验证版本、数据迁移、配置和授权保留。更多受支持直升路径逐一验证。最小更新器已列入 0.1.0 的交付基础。
5. 自动验证下载中断、签名异常、迁移失败及备份恢复；UI 自动化处理操作系统弹窗并断言授权、安装和更新结果。尚无法自动验证的必需路径保持 BLOCKED。
6. 生产发布使用与本版目标数据库同 schema 的隔离副本执行完整业务 E2E，以及已支持迁移/备份恢复路径；真实生产库只做非破坏性的就绪与备份检查。v0.1.0 目标为 SQLite，Codex 的测试 DB 与用户生产 DB 分开。后续迁移 MySQL 时再验证该引擎和 SQLite→MySQL 路径。
7. 检查全部证据与候选一致，确认远端必需检查和受保护发布任务已配置。
8. 在候选提交验证之后，由程序在源码版本控制之外生成 passport，绑定实际执行和产物来源；通过门禁后，发布任务才以同一 `release_id` 创建 Git 发布并分发已验证的安装包。保留 tag、passport、测试报告和更新清单的关联。任何阶段失败不得生成产品 PASS 或更新正式清单。

首个没有上一稳定版的发布，记录历史基线不存在，并验证候选干净安装及候选→受控高版本签名测试包的 App 内更新。测试包只进入隔离源，登记来源、版本和摘要；不能冒充上一公开稳定版。首版已有数据库迁移需求时仍执行迁移测试。开发阶段可用开发签名包，最终发布必须重新验证最终签名、公证包。

release-candidate.yml 在正式 Tag 之前按完整候选 SHA 执行上述门禁；只有取得有效通行证，发布任务才创建 Tag。当前已接入开发原生执行器；最终产物/全发布矩阵、远端保护配置、通行证签发和分发尚未完成验证。

## 5. 失败、复现与清理

- 先保存现场：失败场景、首个错误、完整日志、测试数据摘要、环境和构建信息。
- 用相同种子、时间和初始状态复现。基础设施故障记 BLOCKED；产品断言失败记 FAIL。
- 新缺陷使用[修复模板](../templates/bugfix.md)，先保存未修复版本的回归失败，再进行修复。
- 重试不覆盖第一次失败。不稳定场景不得通过跳过、隔离或增加重试次数放行；修复原因后重新运行完整 E2E。
- 归档证据后，调用清理/重置程序删除专用测试数据、撤销临时凭据。清理失败单独记录，禁止改用无边界删除命令。
- 报告中分别写明“实际执行的检查”和“产品 E2E 状态”；未执行不得写为通过。

## 6. 单次执行记录

每次运行至少记录以下内容，由受信执行程序生成。Codex 读取结果进行修复，不能手写报告将状态改为通过：

| 字段 | 内容 |
| --- | --- |
| 标识 | release_id、独立 run_id、对应版本计划路径 |
| 候选 | 提交 SHA、版本、App 与服务端产物摘要 |
| 清单 | 需求/场景清单摘要、fixture 摘要、生成器版本、种子和参考时间 |
| 环境 | macOS 构建号、架构、数据库版本、执行器版本、测试环境标识 |
| 结果 | 起止时间、退出码、逐场景结果、支持矩阵覆盖 |
| 证据 | 原始结果包、日志、截图、自动安装升级及授权交互报告、passport 路径 |
| 判定 | PASS / FAIL / BLOCKED、原因、缺陷链接、清理状态 |

机器报告的确切格式由门禁实现固定并版本化。报告存在或结构合法不代表测试实际执行；必须核对受信执行任务的原始产物及对应候选。
