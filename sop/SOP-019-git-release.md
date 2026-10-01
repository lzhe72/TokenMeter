# SOP-019 Git 版本追踪

**修订：** 6　**状态：** baselined　**适用：** all

## 目的与范围

由项目总控把各需求分支先集成到本地 `master`，对最终整合树执行适用门禁，再统一推送远端 `master`；保存源码、版本与本地发行的关联。安装包及原始证据不上传 Git。

## 触发条件

需求分支达到本地集成条件，或已通过正式本机发布门禁、需要建立源码 Tag。PR 只在远端策略要求时作为受控替代路径，不再是默认集成步骤。

## 前置条件

用户已授权总控自主整合、推送和适用门禁后的发行。分支具有对应 release_id、文档基线、固定测试程序和适用检查结果；本地与远端 `master` 的实际状态可核对。产品迭代/修复在推送前须有**本地 master 最终整合提交**对应的完整产品 E2E；正式 Tag 还须 SOP-017/018 的最终包和 PASS 通行证。未提交的用户改动不得覆盖或带入整合。

## 输入

需求分支及其提交、版本档案与 Changelog、`origin/master`、最终整合候选 SHA/tree、适用检查、原始 E2E/包证据和通行证摘要。

## 执行步骤

1. 由总控运行 `git status --short --branch`、`git remote -v`、`git ls-remote --heads origin master`，核对当前分支、远端及未提交改动。保存各需求分支提交和 release_id；只将源码、文档、配置、测试及数据程序纳入 Git。DMG/ZIP、数据库、密钥、`node_modules`、原始报告和通行证保留本机忽略目录。
2. 每个需求分支先按其任务和既定 TC 完成适用基础检查及开发阶段回归，记录失败与阻断。总控先以 `git fetch origin master` 获取远端状态，在干净检出中执行 `git switch master`、`git merge --ff-only origin/master`；若远端与本地已分叉则停止并查明差异，不覆盖本地独有提交、用户改动或强制重置。按既定顺序逐支执行 `git merge --no-ff <需求分支>`，遇冲突按原需求/用例修正并保存整合记录。需求分支不各自推送或合并远端 `master`。
3. 最后一支整合后记录 `git rev-parse master`、`git rev-parse 'master^{tree}'`、父提交和工作树状态。对这个**实际本地 master 候选**执行 SOP-008/013/014 的适用检查与本次及此前已交付功能的完整 E2E；正式发行继续 SOP-017/018，从同一最终 DMG 安装验证。分支单独 PASS、旧候选报告、PR 状态或仅 tree 相似均不能替代整合后完整验收。任何整合、冲突修复、源码/依赖/包输入改变均生成新候选并重新核验。
4. 只有整合候选的适用门禁 PASS、工作树与候选一致时，总控再次核对 `origin/master` 未前进，并以普通快进推送 `git push origin master:master`；禁止强推、删分支保护或手写 PASS。推送后用 `git ls-remote --heads origin master` 核对远端 SHA 等于本地 `master`。远端前进、拒绝推送或强制 PR/状态检查时记录 BLOCKED，先按现有保护规则解决冲突并对新的最终整合树重跑门禁，不绕过保护。
5. 默认不触发 GitHub Actions 完整测试；仅用户明确要求多环境时按已定矩阵运行。若远端规则必须经 PR，总控使用同一整合候选走受控 PR，核对远端实际合并提交与被测候选的严格 tree 映射；有内容差异或无法证明一致时重新执行完整门禁。记录不同的远端合并 SHA，不能把它写成原被测 SHA；不要让各需求分支绕开本地整合直接在远端分别合并。
6. 正式发布仅在本机 SOP-018 PASS、通行证与本地 `master` 最终候选/原包一致且远端已读回后，创建同 release_id 的 annotated 源码 Tag，绑定被测提交或第5步已证明严格 tree 相同的远端合并提交，并核对远端 Tag；不创建 GitHub Release，不上传安装包或测试原件。首次尚未发行可继续同版本修候选，已正式发行的 Tag 不移动。
7. 在本机 `.local/git-sync/`、版本 06 和本地发行记录保存需求分支→本地合并 SHA/tree→门禁 run/package/passport→远端 `master` SHA/Tag 的映射及实际命令、退出码；未执行的步骤只记待办，不写 PASS。

## 输出

本地 `master` 整合与门禁记录、远端 `master` 读回、必要时的源码 Tag 和可查询的本地发行索引。

## 成功与失败判据

成功要求所有需求分支按顺序纳入最终本地候选，适用检查和产品完整 E2E 在该候选上真实 PASS；默认快进推送时远端 `master` 读回 SHA 与本地一致，远端强制PR时须有第5步的严格 tree 映射及远端提交记录。正式 Tag 另须最终包门禁和通行证 PASS。任一 FAIL/BLOCKED、无法解释的远端差异、未清理工作树、缺证据或推送拒绝均不得记完成。

## 异常恢复

保留原始失败和已发生的远端事实；不强推、改写历史、移动 Tag 或修改门禁结果。重新核对远端与本地变更，形成新的整合候选并重跑受影响的完整产品门禁；保护策略不允许直推时保持 BLOCKED，按受控规则处理，不自行降低要求。

## 证据位置

本机 `.local/git-sync/`、`releases/<release_id>/06-iteration-record.md`、原始测试/门禁目录和本地发行档案。

## 下一步

源码整合后走 [SOP-022](SOP-022-archive-handoff.md)；正式发行继续 [SOP-020](SOP-020-deployment.md)。具体产品与候选合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。
