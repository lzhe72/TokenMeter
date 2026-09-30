# v0.1.0-20260929T074814Z — 发布预案

## 发布范围与当前状态

TM-001：预置账号与登录、权限管理和最小更新器。版本0.1.0，未发布；[Changelog](../../CHANGELOG.md) 与本档案使用相同 release_id。基础来源为已合并548c582；无上一公开稳定App安装包。

## 候选、平台和资产

源文档/代码/数据/测试先形成干净候选，release门禁在Tag之前运行。最终分发包使用DMG，需Developer ID、公证、Sparkle EdDSA签名；分别登记DMG与内部.app摘要，从DMG安装后执行完整验收，再以GitHub Release资产提供下载。`scripts/package_release_dmg.py` 已建立正式预检、签署、公证、装订和包内校验入口；当前没有真实 Developer ID 候选、Keychain 公证 profile 或完整执行证据，保留BLOCKED。macOS14+ arm64/Intel实际支持矩阵逐项验证。开发迭代可以使用开发签名和明确的开发矩阵，不能据此签发正式通行证。

用户本机体验可按SOP-017的预览诊断分支，从已验证的UITesting App生成带明显标识的本机DMG。`scripts/package_preview_dmg.py`只接受该隔离bundle及loopback服务，验证签名、镜像与App内容，输出摘要。用户已要求本机生产库预置账号，可由预览 App 连只绑定回环地址的生产 SQLite 服务；诊断不得重置该库。v0.1.0 正式 App 也以 `http://127.0.0.1:49176` 为首次默认值，仅回环 HTTP 可用；非回环服务器仍要求 HTTPS。quality工作流在Intel原生运行后将预览DMG上传为短期Actions工件，允许用户在GitHub下载；该上传即使完整产品门禁BLOCKED也不能被解释为发布。此包不带生产更新源，既不是上述最终候选，也不进入GitHub正式Release或通行证。

首版最终候选先独立完成干净安装与六例E2E，其中包括默认本机地址、可配置服务与会话隔离；再经隔离HTTPS源从候选更新到受控高版本包。登记受控包源码、构建版本、摘要、签名；升级后包的结果不替代原候选验收。拒绝坏签名/中断，保留原版与账号状态。未来生产服务器 HTTPS 地址确定后，另一个版本须把新内置默认值和仅迁移未手动配置用户的规则写进该版升级计划，并在真实升级 E2E 中验证；当前不预设地址或把迁移算作通过。

预期Tag和Release名称同本release_id；预期通行证为 `<release_id>.passport.json`，程序校验可信证据通过后才签发。正式发布继续经017→018→019→020。

## 数据与恢复

v0.1.0 服务端生产库为 `database/production/production.db`，Codex 回归库为 `database/test/test.db`；两库不得复用账号或数据。首次生产初始化运行 Alembic 并预置 `admin / 123456`，要求首次登录改密；后续启动和检查不得覆盖已改密码与真实成员。测试 SQL 由程序生成并只导入回归库。无历史产品schema需要升级。生产升级前备份账号库、校验hash和restore；服务健康检查和认证自检通过才分发客户端。失败停止发布，保护旧包和数据库；无有效恢复证据不能上线。MySQL迁移留待后续版本，不作为本版门禁。

## 当前条件与PR

本机缺完整Xcode，远端macOS runner可调度但原生UI/更新须实际验证。远端尚无分支保护或release-validation环境，生产证书/HTTPS分发配置未提供。Codex按用户持续授权创建PR、检查、修复并在适用门禁通过后合并；不得管理员绕过失败检查，不因能合并就创建Tag。缺环境时提交真实进展和阻塞，不能预填通行证。
