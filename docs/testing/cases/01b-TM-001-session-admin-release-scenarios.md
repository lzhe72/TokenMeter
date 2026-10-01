# 01b · TM-001 会话、管理、配置与安装升级：任务级测试场景

适用版本：`v0.1.0-20260929T074814Z`；需求：`REQ-TM001`。本文是本轮测试设计，**设计状态与每次执行状态分开记录；六项原待定规则已获用户确认**。当前固定程序绑定以`tests/test_cases.json`和变体清单为准，执行结论以[本版结果](../../../releases/v0.1.0-20260929T074814Z/07-test-results.md)及独立run原件为准；旧聚合测试不能充当精细TC证据。

## 1. 依据、范围与执行规则

预期依据依次为[本版需求](../../../releases/v0.1.0-20260929T074814Z/01-requirements.md)的 AC-TM001-001–006 与输入/失败行为、[Electron 本机设计](../../architecture/01-electron-local.md)、[已登记验收清单](../../../tests/acceptance.json)。按[任务拆解](../../../releases/v0.1.0-20260929T074814Z/02-breakdown.md)定义可交付任务，再按本文定义操作和独立预期。代码仅用于核对现有自动化覆盖及缺口；不得用实现返回值生成测试答案。

本文细化[六个聚合 E2E](01-TM-001-accounts.md)中的会话、管理、生产首建、配置及最小更新器，不增加 TM-002–012 的产品范围。聚合 E2E ID 保持稳定；细粒度 TC 必须另有执行记录，不能用一条“六例通过”覆盖未执行的细节。

执行链：[SOP-006 测试设计](../../../sop/SOP-006-test-plan.md)→[SOP-008 基线](../../../sop/SOP-008-baseline-check.md)→[SOP-010 数据](../../../sop/SOP-010-test-data.md)→[SOP-011 自动化](../../../sop/SOP-011-test-implementation.md)→[SOP-012 开发](../../../sop/SOP-012-development.md)→[SOP-013 基础检查](../../../sop/SOP-013-build-and-check.md)→[SOP-014 真实 E2E](../../../sop/SOP-014-e2e.md)。安装升级另执行[SOP-017](../../../sop/SOP-017-package-validation.md)，恢复另执行[SOP-016](../../../sop/SOP-016-database-migration.md)。失败走[SOP-015](../../../sop/SOP-015-bugfix.md)，记录维护走[SOP-024](../../../sop/SOP-024-document-change.md)。

### 1.1 共用真实环境和数据合同

- 本机 macOS15 Intel，安装路径为本轮独占目录中从同一原 DMG 复制的 `TokenMeter.app`，profile 为本轮独占 0700 目录。不能使用用户 `/Applications/TokenMeter.app`、生产数据库、真实凭据或现有 49176 服务；不终止未知进程。界面操作必须经真实 Electron 窗口、IPC、FastAPI 和 SQLite，不用 API/IPC mock 生成成功身份。
- **D-A42**：`auth_accounts`，由 [fixtures.py](../../../tests/server/fixtures.py) `generate(run_id,42,workspace=owned_root)` 与 [local_e2e.py](../../../scripts/local_e2e.py) `make_account_database()` 建立真实迁移后的 SQLite，并实际执行 `seed-42.sql`。账号为 `test-admin/test-alice/test-bob/test-disabled`，UUID 尾号 0001/0002/0003/0004；前者为 admin，其余 member，disabled 停用。初始密码 `TEST-ONLY-<名字>-42!`，均需首次改密。
- **D-A43**：相同程序、独立库和 origin、seed43，alice 初始密码 `TEST-ONLY-alice-43!`。服务 A/B 各绑定自己拥有的动态回环端口；端口号从进程实际监听结果取得并写记录，不预先复用固定端口。
- **D-PROD**：`production_bootstrap`，仅在新私有根调用 [bootstrap_sqlite.py](../../../scripts/bootstrap_sqlite.py) `initialize_production(owned_root)`；只有 `admin/123456`，UUID 尾号0005、admin、启用、强制改密。保留真实生成 SQL 与初始 schema。不得在仓库真实生产根运行首建/重置作为测试。
- **D-UPDATE**：同次构建的0.1.0/build100候选 DMG及0.1.1/build101受控 ZIP，固定代码证书、Ed25519公钥与候选摘要；私钥不交 App/测试进程。`local_e2e.UpdateSource` 与 `scripts/granular_update_validation_fixture.py`提供动态回环源、负面包/元数据及脱敏请求记录；暂停响应由对应固定源控制。绑定存在不等于App E2E已通过。
- 固定新密码 **P-NEW**=`TEST-ONLY-Changed-42!`，重置临时密码 **P-RESET**=`TEST-ONLY-Reset-42!`；其他指定新密码见对应 TC，均是合成数据。所有 token 只在测试进程内存中使用；报告记录状态码、字段是否存在及摘要，不记录原 token、Authorization、明文密码或用户生产散列。
- **SETUP-MEMBER**：用新 D-A42，从真实配置界面改到服务 A；UI 登录 alice 并按强制改密表单改为 P-NEW；等待 `/v1/me` 确认 alice。**SETUP-ADMIN**：同样操作 admin。每个 TC 独立执行前置，不依赖上一 TC 成功留下的状态；同一聚合内共享阶段时必须记录阶段入口快照。
- **RESET**：先保留原始失败、DB非敏感快照、SQL/fixture摘要，再由 runner 的归属检查清理本轮 App/服务/挂载/profile/临时库。`fixtures.reset(run_id,workspace=owned_root)` 仅清理由它生成且文件集、owner/run_id一致的 fixture；不直接递归删除未知目录。需要数据库重置时建立新的拥有根，不重放生产 seed.sql。ShipIt 清理另按 UPDATE-08；清理失败记录 BLOCKED，不能覆盖原失败。

### 1.2 每次运行必须生成的记录

每个 `TC-*` 至少记录 `release_id/task_id/acceptance_id/parent_e2e_id/tc_id/run_id`、候选 SHA/tree、DMG/App/ZIP摘要、环境、程序/fixture/SQL摘要、开始结束时间；**每一步**记录实际动作、固定预期、实际观察、比较结论和原始证据引用。记录实际执行的步骤数、失败步骤、退出码、清理结果及 PASS/FAIL/BLOCKED；缺项和未执行不能写 PASS。

UI 保存对应 trace/截图及断言事件；API 记录方法、路径、状态和允许的非敏感字段；DB 只读查询 schema、用户状态、会话失效/删除结果、审计对象与计数；进程记录真实 PID、可执行路径、退出/启动顺序。SQL/hash快照不能替代界面行为；组件固定时钟测试不能写成真实 App 等待30天。本机报告不声称具有不可篡改认证能力。

下文“绑定”指**当前固定程序入口及仍有的覆盖缺口**。各TC身份与程序绑定以`tests/test_cases.json`及变体清单为准；每次执行按run_id逐项记录，首轮精细全量为BLOCKED，新版正在执行。程序绑定存在不等于TC通过。

### 1.3 数据库只读核验约定

每例下方分别列数据库准备、预期变化和只读核验。以下SQL仅用于本例拥有的SQLite，以只读连接执行；`?`用本例参数绑定，不拼接用户名/token。Q-VALID的token摘要只在测试进程内存计算并绑定，报告只记录0/1计数，不输出token或摘要。密码散列比较同样只在进程内完成并输出相等/不等，不能写进诊断日志。

| 查询编号 | 只读SQL |
| --- | --- |
| Q-USERS | `SELECT id,username,role,is_active,must_change_password,credential_version FROM users ORDER BY id;` |
| Q-SESSIONS | `SELECT user_id,credential_version,COUNT(*) AS sessions,MIN(expires_at),MAX(expires_at) FROM sessions GROUP BY user_id,credential_version;` |
| Q-VALID | `SELECT COUNT(*) FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.user_id=? AND s.token_hash=? AND s.credential_version=u.credential_version AND u.is_active=1 AND s.expires_at>?;` |
| Q-AUDIT | `SELECT action,actor_id,target_id,occurred_at FROM audit ORDER BY occurred_at,id;` |
| Q-OWNER | `SELECT environment,run_id FROM tokenmeter_seed_owner;` |
| Q-SCHEMA | `SELECT version_num FROM alembic_version; SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name; PRAGMA table_info(users); PRAGMA table_info(sessions); PRAGMA table_info(audit); PRAGMA table_info(login_buckets);` |
| Q-INTEGRITY | `PRAGMA integrity_check;` |

撤销通过服务401及Q-VALID=0证明；不假设schema有`revoked`或`created_at`列。系统表/列名用于核验实际存储合同，业务预期仍来自需求。SESSION-07的T0由独立测试时钟记录。

## 2. 具体开发任务及完成条件

任务 ID 均以 `TASK-TM001-` 开头；父任务保留原 SERVER/DATA/MAC/UPDATE/RUNNER 追踪。这些是可验证的交付单元，不能只以“开发账号模块”代替。

| 任务 ID | 明确产出及完成条件 | 前序与对应 TC |
| --- | --- | --- |
| SESSION-PERSIST | 当前 origin 的 token 原子写入受保护普通文件；失败不展示成功身份；不保存密码 | 已有登录/改密合同；SESSION-01/02/10 |
| SESSION-RESTORE | 读取已保存 token 后经真实 `/v1/me` 确认；离线无成功身份，失效清理 | PERSIST；SESSION-03/04/05 |
| SESSION-MEMORY | 关闭自动登录后不读取/保留当前 origin 持久 token，布尔选择跨重启保留 | PERSIST；SESSION-06 |
| SESSION-EXPIRY | 会话固定30天到期，不随访问、服务重启或升级延长 | 服务会话/时钟合同；SESSION-07 |
| SESSION-LOGOUT | 退出撤销当前会话、清理本地；不可达时显示待确认并可重试，API切换锁定 | RESTORE；SESSION-08/09 |
| ADMIN-RESET | UI重置成员密码，强制改密并原子撤销全部旧会话 | 管理员权限；ADMIN-01/02 |
| ADMIN-STATUS | UI停用/启用成员；停用拒绝登录/旧会话，启用不复活旧会话 | 管理员权限；ADMIN-03/04 |
| ADMIN-GUARD | 拒绝自停用、避免最后活动管理员不可用，保持事务原子性 | STATUS；ADMIN-05 |
| ADMIN-AUDIT | 管理动作可查正确操作者、对象、动作，不泄露密码/token | RESET/STATUS；ADMIN-06 |
| BOOTSTRAP-INIT | 合成生产空库由同一首建程序只建admin；UI首登强制改密 | 初始化/迁移合同；BOOTSTRAP-01/02 |
| BOOTSTRAP-PRESERVE | 已有库不能被重新首建或seed覆盖；服务重启保留密码/账号 | INIT；BOOTSTRAP-03 |
| BOOTSTRAP-RESTORE | 备份恢复原件可独立查询且实际App连接恢复副本 | INIT；BOOTSTRAP-04 |
| CONFIG-API | 默认值、API URL校验、规范化origin隔离及覆盖持久化 | RESTORE；CONFIG-01/02/03 |
| CONFIG-UPDATE | 更新URL校验、公钥固定、覆盖/取消/恢复默认的原子保存 | CONFIG-API；CONFIG-04/05 |
| CONFIG-LOCKS | 登录/退出待确认时锁API及总恢复；更新忙时锁更新地址 | LOGOUT/CONFIG-UPDATE；CONFIG-06 |
| UPDATE-DISCOVER | 已验证会话与有效源下自动发现；检查与确认安装分离 | CONFIG-UPDATE；UPDATE-01 |
| UPDATE-VERIFY | 下载地址/每跳重定向、字节数、SHA、Ed25519、App身份/版本在交接前全部核对 | DISCOVER；UPDATE-02/03/04/05 |
| UPDATE-INSTALL | 原生Squirrel替换并自主重启，同profile保留配置并经`/me`自动登录 | VERIFY/RESTORE；UPDATE-06/07 |
| UPDATE-ISOLATION | 本机更新源、ShipIt、进程和文件归属检查与清理，未知资源阻断 | RUNNER隔离；UPDATE-08 |

## 3. 会话与自动登录：10 个精细场景

### TC-TM001-SESSION-01 · 默认开启并安全保存当前会话

**任务/依据：** TASK-TM001-SESSION-PERSIST；AC-TM001-001；E2E-TM001-001。**数据/前置：** D-A42，新安装/profile；SQL与默认地址已记录。SOP-010/014，结束用 RESET。

**类型/输入：** E2E/正向/凭据安全。输入：D-A42 alice初始密码→P-NEW；自动登录默认开启。

**数据库：** 准备：D-A42新迁移库与实际seed-42.sql；预期变更：首次改密后must_change_password=false；旧会话失效，新会话可用；密码/原token不出现在明文字段；只读核验：Q-USERS、Q-SESSIONS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 首启登录页，读取自动登录选项；改连服务A后以alice首次登录并改为P-NEW | 选项默认开启；改密前只能在强制改密界面，改后显示已验证alice |
| 2 | 只读检查当前origin的凭据目录/文件元数据与内容格式 | 目录0700、文件0600、当前uid、普通单链接文件；内容仅随机43字符token，不含用户名/密码 |
| 3 | 在内存中用保存token请求`GET /v1/me`；只读检查DB会话记录 | API200且UUID尾号0002；DB只保存token摘要，不含原token；设置文件只存非敏感自动登录选择 |
| 4 | 保存UI、API状态、文件权限与DB脱敏旁证 | 能按本次run定位同一会话；日志/截图不含token或明文密码 |

**绑定/缺口：** `apps/desktop/e2e/tm001.spec.ts::E2E-TM001-001`、`savedToken()`已有权限/格式检查；DB摘要及逐TC记录需补。状态：设计已定；执行结论按run_id查原件。

### TC-TM001-SESSION-02 · 凭据保存失败不能显示登录成功

**任务/依据：** TASK-TM001-SESSION-PERSIST；AC-TM001-001及“保存失败登录整体失败”。**数据/前置：** D-A42；先仅在本例凭据目标放入自己拥有的同名目录，造成文件原子替换失败，记录原对象摘要；不得改用户权限或系统目录。SOP-010/011/014；RESET。

**类型/输入：** E2E/负向/存储故障。输入：D-A42已改密alice、P-NEW；自有同名目录阻挡凭据写入。

**数据库：** 准备：D-A42完成真实改密，记录账号状态；预期变更：保存失败不得改账号角色/密码；服务可能已签发会话，其撤销策略未在原需求明确，不擅自填数据库已撤销；只读核验：Q-USERS、Q-SESSIONS、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI开启自动登录，用已完成强制改密的合成alice登录 | 真实API可以签发会话，但文件保存失败不得转为已验证主页 |
| 2 | 观察错误、身份区域及凭据目标 | 有可观察保存失败；无已验证alice/管理内容；原归属对象未被破坏，不留下部分token文件 |
| 3 | 结束App，仅移走本例阻挡目录，再启动并尝试自动恢复 | 不凭内存/缓存身份恢复；无有效持久凭据时回登录页 |
| 4 | 用同一真实UI重新登录 | 受保护写入恢复后才允许显示服务确认身份，形成前后对照 |

**绑定/缺口：** 完整UI故障的当前固定程序绑定见`tests/test_cases.json`；文件组件检查不替代真实App失败路径。拥有目录的故障生成、重置及结果逐run核对，不通过mock登录返回值造失败。状态按run_id记录。

### TC-TM001-SESSION-03 · 重启必须等待真实服务确认

**任务/依据：** TASK-TM001-SESSION-RESTORE；AC-TM001-001。**数据/前置：** SETUP-MEMBER、自动登录开启，有本例合法token；SOP-010/014；RESET。

**类型/输入：** E2E/正向/重启恢复。输入：合法当前origin持久token、同一profile、运行中的服务A。

**数据库：** 准备：SETUP-MEMBER，记录expires_at及用户状态；预期变更：/me只读确认，不延长期限或改变账号；启动不重新seed；只读核验：Q-USERS、Q-SESSIONS、Q-VALID。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 记录本例token指纹、origin及服务请求计数，正常退出App后重新启动 | 新进程仍使用本例profile，读取相同origin凭据 |
| 2 | 等待真实服务收到`GET /v1/me`并完成200 | 只有该确认后显示alice已验证身份；不能直接复用缓存的已登录标记 |
| 3 | 点击“刷新身份” | 再次真实`/v1/me`200，验证时刻刷新，角色/账号与独立fixture一致 |
| 4 | 对照服务请求、UI事件和进程路径 | 请求与UI顺序能关联同run、同服务、同新PID，无密码输入或直接注入身份 |

**绑定/缺口：** E2E-TM001-001 `auto_restore/session.refresh` 是历史局部证据；当前SESSION-03固定绑定见`tests/test_cases.json`，确认前后事件顺序和结果逐run核对。

### TC-TM001-SESSION-04 · 离线或超时不得沿用缓存身份

**任务/验收：** TASK-TM001-SESSION-RESTORE, AC-TM001-001。

**已确认规则：** 自动登录15秒超时显示可重试错误，不能使用缓存身份；重试后须经真实/v1/me确认。迟到响应不能覆盖新操作。

**类型：** E2E/异常/离线与超时。**输入：** 合法持久token；仅自己的服务停止/恢复及响应延迟。

**前置/数据：** SETUP-MEMBER；只能停止本例服务A，保存DB；不修改App数据。SOP-010/014；RESET。
已确认规则：自动登录15秒超时显示可重试错误，不能使用缓存身份；重试后须经真实/v1/me确认。迟到响应不能覆盖新操作。

| 步骤 | 动作 | 预期结果 |
| --- | --- | --- |
| 1 | 关闭App并停止服务A，再启动同profile App | 认证连接失败可观察；不能显示已验证alice或开放管理功能 |
| 2 | 对照profile、请求失败和UI状态 | 本地存在token不能充当认证成功；无伪造`/me`200 |
| 3 | 在同地址恢复同一真实服务，按UI提供的重试操作；若尚无入口，登记实现缺口 | 成功恢复必须有新的真实`/me`200，之后才能显示身份 |
| 4 | 用本例可控网络响应延迟达到既定请求超时，再重复恢复 | 15秒超时有可重试错误；迟到响应不能覆盖新操作；重试成功后必须有新的真实/me 200。 |

**DB操作：** SETUP-MEMBER，停服务前保存只读快照；网络故障不能修改用户/延长会话；恢复后使用原库真实确认。只读核验按共用SQL合同，不导出token/散列。

**绑定/状态/证据：** `design_status=designed`；实际绑定由结构化清单登记。`execution_status=按run_id查原件`；每次生成独立原始证据及结果，不继承聚合PASS。SOP-010/011/014；每变体独立环境，按owner/run_id清理。

### TC-TM001-SESSION-05 · 已失效的持久会话被拒绝并清理

**任务/依据：** TASK-TM001-SESSION-RESTORE；AC-TM001-001/003。**数据/前置：** SETUP-MEMBER；在真实服务经admin重置alice或停用alice，两种变体各用新库。SOP-010/014；RESET。

**类型/输入：** E2E/负向/失效恢复。输入：持久token；真实admin重置/停用两变体。

**数据库：** 准备：D-A42，每变体新库，通过真实API制造撤销；预期变更：对应旧会话Q-VALID=0；重置强制改密，停用is_active=false；客户端重启不把旧会话恢复有效；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 先证明原持久token在服务A返回200，再执行相应真实管理员操作 | 操作成功，受影响用户旧会话被撤销 |
| 2 | 独立用原token请求`/v1/me` | 401，不能只有UI隐藏而服务仍允许 |
| 3 | 关闭并重启App，观察恢复请求与界面 | `/me`拒绝后回登录，显示会话失效，无已验证身份 |
| 4 | 检查当前origin凭据并再次重启 | 凭据已删除；不重复恢复旧token，不影响其他origin自有文件 |

**绑定/缺口：** RESET/DISABLE两条独立变体已登记于`tests/granular_login_variants.json`，固定UI程序与文件/服务旁证见`tests/test_cases.json`；结果由各run原件判定，不继承聚合PASS。

### TC-TM001-SESSION-06 · 关闭自动登录仅保留内存会话

**任务/依据：** TASK-TM001-SESSION-MEMORY；AC-TM001-001。**数据/前置：** D-A42，已改密alice；本例保存过合法旧token但当前为登录页。SOP-010/014；RESET。

**类型/输入：** E2E/状态切换/内存会话。输入：D-A42 alice/P-NEW，自动登录开→关→开。

**数据库：** 准备：已改密alice；内存/旧持久会话由真实登录生成；预期变更：关闭选项是本地行为，不改用户角色/密码；真实登录可产生新服务会话，不能因无文件推断服务没有会话；只读核验：Q-USERS、Q-SESSIONS、Q-VALID。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 登录页关闭自动登录并以P-NEW登录 | 真实登录成功；不读取旧持久凭据作为认证；新会话只在内存，当前origin旧文件删除 |
| 2 | 点击刷新身份 | 内存会话可正常得到`/me`200；凭据目录仍无该origin文件 |
| 3 | 关闭/重启App | 登录页显示，复选框仍关闭；不从其他origin或旧缓存恢复身份 |
| 4 | 重新开启并真实登录，再次重启 | 保存新token并经过`/me`恢复，证明开关两方向都生效 |

**绑定/缺口：** 上述聚合及组件结果只作历史旁证；SESSION-06当前固定绑定见`tests/test_cases.json`，旧文件与完整UI四步的实测按run_id原件核对。

### TC-TM001-SESSION-07 · 固定30天有效期与精确到期边界

**任务/依据：** TASK-TM001-SESSION-EXPIRY；AC-TM001-001及会话固定期约束。**数据/前置：** D-A42，独立固定时钟T0，真实服务认证/DB实现；不改系统时间或正式App增加测试时钟旁路。SOP-010/013；UI拒绝部分关联SESSION-05；RESET。

**类型/输入：** 服务集成/时间边界。输入：独立T0；T0+2592000-1/T0+2592000/+1；旧expires_at。

**数据库：** 准备：固定时钟fixture创建真实认证DB，系统时间不变；预期变更：expires_at固定不滑动；边界前有效，边界及后Q-VALID=0；服务重启不改原expires_at；只读核验：Q-USERS、Q-SESSIONS、Q-VALID。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 在T0真实登录，记录真实登录时刻T0并读取DB会话到期字段 | 到期=T0+2,592,000秒，预期数值来自需求常量 |
| 2 | 推进组件时钟至到期前1秒，多次`/me`并重建真实服务实例 | 返回200；原expires_at不改变，重启不延长 |
| 3 | 到期瞬间以及后一秒再次`/me` | 均401，不能滑动续期 |
| 4 | 保留旧版本已有expires_at的会话，重启/迁移服务后只读比对 | 旧期限保持，不能统一改为新30天；App遇到该无效会话按SESSION-05处理 |

**绑定/缺口：** `tests/server/test_auth.py::test_new_session_has_fixed_thirty_day_lifetime_and_me_does_not_extend_it`、`test_session_survives_server_restart_and_expires_exactly_at_boundary`、`test_existing_session_expiry_is_preserved_after_server_upgrade_and_restart`；类型为组件/服务测试，不是等待30天的桌面E2E。状态：设计已定；执行结论按run_id查原件。

### TC-TM001-SESSION-08 · 在线退出撤销当前会话

**任务/依据：** TASK-TM001-SESSION-LOGOUT；AC-TM001-001。**数据/前置：** SETUP-MEMBER；另用真实API取得同账号第二会话T2，只保存在测试进程内存。SOP-010/014；RESET。

**类型/输入：** E2E/正向/会话撤销。输入：同账号真实T1/T2两个会话，T1由App退出。

**数据库：** 准备：D-A42已改密alice，记录logout审计计数；预期变更：T1失效，T2仍有效；logout审计恰+1，其他账号状态不变；只读核验：Q-VALID、Q-AUDIT、Q-USERS。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 记录当前T1与第二会话T2均可`/me`200、logout审计基线 | 两个独立活跃会话成立，不输出token |
| 2 | 从UI点击退出并等待完成 | 当前origin持久文件清除，UI回登录；真实logout成功，不只关闭窗口 |
| 3 | 分别用T1/T2请求`/me`，只读核对审计 | T1=401、T2=200；当前退出审计恰好+1，actor/target均该用户 |
| 4 | 重启原profile App | 无自动登录；登录输入可用；不显示服务器尚未撤销提示 |

**绑定/缺口：** 聚合T1和组件T2只作历史旁证；SESSION-08固定程序含真实T1/T2及logout审计计数，结果按run_id原件核对。

### TC-TM001-SESSION-09 · 离线退出待确认与重试

**任务/依据：** TASK-TM001-SESSION-LOGOUT、TASK-TM001-CONFIG-LOCKS；AC-TM001-001/006。**数据/前置：** SETUP-MEMBER；仅停止自己的服务A。SOP-010/014；RESET。

**类型/输入：** E2E/异常/撤销重试。输入：当前token、服务A断开/恢复、UI重试退出。

**数据库：** 准备：D-A42已改密alice，停本例服务保留DB；预期变更：不可达阶段不能宣称DB已撤销；重试成功后Q-VALID=0并有相应logout记录；只读核验：Q-VALID、Q-AUDIT、Q-USERS。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 服务不可达时在App点击退出 | 本地凭据删除，已登录身份清空；显示撤销尚未确认，不能宣称服务端已成功撤销 |
| 2 | 打开配置并尝试改API或恢复全部默认 | 操作被锁定，无origin切换，不把待撤销token发往新服务 |
| 3 | 同地址恢复原服务；通过真实UI重试退出 | 向原服务提交撤销并成功，待确认状态解除；不需要把token写回磁盘 |
| 4 | 用原token独立请求`/me`并检查配置可编辑状态 | 401；API编辑重新可用；无凭据恢复或假成功提示 |

**绑定/缺口：** `accounts.test.ts` 的 logout失败/重试只是组件检查；完整真实服务/UI当前固定绑定见`tests/test_cases.json`，须以各run原件判定，不能借组件结果通过。

### TC-TM001-SESSION-10 · 拒绝非受保护凭据对象

**任务/验收：** TASK-TM001-SESSION-PERSIST, AC-TM001-001, AC-TM001-006。

**已确认规则：** 拒绝符号链接、硬链接、非当前uid、宽权限文件或目录等异常凭据对象；不跟随链接、不改哨兵，显示重新登录提示。缺其他uid测试条件记录BLOCKED。

**类型：** 组件及E2E/文件安全边界。**输入：** 本例profile、自有哨兵、symlink/hardlink/宽权限变体。

**前置/数据：** 全新拥有profile及自己拥有的哨兵文件；逐变体准备符号链接、硬链接、宽权限文件/目录；不读取任何真实用户凭据。SOP-010/013/014；RESET。
已确认规则：拒绝符号链接、硬链接、非当前uid、宽权限文件或目录等异常凭据对象；不跟随链接、不改哨兵，显示重新登录提示。缺其他uid测试条件记录BLOCKED。

| 步骤 | 动作 | 预期结果 |
| --- | --- | --- |
| 1 | 在本例origin位置分别放入上述不合规对象，记录哨兵原摘要 | 变体来源和归属明确；不能拿系统文件作需修改的目标 |
| 2 | 通过正常启动恢复或登录保存触发真实凭据读写 | 拒绝异常对象并提示重新登录；不显示已验证身份，不跟随链接读取或覆盖哨兵。 |
| 3 | 比对哨兵摘要、目录内容、UI错误与服务请求 | 哨兵未变，无token泄漏；不存在把文件失败转为缓存登录的路径 |
| 4 | 仅移除本例故障对象，恢复合法profile后重新登录 | 正常安全保存和恢复可完成；未知归属不自动修权限/删除 |

**DB操作：** D-A42；故障对象只在本轮目录生成；非法文件不应改变用户或读写其他库；若登录已签发会话，记录实际状态，不伪造已回滚。只读核验按共用SQL合同，不导出token/散列。

**绑定/状态/证据：** `design_status=designed`；实际绑定由结构化清单登记。`execution_status=按run_id查原件`；每次生成独立原始证据及结果，不继承聚合PASS。SOP-010/011/014；每变体独立环境，按owner/run_id清理。

## 4. 管理员操作与审计：6 个精细场景

### TC-TM001-ADMIN-01 · 重置成员密码并撤销全部旧会话

**任务/依据：** TASK-TM001-ADMIN-RESET；AC-TM001-003。**数据/前置：** SETUP-ADMIN；bob有两个经真实API获得的旧会话，其中一份由第二个独立App/profile保存。SOP-010/014；RESET。

**类型/输入：** E2E/正向/全部会话撤销。输入：admin/P-NEW；bob两个旧token；P-RESET。

**数据库：** 准备：D-A42真实登录形成两bob会话，记录其他用户基线；预期变更：bob密码散列改变且must_change_password=true；所有旧bob会话Q-VALID=0；其他用户会话有效；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 进入账号管理，选择test-bob，输入P-RESET并确认 | 目标UUID尾号0003，UI显示重置成功；不改变其他用户 |
| 2 | 用bob全部旧token与原密码分别访问 | 全部旧token `/me`401；原密码登录401；DB旧会话均已撤销 |
| 3 | 重启保存bob旧token的App | 无法自动登录，失效凭据删除；不能靠缓存身份进入主页 |
| 4 | UI用P-RESET登录bob | 强制改密，改密前无受保护管理能力；改为新密码后才结束强制状态 |
| 5 | 用其他用户原会话核对并读审计 | 其他用户会话不被误撤销；reset审计正确actor0001/target0003 |

**绑定/缺口：** 旧聚合与服务组件只部分覆盖；ADMIN-01当前固定绑定见`tests/test_cases.json`，多旧会话及其他用户的UI组合以run原件逐步判定。

### TC-TM001-ADMIN-02 · 无效重置输入不能修改账号

**任务/依据：** TASK-TM001-ADMIN-RESET；AC-TM001-003及新密码12–128位规则。**数据/前置：** SETUP-ADMIN，bob已有有效会话；为每种输入记录bob状态、credential_version、活跃会话与审计基线。SOP-010/014；RESET。

**类型/输入：** E2E/负向/输入边界。输入：临时密码空/11位/129位及合法P-RESET。

**数据库：** 准备：D-A42 bob有有效会话，记录密码散列仅供内存比对；预期变更：非法输入不改散列/credential_version/首次改密状态，不产生成功password_reset审计；有效对照按ADMIN-01；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI分别输入空、11位、129位临时密码并确认，每变体从新基线开始 | 显示校验错误，不出现重置成功 |
| 2 | 检查实际请求与DB前后快照，再以bob原凭据登录/访问 | 若请求到服务则真实服务也拒绝；原密码/原会话仍有效，首次改密标志和credential_version未被改变 |
| 3 | 检查password_reset审计增量 | 没有成功重置审计，不将无效请求计为已完成操作 |
| 4 | 使用合法P-RESET再执行 | 合法操作按ADMIN-01生效，避免把按钮整体失效误当负测通过 |

**绑定/缺口：** 三条独立参数变体及UI/DB固定程序见`tests/granular_login_variants.json`和`tests/test_cases.json`；不得根据当前UI是否校验反向删边界。实际结果见各run原件。

### TC-TM001-ADMIN-03 · 停用成员立即拒绝登录及旧会话

**任务/依据：** TASK-TM001-ADMIN-STATUS；AC-TM001-002/003。**数据/前置：** SETUP-ADMIN，bob在另一拥有profile登录并保存token；SOP-010/014；RESET。

**类型/输入：** E2E/正向与负向/账号停用。输入：admin停用bob；bob旧token及正确密码。

**数据库：** 准备：D-A42，bob在独立profile登录；预期变更：bob is_active=false；所有旧会话不可用；新增account_disabled审计；无其他用户误改；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 管理界面停用test-bob | UI目标行显示停用；DB `is_active=false`，其他用户不变 |
| 2 | 用bob所有旧token请求`/me`及以正确密码登录 | 旧token401；登录403、`account_disabled`，不签发新会话 |
| 3 | bob App先刷新身份，再重启恢复 | 两条路径均不能显示已验证身份；无效持久凭据清除 |
| 4 | 核对审计 | `account_disabled` 对应actor0001、target0003；不含凭据 |

**绑定/缺口：** 旧聚合只部分覆盖；ADMIN-03当前固定绑定见`tests/test_cases.json`，刷新路径及全部会话枚举以run原件逐步判定。

### TC-TM001-ADMIN-04 · 启用不复活已撤销会话

**任务/依据：** TASK-TM001-ADMIN-STATUS；AC-TM001-003。**数据/前置：** 新D-A42，经真实操作先建立bob会话并停用；admin保持可用。SOP-010/014；RESET。

**类型/输入：** E2E/正向与负向/账号启用。输入：真实停用后的bob、旧token及当前密码。

**数据库：** 准备：新D-A42先真实登录bob再停用；预期变更：bob is_active=true，但旧会话仍Q-VALID=0；重新登录新会话有效；account_enabled审计新增；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI启用test-bob | 显示启用，DB `is_active=true` |
| 2 | 再次用停用前旧token访问`/me` | 仍401，启用不能重新启用旧会话 |
| 3 | 用bob当前有效密码从登录页重新登录 | 得到新会话；若仍需改密则继续强制改密，不跳过 |
| 4 | 检查审计与新旧会话 | `account_enabled`身份准确；仅新会话可用，旧会话不复活 |

**绑定/缺口：** E2E-TM001-003含启用UI；服务`test_admin_reset_disable_and_enable_revoke_sessions_and_are_audited`含旧会话不复活；需合并为逐TC证据。状态：设计已定；执行结论按run_id查原件。

### TC-TM001-ADMIN-05 · 自停用与最后活动管理员保护

**任务/依据：** TASK-TM001-ADMIN-GUARD；AC-TM001-003及管理员保护约束。**数据/前置：** D-A42仅一个活动admin；并发变体使用独立`two_admin_accounts`合成fixture/SQL，绑定见变体清单。SOP-010/013/014；RESET。

**类型/输入：** 服务集成及E2E/权限/并发边界。输入：单admin自停用；两活动admin并发停对方。

**数据库：** 准备：D-A42单admin；双admin变体fixture/SQL由固定程序独立生成；预期变更：活动管理员计数始终至少1；拒绝事务不产生成功停用状态/审计；最终有效会话与成功事务一致；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | admin管理页面查看自身停用入口；若UI禁用则保存该状态，再用其真实token请求自身disable接口 | UI不允许成功自停用，服务也拒绝；不能只依赖按钮隐藏 |
| 2 | 只读检查活动管理员数、会话与审计 | 至少一个活动admin；当前身份仍可用；无成功自停用审计 |
| 3 | 在独立两管理员fixture中，以两个真实token并发停用对方 | 不得两个都成功使管理员数降为0，拒绝操作不留下半更新 |
| 4 | 核对最终DB、每个HTTP结果与有效管理员登录 | 最终仍有可用管理员，状态/撤销/审计与真正成功的事务一致 |

**绑定/缺口：** 服务组件检查之外，单/双管理员变体已有独立UI与造数程序，见`tests/granular_login_variants.json`；每变体执行结果由run原件判定，不能用组件覆盖代替。

### TC-TM001-ADMIN-06 · 审计展示正确对象且不泄露敏感值

**任务/依据：** TASK-TM001-ADMIN-AUDIT；AC-TM001-003。**数据/前置：** SETUP-ADMIN；依次对bob执行真实reset、disable、enable，分别记录操作前后时间和审计基线；SOP-010/014；RESET。

**类型/输入：** E2E/权限/审计与隐私。输入：admin对bob reset/disable/enable；成员访问审计。

**数据库：** 准备：D-A42，记录每操作前审计计数与请求时刻；预期变更：正确actor0001/target0003/action/UTC时间，密码/token不出现在审计；成员查询不修改审计或读取管理数据；只读核验：Q-USERS、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI打开审计并定位本轮三次操作 | 三种动作均可见，能区分当前操作与旧记录 |
| 2 | 对照真实`GET /v1/admin/audit`与只读DB | actor=admin0001、target=bob0003、动作准确；UTC时间在各请求边界内，记录不是给其他用户 |
| 3 | 在内存搜索本轮密码、临时密码、原token是否出现在响应/审计/应用日志 | 均不存在；只记录搜索结论，不把待检查的敏感值写进报告 |
| 4 | 成员token请求审计接口并检查成员UI | 403且无审计内容；成员界面不出现管理员审计入口 |

**绑定/缺口：** 旧聚合及服务组件只部分覆盖；ADMIN-06当前固定绑定见`tests/test_cases.json`，actor/target/时间/无敏感值的UI/API/DB断言以run原件判定。

## 5. 生产首建与恢复：4 个精细场景

### TC-TM001-BOOTSTRAP-01 · 空库只预置管理员，生成SQL可检查

**任务/依据：** TASK-TM001-BOOTSTRAP-INIT；AC-TM001-005。**数据/前置：** 新D-PROD根、空目标；另有独立D-A42作隔离对照。SOP-010/016；RESET。

**类型/输入：** 集成/正向/SQL与数据隔离。输入：全新D-PROD admin/123456；独立D-A42对照。

**数据库：** 准备：initialize_production(owned_root)生成并执行真实seed.sql；预期变更：只有admin0005、admin角色/启用/强制改密；production owner与schema0001；与测试库物理分离；只读核验：Q-OWNER、Q-SCHEMA、Q-USERS、Q-INTEGRITY。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 运行同一生产首建程序，保存其生成SQL及执行退出码 | 退出0，新SQLite/schema建立；SQL不包含明文123456，仅包含实际密码散列和首建操作 |
| 2 | 只读查询schema版本、owner和users | schema0001、production归属；恰一条admin、UUID0005、启用且强制改密；没有四个test账号 |
| 3 | 对照独立测试库和两个文件真实路径 | 测试库四合成账号，生产同构库只有admin；文件、owner和路径互不相同 |
| 4 | 用本例真实服务以admin/123456登录 | 200且must_change_password=true，证明SQL散列可用于实际认证 |

**绑定/缺口：** `local_e2e.py`005与服务组件只作历史旁证；BOOTSTRAP-01固定绑定见`tests/test_cases.json`，原始SQL和独立预期按run_id核对。

### TC-TM001-BOOTSTRAP-02 · 首登强制改密与管理权限切换

**任务/依据：** TASK-TM001-BOOTSTRAP-INIT；AC-TM001-005。**数据/前置：** 新D-PROD、最终DMG、独占profile/服务；SOP-010/014；RESET。

**类型/输入：** E2E/正向与权限/首次改密。输入：admin/123456→TEST-ONLY-Admin-New-42!。

**数据库：** 准备：全新D-PROD，服务明确绑定合成生产库；预期变更：改密后must_change_password=false；初始旧token失效、新会话有效；始终只有admin；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI改连本例服务，用admin/123456登录 | 进入强制改密表单，不能访问管理员主页 |
| 2 | 用初始token请求用户管理和审计 | 403、password_change_required；不是只隐藏UI |
| 3 | UI改为TEST-ONLY-Admin-New-42! | 服务确认后身份admin，must_change_password=false，管理员入口出现 |
| 4 | 用旧token/123456分别请求，再查UI账号列表 | 旧token401、旧密码401；列表恰只有admin，没有test-* |
| 5 | App重启恢复，再退出并用新密码登录 | 两条真实身份确认都成功，不回初始密码 |

**绑定/缺口：** 旧聚合与服务组件只作历史旁证；BOOTSTRAP-02固定绑定见`tests/test_cases.json`，全部初始管理接口断言按run_id核对。

### TC-TM001-BOOTSTRAP-03 · 重启或重复首建不覆盖已有数据

**任务/依据：** TASK-TM001-BOOTSTRAP-PRESERVE；AC-TM001-005。**数据/前置：** 新D-PROD，在真实UI改密；保留用户/credential_version/审计快照。新增成员由批准的离线`server.tokenmeter_server.provision`程序向本例合成库添加，生成与重置由固定runner绑定。SOP-010/016/014；RESET。

**类型/输入：** 集成及E2E/负向/数据保留。输入：改后密码、重复首建/seed；额外合成成员变体。

**数据库：** 准备：D-PROD先真实改密；额外成员用固定provision输入，独立核对；预期变更：重启不重置散列/账号；重复初始化/错误seed事务拒绝且原行保留；123456仍失效；只读核验：Q-OWNER、Q-SCHEMA、Q-USERS、Q-AUDIT、Q-INTEGRITY。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 停止本例API，再从同一DB启动，重开App用新密码登录 | 不重新seed，密码和账号保留；123456仍失败 |
| 2 | 对本例已有库再次调用首建程序 | 明确拒绝覆盖，非零退出；原DB账户状态/散列/审计不被重置 |
| 3 | 将初始seed.sql重放到本例非空库或错误environment库 | 明确拒绝，事务回滚；不得先改部分用户再报告失败 |
| 4 | 对含额外合成成员的变体重复重启与拒绝首建 | 新成员及admin改后状态完整保留，首建不是每次启动清库 |

**绑定/缺口：** 上述服务测试只作组件旁证；完整服务重启、App与额外成员的当前固定绑定见`tests/test_cases.json`，逐步实测与结果以各run原件为准。

### TC-TM001-BOOTSTRAP-04 · 从真实备份恢复并由App使用恢复库

**任务/依据：** TASK-TM001-BOOTSTRAP-RESTORE；AC-TM001-005与本轮安装恢复预案。**数据/前置：** 新D-PROD，在任何登录前备份，无真实用户会话。SOP-010/016/017；RESET。

**类型/输入：** 集成及E2E/备份恢复/原件验证。输入：无会话初始D-PROD、backup/restored独立路径。

**数据库：** 准备：SQLite backup生成备份，再恢复到新库；真实API只连接恢复运行副本；预期变更：归档备份与恢复副本的schema/行完全一致且sessions空；App真实写入只落恢复运行库，证据原件摘要不变；只读核验：Q-SCHEMA、Q-USERS、Q-SESSIONS、Q-OWNER、Q-INTEGRITY。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 用SQLite backup复制初始库，再从备份恢复到另一拥有路径 | 三个路径不同，原库未覆盖；保留备份/恢复原件与摘要 |
| 2 | 独立只读解析两原件并执行integrity_check及schema/表列/行比对 | integrity=ok；schema0001及users/sessions/audit/login_buckets/owner等必需结构齐全；admin状态相等、sessions为空 |
| 3 | 真实API明确绑定恢复路径，最终DMG App经UI连接该服务并完成首登改密 | 能证明认证读写的是恢复副本；按BOOTSTRAP-02得到预期UI与API结果 |
| 4 | 再次只读核对原备份、恢复证据副本和运行库 | 归档原件不因App登录被改写；运行副本正常变化，恢复结论不只来自手写JSON |
| 5 | 父门禁重新解析保留原件并验证摘要 | 与最初解析一致；错schema、缺表或摘要变更必须阻断 |

**绑定/缺口：** 旧005和组件只作历史旁证；BOOTSTRAP-04固定绑定及备份/恢复证据见`tests/test_cases.json`与各run原件。仅合成、无会话初始副本可留在0700证据目录，不归档用户生产库。

## 6. 配置与origin隔离：6 个精细场景

### TC-TM001-CONFIG-01 · 首次默认值与无凭据访问边界

**任务/依据：** TASK-TM001-CONFIG-API；AC-TM001-006。**数据/前置：** 全新安装/profile，记录已有生产49176进程但不连接它认证；SOP-010/014；RESET。

**类型/输入：** E2E/正向/默认值与持久化。输入：干净profile、默认49176/49177、owned服务A。

**数据库：** 准备：D-A42只在A创建，用户生产库仅保留不读写；预期变更：未登录/保存配置不产生认证会话或管理写入；默认用户生产库完全不作为测试目标；只读核验：Q-USERS、Q-SESSIONS、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 首启读取登录页服务地址，打开配置页读取两地址 | API=http://127.0.0.1:49176；更新=http://127.0.0.1:49177/version.json，与实际签名资源一致 |
| 2 | 未登录状态短暂观察App请求记录和身份 | 不发默认服务认证/写请求，无已验证身份；不能通过登录用户生产服务证明默认值 |
| 3 | 在真实配置页改为本例服务A并保存 | 后续登录请求只发往本例A，保存后UI显示A |
| 4 | 重启后再次打开配置页 | A覆盖保留；不重置为内置端口 |

**绑定/缺口：** CONFIG-01已有固定UI绑定，但默认49176服务启动前的网络观察仍缺，机器写`coverage-blocked.json`；不能由空profile或owned服务零请求推断。确定性失败优先FAIL。

### TC-TM001-CONFIG-02 · API URL校验与规范化

**任务/依据：** TASK-TM001-CONFIG-API；AC-TM001-006及地址规则。**数据/前置：** 新profile、服务A；参数表的远端域名仅测试保存，不向外请求。SOP-010/013/014；RESET。

**类型/输入：** 组件及E2E/URL边界。输入：合法回环HTTP/HTTPS、大小写默认端口、非法host/path/userinfo/query/fragment。

**数据库：** 准备：仅本例A库；远端示例只保存不请求；预期变更：地址校验/规范化不改变DB；拒绝值不能触发认证和写入；连通性试验仅对本例服务；只读核验：Q-USERS、Q-SESSIONS、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 在登录页逐项输入HTTP精确127.0.0.1、localhost、[::1]的合法origin与合法HTTPS地址 | 地址校验接受；实际连通性另判，HTTPS连纯HTTP服务应是网络/TLS失败而非地址非法 |
| 2 | 输入非回环HTTP、127.1、整数IP、空host、非法端口、userinfo、非根路径、query、fragment | 保存/登录前拒绝为地址错误；不向目标发认证，不修改已保存origin |
| 3 | 组件层输入https://EXAMPLE.invalid:443/与https://example.invalid | 规范化结果相同，等价origin映射同一凭据位置；只比较确定字符串，不访问外域 |
| 4 | 输入另一个合法origin | 映射不同凭据位置，不能携带先前服务token；UI非法输入有明确错误 |

**绑定/缺口：** `security.test.ts`只作组件旁证；逐TC真实UI/API及网络错误分类的当前固定绑定见`tests/test_cases.json`，完整步骤和结果按run原件核对。

### TC-TM001-CONFIG-03 · 两套服务、密码与持久会话互不混用

**任务/依据：** TASK-TM001-CONFIG-API；AC-TM001-006。**数据/前置：** D-A42服务A、D-A43服务B，两个真实动态origin；SOP-010/014；RESET。

**类型/输入：** E2E/权限/跨origin隔离。输入：D-A42/A与D-A43/B；两组密码/token。

**数据库：** 准备：两份独立SQL/库/owner，动态origin不同；预期变更：A token只在A有效，B token只在B有效；账号变更及logout各落对应库，不能串库；只读核验：Q-USERS、Q-VALID、Q-AUDIT、Q-OWNER。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI登录A的alice并改密，取得当前token指纹 | A `/me`200；同token在B401；不会用B密码通过A |
| 2 | App重启恢复A，再退出并检查凭据清理 | A保存地址保留；退出清A凭据 |
| 3 | UI改到B，用seed43密码登录并改为TEST-ONLY-Changed-43! | B成功，新token在B200/A401；B请求日志中未出现A token |
| 4 | 比对两个origin的凭据路径，再重启刷新 | 路径不同；重启仍连B且由B `/me`确认；不从A读取身份 |
| 5 | 退出B并检查地址/凭据 | B凭据清除，地址覆盖仍为B；不会删除未知origin文件 |

**绑定/缺口：** 旧聚合只部分覆盖；CONFIG-03固定绑定见`tests/test_cases.json`，目标服务零旧token请求与逐步记录按run_id原件核对。

### TC-TM001-CONFIG-04 · 更新地址边界及固定公钥

**任务/依据：** TASK-TM001-CONFIG-UPDATE；AC-TM001-004/006。**数据/前置：** 新profile，签名资源中的公钥摘要已记录；仅配置地址不发更新请求。SOP-010/013/014；RESET。

**类型/输入：** 组件及E2E/URL边界/公钥固定。输入：合法带路径feed/HTTPS；非回环HTTP/userinfo/?/#/非法端口；固定公钥。

**数据库：** 准备：本例D-A42库；只配置无登录/更新请求；预期变更：保存/拒绝更新URL不改任何用户、会话或审计；固定公钥属于签名资源，不在业务DB改写；只读核验：Q-USERS、Q-SESSIONS、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 分别保存带路径的精确回环HTTP及合法非回环HTTPS清单地址 | 接受；允许清单路径；不能把保存成功说成远端可达 |
| 2 | 分别保存非回环HTTP、空host、userinfo、query/fragment（含空?/#）、非法端口、127.1/整数IP | 每项拒绝 `update_source_rejected`；原配置不变，无外域请求 |
| 3 | 更改合法更新源后检查UI及实际受签名资源 | UI无公钥编辑入口，固定Ed25519公钥摘要不变；源地址不能携带替换公钥 |
| 4 | 关闭/重启并重新打开配置 | 合法覆盖仍在，非法值从未落盘 |

**绑定/缺口：** 旧聚合和组件只部分覆盖；CONFIG-04固定绑定见`tests/test_cases.json`，非法地址及固定公钥复验按run_id原件核对。

### TC-TM001-CONFIG-05 · 成对校验、取消、持久化及恢复默认

**任务/依据：** TASK-TM001-CONFIG-UPDATE；AC-TM001-006。**数据/前置：** 未登录，新profile已保存A与本例合法feed；SOP-010/014；RESET。

**类型/输入：** E2E/事务与持久化/取消恢复。输入：两地址有效/一项无效、取消、保存、恢复默认。

**数据库：** 准备：本例A/B空认证状态与profile设置基线；预期变更：配置操作仅写本地设置，业务库无用户/会话修改；无效保存/取消不部分改变持久设置；只读核验：Q-USERS、Q-SESSIONS、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 同时输入合法B API和非法更新URL并保存 | 报更新地址错误；A/API与原feed均未改变，不发生部分提交 |
| 2 | 输入两项合法新值，点击取消，再重启 | 两项仍为原值，取消不落盘 |
| 3 | 再次输入两项合法新值并保存，再重启 | 两项同时持久化；设置文件不包含密码/token |
| 4 | 点击恢复默认，再关闭设置并重启 | 两项覆盖被删除，API/更新显示本版内置49176与49177/version.json；无测试登录/更新请求触及用户服务 |
| 5 | 只读对照设置文件与受签名内置资源 | 恢复操作是删覆盖，不能固化旧默认或改受签名资源 |

**绑定/缺口：** CONFIG-05已有固定UI绑定，但恢复默认时默认49176网络观察仍缺，机器写`coverage-blocked.json`；取消/覆盖删除的局部结果按run原件判定。

### TC-TM001-CONFIG-06 · 登录、待退出和更新进行中的配置锁定

**任务/依据：** TASK-TM001-CONFIG-LOCKS；AC-TM001-001/004/006。**数据/前置：** SETUP-MEMBER；owned更新源可固定暂停下载，仍须覆盖下载、验证和原生安装各忙态。SOP-010/014；RESET。

**类型/输入：** E2E/状态边界/配置锁定。输入：已登录、退出待确认、下载忙、取消/失败后的四状态。

**数据库：** 准备：D-A42真实会话与owned可控下载；暂停控制由固定程序绑定；预期变更：配置锁定不改变账号或转移会话到新库；真实logout成功后按SESSION-09撤销，更新不修改服务用户；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 已登录时打开配置尝试编辑API和总恢复默认 | 均锁定，旧会话不会因地址编辑被发到新服务；空闲更新源仍按既定设计可配置 |
| 2 | 按SESSION-09进入退出待确认状态，再试上述操作 | 仍锁定，不能借登录页出现绕过 |
| 3 | 确认在线退出完成 | API编辑及总恢复恢复可用 |
| 4 | 登录后开始真实更新下载，暂挂本例响应，再打开配置修改更新源 | 下载/验证/安装忙状态更新源编辑被锁定；当前任务不切换源 |
| 5 | 通过正常取消或失败结束交接前更新，再检查配置 | 未交给原生安装器时按状态恢复编辑；交接后不得假装可安全取消并改源 |

**绑定/缺口：** 固定UI程序已覆盖下载等待态；验证与原生安装忙态仍缺独立观察和锁定断言，机器以`coverage-blocked.json`记录BLOCKED，失败则FAIL优先。

## 7. 下载验证与原生安装：8 个精细场景

### TC-TM001-UPDATE-01 · 自动发现与确认安装分离

**任务/依据：** TASK-TM001-UPDATE-DISCOVER；AC-TM001-004。**数据/前置：** D-UPDATE同机源初始idle，build100、新profile、服务A。SOP-010/014/017；RESET。

**类型/输入：** E2E/正向/自动发现与用户确认。输入：build100、idle204→有效101清单；已验证alice。

**数据库：** 准备：D-A42与同机更新源，登录/改密通过真实UI；预期变更：发现/检查不修改服务账号/会话；登录引起的变化单独登记；无本轮数据库迁移；只读核验：Q-USERS、Q-SESSIONS、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 未登录启动，读取内置feed并经配置改到owned源 | 默认值正确；无认证前不能用缓存身份触发已登录行为 |
| 2 | UI登录并完成真实身份确认，观察idle源请求 | 自动读取清单并显示当前已是最新版本；没有安装或无关外域请求 |
| 3 | 同一源切到有效高版本，点击检查更新 | UI发现0.1.1/build101；只检查不替换App，原build100仍在 |
| 4 | 点击确认安装前检查请求记录和进程 | 不能提前下载/交给Squirrel或退出旧App；检查、用户确认、安装有清晰顺序 |

**绑定/缺口：** 旧聚合和组件只部分覆盖；UPDATE-01固定绑定见`tests/test_cases.json`，确认前零ZIP请求及原生交接旁证按run_id核对。

### TC-TM001-UPDATE-02 · 非回环HTTP下载URL在请求前拒绝

**任务/依据：** TASK-TM001-UPDATE-VERIFY；AC-TM001-004。**数据/前置：** SETUP-MEMBER、D-UPDATE forbidden阶段，合法本机清单返回`http://example.invalid/update.zip`；SOP-010/014/017；RESET。

**类型/输入：** E2E/负向/下载URL安全。输入：forbidden清单含非回环HTTPZIPURL；build100。

**数据库：** 准备：D-A42真实已验证alice，保留更新前快照；预期变更：拒绝更新不修改业务用户/会话，原token仍按原期限有效；只读核验：Q-USERS、Q-VALID、Q-AUDIT。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 记录原App摘要、PID/build100，点击检查更新 | UI稳定错误 `update_source_rejected` |
| 2 | 核对本机源请求与客户端拒绝事件 | 清单被读取，但外域下载请求数为0；不是等待DNS失败 |
| 3 | 核对App和身份 | 原摘要/build100/PID保持，未调用原生安装器，已验证会话不被错误清除 |

**绑定/缺口：** UPDATE-02固定绑定见`tests/test_cases.json`；外域零请求必须有独立目标探针及网络旁证，不能由本机源无日志推断，结果按run_id核对。

### TC-TM001-UPDATE-03 · 非法重定向在跟随前拒绝

**任务/依据：** TASK-TM001-UPDATE-VERIFY；AC-TM001-004。**数据/前置：** 同一D-UPDATE redirect阶段，本机ZIP响应302到非回环HTTP；SOP-010/014/017；RESET。

**类型/输入：** E2E/负向/重定向安全。输入：本机下载302到非回环HTTP；固定程序另含合法回环跳转对照与双跳非法目标。

**数据库：** 准备：D-A42与同一owned更新源；预期变更：拒绝重定向不改用户/会话或延长期限；不会请求外域服务获取新身份；只读核验：Q-USERS、Q-SESSIONS、Q-VALID。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI检查并确认安装 | 只请求本机清单及其本机下载入口 |
| 2 | 收到302后读取UI及原始拒绝事件 | `update_transport_rejected`，拒绝发生在发起目标请求前 |
| 3 | 核对目标请求数、App摘要/build和原生交接事件 | 外域0请求，原build100未变化，Squirrel未收到包 |
| 4 | 合法回环跳转组件对照与多跳边界 | 每一跳都校验，不能仅校验起始URL；多跳数据/完整UI绑定缺失时记录BLOCKED |

**绑定/缺口：** 当前固定UPDATE-03已含合法回环跳转和双跳非法目标；独立目标探针与源日志共同验证零外域请求，结果仍须按run原件核对，不凭组件PASS推断产品PASS。

### TC-TM001-UPDATE-04 · 坏Ed25519签名拒绝原生交接

**任务/依据：** TASK-TM001-UPDATE-VERIFY；AC-TM001-004。**数据/前置：** D-UPDATE invalid阶段，真实完整ZIP及正确bytes/SHA，只有Ed25519签名错误；SOP-010/014/017；RESET。

**类型/输入：** E2E/负向/签名拒绝。输入：完整ZIP正确bytes/SHA，仅Ed25519错误。

**数据库：** 准备：D-A42与invalid源；预期变更：拒绝签名不改业务用户/会话或数据库结构；原登录继续按真实服务校验；只读核验：Q-USERS、Q-SESSIONS、Q-SCHEMA。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 点击检查并确认安装，完整下载ZIP | 实收bytes与SHA等于元数据，明确失败不是缺文件或网络中断 |
| 2 | 等待验证结论 | UI `update_signature_rejected`，固定公钥不变 |
| 3 | 核对原生交接、进程及App | 交接次数0；仍build100/原摘要，未安装、未自主重启 |
| 4 | 清理本轮临时下载并保留元数据/包摘要/请求证据 | 无私钥、无残留可执行高版本；错误没有被写成成功安装 |

**绑定/缺口：** UPDATE-04固定绑定见`tests/test_cases.json`；零原生交接的独立入口观察尚缺，机器写`coverage-blocked.json`，其他断言失败则FAIL优先。

### TC-TM001-UPDATE-05 · 元数据、ZIP与签名App身份全部匹配

**任务/验收：** TASK-TM001-UPDATE-VERIFY, AC-TM001-004。

**已确认规则：** ZIP最大512 MiB（536870912字节），解压内容最大2 GiB（2147483648字节），边界本身允许、超过即拒绝；大小、摘要、签名或包身份校验失败均保留当前版本。

**类型：** 组件及E2E/负向/完整性和包身份。**输入：** bytes/SHA/ZIP/Info版本build/bundleID/代码证书/DR/路径逃逸各单一故障。

**前置/数据：** D-UPDATE及按下表由`granular_update_validation_fixture.py`独立生成的13条负面变体；绑定见`tests/granular_update_variants.json`。固定runner须接收`--key-dir <绝对受限目录>`，按SOP-009/010先检查路径、权限、归属及原ZIP/清单的Ed25519签名和p12公有证书指纹一致，再读取同一原候选身份制作受控负例。公开配置、原ZIP和包清单自身矛盾属候选完整性FAIL；对已核对的有效包，私有输入缺失、不安全或身份不符时App启动前记本次前置BLOCKED。私有内容、密码和完整路径不入报告；预检PASS不代替产品断言。原c291批次FAIL不改写。SOP-009/010/013/014/017；RESET。
已确认规则：ZIP最大512 MiB（536870912字节），解压内容最大2 GiB（2147483648字节），边界本身允许、超过即拒绝；大小、摘要、签名或包身份校验失败均保留当前版本。

| 步骤 | 动作 | 预期结果 |
| --- | --- | --- |
| 1 | 分别提供bytes不符、SHA不符、截断/超上限ZIP并从真实UI安装 | ZIP超过536870912字节或解压超过2147483648字节以及bytes/SHA不符均在交接前拒绝，显示完整性错误，原App未变。 |
| 2 | 提供ZIP有效但元数据version/build与内部Info不符的已签测试变体 | 拒绝不一致；不能靠未认证的“更高版本”标记制造更新成功 |
| 3 | 提供错误bundle ID、不同代码证书或不满足候选DR的包；Ed25519层保持可验证以真正到达此检查 | 代码签名/身份检查拒绝，不能只因前置坏签名失败就声称该层覆盖 |
| 4 | 提供ZIP路径逃逸/符号链接父目录写入变体 | 解包前拒绝，owned目标之外的哨兵摘要不变 |
| 5 | 每次对照原App摘要、原生交接和临时目录 | 所有负例均无Squirrel交接/替换；清理只限自己创建内容 |

**DB操作：** D-A42；每变体新owned包/下载根，由固定fixture生成；所有拒绝均不改用户/会话/schema；不会执行包内迁移或向任意DB路径写入。只读核验按共用SQL合同，不导出token/散列。

**绑定/状态/证据：** `design_status=designed`；实际绑定由结构化清单登记。`execution_status=按run_id查原件`；每次生成独立原始证据及结果，不继承聚合PASS。SOP-010/011/014；每变体独立环境，按owner/run_id清理。

### TC-TM001-UPDATE-06 · 有效包由Squirrel替换并自主重启

**任务/依据：** TASK-TM001-UPDATE-INSTALL；AC-TM001-004。**数据/前置：** SETUP-MEMBER、D-UPDATE valid；同一候选/受控包固定证书和公钥，记录旧PID/路径/App摘要及本轮启动次数。SOP-010/014/017；RESET。

**类型/输入：** E2E/正向/原生安装与进程生命周期。输入：固定同签名100DMG→101ZIP、旧PID/树摘要。

**数据库：** 准备：D-A42真实已验证会话；无本轮schema变化；预期变更：升级不重置用户/会话或DB；新App使用同一真实API，身份恢复要重新/me确认；只读核验：Q-USERS、Q-SESSIONS、Q-SCHEMA。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | UI检查并确认安装，读取下载/验证/安装阶段 | bytes/SHA/Ed25519/真实App Info及代码身份全部通过后，才交给临时本机Squirrel源 |
| 2 | 观察旧PID退出与系统创建的新PID | 新PID由App原生更新流程自主产生；测试不调用launch/open手动启动101 |
| 3 | 从外部核对新可执行路径与安装目录内容 | 路径仍是owned安装App，Info=0.1.1/build101，实际树摘要等于本次受控包 |
| 4 | 重新连接已有新进程，读取UI版本 | UI也显示build101；运行实例不是别处同bundle ID的用户App |
| 5 | 核对源请求、交接及旧/新进程时间线 | 明确一条真实升级链；重试、另起App或只修改UI版本均不能计为成功 |

**绑定/缺口：** 旧聚合只作历史旁证；UPDATE-06当前固定绑定见`tests/test_cases.json`，新PID、包树及完整逐步结果按本例run原件判定。

### TC-TM001-UPDATE-07 · 升级保留profile、用户覆盖及服务确认身份

**任务/依据：** TASK-TM001-UPDATE-INSTALL；AC-TM001-001/004/006。**数据/前置：** 在本例先独立执行UPDATE-06升级前设置：自动登录开启、手动服务A/feed覆盖；拥有的runtime文件0600、profile0700。SOP-010/014/017；RESET。

**类型/输入：** E2E/回归/profile和自动登录保留。输入：同profile/runtime、手动API/feed覆盖、合法持久token。

**数据库：** 准备：D-A42服务A运行，保留expires_at基线；预期变更：/me确认不延长会话；用户状态与schema不变；不能切回默认生产库或产生跨库身份；只读核验：Q-USERS、Q-SESSIONS、Q-VALID、Q-OWNER。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 升级前记录App实际userData路径、runtime摘要、地址覆盖和当前token指纹 | 所有路径均在owned目录，runtime绑定当前App，无用户标准profile |
| 2 | 经真实Squirrel升级后重连其自主启动的新进程 | 没有原argv也恢复同一profile；runtime文件摘要/权限保持，不能回落用户目录 |
| 3 | 不输入密码，观察真实服务A `/me`与新App界面 | 服务确认200后显示同一alice身份；不把缓存名字当已登录 |
| 4 | 刷新身份并打开配置 | 再次`/me`200；API/feed手动覆盖、自动登录选择仍在，固定公钥不变 |
| 5 | 对照进程已打开profile文件与origin文件位置 | 文件确实由新进程使用，不仅是runtime JSON写了旧路径 |

**绑定/缺口：** UPDATE-07固定绑定见`tests/test_cases.json`，须关联同一次UPDATE-06的真实升级原件；不能另行启动高版制造恢复结果，执行结论按run_id判定。

### TC-TM001-UPDATE-08 · 同机源和ShipIt状态有归属才运行/清理

**任务/依据：** TASK-TM001-UPDATE-ISOLATION；AC-TM001-004和本机隔离设计。**数据/前置：** 本轮run_id、owned安装/profile/动态API/更新源；已有用户App和服务只读登记。SOP-010/014/017/022；RESET。

**类型/输入：** 执行器集成及E2E/资源归属/清理。输入：run_id、owned安装/profile/API/更新源/ShipIt标记，未知资源变体。

**数据库：** 准备：本例D-A42与owned库；所有用户生产库不接触；预期变更：清理仅处理本例运行库，保留合成证据；未知库/owner不删除，生产库不读取不改写；只读核验：Q-OWNER、Q-INTEGRITY。

| 步骤 | 操作 | 独立预期及检查位置 |
| --- | --- | --- |
| 1 | 启动前检查同bundle ID的ShipIt缓存、launchd job及ByHost状态是否存在 | 未知既有状态即BLOCKED，不能删除后强行重跑；只读检查不能改变用户状态 |
| 2 | 条件齐全后创建本轮0700缓存/归属标记，动态回环源记录nonce和实际地址 | 127.0.0.1指当前Mac；App配置与准备探针使用同一实例，不引入公网隧道 |
| 3 | 执行四阶段并在结束/失败路径检查ShipIt实际状态 | marker run_id与owned App精确匹配；JSON格式的ShipItState目标文件URL指向本轮安装路径 |
| 4 | 仅停止本轮进程、服务并清理本轮缓存/job/profile；重查未知资源 | 原用户App/生产库/服务未变化；未知归属保留并报BLOCKED，清理失败不放行 |
| 5 | 归档包/源nonce/请求/清理证据 | 能追到同一候选与run；不含私钥/token；失败原件不覆盖 |

**绑定/缺口：** UPDATE-08固定绑定见`tests/test_cases.json`；负面归属变体只在隔离工具目录构造，不伪造真实用户状态后删除。逐TC结果按run_id原件判定。

## 8. 基线后需要补齐的程序和记录

1. 将本文件19个任务与34个TC登记到版本任务/测试计划和机器追踪；审查需求→任务→TC→数据→SOP的双向覆盖，不以现有实现反向缩小集合。
2. 聚合六例的历史断言只供定位；精细TC使用`tests/test_cases.json`和固定Playwright逐项执行，发现覆盖缺口时写`coverage-blocked.json`并判BLOCKED。不能仅更名已有结果冒充补测。
3. 优先补保存失败、离线恢复/退出、所有会话撤销、管理员保护/审计细节、生产库保留、配置锁定及更新多层负例；详细数据生成/重置按SOP-010落实。
4. 文档基线完成后先执行稳定失败复现，再修实现、完整回归，逐次保留TC实际步骤记录；每次发布仍需原DMG六例及所有本轮任务的必测TC完整证据，零例/漏步/缺数据不能PASS。
5. 本文不记录预设运行结论；实际PASS/FAIL/BLOCKED及产物位置只由当次程序产生，并由版本执行记录引用。TM-002–012继续planned，没有对应具体任务、精细TC和基线时不能开始实现。
