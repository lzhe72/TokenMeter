# 版本文档模板索引

**release_id：** `<release_id>`（采用模板时替换为立项已分配的编号）。

**适用 SOP：** [SOP-001 版本立项](../../sop/SOP-001-version-start.md)；模板维护先执行 [SOP-000](../../sop/SOP-000-maintenance.md)和 [SOP-024](../../sop/SOP-024-document-change.md)。

这里仅导航独立模板；详细要求以各模板和对应 SOP 为准。先按[SOP 工作索引](../../sop/README.md)选择工作，再准备本轮文档。技术设计可采用独立模板；范围较小时可在开发计划中单列设计章节并引用全局架构，遵循文档规范。

## 输入与采用方式

- 输入引用：[文档规范](../../docs/standards/documentation.md)、[版本规范](../../docs/standards/versioning.md)、当前目标/反馈、比较基线和本轮 manifest。
- 先按 SOP-001 确定不可变 `release_id` 和版本档案；首次没有比较基线时使用 `null`。
- 模板源文件保留现名；复制到本轮档案时使用下表的 01–06 编号目标文件名，填入真实输入、需求/任务 ID、决定、输出和验收条件；按目标位置检查链接。
- 每份文档正文保留 `release_id`，元数据登记到 `docs/catalog.json`，文档关系登记到本轮 `00-manifest.json`。
- 未存在的程序、测试、报告和产物绑定使用 `null` 并关联具体补齐任务。计划不能填写虚构路径或预填成功。

## 独立版本模板

| 顺序 / 工作 | 模板链接及本轮目标文件名 | 适用 SOP | 主要输出 |
| --- | --- | --- | --- |
| 需求定义 | [01-requirements.md](requirements.md) | [002](../../sop/SOP-002-requirements.md) | 范围、稳定需求 ID、可观察验收条件 |
| 功能拆解 | [02-breakdown.md](breakdown.md) | [003](../../sop/SOP-003-feature-breakdown.md) | 需求→功能→任务、依赖与完成标准 |
| 技术设计 | [technical-design.md](technical-design.md) | [004](../../sop/SOP-004-technical-design.md) | 模块、接口/数据、隐私、兼容与恢复决定 |
| 开发计划 | [03-development-plan.md](development-plan.md) | [005](../../sop/SOP-005-development-plan.md) | 实施顺序、数据/测试准备、集成和验证 |
| 测试计划 | [04-test-plan.md](test-plan.md) | [006](../../sop/SOP-006-test-plan.md) | 需求→用例→数据/重置→SOP→原生测试→预期→报告 |
| 发布预案 | [05-release-plan.md](release-plan.md) | [007](../../sop/SOP-007-release-plan.md) | 构建、门禁、分发、升级和恢复方案 |
| 工作记录/复盘 | [06-iteration-record.md](iteration-record.md) | [022](../../sop/SOP-022-archive-handoff.md)、[023](../../sop/SOP-023-iteration.md) | 各步实际结果、证据、阻塞、交接与下一轮需求 |

## 工作专题模板

| 工作 | 模板 | 使用边界 |
| --- | --- | --- |
| 单项功能的验收细节 | [feature.md](feature.md) | 补充版本需求与测试追踪，按新功能路线执行 |
| 缺陷复现与修复 | [bugfix.md](bugfix.md) | 按 [SOP-015](../../sop/SOP-015-bugfix.md)保留失败复现、根因和永久回归 |
| 新增或修订执行步骤 | [sop.md](sop.md) | 按 [SOP-000](../../sop/SOP-000-maintenance.md)先定义工作边界，再补独立 SOP |

专题模板引用本轮独立文档，不替代需求、设计、开发/测试计划和发布预案。不为不同执行角色另造同一套流程。

## 输出、验收与证据

- 输出：同一 `release_id` 的独立版本文档、manifest/文档目录关联、所需专题记录和 SOP。
- 文档验收：每个阶段有确定输入、输出、验收条件及具体 SOP；关键决定已完成；文件、引用、版本和追踪链一致。
- 执行 [SOP-008 基线检查](../../sop/SOP-008-baseline-check.md)，实际结构/引用检查结果及语义核对写入本轮 `06-iteration-record.md`。基线检查通过后再按 SOP 进入开发。
- 实际测试与发布证据来自执行器；候选 SHA、原生结果、产物摘要和 passport 保存于对应机器运行/资产。没有执行时明确未执行或 `BLOCKED`。
- 完整追踪：`release_id → 文档 → 需求/验收条件 → 任务 → 用例 → 数据/重置程序 → 具体 SOP → 原生测试 → run_id/报告 → passport → 发布 → 下一轮需求`。
