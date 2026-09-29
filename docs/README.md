# 文档导航

执行工作先读 [SOP 总索引](../sop/README.md) 与对应详细文件；本页用于查阅设计和规范。

| 要做的事 | 阅读入口 |
| --- | --- |
| 确定文档规范 | [文档标准](standards/documentation.md)、[元数据登记](catalog.json) |
| 定义和执行任一步骤 | [SOP 总索引](../sop/README.md)：先查工作，再完整读独立文件 |
| 理解全流程顺序 | [全流程框架](lifecycle.md) |
| 阅读完整设计 | [总设计计划](design-plan.md) |
| 接续上次任务 | [当前状态](status.md) |
| 确认产品需求 | [产品约定](product/README.md)、[独立验收登记](../tests/acceptance.json)、[功能矩阵](../tests/feature_matrix.json) |
| 修改模块/数据/接口 | [架构](architecture/README.md) |
| 查看或初始化 SQLite 库、执行造数 SQL | [数据库目录与操作](../database/README.md)、[测试数据 SOP](../sop/SOP-010-test-data.md) |
| 开发或修复功能 | [开发流程](standards/development.md)、[功能模板](templates/feature.md)、[修复模板](templates/bugfix.md) |
| 编写/运行 E2E | [测试策略](testing/strategy.md)、[原生 E2E SOP](../sop/SOP-014-e2e.md)、[数据集登记](../tests/datasets.json) |
| 判定能否发布 | [发布门禁](standards/release.md) |
| 安排版本 | [路线图](roadmap.md)、[变更日志](../CHANGELOG.md) |
| 按版本追踪需求到发布 | [版本命名与索引](standards/versioning.md)、[当前版本档案](../releases/current.json) |

## 文档维护原则

产品文档定义预期行为；架构文档定义实现边界；功能矩阵连接需求、用例、数据和脚本；运行产生的证据说明实际是否通过。四者用途不同，不能用文档中的“计划支持”代替已执行结果。

每次变更同步相应文档，避免复制多份互相矛盾的规格。新增复杂架构决策放入 `docs/decisions/`，写明问题、决定、替代方案和后果，再从架构文档链接。
