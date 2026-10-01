# 01a · TM-001 登录与改密：任务级测试设计

版本：`v0.1.0-20260929T074814Z`。需求：`REQ-TM001`。文档状态：`draft`。编制日期：2026-09-30。

本文件先定义开发任务的验收场景，再用于编写自动测试和检查实现。现有六项 E2E 是业务流程套件，本文件的 `TC-` 是其内部可独立报告的测试场景；套件通过不能代替逐项场景证据。各TC执行状态按run_id查[本版结果](../../../releases/v0.1.0-20260929T074814Z/07-test-results.md)及独立Excel；首轮精细全量BLOCKED，新版正在执行。既有源码只用于识别程序缺口，不用于生成预期答案。

## 需求依据与任务

唯一行为依据为[本版需求](../../../releases/v0.1.0-20260929T074814Z/01-requirements.md)中的 AC-TM001-001/002/003/005 及“输入、权限与失败行为”，并引用[产品约定](../../product/README.md)、[本机设计](../../architecture/01-electron-local.md)。[原六项流程](01-TM-001-accounts.md)用于定位上层回归入口，不作为新增边界规则的来源。任务由[版本拆解](../../../releases/v0.1.0-20260929T074814Z/02-breakdown.md)统一登记。

| 具体任务 | 需求输入 | 应交付行为 | 本文件场景 |
| --- | --- | --- | --- |
| TASK-TM001-LOGIN-VALIDATION | 用户名 ASCII 3–64；登录密码 1–128；不得开放注册 | 必填、长度、字符边界；非法输入不建立会话 | LOGIN-05/06/07/09/17/18/19/20/21/22 |
| TASK-TM001-LOGIN-AUTH | 预置账号、错误凭据统一、停用拒绝 | 真正验证账号密码；失败不能显示已登录或产生有效 token | LOGIN-01/02/03/04/08 |
| TASK-TM001-LOGIN-SESSION | 首次改密限制、本人身份、角色授权、网络失败不伪装成功 | 登录后经服务确认身份；按真实角色展示；异常可恢复 | LOGIN-10/11/12/13/14/15 |
| TASK-TM001-LOGIN-RATE | 5分钟连续5次失败按账号或来源限流 | 限制条件、提示、恢复及是否影响其他账号 | LOGIN-16；规则已确认 |
| TASK-TM001-CHANGE-PASSWORD | 新密码 12–128、二次确认、与旧密码不同、全部旧会话撤销 | 验证输入与旧凭据；原子改密、解除首次限制、撤销旧会话 | PASSWORD-01 至 PASSWORD-11 |

`TC-` 名称使用完整编号，例如 `TC-TM001-LOGIN-01`。任务先完成需求与测试设计基线，随后补数据/自动化，再开发与按本文件执行；不能因实现已有另一行为而改写预期。

## 共用前置、数据与证据合同

### 固定测试数据 D42

每个场景、每个参数行均使用新的 `run_id`、安装位置、0700 profile、动态独占回环端口和独立 SQLite；不共享上一例改密或失败计数。不使用用户现有49176服务、生产库或 `/Applications/TokenMeter.app`。

| 别名 | ID | 账号 / 初始密码 | 初始状态 |
| --- | --- | --- | --- |
| A | `00000000-0000-4000-8000-000000000001` | `test-admin` / `TEST-ONLY-admin-42!` | admin、启用、必须改密 |
| L | `00000000-0000-4000-8000-000000000002` | `test-alice` / `TEST-ONLY-alice-42!` | member、启用、必须改密 |
| B | `00000000-0000-4000-8000-000000000003` | `test-bob` / `TEST-ONLY-bob-42!` | member、启用、必须改密 |
| D | `00000000-0000-4000-8000-000000000004` | `test-disabled` / `TEST-ONLY-disabled-42!` | member、停用、必须改密 |

固定错误密码 `TEST-ONLY-Wrong-42!`；固定未知账号 `test-missing`，生成后独立确认不在四个账号中；固定改后密码 `TEST-ONLY-Changed-42!`。数据依据为预先写明的四行规格，生成后的实际值必须与该表比较，不能以查询结果回填预期。

### 数据程序、SQL、初始化与重置

- 基础账号文件生成器：[tests/server/fixtures.py](../../../tests/server/fixtures.py)，数据集 `auth_accounts`、seed42。现有文件生成命令为 `python3 tests/server/fixtures.py generate --run-id <唯一小写编号> --seed 42`；只生成规范文件，不启动服务、不代表已有数据库。
- SQLite 初始化与 SQL：[scripts/bootstrap_sqlite.py](../../../scripts/bootstrap_sqlite.py)，现有隔离编排：[scripts/local_e2e.py](../../../scripts/local_e2e.py)。执行前依 [SOP-010](../../../sop/SOP-010-test-data.md) 确认本例拥有的根目录；使用其中隔离初始化能力生成并执行 `seed.sql`。不得直接运行默认根目录生产初始化来准备本文件。
- SQL 必须来自本例数据输入，含随机盐散列、空库/归属检查和事务。生成前写定四个 ID、角色和状态；执行后只读检查四行账号、零会话和首次改密状态。账号密码与 token 不写入报告；SQL及原始数据库只留在受限本地证据目录。
- D42 的普通登录准备 `D42-NORMAL-L`：在本例新库，以 L 通过真实登录/改密流程改为固定改后密码，再退出该准备会话；确认 L 的 `must_change_password=false`、角色仍为 member、旧密码401。不得用 SQL 把首次改密标记直接改成成功。
- `D42-NORMAL-A` 同理使用 A；改后密码固定为 `TEST-ONLY-Admin-New-42!`。准备行为单独记录，测试动作从准备完成后的快照计数；准备失败时本场景 BLOCKED。
- `D42-BOUNDS`：用于指定3/64字符账号及128字符密码的扩展种子规格，详见对应场景。扩展生成程序为 `scripts/granular_bounds_fixture.py`，每例独立造数和只读核验；不能在执行时手工改库通过认证。
- 仅账号文件的重置用 `python3 tests/server/fixtures.py reset --run-id <同一编号>`，它不能清理运行中的数据库。完整场景结束后由 runner 关闭本例 App/服务，验证 PID、端口和目录归属，归档证据，再清理本例安装/profile/库；下一例重新生成。细粒度编排与重置由 `scripts/run_test_case.py`、`scripts/granular_e2e.py`负责，结果按run_id核对。

### 每一步如何断言

1. `UI`：操作真实安装 App；可用既有 `auth.*`、`session.*`、`password.*`、`admin.*` 标识定位，不以其现有显示内容生成预期。密码字段输入值属于合成测试数据，截图必须遮蔽。
2. `API`：从本例真实服务的脱敏请求记录观察认证与身份校验；需要独立旁证时调用真实接口。只有明确写定的状态才断言精确码：错误凭据401、停用403、成员/首次改密访问管理403、有效身份200。未规定的输入错误码不得从代码抄成期望。
3. `DB`：只读比较动作前后账号身份/角色/启用/首次改密、有效会话数量和审计的动作/操作者/对象。失败不得改变密码、角色或启用状态；允许单独记录失败次数，但不能把失败会话当成功。会话值仅在测试内存比较，报告保存数量/校验布尔值。
4. 步骤中“无业务变化”是指账号与有效会话不变，不表示服务请求日志或失败计数必须为空。成功登录每次应建立本次真实会话；新会话不能借用种子中预置的 token。
5. 每个 TC 独立保存 `case_id/task_id/AC/数据摘要/被测提交及包摘要/逐步原始断言/UI截图或trace/服务及DB旁证/清理`。证据位于对应run的本地报告 `<case_id>/`；实际有无和结论由该run原件判定。重试不得覆盖首次失败。
6. 本文件所有场景的 SOP：设计用 [003](../../../sop/SOP-003-feature-breakdown.md)→[006](../../../sop/SOP-006-test-plan.md)→[008](../../../sop/SOP-008-baseline-check.md)；执行准备与验证用 [010](../../../sop/SOP-010-test-data.md)→[011](../../../sop/SOP-011-test-implementation.md)→[012](../../../sop/SOP-012-development.md)→[013](../../../sop/SOP-013-build-and-check.md)→[014](../../../sop/SOP-014-e2e.md)。缺项先补规范/数据/程序，不临场改变预期。

### 只读数据库核验语句

下列SQL只针对本例数据库，用 SQLite URI `mode=ro` 连接并开启 `PRAGMA query_only=ON`；目标必须是初始化清单登记的本例绝对路径。字段名依据当前0001 schema定位，期望结果由需求/种子规格及每例动作预先决定，不从查询结果自动学习。Q-SESSION的行数仅为存储旁证，不能代替真实API对会话有效性的判定；被撤销会话可以删除或标失效，不把一种内部存储方式当作需求。

```sql
-- Q-USER：只读账号身份和业务标记。
SELECT id, username, role, is_active, must_change_password
FROM users ORDER BY id;

-- Q-SESSION：只读会话数量，不输出token或其摘要。
SELECT user_id, COUNT(*) AS stored_session_count
FROM sessions GROUP BY user_id ORDER BY user_id;

-- Q-AUDIT：只读动作、执行者和对象，动作前后比较本例增量。
SELECT action, actor_id, target_id, COUNT(*) AS event_count
FROM audit GROUP BY action, actor_id, target_id
ORDER BY action, actor_id, target_id;
```

密码是否正确通过真实认证旁证，审计是否无密钥通过受限原件校验且报告只记录布尔结果。上述查询不读取 `password_hash`、`token_hash`。失败计数规格未定时，不把 `login_buckets` 当前结构与数值固定为预期。

## TC-TM001-LOGIN-01 · 有效预置成员首次登录

**任务/验收：** LOGIN-AUTH；AC-TM001-001。**前置/数据：** D42全新；无客户端凭据；已通过真实配置页选择本例API。

**类型：** `normal`。**输入：** test-alice / TEST-ONLY-alice-42!；D42空profile。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：登录后本次有效会话新增；L首次改密仍true；4个账号身份/角色不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-alice` 和 `TEST-ONLY-alice-42!` | 两项可输入，密码遮蔽；尚无已验证身份 | 尚无认证请求或会话变化 |
| 2. 点击登录 | 显示 L 的真实身份与首次改密要求；不能进入管理员功能 | 登录成功；身份ID=L、member、must_change_password=true；库新增本次会话，四个账号身份不变 |
| 3. 请求本人身份，并尝试真实管理员列表接口 | 仍显示本人；无管理员入口 | `/v1/me`200且仅本人；管理403；账号仍需改密 |

**绑定/状态/证据：** 上层 E2E-TM001-001；细粒度 `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP与重置按共用合同。

## TC-TM001-LOGIN-02 · 未知账号与已有账号的正确密码

**任务/验收：** LOGIN-AUTH；AC-TM001-002。**前置/数据：** 全新D42；确认 `test-missing` 不存在。

**类型：** `negative`。**输入：** test-missing / TEST-ONLY-alice-42!；未知账号已核对不在种子中。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：未知账号不新增；无有效会话；原4账号不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-missing` / `TEST-ONLY-alice-42!` 并登录 | 留在登录页，统一凭据错误，不透露账号不存在 | 401；不返回有效token；不自动注册账号，仍恰好4个账号、零有效会话 |
| 2. 与LOGIN-03的错误类别作独立比较 | 两者均为用户名或密码错误，不能分别提示“账号不存在/密码错误” | 相同凭据错误类别；不要求未规定的耗时完全相同 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP与重置按共用合同。

## TC-TM001-LOGIN-03 · 正确账号与错误密码

**任务/验收：** LOGIN-AUTH；AC-TM001-002。**前置/数据：** 全新D42、空profile。

**类型：** `negative`。**输入：** test-alice / TEST-ONLY-Wrong-42!；随后改输TEST-ONLY-alice-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：错密阶段无会话；正确重试才建立新会话；L密码/角色/首次标记不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-alice` / `TEST-ONLY-Wrong-42!`，点击登录 | 统一凭据错误，无已登录身份 | 401；零有效会话；L密码/角色/首次改密标记不变 |
| 2. 改输 `TEST-ONLY-alice-42!` 再登录 | 该错误不阻止一次正确尝试；显示L首次改密 | 成功建立真实会话；同一账号仍为member |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP与重置按共用合同。

## TC-TM001-LOGIN-04 · 账号和密码同时错误

**任务/验收：** LOGIN-AUTH；AC-TM001-002。**前置/数据：** 全新D42。

**类型：** `negative`。**输入：** test-missing / TEST-ONLY-Wrong-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：账号数保持4、无有效会话、权限不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-missing` / `TEST-ONLY-Wrong-42!` 并登录 | 与LOGIN-02/03相同的凭据错误类别，仍在登录页 | 401，无有效token；不新增账号或会话 |
| 2. 清空输入并观察 | 可以重新输入，不显示缓存身份 | 四账号身份及权限未改变 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP与重置按共用合同。

## TC-TM001-LOGIN-05 · 用户名为空

**任务/验收：** LOGIN-VALIDATION；AC-TM001-001/002输入规则。**前置/数据：** 全新D42；用户名精确空串 `""`，密码 `TEST-ONLY-alice-42!`。

**类型：** `negative`。**输入：** 用户名空串；密码TEST-ONLY-alice-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：空用户名不得产生会话/账号或修改既有账号。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 保持用户名空，填写密码；尝试点击登录与Enter | 不进入已登录状态，允许补填账号 | 空用户名不能获得token；是否前端禁用或显示必填提示须遵循后续交互基线，不能自行固定 |
| 2. 独立向真实登录API提交同样空用户名 | App仍不显示成功身份 | API拒绝、非2xx；无有效会话，四账号不变；精确输入错误码待接口规格明确 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。交互提示细节属未决项U1；SOP/重置按共用合同。

## TC-TM001-LOGIN-06 · 密码为空

**任务/验收：** LOGIN-VALIDATION；AC-TM001-001/002输入规则。**前置/数据：** 全新D42；`test-alice` / 空串 `""`。

**类型：** `negative`。**输入：** 用户名test-alice；密码空串。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：空密码不得产生会话，既有账号不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 填用户名、密码留空；尝试点击与Enter | 不显示已登录，能继续填写密码 | 不能产生有效认证结果；四账号/零会话不变 |
| 2. 独立API提交相同输入 | UI无成功身份 | API非2xx；零有效会话。不能把空串按合法短密码调用成功 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。U1及共用SOP/重置适用。

## TC-TM001-LOGIN-07 · 账号和密码均为空

**任务/验收：** LOGIN-VALIDATION；AC-TM001-001/002。**前置/数据：** 全新D42、全新profile。

**类型：** `negative`。**输入：** 用户名、密码均空串。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：不得自动预置新账号或创建有效会话。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 不填写任何字段，尝试点击登录及Enter | 留在登录页；不得自动使用预置账号或上轮凭据 | 不产生有效认证；零会话、四账号不变 |
| 2. 独立API提交两个空串 | 无成功状态 | API非2xx；不新增用户、不签发会话 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。U1及共用SOP/重置适用。

## TC-TM001-LOGIN-08 · 停用账号输入正确密码

**任务/验收：** LOGIN-AUTH；AC-TM001-002。**前置/数据：** D42中的D，is_active=false。

**类型：** `security`。**输入：** test-disabled / TEST-ONLY-disabled-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：D仍停用；无D有效会话或成功登录结果。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-disabled` / `TEST-ONLY-disabled-42!` 登录 | 显示账号停用的错误，停留登录页 | 403/停用类别；不签发会话；D保持停用 |
| 2. 关闭并重新打开本例App | 不恢复D身份 | 无D有效持久凭据或会话；四账号权限不变 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-LOGIN-09 · 长度合法的单字符错误密码

**任务/验收：** LOGIN-VALIDATION；AC-TM001-002及登录密码1–128规则。**前置/数据：** 全新D42。

**类型：** `boundary`。**输入：** test-alice / x；单字符错误密码。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：单字符为真实错密失败；无有效会话、原密码不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-alice` / `x` 并登录 | 凭据错误，不能误套“新密码至少12位”校验 | 真正按密码验证后401；不签发会话，密码不变 |
| 2. 核对服务旁证 | UI无身份 | 确认这是认证失败而非登录字段最小12位拒绝；零有效会话 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-LOGIN-10 · 已改密成员正常登录

**任务/验收：** LOGIN-SESSION；AC-TM001-001/002。**前置/数据：** D42-NORMAL-L；准备会话已退出；本例App处于登录页。

**类型：** `normal`。**输入：** test-alice / TEST-ONLY-Changed-42!；D42-NORMAL-L。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 D42-NORMAL-L通过真实登录/改密/退出准备。 预期变更：相对于准备快照，正常登录新增本次会话；L仍member且must_change_password=false。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-alice` / `TEST-ONLY-Changed-42!` 登录 | 显示L和“成员”；不再次强制改密 | 登录成功；真实本人身份为L/member、must_change_password=false；新增本次会话 |
| 2. 点击刷新身份 | 保持本人且服务验证成功，管理员入口不存在 | `/v1/me`200；不能返回其他账号；账号状态不变 |

**绑定/状态/证据：** 上层 E2E-TM001-001；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-LOGIN-11 · 管理员首次登录的权限限制与正常登录

**任务/验收：** LOGIN-SESSION；AC-TM001-001/002/005的首次改密约束。**前置/数据：** 全新D42中的A；本例使用合成管理员，不连接用户生产admin。

**类型：** `security`。**输入：** test-admin / TEST-ONLY-admin-42!；改后TEST-ONLY-Admin-New-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：首次会话受限；真实改密后A首次标记false、旧会话撤销；4个原身份/角色不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入 `test-admin` / `TEST-ONLY-admin-42!` 登录 | 显示A、管理员身份和强制改密；管理功能不可用 | 身份A/admin/must_change_password=true；管理接口403；未因admin角色绕过改密 |
| 2. 按PASSWORD-05的真实步骤改为 `TEST-ONLY-Admin-New-42!` | 改密成功后可访问账号管理 | A必须改密标记false；旧会话失效；新会话可访问管理 |
| 3. 退出再以新密码正常登录，加载账号 | 不再强制改密，展示准确的4个测试账号 | 管理请求成功；四个ID/角色/启用状态与D42一致，只有A的改密状态变化 |

**绑定/状态/证据：** 上层 E2E-TM001-001/003；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。生产首建admin/123456仍由E2E-TM001-005另验；SOP/重置按共用合同。

## TC-TM001-LOGIN-12 · 成员不能因登录请求或界面操作获得管理员权限

**任务/验收：** LOGIN-SESSION；AC-TM001-002。**前置/数据：** D42-NORMAL-L，真实App已用改后密码登录L。

**类型：** `security`。**输入：** test-alice / TEST-ONLY-Changed-42!；管理目标B；额外role=admin。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 D42-NORMAL-L通过真实登录/改密/退出准备。 预期变更：L仍member、B仍启用；失败管理请求不能改变账号或产生成功管理审计。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 观察本人身份及可用功能 | 仅L本人身份，role显示成员；无账号管理入口 | `/v1/me`200且role=member；DB角色仍member |
| 2. 以L真实token独立请求账号列表、审计、停用B | UI不出现管理成功 | 三个管理请求均403；B仍启用；不产生成功管理审计 |
| 3. 用真实登录API提交同样有效凭据并附加 `role:"admin"` | 不把输入的role作为可信身份 | API可以拒绝额外字段或忽略它，但不得签发管理员权限；任何返回身份必须仍为L/member。附加字段精确响应待接口规格确认 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。仅验证账号权限，不宣称后续团队统计已实现；SOP/重置按共用合同。

## TC-TM001-LOGIN-13 · 连接在认证前失败及恢复

**任务/验收：** LOGIN-SESSION；AC-TM001-001的网络失败约束。**前置/数据：** 全新D42；runner拥有API端口并在发送认证前停掉自己的服务；不接触用户服务。

**类型：** `fault`。**输入：** L正确初始凭据；本例真实服务在提交前停止后恢复。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：服务停止阶段无认证写入；恢复后才新增本次真实会话。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入L正确初始凭据并点击登录 | 明确连接失败/可重试；不能显示身份已验证 | 连接未建立，无成功API响应；数据库零会话，账号不变 |
| 2. runner重新启动同一数据库的真实服务，再从UI输入正确凭据登录 | 恢复后进入L首次改密，不要求清库或重装 | 真实认证成功、新增会话；没有前次失败伪造的会话 |

**绑定/状态/证据：** 上层 E2E-TM001-001；故障必须为本例服务生命周期；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-LOGIN-14 · 服务故障响应不能当作登录成功

**任务/验收：** LOGIN-SESSION；AC-TM001-001。**前置/数据：** D42；计划受控回环传输故障代理，故障时返回503且不转发认证，恢复时转发真实服务；受控代理已由固定fixture绑定，不mock App/API认证成功。

**类型：** `fault`。**输入：** L正确初始凭据；故障代理503不转发，随后恢复真实转发。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：503未转发阶段无会话；恢复转发后才创建本次真实会话。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 故障开启，输入L正确凭据登录 | 显示操作/连接失败，不显示已验证身份或把服务器原始异常堆栈展示给用户 | 503无token；真实认证未被转发，DB零会话 |
| 2. 恢复正常转发，再登录 | 真实服务确认后显示L首次改密 | 登录/身份成功；本次新增有效会话。不能让代理直接生成成功响应 |

**绑定/状态/证据：** 上层 E2E-TM001-001；`fault_fixture_binding=scripts/granular_service_fixture.py`、`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。具体错误文字未定义，不复制当前实现；SOP/重置按共用合同。

## TC-TM001-LOGIN-15 · 请求超时与再次操作

**任务/验收：** LOGIN-SESSION；AC-TM001-001的超时可重试要求。**前置/数据：** D42；受控传输代理接受连接但不转发/不响应；15秒超时后可重试，旧请求迟到响应不得覆盖新操作。

**类型：** `fault`。**输入：** L正确初始凭据；代理不响应且不转发；客户端15秒超时，再恢复转发并提交新操作。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：不转发阶段无会话；恢复后记录新请求会话及旧迟到请求可能产生的孤立服务端会话，客户端不得采用旧身份。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 开启不响应模式，以L正确凭据登录 | 15秒后结束等待且可重试，不永久挂起或显示已登录 | 未转发时零会话；记录服务代理尚未转发的原始旁证 |
| 2. 恢复新请求转发，先以B正确凭据登录，再释放L旧请求的迟到响应 | 显示B真实身份，迟到L响应不能覆盖新状态或保存的凭据 | B新请求经真实API验证；旧L请求如到达服务须单独记录，其会话不得被客户端采用 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`、`fault_fixture_binding=scripts/granular_service_fixture.py`；`design_status=designed`（15秒超时及迟到响应规则已确认） 、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-LOGIN-16 · 连续错误尝试的限制与恢复

**任务/验收：** LOGIN-RATE；AC-TM001-002，5分钟连续5次失败按同账号或来源限流。**前置/数据：** 全新D42；L / `TEST-ONLY-Wrong-42!`，另一账号B用于隔离检查。

**类型：** `security`。**输入：** L错误密码5分钟内连续5次；再用L与B正确凭据，核对账号或来源维度及窗口结束恢复。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：错误尝试无有效会话；第5次后本例账号或来源受限，窗口末恢复；不直接编辑DB计数以制造恢复。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 5分钟窗口内连续提交L错误密码5次，记录每次状态 | 第5次后显示受限且不能误报登录成功 | 所有错误尝试无有效会话；同账号或来源的限流记录由真实服务产生 |
| 2. 受限时输入L正确密码，再尝试同来源B正确密码 | 两次均提示受限，正确密码不能提前解锁 | 账号或来源任一受限即拒绝，两次均无有效会话；不同来源不在本步骤内推断 |
| 3. 在窗口结束前后分别尝试正确登录L | 299秒仍受限；满300秒后恢复且显示L真实身份 | 会话仅在实际认证成功时创建；测试时钟使用真实服务依赖注入，不直接改DB计数 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`、`clock_fixture_binding=scripts/granular_clock_server.py`；`design_status=designed`（5次/300秒及账号或来源维度已确认；精确错误文字仍按U1）；`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。5次/300秒现为用户批准的验收规则；执行证据仍须按run_id核对。SOP/重置按共用合同。

## TC-TM001-LOGIN-17 · 用户名长度越界

**任务/验收：** LOGIN-VALIDATION；需求用户名3–64。**前置/数据：** 每参数全新D42；密码固定 `TEST-ONLY-alice-42!`。

**类型：** `boundary`。**输入：** ab（2字符）及a重复65次；密码TEST-ONLY-alice-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：两个越界用户名均不能创建会话/账号；四账号不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。


| 参数 | 精确用户名输入 |
| --- | --- |
| 17-A | `ab`（2字符） |
| 17-B | `"a" * 65`（由数据程序生成并独立断言65字符） |

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 逐参数填入并尝试登录 | 不显示已登录；可以修改输入 | 长度非法，不能认证/自动截断成另一账号；零会话 |
| 2. 真实API直接提交同一完整字符串 | 无成功身份 | 非2xx，四账号未变；精确输入错误码待U1，不能只依赖前端长度限制 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同，每参数独立报告。

## TC-TM001-LOGIN-18 · 用户名字符非法

**任务/验收：** LOGIN-VALIDATION；ASCII字母/数字/下划线/短横线。**前置/数据：** 每参数全新D42；相同合法密码输入。

**类型：** `boundary`。**输入：** 测试用户、test.alice、test alice、test'alice；密码TEST-ONLY-alice-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：非法字符不能认证、改写或注入账号；四账号不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。


| 参数 | 精确输入 |
| --- | --- |
| 18-A | `测试用户` |
| 18-B | `test.alice` |
| 18-C | `test alice`（中间一个ASCII空格） |
| 18-D | `test'alice`（单引号） |

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 用各输入与 `TEST-ONLY-alice-42!` 尝试登录 | 不显示身份；不能悄悄转为test-alice成功 | 非法字符不能认证；零会话，账号完整性不变 |
| 2. 独立真实API提交原输入 | 无成功状态 | 非2xx，不能拼接SQL或新增账号；不以“程序没崩溃”替代拒绝断言 |

**绑定/状态/证据：** 上层 E2E-TM001-002；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-LOGIN-19 · 合法用户名最短、最长及允许字符

**任务/验收：** LOGIN-VALIDATION；用户名3–64规则。**前置/数据：** D42-BOUNDS计划分别预置启用member、must_change_password=true；密码均 `TEST-ONLY-Boundary-42!`。新增账号分别在独立库，固定ID `00000000-0000-4000-8000-000000000101`；原D42四账号保持。

**类型：** `boundary`。**输入：** a_1（3）、a重复64次、test_A-42（9）；TEST-ONLY-Boundary-42!；扩展账号ID尾101。

**数据库操作：** 准备：D42-BOUNDS独立额外账号规格；扩展生成器与SQL已绑定并需逐例核验；不得手工写成功认证状态。 预期变更：准备阶段独立库含D42加1个指定扩展账号；操作成功后该ID建立会话，角色member/首次标记true。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。


| 参数 | 精确账号 | 独立长度 |
| --- | --- | --- |
| 19-A | `a_1` | 3 |
| 19-B | `"a" * 64` | 64 |
| 19-C | `test_A-42` | 9 |

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 数据程序生成指定账号，独立只读核对后在App输入同样账号和固定密码 | 展示完整输入，不截断 | 种子包含指定ID/member/启用/首次改密；尚无会话 |
| 2. 登录并刷新本人身份 | 成功显示对应ID身份与首次改密要求 | 真正认证成功，新增本次会话；用户名输入大小写归一另见LOGIN-22，不能只因字符合法就假定大小写敏感策略 |

**绑定/状态/证据：** `data_binding=scripts/granular_bounds_fixture.py`、`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。额外账号由固定D42-BOUNDS生成并核对；SOP/重置按共用合同。

## TC-TM001-LOGIN-20 · 正确的128字符密码可登录

**任务/验收：** LOGIN-VALIDATION；登录密码1–128。**前置/数据：** D42；通过PASSWORD-07将L真实改为 `"A" * 127 + "!"`（128字符），退出准备会话；不得直接覆盖散列。

**类型：** `boundary`。**输入：** test-alice / A重复127次后接!（128）；经真实改密准备。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 先通过真实改密将L密码设为128字符并退出准备会话。 预期变更：相对128字符密码准备快照，仅新增正常登录会话；密码和权限不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入test-alice及完整128字符密码登录 | 可提交且显示L正常身份，不再次强制改密 | 密码不截断，真实验证成功；新增本次会话，member身份不变 |
| 2. 刷新本人身份 | 真实服务验证成功 | `/v1/me`200/L；不是仅前端显示成功 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。准备程序按固定用例绑定；SOP/重置按共用合同。

## TC-TM001-LOGIN-21 · 129字符登录密码拒绝且不得截断认证

**任务/验收：** LOGIN-VALIDATION；登录密码上限128。**前置/数据：** 同LOGIN-20准备，L实际密码为128字符；输入值 `"A" * 127 + "!X"`（129字符）。

**类型：** `boundary`。**输入：** test-alice / A重复127次后接!X（129）；真实密码为128字符。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 先通过真实改密将L密码设为128字符并退出准备会话。 预期变更：不能截断成正确128字符密码；无本次有效会话；账号不变。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 填入129字符并尝试登录 | 不显示已验证身份；不能截去末尾X后按正确密码登录 | 不签发有效会话；账号/密码未变 |
| 2. 独立API提交完整129字符 | 无成功状态 | 非2xx；不能通过截断变成有效128字符密码；精确错误码待U1 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-LOGIN-22 · 大小写及首尾空白的归一规则

**任务/验收：** LOGIN-VALIDATION；用户名忽略大小写，但任何空格均拒绝。**前置/数据：** 全新D42；正确L密码。参数为 `TEST-ALICE`、` test-alice`、`test-alice `。

**类型：** `boundary`。**输入：** TEST-ALICE、前置一个空格的test-alice、尾置一个空格的test-alice；L正确初始密码。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 预期变更：大写参数可为L创建本人会话，含空格参数不得创建会话；不创建新账号或升级权限。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 在各独立场景提交一种参数 | 大写TEST-ALICE可认证L；首尾任一空格均明确拒绝 | 大写输入只匹配L；含空格输入无会话，不自动trim后认证 |
| 2. 对同一输入执行真实API旁证并比较客户端行为 | UI与批准的服务匹配规则一致 | 大小写等价；任何空格拒绝；不创建新账号或越权 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`（忽略大小写且任何空格拒绝已确认）；`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-PASSWORD-01 · 当前密码错误

**任务/验收：** CHANGE-PASSWORD；AC-TM001-001/003。**前置/数据：** D42中L已真实首登，仍需改密；保存该会话仅供内存验证。

**类型：** `negative`。**输入：** 旧TEST-ONLY-Wrong-42!；新/确认TEST-ONLY-Changed-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：密码、首次标记及既有会话不因失败变更；无password_changed成功审计。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 当前密码填 `TEST-ONLY-Wrong-42!`；新/确认均 `TEST-ONLY-Changed-42!`；提交 | 明确改密失败，仍要求首次改密 | 当前凭据验证不通过；不得改散列/首次改密标记或签发成功替代会话 |
| 2. 以旧初始密码、候选新密码分别作真实登录旁证 | 不显示“密码已更新” | 旧密码仍可登录，新密码401；无password_changed成功审计；原会话未因失败被当作成功改密撤销 |

**绑定/状态/证据：** 上层 E2E-TM001-001；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。旁证会话在断言后退出并独立计数；SOP/重置按共用合同。

## TC-TM001-PASSWORD-02 · 两次新密码不一致

**任务/验收：** CHANGE-PASSWORD；需求“界面二次确认”。**前置/数据：** L已首登；当前密码 `TEST-ONLY-alice-42!`；新 `TEST-ONLY-Changed-42!`；确认 `TEST-ONLY-Changed-43!`。

**类型：** `negative`。**输入：** 旧TEST-ONLY-alice-42!；新TEST-ONLY-Changed-42!；确认TEST-ONLY-Changed-43!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：确认不符不提交成功改密；原密码/首次标记/会话不变，无成功改密审计。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 填三项并提交 | 明确两次密码不一致，不能显示改密成功 | 客户端不能提交一项并忽略另一项；没有成功改密/新token；DB首次改密仍true |
| 2. 核对动作后状态 | 仍在首次改密流程，可修改输入 | 原密码有效、候选新密码无效；无password_changed成功审计。界面防止误输不替代服务端对新密码规则的独立校验 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-PASSWORD-03 · 新密码只有11字符

**任务/验收：** CHANGE-PASSWORD；新密码最少12。**前置/数据：** L已首登；旧密码正确；新/确认均 `"A" * 10 + "!"`，独立断言长度11。

**类型：** `boundary`。**输入：** 旧L正确初始密码；新/确认A重复10次后接!（11）。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：11字符不得写成新密码；原密码有效、首次true、无成功改密审计。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 填入后尝试提交/Enter | 不接受新密码；仍需改密 | 无成功改密、无新有效会话；账号不变 |
| 2. 用本例合法token直接向真实改密API提交同一11字符值 | UI不能宣称已更新 | API非2xx；原密码有效、首次改密true、无成功改密审计；不能只测按钮禁用 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。精确输入错误码待U1；SOP/重置按共用合同。

## TC-TM001-PASSWORD-04 · 新密码等于当前密码

**任务/验收：** CHANGE-PASSWORD；新旧密码不能相等。**前置/数据：** L已首登；三字段均 `TEST-ONLY-alice-42!`。

**类型：** `negative`。**输入：** 当前/新/确认均TEST-ONLY-alice-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：同密码不得解除首次限制或撤销有效会话；无成功改密审计。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 提交三项相同的有效长度密码 | 提示新旧密码不能相同，不显示成功 | 拒绝变更；must_change_password保持true，不借此解除首次限制 |
| 2. 检查会话/审计与受限管理访问 | 仍要求改密 | 无password_changed成功审计；管理仍403；原密码与角色未变 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-PASSWORD-05 · 改密成功并撤销全部旧会话

**任务/验收：** CHANGE-PASSWORD；AC-TM001-001/003。**前置/数据：** D42；L在本例两个独立profile中以正确初始密码真实登录，获得S1/S2；由操作App持有S1，旁证进程仅内存保存S2。新密码 `TEST-ONLY-Changed-42!`。

**类型：** `security`。**输入：** L两个真实旧会话S1/S2；旧TEST-ONLY-alice-42!；新/确认TEST-ONLY-Changed-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；P05另用第二owned profile建立第二真实会话。 预期变更：L新密码生效且首次false；S1/S2均失效；新会话有效；password_changed恰好+1且actor/target=L。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 操作App输入正确当前密码，新/确认均固定新密码并提交 | 明确成功，解除首次改密，仍为L成员身份 | 密码原子更新、must_change_password=false；新会话有效，全部旧S1/S2撤销；角色/启用状态不变 |
| 2. 分别用S1/S2请求 `/v1/me`，再刷新操作App身份 | 操作App由有效新会话维持身份 | 两个旧token均401，新会话200；不能只撤销其中一个 |
| 3. 旧/新密码分别进行真实登录旁证 | 旧密码失败、新密码成功且不强制改密 | 旧密码401、新密码成功；password_changed审计恰好新增一项，actor=L、target=L，无密码/token |
| 4. 重启持有旧S2的另一profile App | 不得自动恢复身份，明确会话失效 | 服务拒绝旧token；本地旧凭据清除；不能只靠本地缓存显示L |

**绑定/状态/证据：** 上层 E2E-TM001-001/003；`automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。两个profile都由本例创建/清理；SOP/重置按共用合同。

## TC-TM001-PASSWORD-06 · 恰好12字符的新密码

**任务/验收：** CHANGE-PASSWORD；新密码下界12。**前置/数据：** D42中L已首登；新/确认均 `"A" * 11 + "!"`（12字符），当前密码正确。

**类型：** `boundary`。**输入：** 旧L正确初始密码；新/确认A重复11次后接!（12）。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：12字符完整生效；首次false，旧会话失效；成功改密审计新增。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 提交最短合法新密码 | 改密成功，不应额外要求未规定的数字/大小写组合 | 新密码生效、首次标记false、旧会话撤销，新增成功改密审计 |
| 2. 退出并用完整12字符密码登录 | 正常身份、无强制改密 | 真实验证成功；账号仍L/member |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。密码复杂度如要增加须先改需求；SOP/重置按共用合同。

## TC-TM001-PASSWORD-07 · 恰好128字符的新密码

**任务/验收：** CHANGE-PASSWORD；新密码上界128。**前置/数据：** D42中L已首登；新/确认均 `"A" * 127 + "!"`（128字符）。

**类型：** `boundary`。**输入：** 旧L正确初始密码；新/确认A重复127次后接!（128）；登录旁证127字符前缀与完整值。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：128字符完整生效，127字符前缀无效；首次false、旧会话失效；成功改密审计新增。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 旧密码正确，提交完整新/确认值 | 改密成功，不截断显示或提交的值 | 新密码生效、首次标记false、旧会话撤销 |
| 2. 退出后分别用127字符前缀 `"A" * 127` 和完整128字符登录 | 前缀失败、完整值成功 | 前缀401，完整值成功；据此排除静默截断，DB成功审计与本次操作对应 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## TC-TM001-PASSWORD-08 · 129字符的新密码

**任务/验收：** CHANGE-PASSWORD；新密码最大128。**前置/数据：** D42中L已首登；新/确认均 `"A" * 128 + "!"`（129字符）；旧密码正确。

**类型：** `boundary`。**输入：** 旧L正确初始密码；新/确认A重复128次后接!（129）。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：129字符不得保存或截断保存；原密码/首次true/会话不变，无成功改密审计。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 填入并尝试提交/Enter | 不显示改密成功，不截断后作为合法密码保存 | 未成功改密，首次标记仍true，无新有效会话 |
| 2. 独立API直接提交129字符新密码 | 无成功状态 | API非2xx；原密码仍有效；无password_changed成功审计 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。精确输入错误码待U1；SOP/重置按共用合同。

## TC-TM001-PASSWORD-09 · 改密表单必填字段

**任务/验收：** CHANGE-PASSWORD；当前密码1–128、新密码12–128与二次确认。**前置/数据：** 每行全新D42，L已首登；`OLD=TEST-ONLY-alice-42!`、`NEW=TEST-ONLY-Changed-42!`。

**类型：** `negative`。**输入：** 当前/新/确认分别缺失的四行参数09-A至09-D；OLD=L初始密码；NEW=TEST-ONLY-Changed-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：四个参数均不得写密码、解除首次标记或产生成功改密审计。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。


| 参数 | 当前 / 新 / 确认 |
| --- | --- |
| 09-A | `""` / NEW / NEW |
| 09-B | OLD / `""` / `""` |
| 09-C | OLD / NEW / `""` |
| 09-D | `""` / `""` / `""` |

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 按参数填字段并尝试点击/Enter | 不能完成改密，保留首次改密状态并可补填 | 无成功改密/新token；账号及原密码不变 |
| 2. 对09-A/09-B/09-D独立向API提交相应当前/新密码 | UI不能宣称成功 | API非2xx、无成功改密审计；09-C的确认字段属于UI误输保护，不能用API没有确认字段判为绕过认证 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。每行单独报告，U1及共用SOP/重置适用。

## TC-TM001-PASSWORD-10 · 改密请求发送前断网

**任务/验收：** CHANGE-PASSWORD；AC-TM001-001/003网络失败不伪造成功。**前置/数据：** D42中L已首登；runner在操作前停掉自己的服务，确认未有未完成改密请求。

**类型：** `fault`。**输入：** L正确旧密码及固定改后密码；发送前关闭本例真实服务后恢复。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：提交前连接失败阶段DB不变；恢复后真实提交才改密并撤销旧会话、审计+1。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 输入正确旧密码与固定新密码并提交 | 显示连接失败，不显示密码已更新或已验证成功 | TCP认证连接未建立，数据库密码/标记/会话不因该请求变化 |
| 2. 恢复真实服务后重新提交相同改密 | 服务确认后才显示成功 | 实际密码更新、旧会话撤销、成功审计新增一次 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。本例只断言请求前连接失败；“服务已提交但响应丢失”结果不确定，不能套用DB不变预期，须另立恢复需求。SOP/重置按共用合同。

## TC-TM001-PASSWORD-11 · 当前密码上界与越界

**任务/验收：** CHANGE-PASSWORD；当前密码1–128。**前置/数据：** 先按PASSWORD-07真实改好L的128字符密码；新密码固定 `TEST-ONLY-Second-New-42!`。两参数各自独立准备。

**类型：** `boundary`。**输入：** 当前128字符正确值或129字符越界值；新/确认TEST-ONLY-Second-New-42!。

**数据库操作：** 准备：本例全新D42 seed42；程序生成并执行带归属/空库检查的seed.sql；操作前只读快照。 先通过真实改密将L密码设为128字符并退出准备会话。 L通过真实App登录；不以SQL生成已登录/改密成功。 预期变更：128字符正确旧密码可变更；129字符旧密码拒绝且DB不变；两行分别准备/核验。 只读核验：只读Q-USER、Q-SESSION、Q-AUDIT并对照动作前后快照；有效性以真实/v1/me及旧/新密码旁证确认；不导出散列/token。


| 参数 | 当前密码 | 预期 |
| --- | --- | --- |
| 11-A | `"A" * 127 + "!"`，128字符 | 可真实验证并改密 |
| 11-B | `"A" * 127 + "!X"`，129字符 | 拒绝，不能截断成正确值 |

| 步骤与动作 | 独立预期 UI | 独立预期 API / DB |
| --- | --- | --- |
| 1. 正常登录后展开更改密码，按参数填当前/新/确认后提交 | A成功；B失败，不混用新密码长度规则 | A真实变更并撤销旧会话；B非成功且原128字符密码有效，无成功改密审计 |
| 2. B另以真实API提交完整129字符当前值 | 无成功状态 | API拒绝，不能因客户端截断限制而遗漏服务端边界 |

**绑定/状态/证据：** `automation_binding=tests/test_cases.json当前绑定`；`design_status=designed`、`execution_status=见对应run_id原件`、`evidence=见对应run_id原件`。SOP/重置按共用合同。

## 已确认决定与程序缺口

用户2026-09-30确认15秒超时、5分钟5次限流、用户名忽略大小写并拒绝空白。非法输入的验收为明确拒绝且无会话，附加角色字段不能越权；不要求以当前实现倒填逐字文案。

逐TC绑定以tests/test_cases.json和固定程序为准；执行结论只从独立run原件与结果Excel取得，不因绑定存在宣称通过。
