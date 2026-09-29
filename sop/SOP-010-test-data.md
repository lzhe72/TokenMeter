# SOP-010 测试数据

**修订：** 4　**状态：** baselined　**适用：** all

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
4. TM-001 使用 `python3 tests/server/fixtures.py generate --run-id <本次唯一ID> --seed 42` 生成 `.local/account-fixtures/<本次唯一ID>/` 下的账号、独立 expected、manifest 和所有权标记。它不直接创建数据库。原生 runner 负责新建每例专用 SQLite、数据库所有权标记，调用 `python3 -m server.tokenmeter_server.cli migrate --database-url <隔离SQLite地址>` 和 `provision --database-url <同一地址> --accounts <users.json绝对路径> --test-run-id <同一ID>`，随后启动真实服务。测试账号文件不能导入未标记的数据库或远程数据库。
5. 根据独立 expected 核对生成结果；将新增边界/故障数据加入程序，禁止仅靠手工改数据。同步 manifest 的真实数据程序绑定；测试程序未全部建立时 `program_bindings_status` 保持 planned，待 SOP-011 核对全部真实绑定后改 ready。
6. 归档需要的证据后，对基础 demo 执行 `python3 scripts/test_data.py reset --run-id demo`；TM-001 对应执行 `python3 tests/server/fixtures.py reset --run-id <同一ID>`。这两个入口仅删除各自精确匹配的生成文件。产品库、进程、测试 Keychain 及升级临时资源由原生 runner 单独清理并记录；清理失败不能隐去。
7. 仅在专用 CI Mac 中由更新 fixture 程序准备测试 CA、HTTPS appcast 和签名有效/无效包。遵循009的hosted Mac检查，通过`sudo -n /usr/bin/security`在admin域设置信任；结束时按本次证书或摘要撤销对应信任及导入的证书，不删除其他信任项。命令失败和超时保留安全操作名，清理失败不能覆盖原始异常；未创建成功的资源先核对确实不存在，再记录清理完成。账号文件、密码、数据库、私钥不放入上传证据目录；只保存摘要和不含凭据的执行结果。缺少实际入口或环境时保持 BLOCKED。未来采集场景仍需各工具已支持版本的原始日志，规范化样例不能替代。

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
