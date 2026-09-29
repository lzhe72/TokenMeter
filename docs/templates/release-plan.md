# 本轮发布预案

**release_id：** `<release_id>`　**doc_id：** `<doc_id>`　**文档状态：** `draft`

**适用 SOP：** [SOP-007 发布预案](../../sop/SOP-007-release-plan.md)；文档基线 [SOP-008](../../sop/SOP-008-baseline-check.md)、发布判定 [SOP-018](../../sop/SOP-018-release-gate.md)、文档变更 [SOP-024](../../sop/SOP-024-document-change.md)。

## 输入引用

- 本轮需求、拆解、技术设计、开发/测试计划及 manifest：`<实际引用>`。
- [版本规范](../../docs/standards/versioning.md)、[发布门禁](../../docs/standards/release.md)、同编号 Changelog：`<实际条目引用>`。
- 上一稳定版、兼容矩阵、迁移与恢复设计：`<实际引用；首次无基线为 null>`。

## 范围与当前状态

- 本轮功能/修复、用户可见变化和兼容影响：
- 发布状态：`未发布`；实际产品门禁记录：`null（未执行）`；已有阻塞项：`<实际缺项或无>`。
- release_id、计划 tag/Release 名称与语义版本：
- 客户端/服务端支持平台、数据库和升级来源：

## 构建、验证与分发

| 阶段 | 前置条件与真实入口 | 待交付产物/结果 | 失败处理 | SOP |
| --- | --- | --- | --- | --- |
| 最终包构建/验证 | `<已存在命令；否则 null 和实现任务>` | `<产物及安装升级报告约定>` | `<停止条件>` | [017](../../sop/SOP-017-package-validation.md) |
| 发布门禁 | `<完整原生证据与受保护执行器>` | `<机器报告；仅 PASS 签发 passport>` | `<FAIL/BLOCKED 处理>` | [018](../../sop/SOP-018-release-gate.md) |
| Git 发布 | `<有效 passport、同 SHA/产物及权限>` | `<同 release_id 的 tag/Release>` | `<停止和保留证据>` | [019](../../sop/SOP-019-git-release.md) |
| 部署与更新分发 | `<实际目标和入口>` | `<版本/健康/摘要核对>` | `<恢复触发条件>` | [020](../../sop/SOP-020-deployment.md) |

- 签名、公证、安装、升级及更新清单验证方式：
- 生产数据库迁移、备份和恢复验证：`<引用 SOP-016 方案或不适用依据>`。
- 服务端/客户端部署顺序、凭据来源和最小所需权限；文档中不存凭据：
- 回退条件、目标版本/数据及恢复后检查：`<按 SOP-021 的实际方案>`。

数据库步骤采用 [SOP-016](../../sop/SOP-016-database-migration.md)，异常恢复采用 [SOP-021](../../sop/SOP-021-rollback.md)。所有未知命令或产物位置保持 `null` 并记录补齐任务；预案不赋予发布资格。

## 输出、验收与证据

- 输出：本轮 `05-release-plan.md`、同编号 Changelog 与 manifest 发布索引。
- 文档验收：范围、平台、构建、完整门禁、升级/迁移、分发和恢复已有确定方案，缺失执行条件明确登记。
- 实际证据字段：`release_id`、候选 SHA、`run_id`、受信运行身份、原生报告、产物/数据/场景摘要、机器判定、passport、实际 tag/Release/部署记录。
- 证据位置：`<实际外部运行/资产引用；尚未生成则 null>`。候选提交后由执行器生成，保存在被测源码提交之外；不得手写 PASS、回填“已上线”或覆盖旧证据。
- 执行验收：只有受保护 CI 校验同一候选和最终产物取得完整 PASS 才能发布；已测产物不能在发布时重新构建替换。
- 下一步：开发前走 [SOP-008](../../sop/SOP-008-baseline-check.md)；执行后按 [SOP-022](../../sop/SOP-022-archive-handoff.md)归档，并在本轮 `06-iteration-record.md` 记录实际结果。
