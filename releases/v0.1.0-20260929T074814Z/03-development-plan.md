# v0.1.0-20260929T074814Z — 技术设计与开发计划

## 技术设计（SOP-004）

依据：[需求](01-requirements.md)、[拆解](02-breakdown.md)、[全局架构](../../docs/architecture/README.md)。

### 服务端与数据

Python 3.10+ / FastAPI、SQLAlchemy 2.0、Alembic；v0.1.0 服务端测试与生产都验证 SQLite，文件和账号相互隔离，ORM 保持后续迁移空间但本版不声称 MySQL 兼容通过。users 保存 UUID、username、Argon2 hash、role、is_active、must_change_password、credential_version；sessions 保存 token SHA256、user_id、credential_version、UTC expires_at；audit 保存动作、操作者/目标、时间及非敏感结果；持久化登录节流桶按账号和来源区分，5次失败/5分钟。秘密不进入 audit 或返回的验证错误。

256-bit opaque bearer，固定30天有效期，不因任何请求滑动续期；每次请求查用户活动状态/凭据版本/会话有效期。换密原子递增版本并撤销全部旧会话，返回新 token；reset/disable 同样撤销。SQLite 启用外键、写入事务，管理员保护在事务内检查。数据库初始 schema 由 Alembic 建立，可重复执行且不覆盖账号。

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

SwiftUI、macOS14 deployment target、Swift5、提交 Xcode project/shared scheme，固定 Sparkle2.10.0。v0.1.0 正式 App 内置服务默认值 `http://127.0.0.1:49176`，登录界面可编辑；正式 App 仅对本机回环地址（`127.0.0.1`、`localhost`、`::1`）允许 HTTP，其他地址只接受 HTTPS，且拒绝带凭据、路径、查询或片段的 URL。更新 App 时需区分内置默认值与用户显式覆盖值：本轮实现配置持久化；待生产 HTTPS 地址确定的后续版本只更新未覆盖用户的默认值，不能覆盖手动设置。客户端按规范化 API origin（scheme/host 小写、去默认80/443端口、去尾斜线）隔离 token；切换源不得重用旧源 token。登录页“在此设备上自动登录”仅在登录页可选，首次默认开启，随后把这一非敏感布尔选择保存在 UserDefaults；关闭时启动绝不读取持久凭据。开启时把服务器随机 token 存入受保护本机凭据文件，取消勾选后，在本次成功登录接收会话时清除当前 origin 旧文件，新 token 仅驻内存。启动必须经 `/v1/me` 验证才进入主页，不从本地缓存注入登录成功；离线显示待验证或错误。服务端 token 固定30天到期、不滑动，`/v1/me` 不刷新 `expires_at`，改密/重置/停用执行实际撤销；断网退出先本地清除，仅在本进程内暂存待重试的撤销请求并提示服务端尚未确认。生产文件固定 `~/Library/Application Support/TokenMeter/credentials`，父目录0700、文件0600、所有者当前uid、拒绝symlink并原子写；不保存密码；该保护只限制其他 macOS 用户访问，同 uid 进程可读，主动复制的 token 不受硬件限制。UITESTING 的每例唯一临时 `credentials` 目录由 runner 创建为0700、解析绝对真实路径且拒绝 `/var` 别名与 symlink；通过 `TM_TEST_CREDENTIALS_DIR` 传给两个构建，由 `TMTestCredentialsDirectory` Info.plist 键和首次启动 XCTest 环境同时提供，供 Sparkle 自主重启后读取相同路径；无效测试路径显式报 `invalid_credential_directory`，正式 App 忽略测试环境；绝不读取生产路径或旧 Keychain。持久凭据保存失败使本次登录整体失败，不展示已验证身份。旧预览用户不迁移旧 Keychain，首次使用新版需重新登录一次。开发任务增加能由本机 Command Line Tools 执行的真实 Swift 凭据存储边界测试，覆盖符号链接、权限、文件类型、origin 隔离、超大/畸形 token、缺文件删除及原子替换不影响其他 origin；这项检查不能替代原生产品 E2E。实际程序路径为 `scripts/test_device_credentials.py` 与 `tests/macos/DeviceCredentialsTests.swift`，已登记 manifest；执行结果按 SOP-013 单独记录，不以文件存在推定测试通过。Info.plist 只对这三个回环主机设置 `NSExceptionAllowsInsecureHTTPLoads`，不使用全局 ATS 放宽；macOS 14 起[域例外支持单个 IP 地址](https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSAppTransportSecurity/NSExceptionDomains)，该 HTTP 例外[本身不改变 HTTPS 的默认信任验证](https://developer.apple.com/documentation/bundleresources/information-property-list/nsexceptionallowsinsecurehttploads)。

UI 标识：auth.server/username/password/login/error、auth.automatic-login、password.current/new/confirm/submit、session.username/role/logout/refresh、admin.accounts/disable/enable/reset/audit、updates.check/status。更新使用 SPUStandardUpdaterController、HTTPS SUFeedURL、SUPublicEDKey、SUVerifyUpdateBeforeExtraction。生产配置缺失显示尚未配置，不能伪装已发现版本。测试包同 Bundle ID/源码、递增 build version，隔离更新源有真实有效和无效 EdDSA 包。测试 CA 仅供隔离 CI 的 `cloudflared` 验证本机 TLS origin；App 使用公开可信 HTTPS 域名，不安装测试 CA、不绕过 TLS。

官方依据：[FastAPI 安全](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)、[SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)、[Sparkle2.10.0](https://github.com/sparkle-project/Sparkle/blob/2.10.0/Package.swift)、[GitHub macOS runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。具体依赖解析后锁定到文件，失败不能静默升级。

### 自动登录持久化与升级边界

原生用例004要求有效包安装、重启后，开启自动登录的测试账号经服务器 `/v1/me` 验证恢复。先前使用 Keychain 的版本在原生视频中已成功升级到构建号101，但新二进制弹出系统凭据访问提示，阻断会话恢复；保留为 BUG-TM001-UPGRADE-001 的历史失败证据。内部应用改用受保护凭据文件，跨版本由同一用户与规范化 origin 读取，不通过输入系统密码、修改 Keychain ACL 或预授权二进制摘要取绿。关闭自动登录的用户重启后回登录页；服务端 token 过期、被撤销或离线时不展示已登录身份。候选和受控高版本测试包在 GitHub CI 可由隔离临时自签身份签名来验证 Sparkle 的真实包签名与安装路径；该签名不构成正式分发能力。UITESTING 两构建的 Info.plist 必须持有同一 runner 专用凭据路径，升级后不得落回生产目录；清理只删除本次拥有的文件。此测试包离开 runner 后路径失效且正式逻辑不能回落生产目录，因此不能再作为本机可登录预览 DMG 的来源；CI 仅保留候选 App 压缩件供诊断。内部 DMG 需要独立的无测试路径构建配置和包级门禁。内部 DMG 的安装、启动、升级、权限与全部原生场景仍另需包级证据和机器门禁，公开 Developer ID/公证条件保持独立。

HTTPS更新源由本机临时CA签发的回环TLS服务和固定版本、SHA256校验的`cloudflared` Quick Tunnel组成。`cloudflared --url https://localhost:<端口> --origin-ca-pool <本次ca.pem>` 验证origin证书，App使用临时的`https://<随机子域>.trycloudflare.com`并由系统正常验证边缘证书；两个TLS端点都不得关闭证书检查。无效/有效appcast和签名包仅为合成测试内容，控制切换使用原生用例持有的随机Bearer通过同一HTTPS源，未授权请求拒绝；私钥、账号与数据库不经隧道公开。`native_environment.py` 保留为可单独触发的零产品用例环境诊断，会在完成后清理自己的资源；第004例不能继承该 READY 再为产品新建第二个随机域名。原生 runner 在004本例的活跃 `SigningIdentity` 与 `UpdateSource` 上准备签名、更新源及同一随机域名；先经两个公共HTTPS DNS源确认A记录已发布，再由Mac正常系统DNS/TLS核对公开端点与来源，并对本次回环 origin 证书执行 `security verify-cert`，不用查询得到的IP绕过系统解析。通过后保持同一签名身份、隧道、域名、CA及专用Keychain存活，直到候选与高版本包构建、真实升级、请求校验结束；同一 `finally` 再清理。Quick Tunnel无法使用或任何清理失败都使该例BLOCKED。001–003与005–006仍实际执行并留证，但不能缩小六例门禁；新候选必须完整重跑。隔离测试签名和临时更新源不满足内部包级或公开 Developer ID/公证发布条件；任何分发仍须对最终 DMG 单独完成安装、升级与全量回归。[Apple签名证书](https://developer.apple.com/documentation/technotes/tn3161-inside-code-signing-certificates)、[Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)、[Cloudflare origin CA池](https://developers.cloudflare.com/tunnel/troubleshooting/)是设计依据。

双公共DNS均发布记录后，GitHub Intel Mac仍可能持续无法用系统解析器访问同一域名。首次系统`curl`退出6时，仅在当前活跃隔离fixture中进行一次有界只读诊断：系统resolver与缓存查询、默认及公共resolver的A/AAAA、IPv4限定的正常TLS探测；整组最多60秒，计入原180秒准备窗口，结果脱敏保存。诊断不能更改系统DNS/hosts/信任，也不能把公共DNS或IPv4诊断成功作为App更新成功。主操作BLOCKED与临时资源清理成功分别记录；清理成功不能改变门禁判定。

依据：[Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)、[Code Signing Requirement Language](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/RequirementLang/RequirementLang.html)。历史 Keychain 方案与失败证据仅留在本轮06记录，不再作为当前自动登录设计。

## 实施顺序（SOP-005）

1. 完成 001–007 文档并保存 structure 与 008 baseline 证据；此阶段程序绑定为planned，010/011真实入口完成后再改ready。
2. 009 创建隔离 venv、服务/数据库和 Mac/native target 骨架。读取工具链状态，本机未配置 Xcode 不触发安装；远端验证 native 探针。
3. 010/011 创建账号/更新数据、独立 oracle 与真实 API/native 测试，在实现前保存确定性失败；无法运行的 native 红测写 BLOCKED。可先推进有实际单元/接口验证的子任务。
4. 012 实现服务/界面/更新；数据与测试绑定完整后设 ready/in_progress，产品通过以前不设 implemented。
5. 013 基础回归，014 完整目标六例 native E2E；第001/003/004/006例须核对设备自动登录的启停、过期/撤销、升级重启与服务隔离；第006例须在隔离默认端口和第二套真实服务/SQLite 上核对路由及持久化，不能连接用户生产库。失败按015修复并完整重跑。017/018发布前再验最终包与全支持矩阵。
6. 保存实际证据与流程障碍，创建 PR；适用必需检查通过才合并。不能因用户已授权自动合并而跳过产品测试。

## 并行边界与恢复入口

- backend agent：`server/`、`tests/server/`，先测试后业务。CLI与 fixtures 的调用合同向 root/native 交接。
- macOS agent：`apps/macos/`，项目、App 与 XCUITest。只使用统一 API 合同。
- runner agent：root 确认后负责 `scripts/e2e.py`、原生执行/证据校验与其测试；不得放宽发布。
- 原生六例各使用独立数据库、服务和 UITESTING 专用临时凭据目录，runner 逐例调用 `-only-testing` 并分别保存 xcresult；005 调用生产首建程序但仅指向 runner 临时根，不能让用例顺序承担数据初始化。006 另启动第二套临时服务与 SQLite，第一套占用默认端口 49176；端口被其他进程占用时先 BLOCKED，不能指向用户实际生产库。
- root：版本文档、SOP、catalog、矩阵/数据清单、CI、集成与 PR。

候选代码、测试、文档和数据一同提交；测试后代码或依赖变化重新验证。完整命令在入口真实建立后补入，未建立时明确待实现，不写伪造成功记录。

服务启动使用 `python3 -m uvicorn server.tokenmeter_server.main:app --host 127.0.0.1 --port <隔离端口> --no-proxy-headers`，并显式设置 `TOKENMETER_DATABASE_URL`。当前限流按真实连接来源计数，不信任转发头；生产代理来源识别需另行设计验证。

## 本机测试环境接入

用户已明确授权本机作为开发、SQLite 服务与预览安装环境。实际环境为Intel/macOS15.7.4/已登录桌面，当前只有Command Line Tools，不能在本机运行原生 XCUITest；不以本机安装完整 Xcode 作为继续开发或远端迭代验收的前提。001–006由GitHub托管macOS15 Apple Silicon和Intel runner使用Xcode16.4、真实App和隔离数据执行，其中004的更新fixture仅允许专用CI Mac。若将来另需本机原生重跑，再安装完整Xcode、完成首次启动组件、许可及UI自动化授权；Apple登录和系统管理员确认通过对应机器的系统界面完成，不伪造GitHub环境变量或静默改本机配置。完整支持矩阵与正式发布要求继续保留。
