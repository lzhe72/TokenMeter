# v0.1.0-20260929T074814Z — 实际发布记录

按 SOP-018/019/020/022/024 维护。**当前状态：未发布；独立候选 `d2db551` 本机门禁 PASS 并有机器通行证，最终 `master` 整合树尚未重验、原件归档与正式分发未完成，没有正式 Tag 或原名 DMG。** 发布目标与恢复条件见[发布预案](05-release-plan.md)，实际测试原件见[07测试结果](07-test-results.md)。

## 当前发布资格（2026-10-01）

| 项目 | 实际状态与依据 |
| --- | --- |
| 分发及验证范围 | 团队内部、本机 macOS 15 Intel；其他系统/架构尚无本版 Electron 最终包验收。DMG、更新包、原始报告与通行证只在本机；Git 保存源码、文档和版本追踪 |
| 固定候选 | 独立 TM-001 分支候选 `d2db551` 的门禁 PASS 只属历史；本地 `master` 固定候选 `c2911bc`、tree `d4555b2` 的首次最终包门禁已经 FAIL。旧 dirty 开发包及独立候选均不能替代新整合树验收 |
| 当前开发包产品证据 | 主精细批次`local-534748ff47cb44229183a6bd878c1674`原始BLOCKED：116条结果105 PASS/0 FAIL/11条辅助占位BLOCKED，95个实际Playwright入口PASS，清理完成。独立辅助`aux-818fe55e1e8940e4a3196b9d03b76563`为11/11 PASS，审计v2为12/12 PASS，六组补充`local-5197628d58ac4136b004b87da438220c`为6/6 PASS。联合复核模型中的78父TC与38变体全PASS，但主raw及Excel的原始产品状态仍为BLOCKED，且开发包没有发布资格 |
| 测试程序 | 67条产品父TC、11条辅助TC、38条参数变体有固定可重复入口。`scripts/local_gate.py`已在本地master `c2911bc` 上运行并因精细批次 FAIL 停止；后续辅助、审计、六组补充与正式归档未由这次门禁形成通过。`scripts/local_release.py verify/archive`要求固定里程碑SHA/tree与同源包、通行证；本次没有可归档原件 |
| 历史失败 | dev07六组的004 FAIL；首轮完整精细`local-343e54113b0b442383e80f137013014b`及随后新包全量失败原件继续留存，不能由后续开发包结果覆盖，详见07与06记录 |
| 本机正式门禁 | 独立 `d2db551` 门禁原件仍为历史 PASS；本地 `master` `c2911bc` 首次原件 `.local/gates/tm001-master-gate-c2911bc-20261001T113036Z/gate.json` 为 FAIL、`release_eligible=false`，原始116项91 PASS/14 FAIL/11 BLOCKED。UPDATE-05 父项及13变体缺签名输入；须修复并对新候选完整重跑 |
| 通行证、正式DMG和更新源 | 独立候选机器通行证已生成，SHA-256 `193bf39ca6bd2aed5a802f817ba5aa7bcfdaeeb442e272f1d843e381c941de53`；被测原 DMG SHA-256 `acc86a9f04ed19fe91f1b63481988d615f5d81680602eed1305b3896bb284492`。根 `dmg/<release_id>/` 目前仅有同摘要的 `CANDIDATE-NOT-RELEASED` 便捷副本；正式原名包、归档和稳定更新源尚未发布 |
| Git版本 | 旧Swift实现的[PR#2](https://github.com/lzhe72/TokenMeter/pull/2)仅属历史。本地`master`里程碑 `c2911bc` 的首次最终包门禁 FAIL；后续须修复并固定新SHA/tree重跑，SOP-018 PASS 后才可SOP-020归档。全部目标版本稳定后再统一远端源码登记和Tag；本版正式Tag未创建 |
| 用户查看入口 | 根目录[TokenMeter项目总表.xlsx](../../TokenMeter项目总表.xlsx)现汇总11个Sheet、164条父用例与35个变体（199行）及13条TM-001运行批次；最新 `c2911bc` FAIL 批次有独立结果 Excel，按被测SHA登记。TM-002设计已基线、TM-003仍为草稿，两者未执行产品E2E；0.1当前仍未发布 |

总表的用例状态和批次摘要不替代原始`result.json`、Playwright trace、SQLite、安装包及本机机器门禁。测试AI只能调用已固定程序并分析机器结果，不能临场手填PASS。

## 已存在但不具发布资格的产物

`.local/ci/electron-package-probe-06/`是早期开发包，DMG摘要为`09f0854cefc7584e1cc77e911d92cf1024a826d407e24241bb38cef11d35a529`；其同字节便捷副本在`dmg/v0.1.0-20260929T074814Z/TokenMeter-v0.1.0-20260929T074814Z-DEVELOPMENT-NOT-RELEASED.dmg`。较新的`.local/ci/electron-package-fixes-20261001T0114Z/`仍是 dirty 源码的开发包，上述联合复核只适用于它。两者都不能作为正式下载或更新源。

## 下一步与放行条件

1. TM-001 开发会话按 SOP-015 稳定复现 `c2911bc` 的签名输入缺失，修实现或测试前置并保存定向失败与修复证据；保留此次 FAIL 原件。
2. 总控整合修复后固定新的本地 `master` SHA/tree，按 SOP-017 重建同一最终 DMG，从该包安装 App 并完整执行全部 TM-001 父 TC/变体、独立辅助、审计和六组补充场景，生成独立 Excel 与机器门禁结果。
3. 只有新候选 SOP-018 PASS 后，才由 SOP-020 核对原包、通行证和里程碑并归档正式稳定0.1 DMG，供 TM-002 真实升级。全部目标版本稳定后由总控按 SOP-019 统一远端登记、逐版读回来源与Tag；任一 FAIL/BLOCKED 继续保留原件并回修。

导航：[本版本流程](README.md) · [全部用例](../../TEST_CASES.md) · [测试结果](07-test-results.md) · [执行记录](06-iteration-record.md)。
