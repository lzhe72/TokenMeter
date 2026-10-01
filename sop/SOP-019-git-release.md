# SOP-019 Git 版本追踪

**修订：** 13　**状态：** baselined　**适用：** all

## 目的与范围

在多会话开发中把已提交源码保存到远端同名功能分支，并由总控按依赖顺序集成本地`master`、可选备份整合链；这些操作仅提供版本追踪。全部需求源码完成后，总控统一遵守保护规则登记远端`master`，不以逐版完整E2E、通行证或稳定包为前置。用户另行启动正式对外发布后，才对固定最终候选完成一次完整门禁、正式包归档及正式Tag。安装包及原始证据不上传Git。

## 触发条件

开发会话产生需要保存的WIP/候选源码提交；总控完成一个本地整合里程碑并需要远端源码镜像；全部目标版本源码完成，需要统一登记远端`master`；或正式发布PASS后需要登记正式Tag。PR只在远端策略要求时作为受控路径。

## 前置条件

用户已授权远端Git承担源码版本管理，产品开发、测试、打包及发行在本机完成；2026-10-01最新指令将开发阶段限于各功能已基线固定TC回归，全量跨需求E2E及正式发行待用户另行启动。每个需求有自己的worktree、`codex/<release_id>/<功能名>`分支、明确负责人和输入基线；远端同名分支与单一integration镜像可先保存源码检查点，`master`由总控最后统一办理。待推送源码须有已完成提交、干净工作树、真实检查状态与可核对SHA/tree；WIP及未通过功能回归均如实标记，不称功能验收或发布PASS。开发里程碑及远端源码登记不以逐版完整E2E、SOP-018通行证或SOP-020稳定包为前置。正式Tag须用户发布指令、最终候选完整门禁PASS、稳定包归档和远端读回。未提交的用户改动不得带入其他会话工作树或整合。

## 输入

各需求worktree/分支与负责人、release_id、提交及本地功能TC回归的真实状态、计划推送的远端引用、版本档案与Changelog；本地`master`逐版里程碑SHA/tree、最终整合候选；远端同名分支、整合镜像及`master`的当前引用、保护规则、工作流触发条件和实际Git客户端路径/版本。正式Tag阶段另输入最终候选完整E2E、原包/通行证/稳定归档摘要。官方操作依据：[Git worktree](https://git-scm.com/docs/git-worktree)、[Git push及快进规则](https://git-scm.com/docs/git-push)、[GitHub PR合并方式](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github)、[GitHub Git refs API](https://docs.github.com/en/rest/git/refs)、[GitHub Git commits API](https://docs.github.com/en/rest/git/commits)。

## 执行步骤

1. 每个开发会话在独立worktree使用自身`codex/<release_id>/<功能名>`分支；优先使用Codex托管worktree工具，已有可用检出优先复用。运行`git worktree list --porcelain`、`git status --short --branch`、`git branch --show-current`、`git remote -v`，核对工作树归属、分支名、release_id和负责人；分支共享同一Git对象库但有各自工作目录，不能因分支可见就读取或改写其他会话的未提交文件。总控记录所有分支/本地里程碑映射。按SOP-009记录`command -v git`、`git --version`和实际选用的绝对Git可执行文件路径/版本；同机多个Git实现的push结果分别保存，不能只写“Git失败”或据某个客户端版本推断远端已保存。推送前只读核对目标远端分支、权限、保护及`.github/workflows/`触发；若该推送会未经用户要求启动完整多环境Actions测试，先按SOP-000处理冲突，不悄悄触发。以实际远端规则为准，不从旧快照推断。
2. 开发会话仅选择本任务授权的源码、文档、配置、固定测试和数据程序入库，运行`git diff --cached --name-only`、`git diff --cached --check`和`git status --short`核对暂存范围及敏感内容。按版本规范提交，记录commit SHA、`HEAD^{tree}`、父提交、适用检查命令/退出码及本功能全部固定TC的PASS/FAIL/BLOCKED/NOT_RUN；提交后确认`git status --porcelain`为空。DMG/ZIP、数据库、密钥、`node_modules`、原始报告、通行证及用户真实数据不能入Git。WIP可有未完成或失败的产品检查，但须记录原状态与下一步；只有本功能已基线固定TC完整通过才标记“功能回归通过”，源码候选状态另行记录。所有开发提交均记`release_eligible=false`，未运行的全量门禁记NOT_RUN，不签发通行证。已推送提交不得amend、rebase或删除来改写远端分支历史。
3. 开发会话或总控将已核对的干净提交推送到**同名**远端功能分支。以下Git网络命令均用步骤1记录的同一个绝对Git可执行文件执行，保存每次实际路径、版本、命令和退出码。先用`git ls-remote --heads origin refs/heads/<分支名>`读取远端引用并核对输出的完整ref恰为目标；已存在时运行`git fetch origin refs/heads/<分支名>`并记录`FETCH_HEAD`，要求`git merge-base --is-ancestor FETCH_HEAD HEAD`成功；不存在时记录“待创建”。只使用显式单分支、无强制选项的`git push origin HEAD:refs/heads/<分支名>`，不得使用`--force`、`--force-with-lease`、前缀`+`、`--all`或`--mirror`。推送后用`git ls-remote --heads origin refs/heads/<分支名>`读回完整ref及SHA，再fetch该精确引用，核对`FETCH_HEAD`的SHA和`FETCH_HEAD^{tree}`与本地记录一致；或以只读GitHub Git refs/commits API读回相同完整ref、commit SHA和tree SHA，保存API响应、状态码与仓库身份。`gh api repos/<owner>/<repo>/git/ref/heads/<分支名>`与`gh api repos/<owner>/<repo>/git/commits/<SHA>`是可用入口，须核对实际仓库/host且不把认证信息写日志。若push出现HTTP 400或网络超时，先只读复核远端；确认目标仍未更新且分支无竞争前，可改用另一已记录版本的绝对Git客户端重做同一无强制推送，保留两次原始结果。目标分支前进、分叉、权限拒绝或任何读回不一致时停止，协调负责人合并新提交后再普通快进；传输失败且无法读回时记`remote_code_saved=unknown`/BLOCKED，不因命令已发出写PASS。只有精确SHA/tree读回成功才记`source_checkpoint=WIP`或`CANDIDATE`、`remote_code_saved=true`、`release_eligible=false`，不写E2E/发行PASS。
4. 总控按TM001→TM002→TM003→TM004→TM005依赖顺序，在该需求的开发切片/版本基线、适用基础检查及功能TC真实状态已记录后，把需求分支逐支集成到隔离的本地`master`工作树；已知FAIL/BLOCKED/NOT_RUN可随源码整合，但逐项记录并继续修复，不能称该功能验收通过。先`git fetch origin master`核对远端基线，若本地与远端分叉则停止查明，不覆盖本地独有提交或强制重置。干净检出执行`git switch master`、在可快进时`git merge --ff-only origin/master`，再按版本`git merge --no-ff <需求分支>`；冲突按原需求/用例修正并保留整合记录。功能分支远端备份不等于允许绕开本地顺序直接合并远端`master`。缺上一稳定包不阻断源码整合，仅使依赖它的开发TC及未来正式升级/发行门禁BLOCKED。全部本地里程碑须留在同一`master`祖先链；不rebase或丢弃已登记来源提交。
5. **每个开发里程碑**整合后记录`git rev-parse master`、`git rev-parse 'master^{tree}'`、父提交、release_id、分支来源和干净工作树状态，冻结提交及适用文档/用例/依赖清单。执行本阶段适用SOP-008/013检查及该功能全部固定TC回归，或绑定已实际执行且源码/包/测试输入相同的功能run；新增整合冲突或输入变化须重跑受影响TC。完整跨需求E2E、SOP-018/020及正式Tag留NOT_RUN/未发行，不要求每版里程碑形成稳定包。开发/候选包和首版受控101不可充当上一实际稳定包。独立纯规范分支只做SOP-000/008/024结构、基线、治理和引用检查，明确`release_eligible=false`。功能分支提交、远端备份、旧候选报告或仅tree相似均不能替代功能回归，更不能替代未来最终候选完整门禁。
6. 总控可为本轮五版整合链固定**一个**`codex/<首个release_id>/integration`远端镜像分支，记录其名称和唯一推送负责人。步骤4产生并记录干净的本地`master`整合提交后即可备份该提交，不必等待产品门禁；每次只从该固定SHA推送到镜像引用。先按步骤3核对远端已有提交为该SHA祖先，再用`git push origin <本地整合SHA>:refs/heads/<整合镜像分支>`普通快进更新，读回远端SHA/tree与该提交一致。此分支持续保存同一祖先链，不能强推或改写旧里程碑，也不得提前作为远端`master`、正式Tag或发布PASS；镜像备份时本机门禁未完成就明确记为待测。若未建镜像，记录“可选未执行”；若镜像落后或推送失败，本地真实门禁与稳定包结论单独保留，远端源码备份状态记待办/BLOCKED。
7. 全部目标需求的源码按步骤4/5留在同一本地`master`祖先链且适用开发检查状态已真实记录后，由总控启动**一次最终远端`master`源码整合**；不等待每版完整E2E、018通行证或020稳定包。重新读取远端保护及工作流触发，核对`origin/master`是否前进；2026-10-01远端`master`旧Actions必需检查已移除，仍须以实际PR、管理员执行、对话解决及强推/删除限制为准。若保护允许直推且全部要求实际满足，用普通快进推送并读回；强制PR则走步骤8。远端源码登记只表示Git保存，所有功能回归缺项和正式门禁NOT_RUN/未发行随状态记录，正式Tag保持待办。保护变化无法满足时远端登记BLOCKED，本地原件和结论单独保留。
8. 对强制PR规则，可用步骤6的同一整合镜像分支或以最后一个本地`master`整合候选建立单一PR来源分支，保留全部本地里程碑祖先及最终SHA/tree；核对PR base/head、实际保护和远端`master`未前进。只使用能保留来源祖先的合并提交方式，不能squash或rebase；GitHub的普通Merge pull request会加入来源提交，squash/rebase会改变来源历史。若远端策略无法保留，远端登记BLOCKED并核对可行路线。审查、对话解决及新required checks按实际要求核对；本机报告不能冒充远端检查。GitHub Actions完整多环境测试只在用户明确要求时设计和启动，不私自降低远端保护。
9. 合并PR前逐版复核本地里程碑是整合候选的祖先、各版SHA/tree、来源分支及适用功能检查状态，核对远端base/head是否改变。远端base前进或PR改变候选内容时形成新的本地源码整合候选，重做受影响的开发检查；完整发行门禁仍未启动。合并后读回远端`master`SHA/tree，与本地整合候选严格映射，并逐版核对里程碑提交从远端`master`可追溯。任一来源消失、内容不符或无法证明一致，远端源码登记BLOCKED。记录不同的远端合并SHA，不写成原本地SHA。若后续正式发布的最终候选与已登记源码不同，按保护规则另行登记新源码提交并读回，完整门禁必须绑定该最终候选，不借旧报告。
10. 开发阶段不创建正式发行Tag。只有用户另行启动正式发布、最终候选取得SOP-018 PASS并经SOP-020归档后，总控才为实际正式发行的release_id创建annotated源码Tag，精确指向远端可追溯的被测最终候选里程碑，读回Tag SHA及目标。此前开发里程碑只靠分支/提交追踪，不虚构逐版正式Tag或稳定包；Tag不独立授予发行资格，不创建GitHub Release或上传包/原始证据。Tag已存在、目标冲突或来源不符即停止登记，不移动已登记Tag。
11. 在本机`.local/git-sync/`及各版本06保存“需求分支/worktree→本功能固定TC和适用基础检查真实状态→同名远端读回→本地里程碑→可选整合镜像读回→远端master保护快照/PR/读回→正式发行NOT_RUN/后续最终门禁run/package/passport/020归档→正式Tag”的映射，保存实际命令、退出码、SHA/tree及错误原文；未执行阶段只记NOT_RUN/待办，不写PASS。文档会话按SOP-024将非SOP版本记录与规范同步，不回写原被测提交。

## 输出

各会话独立worktree和已读回的远端源码检查点、可选整合镜像；逐版本地`master`开发里程碑及真实功能TC状态；最终远端`master`源码读回。正式发布另产生最终候选门禁/稳定包和该正式版本Tag映射。本地索引分别显示“代码已保存”“功能回归状态”“正式发行状态”“远端master/Tag状态”。

## 成功与失败判据

源码检查点成功要求提交/工作树干净、范围与真实检查状态可核对、远端同名分支快进或新建并读回相同SHA/tree；WIP可记录产品检查失败或未运行，检查点始终`release_eligible=false`。整合镜像成功只要求远端保持本地里程碑祖先链并读回目标SHA/tree，亦不授予产品PASS。纯规范分支本地整合还须结构、基线和治理检查PASS。最终远端源码登记要求全部目标源码按依赖顺序处于本地`master`祖先链、各功能固定TC及缺项真实记录，并按步骤9读回远端映射；不要求逐版完整E2E/稳定包。正式发行与Tag成功另要求用户发布指令、最终候选完整E2E、最终原包与018门禁真实PASS、020原包/通行证独占归档并读回。远端非快进、来源或读回不符、未清理工作树、缺源码范围证据或推送拒绝阻断源码登记；产品检查FAIL/BLOCKED、缺稳定升级源或原始证据阻断功能验收及正式发行，不抹去已核对的源码保存事实。

## 异常恢复

保留本地提交、每个Git客户端的原始错误、开发测试原件及远端已发生事实。网络结果不明时先用可用Git客户端或只读GitHub API核对精确ref/SHA/tree，不盲目重推；API正常不能证明Git传输故障已恢复，反之亦然。远端分支前进时fetch并协调产生包含双方历史的新提交，只允许普通快进，禁止强推、改写已推送提交、移动Tag或修改门禁结果。保护新增无法满足的要求时仅远端阶段BLOCKED，按步骤8处理；内容变化先重做受影响功能TC，正式发行阶段还须对新最终候选重跑完整门禁。

## 证据位置

本机`.local/git-sync/`、`releases/<release_id>/06-iteration-record.md`、原始测试/门禁目录和本地发行档案。远端Git只留源码提交/分支/Tag，不保存原始证据、通行证或包。

## 下一步

开发中的检查点继续对应需求的SOP-012/013/014；最终远端源码登记完成后走[SOP-022](SOP-022-archive-handoff.md)记录未发行状态。用户另行启动正式发布时，在最终候选执行014→017→018→[SOP-020](SOP-020-deployment.md)，随后按本SOP登记正式Tag。具体产品与候选合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。
