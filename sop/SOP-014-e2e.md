# SOP-014 自动 E2E

**修订：** 1　**状态：** baselined　**适用：** all

## 目的与范围

对每次产品迭代、补丁和测试版自动执行目标及历史功能的真实端到端回归。

## 触发条件

任何产品候选需要验收，或修复后需要确认目标及既有能力仍正确。

## 前置条件

SOP-009–013 就绪；具备实际 App、服务、数据库、原生 UI runner、数据与完整场景集合。当前缺这些条件时保持 BLOCKED。

## 输入

候选提交/产物、release_id、场景与 fixture 清单、支持矩阵和 [执行规范](../docs/testing/execution.md)。

## 执行步骤

1. 固定应执行集合和场景/fixture 摘要，创建唯一 run_id 与隔离环境。
2. 运行 python3 scripts/quality_gate.py iteration；它先检查元数据再调用产品入口，不接收任意外部 PASS JSON。
3. 真实 runner 必须自动构建/初始化账号、驱动原生 UI 和系统交互、贯通真实服务/数据库并断言用户结果与关键持久化。
4. 收集原生测试包、服务日志、截图附件、命令/退出码及实际用例集合；逐项比较预期集合、平台和实际结果。
5. 当前入口只写 .local/e2e/<run-id>/result.json 并返回 BLOCKED；读取 executed_cases/runner_implemented，不能将报告存在视作测试执行。
6. 保存失败证据；修复后新建运行完整回归，不通过重复重试覆盖失败。

## 输出

真实原生结果和机器 PASS/FAIL/BLOCKED，或当前诚实的阻断报告。

## 成功与失败判据

只有完整目标及历史回归全部执行、零失败/跳过/xfail、平台齐全、证据与候选一致才可能 PASS；缺环境/报告/执行器为 BLOCKED，断言错误为 FAIL。

## 异常恢复

按原始数据复现并由 SOP-015 修复；环境缺失返回 SOP-009。不稳定结果查明原因前不得隔离用例或人工放行。

## 证据位置

本次 .local/e2e/<run-id>/result.json 及实际原生附件；对外发布证据由受保护 CI 归档并校验来源。

## 下一步

失败执行 [SOP-015](SOP-015-bugfix.md)；通过且需发布进入 [SOP-017](SOP-017-package-validation.md) 和 [SOP-018](SOP-018-release-gate.md)。
