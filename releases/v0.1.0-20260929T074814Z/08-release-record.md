# v0.1.0-20260929T074814Z — 实际发布记录

按 SOP-018/019/020/022/024 维护。**当前状态：未发布；独立候选 `d2db551` 本机门禁 PASS 并有机器通行证，最终 `master` 整合树尚未重验、原件归档与正式分发未完成，没有正式 Tag 或原名 DMG。** 发布目标与恢复条件见[发布预案](05-release-plan.md)，实际测试原件见[07测试结果](07-test-results.md)。

## 当前发布资格（2026-10-01）

| 项目 | 实际状态与依据 |
| --- | --- |
| 分发及验证范围 | 团队内部、本机 macOS 15 Intel；其他系统/架构尚无本版 Electron 最终包验收。DMG、更新包、原始报告与通行证只在本机；Git 保存源码、文档和版本追踪 |
| 固定候选 | 独立 TM-001 分支候选 `d2db551`、tree `3854696e6212aa68aeccfdc720add187a4f92759` 已用同一原 DMG 完成本机门禁；最终本地 `master` 整合候选尚未锁定与重验。旧 `.local/ci/electron-package-fixes-20261001T0114Z/` 是 dirty 开发包，不继承此次 PASS |
| 当前开发包产品证据 | 主精细批次`local-534748ff47cb44229183a6bd878c1674`原始BLOCKED：116条结果105 PASS/0 FAIL/11条辅助占位BLOCKED，95个实际Playwright入口PASS，清理完成。独立辅助`aux-818fe55e1e8940e4a3196b9d03b76563`为11/11 PASS，审计v2为12/12 PASS，六组补充`local-5197628d58ac4136b004b87da438220c`为6/6 PASS。联合复核模型中的78父TC与38变体全PASS，但主raw及Excel的原始产品状态仍为BLOCKED，且开发包没有发布资格 |
| 测试程序 | 67条产品父TC、11条辅助TC、38条参数变体有固定可重复入口。`scripts/local_gate.py`已编排同一最终候选的主批次、辅助、审计、六组补充及独立Excel，复算`final-product-result.json`；`scripts/local_release.py`复核证据和归档副本。固定Playwright注册95/95通过。这是程序准备状态，不代表最终候选已执行 |
| 历史失败 | dev07六组的004 FAIL；首轮完整精细`local-343e54113b0b442383e80f137013014b`及随后新包全量失败原件继续留存，不能由后续开发包结果覆盖，详见07与06记录 |
| 本机正式门禁 | `.local/gates/tm001-final-gate-d2db551-20261001T0904Z/gate.json` 对独立候选为 PASS、`release_eligible=true`；机器最终结果 78 父 TC、38 变体全 PASS，原始 11 辅助占位仍为 BLOCKED，另有真实辅助 11/11、审计 12/12、六组 6/6 PASS。最终 `master` 整合树必须重新门禁 |
| 通行证、正式DMG和更新源 | 独立候选机器通行证已生成，SHA-256 `193bf39ca6bd2aed5a802f817ba5aa7bcfdaeeb442e272f1d843e381c941de53`；被测原 DMG SHA-256 `acc86a9f04ed19fe91f1b63481988d615f5d81680602eed1305b3896bb284492`。根 `dmg/<release_id>/` 目前仅有同摘要的 `CANDIDATE-NOT-RELEASED` 便捷副本；正式原名包、归档和稳定更新源尚未发布 |
| Git版本 | 旧Swift实现的[PR#2](https://github.com/lzhe72/TokenMeter/pull/2)已合并至`e011857443b503c2bfafcb9cd1c9e6d52f5ff5f2`，不授予Electron候选发布资格。当前需求分支仍待总控在本地`master`整合、对最终树重验并按远端保护完成同步；本版正式Tag未创建 |
| 用户查看入口 | 根目录[TokenMeter项目总表.xlsx](../../TokenMeter项目总表.xlsx)现汇总11个Sheet、109条用例和12条历史运行批次；`d2db551` 的独立逐例 Excel 已生成并核对，门禁/通行证/原件归档完成后才在后续总表文档提交登记本批次与被测SHA；当前版本 Sheet 已注明独立门禁通过且未发布 |

总表的用例状态和批次摘要不替代原始`result.json`、Playwright trace、SQLite、安装包及本机机器门禁。测试AI只能调用已固定程序并分析机器结果，不能临场手填PASS。

## 已存在但不具发布资格的产物

`.local/ci/electron-package-probe-06/`是早期开发包，DMG摘要为`09f0854cefc7584e1cc77e911d92cf1024a826d407e24241bb38cef11d35a529`；其同字节便捷副本在`dmg/v0.1.0-20260929T074814Z/TokenMeter-v0.1.0-20260929T074814Z-DEVELOPMENT-NOT-RELEASED.dmg`。较新的`.local/ci/electron-package-fixes-20261001T0114Z/`仍是 dirty 源码的开发包，上述联合复核只适用于它。两者都不能作为正式下载或更新源。

## 下一步与放行条件

1. 以已合入的SOP-014/018规范核对主raw占位、辅助映射和机器复算程序，完成当前整合树的治理回归；文档/总表与候选源码保持一致。
2. 对总控整合后的新 `master` SHA/tree 按 SOP-017 重建并验证同一最终 DMG；从该包安装 App，执行全部 TM-001 父 TC/变体、独立辅助、审计和六组补充场景，保留新候选的每份原始证据与独立 Excel。
3. 独立 `d2db551` 候选已完成上述测试，后续由总控把最新 SOP、文档和产品分支整合为**新的本地 `master` 候选**，对其重新执行适用完整 E2E/包门禁并保存原始通行证；再按 SOP-019 核对远端树、按 SOP-020 归档正式原名 DMG。任一 FAIL/BLOCKED 保留原件并返回 SOP-015。

导航：[本版本流程](README.md) · [全部用例](../../TEST_CASES.md) · [测试结果](07-test-results.md) · [执行记录](06-iteration-record.md)。
