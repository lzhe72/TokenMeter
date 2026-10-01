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

### BUG-TM001-FIXTURE-005：六例候选的更新域名仍不能由系统解析

候选 `9e61d867dc983faaa0012527353742238b72f7f9` 的 [CI run36660917395](https://github.com/lzhe72/TokenMeter/actions/runs/36660917395) 治理作业通过；macOS 15 Apple Silicon 与 Intel 两平台的 001/002/003/005/006 各五例真实原生 PASS。第004例使用同一 Quick Tunnel 随机域名等待 180 秒后，系统 `/usr/bin/curl` 仍返回 DNS 解析错误（退出6），升级产品步骤未执行，004 和完整六例迭代门禁均 BLOCKED。Intel 产生的本机预览 DMG 不构成正式发布包；PR #2 仍不能合并，未签发通行证或创建 Tag。该观察说明此前 45 秒窗口过短不是唯一已证实的阻断条件；不能把继续加长等待或重跑旧候选当成修复。

按 SOP-015 先保留该运行原始失败证据，再为准备阶段增加确定性回归：取得新域名后，在共享的最多 180 秒准备窗口内，先分别通过 Cloudflare 和 Google 的 HTTPS DNS 查询等待公开 A 记录就绪；在此之前不查询 Mac 系统解析器，以避免过早触发可能的负缓存。两方就绪后，用窗口剩余时间经 Mac 正常系统 DNS/TLS 核对公开 HTTPS 状态和隔离源响应。公共 DNS 结果仅是就绪信号，不注入返回 IP、不代替 App 的 TLS、Sparkle EdDSA 或产品断言；任一准备阶段失败仍为 BLOCKED。SOP-000/024 同步 SOP-009/014、总索引、测试执行参考、技术与测试计划、Changelog 和当前状态。此处只是新候选的设计与源码修订，尚未取得两平台第004例原生 PASS，正式签名/公证、最终安装包回归及受保护发布门禁另按 SOP-017/018 判定；源码 PR 合并须先取得完整迭代与适用检查 PASS，不要求提前签发正式发布通行证。

为独立定位环境，`quality.yml` 新增默认关闭的手动 `environment_probe_only` 输入。显式开启时，两个 Mac 只运行 `native_environment.py`，检查/工件标记 `environment-diagnostic`，不运行产品六例、不制作预览 DMG，也不产生 PR 合并或发布资格；PR/push 和默认手动触发仍走完整产品门禁。原生 runner 对独立探针的父进程采用有界 1800 秒超时，以容纳临时签名、取得域名、共享 180 秒 DNS/TLS 准备和清理；不延长域名窗口或重试产品用例。该诊断路线及 DNS 前置检查均需通过工具回归和实际 Mac 诊断验证，不能预填 READY/PASS；随后仍需全量六例迭代回归。

本次本机检查：`python3 scripts/check_docs.py --mode structure` 与 `--mode baseline` 均退出0，各核对69份文档、435个链接；`python3 scripts/quality_gate.py check` 退出0，覆盖12项功能、37个场景与6项测试绑定，报告明确 `release_eligible=false`；`git diff --check` 退出0。整合工具回归 `python3 -m unittest discover -s tests/governance -p 'test_*.py'` 184项通过，原始日志在 `.local/governance-dns-final.log`；更新源 focused 回归12项通过，日志在 `.local/update-source-dns-final.log`。这些只证明规范、追踪和工具检查，DNS 前置修订及独立诊断尚无实际托管 Mac READY，也无第004例原生产品 PASS。

### BUG-TM001-FIXTURE-006：双公共DNS已发布后 Intel 系统解析仍失败

修正上段“独立诊断尚无实际 Mac READY”的时间点：[环境诊断 run36663159461](https://github.com/lzhe72/TokenMeter/actions/runs/36663159461) 已在候选 `cc5a87b6ec061c77e354e249597302b457887fd4` 的两台托管 Mac 运行。Apple Silicon 的 `environment-diagnostic` 作业 READY；Intel 的 Cloudflare 与 Google HTTPS DNS 查询在取得随机域名后7.3秒均返回 published，但正常系统 `/usr/bin/curl` 在约0.3、31.6、63.3、95.0、126.8、156.8秒仍为退出6/HTTP000，180秒准备窗口到期后环境报告 BLOCKED、`executed_cases=0`。因此“先等两个公共DNS发布”已被实际证明不足以确保 Intel 的系统解析路径就绪；两平台没有共同 READY，不能把 Apple Silicon 的探针结果追认为产品第004例 PASS。候选的[完整 PR 回归 run36663136535](https://github.com/lzhe72/TokenMeter/actions/runs/36663136535) 在本条记录写入时仍运行，须随后核对原始 `xcresult`；当前 PR 合并和正式发布都不具备门禁条件。

Intel 诊断报告同时显示 `cleanup_completed=false` 与 `cleanup_errors=[]`，字段没有准确区分“主操作失败”和“清理实际完成”。按 SOP-015 保留原报告并修正程序：`finally` 按本次实际清理错误设置该字段；主操作 BLOCKED 且清理成功时应为 true，主状态不改变。为定位系统解析差异，按 SOP-000/009/014 将首次系统 `curl` 退出6后的只读诊断写入规范：`scutil --dns`、同一合成域名的 `dscacheutil`、默认与 `@1.1.1.1`/`@8.8.8.8` 的 A/AAAA `dig`、curl版本与 `--ipv4` HTTPS 健康请求，另读取 `/etc/resolv.conf` 的 nameserver/options。最多10个子命令各5秒，整组60秒且占原共享180秒窗口；无关搜索域脱敏、截断后保存 `update-dns-diagnostic.json`；`dig +stats` 保留响应来源与耗时。该诊断不改变系统 DNS/hosts/信任、不延长等待、不重试产品或替代正常系统 TLS 验收。以上为待实现与验证的修订方案，尚无新候选第004例原生通过证据。

### BUG-TM001-UPGRADE-001：升级安装后 App 构建号未达到 101

更正上段记录时“完整 PR 回归仍运行”的状态：[CI run36663136535](https://github.com/lzhe72/TokenMeter/actions/runs/36663136535) 已结束，GitHub 分支头为 `cc5a87b6ec061c77e354e249597302b457887fd4`，实际检出并测试 PR 合成合并提交 `83910695b9a244804ac35d5f2595bc026c18cb67`。macOS 15 Apple Silicon 与 Intel 均真实构建、启动 App 并执行全部六例；001/002/003/005/006 各 PASS，第004例两平台均为确定性 FAIL，`xcodebuild` 退出65。第004例的 DNS 发布和系统 HTTPS 环境前提在本次两平台产品运行中通过；此结果不改写独立环境诊断 run36663159461 的 Intel BLOCKED，两次运行使用不同临时隧道与域名。

原生失败内容为：点击 Install and Relaunch 后等待90秒，`app.build` 静态文本没有变为预期的 `101`，原始断言 `Asynchronous wait failed: Exceeded timeout of 90 seconds`。机器报告逐平台 `executed_cases=6`、`passed_cases=5`、004 `state=FAIL`、`release_eligible=false`，无清理错误；这证明当前候选没有完成004验收，不能仅凭环境就绪或预览 DMG 放行。原始 job 日志位于 `.local/ci/36663136535-arm64/job.log` 和 `.local/ci/36663136535-intel/job.log`，远端 Actions 工件保存原始 `xcresult` 与附件，正在按需检查更新源请求、Sparkle 事件、安装重启和版本读取以定位根因。当前不能断定是下载、签名、安装、重启还是 UI 读数问题，也不调整90秒预期来消除失败。

按 SOP-015 保留此双平台失败基线和 BUG-TM001-UPGRADE-001 追踪；查明实际失败环节后补稳定回归并修最小原因，再执行 SOP-013/014 的新候选完整六例与两平台检查。产品迭代门禁现为 FAIL，PR #2 不可合并；正式签名、公证、安装后支持矩阵与 SOP-018 通行证仍另外缺失。

BUG-TM001-FIXTURE-006 的只读诊断与清理字段修订现已在未提交工作树落盘，更新源 focused 14项、环境探针4项及治理全套188项通过；全套原始日志为 `.local/ci/local-governance-188.log`。这更正前文“待实现”的源码状态，但没有新的远端诊断或产品验收结果。文档 structure/baseline 69份/435链接、追踪12功能/37场景/6绑定与`git diff --check`均退出0，均不授予发布资格；BUG-TM001-UPGRADE-001 仍须依原始原生附件确定修复。


### BUG-TM001-UPGRADE-001 根因复核与内部应用新基线（2026-09-30）

上述“不能断定安装是否成功”是读取原始文字断言时的阶段性结论。随后逐帧复核该次原生测试视频：Sparkle 已实际安装并重启到构建号101，系统弹出 Keychain 凭据访问密码提示，旧 UI 因会话未恢复而未显示 `app.build`，最终004原生断言超时。历史 [run36663136535](https://github.com/lzhe72/TokenMeter/actions/runs/36663136535) 两平台 5/6、004 FAIL 的机器状态保持不变，独立DNS诊断的 Intel BLOCKED 也保持为另一运行。曾尝试制定真实 Apple Development/Developer ID 团队签名路线；本机有效 identity 为0，远端从无四项签名 secrets。用户随后明确本项目仅团队内部使用，无需把付费 Apple 开发者账号作为本轮开发前提。此前临时建立的空 `native-e2e-signing` GitHub environment 已撤回；配置/清理证据位于 `.local/git-sync/native-e2e-signing/`。这是一项新需求与设计变更，不追认历史004通过。

按 SOP-002→007、000/024 重新定义 TM-001：登录页“在此设备上自动登录”默认开启且可关闭。服务端仍签发随机可撤销 token，固定30天过期，不滑动或通过 `/v1/me` 续期；开启时客户端只保存 token 至当前用户的受保护文件（目录0700、文件0600、当前uid、拒绝symlink、原子写、按规范化API origin隔离），关闭后本次成功登录仅内存持有并清除当前origin旧文件，重启回登录页。自动恢复前必须以真实 `/v1/me` 验证；离线、过期、撤销不进入已登录。退出、改密、重置、停用撤销相应会话；离线退出本地清除、仅进程内保留待重试撤销且提示服务端未确认。旧 Keychain 不迁移，旧预览用户首次需重新登录。同设备仅指本机文件保存范围，不是硬件绑定；同uid进程可读，复制 token 仍可能在别处使用。

测试继续使用原六例稳定 ID；001/003/004/006 扩展开关、过期/撤销、升级重启、origin隔离断言。UITESTING 每例由 runner 创建唯一临时凭据目录并将同一真实绝对路径写入候选/高版本 Info.plist，供 Sparkle 自主重启后读取；测试不得触碰生产目录或旧 Keychain。带 `TMTestCredentialsDirectory` 的测试 App 离开 runner 后不适合当作用户预览包；打包器/CI 须拒绝/停止将其生成本机可安装预览 DMG，保留测试 App 压缩件供诊断。内部最终 DMG 需要无测试路径构建、包级原生安装升级矩阵与专用机器门禁；公开 Developer ID/公证流程另保留。两者都仍 BLOCKED，不以预览包或源码迭代替代。

本轮设计修订后实跑 `python3 scripts/check_docs.py --mode structure`、`--mode baseline` 与 `python3 scripts/quality_gate.py check`，均退出0：69份文档、435条链接、12项功能、37个场景、6项绑定；报告 `release_eligible=false`。这是规范和追踪基线，不是新行为的实现、六例原生 E2E 或任一 profile 的发行 PASS。当前准备按 SOP-011/012 补稳定红测与最小实现，之后同候选两架构完整回归。

本轮版本 `00-manifest.json` 已登记 `distribution_profile=internal` 作为机器可查的发行目标；不表示内部门禁程序已经实现。完成全局规范与 SOP-017/018 的 profile 修订后再次实跑 `check_docs --mode structure`、`--mode baseline`、`quality_gate.py check` 和 `git diff --check`，全部退出0；此时文档69份/433链接、12功能/37场景/6绑定，`release_eligible=false`。历史上435链接对应旧文档快照，当前目录链接数以本次运行的433为准。

### 同设备自动登录的基础回归与程序绑定（2026-09-30）

按 SOP-000 先更新总索引，再将 SOP-013 修订为4：在 macOS 上由 Command Line Tools 执行 `python3 scripts/test_device_credentials.py`，编译真实 `Auth.swift` 与 Foundation 断言源 `tests/macos/DeviceCredentialsTests.swift`，将凭据文件权限、符号链接、类型、origin隔离与原子替换作为进入原生 E2E 前的组件检查。两个程序已落盘并登记 `00-manifest.json`、文档目录与03/04计划；登记和源码存在不代表执行 PASS。SOP-024 同步 AGENTS 与测试执行参考。该组件检查无需 XCTest，不能代替原生六例或最终安装包测试。

服务端固定30天期限先有真实失败基线：`tests/server/test_auth.py` 的相关检查在旧实现上出现2失败、1通过，原始记录 `.local/verification/automatic-login/server-red-safe.log`；修改后隔离服务端全套 `tests/server` 为45通过、1个依赖弃用警告，原始记录 `.local/verification/automatic-login/server-green.log`。这只证明服务端基础回归，不证明 App 自动登录、升级或发布。新 Swift 组件和两平台原生六例结果仍需以各自真实命令与 CI 原始证据追加。

本次程序绑定与规范修订后实跑 `python3 scripts/check_docs.py --mode structure`、`--mode baseline` 和 `python3 scripts/quality_gate.py check`，全部退出0：69文档/433链接、12功能/37场景/6绑定，`release_eligible=false`；`git diff --check` 退出0。旧 CI 把带 `TMTestCredentialsDirectory` 的 UITESTING App 包装成预览 DMG 的步骤已移除，打包器增加拒绝该测试路径的保护；目前仍没有新的可分发内部 DMG，SOP-017/018 的内部发行门禁保持 BLOCKED。

本机 `python3 scripts/test_device_credentials.py` 最终编译并执行13例，0失败，原始记录 `.local/ci/device-credentials-13.log`。并发原子替换边界曾真实红测失败：`.local/ci/device-credentials-final.log` 中该例 FAIL（当时程序共11例、1失败）。修复针对已打开的旧 inode 在原子替换后允许链接数0，仍拒绝硬链接数大于1；重新执行该场景及全套13例 PASS。最初测试 fixture 的 `/var` 路径别名使用 `realpath` 修正，未放宽生产代码的符号链接拒绝。`xcrun swiftc -swift-version 5 -typecheck` 对 `Auth.swift`、`AccountStore.swift` 通过，UITest 源码语法解析也通过；这些仅证明源码检查。更新包工具12项通过，记录 `.local/ci/automatic-login-package-tools.log`。这仍未验证真实原生 App 升级后自动登录；旧远端004 FAIL 保留，必须由新候选完整六例重新判定。

补录最终文档核对：增加当前状态到本记录的证据入口后，再次实跑 `python3 scripts/check_docs.py --mode baseline`、`python3 scripts/quality_gate.py check` 与 `git diff --check`，均退出0；文档69份/434链接、12功能/37场景/6绑定，`release_eligible=false`。

提交前整合检查：治理工具193项全部通过，完整日志 `.local/ci/automatic-login-governance.log`。只读审查发现 XCTest 的 Foundation 路径解析会保留 `/var` 别名，已改用系统 `realpath` 核对 runner 的真实路径；退出登录先删除本机凭据再等待服务端撤销；测试配置须具有已存在、当前用户所有、0700的规范路径，缺失时明确错误且不回落生产目录。原生源码解析和账号模块类型检查退出0；新原生结果须在提交后由 CI 产生，未预填通过。

### 同一活跃更新源的第004例环境基线（2026-09-30）

最新[完整PR回归 run36667893097](https://github.com/lzhe72/TokenMeter/actions/runs/36667893097)使用分支头`528859cfde624f31a071f76144ee26ae6a377d7f`，两平台实际检出PR合成合并提交`4df5efb672362f09ec57b86839b9a09b6763793b`。macOS 15 Apple Silicon与Intel各有001/002/003/005/006五例真实PASS；004在更新源准备阶段正常系统`curl`持续退出6/HTTP000，未执行该例原生升级，完整迭代均BLOCKED。原始job日志为`.local/ci/automatic-login-arm-job.log`、`.local/ci/automatic-login-intel-job.log`；门禁与逐例报告在`.local/ci/summaries/36667893097/{arm64,intel}/`。Apple Silicon公共DoH A记录约6.4秒已发布，系统解析直至约155秒仍失败；Intel公共DoH约12.7秒发布，系统解析至约155秒仍失败。只读DNS诊断在同一时刻见默认解析器`192.168.64.1`与Cloudflare UDP A为NXDOMAIN、Google UDP A已发布；AAAA记录TTL 300不能据此推断A记录负缓存持续300秒。此运行与旧run36663136535的004产品FAIL不同，旧FAIL不被新环境BLOCKED改写。

复核执行链发现：原独立`native_environment.py`先创建、验收并销毁一套临时签名身份、隧道与随机域名；004随后又创建另一随机域名。独立诊断的READY仅属于已销毁实例，不能作为004当前域名的准备证据。按SOP-000/004/024先修SOP索引及009/010/014，再同步03/04计划、测试执行说明、状态、Changelog和目录。修订设计要求004在本例拥有的一组活跃`SigningIdentity`与`UpdateSource`上完成签名、同一域名公共DNS及Mac正常系统DNS/TLS准备、本次回环origin的`security verify-cert`，持续保有同一域名、CA和专用Keychain至无效包拒绝、有效包真实升级及请求核对结束，最后统一`finally`清理。独立环境诊断保留零产品用例地位；不得重建域名、延长180秒准备窗口、改系统DNS/hosts/信任、关闭TLS或重试业务取绿。该条为待实现的设计和阻断证据，不能声称新方案004已PASS；源码修订及同一新候选两架构完整六例仍须实跑，PR#2保持草稿，内部/公开发行均无通行证。

本次仅文档修订的实际检查：`python3 scripts/check_docs.py --mode structure`、`--mode baseline`均退出0，核对69份文档和435条链接；`python3 scripts/quality_gate.py check`退出0，追踪12项功能、37个场景、6项程序绑定且`release_eligible=false`；`git diff --check`退出0。旧记录中独立探针由原runner子进程设置1800秒父超时，只描述当时实现；移除“先探针、后新域名”的调用后，不能再把该超时当成004或独立诊断当前保证。文档检查不构成源码修复、产品E2E或发行通过。

独立审查确认单实例执行链和失败阻断保留，并发现新增环境SHA此前只记录、未由父验证器核验。按SOP-000/024先在SOP-014修订13及04测试计划明确不可变准备快照和父报告清理责任，补充父验证器对环境文件路径、摘要、候选和状态的独立校验；该证据合同待源码实现及负向回归，不代替产品原生结果。

源码整合完成：004直接创建并保有一组签名/更新源资源，保留origin证书核验；父验证器重新核验准备快照及同候选/同run绑定，最终清理仍以父报告为准。`python3 -m unittest discover -s tests/governance -p 'test_*.py' -q` 最终197项通过，退出0，原始日志`.local/ci/live-update-fixture-governance-final.log`（上一版195项日志`.local/ci/live-update-fixture-governance.log`保留）。`check_docs.py --mode baseline`核对69份/435链接，`quality_gate.py check`核对12功能/37场景/6绑定，均PASS且不授予发布资格；日志`.local/ci/live-update-fixture-baseline.json`及`live-update-fixture-traceability.json`。已核对远端分支仍为528859c、master仍为548c582；当前提交只推送原版本分支并触发新的完整六例两平台回归，未预填通过或合并。

### 用户指定同机回环更新源与配置管理页（2026-09-30）

用户明确更新源就在运行App的同一台Mac：API默认`http://127.0.0.1:49176`，Sparkle更新feed默认`http://127.0.0.1:49177/appcast.xml`，管理页允许安全修改更新URL并恢复本版内置默认；不再用公网Quick Tunnel。两台GitHub Mac各自提供自己的回环API和更新服务并执行全六例，不能把远端runner的`127.0.0.1`说成用户此Mac。第004例固定49177只启动一组更新源，候选/高版均不注入feed URL，从内置默认地址测试坏EdDSA包拒绝、有效包真实安装重启、构建号变化和`/v1/me`无交互恢复。第006例在配置页测试合法合成更新URL的保存、重启和恢复默认及非法URL拒绝；不连接合成地址、不另开第二更新源。固定公钥、`SUVerifyUpdateBeforeExtraction`与下载地址/重定向安全校验继续保留；仅精确回环HTTP，非回环必须HTTPS。当前源码仍是旧公网fixture，配置页、`--use-default-feed`和同机更新runner属于待实现；本机已安装旧App构建100且`SUFeedURL`/`SUPublicEDKey`空，不能用它当新候选测试。

保留[CI run36670563197](https://github.com/lzhe72/TokenMeter/actions/runs/36670563197)原始结果：分支头`7e33e39`、PR合成测试提交`aaf9594`。Apple Silicon五例原生PASS，004在旧公网随机域名正常系统DNS处BLOCKED；Intel六例原生断言PASS，但父验证器因`Native bundle was changed after execution`最终FAIL，故两平台完整迭代都未PASS。Intel原始日志`.local/ci/live-update-fixture-intel-job.log`的子报告列六例PASS，紧接父报告FAIL；Apple Silicon原始日志`.local/ci/live-update-fixture-arm-job.log`列五例PASS与004 BLOCKED。Intel初始bundle摘要`4048d992...`与最终工件摘要`5040453d...`不同，34个文件经逐项只读重算证实差异；目前不能断定具体写入者。当前证据合同改为所有`xcresulttool`解析和附件导出退出后计算完整bundle摘要，父仍重算全bundle且不排除SQLite，任何后续变化继续FAIL。旧候选不因此追认为PASS。

按SOP-000先改索引和009/010/011/014/017，再经002–007及024同步验收定义、功能拆解、设计、测试、发布预案、产品/架构、数据库说明和状态。用户本机CLT+AX原生驱动可在后续独立计划中实施；当前`AXIsProcessTrusted=false`且执行器不存在，本机E2E不得声称PASS，也不阻断两台CI既有XCUITest门禁。新回环fixture、新设置页和证据摘要顺序须先实现、负测、同一候选两平台完整回归；本段仅是设计基线及旧运行归档，不签发通行证或分发DMG。

本次同机回环文档修订后，实际执行`python3 scripts/check_docs.py --mode structure`和`--mode baseline`均退出0（69份文档、436条链接），`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6程序绑定，`release_eligible=false`），`git diff --check`退出0。新增CLT地址配置组件测试入口已登记到manifest和SOP-013，但文件存在与文档检查不证明该组件通过，更不证明新回环源六例E2E或内部DMG门禁通过。

同机回环原生编排源码的阶段性本机工具证据由整合负责人提供：`tests/governance/test_native_e2e.py`聚焦39/39通过，日志`.local/ci/loopback-native-green-final.log`；此前真实红测7处异常见`.local/ci/loopback-native-red.log`，默认feed包入口红测1处异常见`.local/ci/loopback-default-bundle-red.log`。这些仅证明runner/工具负测，不是新候选两架构六例原生产品结果。旧公网DNS专项fixture测试可由同机source nonce、固定端口归属、URL边界与清理负测取代；必测产品集合仍完整保留001–006六例，不能通过删旧工具测试减少产品场景。

### 第004例选中URL与重定向负测数据合同（2026-09-30）

在既定同机49177单一更新源、固定公钥及一个E2E-TM001-004用例内，补明确四阶段数据顺序：鉴权`control/forbidden`发布enclosure=`http://example.invalid/update.zip`，App应在传输前以`update_source_rejected`拒绝且仍build100；鉴权`control/redirect`发布本机`/redirect.zip`并302到该非回环HTTP URL，必须以ATS `NSURLErrorDomain -1022`（`update_transport_rejected`）拒绝且仍build100，DNS失败不算；原鉴权`control/invalid`恢复完整坏签名包，EdDSA拒绝/build100；原`control/valid`发布有效包，Sparkle真实安装重启至101并经`/v1/me`恢复。三条负测控制URL由runner通过`TM_TEST_UPDATE_{FORBIDDEN,REDIRECT,INVALID}_CONTROL_URL`注入，保留原Bearer控制授权、签名key与fixture清理。`.invalid`保留域名仅用作非回环HTTP拒绝目标，App不主动请求真实公网服务；本轮产品必测集合仍六例，第004例600秒上限未放宽。此为SOP-010/014和03/04计划新增的执行合同，具体源码和原生证据须分别实测，不能预填PASS。

上述四阶段合同同步后实际执行`check_docs.py --mode structure`与`--mode baseline`均退出0（69文档/436链接），`quality_gate.py check`退出0（12功能/37场景/6绑定，`release_eligible=false`），`git diff --check`退出0。只核对文档和追踪，不是四阶段原生结果。

### BUG-TM001-RUNNER-003：父级解析期间原生结果可变化（2026-09-30）

独立审查发现父门禁原先只在自己调用 `xcresulttool` 前核算 `native.xcresult` 完整摘要；若父级解析使 bundle（含 SQLite）变化，单次校验后仍可返回 PASS。先增加模拟父级解析写入 bundle 的治理负测，旧代码真实失败：`.local/ci/loopback-parent-verifier-red.log`，40项中1项失败，未抹除失败证据。随后父级在全部原始解析完成后再次逐文件核算并与子级记录摘要比较，任一次不符均拒绝；SOP-014、04测试计划及测试执行规范同步该判据。整合治理 `python3 -m unittest discover -s tests/governance -p 'test_*.py'` 实际198/198通过，退出0，原始日志`.local/ci/loopback-integrated-governance.log`。

同机回环基础检查实际结果：更新fixture聚焦16/16通过（`.local/ci/loopback-fixture-focused.log`），更新包helper16/16通过（`.local/ci/loopback-integrated-helper.log`），本机Swift凭据组件13/13通过（`.local/ci/loopback-integrated-credentials.log`），本机Swift地址配置组件48项断言0失败（`.local/ci/loopback-integrated-endpoints.log`）。本次文档同步后实跑 `python3 scripts/check_docs.py --mode baseline`、`python3 scripts/quality_gate.py check` 和 `git diff --check` 均退出0：69份文档/436链接、12功能/37场景/6绑定，`release_eligible=false`。这些均为程序/规范基础验证，新候选尚未在两台Mac执行完整六例，PR合并和内部DMG发行仍不具资格。

### 同机更新两平台通过与源码合并（2026-09-30）

SOP-013/014/019/022：CI [36674477502](https://github.com/lzhe72/TokenMeter/actions/runs/36674477502) 在macOS15.7.9 arm64与x86_64各执行六例、子结果与父原始证据门禁均PASS，清理完成。分支头3ad0d7e、PR测试合成4f4d887与最终merge e011857的源码树一致（2b723f41d96256e962cf04ed9105dfb1e2985739）。PR#2已合并master并快进同步本地，未绕过检查。原始日志 `.local/ci/loopback-arm-job.log`、`loopback-intel-job.log` 与治理日志 `loopback-governance-ci.log`；两平台报告 `.local/ci/summaries/36674477502/`；远端核对 `.local/git-sync/loopback-3ad0d7e/handoff.json`。基础198治理、45服务、16helper通过，Mac凭据13项/地址48断言通过。`release_eligible=false`，没有正式Tag/Release/最终DMG。此前状态页停留在提交前的待运行事实，本次同步纠正；新旧候选不得混用。

### 内部发布、详细用例与两日复盘任务（2026-09-30）

用户明确继续发布，同时指出docs看不到每功能test case并要求梳理两天项目对话。按SOP-000/006/024补详细用例总索引和逐功能文件，不以机器矩阵摘要代替步骤/数据/预期；按SOP-023/024对对话与Git/CI交叉核对复盘。发布仍按017/018以实际生产bundle和最终DMG执行，内部应用不把付费Apple账号或公网域名作为前提。需要真实安装包程序、原生最终包矩阵和受保护机器通行证，现有缺口必须实现并测试，不能改写旧迭代报告作为发布报告。该版本尚未发布，继续原release_id和新internal-release分支。

用户明确选择“以目前的测试条件为准，先走通链路”：内部首版支持范围调整为macOS15 arm64/Intel。官方可用矩阵显示个人仓库缺少macOS14 Intel大型runner条件，本机为macOS15，故不能维持未经测试的14承诺。该变化已同步产品、需求、设计、测试和发布计划；不是删除功能用例，六例全部保留。详见内部发布设计。

### 2026-09-30 · 受保护发布环境准备（SOP-009/018/019）

- 用户已授权自动提交、PR、合并和内部发布；据此配置远端master必须通过 `governance`、`product-e2e (macos-15)`、`product-e2e (macos-15-intel)`，要求与最新基线一致，禁止管理员绕过、强推及删除。release-validation环境仅允许master分支部署，不添加人工审批。
- 三次GitHub API写入退出0，随后读取分支保护与环境部署策略确认生效。证据保存 `.local/git-sync/internal-protection/`；配置成立不表示最终包门禁已通过。
- 已安装App采用 `XCUIApplication(url:)`，测试runner保留fixture控制变量，被测App启动环境主动移除测试与签名变量；两平台各顺序六例，标准用户目录仅允许专用托管runner在先不存在且已取得所有权后使用/清理。

### 2026-09-30 · 本轮文档基线与用例门禁（SOP-006/008/011/024）

- 补齐[逐功能详细用例](../../docs/testing/cases/README.md)，12份功能文件覆盖37个唯一用例；TM-001六例绑定真实SwiftUI测试，未来31例保留planned及数据/程序缺项。[两日复盘](../../docs/retrospectives/2026-09-29--2026-09-30-tokenmeter.md)最初整理24个案例，后续根据本机开发、Electron选型和DMG本地保存的用户决定增至27个；可恢复对话的覆盖限制已注明。
- 用例文档机器检查拒绝缺少文档、缺漏/重复用例、没有独立预期、隐藏操作步骤和不匹配验收ID。治理红测45项中的6个失败观察保留 `.local/ci/case-documents-red.log`；实现后45项全部通过，见 `case-documents-green.log`。
- 实施前严格基线83份文档/572链接及37用例追踪通过，证据 `.local/ci/internal-baseline-before-implementation.json`、`internal-trace-before-implementation.json`。复盘入档后重新核对。设计关键边界已确认，进入内部打包、已安装App执行器及父级门禁开发；原生验证尚未运行，不能沿用旧候选PASS。

### 2026-09-30 · 内部包实现与基础验证（SOP-009/011/012/013/017–020）

- 稳定自签代码签名与EdDSA密钥在本机私有目录生成，环境secret写入并读回名称；公开配置只含公钥/证书摘要。没有导入用户钥匙串或改变系统信任。root读取真实master保护与环境策略作为后续机器核验基准。
- 内部打包工具、父级原件门禁、Git发布与本机分发程序已建立；最终安装包执行器与原生installed模式按同一清单整合。独立review发现并修复工作流未创建输出父目录、缺config参数、CI身份字段不一致；父门禁新增必需protection原始证据。
- 官方Sparkle/Apple资料说明非Apple团队签名与默认library validation不兼容。因此内部构建明确关闭Hardened Runtime/library validation，仍强制稳定非ad-hoc代码签名、固定证书、EdDSA及真实升级。公开profile的Developer ID/hardened要求保留。此为基于资料的预先兼容修正，不宣称已经在本轮包重现崩溃；3项配置回归先失败后修复，内部16+公开14项通过，证据 `.local/ci/internal-runtime-{red,green}.log`。
- 服务端45项通过（`internal-server-first.log`），升级helper16项通过（`internal-helper-first.log`）。首轮整合治理225项中仅1个正在编写的父门禁入口缺失错误，已保留 `internal-governance-first.log`，不作为通过；完成后重跑全部。相关155项独立复验已通过（`internal-release-independent-review-tests.log`）。
- 新增本机分发4项工具检查、发布资产/远端约束7项检查、父门禁原始证据负测18项通过；packager另用本机CryptoKit验证真实有效签名并拒绝篡改（`internal-package-crypto-smoke.log`）。工具检查不冒充最终包或产品E2E。源码入口缺失的初始红记录只表示工具尚未建立，不称业务红测。
- 工作流YAML曾在本机解析发现 `--only-binary=:all:` 未使用多行块，已在提交前修复并重新解析5个job及依赖链，证据 `internal-workflow-yaml.json`。最终包和正式发布结果尚待受保护CI实际产生。

- 本机独立执行新SQLite恢复helper：在新临时根调用真实生产初始化程序，备份→另一库恢复→逐表与完整性核对→第三私有副本启动真实API验证管理员登录，并清理进程和DB/WAL/SHM。结果PASS但仅属隔离数据库/API检查，无产品E2E资格，证据 `.local/ci/internal-sqlite-restore-smoke.log`。用户生产库未访问或修改。
- 精确DMG三项白名单新增行为红测发现额外文件会被旧工具接受，修复后内部19+公开14项通过，证据 `.local/ci/internal-dmg-layout-behavior-red.log`、`internal-package-layout-green.log`；另以临时合成镜像确认hdiutil正常布局，未使用用户App。

### 2026-09-30 · 内部候选整合检查与提交（SOP-013/019/022）

- 最终安装包runner与父门禁完成字段、清单、归档路径及资源清理合同核对；真实执行顺序001/002/003/005/006/004保持不变。稳定签名生产App的自动检查保持启用，测试源初始提供空合法feed，受控四阶段后才提供升级。
- 全治理259项通过、服务端45项通过、升级工具16项通过；基线86文档/615链接和12功能/37用例追踪通过，工作流5个job及发布依赖解析通过，diff无空白错误。原始证据为 `.local/ci/internal-governance-final.log`、`internal-server-first.log`、`internal-helper-first.log`、`internal-baseline-final.json`、`internal-quality-final.json`、`internal-workflow-yaml-final.json`。
- 最终包的原始双平台xcresult归档、逐例报告、父门禁判定与通行证将随原DMG作为Release资产保存；发布程序在上传前和GitHub摘要读回时核对。新增归档验证纳入发布工具9项检查。
- 接下来推送源码PR，执行两台Mac完整开发回归并在检查通过后合并，再由同SHA master必需检查与内部最终包流程判定发布。未预填任何新候选产品PASS或Release结果。

提交20e3936后的最终清理边界复核：对本次归属App发送终止后最多等待5秒，确认退出再清理标准凭据/defaults；不会终止其他路径的App，超时保持阻断。新增2项回归后全治理261项通过，证据 `.local/ci/internal-governance-cleanup-final.log`。此为执行器修复，不重试失败业务用例。

## Electron本机发行基线修订（SOP-000/004–008/024）

用户明确所有开发/测试/发行在本机、Git仅源码迭代、DMG本地保存，并提供DataBuddy技术栈。决定采用Electron/React/TypeScript/Vite/electron-vite/node:test/Playwright Electron/electron-builder，保留FastAPI/SQLite与全部六例；当前仅macOS15 Intel。完整Xcode从新路线前提移除，旧Swift与CI保留历史。

先同步SOP索引与详细文件、AGENTS、版本01–05、当前架构、详细用例和目录。新执行器未实现仍BLOCKED，不以旧Swift绑定或旧CI通过放行。默认更新清单迁移version.json，Ed25519签ZIP、原生Squirrel负责安装，元数据版本需与签名包实际Info一致。现有用户App/库/49176服务不动；测试动态端口经真实UI设置。固定证书Security探针证据.local/ci/squirrel-signature-probe-l5vcxdzz/result.json只验证同签名要求，不代表完整升级已通过。

文档基线实际检查结果将随后追加；此条不宣称通过。

### 2026-09-30 · 两日复盘补审（SOP-023/024）

根据用户要求，重新回读本项目可见的开发、仓库绑定与项目解释会话，并与版本记录、Git/CI 证据交叉核对。复盘原有24例已覆盖早期规范、实现和原生验收问题；本次补 RET-025–027，分别记录 Actions 耗时引起的本机执行决定、Xcode 依赖误解与 Electron + Playwright 选型、以及最终 DMG/证据仅在本地按版本保存。主开发会话本次回读快照为3页26个turn，其中11个空items且末轮仍在进行，故不宣称取得两天全部逐字对话；无法恢复的部分保留覆盖限制。历史 SwiftUI PASS 与新路线待验收状态分开记录。

本次复盘文档、索引与状态同步后，`python3 scripts/check_docs.py --mode structure` 两次退出0（首次87份文档/613条链接，随后共享工作区其他文档同步时87份/600条链接，均无错误），`git diff --check` 退出0；27个 RET 编号连续，逐例检查问题、决策、方案、结果和经验五项，补齐 RET-007 原缺少的独立结果标签。以上只证明文档结构和复盘内容检查，不代表 Electron 产品 E2E 或本地发行门禁通过。新的设计/执行基线仍按本轮迁移工作另行核验。

### SOP-008新基线实际检查

structure、baseline与quality_gate check均退出0；87文档、600链接、12功能/37用例追踪通过。证据.local/ci/electron-doc-{structure,baseline,quality}.json。语义已同步Electron本机、version.json、TypeScript打包、六例不减少和本地发行；旧绑定明确只历史，新执行绑定planned不允许回落旧门禁。进入009–013并行实现，产品E2E仍BLOCKED。独立服务回归45例通过，日志.local/ci/electron-server-before.log，不计作Electron E2E。

### Electron工程就绪与真实探针（SOP-009–014/017）

- 绑定文件已真实建立，manifest执行绑定改为ready；baseline/quality检查通过（87文档、598链接、12功能/37用例/6绑定），证据`.local/ci/electron-bindings-{baseline,quality}.json`。ready不代表业务PASS。
- 集成治理279项通过，日志`.local/ci/electron-governance-integrated-1.log`。父门禁新增004请求语义负测，先保留缺函数失败`local-update-gate-red.log`，实现后6项门禁检查通过`local-update-gate-green.log`；属于治理测试。
- GitHub直接下载超时后，使用官方API取得同一Electron44.5.1 x64运行时，大小134208970字节，SHA256同时匹配npm官方checksums和GitHub资产。证据`.local/ci/electron-runtime-download.json`；没有修改代理或跳过校验。
- 真实Playwright开窗探针通过，验证默认API与contextIsolation/sandbox/nodeIntegration以及renderer无require；证据`.local/electron-probe-c0922cf1-c1e6-4530-9563-154b92d0b55f/`。仅009环境验证，尚非六例业务E2E。
- 签名包probe03独立检查拦截builder遗留ATS任意HTTP设置；保留失败并在代码签名前整段替换为仅127.0.0.1例外，继续新probe验证。Squirrel固定用户cache/launchd归属另外纳入004前置与清理，不能仅靠userData声称隔离。
- 当前尚无Electron完整六例PASS、正式DMG通行证或Git版本发布。既有生产App、数据库和服务未用于测试。

### 用户追加HIG界面与图标要求

按SOP-004/006/024先更新设计/开发与测试计划，再实现。采用本机原生窗口/菜单与HIG内容布局，保留已选Electron路线满足无完整Xcode的本机E2E；原生优先偏好和现有技术约束同时记录，不冒充SwiftUI。图标由项目原创SVG导出ICNS，最终包待全部界面修正后重建；已有probe05仅开发联调。

### 本机安装包与父门禁的真实问题（SOP-013–018/024）

- probe05成功生成开发DMG并挂载复核签名/内容，原件在`.local/ci/electron-package-probe-05/`；当时未包含后续HIG/icon与指定要求参数修复，不能用作最终包。首轮runner全局Python缺alembic，改用009既有`.local/venv-tm001/bin/python`；缺依赖现在有明确BLOCKED原因。
- 实际codesign指定要求需`-R =<表达式>`，没有等号时将字符串当文件路径；runner、updater、父门禁统一修正，原命令退出1、正确命令退出0及永久回归见`electron-requirement-red-green.json`和`electron-requirement-unit-{red,green}.log`。
- 实际App启动仍失败，dyld显示主程序与Framework不同TeamID。检查发现osx-sign2.7.1顶层hardenedRuntime:false未作用于文件，probe05仍有runtime flag；修复逐文件optionsForFile配置并增加实际flags检查，不修改系统保护，稳定签名身份保持。新包必须再次启动验证。
- 父门禁独立审查发现归档未检查passport自身发布资格；新增回归真实2失败，修复后4项通过。新增对原始trace ZIP/PNG格式、005真实恢复SQLite副本、全部trace段、进程/profile来源、服务退出和源码/原件解析前后的一致性检查。12项父级工具检查通过，证据`local-parent-final-contract.log`；属于治理验证，不冒充产品E2E。
- 复盘新增RET-028，累计28例，记录本轮运行时、工具API、真实签名配置和隔离/证据问题。界面HIG视觉探针已实际运行，后续截图修正继续，最终包尚未放行。

### HIG界面完成及开发包启动修复

- 真实HIG辅助检查12项、10张截图通过，默认/最小尺寸、深浅色、弹窗焦点/Escape/Cmd+,、中文状态/审计及折叠改密已核对。可复现命令`.local/venv-tm001/bin/python apps/desktop/tests/visual_fixture.py`；最新证据`.local/ci/hig-visual-6ed1ef2dbad84374afbfa2d278b07014/`，服务正常关闭。截图不替代六例包级结果。
- 客户端构建及16项node:test通过（`electron-hig-unit.log`）。probe06使用逐文件签名配置，包含最终UI/图标/-R修复，实际签名标志、嵌套代码签名、固定证书、ATS/资源、DMG挂载原App摘要均通过；随后原包App持续运行无dyld错误。仍是development，不具发行资格。
- 六例开发回归已进入真实UI及服务；001执行到尾部，首次改密/撤销/重启恢复等真实断言通过，但异步React勾选触发Playwright同步check的假阴性，保留FAIL并修为点击后等待实际勾选。修复后必须全套重跑。
- 集成治理290项通过（`electron-governance-integrated-2.log`）；随后本地版本查询新回归先真实失败，修为定位本地evidence通行证，14项registry检查通过（`local-registry-{red,green}.log`）。查询仅索引，不签发资格。


### 需求阶段具体任务与精细用例，以及根Excel统一入口（2026-09-30）

输入为用户最新明确要求：先确定需求和功能点，再拆具体开发任务，按任务设计可直接执行的TC/变体，写明每一步动作、独立预期、输入、数据库准备/预期变化/只读核验和类型，形成文档基线后再实现、测试并逐次记录。按SOP-003/006/008/014/018/022/024同步规范和版本文档。此前已存在的实现保留作差距核查，不把现在补写的用例追认为历史开发前已有。

- 版本导航增加[需求到发布顺序](README.md)，关联功能点、具体TASK、[精细用例索引](../../docs/testing/cases/README.md)、[07实际测试结果](07-test-results.md)和[08实际发布记录](08-release-record.md)。登录/改密01a、会话/管理/配置/升级01b及交付检查01c承担不同任务范围，六个E2E编号继续作为聚合场景组。
- 新TC执行状态全部`unexecuted`；关键预期待定标`baseline_pending`，数据/自动化/逐步记录绑定缺失如实为null。要求父门禁按精确TC/变体和步骤证据检查，不能只计六组。相关程序尚未补齐和验证，不声称这一新门禁已完成。
- 用户先要求腾讯Excel统一查看并授权更新。在线内容没有成功写入；随后用户明确取消在线方案，改为仓库根[TokenMeter项目总表.xlsx](../../TokenMeter项目总表.xlsx)，随Git版本提交。后续按根工作簿汇总需求、功能点、任务、用例、运行结果与发布状态；原始DMG/trace/SQLite/通行证仍保留本机，不因提交Excel而上传这些原件。
- 当前工作优先补齐文档/用例/工作簿链，不新增产品行为，不重新打包或运行E2E。结构与引用检查单独记录；文档检查不能授予发行资格。

### dev07开发回归的真实结果与后续清理（2026-09-30）

本条按已存原件补录，不是新一次运行。原始目录`.local/ci/e2e-dev-probe-07/`，run_id=`local-a1b2c3d4e5f60718293a4b5c6d7e8f94`，执行时间`2026-09-30T11:22:02.779752Z`至`11:24:17.173474Z`。macOS15.7.4 Intel；source_commit=`6e80dd12d60ee5dad641bca030445a2153a269c9`且dirty=true；原DMG来自probe06，scope=development。

1. 六个聚合组实际尝试，001/002/003/005/006各Playwright PASS，004 FAIL；新增精细TC不继承这些结果。
2. 004已观察到自动发现、三项拒绝、Squirrel自主新PID及runtime绑定；随后`new_process_profile_files`即时lsof断言预期true、实际false。只记录观察失败，尚不能把原因定为时序，也不能称完整升级/身份恢复通过。
3. 缺`upgrade-result.json`/`upgrade-process.json`，原runner汇总报`Evidence is absent or outside the owned output`。`executed_cases=6`、`passed_cases=5`，suites仅包含前五组，`cleanup_completed=false`；原FAIL和不完整证据保留。
4. 后续`E2E-TM001-004/cleanup-followup.json`另记scope=post_failure_owned_cleanup、original_result_state=FAIL，观察到隔离App为101，确认自有App/ShipIt/CDP及私有根清理。不得把此记录覆盖原报告、补写缺失升级断言或生成通行证。
5. 此版本未发布、无正式通行证。下一步先完成TASK/TC/数据与逐次记录基线，再分别定位004和失败汇总缺口，补测试/门禁程序；仅在新的干净候选完整验证通过后执行本地发行。

本次文档收尾实际执行`python3 scripts/check_docs.py --mode structure`，退出1；原件`.local/ci/document-chain-structure.json`。检查发现并行新增文档尚未登记，根`TEST_CASES.md`和`TokenMeter项目总表.xlsx`当时尚未生成，故不能记录结构PASS；后续整合完成再检查。本次未执行产品测试、重打包或发布。


### 项目主表保留摘要，每次测试独立输出结果Excel（2026-09-30）

用户进一步明确根目录`TokenMeter项目总表.xlsx`只汇总测试用例，每次执行单独输出测试结果Excel。按SOP-014/018/022/024记录此次展示和归档调整：

1. 根主表目标为11个Sheet；`05测试用例`保留109条摘要，包含功能、任务、输入、独立预期、DB操作、类型与状态。`06测试批次`只保留run摘要和独立结果Excel入口。主表移除352条详细步骤、131条事件、逐例结果与SQL详情页。
2. 详细设计、步骤、SQL和绑定继续保存在`tests/test_cases.json`与01a/01b/01c等用例文档；原始运行事件和资产不删除。主表简化不改变必测范围，也不把新增精细TC视为已执行。
3. 每次实际运行单独输出`.local/test-results/<run_id>/TokenMeter测试结果-<run_id>.xlsx`，仅保存在本机；根主表继续按用户要求随Git版本提交。独立结果表按本次原件整理，保留候选/包/run_id、逐项实测、失败、缺证据与后续清理的区别。
4. 当前dev07的run_id为`local-a1b2c3d4e5f60718293a4b5c6d7e8f94`，目标独立表为`.local/test-results/local-a1b2c3d4e5f60718293a4b5c6d7e8f94/TokenMeter测试结果-local-a1b2c3d4e5f60718293a4b5c6d7e8f94.xlsx`，**生成中，尚未登记生成和回读检查通过**。整理不启动新的App测试，不重打包、不发布。
5. dev07仍为development/dirty、六组尝试五组PASS及004FAIL，原始汇总缺升级资产；后续清理不覆盖原FAIL。新增精细TC全部未执行，版本仍未发布且无正式通行证。腾讯在线方案已经取消，没有在线写入。

工作簿生成与验证结果由对应执行记录追加，不能以本条文档同步声明表格已完成或产品通过。

本次六份文档同步后实际执行`python3 scripts/check_docs.py --mode structure`，退出0（99份文档、856条链接，scope=documentation_structure_only、release_eligible=false）；限定这六份文件的`git diff --check`退出0。按SOP-022执行`python3 scripts/release_registry.py show`退出1：01需求、02拆解、03开发计划和04测试计划目前不是baselined，查询的严格版本合同未满足。文档仍处本轮基线修订阶段，保留该结果，由整合步骤处理；不把结构检查或工作簿生成当作产品通过。本次未执行产品测试、重打包或发布。


### 项目摘要与独立结果表完成记录（2026-09-30）

接续上一条“生成中”记录，现已完成以下实际工作，不改写历史阶段状态或dev07原始FAIL：

- 根`TokenMeter项目总表.xlsx`已生成11个Sheet，`05测试用例`109条摘要，`06测试批次`1条run摘要及独立结果文件的相对路径。详细设计仍在JSON/文档，逐项实测在独立表；主表的最终整合回读由本轮整合步骤登记。
- dev07独立文件`.local/test-results/local-a1b2c3d4e5f60718293a4b5c6d7e8f94/TokenMeter测试结果-local-a1b2c3d4e5f60718293a4b5c6d7e8f94.xlsx`已生成并经Python桥接校验和回读。5个Sheet记录6个历史场景组、131条事件、14条更新请求及37条证据/缺口。原件`.local/ci/e2e-dev-probe-07/excel-export.json`为`scope=test_result_excel_export`、`state=PASS`，同时明确`product_state=FAIL`。源报告SHA256为`0d165916cee6ed516b142c4c26bc54ec161ea2a5be52fee60e311d101ddfc9d3`；独立Excel SHA256为`d935a7eda35bfdccb6039e4383e8e6271a43c38ab730e7d35e8e1e89c746f2e1`。
- `scripts/local_e2e.py`已接入自动导出，保留原产品JSON不变；导出失败返回非零并保留失败收据。runner工具11项和桥接18项检查通过，原始日志为`.local/planning/local-e2e-workbook-check.log`及`.local/planning/test-result-export-green.log`。它们验证报表工具，不算新一次产品E2E。环境修复后可指定全新目录补导原始结果，保留原失败收据，无需重跑App。
- 候选测试期间仅写本机忽略目录，不修改受Git跟踪总表/登记数据；本次执行和门禁结束后再同步摘要，仍引用原被测SHA。此条不声明远端提交、正式发布或通行证完成。dev07保持六组尝试五PASS、一FAIL，新增精细TC全部未执行，本版仍未发布。

本次文档更新未执行App测试、重新打包或发布；后续由整合步骤执行最终structure检查与工作簿回读。

### dev07独立结果表时间显示修正与总表入口同步（2026-09-30）

在独立结果表的视觉回读中发现，初次导出的ISO时间显示为Excel日期序号。保留原表、原导出收据及全部原始测试文件，在同一run目录的`revisions/02/`另存修订文件`TokenMeter测试结果-local-a1b2c3d4e5f60718293a4b5c6d7e8f94.xlsx`。时间列现在显示原UTC时间文本；工作簿5个Sheet、6个历史聚合场景、131条事件、14条更新请求及37条证据/缺口记录的数量未变。修订表SHA256为`2d476b47d1136916ac02ba3a063ea8c4db42b6881ac58f986b8c744f10726032`；源`result.json`仍为`0d165916cee6ed516b142c4c26bc54ec161ea2a5be52fee60e311d101ddfc9d3`。

Python桥接对修订目录实际核验通过，独立新收据为`.local/ci/e2e-dev-probe-07/excel-export-b3c021927550bda4.json`，其中`state=PASS`是Excel归档结果，`product_state=FAIL`保持不变。根总表`06测试批次`已指向修订02；xlsx回读核对11个Sheet、109个不重复TC、无错误单元格。此处没有重新运行App、改写原失败、签发通行证或发布版本。

### 仓库根dmg目录作为本机安装包入口（2026-09-30）

用户反馈隐藏的`.local/`目录难以找到DMG，要求今后所有安装包放在根`dmg/`下。本轮按SOP-000、017、020、024将可见入口改为`dmg/<release_id>/`；完整原件和E2E证据仍按候选保存在独立目录。开发/候选包名称必须标记`NOT-RELEASED`，正式原名包只能在发布门禁PASS并完成归档校验后出现。

已将probe06原始DMG复制为`dmg/v0.1.0-20260929T074814Z/TokenMeter-v0.1.0-20260929T074814Z-DEVELOPMENT-NOT-RELEASED.dmg`。原件与副本实际`shasum -a 256`均为`09f0854cefc7584e1cc77e911d92cf1024a826d407e24241bb38cef11d35a529`。这个可见副本仍是development/dirty包，dev07产品E2E升级004 FAIL，正式版本保持未发布。本轮没有新跑App、打包或部署；只复制并核对现有文件。

### 文档现状复核与两日案例补全（2026-09-30）

按SOP-000/024/008核对当前Electron实现、dev07原始结果、测试用例目录、本机发行位置及101份文档。修正导航和架构、测试执行、TM-001六组用例中仍把本机程序写作“未建立”或把开发包六组写作“完全未执行”的表述；保留正式候选和新增精细TC尚未执行的边界。同步SOP-011/017/018、索引修订号及项目总表的数据源。[决策输入](../../docs/decision-inputs.md)单列六类未批准边界及当前源码线索，避免由现有实现反推需求。两日复盘新增RET-029至031，分别记录dev07升级失败与证据缺口、精细TC/总表分层、开发DMG可见入口；现共31例，未改写历史失败。

实际执行：`python3 scripts/check_docs.py --mode structure`退出0（101份文档、873条链接）；`python3 scripts/export_test_cases.py --check`为CURRENT（109例、352步、产品执行数0）；Codex捆绑artifact-tool重新生成根项目总表，回读11个Sheet、31个复盘ID、109例及1批次，SHA-256与生成收据一致，未发现公式错误；`git diff --check`退出0；`python3 -m unittest discover -s tests/governance -p 'test_*.py'`运行335项，退出0。检查仅验证文档/程序治理，不构成新一次App测试。

严格基线检查`python3 scripts/check_docs.py --mode baseline`及`python3 scripts/quality_gate.py check`均退出1：版本01需求、02拆解、03开发计划、04测试计划及精细用例01a/01b共六份仍为draft，关键行为预期待定。没有将其标成baselined。dev07原始产品结论保持五组PASS、升级004 FAIL，109条精细TC全部未执行；没有正式DMG或通行证，不具发布资格。

## 2026-09-30 已确认的验收边界

依据：用户选择“采用这组规则（推荐）”。下述规则覆盖对应旧的待定项；设计已确定，运行结果仍按证据记录。

- `TC-TM001-LOGIN-15`：登录请求15秒超时，显示可重试连接错误；等待期间不显示已登录。取消后的迟到响应不得覆盖新操作或保存其凭据。
- `TC-TM001-LOGIN-16`：以规范化账号和来源IP分别计数：任一维度5分钟内连续5次认证失败后，后续登录返回429/rate_limited；包括受限期间正确密码。窗口结束自动恢复。
- `TC-TM001-LOGIN-22`：用户名忽略ASCII字母大小写，使用原账号身份；含任何空白（包括首尾空格、制表、换行）直接拒绝，不trim后认证，不创建会话。
- `TC-TM001-SESSION-04`：自动登录15秒超时显示可重试错误，不能使用缓存身份；重试后须经真实/v1/me确认。迟到响应不能覆盖新操作。
- `TC-TM001-SESSION-10`：拒绝符号链接、硬链接、非当前uid、宽权限文件或目录等异常凭据对象；不跟随链接、不改哨兵，显示重新登录提示。缺其他uid测试条件记录BLOCKED。
- `TC-TM001-UPDATE-05`：ZIP最大512 MiB（536870912字节），解压内容最大2 GiB（2147483648字节），边界本身允许、超过即拒绝；大小、摘要、签名或包身份校验失败均保留当前版本。

本次需求确认只关闭设计缺项；产品、测试及发布状态不自动改变。测试包仍为开发诊断包。

### 逐用例证据与受控故障执行器

- 按SOP-010/011建立真实服务前的网络故障代理，记录是否转发，成功响应只能来自真实服务。offline代表请求发送前连接失败，不声称FastAPI进程被停止。
- 文档基线和追踪检查均PASS（101文档、874链接）；该结果不表示产品通过。
- 升级清理发现原生Squirrel会留下空ByHost plist。SOP-014限定仅清理本轮新建、空内容且可归属的文件，未知/有内容状态仍阻断，原失败证据保留。

### 用户明确固定代码测试规则

2026-09-30用户要求：“测试必须是固化的代码……可以让AI调用代码来进行测试。”已同步AGENTS、SOP-011/014和用例/Excel规范。实现单TC命令入口及全量入口，每次独立run；没有人工/AI操作替代机器断言。

### 固定代码全量首轮中断与修复（2026-10-01）

`local-7feea03dd72e4eddba0651cede8fd23d`前16条登录原始PASS，LOGIN-17#A因私有路径含`#`被SQLite只读URI截断，抛出`no such table: alembic_version`。机器汇总BLOCKED，16 PASS/93 BLOCKED（含父项和参数项，不能当作109项全部执行），清理全真；原报告保留。后续分析独立写`interruption-followup.json`。修复只将私有目录中的变体分隔符映射为`--`，TC编号不变；加入3条真实数据库路径回归，并让SQLite异常进入逐例错误记录。命令入口保存控制台日志，注册检查直接调用Playwright `--list`验证实际标题和精确选择。

新批次先修复已识别的脚本/覆盖缺口再完整运行。限流的真实五分钟等待证据已保留，新固定程序用测试服务时钟检查299/300秒边界，避免重复等待；实际接口与认证均不替换。

### 完整精细回归与测试程序修复计划（2026-10-01）

`local-343e54113b0b442383e80f137013014b`已执行95个产品入口；原始78父项为57 PASS、8 FAIL、13 BLOCKED，38参数项为31 PASS、7 FAIL。父项含11条待独立辅助执行的占位，参数项不能与父项相加计数。清理完成，原始结论FAIL。随后由固定辅助程序和独立证据审计生成可复核结论，不能手改原报告。

按SOP-015区分已发现的测试程序问题，保持产品源码及正确预期不变：

1. PASSWORD-05第二App复用了第一App的安装路径，触发运行时存储归属校验。改用执行器复制的独立peer App及0700 profile，第二App重启沿用该路径。
2. ADMIN-03已完成四步业务断言后，收尾再次访问已关闭Playwright对象的process，产生TypeError。记录已关闭状态，收尾只关闭仍存活的本例App。
3. UPDATE-05身份负例已被拒绝，但错误提示先于异步临时目录删除完成。当前证据不足以证明最终清理正确；追加最长20秒的固定条件等待并保存采样，再按原预期断言目录为空，超时仍FAIL，不重试业务动作。

修复后新建定向批次执行PASSWORD-05、ADMIN-03及UPDATE-05全部13变体，生成另一份结果Excel。原全量失败和审计保留；定向通过不构成完整迭代或正式发布通过。


### 固定代码执行与独立复核归档（2026-10-01）

用户补充的约束已写入AGENTS、SOP索引、SOP-011/014及测试规范：所有测试预先固化输入、动作、断言和数据；AI仅调用代码。使用`run_test_case.py --case-id <TC>`或`--all`选择产品用例，运行生成独立run目录；通过`--source-report`校验历史测试源码与包摘要，源码变化时禁止冒充同一条件重放。

- 完整产品执行原件：`.local/ci/local-343e54113b0b442383e80f137013014b/result.json`，退出1，95个真实产品执行入口全部尝试；原始失败保留。另11条固定辅助检查10 PASS/1 FAIL。
- 独立审计代码及导出程序核对证据后，78父用例62 PASS/9 FAIL/7 BLOCKED，38变体31 PASS/7 FAIL；两组不可相加。完整复核Excel：`.local/test-results/local-343e54113b0b442383e80f137013014b-reviewed/TokenMeter测试结果-local-343e54113b0b442383e80f137013014b.xlsx`，12张截图、3,397条原件链接，导出收据PASS只证明归档校验成功。
- 定向验证原件：`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed/result.json`，退出1，清理完成。PASSWORD05使用独立peer App及profile，ADMIN03避免二次访问已关闭对象，原始父结果为2 PASS/1 FAIL。UPDATE05的13个参数为8 PASS/5 FAIL，5个解压身份场景在固定20秒观察期后仍有本次临时目录残留。原始成功还需独立证据审计，不能人工放行。
- UI01的#fff对比度解析缺陷先修纯函数并通过2项单元测试，再以新run `aux-ui01-local-343e54113b0b442383e80f137013014b-02`执行固定单例，原始PASS且清理完成。首次UI01 FAIL原件和完整复核表不覆盖。
- 本轮基础验证55项服务端、378项治理测试通过；之后报表和审计代码的针对性回归另存自身结果。不把基础检查或定向PASS当作全部产品E2E通过。当前开发包与dirty源码仍未发布，不创建正式tag/通行证。


定向原件随后由固定审计程序核对：`.local/ci/local-877830fb340a4d12b4e29cf76fa422ed-audit-peer-v3/audit.json`为审计PASS，确认PASSWORD05独立peer App/profile、重启trace与真实旧会话拒绝证据一致，ADMIN03四步证据齐全。原目标父结果2 PASS/1 FAIL可以保持；此审计PASS不改变UPDATE05失败或发布资格。旧审计原件不覆盖。审计程序12项自测通过。

报表及辅助测试程序的最后定向检查原件为`.local/ci/workbook-aux-validation-20260930T173440Z/receipt.json`：32项granular治理检查、2项颜色解析单测通过，辅助TypeScript严格检查退出0。主结果Excel逐页回读、3,397/3,397个证据目标及摘要校验通过；UI01单例53/53通过。回读记录各自在结果目录`workbook-readback.json`。这些属于工具/归档检查，不能代替产品回归。


最终归档：目标定向表为`.local/test-results/local-877830fb340a4d12b4e29cf76fa422ed-reviewed/TokenMeter测试结果-local-877830fb340a4d12b4e29cf76fa422ed.xlsx`（使用peer-v3审计），父2 PASS/1 FAIL、13变体8 PASS/5 FAIL、304条证据链接，其他75个TM001父用例范围外。UI01单例表为`.local/test-results/aux-ui01-local-343e54113b0b442383e80f137013014b-02-reviewed/TokenMeter测试结果-aux-ui01-local-343e54113b0b442383e80f137013014b-02.xlsx`。各次首次报告和历史复核保留。

根目录`TokenMeter项目总表.xlsx`已更新为11个Sheet、109条设计用例、5条批次索引。`scripts/verify_project_workbook.py`实际回读PASS（`.local/workbook/readback.json`），各Sheet预览已核对。总表同时展示完整回归FAIL与后续定向验证，并给每个最近观察状态绑定实际run_id；来自不同批次的状态不能合成全量PASS。表格生成和只读校验没有重新运行App。

最终规范校验记录：`.local/planning/fixed-tests-final-20261001/checks.json`。文档基线101份/877引用、质量追踪检查、109用例/352步骤索引、`git diff --check`均退出0；检查范围仅规范/索引，不赋予产品发布资格。


### 2026-10-01：修复全部必测失败与阻断

用户要求所有已开发功能测试通过。按SOP-015分类为六项产品缺陷、七项覆盖/证据缺口，已修复的三项脚本缺陷仍参加完整回归。新增09修复计划，沿用未发布v0.1.0编号和全部既定TC；不更改正确预期。多agent按文件边界实现，GUI/打包/完整回归由根串行调度。

本轮实现与根因详见[09修复计划的实施进度](09-regression-fixes.md)：自动恢复真实重试和异常凭据重登提示已接入；管理员重置密码补可见校验和主进程拒绝；配置采用稀疏覆盖，恢复默认删除地址覆盖，登录/待退出/更新忙态均锁定总恢复。固定观察器在业务入口前安装，记录真实网络与原生更新器调用；SESSION-10的其他UID场景由自建HFS+镜像固定造数并核对UID、摘要及卸载，不操作用户真实凭据。

UPDATE-05临时目录残留已由固定真实ZIP组件诊断定位：普通Node删除成功，Electron补丁`fs`把`app.asar`视为虚拟目录，递归删除留下真实文件并报`ENOTEMPTY`。诊断收据`.local/ci/updater-cleanup-diagnostic-20261001T004930Z/receipt.json`保留失败原件；实现改用`original-fs`清除且核对本次私有目录，清理失败不交接安装。原完整/定向产品FAIL记录及20秒采样没有覆盖。

基础收据`.local/ci/fixes-basic-20261001T0125Z/receipt.json`：文档基线和质量检查退出0，治理388项、服务端55项、桌面单元25项PASS；定向更新器7项、主进程观察器4项单测和TypeScript检查分别记录于`.local/ci/updater-fix-static-20261001T010408Z/receipt.json`、`.local/ci/update-observer-freeze-20261001T012045Z/receipt.json`。这些基础及组件结果不等于新包产品E2E通过。

新开发候选包已构建，清单`.local/ci/electron-package-fixes-20261001T0114Z/package-manifest.json`注明本机macOS 15 Intel、内部签名和`release_eligible=false`；本轮新包产品E2E正在执行，不能据上述基础检查判定全部用例通过。正式通行证、tag和发布仍未生成。

### 2026-10-01：新包完整精细回归、失败修正与再次运行

按SOP-014运行安装后App的全部精细产品入口。首次新包批次`local-571dd63bfe5b4d90a95ed9c70d80de07`的原始`result.json`为FAIL、清理完成、发布资格否：116行104 PASS/1 FAIL/11 BLOCKED，11条BLOCKED是后续独立辅助TC占位。38参数变体均PASS；审阅模型的78父TC为66 PASS/1 FAIL/11 BLOCKED。独立证据审计PASS，未修改SESSION-09的原始失败。其原始证据在`.local/ci/local-571dd63bfe5b4d90a95ed9c70d80de07/`，审计在同ID加`-audit/audit.json`，独立Excel在`.local/test-results/local-571dd63bfe5b4d90a95ed9c70d80de07-reviewed/`；Excel回读PASS而产品结论FAIL。此次结果不覆盖此前失败批次。

SOP-015定位`TC-TM001-SESSION-09`的30秒点击超时：在退出待确认状态，固定脚本对已禁用的`configuration.reset-defaults`执行点击，并期待错误提示；既定SESSION-09和CONFIG-06用例要求该按钮锁定。产品的锁定是正确行为，故只纠正测试动作与断言为直接核验按钮禁用；原有API不可编辑、settings不变、无新origin/token请求、重试真实撤销及旧token 401断言保持。首批`playwright.log/json`保留为修正前失败证据，不把新结果回填旧run。

新定点`local-4a8815e9d61e4b4bbdd41f7a2f897c52`实际执行SESSION-09四步，`result.json`为PASS、清理完成，独立Excel和回读收据位于`.local/test-results/local-4a8815e9d61e4b4bbdd41f7a2f897c52-reviewed/`。该单例只能证明修正后的固定脚本及产品行为在此输入下通过。随后启动第二次完整精细批次`local-f47f8257607c48458cc52b886d281d70`；实际结束结论及下一步见下节，未签发正式通行证。

### 2026-10-01：第二次完整回归在owned资源清理阶段失败

`local-f47f8257607c48458cc52b886d281d70`原始报告`.local/ci/local-f47f8257607c48458cc52b886d281d70/result.json`记`state=FAIL`、`cleanup_completed=false`、`release_eligible=false`。116行103 PASS/1 FAIL/12 BLOCKED；11条为辅助用例占位，UPDATE-08因上一例未清理而安全阻断。审阅模型78父TC为65 PASS/1 FAIL/12 BLOCKED，38变体PASS；审计`.local/ci/local-f47f8257607c48458cc52b886d281d70-audit/audit.json`为PASS。结果Excel及回读记录在`.local/test-results/local-f47f8257607c48458cc52b886d281d70-reviewed/`，导出PASS而产品FAIL，原报告未修改。

UPDATE-07本轮真实Playwright入口及五项逐步断言均PASS，包括自主升级后的新进程、原profile、`/v1/me`身份、配置及打开文件归属。runner在结束时发现本例`shipit=false`、`private=false`，将其判为FAIL；这不是产品步骤断言失败，也不能因步骤PASS而忽略清理条件。现场诊断指向本run创建的空ByHost偏好文件，`defaults -currentHost read`报告该域不存在，当前owner清理流程因此未完成。修复仍在进行，且本批UPDATE-08未执行；在核实残留归属并安全清理前不启动新的GUI测试，不改写这次原件。

用户提出全量回归耗时问题。本包首次完整精细运行`local-571dd63bfe5b4d90a95ed9c70d80de07`从报告起止时间计为36分44秒，完成95个真实Playwright执行入口。按每例开始/结束时间与各`playwright.json`的`stats.duration`求和，Playwright累计20分56秒、逐例准备约13分33秒、清理约2分13秒，另约2秒为批次管理开销。SESSION-09定点批次`local-4a8815e9d61e4b4bbdd41f7a2f897c52`的Playwright阶段约8秒，整批起止约17秒。后续可优先优化逐例准备效率并保留每例隔离、真实安装App与全部固定断言；这些时间是实测基线，不承诺尚未验证的提速幅度，也不能以定点运行代替正式一次完整全量回归。

下一步：按SOP-015修正并验证本run所拥有的ShipIt/ByHost清理，保留原失败；新run执行完整精细，再串行执行11辅助及六组补充回归、独立审计与Excel，满足最终候选门禁后方可正式发布。

### 2026-10-01：清理规则首修后的UPDATE-07/08定点仍失败

首次代码修正处理`defaults -currentHost read`返回“域不存在”的空ByHost偏好情况；固定治理检查`.local/ci/shipit-absent-domain-governance-20261001T0445Z/receipt.json`退出0。该检查只证明程序规则在隔离样例通过。随后使用相同开发包、固定UPDATE-07/08用例新建`local-c8e31657d5e4428584a6f316936113e1`。原始报告`.local/ci/local-c8e31657d5e4428584a6f316936113e1/result.json`为FAIL、`cleanup_completed=false`、`release_eligible=false`：UPDATE-07五步Playwright全部PASS，但runner的`shipit=false`、`private=false`使整例FAIL；UPDATE-08因前例资源未清理而BLOCKED。本次结果不改变`local-f47f8257607c48458cc52b886d281d70`的全量FAIL，也不能据五步业务断言签发通行证。

单独结果Excel`.local/test-results/local-c8e31657d5e4428584a6f316936113e1-reviewed/TokenMeter测试结果-local-c8e31657d5e4428584a6f316936113e1.xlsx`已生成；`verification.json`为导出/回读PASS、`product_state=FAIL`，只覆盖本次两例。失败后执行仅本run资源的只读归属预检，原件`.local/ci/local-c8e31657d5e4428584a6f316936113e1-cleanup-followup-01/pre-cleanup.json`记录私有根与缓存owner、空ByHost偏好、对应安装App进程为0及无现存ShipIt job；它不证明资源已移除，也不改原失败报告。

第一次规则修正未解决即时升级后的清理时间差。ShipIt可能异步收尾，因此继续实现有界等待：仅对核对owner的本run状态重复观察并保存诊断，不能放宽清理成功判据或删除未知文件。当时完成安全清理前暂停新GUI；修正后的定点与完整回归须产生新的原始run，再执行辅助11例和六组补充场景。当前发布资格仍为否。

### 2026-10-01：UPDATE-07/08环境阻断与定点通过

在完成归属核对及安全清理后，新定点`local-70e531d3092c4cbea30160117c379287`误用系统Python，运行准备缺少`alembic`，UPDATE-07/08均记BLOCKED，`cleanup_completed=true`。原件`.local/ci/local-70e531d3092c4cbea30160117c379287/result.json`保留；独立审计`.local/ci/local-70e531d3092c4cbea30160117c379287-audit/audit.json`为PASS，Excel`.local/test-results/local-70e531d3092c4cbea30160117c379287-reviewed/TokenMeter测试结果-local-70e531d3092c4cbea30160117c379287.xlsx`回读PASS、`product_state=BLOCKED`。该批没有形成升级功能通过证据。

改用项目venv重新执行固定UPDATE-07/08，生成`local-b6627e4379c64386bfc1a535fb432c16`。两例原始结果均PASS、`cleanup_completed=true`，各例的ShipIt、私有目录、App进程及服务清理字段均为true；原件`.local/ci/local-b6627e4379c64386bfc1a535fb432c16/result.json`。独立审计`.local/ci/local-b6627e4379c64386bfc1a535fb432c16-audit/audit.json`为PASS；Excel`.local/test-results/local-b6627e4379c64386bfc1a535fb432c16-reviewed/TokenMeter测试结果-local-b6627e4379c64386bfc1a535fb432c16.xlsx`回读PASS、`product_state=PASS`。本次只覆盖两例，`release_eligible=false`，不改写之前两次完整回归的FAIL。

此条写入时，新完整精细批次`local-534748ff47cb44229183a6bd878c1674`刚启动、尚无结果；后续实际结果与11条辅助、六组补充场景见下方新记录。任一必要项FAIL/BLOCKED仍须保持不发布。

### 2026-10-01：SOP 维护会话统一接收修订需求

用户明确指定当前「SOP」会话（thread ID `01a0f5a5-63f7-76b0-aa53-ac6befec91ef`）为本项目 SOP 新增、修改、删除的统一执行入口。按 SOP-000 和 SOP-024 检查现行规范后，决定保持既有 SOP 编号与工作依赖，仅调整维护分工：其他会话提供缺口、依据和受影响流程，管理会话修订并回告；依赖修订的步骤在同步前阻断。已向当前列表中的六个其他 TokenMeter 会话逐一发送通知（开发总控、开发-REQ-TM002-首次授权、开发-REQ-TM001-账号与更新、文档、解释 TokenMeter 项目用途、绑定 TokenMeter Git 仓库），发送工具均返回成功。未来新会话从 AGENTS、SOP 索引和文档规范读取该约定。

修订 `sop/README.md`、SOP-000（修订 5）、AGENTS、文档规范、目录元数据和 Changelog。初次 `python3 scripts/check_docs.py --mode structure` 退出 1，因新增索引链接被检查器识别为重复 SOP-000 映射；改为纯文字引用后同命令退出 0（102 文档、894 链接）。随后 `python3 scripts/check_docs.py --mode baseline` 退出 0（102 文档、894 链接），`python3 scripts/quality_gate.py check` 退出 0（12 功能、37 场景、6 测试绑定，`release_eligible=false`），治理测试 `python3 -m unittest discover -s tests/governance -p 'test_*.py'` 退出 0（405 项）。这些是规范/治理结果，不改变现有产品 E2E 失败、阻断或未发布状态。

开发总控会话另报告 SOP-019 索引修订 6 与独立文件修订 5 冲突。本会话即时核对共享工作区，独立文件现已为修订 6，正文与索引均采用本地 `master` 总控集成和统一推送规则；已把该核对结论回告开发总控。若后续出现新的实际差异，按本会话统一维护流程处理。

### 2026-10-01：需求分支改为本地 master 总控集成

用户明确要求各需求分支先由总控在本地`master`依门禁整合，再由总控统一推送远端`master`。按SOP-000核对发现：SOP-019修订5以推送需求分支、远端PR合并为默认；发布规范与Electron本机设计沿用PR head/远端合并判据；版本规范仍写默认分支`release-candidate.yml`。这些现行文字与新指令及“Actions仅在明确多环境要求时执行”冲突，故修订SOP-019至6，并同步SOP索引、AGENTS、版本/发布规范、Electron本机设计、本版发布预案和Changelog；SOP编号及版本release_id不变。旧PR/CI结果仍是当时真实历史，不改写。

新规则区分分支进入本地整合的适用检查与**本地`master`最终整合提交**的完整产品E2E及最终包门禁。分支单独PASS不授予整合后候选发布资格；所有需求分支、冲突处理及后续代码/依赖变化完成后，才用最终SHA/tree测试，再由总控普通快进推送远端`master`并读回SHA。远端保护拒绝直推或强制PR时保持BLOCKED，按保护规则处理，不强推、不伪造检查。此处是流程规范修订：尚未切换/合并本地`master`，也未推送、创建PR或Tag；当前完整产品回归仍以其原始run单独判定，不能由本次文档修订声称PASS。

本次只改规范与执行记录，未更改运行中的granular执行输入或启动GUI。`docs/project-register.json`及根项目总表的SOP快照待当前产品执行与候选冻结后按SOP-024同步并回读；不能在运行中以工作簿刷新覆盖被测源码状态。实际检查：`python3 scripts/check_docs.py --mode structure`、`--mode baseline`均退出0（102文档、893链接，101 baselined、1 superseded）；`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6测试绑定，`release_eligible=false`）；限定本轮文件的`git diff --check`退出0。这些只证明文档/追踪一致，不代表产品E2E、最终包门禁或Git集成已通过。

### 2026-10-01：新包完整精细、辅助与六组回归原件

按SOP-014用项目`.local/venv-tm001/bin/python`在本机串行执行固定程序。三批共同输入为`.local/ci/electron-package-fixes-20261001T0114Z/`中的`package-manifest.json`、`TokenMeter-v0.1.0-20260929T074814Z-internal.dmg`与`update.zip`；精细和六组使用候选标识`6e80dd12d60ee5dad641bca030445a2153a269c9`及`--development`。各批采用全新run_id/output，未并行GUI、未修改测试源码、未重试取绿，原件互不覆盖。

1. `.local/venv-tm001/bin/python scripts/granular_e2e.py`以完整集合运行、不加`--case-id`，run_id=`local-534748ff47cb44229183a6bd878c1674`，退出码2。原始`.local/ci/local-534748ff47cb44229183a6bd878c1674/result.json`为`state=BLOCKED`、`cleanup_completed=true`：116条结果105 PASS/0 FAIL/11 BLOCKED。95个真实Playwright入口均PASS，10条父TC由各自变体推导PASS；11条UI/CATALOG/RECORDS/GATE辅助TC在主runner中只是无步骤占位。实时控制日志为`.local/ci/local-534748ff47cb44229183a6bd878c1674-progress.log`，不能据105条PASS改写原始状态。
2. 上批退出且清理完成后，`.local/venv-tm001/bin/python scripts/granular_auxiliary.py --with-ui`绑定该主报告，同一包资产生成`aux-818fe55e1e8940e4a3196b9d03b76563`，退出码0。原始`.local/ci/aux-818fe55e1e8940e4a3196b9d03b76563/result.json`为11/11 PASS、`cleanup_completed=true`；控制日志为同ID的`.local/ci/aux-818fe55e1e8940e4a3196b9d03b76563-progress.log`。这是独立执行原件，主run的11条占位仍保留BLOCKED。
3. 辅助进程退出后，`.local/venv-tm001/bin/python scripts/local_e2e.py`以六组完整集合和`--development`生成`local-5197628d58ac4136b004b87da438220c`，退出码0。原始`.local/ci/local-5197628d58ac4136b004b87da438220c/result.json`为6/6 PASS、`cleanup_completed=true`，mount、服务、App进程、profile、安装目录、端口、ShipIt清理均true。`shipit-cleanup/cleanup-stage.json`与本轮空ByHost偏好副本由报告中的SHA描述符绑定；独立Excel在`.local/test-results/local-5197628d58ac4136b004b87da438220c/TokenMeter测试结果-local-5197628d58ac4136b004b87da438220c.xlsx`。六组补充证据不替代逐TC结果。

随后固定独立审计v1`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit/audit.json`为BLOCKED，唯一`PASSWORD-05`的peer fixture源码与已审阅绑定不一致。本条写入时新绑定复核/审计v2仍在进行，故当时不预判其结论；完成结果见下方新增记录。正式候选门禁当时未通过，也不能以主run、辅助和六组局部原件替代独立复核。

本次按SOP-024仅同步`docs/status.md`及本版本06/07/09四份状态/结果文档；`python3 scripts/check_docs.py --mode structure`退出0（102份登记文档、894条链接）。已跟踪的status/06执行`git diff --check`退出0；07/09当前仍未纳入Git索引，对两份文件单独检查空白和冲突标记，结果为零问题，待总控按版本提交时纳入。结构检查只验证文档合同，不提升上述BLOCKED或发布资格。

### 2026-10-01：审计绑定修复后联合逐例复核完成

上一条记录时审计v2尚未结束。当前固定审计v2原件`.local/ci/local-534748ff47cb44229183a6bd878c1674-audit-v2/audit.json`已经为12/12 PASS；此前v1原件仍是BLOCKED，唯一`PASSWORD-05` peer fixture绑定差异作为历史保留。新审计只核对原始证据与冻结代码绑定，不改写主run的105 PASS/0 FAIL/11辅助占位BLOCKED、辅助11/11 PASS或六组6/6 PASS。

固定合并结果已导出至`.local/test-results/local-534748ff47cb44229183a6bd878c1674-reviewed/TokenMeter测试结果-local-534748ff47cb44229183a6bd878c1674.xlsx`。同目录`granular-source.json`登记`auxiliary_bound=true`，核对同一候选、原DMG和执行时间；`verification.json`为Excel导出/回读PASS，78父TC（67产品、11辅助）PASS/0 FAIL/0 BLOCKED、38变体PASS/0 FAIL/0 BLOCKED、六组PASS、12条审计PASS。该`verification.json`仍记`product_state=BLOCKED`，与主run原始11条辅助占位一致；复核模型的逐例PASS与主run原始状态分开保存。

至此开发包的联合逐例复核完成且全部必测条目通过，但该包清单仍为`release_eligible=false`，不是干净正式候选的发布判定。尚未对最终DMG完成SOP-017/018门禁、签发通行证或正式发布；下一步由总控锁定干净候选并运行适用完整门禁，不能用本次Excel回读替代。

本轮四份状态/结果文档同步后，`python3 scripts/check_docs.py --mode structure`与`--mode baseline`均退出0（102份登记文档、894条链接），`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6测试绑定，`release_eligible=false`）。已跟踪的status/06执行`git diff --check`退出0；07/09仍待Git纳入，另行检查空白和冲突标记均无问题。上述检查只证明文档与追踪合同，不取代开发包E2E或最终发布门禁。

### 2026-10-01：项目总表同步12批次及当前回读

根[TokenMeter项目总表.xlsx](../../TokenMeter项目总表.xlsx)已根据现有机器原件重新导出，当前SHA-256为`cda277e40c77d46d5825ab47782c07ccbac772485f46efe6346ec61c15899e50`。`.local/workbook/verification.json`登记11个Sheet、109条用例及12条测试批次；本轮执行`python3 scripts/verify_project_workbook.py`退出0，回读同一SHA、11/109/12及零错误，`product_tests_executed=false`、`release_eligible=false`。旧`.local/workbook/readback.json`仍对应以前5批次文件，不能用于核验当前SHA。此处只同步状态与证据索引，不重跑App、不改变原始测试或审计报告。

总表的第12条以主run`local-534748ff47cb44229183a6bd878c1674`为标识，登记联合复核模型的PASS，并指向`.local/test-results/local-534748ff47cb44229183a6bd878c1674-reviewed/TokenMeter测试结果-local-534748ff47cb44229183a6bd878c1674.xlsx`；辅助11例和六组证据在该独立复核表中绑定，并非另占两条总表批次行。审计v2及复核模型显示78父TC和38变体全PASS；主raw仍为11条辅助占位导致的BLOCKED。总表的复核状态不改写原始报告，也不替代最终干净DMG与SOP-018发布门禁；正式通行证仍未签发。

### 2026-10-01：远端 master 保护与本机门禁不兼容的 SOP-019 修订

开发总控报告远端保护缺口。本会话只读核对 `gh api repos/lzhe72/TokenMeter/branches/master/protection`：当前`master`强制PR、`enforce_admins=true`、strict required checks 为 `governance`、`product-e2e (macos-15)`、`product-e2e (macos-15-intel)`，三项均绑定GitHub Actions app_id 15368，禁止强推/删除。总控先前快照为其隔离工作树`.local/git-sync/20261001T053249Z-remote-master-protection.json`；本次API读回与其列出的关键字段一致。当前TM001工作流只有`workflow_dispatch`，而GitHub官方required checks排障说明指出手动触发PR head工作流产生的检查可能不会出现在PR检查中、也不能满足保护规则。因此现有本机PASS不能满足这三项远端检查，直接推送也受PR保护限制；无最终候选可推，本次未推送、改保护、写状态或启动Actions。

按SOP-000将SOP-019修订至7，同步SOP索引、发布/版本规范、Electron本机设计与Changelog。新流程在本地整合前和远端操作前只读保存保护快照，要求实际满足指定来源与strict最新提交检查。无法满足时远端阶段保持BLOCKED，并列两条需用户明确决定的受控路径：真实多环境Actions在PR最新候选产生所需检查；或接受以本机原始门禁为依据的保护规则迁移及其远端检查强度变化。任何路径都须保存旧/新规则、用户决定、真实运行或机器核验证据，不能手写状态、临时关保护、管理员绕过或借用旧SHA。本条仅是规范修订，产品E2E及发布资格仍由实际最终候选门禁决定。

本轮实际检查：`python3 scripts/check_docs.py --mode structure`及`--mode baseline`均退出0（102文档、899链接）；`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6绑定，`release_eligible=false`）；本轮相关文件`git diff --check`退出0。这些是规范/追踪检查，不改变远端集成的BLOCKED状态。

### 2026-10-01：TM-002 目录选择授权模型的通用 SOP 边界

TM-002 会话传来用户决定：本版使用 macOS 原生目录选择器、App 持久保存已选来源并由主进程强制限制读取；不要求 App Sandbox 的持久 security-scoped grant 或 TCC 撤销。[Electron 官方目录选择器文档](https://www.electronjs.org/docs/latest/api/dialog)仅对 macOS MAS 的 `securityScopedBookmarks` 返回书签，非 MAS 返回空数组，故真实面板选择不能被记为沙盒持久授权。TM-002 需求、设计与用例草稿已按该模型更新，持久 locator 的可逆信息与本机保存边界仍待用户答复。

按 SOP-000 将 SOP-002/004/006 分别修订至 4/4/6：需求阶段明确系统与 App 各自负责的选择、限制、撤销和持久性；设计阶段约束主进程只读能力、身份/根绑定与停读；测试计划驱动真实面板并区分 App 撤销/访问失效与系统权限。AGENTS 仅登记当前已确定模型和 locator 待决，不为保存可解析路径或书签开例外；TM-002 依赖重启恢复的基线仍保持待决。本轮通用规范在当前工作树核对，TM-002 分支的版本档案/Changelog 由其会话在同步这些 SOP 后维护。

实际检查：`python3 scripts/check_docs.py --mode structure`和`--mode baseline`退出0（102文档、899链接）；`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6绑定，`release_eligible=false`）；相关 SOP、AGENTS 与目录 `git diff --check`退出0。检查仅证明当前规范结构，不解除 TM-002 的 locator 待决或任何产品 E2E 阻断。

### 2026-10-01：移除旧 GitHub Actions 必需检查，保留本机门禁

用户再次明确：应用程序在本机完成测试，远端 Git 只做源码版本管理；此前把旧 GitHub Actions 必需检查当成新流程验收条件应修正。本会话按 SOP-000 和 SOP-019 核对当前远端 `master`：修改前 `required_status_checks.strict=true`，三项 `governance`、`product-e2e (macos-15)`、`product-e2e (macos-15-intel)` 均绑定 Actions app_id 15368。执行 `gh api --method DELETE repos/lzhe72/TokenMeter/branches/master/protection/required_status_checks`，退出0；随后 GET 读回 `required_status_checks=null`。PR、管理员执行、对话解决、禁止强推/删除的字段与修改前逐项相同。前后原始JSON和机器比较结果保存于本机 `.local/git-sync/20261001T055756Z-local-only-protection/`；远端 `master` 在操作前为 `e011857443b503c2bfafcb9cd1c9e6d52f5ff5f2`，本次未推送源码、合并PR、建Tag或启动Actions。

SOP-019修订至8并同步索引、AGENTS、发布/版本规范、Electron本机设计及Changelog。旧三项远端检查不再是当前验收条件；远端PR及其余实际保护继续满足，最终本地`master`整合树的完整产品E2E、同一最终包和本机机器门禁仍须真实PASS。此次仅完成远端配置与规范迁移，不宣称产品E2E或发布通过。

本次规范检查：`scripts/check_docs.py --mode structure`、`--mode baseline`及`scripts/quality_gate.py check`均退出0（102文档、904链接，12功能/37场景/6绑定，`release_eligible=false`）；治理单测417项通过，相关文件`git diff --check`退出0。上述结果只验证文档和治理程序，不代替安装后App产品E2E。

### 2026-10-01：最终候选门禁程序接入与文档同步

同一候选的本机门禁已在代码层编排完整精细主runner、独立辅助11例、证据审计12项、六组补充E2E和逐例Excel。`scripts/local_gate.py`从各自原始证据复算78条父TC与38条变体的最终状态，输出`final-product-result.json`；主runner的11条辅助占位继续保留原始BLOCKED，只有真实辅助批次逐条PASS才能获得最终集合PASS。`scripts/local_release.py`在归档前后复核摘要、最终结果及证据副本。固定负测覆盖缺失/篡改/伪造映射与错误退出码。代码就绪不等于最终候选产品验收；当前未生成新的正式run、通行证或Tag。SOP-018修订11中关于精细集合校验“仍待实现”的文字已报告SOP管理会话，规范同步前依赖步骤仍待完成。

固定入口核对`python3 scripts/check_granular_bindings.py --output .local/ci/final-registration-20261001T0526Z.json`实际95/95 PASS，精确选择器匹配，仅证明Playwright用例注册。`apps/desktop/tests/visual_fixture.py`在`.local/ci/hig-visual-c759e9f93b2f40cf9f72a40d438ca3f2/`生成10张界面图、12项布局/键盘辅助检查和`service_closed=true`；该辅助检查不代替最终安装包E2E。主任务已执行服务端55项、桌面单元25项与桌面构建，结果用于准备候选，不提升产品发布状态。

本次按SOP-024同步Changelog、状态、07/08/09及本记录。`docs/project-register.json`的25份SOP快照与当前磁盘文件逐章节、修订号比较为0差异，故无需修改登记；根`TokenMeter项目总表.xlsx`按现有登记重导，`python3 scripts/verify_project_workbook.py`退出0，回读11个Sheet、109条用例、12条批次、零错误，SHA-256为`a53f219f6f17c6cdc32609c98b66fd1641a38c31168d87f0c3563236e58ee64f`，`release_eligible=false`。`python3 scripts/export_test_cases.py --check`退出0，109例、352步。`python3 scripts/release_registry.py show`退出0，显示本版工作树档案且没有正式Tag或已验证通行证。

文档`python3 scripts/check_docs.py --mode structure`与`--mode baseline`均退出0（102份文档、904条链接），`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6绑定，`release_eligible=false`），`git diff --check`退出0。一次完整治理`python3 -m unittest discover -s tests/governance -p 'test_*.py'`在门禁代码及fixture仍被并发修改期间运行，422项中1 FAIL、7 ERROR，退出1：7个错误是归档fixture未满足新增补充run绑定，1个失败是PASSWORD-05冻结源码摘要改变。它不是最终稳定候选检查，不能记为治理PASS；源码/测试负责人修复后须重新运行并保留新的结果。最终包E2E与发布门禁仍未执行。

### 2026-10-01：SOP 独立分支先行整合（纯规范）

用户本轮明确要求将SOP改动作为独立分支提交到远端`master`；此前各需求分支由总控统一整合的常规顺序在本次规范分支上让位于这条明确指令。以当时远端`master` `e011857443b503c2bfafcb9cd1c9e6d52f5ff5f2`为基线创建`codex/v0.1.0-20260929T074814Z/sop-governance`隔离工作树，只承载SOP、使其链接和治理检查可执行的设计/规范附件、目录、AGENTS、Changelog、总表格式快照及关闭旧自动Actions触发的配置；不带入TM001产品实现、原始测试结果、候选包或版本指针。产品分支以后须以新远端基线重新整合并在最终产品树完整回归。

本次SOP-019修订为纯规范先行提供边界：SOP-008结构/基线/治理PASS仅允许源码规范整合，`release_eligible=false`；不生成产品E2E PASS、通行证或Tag。SOP-014/018补明确主run的11条辅助占位BLOCKED必须原样保留，只有同候选辅助、审计、六组及独立重算的78父TC/38变体最终规范化结果均零失败/阻断才可发布。SOP-014/018/024补清晰的两阶段顺序：干净候选先产本机原件、独立结果Excel、通行证和归档，根总表测试批次作为引用被测SHA的后续文档提交，不回写被测树。TM002依据用户已选目录跨重启保存决定，仅允许私有加密locator，撤销删除、失钥停读；不把App访问控制冒充系统授权。

独立树编制期实跑`python3 scripts/check_docs.py --mode structure`和`--mode baseline`均退出0；最终去除不属于纯规范范围的总表数据文件后重查为74文档、441链接。`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6绑定，`release_eligible=false`）。这些为文档/追踪条件，尚未运行本版Electron最终DMG产品E2E；不授予任何产品发布资格。远端PR、合并SHA/tree与候选提交后的治理复核记录在本机`.local/git-sync/`，不得预填在本条。

初次治理单测198项中2项失败：旧`test_candidate_gate.py`仍强制要求PR/push自动运行原生门禁，与用户本机流程冲突；原失败保留在本轮执行记录。调整固定负测为断言工作流仅`workflow_dispatch`、无PR/push/schedule自动触发，手动占位流程明确退出2且不含产品门禁或上传步骤；单文件11/11通过，随后完整治理198/198通过。此处修改的是旧触发要求的测试合同，不更改产品用例预期或借测试通过宣称产品E2E成功。

### 2026-10-01：TM002/003/004 macOS Keychain 测试隔离规范

总控会话报告新缺口：TM002 的 `safeStorage.encryptStringAsync` 在 macOS 使用 Keychain，独立的 `--user-data-dir` 不覆盖该系统资源；未证明最终包实际测试 item 身份、与正式 App 分离以及清理归属前，TM002/003/004 的相关 E2E 不能启动。按 SOP-000 在独立分支修订 SOP-006/009/010/014 与索引、测试用例规范、Electron 架构、AGENTS 和 Changelog。Electron 44.5.1 主进程源码中的 `KeychainPassword` 命名只能用于设计推断，不能证明异步提供者和最终 DMG 的实际 item 身份。新合同要求首次调用前用同一最终 DMG 在隔离 macOS 测试账号或经证明独立的 Keychain 命名空间作原生探针；确认精确测试身份先前不存在，记录本次 owner 与创建元数据，仅清理确属本次创建的精确 item。预存、身份未知或与正式 App 冲突均阻断依赖场景，不能查询、覆盖、删除正式凭据。本条是后续 TM002/003/004 执行前置，不追溯改判正在运行的 TM001 候选证据。当前只有规范修订，没有该最终包的原生证明或产品 E2E PASS。

独立规范树的实际检查：`python3 scripts/check_docs.py --mode structure` 与 `--mode baseline` 均退出0，74文档/441链接；`python3 scripts/quality_gate.py check`退出0，12功能/37场景/6绑定，`release_eligible=false`；`python3 -m unittest discover -s tests/governance -p 'test_*.py'`执行198项、全部通过。原始输出保存在本机`.local/git-sync/20261001-keychain-sop/`。这些只证明本轮规范与治理检查，不代表 Keychain 原生探针或产品E2E通过。

### 2026-10-01：SOP 基线合入后的 TM-001 文档与候选前检同步

独立规范PR#4已进入远端`master`，读回合并提交`f3b29f6b4203fe22ae8a40533e775291253bb7b3`。当前工作树正将TM-001分支与该基线合并；本条只记录规范和门禁程序对齐，**不表示这次产品合并已经提交、测试或发布**。现行SOP-014修订23、SOP-018修订12明确保留主精细run的11条辅助占位BLOCKED，从同一候选辅助11例、审计12项、补充六组及原始目录独立复算78父TC/38变体的最终规范化结果；SOP-024修订6规定候选输入先进入干净提交，通行证及本机归档完成后再用后续文档提交登记总表批次与被测SHA。原本“SOP-018修订11尚未同步”的描述属于前一阶段事实，当前已由上述修订替代。

候选前检代码已补：补充六组使用独立`local-<uuid>`运行编号，并以`--parent-report`绑定主精细报告、候选及DMG；门禁重新核对独立Excel与`final-product-result.json`，归档时再从原件复算；PASSWORD-05受审查的peer源码摘要已同步。此前治理422项的1 FAIL/7 ERROR原件继续保留为并发改动阶段诊断。源码负责人报告修复后治理424/424通过；本次合并树的完整治理仍须由总控在冲突全部解决后重新执行并保存原始日志/收据，未有该证据前不把候选治理写为最终PASS。最终签名/安装DMG的全量产品E2E、发布门禁和通行证也尚未执行。

本次文档冲突解决后，`docs/project-register.json`的25份SOP快照与现行文件修订号、十章节内容逐项比较为0差异。根项目总表使用捆绑artifact-tool重新导出，`python3 scripts/verify_project_workbook.py`回读11个Sheet、109条用例、12条批次、零错误，SHA-256为`ef94e5e15c1c6c0b4fe4a0ae8d550728c54ad502e317262b7dc02ffba41c8ae3`；`product_tests_executed=false`、`release_eligible=false`。`python3 scripts/check_docs.py --mode structure`和`--mode baseline`均退出0（102文档、902链接），`python3 scripts/quality_gate.py check`退出0（12功能、37场景、6绑定，发布资格否），`python3 scripts/export_test_cases.py --check`退出0（109例、352步），`git diff --check`退出0。以上仅是文档、总表与追踪检查；本次合并树完整治理仍由总控另行保存原始结果。


### 2026-10-01：合并后治理原始检查

TM-001源码提交`44e3844ce566eb3120f17ee555321434fcac4231`与已合入的SOP规范提交`f3b29f6b4203fe22ae8a40533e775291253bb7b3`在本地合并，冲突按现行SOP内容及TM-001用例合同解决；本条检查发生在合并提交前的已暂存树，不冒充最终包验收。原始命令输出及各文件SHA-256保存在`.local/ci/tm001-merge-preflight-20261001T0716Z/receipt.json`及同目录日志。`python3 scripts/check_docs.py --mode structure`、`--mode baseline`、`python3 scripts/quality_gate.py check`和`git diff --cached --check`均退出0；`python3 -m unittest discover -s tests/governance -p 'test_*.py'`在46.0秒内实际运行426项、全部通过，退出0。先前并发改动期间422项的1 FAIL/7 ERROR仍按历史保留，由本次新原件证明合并后的治理检查已修复。上述结果仍不是最终签名DMG的产品E2E或SOP-018发布门禁；正式候选尚无通行证。


### 2026-10-01：首次干净候选门禁及两项固定测试证据缺口

本地合并提交`3467dc143b2e2fc71f51515f483f0ecff8637947`（tree `136c200d20f6e399928b06fee65780f39e7b99b1`）在隔离工作树构建签名内部DMG，包清单`.local/ci/tm001-final-package-3467dc1-20261001T0726Z/package-manifest.json`；DMG SHA-256 `e310a0aa5f05cc08930b4a2f57453c51a564ca16e5f3d756c65e25443ef1ac4d`。正式门禁`.local/gates/tm001-final-gate-3467dc1-20261001T0730Z/gate.json`运行约48分钟后返回**FAIL**、`release_eligible=false`、`No actual identity verification`。95个实际精细Playwright入口PASS，主原件116条105 PASS/0 FAIL/11辅助占位BLOCKED；辅助11/11、审计12/12、补充六组6/6分别PASS，Excel已导出并回读PASS；这些分项不使最终门禁通过，未生成`final-product-result.json`或通行证。

按SOP-015复核保留原件。补充003组管理员管理操作通过，但固定脚本仅对撤销后的成员会话请求`/v1/me`并得到预期401，没有有效管理员身份200。只读继续核验发现补充004组的`lsof -Fn`包含一条无文件名的`n`行，固定采集器将其记为空路径，后续发布校验会报`Incomplete restarted-process open-file list`。两者均属于固定测试/证据采集缺口，未发现产品认证或升级的确定性失败。现已在003脚本增加真实App重启、自动恢复管理员身份和服务账号/角色断言；在003及精细更新采集器用同一解析器忽略空名称，保留所有具名路径，并添加解析单元测试及003缺200的门禁负测。修改后基础检查与新候选完整门禁需重新运行，旧FAIL原件不覆盖。

修订后候选前检日志保存在`.local/ci/tm001-gate-fix-preflight-20261001T0837Z/`：文档严格基线与质量追踪均退出0（102文档、904链接；质量检查仍`release_eligible=false`），完整治理426/426、服务端55/55、桌面单元26/26（含`lsof`解析回归）通过，Electron构建退出0。固定精细Playwright注册95/95、补充六组注册6/6，`git diff --check`通过。补充列表首次因预检命令遗漏执行器所需`TM_E2E_JSON`而退出1，补齐隔离输出路径后同一固定六组列表核对通过；该列表检查没有执行App。所有基础与列表检查仅用于新候选前检，不能替代再次完整E2E。
