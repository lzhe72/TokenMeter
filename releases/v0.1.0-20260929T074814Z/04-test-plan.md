# v0.1.0-20260929T074814Z — 测试计划

## 范围和追踪

REQ-TM001 / TM-001；应执行四个目标场景，当前没有此前已交付产品功能。独立验收来源为 [产品规格](../../docs/product/README.md) 与 [验收清单](../../tests/acceptance.json)，不得从剩余测试反向删条件。

| 用例 | 任务 | 数据和独立预期 |
| --- | --- | --- |
| TEST-TM001-GOVERNANCE | TASK-TM001-PLAN、TASK-TM001-REVIEW | 结构/基线/追踪/门禁负向回归；只证明工具合同 |
| TEST-TM001-SERVER | TASK-TM001-DATA、TASK-TM001-SERVER | 实际 SQLite + FastAPI；错密/停用/节流/过期/越权/事务/迁移/密码与会话撤销；网络 smoke |
| E2E-TM001-001 | TASK-TM001-SERVER、TASK-TM001-DATA、TASK-TM001-MAC、TASK-TM001-RUNNER | test-alice 首次改密→本人主页→重启真实恢复→退出→旧 token 被拒绝 |
| E2E-TM001-002 | TASK-TM001-SERVER、TASK-TM001-MAC、TASK-TM001-RUNNER | member无管理员入口且API403；错误密码提示；test-disabled不能登录 |
| E2E-TM001-003 | TASK-TM001-SERVER、TASK-TM001-MAC、TASK-TM001-RUNNER | admin改密后停用/启用/重置bob；bob旧会话失效，新密码须改密；UI显示真实审计 |
| E2E-TM001-004 | TASK-TM001-UPDATE、TASK-TM001-RUNNER | 真实HTTPS隔离源，拒绝签名损坏包且原版不变；有效高版本包替换并重启，/me验证原账号仍可用 |

## 账号、数据和重置

四个固定 UUID（尾号0001–0004），用户名 test-admin/test-alice/test-bob/test-disabled；角色admin/member/member/member，disabled停用，初始均强制改密。口令仅在隔离 fixture；每次运行创建新临时库，由真实CLI迁移/导入；禁止连生产库、扫描真实Codex/Claude日志或在App预埋测试登录。

账号配置和expected按固定seed42生成；真实密码 hash 使用随机盐，逻辑账号可重建但不要求安全散列逐字节相同。数据源与生成产物摘要均记录。重置只允许带所有权标记的本次目录，拒绝symlink/外来文件；更新私钥和测试CA只在隔离目录，不能提交或上传。

## 执行方案与证据

测试实现前的接口失败记录由pytest产生；native测试以XCUITest驱动真实App→API→真实账号库。核心链路不得mock。每例重置数据、退出App并清隔离Keychain以免互相污染。native run保存原始xcresult、逐例状态/截图、App/service/fixture/source摘要、候选SHA、运行nonce/时刻；比较预期集合与原生标识，无失败、缺失、跳过才可通过。

本机Python检查可执行；当前native运行受完整Xcode缺失阻塞。迭代先在明确的macOS15 arm64与Intel runner验证开发环境；发布仍须macOS14最低版本和所有声明支持的OS/架构，以及生产MySQL、最终签名/公证。不能把开发矩阵通过当作正式支持范围通过。

数据/测试程序初始未建立，因此manifest与矩阵保持空绑定并登记任务，入口真实建立后同步。程序就绪不等于已执行，测试不齐全时禁止将功能标implemented。适用SOP：009→010→011→012→013→014，更新验证017，发布判定018。

## 临时信任与异常恢复回归

按009/010验证GitHub托管Mac身份及非交互sudo权限，拒绝开发者机器、自托管或权限缺失环境。codeSign/ssl信任只针对本次证书，独立核对撤销及精确清理；命令失败/超时记录操作名，不打印密码/私钥。增加主操作失败与清理同时失败的回归，两个原因都必须保留；资源未创建时要验证不存在，不能无条件忽略清理错误。工具回归通过后，004仍必须实际完成签名、HTTPS更新及清理才可通过。

## 判定

确定性断言失败=FAIL，缺工具链、数据或有效证据=BLOCKED；PASS必须真实执行全部集合。发布单独要求平台/签名/可信CI证据齐全。机器报告不能由agent手写；缺条件不阻止独立子任务，但不能合并冒称完整产品迭代。

## 更新包输入负测

`python3 -m unittest discover -s apps/macos/tests -p 'test_*.py' -v` 验证更新包程序拒绝非HTTPS源、ad-hoc身份、非本机明文API、错误权限/畸形私钥、符号链接和已有输出。这些隔离工具测试不替代真实Mac构建、签名校验和004更新用例。
