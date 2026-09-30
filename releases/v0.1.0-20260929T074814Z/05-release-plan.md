# v0.1.0-20260929T074814Z — 发布预案

## 发布范围与当前状态

TM-001：预置账号与登录、权限管理和最小更新器。版本0.1.0，未发布；[Changelog](../../CHANGELOG.md) 与本档案使用相同 release_id。基础来源为已合并548c582；无上一公开稳定App安装包。

## 候选、平台和资产

源文档/代码/数据/测试先形成干净候选。用户本轮目标为团队内部使用：`distribution_profile=internal`。内部 DMG 仍须从固定 SHA 构建、记录 DMG/内部 App 摘要，经 macOS14+ arm64/Intel 实际包安装、启动、六例原生回归、隔离 HTTPS 更新源升级、生产 SQLite 副本备份恢复与专用机器门禁，才能作为内部版本分发；签名类型、Gatekeeper 行为、安装路径和交付边界须在候选上实测并写报告。现有 `package_preview_dmg.py` 只能产生预览诊断包，`package_release_dmg.py` 只覆盖 Developer ID 公证公开分支；内部包打包/验证和 `distribution_profile=internal` 的质量门禁尚未实现，故内部正式发布 BLOCKED，不能把预览包改名或改报告字段冒充通过。公开分支 `distribution_profile=public` 保留 Developer ID、hardened runtime、公证、装订、Gatekeeper 和最终包全矩阵；当前亦缺真实 Developer ID、Keychain 公证 profile 和完整执行证据，保持 BLOCKED。两个 profile 共用 SOP-017/018 的步骤顺序，但各自判定不同，不互借通过证据。开发迭代允许隔离自签身份验证 Sparkle 包签名与本版文件凭据自动登录，迭代 PASS 不授予任一 profile 的发行资格。

此前 `package_preview_dmg.py` 曾将 CI 的 UITESTING App 包装成本机预览 DMG；新的严格临时凭据路径被写入 UITESTING Info.plist，离开 runner 后不可用于用户本机登录，也不得回落读取生产凭据。故本候选停止自动从该包生成预览 DMG，脚本须显式拒绝 `TMTestCredentialsDirectory`，工作流仅可保留测试 App 压缩件作诊断，不提供新的可安装预览包。现有 `/Applications/TokenMeter.app` 是旧预览诊断，不代表新候选或内部分发；用户本机使用的新内部 DMG 须等独立无测试路径构建与完整包级门禁。

首版最终候选先独立完成干净安装与六例E2E，其中包括默认本机地址、可配置服务与会话隔离；再经隔离HTTPS源从候选更新到受控高版本包。登记受控包源码、构建版本、摘要、签名；升级后包的结果不替代原候选验收。拒绝坏签名/中断，保留原版与账号状态。未来生产服务器 HTTPS 地址确定后，另一个版本须把新内置默认值和仅迁移未手动配置用户的规则写进该版升级计划，并在真实升级 E2E 中验证；当前不预设地址或把迁移算作通过。

内部 Tag/Release 或任何分发动作仍以 `distribution_profile=internal` 的机器通行证为前提；预期Tag和Release名称同本release_id，预期通行证为 `<release_id>.passport.json`。当前不能签发；源码 PR 在完整迭代通过后可先合并，但合并不等于发版。内部与公开两个 profile 均按017→018→019→020执行，程序须绑定profile、固定SHA和最终包证据。

## 数据与恢复

v0.1.0 服务端生产库为 `database/production/production.db`，Codex 回归库为 `database/test/test.db`；两库不得复用账号或数据。首次生产初始化运行 Alembic 并预置 `admin / 123456`，要求首次登录改密；后续启动和检查不得覆盖已改密码与真实成员。测试 SQL 由程序生成并只导入回归库。无历史产品schema需要升级。生产升级前备份账号库、校验hash和restore；服务健康检查和认证自检通过才分发客户端。失败停止发布，保护旧包和数据库；无有效恢复证据不能上线。MySQL迁移留待后续版本，不作为本版门禁。

## 当前条件与PR

本机缺完整Xcode，远端macOS runner可调度但原生UI/更新须实际验证。远端内部发版保护与专用机器门禁未就绪；公开分支另缺 Developer ID/公证和受保护分发配置。Codex按用户持续授权创建PR、检查、修复并在适用门禁通过后合并；不得管理员绕过失败检查，不因能合并就创建Tag。缺环境时提交真实进展和阻塞，不能预填通行证。
