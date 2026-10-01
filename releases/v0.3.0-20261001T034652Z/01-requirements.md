# REQ-TM003 · Codex 采集需求

**release_id：** `v0.3.0-20261001T034652Z`　**状态：** draft；产品未实现、未验收、未发布。

## 用户、问题与边界

已通过身份接口验证 origin+account.id、并在 TM-002 明确确认 Codex 日志目录的成员，需要在 App 中看到可核对的已采集 Token 总量和采集诊断。日志是只读来源，采集不能依靠用户生产库、默认凭据或测试代写用量表。TM-001 的身份与 TM-002 的真实目录授权是本轮产品前置；本独立分支现以 TM-001 干净候选 `3467dc143b2e2fc71f51515f483f0ecff8637947` 为技术基底，但其最终产品门禁尚未通过，TM-002 也未交接稳定接口，故集成与产品 E2E 为 **BLOCKED**。

本轮只处理 Codex 已验证格式的会话日志及可核实用量，包含主会话与通过原生日志身份可识别的分支。Claude Code、完整统计筛选、价格计算和团队同步分别由 TM-004/005/006/007 交付。本轮提供最低限度的采集状态、用量核对和诊断界面，不将其称为 TM-005 的完整统计。

## 可观察的验收条件

| AC | 输入与权限 | 正常结果 | 失败及边界结果 |
| --- | --- | --- | --- |
| `AC-TM003-001` | 已登录，TM-002 已确认 Codex 授权根；在该根内逐次写入经版本核验的原生 JSONL 用量记录 | 完整行增量采集；A/B/C 分别 100/10、200/20、300/30 时唯一响应 3 个、input 600、output 60、total 660；cached 20/40/60 是 input 子项，单列 120 而不另加总；手动重扫、30 秒补扫、重启、同根移动源文件后仍为 660 | 未授权根、越界符号链接、缺用量字段、无效负数或大于 input 的 cached 不产生成功事件；未知值显示诊断，不以 0 填补 |
| `AC-TM003-002` | 同一日志给出逐响应 `usage` 与累计的 `turn_token_usage`/`thread_token_usage`；重复 response ID、独立新会话和带可核实 fork 身份的新分支；共享事件键核对 Codex/Claude 字面相同原生 ID | 每个可信调用 ID 在其显式来源域仅计一次，不逐行累加累计快照；示例增量 100/10、50/5、30/3、20/2 得 input 200、output 20、total 220；跨来源同字面 ID 生成不同不可逆键，重复及继承记录贡献 0 | 缺调用 ID、同来源同 ID 的矛盾用量/模型或跨会话/Agent 无法证实的重用、无法核实的累计回退、未知结构均保留诊断和不完整覆盖，不污染可信总量；不猜测分支继承数字；本机身份密钥不可用时保留已落库可信用量并停采集，恢复原密钥或可核验迁移前不能以新密钥重扫旧日志 |
| `AC-TM003-003` | 完整 A=100/10，随后只追加 B=50/5 的半行，再补足换行；之后仅删除测试拥有的源文件；另有超过 TM-002 预览上限且最后一份含可信用量的授权根 | 半行阶段仅 A 且 total 110；完整后两响应 total 165，重启不重计；已落库事件在源文件清理后保留；授权后的内部可续扫须读到上限后的 A=110，直至全量完成前覆盖仍为不完整 | 游标不跨过半行；文件截断/替换导致重新扫描并以响应身份去重；预览截断不能冒充历史扫描完成，页间撤权或目录 dev/ino/mtime/ctime 变化后的旧 cursor/candidateToken 均不得继续读取，全部暂定页和暂存解析/同步结果须回滚，从新 generation 第1页重扫；候选树 complete 后另核实正文稳定完整；缺分页能力时该场景 BLOCKED；早于可证明覆盖起点的历史显示“缺失/未核实”，不能写 0 |
| `AC-TM003-004` | TM-002 对同一隔离根先授权、撤销或失效、再通过真实界面重新授权；失效期间追加 C 与重复 A | 失效时不读取；授权前 A/B total 330，恢复后唯一 A/B/C total 660；重复 A、刷新、重启不重计 | 授权失效或身份切换显示需重新授权，不能沿用旧句柄读失效根、访问未选目录或混看另一 origin+account.id 的采集事件；无可执行授权恢复绑定时本 AC 为 BLOCKED |

## 数据口径和隐私

本轮 `total=input+output`；cached read 与 cache write input 是 input 的子项，reasoning output 是 output 的子项；未知子项保持未知，不以 0 代替。只保存用量、UTC 时间、模型标识、必要的去重身份摘要、授权根的不可逆本地标识、读取游标和诊断代码。不得保存或上传提示词、回复、代码、API key、完整本机路径或完整原始 JSONL。会话文本和源码内容既不写库也不写测试报告。

App 只经 TM-002 已确认来源的主进程只读能力访问文件；确认前不持续采集，已验证 origin+account.id 切换时立即停读并隔离采集状态。文件变化可触发读取，每 30 秒补扫，手动刷新可立即扫描；App 退出即停。首次按事件 UTC 时间默认导入最近 30 天（含截止秒）；缺失或无效时间不计入可信量，时间存 UTC，缺历史须明确提示。采集结果保存在客户端隔离 SQLite；本轮没有团队同步请求。

## 来源核验及支持条件

2026-10-01 在独立工作树执行 `codex --version` 得 `codex-cli 0.158.0-alpha.2.1`。官方同版本 tag `rust-v0.158.0-alpha.2.1` 对应提交 [`0d9c7cbf`](https://github.com/openai/codex/tree/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807)。其[协议结构](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/protocol/src/protocol.rs)定义逐响应 `TokenUsageRecord` 的 `response_id`、`usage`、累计 turn/thread 用量及 `TokenUsage` 子项；[JSONL wire 结构](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/history/src/rollout_payload.rs)定义顶层 `type=token_usage_record` 和 `payload`；[rollout 记录器](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/rollout/src/recorder.rs)包含 `session_meta`、fork 身份；[fork 处理](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/core/src/agent/control/spawn.rs)明确子会话不继承父会话的逐响应用量记录。源码结构是设计依据，**不是**这台电脑已产生的原生样例或所有 Codex 版本兼容证明。

追加核验：同版[会话状态实现](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/core/src/state/session.rs)把单次 `usage` 累加为 turn/thread 快照；[响应完成处理](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/core/src/session/mod.rs)仅在完成响应带用量时持久化 `TokenUsageRecord`，并从 rollout/压缩点恢复最近记录。[官方累计用量测试夹具](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/app-server/tests/common/rollout.rs)只追加 `event_msg.token_count`，不能冒充逐响应增量样例。[官方 Responses 测试夹具](https://github.com/openai/codex/blob/0d9c7cbfa6cf1489f55a8a9542b75ddd2c061807/codex-rs/core/tests/common/responses.rs)给出本地 SSE 的 `response.created`、`response.output_item.done`、含 `usage` 的 `response.completed` 格式。源码文件、SHA-256 和仍未知事项留在本机 `.local/research/codex-0.158.0-alpha.2.1/source-audit.json`。

SOP-010 须在完全隔离的测试根取得与声明版本匹配的原生日志样例，登记版本、字段与摘要，并以固定数据程序重建无敏感内容的等价测试文件。不得扫描真实 `~/.codex` 或从规范化用量样例冒充原生格式。TM-002 对普通 `.jsonl` 文件的候选预览只证明相对名称/大小/mtime，不能替代 TM-003 的原生格式与版本核验；测试文件位于其受限枚举范围内的 `sessions/YYYY/MM/DD/*.jsonl`。TM-002 草稿的根深度0、最多8层目录/1000文件/5000目录项/2秒仅约束候选预览；超限“不完整”不能被 TM-003 当成历史已覆盖，具体接口以 TM-002 稳定交接为准。若无法取得可信原生样例，产品兼容与 E2E 保持 BLOCKED；读取器将不认识的记录明确诊断，不宣称该版本受支持。

按 SOP-004 来源研究、沿用 SOP-009/010 隔离边界的固定探针 `scripts/tm003_native_probe.py` 已在本轮私有目录实际运行。第一轮 `20261001T054012Z-93603` 生成原生记录，但还向本地拒绝代理尝试访问外部域名，依预定请求边界判为 BLOCKED；第二轮 `20261001T054336Z-94554` 使用[官方配置键](https://learn.chatgpt.com/docs/config-file/config-reference)关闭插件、远端插件、应用更新、analytics 与 OTEL 后，仅观察到一次向独占 `127.0.0.1` 端口的 `/v1/responses` POST。第三轮 `20261001T054930Z-96270` 加严对用量、LF、UTC、路径、归属和无认证文件的固定断言后同样通过。已安装 CLI 自写 `sessions/2026/10/01/*.jsonl`，`session_meta.cli_version=0.158.0-alpha.2.1`，逐响应记录 `response_id=tm003-native-probe-response-1`、input100/cached20/cache write0/output10/reasoning2/total110。第三轮 CLI 退出码0，原件 SHA-256 为 `3b30cfa81c0c29a80f1bfc1de5bf823db01a9a85636e41ec58dfdd00f0436d08`；原始 stdout/stderr、请求清单、前置状态、归属和结果位于 `.local/tm003-native-probe/20261001T054930Z-96270/`，不提交原始 JSONL。该结果只核验本机同版 CLI 的基础落盘形状，**不构成** SOP-010 数据 fixture、TM-003 自动化或产品 E2E PASS；resume/fork/子代理边界、动态衍生 fixture 与其他 build 仍待验证。

后续固定隔离程序 `scripts/tm003_lifecycle_probe.py` 在 `.local/tm003-lifecycle-probe/20261001T060101Z-1879/` 记录同版 CLI 的原生恢复、`exec fork` 与无用量完成响应。四次请求只到本机 Responses 服务，三个 CLI 自写 rollout：根线程 A=100/10 后恢复追加 B=50/5，根文件两条逐响应记录的 thread 累计为 165；fork 子文件只含新 C=20/2 的逐响应记录，`forked_from_id` 指向根，**其 `thread_token_usage` 仍延续父累计到 187**；第四个独立无用量完成文件没有 `token_usage_record`，其 `event_msg.token_count.info=null`。首次生命周期探针因把 fork 累计误设为只含 C 而判 BLOCKED，原件留在 `20261001T055851Z-1040/`；上述第二次运行改按观测语义断言后为 `SOURCE_LIFECYCLE_PASS`。这证明普通 CLI fork 的文件不复制父逐响应记录，但不能推出子代理、其他版本或 App 采集已通过。

## 依赖与决定

- 最初比较源码快照来自 TM-001 工作树提交 `6e80dd1` 加 2026-10-01 逐文件稳定复制；收据留在旧独立工作树 `.local/planning/`，该快照未带入现有干净分支。现有技术基底为上述 TM-001 干净候选；其产品通过与 TM-002 稳定交接仍待证据，不能用来源研究替代。
- 本轮采用逐响应 `usage` 与稳定 `response_id` 为可信计量主路径；累计字段只作一致性核对，不作为新增量直接累加。旧 `event_msg/token_count` 没有可核实响应身份时只诊断。这样可以保留未知而不把相同数字的两次真实调用错误合并。
- 回复文本、工具调用内容及完整路径均不进入采集库。能否识别某模型与能否取得其实际费用是两件事，本轮只保留模型标识和 Token 口径。
- 需与 TM-002 明确交接：与已验证 origin+account.id 绑定的已确认来源只读能力、失效/撤销/切换身份通知、重新确认后的能力和隔离测试 fixture。用户已在 TM-002 会话确定 macOS 原生目录选择器，由 App 私有保存所选目录并强制限制后续读取；本版按非 MAS 环境和该主进程边界设计，不声称拥有沙盒级持久 security-scoped grant。用户“App 持久保存所选目录”的决定已覆盖必要的当前用户私有可解析 locator；按 SOP-004 该 locator 必须在当前用户私有来源配置中由 macOS 系统密钥保护能力加密保存，无明文回退，失效或密钥不可用时停读重选；具体字段与重启恢复行为待 TM-002 稳定合同核对，TM-003 不预设其实现。接口尚未交接前，依赖任务不标完成。

后续按 [SOP-003](../../sop/SOP-003-feature-breakdown.md) 拆任务；当前需求定义不构成产品 PASS。
