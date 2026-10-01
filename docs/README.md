# 文档导航

执行工作先读 [SOP 总索引](../sop/README.md) 与对应详细文件；本页用于查阅设计和规范。

| 要做的事 | 阅读入口 |
| --- | --- |
| 统一查看项目全流程 | [项目总表Excel](../TokenMeter项目总表.xlsx)、[当前0.2版本档案](../releases/v0.2.0-20261001T034118Z/00-manifest.json)、[TM-003草稿导航](../releases/v0.3.0-20261001T034652Z/README.md) |
| 查看所有用例集合 | [根目录TEST_CASES](../TEST_CASES.md)、[任务与用例规范](standards/test-cases.md) |
| 确定文档规范 | [文档标准](standards/documentation.md)、[元数据登记](catalog.json) |
| 查项目会话和文档交接 | [项目会话体系](project-sessions.md)：文档、SOP、开发总控与需求会话 |
| 定义和执行任一步骤 | [SOP 总索引](../sop/README.md)：先查工作，再完整读独立文件 |
| 理解全流程顺序 | [全流程框架](lifecycle.md) |
| 阅读完整设计 | [总设计计划](design-plan.md) |
| 查阅问题、决定与经验 | [复盘索引](retrospectives/README.md)：9月历史、10月1日前段及10月1日晚至2日续篇 |
| 接续上次任务 | [当前状态](status.md) |
| 确认产品需求 | [产品约定](product/README.md)、[独立验收登记](../tests/acceptance.json)、[功能矩阵](../tests/feature_matrix.json) |
| 修改模块/数据/接口 | [架构](architecture/README.md) |
| 查看或初始化 SQLite 库、执行造数 SQL | [数据库目录与操作](../database/README.md)、[测试数据 SOP](../sop/SOP-010-test-data.md) |
| 开发或修复功能 | [开发流程](standards/development.md)、[功能模板](templates/feature.md)、[修复模板](templates/bugfix.md) |
| 按功能查测试用例、步骤与独立预期 | [详细用例总索引](testing/cases/README.md) |
| 验证最终内部安装包 | [Electron 本机设计](architecture/01-electron-local.md)、[本版发布预案](../releases/v0.1.0-20260929T074814Z/05-release-plan.md)、[安装与本机服务](releases/02-installation.md) |
| 编写/运行 E2E | [测试策略](testing/strategy.md)、[产品 E2E SOP](../sop/SOP-014-e2e.md)、[数据集登记](../tests/datasets.json) |
| 判定能否发布 | [发布门禁](standards/release.md) |
| 安排版本 | [路线图](roadmap.md)、[变更日志](../CHANGELOG.md) |
| 按版本追踪需求到发布 | [版本命名与索引](standards/versioning.md)、[当前版本档案](../releases/current.json) |

## 文档维护原则

产品文档定义预期行为；架构文档定义实现边界；功能矩阵连接需求、用例、数据和脚本；运行产生的证据说明实际是否通过。四者用途不同，不能用文档中的“计划支持”代替已执行结果。

每次变更同步相应文档，避免复制多份互相矛盾的规格。新增复杂架构决策放入 `docs/decisions/`，写明问题、决定、替代方案和后果，再从架构文档链接。
