# v0.2.0-20261001T034118Z — 执行记录

## 2026-10-01 新仓库恢复时的目录治理

新本地主仓库基线 `8f6cac8` 尚未包含旧文档树已验证的跨版本来源校验修复。非SOP资料及0.2当前指针迁入独立文档树后，首次完整治理452项中10项ERROR：9项来自 TM-001 父TC/变体仍按顶层0.2 release解释，另1项为该新工作树尚未安装锁定 Playwright 依赖；原始日志 `.local/docs-checks/20261001-recovery-migration/governance.log` 保留。文档会话仅恢复旧候选中的 `scripts/granular_gate.py`、`scripts/granular_test_result.py` 及其两份治理负测，再于本树执行 `npm ci`，随后治理457/457 PASS，原始日志 `governance-after-fix.log`。本轮结构、当前0.2基线、质量追踪、机器用例与根Excel回读也PASS。该恢复只使文档/目录治理可核，不更改TM-002产品E2E的AX/测试账号BLOCKED和正式发行NOT_RUN。

## 2026-10-01 开发工作树后续交接

开发会话报告主进程原生目录面板、当前用户私有加密 locator、根 FD 受限读取、React 授权 UI、0.2 开发 helper 打包检查已实现；固定产品 E2E 已编码 33 个叶入口，其中 28 个可执行入口和 5 个场景摘要父项。其工作树报告桌面构建 PASS、Node 单元 59/59、治理 473/473、结构/基线/质量追踪 PASS。文档会话所处独立树未合入这些源码，不能据报告将本树机器绑定标 ready，固定 TC 的产品 E2E 因 AX `trusted=false` 与隔离标准测试账号缺失保持 BLOCKED，最终 DMG Keychain 实证亦未取得。开发会话另保存源码快照 `.local` 之外的 `tm002-source-rescue-20261001T1433Z.tar.gz`，SHA-256 `969afaa1544546a3fba88fd44d5c3a683e97dd0b027befb6e6b08ef14bf9a435`；这只保护普通文件，不是可读回的 Git 提交。主 Git 对象库路径当前不可见，提交/tree 和整合均待恢复。根据用户新阶段决定，本版开发按已固定功能 TC 回归，完整跨需求 E2E、SOP-018/020 与稳定原包只在用户启动正式发行后执行，现记 `NOT_RUN`，不改历史失败。

## 公开构建配置设计（2026-10-01）

文档会话新增[本版local-release配置](local-release.json)，设计值为0.2.0/build200、受控高版0.2.1/build201、macOS15 Intel、沿用当前0.1公开bundle ID/API/更新源/公钥/证书指纹；声明上一实际稳定原包来自`v0.1.0-20260929T074814Z`且必须有SOP-018 PASS与SOP-020归档读回。配置纳入机器manifest、文档目录及项目总表来源。当前`local_package.py`硬编码0.1/schema1/build100/101，桌面开发入口读取0.1配置；0.2尚需固定程序扩展及负测，再绑定0.1最终稳定原包的实际身份。本次仅形成构建设计，未生成0.2 DMG或产品PASS，0.1正式稳定源与Keychain原生隔离仍缺。

文档工作树接入未来版TM-004/005源草稿和机器用例后，执行`python3 scripts/check_docs.py --mode structure`及`--mode baseline`均退出0、PASS，134份登记文档、1190条链接；严格基线仅针对当前0.2，未来0.4/0.5仍为draft。`python3 scripts/quality_gate.py check`退出0、`release_eligible=false`，`python3 scripts/export_test_cases.py --check`退出0，216父TC/685父步骤（含未来版52条细TC），根项目总表回读PASS、11 Sheet、216父TC/41变体/257行、13个历史批次，SHA-256 `acfd57a242d6e8c6108f20404925bb80e7d4fee450d9a101abc8852ed6e35e3f`。本轮仅验证文档设计一致性，不执行TM-002/004/005产品E2E。

## SOP-001 立项（2026-10-01）

- 输入：用户指定 `REQ-TM002` 独立会话开发；上版为未发布的 `v0.1.0-20260929T074814Z`，其完整产品 E2E 仍 FAIL/BLOCKED。用户将 REQ-TM003、REQ-TM005 分至独立会话。
- 决定：按一个功能一个版本分配 `v0.2.0-20261001T034118Z`，仅纳入 `TM-002`；本分支为 `codex/v0.2.0-20261001T034118Z/permissions`。版本档案为草稿，产品结果仍未执行。
- 源码基座：独立工作树从 `6e80dd12d60ee5dad641bca030445a2153a269c9` 建立，并复制了 TM-001 主工作区 281 个稳定文件的本机快照；来源中有未提交文件，不能作为锁定候选。快照收据位于本工作树 `.local/planning/tm001-source-snapshot-20261001T034118Z.json`。
- SOP-024 结构检查：`python3 scripts/check_docs.py --mode structure`，退出码 0，`PASS`，108 份登记文档、898 条链接；原始命令/输出见 `.local/planning/tm002-sop001-structure.json`。这只证明草稿结构，不证明需求基线或产品通过。
- 下一步：按 SOP-002 明确授权边界。TM-001 基线未锁定前，只推进不依赖其产品 PASS 的设计与准备。

## SOP-000/002 待决冲突（2026-10-01）

- 已核对非 MAS Electron 原生目录选择器不返回安全作用域书签，而现有本地 DMG 构建和 TM-001 原生更新器均按非 MAS 运行。既有“真实系统授权/撤销”不能直接解释为 macOS 沙盒的逐目录持久授权；依据与备选方案在[需求草稿](01-requirements.md#已确认的授权模型与本地存储边界)。已向用户提问，待决定后按 SOP-000 同步相关规范/用例。
- 重启恢复已选目录与“不保存完整本机路径”存在定位信息冲突，须在需求/隐私规范中限定本机 locator 形式与保存范围；不得把完整路径写入用量、同步、诊断和证据。已向用户另问是否允许当前用户私有可解析目录书签并在撤销时删除；未解决前不将需求或后续文档标为 baselined。

## SOP-003–007 草稿与结构检查（2026-10-01）

- 已将 `REQ-TM002` 拆为三个功能点、九项具体 TASK，并在 04-test-plan.md 暂列 23 条逐 TASK TC；详细用例、数据程序和执行器仍待编制。采集意愿与未来同步意愿按独立布尔值设计：`false/true` 表示已确认但暂停采集，不能因未来同步意愿为 true 就读取或上传。
- 05-release-plan.md 已登记上一实际稳定包升级、最终 DMG 安装、TM-001+TM-002 完整 E2E、原始证据与本机门禁、失败停发和恢复要求。此为发布**预案**，不是发布结果；上一稳定包和 TM-001 当前完整回归仍缺。
- `python3 scripts/check_docs.py --mode structure`：退出码 0，`PASS`，108 份文档、924 条链接，原始输出收据 `.local/planning/tm002-sop007-structure.json`。SOP-008 的 `--mode baseline` 与 `quality_gate.py check` 尚未作为 TM-002 基线执行；授权语义、locator 规则、候选枚举与逐条 TC 未定，结构成功不能解除阻断。
- 用户另外设立 SOP 会话负责 SOP 新增/修改/删除。本会话已向其登记授权和路径持久化的规范冲突；答案确定后由 SOP 会话按 SOP-000 修订，TM-002 再同步需求、设计与用例。开发总控已获知本分支只有草稿与未锁定 TM-001 源码快照，不作为可集成候选。

## SOP-002 授权模型决定与追踪修订（2026-10-01）

- 用户明确选择：“用 macOS 原生目录选择器，由 App 持久保存所选目录并强制限制读取”。本版验收是实际系统面板调用、App 主进程选中根 allowlist、明确同意、App 内撤销与访问失效停读；不声明 macOS App Sandbox 持久 security-scoped grant 或 TCC 撤销。原“真实系统授权”文案已开始在产品定义、`tests/acceptance.json`、矩阵、需求和技术设计同步改写；SOP 入口由 SOP 管理会话统一按 SOP-000 修订。
- 候选预览规则已按技术设计固定为所选根内递归普通 `.jsonl` 的语法候选，最大深度 8、候选 1000、目录项 5000、2 秒，超限显示不完整；原生日志格式兼容由 TM-003/004 验证。详细用例草稿新增 Claude Code 与边界检查，现为 26 条父 TC、16 条稳定变体；时间截止由辅助单元用例验证，不充当真实 App E2E。
- 另问用户是否允许当前用户私有的可解析目录书签以支持跨重启恢复。答案及 SOP 隐私规范尚未确定，所以本文档与发布仍是草稿，未执行产品测试或 SOP-008 完整基线检查。

## SOP-002–006、024 授权与用例设计收敛（2026-10-01）

- 本节记录前面“待决”段落之后的实际进展，不回写当时记录。用户已明确要求原生目录选择器、App 持久保存所选目录并强制限制读取；由此确定必要 locator 只在当前用户 0700/0600 私有来源记录中以系统密钥加密保存，撤销删除，密钥不可用/解密失败/根身份不符均停读要求重选。SOP 管理会话已将有限存储边界同步到 SOP-002/004/006；新的隔离回归 Keychain 证据要求已在其后续 SOP 修订中确定，尚待本工作树同步和基线复核。App 撤销和访问失效仍不声称为沙盒或 TCC 权限变化。
- [详细 TM-002 用例](../../docs/testing/cases/02-TM-002-permissions.md)现设计 28 条父 TC、30 个稳定变体；其中 20 条父 TC 属安装后产品 E2E、8 条为辅助检查。`tests/test_cases.json` 已有对应 28 条父记录和 30 个变体；本轮据此更新 02/03/04 计划，并将版本 manifest 的 `traceability` 重建为 37 条不重复的需求/任务/组或父 TC 关系、30 个唯一测试 ID。根 `TEST_CASES.md` 与项目总表的最终同源回读仍由后续同步步骤完成；本节没有产品运行结果。
- 技术设计将 UI 的 1000 候选/5000 目录项/2 秒截断与内部最多 256 项一页、稳定树穷尽后才完整的能力分开。对 1001 个可完整读取的候选须按相对名称 UTF-8 字节序先确定前 1000 项，不能按 `readdir` 偶然顺序截取。主进程目录访问设计为同 UID、随最终 App 打包签名的最小 C helper：私有 stdin 交根，目录描述符相对 no-follow 枚举/打开，控制 stdout 仅相对名/元数据/错误码。此时只是设计，helper 和竞态拒绝尚未实现或实测。
- 测试 profile 的稳定派生 App 名称只是异步 `safeStorage` 隔离方案；同一最终 DMG 在首次调用前必须用受控证据确定实际 Keychain item 身份、签名访问边界及测试项此前不存在，并证明与正式 App 项分离。不能依据同步加密源码推定异步实现；不得查询或修改正式密钥项。未取得证据时相关产品 E2E 为 BLOCKED。
- SOP-024 结构检查：`python3 scripts/check_docs.py --mode structure` 退出码 0，`PASS`，108 份登记文档、984 条链接；原始输出 `.local/planning/tm002-sop024-release-docs-structure.json`。`git diff --check` 退出码 0。该结果仅证明本阶段文档结构，不表示 SOP-008 基线、产品 E2E 或发行门禁通过。下一步同步本工作树的最新 SOP、生成/回读机器用例和总表，执行 SOP-008 语义及机器基线检查，再依 SOP-009–014 推进可重复测试与产品实现；TM-001 上游有源码候选但未有可用于本版升级的已发布稳定 DMG。

## SOP-008 只读语义审阅后的计划修订（2026-10-01）

- 审阅发现已确认来源缺少后续意愿修改入口。03 设计补 `updateSourceConsent({sourceId, collectAllowed, syncIntent})`：只允许当前验证过的 origin/account/tool/sourceId 原子更新，失败保留旧值；关闭采集须取消旧扫描及待提交刷新，重新开启前复核身份和根。02 任务和 04 用例摘要同步了关闭/重开的判据；同步意愿变更仍不在 TM-002 发起上传。
- 同一 origin/account/tool 限一个已确认根。健康旧根上可暂选新根，但系统面板取消、预览失败或新根已加密后私有记录原子提交失败时健康旧根、意愿和读取能力不变；系统密钥整体不可用或旧密文解密失败则旧根也停读；新根只有密文及记录原子提交成功才替换旧根并使旧扫描失效。`needs_reselect` 允许主动撤销，删除残留密文。详细与机器用例正在增补 `SELECT-02#REPLACE_CONFIRMED`、`STORE-01#WRITE_FAIL_KEEP_OLD`、`CONSENT-04#TURN_COLLECT_OFF_ON` 和 `STATE-01#NORMAL_RESTORE/#CORRUPT_LOCATOR`；目标集合为 28 条父 TC、35 个稳定变体。此处是计划与用例设计修订，未将其写成已运行 PASS。
- 05 发布预案纠正 0.1→0.2 升级预期：0.1 旧版没有 TM-002 来源记录；实际验收应保留 TM-001 合成账号/配置、经 `/v1/me` 再验证身份，进入 TM-002 `none`，然后在新版真实选择、确认、重启恢复。旧稳定 DMG 当前缺失时该升级链路仍 BLOCKED；不能要求恢复旧版不存在的来源。
- 已将同一最终 DMG、异步 `safeStorage` 首次调用前取得实际测试 Keychain service/account、目标项不存在和签名访问边界证据列入 03/04/05。确定性派生的测试运行时 App 名称只是待原生验证的隔离机制；缺证据不运行依赖密钥的产品 TC，不读取或修改正式 App 密钥项。结构/基线检查及详细用例最终计数待全部文档与机器清单同步后重跑记录。
- 分页算法进一步锁定为 helper 持根 FD、按相对名 UTF-8 字节序逐级遍历，记录每个已遍历目录的 dev/ino/mtime/ctime 纳秒快照；每页与宣布完整前安全重开逐项复核，变化或不可复核即使旧游标 invalid/incomplete。`ACCESS-06#TREE_CHANGED` 的计划负测改为第一页后在已返回范围内真实插入早排序候选，专门证明不会漏掉跨页新增项。内部 `openCandidateReadOnly` 仅在 helper 验当前令牌/身份/目标 dev+ino 后通过主进程私有有界流交字节；TM-002 本身不读正文。本轮仅记录设计及拟定负测，未运行 helper 或产品 E2E。

## 文档会话接管与稳定升级前置（2026-10-01）

用户指定所有非SOP文档（包括根项目总表和逐批测试结果Excel）由“文档”会话统一编写，原TM-002会话保留源码、固定数据/测试程序和原始结果的开发职责。文档会话从该需求工作树接管01–06、详细用例、机器目录、验收/数据/矩阵和总表草稿；没有从旧工作树继承产品通过结论。已确定的三功能点、九TASK、28条父TC和35个变体保留，完整动作/预期与DB/重置写在详细用例和机器目录，自动化绑定仍为null。当前0.1门禁优先，`releases/current.json`保持0.1；本版档案及详细用例在`docs/catalog.json`保持draft，28条父TC仍为`baseline_pending`/`unexecuted`，待0.1稳定前置及本版SOP-008内容基线后再切换当前版本。本版产品E2E、最终DMG与发布门禁均未执行。

SOP-only `090d808`及总控本地`master`整合 `c6729ea`确定顺序：0.1在本地`master`固定不可变里程碑并完成同树最终原包全量E2E、SOP-018门禁PASS及SOP-020归档后，才存在供本版真实升级的本机正式稳定0.1 DMG；远端源码登记和Tag可等全部目标版本完成后统一办理。独立`d2db551`候选的门禁PASS不能代替上述里程碑、正式原包和归档。`TC-TM002-DELIVERY-01`须核对上一稳定原包摘要、通行证、归档、来源SHA/tree及0.1→0.2真实App自主升级；当前缺上一稳定原包，保持BLOCKED。0.1版没有TM-002来源记录，升级后初态为`none`，须在新版真实选择、确认并重启后才恢复本版密文来源。

TM-002开发会话报告的隔离调查指出：仅改变profile或创建私有签名keychain，尚不能证明最终DMG的异步`safeStorage`写入独立Keychain命名空间；当前未取得独立macOS测试账号，也没有最终包原生item身份、签名边界和首次调用前不存在证明。该调查没有访问用户Keychain item，仅为执行风险输入，不是原生探针PASS。SOP-009第5步及所有依赖该密钥隔离的产品TC继续BLOCKED，直到受控测试账号或另一个经最终包实测证明的隔离方案具备。签名用临时keychain不等于产品存储目标。

文档会话在独立整合树仅做规范检查：`python3 scripts/export_test_cases.py --check`返回CURRENT（137条父记录、437个父步骤；TM-002另有35个带有序步骤的固定变体）；`python3 scripts/check_docs.py --mode structure`和`--mode baseline`均PASS（110份登记文档、1028条链接，其中7份TM-002文档仍为草稿，严格基线只核对当前0.1）；`python3 scripts/quality_gate.py check`PASS、`release_eligible=false`；治理回归447/447 PASS，原件`.local/docs-checks/20261001-tm002-draft-and-milestones/governance.log`。根项目总表导出与回读PASS：11个Sheet、137条父用例、35个变体、172行用例、12次TM-001历史批次，SHA-256 `670e0a4c6185f8f038744b81a341168d6aed3c37e19eb657919c1fe11cb738f0`，回读收据`.local/workbook/verification.json`。这些检查未执行任何TM-002产品E2E，不构成本版SOP-008基线或发布资格；实际总表文件随本轮文档提交锁定，后续若再修改须更新上述摘要。

## 稳定原包消费者和Keychain执行阻断补充（2026-10-01）

总控已将TM-001里程碑归档校验代码`fbab99b`合入本地`master` `4bdeb13`。后续实际0.1归档使用schema2 `release-index.json`，含`milestone_sha/tree`、`master_tip_sha`、`remote_source_state=PENDING`和DMG/manifest/passport摘要；当前尚未产生由最终整合树门禁PASS的稳定原包。本版`TC-TM002-DELIVERY-01`及测试/发布计划已增固定消费者和负测：拒绝旧schema、开发/候选包、错误里程碑或摘要；只有读回原件、签名、通行证及真实App自主升级均符合，才可把它作为0.2升级源。消费者代码与程序绑定由TM-002开发会话负责，现未交付或执行，故该项仍BLOCKED。最终包异步`safeStorage`测试项身份探针也缺隔离macOS测试账号或实测独立命名空间；本版Keychain相关E2E保持BLOCKED。本轮只是计划与机器用例同步，不增加测试运行批次。

文档分支随后合入含里程碑归档校验的本地`master` `4bdeb13`并重跑检查：治理454/454 PASS，原始日志`.local/docs-checks/20261001-tm002-draft-and-milestones/governance-after-milestone.log`；structure、当前0.1的baseline、quality、用例导出一致性、总表回读和`git diff --check`均退出0，同目录`*-milestone.log`留原始输出。总表最终SHA-256为`670e0a4c6185f8f038744b81a341168d6aed3c37e19eb657919c1fe11cb738f0`，仍是172用例行/12历史批次。以上只是文档/治理检查，TM-002草稿未取得SOP-008本版基线或任何产品PASS；未来代码与最终包还须另按SOP运行。

## SOP-008 独立 0.2 文档基线（2026-10-01）

- 输入与决定：总控要求缩短 TM-002 开发关键路径，先在独立文档分支形成 0.2 设计基线，同时让本地 `master` 的 0.1 最终候选继续门禁。SOP-008 的前置是 001–007 计划与可验收逐条用例齐全；0.1 本机稳定原包是本版真实升级和发行的执行前置，不是 0.2 设计内容核对的前置。Keychain 原生隔离是依赖测试运行的前置，设计已写明证据与失败判据，尚未获得该证据。本分支把 `releases/current.json` 切至本版，仅供独立设计基线检查，不改变总控的 0.1 最终候选。
- 首次切换后 `scripts/export_test_cases.py` 检出历史 TM-001 的 78 条父用例未显式归属 0.1，默认落入当前 0.2 manifest；补齐每例 `release_id=v0.1.0-20260929T074814Z` 后，又检出 45 个早期 `source.heading` 只存 ID 而非原文完整标题。逐行核对原详细文档后补齐精确标题；未修改 TM-001 的动作、输入、预期、结果或既有原始证据。第二次导出返回 `GENERATED`，后续 `--check` 返回 `CURRENT`。这个跨版本目录问题及修复记录在[复盘](../../docs/retrospectives/2026-10-01-development-and-governance.md)。
- 语义核对：本版 3 功能点、9 TASK、2 场景组、28 条父 TC（20 条安装后产品 E2E、8 条辅助）、35 个稳定变体与 37 个 manifest 任务/用例链接双向一致；每条父 TC 有具体 TASK、AC、输入、有序步骤、逐步预期、DB 操作或不适用理由、数据/重置与证据计划。28 条父 TC 及两组摘要的设计状态由 `baseline_pending` 改为 `baselined`，执行状态仍为 `unexecuted`，绑定仍为 null；manifest 的 `program_bindings_status=planned`，本版产品 E2E 未运行。语义核对输出在 `.local/docs-checks/20261001-tm002-baseline/semantic.log`。
- 机器检查：`python3 scripts/check_docs.py --mode structure` 退出 0、PASS；`--mode baseline` 退出 0、PASS，110 份登记文档、1030 条链接；`python3 scripts/quality_gate.py check` 退出 0、PASS，明确 `scope=traceability_only`、`release_eligible=false`；`python3 scripts/export_test_cases.py --check` 退出 0、CURRENT，137 条父记录/437 个父步骤。原始输出分别在 `.local/docs-checks/20261001-tm002-baseline/{structure-final,baseline-final,quality-final,export-check-final}.log`。此处的 SOP-008 结论仅为设计基线，不是产品实现、E2E 或发布 PASS。
- 完整治理回归另执行 `python3 -m unittest discover -s tests/governance -p 'test_*.py'`，退出 1，452 项中 9 项 ERROR。旧 TM-001 治理测试的变体合并/结果模型仍将顶层当前 `catalog.release_id` 当成 TM-001 的 0.1 来源；切至 0.2 后与历史变体 manifest 冲突。原始失败在 `.local/docs-checks/20261001-tm002-baseline/governance.log`，已交 TM-002 开发会话修代码并回归；不能将此候选称为完整治理全绿，依赖程序执行继续阻断。
- 根项目总表按当前 0.2 基线重新导出并回读：11 个 Sheet、137 条父用例、35 个变体、172 行用例、12 个历史 TM-001 批次，SHA-256 `d4dad13552db7b42a99f1f513617194f6a678339e53dde6ea606908886975fa5`；回读为 PASS、`product_tests_executed=false`、`release_eligible=false`，原始收据 `.local/docs-checks/20261001-tm002-baseline/workbook-verify.log`。没有新增 TM-002 测试批次，也未重写历史结果 Excel。
- 下一步：TM-002 开发会话可据此完成不依赖稳定 0.1 原包的 SOP-009–012 准备、数据和固定测试。真实 Keychain 隔离证明缺失时相关用例 BLOCKED；0.1 正式稳定原包缺失时真实升级/发行用例 BLOCKED；最终整合候选仍须按 SOP-013/014/017/018 全量验证。

## SOP-019 远端代码检查点与本版状态（2026-10-01）

SOP 会话以提交`1bc01e38e8de5ab2786a2b5207dbaff434206156`修订SOP-019至11；文档会话在独立树同步了需求worktree/同名远端功能分支的干净WIP/候选快进保存、可选单一integration镜像，以及逐版本地稳定包后才最终登记远端`master`与Tag的四种状态。本版文档基线提交`aa9b74219b105d1b7edc319e2b3aad98e70bae42`只在本地形成，未据此推送0.2远端功能分支；`remote_code_saved`、0.2产品E2E、0.2本机发行、远端`master`及Tag均未记完成。0.1最终包门禁在总控固定本地里程碑运行，文档分支不回写其被测树。TM-002固定程序、隔离Keychain证据和上一0.1正式稳定原包缺项仍按各自依赖阻断。

## 跨版本治理错误修复及上游门禁结果（2026-10-01）

上文记录的 452 项中 9 项 ERROR 保留为首次原始失败。TM-002 开发会话提交 `ca0c43b` 修复历史 TM-001 父 TC/变体的显式来源校验；文档树在完成非 SOP 文档/Excel 提交 `bce7902` 后拣选为 `dcf215f`，只涉及两份治理脚本及两份回归测试。相同独立树执行 `python3 -m unittest discover -s tests/governance -p 'test_*.py'`，退出 0，457/457 PASS，原始日志 `.local/docs-checks/20261001-remote-checkpoint-docs/governance-after-ca0.log`。这仅解除本树的跨版本治理程序错误；0.2 固定产品程序与隔离 Keychain 证明仍按前述状态分别检查。

总控交接的 0.1 本地 `master` 首次最终包门禁 `c2911bc` 为 FAIL；文档会话只读核对其 `gate.json` 与精细原件，UPDATE-05 的 13 个变体缺签名输入而失败。0.1 本机稳定原包仍不存在，本版 `TC-TM002-DELIVERY-01` 真实升级依赖继续 BLOCKED。该失败批次已在 0.1 版本记录和根项目总表单独登记；不改变本版 `unexecuted`、`release_eligible=false`。

TM-002 开发会话后续交接：0.2 实现工作树完整治理 460/460 PASS，原件 `.local/ci/tm002-governance-cross-release.log`（在该开发工作树），SOP-008 baseline/quality PASS；已准备 SOP-009 本机工具链和锁定依赖，桌面基线构建 PASS、Node 单元 26/26、服务 pytest 55/55。来源存储、native helper 和 E2E 固定代码仍为未提交 WIP，尚无可交接干净候选 SHA/tree；Keychain/AX 隔离仍 BLOCKED、产品 E2E 未执行。以上为开发会话检查事实，不宣称本树执行过这些构建或测试。
