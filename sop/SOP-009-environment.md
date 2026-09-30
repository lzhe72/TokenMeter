# SOP-009 环境准备

**修订：** 8　**状态：** baselined　**适用：** all

## 目的与范围

准备隔离的开发测试环境，并按已基线设计建立首个可运行工程骨架，使后续业务数据、真实测试和功能实现能按依赖开展。

## 触发条件

首次工程建立、工具链变化、新建 Mac runner，或运行因环境缺失中断。

## 前置条件

SOP-008 文档基线完整；SOP-004/005 已定义骨架范围、接口、任务与独立验证条件；测试计划列出所需 macOS、架构、Xcode、GUI 和数据库。建立骨架不要求先有业务红测或产品 PASS。

## 输入

本轮设计与开发计划、依赖配置、平台矩阵、测试目录/数据库约定、骨架的启动及连通性检查方案。

## 执行步骤

1. 只读检查系统/架构与工具链，先运行 `xcode-select -p`；只有已选择完整 Xcode 时再运行 `xcodebuild -version`。未配置时记录缺项，避免触发系统安装提示；区分仅有 Command Line Tools。
2. 按已基线的骨架任务建立真实 App 工程、服务启动入口、数据库初始化/迁移入口、原生测试 target 及 runner；已有骨架时核对兼容性。manifest 程序绑定尚为 planned 时按任务逐项补齐，独立骨架源码完成不自动将业务程序标为 ready。允许业务尚未实现并明确展示未完成状态，禁止创建绕过认证或返回伪造业务结果的测试入口。
3. 按已提交依赖配置准备隔离运行时；Python 依赖使用 `--only-binary=:all:`，无适配 wheel 时停止并核对依赖及平台，避免安装过程隐式调用缺失的系统编译工具。为本次运行划定专用目录、数据库、测试 Keychain 项和服务端口。核对所有权，仅访问测试目标，不打印凭据或静默改变开发者系统配置。
4. 检查已登录桌面会话、UI 自动化授权和实际系统；用真实启动、服务健康、数据库初始化及最小原生测试探针验证骨架，保留构建/连通性与运行证据。探针通过仅证明骨架可用，不能替代任何产品验收场景。
5. 分别记录“源码/配置准备”和“真实运行验证”。缺 Xcode、GUI 或执行器时，对依赖它们的构建、运行与验收记录 BLOCKED；仍可完成计划中具有独立验证条件的源码、数据程序、测试编写与文档任务，不得声称骨架运行通过。
6. 开发和业务 E2E 可使用隔离开发签名包。生产签名、公证和分发凭据在 SOP-017/018 检查，部署权限在 SOP-020 检查；其缺失不阻止开始工程准备或业务编码，最终签名包仍须单独验证。

7. TM-001 更新 fixture 只允许 `GITHUB_ACTIONS=true`、`RUNNER_ENVIRONMENT=github-hosted`、`RUNNER_OS=macOS` 且具有 `RUNNER_TEMP` 的专用临时 runner。工作流安装固定版本并按仓库记录的 SHA256 校验 `cloudflared`，再运行 `python3 scripts/native_environment.py` 作有界探针；不能用未校验的下载或仅设置环境变量放行。探针在隔离目录创建临时代码签名身份和专用 Keychain，检查该身份可以对代码实际签名和验证；014 仍须证明候选包及高版本包使用同一身份。临时 CA 只用于 `cloudflared --url https://localhost:<端口> --origin-ca-pool <本次ca.pem>` 验证回环 TLS 源。Quick Tunnel 提供面向 App 的公开可信 HTTPS `trycloudflare.com` 地址，探针须经系统 TLS 客户端实际请求该地址并核对来源响应。不得向 System.keychain 写证书、改系统/管理员域信任、修改 `authorizationdb`、关闭任一段 TLS 校验或使用 HTTP App 更新源。隧道只服务合成更新内容和持随机 Bearer 的测试控制请求；未授权控制请求必须拒绝，私钥、账号与控制口令不进入公开响应和证据。每次必须停止隧道/HTTPS 服务、恢复 Keychain 列表并删除本次专用 Keychain；准备或清理失败均阻断，保留首个错误与清理错误。Quick Tunnel 无可用性保证，无法取得或验证地址时记录 BLOCKED。014 在第004例前调用该探针；001–003及005可按自身前提执行和归档，004缺项仍使完整五例门禁 BLOCKED。探针 READY 仅证明环境前提，不是产品 PASS。[Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) 和 [origin CA pool](https://developers.cloudflare.com/tunnel/troubleshooting/) 为此隔离测试链路的依据。

8. 用户明确授权本机作为测试机时，可以在本机执行014的App构建及账号原生场景；记录此授权和环境事实，不把本机伪装为GitHub runner。TM-001采用Xcode16.4，先确认完整Xcode.app已安装并首次启动完成组件与许可。当前只有Command Line Tools时保持BLOCKED，不能把/usr/bin/xcodebuild占位入口当作完整工具链。Apple账号登录、许可和管理员初始授权由用户通过系统正常界面完成，密码不进入聊天或脚本日志。本机004尚无经过验证的独立运行程序和证据；即使隔离CI方案不改系统信任，也不能把CI专用fixture直接套用本机。

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
