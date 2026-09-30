# SOP-014 自动 E2E

**修订：** 13　**状态：** baselined　**适用：** all

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
5. TM-001 入口由 `scripts/e2e.py` 调用 `scripts/native_e2e.py`：检查完整 Xcode 和已登录桌面，逐例建立隔离 SQLite，启动真实服务，构建候选，并用 `xcodebuild test-without-building` 执行清单的 `native_test`。每例保存 `native.xcresult`、原生命令日志、候选包和 fixture 摘要；当前六例都需要执行。001–003使用临时回归账号；005在独立临时根执行生产首建程序，以真实 App 验证 `admin` 初始登录、改密和库隔离，绝不访问用户实际生产库。006在默认端口49176及第二隔离端口启动两套真实服务/SQLite，以原生 UI 验证默认值、地址切换、重启持久化及会话隔离；若端口被用户服务占用或双服务执行器缺失则 BLOCKED。第004例直接在本例隔离目录创建并保有一组 `SigningIdentity` 与 `UpdateSource`，核对隔离CI临时签名、更新源与本例专用凭据目录前提：同一 Quick Tunnel 域名在共享的最多 180 秒窗口内，先核对两个公共 HTTPS DNS 源的 A 记录，再用 Mac 正常系统 DNS/TLS 请求核对来源与本次 origin 证书（`security verify-cert`）；公共 DNS 查询不替代系统检查。004 的准备 READY 仅对该仍活跃的实例有效，不能借用独立 `native_environment.py` 已销毁资源的 READY。首次系统请求出现DNS退出6时按009只读采集有界诊断，保留原始失败、域名及清理证据；诊断不能重置准备时钟或将第004例改为通过。任一准备阶段 BLOCKED 时不得执行产品升级步骤，也不得将环境 READY 计作004通过；不重启隧道、更换随机域名或重试业务以取绿。准备成功后，保持同一 `SigningIdentity`、`UpdateSource`、域名、CA 和 Keychain 活跃至原生测试及更新请求核对完成，随后在本例 `finally` 中统一清理并分别记录主结果和清理错误。实际用例必须核对候选与高版本包使用同一隔离签名身份和 Info.plist 凭据目录、拒绝无效包、有效包升级重启，并通过原文件 token 调用真实 `/v1/me` 无交互恢复；若读取生产凭据、旧 Keychain，或仅因改断言等待而变绿，仍为 FAIL。关闭自动登录时重启必须显示登录页，过期/撤销/离线不得展示已登录身份。其余五例可按自身依赖先执行并归档；004本例环境准备失败仍阻断全体六例门禁，不得缩小应执行集合或重试产品用例取绿。独立 `native_environment.py` 与手动 `environment_probe_only` 继续只作零产品用例的诊断，不能代替同一候选的004执行。
6. 第004例的 `environment.json` 是不可变准备快照：`snapshot_stage=preparation`、`cleanup_owner=parent_run_result`；此时资源仍活跃，`cleanup_completed=false`，最终清理结果以父运行报告为准。父验证器必须重新读取本例环境文件并核对受限相对路径、SHA256、候选提交、干净状态、READY、零产品用例、非发布资格与快照标记；缺失、篡改或混用候选均拒绝。该检查不替代原始原生结果。父门禁为本次子进程分配唯一 nonce；子进程返回后，父门禁重新用 `xcresulttool` 解析原始结果，对照提交、清单摘要、原生测试 ID、数量、零失败/跳过及清理结果。只返回退出0或写 PASS JSON 均不能放行。每个 CI 平台分别出结果，开发矩阵全部通过才可验收。
7. 缺本机 Xcode 时记录本机无法执行，使用版本计划指定的 GitHub 托管 `macos-15` 与 `macos-15-intel` 执行 `.github/workflows/quality.yml`；本机安装 Xcode 不是远端迭代 E2E 的前置条件。每个平台在自身机器上构建并运行真实 App、两套所需隔离服务、数据库和原生 UI，用原始 `xcresult` 核对同一候选及完整六例；远端无有效结果仍为 BLOCKED。`workflow_dispatch` 的 `environment_probe_only=true` 只产生另名 `environment-diagnostic` 检查与环境工件，执行零产品用例；即使探针 READY，也不能用于本步骤 PASS、PR 合并或正式发布。PR/push 以及默认 `workflow_dispatch` 仍须运行完整迭代门禁。远端 PASS 不倒填为本机 PASS。隔离自签开发迭代不代表任一分发 profile 可用；内部包级门禁仍须最终 DMG 安装升级、完整支持矩阵与受保护证据，公开 profile 另需 Developer ID 签名/公证、当前版本指定的生产数据库及受保护流程；v0.1.0 指定服务端 SQLite，MySQL 迁移属于后续独立版本。迭代 PASS 不授予发布资格。
8. 保存失败证据；修复后新建运行完整回归，不通过重复重试覆盖失败。

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
