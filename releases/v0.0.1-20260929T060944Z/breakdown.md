# v0.0.1-20260929T060944Z — 功能拆解

## 输入

[需求](requirements.md) REQ-GOV-001 至 REQ-GOV-005。

## 功能与任务

| 功能 | 任务 | 关联需求 | 交付 |
| --- | --- | --- | --- |
| TM-000 | TASK-GOV-001 | REQ-GOV-001 | SOP 总索引/25 独立文件、全流程框架、文档标准、产品/架构/总设计、Codex 约定 |
| TM-000 | TASK-GOV-002 | REQ-GOV-002 | 12 项产品功能与 30 个计划 E2E 场景、数据登记、模板、SOP |
| TM-000 | TASK-GOV-003 | REQ-GOV-003 | 合成用户/数据生成、安全重置和独立预期 |
| TM-000 | TASK-GOV-004 | REQ-GOV-004 | 规范检查、BLOCKED 执行记录、防止伪通过的工具测试 |
| TM-000 | TASK-GOV-005 | REQ-GOV-005 | 版本查询程序/规范、同名档案、Changelog、Git 命名与通行证合同 |

## 依赖与拆分规则

先确定规范和全流程，再完成文档合同；工具仅用于验证该基础，不能把它们当作产品发布。产品 TM-001 至 TM-012 的拆解详见 [功能矩阵](../../tests/feature_matrix.json)；每轮只选取本次目标，保留此前已交付功能回归。

## 输出

[开发计划](development-plan.md)、[测试计划](test-plan.md)。
