# SOP-013 构建与检查

**修订：** 5　**状态：** baselined　**适用：** all

## 目的与范围

构建候选并运行适当的静态、单元、集成和迁移检查，尽早定位问题。

## 触发条件

实现或依赖变化后、整合 agent 工作后、进入产品 E2E 或正式包验证前。

## 前置条件

SOP-009 环境可用，待测实现及构建入口真实存在；清楚哪些检查属于基础工具、哪些属于产品。

## 输入

候选源码、依赖锁定、测试计划、构建配置和适用数据库。

## 执行步骤

1. 运行 python3 scripts/check_docs.py 与 python3 scripts/quality_gate.py check，核对规范、版本和追踪关系。
2. 当前治理工具自测执行 python3 -m unittest discover -s tests/governance -p 'test_*.py'，保存测试数量、退出码和结果。
3. TM-001 服务端先在隔离 Python 环境安装 `python3 -m pip install --only-binary=:all: -r server/requirements-dev.txt`，再执行 `python3 -m pytest tests/server -q`。依赖安装失败单独记录，不能当成业务红测；不在缺编译器的本机退回源码包安装。
4. 在 macOS 上执行 `python3 scripts/test_device_credentials.py`，用本机 Swift 工具链编译真实 `Auth.swift` 与 Foundation 断言程序 `tests/macos/DeviceCredentialsTests.swift`，检查凭据文件权限、类型、符号链接、origin 隔离和原子替换等边界。Command Line Tools 足以执行此检查，无需 XCTest 或完整 Xcode；非 macOS 或缺 Swift 编译器须记录 BLOCKED。保存命令、退出码与原始结果。该组件检查不代替产品原生 E2E。
   地址配置变化还要执行 `python3 scripts/test_endpoint_configuration.py`，用同一 macOS Command Line Tools 编译真实 `Auth.swift` 和 `tests/macos/EndpointConfigurationTests.swift`，核对 API/更新 URL 校验、内置默认、显式覆盖与恢复默认的组件边界。程序入口已建立不等于检查已运行；保存实际退出码。此检查也不代替第004/006例真实 App UI。
5. 原生构建使用版本计划固定的 Xcode、项目和 scheme，由 SOP-014 runner 调用真实 `xcodebuild build-for-testing`。尚未具备入口或环境的检查记录具体 BLOCKED。构建与检查必须使用同一候选依赖和配置；记录客户端/服务端版本、产物摘要和工具链。
6. 失败立即定位；修复后的候选重新执行受影响检查，再进入完整产品 E2E。治理测试通过只说明治理工具有效。

## 输出

构建物、摘要、基础检查与产品检查报告，或精确的环境/入口缺失记录。

## 成功与失败判据

所有适用检查确实执行且通过、产物可追踪才可进入 E2E；零测试、非零退出码或构建缺失均不能放行。此步骤本身不授予发布资格。

## 异常恢复

保留首个失败和完整相关日志，区分构建/测试/环境问题后修复；不加 continue-on-error 或隐藏失败输出。

## 证据位置

机器检查报告、构建摘要、实际命令与退出码；06-iteration-record.md 简述结论和下一步。

## 下一步

执行 [SOP-014 自动 E2E](SOP-014-e2e.md)；最终发布包由 [SOP-017](SOP-017-package-validation.md) 验证。
