# TokenMeter

macOS 团队模型用量监控工具。首版读取 Codex、Claude Code 本地日志，展示 Token、估算费用和团队统计。

**当前正在验收第一个功能 TM-001：账号、登录与最小更新器。SwiftUI App、FastAPI 服务及原生测试程序已建立；实际测试结果见[当前状态](docs/status.md)。产品尚未发布。**

## 开发入口

- [SOP 总索引](sop/README.md)：任何工作先查索引，再读取对应独立 SOP。
- [全流程框架](docs/lifecycle.md)：先定需求、拆解与计划，再按文档开发、测试和发布。
- [总设计计划](docs/design-plan.md)：已确认的全部产品与工程设计。
- [AGENTS.md](AGENTS.md)：Codex 开发、修复、测试和交接约定。
- [文档索引](docs/README.md)：产品、架构、版本、测试、发布说明。
- [当前状态](docs/status.md)：已实现能力和真实阻塞项。
- [功能与 E2E 矩阵](tests/feature_matrix.json)：每个功能的用例、数据程序和 SOP。
- [SQLite 数据库](database/README.md)：测试/生产 DB 的位置、可执行造数 SQL、初始化和生产服务启动。

## 本地检查

以下文档与治理检查使用 Python 3.10+ 标准库：

```sh
python3 scripts/release_registry.py show
python3 scripts/check_docs.py --mode structure
python3 scripts/check_docs.py --mode baseline
python3 scripts/quality_gate.py check
python3 -m unittest discover -s tests/governance -p 'test_*.py'
python3 scripts/test_data.py generate --run-id demo --seed 42
python3 scripts/test_data.py reset --run-id demo
```

服务端及真实产品测试先按 [SOP-009](sop/SOP-009-environment.md) 准备隔离环境：

```sh
python3 -m venv .local/venv
.local/venv/bin/python -m pip install --only-binary=:all: -r server/requirements-dev.txt
.local/venv/bin/python -m pytest tests/server -q
.local/venv/bin/python scripts/bootstrap_sqlite.py verify
```

在执行原生测试的 Mac 上使用同一已安装依赖的环境运行产品门禁；该 Mac 还需完整 Xcode、登录桌面及隔离的更新签名环境：

```sh
.local/venv/bin/python scripts/quality_gate.py iteration
.local/venv/bin/python scripts/quality_gate.py release
```

门禁自动初始化真实测试库、构建 App、逐例执行原生 UI，并复核原始 `xcresult`。缺环境输出 `BLOCKED`，断言失败输出 `FAIL`，均返回非零。完整开发矩阵通过才可验收；v0.1.0 正式发布还需最终签名、公证、完整支持矩阵、隔离的生产 SQLite 验证和受保护流程。测试数据或服务端测试通过不能替代原生验收。

当前本机只有 Command Line Tools，可继续开发、运行 SQLite 服务和安装预览 App；在本机运行原生门禁会得到 `BLOCKED`，无需先安装 Xcode 才能推进本版。PR 的 [quality.yml](.github/workflows/quality.yml) 在 GitHub 托管的 macOS 15 Apple Silicon 与 Intel 上选择 Xcode 16.4，针对同一提交自动运行六例真实 App E2E，并上传原始结果。CI 的 `127.0.0.1:49176` 是 runner 自己的隔离服务，不连接本机生产库。远端迭代结果与本机预览分别记录，正式发布仍走最终安装包和发布门禁；详见[测试执行参考](docs/testing/execution.md)与[当前状态](docs/status.md)。

structure 支持逐步编写草稿；baseline 验收完整计划。验收规格、独立清单和用例双向校验。常规 CI 执行 iteration，候选 CI 按完整 SHA 在创建 Tag 前执行 release；远端保护与可信签发仍待接通，详见[发布门禁](docs/standards/release.md)。
