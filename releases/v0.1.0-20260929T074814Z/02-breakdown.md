# v0.1.0-20260929T074814Z — 功能与任务拆解

## 任务与依赖

输入：[需求](01-requirements.md)，全部任务归属 TM-001 / REQ-TM001。

| 任务 | 产出与完成标准 | 前序 | 对应用例 |
| --- | --- | --- | --- |
| TASK-TM001-PLAN | 六文档、完整追踪、SOP 修正、基线通过 | 需求 | TEST-TM001-GOVERNANCE |
| TASK-TM001-SERVER | FastAPI/SQLAlchemy/Alembic 工程、真实认证/权限/审计 API、持久会话和失败行为 | 计划、数据/测试 | E2E-TM001-001、E2E-TM001-002、E2E-TM001-003 |
| TASK-TM001-DATA | 隔离账号/数据库初始化、独立预期、安全重置、CLI | 计划、工程骨架 | TEST-TM001-SERVER、E2E-TM001-001 |
| TASK-TM001-MAC | SwiftUI 登录/改密/主页/管理、Keychain、稳定 UI 标识、原生测试 target | API 合同、工程骨架 | E2E-TM001-001、E2E-TM001-002、E2E-TM001-003 |
| TASK-TM001-UPDATE | 固定 Sparkle、HTTPS 更新源/签名测试包/失败包及真实更新用例 | Mac 工程 | E2E-TM001-004 |
| TASK-TM001-RUNNER | 原生测试执行、xcresult 解析、必测集合/摘要验证、失败证据、CI | 数据/原生测试 | E2E-TM001-001、E2E-TM001-002、E2E-TM001-003、E2E-TM001-004 |
| TASK-TM001-REVIEW | 完整回归、流程复盘、PR 与合并判定、发布阻塞记录 | 全部实现任务 | TEST-TM001-GOVERNANCE |

工程骨架可在业务红测前建立；可独立验证的服务 API/数据/源码任务并行推进，缺 native 运行不宣称业务 E2E 已完成。文件所有权在开发计划中固定。
