# v0.1.0-20260929T074814Z — 发布预案

## 范围、输入与状态

输入：[需求](01-requirements.md)、[测试计划](04-test-plan.md)、[当前设计](../../docs/architecture/01-electron-local.md)、[发布规范](../../docs/standards/release.md)。TM-001首版0.1.0/build100，macOS15 Intel，本机Electron内部分发。当前未发布；六例及最终包门禁尚待执行，不预填通行证。

## 构建、验证与本地资产

使用干净候选完整SHA/tree和锁定依赖，electron-builder目录包→固定自签证书嵌套签名→DMG安装包与ZIP更新包。无Apple Developer账号或公网发布要求。公证不作为本轮内部配置的必需项，实际签名与系统打开行为必须如实记录；不关闭Gatekeeper或全局移除隔离来伪造通过。

从同一DMG安装正式App，完整六例；首版没有上一稳定版，另构建同源受控0.1.1/build101验证真实自主更新，受控包不交给用户充当0.1.0。以后使用上一实际稳定本地包升级。全部原始证据经local_gate独立复核，PASS才生成v0.1.0-20260929T074814Z.passport.json。

开发/候选DMG的便捷副本以`NOT-RELEASED`标记放在仓库根`dmg/v0.1.0-20260929T074814Z/`，原件仍按候选独立保存并接受测试。门禁PASS后，最终原DMG、更新ZIP、package-manifest、测试报告/通行证存同版本目录的`release-archive/`并读回摘要，再把已验证原DMG以原名独占复制到版本目录供安装；不覆盖已有档案，不重建包借用报告。Git保存源码、版本文档、Changelog与Tag索引；不创建GitHub Release、不上传安装包/报告。Actions仅未来用户明确要求多环境时执行。

## Git、部署和恢复

总控先把本版需求分支按适用检查集成本地`master`；对最终整合提交执行完整逐TC及六组补充产品E2E、最终DMG安装升级验证和本机发布门禁。PASS后按当前远端强制PR规则，以同一已测本地整合候选建立受控PR，满足仍有效的保护并读回实际合并SHA/tree，再建立正式Tag与本地归档；禁止强推、删除保护或用旧分支报告替代整合候选。2026-10-01已按用户决定移除旧Actions必需检查，不启动多环境Actions；若远端保护发生变化则重新核对。实际合并tree与被测候选不同须重测。产物始终绑定实际被测SHA。

API默认http://127.0.0.1:49176，更新清单默认http://127.0.0.1:49177/version.json；可在App真实配置管理中修改。生产SQLite保留database/production/production.db，Codex测试database/test/test.db及隔离临时副本，不能覆盖生产账号。新库仅admin/123456且强制改密；已有库不重置。服务端归档可独立安装，先备份并验证恢复，再升级兼容服务，随后用户安装已验证DMG。

测试不替换用户现有/Applications/TokenMeter.app、不终止用户服务。失败保留原包、原库和诊断，停止通行证签发，按SOP-015/021修复或恢复；没有PASS不得写更新清单推广。公开分发或arm64另立范围、测试矩阵和证据。
