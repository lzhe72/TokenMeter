# v0.1.0-20260929T074814Z — 技术设计与开发计划

## 设计依据

输入：[需求](01-requirements.md)、[拆解](02-breakdown.md)、[全局架构](../../docs/architecture/README.md)。独立详细设计为[Electron本机合同](../../docs/architecture/01-electron-local.md)，包括进程/IPC、凭据隔离、更新协议、签名与重启、父门禁及Git边界。服务端API/schema沿用已有FastAPI/SQLite，无MySQL迁移。

## 当前先完成的需求阶段修订

先按[具体任务](02-breakdown.md)逐项建立TC，再在[测试计划](04-test-plan.md)明确输入、动作、预期、DB操作、类型及记录方式；SOP-008形成基线后才进入依赖开发。现有实现仅作差距检查，旧六组结果不证明新增TC执行。CASE-CATALOG→CASE-RECORDS→CASE-GATE依次落实总表、逐项执行和判定；基线/绑定不全保持阻断。

## 后续工作顺序与文件所有权

1. PLAN：按SOP-000/024同步AGENTS、索引、详细SOP、产品/测试/版本文档，按008完成基线。
2. SERVER/DATA：复用真实服务、SQL生成与生产首建程序，隔离venv执行基础回归；生产数据库和运行中旧App不变。
3. MAC：客户端agent独占apps/desktop的package/lock、electron-vite配置、main/preload/React UI、node:test；不编辑src/main/updater.ts或e2e。工程采用精确依赖锁定、正式包同等安全选项。
4. UPDATE：打包agent负责src/main/updater.ts、local_package.py及对应基础回归，使用electron-builder真实目录包、成熟嵌套签名、DMG/ZIP；保留失败探针再修复。包元数据、应用真实版本和信任锚一致。
5. RUNNER：E2E agent负责apps/desktop/e2e、local_e2e.py与负测。先编写用例、数据和有效失败基线，再补业务；按001/002/003/005/006/004完整回归。源码存在不等于运行通过。
6. REVIEW：整合者负责local_gate/local_release、质量入口、工作流触发迁移、目录/版本追踪；读取原始结果，不相信手写PASS。
7. 干净候选构建一次最终包，实际安装后全六例、门禁PASS、原包本地归档，再自动推送PR并合并源码，Git Tag追踪同一版本；不创建GitHub Release。

## 风险、失败与交接

Playwright Electron为实验支持，Xcode不是前提；签名兼容、正式包驱动、原生更新自主重启都须实测。缺原包或任一场景保留BLOCKED/FAIL。便携profile错误必须停止，不能回退生产目录。任何实现/依赖/包变化都使旧证据失效；修复后完整回归。首版升级为100→受控101，后续上一实际稳定包→新候选。

新程序未实现前在manifest登记本机执行绑定planned并明确旧绑定仅作历史，不以旧结果放行；实际建立后更新ready。当前进展和失败入口追加到[执行记录](06-iteration-record.md)，实际状态见[状态页](../../docs/status.md)。

## 追加：macOS界面统一

按[当前设计](../../docs/architecture/01-electron-local.md)落实用户HIG要求，保持Electron和六例业务合同；统一系统字体/密度/状态/深浅色和键盘交互，原创仪表图标嵌入App。完成真实窗口截图审查再构建最终候选。


## 本轮全量缺陷修复

2026-10-01用户要求所有已开发功能必测用例通过，按[回归修复计划](09-regression-fixes.md)执行。验收条件不变，原FAIL/BLOCKED保留，新包重新验证。
