# REQ-TM003 · 功能与具体任务

**release_id：** `v0.3.0-20261001T034652Z`　**状态：** draft；依赖交接未完成。

输入为[本版需求](01-requirements.md)、[长期架构](../../docs/architecture/README.md)和四个稳定 E2E 场景组。功能仅 `TM-003`，需求仅 `REQ-TM003`；不吸收 TM-002 授权或 TM-005 完整统计的实现。

## 需求到功能点

| 功能点 | AC | 可交付行为 | 任务 |
| --- | --- | --- | --- |
| `FP-TM003-01` Codex 原生来源识别 | `AC-TM003-001`, `AC-TM003-002` | 只接受经核验的原生记录结构，未知结构可见 | `TASK-TM003-SOURCE`, `TASK-TM003-FIXTURE`, `TASK-TM003-PARSE` |
| `FP-TM003-02` 本地持久采集与去重 | `AC-TM003-001`, `AC-TM003-002`, `AC-TM003-003` | 完整行游标、响应身份、累计核对、重启/移动/分支不重计 | `TASK-TM003-STORE`, `TASK-TM003-SCAN`, `TASK-TM003-IDENTITY`, `TASK-TM003-MIGRATE` |
| `FP-TM003-03` 权限和状态 | `AC-TM003-001`, `AC-TM003-004` | 已确认授权根才读取，失效即停，重新授权后补扫 | `TASK-TM003-AUTH`, `TASK-TM003-UI` |
| `FP-TM003-04` 自动验证与交付 | 全部四个 AC | 固定数据、逐 TC 产品 E2E、同候选全回归与可追踪档案 | `TASK-TM003-E2E`, `TASK-TM003-RELEASE` |

## 具体 TASK 与验收出口

| TASK | 输入和依赖 | 模块边界与具体产物 | 可检查完成条件 | 对应 TC |
| --- | --- | --- | --- | --- |
| `TASK-TM003-SOURCE` | 官方协议/rollout 来源、受控 Codex CLI 样例；独立 | 固定支持版本、原生字段/来源/分支语义清单；样例只在本轮隔离根的 `sessions/YYYY/MM/DD/*.jsonl`；TM-002 元数据预览不当格式证明；不读真实用户日志 | 每个宣称支持的版本都有原生结构、字段摘要和复现来源；缺证据保持不支持 | `TC-TM003-SOURCE-01`, `TC-TM003-SOURCE-02`, `TC-TM003-CORE-02` |
| `TASK-TM003-FIXTURE` | SOURCE、SOP-010；独立 | `codex_raw` 生成/重置程序，在 TM-002 深度/数量上限内造嵌套 `.jsonl`、同层越界 symlink、半行、重复、冲突、fork、失效组合；独立 expected 与归属清理 | 固定种子重建同字节输入和 110/660/220/165 等预期，不插入用量表，不触碰真实目录 | `TC-TM003-DATA-01`, `TC-TM003-DATA-02` |
| `TASK-TM003-STORE` | 已基线 schema/隐私；依赖 TM-001 Electron 主进程基线 | 客户端 SQLite 的事件、游标、诊断、覆盖范围表及事务入口；仅保留白名单字段 | 来源域内调用键唯一约束、事件+游标原子提交、重启可读；身份密钥不可用停采集且恢复原键后不双计；无原文/完整路径 | `TC-TM003-STORE-01`, `TC-TM003-PRIVACY-01`, `TC-TM003-CORE-04`, `TC-TM003-CORE-06`, `TC-TM003-CORE-07` |
| `TASK-TM003-PARSE` | SOURCE、FIXTURE；可先独立源码准备 | 将完整原生 JSONL 行转换为只含白名单字段的候选用量；检验非负数、子项、UTC、版本、模型 | 增量、累计、未知/损坏及未知模型分别有确定结果；不从累计字段重复算量 | `TC-TM003-PARSE-01`, `TC-TM003-PARSE-02`, `TC-TM003-MODEL-01`, `TC-TM003-CORE-01`, `TC-TM003-CORE-02` |
| `TASK-TM003-IDENTITY` | PARSE、STORE；独立于 UI | 版本固定的来源域+原生调用 ID 本机 HMAC、同 ID 冲突/不明重用诊断、fork 继承边界与重放处理；共享事件字段与 TM-004 合同一致 | 同来源同 ID 重放计一次，跨来源同字面 ID 不冲突；无可证实的跨 Agent/会话重用标覆盖不完整；方案升级或本机密钥损坏不能使旧日志双计 | `TC-TM003-DEDUP-01`, `TC-TM003-BRANCH-01`, `TC-TM003-NAMESPACE-01`, `TC-TM003-CORE-03` |
| `TASK-TM003-SCAN` | PARSE、IDENTITY、STORE、AUTH | 限定授权根的可续扫内部分页枚举、完成/截断/取消状态、完整行游标、文件变化/30 秒补扫/手动刷新、移动/截断恢复；不把 UI 预览上限当全量 | 半行不前进、补全一次入库；超预览上限后仍能读到授权根末端用量并仅在全量完成时清除不完整提示；移动/重启/截断不重计，目录外与越界符号链接不可读 | `TC-TM003-SCAN-01`, `TC-TM003-SCAN-02`, `TC-TM003-SCAN-03`, `TC-TM003-WINDOW-01`, `TC-TM003-COVERAGE-OVERFLOW-01`, `TC-TM003-BOUNDARY-01`, `TC-TM003-CORE-05`, `TC-TM003-CORE-06`, `TC-TM003-CORE-07` |
| `TASK-TM003-AUTH` | TM-002 稳定提交及接口，**BLOCKED** | 经 TM-002 可替换只读能力获取确认来源及已验证 origin+account.id，接收失效/撤销/身份切换通知；仅主进程读日志 | 确认前/失效/身份切换时无旧能力读取；不同主体事件与游标隔离，重新确认后仅本主体补扫 | `TC-TM003-AUTH-01`, `TC-TM003-AUTH-02`, `TC-TM003-ISOLATION-01` |
| `TASK-TM003-UI` | STORE、SCAN、AUTH，**BLOCKED** | React 最小采集卡片与诊断，受限 preload/IPC，无任意路径参数 | 显示可信总量、cached 子项、覆盖起点、未知/失效/最后采集；UI 手动刷新真实驱动主进程 | `TC-TM003-UI-01`, `TC-TM003-UI-02` |
| `TASK-TM003-MIGRATE` | STORE、TM-001 已分发稳定包状态，**BLOCKED** | 新客户端 SQLite schema 的事务迁移、备份/恢复和旧版启动兼容 | 源/目标 schema、聚合和中断恢复由 SOP-016 在隔离库验证；无稳定旧包时记录该事实 | `TC-TM003-MIGRATE-01` |
| `TASK-TM003-E2E` | FIXTURE、UI、TM-001/002 稳定产品与隔离 GUI 资源，**BLOCKED** | 扩展当前仅 TM-001 的 runner、逐 TC Playwright Electron 测试、每步原件与跨版本完整集合机器门禁；四场景组作补充 | 每条本版 TC 可独立调用；门禁拒绝缺任一本版/历史 TC、变体或步骤的原件；最终 DMG 安装后真实 UI/IPC/SQLite 与全部历史功能同批完整通过 | `TC-TM003-E2E-01`, `TC-TM003-E2E-02` |
| `TASK-TM003-RELEASE` | 全部任务、SOP-013/014/017/018 | 本版文档、总表、Changelog、源码交接、候选与本机档案 | 清单/Excel回读、实际结果和候选一致；门禁 PASS 才正式 tag/DMG，否则准确 BLOCKED | `TC-TM003-GOV-01` |

上述每项 TASK 均有明确 TC；SOP-006 在[本版测试计划](04-test-plan.md)逐条给出输入、动作、预期、DB 操作及固定程序计划。`TC-TM003-E2E-01/02` 验证执行器自身的完整性，不能替代业务产品 TC。

## 顺序、边界与交接

先 SOURCE→FIXTURE→技术设计→逐 TC 基线，再建立独立 PARSE/IDENTITY 源码和数据测试；STORE/SCAN 需 TM-001 源码，AUTH/UI/E2E 需 TM-002 稳定接口。两个依赖任一未交接时，完成独立任务而将其余任务保持 BLOCKED。TM-001 与 TM-002 的文件由各自会话拥有；本工作树只改 TM-003 模块、接口适配点与本版文档，稳定提交后再在本分支整合，冲突需按接口合同核对。

不改变已有账号、服务端生产库或更新器；本轮先不实现同步 API。跨功能 E2E-TM003-004 留在依赖齐备的 TM-003，不反向要求 TM-002 的权限版本证明采集去重。
