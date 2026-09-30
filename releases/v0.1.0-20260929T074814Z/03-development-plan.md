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

地址配置边界另由可在本机CLT运行的 `scripts/test_endpoint_configuration.py` 编译真实 `Auth.swift` 与 `tests/macos/EndpointConfigurationTests.swift` 核对默认值、URL校验、覆盖和恢复；程序已登记manifest，但运行结果须另记，不能替代004/006的原生UI。

UI 标识：auth.server/username/password/login/error、auth.automatic-login、password.current/new/confirm/submit、session.username/role/logout/refresh、admin.accounts/disable/enable/reset/audit、configuration.open/api-url/update-url/save/reset-defaults/cancel/error/status、updates.check/status。配置页从常驻 `configuration.open` 打开；保存前同时验证两个URL，再一次提交两个覆盖值，取消不保存输入；恢复默认立即删除API和更新URL显式覆盖并显示本版内置值，取消只关闭页面。已登录或有 `pendingLogout` 时锁定API编辑和总恢复默认，提示先退出；更新进行中锁定更新源编辑。登录页 `auth.server` 继续可用。更新使用 `SPUStandardUpdaterController`、固定 `SUPublicEDKey`、`SUVerifyUpdateBeforeExtraction` 和可配置的 feed URL 委托；内置默认 `SUFeedURL=http://127.0.0.1:49177/appcast.xml`，只有用户显式覆盖才持久保存URL。候选与高版本测试包同 Bundle ID/源码、递增 build version；004的两个构建均不注入 `TM_UPDATE_FEED_URL`，从各自 App 内置默认值走真实更新。`apps/macos/build_update_fixture.py` 必须增加仅当准备源等于该默认值才允许的 `--use-default-feed` 路线。更新URL允许appcast路径，拒绝userinfo、query、fragment、空host和非法端口；HTTP只允许精确回环主机，非回环需正常HTTPS/TLS。Appcast选中包的fileURL与重定向也需安全边界验证。004在同一49177活跃源先用鉴权`control/forbidden`把enclosure指向`http://example.invalid/update.zip`，由选中包URL校验在传输前返回`update_source_rejected`；再用鉴权`control/redirect`将enclosure指向本机`/redirect.zip`，302到同一非回环HTTP URL，要求ATS实际返回`NSURLErrorDomain -1022`并映射`update_transport_rejected`，DNS失败不能充数；然后原`control/invalid`恢复完整坏签名包，最后原`control/valid`发布有效包。前三阶段都保持build100，最后真实升级build101。runner注入`TM_TEST_UPDATE_{FORBIDDEN,REDIRECT,INVALID}_CONTROL_URL`，保持原控制Bearer、EdDSA key与单一更新源；完整004的600秒上限不延长。公钥不随地址覆盖变化，测试私钥只在隔离fixture。Info.plist只对三个回环主机保留现有ATS窄例外，不打开全局明文。

官方依据：[FastAPI 安全](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)、[SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)、[Sparkle2.10.0](https://github.com/sparkle-project/Sparkle/blob/2.10.0/Package.swift)、[GitHub macOS runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。具体依赖解析后锁定到文件，失败不能静默升级。

### 自动登录持久化与升级边界

原生用例004要求有效包安装、重启后，开启自动登录的测试账号经服务器 `/v1/me` 验证恢复。先前使用 Keychain 的版本在原生视频中已成功升级到构建号101，但新二进制弹出系统凭据访问提示，阻断会话恢复；保留为 BUG-TM001-UPGRADE-001 的历史失败证据。内部应用改用受保护凭据文件，跨版本由同一用户与规范化 origin 读取，不通过输入系统密码、修改 Keychain ACL 或预授权二进制摘要取绿。关闭自动登录的用户重启后回登录页；服务端 token 过期、被撤销或离线时不展示已登录身份。候选和受控高版本测试包在 GitHub CI 可由隔离临时自签身份签名来验证 Sparkle 的真实包签名与安装路径；该签名不构成正式分发能力。UITESTING 两构建的 Info.plist 必须持有同一 runner 专用凭据路径，升级后不得落回生产目录；清理只删除本次拥有的文件。此测试包离开 runner 后路径失效且正式逻辑不能回落生产目录，因此不能再作为本机可登录预览 DMG 的来源；CI 仅保留候选 App 压缩件供诊断。内部 DMG 需要独立的无测试路径构建配置和包级门禁。内部 DMG 的安装、启动、升级、权限与全部原生场景仍另需包级证据和机器门禁，公开 Developer ID/公证条件保持独立。

用户此 Mac 的默认更新源应由同机回环服务提供，默认 `http://127.0.0.1:49177/appcast.xml`；在GitHub两台runner上，`127.0.0.1` 分别是各自runner，并非用户此Mac。004只在每台runner固定49177启动一组隔离 `UpdateSource`，先通过 `/healthz` 的一次性 source nonce 核对端口所有权、HTTP状态/来源，发布fixture后再由真实App与请求核验程序检查 `/appcast.xml` 与包响应，并核对同一候选；candidate与高版保持内置默认feed，先拒绝损坏EdDSA包且原构建号不变，再用同一活跃源提供有效包并经Sparkle安装重启、构建号改变及`/v1/me`无交互恢复。每例在同一 `finally` 清理源进程、隔离签名Keychain和凭据目录。第006例通过配置页保存合法合成更新URL、重启复核、恢复默认与非法URL拒绝，不连接该合成更新地址，也不需第二更新服务。CI更新测试不再需要公网隧道、公共DNS或本机测试CA；旧Quick Tunnel程序/诊断仅属历史源码，不再是本轮E2E前提。Sparkle官方[ATS说明](https://sparkle-project.org/documentation/app-transport-security/)及2.10.0源码支持按App的ATS策略访问feed；回环HTTP仍须经真实App负测证明，不能仅凭文档宣称。隔离开发代码签名与固定EdDSA包签名仅用于迭代，不满足内部最终DMG或公开Developer ID/公证发布条件。

本机已安装的旧 `/Applications/TokenMeter.app` 构建号100且缺`SUFeedURL`与`SUPublicEDKey`，不能用于验证新默认源或真实升级；不覆盖它，也不触碰真实`database/production/production.db`。本轮现有CI的XCUITest全六例为迭代门禁；本机可待新App/本机服务安全部署后按同模式体验。若以后另立本机CLT构建及AX驱动任务，必须使用隔离App安装位置、数据库、凭据和回环源，由真实App完成更新UI断言；当前`AXIsProcessTrusted=false`、执行器未建立，故本机E2E没有PASS证据，不作为现有CI前置阻断。
依据：[Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)、[Code Signing Requirement Language](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/RequirementLang/RequirementLang.html)。历史 Keychain 方案与失败证据仅留在本轮06记录，不再作为当前自动登录设计。

## 实施顺序（SOP-005）

1. 完成 001–007 文档并保存 structure 与 008 baseline 证据；此阶段程序绑定为planned，010/011真实入口完成后再改ready。
2. 009 创建隔离 venv、服务/数据库和 Mac/native target 骨架。读取工具链状态，本机未配置 Xcode 不触发安装；远端验证 native 探针。
3. 010/011 创建账号/同机回环更新数据、独立 oracle 与真实 API/native 测试，在实现前保存确定性失败；无法运行的 native 红测写 BLOCKED。可先推进有实际单元/接口验证的子任务。
4. 012 实现服务/配置管理页/更新；数据与测试绑定完整后设 ready/in_progress，产品通过以前不设 implemented。
5. 013 基础回归，014 完整目标六例 native E2E；第001/003/004/006例须核对设备自动登录的启停、过期/撤销、升级重启与服务隔离；第004例须在各runner同机固定49177核对默认更新源；第006例须在隔离API默认端口和第二套真实服务/SQLite 上核对路由、配置页更新URL持久化和恢复默认，不能连接用户生产库。失败按015修复并完整重跑。017/018发布前再验最终包与全支持矩阵。
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
