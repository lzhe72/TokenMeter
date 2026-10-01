# 开发规范

首先读取[SOP索引](../../sop/README.md)和对应详细步骤；规范驱动文档、文档驱动开发。当前技术合同见[Electron本机设计](../architecture/01-electron-local.md)，不再把完整Xcode列为开发前提。

## 实现约束

- Electron/React/TypeScript、Vite/electron-vite、node:test、Playwright Electron、electron-builder，精确版本和lockfile同轮提交。客户端、更新打包、测试编排与父门禁按版本开发计划明确文件所有权。
- FastAPI单体与版本化/v1接口；当前服务端开发/生产均SQLite，测试和生产独立目录。MySQL仅后续独立迁移需求。权限由服务端执行。
- renderer无Node权限，contextIsolation/sandbox开启，preload只暴露业务方法；主进程逐项校验IPC参数、sender/window/frame/origin。禁止外部导航、新窗和任意文件/网络接口，CSP限制静态资源。
- token仅主进程持有，受保护目录0700/文件0600、同uid、拒绝symlink/hardlink、按API origin隔离和原子写。保存密码、把token发renderer或写日志都不允许。自动登录必须/me真实验证，退出与重置撤销会话。
- 正式App支持合法独立profile，测试从同一安装包配置隔离；无认证旁路或业务mock。生产App/库/真实工具日志及现有服务不能作测试数据。
- 更新URL逐跳校验；元数据不证明包身份，须验长度/hash/Ed25519、实际App Info和签名要求后交原生更新器；完整升级由实际E2E证明。
- 日志采集仅授权目录及必要用量/去重数据，不上传正文、密钥、完整路径；时间UTC、未知值不填零、价格版本可追踪。用户已选目录的可恢复 locator 只在当前用户私有来源配置中以系统密钥保护的密文保存（目录0700、文件0600），不回退明文；密文和明文完整路径均不得进入用量、同步、诊断、报告或Git。解密/密钥失败须停读重选，撤销须删除密文，主进程每次核对来源、账号与授权根身份。

## 开发与完成

每项功能先需求/验收/详细用例/数据SQL/SOP；骨架后先有效失败用例，再实现；变更同步文档、矩阵、Changelog。基础检查后，功能完成或修复执行该功能已基线固定TC与变体的真实回归；缺项/失败不能记功能PASS。整版仍draft时，只有按SOP-008明确列出的无未决依赖TASK/TC切片可先开发，模块测试不代替对应产品TC。用户另行启动正式对外发布后，对最终候选执行目标及已交付功能的完整E2E并集；不能仅跑单元或降低正确预期。

文档完成、实现存在、测试通过分别登记；缺环境/程序/证据明确BLOCKED。保留首个失败，按SOP-015修根因。最终原DMG和本机门禁通过才可发行，Git不保存安装包或原始报告。状态页和版本06记录实际命令、结果、证据与接手入口。

## 多会话工作树与源码检查点

每个需求会话使用独立worktree和`codex/<release_id>/<功能名>`分支，先核对分支、来源提交、负责人和未提交文件的归属。只把本任务已核对的源码、文档、配置、固定测试和数据程序暂存；运行`git diff --cached --name-only`、`git diff --cached --check`并保存实际结果。提交后工作树须干净，记录完整SHA/tree、父提交和适用检查的真实PASS/FAIL/BLOCKED。不能把另一会话的未提交文件复制成无来源的候选。

干净且范围可核对的WIP或候选提交可按[SOP-019](../../sop/SOP-019-git-release.md)普通快进推送远端**同名功能分支**，前后读取精确引用并核对SHA/tree。WIP允许产品测试未通过或未运行，须原样登记`source_checkpoint=WIP`、`remote_code_saved`和`release_eligible=false`；源码读回只说明代码已保存。已推送提交不amend/rebase，不强推或覆盖他人进展。总控可选单一`codex/<首个release_id>/integration`镜像本地整合祖先链；镜像读回也不产生本机产品PASS。DMG、ZIP、数据库、密钥、`node_modules`、原始证据和通行证留本机，不进入Git。完整多环境Actions只在用户明确要求时运行。
