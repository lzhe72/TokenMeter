# 全流程版本编号与查询

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
| commit 标题 | `[<release_id>][TM-编号] 类型: 具体变更` |
| Git annotated tag | 与 `release_id` 完全相同，通过门禁后才创建 |
| GitHub Release 标题 | 与 `release_id` 完全相同 |
| Changelog 二级标题 | `## <release_id>`，不使用模糊的“本次更新” |
| 发布资产 | `<release_id>-<平台/组件>.<后缀>` |
| 通行证 | `<release_id>.passport.json`，仅受保护 CI 校验通过后签发 |

Changelog 每个版本记录状态、关联功能、变更、兼容/迁移影响、测试计划和发布文档链接。计划中或阻断中的版本也可提前写 Changelog，但必须明确“未发布”，不能据此创建产品 tag。

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

`releases/current.json` 指向当前迭代；切换只影响默认查询，历史档案保留。每个档案都记录相同编号并引用相关功能矩阵。产品阶段每个目标功能/验收条件必须落到具体用例 ID，实际测试绑定和数据程序不得为空。

当前已实现只读查询程序：

```sh
python3 scripts/release_registry.py show
python3 scripts/release_registry.py show --release-id v0.0.1-20260929T060944Z
```

默认从 current.json 取编号；已有同名 Tag 时读取该 Tag 中的不可变档案，否则读取工作树。输出需求/功能/任务/用例、数据程序和 SOP、计划、Changelog、本地 Git 提交/Tag、预期通行证资产名。它不签发或验证通行证；发布资格仍由受保护门禁判定。尚未立项的路线图版本没有完整 release ID，不能当作已发布版本查询。

未发布时直接读取 `releases/<release_id>/00-manifest.json`，索引中列出需求、拆解、计划、测试程序、Changelog、发布说明和预期通行证名。正式 Git 发布后可通过以下命令查询不可变版本档案：

```sh
git show <release_id>:releases/<release_id>/00-manifest.json
git log --all --fixed-strings --grep='<release_id>'
git show <release_id>:CHANGELOG.md
```

查询命令中的 `<release_id>` 替换成实际编号。正式版本的通行证与测试报告从同名 Git Release 的附件查询，并核对提交和产物摘要；当前版本无发布 tag 和 PASS 通行证。Git tag 存在也不能替代通行证验证。后续自动发布工具必须实现同样的机器索引校验。

## 通行证与源码提交的关系

先提交全部源码、计划、测试、数据和 Changelog，形成干净候选提交；再构建、执行 E2E 和生成通行证。通行证引用被测提交，不回写到该提交中，避免“提交内的文件必须包含自己的 commit SHA”的循环依赖。

通行证作为受保护 CI 的不可变产物和 GitHub Release 附件保存，记录：release ID、源码提交、构建物摘要、需求/用例/fixture 摘要、平台矩阵、原生报告摘要、CI 运行身份、签名/公证结果、通过时间和最终判定。发布任务验证证据与候选一致后，才创建指向该提交的 annotated tag 并分发同一批构建物。

失败或缺环境只产生 FAIL/BLOCKED 执行记录，不签发通行证。不得手写、复制旧版本或接受任意外部 PASS JSON；验证规则见 [发布门禁](release.md)。

当前基础规范档案为 `v0.0.1-20260929T060944Z`，目标是保存设计与工程基础，产品 E2E 尚未具备，没有发布 tag 或发布通行证。
