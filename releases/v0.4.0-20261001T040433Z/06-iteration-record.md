# v0.4.0-20261001T040433Z — 执行记录与交接

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


## 2026-10-01：移植至 TM-001 Electron 候选（SOP-004/006/022/024）

本独立工作树从已提交的 TM-001 候选 `3467dc143b2e2fc71f51515f483f0ecff8637947` 建立；原研究分支 `codex/v0.4.0-20261001T040433Z/claude-collection` 及其本机原件保留。仅移植 TM-004 版本档案、详细用例，并合并所需目录、Changelog与状态；保留 `releases/current.json` 指向 TM-001，以免改变 TM-001 本机门禁和治理用例的候选身份；不覆盖 TM-001 Electron 程序、测试或历史结果。此前记录的 `6e80dd1`、缺 Electron 等事实仅适用于原调查分支，不再描述当前工作树。当前工作树已有 TM-001 Electron 骨架，但 TM-004 的20条细TC未绑定仓库固定程序，TM-002/003稳定实现、完整raw/SQL数据及安装App结果仍缺。本移植不产生 TM-004 产品PASS或发布资格。

本次依新基线 SOP-004 加密 locator 合同修订需求和设计：私有0700/0600配置只存系统密钥保护的密文，密钥不可用停读重选，撤销删除；完整路径/密文不进用量与原件。历史探针结果及其未验证范围不变。本机证据已复制到本工作树 `.local/ci/tm004-claude-2.1.126-research/`，保留原件及逐文件摘要；复制不是新探针或新E2E。实际结构检查、治理和 Git 提交结果在本节后续记录。


移植工作树实际检查原件在 `.local/ci/tm004-port/`，未覆盖首次失败：`structure.log` 首次退出1，原因是 Changelog 标题附注破坏精确 release_id；更正后 `structure-02.log` 和末次 `structure-03.log` 均退出0，108文档/926链接、零结构错误。`quality-02.log` 退出1，只余 TM-004 细用例文档为 draft；这不是通过门禁。`governance.log` 首次退出1，原因是把 `current.json` 临时改到0.4.0，影响了 TM-001 门禁的版本假设；保持 current 为0.1.0后 `governance-02.log` 仍退出1，仅因新工作树缺锁定 Playwright 依赖。首次 `npm ci` 因共享 npm cache 的 EACCES 退出243；随后使用本工作树私有 `.local/npm-cache` 按 lockfile 安装361项，退出0，不修改仓库源码。末次 `governance-03.log` 为426项全部通过、退出0；`diff-check-02.log` 退出0。TM-004 的20条 TC 尚未登记到机器 `tests/test_cases.json`、根总表及固定 Playwright 程序，仍为设计草稿，不得把结构/治理通过转成产品验收。TM-002 加密 locator 的最终包测试若触及 safeStorage/Keychain，必须有与生产项分离的原生测试项、所有权和精确清理证据；当前未执行。
总控另确认当前共享 `scripts/export_test_cases.py` 仅接受单段字母 TC ID，并以当前 release 的任务拆解核对全部 TASK；跨版本整合 TM-003/004/005 会受阻。TM-002 工作流正在修共享导出器及治理负测。本版保持 `TC-TM004-...` 稳定编号，待共享修复后再把20条细TC写入机器清单、根总表和固定程序；此依赖未解除前仍 BLOCKED。


## 2026-10-01：可独立复核的来源投影与数据缺口（SOP-002/004/006/008/010/011/024）

沿用旧分支已隔离取得的2.1.126 CLI原件，只读从六份 JSONL 投影出会话/调用身份、usage、版本及父子字段；删除正文、完整本机路径和工具结果正文。仓库保存投影、原件SHA、投影SHA、行数、独立预期及 `scripts/tm004_fixture.py`。原件仍只在本机忽略目录，投影字节不同于原件，不能据此声明通用原始格式兼容。固定数字：main 1次13/7/20；main+复制fork 2次26/14/40；Agent父两次与子一次共3次59/18/77；双内容块1次31/9/40。畸形合成SSE的原生日志0/0无法证明有效零。程序另从已提交投影确定性地产生半行、补全、同ID用量冲突、真正缺usage四份**衍生故障注入**，独立预期0→20、可信20且冲突1、缺usage可信0且诊断1；它们不是CLI原件。详细说明见[研究数据](../../tests/fixtures/tm004/README.md)。

程序只在仓库 `.local/test-runs/tm004-<run-id>` 以0700/0600新建本轮数据；校验所有权标记、精确文件集合及摘要后清理。未触及用户默认 `~/.claude`、生产库、凭据、现有App或服务。实际原件在 `.local/ci/tm004-projection/receipt-02.json`：`verify-origin`、generate、verify-run、reset 均退出0；完整治理 `governance-02.log` 为429项通过/退出0；`structure-02.log` 为PASS（109文档/929链接）；`diff-02.log` 退出0。此前 `receipt.json` 保留首次窄范围验证，包含3项fixture治理通过。未运行 TM-004 Playwright、安装包或产品E2E。

尝试 SOP-008 严格基线的原件 `baseline-02.log` 与 `quality-02.log` 均退出1，仅机器报 TM-004 细用例文档仍为draft；语义核对还存在未取得的改写UUID、`fork-context-ref`、嵌套Agent和有效零原件，TM-002/003稳定接口及真实SQL未到，20条TC未进最终机器清单/总表，故不得将文档改为baselined。当前 `claude_raw` 仍 planned，派生投影只是来源调查/基础数据输入；没有 TM-003 真实schema前不编造产品SQL。现有 `granular_e2e.py` 只接受 `TC-TM001-...` 并固定78父TC，`local_gate.py` 固定78父/38变体/6补充；TM-004逐TC Playwright、完整已交付双来源集合、结果Excel与独立门禁重算均未绑定，旧 TM-001 通行不能代替。共享跨版本 exporter 修复由总控工作流推进，本版保留稳定ID与20条详细TC，不删不改预期来通过检查。
为避免 `releases/current.json` 仍指 TM-001 时只检查到其当前合同，又在本独立工作树临时将该指针置为 TM-004，分别执行目标版本 `check_docs.py --mode baseline` 与 `quality_gate.py check`，随即在 `finally` 恢复原字节并核对。原件 `.local/ci/tm004-projection/target-release-baseline-receipt.json` 与两份日志记录两命令均退出1、各13条错误，仅为本版01–06及细TC仍draft的严格基线要求；该复核不是基线PASS，也未改变提交的 current 指针。原 `baseline-02/quality-02` 是保留 TM-001 current 时的运行，各只报细TC draft，不能代表 TM-004 全部版本档案已基线。
