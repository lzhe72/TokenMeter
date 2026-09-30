# v0.1.0-20260929T074814Z — 技术设计与开发计划

## 技术设计（SOP-004）

依据：[需求](01-requirements.md)、[拆解](02-breakdown.md)、[全局架构](../../docs/architecture/README.md)。

### 服务端与数据

Python 3.10+ / FastAPI、SQLAlchemy 2.0、Alembic；v0.1.0 服务端测试与生产都验证 SQLite，文件和账号相互隔离，ORM 保持后续迁移空间但本版不声称 MySQL 兼容通过。users 保存 UUID、username、Argon2 hash、role、is_active、must_change_password、credential_version；sessions 保存 token SHA256、user_id、credential_version、UTC expires_at；audit 保存动作、操作者/目标、时间及非敏感结果；持久化登录节流桶按账号和来源区分，5次失败/5分钟。秘密不进入 audit 或返回的验证错误。

256-bit opaque bearer，24h 有效期；每次请求查用户活动状态/凭据版本/会话有效期。换密原子递增版本并撤销全部旧会话，返回新 token；reset/disable 同样撤销。SQLite 启用外键、写入事务，管理员保护在事务内检查。数据库初始 schema 由 Alembic 建立，可重复执行且不覆盖账号。

### 接口合同

用户名按小写规范化；CLI 约定为 `python -m server.tokenmeter_server.cli migrate --database-url <隔离SQLite>` 和 `provision --database-url <隔离SQLite> --accounts <显式JSON>`。服务由 `TOKENMETER_DATABASE_URL` 配置，使用 uvicorn 启动 main:app；启动服务不重建数据库或重置凭据。生产库通过独立的首次初始化步骤预置 `admin / 123456` 并要求首次改密，测试库由回归造数程序初始化；两者都不绕过正常认证 API。账号 fixture 定义位于 tests/server/fixtures.py，native runner 可复用相同输入及独立 expected。上述入口在工程步骤创建后才执行。

统一错误：`{"error":{"code":"...","message":"..."}}`；422 不回显密码 input。user 为 `{id,username,role,is_active,must_change_password}`。

| API | 输入与返回 |
| --- | --- |
| GET /v1/health | 存活/数据库就绪，不返回秘密 |
| POST /v1/auth/login | username/password → access_token/token_type/expires_at/user |
| GET /v1/me | Bearer → user |
| POST /v1/auth/change-password | current_password/new_password → 新 access_token/token_type/expires_at/user |
| POST /v1/auth/logout | 撤销当前会话 → 204 |
| GET /v1/admin/users | admin → users 列表 |
| POST /v1/admin/users/{id}/disable | 停用/撤销会话 → user |
| POST /v1/admin/users/{id}/enable | 启用但不恢复旧会话 → user |
| POST /v1/admin/users/{id}/reset-password | temporary_password → user（不返回口令） |
| GET /v1/admin/audit | admin → 脱敏事件列表 |

401 invalid_credentials/invalid_session、403 account_disabled/forbidden/password_change_required、409 admin_protected/password_unchanged、429 rate_limited。CLI provision 使用显式账号文件，生产首建管理员由独立数据库初始化程序写入；真实 HTTP 网络 smoke 补充 TestClient 集成回归。

### macOS 与更新

SwiftUI、macOS14 deployment target、Swift5、提交 Xcode project/shared scheme，固定 Sparkle2.10.0。API 端点可设置，生产仅 HTTPS；开发 loopback 仅测试配置允许。Keychain service 按服务源和隔离运行区分；token 不用 UserDefaults。启动经 /v1/me 确认，不从本地注入登录成功。

UI 标识：auth.server/username/password/login/error、password.current/new/confirm/submit、session.username/role/logout/refresh、admin.accounts/disable/enable/reset/audit、updates.check/status。更新使用 SPUStandardUpdaterController、HTTPS SUFeedURL、SUPublicEDKey、SUVerifyUpdateBeforeExtraction。生产配置缺失显示尚未配置，不能伪装已发现版本。测试包同 Bundle ID/源码、递增 build version，隔离更新源有真实有效和无效 EdDSA 包。测试 CA 仅供隔离 CI 的 `cloudflared` 验证本机 TLS origin；App 使用公开可信 HTTPS 域名，不安装测试 CA、不绕过 TLS。

官方依据：[FastAPI 安全](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)、[SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)、[Sparkle2.10.0](https://github.com/sparkle-project/Sparkle/blob/2.10.0/Package.swift)、[GitHub macOS runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。具体依赖解析后锁定到文件，失败不能静默升级。

### 开发升级包的签名连续性

原生用例004要求升级后恢复Keychain会话，因此候选和受控高版本包必须使用同一临时代码签名身份。仅在隔离的GitHub托管Mac CI生成短期测试证书与专用临时Keychain，两个包显式指定同一identity和keychain；结束时恢复原Keychain列表，删除专用Keychain和私钥，不更改System.keychain、管理员信任或`authorizationdb`。旧方案在托管Mac撤销最后一项admin信任时超时，保留失败证据，不再尝试系统信任写入。签名能否被`codesign`及升级后的Keychain访问接受，必须由新探针和实际第004例分别证明；设计本身不等于PASS。

HTTPS更新源由本机临时CA签发的回环TLS服务和固定版本、SHA256校验的`cloudflared` Quick Tunnel组成。`cloudflared --url https://localhost:<端口> --origin-ca-pool <本次ca.pem>` 验证origin证书，App使用临时的`https://<随机子域>.trycloudflare.com`并由系统正常验证边缘证书；两个TLS端点都不得关闭证书检查。无效/有效appcast和签名包仅为合成测试内容，控制切换使用原生用例持有的随机Bearer通过同一HTTPS源，未授权请求拒绝；私钥、账号与数据库不经隧道公开。`native_environment.py`在第004例前探测签名、公开HTTPS连通和完整清理；Quick Tunnel无法使用或任何清理失败都使该例BLOCKED。001–003与005仍实际执行并留证，但不能缩小五例门禁；新候选必须完整重跑。该测试签名和临时源不满足Developer ID、公证或正式发布条件。[Apple签名证书](https://developer.apple.com/documentation/technotes/tn3161-inside-code-signing-certificates)、[Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)、[Cloudflare origin CA池](https://developers.cloudflare.com/tunnel/troubleshooting/)是设计依据。

依据：[Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)、[Code Signing Requirement Language](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/RequirementLang/RequirementLang.html)。不同ad-hoc包的摘要变化，不能作为跨版本Keychain身份连续性的设计依据。

## 实施顺序（SOP-005）

1. 完成 001–007 文档并保存 structure 与 008 baseline 证据；此阶段程序绑定为planned，010/011真实入口完成后再改ready。
2. 009 创建隔离 venv、服务/数据库和 Mac/native target 骨架。读取工具链状态，本机未配置 Xcode 不触发安装；远端验证 native 探针。
3. 010/011 创建账号/更新数据、独立 oracle 与真实 API/native 测试，在实现前保存确定性失败；无法运行的 native 红测写 BLOCKED。可先推进有实际单元/接口验证的子任务。
4. 012 实现服务/界面/更新；数据与测试绑定完整后设 ready/in_progress，产品通过以前不设 implemented。
5. 013 基础回归，014 完整目标五例 native E2E；失败按015修复并完整重跑。017/018发布前再验最终包与全支持矩阵。
6. 保存实际证据与流程障碍，创建 PR；适用必需检查通过才合并。不能因用户已授权自动合并而跳过产品测试。

## 并行边界与恢复入口

- backend agent：`server/`、`tests/server/`，先测试后业务。CLI与 fixtures 的调用合同向 root/native 交接。
- macOS agent：`apps/macos/`，项目、App 与 XCUITest。只使用统一 API 合同。
- runner agent：root 确认后负责 `scripts/e2e.py`、原生执行/证据校验与其测试；不得放宽发布。
- 原生五例各使用独立数据库、服务和 Keychain service，runner 逐例调用 `-only-testing` 并分别保存 xcresult；005 调用生产首建程序但仅指向 runner 临时根，不能让用例顺序承担数据初始化。
- root：版本文档、SOP、catalog、矩阵/数据清单、CI、集成与 PR。

候选代码、测试、文档和数据一同提交；测试后代码或依赖变化重新验证。完整命令在入口真实建立后补入，未建立时明确待实现，不写伪造成功记录。

服务启动使用 `python3 -m uvicorn server.tokenmeter_server.main:app --host 127.0.0.1 --port <隔离端口> --no-proxy-headers`，并显式设置 `TOKENMETER_DATABASE_URL`。当前限流按真实连接来源计数，不信任转发头；生产代理来源识别需另行设计验证。

## 本机测试环境接入

用户已明确授权本机作为测试机，覆盖本轮App构建和原生测试。实际环境为Intel/macOS15.7.4/已登录桌面，当前只有Command Line Tools。先安装与CI一致的完整Xcode16.4并完成首次启动组件、许可及UI自动化授权；Apple登录和系统管理员确认通过系统界面完成。001–003及005复用现有真实runner和隔离数据；004的新fixture限定专用GitHub Mac CI，本机运行路径尚未独立验证，不伪造GitHub环境变量或静默改本机配置。完整矩阵与正式发布要求继续保留。
