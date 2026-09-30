# 01 · TM-001 账号与登录：详细测试用例

需求：`REQ-TM001`。版本：`v0.1.0-20260929T074814Z`。功能矩阵当前为 `in_progress`；下列六例已在 [CI 36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502) 的 macOS 15 Apple Silicon、Intel 各执行并经父门禁复核 PASS。此记录只引用该次开发迭代，不授予最终 DMG 发布资格。正式包门禁结果以[状态页](../../status.md)及其实际证据为准。

## 共用前置、数据与执行

- 先读 [SOP-010 数据](../../../sop/SOP-010-test-data.md)、[SOP-011 测试实现](../../../sop/SOP-011-test-implementation.md)、[SOP-014 E2E](../../../sop/SOP-014-e2e.md)。在已登录桌面且具备完整 Xcode 的隔离 Mac 上运行；本机仅有 CLT 时，不能把组件检查称为这六例。
- 自动化文件：[TM001AccountUITests.swift](../../../apps/macos/TokenMeterUITests/TM001AccountUITests.swift)。每例绑定 `TokenMeterUITests/TM001AccountUITests/testE2E_TM001_NNN`；下文 `NNN` 对应稳定 ID 尾号。
- 开发模式：[native_e2e.py](../../../scripts/native_e2e.py) 为每例生成新 API/SQLite、UserDefaults 测试域及 0700 凭据目录；真实 App 连接真实认证接口。完整应执行集合由 `python3 scripts/quality_gate.py iteration` 驱动，退出码 `0=PASS`、`1=FAIL`、`2=BLOCKED`，不能挑一例绿灯代替回归。
- 最终包模式：按[内部发布设计](../../releases/01-internal-v0.1.0.md)在一次性GitHub托管Mac从同一DMG安装生产Bundle `org.tokenmeter.TokenMeter`；独立XCUITest使用 `XCUIApplication(url:)` 指向安装路径并核对实际运行路径。API/SQLite仍逐例隔离，凭据和UserDefaults使用该runner账号标准位置，先证明不存在并登记所有权、结束后验证清理。全部测试/签名输入只交独立runner，生产App不接收测试路径或业务旁路。六个ID和业务断言不减少；本模式尚需本轮原始执行结果，不能套用前述开发CI PASS。
- 账号程序：[tests/server/fixtures.py](../../../tests/server/fixtures.py)，`auth_accounts`，seed 42。四个账号 `test-admin/test-alice/test-bob/test-disabled`，初始密码分别为 `TEST-ONLY-<名字>-42!`；角色 admin/member/member/member，最后一个停用，全部强制首次改密。UUID 尾号依次 0001–0004。改后密码 `TEST-ONLY-Changed-42!`，重置临时密码 `TEST-ONLY-Reset-42!`。这些只是公开合成测试凭据。
- fixture 的 `expected()` 是独立预期：四账号、角色/激活标志、首次改密、固定会话寿命 2,592,000 秒。生产认证/ORM 不用于生成答案。原生 UI 覆盖下述操作；固定时钟的 30 天过期、不滑动及文件边界由服务/Swift 组件检查补充，不能声称原生测试等待过 30 天。
- 本机回归 SQL 由 [bootstrap_sqlite.py](../../../scripts/bootstrap_sqlite.py) 生成：`database/test/seed.sql` 与隔离的 `database/test/test.db`。程序先验证空库/环境标记再执行，不能把 SQL 指向用户生产库。命令和安全重置见[数据库说明](../../../database/README.md)。原生 runner 使用逐例临时库，001/002/003/006 通过真实 CLI 迁移导入同一 fixture；不直接复用固定 `test.db`。
- 每次结束 runner 清理本次进程、fixture、测试域和凭据目录；清理异常保留证据并阻断。不得清除用户实际 App 的设置、会话和生产库。

## E2E-TM001-001 · 首次改密、自动登录和退出

**验收：** `AC-TM001-001`，有效账号可登录，首次改密生效，默认自动登录经 `/v1/me` 确认，关闭后重启回登录，退出撤销会话。

**前置/数据：** 共用环境与 `auth_accounts`；干净的 alice 状态；预先经真实 API 取得一个旧 alice token，仅存在测试进程内存。

**步骤：**

1. 启动 App，检查 `auth.automatic-login` 默认选中；输入 alice 初始账号密码，点击 `auth.login`。
2. 检查强制改密页面存在、管理员入口不存在；从初始密码改为约定新密码。
3. 检查界面身份为 `test-alice`；只断言保存 token 的格式/权限，不把内容写日志；分别用旧 token 和旧密码请求服务。
4. 退出进程并重新启动；不输入密码，等待本人身份；点击 `session.refresh`，确认服务验证时刻变化且没有未验证身份提示。
5. 经独立管理员会话记录 alice 当前 logout 审计数；点击 UI 退出，等待登录输入框重新启用；检查凭据文件已删除，再用旧保存 token 请求 `/v1/me`。
6. 重启，取消自动登录并以新密码登录；检查没有持久 token。再重启应回到登录页且复选框仍关闭。
7. 重新开启自动登录并登录，确认当前 origin 的 token 文件重新建立。

**独立预期：** UI 身份正确；旧密码/被改密撤销 token 均 401；会话文件为当前 UID 的普通 0600 文件、父目录 0700，只含 43 字符不透明 token。重启恢复仍须真实服务确认。UI 退出使 token 401，logout 审计数恰好 +1；关闭自动登录不落盘且重启不恢复。固定有效期和不滑动由独立服务测试另验。

**绑定/证据/状态：** 原生 `testE2E_TM001_001`，SOP-014；原始 `native.xcresult`、截图 `TM001-001-01-login` / `02-authenticated-account`、逐例 result、服务/fixture 摘要及父门禁。上述 CI 两平台 PASS；不是最终包测试。

## E2E-TM001-002 · 错密、停用及成员权限

**验收：** `AC-TM001-002`，成员只见本人身份，无账号管理权限；错误密码和停用账号显示对应错误。

**前置/数据：** 共用环境与全新 `auth_accounts`。bob 为启用 member，disabled 为停用 member。

**步骤：**

1. 启动 App，以 bob 和 `TEST-ONLY-Wrong-42!` 登录，等待 UI `invalid_credentials`。
2. 以 disabled 正确初始密码登录，等待 UI `account_disabled`。
3. 以 bob 正确密码登录并完成首次改密；检查本人身份和 role。
4. 检查 `admin.accounts` 不存在；用 bob 的独立真实 API 会话分别请求用户列表、审计列表和停用 alice 的管理接口。
5. 点击 UI 刷新身份，保存已断言的成员界面截图。

**独立预期：** 两个失败都留在登录页且错误分类准确；成功后 username=`test-bob`、role=`member`；`/v1/me` 返回本人；三个管理请求均 403。此例不验证尚未实现的团队统计越权，后者见 TM-007-004。

**绑定/证据/状态：** 原生 `testE2E_TM001_002`，SOP-014；`TM001-002-01-member-permissions`、原始 xcresult、真实服务结果与父门禁；上述 CI 两平台 PASS。

## E2E-TM001-003 · 管理操作、审计与已保存会话撤销

**验收：** `AC-TM001-003`，重置密码/停用撤销旧会话和自动登录，管理动作有正确执行者与对象的审计。

**前置/数据：** 共用环境与全新 `auth_accounts`；预先保存 bob 的旧 API token。

**步骤：**

1. 从 App 登录 admin、完成首次改密并进入账号管理；为 bob 重置到 `TEST-ONLY-Reset-42!`。
2. 等待 `password_reset` 状态；用 bob 原 token 请求 `/v1/me`。
3. 从 UI 停用 bob，等待其状态 `disabled`；用重置密码尝试真实 API 登录。
4. 从 UI 启用 bob并打开审计，检查 reset/disable/enable 三类动作，reset 的 actor UUID=0001、target UUID=0003。
5. 退出 admin，从 UI 登录 bob，以临时密码完成首次改密到 `TEST-ONLY-Bob-New-42!`，保存本次 token。
6. 经独立真实 admin API 再重置 bob；先断言该保存 token 401，再退出进程/启动，等待 `invalid_session`、登录页及本地凭据删除。
7. 重新登录 bob，保存新 token；经 admin API 停用 bob；同样检查 token 401，重启 App 不恢复身份、显示无效会话并删除凭据。

**独立预期：** 重置撤销既有会话，临时密码要求改密；停用后登录403；审计对象/操作者正确。两种服务端撤销都不能以本地 token 或缓存身份绕过服务验证。用于制造撤销的 API 仅控制外部真实服务，恢复失败必须从 App UI 断言。

**绑定/证据/状态：** 原生 `testE2E_TM001_003`，SOP-014；截图 `TM001-003-01-admin-audit` / `02-revoked-automatic-login`、原始 xcresult 与父门禁；上述 CI 两平台 PASS。

## E2E-TM001-004 · 同机更新、拒绝非法包和真实重启

**验收：** `AC-TM001-004`，默认同机 feed、HTTP 仅回环、非法下载/重定向/签名拒绝，有效包由 Sparkle 安装重启后经服务恢复账号。

**前置/数据：** `tm001_update_packages`，生成器 [update_source.py](../../../tests/e2e/update_source.py)，构建器 [build_update_fixture.py](../../../apps/macos/build_update_fixture.py)，以及 alice 账号。每台执行 Mac 自己独占 `127.0.0.1:49177`；一次性 nonce 验证进程归属。开发模式使用一组临时代码签名身份、EdDSA 公私钥和四阶段 appcast；最终包模式使用内部构建任务生成的固定公钥、稳定代码签名身份及预先签好的候选/101包，测试机不需要私钥。私钥不上报。候选 build 100 与受控高版 101 的 feed 构建值均为空，由 App 内置默认值生效；两包固定相同公钥且 `SUVerifyUpdateBeforeExtraction=true`。更新源是文件/HTTP fixture，无造数 SQL；账号库仍由共用程序生成。

**步骤：**

1. 启动 App，打开配置页检查 `http://127.0.0.1:49177/appcast.xml`，取消关闭；登录 alice、改密并保存当前 token，仅在测试内存比较。
2. 外部鉴权控制切换 forbidden feed，其下载地址为 `http://example.invalid/update.zip`。点击检查更新，关闭错误对话框，断言 `update_source_rejected` 且仍是 build 100。
3. 切换 redirect feed：本机包 URL 302 到上述非回环 HTTP。点击检查和安装，取消错误，断言 `update_transport_rejected: -1022`，仍为 build 100。DNS 错误不能满足此断言。
4. 切换 invalid feed，下载实际完整坏 EdDSA 包。取消错误后必须为 `update_signature_rejected` 且 build 100。
5. 退出 App，切换同一源为 valid feed，启动并确认自动登录；检查更新，点击 `Install Update`，再点击 `Install and Relaunch`。
6. 此后测试不得调用 `app.launch()`；等待 Sparkle 自己重启并显示 build 101，检查 alice 身份，点击刷新确认 `/v1/me`，核对同一 token 延续。
7. 打开配置，确认默认 feed 保留，已登录时 API 编辑和恢复默认锁定；由 fixture 核对四次控制顺序、feed/包真实请求与清理结果。

**独立预期：** forbidden→redirect→invalid→valid 必须完整且顺序正确。前三阶段原版保留，最后包摘要/版本对应受控构建，真实替换/自主重启成功；无新登录交互且身份来自服务。回环放行不扩展到其他 HTTP 主机，也不改变固定公钥。测试包不是可分发稳定版。

**绑定/证据/状态：** 原生 `testE2E_TM001_004`、SOP-014/017；准备 `environment.json`、脱敏请求记录、包签名/摘要、原始 xcresult、三张阶段截图与父门禁。完整 xcresult 摘要在解析/附件导出结束后生成，父级重新解析前后均复核全部文件。上述 CI 两平台 PASS；最终 DMG 安装和正式 profile 仍需另验。

## E2E-TM001-005 · 生产首建管理员与测试数据隔离

**验收：** `AC-TM001-005`，空生产库只预置 admin/123456，强制改密，已有密码不得因再次启动而重置。

**前置/数据：** `production_bootstrap`，由 [bootstrap_sqlite.py](../../../scripts/bootstrap_sqlite.py) 在本例私有临时根建立生产布局和 SQL；不是用户的 `database/production/production.db`。首建账号 UUID 尾号0005、username=`admin`、role=`admin`。生成的 `seed.sql` 只含随机盐密码散列及首建审计，拒绝非空库重放。

**步骤：**

1. 通过独立真实 API 用 admin/123456 登录，确认 must_change_password=true；访问管理员列表应403且 `password_change_required`。
2. 启动真实 App，以同一账号首登，检查强制改密 UI 和 admin 身份，管理员入口暂不可见。
3. 改为约定至少12位新密码；检查管理员入口出现；旧 token 和123456均401。
4. 打开账号列表，检查只有 admin，没有 `test-*` 管理行；独立 API 用户列表必须恰好一个用户，UUID0005、must_change_password=false。
5. 退出进程/启动，检查自动恢复 admin；主动退出再以新密码登录，刷新身份成功。
6. 首建程序的服务回归另验证已有库拒绝再次初始化、重启服务不重建库、不重置改后密码；该回归结果不能代替上述原生过程。

**独立预期：** 原生 UI 和 API 均证明首建身份/角色与强制改密；生产副本无四个测试账号；新密码跨 App/服务生命周期有效。只检查非敏感列，不上传密码散列或 token。

**绑定/证据/状态：** 原生 `testE2E_TM001_005`，SOP-010/014；三张 `TM001-005-*` 截图、临时库/SQL摘要、bootstrap及服务回归、xcresult/父门禁；上述 CI 两平台 PASS。

## E2E-TM001-006 · 默认/可配地址和跨服务会话边界

**验收：** `AC-TM001-006`，默认本机 API，可配置且重启保留；会话按规范化 origin 隔离；更新地址成对校验、持久化和恢复默认。

**前置/数据：** 两套真实 FastAPI/独立 SQLite，第一套 `http://127.0.0.1:49176`、seed42；第二套独立临时回环端口、seed43。第二套 alice 密码 `TEST-ONLY-alice-43!`。两套数据库均由 `auth_accounts` 从空环境生成。App 必须读取发布源码的内置API值。开发模式删除API测试注入且本例不配置更新公钥；最终包模式不向生产App注入任何测试变量，使用包内固定公钥，并由测试runner按候选配置核对该公钥。

**步骤：**

1. 启动 App，登录页与配置页 API 必须等于第一套地址，更新地址为本机49177。
2. 配置页输入第二 API，但同时填非回环 HTTP 更新 URL；保存应报 `invalid_update_source`。取消关闭后 API 仍是第一套，证明先验证两项再写入。
3. 用第一套 alice 登录，独立断言该 token 在第一套200、第二套401；重启恢复，退出后删除第一套凭据。
4. 登录页改为第二套地址；用 seed43 密码登录并改密，先证明这个密码在第一套不能登录。检查第二 token 仅在第二套200，第一套401；两 origin 的文件路径不同。
5. 重启自动恢复第二套身份并刷新；退出后地址仍为第二套、该 origin 凭据清除。
6. 配置页逐一保存非回环HTTP、带userinfo和65536非法端口的更新地址，均应拒绝；开发模式保存 `https://updates.example.invalid/team/appcast.xml`；最终包模式保存 `http://127.0.0.1:49177/configuration-only.xml`。重启检查各自覆盖保留；本步骤不点击检查更新，不以合成地址连通作为通过条件。
7. 开发模式检查没有公钥时更新按钮仍禁用；最终包模式检查更新按钮可用且配置页没有公钥编辑入口，保持构建时固定公钥。编辑另一个 URL 后取消不保存；点击恢复默认，API与更新源都回到内置值，重启仍正确。
8. 登录页尝试非回环HTTP API，必须为 `invalid_server`；以 HTTPS 请求第二套纯HTTP测试服务，应通过地址校验但在TLS/网络失败并显示无法连接，不能误报地址非法。

**独立预期：** 路由、密码、token和保存路径同时证明服务隔离；失败的双地址保存不能部分提交；取消不保存、手动覆盖跨重启保留、恢复默认删除覆盖；更新URL配置不能改变公钥：无公钥开发包不能因此启用更新，生产包保留固定公钥且验签不可绕过。纯配置HTTPS接受不证明某个远端服务已连通。

**绑定/证据/状态：** 原生 `testE2E_TM001_006`，SOP-014；`TM001-006-*` 三张截图、两份fixture/服务摘要、原始 xcresult与父门禁；上述 CI 两平台 PASS。

## 覆盖解释与证据查询

从 [总索引](README.md) 进入机器[验收清单](../../../tests/acceptance.json)和[功能矩阵](../../../tests/feature_matrix.json)可核对六个ID。服务端及Swift组件覆盖固定时钟、散列/权限、非法文件、退出网络失败等边界，原生六例覆盖主要产品交互，两类结果分别记录。

[PR #2](https://github.com/lzhe72/TokenMeter/pull/2) 已合并到 master（合并提交 `e011857`）。最新 CI PASS 属于其被测候选，不自动转移到随后修改的提交或新 DMG。新候选必须按 SOP 重新执行适用门禁。
