# v0.1.0-20260929T074814Z — 测试计划

输入：[开发计划](03-development-plan.md)、[六例详细用例](../../docs/testing/cases/01-TM-001-accounts.md)、[测试策略](../../docs/testing/strategy.md)。全部ID继续保留，旧Swift证据不替代本轮Electron。

## 用例、数据、独立预期与SOP

| 用例 | 必测观察 | 数据 |
| --- | --- | --- |
| E2E-TM001-001 | 首登改密、/me、自动登录开/关、重启、退出撤销与30天非滑动会话 | fixtures seed42，真实SQL/独立账号预期 |
| E2E-TM001-002 | 错密/停用拒绝、成员身份与管理403 | 同上，真实App+API旁证 |
| E2E-TM001-003 | 管理停启/重置/审计、旧会话与自动登录失效 | 同上，不手写成功响应 |
| E2E-TM001-005 | 生产首建仅admin123456、强制改密、重启不覆盖、备份恢复 | bootstrap_sqlite隔离副本，不读用户库 |
| E2E-TM001-006 | 内置默认、两个API配置/重启/origin隔离、更新URL保存取消重置/非法输入 | seed42/43两个owned服务和SQLite |
| E2E-TM001-004 | 非法URL、坏重定向、坏签名拒绝、有效签名100→101安装自主重启、/me恢复 | 同机owned更新源与真实固定签名高版本ZIP |

SOP-009准备真实骨架；010生成账号/SQL/expected并安全清理；011先编写真实测试和失败基线；013基础检查；014完整执行；017最终原包验证；018父门禁。详细步骤、UI标识、数据程序、独立预期以详细用例文档为准，机器ID登记在tests/acceptance.json与feature_matrix.json。

## 执行边界

当前平台macOS15 Intel。App从原始DMG安装到独占目录，Playwright指定真实executablePath，不用开发服务器，不mock IPC/API/DB。每例独立0700profile、SQLite与动态端口，经真实设置UI选择。默认49176已有用户服务，不占用、不终止、不造数；首次仅核对默认值且无token不发认证请求。

Node更新传输拒绝不安全URL/重定向，不要求Foundation ATS错误码。004升级后仅重新连接App自主启动的新PID；不能手动启动高版制造成功。检查版本/build、签名、真实包、profile及/me证据。所有成功/失败保留原始Playwright JSON、trace/截图、SQL/fixture摘要、服务日志与清理结果。

## 判定与证据

零例、漏例、跳过、重试取绿、失败、证据哈希/提交/包不匹配、缺清理均阻断。门禁独立解析原始结果，报告不能仅自报PASS。基础服务/单元测试不能替代六例。运行证据只存本地0700目录，不推Git。程序合同及字段见[当前设计](../../docs/architecture/01-electron-local.md)；新执行器计划中时保持BLOCKED，真实建立/执行后再登记结果。

## 基础验证追踪

- TEST-TM001-GOVERNANCE：文档基线/完整追踪/治理负测，验证漏例、假证据、错误候选和跳过必须阻断；这些检查不代表产品E2E。
- TEST-TM001-SERVER：隔离venv运行tests/server，涵盖真实SQLite认证/权限/撤销/生产首建/SQL生成/备份恢复；不替代App完整六例。

## 追加：视觉与可访问性检查

真实Electron窗口核对默认/760×640最小尺寸、深浅色、主要表单及配置弹窗，保留截图、检查溢出/对齐/层级/焦点与键盘操作并自主修复。此为辅助验证，不替代六例E2E；正式包必须包含最终ICNS和最新界面后重新完整回归。

## 需求阶段具体任务与TC清单

以下用例在功能实现前应完成设计。本轮是对已存在实现补做基线修订，所有新增TC未执行；六个历史场景组不是逐项覆盖证明。具体输入、步骤、预期、DB操作、类型见[根目录集合](../../TEST_CASES.md)及[结构化用例](../../tests/test_cases.json)，统一查看[项目总表](../../TokenMeter项目总表.xlsx)。

| TC | 开发任务 | AC | 设计状态 | 执行状态 |
| --- | --- | --- | --- | --- |
| TC-TM001-LOGIN-01 | TASK-TM001-LOGIN-AUTH | AC-TM001-001 | designed | 未执行 |
| TC-TM001-LOGIN-02 | TASK-TM001-LOGIN-AUTH | AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-03 | TASK-TM001-LOGIN-AUTH | AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-04 | TASK-TM001-LOGIN-AUTH | AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-05 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-06 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-07 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-08 | TASK-TM001-LOGIN-AUTH | AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-09 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-10 | TASK-TM001-LOGIN-SESSION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-11 | TASK-TM001-LOGIN-SESSION | AC-TM001-001, AC-TM001-002, AC-TM001-005 | designed | 未执行 |
| TC-TM001-LOGIN-12 | TASK-TM001-LOGIN-SESSION | AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-13 | TASK-TM001-LOGIN-SESSION | AC-TM001-001 | designed | 未执行 |
| TC-TM001-LOGIN-14 | TASK-TM001-LOGIN-SESSION | AC-TM001-001 | designed | 未执行 |
| TC-TM001-LOGIN-15 | TASK-TM001-LOGIN-SESSION | AC-TM001-001 | designed | 未执行 |
| TC-TM001-LOGIN-16 | TASK-TM001-LOGIN-RATE |  | designed | 未执行 |
| TC-TM001-LOGIN-17 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-18 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-19 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-20 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001 | designed | 未执行 |
| TC-TM001-LOGIN-21 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-LOGIN-22 | TASK-TM001-LOGIN-VALIDATION | AC-TM001-001, AC-TM001-002 | designed | 未执行 |
| TC-TM001-PASSWORD-01 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-02 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-03 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-04 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-05 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-06 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-07 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-08 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-09 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-10 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-PASSWORD-11 | TASK-TM001-CHANGE-PASSWORD | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-SESSION-01 | TASK-TM001-SESSION-PERSIST | AC-TM001-001 | designed | 未执行 |
| TC-TM001-SESSION-02 | TASK-TM001-SESSION-PERSIST | AC-TM001-001 | designed | 未执行 |
| TC-TM001-SESSION-03 | TASK-TM001-SESSION-RESTORE | AC-TM001-001 | designed | 未执行 |
| TC-TM001-SESSION-04 | TASK-TM001-SESSION-RESTORE | AC-TM001-001 | designed | 未执行 |
| TC-TM001-SESSION-05 | TASK-TM001-SESSION-RESTORE | AC-TM001-001, AC-TM001-003 | designed | 未执行 |
| TC-TM001-SESSION-06 | TASK-TM001-SESSION-MEMORY | AC-TM001-001 | designed | 未执行 |
| TC-TM001-SESSION-07 | TASK-TM001-SESSION-EXPIRY | AC-TM001-001 | designed | 未执行 |
| TC-TM001-SESSION-08 | TASK-TM001-SESSION-LOGOUT | AC-TM001-001 | designed | 未执行 |
| TC-TM001-SESSION-09 | TASK-TM001-CONFIG-LOCKS, TASK-TM001-SESSION-LOGOUT | AC-TM001-001, AC-TM001-006 | designed | 未执行 |
| TC-TM001-SESSION-10 | TASK-TM001-SESSION-PERSIST | AC-TM001-001, AC-TM001-006 | designed | 未执行 |
| TC-TM001-ADMIN-01 | TASK-TM001-ADMIN-RESET | AC-TM001-003 | designed | 未执行 |
| TC-TM001-ADMIN-02 | TASK-TM001-ADMIN-RESET | AC-TM001-003 | designed | 未执行 |
| TC-TM001-ADMIN-03 | TASK-TM001-ADMIN-STATUS | AC-TM001-002, AC-TM001-003 | designed | 未执行 |
| TC-TM001-ADMIN-04 | TASK-TM001-ADMIN-STATUS | AC-TM001-003 | designed | 未执行 |
| TC-TM001-ADMIN-05 | TASK-TM001-ADMIN-GUARD | AC-TM001-003 | designed | 未执行 |
| TC-TM001-ADMIN-06 | TASK-TM001-ADMIN-AUDIT | AC-TM001-003 | designed | 未执行 |
| TC-TM001-BOOTSTRAP-01 | TASK-TM001-BOOTSTRAP-INIT | AC-TM001-005 | designed | 未执行 |
| TC-TM001-BOOTSTRAP-02 | TASK-TM001-BOOTSTRAP-INIT | AC-TM001-005 | designed | 未执行 |
| TC-TM001-BOOTSTRAP-03 | TASK-TM001-BOOTSTRAP-PRESERVE | AC-TM001-005 | designed | 未执行 |
| TC-TM001-BOOTSTRAP-04 | TASK-TM001-BOOTSTRAP-RESTORE | AC-TM001-005 | designed | 未执行 |
| TC-TM001-CONFIG-01 | TASK-TM001-CONFIG-API | AC-TM001-006 | designed | 未执行 |
| TC-TM001-CONFIG-02 | TASK-TM001-CONFIG-API | AC-TM001-006 | designed | 未执行 |
| TC-TM001-CONFIG-03 | TASK-TM001-CONFIG-API | AC-TM001-006 | designed | 未执行 |
| TC-TM001-CONFIG-04 | TASK-TM001-CONFIG-UPDATE | AC-TM001-004, AC-TM001-006 | designed | 未执行 |
| TC-TM001-CONFIG-05 | TASK-TM001-CONFIG-UPDATE | AC-TM001-006 | designed | 未执行 |
| TC-TM001-CONFIG-06 | TASK-TM001-CONFIG-LOCKS | AC-TM001-001, AC-TM001-004, AC-TM001-006 | designed | 未执行 |
| TC-TM001-UPDATE-01 | TASK-TM001-UPDATE-DISCOVER | AC-TM001-004 | designed | 未执行 |
| TC-TM001-UPDATE-02 | TASK-TM001-UPDATE-VERIFY | AC-TM001-004 | designed | 未执行 |
| TC-TM001-UPDATE-03 | TASK-TM001-UPDATE-VERIFY | AC-TM001-004 | designed | 未执行 |
| TC-TM001-UPDATE-04 | TASK-TM001-UPDATE-VERIFY | AC-TM001-004 | designed | 未执行 |
| TC-TM001-UPDATE-05 | TASK-TM001-UPDATE-VERIFY | AC-TM001-004 | designed | 未执行 |
| TC-TM001-UPDATE-06 | TASK-TM001-UPDATE-INSTALL | AC-TM001-004 | designed | 未执行 |
| TC-TM001-UPDATE-07 | TASK-TM001-UPDATE-INSTALL | AC-TM001-001, AC-TM001-004, AC-TM001-006 | designed | 未执行 |
| TC-TM001-UPDATE-08 | TASK-TM001-UPDATE-ISOLATION | AC-TM001-004 | designed | 未执行 |
| TC-TM001-UI-01 | TASK-TM001-UI-CONSISTENCY | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-UI-02 | TASK-TM001-UI-CONSISTENCY | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-UI-03 | TASK-TM001-UI-CONSISTENCY | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-CATALOG-01 | TASK-TM001-CASE-CATALOG | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-CATALOG-02 | TASK-TM001-CASE-CATALOG | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-CATALOG-03 | TASK-TM001-CASE-CATALOG | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-RECORDS-01 | TASK-TM001-CASE-RECORDS | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-RECORDS-02 | TASK-TM001-CASE-RECORDS | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-GATE-01 | TASK-TM001-CASE-GATE | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-GATE-02 | TASK-TM001-CASE-GATE | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |
| TC-TM001-GATE-03 | TASK-TM001-CASE-GATE | AC-TM001-001, AC-TM001-002, AC-TM001-003, AC-TM001-004, AC-TM001-005, AC-TM001-006 | designed | 未执行 |

### 新基线的执行绑定

2026-09-30 用户确认六项规则时，逐 TC 程序与精确门禁仍在准备，`manifest.execution_bindings_status` 当时保持 `planned`。截至 2026-10-01，78 条 TM-001 父 TC、38 条参数变体和 11 条独立辅助用例已有固定程序；`scripts/check_granular_bindings.py` 实际注册检查 95/95 个 Playwright 入口，精确选择含 `#` 的变体也通过。正式本机门禁须同一候选依次核对逐 TC 原件、11 条辅助原件、独立审计及六组补充 E2E；`manifest.execution_bindings_status` 据程序与门禁负测改为 `ready`。这一字段只表示绑定可执行，最终干净候选的产品验收和发布结论仍由本次门禁原件决定。

表中“未执行”是设计初始状态，不继承旧六组结论。已有开发包的各批真实结果、失败历史和联合复核见[07 实际测试结果](07-test-results.md)；开发包结果不能替代干净最终包。

## 2026-09-30 已确认的验收边界

依据：用户选择“采用这组规则（推荐）”。下述规则覆盖对应旧的待定项；设计已确定，运行结果仍按证据记录。

- `TC-TM001-LOGIN-15`：登录请求15秒超时，显示可重试连接错误；等待期间不显示已登录。取消后的迟到响应不得覆盖新操作或保存其凭据。
- `TC-TM001-LOGIN-16`：以规范化账号和来源IP分别计数：任一维度5分钟内连续5次认证失败后，后续登录返回429/rate_limited；包括受限期间正确密码。窗口结束自动恢复。
- `TC-TM001-LOGIN-22`：用户名忽略ASCII字母大小写，使用原账号身份；含任何空白（包括首尾空格、制表、换行）直接拒绝，不trim后认证，不创建会话。
- `TC-TM001-SESSION-04`：自动登录15秒超时显示可重试错误，不能使用缓存身份；重试后须经真实/v1/me确认。迟到响应不能覆盖新操作。
- `TC-TM001-SESSION-10`：拒绝符号链接、硬链接、非当前uid、宽权限文件或目录等异常凭据对象；不跟随链接、不改哨兵，显示重新登录提示。缺其他uid测试条件记录BLOCKED。
- `TC-TM001-UPDATE-05`：ZIP最大512 MiB（536870912字节），解压内容最大2 GiB（2147483648字节），边界本身允许、超过即拒绝；大小、摘要、签名或包身份校验失败均保留当前版本。

### 固定执行与时间边界

所有动作和断言由仓库固定代码执行，AI只调用入口。LOGIN-16初次批次已使用真实五分钟等待通过；随后批次为避免重复等待，使用测试专用服务启动器注入只读文件时钟，真实App仍经实际API完成请求，明确断言299秒仍受限、300秒恢复。不修改数据库限流计数，不改主机时间，不提供生产控制接口。SESSION-07使用同一方式检查30天会话边界。每例保留时钟初值/终值、UI轨迹、服务请求和SQLite旁证；组件自测不能代替App运行结果。


## 本轮全量缺陷修复

2026-10-01用户要求所有已开发功能必测用例通过，按[回归修复计划](09-regression-fixes.md)执行。验收条件不变，原FAIL/BLOCKED保留，新包重新验证。
