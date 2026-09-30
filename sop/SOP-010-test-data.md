# SOP-010 测试数据

**修订：** 12　**状态：** baselined　**适用：** all

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
7. 由第004例更新 fixture 在执行 App 的同一台 Mac 创建隔离回环 HTTP 更新源，默认 `http://127.0.0.1:49177/appcast.xml`；先独占49177，不复用未知进程。配置修改场景只保存合法合成地址并测试重启、恢复默认与非法地址拒绝，不连接第二更新源。GitHub `macos-15` 与 `macos-15-intel` 各自在自身机器启动服务，绝不访问用户本机端口。fixture 生成受控高版本测试 App、有效/无效 EdDSA 签名包和独立预期；App 固定公钥，测试私钥仅存在本次隔离目录且不写入仓库、构建报告或生产配置。临时自签代码身份与专用 Keychain 可用于 CI 的开发迭代，不能替代最终内部分发包的签名/Gatekeeper 证据；本机若仅有 CLT，代码签名方式需先实测，不预设 ad-hoc 包可完成 Sparkle 升级。随机 Bearer 控制无效→有效 appcast 内容，未授权控制请求拒绝；测试服务只绑定回环，不公开账号、私钥或数据库。每例只保有一组活跃 `SigningIdentity` 与 `UpdateSource`，准备、真实 App 请求、安装与请求核对均使用同一实例，到最终 `finally` 才逐项停止源服务、恢复临时 Keychain 搜索列表并核对清理。任何端口、签名、准备或清理缺项都保留原始错误并使该例 BLOCKED。

   第004例在同一49177源上按固定顺序提供四种测试数据，不新建隧道或服务：先由鉴权的 `control/forbidden` 将appcast的enclosure设为 `http://example.invalid/update.zip`，该保留域名仅作非回环HTTP负测，App在下载前拒绝；再由鉴权的 `control/redirect` 将enclosure设为本机 `/redirect.zip`，该路径返回302到同一非回环HTTP地址，App须得到ATS `NSURLErrorDomain -1022`，不能把DNS失败当作预期；然后由原有鉴权 `control/invalid` 恢复完整坏签名包，最后原有 `control/valid` 发布完整有效包。控制端点沿用原随机Bearer/固定key授权，不改变公开响应的秘密边界；runner将三条负测控制URL分别通过 `TM_TEST_UPDATE_FORBIDDEN_CONTROL_URL`、`TM_TEST_UPDATE_REDIRECT_CONTROL_URL`、`TM_TEST_UPDATE_INVALID_CONTROL_URL` 注入UI测试。每阶段保存请求顺序与脱敏预期，前三阶段构建号均保持100，有效阶段升级至101；不能让非回环主机接收真实请求。

8. 原生 runner 每例在隔离根创建唯一0700 `credentials` 目录，把解析后的绝对路径以 `TM_TEST_CREDENTIALS_DIR` 传给候选与高版本构建，核对两者 `TMTestCredentialsDirectory` Info.plist 键及首次 XCTest 环境一致，拒绝 symlink、`/var` 别名和生产路径；无效时显式报 `invalid_credential_directory`。两构建不读取生产 `~/Library/Application Support/TokenMeter/credentials` 或旧 Keychain；升级后默认自动登录必须由真实 `/v1/me` 验证。独立 `native_environment.py` 若保留，只能作为零产品用例的同机回环准备诊断，结果不得给已销毁资源后的004取绿；其现有公网 Quick Tunnel 源码在迁移前不可当成新基线的运行证据。测试源、凭据及产物在结束时精确清理，保存脱敏请求、摘要、权限与清理结果，不保存 token、口令、私钥或测试账号。

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
