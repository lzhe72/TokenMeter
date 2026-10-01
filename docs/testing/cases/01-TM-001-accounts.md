# 01 · TM-001 账号与登录：详细测试用例

需求：`REQ-TM001`。版本：`v0.1.0-20260929T074814Z`。功能矩阵当前为 `in_progress`。以下六个聚合场景已迁移到 Electron + Playwright；dev07的五组PASS、升级004 FAIL属于历史运行。首轮精细全量BLOCKED，新版正在执行；正式候选仍须在当前本机 macOS 15 Intel 上从固定DMG安装后执行完整集合。本次开发结果不能作为正式发布通行证。[CI 36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502) 的 SwiftUI/XCUITest 双平台 PASS 只属历史实现。具体状态见[状态页](../../status.md)和[本版结果](../../../releases/v0.1.0-20260929T074814Z/07-test-results.md)。

## 共用前置、数据与执行

- 先读 [SOP-010 数据](../../../sop/SOP-010-test-data.md)、[SOP-011 测试实现](../../../sop/SOP-011-test-implementation.md)、[SOP-014 E2E](../../../sop/SOP-014-e2e.md) 与[Electron 本机设计](../../architecture/01-electron-local.md)。本轮无需完整 Xcode；Playwright 必须驱动最终 DMG 中实际安装的 Electron App，不接受网页预览、开发服务器或 API/IPC mock 作为产品 E2E。
- 已有聚合绑定：`apps/desktop/e2e/tm001.spec.ts`和`scripts/local_e2e.py`，保留`E2E-TM001-001`至`006`稳定ID；旧[TM001AccountUITests.swift](../../../apps/macos/TokenMeterUITests/TM001AccountUITests.swift)仅供历史行为核对。新增精细TC的程序、数据和逐步证据仍须单独绑定；不得继承聚合场景的PASS。
- 本机 runner 应从同一最终 DMG 安装原包，核对包摘要与签名，再用 Playwright 的 Electron `executablePath` 启动安装路径。每例用全新 0700 profile、隔离安装位置、独立 SQLite 和真实 FastAPI；正式 App 的通用工作目录配置须跨更新器自主重启保留，不能回落至用户标准目录。UI 使用与旧用例同名的 `data-testid`；主进程、preload、IPC 与数据库均用待发布实现。
- 当前本机 49176 已有用户生产服务，`/Applications/TokenMeter.app` 也在运行。测试不终止、覆盖或对其登录/造数；无凭据首启只从 UI 核对默认 API `http://127.0.0.1:49176` 与更新清单 `http://127.0.0.1:49177/version.json`，在登录前通过真实设置 UI 切换到每例独占的动态回环 API 端口。不得向默认生产端口发认证/写请求。第004例的更新源也由 UI 指向本例拥有的动态端口；第006例使用两个动态独立服务。
- 账号程序：[tests/server/fixtures.py](../../../tests/server/fixtures.py)，`auth_accounts`，seed 42。四个账号 `test-admin/test-alice/test-bob/test-disabled`，初始密码分别为 `TEST-ONLY-<名字>-42!`；角色 admin/member/member/member，最后一个停用，全部强制首次改密。UUID 尾号依次 0001–0004。改后密码 `TEST-ONLY-Changed-42!`，重置临时密码 `TEST-ONLY-Reset-42!`。这些只是公开合成测试凭据。
- fixture 的 `expected()` 是独立预期：四账号、角色/激活标志、首次改密、固定会话寿命 2,592,000 秒。生产认证/ORM 不用于生成答案。Electron UI覆盖下述操作；固定时钟的30天过期、不滑动及文件边界由独立组件检查补充，不能声称产品E2E等待过30天。
- 本机回归 SQL 由 [bootstrap_sqlite.py](../../../scripts/bootstrap_sqlite.py) 生成；已有 `database/test/seed.sql` 仅供隔离测试库，不得指向用户生产库。runner 对 001/002/003/006 逐例调用真实 CLI 迁移和导入；005 在专属临时根调用相同生产首建程序，不直接复用用户 `database/production/production.db`。
- 每例结束只清理由本次 `run_id` 标记且确实拥有的 App 进程、服务、端口、fixture、安装目录及 profile；保留脱敏原始 Playwright JSON、断言事件、trace/截图、服务审计和数据库摘要。异常清理阻断。完整六例零失败/跳过后仍须由独立本机父门禁复核候选、DMG、数据、真实 UI 结果与摘要，不能由 runner 自报 PASS 放行。

## E2E-TM001-001 · 首次改密、自动登录和退出

**验收：** `AC-TM001-001`，有效账号可登录，首次改密生效，默认自动登录经 `/v1/me` 确认，关闭后重启回登录，退出撤销会话。

**前置/数据：** 共用环境与 `auth_accounts`；干净的 alice 状态；runner 为本例启动一套动态端口 API 和新 SQLite。预先经这套真实 API 取得一个旧 alice token，仅存在测试进程内存。

**步骤：**

1. 首次启动安装后的 App，核对默认地址显示且没有凭据或默认 API 认证请求；在登录前由真实配置 UI 切换到本例动态 API，检查 `auth.automatic-login` 默认选中；输入 alice 初始账号密码，点击 `auth.login`。
2. 检查强制改密页面存在、管理员入口不存在；从初始密码改为约定新密码。
3. 检查界面身份为 `test-alice`；只断言保存 token 的格式/权限，不把内容写日志；分别用旧 token 和旧密码请求服务。
4. 退出进程并重新启动；不输入密码，等待本人身份；点击 `session.refresh`，确认服务验证时刻变化且没有未验证身份提示。
5. 经独立管理员会话记录 alice 当前 logout 审计数；点击 UI 退出，等待登录输入框重新启用；检查凭据文件已删除，再用旧保存 token 请求 `/v1/me`。
6. 重启，取消自动登录并以新密码登录；检查没有持久 token。再重启应回到登录页且复选框仍关闭。
7. 重新开启自动登录并登录，确认当前 origin 的 token 文件重新建立。

**独立预期：** UI 身份正确；旧密码/被改密撤销 token 均 401；会话文件为当前 UID 的普通 0600 文件、父目录 0700，只含 43 字符不透明 token。重启恢复仍须真实服务确认。UI 退出使 token 401，logout 审计数恰好 +1；关闭自动登录不落盘且重启不恢复。固定有效期和不滑动由独立服务测试另验。

**绑定/证据/状态：** Playwright `E2E-TM001-001`，SOP-014；原始 Playwright JSON、UI 断言事件、trace/截图 `TM001-001-01-login` / `02-authenticated-account`、服务/fixture/安装包摘要及父门禁。dev07开发包该组PASS；正式候选尚未通过；精细TC结果见独立run，旧Swift CI仅为历史证据。

## E2E-TM001-002 · 错密、停用及成员权限

**验收：** `AC-TM001-002`，成员只见本人身份，无账号管理权限；错误密码和停用账号显示对应错误。

**前置/数据：** 共用环境与全新 `auth_accounts`、独立动态 API/SQLite。bob 为启用 member，disabled 为停用 member。

**步骤：**

1. 首启核对默认值且无凭据时不向默认生产 API 发认证/写请求，通过真实 UI 改连本例动态服务；以 bob 和 `TEST-ONLY-Wrong-42!` 登录，等待 UI `invalid_credentials`。
2. 以 disabled 正确初始密码登录，等待 UI `account_disabled`。
3. 以 bob 正确密码登录并完成首次改密；检查本人身份和 role。
4. 检查 `admin.accounts` 不存在；用 bob 的独立真实 API 会话分别请求用户列表、审计列表和停用 alice 的管理接口。
5. 点击 UI 刷新身份，保存已断言的成员界面截图。

**独立预期：** 两个失败都留在登录页且错误分类准确；成功后 username=`test-bob`、role=`member`；`/v1/me` 返回本人；三个管理请求均 403。此例不验证尚未实现的团队统计越权，后者见 TM-007-004。

**绑定/证据/状态：** Playwright `E2E-TM001-002`，SOP-014；`TM001-002-01-member-permissions`、原始UI断言事件、trace/截图、真实服务审计与父门禁。dev07开发包该组PASS；正式候选尚未通过；精细TC结果见独立run，旧Swift CI仅为历史证据。

## E2E-TM001-003 · 管理操作、审计与已保存会话撤销

**验收：** `AC-TM001-003`，重置密码/停用撤销旧会话和自动登录，管理动作有正确执行者与对象的审计。

**前置/数据：** 共用环境与全新 `auth_accounts`、独立动态 API/SQLite；预先保存 bob 的旧 API token。

**步骤：**

1. 首启核对默认值且无凭据时不向默认生产 API 发认证/写请求，经真实 UI 改连本例动态服务；再从 App 登录 admin、完成首次改密并进入账号管理；为 bob 重置到 `TEST-ONLY-Reset-42!`。
2. 等待 `password_reset` 状态；用 bob 原 token 请求 `/v1/me`。
3. 从 UI 停用 bob，等待其状态 `disabled`；用重置密码尝试真实 API 登录。
4. 从 UI 启用 bob并打开审计，检查 reset/disable/enable 三类动作，reset 的 actor UUID=0001、target UUID=0003。
5. 退出 admin，从 UI 登录 bob，以临时密码完成首次改密到 `TEST-ONLY-Bob-New-42!`，保存本次 token。
6. 经独立真实 admin API 再重置 bob；先断言该保存 token 401，再退出进程/启动，等待 `invalid_session`、登录页及本地凭据删除。
7. 重新登录 bob，保存新 token；经 admin API 停用 bob；同样检查 token 401，重启 App 不恢复身份、显示无效会话并删除凭据。

**独立预期：** 重置撤销既有会话，临时密码要求改密；停用后登录403；审计对象/操作者正确。两种服务端撤销都不能以本地 token 或缓存身份绕过服务验证。用于制造撤销的 API 仅控制外部真实服务，恢复失败必须从 App UI 断言。

**绑定/证据/状态：** Playwright `E2E-TM001-003`，SOP-014；截图 `TM001-003-01-admin-audit` / `02-revoked-automatic-login`、原始断言事件/真实服务审计与父门禁。dev07开发包该组PASS；正式候选尚未通过；精细TC结果见独立run，旧Swift CI仅为历史证据。

## E2E-TM001-004 · 同机更新、拒绝非法包和真实重启

**验收：** `AC-TM001-004`，默认同机更新清单、HTTP 仅回环、非法下载/重定向/签名拒绝，有效包经 Electron macOS 原生更新器安装并自主重启，随后从真实服务恢复账号。

**前置/数据：** 计划中的 Electron `tm001_update_packages` fixture、打包程序与 alice 账号。最终 DMG 中的候选为 0.1.0/build100，受控高版为 0.1.1/build101，两个 App 用同一固定代码签名身份；高版仅供本例升级，不是分发版本。固定 Ed25519 公钥随候选资源发布，私钥仅由本机私有打包程序读取，不交测试进程、App 或 Git。更新 JSON 元数据明确 zip 的版本/build、字节数、SHA256 与独立 Ed25519 签名；预验证还须核对签名 App 的 Info 版本/build 与元数据一致。runner 独占本例动态回环 API/更新端口，以 nonce 核对源归属；四阶段共用同一源。更新源无造数 SQL，账号库仍由共用程序生成。旧 [update_source.py](../../../tests/e2e/update_source.py)和 [build_update_fixture.py](../../../apps/macos/build_update_fixture.py)仅作历史实现参考，不能直接充当新元数据/包生成器。

**步骤：**

1. 从最终 DMG 安装 build100 后首次启动，检查 UI 默认清单 `http://127.0.0.1:49177/version.json`，且无凭据时没有向已占用的默认 API 发认证/写请求。在登录前通过真实 UI 分别选择本例动态 API 与更新源；登录 alice、改密并保存当前 token，仅在测试进程内存比较。核对通用工作目录和同级 runtime 归属文件均为本例所有。
2. fixture 切换 forbidden 元数据，其 zip URL 为非回环 `http://example.invalid/update.zip`。点击真实 UI 检查更新，断言 `update_source_rejected`、无该包请求、仍为 build100；不能以 DNS 失败代替下载前 URL 拒绝。
3. 切换 redirect 元数据：本例回环 zip URL 返回 302，目标为同一非回环 HTTP 地址。点击 UI 检查/安装，断言 `update_transport_rejected`、请求停在本机重定向响应、不跟随外域且仍为 build100。Electron/Node 不使用旧 Swift Foundation ATS 的 `-1022` 错误码。
4. 切换 invalid 元数据，下载实际完整 zip，先核对网络字节数/SHA256，再使固定 Ed25519 验签失败；UI 显示 `update_signature_rejected`，证据证明未交给原生更新器，原 App 保持 build100。
5. 切换 valid 元数据；从 UI 检查并确认安装。预验证核对字节数/SHA256、Ed25519 和签名 App Info 版本/build，随后将已验证 zip 交给本例拥有的临时回环 Squirrel feed，由 macOS 原生更新器执行替换与自主重启。
6. 测试只观察旧 PID 退出及**App 自己**启动的新 PID，不调用 `electron.launch` 或其他命令手动启动高版。重新连接新进程，核对真实安装路径与高版 App/zip 摘要、build101、同一 runtime 文件及 0700 profile；无需输入密码显示 alice，并刷新触发真实 `/v1/me`，核对会话和动态 API/更新地址仍保留。
7. 核对同一源的 forbidden→redirect→invalid→valid 控制与请求顺序、每阶段原始 UI 事件、服务审计、代码签名和清理。任一异常、外域请求、未自主重启或路径回落均阻断。

**独立预期：** 四阶段完整且顺序正确；前三阶段均保留 build100，只有最后已验签包进入 Squirrel 并自主重启至 build101。固定公钥不因配置源而变化，回环 HTTP 许可不扩展到其他主机。升级后同一 profile 的自动登录仍由真实服务确认；高版测试包不作为稳定分发版本。

**绑定/证据/状态：** Playwright `E2E-TM001-004`、SOP-014/017；原始断言事件、四阶段截图/trace、脱敏请求记录、metadata/zip/App摘要和签名、旧/新PID、实际路径/profile、`/v1/me`审计与独立父门禁。dev07开发包该组FAIL，`new_process_profile_files`断言未满足且汇总缺升级资产；正式候选尚未通过；精细TC结果见独立run，旧Swift/Sparkle CI仅为历史证据。

## E2E-TM001-005 · 生产首建管理员与测试数据隔离

**验收：** `AC-TM001-005`，空生产库只预置 admin/123456，强制改密，已有密码不得因再次启动而重置。

**前置/数据：** `production_bootstrap`，由 [bootstrap_sqlite.py](../../../scripts/bootstrap_sqlite.py) 在本例私有临时根建立生产布局和 SQL；不是用户的 `database/production/production.db`。首建账号 UUID 尾号0005、username=`admin`、role=`admin`。生成的 `seed.sql` 只含随机盐密码散列及首建审计，拒绝非空库重放。

**步骤：**

1. runner 在本例私有根由同一生产初始化程序建立**合成同构** SQLite，先备份/恢复到另一隔离副本并验证完整性，不接触用户实际生产库。为本例动态端口启动真实服务；通过该 API 用 admin/123456 登录，确认 must_change_password=true，访问管理员列表应403且 `password_change_required`。
2. 从最终 DMG 启动真实 App，先检查无凭据首启与内置默认地址，然后在登录前经真实 UI 改为本例动态 API；以同一 admin 首登，检查强制改密 UI 和 admin 身份，管理员入口暂不可见。
3. 改为约定至少12位新密码；检查管理员入口出现；旧 token 和123456均401。
4. 打开账号列表，检查只有 admin，没有 `test-*` 管理行；独立 API 用户列表必须恰好一个用户，UUID0005、must_change_password=false。
5. 退出进程/启动，检查自动恢复 admin；主动退出再以新密码登录，刷新身份成功。
6. 首建程序的服务回归另验证已有库拒绝再次初始化、重启服务不重建库、不重置改后密码；该回归结果不能代替上述桌面 UI 过程。

**独立预期：** 安装后桌面 UI 和 API 均证明首建身份/角色与强制改密；合成生产副本无四个测试账号；新密码跨 App/服务生命周期有效。备份与恢复的 schema、账号及非敏感行内容一致。只归档无会话初始副本与脱敏验证，不上传密码散列或 token。

**绑定/证据/状态：** Playwright `E2E-TM001-005`，SOP-010/014；三张 `TM001-005-*` 截图、隔离库/SQL与备份恢复摘要、原始UI断言、bootstrap/服务审计和父门禁。dev07开发包该组PASS；正式候选尚未通过；精细TC结果见独立run，旧Swift CI仅为历史证据。

## E2E-TM001-006 · 默认/可配地址和跨服务会话边界

**验收：** `AC-TM001-006`，默认本机 API，可配置且重启保留；会话按规范化 origin 隔离；更新地址成对校验、持久化和恢复默认。

**前置/数据：** 两套真实 FastAPI/独立 SQLite，分别使用 runner 独占的两个动态回环端口，第一套 seed42、第二套 seed43；第二套 alice 密码 `TEST-ONLY-alice-43!`。两库由 `auth_accounts` 从空环境生成。最终 DMG App 无测试认证旁路，固定 Ed25519 公钥及内置 API/更新默认值来自受签名资源。默认49176上的用户生产服务不是本例 fixture，禁止登录或写入。

**步骤：**

1. 无凭据首次启动后，从登录页与配置页读取内置 API `http://127.0.0.1:49176` 和更新清单 `http://127.0.0.1:49177/version.json`，检查尚未向已占用49176发送认证/写请求。随后通过真实设置 UI 把 API 改为第一套动态地址。
2. 配置页输入第二套动态 API，但同时填非回环 HTTP 更新 URL；保存应报 `invalid_update_source`。取消关闭后 API 仍为第一套动态地址，证明先验证两项再写入。
3. 用第一套 alice 登录，独立断言该 token 在第一套200、第二套401；重启恢复，退出后删除第一套凭据。
4. 登录页改为第二套动态地址；用 seed43 密码登录并改密，先证明这个密码在第一套不能登录。检查第二 token 仅在第二套200，第一套401；两 origin 的凭据文件路径不同。
5. 重启自动恢复第二套身份并刷新；退出后地址仍为第二套、该 origin 凭据清除。
6. 配置页逐一保存非回环HTTP、带userinfo和65536非法端口的更新地址，均应拒绝；保存本例拥有的 `http://127.0.0.1:<动态端口>/configuration-only.json`，重启检查覆盖保留。另验证合规非回环 HTTPS 地址可保存但本例不连接它，随后恢复本例地址。
7. 检查更新按钮可用、配置页没有公钥编辑入口，保持构建时固定公钥。编辑另一个 URL 后取消不保存；点击恢复默认，API与更新源都回到内置49176和49177/version.json，重启后从 UI 核对；此时不进行登录或更新检查，避免触及用户现有服务。
8. 登录页尝试非回环HTTP API，必须为 `invalid_server`；以 HTTPS 请求第二套纯HTTP测试服务，应通过地址校验但在TLS/网络失败并显示无法连接，不能误报地址非法。

**独立预期：** 默认 UI 值真实而未接触用户生产账号；两个动态服务的路由、密码、token和保存路径同时证明隔离。失败的双地址保存不能部分提交；取消不保存、手动覆盖跨重启保留、恢复默认删除覆盖。更新URL配置不能改变受签名资源中的固定公钥；纯配置HTTPS接受不证明某个远端服务已连通。

**绑定/证据/状态：** Playwright `E2E-TM001-006`，SOP-014；`TM001-006-*`三张截图、两份fixture/服务及origin归属摘要、原始UI断言与父门禁。dev07开发包该组PASS；正式候选尚未通过；精细TC结果见独立run，旧Swift CI仅为历史证据。

## 覆盖解释与证据查询

从 [总索引](README.md) 进入机器[验收清单](../../../tests/acceptance.json)和[功能矩阵](../../../tests/feature_matrix.json)可核对六个ID。服务端与新桌面组件测试覆盖固定时钟、散列/权限、非法文件和网络失败等边界，完整六例则从最终安装 App 操作真实 UI；两类结果分别记录，不互相替代。

历史 [PR #2](https://github.com/lzhe72/TokenMeter/pull/2) 的 XCUITest PASS 对应 SwiftUI 候选。Electron早期开发包曾有六组五PASS、升级004 FAIL及精细批次FAIL/BLOCKED，原件均保留。最新开发包的逐TC、11条辅助及六组补充结果已完成联合复核，见[本版实际测试结果](../../../releases/v0.1.0-20260929T074814Z/07-test-results.md)；该包来自未提交工作树，不形成正式通行证。须固定干净候选并从最终DMG重新运行完整本机父门禁，才能判断发布资格。
