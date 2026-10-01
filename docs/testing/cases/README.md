# 功能测试用例总索引

**用户统一查看入口：仓库根[TokenMeter项目总表.xlsx](../../../TokenMeter项目总表.xlsx)，随Git版本提交。** 仓库根[全部用例集合](../../../TEST_CASES.md)保存可追踪的用例目录，本文提供详细操作文档导航；本版本[需求到发布导航](../../../releases/v0.1.0-20260929T074814Z/README.md)串联需求、功能点、任务、测试设计、结果与发布记录。

## 主表摘要与独立结果表

当前根项目总表按0.2基线及TM-003/004/005草稿目录重新导出并回读：11个Sheet、260行用例摘要（219条父用例、41个稳定变体）和13次 TM-001 历史测试批次；SHA-256为`aebe4e58f29fd88fca1d043531c2999d09fa791ebd3eac9257762070e5207c47`，本机回读收据在`.local/workbook/verification.json`。`05测试用例`汇总功能、任务、输入、独立预期、DB操作、类型和状态；`06测试批次`保存run_id、候选、范围、结果摘要及独立结果Excel入口。TM-001 独立候选 `d2db551` 的门禁 PASS 与结果 Excel 已生成，其批次若缺原始结果表读回/候选身份核对就保持未登记；不能把旧13批次当成本次结果。完整动作、SQL及绑定设计保存在[tests/test_cases.json](../../../tests/test_cases.json)和下列详细文档。

每次真实执行单独生成`.local/test-results/<run_id>/TokenMeter测试结果-<run_id>.xlsx`，包括该次逐例/逐步实测、失败和证据索引，只留本机。dev07当前可读表位于同run目录的`revisions/02/`，时间列已修正并经桥接和回读校验，含5个Sheet、6个历史场景组、131条事件、14条更新请求及37条证据/缺口记录；原表保留。Excel导出PASS与产品FAIL分别保留。表格是原始证据的可读整理，不替代原件或发布门禁；未执行TC仍标未执行。

## 先设计，再开发和记录

按[SOP索引](../../../sop/README.md)和[用例规范](../../standards/test-cases.md)执行：需求/验收条件→功能点→具体TASK→逐项TC/变体与数据→文档基线→自动化/功能实现→按既定步骤测试→逐次记录→门禁。用例表必须列功能、任务、输入、每步动作和预期、DB准备/预期变化/只读核验、类型、数据/SOP、绑定和状态。

原先只有版本计划、机器矩阵与测试源码，缺少可读文档；后来补的六个聚合场景仍不足以说明所有输入和边界已覆盖。01a/01b/01c补齐精细设计，当前绑定以`tests/test_cases.json`及变体清单为准。历史精细 BLOCKED/FAIL 和独立候选 `d2db551` 的门禁 PASS 各有原件；逐项结论只看对应 run，不能将旧聚合 PASS 回填。

## TM-001精细用例入口

| 顺序 | 详细文档 | 用途和当前状态 |
| --- | --- | --- |
| 01 | [账号及最小更新器场景组](01-TM-001-accounts.md) | 保留E2E-TM001-001–006聚合入口，不能代表完整精细覆盖 |
| 01a | [登录与改密任务级场景](01a-TM-001-login-scenarios.md) | 登录组合、空值/边界、权限与改密；逐项结果见独立run原件 |
| 01b | [会话、管理、配置和升级任务级场景](01b-TM-001-session-admin-release-scenarios.md) | 19个具体任务、34个TC，含逐步预期/DB核验；逐项结果见独立run原件 |
| 01c | [交付与门禁检查](01c-TM-001-delivery-checks.md) | 规范、数据、包、执行记录、门禁和发布任务；辅助检查需固定程序执行，不冒充产品E2E |

## 按功能查找

| 顺序 | 功能和详细文件 | 用例 | 当前执行状态 |
| --- | --- | --- | --- |
| 01 | [TM-001 账号、登录及最小更新器](01-TM-001-accounts.md) | E2E-TM001-001–006，6个聚合场景组 | 旧 dev07 与精细 FAIL/BLOCKED 原件保留；独立候选 `d2db551` 门禁 PASS、78父TC和38变体全PASS；最终 `master` 未重验、未发布 |
| 02 | [TM-002 首次授权](02-TM-002-permissions.md) | E2E-TM002-001–002，2组；28条父TC、35个稳定变体 | 设计已过SOP-008基线；固定fixture、自动化与产品E2E尚未执行 |
| 03 | [TM-003 Codex采集](03-TM-003-codex-collection.md) | E2E-TM003-001–004，4组；原27条逐项TC加3条无授权模块辅助TC | draft、unexecuted；隔离研究样例已有，正式数据/程序与本版SOP-008未完成 |
| 04 | [TM-004 Claude Code采集](04-TM-004-claude-collection.md) | 4组、20条细TC | draft/unexecuted；已见部分2.1.126原生形态，零值、嵌套与完整来源仍待证据 |
| 05 | [TM-005 用量统计](05-TM-005-usage-statistics.md) | 2组、原32条产品细TC与新增3条纯统计辅助TC、6变体 | 整版draft/unexecuted；辅助切片待SOP-008独立核对，双来源原生与产品绑定待建 |
| 06 | [TM-006 费用估算](06-TM-006-cost-estimates.md) | E2E-TM006-001–002，2例 | planned，基础价格样例可生成，扩展数据待建 |
| 07 | [TM-007 团队同步](07-TM-007-team-sync.md) | E2E-TM007-001–004，4例 | planned，缺故障fixture/同步与权限绑定 |
| 08 | [TM-008 CSV导出](08-TM-008-csv-export.md) | E2E-TM008-001–002，2例 | planned，缺导出数据/自动化 |
| 09 | [TM-009 预算提醒](09-TM-009-budget-alerts.md) | E2E-TM009-001–002，2例 | planned，缺周期/阈值/通知fixture |
| 10 | [TM-010 完整软件更新](10-TM-010-software-updates.md) | E2E-TM010-001–003，3例 | planned；TM-001最小更新仍在验收，不代表此功能完成 |
| 11 | [TM-011 数据与迁移](11-TM-011-data-migration.md) | E2E-TM011-001–004，4例 | planned；MySQL只在未来独立版本验证 |
| 12 | [TM-012 菜单栏与诊断](12-TM-012-menu-diagnostics.md) | E2E-TM012-001–002，2例 | planned，缺菜单/诊断/系统设置绑定 |


这里保留12功能、37个历史概要场景组：TM-001六组、未来功能31组。它们与根总表中的精细TC不是同一层级，不相加为“已测试数量”。TM-002 已完成28条逐项父TC与35个必跑变体的设计基线，TM-003 原27条目标TC与新增3条模块辅助TC仍是草稿；两版均无产品PASS。TM-004/005的细TC已接入根机器目录但仍是草稿；是否形成基线以各自最终文档和SOP-008原件为准；TM-006 至 TM-012 仍按对应功能规划处理，不能拿概要文件直接开始实现。

## 实际结果和发行资格

dev07历史开发证据为`.local/ci/e2e-dev-probe-07/`：六组实际尝试、五组PASS、004FAIL，后续清理独立保存，不覆盖FAIL。首轮精细全量`local-7feea03dd72e4eddba0651cede8fd23d`机器结果为BLOCKED（109条预期、16条PASS、93条BLOCKED）；新版`local-343e54113b0b442383e80f137013014b`已结束FAIL，独立复核表为78父用例62 PASS/9 FAIL/7 BLOCKED、38变体31 PASS/7 FAIL；后续定向验证和UI01单例各有独立Excel，不改原始失败。详见[07实际测试结果](../../../releases/v0.1.0-20260929T074814Z/07-test-results.md)。

历史[CI36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502)是SwiftUI/XCUITest在双架构Mac的六例及父门禁PASS，随[PR#2](https://github.com/lzhe72/TokenMeter/pull/2)合并；不能转移到当前Electron候选、最终DMG或新增TC。当前默认本机macOS15 Intel，其他平台未验证；无需完整Xcode。

正式验收按[SOP-014](../../../sop/SOP-014-e2e.md)记录精确TC/变体每步实测；从原DMG安装按[SOP-017](../../../sop/SOP-017-package-validation.md)，由[SOP-018](../../../sop/SOP-018-release-gate.md)独立核对完整集合、原件、候选、包与清理。独立候选 `d2db551` 有机器通行证；当前最终 `master` 未验、正式版本未发布，见[08发布记录](../../../releases/v0.1.0-20260929T074814Z/08-release-record.md)及[状态页](../../status.md)。

## 维护约定

- [验收清单](../../../tests/acceptance.json)是独立需求依据，[功能矩阵](../../../tests/feature_matrix.json)保存场景组与程序绑定；具体任务、TC、根总表和逐次证据须能双向追踪。
- 每条TC、参数变体分别登记设计/程序/执行状态；程序存在不等于执行成功，构建/截图/API组件测试不替代真实App场景。
- 测试仅用本轮拥有的合成账号、数据库和SQL，按[SOP-010](../../../sop/SOP-010-test-data.md)生成/重置；不访问用户生产库或真实凭据来凑数据。
- 开发定位先写明失败、变更和目标TC再运行；正式候选完整回归。相同条件下不反复全量重试取绿，不删失败变体或补写PASS。
- 结果自动导出已接入`local_e2e.py`，保留原JSON，导出失败非零返回；环境修复后可在全新目录补导同一原始结果，保留失败收据，不需重跑App。
- 候选测试期间不改Git跟踪总表和登记文件，执行和门禁结束后再同步摘要，继续引用原被测SHA。
- 行为/数据/程序变化同时更新文档、主表摘要、版本计划和Changelog。根Excel随文档和Git版本同步；每次独立测试结果Excel、原始DMG、trace、运行数据库与通行证只保存在本机。按run_id追加结果，保留历史FAIL和独立清理记录，不用新表覆盖旧结论。腾讯在线方案已取消，未发生在线写入。
