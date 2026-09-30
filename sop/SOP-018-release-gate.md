# SOP-018 发布门禁

**修订：** 7　**状态：** baselined　**适用：** all

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
2. internal执行[内部发布设计](../docs/releases/01-internal-v0.1.0.md)的受保护流程。在master全部必需检查通过后执行 `gh workflow run internal-release.yml --ref master -f candidate_sha=<已核实master完整SHA>`。preflight读取真实分支保护、环境master策略、同SHA必需检查并分配nonce；构建一次最终生产DMG；两平台从同一DMG安装各执行六例；父级 `scripts/internal_release_gate.py` 对照同次run/attempt与清单重解析全部原始xcresult，再签发通行证；发布job重新读回远端前提并上传原包。具体CLI参数固定在工作流，禁止手改报告或以本机输出替换CI产物。对于public，继续用默认分支 `.github/workflows/release-candidate.yml` 的完整candidate_sha，执行 `quality_gate.py release`，其公开签名/公证前提独立保留。两条路径都要求candidate_sha等于本次dispatch GITHUB_SHA和实际HEAD，正式Tag必须尚不存在。
3. 真实执行器必须核对本次运行身份、原生报告来源与摘要、场景集合相等、零失败/跳过、产物签名及有效时限。
4. 仅受保护 CI 完整 PASS 后生成 <release_id>.passport.json，绑定 distribution_profile、提交、构建物和执行证据，保存在候选源码之外。
5. 候选先通过SOP-013治理/服务端/工具检查及两平台完整开发回归，再进入上述最终包链路。v0.1.0使用SQLite，真实生产库只做非破坏性就绪与备份检查，隔离同构副本验证初始化、恢复和真实业务；MySQL留迁移版本。内部最终包六例、两架构、清理、恢复、受保护身份或报告缺任一项即FAIL/BLOCKED，不创建Tag或通行证。公开版缺Developer ID/公证保持BLOCKED，不改变内部profile的已定边界。
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
