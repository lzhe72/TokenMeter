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

基础测试保存运行输出；产品入口记录在 .local/e2e/ 的 result.json，必须为 BLOCKED、executed_cases=0。实际运行结果见 [本轮记录](iteration-record.md)。后续产品版本绑定真实原生报告与版本通行证，按 [发布门禁](../../docs/standards/release.md) 自动校验。
