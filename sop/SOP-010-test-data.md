# SOP-010 测试数据

**修订：** 8　**状态：** baselined　**适用：** all

## 目的与范围

用程序生成、导入和重置所有测试用户/数据，使测试可重复并与生产数据隔离。

## 触发条件

新增场景、重跑测试、准备旧版本升级数据或恢复干净测试状态。

## 前置条件

SOP-006 已定义角色、数据、独立预期与来源版本；SOP-009 指定安全测试目标。

## 输入

数据集登记、固定种子/参考时间、用例 ID、生成/初始化/重置程序和所有权标记。

## 执行步骤

1. 当前基础示例执行 python3 scripts/test_data.py generate --run-id demo --seed 42；若目录已存在先确认所有权和是否仍需证据，不能覆盖他人运行。
2. 核对 .local/test-runs/demo/ 的 users、usage、prices、expected、manifest 和所有权标记，检查固定时钟及文件摘要。
3. 识别 fixture_kind=normalized-test-spec：当前只产生合成账号资料和规范化用量，不创建真实数据库用户、不证明供应商原始日志解析。
4. TM-001 使用 `python3 tests/server/fixtures.py generate --run-id <本次唯一ID> --seed 42` 生成 `.local/account-fixtures/<本次唯一ID>/` 下的账号、独立 expected、manifest 和所有权标记。它不直接创建数据库。原生 runner 负责新建每例专用 SQLite、数据库所有权标记，调用 `python3 -m server.tokenmeter_server.cli migrate --database-url <隔离SQLite地址>` 和 `provision --database-url <同一地址> --accounts <users.json绝对路径> --test-run-id <同一ID>`，随后启动真实服务。第006例复用该账号程序，但必须由 runner 分别初始化两套独立 SQLite/服务；第一套独占默认端口49176，第二套使用另一个本机临时端口，并独立核对账号/会话归属。测试账号文件不能导入未标记的数据库或远程数据库。第006例的第二服务程序尚未实现时记录 BLOCKED，不把文档计划当作已就绪数据。
5. 根据独立 expected 核对生成结果；将新增边界/故障数据加入程序，禁止仅靠手工改数据。同步 manifest 的真实数据程序绑定；测试程序未全部建立时 `program_bindings_status` 保持 planned，待 SOP-011 核对全部真实绑定后改 ready。
6. 归档需要的证据后，对基础 demo 执行 `python3 scripts/test_data.py reset --run-id demo`；TM-001 对应执行 `python3 tests/server/fixtures.py reset --run-id <同一ID>`。这两个入口仅删除各自精确匹配的生成文件。产品库、进程、测试 Keychain 及升级临时资源由原生 runner 单独清理并记录；清理失败不能隐去。
7. 仅在 SOP-009 约定的专用 CI Mac 中由更新 fixture 程序准备临时代码签名身份、测试 CA、回环 HTTPS appcast 与签名有效/无效包。候选和高版本包使用同一专用 Keychain 身份；`cloudflared` 用本次 CA 池验证回环 TLS，将临时公开 HTTPS 地址写入隔离 App 更新配置及 appcast。App 对公开域名执行正常 TLS 验证，Sparkle 对包执行真实 EdDSA 验证；控制端点由原生用例携随机 Bearer 通过同一 HTTPS 隧道切换无效→有效，未授权请求必须拒绝，证据只保存脱敏请求记录和摘要。不得改系统/管理员信任、关闭 TLS 验证或将私钥、账号、密码、数据库上传到隧道或证据目录。按本次资源精确停止隧道/HTTPS 服务并删除专用 Keychain，核对没有遗留进程、Keychain 或私钥；主操作和清理同时失败时分别保留，未创建的资源先确认不存在。缺少固定版本的 `cloudflared`、可验证的公开 HTTPS、签名或清理结果时记录 BLOCKED。未来采集场景仍需各工具已支持版本的原始日志，规范化样例不能替代。

8. 保留此前 admin 域撤销信任超时的历史证据，不再重试该已知失败路径。新路径先由 `python3 scripts/native_environment.py` 验证身份、双段 TLS 和完整清理，再由014运行真实第004例。独立工具回归或探针 READY 不等于升级成功；必须取得实际 App 对无效包拒绝、有效包升级、会话恢复以及六例完整回归的原生证据。若隧道或证书链不可用，保持 BLOCKED，先修复可重复环境和程序，不能缩小必测集合。

9. 本机固定回归库运行 `python scripts/bootstrap_sqlite.py init-test --run-id <唯一测试ID>`，程序生成并执行 `database/test/seed.sql`，其中含四个回归账号的随机盐 Argon2 散列和固定参考时钟，不含明文口令。先读 `database/test/.tokenmeter-test-database.json` 与数据库内环境标记，再执行 `python scripts/bootstrap_sqlite.py verify`；SQL 只允许匹配的已迁移空测试库，错误环境或已有账号必须拒绝。需要重造时，确认测试服务已停，运行 `python scripts/bootstrap_sqlite.py rebuild-test --current-run-id <原ID> --run-id <新ID>`；先归档旧材料，异常中断按 `repair-test-material` 恢复，禁止删除或重建生产库。原生 runner 的逐例临时 SQLite 仍是产品回归隔离目标，第005例仅在临时根验证生产初始化流程；实际用户库从不作为测试造数目标。

## 输出

可复现用户/fixture/expected、数据摘要、真实初始化结果或缺口，以及重置/清理记录。

## 成功与失败判据

同一输入得到相同逻辑数据，目标隔离，预期独立，场景所需真实数据已进入正确产品入口才可验收。Argon2 的随机盐应保留，不能为字节一致固定密码散列。仅生成 JSON 不能视作账号或产品 E2E 已通过。

## 异常恢复

生成拒绝已有目录、额外文件、缺失文件或符号链接时先核对归属并保留现场；不使用无范围删除绕过安全检查。失败数据修回生成程序后重建。

## 证据位置

fixture manifest、生成/重置退出码、用例与数据绑定、实际数据库初始化报告；测试密码只存在隔离测试材料，报告不含真实凭据。

## 下一步

执行 [SOP-011 测试实现](SOP-011-test-implementation.md)；已有测试由 [SOP-014](SOP-014-e2e.md) 调用本步骤。
