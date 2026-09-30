# v0.1.0-20260929T074814Z — 测试计划

## 范围和追踪

REQ-TM001 / TM-001；应执行六个目标场景，当前没有此前已交付产品功能。独立验收来源为 [产品规格](../../docs/product/README.md) 与 [验收清单](../../tests/acceptance.json)，不得从剩余测试反向删条件。

| 用例 | 任务 | 数据和独立预期 |
| --- | --- | --- |
| TEST-TM001-GOVERNANCE | TASK-TM001-PLAN、TASK-TM001-REVIEW | 结构/基线/追踪/门禁负向回归；只证明工具合同 |
| TEST-TM001-SERVER | TASK-TM001-DATA、TASK-TM001-SERVER | 实际 SQLite + FastAPI；错密/停用/节流/过期/越权/事务/迁移/密码与会话撤销；网络 smoke |
| E2E-TM001-001 | TASK-TM001-SERVER、TASK-TM001-DATA、TASK-TM001-MAC、TASK-TM001-RUNNER | test-alice 首次改密→默认自动登录经 `/v1/me` 恢复→关闭自动登录后重启回登录→退出后旧 token 被拒绝 |
| E2E-TM001-002 | TASK-TM001-SERVER、TASK-TM001-MAC、TASK-TM001-RUNNER | member无管理员入口且API403；错误密码提示；test-disabled不能登录 |
| E2E-TM001-003 | TASK-TM001-SERVER、TASK-TM001-MAC、TASK-TM001-RUNNER | admin改密后停用/启用/重置bob；bob旧会话与自动登录均失效，新密码须改密；UI显示真实审计 |
| E2E-TM001-004 | TASK-TM001-UPDATE、TASK-TM001-RUNNER | 执行App同一台Mac固定49177回环源及内置默认feed，拒绝签名损坏包且原版不变；有效高版本包替换并重启，默认开启自动登录时由 `/v1/me` 无交互验证原账号仍可用 |
| E2E-TM001-005 | TASK-TM001-DATA、TASK-TM001-MAC、TASK-TM001-RUNNER | 在隔离生产库副本运行首建程序；真实 App 以 `admin / 123456` 首登、改密、进入管理员界面；服务端核对仅有 admin、无 `test-*`，再次初始化不得重置密码 |
| E2E-TM001-006 | TASK-TM001-MAC、TASK-TM001-RUNNER | 第一个隔离 FastAPI/SQLite 服务绑定 `127.0.0.1:49176`，另一个隔离服务使用独立临时端口和库；原生 App 首开显示默认地址并登录第一个服务；退出后在 `auth.server` 改为第二服务、登录并重启确认沿用该地址；核对旧源 token 没有发送给新源，两个 origin 的持久凭据互不覆盖，配置页保存合法合成更新URL并跨重启保留，恢复默认后显示内置49177地址；非法更新URL与非回环HTTP显示校验错误，合成更新URL无需连通 |

## 账号、数据和重置

四个固定 UUID（尾号0001–0004），用户名 test-admin/test-alice/test-bob/test-disabled；角色admin/member/member/member，disabled停用，初始均强制改密。口令仅在隔离 fixture；固定 `database/test/test.db` 只供 Codex 本机回归检查，自动原生用例每次运行创建新临时测试库并由真实CLI迁移/导入，以避免相互污染；禁止连用户生产库、扫描真实Codex/Claude日志或在App预埋测试登录。

另对生产首次初始化程序进行独立服务回归：在隔离副本验证仅预置 `admin`、`123456` 能通过真实认证接口登录、返回首次改密标志且改密前管理接口拒绝；完成改密并加入成员后重新创建服务实例并执行只读检查，确认新密码和成员均保留。验证测试造数 SQL 只写入匹配环境的空测试库，生产库不出现 `test-*` 账号。第005例再用原生 App 驱动同一类隔离生产库副本；服务/数据库回归不能替代这例原生 E2E。

账号配置和expected按固定seed42生成；真实密码 hash 使用随机盐，逻辑账号可重建但不要求安全散列逐字节相同。数据源与生成产物摘要均记录。重置只允许带所有权标记的本次目录，拒绝symlink/外来文件；更新私钥只在隔离目录，不能提交或上传。

第006例复用 `auth_accounts` 的合成角色与密码，通过 runner 从空目录分别初始化两份测试 SQLite 和两套真实 FastAPI。第一套独占 `127.0.0.1:49176`，不得读取或重置 `database/production/production.db`；若本机已有用户生产服务占用该端口，记录 BLOCKED，先安排可验证的隔离测试窗口。第二套账号 ID/会话独立，记录两个数据库与响应摘要作为路由独立预期。启动前校验端口归属，结束时仅清理本次拥有的进程、数据库、临时凭据文件和 UserDefaults 测试域。正式安装包验收需再次验证默认值，不能以测试构建的注入地址代替。未来生产域名迁移不属于本版六例，按 TM-010 的计划条件验证。

## 执行方案与证据

测试实现前的接口失败记录由pytest产生；native测试以XCUITest驱动真实App→API→真实账号库。核心链路不得mock。每例重置数据、退出App并清理本次 UITESTING 专用凭据目录以免互相污染。native run保存原始xcresult、逐例状态/截图、App/service/fixture/source摘要、候选SHA、运行nonce/时刻；比较预期集合与原生标识，无失败、缺失、跳过才可通过。

本机Python检查可执行；本机XCUITest受完整Xcode缺失阻塞；本机CLT+AX自动化暂无执行器且AX权限未授，只能另列体验/诊断，不替代远端迭代门禁。迭代在明确的macOS15 arm64与Intel托管runner执行完整六例；内部 DMG 仍须 macOS14 最低版本及声明架构、包级安装升级六例回归、生产 SQLite 初始化/备份/恢复和专用自动门禁；公开分发另需最终 Developer ID 签名与公证。不能把开发矩阵通过当作正式支持范围通过。

数据/测试程序初始未建立，因此manifest与矩阵保持空绑定并登记任务，入口真实建立后同步。程序就绪不等于已执行，测试不齐全时禁止将功能标implemented。适用SOP：009→010→011→012→013→014，更新验证017，发布判定018。

## 隔离签名、同机回环更新与异常恢复回归

004在每台GitHub托管Mac各自独占 `127.0.0.1:49177`，启动一组仅本机可访问的更新fixture；先用 `/healthz` 的一次性 source nonce 核对端口/进程归属和来源；发布fixture后才由真实App及请求核验程序检查 `/appcast.xml` 与包响应。候选和受控高版的 `TM_UPDATE_FEED_URL` 均为空，真实App从内置默认 `http://127.0.0.1:49177/appcast.xml` 检查更新；打包helper的计划 `--use-default-feed` 仅在准备URL严格等于默认值时允许。测试私钥只留本次隔离目录，公钥固化在App，保留 `SUVerifyUpdateBeforeExtraction`；先通过鉴权`control/forbidden`发布enclosure=`http://example.invalid/update.zip`，断言App在网络请求前明确`update_source_rejected`且build100；再通过`control/redirect`发布本机`/redirect.zip`，其302指向该非回环HTTP地址，断言ATS `NSURLErrorDomain -1022`并映射`update_transport_rejected`且build100，DNS错误不能代替；再走原`control/invalid`完整坏EdDSA签名包，断言拒绝/build100；最后原`control/valid`有效包，经Sparkle真实安装/重启并确认build101、同一受保护token仍在、`/v1/me`无交互返回原账号。单一 `UpdateSource` 和代码签名身份须保持到全部请求核对后统一 `finally` 清理；不采用公网隧道、公共DNS、测试CA或另一套探针READY。端口占用或准备失败为BLOCKED，不能跳过004或自动重试取绿。UITESTING两个构建继续共用runner本例唯一0700凭据目录，同一 `TMTestCredentialsDirectory` Info.plist键，拒绝symlink、`/var`别名和生产路径；不读旧Keychain。准备快照 `environment.json` 绑定当前run、候选、端口/进程、READY和摘要，`snapshot_stage=preparation`、`cleanup_owner=parent_run_result`；父复核路径与SHA256、原始原生测试和最终清理结果，不能把准备READY当产品PASS。

006在配置管理页以 `configuration.open` 打开 `configuration.api-url/update-url`，保存合法合成更新URL，重启后核对覆盖仍在；`configuration.reset-defaults` 立即删除API/更新源覆盖并显示本版内置值，`configuration.cancel` 只关闭当前未应用输入。两URL需在保存前一并验证；API已登录或退出待确认时锁API编辑与总恢复默认，更新进行中锁更新URL编辑。保留登录页`auth.server`及双隔离API服务/SQLite断言；本例只保存合成更新URL，不连通该地址也不创建第二更新服务。更新URL允许appcast路径，但拒绝userinfo、query、fragment、空host、非法端口；HTTP仅精确回环主机，其他主机须HTTPS。003继续验证退出、改密、reset、disable导致本机凭据失效；001覆盖自动登录开启/关闭、固定30天且不滑动。组件/服务回归不能替代六例真实原生E2E。

本机CLT组件入口 `python3 scripts/test_endpoint_configuration.py` 验证真实Swift地址配置逻辑与边界；程序存在不等于已通过，运行退出码单独归档，不能替代004/006的原生App UI。

004仍只占原一个用例及600秒上限；runner注入`TM_TEST_UPDATE_{FORBIDDEN,REDIRECT,INVALID}_CONTROL_URL`，三条控制URL沿用原Bearer鉴权与固定key，不连接真实公网域名。`.invalid`仅作为非回环HTTP拒绝目标，直接enclosure必须在传输前拒绝；redirect必须因ATS -1022拒绝，不能拿DNS失败或构建号不变的模糊状态取绿。每阶段控制响应与原生结果按顺序留脱敏证据；任一缺失/错序都不PASS。

更新工具负测须覆盖固定公钥不随更新URL修改、坏签名、`SUVerifyUpdateBeforeExtraction`、选中下载URL与重定向不能把非回环HTTP伪装成回环许可、无效/占用端口阻断、无生产数据库/凭据访问、快照篡改或跨候选复用拒绝。`native.xcresult`完整bundle摘要必须在本例所有`xcresulttool`解析和附件导出退出后计算；父门禁在自己重读原始结果前后各逐文件重算全部内容，包括SQLite文件。父级解析时修改bundle的治理负测必须阻断，任一次摘要不符均FAIL。仅下载工具/接口检查不能替代真实App内升级。带`TMTestCredentialsDirectory`的UITESTING包不能分发为用户内部DMG；内部最终包另经017/018包级安装升级全矩阵门禁。

## 判定

确定性断言失败=FAIL，缺工具链、数据或有效证据=BLOCKED；PASS必须真实执行全部集合。发布单独要求平台/签名/可信CI证据齐全。机器报告不能由agent手写；缺条件不阻止独立子任务，但不能合并冒称完整产品迭代。

## 更新包输入负测

`python3 -m unittest discover -s apps/macos/tests -p 'test_*.py' -v` 验证更新包程序拒绝非回环HTTP源、错误或不匹配的默认feed、非法URL、非本机明文API、错误权限/畸形私钥、符号链接和已有输出。这些隔离工具测试不替代真实Mac构建、签名校验和004更新用例。
