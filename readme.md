# TokenMeter

> 2026-09-30当前执行基线：[Electron本机设计](docs/architecture/01-electron-local.md)。Electron/React/TypeScript、Vite/electron-vite、Playwright Electron、electron-builder；本机开发/全量测试/打包，当前仅macOS15 Intel实测范围。Git保存源码/文档/版本；DMG、更新包、报告和通行证只存本地，Actions仅明确多环境要求时启用。旧流程在历史提交与明确标记的历史设计中查询。每项功能真实E2E与发布门禁不变。

macOS 团队模型用量监控工具。产品目标是读取 Codex、Claude Code 本地日志，展示 Token、估算费用和团队统计；当前0.1.0交付账号与更新基础，采集和统计按后续功能迭代。

**TM-001 正在进行最终候选回归。首次干净候选门禁为 FAIL，修复后候选仍须以原始门禁终态判定；目前没有正式发布通行证。实际运行、证据和后续需求状态以[当前状态](docs/status.md)为准。**

## 项目查看入口

[TokenMeter项目总表.xlsx](TokenMeter项目总表.xlsx)按Sheet查看需求、功能、开发任务、用例汇总（输入、预期、DB操作、类型）、测试批次和发布版本。总表随Git版本维护；每次测试单独生成结果Excel，总表的“06测试批次”记录本机详细报告位置。

- [根目录用例集合](TEST_CASES.md)
- [当前0.2设计基线](releases/v0.2.0-20261001T034118Z/00-manifest.json)、[TM-003草稿导航](releases/v0.3.0-20261001T034652Z/README.md)、[0.1历史全流程](releases/v0.1.0-20260929T074814Z/README.md)
- [总表维护规范](docs/standards/project-workbook.md)

## 开发入口

- [SOP 总索引](sop/README.md)：任何工作先查索引，再读取对应独立 SOP。
- [全流程框架](docs/lifecycle.md)：先定需求、拆解与计划，再按文档开发、测试和发布。
- [总设计计划](docs/design-plan.md)：已确认的全部产品与工程设计。
- [AGENTS.md](AGENTS.md)：Codex 开发、修复、测试和交接约定。
- [文档索引](docs/README.md)：产品、架构、版本、测试、发布说明。
- [当前状态](docs/status.md)：已实现能力和真实阻塞项。
- [项目会话体系](docs/project-sessions.md)：非 SOP 文档统一由“文档”会话编写，SOP 由“SOP”会话维护，开发总控整合提交。
- [Git 版本追踪](docs/standards/versioning.md)：需求分支的远端源码检查点与本机产品门禁、最终远端`master`和Tag分别登记。
- [功能与 E2E 矩阵](tests/feature_matrix.json)：每个功能的用例、数据程序和 SOP。
- [SQLite 数据库](database/README.md)：测试/生产 DB 的位置、可执行造数 SQL、初始化和生产服务启动。

## 本地检查

下列命令以 Python 3.10+ 启动。`release_registry.py`、`check_docs.py`、`quality_gate.py`与`test_data.py`可只用标准库；**全量治理发现测试还会调用固定结果 Excel 导出器**，需本机 Node 和工作簿依赖。运行治理前按本机 Codex `load_workspace_dependencies` 返回的实际 Node 可执行文件设置`TOKENMETER_WORKBOOK_NODE`，并将忽略目录`.local/workbook/node_modules`指向同一依赖包目录（其中有`@oai/artifact-tool`）；缺少依赖时应记环境 BLOCKED，不把部分测试当全量 PASS：

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

Electron依赖与构建在apps/desktop执行（使用Node24/npm11与锁文件）：

```sh
npm ci --cache ../../.local/npm-cache
npm run runtime:install
npm run build
npm test
```

最终包先按SOP-017用local_package.py在干净候选构建，再按SOP-014/018执行local_gate.py。各脚本`--help`提供真实参数；TM-001 独立候选 `d2db551` 已通过本机门禁，最终本地 `master` 整合树仍须重测，实际进展见状态页。quality_gate.py在local_electron配置下必须提供`--package-manifest`和新的`--output`，不允许落回旧XCUITest结果。

完整门禁从原DMG安装真实App，贯通UI、IPC、API和SQLite并复核六例原始结果；基础测试不替代E2E。无需完整Xcode，当前验收仅此macOS15 Intel。现有App、生产数据库和49176服务不作为测试资源。

仓库根目录的[dmg安装包目录](dmg/README.md)按版本保存本机安装包。现有v0.1.0文件标记为开发包；门禁通过后，正式DMG原名放在`dmg/<release_id>/`，同目录`release-archive/`保存原包与报告/通行证归档。DMG和原始证据不提交Git，Git保存代码、文档和版本。工作流默认无push/PR触发；多环境测试需要用户明确要求后建立矩阵。安装说明见[本地安装](docs/releases/02-installation.md)，每功能test case见[详细用例](docs/testing/cases/README.md)。
