# 自动 E2E 与发布门禁

## 当前真实状态

TM-001 已建立 App、服务端、原生执行器和原始结果复核，当前验收结果统一记录在[状态页](../status.md)。迭代门禁根据本次真实原生执行判定；内部分发按[内部包设计](../releases/01-internal-v0.1.0.md)验证最终DMG及两平台完整原生回归；在该候选实际完成前不具发布资格。公开分发的Developer ID、公证条件独立保留。v0.1.0 的数据库目标是隔离的生产 SQLite，MySQL 不属于本版门禁。

下面定义执行器必须持续满足的合同。不能通过删除阻断、手写 PASS JSON 或让空脚本返回零来宣称完成。

## Codex 的自动闭环

需求→功能拆解→技术设计与开发计划→测试计划→发布预案→文档基线 → 工程骨架与隔离环境 → 数据与真实测试程序 → 行为红测 → 业务实现 → 构建 → 执行本次目标及全部此前已交付功能 E2E → 收集原生结果 → 机器判定 → 失败修复后重新完整执行。

文档编制采用 structure 检查；整套计划完成后才执行严格 baseline。文档基线允许明确的 planned 程序绑定，不能要求尚未进入的工程步骤已经完成。SOP-009 建立骨架并分别记录源码完成和真实运行状态；缺运行环境时可做具有独立验证条件的子任务，不能把未执行的红测或产品回归标记通过。

SOP 负责让 Codex 可重放每一步；门禁结论由程序根据本次执行证据生成。人工复核可以补充意见，不能替代自动执行或把 FAIL/BLOCKED 改成 PASS。

## 入口、状态与退出码

| 命令 | 用途 | 当前行为 |
| --- | --- | --- |
| `python3 scripts/quality_gate.py check` | 检查文档基线、功能、用例、数据程序和 SOP 引用 | 仅规范检查；通过也无发布资格 |
| `python3 scripts/quality_gate.py iteration` | 本次产品迭代门禁 | 规范检查后启动真实原生 E2E，复核本次结果 |
| `python3 scripts/quality_gate.py release` | 公开发布候选诊断 | 保留Developer ID/公证合同，当前缺凭据时BLOCKED |
| `internal-release.yml` / `internal_release_gate.py` | 内部最终包发布门禁 | 受保护master同一DMG、两平台六例原件校验；仅完整PASS签发通行证 |
| `python3 scripts/e2e.py --phase iteration` | 直接运行产品 E2E 适配层 | 真实构建与逐例执行；缺环境记录 BLOCKED |

- `0 / PASS`：该命令对应检查已通过；只有产品发布门禁的 PASS 才有发布资格。
- `1 / FAIL`：规范无效、测试断言失败或证据校验失败。
- `2 / BLOCKED`：缺运行条件、执行器、必需数据、平台或有效证据。

报告写入 `.local/e2e/<run-id>/result.json`。`runner_implemented`、`executed_cases`、逐例结果和清理状态必须来自实际执行；零执行/未接入不能通过。父门禁分配本次运行ID并重新解析原始xcresult，检查提交、清单、产物和数据摘要。迭代`release_eligible`始终false。内部最终包门禁只消费同次受保护workflow/attempt的原始资产和原生证据，完整复核后才签发通行证；不接受任意外部PASS报告。

## 必须自动执行的检查

| 层级 | 自动检查 | 不通过时 |
| --- | --- | --- |
| G0 需求追踪 | 每个目标功能有规格、正常/失败/边界用例、生成/重置程序、SOP、真实测试绑定；不能删掉核心需求绕过 | FAIL/BLOCKED |
| G1 数据环境 | 固定种子/时钟生成用户、数据、独立 expected；初始化隔离真实服务与数据库；验证清理范围 | FAIL/BLOCKED |
| G2 构建基础 | 客户端/服务端构建，单元/集成/迁移测试，锁定版本与依赖 | FAIL/BLOCKED |
| G3 产品 E2E | 原生 UI 驱动真实 App，贯通真实服务与数据库，回归本版本及全部之前已交付功能 | FAIL/BLOCKED |
| G4 发布验证 | 按 `distribution_profile=internal/public` 核对最终包签名/Gatekeeper、干净安装、上一稳定版升级、数据迁移/恢复和 OS/架构/数据库矩阵；public 另核对 Developer ID 与公证 | FAIL/BLOCKED |
| G5 证据一致 | 源码提交、构建物、fixture、用例清单、执行结果、Changelog/版本完全一致 | FAIL/BLOCKED |

每次产品迭代（包括修复、beta）必须跑 G0–G3 和适用的兼容回归；每次内部或公开正式分发再按对应 profile 跑 G4–G5。与该版本无关的未来功能可以仍为 planned，但目标版本要求交付的功能不能通过改成 planned 被排除。

矩阵所有已发布功能的用例必须完整执行；测试发现数量与预期不一致、零用例、skipped、xfail、超时、中断或缺少任一平台结果，均不通过。不得自动重跑失败直到变绿；修复后创建新运行，保留旧失败证据。

## 真实 runner 的接通要求

TM-001 的 `scripts/e2e.py` 与 `scripts/native_e2e.py` 已接入真实执行，`scripts/quality_gate.py` 负责父进程复核。伪造/缺失/过期证据、零用例、错ID和跳过场景都有负向工具测试；工具负测不替代产品结果。

执行器负责：

1. 检查完整 Xcode、已登录 GUI 会话、原生测试目标、工具链、测试数据库和端口可用性；不足时明确 BLOCKED，不尝试静默改变开发者系统配置。
2. 从候选提交构建测试 App/服务端；发布阶段测试最终候选签名包。为本次运行创建隔离目录、数据库、UITESTING 专用凭据目录、临时签名 Keychain 和执行App同机的可控回环更新服务器；TM-001 第004例固定49177，不能复用未知服务或公网隧道。
3. 用程序生成/重置测试账号与数据，使用与生产一致的密码散列和认证逻辑初始化测试库；合成账号文件本身不是已创建账号。
4. 用 XCUITest 驱动 UI，包括系统授权/拒绝/恢复；日志、离线/故障、时钟、升级服务器通过场景程序控制。环境适配不能跳过真实被测行为。
5. 通过 `xcodebuild` 原生测试结果提取用例与断言，采集 `.xcresult`、服务日志、截图/失败附件、fixture 清单、构建摘要及迁移结果。
6. 程序对比功能矩阵中应执行的 case ID、实际发现/执行的 case ID、结果和平台清单，生成结构化判定，退出码与判定一致。
7. 保存失败证据，清理本次持有的资源；清理失败也必须报告，不能删除开发者真实日志、账号或数据库。

macOS 支持矩阵由受版本控制的配置定义，至少验证最低受支持系统与当前支持系统、arm64 与 x86_64；生产发布验证本版实际目标数据库，v0.1.0 为 SQLite，真实生产库只做非破坏性就绪/备份检查，隔离同构副本执行恢复及完整业务链路。未来迁移至 MySQL 时另增该引擎和迁移矩阵。每个平台都需要对应机器的原生结果，不能用主机名称或编译目标代替执行。

0.1.0 随账号链路交付最小签名更新器。首次没有上一稳定版时，记录历史基线不存在，验证候选干净安装，并从候选 App 更新至隔离源中的受控高版本签名测试包；记录测试包来源、版本、摘要和独立预期，不将其冒称历史公开版本。自 0.2.0 起每次发布验证上一对应profile稳定版→候选的真实 App 内更新。0.10.0 完善更新体验，不作为首次加入更新器的时间点。开发阶段可用隔离临时自签名包；默认更新源 `http://127.0.0.1:49177/appcast.xml` 只在App所在Mac上服务，固定EdDSA公钥、坏签名拒绝和下载URL边界仍须真实测试；内部发行阶段必须另验无测试路径的最终 DMG、实际 Gatekeeper 行为、包级 E2E 与机器通行证，公开发行另验 Developer ID/公证包。任一分发凭据不作为开始编码的前提。

## 产品通过报告必须绑定的证据

正式产品报告在当前 schema 基础上扩展，至少包含：

- 统一 release ID、唯一 run ID、阶段、起止时间、可信 runner/CI job 身份。
- 干净源码 commit、产品版本、客户端和服务端构建物 SHA-256。
- 功能清单/用例清单摘要、fixture 清单摘要、生成器版本、种子、固定时钟、数据集版本。
- 每个 OS/架构/数据库环境、工具链版本和实际执行命令/退出码。
- 预期用例列表与实际用例结果；零失败、零跳过且集合相等。
- 原生测试报告、日志、截图附件、升级/恢复记录的位置与 SHA-256。
- `distribution_profile`、对应签名/Gatekeeper 结果；public 另含公证校验，以及最终 `PASS/FAIL/BLOCKED`。

校验器必须验证本次进程确实产生原生报告、结果可解析、文件摘要匹配、运行时限有效。单独一份 JSON 中的 `passed: true` 不构成证据。只有受保护 CI 使用相同候选最终包产生的结果才可用于正式内部或公开分发；本机报告用于开发诊断。

报告不包含真实凭据、对话和代码正文。失败与通过证据保存至少 90 天，发布证据按版本长期保存。仅验证通过的受保护 CI 可生成 `<release_id>.passport.json` 发布通行证，绑定全部证据并作为同名 Git Release 资产保存；源码中仅保存计划及索引，避免 commit SHA 自引用。详见 [版本规范](versioning.md)。

## Git、CI 与发布权限

- [常规工作流](../../.github/workflows/quality.yml)在 PR、主分支更新和手动触发时执行规范与 iteration 门禁，不依赖版本 Tag。
- [内部发布工作流](../../.github/workflows/internal-release.yml)执行 preflight→单次生产构建→两平台安装回归→原件父门禁→自动Git发布，全部使用同一候选SHA和run/attempt。代码签名与EdDSA私钥只交构建step，写仓库权限仅交发布job；测试job无私钥。发布前后都读回远端状态与摘要。
- [公开候选工作流](../../.github/workflows/release-candidate.yml)通过默认分支的 workflow_dispatch 接收完整 `candidate_sha`，checkout 该提交并验证 HEAD、干净工作区及同名正式 Tag 尚不存在，再执行 release 门禁。配置 `release-validation` 环境、只读仓库权限，不包含签发或分发能力。当前原生入口仍返回 BLOCKED。
- [candidate_gate.py](../../scripts/candidate_gate.py)的 PASS 仅表示候选身份与触发上下文有效，`release_eligible` 始终为 false。它不替代产品门禁、可信 CI 证明或远端保护配置核实。
- **工作流文件不等于已生效的分支保护。** 需要在远端配置 required checks、禁止跳过检查，并保护发布凭据；2026-09-30 已通过GitHub API配置并读回master的governance和两平台product-e2e必需检查、管理员不可绕过、禁止强推/删分支；release-validation环境仅允许master部署，证据见版本06记录。稳定内部签名和EdDSA私钥已保存该环境，只有构建step取用；最终包仍须逐候选真实验证。
- 发布任务必须依赖同一提交全部 required checks 成功，取已验证构建物进行发布，不能通过后重新构建另一包。
- appcast、安装包和服务端部署凭据仅供受保护发布任务使用。开发/PR 测试任务无这些凭据。
- 不允许手工上传包或改 appcast 绕过门禁。热修复执行相同规则。
- Git tag/Release 和 Changelog 二级标题使用同一 release ID，档案可查询需求→拆解→开发计划→测试计划→发布预案→实际证据/通行证。tag、源码、产品版本、构建物和测试报告对应同一候选提交；源码或依赖变化后重新执行门禁。

内部发布程序按本轮设计建立并受原始证据约束，实际是否发布以状态页和通行证为准；公开Developer ID/公证缺失只阻断public profile，不能误用其条件阻断已明确的内部发行。

手动工作流需先存在于默认分支；本仓库额外检查实际触发引用必须是默认分支。相关平台行为见 [GitHub 工作流触发文档](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。环境名称不代表已启用保护，发布前必须按[环境保护文档](https://docs.github.com/en/enterprise-cloud@latest/actions/reference/workflows-and-actions/deployments-and-environments)核实配置并归档证据。
