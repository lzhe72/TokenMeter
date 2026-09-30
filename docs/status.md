# 当前状态

当前版本 `v0.1.0-20260929T074814Z`：TM-001 开发迭代已验收并合并，内部最终安装包仍在准备，**尚未发布 DMG、正式 Tag 或 Release**。执行先读 [SOP 总索引](../sop/README.md)。

## 已核实结果（2026-09-30）

- [CI 36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502)：macOS 15.7.9 Apple Silicon 与 Intel 各完整执行六例原生 E2E，零失败、零跳过；父门禁重新解析原始 xcresult 并核对完整摘要后均 PASS，资源清理成功。
- 测试分支头 `3ad0d7eab06e31b9612d01ecbae9b2a5017f5b6b`，实际 PR 合成候选 `4f4d887c6cb1ce9db89761a61b07ce4004236be6`。两者与最终合并提交的源码树均为 `2b723f41d96256e962cf04ed9105dfb1e2985739`。
- [PR #2](https://github.com/lzhe72/TokenMeter/pull/2) 已于 2026-09-30 合并远端 master，提交 `e011857443b503c2bfafcb9cd1c9e6d52f5ff5f2`。源码合并和开发迭代 PASS 不等于安装包发布 PASS。
- CI 基础检查：198 项治理、45 项服务端、16 项升级包工具全部通过。两台 Mac 的 Swift 凭据13项、地址配置48条断言通过。本机 CLT 也完成上述两项组件检查；本机没有完整 Xcode，未宣称本机产品 E2E 通过。
- 同机方案已实证：各 Mac 自己运行 App、API、SQLite 和更新服务；API默认 `http://127.0.0.1:49176`，更新源默认 `http://127.0.0.1:49177/appcast.xml`。配置页可保存合法覆盖和恢复默认。004验证非法下载URL、非回环HTTP重定向、坏签名拒绝与有效包安装、自主重启及 `/v1/me` 自动登录。
- 生产库 `database/production/production.db` 供用户使用，首次预置 `admin / 123456` 并强制改密；测试库 `database/test/test.db` 与原生逐例临时库只供回归，造数 SQL 和重置流程见[数据库说明](../database/README.md)。此次测试没有改用户生产库、旧安装包或系统信任。

## 当前任务

用户要求继续内部正式发布，并补齐逐功能详细 test case、梳理2026-09-29与2026-09-30的项目对话和执行复盘。本轮在 `codex/v0.1.0-20260929T074814Z/internal-release` 继续同一个尚未发布版本；先完成用例导航、真实状态同步与内部安装包设计，再执行最终包门禁。

1. 文档用例此前分散在机器矩阵、版本04计划和源码，缺少 docs 中的逐功能入口。已补齐[详细用例总索引](testing/cases/README.md)及12项功能文件，共37例；未来功能如实为计划中，只有TM-001有上述开发原生通过证据。
2. [两日复盘](retrospectives/2026-09-29--2026-09-30-tokenmeter.md)已整理24个案例，基于项目会话、版本记录、Git和CI；已明示部分早期会话只返回摘要/空内容的覆盖限制。
3. 内部最终包必须为生产 bundle，不能包含 `TMTestCredentialsDirectory` 或测试认证路径；从实际 DMG 安装后执行完整原生回归与升级，再由受保护 CI 绑定候选、包摘要、矩阵和证据签发通行证。
4. 生产内部构建、最终DMG安装执行器、父级门禁和自动发布程序已实现，待同一候选在受保护CI执行；用户已确认本版仅支持现有macOS15 arm64/Intel；macOS14暂不承诺。已在远端配置并读回master三项必需检查、管理员不可绕过、禁止强推/删除及release-validation仅master策略。稳定签名私钥只存该环境secret和本机0700私有目录，不进入Git/产物。

本轮提交前检查：259项治理测试、45项服务端测试和16项升级工具检查通过；文档基线86份/615链接及12功能/37用例追踪通过。新的最终包E2E与发布资格仍待CI判定。基础证据见 `.local/ci/internal-governance-final.log`、`internal-server-first.log`、`internal-helper-first.log`、`internal-baseline-final.json`。

## 证据与历史

最新原始 job 日志保存在 `.local/ci/loopback-{arm,intel}-job.log`，逐例报告在 `.local/ci/summaries/36674477502/`，远端合并核对和交接在 `.local/git-sync/loopback-3ad0d7e/`。受信源为上述GitHub运行及其原始工件；本机副本供核查，不签发通行证。

历史公网DNS阻断、Keychain升级提示、不同活跃源准备、xcresult摘要变化及修复证据均保留在[版本执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)，不因新候选通过而改写旧结果。当前 `/Applications/TokenMeter.app` 若仍为旧预览构建100，不代表本轮最终包。
