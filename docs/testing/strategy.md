# 测试策略与发布门禁

当前 TM-001 的 Electron 客户端和本机包级执行器已建立，完整原包验收仍在进行；旧 SwiftUI/XCUITest 的 PASS 只属历史候选。[当前状态](../status.md)记录实际结果，[Electron 本机设计](../architecture/01-electron-local.md)定义本版路径。

1. 每项功能同轮交付需求/验收条件、稳定 E2E ID、详细用例、独立 expected、测试账号/数据生成及重置程序、执行 SOP 与真实产品测试。索引见[详细用例](cases/README.md)、[独立验收清单](../../tests/acceptance.json)、[功能矩阵](../../tests/feature_matrix.json)。缺绑定、数据或证据保持 BLOCKED。
2. 每次迭代、修复和发布执行本次目标及全部此前已交付功能；未来 planned 项不提前加入，目标不得降级以逃避测试。TM-001六个聚合场景组是历史入口，当前必须逐项执行`tests/test_cases.json`中的本版父TC及全部已声明变体，按[详细步骤](cases/README.md)执行；聚合PASS不能代填精细TC。
3. 本版默认在用户本机 macOS15 Intel，从最终 DMG 安装 Electron App，用 Playwright 操作真实 UI，贯通真实主进程/IPC、FastAPI 和逐例隔离 SQLite。Node/组件/API 自测、开发页面、截图或旧 Swift CI 结果不能替代。完整 Xcode 不是前提；其他 macOS/架构未经实测不宣称支持。仅用户明确要求多环境时运行 Actions。
4. 每例用新 0700 profile、安装位置、动态独占回环服务端口和 fixture；只清理本次拥有资源。本机49176已有用户生产服务、旧 App 也在运行，测试不得终止、覆盖、登录或写入。无凭据首启先从 UI 核对内置默认值，再经 UI 改至动态隔离服务。005仅在私有根运行生产首建程序验证 admin/123456 和强制改密，不访问用户生产库。
5. 004 保留 forbidden→redirect→invalid→valid 四阶段：非法下载和非回环 HTTP 重定向在外连前拒绝；完整坏签名 zip 被 Ed25519 拒绝且不交 Squirrel；正确 zip 通过长度/SHA256/签名/App Info 预验证后由 App 自主安装重启至 build101，恢复同一工作目录与 `/v1/me` 身份。默认更新清单为 `http://127.0.0.1:49177/version.json`，本例实际服务可由 UI 选择动态归属端口。Node 路径不沿用 Swift ATS `-1022` 错误码。
6. 测试数据有固定种子和独立预期，不能运行生产逻辑生成自己的答案。合成账号、SQL 和请求日志不得混入用户库、真实日志或 Git；未知数据不写成零。产品功能变化同步规格、矩阵、详细用例、SOP 和 Changelog。
7. 本机runner保存候选SHA/干净状态、最终包摘要、macOS/架构、每个TC及变体的原始Playwright JSON/逐步断言/trace/截图、fixture/SQL摘要、服务审计、更新前后包和进程证据及清理结果。测试输入、动作、预期和断言须先固定成可按TC重复执行的代码；Codex只调用程序并分析原件。父门禁独立复读原件、核对精确集合和摘要；runner自报PASS不具发布资格。
8. PASS仅在本版完整集合真实执行、零失败/跳过/重试取绿、同一候选/包/数据证据一致且清理完成时签发本机通行证。确定性断言失败为FAIL；缺执行器、权限、程序、步骤或证据为BLOCKED。已知CONFIG-01/05、CONFIG-06、UPDATE-04覆盖缺口由固定代码记录`coverage-blocked.json`，局部断言通过仍BLOCKED；有确定性失败时FAIL优先。保留首个失败，修根因后以新run_id完整重跑，不能删场景或调低期望。UPDATE-05受控签名负例在App启动前，以显式`--key-dir`核对受限目录归属、祖先路径安全、原ZIP重签名和p12公有证书指纹；公开配置、原ZIP或包清单自身矛盾为候选完整性FAIL；对有效包，私有输入缺失、不安全或身份不符为本次测试前置BLOCKED，预检PASS只准许执行，真实App断言失败为产品FAIL。2026-10-01固定候选c291的原13变体FAIL保持原样，新run单独记录。
9. 版本 `release_id` 贯穿需求→拆解→计划→测试→发布文档→Git tag，每次执行另有唯一 `run_id`。最终 DMG/更新包/原始报告/通行证只在本机版本目录归档；Git 只追踪代码、文档和索引，不创建 GitHub Release/上传资产。门禁和发布细节见[发布规范](../standards/release.md)。

后续采集、费用、同步、导出、提醒和数据库迁移的完整边界仍见[产品规格](../product/README.md)；各功能首次交付时新增对应 E2E，此后每版完整回归。仅对真实支持的平台签发结论，不把构建成功当跨平台通过。
