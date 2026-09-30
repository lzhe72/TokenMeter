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
| E2E-TM001-004 | TASK-TM001-UPDATE、TASK-TM001-RUNNER | 真实HTTPS隔离源，拒绝签名损坏包且原版不变；有效高版本包替换并重启，默认开启自动登录时由 `/v1/me` 无交互验证原账号仍可用 |
| E2E-TM001-005 | TASK-TM001-DATA、TASK-TM001-MAC、TASK-TM001-RUNNER | 在隔离生产库副本运行首建程序；真实 App 以 `admin / 123456` 首登、改密、进入管理员界面；服务端核对仅有 admin、无 `test-*`，再次初始化不得重置密码 |
| E2E-TM001-006 | TASK-TM001-MAC、TASK-TM001-RUNNER | 第一个隔离 FastAPI/SQLite 服务绑定 `127.0.0.1:49176`，另一个隔离服务使用独立临时端口和库；原生 App 首开显示默认地址并登录第一个服务；退出后在 `auth.server` 改为第二服务、登录并重启确认沿用该地址；核对旧源 token 没有发送给新源，两个 origin 的持久凭据互不覆盖，非回环 HTTP 显示校验错误，HTTPS URL 可保存为配置而不要求连接不存在的生产服务器 |

## 账号、数据和重置

四个固定 UUID（尾号0001–0004），用户名 test-admin/test-alice/test-bob/test-disabled；角色admin/member/member/member，disabled停用，初始均强制改密。口令仅在隔离 fixture；固定 `database/test/test.db` 只供 Codex 本机回归检查，自动原生用例每次运行创建新临时测试库并由真实CLI迁移/导入，以避免相互污染；禁止连用户生产库、扫描真实Codex/Claude日志或在App预埋测试登录。

另对生产首次初始化程序进行独立服务回归：在隔离副本验证仅预置 `admin`、`123456` 能通过真实认证接口登录、返回首次改密标志且改密前管理接口拒绝；完成改密并加入成员后重新创建服务实例并执行只读检查，确认新密码和成员均保留。验证测试造数 SQL 只写入匹配环境的空测试库，生产库不出现 `test-*` 账号。第005例再用原生 App 驱动同一类隔离生产库副本；服务/数据库回归不能替代这例原生 E2E。

账号配置和expected按固定seed42生成；真实密码 hash 使用随机盐，逻辑账号可重建但不要求安全散列逐字节相同。数据源与生成产物摘要均记录。重置只允许带所有权标记的本次目录，拒绝symlink/外来文件；更新私钥和测试CA只在隔离目录，不能提交或上传。

第006例复用 `auth_accounts` 的合成角色与密码，通过 runner 从空目录分别初始化两份测试 SQLite 和两套真实 FastAPI。第一套独占 `127.0.0.1:49176`，不得读取或重置 `database/production/production.db`；若本机已有用户生产服务占用该端口，记录 BLOCKED，先安排可验证的隔离测试窗口。第二套账号 ID/会话独立，记录两个数据库与响应摘要作为路由独立预期。启动前校验端口归属，结束时仅清理本次拥有的进程、数据库、临时凭据文件和 UserDefaults 测试域。正式安装包验收需再次验证默认值，不能以测试构建的注入地址代替。未来生产域名迁移不属于本版六例，按 TM-010 的计划条件验证。

## 执行方案与证据

测试实现前的接口失败记录由pytest产生；native测试以XCUITest驱动真实App→API→真实账号库。核心链路不得mock。每例重置数据、退出App并清理本次 UITESTING 专用凭据目录以免互相污染。native run保存原始xcresult、逐例状态/截图、App/service/fixture/source摘要、候选SHA、运行nonce/时刻；比较预期集合与原生标识，无失败、缺失、跳过才可通过。

本机Python检查可执行；本机native运行受完整Xcode缺失阻塞。迭代在明确的macOS15 arm64与Intel托管runner执行完整六例；内部 DMG 仍须 macOS14 最低版本及声明架构、包级安装升级六例回归、生产 SQLite 初始化/备份/恢复和专用自动门禁；公开分发另需最终 Developer ID 签名与公证。不能把开发矩阵通过当作正式支持范围通过。

数据/测试程序初始未建立，因此manifest与矩阵保持空绑定并登记任务，入口真实建立后同步。程序就绪不等于已执行，测试不齐全时禁止将功能标implemented。适用SOP：009→010→011→012→013→014，更新验证017，发布判定018。

## 隔离签名、HTTPS 与异常恢复回归

按009/010验证GitHub托管Mac身份、固定版本 `cloudflared` 的 SHA256、临时自签代码身份在隔离CI中可用于 Sparkle 包校验、回环TLS由临时CA校验、公开Quick Tunnel HTTPS由系统客户端校验。fixture拒绝普通开发机、自托管、未校验下载、关闭任一段TLS校验或写入系统信任；内部应用的迭代签名不宣称具备内部分发包门禁或公开 Developer ID 公证资格。runner 为每例创建唯一0700临时 `credentials` 目录；以 `TM_TEST_CREDENTIALS_DIR` 注入 build100/build101，Info.plist 的 `TMTestCredentialsDirectory` 与首次启动 XCTest 环境必须指向相同解析绝对路径，不接受 `/var` 别名或 symlink，无效时显式报 `invalid_credential_directory`。候选与高版本测试 App 的 Info.plist 必须保留同一专用临时凭据路径，不能访问生产 `~/Library/Application Support/TokenMeter/credentials` 或旧 Keychain；无效EdDSA包不得替换原App，有效包必须真实安装、重启，默认自动登录经 `/v1/me` 无交互恢复。004须在本例同一活跃 `SigningIdentity` 与 `UpdateSource` 上完成签名、隧道域名准备、公共DNS、系统DNS/TLS与本次 origin `security verify-cert`，随后保留同一域名/CA/Keychain 至真实升级及请求校验结束；统一 `finally` 逐项核对临时隧道进程、HTTPS服务、专用Keychain和凭据目录清理，主操作与清理同时失败时两个原因都保留。准备证据为不可变 `environment.json`，明确 `snapshot_stage=preparation`、`cleanup_owner=parent_run_result`，准备时 `cleanup_completed=false` 不表示最终清理失败；最终清理由父报告证明。父门禁重新核验环境文件的受限相对路径、SHA256、候选提交/dirty、READY、零用例、非发布资格及快照标记，工具回归必须拒绝缺失、篡改和其他候选证据。工具回归和另一次独立环境探针READY仍不能替代004原生执行。

001验证自动登录默认开启、服务器随机token只存本机受保护文件、重启经 `/v1/me` 确认、固定30天过期且 `/v1/me` 不滑动延长；关闭记住时在成功登录接收会话后清除当前origin旧文件，新token仅驻内存，重启返回登录。003验证退出/改密/管理员重置/停用撤销及本地删除；离线退出先本地清除、仅内存待重试撤销并显示未确认，不能假报服务端已撤销。006验证切换服务时凭据按规范化origin隔离且不向第二服务发送第一服务token。测试要覆盖旧预览版首次迁移需重登一次、生产目录0700/文件0600/当前uid、拒绝symlink及异常类型、原子写、超大和畸形token。使用固定时钟与独立expected，服务端和Swift存储边界测试可先验证逻辑，真实App E2E仍须六例完整执行。本机 Command Line Tools 可运行已落盘的真实 Swift 存储边界测试 `python3 scripts/test_device_credentials.py`；程序与 Swift 断言源已登记 manifest，实际通过状态以本次命令结果为准，不能代替六例原生产品 E2E。带 `TMTestCredentialsDirectory` 的 UITESTING App 不可离开 runner 作为本机可登录预览包；打包器必须拒绝，CI 只保留测试 App 压缩件供诊断。内部 DMG 须使用无测试路径的独立配置并按017/018包级门禁验证。

保留旧 admin 信任撤销超时与自签跨版本 Keychain 弹窗的失败证据；当前新程序不得访问旧会话 Keychain 或修改系统/管理员信任。环境报告保留SOP、release_id、真实提交及dirty状态；第004例自身环境准备失败必须阻断完整门禁，001–003和005–006的真实PASS不能补齐缺失场景。004在其他五例之后准备本例活跃资源；独立环境探针仅用于零产品用例诊断，不能在前一次清理后把旧READY赋给新域名。针对随机域名在180秒内仍无法由系统解析的阻断，工具回归需用模拟DNS响应证明：Cloudflare或Google任一HTTPS DNS源尚无A记录时绝不开始系统探针；两方就绪后仍必须用系统DNS/TLS核对公开源；共享180秒窗口内DNS未发布或系统检查不就绪均BLOCKED；不得把公共DNS返回IP注入App或curl。工具回归还须证明004不会调用先创建又清理的独立探针；本例只创建一组签名身份与更新源，准备、打包、升级、请求核验使用同一实例，失败和成功均仅在最终 `finally` 清理，且准备失败不得继续安装。环境单独诊断记录为零产品用例、无合并或发布资格，不能代替本候选完整六例。Quick Tunnel暂时不可用按环境BLOCKED记录，不能换域名、重启隧道、提高180秒窗口或重试业务取绿并复用其他候选结果。

增加首次系统`curl`退出6的确定性工具用例：只触发一次只读DNS诊断；`scutil`/`dscacheutil`/默认与公共`dig`的A/AAAA/`curl --ipv4`均有单项5秒与整组60秒界限，整组占原共享180秒窗口；诊断文件过滤真实搜索域并限制输出长度，失败仍保留原解析错误与BLOCKED。用例须证明不写系统DNS、hosts或证书信任，不用诊断返回IP替代App请求，不重试产品场景。独立环境报告另验证主操作BLOCKED且实际清理成功时`cleanup_completed=true`、`release_eligible=false`、`executed_cases=0`；清理失败则记录错误且不能被主错误覆盖。工具自测不代替新候选两架构第004例原生执行。

## 判定

确定性断言失败=FAIL，缺工具链、数据或有效证据=BLOCKED；PASS必须真实执行全部集合。发布单独要求平台/签名/可信CI证据齐全。机器报告不能由agent手写；缺条件不阻止独立子任务，但不能合并冒称完整产品迭代。

## 更新包输入负测

`python3 -m unittest discover -s apps/macos/tests -p 'test_*.py' -v` 验证更新包程序拒绝非HTTPS源、ad-hoc身份、非本机明文API、错误权限/畸形私钥、符号链接和已有输出。这些隔离工具测试不替代真实Mac构建、签名校验和004更新用例。
