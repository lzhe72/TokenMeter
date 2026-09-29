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

本轮App、服务、测试数据和原生执行器正在联调，原生产品验收已在CI执行但未通过，当前结果见文末。正式支持矩阵、证书、生产MySQL和受保护发布环境缺失，产品发布BLOCKED。后续实际结果继续追加，不能用文档基线或Python测试代替原生E2E。


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
