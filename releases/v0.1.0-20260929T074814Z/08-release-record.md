# v0.1.0-20260929T074814Z — 实际发布记录

按 SOP-018/019/020/022/024 维护。**当前状态：未发布；没有本版 Electron 正式通行证、Tag 或正式 DMG。** 发布目标与恢复条件见[发布预案](05-release-plan.md)，实际测试原件见[07测试结果](07-test-results.md)。

## 当前发布资格（2026-10-01）

| 项目 | 实际状态与依据 |
| --- | --- |
| 分发及验证范围 | 团队内部、本机 macOS 15 Intel；其他系统/架构尚无本版 Electron 最终包验收。DMG、更新包、原始报告与通行证只在本机；Git 保存源码、文档和版本追踪 |
| 固定候选 | 尚未取得干净、已提交的最终候选及与之对应的正式包级门禁；`.local/ci/electron-package-fixes-20261001T0114Z/package-manifest.json`是 dirty 源码构建的未发布开发包，`release_eligible=false` |
| 当前开发包产品证据 | 主精细批次`local-534748ff47cb44229183a6bd878c1674`原始BLOCKED：116条结果105 PASS/0 FAIL/11条辅助占位BLOCKED，95个实际Playwright入口PASS，清理完成。独立辅助`aux-818fe55e1e8940e4a3196b9d03b76563`为11/11 PASS，审计v2为12/12 PASS，六组补充`local-5197628d58ac4136b004b87da438220c`为6/6 PASS。联合复核模型中的78父TC与38变体全PASS，但主raw及Excel的原始产品状态仍为BLOCKED，且开发包没有发布资格 |
| 测试程序 | 67条产品父TC、11条辅助TC、38条参数变体有固定可重复入口。`scripts/local_gate.py`已编排同一最终候选的主批次、辅助、审计、六组补充及独立Excel，复算`final-product-result.json`；`scripts/local_release.py`复核证据和归档副本。固定Playwright注册95/95通过。这是程序准备状态，不代表最终候选已执行 |
| 历史失败 | dev07六组的004 FAIL；首轮完整精细`local-343e54113b0b442383e80f137013014b`及随后新包全量失败原件继续留存，不能由后续开发包结果覆盖，详见07与06记录 |
| 本机正式门禁 | 最终干净候选的安装包、全量E2E、结果Excel和机器校验尚未执行完毕；当前SOP-018修订11的旧文字待SOP管理会话同步。FAIL/BLOCKED不得签发通行证 |
| 通行证、正式DMG和更新源 | 均未发布；`dmg/<release_id>/`仅可提供明确标记`NOT-RELEASED`的开发/候选便捷副本，正式原名包须待机器门禁PASS后归档 |
| Git版本 | 旧Swift实现的[PR#2](https://github.com/lzhe72/TokenMeter/pull/2)已合并至`e011857443b503c2bfafcb9cd1c9e6d52f5ff5f2`，不授予Electron候选发布资格。当前需求分支仍待总控在本地`master`整合、对最终树重验并按远端保护完成同步；本版正式Tag未创建 |
| 用户查看入口 | 根目录[TokenMeter项目总表.xlsx](../../TokenMeter项目总表.xlsx)汇总11个Sheet、109条用例和12条运行批次；详细逐例证据在各批次独立Excel，历史失败与本次复核分别保留，总表回读结果见06执行记录 |

总表的用例状态和批次摘要不替代原始`result.json`、Playwright trace、SQLite、安装包及本机机器门禁。测试AI只能调用已固定程序并分析机器结果，不能临场手填PASS。

## 已存在但不具发布资格的产物

`.local/ci/electron-package-probe-06/`是早期开发包，DMG摘要为`09f0854cefc7584e1cc77e911d92cf1024a826d407e24241bb38cef11d35a529`；其同字节便捷副本在`dmg/v0.1.0-20260929T074814Z/TokenMeter-v0.1.0-20260929T074814Z-DEVELOPMENT-NOT-RELEASED.dmg`。较新的`.local/ci/electron-package-fixes-20261001T0114Z/`仍是 dirty 源码的开发包，上述联合复核只适用于它。两者都不能作为正式下载或更新源。

## 下一步与放行条件

1. SOP管理会话同步SOP-014/018与已实现的主raw占位、辅助映射和机器复算合同；文档/总表与候选源码保持一致。
2. 锁定干净、已提交的候选SHA/tree，按SOP-017制作并验证同一最终DMG；从该包安装App，执行全部TM-001父TC/变体、独立辅助、审计和六组补充场景，保留每份原始证据与独立Excel。
3. 仅当机器从本次原件复算最终所有必测项PASS、摘要/清理/平台/候选一致并签发有效通行证后，才由总控按SOP-019整合及核对远端，再按SOP-020归档正式原名DMG。任一FAIL/BLOCKED保留原件并返回SOP-015。

导航：[本版本流程](README.md) · [全部用例](../../TEST_CASES.md) · [测试结果](07-test-results.md) · [执行记录](06-iteration-record.md)。
