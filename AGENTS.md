# TokenMeter — agent 工作约定

## 第一项硬性规范：先查 SOP 索引

**执行任何工作前，第一步必须读取 [sop/README.md](sop/README.md)。**

1. 根据当前工作查找对应 SOP，完整读取其独立文件，确认前置条件和输入，然后严格按照 SOP 执行。
2. 每一步验证输出并保存规定的证据；未达到完成条件，不得进入依赖它的下一步。
3. 涉及多个 SOP 时，按照索引列出的依赖顺序执行；SOP 按工作步骤拆分。
4. 不得仅凭索引摘要、历史记忆或经验跳过详细 SOP。
5. 缺少对应 SOP，或内容有冲突、缺失、不可执行时，先按照 [SOP-000](sop/SOP-000-maintenance.md) 修订规范，再继续原工作。
6. 明确的用户指令优先；发生冲突时，在本轮执行记录中登记指令及影响，并同步更新规范。

最高规则：**规范驱动文档，文档驱动设计、开发、测试、发布和迭代；每一步都必须有 SOP。**

## 项目与阅读入口

这是由 Codex 持续开发的 macOS 团队模型用量工具。首版只读 Codex、Claude Code 已有日志，统计 Token 和估算费用，并同步到单团队服务端。

读完对应 SOP 后，再根据输入要求查阅：

- [当前状态](docs/status.md)：实际实现、检查结果和阻塞。
- [全流程框架](docs/lifecycle.md)、[文档规范](docs/standards/documentation.md)：阶段依赖、文档基线和维护规则。
- [产品约定](docs/product/README.md)、[架构](docs/architecture/README.md)：验收行为与实现边界。
- [开发规范](docs/standards/development.md)、[测试策略](docs/testing/strategy.md)、[发布门禁](docs/standards/release.md)：工程约束。
- [功能矩阵](tests/feature_matrix.json)、[文档目录](docs/catalog.json)、[当前版本](releases/current.json)：机器追踪入口。

按任务读取所需文档。下级 AGENTS.md 可以补充模块约定，不能降低本规则和发布门禁。

## 必须遵守的完成标准

1. 每项功能先登记需求 ID、可验收行为、E2E 用例、测试用户/数据生成程序、执行 SOP，再写实现。使用 [功能模板](docs/templates/feature.md)。
2. 功能、测试、数据程序、SOP 同次提交。不能把“测试后补”作为完成状态。
3. Codex 必须自动编写和执行测试、收集结果、判定门禁；SOP 是可执行操作说明，不能依赖人工勾选“通过”。
4. 每次产品迭代、修复、预发布、正式发布都执行全部已交付功能 E2E 回归。单元测试、接口测试、截图和构建成功均不能替代产品 E2E。
5. 测试失败、跳过、零用例、缺少环境/数据/报告、证据与提交或安装包不匹配，全部阻断。不得使用 `continue-on-error`、`|| true`、排除失败用例或反复重试取绿放行。
6. 修复问题先增加稳定复现用例，再修实现，再执行回归。使用 [修复模板](docs/templates/bugfix.md)。
7. 不手写通过报告，不伪造厂商日志兼容性，不将合成数据工具的自测宣称为 App E2E。
8. 文档基线后先按 SOP-009 建立真实 App、服务、数据库初始化和原生测试 target/runner 的工程骨架，不要求预先存在业务红测或产品 PASS。缺 Xcode、GUI 或执行器只阻断依赖它们的构建、运行和验收；可继续有独立验证条件的源码、fixture、测试编写和文档任务。分别记录完成与 BLOCKED，禁止认证旁路或伪造业务结果。生产签名/公证与发布凭据属于 SOP-017/018 前提，不能作为开始开发的前提。
9. 只有对应 `distribution_profile`（内部或公开）的发布门禁为 `PASS` 才能正式分发安装包、部署服务端或更新 appcast。TM-001 已接入真实原生执行器，当前实现与运行结果以 [docs/status.md](docs/status.md) 为准；迭代通过不替代最终 DMG 安装升级、全平台及受保护发布条件。公开 profile 另要求 Developer ID 与公证；内部 profile 的自动包级门禁尚未实现时为 BLOCKED。

## 当前可执行命令

在仓库根目录执行以下治理检查，Python 3.10+ 无需第三方包；HTTPS fixture 工具自测还需要 `openssl` 命令：

```sh
python3 scripts/check_docs.py --mode structure
python3 scripts/check_docs.py --mode baseline
python3 scripts/quality_gate.py check
python3 -m unittest discover -s tests/governance -p 'test_*.py'
python3 scripts/test_data.py generate --run-id demo --seed 42
python3 scripts/test_data.py reset --run-id demo
```

服务端和原生门禁需先按 [SOP-009](sop/SOP-009-environment.md) 在隔离环境安装锁定依赖，再执行 [SOP-013](sop/SOP-013-build-and-check.md) 的基础回归和 [SOP-014](sop/SOP-014-e2e.md) 的原生流程：

```sh
python3 -m pip install --only-binary=:all: -r server/requirements-dev.txt
python3 -m pytest tests/server -q
python3 scripts/test_device_credentials.py
python3 -m unittest discover -s apps/macos/tests -p 'test_*.py' -v
python3 scripts/quality_gate.py iteration
python3 scripts/quality_gate.py release
```

Swift 凭据边界检查可在有 Command Line Tools 的本机 macOS 执行，但不能替代原生用例。原生用例还要求完整 Xcode、已登录 Mac 桌面；TM-001 升级 fixture 的隔离临时自签名与公开 HTTPS 测试源仅允许专用 GitHub Mac CI，不修改系统证书信任。缺条件返回 BLOCKED，不静默修改用户机器。门禁对实际原始结果判定，不能为变绿跳过用例或删除阻断。

编制期间用 `--mode structure` 检查草稿并返回原步骤；SOP-001–007 齐全后经 SOP-008 执行 `--mode baseline` 和质量检查。无参数默认严格基线模式，结构通过不代表基线完成。文档检查、引用检查、自测和造数操作仅检查规范或生成隔离数据。

## 数据与实现约束

- 只读取用户授权的日志目录，不改写其他工具的配置或原始日志。
- 不保存/上传提示词、回复、代码、API key 或完整本机路径；只保留用量及必要去重元数据。
- 累计计数、缓存子项、会话分支、子代理及重复同步必须有专门用例；未知值不能用零掩盖。
- 测试只使用隔离目录与合成账号。不能扫描开发者真实 `~/.codex`、`~/.claude` 生成测试数据。
- 时间统一存 UTC，团队默认 Asia/Shanghai；费用以价格版本计算，并标注估算。
- 先保持客户端/服务端的简单单体结构。客户端 SQLite；v0.1.0 服务端测试与生产均使用隔离的 SQLite 文件，MySQL 迁移在后续独立版本设计和验证。
- v0.1.0 测试库为 `database/test/test.db`，只供 Codex 回归；用户生产库为 `database/production/production.db`，首次建库预置 `admin / 123456` 并强制改密。初始化、SQL 造数、只读检查和生产服务启动必须按 [数据库说明](database/README.md) 与 SOP-009/010 执行，不得用生产库重置测试数据。

## 文档、Git 与交接

- 统一编号使用 `vMAJOR.MINOR.PATCH-YYYYMMDDTHHMMSSZ`，在立项时分配 UTC 时间；贯穿版本档案、Changelog 标题、commit、通行证和最终 tag。见 [版本规范](docs/standards/versioning.md)。
- 分支使用 `codex/<release_id>/<功能名>`，commit 标题带 `[release_id][TM-编号]`；一个可验收功能一个版本，修复升补丁版本。不要把每个中间提交都当作发布。
- 每次行为、数据、接口、命令改变时，同步相关 docs、用例矩阵和 CHANGELOG.md。架构取舍记录原因。
- 长任务在 docs/status.md 保留已完成项、未完成项、实际测试命令、结果和阻塞项，便于新会话接续。
- 完成汇报写清：改了什么、实际执行了什么、结果/证据在哪里、产品 E2E 是否通过、是否具备发布资格。
- 对测试和质量门禁的改动同样需要回归，不能仅通过修改期望值消除失败。
- 用户已授权后续工作由 Codex 自行提交、推送、创建 PR，并在适用检查通过后合并；按 SOP-019 核对候选 SHA、检查和远端结果，不再重复索取授权。授权不等于允许跳过产品 E2E 或发布门禁。

文件名使用 `AGENTS.md`。Codex 的目录级指令读取行为见 [官方说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。
