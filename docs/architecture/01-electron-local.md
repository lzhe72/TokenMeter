# 01 · Electron 本机开发、测试与本地发行

版本：`v0.1.0-20260929T074814Z`。用户2026-09-30确认采用DataBuddy同类Electron + Playwright方案：默认本机开发、测试、打包、发布；Git只保存代码、文档和版本追踪；最终DMG与执行证据保存在本地，不上传GitHub。多环境Actions仅在用户明确要求时启用。本版尚未发行，沿用原release_id；原SwiftUI、XCUITest及云端包门禁作为历史实现保留，不能代表新客户端已通过。

## 需求与验收范围

继续交付TM-001全部六例：预置账号/强制改密、权限、管理员重置停启与审计、设备自动登录、生产首建admin、服务地址配置和真实更新。FastAPI、SQLite、造数SQL、固定种子与独立预期复用；不把迁移解释为减少测试。后续采集/统计功能仍为planned。

当前实际可验平台为用户本机macOS15.7.4 x86_64；本轮仅签发该实测平台通行证，不声明arm64或其他系统已通过。完整Xcode不是前置条件，使用已有Node24/npm11、预编译Electron、Playwright与macOS系统工具；锁定依赖版本并保留lockfile。原生模块新增时单独核对ABI/CLT要求。

## 客户端与进程边界

`apps/desktop/`采用Electron主进程、preload与React/TypeScript界面；Vite + electron-vite构建、node:test基础测试、electron-builder打包。参考DataBuddy架构，依赖采用实际核对过的维护版本并锁定，不因参考清单而固定过期Electron33。不引入无当前业务用途的Monaco。UI标识沿用旧Swift用例名称作为`data-testid`。主进程持有API会话及所有Authorization头；renderer只收到公开账号、列表、状态和错误代码，不能得到token或任意文件/HTTP接口。

开启contextIsolation与sandbox，关闭nodeIntegration；preload仅暴露明确业务方法，逐方法校验参数，主进程验证同一窗口/主frame/自有页面来源。静态UI通过自有协议加载，禁止外部导航和新窗，CSP不允许renderer直接访问任意网络。功能测试经真实IPC到真实FastAPI与SQLite，禁止mock认证、数据库或成功响应取代E2E。

固定业务接口为`snapshot/login/changePassword/logout/retryLogout/refresh/listUsers/manageUser/listAudit/saveConfiguration/resetConfiguration/setAutomaticLogin/checkUpdates/installUpdate/onState`；账户字段和API沿用现有服务。服务端继续是权限判定方。

## 用户数据与隔离

默认用户数据在当前用户Application Support/TokenMeter；token目录0700、文件0600、同uid、拒绝symlink/硬链接、按规范化API origin隔离、原子替换，只存token不存密码。首登默认勾选自动登录；启动有凭据时经`/v1/me`验证，失效清理，网络失败不伪造登录；关闭自动登录只保留内存。退出先清本地，再撤销服务会话，失败保留明确重试状态并锁定服务地址。

正式App支持通用`--user-data-dir <绝对路径>`作为独立工作目录，不是测试认证入口。main在ready与任何网络/存储前验证目录并`app.setPath('userData', ...)`，sessionData/cache/log也放此目录。无token的干净profile在用户登录前不向默认API发送登录/写请求。

TM002已确定使用`safeStorage.encryptStringAsync`保存用户所选来源的加密locator。macOS Keychain在profile目录之外，故`--user-data-dir`不能单独证明测试与用户正式TokenMeter凭据隔离。[Electron 44.5.1 源码](https://github.com/electron/electron/blob/v44.5.1/shell/browser/electron_browser_main_parts.cc)显示`PostCreateMainMessageLoop()`将Browser Name用于`KeychainPassword`的service/account；[Electron safeStorage文档](https://www.electronjs.org/docs/latest/api/safe-storage)确认异步API在macOS使用Keychain并延迟初始化。这两项仅支持设计隔离方案，尚不证明异步提供者在本项目最终DMG中的实际item身份。TM002/003/004在本机同用户E2E前须按SOP-009在隔离测试账号或经证明独立的Keychain命名空间，对**同一最终DMG**原生核对实际service/account（或等效标识）及签名访问边界；进入目标用户环境前再按SOP-010确认精确测试item不存在并记录本次owner。若不能证明与正式item分离，相关E2E保持BLOCKED。只读观察和清理限本次测试item，不读取密钥值、不碰正式item；源码依据与最终包运行证据分开记录。

Squirrel原生重启不保证保留argv，因此显式工作目录首次登记在App同级`TokenMeter.runtime.json`：文件0600、同uid、非symlink、仅绑定当前规范化App路径与既存0700 profile。启动先读取并校验此文件；损坏、替换或无归属时硬失败，不能回退到用户默认目录。它在.app外，不随包更新替换。默认用户安装不带此文件；测试只在自己创建的安装父目录写入。E2E从同一分发包验证初装和自动更新后的实际profile路径相同。

当前本机49176已有用户生产服务，旧`/Applications/TokenMeter.app`也在运行；本轮不得终止、覆盖或用其造数。每例动态分配独占回环API端口，经真实配置UI选择；006先检查首次UI的内置默认，再切两个隔离服务验证登录/持久化/origin隔离。004更新源也可用独占动态端口，经真实UI配置。默认API仍`http://127.0.0.1:49176`，默认更新清单为`http://127.0.0.1:49177/version.json`。旧Sparkle XML不作为新客户端输入。

## 更新、签名与打包

采用Electron成熟的macOS原生autoUpdater/Squirrel完成包替换和自主重启，前置轻量验证层保留稳定Ed25519信任：检查更新URL、每次重定向、包长度/SHA256及独立Ed25519签名，只有完整验证的包才交给本次拥有的临时回环feed；Squirrel再校验代码签名与原App designated requirement。electron-builder以publish=never构建目录包，再用成熟签名工具处理嵌套框架，hdiutil制作DMG供安装，ditto制作ZIP供原生更新。禁止自写绕过签名的替换器或把下载成功当成安装成功。

清单合同：`{schema_version:1,version,build,url,sha256,bytes,ed25519_signature}`，Ed25519签名对象为ZIP原始字节。元数据自身不是已签名声明；下载前限制大小，验摘要和签名后安全解包、校验App代码签名/旧版指定要求、实际Info版本/build与清单一致及严格递增，才能准备安装。不能因清单自称高版本就展示安装成功。私钥仅打包读取，不交测试执行器。

仅精确回环HTTP可用，其他地址必须HTTPS；拒绝userinfo/query/fragment、非法端口和空host。对非法下载URL、非回环HTTP重定向、坏Ed25519签名分别提供可区分的错误状态，原App保持可用；有效更新真实下载/安装/退出/重启，恢复原profile及`/v1/me`身份。

更新控制器位于`apps/desktop/src/main/updater.ts`，导出`createUpdater({app,profilePath,buildInfo,getFeed,onChange})`，返回`snapshot/check/install/cancel`。状态含phase、canCheck、canConfigure、status、errorCode、availableBuild、availableVersion；主进程将事件映射到UI。资源`release-config.json`包含release_id、version、build、api_url、update_feed_url、update_public_key与签名证书摘要，打包验证其与源码配置一致。

候选版本0.1.0/build100；首版无上一稳定包，同源码构建受控0.1.1/build101仅用于升级试验，不能作为最终发布包。固定自签证书/Ed25519私钥保存在本机私有目录，只有打包进程读取；不进入Git、报告、App或测试fixture。需要临时钥匙串时仅导入本次私有临时库并恢复列表，不修改系统信任。候选和升级包保持同一签名身份；自签与Squirrel兼容须先真实探针，再完整包E2E，失败即阻断。

成熟库文档中尚未发布的签名清单字段不能冒充当前稳定依赖能力。2026-09-30查明electron-updater6.8.9没有next文档的updateManifestPublicKey；因此明确使用前置Ed25519验证层。原生替换仍交成熟实现。

## 执行与证据合同

以下程序已建立，当前仅完成开发包诊断。最新六个聚合场景组为五组PASS、升级004 FAIL；新增精细TC尚未执行。正式候选须先完成文档基线、程序与数据绑定，再按本合同运行并核对原件：

| 步骤 | 现有入口 | 责任与输出 |
| --- | --- | --- |
| 客户端构建/基础测试 | apps/desktop 的 npm build/test | 固定依赖、静态UI/主进程与单元结果 |
| 本机构建与镜像 | scripts/local_package.py | 固定候选SHA、原App/DMG/100及101zip、签名/资源与package-manifest |
| 安装包全量E2E | scripts/local_e2e.py | 安装同一DMG内App，Playwright六例、真实服务/SQLite、原始JSON/trace/截图/清理 |
| 父级机器门禁 | scripts/local_gate.py | 独立复读原始结果、精确用例集/fixture/哈希/平台/时间/清理，PASS才生成passport |
| 本地发行归档 | scripts/local_release.py | 原包原证据原通行证复制到本地版本目录并读回摘要，不上传GitHub |

E2E顺序001/002/003/005/006/004，每例新SQLite、新profile和独立安装位置。只允许操作自己启动的App/服务，finally核对退出、端口、镜像和目录清理。第五例用生产初始化程序建立合成同构副本，备份恢复后核对真实登录；不访问用户生产库。第004例同一源依次给非法URL、坏重定向、坏签名、正确高版本包；检查旧PID退出、新PID/路径/版本、profile、会话恢复与包摘要。升级后测试只能重新连接已经自主启动的进程，不能手动launch高版造成假通过。

Playwright使用安装后的`Contents/MacOS/TokenMeter`作为executablePath，不依赖开发服务器；保留正式包测试所需的inspector fuse，显式开启chromiumSandbox。平台系统许可/签名/Gatekeeper单独记录真实结果，不把DOM点击或stub原生dialog当系统验证。若打包配置导致无法驱动原包，记录BLOCKED并修复。

顶层报告含schema、scope=final_package、distribution_profile=internal、source_commit/working_tree_dirty、run_id、时间、实际host/arch、所有包摘要、expected/executed/passed六例、suites、清理结果且release_eligible=false。每例关联原始Playwright JSON、断言事件、截图/trace、fixture/SQL摘要、服务审计/脱敏DB验证；004附请求序列与真实重启证据。证据只在0700本机目录，合成凭据不得推Git。父级不信任手写PASS字段，原始报告缺例/失败/重试取绿/跳过/零例/哈希不符均不放行。

## Git与本地发布

源码形成干净候选后才执行最终包验证，机器记录候选完整SHA与tree。构建成功的开发/候选DMG以`NOT-RELEASED`文件名复制到根`dmg/<release_id>/`方便定位，原件仍按候选独立保留并接受安装测试。门禁PASS后将同一原包与原证据归档到`dmg/<release_id>/release-archive/`，并将已验证正式DMG原名放在同一版本目录，不覆盖同名旧文件。安装给用户的版本必须是该候选100，不能重新构建并借用旧报告。Git Tag可作为源码版本索引；不创建GitHub Release、不上传DMG、zip或原始报告。签名钥匙、数据库、node_modules、build输出和本地发行产物均被忽略，目录说明文件随Git保存。

各需求分支由总控按依赖顺序集成本地`master`，为每版固定不可变SHA/tree里程碑，再从该版干净里程碑构建最终包、执行完整本机E2E与机器门禁。PASS后按SOP-020先把同一原包、通行证和原始证据归档为本机正式稳定包，下一版从这份原包真实升级。全部目标版本本机稳定后，总控一次按远端保护通过受控PR登记源码，核对每版里程碑仍在远端祖先链、来源tree及Tag映射；不同则阻断相应远端登记并重新验证。原包始终绑定实际被测里程碑，远端源码登记待办不被写作本机包门禁失败，也不冒充已完成Git发布。

2026-10-01按用户本机测试、Git仅做源码版本管理的决定，远端`master`旧三项GitHub Actions required checks已移除并保存前后读回；当前仍强制PR、管理员执行及对话解决，禁止强推/删除。SOP-019要求每次集成前只读核对实际保护与远端基线；本机最终候选门禁保持原要求，不将本机通行证改写成GitHub检查PASS。

GitHub工作流默认禁用自动触发；明确多环境需求时按当时矩阵单独启用，不因版本发布默认开启。本机报告可被同uid修改，因此通行证表示程序核对结果，不宣称第三方不可篡改证明；保存原始日志、摘要和源码追踪即可满足当前内部流程。

## 实施顺序与交接

1. SOP索引/详细规范、AGENTS、版本01–05、功能用例与本设计同步，经structure再baseline。
2. 客户端主进程/界面/隔离与基础失败用例；更新/打包兼容探针；六例Playwright和数据编排并行，接口按本文。
3. 基础检查、真实App启动与业务红测后修实现；总控本地`master`整合所有需求分支，在最终干净候选上构建原包并执行完整逐TC与六组补充E2E、父gate验原件。
4. 本版门禁PASS后先按SOP-020在本机归档同一原包、通行证和证据，提供正式稳定DMG供下一版真实升级；全部目标版本本机完成后由总控统一按远端保护登记源码并逐版建立Tag。FAIL/BLOCKED保留诊断并修复，不签发通行证。

文件所有权：客户端agent负责apps/desktop除updater/e2e；打包agent负责src/main/updater.ts与local_package.py及对应基础测试；E2E agent负责apps/desktop/e2e、local_e2e.py及其负测；整合者负责规范/文档、local_gate/local_release与Git。不得覆盖另一个agent的修改。

## 依据

- [Electron前提](https://www.electronjs.org/docs/latest/tutorial/tutorial-prerequisites)：预编译运行时与Node/npm。
- [Playwright Electron](https://playwright.dev/docs/api/class-electron)：实验性支持、指定executablePath、inspector fuse和原生dialog边界。
- [Electron安全](https://www.electronjs.org/docs/latest/tutorial/security)：进程隔离、IPC与导航校验。
- [Electron自动更新](https://www.electronjs.org/docs/latest/api/auto-updater)：macOS原生更新与签名要求。
- Squirrel重启参数行为由本轮源代码核对；实际同profile恢复仍以原包E2E为准。

## 本轮锁定工具链

已通过npm元数据核对兼容组合：Electron44.5.1、React19.3.0、TypeScript5.9.3、electron-vite5.0.0、Vite7.3.6、plugin-react5.2.0、Playwright1.63.0、electron-builder26.15.3、osx-sign2.7.1、yauzl3.4.0。package/lock实际安装和构建仍需验证；Vite8与electron-vite5的peer范围不符，不能直接拼接各包latest。产物入口out/main/index.cjs、out/preload/index.cjs、out/renderer/index.html，package.main固定主入口。

本地公开构建配置存 releases/v0.1.0-20260929T074814Z/local-release.json，旧internal-release.json保留历史；新配置的构建/签名/URL/架构字段由打包程序严格校验。updater.ts由electron-vite编入主入口，不复制独立未编译模块。

更新UI的check只获取版本元数据，install下载验签后交Squirrel并quitAndInstall。handoff前可中止，交付Squirrel后禁用取消与配置，避免承诺可以撤销系统已暂存更新。Squirrel原生内部回环代理需仅127.0.0.1的NSExceptionAllowsInsecureHTTPLoads例外，不启用NSAllowsArbitraryLoads；Node外部下载仍逐跳执行URL安全策略。

## 父门禁与发布工具边界

`local_gate.py`正式执行先分配唯一run_id和新0700证据根，再调用local_e2e，独立解析本次原始结果（不能传入任意旧报告直接签发）。它检查当前Git SHA/tree/干净状态、包清单与固定配置/锁文件、所有资产实际摘要、macOS/架构、包签名、每例唯一原始Playwright结果和断言/fixture旁证、时间范围及清理。结构缺失为BLOCKED、矛盾/失败为FAIL；均无passport。内部可暴露只读verify函数供治理负测和归档再验证，不能跳过原件核查。

基础负测至少包括漏例/重复、失败/跳过/重试取绿、fixture或原包改动、错误SHA/平台、路径越界/symlink、旧run或时间、未完成清理和零原始结果。质量入口在execution_profile=local_electron时不允许落回native_e2e；未完成绑定返回BLOCKED，完成后委托本地新门禁，保持历史profile兼容仅供明确历史测试。

`local_release.py verify/archive`现在要求显式`--milestone-sha`和`--milestone-tree`，只接收已通过本机门禁的原件；归档前须机器核对干净检出的HEAD精确等于被测提交、本版固定的本地`master`里程碑SHA/tree及其祖先关系、原包和通行证同源，再以独占新目录复制，保留关联的candidate/package/evidence原始层级，生成schema 2读回SHA清单，记录`remote_source_state=PENDING`；该固定里程碑归属检查已由TM-001代码提交`fbab99b`提供，但仍须在最终整合树及真实原包上执行，不能以程序存在声称归档已通过。归档成功后才形成可供下一版升级的本机正式稳定包。全部目标版本完成后的远端受控PR、每版里程碑祖先/来源读回与Tag属于SOP-019后续单独步骤；远端登记收据另存，不改原归档或通行证。Git API写成功或Tag不替代本地发行验证。

## 升级后UI重连诊断接口

Playwright Electron没有attach现有主进程接口，旧ElectronApplication会随Squirrel退出关闭。004使用正式App通用的显式诊断选项，在本次受保护portable侧文件保存随机CDP端口；App在ready前仅为该隔离安装开启127.0.0.1调试监听，升级自主重启沿同一侧文件恢复。正常安装无此选项，不开监听。该接口不注入账号、不绕过登录、不改变sandbox/CSP；侧文件校验与profile一致，端口占用或地址无法限为回环即BLOCKED。

runner先观察旧PID退出、新PID由更新器自动出现，核对进程命令/可执行路径、实际版本和绑定地址，再用chromium.connectOverCDP重新连接已运行renderer验证UI、配置和真实/me恢复；禁止手动启动高版。证据包含新旧PID、监听地址、重连时间与侧文件摘要。结束后只关闭本例进程，核对CDP端口不再监听。

新功能矩阵绑定使用`engine=playwright_electron`、`test_identity=<稳定E2E ID>`与真实测试文件，质量检查核对身份与case.id相同。旧native_test字段仅历史Swift绑定使用，不为新用例伪造XCTest方法。具体程序路径在文件真实建立后更新，in_progress和六项必测身份保持不变。

实际依赖准备：Electron44运行时不再由npm postinstall下载，`npm ci`后执行`npm run runtime:install`；使用仓库.local独立缓存以避免更改用户缓存权限。构建工具与运行时安装分别保留日志，npm成功不代表能启动App。

开发联调可用显式`--development`包/runner，必须记录dirty状态及development/development_package范围，永不签发通行证；用于实际可启动探针和业务失败基线。最终默认流程仍要求干净候选、final_package与完整六例，不能将开发结果字段改成正式结果。

自动发现版本在账号真实验证且已完成首次改密后触发，同一次App启动对账号/源节流，不自动安装。004先由初始204更新源证明自动请求和无更新，再执行四阶段；006仅保存合成地址时先退出会话，避免发往未提供的合成服务器。实际安装始终需要用户点击。

## Squirrel固定用户资源的归属

Squirrel不使用Electron userData作为安装后台缓存：它使用用户NSCachesDirectory下的`org.tokenmeter.TokenMeter.ShipIt`以及同名launchd job。因此仅设置独立profile不足以隔离更新。004前须只读证明两项都不存在，才创建带本次owner标记的0700目录；发现任何已有未知内容或job即BLOCKED，不删除、不覆盖、不改bundleID绕过。升级后核对ShipItState目标确为本次隔离安装，并只清理本次创建的目录/job；无法核实归属保留证据并阻断。

父门禁独立读取004源的请求日志：本次run/case/精确回环origin、时间和阶段顺序，自动发现204，四阶段元数据200，重定向302，坏签名与有效包都实际完整发送并具有原ZIP字节数/SHA256。非法URL不能产生下载。仅有文件摘要而没有真实请求不能证明升级场景已执行。

## macOS界面与图标（用户追加要求）

用户要求按Apple HIG统一界面、优先SwiftUI、执行截图检查并自主修正；产品功能取舍才提问。结合此前明确采用Electron解决本机无完整Xcode的开发/E2E条件，本轮保留Electron，不重新引入XCUITest依赖；使用macOS原生窗口、菜单和系统字体，内容层按macOS15的布局/控件习惯实现，不宣称SwiftUI原生组件。

界面自主决定为侧栏加内容区，账号、权限与服务配置保持原功能。主标题约20–22pt、正文13–14pt、辅助信息12pt；8pt基础间距，组间16/24pt，避免大块网页式表单。统一中性色、系统蓝强调、分隔线和有限圆角；错误/成功同时提供文字和图形，不只靠颜色。支持系统深浅色、键盘可见焦点、表单Enter、弹窗Escape、明确加载/禁用/错误/空状态。保留现有稳定testID和六例业务合同，组件重排不能减少操作与断言。

产品图标采用原创“仪表弧线与三段用量柱”组合，蓝色圆角底和白色主体，无小字，在Dock小尺寸下仍可识别。SVG是可维护源文件，导出1024PNG和macOS多尺寸ICNS，正式包嵌入同一图标；不使用默认Electron图标、不声称复制Apple系统图标。

验证在真实Electron窗口完成：默认与最小760×640尺寸、深浅色、登录/改密/账号列表/配置/更新状态，保存截图并检查拥挤、对齐、滚动及层级；修复后重新检查。视觉检查作为六例产品E2E之外的辅助证据，最终包仍重跑完整六例。图标和样式变更完成后重新打包，开发probe05不用于最终发行。

依据：[macOS平台设计](https://developer.apple.com/design/human-interface-guidelines/designing-for-macos/)、[侧栏](https://developer.apple.com/design/human-interface-guidelines/sidebars)、[布局](https://developer.apple.com/design/human-interface-guidelines/layout)。上面的具体尺寸、配色和图标概念为本项目设计决定。

图标重建命令为根目录`node scripts/build_desktop_icon.mjs`，使用项目锁定Electron渲染SVG并由系统iconutil生成ICNS。正式包独立核对实际ICNS摘要与源文件一致。父门禁检查trace/PNG真实格式、005归档SQLite原件，并在解析和签发前后复核证据与源码一致性。
