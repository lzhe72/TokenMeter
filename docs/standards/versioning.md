# 全流程版本编号与查询

> 2026-10-01当前执行基线：[Electron本机设计](../architecture/01-electron-local.md)。Electron/React/TypeScript、Vite/electron-vite、Playwright Electron、electron-builder；开发期按功能固定TC回归，用户启动正式发行后对最终候选完整E2E、打包与门禁，当前仅macOS15 Intel实测范围。Git保存源码/文档/版本；DMG、更新包、报告和通行证只存本地，Actions仅明确多环境要求时启用。旧流程在历史提交与明确标记的历史设计中查询。

## 唯一编号

发布编号（`release_id`）固定格式：

```text
v<MAJOR>.<MINOR>.<PATCH>-<YYYYMMDD>T<HHMMSS>Z
例：v0.1.0-20260929T040000Z
```

时间使用 UTC，精确到秒；示例对应北京时间 2026-09-29 12:00:00。它是迭代立项时间，不是假称的实际上线时间。开始迭代时生成一次，此后需求、计划、测试、发布文档、Changelog、commit 信息和最终 tag 使用同一个编号。实际构建、测试、发布分别记录自己的发生时间。

- `version`：语义版本，如 `0.1.0`；新功能升 MINOR，修复升 PATCH，重大升级升 MAJOR。
- `release_id`：语义版本 + 立项时间，贯穿本次迭代。
- `commit_sha`：本次候选的实际源码标识；迭代中可变化，每次变化后重新测试。
- `run_id`：一次测试执行标识；每次重跑不同，不能覆盖前次失败。
- `artifact_sha256`：最终 App、服务端、测试结果包的内容摘要。

这五者分别表示版本、源码、执行和产物，不能只用“版本号相同”判断报告有效。一个语义版本正式发布一次；未发布候选可以继续开发并重测，已发布后不可改写 tag 或替换同名产物，修复使用新版本和新编号。

## Git 和 Changelog 命名

| 项目 | 规范 |
| --- | --- |
| 功能分支 | `codex/<release_id>/<短功能名>` |
| 可选整合镜像分支 | `codex/<首个release_id>/integration`，本轮固定一个 |
| commit 标题 | `[<release_id>][TM-编号] 类型: 具体变更` |
| Git annotated tag | 与实际正式发行的 `release_id` 完全相同；用户启动正式发布、最终候选门禁与归档PASS、远端来源读回后创建；开发里程碑不打正式Tag |
| 本地发行目录 | 以 `release_id` 命名，不创建GitHub Release |
| Changelog 二级标题 | `## <release_id>`，不使用模糊的“本次更新” |
| 发布资产 | `<release_id>-<平台/组件>.<后缀>` |
| 通行证 | `<release_id>.passport.json`，仅本机机器门禁校验完整证据后签发 |

Changelog 每个版本记录状态、关联功能、变更、兼容/迁移影响、测试计划和发布文档链接。计划中或阻断中的版本也可提前写 Changelog，但必须明确“未发布”，不能据此创建产品 tag。

用户授权后，各需求在独立worktree按同名功能分支提交；干净且范围可核对的WIP/候选源码可普通快进推送远端同名分支并读回SHA/tree，标记`remote_code_saved=true`与WIP/候选，`release_eligible=false`。总控可选一个整合镜像保存本地祖先链。上述源码检查点不等于本机产品验收。总控按依赖顺序集成本地`master`，逐版冻结源码里程碑SHA/tree并记录功能TC的真实状态；全部目标源码完成后可按保护规则一次登记远端`master`。用户另行明确正式发布后，对最终候选执行跨需求完整E2E、适用真实升级和本机门禁，SOP-020归档后才登记正式Tag；未发布版本不虚构稳定包。四种状态——远端功能分支代码已保存、本机产品/发行、远端`master`登记、Tag——分别记录；步骤见[SOP-019](../../sop/SOP-019-git-release.md)。

## 每个编号对应的版本档案

```text
releases/<release_id>/
  00-manifest.json         # 机器索引：版本、功能、文档、测试程序、预期通行证名
  01-requirements.md       # 本版本需求与验收条件
  02-breakdown.md          # 功能拆解和稳定需求 ID
  03-development-plan.md   # 实现顺序、依赖、接口、交接
  04-test-plan.md          # 用例、用户/数据程序、SOP、E2E、预期、环境
  05-release-plan.md       # 发布内容、兼容性、部署/恢复、当前阻塞
  06-iteration-record.md   # 步骤执行、证据、阻塞与交接
```

文件名使用两位顺序前缀：`00` 为机器总索引，`01`–`06` 依次为需求、拆解、开发计划、测试计划、发布预案、迭代记录。编号体现主文档顺序，迭代记录从立项起持续追加。技术设计仍在开发计划中记录或链接独立设计附件，按 SOP-004 在开发计划前完成。模板复制到版本目录时使用这些目标文件名；机器索引的语义键和文档 ID 保持稳定。

`program_bindings_status` 记录计划中的程序是否已建立：planned 允许 `test_programs=[]`、`test_data_program=null`；ready 要求真实的非空程序绑定。两者均需完整需求→任务→用例追踪和实际 SOP 文件，已填写的引用必须有效。此字段不表示测试已通过：本基础版本的治理程序为 ready；当前 Electron 开发包 E2E 六组中升级004 FAIL，精细TC仍未执行。

检查器与查询器共用 [release_contract.py](../../scripts/release_contract.py)，拒绝空追踪、孤立需求/任务/用例、错功能归属、程序或 SOP 断链，以及把版本目录文档错误登记为 all。编制中的草稿使用 structure，并直接读取 00-manifest.json；严格 baseline 和完整版本查询要求文档基线齐全，不能为了查询草稿而伪标完成。

`releases/current.json` 指向当前迭代；切换只影响默认查询，历史档案保留。每个档案都记录相同编号并引用相关功能矩阵。产品阶段每个目标功能/验收条件必须落到具体用例 ID，实际测试绑定和数据程序不得为空。

当前已实现只读查询程序：

```sh
python3 scripts/release_registry.py show
python3 scripts/release_registry.py show --release-id v0.0.1-20260929T060944Z
```

默认从 current.json 取编号；已有同名 Tag 时读取该 Tag 中的不可变档案，否则读取工作树。输出需求/功能/任务/用例、数据程序和 SOP、计划、Changelog、本地 Git 提交/Tag、预期通行证资产名。它不签发或验证通行证；发布资格仍由本机机器门禁判定。尚未立项的路线图版本没有完整 release ID，不能当作已发布版本查询。

未发布时直接读取 `releases/<release_id>/00-manifest.json`，索引中列出需求、拆解、计划、测试程序、Changelog、发布说明和预期通行证名。正式 Git 发布后可通过以下命令查询不可变版本档案：

```sh
git show <release_id>:releases/<release_id>/00-manifest.json
git log --all --fixed-strings --grep='<release_id>'
git show <release_id>:CHANGELOG.md
```

查询命令中的`<release_id>`替换为实际编号。通行证与原始报告从本机同名版本目录查询并核对提交/产物摘要；Git tag提供源码追踪，不单独证明发布资格。

## 通行证与源码提交的关系

开发阶段先提交源码、计划、固定TC与数据，并记录该功能回归的实际状态；源码提交和远端登记不生成通行证。用户另行启动正式发布后，冻结最终候选，再构建、执行跨需求完整E2E和生成通行证。通行证引用被测提交，不回写到该提交中，避免“提交内的文件必须包含自己的 commit SHA”的循环依赖。

通行证作为本机版本档案保存：release ID、internal profile、被测里程碑SHA/tree、原包摘要、用例/fixture/SOP摘要、实际平台、原始报告、运行身份、签名/Gatekeeper实际结果、通过时间与判定。用户正式发布时机器复核通过后按SOP-020归档最终原件并形成实际本机稳定包；总控在远端来源读回后登记该正式发行Tag，不创建GitHub Release。

正式发布前以本地`master`冻结的最终整合提交为候选，核对真实HEAD、源码tree和同名Tag不存在，再执行最终包、适用真实升级与完整本机发布门禁。只有最终候选PASS并完成原包/通行证归档，才称本机正式稳定版；开发里程碑及开发DMG一直标未发布。远端master源码可在此前按SOP-019保护规则登记，正式Tag只能在本次门禁和归档通过、远端来源读回后创建；不能先打Tag再测试。GitHub Actions完整测试只在用户明确要求多环境时运行；2026-10-01已移除远端`master`旧Actions必需检查，当前仍强制PR及其他保护。不得用旧候选或手写状态创建Tag。

失败或缺环境只产生 FAIL/BLOCKED 执行记录，不签发通行证。不得手写、复制旧版本或接受任意外部 PASS JSON；验证规则见 [发布门禁](release.md)。

当前基础规范档案为 `v0.0.1-20260929T060944Z`，目标是保存设计与工程基础，产品 E2E 尚未具备，没有发布 tag 或发布通行证。
