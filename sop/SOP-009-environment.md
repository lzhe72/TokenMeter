# SOP-009 环境准备

**修订：** 20　**状态：** baselined　**适用：** all

## 目的与范围

准备本机Electron开发、真实服务和Playwright桌面执行环境。

## 触发条件

首次建立环境、依赖或工具链变化、运行缺条件。

## 前置条件

SOP-008文档基线与Electron本机设计就绪。

## 输入

本轮设计、Node/npm锁文件、Python锁定依赖、实际Mac和隔离位置；需要TM001 UPDATE-05受控签名负例时另输入最终包清单、原更新ZIP及显式的本机私有签名目录绝对路径。远端Git源码保存另输入实际Git可执行文件路径/版本与远端地址。

## 执行步骤

1. 读取系统/架构、Node/npm和CLT版本，检查已登录桌面；完整Xcode不是Electron路线前提。Playwright锁定兼容Electron版本，缺运行时如实BLOCKED。需要远端源码检查点时另运行`command -v git`、`git --version`，并核对可用的`/usr/bin/git --version`，记录本次实际使用的绝对Git可执行文件与版本；同一主机不同Git实现的网络结果不能互相冒充成功。
2. 按本机设计准备apps/desktop真实工程；程序未就绪时只做源码/依赖准备，不声称产品可运行。Python使用隔离环境与requirements-dev.txt，npm使用锁文件安装，不全局升级工具。Electron44不再通过postinstall下载运行时；apps/desktop执行npm ci后必须npm run runtime:install，使用本项目.local独立npm/Electron缓存，不修改用户缓存权限。
3. 先只读核对现有App、生产库、端口和profile。本机49176及旧/Applications应用属于用户；新测试使用自有安装父目录、动态回环服务、0700 profile，不能接管旧服务。
4. 生产App通用--user-data-dir在ready前显式设置userData/sessionData；同级0600 runtime侧文件维持更新重启归属，拒绝坏路径/符号链接/其他用户文件。缺隔离条件不得启动App。
5. TM002/003/004 若以 macOS `safeStorage` 保存来源 locator，先将 Keychain 视为独立于 `--user-data-dir` 的系统资源。首次调用 `safeStorage` 前，核对未改动的最终 DMG、签名、实际测试 App 名称及密钥提供者，确定测试 item 的 service/account（或异步提供者的等效身份）与正式 App 不同；只读证明目标测试身份当前不存在，不查询正式 item 的值。Electron 44.5.1 源码中 `PostCreateMainMessageLoop()` 按 Browser Name 设置 `KeychainPassword` service/account 仅是设计依据，**不证明异步提供者或最终包**采用同一身份。须用隔离的 macOS 测试账号或经证明独立的 Keychain 命名空间对同一最终 DMG 做原生探针，核对实际创建 item 身份与签名访问边界，再允许本机测试；仅改 profile 或运行时推测 App 名称不足以放行。无法在触碰用户现有凭据前证明身份分离时，相关 E2E 为 BLOCKED，其他不依赖步骤可继续。探针记录包摘要、平台、实际身份、操作及退出码，不保存密钥值。
6. 需要TM001精细UPDATE-05受控签名负例时，正式运行前由固定程序接收显式`--key-dir <绝对受限目录>`，不从当前worktree的`.local/internal-release-keys`猜测路径，也不复制或新造一套密钥冒充原候选身份。先核对目录为执行uid拥有、非符号链接且权限0700，祖先路径无可替换该目录的危险符号链接/非受控写权限；`seed`、`codesign.p12`、`password`须为同uid拥有、非符号链接且无组/其他读取权限的文件。私有材料留在本机受限目录，不入Git、包、报告或普通fixture。目录缺失、权限/归属不安全或无法证明属于本候选时，依赖它的用例在App启动前BLOCKED；其他不依赖用例继续。签名身份与本次包的密码学绑定按SOP-010核对，环境预检本身不算产品PASS。该参数和校验程序未进入最终候选前，相关正式用例继续BLOCKED。
7. 建立真实App启动与Playwright最小探针；仅验证环境，零业务用例不能算E2E PASS。记录实际版本、命令、退出码。需要系统授权时走正常界面，不修改TCC。
8. 默认本机执行。用户明确要求多环境时才启用对应Actions和矩阵；旧云端通过证据不覆盖新Electron候选。

## 输出

环境清单、工程骨架、探针和隔离目录；适用时另有私有签名输入归属/权限预检与Git客户端版本记录，或明确缺项。

## 成功与失败判据

真实启动和执行器探针通过才可进行依赖它的业务测试；UPDATE-05另须SOP-010证明显式私有输入与本次原更新包同一身份，文件存在不能替代密码学核验。Git客户端版本记录不表示远端推送成功，须按SOP-019读回。

## 异常恢复

保留原始失败，修复依赖或隔离；不以安装完整Xcode作为默认补救。跨worktree缺私有目录不能更改原失败结论或从别处临时借用未经核验的密钥。

## 证据位置

本轮.local/ci环境结果及版本06。

## 下一步

010→011。

具体合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。旧云端/Swift路径仅用于历史查询，不能覆盖用户本机优先规则。
