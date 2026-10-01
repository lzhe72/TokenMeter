# v0.4.0-20261001T040433Z — 执行记录与交接

## 2026-10-02 · 已打开句柄reader辅助TC编制

SOP-008独立切片核对以输入提交`fea41fe494d655d279470b5032d87cdb10b57689`及后续SOP同步干净候选`ebbcfd01062939ca872f9f2f2ffba269158d894f`为准，收据`.local/docs-checks/20261002-tm004-reader-slice-final/receipt.json`：structure退出0、治理477/477退出0、用例目录225父/712步CURRENT、总表11 Sheet/225父/41变体/266行/13旧批次回读PASS、工作树clean。逐TC语义核对分别覆盖LF半行及754字节限额、keyed prefixMAC及同长度/mtime改写、非法UTF8/未知版本和无产品DB的重置；只对`CORE-01/02/03`与`TASK-TM004-INCREMENTAL/PARSER`已打开句柄纯模块部分判`development_slice_ready`。原20产品TC、四组摘要、TM-002授权与稳定产品文件身份、TM-003事务及App E2E继续draft/BLOCKED；0.4整版baseline、模块在本树实际运行、产品E2E、正式发行均NOT_RUN。

TM-004代码会话随后交接`e52b62e81f5f02b78c5c09241d7db0cd685f874b`（tree`eeac3b3df706eeef6617f2463e9a304bfb22b4c2`）的reader/适配/分页/事件模块，报告目标reader9/9、桌面49/49、build PASS；逐步测试提交`816ecd8cb5594743b33f9ebf9fb1dddbb5d2bb6a`（tree`fda54d4e12564e7e1061be77160d47dc8226e5fe`）报告CORE三例3/3、桌面52/52及typecheck PASS。原始模块结果尚无本版`source_check`独立Excel及批次回读，且代码未合入本文档树，机器binding保持null；更广的分页/归属/事件映射还需新辅助TC，不能把模块日志回填原SOURCE/LINEAGE等产品TC。

新的模块代码检查点`1c785082cf91fd5a017f1aae5080398646174256`（tree`63893ef27577841f524f3a06698315db9da109e2`）使扫描租约持续到受TM-002 `commitGuard`核对的同步提交回调结束，guard失败不调用回调；开发会话报告定向模块4/4及typecheck PASS。该代码仍依赖TM-002实际guard合同与TM-003 SQLite适配器和App触发，未完成本版`source_check`独立Excel或产品TC，故本记录只作源码进度，不登记模块/产品批次PASS。

后续代码检查点`7b5aae463a5bad78365cc0397a2a9cc45bb96c69`（tree`14dfa55bf2a68e43c8fd8887b2214850f8842e1e`）增加候选文件/扫描chunk间的父调用证据及复制fork去重；`.local/ci/tm004-cross-file-red.log`保留复现红测，`.local/ci/tm004-cross-chunk-green.log`显示定向7/7，开发会话另报桌面57/57和typecheck PASS。当前父证据及原生ID只在内存中，尚无跨扫描持久化、SQLite/App及`source_check` Excel；未来扫描辅助TC需冻结跨文件/chunk/重复fork输入，不能以本模块运行回填产品LINEAGE用例。

TM-004新代码工作树报告 `claude-reader.ts` 以已打开的只读FileHandle、完整LF游标和32字节秘密进行限额读取，模块红测0/3、修后绿测3/3及typecheck PASS原件位于其`.local/ci/tm004-reader-*`；源码目前尚未形成该切片的干净提交，以上只作为设计交接证据，不能回填产品`INCREMENTAL-01/02`或`PARSER-02` PASS。文档会话按SOP-002–008、024冻结 `TC-TM004-CORE-01/02/03` 的合成输入和逐步独立预期，保留原20条产品TC、四组摘要及真实授权/SQLite/IPC/App阻断。特别核对TM-002当前候选`fileIdentityDigest`包含size/mtime，追加即改变，不能当作稳定游标身份；同长度/同mtime前缀改写也须用keyed prefixMAC检出，密钥失效时不得提交新游标。纯reader模块既不完成事件与游标的SQLite原子事务，也不证明已授权文件身份。0.4整版基线、产品E2E和正式发行均NOT_RUN/BLOCKED。

SOP-024编制检查：structure退出0（134文档、1219链接），用例目录生成225父TC/712步退出0，治理457/457退出0（原始日志`.local/docs-checks/20261002-tm004-reader-governance.log`），`git diff --check`退出0，根总表回读退出0（11 Sheet、225父TC、41变体、266行、13旧批次；SHA-256 `671ed5da0024d11e9bcd9d0276d3d9d145628302b373ec483b0c536717def3cb`）。此前导出器因TM-005两条E2E标题移动报告stale失败，已把来源行从19/36更新为21/38并重生；不删测试以求通过。固定reader fixture SHA-256 `26c98b52b0af648fd591d6a42eeda83115746cab3f8c920ca7d815a4b5387a49`，逐TC文档 `9ac6b4aaa920ea1eecd3790455fbe648fccd9906346e4eb8a8ceee494f264bb4`，机器用例 `863273f87932606840d963b7b537be2e64c742d63ae9d360a9cb2928bd7c974e`。输入提交后另做SOP-008逐TC语义与依赖核对；本段结构/治理PASS不等于切片或产品PASS。

## 文档会话接管与可执行边界（2026-10-01）

文档会话保留源分支`05a9cd8`的01–06和20条细TC草稿，并从TM-004代码分支只读核对原生定向收据。`tm004-native-zero-20261001T1130Z/result.json`记录显式上游0/0和省略usage两种SSE都在Claude Code 2.1.126原生assistant JSONL成为0/0，`valid_provider_zero_proven=false`；不能把JSONL零直接当有效零。`tm004-native-nested-20261001T1131Z/result.json`仅记录本次Agent配置的三个请求、父/子两个文件及无`fork-context-ref`，不能推断所有嵌套模式不支持。有效零和`TC-TM004-SOURCE-03`继续`baseline_pending`。0.4正式升级须来自SOP-018/020通过并归档的0.3稳定原包，当前缺失；本轮只同步设计与机器用例，未运行安装后App E2E。

## 2026-10-01 04:04:33 UTC：SOP-001 立项

依据：总控委派 TM-004，路线图规划0.4.0；从当前已提交 `6e80dd1` 独立工作树建立 `codex/v0.4.0-20261001T040433Z/claude-collection`，不修改 TM-001 主工作区。读取了 `sop/README.md` 及 SOP-001–014、016、022、024，版本规范、产品、架构和现有 TM-004 用例。`releases/current.json` 原指未发布 v0.1.0；本独立分支指本版草稿，不改主工作树。基线选择已提交 v0.1.0；TM-002/003 版本仅在各自未提交工作树中，不能作为可追踪基线。未创建 tag。

## 需求与来源调查：SOP-002/024

`claude --version` 为2.1.126。未访问真实 `~/.claude`、生产库或用户App。官方资料确认日志目录与子代理目录、并行 assistant ID 需去重、fork继承历史；未确认 2.1.126 原始 JSONL 的稳定 schema、fork改写ID lineage或子代理父链。来源链接见 [01需求](01-requirements.md)。四项 AC 沿用既有产品规格；关键 raw 未决使文档维持 draft。独立工作树已记录需求，不声称已收集原始样本。

## 拆解、设计与测试计划：SOP-003–006/024

`02-breakdown.md` 建立8项具体 TASK 和18条细TC；`03-development-plan.md` 记录数据流/拒绝边界与依赖；`04-test-plan.md` 将四个 E2E 汇总场景回链细TC、独立数字与 SQL/重置缺项；[详细TC](../../docs/testing/cases/04-TM-004-claude-collection.md#本版细tc设计草稿)逐条写输入、动作、预期和阻断。TM-001 Electron工程在此分支的已提交树缺失，TM-002/003仍planned，`claude_raw`无程序；不能执行 SOP-009–014 依赖工作。确切 SQLite SQL、raw字段、部分 fork oracle 为 `baseline_pending`，未建立测试程序、未运行产品红测或E2E。

## 发布预案：SOP-007

`05-release-plan.md` 定义最终包、完整历史回归、升级、迁移、证据/清理与总控集成顺序。当前没有包、运行、通行证或发布资格。本版 Changelog 标为未发布。

## 结构检查与实际阻塞

编制中按 SOP-024 每步执行 `python3 scripts/check_docs.py --mode structure`，原始输出保存在本工作树 `.local/ci/tm004-planning/` 的 `001`–`006` 文件。001–004 的 FAIL 来自当时尚未填写的需求/任务/用例引用；005和006均 PASS（92文档、635链接、零错误），只证明结构。严格 baseline 尚未执行；缺 raw、依赖及机器TC/总表合同，按 SOP-008 不得标 baselined。产品 E2E `BLOCKED`，发布资格否。

## 交接所需下一步

1. 等 TM-001 Electron、TM-002授权和TM-003存储/诊断分别形成稳定提交，按顺序整合到本分支，再复核实际接口，不拷贝未提交主工作树作为发布基线。
2. 在隔离目录取得有来源的 Claude raw 版本样本，验证父子与 fork 改写 ID 语义；无可判定 lineage 时保持诊断和用例阻断。补全确切 SQL、fixture、`tests/test_cases.json`、总表和程序绑定。
3. 完成 SOP-008 baseline 后，按 SOP-009→010→011 真正运行红测，再实施 TM-004，完成 SOP-013/014/017/018；总控完成 SOP-019。任何 FAIL 原件保留，不以单元或计划代替产品通过。

## 2026-10-01：TM-003 草稿合同输入

收到 TM-003 会话的草稿规范事件结构：source/source_event_key/occurred_at_utc/model_id/input_tokens/output_tokens/cached_input_tokens/reasoning_output_tokens；input+output 为总量，缓存/推理仅为子项；游标与事件同事务、权限根由 TM-002 主进程提供。已同步设计章节；尚无稳定提交，不能解除依赖阻断。

## 本轮结束前的实际检查

- `python3 scripts/check_docs.py --mode structure`：最后一次 `.local/ci/tm004-planning/011-structure.json` 为 PASS，92份文档、638链接、0错误；`release_eligible=false`。早期001–004及010的失败原件保留，原因是草稿编制中引用未齐，后续修正后新输出通过。
- `python3 -m unittest discover -s tests/governance -p 'test_*.py'`：本工作树 `.local/ci/tm004-planning/governance.log` 原始输出为261项通过，退出0；只验证已提交旧基线的治理程序，不是 TM-004 E2E。
- `python3 scripts/quality_gate.py check`：`.local/ci/tm004-planning/quality-check-02.json` 为 FAIL，退出1；本版01–06和 TM-004 细用例仍是 draft，符合当前关键未决事实。严格基线与产品门禁均未通过。
- `git diff --check`：退出0。未执行 Electron构建、服务pytest、安装 App E2E、DMG门禁；本分支已提交基线无 Electron 工程和 TM-002/003 实现，依赖 BLOCKED。

## 2026-10-01：总控追踪复核

总控指出旧原件 `.local/ci/tm004-planning/quality-check-02.json` 中 `TC-TM004-INCREMENTAL-02` 缺少测试计划引用。该检查运行于提交前的中间草稿；提交 `2b04dc9` 已在 `04-test-plan.md` 使用完整ID，并在 manifest 追踪。对提交后干净树重新运行 `python3 scripts/check_docs.py --mode structure`，原件 `.local/ci/tm004-planning/013-structure.json`：PASS、退出0、零错误。重新运行 `python3 scripts/quality_gate.py check`，原件 `.local/ci/tm004-planning/quality-check-03.json`：FAIL、退出1，但追踪错误已消失；仅剩本版 01–06 与 TM-004 细用例保持 draft 的严格基线错误。未调整预期、未改功能状态；raw、SQL、产品 E2E 仍 BLOCKED。此条更正不覆盖或删除旧检查原件。

## 2026-10-01：Claude 2.1.126 安装包与官方资料安全核验

按总控要求只读核验本机安装包与官方资料，没有读取开发者真实 `~/.claude`、默认凭据、生产日志，未执行模型调用。`claude --version` 与包元数据均为2.1.126；实际 CLI 二进制 SHA-256 `49a90c474383a9eda11310bd71f7ea6bb91361ec99443b733cb5003f6e703ccb`。本地原件 `.local/ci/tm004-claude-2.1.126-research/bundle-inspection.json` 保存只读字符串扫描的标记、数量、字节偏移和边界说明。静态线索显示 `forkedFrom` 可标复制或 UUID 改写的历史消息，`fork-context-ref` 可记录 agentId/父会话/父最后UUID/上下文长度；读取父引用依赖父消息存在。子代理有可嵌套的 `agent-<id>.jsonl` 与 `.meta.json`；assistant 多内容块保留同一 message.id/usage。本机安装包11个文件中无独立 JSONL 或以 fixture/sample 命名的文件；所审阅的官方目录/子代理/SDK用量文档及同版发布说明提供目录和聚合原则，但未给出覆盖本版四类raw形态的测试样本，不排除其他来源有样本。隔离版本检查原件为 `.local/ci/tm004-claude-2.1.126-research/isolated-version-check.json`，退出0且隔离配置目录仍为空。

据此在01需求与03设计区分“已安装包静态字段”与“真实日志已验证”，详细用例增加 SOURCE-03、PARSER-03、LINEAGE-03/04/05，共18条。新增各条的实际raw、独立SQL、程序绑定和产品E2E仍 `baseline_pending`/BLOCKED；没有将二进制标记当作产品PASS。下一步需隔离生成或取得同版有来源的实际日志，先验证父链、usage最终值、重放与缺失反例，再冻结支持范围。

核验后运行 `python3 scripts/check_docs.py --mode structure`，本轮原件 `.local/ci/tm004-claude-2.1.126-research/structure-02.json` 为 PASS、退出0、零错误；`python3 scripts/quality_gate.py check` 原件同目录 `quality-check.json` 为 FAIL、退出1，13条错误全部是本版文档/细用例仍为 draft 的基线要求，没有追踪错误。新增5条TC已在04计划、详细用例和manifest一一登记，18条细TC均无执行绑定，功能/发布资格未变化。

## 2026-10-01：隔离原生 Claude JSONL 探针（SOP-002/004/006/009/010/024）

总控补充了安全条件：仅隔离 `CLAUDE_CONFIG_DIR`、假 key、独占回环合成 API 与无外联沙箱可运行 CLI，禁止真实 `~/.claude`、默认凭据和模型调用。先查官方目录/环境变量说明及安装包，再在本机 `sandbox-exec` 验证“仅指定 localhost 端口出站、开发者 home 文件读写拒绝”；合成 localhost 连接成功，保留地址外联和 home 合成标记读取均获 EPERM。未覆盖系统级所有可能文件读取，结论限于该沙箱策略与这次进程。随后在相同规则下 `claude --version` 退出0、配置目录为空。没有改写 `HOME`；调用环境仅提供隔离 `CLAUDE_CONFIG_DIR`、`TMPDIR`、假 `ANTHROPIC_API_KEY`、回环 `ANTHROPIC_BASE_URL` 及停用非必要流量配置。证据：本机 `.local/ci/tm004-claude-2.1.126-research/combined-isolation-probe.json`、`cli-combined-sandbox-version.json`。

在独占动态回环 HTTP 服务预先写好固定合成 prompt/SSE/usage 后，CLI 三次实验均退出0：主会话请求1次，写出 `raw-main.jsonl`（SHA-256 `b7001f9fe280b09a99f9a35ffb321fbcbe659cd7a89d0e393b103da2704bff99`）；`--resume <主会话> --fork-session` 请求1次，写出 `raw-fork.jsonl`（`d334760767ca91d0a658bd97ce1393e0587db41817596f5f57d6408a5e926684`）；Agent 场景请求3次，写出父 `raw-agent-parent.jsonl`（`3f2dffc120c83af5e489378dc5923b69be65b9b36208232bc7528cb29ecdf08a`）与子 `raw-agent-sub.jsonl`（`cc0f46f21b08ac7feb76be380ebb1468a14d6855a09ada6fcafde315a4eaefb5`）。子代理的原生 `agentId`、`isSidechain` 和目录层级出现，父会话两次 usage 17/5 与23/7，子代理19/6，独立预期合计59/18。主会话及 fork 新调用各13/7；fork 复制的历史 UUID、message.id、usage 与源文件相同，**没有**预设的 `forkedFrom` 字段。这项预设与实际不符，已改设计和TC；`fork-expected-before-run.json` 保留原预期而未覆盖。子代理、fork 的 JSONL 由2.1.126 CLI 写出，HTTP 响应是事先固定的合成模型结果，不能说明实际计费。

原始命令、请求、固定响应、stdout/stderr、源程序、文件摘要与结果在 `.local/ci/tm004-claude-2.1.126-research/evidence-manifest.json` 及其列出的文件，均为本机忽略目录，不入 Git。实验结束核验 0700 根目录所有权、owner marker、28项内容无符号链接/异主文件后，只清理本次 `/private/tmp` 合成目录；`cleanup.json` 记录已删除，回环服务器随程序停止。未碰真实日志、生产库、已有 App/服务。当前仅覆盖主、单层 Agent 和未改写 UUID 的 CLI fork；改写 UUID、`fork-context-ref`、嵌套代理、重复内容块、半行与真实安装 App 仍缺，完整 `claude_raw` 数据程序及产品E2E BLOCKED。TM-002 新选择原生目录面板 + App 访问限制，持久 locator 未决，设计已据此修正而未声称 OS 沙盒/TCC 授权。

本轮文档修改后 `structure` 退出0（92文档、638链接、零错误），治理单元261项通过，`git diff --check` 退出0；原件分别在同目录 `structure-final.json`、`governance-final.json`、`diff-check.json`。`quality_gate.py check` 退出1，13条错误仍全部是本版01–06和细TC文档 draft，未发生追踪错误；原件 `quality-final.json`。这些检查不构成产品E2E或发布门禁；无候选DMG、安装App测试或通行证。

## 2026-10-01：剩余来源形态调查（SOP-004/006/010/024）

总控要求继续独立核对改写 UUID、`fork-context-ref`、嵌套/重复 usage 块和缺字段。仍用2.1.126 同一 CLI 二进制、独立0700根、假 key、固定回环 API、开发者 home 拒读写及仅指定动态端口可出站的沙箱；测试前写下合成响应与独立 expected，未读取用户目录、调用模型或使用生产服务。官方[命令说明](https://code.claude.com/docs/en/commands)与[环境变量说明](https://code.claude.com/docs/en/env-vars)描述 `/branch` 与 `CLAUDE_CODE_FORK_SUBAGENT`，但当前网页内容不等于2.1.126运行事实；本机二进制确有相应字符串与 `forksParentContext` 条件分支，探针只以实际 JSONL 为结论。固定程序、请求、stdout/stderr、raw SHA 与失败预期都列在本机 `.local/ci/tm004-claude-2.1.126-research/followup-evidence-manifest.json`。

双 text 内容块探针退出0、请求1次；原生 `raw-multiblock.jsonl` SHA-256 `9084777275eab766b2916f8a774e2c9cc62745caa56faa0a8b94495db641ad80`。两条 assistant 行具有同一 `message.id` 和各自完整31/9 usage，独立唯一调用预期是40，不是逐行相加80。原生 Agent 父工具结果另有 `<usage>total_tokens: 25</usage>`，对应子代理19/6，不能叠加。另一次故意省略 API SSE usage 的负测同样退出0、请求1次；CLI 原生 `raw-missing-usage.jsonl` SHA-256 `497e7a456c1ac3d5b6d8d0b63fd415739b941030d6e65ed55af79f003731de38` 中却出现0/0。此畸形合成 API 只证明 CLI 会补零，不能作为有效零或真实服务缺usage的供应商样本；TC的真正 JSONL 缺字段 Q 与有效零 Z 仍缺独立来源。

开启 `CLAUDE_CODE_FORK_SUBAGENT=1` 的子代理探针及隔离自定义 `forksParentContext: true` Agent 探针都生成父/子 JSONL，却均未出现 `fork-context-ref`；开关场景还出现第四次父请求与重复合成响应，不能据此冻结该模式的账本语义。普通 Agent 子请求无 Agent 工具，本轮没有嵌套样本；不能据单次工具列表宣布嵌套不可能。改写 UUID 的 fork 需可控制的 `/branch`/同等原生触发路径和预期，当前只完成静态定位，没有 raw，LINEAGE-03/04、SOURCE-03 继续 `baseline_pending`。这些未复现路径没有用手工 JSONL 充当原件。隔离临时根核对 owner marker、0700权限、49项均由本用户拥有且无符号链接/套接字后精确清理；清理原件 `followup-cleanup.json`。TM-001/002/003 稳定接口、固定仓库测试程序、安装 App E2E 和发行门禁仍 BLOCKED。

为追查改写 UUID，又在第三个隔离根固定主会话后执行 `claude -p '/branch tm004-synthetic' --resume <合成父会话>`：退出0，但结果明确称 `/branch isn't available in this environment.`，无 API 请求或新会话。随后有时限的伪终端运行在输入 `/branch` 前退出1，终端原始输出提示对 `api.anthropic.com` 连通失败；沙箱仍只允许本次回环端口，未放行外联，零回环请求。父 JSONL 只多出 queue/system 运行记录，没有改写 UUID 或 `forkedFrom`。原始结果、前后 JSONL、命令、固定预期及摘要见本机 `branch-evidence-manifest.json`；不放宽隔离条件追求取绿，LINEAGE-03 维持阻断。第三个根经 owner marker、0700权限、12项归属和无符号链接/套接字核对后精确清理，原件 `branch-cleanup.json`。总控后来确认用户允许 TM-002 App 私有持久 locator，本版需求/设计已记录该决定，最终接口仍等上游稳定提交。

本阶段 SOP-024 `structure` 实跑退出0、92文档/638链接/零错误；`git diff --check` 退出0。严格 `quality_gate.py check` 退出1、13条均为本版 draft 基线错误，无追踪错误。三份原件分别为同目录 `followup-structure.json`、`followup-diff.json`、`followup-quality.json`。产品 E2E 未运行，不能据原生 CLI 来源探针发通行证。

## 2026-10-01：TM-003 调用身份与 TM-002 续扫合同协调（SOP-004/006/016/024）

总控只读核对发现 TM-003 草稿 `usage_event` 原主键 `(principal_key,response_key)` 若对 Codex/Claude 原生 ID 直接 HMAC，可能跨来源误去重；TM-002 UI 候选预览有1000文件/5000项/2秒限制，不能充当全量采集。读取 TM-003 独立工作树的03设计并与其会话直接核对；双方确认共同**草稿** `usage-identity-v1`：`source` 枚举 `codex`/`claude_code`，`source_event_key` 为本机 HMAC-SHA256 对长度前缀编码的身份版本、source、provider调用作用域、原生调用ID计算。Codex 为 `provider-response`+`payload.response_id`，Claude 为 `provider-message`+`assistant.message.id`；`principal_key` 独立分区，session/thread/agentId 只进不可逆来源归属键，不进调用唯一键；拟定主键 `(principal_key,source,source_event_key)`。同 ID 双块和已证实复制 fork 去重，跨 Agent/会话不明重用或用量/模型矛盾留首可信记录、诊断且覆盖不完整，父 Agent `<usage>` 摘要不入账。身份版本不随 CLI build 变，未来改版必须迁移/映射旧键。TM-003 尚无稳定提交或真实数据库，因此这里只冻结设计输入，不声称 schema 已实现或迁移通过。

本版新增 `TC-TM004-INCREMENTAL-03`：同主体下 Codex 与 Claude 原生字面 ID 均为 `shared-call-01`，C11/1 + M100/10 分别入账为2次/122；Claude fork 复制M不增，Agent S200/20 后3次/342；矛盾的衍生故障行只诊断，不覆写。另新增 `TC-TM004-SOURCE-04`：超1000文件的授权根在 UI 预览截断后，内部 continuation 未耗尽或深层子代理未扫到均保持 `history_incomplete`，全页完成才可报告 M100/10+S50/5=165。两项已写入 TASK、04计划、详细TC和 manifest 追踪；均缺上游稳定接口、固定原生数据/SQL和安装 App 自动绑定，继续 BLOCKED。TM-002 内部可续扫/分页和失权合同由其会话确定，本版不猜其 API 名称。细TC总数从18增至20。
本版新增 `TC-TM004-INCREMENTAL-03`：同主体下 Codex 与 Claude 原生字面 ID 均为 `shared-call-01`，C11/1 + M100/10 分别入账为2次/122；Claude fork 复制M不增，Agent S200/20 后3次/342；矛盾的衍生故障行只诊断，不覆写。另新增 `TC-TM004-SOURCE-04`：至少1025文件的授权根在 UI 预览1000上限截断后，内部 continuation 未耗尽或深层子代理未扫到均保持 `history_incomplete`，全页完成才可报告 M100/10+S50/5=165。两项已写入 TASK、04计划、详细TC和 manifest 追踪；均缺上游稳定接口、固定原生数据/SQL和安装 App 自动绑定，继续 BLOCKED。TM-002 后续给出草稿内部能力 `beginCandidateScan`→`nextCandidatePage`（最多256/页、opaque cursor及 complete/incomplete reason）→`openCandidateReadOnly(candidateToken)`→`cancelScan`，每页/打开重验授权、身份、根 dev/ino、边界和撤销世代；本版已据此细化 SOURCE-04，稳定提交前不能当成实现已存在。细TC总数从18增至20。

本阶段机器检查：`identity-governance.json` 记录261项治理单元通过；末次 `identity-final-structure.json` 为 PASS/零错误，`identity-final-diff.json` 退出0；`identity-final-quality.json` 退出1且仍仅13条本版 draft 基线错误。无数据库迁移程序或安装 App，因此 SOP-016 只完成方案核对，产品 E2E/发行仍 BLOCKED。

随后只读核对 TM-003 已提交 `dbcaa5e` 的03设计和 `NAMESPACE-01`、`COVERAGE-OVERFLOW-01`：`source=codex|claude_code`、长度前缀/HMAC 域、`provider-response|provider-message`、三字段主键、跨 scope 歧义诊断及首次建表无历史事件，与本版身份语义一致。TM-003 草稿 schema 另显式有 `cache_write_input_tokens`、`source_version`、`identity_scheme_version` 和 `coverage.scan_incomplete`；本版03设计和 SOURCE-04 已补齐这些字段与 UI 映射。无可见语义冲突；两边仍是文档/固定用例合同，实际 SQLite 与 App 尚未实现，不把提交视为产品 PASS。

总控通报 TM-001 Electron 干净候选 `3467dc1` 已合并新 SOP `master` 并通过其文档/治理预检，尚无最终 DMG 产品 E2E。只读检查该确切提交的 `apps/desktop/package.json`、主进程 `tokenmeter:invoke` 主窗口/主 frame 校验、preload `Bridge`、共享 `Snapshot` 和测试入口：真实 Electron/React/electron-vite 骨架、`scripts/run_test_case.py` 与 `scripts/local_e2e.py` 已存在于候选；但 `scripts/granular_e2e.py` 的身份正则和 spec 映射只支持 `TC-TM001-*`。本分支基点没有该 Electron 树，未复制 TM-001 快照或修改其文件。TM-004 后续需在总控整合树接入受限 preload/主进程与扩展逐TC runner；候选本身不能执行 TM-004 产品场景，且 TM-002/003 未稳定，仍 BLOCKED。

## 2026-10-01 · 2.1.126 已证实形态的纯解析器源码检查点

TM-004 开发会话交接其独立分支 `codex/v0.4.0-20261001T040433Z/claude-electron-port` 提交 `f2c3972`：新增 `apps/desktop/src/main/collection/claude-format.ts` 与 `apps/desktop/tests/claude-format.test.ts`，仅为纯内存 2.1.126 JSONL 解析器切片，尚未接 TM-002 授权目录、TM-003 HMAC/SQLite、UI/IPC 或最终包。文档会话只读核实了两文件存在及原始日志尾部：`.local/ci/tm004-parser-npm-test-02.log` 记录桌面单元36 PASS/0 FAIL，`tm004-parser-governance-01.log` 记录治理452/452 PASS；开发会话另报告 typecheck PASS，红测原件保留于同目录多个 `tm004-parser-*-red.log`。这些是源码/单元证据，不是细TC产品PASS。

当前解析器固定：只消费完整LF行；同 `message.id` 的双内容块和原样复制 fork 只记一次；父 Agent tool_result 的用量摘要不再入账，子 Agent 只有可验证的同版父 summary 才归属；0/0 保持 `ambiguous_zero`，未知版本、缺/非法 usage、时间与结构记诊断，同ID冲突或不明继承保留首可信调用，不把内容/路径放入返回结果。11项单元检查使用 PARSER-02/03、LINEAGE-01/02/05、INCREMENTAL-01、DIAG-01/02 的稳定父TC编号作范围提示，但没有执行这些TC的完整输入/逐步UI/DB判据，不能代填测试清单。改写UUID fork、`fork-context-ref`、嵌套Agent及有效零的原生来源仍不足，保留 `baseline_pending`；整版严格baseline和quality因详细用例仍draft而失败，正式数据、产品E2E/发行NOT_RUN。

编制此记录时主仓库Git对象库路径在外部操作后暂不可见，文档会话不能核对新提交对象或提交本版文档，只按开发交接的短SHA、仍在其工作树中的源码文件和实际日志记录。恢复后须读回完整commit/tree并把本记录纳入文档候选，不把短SHA或单元日志当作整版基线。
