# v0.1.0-20260929T074814Z — 执行与交接记录

## 输入与目标

用户要求完成首个功能，并实际验证“第一版SOP→文档驱动”流程。按001分配版本0.1.0，UTC立项时间2026-09-29T07:48:14Z；基线为master合并提交548c582，保留0.0.1档案。目标TM-001包含全部四个既定验收场景。

## 逐步执行记录

| 步骤 | 实际操作与观察 | 证据/结果 |
| --- | --- | --- |
| 000 规范维护 | 001第5步及总索引写死基础版本，阻碍新版本启动；改为current指针和本次范围 | SOP001修订4，旧档案保留 |
| 001 立项 | 新分支、current、00–06草稿、catalog、Changelog建立 | .local/process/v0.1.0-20260929T074814Z/001-structure.json，结构检查通过 |
| 002–007 编制 | 顺序写需求、任务、API/数据/界面设计、开发计划、四例E2E计划和发布预案，每步structure检查 | 同证据目录保存逐步命令输出 |
| 环境预读 | xcode-select退出2；Python3.10.4可用；仓库公开、gh权限可用 | 缺本机native环境，转远端探索；不声称运行通过 |

## 本轮并行与决定

008 实际结果：baseline 与 quality check 均退出0，68份文档、12项全局功能/34场景；本轮目标仍固定TM-001四例。证据为同目录008-baseline.json、008-traceability.json。基线通过后才授权服务、Mac与runner agent按文件边界实现。

流程发现第二项缺口：019仅描述源码推送与正式发布，缺已授权的PR闭环。本轮修订019至4、AGENTS记录持续授权，要求核对候选/适用检查后合并，不允许产品PR沿用基础规范上传例外。远端实际已运行基础CI（master run36538259111）：治理通过、产品因缺执行器BLOCKED失败；旧状态页“远程未运行”需更新。

后端和macOS agent先只读设计，文档baseline通过后才获得实现授权。服务API可本机真实验证；原生UI与Sparkle通过远端Mac实际探针验证。工程骨架与生产签名分开，不为缺证书停止可独立完成的源码/测试工作。

## 尚未完成

本轮App、服务、测试数据和原生执行器正在联调，原生产品验收已在CI执行但未通过，当前结果见文末。此段为先前规划状态；当时的正式支持矩阵、证书、生产MySQL和受保护发布环境缺失，产品发布BLOCKED。后来用户将本版目标改为 SQLite，MySQL 不再是 v0.1.0 门禁。后续实际结果继续追加，不能用文档基线或Python测试代替原生E2E。


## 开发中发现的流程与实现问题

- Python 依赖在旧 pip 上退回源码包，触发缺失编译器探测。未安装系统工具；隔离升级 pip 并使用预编译 wheel，SOP-009/013 与 CI 固定 `--only-binary=:all:`。安装故障单独留证，不能算业务红测。
- 旧基础 fixture 只生成账号 JSON，不能初始化真实服务。010 增加真实账号生成、独立 expected、CLI 导入和数据库所有权验证；原生 runner 为每例建立独立数据库、端口和 Keychain 范围。
- 预审发现原生退出测试只验证另一个 API token 的撤销，不能证明 UI 退出。已要求以真实管理员审计及重启登录状态验证 UI 触发的退出，服务端另有会话失效断言。
- 预审发现网络失败退出会保留本机凭据，与需求冲突；按本地退出、服务端撤销未确认提示和重试实现修正，不修改验收要求。
- 原生环境本机缺失，四例 UI 测试先编写并保持未验证；通过远端开发矩阵取得真实构建/行为结果。已建立草稿 PR #2；所有适用检查通过后才转正式并合并。


## 首轮实现整合

- 服务端从真实19失败/9通过基线进入012，实现后34项全部通过（17.41秒），含真实TCP请求、SQLite备份恢复、并发停用和凭据版本检查；证据 `server/green-final-command.json` 与 `green-final.log/xml`。
- 程序实际建立后，00-manifest标为ready，TM-001标为in_progress；四例绑定具体native_test和auth_accounts/tm001_update_packages数据集，未来更新故障数据集仍planned。
- 原生工具与证据负测129项通过（`governance-integrated-green.log`）；升级helper输入负测7项通过。一次整合检查遇到正在补充的native identity红测，保留原失败并在规则实现后完整回归，未覆盖原日志。
- 审查修正ad-hoc无法作为跨版本Keychain身份连续性的依据：先更新03设计并baseline通过，再给004两个包使用相同临时CI自签identity。该身份不授予正式发布资格。
- 跨模块审查继续核对审计UI、Keychain错误和无效签名的精确失败原因，实际远端结果随后追加。


## 远端候选运行

首个产品候选8235906触发[run36541834950](https://github.com/lzhe72/TokenMeter/actions/runs/36541834950)，工作流解析失败，未创建job。原因是未引用的YAML单行命令中`--only-binary=:all:`含冒号加空格；已改为块文本。修复前本机YAML解析明确复现第22行错误，修复后两个workflow均通过语法解析。此运行不算产品构建或E2E执行。

同候选本机iteration退出2，原始报告`.local/e2e/gate-dadc896eb2134f18a9e224649cb47d1b/result.json`记录完整Xcode缺失与0原生用例；不是业务断言失败。


### BUG-TM001-CI-001：工作流命令格式

上文run36541834950对应的YAML缺陷归档为BUG-TM001-CI-001，属于执行配置问题；2ee93ec修复后远端成功创建三个job，未改变产品验收条件。

### BUG-TM001-RUNNER-001：Xcode不支持的参数

[run36541990316](https://github.com/lzhe72/TokenMeter/actions/runs/36541990316)在macOS15.7.9 arm64/x86_64、Xcode16.4/16F6上真实执行。两平台SQLite迁移、四账号导入与/v1/health均通过；`xcodebuild`因不存在的`-maximum-concurrent-test-macos-destinations`选项退出64，未执行原生用例。原始工件保存到`.local/ci/36541990316/`，远端归档可回溯。删除该无效选项，继续保持逐例串行与禁用测试并行；修复后须新运行完整四例，两平台均不能复用旧结果。

流程复核补齐候选workflow与日常CI的前置条件：显式Python3.10/Xcode16.4、锁定依赖及服务端/更新工具回归。修复其直接调用缺依赖native runner的路径；最终包/全矩阵/MySQL/受保护签发仍未实现，018修订3明确候选诊断与发布资格。


### BUG-TM001-MAC-001：Sparkle框架嵌入路径

[run36542491053](https://github.com/lzhe72/TokenMeter/actions/runs/36542491053)的arm64任务已越过参数检查，`build-for-testing`在复制框架时因`Build/Products/UITesting/Sparkle`不存在退出65。原生用例执行数0；原始构建日志保存在`.local/ci/36542491053/arm64/`。按实际Swift Package产物检查并修复项目嵌入配置，重新构建和执行全部场景，不能将构建日志中没有测试失败当成E2E通过。

入口复核同步AGENTS：删除过期的“产品未接通/原生命令无需依赖”断言，分别指向标准库治理检查、隔离Python服务环境及专用Mac原生执行前提；当前结果统一从status读取。

Intel任务随后确认同一Sparkle复制错误，证据在`.local/ci/36542491053/intel/`。日志证明Xcode已自动复制并签名Sparkle.framework，额外手工Copy才查找错误路径；修复仅删除重复Copy阶段，保留SPM依赖与链接。该轮远端治理131项、服务34项、升级工具7项通过，仍无原生产品通过。

### BUG-TM001-MAC-002：macOS静态文本断言

[run36543142719](https://github.com/lzhe72/TokenMeter/actions/runs/36543142719)两平台App构建成功，实际各执行001–003并失败。001/003服务登录、改密返回200，界面账号控件存在，但其AXLabel为空；002错误登录返回401，等待label错误文案超时。macOS静态文本显示值位于AXValue。修复测试统一读取value，保留相同用户名、错误码、角色和版本号预期；修复后仍须完整原生回归。

### BUG-TM001-RUNNER-002：原始结果解析与判定

同轮原始native-tests.json的bundle类型为`UI test bundle`，旧解析只接受`Test Bundle`，导致用例缺目标前缀。使用该轮脱敏原始结构加入永久回归，保留精确用例集合、计数、零跳过和全部通过检查。原始设备为macOS15.7.9，Apple Silicon显示arm64e、Intel显示x86_64h；以真实结果核对实际平台和架构家族。另修正前三例确定性FAIL不能被第四例环境BLOCKED覆盖的问题，独立记录阻塞和失败。

### BUG-TM001-FIXTURE-001：临时签名身份导入

同轮004在`security import`临时P12时退出1，未进入原生UI。现代OpenSSL默认PKCS12封装存在Apple Security兼容性限制，与本轮故障线索一致；按[Apple DTS说明](https://developer.apple.com/forums/thread/723242)与OpenSSL文档指定临时P12容器的兼容算法和随机非空口令，App的RSA/SHA256签名及更新包EdDSA签名保持原有设计。临时私钥及口令不进入日志/工件；实际导入和升级仍待新候选CI确认。

本轮原始完整工件保存在远端run36543142719；本机通过有界ZIP读取获取原始小日志与JSON副本到`.local/ci/summaries/36543142719/{arm64,intel}/`。补充执行器逐例阶段与失败诊断，避免仅显示总状态导致无法及时定位。两平台均未PASS，PR保持草稿。

### BUG-TM001-MAC-003：非沙盒更新器配置审查

代码审查发现App所有配置均`ENABLE_APP_SANDBOX=NO`，Info却启用`SUEnableInstallerLauncherService`。按[Sparkle官方配置说明](https://sparkle-project.org/documentation/customization/)，该服务仅供沙盒App使用；移除沙盒专用服务键，沿用非沙盒默认配置。此项来自实现与官方契约比对，004此前未运行，不能声称已观察或修复了原生升级失败。HTTPS、EdDSA及解压前签名验证保持启用，仍执行完整004。

上述修复的本机回归：139项治理检查通过（`.local/governance/tm001-native/ci-repair-green.log`），9项升级helper检查通过；基线与追踪检查通过。签名容器实际生成并验证非空口令、封装算法及SHA256证书，但没有在本机导入Keychain，实际原生升级继续由新候选CI验证。原失败和永久回归的红绿日志均保留，未通过修改业务预期放行。

### 候选dcd8360：前三例双平台通过

[run36545478638](https://github.com/lzhe72/TokenMeter/actions/runs/36545478638)通过139项治理、34项服务和9项升级工具检查；macOS15.7.9 arm64/Intel均实际执行001–003，各3例PASS。修复后的真实界面值、账号权限、管理审计和用例解析均取得原生证据，仍不构成完整四例验收。

### BUG-TM001-FIXTURE-002：信任配置与主异常保留

同轮004在prepare-signing约60秒后中断，两平台最终只报告`remove signing trust failed (1)`。清理进入trust_attempted路径，证明此前P12导入和codesign权限配置已完成；结合原程序的60秒超时，用户域信任操作等待授权是当前调查方向。清理抛错遮住原异常，需同时保存主操作和清理失败。仅在专用CI核实并使用非交互临时信任，精确撤销本次证书，缺权限阻断；不绕过App的TLS或签名校验。原始日志副本为`.local/process/v0.1.0-20260929T074814Z/ci-36545478638-failed.log`，完整原生结果保存在该CI工件。

按000先修订009/010至4，索引与03/04同步上述hosted Mac非交互admin域策略；依据Apple信任API及GitHub托管runner管理员权限说明。该方案作为待真实验证的环境实现，不将sudo可执行等同于证书信任或004通过。

Apple Big Sur 11.0.1说明与GitHub runner维护者记录均表明，仅root身份不保证信任操作免交互。因此先在两个CI工作流增加009环境探针，保存独立environment_only记录；探针失败保持job失败，014仍要求真实四例完整执行。探针不能签发通行证，也不修改系统授权规则。

该修复本机完整治理147项通过，原生环境探针实际返回BLOCKED（缺完整Xcode），未修改本机证书信任。`security help verify-cert/add-trusted-cert`已只读核对实际参数；远端必须另行验证信任与完整产品用例。证据`.local/governance/tm001-native/ci-trust-green.log`及`environment-probe-{red,green,local-blocked}.log`。

用户询问为何看不到DMG。已核对源码：未实现hdiutil/DMG打包入口，当前只有App工程与隔离更新ZIP helper；正式签名/公证配置与发布门禁也未就绪。明确记录安装包交付尚未完成，不能将测试包或源码PR视作正式安装包。

### BUG-TM001-FIXTURE-003：代码签名信任清理挂起

[run36547335412](https://github.com/lzhe72/TokenMeter/actions/runs/36547335412)两平台环境探针已实际完成代码签名身份准备、HTTPS CA信任及系统TLS验证，主操作无阻塞；只有代码签名信任撤销等待60秒超时。TLS信任及证书清理成功。产品四例未在此候选执行，environment_only不能替代上一候选的原生结果。

[GitHub官方runner问题12116](https://github.com/actions/runner-images/issues/12116)记录同类撤销挂起，当前程序的对应差异是代码签名公钥证书仅在临时用户keychain。先更新03：将该公钥证书也导入System.keychain，私钥仍留专用keychain；继续严格先撤销admin信任，再按自身指纹删除证书及私有资源。此为待探针验证的最小修复，不把只删证书当作已撤销信任。增加安全操作阶段诊断，任何清理失败保持阻断。

用户询问无DMG如何执行App测试，已澄清远端Mac由Xcode构建真实.app并由XCUITest启动窗口，不依赖DMG；最终DMG安装验收仍缺失。按04既有截图证据要求补充关键界面的自动截图附件，截图不替代业务断言或原始xcresult。

按000将017修订至3，明确正式交付为DMG、需要从DMG安装后的.app执行完整回归，并分别绑定摘要；开发阶段直接测试.app仍按014执行。索引、执行规范和05同步，缺实际DMG程序仍BLOCKED，没有新增通过声明。

本轮工具回归150项通过，升级helper9项通过；baseline与追踪检查通过。原生附件导出先核对CI实际xcresulttool help，再导出PNG并登记摘要，父门禁核对文件一致性。新截图和System证书清理仍待新候选CI实际执行；未用工具自测代替原生结果。

候选69c717d的[run36548537959](https://github.com/lzhe72/TokenMeter/actions/runs/36548537959)基础检查通过（150项治理、34项服务、9项helper），但两平台环境探针仍在最后codeSign信任撤销超时。逐操作日志证明TLS信任撤销、TLS证书删除与codeSign公钥证书删除都成功；System副本假设未解决根因，保留失败，不将其写成修复完成。四例产品测试及新增截图未执行。Apple开源TrustSettings代码显示删除最后admin条目存在额外授权路径，继续只读核实受限CI环境配置方案，不保留残余证书或跳过清理换取通过。

依据[Apple内置授权规则](https://github.com/apple-oss-distributions/Security/blob/db15acbe6a7f257a859ad9a3bb86097bfe0679d9/OSX/authd/authorization.plist)和[security官方CLI实现](https://github.com/apple-oss-distributions/Security/blob/db15acbe6a7f257a859ad9a3bb86097bfe0679d9/SecurityTool/macOS/authz.c)，按000将009/010修订至5：替换本轮新增的笼统“不修改authorizationdb”实现限制，为仅限一次性托管CI、单一right、is-root短窗口、普通用户拒绝与完整恢复的可验证流程。现有root来自GitHub原生管理员授权；不改产品认证、TLS校验、原生用例和发布要求。缺任何验证条件仍阻断，不在用户本机执行。03/04先更新并基线后再实现。

### 受限授权方案审查撤回与环境阻塞

独立审查进一步核实[Apple授权引擎](https://github.com/apple-oss-distributions/Security/blob/db15acbe6a7f257a859ad9a3bb86097bfe0679d9/OSX/authd/engine.m#L1235)对该right使用固定规则，数据库写回不能使root-only方案成立。因此撤回上一段的实施决定和未提交helper，保留本机草稿与159项工具自测日志作审查记录；这些测试只模拟OS，不证明真实Mac兼容。未在本机或CI执行该授权数据库修改。009/010修订5改为遵守系统授权并在已知清理前提缺失时先阻断，不部署无效方案。

升级探针改到014第004例的依赖位置，001–003按自身前提正常执行；四例集合、完整门禁和清理标准不变。这样可以保留真实App、截图及业务证据，同时如实标明004尚未运行。恢复需专用测试环境提供正常系统授权及自动清理程序，不能用sudo可用、环境标志或工具mock通过替代。

用户随后明确表示“本机可以作为测试机”，据此扩展009本机测试入口。只读结果：macOS15.7.4、Intel x86_64、已登录用户桌面；xcode-select现为CommandLineTools，/Applications及Spotlight未找到完整Xcode.app或Xcode.xip，磁盘可用约35GiB。未触发安装、改系统配置或导入证书。Apple兼容表确认Xcode16.4支持当前系统；已告知用户安装与首次启动所需操作。该授权允许推进本机测试准备，不证明原生执行或升级fixture已经可用。

本轮152项治理/门禁工具回归通过，68份文档基线与追踪检查通过。新负测证明清理路径不可用时不调用系统写入、004探针的BLOCKED与FAIL分别传播且非零不能放行；本机probe实际退出2，原因仍为缺完整Xcode。证据位于`.local/governance/tm001-native/blocked-environment-{red,green}.log`及`local-machine-preflight.log`。这些结果不等同于产品验收。

### 0a9c39e真实原生回归与本机预览

[run36551758767](https://github.com/lzhe72/TokenMeter/actions/runs/36551758767)为0a9c39e分支的PR合成合并提交624d360执行了两平台原生门禁。macOS15.7.9/Xcode16.4的Apple Silicon与Intel分别运行真实App、FastAPI、SQLite和XCUITest，001登录/改密/退出、002权限、003管理员操作及审计全部PASS；每平台各执行3/4、通过3/4，原始xcresult、候选App摘要和实际窗口PNG在GitHub Actions产物。004环境探针在任何证书系统写入前判为BLOCKED，完整门禁两个平台都BLOCKED，CI作业以退出2失败。治理、34项服务和9项升级工具自测通过。不能将前三例复用为下一候选的四例通过，也无正式安装包或通行证。

按用户授权在本机使用CI产物构建的同一开发App归档，先核对候选App ZIP摘要、限制解压路径与符号链接、执行`codesign --verify --deep --strict`，然后在本机Intel/macOS15.7.4启动`.app`与隔离FastAPI/SQLite测试服务。实测App进程仍在、服务`/v1/health`返回schema0001；本机自动UI用例执行数0。机器证据`.local/process/v0.1.0-20260929T074814Z/local-preview-36551758767.json`，隔离预览资源位于`.local/preview/36551758767-intel/`且目前仍供用户体验，后续停用时按本轮所有权标记清理。Apple下载页正在等待用户登录/安装完整Xcode16.4；下载、系统授权和004清理程序均未伪造为完成。

### 本机预览 DMG 与发布资格复核

用户要求提供可安装DMG、管理员账号并完成正式Git发布。按000/017补充明确标记的本机预览诊断分支，原017正式发布前提不变。新增`python3 scripts/package_preview_dmg.py`：只接受签名有效、无更新源的UITesting App和loopback测试服务，保留原App不修改；核对源/暂存/镜像中的App内容一致，校验DMG并输出SHA256。发布预案和Changelog同步更新。

开发App来自[run36551758767](https://github.com/lzhe72/TokenMeter/actions/runs/36551758767)的Intel CI产物，`.local/preview/36551758767-intel/TokenMeter.app`；从其构建的可复现预览包为`.local/preview/36551758767-intel/TokenMeter-v0.1.0-20260929T074814Z-local-preview-verified.dmg`，SHA256 `19ab21c41e7e943d4ebae1d7587efbb0262a91de2f995fc223502841a89463c1`，App树摘要`af706179862d709e8bdace9d25142712117db53336badb79bc082c5c1dc33b03`。程序实际运行退出0，镜像校验通过；从该镜像解包到`verified-install/TokenMeter.app`后`codesign --verify --deep --strict`通过，`open -g -n -a <绝对路径>`启动进程9314。另从同来源预览包安装同一App到`/Applications/TokenMeter.app`并验证签名与可执行文件摘要；没有覆盖此前存在的App。隔离服务`http://127.0.0.1:60470/v1/health`返回200/schema0001，`test-admin`合成初始密码登录返回200/admin且要求首次改密。服务仅当前本机运行，DMG内说明要求把默认CI地址改为此loopback地址；预览包为临时签名、未公证且无更新源。

当前分支提交`6d964d2b55846ba31ebc74c928455ad502cd3963`的[run36553523311](https://github.com/lzhe72/TokenMeter/actions/runs/36553523311)两架构各运行001–003并PASS，004升级环境缺少可验证证书信任清理路径而BLOCKED，完整E2E为3/4、发布资格false。本机只有CommandLineTools，安装包原生UI回归执行数0；正式017还缺Developer ID、公证、正式DMG程序和全支持矩阵，018缺受保护候选与通行证。PR #2保持草稿，不创建正式tag、GitHub Release或通行证。本次预览包及本机账号只用于诊断，不计入正式发布证据。

预览包机器诊断为`.local/process/v0.1.0-20260929T074814Z/preview-dmg.json`：两份解包/安装App的`codesign --verify --deep --strict`均退出0，安装后进程在运行，隔离服务健康200，安装包原生UI E2E执行0例。新增打包程序的远程URL、含凭据URL和路径URL负测均拒绝；`py_compile`退出0。文档structure/baseline和`quality_gate.py check`退出0，治理152项、服务端34项、更新helper9项通过。这些基础检查不能提升产品门禁状态。预览服务现由本轮保留的隔离进程提供；停止服务、重启本机或迁移机器后需按009/010重建测试环境。

为便于GitHub下载，quality工作流在Intel原生门禁结束后从该运行的001候选App制作同样受限的预览DMG，并上传为`local-preview-dmg-<SHA>-<attempt>` Actions工件；上传与产品门禁分别判定，现有本机DMG的摘要不冒充未来CI工件。正式GitHub Release资产仍必须等017/018完整通过。该新增工作流步骤待当前分支CI真实验证，不能凭本机打包成功声称远端工件已经存在。

## SQLite 双库、生产管理员与第五项原生回归（2026-09-29T15:05:46Z）

用户先将本版服务端目标由 MySQL 改为 SQLite，要求可查找的测试/生产 DB 文件和可执行造数 SQL；随后明确生产库预置 `admin / 123456` 供本人使用，测试库只供 Codex 回归。按 SOP-000/002–008/009/010/014/017/018/024 更新当前基线：`database/test/test.db` 与 `database/production/production.db` 分离，生产管理员首次登录强制改密，初始化不得覆盖后续密码和成员。MySQL 迁移留给后续版本；本版发布验证使用隔离同构 SQLite 副本，不把真实生产库作为测试造数目标。

`scripts/bootstrap_sqlite.py` 在独立私有暂存目录完成 Alembic、SQL 与账号校验后才发布目标文件；生成的 `database/test/seed.sql` 和 `database/production/seed.sql` 是可执行 SQL，含每次生成的 Argon2 盐散列，不含明文密码。测试 SQL 仅匹配带内部环境标记的空测试库；重建前保存旧库，异常中断可按 `repair-test-material` 根据数据库所有权恢复 SQL/标记。生产无重建入口，服务启动只读核对，不重复造数。两份 DB、SQL 与测试所有权标记被 Git 忽略，本机文件权限均为0600；源码提交仅包含生成程序、文档与空目录占位。

本机实际执行 `init-test --run-id codex-local-20260929`、`init-production` 与 `verify` 均退出0；只读查询显示生产库仅 `admin`（admin/active/首次改密），测试库仅四个 `test-*` 账号。真实生产库的临时副本通过 FastAPI 登录 `admin / 123456` 返回200和 `must_change_password=true`，真实生产库 `sessions=0`。生产服务在`127.0.0.1:49176`运行，健康接口返回200；已安装 `/Applications/TokenMeter.app` 内置同一预览地址并实际启动进程。此为本机 `.UITesting` App 和回环服务使用，不是正式生产签名/HTTPS App 的安装验收。数据库造数/只读验证原始证据在 `.local/sqlite-bootstrap-evidence/`，生产进程保留供用户体验。

需求新增 AC-TM001-005、E2E-TM001-005 与 `production_bootstrap` 数据集。原生 runner 在专用临时根调用相同生产初始化程序，真实 UI 登录、强制改密、管理权限及重登，服务/API和库只读断言无测试账号；原生产库不参与该用例。执行顺序为001→002→003→005→004，保留004的真实签名更新路径和全体五例门禁。第五例的程序和独立治理合同已编写，**尚未取得真实原生 XCUITest 结果**；本机 `quality_gate.py iteration` 退出2，报告 `.local/e2e/gate-2817370fb06d420eb196608571f34d94/result.json` 为 `BLOCKED`，原因是只选中 Command Line Tools，0/5执行。本轮新候选须提交后在双平台重新完整执行，旧提交3/4证据不能复用。

`scripts/package_release_dmg.py` 增加正式 App 预检、Developer ID DMG 签署、Apple 公证状态确认、装订、Gatekeeper及包内摘要校验。对已安装预览 App 运行 `preflight` 退出1，按预期拒绝 UITesting bundle；打包程序的14项隔离测试通过，未执行真实 Developer ID 签署或公证。更新源治理测试先稳定复现响应已发出但`served_bytes`尚未登记的竞态，再修复事件等待；失败原件及修后日志在`.local/process/v0.1.0-20260929T074814Z/governance-update-race/`。正式 DMG、最终安装/升级原生测试、全发布平台矩阵和受保护通行证仍缺，因此不创建 Tag/Release。

本轮源码/计划整合后的本机检查：`check_docs.py --mode baseline` 退出0（69文档）、`quality_gate.py check`退出0（12功能、35场景、5个目标测试绑定，仅traceability）、governance 170项通过、server 41项通过、更新helper9项通过、`bootstrap_sqlite.py verify`退出0、`git diff --check`退出0。这些是文档、工具和服务端结果，不能提升产品迭代或发布状态。上一候选`23bbc83`的[CI run36579356475](https://github.com/lzhe72/TokenMeter/actions/runs/36579356475)上传了明确标识的预览DMG Actions工件；两架构旧四例各001–003真实PASS、004 BLOCKED，完整门禁3/4未通过。当前变更提交后的新 CI 结果另以远端不可覆盖记录为准，不能在此预填。

### 双库核验与回归隔离复核（2026-09-29T15:20:02Z）

提交前只读审查发现三处当前规则与程序不一致：双库 `verify` 在只有一个库时仍返回成功、本机预览服务可被指定为非回环 HTTP 地址、候选工作流注释仍将 MySQL 写为本版阻断。按 SOP-000/009/024 修订：`verify` 对缺任一库返回失败，服务入口拒绝非回环地址，发布注释与 SQLite 预案一致；SOP-009 修订7并更新索引。第005例的独立服务测试还在改密并加入成员后新建服务实例，断言旧密码失效、新密码有效且成员保留。固定测试库定位为 Codex 本机回归材料，原生自动化逐例用临时 SQLite 隔离；用户真实生产库不参与造数或 E2E。

上述修订后的本机完整检查：文档 baseline 69/69、追踪 12 功能/35 场景/5 目标绑定均退出0（仅规范）；governance 170、server 43、升级 helper 9 项通过，Swift 用例语法解析及双库 `verify` 退出0，`git diff --check`退出0。完整 Xcode 本机尚缺，当前候选五例原生 E2E 和正式发布继续 BLOCKED；源码提交及远端 CI 结果在后续记录，不提前声称通过。

源码候选 `3323c7dddcc44cd17c5f7b9431faf82defc7e098` 已推送分支，远端 [run36589629575](https://github.com/lzhe72/TokenMeter/actions/runs/36589629575)开始检查。推送后本机针对该干净提交执行 `quality_gate.py iteration` 退出2，`.local/e2e/gate-fd2bc7d1c2fb457394d7ea403103d9b6/result.json` 记录 `BLOCKED`、原生0/5，原因是只选中Command Line Tools；此结果不替代远端Mac运行。复核 CI 预览 DMG 时发现它原先内置端口60470，与本机生产服务及已安装预览 App 使用的49176不一致；将后续临时预览工件端口统一为49176，再由新候选完整检查。该修订不改变正式发布包或生产 HTTPS 设计。

## 升级fixture隔离路径修订（2026-09-30）

用户要求继续按SOP自动合并与发版本，适用前提仍是完整产品E2E和正式发布门禁PASS；未收到跳过测试的指令。按SOP-000/009/010/018/024复核环境与文档，远端候选`5de2283aab9600ce6117eece63d9419f5ef70352`的[run36590006685](https://github.com/lzhe72/TokenMeter/actions/runs/36590006685)governance通过，两架构各有001/002/003/005真实原生PASS，004因旧系统信任清理路径不成立而BLOCKED。完整五例迭代门禁两架构均未通过；旧候选结果不能给新提交使用。

技术决定：保留同一临时代码签名身份以验证升级后的Keychain连续性，将签名身份与私钥限制在专用临时Keychain；放弃旧的System.keychain/admin信任写入。隔离HTTPS更新源仍由本机临时CA签发，但`cloudflared`使用`--origin-ca-pool`验证回环TLS，并提供公开可信`trycloudflare.com`临时域名供App正常TLS访问。CI安装固定版本且核对SHA256；签名、公开HTTPS、失效签名包拒绝、有效包升级、会话恢复与清理均需程序实测。第004例的控制请求用随机Bearer保护；测试内容仅限合成包，不上传账号或私钥。Quick Tunnel无法使用或清理失败维持BLOCKED；探针READY也不等于产品PASS。同步修改009/010、开发/测试计划、测试执行参考、Changelog和文档目录，源码与CI程序由后续实现/回归证据验证。

文档编制阶段实际运行`python3 scripts/check_docs.py --mode structure`和`--mode baseline`均退出0，各检查69份文档、433个链接；`git diff --check`退出0。该结果只证明文档结构/基线和空白规范，不改变产品门禁。质量检查、源码回归及远端五例结果须在整合候选后另行记录。

正式发布另需最终Developer ID签名、公证DMG、安装后全量原生回归、macOS14+支持矩阵及受保护通行证。SOP-018明确受信默认分支手动候选任务的`candidate_sha`须等于dispatch的`GITHUB_SHA` tip；不能发布未合并分支或旧提交。PR #2在必需检查未通过时保持草稿，不创建正式Tag/Release，等待新提交完整CI实测后按SOP-019继续。

源码与本机检查：已移除升级fixture的系统证书信任读写，改用专用临时Keychain中的同一自签身份；HTTPS源由固定SHA256的`cloudflared 2026.9.3`临时隧道提供，隧道到回环源仍校验本次CA。候选工作流在检出代码之前及检出后核对输入SHA等于默认分支触发SHA，避免以后为未合并代码开放发布凭据。本机`check_docs.py --mode baseline`通过（69文档、433链接）、`quality_gate.py check`通过（12功能、35场景、5项绑定）、governance 173项、服务端43项、更新包工具9项及`git diff --check`通过。常用全局Python缺服务依赖，服务端检查改用SOP-009建立的隔离`.local/venv-tm001`运行；原始全局Python失败不被记作产品失败。本机`native_environment.py`实际返回BLOCKED，原生0例，原因是仅安装Command Line Tools；未触碰系统信任。新提交的两架构原生及升级结果须由远端CI另行判定，尚未标记PASS。

## 本机服务默认值与可配置地址（2026-09-30）

用户指定本机承担开发与测试，v0.1.0 App 首次默认连接 `http://127.0.0.1:49176`，登录页可更改 TokenMeter 服务地址。依据 SOP-002→003→004→005→006→007→024，新增 AC-TM001-006 / E2E-TM001-006：隔离测试服务占用默认端口，第二套 FastAPI/SQLite 用于配置切换和会话隔离；重启验证手动地址保持，非回环 HTTP 必须拒绝，HTTPS URL 应可配置。两套测试库只含合成账号，不能连接或重置用户生产库。正式包只给本机回环 HTTP 开窄例外，外部服务仍必须 HTTPS。测试机授权不等于完整 Xcode 或原生结果就绪。

生产服务器地址尚未提供，未来升级迁移内置 HTTPS 默认值单列 AC-TM010-003 / E2E-TM010-003，计划数据集为 `server_default_migration`；已有手动覆盖不能被升级改变。此项不属于本轮 v0.1.0 通过条件，若生产服务器更早就绪则在对应版本立项时前移。当前文档与追踪变更不代表第006例已实现或通过，旧五例候选的运行证据不能覆盖新六例范围；源码、数据程序、完整原生回归和正式发布门禁仍按实测结果判定。

规范冲突修订：既有 SOP-009/010/014 写死五例、SOP-017 将正式 App 的服务 API 一律限定 HTTPS。按 SOP-000 先更新总索引，再将 009/010/014/017 分别修订为 9/8/6/6；第004例仍只在专用 CI 使用隔离更新源，正式 App 只允许本机回环 API HTTP，Sparkle 更新源与非回环 API 仍使用 HTTPS。SOP-024 同步产品、架构、路线图、测试策略与版本 00–05，`program_bindings_status=planned` 等待第006例方法与双服务 runner 真正就绪。

本次文档与治理检查实际结果：`python3 scripts/check_docs.py --mode structure` 退出0（69文档、433链接）；`python3 scripts/check_docs.py --mode baseline` 退出0（相同范围）；`python3 scripts/quality_gate.py check` 退出0（12功能、37场景、6项目标测试文件绑定，`release_eligible=false`）；`python3 -m unittest discover -s tests/governance -p 'test_*.py'` 173项通过；`git diff --check` 退出0。这些结果只证明文档、追踪与治理自测，不证明第006例原生执行或正式发布可行。

### 第004例最近远端阻断与探针修订（2026-09-30）

候选 `b173f89cb194cd0d20e5a670f8320ce6fdc3d94b` 的 [CI run36655690112](https://github.com/lzhe72/TokenMeter/actions/runs/36655690112) 治理作业通过；macOS 15 Apple Silicon 与 Intel 的原生 001/002/003/005 各四例 PASS，004 在升级环境探针前置检查返回 BLOCKED，两个产品作业退出2，完整五例均未 PASS。该提交在第006例需求形成之前，不可复用其结果给六例候选。健康探针的下一版修订使用 `/usr/bin/curl` 系统信任验证公开 HTTPS 并保留更明确的诊断；源码修订尚未取得新的远端探针 READY 或 004 原生 PASS，后续必须在同一新候选上完整执行全部六例。

### 本机开发与远端原生验收路线（2026-09-30）

用户确认本机不能安装完整 Xcode，但仍将本机用于开发、SQLite 服务和预览安装。按 SOP-000/009/014/024 更新执行路线：本机源码、服务端和安装预览各按实际检查记录；原生迭代 E2E 使用现有 `quality.yml` 在 GitHub 托管 `macos-15` 与 `macos-15-intel` 上选择 Xcode 16.4，分别执行同一候选的真实 App、隔离 FastAPI/SQLite 和完整六例 XCUITest。CI 中 `127.0.0.1:49176` 是 runner 自己的回环端口，不是用户本机生产服务。每台 runner 必须核对原始 `xcresult`、候选 SHA、fixture 与清理结果；任何一例或平台缺证据仍为 BLOCKED。本机缺 Xcode 仅阻断本机原生运行，不阻断远端有效回归。远端迭代结果不得记作本机原生 PASS，也不替代最终签名/公证 DMG 安装后回归和完整发布矩阵。

### BUG-TM001-FIXTURE-004：新建 Quick Tunnel 域名的系统 DNS 生效晚于探针窗口

[CI run36658315958](https://github.com/lzhe72/TokenMeter/actions/runs/36658315958) 的 Intel 与 Apple Silicon 第004例在公开 HTTPS 就绪探针被阻断；系统 `/usr/bin/curl` 对新域名在原45秒准备窗口返回退出6、HTTP 000。对同一仍在运行的受控隧道进行有界诊断，系统请求在域名创建后约7、28、51、77秒仍无法解析，约105秒首次经正常 TLS 得到预期200，并在129、156、180、202秒持续成功。Cloudflare DoH 在7秒为 NXDOMAIN、28秒已解析；Google DoH 在7秒已有记录，说明不同解析路径生效时间不同。该证据定位为环境准备窗口过短，未观察到 App 升级断言失败；本次候选完整六例仍为 BLOCKED，不能将后续诊断成功追认为原运行 PASS。

修订009/014及测试执行参考，保持单一隧道与域名，允许最多180秒的准备等待，每约30秒留存系统TLS/状态/来源诊断；不覆盖DNS、不关闭证书验证、不重启隧道或自动重试业务用例。超过时限仍 BLOCKED，准备通过仅为第004例前提。fixture 源码与确定性负向治理用例须在同一候选中检查；修复后仍需两架构完整六例原生回归以及正式发布包门禁，当前未取得这些结果。

第006例的 Swift 配置、登录页和原生用例已写；runner 先占用49176端口再造两套数据，并将已绑定 socket 传给真实服务，健康确认前保持占用以避免误连已有服务。两套库使用固定种子42/43，测试包无注入服务地址，构建后核对 Info.plist；预览 DMG 工作流选用此候选包，打包器拒绝带注入地址的 App。数据/测试/SOP 入口均存在，manifest 的 `program_bindings_status` 从 planned 改为 ready，表示程序绑定齐备，不表示产品 E2E PASS。本机针对两套真实 FastAPI/SQLite 的账号及跨库 token 冒烟通过；focused native governance 29/29、Swift 语法解析、plist lint、文档 structure/baseline、追踪检查及 `git diff --check` 通过。本机无完整 Xcode，尚无第006例真实原生结果；需提交后的两架构 CI 执行。

整合候选提交前的本机完整检查：`python3 -m unittest discover -s tests/governance -p 'test_*.py'` 180项通过，服务端 pytest 43项通过，更新工具 9项通过；文档 baseline 69份/433链接、追踪 12功能/37场景/6项绑定均通过；Auth 与 AccountStore 的 UITESTING Swift typecheck 退出0。状态页整理后再次执行 baseline 与追踪检查，69份/435链接、12功能/37场景/6项绑定通过，`git diff --check` 退出0。原始完整治理日志保存在 `.local/governance/local-default-precommit.log`；这些本机检查不构成原生产品 E2E。为避免状态页继续将旧五例叙述当作当前结论，当前交接集中在 `docs/status.md`，历史运行链接与根因仍保存在本记录中。下一步是提交后同一候选的两架构六例 CI。
