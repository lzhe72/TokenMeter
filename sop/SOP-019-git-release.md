# SOP-019 Git 版本追踪

**修订：** 11　**状态：** baselined　**适用：** all

## 目的与范围

在多会话开发中把已提交源码保存到远端同名功能分支，并由总控可选地备份本地整合链；两者仅提供版本追踪。总控仍按版本依赖逐个集成本地`master`，在每个不可变里程碑完成本机产品门禁、形成稳定包；全部目标版本完成后才统一把源码并入受保护的远端`master`并登记逐版Tag。安装包及原始证据不上传Git。

## 触发条件

开发会话产生需要保存的WIP/候选源码提交；总控完成一个本地整合里程碑并需要远端源码镜像；或全部目标版本完成、需要统一远端`master`与正式Tag登记。PR只在远端策略要求时作为受控路径。

## 前置条件

用户已授权远端Git承担源码版本管理，产品开发、全量测试、打包及发行在本机完成；2026-10-01新增明确要求允许在最终远端`master`整合前，把可核对源码检查点快进保存到远端功能分支或单一整合镜像分支。每个需求有自己的worktree、`codex/<release_id>/<功能名>`分支、明确负责人和输入基线；远端推送只针对对应分支，`master`仍由总控最后统一办理。待推送的源码须有已完成提交、干净工作树、真实检查状态与可核对SHA/tree；WIP允许尚未通过产品测试，但必须如实标记。被测产品版本仍须在**本地master固定里程碑提交**上由固定程序完成本轮与此前已交付功能的完整E2E、SOP-017/018最终包门禁，再按SOP-020形成本机稳定包；远端检查点、PR或Actions结果均不能替代。正式Tag须本机通行证、稳定包归档和最终远端读回。仅规范分支可在结构、基线和治理检查后先行本地整合，记录`release_eligible=false`。未提交的用户改动不得带入其他会话工作树或整合。

## 输入

各需求worktree/分支与负责人、release_id、提交及本地检查结果、计划推送的远端引用、版本档案与Changelog；本地`master`逐版里程碑SHA/tree、原始E2E/包/通行证/稳定归档摘要、最终整合候选；远端同名分支、整合镜像及`master`的当前引用、保护规则和工作流触发条件。官方操作依据：[Git worktree](https://git-scm.com/docs/git-worktree)、[Git push及快进规则](https://git-scm.com/docs/git-push)、[GitHub PR合并方式](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github)。

## 执行步骤

1. 每个开发会话在独立worktree使用自身`codex/<release_id>/<功能名>`分支；优先使用Codex托管worktree工具，已有可用检出优先复用。运行`git worktree list --porcelain`、`git status --short --branch`、`git branch --show-current`、`git remote -v`，核对工作树归属、分支名、release_id和负责人；分支共享同一Git对象库但有各自工作目录，不能因分支可见就读取或改写其他会话的未提交文件。总控记录所有分支/本地里程碑映射。推送前只读核对目标远端分支、权限、保护及`.github/workflows/`触发；若该推送会未经用户要求启动完整多环境Actions测试，先按SOP-000处理冲突，不悄悄触发。以实际远端规则为准，不从旧快照推断。
2. 开发会话仅选择本任务授权的源码、文档、配置、固定测试和数据程序入库，运行`git diff --cached --name-only`、`git diff --cached --check`和`git status --short`核对暂存范围及敏感内容。按版本规范提交，记录commit SHA、`HEAD^{tree}`、父提交、适用检查命令/退出码及真实缺项；提交后确认`git status --porcelain`为空。DMG/ZIP、数据库、密钥、`node_modules`、原始报告、通行证及用户真实数据不能入Git。WIP可有未完成或失败的产品检查，但须记录原状态与下一步；只有达到本轮适用开发检查条件才标记“候选”，两者均记录`remote_code_saved`状态及`release_eligible=false`，不签发产品通行证。已推送提交不得amend、rebase或删除来改写远端分支历史。
3. 开发会话或总控将已核对的干净提交推送到**同名**远端功能分支。先用`git ls-remote --heads origin refs/heads/<分支名>`读取远端引用并核对输出的完整ref恰为目标；已存在时运行`git fetch origin refs/heads/<分支名>`并记录`FETCH_HEAD`，要求`git merge-base --is-ancestor FETCH_HEAD HEAD`成功；不存在时记录“待创建”。只使用显式单分支、无强制选项的`git push origin HEAD:refs/heads/<分支名>`，不得使用`--force`、`--force-with-lease`、前缀`+`、`--all`或`--mirror`。推送后再用`git ls-remote --heads origin refs/heads/<分支名>`读回，确认完整ref及SHA等于待推送HEAD；再次fetch该精确引用，确认`FETCH_HEAD`的SHA及`FETCH_HEAD^{tree}`等于本地记录，并保存命令/退出码。目标分支前进、分叉、权限拒绝、网络错误或读回不一致时停止，保留本地提交和实际远端状态，协调负责人合并新提交后再尝试普通快进；不得覆盖远端进展。读回成功仅记`source_checkpoint=WIP`或`CANDIDATE`、`remote_code_saved=true`、`release_eligible=false`，不写E2E/发行PASS。
4. 总控按TM001→TM002→TM003→TM004→TM005依赖顺序，在上一版本本机稳定包及本版前置条件实际成立后，把需求分支逐支集成到隔离的本地`master`工作树；先`git fetch origin master`核对远端基线，若本地与远端分叉则停止查明，不覆盖本地独有提交或强制重置。干净检出执行`git switch master`、在可快进时`git merge --ff-only origin/master`，再按版本`git merge --no-ff <需求分支>`；冲突按原需求/用例修正并保留整合记录。功能分支远端备份并不等于允许绕开本地顺序直接合并远端`master`。缺上一稳定包时可继续不依赖它的开发准备，下一版本正式升级/E2E/发行门禁仍BLOCKED。全部本地里程碑须留在同一`master`祖先链；不rebase或丢弃已发行的本机来源提交。
5. **每个版本里程碑**整合后记录`git rev-parse master`、`git rev-parse 'master^{tree}'`、父提交、release_id、分支来源和干净工作树状态，冻结该提交及适用文档/用例/依赖清单。对实际本地`master`里程碑执行SOP-008/013/014的适用检查与本版及此前已交付功能完整E2E；正式本机发行继续SOP-017/018，从同一最终DMG安装验证，PASS后按SOP-020独占归档正式稳定包，记录通行证、原包摘要与“远端master/Tag待办”。只有该实际稳定包可供下一版本正式升级；开发/候选包和首版受控101不可替代。独立纯规范分支只做SOP-000/008/024结构、基线、治理和引用检查，明确`release_eligible=false`。功能分支提交、远端备份、旧候选报告或仅tree相似均不能替代里程碑的完整验收；源码/依赖/包输入改变须形成新候选并重新核验。
6. 总控可为本轮五版整合链固定**一个**`codex/<首个release_id>/integration`远端镜像分支，记录其名称和唯一推送负责人。步骤4产生并记录干净的本地`master`整合提交后即可备份该提交，不必等待产品门禁；每次只从该固定SHA推送到镜像引用。先按步骤3核对远端已有提交为该SHA祖先，再用`git push origin <本地整合SHA>:refs/heads/<整合镜像分支>`普通快进更新，读回远端SHA/tree与该提交一致。此分支持续保存同一祖先链，不能强推或改写旧里程碑，也不得提前作为远端`master`、正式Tag或发布PASS；镜像备份时本机门禁未完成就明确记为待测。若未建镜像，记录“可选未执行”；若镜像落后或推送失败，本地真实门禁与稳定包结论单独保留，远端源码备份状态记待办/BLOCKED。
7. 全部目标版本均按步骤5取得本机门禁PASS和稳定包后，才由总控启动**一次最终远端`master`源码整合**。重新读取远端保护及工作流触发，核对`origin/master`是否前进；2026-10-01远端`master`旧Actions必需检查已移除，仍须以实际PR、管理员执行、对话解决及强推/删除限制为准。若保护允许直推且全部要求实际满足，用普通快进推送并读回；当前强制PR则走步骤8。期间各版本远端`master`源码登记和正式Tag保持待办；功能分支或镜像备份不能冒充远端`master`PASS。保护变化无法满足时远端登记BLOCKED，本机原件和结论单独保留。
8. 对强制PR规则，可用步骤6的同一整合镜像分支或以最后一个已测本地`master`候选建立单一PR来源分支，保留全部本地里程碑祖先及最终SHA/tree；核对PR base/head、实际保护和远端`master`未前进。只使用能保留来源祖先的合并提交方式，不能squash或rebase；GitHub的普通Merge pull request会加入来源提交，squash/rebase会改变来源历史。若远端策略无法保留，远端登记BLOCKED并核对可行路线。审查、对话解决及新required checks按实际要求核对；本机报告不能冒充远端检查。GitHub Actions完整多环境测试只在用户明确要求时设计和启动，不私自降低远端保护。
9. 合并PR前逐版复核本地里程碑是最终候选的祖先、每版原始门禁与未变的SHA/tree、包输入及正式本机DMG对应，并复核最后候选完整门禁。远端base前进或PR改变候选内容时形成新本地最终候选，重跑受影响完整门禁；已归档稳定原包及不可变来源不回写或冒用。合并后读回远端`master`SHA/tree，与最后被测候选严格映射；逐版核对里程碑提交从远端`master`可追溯、通行证/归档SHA/tree和原包摘要精确一致。任一来源消失、内容不符或无法证明一致，远端登记BLOCKED，不补Tag。记录不同的远端合并SHA，不写成原被测SHA。
10. 步骤9全部核对通过后，总控按版本顺序为每个已取得SOP-018 PASS和SOP-020稳定归档的release_id创建annotated源码Tag，精确指向远端可追溯的本地里程碑提交，逐个读回Tag SHA及目标。不能用最终第五版树替代前版Tag；Tag不独立授予发行资格，不创建GitHub Release或上传包/原始证据。Tag已存在、目标冲突或来源不符即停止该版及后续远端登记，不移动已登记Tag。
11. 在本机`.local/git-sync/`及各版本06保存“需求分支/worktree→本地检查与WIP/候选提交→同名远端读回→本地里程碑→门禁run/package/passport→020稳定归档→可选整合镜像读回→远端master待办/最终保护快照/PR/读回→逐版Tag”的映射，保存实际命令、退出码、SHA/tree及错误原文；未执行阶段只记待办，不写PASS。文档会话按SOP-024将非SOP版本记录与规范同步，不回写原被测提交。

## 输出

各会话独立worktree和已读回的远端源码检查点、可选整合镜像；逐版本地`master`里程碑及本机门禁/稳定包记录；最终远端`master`和逐版源码Tag映射。本地索引分别显示“代码已保存”“本机产品/发行状态”“远端master/Tag状态”。

## 成功与失败判据

源码检查点成功只要求提交/工作树干净、范围与真实检查状态可核对、远端同名分支快进或新建并读回相同SHA/tree；WIP可记录产品检查失败或未运行，检查点始终`release_eligible=false`。整合镜像成功只要求远端保持本地里程碑祖先链并读回目标SHA/tree，亦不授予产品PASS。纯规范分支本地整合还须结构、基线和治理检查PASS。逐版本机稳定成功要求该版里程碑及此前已交付功能完整E2E、最终包与018门禁真实PASS，020原包/通行证独占归档并读回。最终远端源码登记另要求全部版本按顺序处于本地`master`祖先链、各版稳定原件有效、最后候选完整门禁PASS，并按步骤9读回远端映射；Tag逐版按步骤10核对。远端非快进、来源或读回不符、未清理工作树、缺源码范围证据或推送拒绝阻断源码检查点；产品检查FAIL/BLOCKED、缺前版稳定源或缺原始证据阻断相应候选/发行阶段，不抹去已核对的WIP保存事实。

## 异常恢复

保留本地提交、原始失败、本机稳定原件及远端已发生事实。网络结果不明时先`git ls-remote`读回，不盲目重推；远端分支前进时fetch并协调产生包含双方历史的新提交，只允许普通快进，禁止强推、改写已推送或已发行提交、移动Tag或修改门禁结果。保护新增无法满足的要求时仅远端阶段BLOCKED，按步骤8处理；新候选须重跑受影响的完整产品门禁。

## 证据位置

本机`.local/git-sync/`、`releases/<release_id>/06-iteration-record.md`、原始测试/门禁目录和本地发行档案。远端Git只留源码提交/分支/Tag，不保存原始证据、通行证或包。

## 下一步

开发中的检查点继续对应需求的SOP-012/013/014；本地版本里程碑门禁PASS后走[SOP-020](SOP-020-deployment.md)形成稳定源，再继续下一版本；最终远端逐版登记完成后走[SOP-022](SOP-022-archive-handoff.md)。具体产品与候选合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。
