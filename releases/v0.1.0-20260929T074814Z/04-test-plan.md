# v0.1.0-20260929T074814Z — 测试计划

## 范围和追踪

REQ-TM001 / TM-001；应执行六个目标场景，当前没有此前已交付产品功能。独立验收来源为 [产品规格](../../docs/product/README.md) 与 [验收清单](../../tests/acceptance.json)，不得从剩余测试反向删条件。

| 用例 | 任务 | 数据和独立预期 |
| --- | --- | --- |
| TEST-TM001-GOVERNANCE | TASK-TM001-PLAN、TASK-TM001-REVIEW | 结构/基线/追踪/门禁负向回归；只证明工具合同 |
| TEST-TM001-SERVER | TASK-TM001-DATA、TASK-TM001-SERVER | 实际 SQLite + FastAPI；错密/停用/节流/过期/越权/事务/迁移/密码与会话撤销；网络 smoke |
| E2E-TM001-001 | TASK-TM001-SERVER、TASK-TM001-DATA、TASK-TM001-MAC、TASK-TM001-RUNNER | test-alice 首次改密→本人主页→重启真实恢复→退出→旧 token 被拒绝 |
| E2E-TM001-002 | TASK-TM001-SERVER、TASK-TM001-MAC、TASK-TM001-RUNNER | member无管理员入口且API403；错误密码提示；test-disabled不能登录 |
| E2E-TM001-003 | TASK-TM001-SERVER、TASK-TM001-MAC、TASK-TM001-RUNNER | admin改密后停用/启用/重置bob；bob旧会话失效，新密码须改密；UI显示真实审计 |
| E2E-TM001-004 | TASK-TM001-UPDATE、TASK-TM001-RUNNER | 真实HTTPS隔离源，拒绝签名损坏包且原版不变；有效高版本包替换并重启，/me验证原账号仍可用 |
| E2E-TM001-005 | TASK-TM001-DATA、TASK-TM001-MAC、TASK-TM001-RUNNER | 在隔离生产库副本运行首建程序；真实 App 以 `admin / 123456` 首登、改密、进入管理员界面；服务端核对仅有 admin、无 `test-*`，再次初始化不得重置密码 |
| E2E-TM001-006 | TASK-TM001-MAC、TASK-TM001-RUNNER | 第一个隔离 FastAPI/SQLite 服务绑定 `127.0.0.1:49176`，另一个隔离服务使用独立临时端口和库；原生 App 首开显示默认地址并登录第一个服务；退出后在 `auth.server` 改为第二服务、登录并重启确认沿用该地址；核对旧源 token 没有发送给新源，非回环 HTTP 显示校验错误，HTTPS URL 可保存为配置而不要求连接不存在的生产服务器 |

## 账号、数据和重置

四个固定 UUID（尾号0001–0004），用户名 test-admin/test-alice/test-bob/test-disabled；角色admin/member/member/member，disabled停用，初始均强制改密。口令仅在隔离 fixture；固定 `database/test/test.db` 只供 Codex 本机回归检查，自动原生用例每次运行创建新临时测试库并由真实CLI迁移/导入，以避免相互污染；禁止连用户生产库、扫描真实Codex/Claude日志或在App预埋测试登录。

另对生产首次初始化程序进行独立服务回归：在隔离副本验证仅预置 `admin`、`123456` 能通过真实认证接口登录、返回首次改密标志且改密前管理接口拒绝；完成改密并加入成员后重新创建服务实例并执行只读检查，确认新密码和成员均保留。验证测试造数 SQL 只写入匹配环境的空测试库，生产库不出现 `test-*` 账号。第005例再用原生 App 驱动同一类隔离生产库副本；服务/数据库回归不能替代这例原生 E2E。

账号配置和expected按固定seed42生成；真实密码 hash 使用随机盐，逻辑账号可重建但不要求安全散列逐字节相同。数据源与生成产物摘要均记录。重置只允许带所有权标记的本次目录，拒绝symlink/外来文件；更新私钥和测试CA只在隔离目录，不能提交或上传。

第006例复用 `auth_accounts` 的合成角色与密码，通过 runner 从空目录分别初始化两份测试 SQLite 和两套真实 FastAPI。第一套独占 `127.0.0.1:49176`，不得读取或重置 `database/production/production.db`；若本机已有用户生产服务占用该端口，记录 BLOCKED，先安排可验证的隔离测试窗口。第二套账号 ID/会话独立，记录两个数据库与响应摘要作为路由独立预期。启动前校验端口归属，结束时仅清理本次拥有的进程、数据库、Keychain 和 UserDefaults 测试域。正式安装包验收需再次验证默认值，不能以测试构建的注入地址代替。未来生产域名迁移不属于本版六例，按 TM-010 的计划条件验证。

## 执行方案与证据

测试实现前的接口失败记录由pytest产生；native测试以XCUITest驱动真实App→API→真实账号库。核心链路不得mock。每例重置数据、退出App并清隔离Keychain以免互相污染。native run保存原始xcresult、逐例状态/截图、App/service/fixture/source摘要、候选SHA、运行nonce/时刻；比较预期集合与原生标识，无失败、缺失、跳过才可通过。

本机Python检查可执行；本机native运行受完整Xcode缺失阻塞。迭代在明确的macOS15 arm64与Intel托管runner执行完整六例；发布仍须macOS14最低版本和所有声明支持的OS/架构，以及独立生产SQLite文件的初始化/备份/恢复、最终签名/公证。不能把开发矩阵通过当作正式支持范围通过。

数据/测试程序初始未建立，因此manifest与矩阵保持空绑定并登记任务，入口真实建立后同步。程序就绪不等于已执行，测试不齐全时禁止将功能标implemented。适用SOP：009→010→011→012→013→014，更新验证017，发布判定018。

## 隔离签名、HTTPS 与异常恢复回归

按009/010验证GitHub托管Mac身份、固定版本`cloudflared`的SHA256、同一临时Keychain身份可用、回环TLS由临时CA校验、公开Quick Tunnel HTTPS由系统客户端校验。fixture拒绝普通开发机、自托管、未校验下载、关闭任一段TLS校验或写入系统信任；本机账号原生重跑若将来具备Xcode，可另按本机前提执行，但004必须先有经验证的独立fixture，本轮以两架构托管CI的原生证据为准。候选包与高版本包必须有相同签名要求；无效EdDSA包不得替换原App，有效包必须完成真实更新、重启及Keychain会话恢复。随机Bearer保护控制切换，未授权POST要拒绝；公开源只服务合成appcast、包和受控请求，不泄露私钥、账号或数据库。逐项核对临时隧道进程、HTTPS服务、Keychain列表及专用Keychain清理；命令失败/超时记录操作名，不打印口令或私钥。增加主操作与清理同时失败的回归，两个原因都保留；资源未创建时先验证不存在。工具回归和环境探针READY仍不能替代004实际原生执行。

保留旧admin信任撤销超时的失败证据，增加负测确保新程序完全不调用系统/管理员信任写入。环境报告保留SOP、release_id、真实提交及dirty状态；第004例探针失败必须阻断完整门禁，001–003和005–006的真实PASS不能补齐缺失场景。探针置于004前，避免无依赖的账号场景失去实际运行证据。针对随机域名在180秒内仍无法由系统解析的阻断，工具回归需用模拟DNS响应证明：Cloudflare或Google任一HTTPS DNS源尚无A记录时绝不开始系统探针；两方就绪后仍必须用系统DNS/TLS核对公开源；共享180秒窗口内DNS未发布或系统检查不就绪均BLOCKED；不得把公共DNS返回IP注入App或curl。环境单独诊断记录为零产品用例、无合并或发布资格，不能代替本候选完整六例。Quick Tunnel暂时不可用按环境BLOCKED记录，不能重试取绿并复用其他候选结果。

## 判定

确定性断言失败=FAIL，缺工具链、数据或有效证据=BLOCKED；PASS必须真实执行全部集合。发布单独要求平台/签名/可信CI证据齐全。机器报告不能由agent手写；缺条件不阻止独立子任务，但不能合并冒称完整产品迭代。

## 更新包输入负测

`python3 -m unittest discover -s apps/macos/tests -p 'test_*.py' -v` 验证更新包程序拒绝非HTTPS源、ad-hoc身份、非本机明文API、错误权限/畸形私钥、符号链接和已有输出。这些隔离工具测试不替代真实Mac构建、签名校验和004更新用例。
