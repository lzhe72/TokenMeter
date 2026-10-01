# TM-005 功能点与任务草案

**release_id：** `v0.5.0-20261001T034729Z`
**状态：** draft / baseline_pending。

## 需求到任务

| 功能点 / 验收 | TASK | 输入与产出 | 依赖 / 完成条件 |
| --- | --- | --- | --- |
| `FP-TM005-01` · 可信事件 / 两项 AC | `TASK-TM005-EVENT-CONTRACT` | 读取 TM-003/004 不可变 `usage_event` 与诊断，核对 `principal_key/source/source_event_key`、UTC 时间、三个子项的已知/未知状态和模型 `null`；输出当前身份的可信事件集合 | 两来源稳定 schema 与原生版本；不读取正文，重复不入账，身份冲突不静默完成 |
| `FP-TM005-02` · 范围和汇总 / `AC-TM005-001` | `TASK-TM005-RANGE-QUERY` | 以本地日期、IANA 时区和可信事件为输入；在同一只读事务输出汇总、逐日点、明细身份和模型分组 | 实际 schema；上海/UTC 半开边界及纽约 23/25 小时日与独立预期一致 |
| `FP-TM005-03` · 三态数据 / `AC-TM005-002` | `TASK-TM005-COVERAGE` | 已证明覆盖范围、源诊断和未知字段；输出缺失、零、未知状态 | 采集器覆盖合同；不能用空查询推断零 |
| `FP-TM005-04` · 界面 / `AC-TM005-001` | `TASK-TM005-UI` | 受限统计 IPC 结果；日期按钮、自定义范围、卡片、趋势、明细、模型维度及 `model_id=null` 的未知模型组 | 真实 Electron IPC/本地库贯通，倒置/空日期拒绝，刷新与重启保持一致 |
| `FP-TM005-05` · 数据 / 两项 AC | `TASK-TM005-DATA` | seed 42、参考时钟、经验证的 Codex/Claude 原始 fixture；独立 expected、账户/库/目录重置 | TM-003/004 的版本化 raw 样例；SQL 不直接灌规范化用量来证明采集 |
| `FP-TM005-06` · 测试 / 两项 AC | `TASK-TM005-E2E` | 逐 TC 固定程序、安装后的 App、真实服务与隔离 SQLite；原始逐步结果 | 每个必测 TC 与此前已交付功能完整 E2E 通过 |

各任务的稳定验收用例入口为[04a 逐 TC 草案](04a-test-cases.md)，其中原32条产品例均须真实安装包执行：`EVENT-CONTRACT` 对应 `CONTRACT-01` 至 `10`（`10-USAGE/MODEL` 分行）；`RANGE-QUERY` 对应 `RANGE-01` 至 `11`（`10-START-EMPTY/END-EMPTY`、`11-SPRING/FALL` 分行）；`COVERAGE` 对应 `STATE-01` 至 `06`；`UI` 对应 `MODEL-01/02` 与范围/状态的界面断言；`DATA` 对应 `DATA-01/02`；`E2E` 对应 `E2E-01` 和 `E2E-TM005-001/002` 两组。另有 `CORE-01/02/03` 三条辅助模块TC，分别归 `EVENT-CONTRACT`/`RANGE-QUERY`、`EVENT-CONTRACT`/`COVERAGE`、`COVERAGE`，只以受控合成标准事件与声明式覆盖事实验证纯统计函数；它们不验原生日志、授权、数据库或App，也不代替原32条产品例。TC 编号、TASK 和 REQ 的机器追踪列于本版 manifest；未绑定程序的用例仍为计划，不能以编号存在证明验收。

`CORE-04`进一步属于`TASK-TM005-RANGE-QUERY`的IANA当地日纯模块，固定上海/UTC/纽约23与25小时边界；`CORE-05`属于`TASK-TM005-EVENT-CONTRACT/RANGE-QUERY`的合成双来源隔离SQLite同窗只读快照，固定主体/来源/UTC筛选与WAL并发一致性。两例仍是辅助`source_check`，无真实采集/App或完整空日证明，原32条产品父TC及6变体保持原范围。

## 顺序及边界

双来源范围已确定。先完成 TM-003/004 的采集合同，再完成事件与覆盖设计、逐 TASK 的 TC 和独立数据预期，形成文档基线；随后按照 SOP-009→010→011→012→013→014 开发和验证。当前任务仅完成草案，不把尚未交付的依赖标为已交付。

`TASK-TM005-RANGE-QUERY`另拆出`TC-TM005-CORE-06`最小辅助查询切片：在CORE05真实UsageStore双来源物理库上，同一只读事务返回summary/sources/models/details/当地日点；固定partial/known330/total null、缺失日null、缓存子项未知行，以及`modelId:null`与字面`unknown_model`分离和合法99字符冒号Claude模型。固定输入见[查询fixture](../../tests/fixtures/tm005-query-view-slice.json)及[逐步用例](04a-test-cases.md)。独立React展示、共享IPC/App接线后续单独切片；原32产品父TC/6变体保持未通过。
