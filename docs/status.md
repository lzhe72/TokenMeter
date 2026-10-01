# 当前状态

## 2026-10-02 恢复后源码与文档同步

TM-001 709d候选`SESSION`功能定向run`local-ff24478631134a96bd7d40f2bbc5e254`覆盖10父+2变体，12行/44步PASS、清理和Excel回读PASS；仅`SESSION-04`独立审计PASS，作为总表第26批次。其余TM-001功能、完整审计及正式发行仍按原阻断。


[10月1日晚至2日复盘续篇](retrospectives/2026-10-01--2026-10-02-followup.md)已将Git恢复、模块与产品报表边界、TM002预检、TM005真零、TM003大文件与远端读回等10例（RET-042–051）按问题、决策、方案、实测结果和经验逐条记录；未完成行动仍按各版本阻断状态追踪。


[项目会话体系](project-sessions.md)已逐一核对TM-003/004/005开发会话的实际ID与标题，补齐五需求开发会话、文档/SOP/总控分工及当前交接索引。旧2026-10-01队列保留为历史快照，不用其中旧数量表示当前进度。


TM-001 709d候选`CHANGE-PASSWORD`独立真实App run`local-64cdbd1050d84763928c0b6a7f30e2c3`覆盖11父+6变体，17行/32步PASS、清理和Excel回读PASS；仅`PASSWORD-05`独立审计PASS，登记总表第25批次。其他TM-001功能、完整审计、旧c291完整门禁FAIL及正式发行NOT_RUN保持。


TM-005代码候选`259cf768`的`CORE-04/05`两次独立`source_check`各1/1、三/四步、清理及独立Excel回读PASS，作为总表第23/24批次。代码同名远端功能分支已由push与GitHub API读回同SHA/tree；Git ls-remote曾因443不可达失败。测试程序尚未并入本文档树，机器目录绑定保持null；0.5产品TC、真实App/原生日志E2E和正式发行仍NOT_RUN。

TM-001同一709d候选新增`LOGIN-VALIDATION`十父/十二变体22行36步与`LOGIN-RATE`单父三步两次真实App定向PASS，独立Excel均回读，分列总表第21/22批次。四批登录任务合计22父+12变体已按各自run通过；其余TM-001功能尚未验收，旧c291完整门禁FAIL与正式发行NOT_RUN。


TM-003新增`CORE-07`主进程编排辅助输入：固定两页两文件、分块读满、HMAC键、守卫撤权与超预算安全失败；目前仅设计、程序绑定null/未执行。它不证明任意大日志或真实App/Keychain产品链路，0.3产品E2E仍NOT_RUN。

`CORE-07`干净输入提交`a3e99dafa8948cdf91d733c374d25a132dc60df2`的[SOP-008收据](../.local/docs-checks/20261002-tm003-core07-slice/receipt.json)判仅该辅助切片`development_slice_ready`；structure、治理477/477、用例233/744和总表回读PASS。程序绑定及实际执行仍空，产品和发行状态不因此改变。


TM-002候选`0cc4f3e6`的run`local-6ece8e342b514683a64d1cc0a9bf5282`在产品包预检因缺显式独立测试账号及排除账号而33/33 BLOCKED、零步骤，清理PASS，App未启动且未触及Keychain；较早格式错误的预检FAIL另存。该run没有固定导出的独立结果Excel/verification，因此根总表尚未登记批次；0.2真实产品E2E和正式发行未通过。


TM-001候选`709d2125`安装原DMG的`LOGIN-01/02/03/04/08`定向真实App run`local-2aa05fb7b2754289a1d77b9ef89bd321`为5/5、11步、清理PASS，独立结果Excel回读PASS，作为总表第19批次。前次误带`--development`的独立run在清单预检处五例BLOCKED且App未启动；其原件保留。709d其余TM-001父例未运行，旧c291完整门禁FAIL与正式发行NOT_RUN。`BOOTSTRAP-03`额外合成成员的固定provision和重启绑定已在代码核实，机器目录过时的“待补”文字已修正，未改测试预期或运行结果。

同一709d候选另一次`LOGIN-SESSION`定向真实App run`local-1d7d9238f9fd4d389e27cad990a6cb97`为6/6、14步、清理PASS，独立Excel回读PASS，作为总表第20批次；与第19批次分开保存。709d仍非TM-001全量回归，旧c291完整门禁FAIL及正式发行NOT_RUN。


TM-005新增尚未运行的`CORE-04/05`固定辅助输入，分别为IANA日界/纽约23与25小时和合成双来源SQLite同窗只读快照；0.5原32条产品TC及6变体不缩减。干净输入提交`986e0d382f5dbb09025460f5b041a0089797f213`（tree`ac5d73e5b697bc25ee9d8468dd1cc73345ff3318`）的[SOP-008切片收据](../.local/docs-checks/20261002-tm005-iana-sqlite-slice/receipt.json)判`development_slice_ready`：structure、治理477/477、机器目录232父/739步、总表11 Sheet/232父/42变体/274行/18批次回读PASS；总表SHA-256 `20c539a9ab8137ce4022f4e0bd2fb8b0d60ebd09c5929ab1cf4391a3cef0bc94`。TM-003当前coverage表不能证明任意历史当地日两来源连续完整覆盖，故TM-005产品`STATE-02/04`的真零判据和安装App E2E保持BLOCKED/NOT_RUN；切片仅允许固定辅助红测及实现，程序绑定和实际运行仍空。

TM-003 `CORE-06`先在`408ebf8`固定红测的第二步失败，修复提交`eef956b`（tree`802e6c9`）的新run`tm003-core06-20261001T182500Z`为`source_check` 1/1、四步和清理PASS；报告SHA-256 `b6a2a8586ffbb14626858263638a7f13c690e3cf5503741bd2526cda3ea24e87`，独立结果Excel SHA-256 `4bfb058e0d0d9779a90ae61ebb207bdf0f8cec2dc6d55e813e33fcd4920f49a5`，verification回读PASS。原始红/绿报告与Excel均已复制到本工作树`.local/`，根总表登记第18批次；原27条产品TC及正式发行仍NOT_RUN。

TM-004新增未执行的`TC-TM004-CORE-04/05`辅助设计：前者固定合成账号/授权源/提交端口的拒绝码、扫描中取消与隐私汇总；后者固定dev/ino来源摘要分域HMAC、三文件各自事件/诊断/游标、scope-only turn代号、异常modelId哨兵与一次SQLite事务。根总表已同步为11 Sheet、230父TC、42变体、272用例行、18批次，SHA-256 `7088db53f08bfd2391e7d93112bfa0995c7c38807eda261cb576f20dd6850525`、回读PASS；两条新辅助TC尚无程序绑定或实际运行。TM-004原20条产品TC、真实TM-002/003整合、安装App E2E和正式发行仍未通过；切片就绪判定以干净提交的SOP-008收据为准。

TM-004 `CORE-04/05`干净输入提交`33fd7c30f6d63b11a5c43820db57c7c572dc5ba0`（tree`aa644aa09314a0bbcd2b5105e60eeb1ac3e830bc`）的SOP-008收据`.local/docs-checks/20261002-tm004-trigger-slice/receipt.json`判`development_slice_ready`：structure、治理477/477、机器用例230/732、总表230父+42变体/18批次回读PASS。此结论仅允许这两条合成端口/隔离SQLite辅助模块进入固定红测和实现；程序绑定和实际运行仍空，整版0.4严格基线、原20产品TC及正式发行均未因此通过。

SOP会话已把固定模块结果导出合同提交 `4cca9188f37cd85e677234dbc405952b79de4163` 并由总控整合入新主仓库本地 `master=6bbab2ed20878fe7fd4742967982f1d0b65c6138`。文档会话按新SOP-011/013/014/024同步[总表规范](standards/project-workbook.md)、[执行模板](templates/test-execution.md)、项目登记与Excel。TM-003已有两个CORE01/02/03与一个CORE04/05独立模块批次生成并回读；另新增未执行的CORE06跨文件generation设计。TM-001的709d UPDATE-05定向父例+13变体原始PASS已由后置固定导出器生成独立Excel并回读，为第16批次；TM-002新增一条未执行的chooser见证治理变体。根总表目前11 Sheet、228父TC、42变体、270用例行、17批次，SHA-256 `7e5b566c3247c802fa1bbadad87e23b95ed1adc33451de5e344ed17d20e3c91e`，回读PASS。TM-001仍有77父TC在该定向批次范围外，旧c291完整门禁FAIL、正式发行NOT_RUN；TM-005模块Excel仍待共享runner在其候选树接通。

TM-003候选`9efc6fa9d8523f30dfc20f4cfb8282cc54f18dd0`的`CORE-04/05`原始模块run`tm003-core45-20261001T175000Z`为2/2、九步、逐例清理PASS，独立Excel及verification回读PASS，作为第17批次登记；被测机器用例摘要仍指向原CORE04/05输入`2fa3b6...`，后续CORE06设计不倒填该run。新增CORE06 fixture固定两文件各410字节及整代一次提交/失败全回滚，程序绑定null、实际未运行；0.3产品E2E与正式发行仍NOT_RUN。

`CORE-06`输入提交`ff668d0de1fef3dfc162c0d2bc71825df6425511`已按SOP-008独立判`development_slice_ready`，收据`.local/docs-checks/20261002-tm003-core06-slice-ready/receipt.json`含结构、治理477/477、用例228/725、Excel 17批次及fixture/机器用例SHA。该就绪只允许无真实授权依赖的跨文件generation模块固定红测/实现；程序绑定null、产品E2E和正式发行仍NOT_RUN。

TM-002 `EVIDENCE-01#MISSING_CHOOSER_WITNESS`已作为第七固定负例进入详细用例、机器目录与总表：删除合成picker事件的确认按钮字段并重算单项摘要后，独立复核仍必须拒绝，不能用通用弹窗冒充目录选择确认。`SECURITY-01`合成A/B继续在短`/tmp`根，测试profile另在当前用户独占私有目录，避免SourceStore拒绝world-writable祖先。0.2现有28父TC、36变体，新增变体未运行；产品E2E和正式发行仍NOT_RUN。

TM-002上述修订的干净输入提交`0c4f2604657484ae29cc601b6246bbc232e49450`已按SOP-008复核当前文档基线，收据`.local/docs-checks/20261002-tm002-chooser-baseline/receipt.json`：structure、baseline、quality、治理477/477、机器用例和Excel回读均PASS。它只确认冻结测试输入，`EVIDENCE-01#MISSING_CHOOSER_WITNESS`的程序绑定/实际运行及0.2产品E2E仍未由文档检查产生PASS。

TM-003新的`CORE-04/05`固定输入已写入[0.3测试计划](../releases/v0.3.0-20261001T034652Z/04-test-plan.md)及详细用例，fixture精确冻结410/750/1090字节偏移、原子事务故障注入、有效错键、完整LF增量与前缀MAC改写/截短；机器目录和总表增加两行，当前两例程序绑定null、unexecuted。独立SOP-008切片须先对干净文档候选做语义/结构/治理核对，不能因已有CORE-01/02/03的模块3/3而填通过；原27条产品TC继续未执行。

上述`CORE-04/05`输入提交`ba9c782da2cd24f909e26a22c77c506627a40a2f`已按SOP-008独立判`development_slice_ready`，收据`.local/docs-checks/20261002-tm003-core45-slice-ready/receipt.json`绑定该提交/tree、fixture/详细用例/机器目录SHA：structure、治理477/477、用例227/721、总表227父+41变体/15批次均PASS。只允许无TM-002授权依赖的同步事务和合成句柄游标模块进入红测/实现；两条TC实际执行仍0，0.3整版、产品E2E及正式发行均NOT_RUN。

新主仓库 `/Users/lz/文档/git/TokenMeter` 的 `master` 已将文档恢复提交 `48ca089a8569cb33ad3e97ba91b6712cc6be51d0` 集成为 `d606fbd9763447387b88f0d02a881091d0982631`；总控对该整合树执行的文档 structure、当前0.2 baseline、quality 和治理457/457均PASS。该合并只说明源码文档进入本地 master，旧仓库Git对象丢失、历史 c291 产品门禁 FAIL、各需求产品 E2E 未通过和正式发行 `NOT_RUN` 均保留。

TM-003 开发分支提交 `311deedf19d54a77e4c2d5c99eaeb3a1ea45c787`（tree `b4df51097810a44ce56118e7edce0b35e525a886`）的原始收据 `.local/ci/tm003-core-20261001/receipt.json` 报 `TC-TM003-CORE-01/02/03` 模块3/3 PASS，另有桌面单元29/29、typecheck、身份向量及治理检查PASS；初次绿测因临时目录权限失败，修正后第二次绿测PASS，原记录保留。当时的产品导出器只接受聚合报告，该批次未生成模块Excel；后续`ea6b187`新运行已由独立模块导出器完成结果表与总表登记。开发代码尚未合入本文件所在文档分支，机器用例目录中的程序绑定继续为空；产品 E2E、真实授权源与正式发行均未运行。

TM-003 更新的干净代码候选 `44379e6d8546ba3a8cef9f000a99695c6027a9d4`（tree `2df6e47f388def16618144358b5dd28d89ca5334`）在新运行 `.local/ci/tm003-core-step-evidence-20261002/` 保存三条CORE的每步实际数值、3/3 PASS、桌面29/29、typecheck/build PASS；这是独立模块验证，不覆盖旧311deed批次，也不授予原27条产品TC PASS。TM-005代码分支 `6a0f6f44096b04052ce5a0d1d4ff8939a421abd1`（tree `a7f9c40036df81f98c2cf247eb03df25833b5531`）的 `.local/tm005-core-postcommit-20261001T162401Z/summary.json` 与TAP逐步原件为CORE3/3、桌面29/29和build PASS；产品E2E执行0。两套代码尚未进入本文件所在文档树，固定程序路径暂不写成本树ready绑定；等总控整合后复核。

TM-001的本地主仓库源码里程碑`709d212`（被测tree`6309bb7`）仅执行UPDATE-05主例与13变体的一次定向候选包探针：开发会话交接原始`local-65796d0033704e3988cd7174dec93c81/result.json`报14/14 PASS、240证据文件摘要核对及清理完成，运行7分36秒。其`scope=granular_targeted_probe`、`release_eligible=false`；未执行该候选全部功能TC或完整发行门禁，后续SOP-only整合`6bbab2e`也未参与被测包。旧c291失败原件仍有效；独立Excel及总表批次索引待固定产品导出器回读后登记。

TM-003新固定模块运行`tm003-core-20261001T163807Z`基于候选`ea6b18765ce63a5b32b7de0488de5d2a4647de94`、tree`126e3f2c866d908661b651b1ee027440db0b9af1`，原始`source_check`报告列三条CORE/九步全部PASS、逐例清理PASS；固定导出器生成并回读独立结果Excel `.local/test-results/tm003-core-20261001T163807Z/TokenMeter测试结果-tm003-core-20261001T163807Z.xlsx`，SHA-256`f4a359bd7f7658992685570d90c6d88c8f5f31871b84611dbafbb82dcc3b3cff`。本轮以被测SHA在根总表新增第14批次，标`source_check`、`product_e2e=NOT_RUN`；原27条产品TC未执行。TM-004 reader CORE-01/02/03在干净文档候选`ebbcfd0`上按SOP-008独立判为`development_slice_ready`，收据`.local/docs-checks/20261002-tm004-reader-slice-final/receipt.json`的structure、治理477/477、用例目录与总表回读均PASS。开发代码分支`e52b62e`只报告reader目标9/9、桌面49/49、build PASS，后续逐步测试`816ecd8`为CORE三例3/3、桌面52/52/typecheck PASS；模块Excel尚未生成，原20条产品TC/真实App E2E继续未运行。TM-005 CORE-01已澄清为调用方传入fixture固定UTC半开界的聚合，**不验证**IANA日界换算；该换算另设辅助切片，原产品RANGE用例仍待执行。

TM-003共享runner又提交`d7c3d39ac0a007f0e16f55bbb3cfc9b15fd9fe34`，固定区分`owned_root`与`memory_only`清理原件；新run`tm003-core-20261001T165439Z`同为CORE3/3、九步、逐例拥有目录清理PASS，独立Excel回读PASS，SHA-256`51b6f476b16d255eb29caba77f447e33d4c7efb8f3030239d6b08adf4831d620`。此为第15批次及三条CORE当前最近模块运行，旧第14批次不覆盖；产品E2E仍NOT_RUN。

TM-004代码`7b5aae463a5bad78365cc0397a2a9cc45bb96c69`增加跨文件/chunk父证据与复制fork去重，开发会话保留红测并报告定向7/7、桌面57/57、typecheck PASS；TM-005代码`69d2ccff5dd65d5dd07c11dca6c2f14e79b5953a`报告CORE三例逐步原件、真实`memory_only`清理、桌面29/29及build退出0。两者均未生成可回读独立模块Excel，根总表仍15批次；原产品TC、App E2E和发行资格不受这些模块运行赋予PASS。详细原件见各版本06记录。

TM-002 `TC-TM002-SECURITY-01#ABSOLUTE/#FILE_URL/#DOTDOT`原“向业务IPC提交路径”无法唯一判定结果：`chooseSource`会忽略额外`rootPath`。本轮修订为真实业务`previewSource.selectionId`分别接收短根内B绝对路径、对应file URL和`../B/b.jsonl`，固定预期snapshot错误码`invalid_selection`且B元数据/open/read为零；这是一项文档基线输入纠错，不是产品测试通过。相关机器用例、详细文档、测试计划和Excel已同源更新。

TM-005 纯统计三条辅助 `TC-TM005-CORE-01/02/03` 已冻结合成可信事件、未知诊断和声明式覆盖输入，并在输入提交 `061c759` 上按SOP-008独立判为 `development_slice_ready`（structure、治理457/457、总表回读PASS）。原32条产品父TC及6个变体保留草稿/未执行；三条CORE程序也未绑定和执行。该判定时的根总表为11 Sheet、222父TC、41变体、263行、13旧批次，SHA-256 `4a596813f2fa99fd1473bbaacd743341f9d2ef01e3546f779327e41705b11e65`；后续TM-004辅助输入使当前总表增加三行。具体收据见[0.5执行记录](../releases/v0.5.0-20261001T034729Z/06-iteration-record.md)；其模块代码、完整双来源采集、真实SQLite/IPC/App及产品 E2E 尚不能据此宣称通过。

TM-004 另编三条已打开只读句柄的 reader 辅助 `CORE-01/02/03`，固定LF半行、1MiB限额、前缀HMAC、原地改写/截短、损坏行和未知版本的独立预期，原20条产品TC及四组摘要不变。TM-004 开发树的早期reader红0/3、绿3/3和typecheck原件属于模块检查，不给产品TC填PASS。编制时的根总表为11 Sheet、225父TC、41变体、266行、13旧批次，SHA-256 `671ed5da0024d11e9bcd9d0276d3d9d145628302b373ec483b0c536717def3cb`；后续SOP-008就绪与代码进展见[0.4执行记录](../releases/v0.4.0-20261001T040433Z/06-iteration-record.md)，当前总表以本节开头的15批次索引为准。

## 2026-10-01 当前开发阶段与证据边界

用户决定先完成 TM-001→TM-005 的源码和各功能已基线固定 TC 的实际回归。总控按依赖顺序整合本地 `master`，全部目标源码完成后按远端保护登记并读回；开发期不以逐版跨需求完整 E2E、SOP-018/020 或稳定包为整合前置。用户另行明确启动正式对外发行后，才对固定最终候选运行跨需求完整产品 E2E、适用真实升级和本机门禁，PASS 并归档后登记正式 Tag。所有开发/候选 DMG 标 `NOT-RELEASED`；完整发行门禁目前 `NOT_RUN`。功能回归的 FAIL/BLOCKED/NOT_RUN 和历史 c291 门禁 FAIL 各自保留，源码登记不转换为产品 PASS。

TM-001 开发会话提交 `9f06cb1bb2f116c87ab5543173e15c0613b60991` 修正私有签名输入；其开发检查报告治理 454 项、服务 55 项、桌面 26 项和构建 PASS，开发 DMG 摘要为 `d342c8ffa571e28aad38bc37ec682389c2c54d3791246f2a828bd85c024d523d`。其后定向 App 原件 `local-6e066...` 为 0 PASS/14 FAIL，`local-7264e...` 为 9 PASS/2 FAIL/3 BLOCKED，仍有 ENOSPC/环境及功能失败；这两个省略 run_id 的数字来自开发会话交接，完整原件需在该工作树读回后才可登记为根总表独立批次。旧 `local-883bf...` 的 14/14 PASS 只属于旧候选，不覆盖新失败。0.1 功能仍未完成回归，正式发行未启动。

TM-002 开发会话交接：已接入主进程原生目录面板、当前用户私有加密 locator、根 FD 受限读取、React 授权 UI 和 0.2 开发 helper 打包检查；固定产品 E2E 已编码 33 个叶入口（28 个可执行入口及 5 个场景摘要父项）。开发树报告桌面构建 PASS、Node 单元 59/59、治理 473/473、文档结构/基线/质量追踪 PASS。产品 E2E 因 AX `trusted=false` 且隔离标准测试账号不可用而 BLOCKED，最终 DMG 的 Keychain 实际隔离和真实产品结果仍缺。本文件所处文档树尚未整合该代码，机器功能矩阵不得提前将 0.2 绑定标 `ready`；开发树的检查不作本树或最终包产品 PASS。固定源码快照由该开发会话单独保存，恢复后的新仓库仍需核对其提交/tree并按总控顺序整合。

TM-003 的 CORE 三条仅固定无授权模块输入与预期，尚无正式程序或运行；TM-004 的纯解析器已有部分源码/单元检查但未接授权或产品 E2E；TM-005 目前为纯统计设计/代码定向检查，完整双来源产品绑定未完成。版本状态详见各版 06 记录及根 Excel。原主仓库目录及 Git 对象库曾突然不可见；总控已在 `/Users/lz/文档/git/TokenMeter` 恢复新的本地主仓库，固定 `master=8f6cac8bd8d0358dcb5eebd72df26f59fa7bf6ff`，旧对象丢失和原测试证据不被新 Git 基线抹除。文档会话在独立新工作树从逐文件验证的快照迁入非 SOP 文件并核对新 SOP，候选文档提交与TM-003切片SHA已取得，待总控整合读回。历史原件路径仅按其真实位置引用。

恢复工作树首次治理452项中10项ERROR的原始报告保留；9项是跨版本来源校验旧代码，1项是本树缺锁定Playwright依赖。恢复四个此前已验证的治理文件、执行本树`npm ci`后，治理457/457 PASS；结构、当前0.2基线、质量追踪、用例目录及根Excel回读PASS。收据位于本树`.local/docs-checks/20261001-recovery-migration/`。这些检查仅用于文档与固定目录迁移，未启动产品E2E。

## TM-003 无授权模块切片（2026-10-01）

TM-003 原27条逐项 TC 之外，文档会话新增 `TC-TM003-CORE-01/02/03` 三条辅助模块 TC，分别固定完整 LF/半行增量、累计与非法用量诊断、公开身份向量下的去重/冲突和临时 SQLite 只读核验；项目机器清单现为219父TC、41变体。它们只用于不调用 TM-002 来源能力、产品 Keychain、真实 App/服务的源码切片；程序绑定尚为 null、实际执行 unexecuted，不给原 `PARSE-01/PARSE-02/DEDUP-01/SOURCE-02` 等产品 TC 填 PASS。整版0.3仍 draft，正式数据、授权/密钥、App 与产品E2E仍 BLOCKED。详细输入与每步判据见[TM-003 用例](testing/cases/03-TM-003-codex-collection.md#无授权依赖的解析与身份开发切片)，本轮语义纠错及检查记录见[0.3 执行记录](../releases/v0.3.0-20261001T034652Z/06-iteration-record.md)。用户新指令下跨需求完整E2E与发行门禁将在其明确正式发布后执行；现阶段只按功能固定TC推进并保留既有c291/ENOSPC失败。

本切片的结构、用例目录、质量追踪、治理457/457和项目总表回读均退出0，工作簿为11 Sheet、219父TC、41变体、13历史批次，SHA-256 `ccaad4b3fcd717661259b10a69af98d85d28d73c5484b4456bc931ac022530b1`；检查收据在本树 `.local/docs-checks/20261001-tm003-core-slice/receipt.json`。当前主仓库 Git 对象库路径突然不可见，文档改动还不能提交，SOP-008切片就绪的提交SHA条件未满足，暂记 BLOCKED；已做私有只读快照并通知总控，未重建仓库或覆盖原件。以上检查不证明产品E2E。

后续按开发新进度更新项目登记并重生根 Excel，工作簿为11 Sheet、219父TC、41变体、260条用例行、13个历史批次，回读PASS，迁移候选SHA-256 `aebe4e58f29fd88fca1d043531c2999d09fa791ebd3eac9257762070e5207c47`。结构/当前0.2基线、质量追踪、用例目录和治理457/457均PASS；这些仅证明文档树内部一致，不改变任何产品结论。下段记录恢复后的切片判定。

新仓库候选 `7d77d63e30cfb25baf0b6875acdbfc92dec87ca0` 已使 `CORE-01/02/03` 的SOP-008**独立开发切片**达到 `development_slice_ready`，新收据 `.local/docs-checks/20261001-tm003-recovery-slice/receipt.json` 核对固定ID、八份输入摘要、结构PASS与治理457/457。先前“缺Git提交SHA”的阻断已解除，但仅限这三条辅助模块TC；程序和红测待实现，原27条目标TC、0.3整版draft、授权/Keychain/真实App/服务产品E2E阻断及正式发行NOT_RUN均不变。

TM-004 开发会话交接纯内存 Claude Code 2.1.126 解析器提交短SHA `f2c3972`；文档会话核实旧工作树源码与单元36/36、治理452/452日志尾部。当前支持范围限已实测主会话、原样复制fork、同ID双内容块及可核实单层Agent关系；0/0仍未知。TM-002授权、TM-003身份/SQLite、真实App逐TC与最终包未接入，改写UUID、fork-context-ref、嵌套Agent和有效零仍待原生证据。本版20条细TC仍draft/unexecuted，不记产品PASS；详细见[0.4执行记录](../releases/v0.4.0-20261001T040433Z/06-iteration-record.md)。旧对象库丢失后，开发短SHA须在恢复的新仓库重新建立可核对的提交/tree。

## 多会话远端源码检查点规范（2026-10-01）

用户要求多会话代码有远端版本检查点。SOP 会话已将 SOP-019 修订至11：每个需求独立worktree、`codex/<release_id>/<功能名>`分支，干净WIP/候选提交可普通快进保存到远端同名功能分支并读回SHA/tree；总控可选单一integration镜像本地逐版祖先链。`remote_code_saved`只说明源码已保存，不改变本机产品 E2E、SOP-018/020稳定发行、最终远端`master`受保护PR及逐版Tag状态。远端不保存DMG/ZIP、数据库、密钥、原始报告或通行证。本次是规范与文档同步，尚未据此完成任何远端功能分支推送；0.1 的本地 `master` 固定候选 `c2911bc65d55579fcf71e5ba11db87357a01a5e4` 已完成首次最终包门禁，结论为 FAIL，详见下节；本会话未改该被测树。

## TM-001 本地 master 首次最终包门禁失败（2026-10-01）

总控固定里程碑 `c2911bc65d55579fcf71e5ba11db87357a01a5e4`、tree `d4555b207b50e7cbe313b54ba9bfec1b7fdccb54` 的本机原件位于其独立整合树 `.local/gates/tm001-master-gate-c2911bc-20261001T113036Z/`。`gate.json` 为 FAIL、`release_eligible=false`；`granular/result.json` 原始 116 项为 91 PASS/14 FAIL/11 BLOCKED，其中 UPDATE-05 父项及 13 个变体因签名输入缺失失败，11 项为辅助程序占位。文档会话按固定程序生成本批独立结果 Excel `TokenMeter测试结果-local-0512d4fc44544eba97f9d1ae79cbfc37.xlsx`，回读仅证明报表一致；父 TC 模型 66 PASS/1 FAIL/11 BLOCKED，38 变体 25 PASS/13 FAIL。本次失败已交 TM-001 开发会话按 SOP-015 修复；0.1 尚无本地正式稳定包，0.2 真实升级前置仍未成立。

## TM-003 采集文档草稿接管（2026-10-01）

后续版本的源文档已由文档会话接管：TM-004有8项TASK、20条细TC，TM-005有6项TASK、32条细TC与6个稳定变体，均为未来版draft/unexecuted；当前根机器目录合计216父TC、41变体。TM-004原生2.1.126定向证据无法仅凭JSONL 0/0区分有效零和缺usage，也只覆盖一个未触发嵌套的Agent配置；TM-005语义oracle仅为固定算术输入。开发总控要求先冻结TM-003最小可执行任务/TC/接口，再推进TM-004已验证子集和TM-005纯统计合同；两版缺完整SOP-008、上游稳定原包及最终包产品E2E，不进入当前0.2门禁。

文档会话已从独立 TM-003 开发工作树接管本版 01–08/README、详细用例、机器验收/数据/矩阵/目录与项目登记草稿；27 条逐项 TC（四组 E2E 摘要）保留 `draft` / `unexecuted`，程序绑定为空。本分支当前版本仍为 0.2，TM-003 尚未执行自己的 SOP-008 基线或产品 E2E。隔离原生日志研究样例和 `identity-v1` 向量已有来源记录；其可重建基础探针不能替代正式 SOP-010 测试数据、安装后 App 的 UI/IPC/服务/SQLite 回归。实际阻断和来源见[TM-003 执行记录](../releases/v0.3.0-20261001T034652Z/06-iteration-record.md)。

## TM-002 独立文档基线（2026-10-01）

0.2新增[公开构建配置](../releases/v0.2.0-20261001T034118Z/local-release.json)：version `0.2.0`/build `200`，受控高版 `0.2.1`/build `201` 只供更新器测试；现阶段沿用0.1的公开签名身份及默认连接配置，上一正式稳定0.1原包是实际0.1→0.2升级来源。当前打包器只接受0.1/schema1、桌面开发入口也固定读0.1配置；0.2实际打包、升级和门禁在代码扩展、0.1正式原包与Keychain隔离实证前仍BLOCKED。配置是设计基线，尚无已构建0.2包。

本工作树的 `releases/current.json` 指向 `v0.2.0-20261001T034118Z`，与正在执行 0.1 最终门禁的本地 `master` 隔离。TM-002 的三功能点、九项 TASK、28 条父 TC、35 个稳定变体和七份本版文档已完成 SOP-008 内容及机器基线检查；固定程序仍为 `planned`，所有本版用例尚未执行，产品 E2E 没有 PASS，发布资格为否。实际检查与限制见[本版执行记录](../releases/v0.2.0-20261001T034118Z/06-iteration-record.md)。这份基线可供不依赖 0.1 稳定包的 TM-002 实现准备、隔离数据和固定测试绑定使用。

首次完整治理回归有 9 项跨版本程序 ERROR（452 项中），原件保留。TM-002 开发会话交付的 `ca0c43b` 已在本独立文档树拣选为 `dcf215f`；随后完整治理 457/457 PASS，原始日志 `.local/docs-checks/20261001-remote-checkpoint-docs/governance-after-ca0.log`。这解决了当前文档树的程序核对错误，不表示 TM-002 产品 E2E 已执行或可发行。

TM-002 开发会话另报告其 0.2 **实现工作树**治理 460/460 PASS、SOP-008 baseline/quality PASS、桌面构建 PASS、Node 单元 26/26、服务 pytest 55/55；治理原件在该树 `.local/ci/tm002-governance-cross-release.log`。来源存储、native helper 与 E2E 代码仍在开发且有未提交 WIP；Keychain/AX 隔离与产品 E2E 未满足，以上开发检查不移作本树或最终包产品 PASS。

0.1 正式本机稳定原包仍是 0.2 真实自主升级和发行的前置；最终 DMG 的异步 `safeStorage` 测试 Keychain 项身份及隔离也未获原生证明。依赖这两项的实际运行保持 BLOCKED，不能以文档基线代替验证。

## TM-002 草稿阶段与0.1稳定包前置（历史快照，2026-10-01）

当前版本指针暂为 `v0.1.0-20260929T074814Z`，供0.1固定里程碑执行最终门禁；TM-002档案已预登记。TM-002 已按三个功能点、九项 TASK 编制28条父TC和35个固定变体，并将详细规格、独立验收、机器用例与根项目总表同源核对；当前TM-002保持draft/baseline_pending，0.1严格基线和总表回读的实际结论见TM-002 06记录。计划中的原生面板、私有加密来源 locator、主进程受限读取和测试 Keychain 隔离仍缺固定数据/程序与最终包实测；当前还没有独立macOS测试账号或经原生证明的进程专属Keychain命名空间，依赖密钥的用例及SOP-009第5步保持BLOCKED，TM-002 产品 E2E 为 `NOT_RUN`，发布资格为否。

0.2的真实升级必须从 TM-001 在本地 `master` 固定0.1里程碑后，经同树最终包全量产品E2E、SOP-018门禁PASS和SOP-020本机归档取得的正式稳定0.1原包开始；远端源码登记与Tag可在全部目标版本后统一办理。独立 `d2db551` 候选虽有门禁PASS，本地 `4bdeb13` 整合树（已纳入里程碑归档校验代码）尚无同树产品门禁或稳定原包，故不能作为0.2升级源。旧失败原件和12次历史总表批次保留。

## 会话与文档交接（2026-10-01）

用户指定[“文档”会话](project-sessions.md)统一编写所有非 SOP 文档，**包括项目总表与每批测试结果 Excel**，随开发进度和原始证据持续更新；“SOP”会话维护 `sop/`；开发总控整合本地 `master`，需求会话继续实现与固定测试。已通知开发总控、SOP、TM-001 和 TM-002。TM-003/004/005 的独立开发分支已有文档草稿或已提交改动，正在由文档会话核对接管；草稿、缺产品绑定与产品 E2E 的阻断不因本次会话归口解除。跨版本门禁与本机稳定里程碑的 SOP-only 提交 `afee30d`、`090d808` 已由总控纳入本地 `master` `c6729ea`；本会话正在把对应非SOP规范、版本档案和总表整合成独立文档候选，最终整合后仍需检查产品里程碑。TM-001 旧 `3467dc1` 门禁 FAIL 原件保留；修复后独立候选 `d2db551` 的本机门禁原件已为 PASS、生成通行证，但总控最终 `master` 整合树仍须重新执行适用门禁，不能把分支结果写成正式发布。

## TM-001 独立候选门禁通过，最终整合待验（2026-10-01）

只读核对 `.local/gates/tm001-final-gate-d2db551-20261001T0904Z/gate.json`：候选 `d2db5514e3dde2abb0b039f6188ae82f1ba3d53e`、tree `3854696e6212aa68aeccfdc720add187a4f92759`、DMG SHA-256 `acc86a9f04ed19fe91f1b63481988d615f5d81680602eed1305b3896bb284492`。该独立候选门禁 `state=PASS`、`release_eligible=true`，主精细116行中105 PASS/11辅助占位BLOCKED；独立辅助11/11、审计12/12、补充六组6/6均PASS；规范化最终结果78父TC与38变体全PASS。同目录机器通行证已生成；逐例 Excel 位于 `granular-reviewed/TokenMeter测试结果-local-1ab724d58a804b56aafd05af7606803e.xlsx`。该 Excel 是本次门禁原件，不覆盖旧 FAIL 或给最终整合树授予资格。原件归档、总控整合后的完整回归与正式分发仍待核实；根总表在这些步骤完成后以独立文档提交登记本批次和被测SHA。

## TM-001 首次干净候选门禁失败（2026-10-01）

固定候选`3467dc143b2e2fc71f51515f483f0ecff8637947`的本机正式门禁已运行结束，原件`.local/gates/tm001-final-gate-3467dc1-20261001T0730Z/gate.json`为**FAIL**、`release_eligible=false`，没有通行证或正式DMG。精细主批次95个实际Playwright入口PASS、辅助11/11、审计12/12、补充六组6/6各自PASS，逐例Excel已导出并回读PASS；门禁仍因003组缺有效`/v1/me` 200而拒绝。只读核验还发现004组完整`lsof`列表中有一个空名称。原件保留。现已在固定测试中补真实App恢复身份、服务账号/角色断言及空名称解析回归；下一步冻结新候选、重建DMG并完整重测，当前**不可发布**。细节见[本版测试结果](../releases/v0.1.0-20260929T074814Z/07-test-results.md)和[修复记录](../releases/v0.1.0-20260929T074814Z/09-regression-fixes.md)。

## TM-001 最终候选门禁准备（首次运行前记录）

同一候选的本机门禁程序已接入：`scripts/local_gate.py`顺序调用完整精细主批次、11条辅助固定检查、独立证据审计和六组补充E2E，再从原始证据推导`final-product-result.json`中的78条父TC与38条变体最终状态，导出并核对同批次独立Excel。主批次的11条辅助占位仍保留原始BLOCKED；只有对应辅助原件真实PASS、全部其他结果PASS，且候选、DMG、原件与归档摘要一致时，机器才可生成正式通行证。`scripts/local_release.py`还会从原件复核最终结果与归档副本。治理负测覆盖缺失或篡改证据、伪造占位映射及错误的主runner退出码。当前这套程序尚未在**干净、已提交的最终候选DMG**上完成正式执行，因此TM-001仍未发布、无通行证；旧开发包联合复核不能移作本轮正式PASS。

准备阶段实测：固定Playwright注册核对`.local/ci/final-registration-20261001T0526Z.json`为95/95 PASS，仅证明入口存在；Electron桌面单元25/25、服务端55项、桌面构建均通过；本机视觉辅助批次`.local/ci/hig-visual-c759e9f93b2f40cf9f72a40d438ca3f2/visual-checks.json`记录10张界面图与12项布局/键盘检查，清理记录为true。这些不是最终包E2E。完整治理、文档检查和总表回读结果在[本版执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)登记。SOP-014修订23、SOP-018修订12已明确主run辅助占位与最终结果复算合同；当前合并树的完整治理及最终候选产品门禁仍待实跑和原始收据。

## 本轮修复执行中（2026-10-01）

用户要求全部已开发功能的必测用例通过。已按[修复计划](../releases/v0.1.0-20260929T074814Z/09-regression-fixes.md)完成六项产品修复及固定测试观察器；基础检查为394治理、55服务、25桌面单元通过。新开发DMG原件在`.local/ci/electron-package-fixes-20261001T0114Z/`，它仍是未发布开发包。

本包首个完整精细回归`local-571dd63bfe5b4d90a95ed9c70d80de07`已结束为**FAIL**，清理完成、发布资格为否。原始116条结果为104 PASS/1 FAIL/11 BLOCKED；11条BLOCKED是尚未执行独立辅助程序的占位。按父TC与参数变体分别统计，独立审阅表记录78父TC为66 PASS/1 FAIL/11 BLOCKED、38变体全部PASS；独立证据审计为PASS，但不改变SESSION-09的原始FAIL或辅助占位。原件在`.local/ci/local-571dd63bfe5b4d90a95ed9c70d80de07/result.json`；逐步证据Excel在`.local/test-results/local-571dd63bfe5b4d90a95ed9c70d80de07-reviewed/TokenMeter测试结果-local-571dd63bfe5b4d90a95ed9c70d80de07.xlsx`，其导出/回读PASS只证明表格一致，`product_state=FAIL`。

SESSION-09的确定性失败来自测试脚本在退出待确认时点击了已被正确禁用的“恢复默认”按钮，30秒后超时。既定用例要求该操作锁定；CONFIG-06也要求待退出时总恢复禁用。保留原失败，修正固定脚本为明确断言按钮禁用，同时继续检查API不可编辑、配置不变、无新服务请求和真实撤销。新单例`local-4a8815e9d61e4b4bbdd41f7a2f897c52`四步全部PASS、清理完成，独立Excel在`.local/test-results/local-4a8815e9d61e4b4bbdd41f7a2f897c52-reviewed/TokenMeter测试结果-local-4a8815e9d61e4b4bbdd41f7a2f897c52.xlsx`；它不覆盖首个完整回归FAIL。

修订测试代码后的第二次完整精细回归`local-f47f8257607c48458cc52b886d281d70`已结束为**FAIL**，`cleanup_completed=false`、`release_eligible=false`。原始116条结果为103 PASS/1 FAIL/12 BLOCKED；其中UPDATE-08因前例资源未清理而安全阻断，另11条仍是独立辅助程序占位。审阅模型为78父TC 65 PASS/1 FAIL/12 BLOCKED、38变体全部PASS。UPDATE-07的五步Playwright真实升级及身份/配置断言均PASS，但其owned ShipIt/私有资源清理失败，所以父TC必须保持FAIL。独立审计`.local/ci/local-f47f8257607c48458cc52b886d281d70-audit/audit.json`为PASS；原始报告`.local/ci/local-f47f8257607c48458cc52b886d281d70/result.json`和逐步Excel`.local/test-results/local-f47f8257607c48458cc52b886d281d70-reviewed/TokenMeter测试结果-local-f47f8257607c48458cc52b886d281d70.xlsx`均保留，Excel回读PASS、产品结论FAIL。

清理诊断指向本轮创建的空ByHost偏好文件：`defaults -currentHost read`报告该域不存在，当前清理合同因此未完成。修复程序仍在进行，不能把Playwright五步PASS或审计PASS写成UPDATE-07通过；**在核实资源归属并完成安全清理前不再启动GUI测试**。随后须新run验证清理，再执行完整精细回归、11辅助用例、六组补充场景、审计与同批次Excel。此前定向`local-2b3be14c180e463eb884d50c55ff1ada`为14父TC 12 PASS/2 FAIL、16变体PASS；后续`local-87321b477c044b5fa39a2bfa9bcda9a1`两条修正用例及审计PASS。各批原件保留，不能合并局部PASS冒充全量通过。

首次针对“域不存在”的清理代码修正通过固定治理检查（`.local/ci/shipit-absent-domain-governance-20261001T0445Z/receipt.json`），但新定点`local-c8e31657d5e4428584a6f316936113e1`仍为**FAIL**、`cleanup_completed=false`：UPDATE-07的五步Playwright均PASS，ShipIt/私有目录清理仍失败；UPDATE-08因前例残留而BLOCKED。本次原始报告为`.local/ci/local-c8e31657d5e4428584a6f316936113e1/result.json`，独立Excel在`.local/test-results/local-c8e31657d5e4428584a6f316936113e1-reviewed/TokenMeter测试结果-local-c8e31657d5e4428584a6f316936113e1.xlsx`，回读PASS但`product_state=FAIL`。失败后的归属预检`.local/ci/local-c8e31657d5e4428584a6f316936113e1-cleanup-followup-01/pre-cleanup.json`记录本轮私有根、ShipIt缓存和空偏好文件的owner核对；这不是清理完成证明。该批次怀疑即时升级后的ShipIt异步收尾存在时间差，因此先核对归属并安全清理，再实施有界稳定等待与诊断。

后续UPDATE-07/08定向`local-70e531d3092c4cbea30160117c379287`因误用系统Python、缺少`alembic`，两例均**BLOCKED**，`cleanup_completed=true`；审计PASS及独立Excel回读PASS只证明原件和表格一致，`product_state=BLOCKED`。改用项目venv的全新定向`local-b6627e4379c64386bfc1a535fb432c16`两例原始结果均**PASS**，本轮ShipIt及私有资源清理为true，`cleanup_completed=true`；独立审计和结果Excel回读均PASS，`product_state=PASS`。两次原始报告分别在对应`.local/ci/<run_id>/result.json`，Excel分别在`.local/test-results/<run_id>-reviewed/TokenMeter测试结果-<run_id>.xlsx`。定向PASS不覆盖此前全量FAIL。

同一未发布开发包的新完整精细回归`local-534748ff47cb44229183a6bd878c1674`已落盘：原始`state=BLOCKED`，116条结果为105 PASS/0 FAIL/11 BLOCKED，11条均为需由独立辅助程序执行的占位；95个实际Playwright入口全部PASS，另外10条父TC由变体结果推导，`cleanup_completed=true`。原件为`.local/ci/local-534748ff47cb44229183a6bd878c1674/result.json`。随后独立辅助批次`aux-818fe55e1e8940e4a3196b9d03b76563`的11条固定检查全部PASS、清理完成，原件在`.local/ci/aux-818fe55e1e8940e4a3196b9d03b76563/result.json`；六组补充产品E2E批次`local-5197628d58ac4136b004b87da438220c`为6/6 PASS、清理完成，原件在`.local/ci/local-5197628d58ac4136b004b87da438220c/result.json`，独立结果Excel在`.local/test-results/local-5197628d58ac4136b004b87da438220c/TokenMeter测试结果-local-5197628d58ac4136b004b87da438220c.xlsx`。三份原始结论各自保留，不把辅助或聚合场景回填成主run原始PASS。

独立证据审计v1原件`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit/audit.json`保持**BLOCKED**：当时唯一`PASSWORD-05`的peer fixture源码与已审阅绑定不一致。重新核对固定绑定后的审计v2原件`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit-v2/audit.json`为12/12 PASS，未修改v1或主run原始状态。

联合逐例复核表`.local/test-results/local-534748ff47cb44229183a6bd878c1674-reviewed/TokenMeter测试结果-local-534748ff47cb44229183a6bd878c1674.xlsx`及同目录`verification.json`已导出、回读PASS；它绑定主run、11条辅助、审计v2和六组补充原件，模型中78条父TC、38条变体、11条辅助与六组场景均PASS。`verification.json`仍明确`product_state=BLOCKED`，对应主run保留的11条辅助占位，表格归档PASS不改写该原始状态。当前证据说明开发包的联合逐例复核通过；干净正式包与发布门禁尚未通过，无通行证或正式发布。

## 修复前完整回归结论（2026-10-01，原件保留）

`v0.1.0-20260929T074814Z`仍未发布，无正式通行证。dev07六个聚合场景组的历史原件为五组PASS、004升级FAIL，汇总缺升级资产；不能证明精细TC通过。首轮精细全量`local-7feea03dd72e4eddba0651cede8fd23d`为BLOCKED（109条预期、16条PASS、93条BLOCKED），原件和独立Excel均保留。新全量`local-343e54113b0b442383e80f137013014b`已结束为**FAIL**，`release_eligible=false`、`cleanup_completed=true`。其原始`result.json`在`.local/ci/local-343e54113b0b442383e80f137013014b/`，记录78条父TC为57 PASS/8 FAIL/13 BLOCKED，38条变体为31 PASS/7 FAIL。另运行11条辅助固定检查得10 PASS/1 FAIL；独立证据审计把五条原始PASS降为BLOCKED。合并后的结果模型为78条父TC **62 PASS/9 FAIL/7 BLOCKED**，38条变体**31 PASS/7 FAIL**。这些是按原件与审计调整后的结论，不能改写主run原始计数。

当前执行链为：**需求→功能点→具体TASK→逐项TC/变体、输入、动作、预期、DB操作→基线→固定代码实现→逐TC执行和记录**。本轮`tests/test_cases.json`有78条TM-001父TC（67产品、11辅助），均已具固定程序；另31条为后续功能规划。`tests/granular_login_variants.json`登记25条认证参数变体，`tests/granular_update_variants.json`登记13条UPDATE-05负例变体，合计38条；首轮BLOCKED批次仍以当时31条变体的代码快照解释。证书差异和DR差异已通过固定组件身份层检查，但新全量真实App测试在最终临时目录清理断言失败，不能记为产品PASS。原有六条待定产品预期已按用户决定细化；补充文档不追认为先于历史代码存在。

测试必须由仓库中固定、按TC编号可重复执行的程序完成；Codex只调用程序并分析原始结果，不以临时手工操作、截图目测或手填表格判PASS。独立入口为`scripts/run_test_case.py --case-id <TC-ID>`，完整集合使用`--all`，均需显式`--package-manifest <本轮包清单>`；开发包另加`--development`。命令会创建新run_id和隔离目录，输入、动作、断言及判定来自版本化代码。`scripts/granular_e2e.py`保存逐步事件、Playwright原件、SQL/DB旁证、trace和截图；父TC由其全部声明变体的实际结果推导。任何FAIL/BLOCKED、缺步骤或清理失败继续阻断发布。

覆盖缺口也由固定代码留下`coverage-blocked.json`，机器在用例其他断言通过时将其判为BLOCKED：CONFIG-01/05尚缺默认服务启动前的网络观察，CONFIG-06尚缺验证和原生安装阶段忙态观察，UPDATE-04尚缺零原生交接观察。若用例已有确定性断言失败，保留FAIL优先；这四项不能凭现有局部断言放行。

独立审计原件`.local/ci/local-343e54113b0b442383e80f137013014b-audit/audit.json`还将CONFIG-02/03/04、UPDATE-01/07的原始PASS降为BLOCKED，原因包括逐值保存回读、新进程`/me`、安装确认前外连/交接，以及未经筛选的`lsof`证据缺失。辅助原件`.local/ci/aux-local-343e54113b0b442383e80f137013014b-01/result.json`为10 PASS/1 FAIL；UI-01的测试脚本颜色`#fff`解析已修，新单例`aux-ui01-local-343e54113b0b442383e80f137013014b-02`真实PASS，独立Excel另存，不改旧FAIL或主审阅表。定向复测`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed/result.json`有16条结果行（3父TC加13变体），其中15个Playwright执行入口；机器结果10 PASS/6 FAIL、清理完成。PASSWORD-05第二App前置与ADMIN-03收尾脚本缺陷修复后分别真实PASS；UPDATE-05父TC及五条Info/代码身份变体仍FAIL。`cleanup-observation.json`对INFO_VERSION/INFO_BUILD约20秒采样仍见临时目录残留，属于待修产品清理问题。定向结果不替换完整回归原件。

目标新审计`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed-audit-peer-v3/audit.json`为PASS，独立核对PASSWORD-05第二App peer及两个旧会话401、ADMIN-03四步证据；目标审阅表`.local/test-results/local-877830fb340a4d12b4e29cf76fa422ed-reviewed/TokenMeter测试结果-local-877830fb340a4d12b4e29cf76fa422ed.xlsx`已回读PASS、产品FAIL，3父TC为2 PASS/1 FAIL，13变体8 PASS/5 FAIL。它确认两条脚本缺陷的定向修复，不改变UPDATE-05产品清理失败或主全量FAIL。

用户统一查看入口为仓库根[TokenMeter项目总表.xlsx](../TokenMeter项目总表.xlsx)，随 Git 版本维护。当前表已回读 PASS：11 个 Sheet、164 条父用例与 35 个变体共 199 行、13 次 TM-001 历史批次，SHA-256 `fa36939ff901254b9bce7775d194943ceccc3c7e41d64680c0ab1b4b22701a5d`，`product_tests_executed=false` 表示导表程序本身未运行产品。最新 `c2911bc` 失败批次的独立结果 Excel 在本工作树 `.local/test-results/local-0512d4fc44544eba97f9d1ae79cbfc37-reviewed/`，与旧批次并列而不覆盖；总表用例最近状态和批次摘要不能替代原始门禁。完整设计见[用例 JSON](../tests/test_cases.json)与[详细用例](testing/cases/README.md)，腾讯在线表格已停止同步。

每次实际测试单独输出`TokenMeter测试结果-<run_id>.xlsx`并留在本机。新版全量审阅表已生成于`.local/test-results/local-343e54113b0b442383e80f137013014b-reviewed/TokenMeter测试结果-local-343e54113b0b442383e80f137013014b.xlsx`；同目录`verification.json`为Excel回读PASS、`product_state=FAIL`，记录78父TC 62/9/7与38变体31/7/0。UI-01新单例表另存于`.local/test-results/aux-ui01-local-343e54113b0b442383e80f137013014b-02-reviewed/TokenMeter测试结果-aux-ui01-local-343e54113b0b442383e80f137013014b-02.xlsx`，本次仅1例PASS。导出PASS不授予产品通过，也不改主审阅表。首轮BLOCKED和dev07历史批次各有独立结果Excel；详见[07结果](../releases/v0.1.0-20260929T074814Z/07-test-results.md)。

`scripts/local_e2e.py`已接入结果自动导出，原JSON保持不变，导出失败返回非零；相关runner工具11项、桥接18项检查通过。补导历史运行不构成新的App测试；若导出失败可保留原收据，在全新目录补导，无需重跑产品。候选测试期间只写本地忽略目录，待执行和门禁结束后再更新Git跟踪的主表和摘要，保留原被测SHA。

## 保留的dev07开发运行

- 原件：`.local/ci/e2e-dev-probe-07/`；run_id=`local-a1b2c3d4e5f60718293a4b5c6d7e8f94`，2026-09-30 11:22:02–11:24:17 UTC。
- 包：`.local/ci/electron-package-probe-06/package-manifest.json`，DMG摘要`09f0854cefc7584e1cc77e911d92cf1024a826d407e24241bb38cef11d35a529`。`scope=development`，`working_tree_dirty=true`，不能当作已锁定的正式候选。
- 可见副本：[根dmg目录](../dmg/README.md)下`v0.1.0-20260929T074814Z/TokenMeter-v0.1.0-20260929T074814Z-DEVELOPMENT-NOT-RELEASED.dmg`，与开发原件SHA-256相同。正式DMG尚未生成；今后构建的开发/候选包标记未发布，门禁PASS后才在同版本目录放正式原名包。
- 001/002/003/005/006的原始Playwright结果通过；004观察到自主新PID和runtime绑定，但`new_process_profile_files`期望true、实测false。即时lsof没有证明新进程正使用隔离profile文件，完整升级/恢复断言未完成。
- 原汇总为FAIL，六次尝试只写入前五个suite，并报`Evidence is absent or outside the owned output`；升级结果/进程资产缺失，原`cleanup_completed=false`。
- 后续`E2E-TM001-004/cleanup-followup.json`独立记录仅本轮资源的清理及隔离安装中观察到build101。它不修改原FAIL、不补造缺失报告，也不证明后续身份恢复成功。

详细候选、摘要、逐组结果及证据范围见[07测试结果](../releases/v0.1.0-20260929T074814Z/07-test-results.md)；未发布条件见[08发布记录](../releases/v0.1.0-20260929T074814Z/08-release-record.md)。

## 已建立与尚缺

已建立Electron/React/TypeScript客户端、FastAPI/SQLite、SQL造数、electron-builder本机签名DMG、Playwright场景组、原件校验门禁及本地归档程序。构建、组件、治理与HIG辅助检查的既有结果记录在[06执行记录](../releases/v0.1.0-20260929T074814Z/06-iteration-record.md)；这些结果不是完整产品验收。

新增[01a登录/改密](testing/cases/01a-TM-001-login-scenarios.md)、[01b会话/管理/配置/更新](testing/cases/01b-TM-001-session-admin-release-scenarios.md)、[01c交付检查](testing/cases/01c-TM-001-delivery-checks.md)用于补齐任务级用例。67条产品父TC、38条参数/负例变体及11条辅助TC已有固定程序；完整结果按主raw、辅助和审计原件联合判定。本轮首次新包运行的父TC为66 PASS/1 FAIL/11辅助占位BLOCKED；第二次为65 PASS/1 FAIL/12 BLOCKED，38变体两批均PASS。新完整精细原件105 PASS/0 FAIL/11辅助占位BLOCKED；辅助11/11、六组6/6及审计v2的12/12另有独立PASS原件，联合逐例复核为78父TC与38变体全PASS。原主run仍BLOCKED，干净包门禁与通行证未完成。TM-002–012继续planned，不因TM-001已有程序进入实现。

此前`python3 scripts/check_docs.py --mode structure`返回PASS：102份登记文档、890条链接，101份baselined、1份superseded；这只证明当时结构和引用检查。基础收据还记录严格基线、质量、治理、服务和桌面单元结果，均不能替代逐TC产品E2E。当前开发包的联合逐例复核已完成；仍须以最终干净候选重新核对包与测试证据并执行正式发布门禁，三批原始运行不得改写。

下一步依次为：锁定干净候选并执行最终DMG安装/升级及发布门禁→仅在门禁PASS后签发通行证与正式发行。若任一必要项FAIL/BLOCKED，保留原件按SOP-015定位，不能提前本地正式发布。

## 当前运行边界

- 默认本机完成开发、测试、打包和发布，当前实测范围macOS15.7.4 Intel；其他架构/系统未验证，无需完整Xcode。Actions完整测试仅在用户明确要求多环境时运行。
- 默认API `http://127.0.0.1:49176`、更新清单 `http://127.0.0.1:49177/version.json`；测试另用拥有的动态回环服务和独立profile，不对默认生产服务登录或造数。
- 用户已有App、49176服务与`database/production/production.db`不参与回归。生产首建约定admin/123456并强制改密；回归用`database/test/test.db`或逐例私有合成库，见[数据库说明](../database/README.md)。
- DMG、更新包、原始报告和通行证只保存在本机。Git保留源码、文档、PR与版本追踪，不创建GitHub Release安装包资产。无正式门禁PASS时不分发开发包、不更新稳定源、不创建正式Tag。

## 保留的历史事实

[CI36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502)在macOS15.7.9 Apple Silicon/Intel分别完成旧SwiftUI/XCUITest六例与父门禁PASS；[PR#2](https://github.com/lzhe72/TokenMeter/pull/2)已合并master至`e011857443b503c2bfafcb9cd1c9e6d52f5ff5f2`。该历史源码树为`2b723f41d96256e962cf04ed9105dfb1e2985739`，不代表当前Electron候选、最终DMG或精细TC已验证。

此前受保护CI、双架构内部发行和Sparkle appcast是迁移前方案；现由用户确认的本机Electron流程取代。历史公网DNS、Keychain、签名及原始结果问题，以及开发包失败、用例总表和DMG入口问题，保存在06和[两日31例复盘](retrospectives/2026-09-29--2026-09-30-tokenmeter.md)，不改写旧失败。接手先读[SOP总索引](../sop/README.md)。
