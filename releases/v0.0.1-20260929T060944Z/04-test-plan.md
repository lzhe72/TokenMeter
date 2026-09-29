# v0.0.1-20260929T060944Z — 测试计划

## 范围与判定

本轮只验证设计/规范工具，以下 GOV 用例不是产品 E2E。真实产品 E2E 未实现，发布门禁预期为 BLOCKED，不能签发通行证。

| 用例 | 需求/任务 | 输入和执行入口 | 预期 |
| --- | --- | --- | --- |
| GOV-001 | REQ-GOV-001 / TASK-GOV-001 | check_docs.py / test_check_docs.py 检查25份SOP、索引、章节、文档链接、版本合同和模板 | 文档可导航，设计/实现/测试状态分明 |
| GOV-002 | REQ-GOV-002 / TASK-GOV-002 | quality_gate check 与 test_quality_gate.py 的缺项/类型/引用负向用例 | 有效计划通过元数据检查；删需求、缺 SOP/数据、越界路径等拒绝 |
| GOV-003 | REQ-GOV-003 / TASK-GOV-003 | test_test_data.py、生成与重置命令 | 相同种子字节一致，独立预期匹配，越界/外来文件拒绝清理 |
| GOV-004 | REQ-GOV-004 / TASK-GOV-004 | iteration/release 与伪造 PASS/空成功 runner 测试 | 返回非零 BLOCKED/FAIL；无产品执行时不能放行 |
| GOV-005 | REQ-GOV-005 / TASK-GOV-005 | release_registry.py / test_release_registry.py；manifest、文档编号、Changelog、Git commit/tag | 一致编号可追踪；当前未发布，无 tag/通行证 |

## 程序与 SOP

```sh
python3 scripts/check_docs.py
python3 scripts/release_registry.py show
python3 scripts/quality_gate.py check
python3 -m unittest discover -s tests/governance -p 'test_*.py' -v
python3 scripts/test_data.py generate --run-id demo --seed 42
python3 scripts/test_data.py reset --run-id demo
python3 scripts/quality_gate.py iteration
python3 scripts/quality_gate.py release
```

账号、固定时钟、数据摘要、安全重置与失败处理见 [数据 SOP](../../sop/SOP-010-test-data.md) 与[测试执行参考](../../docs/testing/execution.md)。种子 42、时钟 2026-09-29T04:00:00Z、Asia/Shanghai；数据只是标准化规范样例，不能证明真实工具解析或产品账号已初始化。

## 证据

基础测试保存运行输出；产品入口记录在 .local/e2e/ 的 result.json，必须为 BLOCKED、executed_cases=0。实际运行结果见 [本轮记录](06-iteration-record.md)。后续产品版本绑定真实原生报告与版本通行证，按 [发布门禁](../../docs/standards/release.md) 自动校验。

## 一致性修复回归

- GOV-001：有效草稿通过 structure、未完成基线拒绝 baseline；已填写的错误引用两个模式均拒绝。人工语义核对 001–008 编制路线及 009 骨架→010 数据→011 红测→012 业务开发路线不存在前后循环。
- GOV-002：删掉仍有验收条件的用例、删登记条件、条件归属错误、缺前序功能、以基础 pricing 数据冒充高级场景，均应失败；移到后序功能的场景保持验收与用例对应。
- GOV-004：新增 test_candidate_gate.py，以隔离 Git 仓库验证完整 SHA、来源分支、手动触发、实际 HEAD、脏工作区、已存在的版本 Tag；验证 Tag 不存在时可校验候选上下文，但不能取得发布资格。产品 iteration/release 仍返回 2。
- GOV-005：空追踪、缺行、错需求/任务/用例、缺程序/数据/SOP、版本文档错误标为 all、Tag 快照与工作树混用，均拒绝。检查器和查询器采用同一合同。
- GOV-003：高级价格数据标记 planned、生成器为空；基础合成数据继续执行原有确定性和清理回归。

本轮失败与通过证据保存在 `.local/reviews/` 和 `.local/governance/`，由实际测试进程产生。SOP 与计划语义修复不声称已有原生产品运行证据。
