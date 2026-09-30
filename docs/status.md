# 当前状态

当前功能版本为 `v0.1.0-20260929T074814Z`，TM-001（账号、登录与最小更新器）仍在开发验收中，**未发布**。接手先读 [SOP 总索引](../sop/README.md) 和对应独立 SOP；详细开发与失败历史见[本轮执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)。

## 当前交接（2026-09-30）

- 本轮原生必测集合为 E2E-TM001-001、002、003、005、006、004，共六例。第006例的需求、独立数据、Swift UI 用例和双服务 runner 已编写：App 首次默认 `http://127.0.0.1:49176`，登录页允许改服务地址并保存手动覆盖；正式 App 仅允许本机回环 API 使用 HTTP，非回环 API 与软件更新源要求 HTTPS。runner 先独占 49176，再以两套隔离 FastAPI/SQLite 验证切换、重启及会话边界；端口被占用即 BLOCKED，不访问用户生产库。程序绑定状态为 `ready`，表示入口齐全，**不表示六例已通过**。
- 本机 Intel Mac 只有 Command Line Tools，原生 XCUITest 在本机不能运行。开发、服务端检查及预览安装继续在本机进行；迭代原生 E2E 由 [quality.yml](../.github/workflows/quality.yml) 在 GitHub 托管的 macOS 15 Apple Silicon 与 Intel 上使用 Xcode 16.4 自动执行。CI 中 `127.0.0.1` 指各自 runner 的隔离服务，不是本机生产服务。
- 候选 `9e61d867dc983faaa0012527353742238b72f7f9` 的 [run36660917395](https://github.com/lzhe72/TokenMeter/actions/runs/36660917395) 两架构各有 001/002/003/005/006 五例原生 PASS；004 的 Quick Tunnel 随机域名在同一隧道 180 秒系统 DNS/TLS 探针内仍未解析（`curl` 退出6），第004例 BLOCKED，完整六例迭代门禁仍 BLOCKED，PR 不能合并。现正将两个公开 HTTPS DNS 源的记录发布检查放在首次系统解析之前，共享原有180秒窗口；两方就绪后仍必须由 Mac 系统 DNS/TLS 实际访问并核对来源。另增默认关闭、只运行环境探针的手动 `environment-diagnostic` 路线，零产品用例且无合并资格。两项修订尚无同一新候选的原生结果，不能宣称004或六例通过。此前45秒阻断、同一域名约105秒后可访问的诊断及更早运行见[迭代记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)。
- 本机 `database/test/test.db` 只供 Codex 回归；`database/production/production.db` 为用户生产库，首建仅预置 `admin / 123456` 且首次登录强制改密。[数据库说明](../database/README.md)给出初始化、造数 SQL、只读核验和服务重启命令。当前 `127.0.0.1:49176/v1/health` 实测返回 200，`/Applications/TokenMeter.app` 预览 App 仍存在；该临时签名 `.UITesting` App 不是本次正式候选，也不构成安装包验收。原生 E2E 逐例使用临时 SQLite，不重置这两份本机库。
- 本机最终整合检查：文档 baseline 69 份/435 链接、追踪 12 功能/37 场景/6 项绑定、governance 180 项、server 43 项、更新工具 9 项均通过；Auth 与 AccountStore 的 UITESTING Swift typecheck 通过。第006例双服务真实 FastAPI/SQLite 冒烟、runner focused governance 29 项、Swift 用例语法解析和 plist lint 通过。这些只证明源码、规范与辅助程序检查，不是 App 原生 E2E 或发布 PASS。
- 正式发布仍需同一候选的两架构完整六例迭代回归、最终 Developer ID 签名与公证 DMG、安装后全量原生回归、macOS 14+ 声明支持矩阵、受保护发布流程和有效通行证。PR #2 保持草稿；远端 master 尚未合并 v0.1.0，无正式 Tag/Release。预览 DMG 只供本机体验。

## 下一步

1. 验证 DNS 发布前置探针和隔离环境诊断程序，再提交新候选，让 GitHub 两架构对同一提交执行完整六例；逐平台检查原始 `xcresult`、候选 SHA、数据摘要和清理结果。单独环境诊断只能说明前提是否就绪，不能替代产品回归。FAIL 按 SOP-015 修复后完整重跑，缺环境或证据保持 BLOCKED。
2. 同一候选的迭代回归完整通过且 PR 适用检查通过后，按 SOP-019 合并源码 PR；正式发布另按 SOP-017/018 验证最终安装包并取得有效通行证，之后才创建正式 Tag/Release。历史运行日志和本机过程证据索引见[06-iteration-record.md](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)。
