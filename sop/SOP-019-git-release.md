# SOP-019 Git 发布

**修订：** 4　**状态：** baselined　**适用：** all

## 目的与范围

将源码与文档基线推送到授权远端；产品门禁通过后，将同一版本的通行证和已验证产物固化为正式 Git 发布。先按本次任务选择对应分支。

## 触发条件

用户授权推送源码，或候选取得有效通行证且已有正式发布授权。

## 前置条件

源码推送：明确目标远端、分支、版本范围和授权，文档及适用工具检查通过，保留实际产品测试状态。正式 Tag 创建前还须 SOP-018 针对确定候选 SHA 完整 PASS 并生成有效通行证；受保护发布任务和远端权限已配置，预期 tag/Release 不存在且候选提交/产物未改变。不得先建 Tag 以触发首次发布验证。

## 输入

release_id、源码提交、版本 manifest、Changelog、实际检查证据及目标 Git 远端；正式发布另需通行证和最终资产。

## 执行步骤

### 源码基线推送

1. 用 `git status --short --branch`、`git remote -v`、`git ls-remote --heads origin` 核对改动、远端和目标分支；其他远端使用已确认名称。提交前同步版本说明与执行记录，按版本规范保留历史和提交标题。
2. 执行 `python3 scripts/check_docs.py --mode baseline`、`python3 scripts/quality_gate.py check` 及适用回归。基础规范版本允许上传源码和文档，产品 E2E 的 BLOCKED 必须如实保留；源码上传不触发正式发布步骤。
3. 确认提交范围后，按授权目标执行 `git push --set-upstream origin HEAD`，默认推送当前版本分支。不得隐式强推、改写远端历史或改推主分支；冲突先检查原因。
4. 用 `git rev-parse HEAD` 和 `git ls-remote --heads origin <实际分支名>` 核对完整 SHA；保存命令、退出码、远端引用与结果到本轮证据。仅推送源码时转 SOP-022，不创建 Tag/Release 或通行证。

### PR 创建与合并

用户已授权后续由 Codex 自行创建 PR 并在适用检查通过后合并。源码推送后先用 `gh pr list --head <实际分支>` 查重；不存在时用 `gh pr create --base <已核实默认分支> --head <实际分支> --title <版本标题> --body-file <说明文件>` 创建。说明写最终范围、实际测试、阻塞与版本档案；创建后将 PR 链接附加到当前任务。

用 `gh pr view <PR> --json headRefOid,mergeable,statusCheckRollup` 和 `gh pr checks <PR>` 核对实际候选及检查，失败先读取日志并按 SOP-015 修复。产品功能 PR 必须有完整本轮与历史 E2E，通过后以 `gh pr merge <PR> --merge --match-head-commit <已验证SHA>` 合并；不得使用管理员绕过、删除失败检查或把产品改成基础规范逃避。合并后核对 PR merged 状态、merge SHA 与远端主分支，再快进同步本地；保留失败证据。缺环境时可以创建带明确阻塞的 PR，不能宣称功能验收完成或强行合并。

### 正式产品发布步骤

1. 执行 python3 scripts/release_registry.py show 核对当前档案；如发布其他版本，使用 --release-id 指定实际编号，并核对返回编号。
2. 受保护发布任务消费候选 CI 生成的原通行证，重新核验受信运行身份、来源、签名产物摘要、对应 commit 和精确 Changelog 标题。若后续配置 Tag 触发，仅用于核对已经通过的发布，不补做或替代创建 Tag 前的候选门禁。
3. 仅创建与 release_id 完全相同的 annotated tag，指向通过验证的提交；创建同名 Git Release 并附原包、原报告和原通行证。
4. 检查远端 tag 指向、Release 名称、资产摘要与查询链；不能成功后再替换包或移动 tag。
5. 实际结果写入不可覆盖的发布记录，源文档不得为写入自身 SHA 而反复提交。内部版由 `internal-release.yml` 的publish job调用 `scripts/internal_publish.py publish` 消费本次通行证，重新读回远端必需检查、依赖job与环境策略后创建annotated Tag和同名Release，并核对GitHub资产SHA256；基础建设版无产品PASS，不创建产品tag。

## 输出

源码推送产出已核对 SHA 的远端分支；正式发布产出不可变 tag、同名 Release、已验证资产/报告/通行证和可查询关联。

## 成功与失败判据

源码推送成功须远端目标分支等于本地提交且未改写未授权历史。正式发布须所有标识、commit、资产与通行证一致且远端操作成功；源码推送成功、单有 Git tag 或同名 JSON 均不构成产品发布通过证明。

## 异常恢复

部分失败时停止后续部署，保留已发生操作的事实并核验远端状态；不盲目重建已存在 tag/Release，不改写历史来掩盖失败。

## 证据位置

源码推送保存本轮 `.local/git-sync/` 命令日志、远端引用/提交及工作记录；正式发布保存受保护任务日志、远端 tag/Release URL、资产摘要和版本查询结果。失败同样保留，推送后证据引用已有提交，避免将自身 SHA 回写成循环提交。

## 下一步

正式发布后执行 [SOP-020 部署分发](SOP-020-deployment.md)；源码基线推送或只需归档时执行 [SOP-022](SOP-022-archive-handoff.md)。
