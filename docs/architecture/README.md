# 架构与实现边界

状态：TM-001 的 Electron 客户端与本机精细TC执行器已建立；首轮精细全量BLOCKED，新版全量正在执行，最终DMG尚未通过门禁。旧 SwiftUI/XCUITest 的 [CI 36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502) 仅是历史实现证据。当前事实见[状态页](../status.md)，本轮详细合同见[Electron 本机设计](01-electron-local.md)。

## 组成与数据流

- `apps/desktop/`：Electron 主进程、受限 preload、React/TypeScript 界面、历史六组场景及按TC编号固定的Playwright精细用例。主进程持有认证 token 和 API Authorization；renderer 只取得必要的业务状态与错误码，不能直接读取任意文件、token 或发任意 HTTP 请求。主进程检查 IPC 来源、参数和窗口归属，启用 contextIsolation 与 sandbox。
- `server/`：保留真实 FastAPI 认证、角色权限、账号管理、审计及 SQLAlchemy/Alembic；用量接口和统计按后续功能交付。
- `scripts/`：文档追踪、服务/SQLite 初始化，以及已建立的本机构建、安装 E2E、独立门禁和本地发行程序。开发包已运行六个历史场景组，升级 004 失败；程序存在不代表最终候选或发布门禁通过，实际结果见[状态页](../status.md)。
- `apps/macos/`：旧 SwiftUI/Sparkle 与 XCUITest 源码供迁移核对，不是 Electron 候选的验收入口。

长期数据流是授权日志目录 → 来源适配器 → 标准化/去重 → 客户端 SQLite/待同步队列 → 真实服务 API → 团队统计。首版仅 TM-001 账号链路交付；采集、统计和客户端 SQLite 属于后续功能，不能因架构说明声称已实现。服务端本版用 SQLite：`database/test/test.db` 专供回归，用户 `database/production/production.db` 首建仅预置 admin/123456 并强制改密，后续启动不得覆盖。MySQL 另版设计和验证，客户端不直接连接服务端数据库。

## 地址、账号与工作目录

首次登录页的内置 API 默认值为 `http://127.0.0.1:49176`，更新清单默认值为 `http://127.0.0.1:49177/version.json`。两者只指运行 App 的电脑。配置 UI 区分内置默认与手动覆盖，跨启动保存覆盖，恢复默认删除覆盖。仅精确回环地址可用 HTTP，其他主机必须 HTTPS；拒绝 userinfo、query、fragment、空主机和非法端口。切换 API 时不得将旧 origin 的 token 发给新服务。

本机49176已有用户生产服务且旧 `/Applications/TokenMeter.app` 正在运行。自动回归只在无凭据首启从真实 UI 核对默认值，登录前经 UI 改至本例动态独占回环 API；第006例用两个动态独立服务。更新源同理可由 UI 改至本例动态端口。不得向用户生产服务登录/写入、终止旧 App、覆盖其目录或复用未知端口。

登录默认开启设备自动登录，关闭时仅保留内存会话。服务端 token 随机、可撤销、固定期限且不滑动；客户端只存 token、不存密码，并按规范化 origin 隔离。目录0700、文件0600、当前 UID、拒绝 symlink/硬链接与非原子替换。启动必须经真实 `/v1/me` 验证身份；退出先清本地，撤销失败保留可见重试状态。默认用户数据位于当前用户 Application Support/TokenMeter。正式 App 的通用 `--user-data-dir` 工作目录在 `ready` 与任何业务网络/存储前验证并由主进程设置 userData/sessionData；同级0600 `TokenMeter.runtime.json` 将本次工作目录绑定到归属安装路径，使原生更新器自主重启后继续使用相同 profile，验证失败不能回退到用户默认目录。测试只操作自己创建的安装与 profile。

## 更新、发布与验证

0.1.0 提供最小真实更新器：固定 Ed25519 公钥校验更新 zip，预验证元数据中的版本/build、字节数、SHA256、每跳下载 URL 及签名 App Info 一致性；只有完整通过才交给 macOS 原生 Squirrel 更新器。候选0.1.0/build100从同机隔离源升级到受控0.1.1/build101，由 App 自行安装、退出和重启，恢复同一 profile/配置并经 `/v1/me` 自动登录。非回环 HTTP 下载或重定向在外连前拒绝，坏签名包不交原生更新器。自签内部包须实际验证代码签名、Gatekeeper 和升级；公开分发条件另立版本，不把本轮内部测试外推。

默认只在用户本机 macOS15 Intel 运行最终 DMG 全六例，记录候选 SHA、原包/安装包摘要、真实 FastAPI/隔离 SQLite、原始 Playwright JSON/断言/截图/trace、服务审计和精确清理。完整 Xcode 不是 Electron 方案前提。API/IPC mock、开发服务器页面、构建成功或历史 Swift PASS 均不能替代安装后的真实产品 E2E。其他架构/系统未验证；仅用户明确要求多环境时启用 Actions。最终 DMG、更新包、通行证及原始报告按版本保存在本地，不上传 GitHub Release；Git 只追踪源码、文档与版本索引。

## 后续功能必须守住的边界

来源适配器只读已授权日志，只上传用量及必要去重元数据；不得上传对话、代码、密钥或完整本机路径。累计差值、重复事件、缓存/推理子项、移动日志、分支和子代理分别验收。未知或不可可靠去重的数据明确诊断，不用零掩盖。离线队列持久化与确认删除应有事务保证，服务器从认证上下文确定成员归属。测试 expected 独立于生产统计实现；规范化 fixture 不证明供应商原始日志兼容。数据迁移需备份、事务、聚合和恢复验证，发布包必须绑定被测候选与原始证据。
