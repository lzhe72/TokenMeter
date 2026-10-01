# SOP-019 Git 版本追踪

**修订：** 7　**状态：** baselined　**适用：** all

## 目的与范围

由项目总控把各需求分支先集成到本地 `master`，对最终整合树执行适用门禁，再统一推送远端 `master`；保存源码、版本与本地发行的关联。安装包及原始证据不上传 Git。

## 触发条件

需求分支达到本地集成条件，或已通过正式本机发布门禁、需要建立源码 Tag。PR 只在远端策略要求时作为受控替代路径，不再是默认集成步骤。

## 前置条件

用户已授权总控自主整合、推送和适用门禁后的发行。分支具有对应 release_id、文档基线、固定测试程序和适用检查结果；本地与远端 `master` 的实际状态可核对。产品迭代/修复在远端集成前须有**本地 master 最终整合提交**对应的完整产品 E2E；正式 Tag 还须 SOP-017/018 的最终包和 PASS 通行证。远端保护要求须可由真实执行满足；用户的发行授权不等于授权降低分支保护或启动未要求的多环境 Actions。未提交的用户改动不得覆盖或带入整合。

## 输入

需求分支及其提交、版本档案与 Changelog、`origin/master`、最终整合候选 SHA/tree、适用检查、原始 E2E/包证据和通行证摘要；远端保护规则、required checks 的来源、工作流触发及适用的用户决定。

## 执行步骤

1. 由总控运行 `git status --short --branch`、`git remote -v`、`git ls-remote --heads origin master`，核对当前分支、远端及未提交改动。以只读 GitHub API 核对 `master` 的 PR、required checks（名称、预期 App、strict）、管理员执行、强推/删除规则，并核对工作流实际触发条件；保存带时间的原始规则快照，不能从旧记录推断当前保护。保存各需求分支提交和 release_id；只将源码、文档、配置、测试及数据程序纳入 Git。DMG/ZIP、数据库、密钥、`node_modules`、原始报告和通行证保留本机忽略目录。
2. 每个需求分支先按其任务和既定 TC 完成适用基础检查及开发阶段回归，记录失败与阻断。总控先以 `git fetch origin master` 获取远端状态，在干净检出中执行 `git switch master`、`git merge --ff-only origin/master`；若远端与本地已分叉则停止并查明差异，不覆盖本地独有提交、用户改动或强制重置。按既定顺序逐支执行 `git merge --no-ff <需求分支>`，遇冲突按原需求/用例修正并保存整合记录。需求分支不各自推送或合并远端 `master`。
3. 最后一支整合后记录 `git rev-parse master`、`git rev-parse 'master^{tree}'`、父提交和工作树状态。对这个**实际本地 master 候选**执行 SOP-008/013/014 的适用检查与本次及此前已交付功能的完整 E2E；正式发行继续 SOP-017/018，从同一最终 DMG 安装验证。分支单独 PASS、旧候选报告、PR 状态或仅 tree 相似均不能替代整合后完整验收。任何整合、冲突修复、源码/依赖/包输入改变均生成新候选并重新核验。
4. 本地候选门禁完成后再次读取远端保护并核对 `origin/master` 未前进。只有远端允许直推且全部实际要求已满足，才普通快进推送并读回 SHA。远端强制 PR 时先走第5步，不尝试把本地 PASS 当作远端 required check。当前若 required checks 绑定 GitHub Actions，而相关工作流仅有 `workflow_dispatch`，不得假定手动运行可满足 PR 检查：[GitHub 官方说明](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)指出在 PR head 手动触发的检查可能不出现在 PR 检查中，也不能满足规则。不得强推、管理员绕过、删除保护、伪造或手写 PASS；不兼容时将远端集成记为 BLOCKED，本地产品结果单独保留。
5. 远端保护不兼容当前本机流程时，先取得用户对**具体迁移方案**的明确决定并保存原规则、拟变更内容和影响：其一，用户明确要求多环境 Actions 后，设计能对该 PR 最新提交实际产生指定来源检查的工作流并真实执行，核对全部 required checks 的名称、App 来源、结论及 strict 基线；仅 `workflow_dispatch` 不足以证明满足。其二，用户明确同意以本机原始门禁为发行依据并调整旧 Actions required checks；须说明远端不再强制这些产品检查的影响，确定保留的 PR/管理员执行/禁止强推删除等规则。若改为新的可信检查，先实现可独立复核原件的集成并验证其身份，不能人工提交成功状态。未获决定、无可执行检查或规则变更未读回时维持 BLOCKED，不能为了通过而临时移除保护再恢复。
6. 经确认的规则实际生效后，以同一已测整合候选走受控 PR；若工作流、源码、依赖或包输入改变，先形成新本地整合候选并重跑适用完整门禁。远端 required checks 必须在最新提交及严格基线真实满足，不接受旧 SHA、仅本地 PASS 或手动状态。合并后读回远端 `master` SHA/tree，与被测候选建立严格 tree 映射；有内容差异或无法证明一致时停止发行并重新验证。记录不同的远端合并 SHA，不能写成原被测 SHA；不要让各需求分支绕开本地整合直接在远端分别合并。
7. 正式发布仅在本机 SOP-018 PASS、通行证与本地 `master` 最终候选/原包一致且远端已读回后，创建同 release_id 的 annotated 源码 Tag，绑定被测提交或第6步已证明严格 tree 相同的远端合并提交，并核对远端 Tag；不创建 GitHub Release，不上传安装包或测试原件。首次尚未发行可继续同版本修候选，已正式发行的 Tag 不移动。
8. 在本机 `.local/git-sync/`、版本 06 和本地发行记录保存需求分支→本地合并 SHA/tree→门禁 run/package/passport→远端保护快照/决定/检查→远端 `master` SHA/Tag 的映射及实际命令、退出码；未执行的步骤只记待办，不写 PASS。

## 输出

本地 `master` 整合与门禁记录、远端 `master` 读回、必要时的源码 Tag 和可查询的本地发行索引。

## 成功与失败判据

成功要求所有需求分支按顺序纳入最终本地候选，适用检查和产品完整 E2E 在该候选上真实 PASS；远端保护规则已只读核对且全部实际满足。允许快进推送时远端 `master` 读回 SHA 与本地一致，强制 PR 时须有第6步的严格 tree 映射及远端提交记录。正式 Tag 另须最终包门禁和通行证 PASS。旧 Actions required checks 与当前工作流不兼容、缺用户迁移决定、任一 FAIL/BLOCKED、无法解释的远端差异、未清理工作树、缺证据或推送拒绝均不得记完成。

## 异常恢复

保留原始失败和已发生的远端事实；不强推、改写历史、移动 Tag 或修改门禁结果。重新核对远端与本地变更，形成新的整合候选并重跑受影响的完整产品门禁；保护策略不允许直推或 required checks 无法真实满足时保持 BLOCKED，按第5步取得决定并执行受控规则变更，不自行降低要求。

## 证据位置

本机 `.local/git-sync/`、`releases/<release_id>/06-iteration-record.md`、原始测试/门禁目录和本地发行档案。

## 下一步

源码整合后走 [SOP-022](SOP-022-archive-handoff.md)；正式发行继续 [SOP-020](SOP-020-deployment.md)。具体产品与候选合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。
