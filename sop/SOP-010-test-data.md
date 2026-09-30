# SOP-010 测试数据

**修订：** 9　**状态：** baselined　**适用：** all

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
7. 仅在 SOP-009 约定的专用 CI Mac 中由更新 fixture 程序生成临时自签代码身份、专用签名 Keychain、测试 CA、回环 HTTPS appcast 和有效/无效 EdDSA 包。该身份仅供开发迭代，不授权内部或公开发布。原生 runner 每例从隔离根创建唯一0700 `credentials` 目录；将解析后的绝对路径以 `TM_TEST_CREDENTIALS_DIR` 传给候选与高版本构建，并核对两者 `TMTestCredentialsDirectory` Info.plist 键及首次 XCTest 环境一致，拒绝 symlink、`/var` 别名和生产路径；无效路径显式报 `invalid_credential_directory`。两个包共用签名身份与专用凭据目录，但不读取生产 `~/Library/Application Support/TokenMeter/credentials` 或旧 Keychain。`cloudflared` 用本次 CA 池验证回环 TLS，App 正常验证公开 HTTPS，Sparkle 真正校验 EdDSA；随机 Bearer 控制无效→有效更新内容，未授权请求拒绝。证据只保存脱敏请求、摘要和目录安全状态，不保存 token、密码、私钥或测试账号。逐项停止隧道/HTTPS服务、恢复签名 Keychain 列表、精确删除本例拥有的临时目录并核对清理；失败与清理错误分别记录。缺固定版本工具、有效 HTTPS、签名或清理结果为 BLOCKED。

8. 保留过去 admin 信任撤销超时与跨版本 Keychain 弹窗的真实历史证据；当前 App 使用文件凭据，不重试旧会话 Keychain 的信任/ACL 路径。`python3 scripts/native_environment.py` 先验证隔离签名、双段 TLS 与清理，再由014执行真实004：无效包拒绝、有效包安装重启、默认自动登录经 `/v1/me` 无交互恢复；旧预览用户第一次使用新版本重新登录一次。工具探针 READY 不等于产品成功；缺环境保持 BLOCKED，不能缩小六例集合。

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
