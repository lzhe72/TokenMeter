# SOP-009 环境准备

**修订：** 16　**状态：** baselined　**适用：** all

## 目的与范围

准备隔离的开发测试环境，并按已基线设计建立首个可运行工程骨架，使后续业务数据、真实测试和功能实现能按依赖开展。

## 触发条件

首次工程建立、工具链变化、新建 Mac runner，或运行因环境缺失中断。

## 前置条件

SOP-008 文档基线完整；SOP-004/005 已定义骨架范围、接口、任务与独立验证条件；测试计划列出所需 macOS、架构、Xcode、GUI 和数据库。建立骨架不要求先有业务红测或产品 PASS。

## 输入

本轮设计与开发计划、依赖配置、平台矩阵、测试目录/数据库约定、骨架的启动及连通性检查方案。

## 执行步骤

1. 只读检查系统/架构与工具链，先运行 `xcode-select -p`；完整 Xcode 路线再运行 `xcodebuild -version`，本机仅有 Command Line Tools 时单独记录其能否构建真实 App；本机可选 AX 驱动的权限与实现状态另列，不作为现有远端 XCUITest 门禁前提。未配置时记录缺项，避免触发系统安装提示。
2. 按已基线的骨架任务建立真实 App 工程、服务启动入口、数据库初始化/迁移入口、原生测试 target 及 runner；已有骨架时核对兼容性。manifest 程序绑定尚为 planned 时按任务逐项补齐，独立骨架源码完成不自动将业务程序标为 ready。允许业务尚未实现并明确展示未完成状态，禁止创建绕过认证或返回伪造业务结果的测试入口。
3. 按已提交依赖配置准备隔离运行时；Python 依赖使用 `--only-binary=:all:`，无适配 wheel 时停止并核对依赖及平台，避免安装过程隐式调用缺失的系统编译工具。为本次运行划定专用目录、数据库、测试 Keychain 项和服务端口。核对所有权，仅访问测试目标，不打印凭据或静默改变开发者系统配置。
4. 检查已登录桌面会话、UI 自动化授权和实际系统；用真实启动、服务健康、数据库初始化及最小原生测试探针验证骨架，保留构建/连通性与运行证据。若另行开展本机 AX 自动化，以只读 `AXIsProcessTrusted` 核对权限；未授权的本机 AX 运行记 BLOCKED，由用户通过正常 macOS 系统界面授权，不能静默更改 TCC 数据库。此状态不覆盖远端两平台 XCUITest 结果。探针通过仅证明骨架可用，不能替代任何产品验收场景。
5. 分别记录“源码/配置准备”和“真实运行验证”。缺 Xcode、GUI 或执行器时，对依赖它们的构建、运行与验收记录 BLOCKED；仍可完成计划中具有独立验证条件的源码、数据程序、测试编写与文档任务，不得声称骨架运行通过。
6. 开发与业务 E2E 可使用隔离开发签名包。TM-001 同设备自动登录采用受保护本地凭据文件，升级后仍须用真实 `/v1/me` 核对，而不是通过输入系统 Keychain 密码或预授权二进制摘要取绿。隔离 CI 的临时自签名只用于开发迭代的 Sparkle 包签名与安装验证，不代表内部 DMG 包级门禁通过；公开 Developer ID、公证及分发凭据仍按 SOP-017/018 单独检查，其缺失不阻止开发。

7. TM-001 的更新源由运行被测 App 的 Mac 自己提供：正式内置默认值为 `http://127.0.0.1:49177/appcast.xml`，004测试同样须独占固定49177；API 默认端口 49176 与更新源 49177 彼此独立。`127.0.0.1` 在用户本机指用户此 Mac，在 GitHub runner 指该 runner，远端用例不得读取用户本机服务。更新源地址可在 App 设置中显式修改并跨重启保存；仅 HTTP 回环主机 `127.0.0.1`、`localhost`、`::1` 合法，非回环必须 HTTPS；拒绝 userinfo、query、fragment、空host、非法端口或畸形 URL，更新发现所选下载 URL 与重定向仍须满足同一安全边界。保持 Sparkle EdDSA 公钥固化、`SUVerifyUpdateBeforeExtraction`、真实包签名验证与无效包拒绝，不因回环 HTTP 取消签名。App Transport Security 只对回环主机设窄例外，不开启全局明文许可；具体 Sparkle 2.10.0 配置和重定向行为在工具负测及真实 App 试验中确认。

   现有迭代门禁在 `macos-15` 和 `macos-15-intel` GitHub 托管 Mac 各自用 Xcode/XCUITest 执行完整六例；004 在其同一台 runner 上启动隔离回环更新服务，并由该 runner 的真实 App 核对内置默认地址、拒绝坏签名、安装有效包和恢复自动登录；第006例通过设置页核对用户地址覆盖与恢复默认。默认 `127.0.0.1:49177` 必须指执行 App 的 Mac；本例先独占49177验证真实默认值；配置页对其他合规地址仅做保存、重启和恢复默认测试，不为第004例另建更新源，不能把 runner 的地址说成用户本机服务。若端口占用或无法证明归属则 BLOCKED，不连接已有服务。App、服务、SQLite、临时凭据及测试 EdDSA 私钥均在本例隔离；公钥固化在 App，私钥不进入 Git 或报告，测试 App 不得覆盖 `/Applications/TokenMeter.app` 或连接用户 `database/production/production.db`。准备、App 内检查/安装、请求核对均使用同一活跃回环源，最终精确清理，并记录端口、进程、候选与包摘要。独立环境诊断只证明一次准备，不授予产品 PASS。

   用户本机可按同样的回环配置运行 App、API 与更新服务作为体验/诊断环境，先区分已安装旧 App 与新候选；仅有 Command Line Tools 且尚无本机原生 AX 执行器/权限时，本机 E2E 另记 BLOCKED，不把该缺口转嫁到已有远端 XCUITest 门禁。未来若补 CLT 构建与 AX 自动化，先隔离安装位置、数据库、凭据与更新源，使用真实 App 完成签名拒绝和升级重启断言，且不替换用户 `/Applications` 旧 App。

8. 本机已获授权用于开发、服务和预览安装；当前只有 Command Line Tools，无须在本机安装 Xcode 才能推进源码或远端原生验收。TM-001 的原生 E2E 使用 `.github/workflows/quality.yml` 中 `macos-15` 与 `macos-15-intel` 两台 GitHub 托管 Mac，选择 Xcode 16.4，并分别在 runner 自己的已登录桌面、隔离 SQLite 与回环服务上执行；`127.0.0.1` 在 CI 指向该 runner，绝不指向用户本机生产库。远端每个平台须留下原始 `xcresult`、候选 SHA、fixture 与清理证据。`workflow_dispatch` 可显式设置 `environment_probe_only=true`，此时两平台仅运行 `scripts/native_environment.py`，输出单独命名的 `environment-diagnostic` 检查/工件，零产品用例，不制作预览包，也不具有 PR 合并或正式发布资格；默认值 `false`、PR 和 push 仍执行完整产品门禁。只有将来确需本机原生重跑时才检查完整 Xcode.app、首次启动组件及许可；只有 Command Line Tools 时本机运行记 BLOCKED，不影响远端有效结果。Apple 登录、许可和管理员初始授权只能在对应机器的正常系统界面完成，不把密码写入脚本或聊天。CI 的第004例专用 fixture 不套用本机。第006例在执行所在 Mac 的端口 49176 启动临时测试服务；先确认该端口未被其他服务占用，不得复用或重置用户生产库。端口占用且无安全隔离窗口时，该平台第006例记 BLOCKED。

9. v0.1.0 首次缺库时，用本轮 Python 环境执行 `python scripts/bootstrap_sqlite.py init-test --run-id <唯一测试ID>` 和 `python scripts/bootstrap_sqlite.py init-production` 建立 `database/test/test.db` 与 `database/production/production.db`；实际命令中的 `python` 指向步骤3的隔离解释器。两份初始化各仅允许空目标，已有生产库不得再执行初始化，生产首建 `admin / 123456` 后强制改密，服务启动不再次造数。执行 `python scripts/bootstrap_sqlite.py verify` 检查两库的 schema、环境标记及账号隔离，缺任一库必须失败；本机预览服务使用 `python scripts/bootstrap_sqlite.py serve-production --host 127.0.0.1 --port <本机端口>`，入口仅接受回环地址且只绑定生产库，不提供公网 HTTP。`database/README.md` 给出可执行命令、SQL 位置与本机路径。原生 E2E 不接触用户生产库，逐例仍用临时测试数据库；第005例在独立临时根下调用同一生产初始化程序。

## 输出

骨架源码与实际入口、环境清单、隔离资源、准备及运行的分别状态、实际检查证据或具体恢复条件。

## 成功与失败判据

骨架实际构建、启动、数据库初始化和原生执行探针通过后，才满足后续真实业务红测的运行前提。仅源码或 Python 工具验证通过不能宣称 App 可运行；缺条件不阻止具有独立验证条件的任务，产品验收及发布仍 BLOCKED。

## 异常恢复

保留检测结果与失败现场，修复明确缺项后重检；不删除真实日志/账号、不绕过权限，不将编译或环境失败记作业务行为失败。

## 证据位置

版本记录保存骨架任务、实际命令/退出码、系统/工具链和未就绪项；机器报告记录环境与隔离资源。未运行的项目保留未验证状态。

## 下一步

按 [SOP-010](SOP-010-test-data.md)准备数据，骨架可运行后由 [SOP-011](SOP-011-test-implementation.md)取得真实业务失败基线，再进入 [SOP-012](SOP-012-development.md)。依赖缺失按任务范围阻断并通过 [SOP-022](SOP-022-archive-handoff.md)交接。
