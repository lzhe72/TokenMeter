# SOP-009 环境准备

**修订：** 14　**状态：** baselined　**适用：** all

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
6. 开发与业务 E2E 可使用隔离开发签名包。TM-001 同设备自动登录采用受保护本地凭据文件，升级后仍须用真实 `/v1/me` 核对，而不是通过输入系统 Keychain 密码或预授权二进制摘要取绿。隔离 CI 的临时自签名只用于开发迭代的 Sparkle 包签名与安装验证，不代表内部 DMG 包级门禁通过；公开 Developer ID、公证及分发凭据仍按 SOP-017/018 单独检查，其缺失不阻止开发。

7. TM-001 更新 fixture 只允许 `GITHUB_ACTIONS=true`、`RUNNER_ENVIRONMENT=github-hosted`、`RUNNER_OS=macOS` 且具有 `RUNNER_TEMP` 的专用临时 runner。工作流安装固定版本并按仓库记录的 SHA256 校验 `cloudflared`，再运行 `python3 scripts/native_environment.py` 作有界探针；不能用未校验的下载或仅设置环境变量放行。探针仅在隔离 CI 目录创建临时自签代码签名身份和专用 Keychain，核对其能实际签名/验证；014 继续证明候选与高版本包使用同一隔离签名身份，并通过真正升级后读取专用凭据目录、调用 `/v1/me` 验证会话。不得更改 App 会话旧 Keychain 条目的 ACL、预授权新旧二进制摘要或由自动化输入系统密码取绿。临时 CA 只用于 `cloudflared --url https://localhost:<端口> --origin-ca-pool <本次ca.pem>` 验证回环 TLS 源。Quick Tunnel 提供面向 App 的公开可信 HTTPS `trycloudflare.com` 地址。拿到本次随机域名后，在同一最长 180 秒的准备窗口内，先分别通过 Cloudflare 和 Google 的 HTTPS DNS 查询检查其公开 A 记录；任何一方仍为 NXDOMAIN、无 A 记录或查询失败，均不得提前调用系统解析器探测该域名。两方记录就绪后，保持同一隧道和域名，用窗口剩余时间以 `/usr/bin/curl` 正常系统 DNS 与 TLS 信任反复核对 HTTPS 状态和来源响应，并记录带时间的诊断。DNS 查询结果只作准备前提，不把返回 IP 写入 hosts、App 配置或 curl `--resolve`，也不能替代系统 TLS 健康检查。任一阶段到期仍不可用则 BLOCKED；不得重建隧道、替换域名、关闭 TLS 验证或将准备等待变成产品用例自动重试。只有系统 TLS 健康检查与来源核对均成功才标记 READY。首次系统健康请求若出现 `curl` 退出6，立即在本次专用 runner 对同一合成域名采集一次有界只读诊断：`/usr/sbin/scutil --dns` 仅保留 resolver 编号、nameserver、flags、reach 等配置摘要；与合成主机名无关的 search/domain 值替换为 `<unrelated>`；`/usr/bin/dscacheutil -q host -a name <合成域名>`；`/usr/bin/dig` 带 `+stats` 分别对默认 resolver、`@1.1.1.1` 和 `@8.8.8.8` 查询 A/AAAA，保存响应来源与耗时；`/usr/bin/curl --disable --version`；以及 `/usr/bin/curl --disable --ipv4` 对同一公开 HTTPS `/healthz` 进行仅供诊断的系统 TLS 请求。另只读读取 `/etc/resolv.conf` 的 nameserver/options 行，过滤 search/domain。最多10条子命令各限5秒，整组最多60秒，全部计入原共享180秒准备窗口；输出过滤、截断后写入 `update-dns-diagnostic.json`，包含命令、退出码、耗时及必要DNS信息，不记录真实搜索域或敏感配置。诊断失败保留原 `curl` 退出6，不改变 BLOCKED 判定；`dig` 答复或 `curl --ipv4` 成功也不能替代App的正常系统DNS/TLS健康检查。不得修改系统 DNS、hosts、信任配置或重试产品用例。不得向 System.keychain 写证书、改系统/管理员域信任、修改 `authorizationdb`、关闭任一段 TLS 校验或使用 HTTP App 更新源。隧道只服务合成更新内容和持随机 Bearer 的测试控制请求；未授权控制请求必须拒绝，私钥、账号与控制口令不进入公开响应和证据。每次必须停止隧道/HTTPS 服务、恢复 Keychain 列表并删除本次专用 Keychain；准备或清理失败均阻断，保留首个错误与清理错误。报告的 `cleanup_completed` 只表示实际清理动作成功，可与主操作 BLOCKED 同时为 true；清理结果不得将主操作改成 READY。Quick Tunnel 无可用性保证，无法取得或验证地址时记录 BLOCKED。014 在第004例前调用该探针；001–003及005–006可按自身前提执行和归档，004缺项仍使完整六例门禁 BLOCKED。原生 runner 对该独立探针设置有界 1800 秒的父进程超时，覆盖签名、域名取得、共享 180 秒 DNS/TLS 准备及必要清理；它不延长域名准备窗口，也不重试产品步骤。探针 READY 仅证明环境前提，不是产品 PASS。[Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) 和 [origin CA pool](https://developers.cloudflare.com/tunnel/troubleshooting/) 为此隔离测试链路的依据。

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
