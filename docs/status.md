# 当前状态

当前功能版本：`v0.1.0-20260929T074814Z`，TM-001 账号登录与最小更新器。上一基础版本已通过 PR #1 合并为 548c582。本页记录实际结果；接手工作第一步仍是读取 [SOP 总索引](../sop/README.md) 及对应独立文件。

## 最新状态（2026-09-29）

- 用户指定 v0.1.0 服务端用 SQLite；本机已实际建立 `database/test/test.db`（Codex 回归，四个 `test-*` 账号）和 `database/production/production.db`（用户使用，仅 `admin / 123456`，首次登录强制改密），两份 SQL 位于各自目录且 DB/SQL 均不提交 Git。[数据库说明](../database/README.md)含路径、造数和启动命令。生产库只读检查通过；在隔离副本上经真实认证 API 验证初始登录与强制改密标志，原生产库没有测试会话。
- 数据库检查现要求测试库和生产库同时存在，缺任一库直接失败；本机预览服务只接受回环绑定。43 项服务端回归覆盖缺库阻断、服务实例重启后的密码/成员保留与两库隔离。固定测试库供 Codex 本机回归，原生 E2E 使用逐例临时测试库，避免修改固定库或用户生产库。
- `/Applications/TokenMeter.app` 是已安装的 `.UITesting` 本机预览 App，内置服务地址 `http://127.0.0.1:49176`。当前生产 SQLite 服务已在同一回环地址启动，`/v1/health` 返回 200，App 进程已启动；用户可用该预览 App 登录生产库。后续 CI 预览 DMG 也固定同一端口。该服务随本次本机进程停止，重启命令见数据库说明。正式 App 需要 HTTPS，预览 App 的临时签名和配置不代表发布验收。
- 本轮增加 AC/E2E-TM001-005，要求在**临时生产库**上由原生 App 验证 `admin / 123456` 的首次改密和库隔离。原生 runner/Swift 用例已编写并通过治理合同检查，必测集合为 001、002、003、005、004；本机只有 Command Line Tools，最新本机 `iteration` 仍为 BLOCKED、原生执行 0/5。旧候选两平台 001–003 的 3/4 结果只属于旧提交，不能视为本轮五例通过。
- 正式 DMG 的预检/签署/公证/装订/镜像核验程序已建立；本机预览 App 被正式预检正确拒绝。尚无 Developer ID 签名的正式 App、公证凭据及真实正式 DMG。004 升级环境、最终安装包全量原生 E2E、macOS14+ 双架构矩阵和受保护 CI 通行证仍缺，PR #2 保持草稿，v0.1.0 无正式 Tag/Release，发布为 BLOCKED。

## 0.1.0 实际流程进展

- 已按001建立版本、分支、00–06草稿，按002–007逐步编制并执行structure；008基线与追踪检查已通过（68份文档）。[本轮档案](../releases/v0.1.0-20260929T074814Z/00-manifest.json)保存完整任务/API/测试与发布计划。
- 实际发现并修复001写死旧版本、019缺PR闭环两处流程缺口；记录在[执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)。
- 服务端、SwiftUI/XCUITest/Sparkle和原生runner已建立，TM-001为in_progress，五个真实测试/数据入口已绑定；原生结果尚未齐全，不宣称功能完成。
- 本机完整Xcode缺失；已在macOS15 arm64/Intel CI实际构建并执行旧四例中的001–003，004阻断；新增005需新候选验证。生产签名、全发布矩阵与受保护环境仍未具备，发布BLOCKED。

## 一致性修复完成

2026-09-29 已修复审查中的 R01–R08 和 D01，详见[审查与解决记录](reviews/2026-09-29-plan-consistency.md)。草稿编制、文档基线、程序绑定和工程骨架有各自前提；早期用例依赖、技术设计模板、最小更新器交付时间和候选 CI 顺序已统一。双向验收覆盖与完整版本合同已有负向回归；高级价格数据明确保持待实现。

## 基础版本归档结果

- 根 SOP 总索引、25 份按工作步骤拆分的独立文件；AGENTS.md 强制先索引、后详细 SOP，检查输入、验证输出和保留证据。
- 文档规范、11 份模板/模板索引、首版产品与架构设计、本轮六类档案；含本次审查报告的 62 份 Markdown 均有元数据登记。
- 基础版当时登记 12 项产品功能、34 个规划 E2E 场景；本轮补充生产首建场景后当前为 35 个，独立验收清单与产品规格、测试矩阵双向校验。
- 确定性合成用户/用量数据生成与安全重置；文档/引用检查、只读版本查询、明确阻断的产品门禁入口及 CI 工作流。
- 2026-09-29 版本档案已按 00–06 编号，索引、模板、SOP 和查询/检查程序已同步。
- 2026-09-29 最新完整基础工具回归：108 项测试通过。structure、baseline、功能追踪、版本查询均退出 0；原审查漏检及计划顺序重放 10 项均符合预期。测试覆盖数据生成与重置、Tag 快照、缺项/错引用、隐藏验收、候选 SHA 与发布前后顺序。
- iteration / release 均退出 2（BLOCKED），原生产品用例执行数为 0，无发布通行证。

以上是基础版本验证结果。远端已实际运行基础CI：master run36538259111治理检查通过，产品入口按既有阻断逻辑失败；仓库保护规则及发布环境尚未配置。本轮产品结果另行记录，基础检查不能替代它。

## 本轮实现与待验证能力

- 服务API已取得真实失败基线19失败/9通过，当前服务端回归43项通过；包含uvicorn TCP、SQLite迁移/备份、账号CLI、生产首建/SQL隔离和权限/会话验证。原生001–003已在旧候选两平台通过，当前五例验收尚未通过。
- 真实账号生成/初始化/重置已落地；原始Codex/Claude Code日志fixture按后续采集功能建立。更新fixture程序需专用Mac CI实际造包与签名验证。
- 本机缺完整Xcode；远端开发矩阵已确认macOS15.7.9、Xcode16.4、arm64/Intel。候选dcd8360两平台前三个原生用例全部通过，第四例在临时签名信任配置中中断。之后的候选在环境探针清理阶段失败，未执行产品用例；不能复用旧候选结果宣称新候选通过。完整发布支持矩阵仍未验证。
- Developer ID、公证、生产部署、GitHub required checks和受保护发布凭据缺失；临时测试签名不能替代正式签名。
- `package_preview_dmg.py`可将隔离UITesting App打成本机预览DMG并校验镜像。`package_release_dmg.py`已实现正式包的预检/签署/公证/装订与核验程序，但缺真实 Developer ID/App、公证凭据及执行证据，尚无正式DMG；现有更新helper仅构建隔离E2E用的App与ZIP。
- 本机当前 `xcode-select -p` 指向 `/Library/Developer/CommandLineTools`，未发现完整 Xcode；本机未执行原生产品 E2E。远端实际执行结果见下方CI记录。

上述缺项按依赖阻断实际运行和发布；SOP-009 的工程骨架准备，以及有独立验证条件的源码、数据、测试编写可继续。生产签名/公证凭据只作为最终包与发布验证前提。

## 证据与下一步

最新验证证据：`.local/governance/consistency-fixes-20260929T073101Z/summary.json`，保存命令、退出码、日志及工具/用例源码摘要。失败复现和重放记录位于 `.local/reviews/consistency-fix-r01-r08/`、`.local/reviews/consistency-fix-r06/`、`.local/reviews/consistency-fixes/`。详见[本轮执行与交接记录](../releases/v0.0.1-20260929T060944Z/06-iteration-record.md)。这些本机诊断文件未上传，不作为正式发布证据。

本轮接续入口：按0.1.0计划完成013/014综合回归和远端原生验证，保留首个失败并按015修复后完整重跑。源码、服务端通过和原生通过分别记录。草稿[PR #2](https://github.com/lzhe72/TokenMeter/pull/2)跟踪本轮实现，适用检查通过才合并。

原生runner和证据复核已同时实现并通过工具负测，但实际产品E2E仍需运行证明。缺环境的 `iteration` 为BLOCKED；正式 `release` 继续受最终签名/全矩阵/生产数据库与保护条件阻断。恢复条件见[发布门禁](standards/release.md)。

本轮过程证据：`.local/process/v0.1.0-20260929T074814Z/`；服务首轮红绿位于其`server/`，runner工具负测位于`.local/governance/tm001-native/`。这些本机结果不构成发布通行证。

候选dcd8360的[run36545478638](https://github.com/lzhe72/TokenMeter/actions/runs/36545478638)两个Mac平台原生001–003全部通过，004未完成。新候选0ec1c4d的[run36547335412](https://github.com/lzhe72/TokenMeter/actions/runs/36547335412)通过147项治理、34项服务、9项升级工具检查；独立环境探针已完成签名与HTTPS信任及验证，但代码签名信任撤销超时，故未运行四例产品测试。正在修复这一精准清理问题；功能仍in_progress，PR保持草稿。原始证据由CI归档，历次失败及修复见本轮06记录。

此前候选69c717d的[run36548537959](https://github.com/lzhe72/TokenMeter/actions/runs/36548537959)通过150/34/9项基础检查，两个环境探针仍未通过最后的代码签名信任撤销。当时新增原生截图尚未执行，旧四例仍不齐全，安装包与发布仍未完成。

用户已授权本机作为测试机。2026-09-29最新只读检查确认本机为Intel x86_64、macOS15.7.4、已登录桌面；xcode-select现在指向/Library/Developer/CommandLineTools，仍未发现完整Xcode.app，未运行本机原生E2E。下一步安装并首次启动Xcode16.4，按009补齐本机环境；本机升级fixture的正常授权与清理路径仍待实现验证，不能仅授权使用机器就记为环境READY。

Apple源码审查否定了临时改authorizationdb方案，未提交的helper已撤回且从未实际运行。新版环境入口在已知缺少完整清理路径时先返回BLOCKED；探针按004依赖调用，001–003可留下真实App与窗口截图。该历史候选需四例全通过；本轮已增至五例。

## 候选0a9c39e与本机预览的实际结果

[CI run36551758767](https://github.com/lzhe72/TokenMeter/actions/runs/36551758767)已完成：Apple Silicon与Intel的E2E-TM001-001/002/003各实际执行并PASS，均保存原始xcresult和按摘要绑定的候选App；关键界面由原生测试导出PNG。004在环境探针中因缺少受支持的证书授权/完整清理路径返回BLOCKED，两个平台都是执行3、通过3、完整迭代BLOCKED。PR #2保持草稿，不签发通行证。CI对应PR合成合并提交624d360，分支提交0a9c39e；各自提交标识分别保留。

用户授权的本机已从上述Intel产物按SHA256取出开发`TokenMeter.app`并实际启动；本地隔离SQLite/服务的健康检查通过，进程仍供用户预览。证据`.local/process/v0.1.0-20260929T074814Z/local-preview-36551758767.json`。此为开发预览，本机XCUITest执行数0，当前`xcode-select -p`仍指向CommandLineTools。完整Xcode安装和首次启动需用户在Apple下载/系统界面完成；之后按009/014接续。004仍需实现本机按系统正常授权并可完整清理的fixture程序，不能以本机预览代替产品E2E。

当前分支提交`6d964d2b55846ba31ebc74c928455ad502cd3963`的[CI run36553523311](https://github.com/lzhe72/TokenMeter/actions/runs/36553523311)在Apple Silicon与Intel两平台各有001–003真实原生用例PASS，004在升级环境探针处BLOCKED；完整回归均为3/4、发布资格false。治理检查通过，PR #2仍为草稿。

按SOP-017的预览诊断分支，本机制作`.local/preview/36551758767-intel/TokenMeter-v0.1.0-20260929T074814Z-local-preview-verified.dmg`，SHA256为`19ab21c41e7e943d4ebae1d7587efbb0262a91de2f995fc223502841a89463c1`。程序验证镜像与源App内容一致，随后从该镜像解包到隔离目录并启动实际App进程；另将同一来源App安装到`/Applications/TokenMeter.app`供体验。隔离SQLite服务`http://127.0.0.1:60470`健康与合成管理员登录接口成功。此包未签Developer ID、未公证，不含正式更新源；本机没有执行安装包原生UI E2E。正式017/018保持BLOCKED，不能创建Tag、GitHub Release或通行证。

quality工作流已加入Intel原生执行后生成并上传`local-preview-dmg-*` Actions临时工件的步骤，远端实际上传结果待新分支CI验证。该工件与正式Release资产分开，CI完整产品门禁BLOCKED时仍不能发布。
