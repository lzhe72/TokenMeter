# TokenMeter

macOS 团队模型用量监控工具。首版读取 Codex、Claude Code 本地日志，展示 Token、估算费用和团队统计。

**当前只有开发规范、测试数据工具和门禁基础设施，App 与服务端尚未实现。产品 E2E 未通过，禁止发布产品。**

## 开发入口

- [SOP 总索引](sop/README.md)：任何工作先查索引，再读取对应独立 SOP。
- [全流程框架](docs/lifecycle.md)：先定需求、拆解与计划，再按文档开发、测试和发布。
- [总设计计划](docs/design-plan.md)：已确认的全部产品与工程设计。
- [AGENTS.md](AGENTS.md)：Codex 开发、修复、测试和交接约定。
- [文档索引](docs/README.md)：产品、架构、版本、测试、发布说明。
- [当前状态](docs/status.md)：已实现能力和真实阻塞项。
- [功能与 E2E 矩阵](tests/feature_matrix.json)：每个功能的用例、数据程序和 SOP。

## 本地检查

Python 3.10+，无需安装依赖：

```sh
python3 scripts/release_registry.py show
python3 scripts/check_docs.py
python3 scripts/quality_gate.py check
python3 -m unittest discover -s tests/governance -p 'test_*.py'
python3 scripts/test_data.py generate --run-id demo --seed 42
python3 scripts/test_data.py reset --run-id demo
```

自动产品门禁入口：

```sh
python3 scripts/quality_gate.py iteration
python3 scripts/quality_gate.py release
```

当前两条产品门禁会写出 `BLOCKED` 结果并返回非零；这说明实际 E2E 尚未具备，不是一个可以忽略的失败。测试数据自测通过不代表产品通过验收。
