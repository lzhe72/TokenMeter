# TokenMeter — agent 工作约定

## 第一项硬性规范：先查 SOP 索引

**执行任何工作前，第一步必须读取 [sop/README.md](sop/README.md)。**

1. 根据当前工作查找对应 SOP，完整读取其独立文件，确认前置条件和输入，然后严格按照 SOP 执行。
2. 每一步验证输出并保存规定的证据；未达到完成条件，不得进入依赖它的下一步。
3. 涉及多个 SOP 时，按照索引列出的依赖顺序执行；SOP 按工作步骤拆分。
4. 不得仅凭索引摘要、历史记忆或经验跳过详细 SOP。
5. 缺少对应 SOP，或内容有冲突、缺失、不可执行时，先按照 [SOP-000](sop/SOP-000-maintenance.md) 修订规范，再继续原工作。
6. 明确的用户指令优先；发生冲突时，在本轮执行记录中登记指令及影响，并同步更新规范。

SOP 维护由本项目的「SOP」管理会话（thread ID `01a0f5a5-63f7-76b0-aa53-ac6befec91ef`）统一负责。其他会话需要新增、修改或删除 SOP 时，先通知该会话并提供缺口、依据和受影响流程；依赖修订的步骤待规范同步后继续。详见 [SOP-000](sop/SOP-000-maintenance.md)。

除 SOP 外，**所有项目文档的新增、修改和删除统一由「文档」会话**（thread ID `01a0f14b-0888-7e93-bb85-a76b419f2ba7`）实施，范围包括根项目总表及每次测试的独立结果 Excel。开发、测试、总控与 SOP 会话提交变更依据、候选身份和原始证据，由文档会话按 SOP-024 随开发进度更新文档、目录、工作簿和关联引用，再把文档提交交给总控整合。已经在其他分支形成的文档改动先作为待核对输入，不直接继续改写。会话身份、交接字段和当前队列见[项目会话体系](docs/project-sessions.md)。这项分工不改变先文档基线后开发、最终整合树测试及发布门禁。

最高规则：**规范驱动文档，文档驱动设计、开发、测试、发布和迭代；每一步都必须有 SOP。**

## 项目与阅读入口

这是由 Codex 持续开发的 macOS 团队模型用量工具。首版只读 Codex、Claude Code 已有日志，统计 Token 和估算费用，并同步到单团队服务端。

读完对应 SOP 后，再根据输入要求查阅：

- [当前状态](docs/status.md)：实际实现、检查结果和阻塞。
- [项目会话体系](docs/project-sessions.md)：文档/SOP/开发总控与需求会话的职责、交接和当前队列。
- [全流程框架](docs/lifecycle.md)、[文档规范](docs/standards/documentation.md)：阶段依赖、文档基线和维护规则。
- [产品约定](docs/product/README.md)、[架构](docs/architecture/README.md)：验收行为与实现边界。
- [开发规范](docs/standards/development.md)、[测试策略](docs/testing/strategy.md)、[发布门禁](docs/standards/release.md)：工程约束。
- [功能矩阵](tests/feature_matrix.json)、[文档目录](docs/catalog.json)、[当前版本](releases/current.json)：机器追踪入口。

按任务读取所需文档。下级 AGENTS.md 可以补充模块约定，不能降低本规则和发布门禁。

## 必须遵守的完成标准

1. 在需求阶段先写功能点，再拆具体 TASK，再基于每个 TASK 设计逐条 TC（实际输入、有序动作、逐步预期、DB操作、类型、数据/重置和 SOP）；文档基线后才开发。按已定 TC 执行并逐项记录，不能根据现有代码倒推预期。规则见[任务与用例规范](docs/standards/test-cases.md)；根目录`TEST_CASES.md`须随产品分支的用例基线进入最终整合树，进入前依赖它的产品验收保持BLOCKED。功能/测试/数据/规范同轮交付。
2. 用户2026-09-30明确：Electron + React/TypeScript + Vite/electron-vite；Playwright Electron真实桌面E2E；electron-builder打包。默认在本机完成开发、全量测试和发行，无需完整Xcode。详见[当前设计](docs/architecture/01-electron-local.md)。旧Swift/XCUITest证据仅作历史。
3. 每次迭代/修复/发布执行目标及此前已交付功能全部E2E。本轮TM-001六个场景组及其细化必测 TC 全部覆盖；最终DMG安装后的正式App贯通UI、IPC、真实服务与隔离SQLite。单元/API/mock/截图不能替代产品E2E。
4. 失败、跳过、零例、缺环境/报告、重试取绿、证据与提交/包不匹配均阻断。禁止手填通过、认证旁路、删除失败用例、continue-on-error或伪造数据。
5. 修复先稳定复现，再修实现和完整回归；每步保存真实输出。文档完成、实现完成、产品通过分别记录。
6. 文档基线后建立真实工程和测试骨架，缺条件仅阻断依赖任务；未来命令标不可执行，不伪装已实现。
7. 只有本机机器门禁复核原始结果和最终包PASS才发通行证。当前实测范围macOS15 Intel，其他平台未验证；同uid本地证据不宣称第三方不可篡改证明。
8. 用户授权自动提交与发布：每个需求在独立worktree使用`codex/<release_id>/<功能名>`分支；范围可核对的干净WIP/候选提交可按SOP-019普通快进推送到远端同名功能分支并读回SHA/tree，总控可选单一`codex/<首个release_id>/integration`分支镜像本地整合祖先链。上述远端操作仅保存源码检查点，WIP失败或未测状态原样登记，`release_eligible=false`。总控仍按依赖顺序集成本地`master`并固定各版不可变SHA/tree；每版最终原包完成必需产品E2E与发布门禁，PASS后按SOP-020本机归档正式稳定DMG，下一版从上一实际稳定原包真实升级。全部目标版本本机稳定后，总控统一按远端保护以一次PR登记`master`源码并逐版读回来源与Tag，不重复索取授权。Git只保存源码/文档/固定测试/版本追踪；DMG的可见入口为根`dmg/<release_id>/`，开发/候选包标记未发布，门禁PASS并归档后才放正式原名包；ZIP、数据库、密钥、原始报告、通行证按版本留本机，不上传Git或GitHub Release。Actions完整测试仅用户明确要求多环境时启动。远端`master`旧Actions必需检查已移除，其余实际保护仍须核对；本机最终候选门禁不降低。
9. 测试不得访问用户生产库、默认凭据、现有App或占用服务；动态独占端口经真实配置UI设置。只终止自己创建的进程、只清理取得所有权的目录。TM002/003/004 的 `safeStorage` 测试还须证明最终包实际 Keychain item 与正式 App 分离并只清理本次创建的精确 item；隔离 profile 不等于隔离 Keychain，无法证明即阻断依赖用例。

10. 测试必须是仓库中固化、可按TC编号重复执行的代码。输入、动作、预期和断言在运行前确定；AI只能调用这些代码并分析原始结果，不能以临场操作、看图判断或手填结果代替测试。缺自动化绑定或缺可执行判据为BLOCKED。

## 当前可执行命令

先执行治理检查：

```sh
python3 scripts/check_docs.py --mode structure
python3 scripts/check_docs.py --mode baseline
python3 scripts/quality_gate.py check
python3 -m unittest discover -s tests/governance -p 'test_*.py'
```

服务端使用隔离venv和server/requirements-dev.txt，按SOP-013执行pytest。Electron、打包、安装E2E与本机gate入口以[架构执行合同](docs/architecture/01-electron-local.md)和SOP-009/013/014/017/018为准，计划中的程序完成绑定前保持BLOCKED。不要执行旧CI发布或XCUITest当作当前门禁。

## 数据与实现约束

- 只读取用户授权的日志目录，不改写其他工具的配置或原始日志。
- 不保存/上传提示词、回复、代码、API key 或完整本机路径；只保留用量及必要去重元数据。唯一的本机持久例外是用户已选目录的必要 locator：只可加密保存于当前用户私有来源配置，目录0700、文件0600，不回退明文，且不得进入用量、同步、诊断、报告或Git。
- TM-002 使用 macOS 原生目录选择器与 App 主进程强制的读取范围；App 持久保存已选目录的加密 locator 以跨重启恢复，撤销时删除。密钥不可用、解密失败或来源/账号/根身份不符即停读并要求重选；App 内撤销及系统访问失效不宣称为沙盒持久授权或 TCC 撤销。
- 累计计数、缓存子项、会话分支、子代理及重复同步必须有专门用例；未知值不能用零掩盖。
- 测试只使用隔离目录与合成账号。不能扫描开发者真实 `~/.codex`、`~/.claude` 生成测试数据。
- 时间统一存 UTC，团队默认 Asia/Shanghai；费用以价格版本计算，并标注估算。
- 先保持客户端/服务端的简单单体结构。客户端 SQLite；v0.1.0 服务端测试与生产均使用隔离的 SQLite 文件，MySQL 迁移在后续独立版本设计和验证。
- v0.1.0 测试库为 `database/test/test.db`，只供 Codex 回归；用户生产库为 `database/production/production.db`，首次建库预置 `admin / 123456` 并强制改密。初始化、SQL 造数、只读检查和生产服务启动必须按 [数据库说明](database/README.md) 与 SOP-009/010 执行，不得用生产库重置测试数据。

## 文档、Git 与交接

- 用户统一查看入口为根目录 `TokenMeter项目总表.xlsx`；测试用例一例一行汇总，每次实际测试单独生成 `TokenMeter测试结果-<run_id>.xlsx`，总表仅登记批次摘要和文件入口。按[总表规范](docs/standards/project-workbook.md)在候选测试前提交需求、任务、用例和版本输入；门禁与本机归档完成后由后续文档提交登记批次及被测SHA，不能回写被测树或冒充新包验收。总表随Git提交，详细运行结果留本机且不覆盖历史。腾讯在线表格未更新，用户已改为本地Excel。

- 统一编号使用 `vMAJOR.MINOR.PATCH-YYYYMMDDTHHMMSSZ`，在立项时分配 UTC 时间；贯穿版本档案、Changelog 标题、commit、通行证和最终 tag。见 [版本规范](docs/standards/versioning.md)。
- 分支使用 `codex/<release_id>/<功能名>`，commit 标题带 `[release_id][TM-编号]`；一个可验收功能一个版本，修复升补丁版本。不要把每个中间提交都当作发布。
- 每次行为、数据、接口、命令改变时，同步相关 docs、用例矩阵和 CHANGELOG.md。架构取舍记录原因。
- 长任务在 docs/status.md 保留已完成项、未完成项、实际测试命令、结果和阻塞项，便于新会话接续。
- 完成汇报写清：改了什么、实际执行了什么、结果/证据在哪里、产品 E2E 是否通过、是否具备发布资格。
- 对测试和质量门禁的改动同样需要回归，不能仅通过修改期望值消除失败。
- 用户已授权需求会话把干净且范围可核对的源码提交普通快进保存到远端同名功能分支，总控可选单一整合镜像；每次保存读回SHA/tree并分别记录`remote_code_saved`、WIP/候选及实际检查状态，不授产品PASS。总控在本地`master`逐版整合、固定SHA/tree并通过完整门禁后形成可供下一版升级的本机稳定包；全部目标版本完成后按SOP-019一次办理受保护的远端`master`源码登记与逐版Tag。远端若强制PR，遵守实际保护并记录阻断；远端源码保存、本机产品E2E/发行、远端`master`及Tag分别记录。

文件名使用 `AGENTS.md`。Codex 的目录级指令读取行为见 [官方说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。
