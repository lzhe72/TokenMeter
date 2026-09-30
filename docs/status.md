# 当前状态

当前版本 `v0.1.0-20260929T074814Z` 的 TM-001（账号、登录与最小更新器）仍在开发验收中，**未发布**。接手先读 [SOP 总索引](../sop/README.md) 和对应独立文件；历史失败与原始证据索引见[本轮执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)。

## 当前交接（2026-09-30）

- 本轮仍须在同一候选上执行 E2E-TM001-001、002、003、004、005、006 六例。用户确定团队内部应用，无需把付费 Apple 开发者账号当作开发迭代前提。新版设计把登录页“在此设备上自动登录”设为默认开启，用服务器随机、可撤销、固定30天到期的 token；开启时存于当前用户受保护文件，关闭后仅内存会话。启动必须经真实 `/v1/me` 确认，离线、过期和撤销不授予已登录身份。UITESTING 每例专用临时凭据目录由 runner 提供给候选与高版本包，生产版绝不读取测试路径；旧预览版 Keychain 不迁移，用户首次需重新登录。需求、设计、测试计划及相应源码/用例已同步，新增基础检查和六例原生回归仍须按实际结果判定。
- 本机 Intel Mac 只有 Command Line Tools；原生 XCUITest 由 [quality.yml](../.github/workflows/quality.yml) 在 GitHub 托管 macOS 15 Apple Silicon 与 Intel 上运行。CI 的 `127.0.0.1` 指各自 runner 的隔离 FastAPI/SQLite，不是用户本机生产库。命令行 Swift 凭据存储边界测试可在本机建立并执行，但不能替代原生产品 E2E。
- 历史[完整 PR 回归 run36663136535](https://github.com/lzhe72/TokenMeter/actions/runs/36663136535) 在两平台实际执行六例，001/002/003/005/006 各 PASS、004 FAIL，完整迭代门禁 FAIL。视频复核显示更新已安装并重启至构建号101，但旧 Keychain 方案弹出系统凭据访问提示，阻断原会话恢复；不能把该失败记为“未升级”或新方案 PASS。旧[独立环境诊断 run36663159461](https://github.com/lzhe72/TokenMeter/actions/runs/36663159461) 的 Intel DNS BLOCKED 是另一运行，零产品用例，不覆盖完整 PR 的产品 FAIL。新文件凭据方案需新候选两架构完整回归。
- 曾为 Apple 团队签名探索创建的空 `native-e2e-signing` GitHub environment 已撤回；其中从未设置证书 secrets。当前迭代使用专用 CI 的隔离临时自签身份，仅验证开发包的 Sparkle 签名与安装。DNS 公布、系统 TLS 与一次性只读诊断仍按 SOP-009/014 执行，不关闭 TLS 或跳过004。
- 严格测试凭据目录写入 UITESTING App 后，旧 CI 从该 App 自动包装的预览 DMG 离开 runner 便不能正常登录；打包器现拒绝带 `TMTestCredentialsDirectory` 的包，工作流已移除从 UITESTING App 制作/上传预览 DMG 的步骤，仅保留测试 App 压缩件供诊断。`/Applications/TokenMeter.app` 若仍是旧预览包，不代表新候选。**当前没有新的可供用户安装的内部 DMG。**
- `database/test/test.db` 只供 Codex 回归；`database/production/production.db` 为用户生产库，首建预置 `admin / 123456` 且强制改密。[数据库说明](../database/README.md)给出 SQL 造数与安全检查。新同设备自动登录要求原生 UI、服务端固定30天和凭据文件边界测试同步实现；现有程序路径虽登记为 `ready`，仅表示入口存在，不表示更新后的断言或产品通过。
- 本轮新设计的 `check_docs --mode structure`、`--mode baseline` 和 `quality_gate.py check` 已实际通过；最后一次 baseline 核对69份文档/434条链接，追踪检查核对12项功能/37个场景/6项绑定，均 `release_eligible=false`。SOP-013 的本机 Swift 凭据组件检查13/13通过，服务端45项与更新包工具12项通过；原始记录见[本轮执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)。这些检查不构成新方案产品 E2E；仍须同一新候选两平台六例完整回归。
- 正式分发按 `distribution_profile=internal/public` 走同一 SOP-017/018 步骤、不同证据前提。内部最终 DMG 构建、安装升级全矩阵与专用自动门禁尚未实现，故内部发行 BLOCKED；公开发行另缺 Developer ID、公证与受保护发布配置，也 BLOCKED。源码 PR #2 保持草稿，远端 master 尚未合并 v0.1.0；无正式 Tag、Release 或通行证。

## 下一步

1. 服务器固定30天会话、Swift凭据存储、登录开关、隔离 runner路径与原生断言已写入候选，基础回归已执行。保留历史 BUG-TM001-UPGRADE-001 与DNS证据；接下来让提交后的同一候选在两平台完整执行六例。任何缺项或失败均不得合并。
2. 完整迭代和适用检查 PASS 后按 SOP-019 合并源码 PR。内部版本的正式 DMG、包级原生安装/升级矩阵与机器门禁须另按 SOP-017/018 实现和验证，取得绑定 profile 的通行证后才能创建 Tag/Release 并分发；公开分支仍另按 Developer ID/公证要求判定。
