# v0.1.0-20260929T074814Z — 技术设计与开发计划

## 技术设计（SOP-004）

依据：[需求](01-requirements.md)、[拆解](02-breakdown.md)、[全局架构](../../docs/architecture/README.md)。

### 服务端与数据

Python 3.10+ / FastAPI、SQLAlchemy 2.0、Alembic；本轮实际验证 SQLite，保持 ORM 可迁移。生产 MySQL 未运行则不声称兼容通过。users 保存 UUID、username、Argon2 hash、role、is_active、must_change_password、credential_version；sessions 保存 token SHA256、user_id、credential_version、UTC expires_at；audit 保存动作、操作者/目标、时间及非敏感结果；持久化登录节流桶按账号和来源区分，5次失败/5分钟。秘密不进入 audit 或返回的验证错误。

256-bit opaque bearer，24h 有效期；每次请求查用户活动状态/凭据版本/会话有效期。换密原子递增版本并撤销全部旧会话，返回新 token；reset/disable 同样撤销。SQLite 启用外键、写入事务，管理员保护在事务内检查。数据库初始 schema 由 Alembic 建立，可重复执行且不覆盖账号。

### 接口合同

用户名按小写规范化；CLI 约定为 `python -m server.tokenmeter_server.cli migrate --database-url <隔离SQLite>` 和 `provision --database-url <隔离SQLite> --accounts <显式JSON>`，服务由 `TOKENMETER_DATABASE_URL` 配置，使用 uvicorn 启动 main:app，不在启动时创建默认管理员。账号 fixture 定义位于 tests/server/fixtures.py，native runner 可复用相同输入及独立 expected。上述入口在工程步骤创建后才执行。

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

401 invalid_credentials/invalid_session、403 account_disabled/forbidden/password_change_required、409 admin_protected/password_unchanged、429 rate_limited。CLI provision 使用显式账号文件，不提供生产默认管理员。真实 HTTP 网络 smoke 补充 TestClient 集成回归。

### macOS 与更新

SwiftUI、macOS14 deployment target、Swift5、提交 Xcode project/shared scheme，固定 Sparkle2.10.0。API 端点可设置，生产仅 HTTPS；开发 loopback 仅测试配置允许。Keychain service 按服务源和隔离运行区分；token 不用 UserDefaults。启动经 /v1/me 确认，不从本地注入登录成功。

UI 标识：auth.server/username/password/login/error、password.current/new/confirm/submit、session.username/role/logout/refresh、admin.accounts/disable/enable/reset/audit、updates.check/status。更新使用 SPUStandardUpdaterController、HTTPS SUFeedURL、SUPublicEDKey、SUVerifyUpdateBeforeExtraction。生产配置缺失显示尚未配置，不能伪装已发现版本。测试包同 Bundle ID/源码、递增 build version，隔离更新源有真实有效和无效 EdDSA 包。测试 CA 仅可配置到隔离 CI，不在用户机器或 App 中绕过 TLS。

官方依据：[FastAPI 安全](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)、[SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)、[Sparkle2.10.0](https://github.com/sparkle-project/Sparkle/blob/2.10.0/Package.swift)、[GitHub macOS runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。具体依赖解析后锁定到文件，失败不能静默升级。

### 开发升级包的签名连续性

原生用例004要求升级后恢复Keychain会话，因此候选和受控高版本包必须使用同一临时代码签名身份。仅在隔离Mac CI生成短期自签测试证书和专用临时keychain，两个包显式指定同一identity和keychain；结束时独立清理临时信任、专用keychain和私钥。该测试签名不满足Developer ID、公证或正式发布条件。开发过程不改变用户本机的信任设置。

依据：[Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)、[Code Signing Requirement Language](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/RequirementLang/RequirementLang.html)。不同ad-hoc包的摘要变化，不能作为跨版本Keychain身份连续性的设计依据。

## 实施顺序（SOP-005）

1. 完成 001–007 文档并保存 structure 与 008 baseline 证据；此阶段程序绑定为planned，010/011真实入口完成后再改ready。
2. 009 创建隔离 venv、服务/数据库和 Mac/native target 骨架。读取工具链状态，本机未配置 Xcode 不触发安装；远端验证 native 探针。
3. 010/011 创建账号/更新数据、独立 oracle 与真实 API/native 测试，在实现前保存确定性失败；无法运行的 native 红测写 BLOCKED。可先推进有实际单元/接口验证的子任务。
4. 012 实现服务/界面/更新；数据与测试绑定完整后设 ready/in_progress，产品通过以前不设 implemented。
5. 013 基础回归，014 完整目标四例 native E2E；失败按015修复并完整重跑。017/018发布前再验最终包与全支持矩阵。
6. 保存实际证据与流程障碍，创建 PR；适用必需检查通过才合并。不能因用户已授权自动合并而跳过产品测试。

## 并行边界与恢复入口

- backend agent：`server/`、`tests/server/`，先测试后业务。CLI与 fixtures 的调用合同向 root/native 交接。
- macOS agent：`apps/macos/`，项目、App 与 XCUITest。只使用统一 API 合同。
- runner agent：root 确认后负责 `scripts/e2e.py`、原生执行/证据校验与其测试；不得放宽发布。
- 原生四例各使用独立数据库、服务和 Keychain service，runner 逐例调用 `-only-testing` 并分别保存 xcresult；不能让用例顺序承担数据初始化。
- root：版本文档、SOP、catalog、矩阵/数据清单、CI、集成与 PR。

候选代码、测试、文档和数据一同提交；测试后代码或依赖变化重新验证。完整命令在入口真实建立后补入，未建立时明确待实现，不写伪造成功记录。

服务启动使用 `python3 -m uvicorn server.tokenmeter_server.main:app --host 127.0.0.1 --port <隔离端口> --no-proxy-headers`，并显式设置 `TOKENMETER_DATABASE_URL`。当前限流按真实连接来源计数，不信任转发头；生产代理来源识别需另行设计验证。
