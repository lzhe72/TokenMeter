# 功能测试用例总索引

本目录按功能保存可读的详细 test case。文件名前缀 `01`–`12` 对应功能顺序；每份文件内以稳定 `E2E-TMxxx-NNN` 标题定位具体用例，包含验收、前置/数据、步骤、独立预期、自动化绑定/SOP、证据和状态。

## 为什么之前在 docs 找不到逐功能用例

原先资料分散在三处：[版本测试计划](../../../releases/v0.1.0-20260929T074814Z/04-test-plan.md)给出版本范围与场景摘要，[验收清单](../../../tests/acceptance.json)和[功能矩阵](../../../tests/feature_matrix.json)保存机器追踪，[原生测试源码](../../../apps/macos/TokenMeterUITests/TM001AccountUITests.swift)实现具体操作。SOP-006 未规定必须在 docs 提供逐功能详细用例及导航，因此有程序和摘要，却缺少方便人和下一轮 agent 查阅的文档层。

现在 [SOP-006](../../../sop/SOP-006-test-plan.md)要求本索引与各功能独立文件。详细用例、JSON 与测试源码使用同一稳定ID，行为变化必须同步；详细文档不能代替原始测试结果。

## 按功能查找

| 顺序 | 功能和详细文件 | 用例 | 当前执行状态 |
| --- | --- | --- | --- |
| 01 | [TM-001 账号、登录及最小更新器](01-TM-001-accounts.md) | E2E-TM001-001–006，6例 | 最新开发CI两平台各6/6 PASS；最终包资格另验 |
| 02 | [TM-002 首次授权](02-TM-002-permissions.md) | E2E-TM002-001–002，2例 | planned，缺权限fixture和原生绑定 |
| 03 | [TM-003 Codex采集](03-TM-003-codex-collection.md) | E2E-TM003-001–004，4例 | planned，缺已验证raw与采集程序 |
| 04 | [TM-004 Claude Code采集](04-TM-004-claude-collection.md) | E2E-TM004-001–004，4例 | planned，缺已验证raw/子代理/分支数据 |
| 05 | [TM-005 用量统计](05-TM-005-usage-statistics.md) | E2E-TM005-001–002，2例 | planned，仅有部分标准化语义样例 |
| 06 | [TM-006 费用估算](06-TM-006-cost-estimates.md) | E2E-TM006-001–002，2例 | planned，基础价格样例可生成，扩展数据待建 |
| 07 | [TM-007 团队同步](07-TM-007-team-sync.md) | E2E-TM007-001–004，4例 | planned，缺故障fixture/同步与权限绑定 |
| 08 | [TM-008 CSV导出](08-TM-008-csv-export.md) | E2E-TM008-001–002，2例 | planned，缺导出数据/自动化 |
| 09 | [TM-009 预算提醒](09-TM-009-budget-alerts.md) | E2E-TM009-001–002，2例 | planned，缺周期/阈值/通知fixture |
| 10 | [TM-010 完整软件更新](10-TM-010-software-updates.md) | E2E-TM010-001–003，3例 | planned；TM-001最小更新已测不等于此功能完成 |
| 11 | [TM-011 数据与迁移](11-TM-011-data-migration.md) | E2E-TM011-001–004，4例 | planned；MySQL只在未来独立版本验证 |
| 12 | [TM-012 菜单栏与诊断](12-TM-012-menu-diagnostics.md) | E2E-TM012-001–002，2例 | planned，缺菜单/诊断/系统设置绑定 |

共12个功能、37个稳定用例：6例有真实原生执行，31例属于未来设计。未来规划文件中的具体输入数值是测试合同设计，不是已经生成的原始日志或已运行证据；每例逐项列出缺失程序、SQL、数据、UI及未确定行为。

## 执行顺序和证据

1. 查 [SOP总索引](../../../sop/README.md)，读取对应独立SOP；从本页进入功能文件，核对本轮需求、版本和依赖。
2. 按 [SOP-010](../../../sop/SOP-010-test-data.md)准备隔离账号、数据与SQL，按 [SOP-011](../../../sop/SOP-011-test-implementation.md)核对真实自动化绑定。不能在生产库造回归数据。
3. 在实际有完整Xcode/GUI的Mac执行 `python3 scripts/quality_gate.py iteration`。它执行应有集合并校验原始证据，`0=PASS`、`1=FAIL`、`2=BLOCKED`；当前完整集合为TM-001六例，每个支持架构全部执行。
4. 查程序输出的 `.local/e2e/<run-id>/result.json`、逐例 `native.xcresult`、fixture摘要、截图/日志和父门禁。CI执行从对应run下载原始artifact核对，不能从文档标题推定PASS。
5. 最终DMG另按 [SOP-017](../../../sop/SOP-017-package-validation.md)和 [SOP-018](../../../sop/SOP-018-release-gate.md)验证实际安装包并生成通行证；文档及开发用例通过不授予分发资格。

TM-001最近一次已核验开发结果为 [CI 36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502)，macOS15 arm64/Intel各六例及父门禁PASS；[PR #2](https://github.com/lzhe72/TokenMeter/pull/2)已合并（`e011857`）。该证据只适用于该被测候选。首个内部版本按用户确认仅声明macOS15两架构；其他macOS主版本在后续独立扩展验证。新源码或新安装包须重新验证；最新发布状态见[状态页](../../status.md)。

## 维护约定

- `tests/acceptance.json`定义独立验收条件；矩阵定义功能状态、数据和执行绑定；本文档解释操作和独立预期。不得从现有少量测试反向删减验收条件。
- 功能为planned可无可执行绑定，但必须写清缺项；进入实现前补齐真实程序、数据和原生测试。基础JSON造数不代表厂商日志兼容或产品E2E。
- 每次功能/断言/数据改变，同时维护对应详细文件、验收清单、矩阵、版本测试计划及Changelog。文档登记和追踪检查须通过，执行结果另由机器报告提供。
- 失败、跳过、缺证据、零用例或未解释的不稳定结果阻断；不得手写PASS或复用不匹配候选的历史结果。
