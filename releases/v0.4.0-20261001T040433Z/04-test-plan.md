# v0.4.0-20261001T040433Z — TM-004 测试计划（draft）

输入：[需求](01-requirements.md)、[TASK拆分](02-breakdown.md)、[设计](03-development-plan.md)、[测试策略](../../docs/testing/strategy.md)、[现有详细场景](../../docs/testing/cases/04-TM-004-claude-collection.md)。本计划先定义独立判据；本机已取得2.1.126主、单层子代理及复制历史 fork 的原生 JSONL 子集，但改写ID等结构、TM-002/003 SQLite/IPC 和 Electron 安装执行器未就绪，全部产品用例程序绑定为 `null`、执行为 BLOCKED。规划总量仅用于约束 oracle，不把合成 API 响应视为实际计费或已通过的产品 fixture。


**开发切片实况：** 纯解析器单元测试已覆盖部分 PARSER/LINEAGE/INCREMENTAL/DIAG 编号的已证实输入边界，桌面单元总36/36、治理452/452；这些单元检查不满足细TC要求的真实授权、HMAC/SQLite、UI/IPC、逐步原件或安装包。四个来源缺口与整版draft继续保留，详见[06记录](06-iteration-record.md)。

**新增reader辅助切片：** `TC-TM004-CORE-01/02/03` 使用固定[合成输入](../../tests/fixtures/tm004-reader-core-slice.json)及[逐步判据](../../docs/testing/cases/04-TM-004-claude-collection.md#无授权依赖的reader辅助切片)，分别验证半行/限额、前缀MAC/重扫和损坏完整行。输入为测试拥有的已打开只读文件，DB操作不适用；每例新临时目录并只清理本例资源。独立SOP-008仅可给这三条与相应TASK纯reader部分切片就绪；原20条产品TC、四组摘要、真实授权、SQLite事务、App E2E与整版0.4基线仍draft/BLOCKED。现有模块单元结果不可回填为原产品TC PASS。
## 场景与任务覆盖

| 汇总场景 | AC | 对应具体 TASK → 细TC | 独立数字/错误边界 |
| --- | --- | --- | --- |
| E2E-TM004-001 | AC-TM004-001 | SOURCE→TC-TM004-SOURCE-01、TC-TM004-SOURCE-03、TC-TM004-SOURCE-04；PARSER→TC-TM004-PARSER-01、TC-TM004-PARSER-03；LINEAGE→TC-TM004-LINEAGE-01；INCREMENTAL→TC-TM004-INCREMENTAL-03；E2E→TC-TM004-E2E-01 | 主M100/10、子S200/20，仅2调用、total330；预览超限续扫变体 M100/10+S50/5=165，未扫完不得显示历史完整；跨工具同ID冲突变体见细TC |
| E2E-TM004-002 | AC-TM004-002 | LINEAGE→TC-TM004-LINEAGE-02、TC-TM004-LINEAGE-03、TC-TM004-LINEAGE-04、TC-TM004-LINEAGE-05；INCREMENTAL→TC-TM004-INCREMENTAL-01、TC-TM004-INCREMENTAL-02、TC-TM004-INCREMENTAL-03 | fork继承M不增，新N50/5后165；P半行不增，补全后187；跨工具同ID仍分别计、Claude复制历史不增 |
| E2E-TM004-003 | AC-TM004-003 | PARSER→TC-TM004-PARSER-02；DIAGNOSTIC→TC-TM004-DIAG-01；DATA→TC-TM004-DATA-01 | 支持结构完整 usage 可核对；未知结构和缺usage非零值，可信汇总不变 |
| E2E-TM004-004 | AC-TM004-004 | SOURCE→TC-TM004-SOURCE-02、TC-TM004-SOURCE-04；DIAGNOSTIC→TC-TM004-DIAG-02；E2E→TC-TM004-E2E-01；RELEASE→TC-TM004-RELEASE-01 | 失权不读取，恢复后旧M/S/继承不增，新N50/5，total385；页间失权的覆盖仍不完整 |

表内细TC使用完整稳定ID。逐条输入、动作和分步预期见[04详细场景的细TC章节](../../docs/testing/cases/04-TM-004-claude-collection.md#本版细tc设计草稿)。每个 TASK 至少有一条 TC；正式基线必须把这些条目补入 `tests/test_cases.json`、`TEST_CASES.md`、总表，并与版本 manifest 核对，不能仅以本表覆盖。原有四个 E2E ID 保留为场景组，本版细TC现为20条。本机原生探针使主、单层子代理、未改写 UUID 的 `--fork-session` 及同 ID/usage 的双内容块有可追溯样本；PARSER-03 双块子样本的独立预期为31+9=40、一次调用，不能逐行累加为80。畸形合成 API 无 usage 却被 CLI 写成0/0，不能用于证明有效零。新增 SOURCE-04 将 TM-002 预览上限与内部续扫覆盖分开，新增 INCREMENTAL-03 固定跨来源同字面调用ID、Claude复制与冲突的独立数字。SOURCE-03 嵌套、LINEAGE-03 改写 UUID、LINEAGE-04 `fork-context-ref` 及 LINEAGE-05 冲突反例仍须原生样本与真实产品绑定，不能据静态字段或单次探针判通过。

## 数据、账号、SQL和重置

- 每例使用新0700目录和独占动态回环端口、合成 `test-alice` / 项目A、单例 SQLite 与全新 Electron profile。账号用 `tests/server/fixtures.py` 同一生产初始化流程生成，但只指向本次隔离库；不访问固定生产库、旧 App、默认49176服务，也不从真实 `~/.claude` 取数据。动态地址通过真实配置 UI 选择。
- `claude_raw` 需要真实来源版本、每个原始文件/行的 SHA256、生成命令、父子和 fork 线索、独立 expected。测试写入的是获授权隔离目录中的原始格式；append、半行、复制、失权/重授权动作由固定程序执行。规范化数据仅能自检解析后存储，不能证明 Claude 兼容。
- SQLite schema 在 TM-003 之后确定。届时将每例所需 `SELECT` 的事件唯一键、归属、token和诊断行写入固定查询文件，程序只读检查实际 DB；禁止运行时临场 SQL 造成功结果。预期计数由本段数字和具体 raw 内容独立给出，不调用产品统计函数。每例 reset 只删除自身创建的 profile、源、服务和库，保留原始报告与输入摘要。
- 同一候选先定向运行 TM-004 失败基线，再修实现；完整迭代集合为 TM-001、TM-002、TM-003 所有已交付 TC 及 TM-004 本版全部 TC/变体。不能通过缺少上游提交把已交付功能排除。

## 自动化与证据

仓库固定入口计划为 `scripts/run_test_case.py --case-id TC-TM004-... --package-manifest <原始包清单>`；本分支旧基点没有该程序。TM-001 干净候选 `3467dc1` 已有此入口，但其 `granular_e2e.py` 只接受 `TC-TM001-*`、只映射 TM-001 spec，不能执行本版20条 TC；须在最终整合树按固定清单扩展 runner/Playwright/数据与门禁绑定。真正绑定后每步由 Playwright Electron 操作 DMG 安装 App，真实服务/SQLite 与授权 UI，不注入解析/认证 IPC mock。按 SOP-010 造数据，SOP-011 固定程序，SOP-014 逐TC运行并留 JSON、trace、必要截图、DB只读结果、fixture摘要与清理记录；输出独立 `TokenMeter测试结果-<run_id>.xlsx` 并汇总到项目总表。程序、SQL或 raw 证据任一缺失即 BLOCKED；测试断言失败为 FAIL，不能重试覆盖。当前暂无 run_id、包摘要或 PASS 原件。

## 进入 SOP-008 的缺项

TM-001 Electron基线及 TM-002/003 稳定提交、TM-002 授权内部续扫/覆盖合同与 TM-003 `usage-identity-v1` 实际 schema/迁移、Claude raw 全部变体和 fork 改写 ID 证据、完整逐TC机器清单/SQL/重置、总表生成器与本版详细用例的未决原始字段，尚未完成。`baseline_pending` 的 TC 不进入产品实现；结构检查通过只能表示草稿可定位。之后需 SOP-007 发布预案，再 SOP-008 严格 baseline；当前不得将文档标为 baselined。
