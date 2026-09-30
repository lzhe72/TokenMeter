# SOP-014 自动 E2E

**修订：** 16　**状态：** baselined　**适用：** all

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
5. TM-001 入口由 `scripts/e2e.py` 调用 `scripts/native_e2e.py`：在现有两平台 CI 检查完整 Xcode 和已登录桌面，逐例建立隔离 SQLite，启动真实服务，构建候选，并用 `xcodebuild test-without-building` 执行清单的 `native_test`。每例保存 `native.xcresult`、原生命令日志、候选包和 fixture 摘要；当前六例都需要执行。001–003使用临时回归账号；005在独立临时根验证生产首建程序，但绝不访问用户实际生产库；006在执行 App 的 Mac 上独占 API 默认端口49176，再由同机第二隔离服务验证可配置 API 地址与会话隔离。

   004 的真实 App 与更新服务必须在同一台 Mac：先独占该机默认更新端口49177，核对 App 设置管理页显示 `http://127.0.0.1:49177/appcast.xml`；第006例另在配置页保存合法合成更新地址、重启再读、恢复默认以删除显式覆盖，并拒绝非法 URL；该场景不请求合成地址，004只使用固定49177默认源升级，公钥不随 URL 改变。该页保留登录页 `auth.server`，配置项的稳定 UI ID 见本版设计；已登录或待撤销会话时不能改 API，更新执行时不能改 feed。URL 验证拒绝 userinfo、query、fragment、空host、非法端口及非回环 HTTP；允许合规非回环 HTTPS，但本轮 fixture 不连接公网。对选中的 appcast 下载地址与重定向执行同一安全边界负测，不能用关闭 ATS 取绿。

   在本例隔离根只创建一组活跃签名身份与 `UpdateSource`，候选/高版本使用同一专用凭据目录与 EdDSA 公钥；测试私钥只在隔离 fixture 内。准备时先用 `/healthz` 的一次性 source nonce 验证本次回环服务的状态、来源及进程归属；发布fixture后由真实App及请求核验程序验证 `/appcast.xml` 与包响应，保持同一源至真实 App 无效签名拒绝、有效包安装重启、构建号变化、更新请求校验与 `/v1/me` 无交互恢复完成，然后统一 `finally` 清理。在单一49177源上，004先经鉴权 `control/forbidden` 发布 `http://example.invalid/update.zip` enclosure，App选中包URL校验须以 `update_source_rejected` 在传输前拒绝且仍为build100；再经 `control/redirect` 发布本机 `/redirect.zip`，其302指向该非回环HTTP URL，必须由ATS返回 `NSURLErrorDomain -1022`（`update_transport_rejected`）且仍为build100，DNS失败不算命中；随后原 `control/invalid` 恢复完整坏签名包并确认拒绝/build100，最后原 `control/valid` 真实升级至build101并经 `/v1/me` 验证。三条负测控制URL由runner注入 `TM_TEST_UPDATE_{FORBIDDEN,REDIRECT,INVALID}_CONTROL_URL`，控制鉴权与签名key不变。完整004仍是一个原生用例，600秒上限不延长；任一阶段未执行或错误类型不符即不能PASS。准备快照 READY 只属于同一候选、run、进程和端口，不算产品004 PASS。端口被占或源不明时 BLOCKED；失败时不跳过安装、不自动重试产品用例、不改签名或结果判据。不得访问用户 `/Applications/TokenMeter.app`、生产数据库或凭据。
6. 第004例的 `environment.json` 是不可变准备快照：`snapshot_stage=preparation`、`cleanup_owner=parent_run_result`；此时资源仍活跃，`cleanup_completed=false`，最终清理结果以父运行报告为准。父验证器必须重新读取本例环境文件并核对受限相对路径、SHA256、候选提交、干净状态、READY、零产品用例、非发布资格与快照标记；缺失、篡改或混用候选均拒绝。该检查不替代原始原生结果。父门禁为本次子进程分配唯一 nonce；子进程须先完成本例所有 `xcresulttool` 解析与附件导出，随后计算完整 `native.xcresult` bundle 摘要并返回；父门禁在子进程返回后先逐文件核算整个 bundle，再重新用 `xcresulttool` 解析原始结果，对照提交、清单摘要、原生测试 ID、数量、零失败/跳过及清理结果；解析完成后对同一 bundle 再次逐文件核算并与子进程摘要比较。两次核算均不得排除 SQLite 文件，任一次不符即 FAIL。治理负测须使父级解析过程修改 bundle 并验证拒绝，不能只覆盖解析前改动。只返回退出0或写 PASS JSON 均不能放行。每个 CI 平台分别出结果，开发矩阵全部通过才可验收。
7. 本机缺 Xcode 时记录本机 XCUITest 无法执行；现有迭代门禁使用版本计划指定的 GitHub 托管 `macos-15` 与 `macos-15-intel`，每台 runner 都在自己机器上运行 App、API、SQLite 和回环更新源，分别执行完整六例并用原始 `xcresult` 核对同一候选。两台 CI 的 `127.0.0.1` 均不指向用户此 Mac。若用户此 Mac 另做体验部署，先核对旧安装包与新候选的来源、版本、签名、服务和数据库；本机只有 Command Line Tools、AX 权限未授且无本机自动执行器时，不将其记录为已通过 E2E，也不因此抹去有效 CI 结果。独立 `environment_probe_only` 若继续存在，只能产生零产品用例的诊断，不得用于004、PR合并或发布；其公网 Quick Tunnel 旧实现不可作为本轮新的准备结果。内部包级门禁仍须最终 DMG 安装升级与完整支持矩阵，公开 profile 另需 Developer ID/公证；迭代 PASS 不授予发布资格。
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
