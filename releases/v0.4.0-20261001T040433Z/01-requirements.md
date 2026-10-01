# v0.4.0-20261001T040433Z — Claude Code 采集需求（draft）

## 输入和当前事实

需求为 REQ-TM004 / TM-004；用户要在已授权 Claude Code 日志中只读采集实际调用、子代理、继承历史、重复片段、半写入及重新授权后的新增调用。继承 [产品约定](../../docs/product/README.md) 的 AC-TM004-001 至 AC-TM004-004 和 [既有场景](../../docs/testing/cases/04-TM-004-claude-collection.md)。本分支从已提交的 TM-001 `6e80dd1` 建立；该树只有旧 `apps/macos`，无已提交 Electron 工程，TM-002/003 在矩阵仍为 planned，`claude_raw` 没有原始数据程序。主工作区的未提交 TM-001 内容不是本分支的可追踪实现依赖。

[Claude 官方目录文档](https://code.claude.com/docs/en/claude-directory)说明 `projects/<project>/<session>.jsonl` 和 `<session>/subagents/` 的储存位置；[官方用量文档](https://code.claude.com/docs/en/agent-sdk/cost-tracking)说明并行工具步骤可能共享 assistant message ID，不能逐行累加；[官方会话文档](https://code.claude.com/docs/en/agent-sdk/sessions)说明 fork 继承对话历史。它们没有给出本机 CLI 2.1.126 各种原始 JSONL 事件的稳定公开 schema，也没有证明 fork 后改写 ID 时如何识别已计费调用。来源事实只支持目录发现和保守去重设计，不能据此声明已兼容某个原始格式。

## 2.1.126 来源证据与解释边界

本机在0700隔离 `CLAUDE_CONFIG_DIR`、清除凭据环境变量后执行 `claude --version` 得到2.1.126，隔离目录仍为空；只读核对已安装 `@anthropic-ai/claude-code` 2.1.126 的 `package.json`、`sdk-tools.d.ts` 与实际 CLI 二进制；二进制 SHA-256 为 `49a90c474383a9eda11310bd71f7ea6bb91361ec99443b733cb5003f6e703ccb`，本地调查原件 `.local/ci/tm004-claude-2.1.126-research/bundle-inspection.json` 记录字节偏移及标记（不入Git）。安装包含将复制或改写 UUID 的记录标为 `forkedFrom:{sessionId,messageUuid}` 的两处代码路径；另一处子代理路径写 `fork-context-ref`，字段为 `agentId,parentSessionId,parentLastUuid,contextLength`，读取时需要在父会话中找到 `parentLastUuid`。它还构造 `subagents/agent-<id>.jsonl`，可按子代理层级再嵌套；`agent-<id>.meta.json` 仅见 agentType 等元数据，不能单凭该文件推定父项目。内容块拆分代码保留同一 `message.id` 与 usage，因此逐行求和不成立。随包的 `sdk-tools.d.ts` 定义 Agent 工具结果的 `usage` 与 `totalTokens`，但它不是原始会话 JSONL 的正式 schema，不能再与子代理事件相加。

上述 `forkedFrom`、`fork-context-ref` 与嵌套路径仍是**静态代码线索**。随后使用本机该版 CLI、隔离 `CLAUDE_CONFIG_DIR`、假 API key、仅允许独占回环端口的 `sandbox-exec` 与固定合成 HTTP/SSE 响应，实际生成四份原生 JSONL：主会话、`--resume ... --fork-session` 新会话、Agent 父会话和 `subagents/agent-<id>.jsonl`。CLI 三组调用均退出0，分别向合成服务发出1、1、3次请求；外部网络被沙箱拒绝，开发者 home 文件读写被拒绝，没有默认凭据或真实模型调用。原始命令/请求响应、JSONL、SHA-256、隔离验证和精确清理保存在本机 `.local/ci/tm004-claude-2.1.126-research/evidence-manifest.json` 所列文件（不入 Git）；源版本和二进制摘要同上。

本次主会话 usage 为13/7；Agent 父会话两次调用分别17/5、23/7，子代理独立调用19/6，三次实际调用合计 input59、output18。子代理文件与父会话同 `sessionId`，以 `agentId`、`isSidechain=true` 和受限相对路径区分。fork 文件复制了父会话原有的 UUID、`message.id` 和13/7 usage，再追加新调用13/7；**这次原生日志没有 `forkedFrom` 字段**，不能要求该字段作为所有 fork 的必备条件，也不能对 fork 文件逐行求和。首轮试验尚未证明改写 UUID、`fork-context-ref`、嵌套子代理、重复内容块、半写入、其他版本或安装 App 兼容；不把合成 API 输入误称实际计费或产品 E2E。官方[目录说明](https://code.claude.com/docs/en/claude-directory)、[子代理说明](https://code.claude.com/docs/en/sub-agents)、[SDK用量说明](https://code.claude.com/docs/en/agent-sdk/cost-tracking)与[2.1.126发布说明](https://github.com/anthropics/claude-code/releases/tag/v2.1.126)的本次审阅范围没有提供覆盖全部变体的同版 raw fixture；本机安装包11个文件中也无独立样本，不排除其他来源。公开社区问题仅提示风险，不作为 oracle。

第二次同版隔离探针补足一项形态：固定合成 API 把同一消息拆成两个 text 内容块、最终 usage 31/9，CLI 原生 JSONL 写出**两条 assistant 行**，两行的 `message.id` 和完整 usage 相同；独立预期是一次调用、total40，不能逐行得到80。父 Agent 的 tool_result 文本还含 `<usage>total_tokens: 25</usage>`（该子代理本身19/6），不能再计一次。负测中，合成 API 故意在 SSE 的 message_start/message_delta 都省略 usage，CLI 仍写出完整的数值 0/0；因此**原生日志中的零不能单独证明上游提供了已知零**。这是故意畸形的合成 API 响应，不推断真实服务会省略 usage，也不把它当作有效零调用。原件及固定响应 SHA 见本机 `.local/ci/tm004-claude-2.1.126-research/followup-evidence-manifest.json`。尝试 `CLAUDE_CODE_FORK_SUBAGENT=1` 及隔离自定义 agent 的继承上下文配置后，生成的子文件仍未出现 `fork-context-ref`；这仅说明两次探针没有复现该结构。改写 UUID、该引用、嵌套层级与有效零样本仍未验证。

## 用户结果与验收条件

| AC | 输入与操作 | 用户可见结果和可核对边界 |
| --- | --- | --- |
| AC-TM004-001 | 用户经 TM-002 授权隔离 Claude 项目目录；主会话与其子代理各产生一笔完整用量 | 每次可证实的实际调用各计一次；子代理归属父会话和正确项目，模型明细保留来源；重扫/重启不增加。规划样例 M=100/10、S=200/20，合计 input300、output30、total330。UI 预览被截断或内部续扫未结束时覆盖标为不完整，不能声称已扫全。Codex 与 Claude 同字面原生调用 ID 不能互相吞并。 |
| AC-TM004-002 | 原会话、复制或引用历史的 fork、重复片段、半写入 | 可证实的继承历史不二次入账，分支新增调用计一次；不完整末行等待补全。规划 M=100/10、N=50/5、P=20/2，总量依次110、165、187。若无法证明继承关系或同调用身份出现矛盾用量，显示未确定且不把有疑点记录加入可信总量。 |
| AC-TM004-003 | 已验证版本的完整 usage、未知结构或缺字段事件 | 完整记录按已验证字段计数；未知格式与缺 usage 明确显示诊断和未覆盖数量，不能作为真实零值；既有可信总量不被覆盖。具体支持版本必须由原始样本及真实 App 结果确立。 |
| AC-TM004-004 | 授权失效期间新增子代理调用，随后重新授权重扫 | 失权期间显示读取受阻；恢复后旧主/子/继承数据不重复，新调用计一次，规划 total 从330到385；重启后相同。 |

## 权限、隐私和非目标

只读取用户通过真实界面明确授权的目录。原始提示词、回复、工具结果、代码、密钥或完整本机路径不进入持久化统计、服务上传、日志和测试报告；仅保存用量、必要的不可逆去重标识、相对归属和诊断代码。未授权路径、符号链接越界与失效目录不扫描。未知值以 unknown/missing 表示，不能填零；不能从模型文本推算 usage。时间用 UTC，展示可按团队 Asia/Shanghai；费用留给 TM-006。TM-005 显示聚合是下游，不由本版声称已验收。服务端团队同步属于 TM-007，不以 SQL 直灌代替本版采集。

## 关键未决与进入开发的判据

1. TM-002 已提交的授权/撤销/重授 IPC 与持久化接口，以及 TM-003 已提交的标准事件、去重 SQLite 与诊断接口仍缺；先记录各自 commit 与行为验证，才能冻结接入设计。
2. 已隔离生成本版主、单层子代理、`--fork-session` 复制历史及重复内容块的原生日志；仍需原生改写 ID、`fork-context-ref`、嵌套代理、有效零与半写入反例，才能冻结 AC-002 的完整继承 oracle 和支持列表。`claude -p '/branch ...'` 返回当前环境不可用；受限交互探针在命令输入前因对外服务连通性检查退出，沙箱没有放行外联，不得把这两次失败冒充改写 ID 原件。TM-002 选原生目录面板及 App 访问范围，用户已决定由 App 持久保存所选目录的必要私有 locator；精确隐私规范与实现合同仍待稳定提交，不能把它表述为 macOS 沙盒/TCC 持久授权。
3. 未决字段对应 TC 先标 `baseline_pending`，本版文档保持 draft。不得编造原始字段、以规范化 fixture 充当来源兼容证据，或将目标功能改 planned 来规避发布门禁。

下一步：[功能任务](02-breakdown.md)。
