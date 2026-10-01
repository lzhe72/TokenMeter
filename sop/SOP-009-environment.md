# SOP-009 环境准备

**修订：** 18　**状态：** baselined　**适用：** all

## 目的与范围

准备本机Electron开发、真实服务和Playwright桌面执行环境。

## 触发条件

首次建立环境、依赖或工具链变化、运行缺条件。

## 前置条件

SOP-008文档基线与Electron本机设计就绪。

## 输入

本轮设计、Node/npm锁文件、Python锁定依赖、实际Mac和隔离位置。

## 执行步骤

1. 读取系统/架构、Node/npm和CLT版本，检查已登录桌面；完整Xcode不是Electron路线前提。Playwright锁定兼容Electron版本，缺运行时如实BLOCKED。
2. 按本机设计准备apps/desktop真实工程；程序未就绪时只做源码/依赖准备，不声称产品可运行。Python使用隔离环境与requirements-dev.txt，npm使用锁文件安装，不全局升级工具。Electron44不再通过postinstall下载运行时；apps/desktop执行npm ci后必须npm run runtime:install，使用本项目.local独立npm/Electron缓存，不修改用户缓存权限。
3. 先只读核对现有App、生产库、端口和profile。本机49176及旧/Applications应用属于用户；新测试使用自有安装父目录、动态回环服务、0700 profile，不能接管旧服务。
4. 生产App通用--user-data-dir在ready前显式设置userData/sessionData；同级0600 runtime侧文件维持更新重启归属，拒绝坏路径/符号链接/其他用户文件。缺隔离条件不得启动App。
5. 建立真实App启动与Playwright最小探针；仅验证环境，零业务用例不能算E2E PASS。记录实际版本、命令、退出码。需要系统授权时走正常界面，不修改TCC。
6. 默认本机执行。用户明确要求多环境时才启用对应Actions和矩阵；旧云端通过证据不覆盖新Electron候选。

## 输出

环境清单、工程骨架、探针和隔离目录，或明确缺项。

## 成功与失败判据

真实启动和执行器探针通过才可进行依赖它的业务测试；文件存在不能替代运行。

## 异常恢复

保留原始失败，修复依赖或隔离；不以安装完整Xcode作为默认补救。

## 证据位置

本轮.local/ci环境结果及版本06。

## 下一步

010→011。

具体合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。旧云端/Swift路径仅用于历史查询，不能覆盖用户本机优先规则。
