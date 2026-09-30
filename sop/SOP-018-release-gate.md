# SOP-018 发布门禁

**修订：** 6　**状态：** baselined　**适用：** all

## 目的与范围

以真实原生结果和可信构建来源自动判断候选是否可发布，只有通过后签发版本通行证。

## 触发条件

最终候选完成产品回归与安装包验证，准备按 `distribution_profile=internal/public` 正式分发。

## 前置条件

确定且干净的完整候选 SHA、明确的 distribution_profile、SOP-014/017 所需运行环境、profile 对应最终包与完整证据，以及受保护 CI、远端 required checks 和凭据隔离已真实配置。正式 Tag 不得作为启动本步骤的前置条件。

## 输入

release_id、distribution_profile、commit、客户端/服务端摘要、场景/fixture/平台清单、原生报告、签名/公证和版本档案。

## 执行步骤

1. 核对版本范围、distribution_profile、目标及所有此前已交付功能、平台矩阵、Changelog、文档/数据/测试与同一候选一致；internal 与 public 的包和结果不能互换。
2. 当前 `.github/workflows/release-candidate.yml` 和 `scripts/quality_gate.py release` 只定义公开 Developer ID/公证候选合同；本轮内部包级门禁、最终内部 DMG 的原生安装升级矩阵及机器通行证签发程序尚未实现，`distribution_profile=internal` 必须返回 BLOCKED，不能把当前 release 命令、预览包或迭代 PASS 改名为内部 PASS。内部程序完成后，仍须在受保护默认分支固定 SHA、profile 和最终包摘要，并由机器对照 SOP-017 的所有证据自动判定。对于 `distribution_profile=public`，正式 Tag 创建前，从受信默认分支手动触发 `.github/workflows/release-candidate.yml`，必填完整 `candidate_sha`；它必须等于本次默认分支 dispatch 的 `GITHUB_SHA`，也就是实际检出的主分支 tip，不能指定其他分支或旧提交。受保护 `release-validation` 环境的任务检出并核对该 SHA，执行 `python3 scripts/quality_gate.py release`，绑定同一最终签名产物。常规 quality 工作流执行 iteration，不能以 Tag 触发代替候选门禁。读取完整过程、状态与退出码；前置 traceability_only 的 PASS 不能代替最终结论。
3. 真实执行器必须核对本次运行身份、原生报告来源与摘要、场景集合相等、零失败/跳过、产物签名及有效时限。
4. 仅受保护 CI 完整 PASS 后生成 <release_id>.passport.json，绑定 distribution_profile、提交、构建物和执行证据，保存在候选源码之外。
5. 当前候选入口固定 SHA、Python/Xcode 和依赖，先执行 SOP-013 的治理、服务端及升级工具检查，再运行真实原生回归。服务端数据库按本版发布预案验证；v0.1.0使用SQLite，真实生产库只做非破坏性就绪与备份检查，在隔离同构副本证明初始化、恢复和真实业务链路，MySQL兼容性留待迁移版本。当前 internal 缺最终内部包程序、包级 E2E 与受保护通行证；public 另缺最终签名/公证包、全部支持平台及受保护签发，因此两种正式分发均 BLOCKED；FAIL/BLOCKED不创建Tag或通行证。即使替换为空成功脚本也不得放行，不接受任意外部通过JSON。受保护环境须在远端实际配置后才成立。
6. 保存失败与阻塞记录；任何代码、测试、数据、构建或发布配置变化均使旧候选证据失效，重新验证。

## 输出

经可信证据校验的 PASS 通行证，或明确 FAIL/BLOCKED 运行记录。

## 成功与失败判据

只有对应 distribution_profile 的最终产品门禁 PASS 才具备该 profile 的发布资格；缺平台/权限/报告、伪造或过期证据、空用例、跳过、未解释不稳定结果一律不通过。

## 异常恢复

保存失败来源，返回对应环境、测试、实现或签名步骤修复；不删除阻断、不手写/拷贝通行证、不调整状态替代实际检查。

## 证据位置

受保护 CI 原始产物、机器门禁报告及通行证；本机 .local 报告仅用于诊断，不能冒充正式发布证据。

## 下一步

有效 PASS 后进入 [SOP-019 Git 发布](SOP-019-git-release.md)；否则回对应修复步骤。
