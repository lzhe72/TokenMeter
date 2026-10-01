# v0.4.0-20261001T040433Z — TM-004 功能点与任务（draft）

输入：[需求](01-requirements.md)、[既有矩阵](../../tests/feature_matrix.json)、[Claude详细场景](../../docs/testing/cases/04-TM-004-claude-collection.md)。本版 REQ-TM004 / TM-004 的功能点为授权源发现、主/子代理调用解析、跨文件去重、持久增量、诊断与恢复。TM-002/003 是前置依赖，不在此分支复制实现。

| TASK | AC / 输入 | 产出、模块边界和可检查完成条件 | 前序 | TC（设计见04） |
| --- | --- | --- | --- | --- |
| TASK-TM004-SOURCE | 001/004；TM-002授权句柄、项目目录 | Electron主进程只遍历授权根下已确认的会话与子代理日志；失权停止、重授补扫，拒绝越界路径；预览截断与采集覆盖分别判定。 | TM-002已提交接口及可续扫合同 | TC-TM004-SOURCE-01/02/03/04 |
| TASK-TM004-PARSER | 001/003；有版本来源的完整原始行 | 仅对已验证 schema 抽取每次调用的 usage、模型、时间、主/子标志及来源标识；不保留正文。 | raw样本、TM-003事件合同 | TC-TM004-PARSER-01/02/03 |
| TASK-TM004-LINEAGE | 001/002/004；父子与fork来源证据 | 在可证明父子关系时将子调用归属正确项目；可证明继承历史时跨会话去重；歧义进入诊断而不污染可信量。 | raw父子/fork样本、PARSER | TC-TM004-LINEAGE-01/02/03/04/05 |
| TASK-TM004-INCREMENTAL | 001/002/004；追加、半行、重复片段、跨来源身份冲突、重启 | 持久读取游标、事件唯一键与事务；完整行才提交；Codex/Claude 同原生 ID 不误去重、Claude fork 副本不重复；重扫与重授幂等。 | TM-003 SQLite身份合同、PARSER | TC-TM004-INCREMENTAL-01/02/03 |
| TASK-TM004-DIAGNOSTIC | 003/004；缺usage、未知格式、读取失败 | UI 明确区分可信零、未知、缺失和无授权；只出诊断码/数量，不泄漏正文或完整路径。 | TM-003诊断接口、PARSER | TC-TM004-DIAG-01/02 |
| TASK-TM004-DATA | 001–004；隔离CLI 2.1.126或官方raw样本 | 固化版本化原始fixture、生成/追加/半行/撤权程序、独立expected和SQLite只读检查；不读开发者真实日志。 | raw来源、TM-002/003数据合同 | TC-TM004-DATA-01 |
| TASK-TM004-E2E | 001–004；最终安装App、真实服务、隔离SQLite | 将全部细TC绑定仓库固定Playwright Electron测试；每条逐步原始记录和清理，目标与历史已交付功能全量回归。 | SOURCE→DATA、TM-001包执行器 | TC-TM004-E2E-01 |
| TASK-TM004-RELEASE | 001–004；完整候选 | 文档/矩阵/总表/Changelog同步、构建与DMG安装门禁，交总控集成。 | E2E与前版本全回归 | TC-TM004-RELEASE-01 |

依赖顺序：TM-001稳定已提交 Electron 基线 → TM-002授权接口 → TM-003规范事件/SQLite/诊断 → 有来源的 Claude raw 证据 → 设计基线 → 数据与红测 → 实现 → 完整 E2E → 包/门禁。当前仅本版独立规划可推进；依赖任务状态 BLOCKED。各 TASK 的具体失败、权限和边界组合由 [测试计划](04-test-plan.md)逐条规定，不能用四个 E2E 汇总 ID 替代细TC。

`TASK-TM004-INCREMENTAL` 与 `TASK-TM004-PARSER` 另拆出已打开只读文件句柄的辅助开发切片 `TC-TM004-CORE-01/02/03`。它只验证LF提交、带密钥的前缀校验、重扫、限额与损坏行诊断，固定输入见[reader合成fixture](../../tests/fixtures/tm004-reader-core-slice.json)；TM-002授权、TM-003原子事件+SQLite游标、源文件身份、账号/覆盖及原20条产品TC仍为独立依赖。TM-002当前`fileIdentityDigest`包含size/mtime，正常追加就变化，不能直接作为稳定游标身份；产品接入需另核对稳定匿名身份和前缀MAC口径。此切片不拆除或降级原产品目标。
