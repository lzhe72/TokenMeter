# 01 · v0.1.0 内部安装包与自动发布设计

版本：`v0.1.0-20260929T074814Z`。输入：用户在2026-09-30确认“以目前的测试条件为准，先走通链路”；[既有需求](../../releases/v0.1.0-20260929T074814Z/01-requirements.md)、[发布预案](../../releases/v0.1.0-20260929T074814Z/05-release-plan.md)和已通过的开发迭代。执行SOP-004/005/006/007/017/018/019/020/024。本文为本轮内部包实施合同，程序和实际结果分开登记。

## 需求与范围

本轮发布 `distribution_profile=internal`，首版仅承诺 **macOS 15、arm64及x86_64**，使用现有GitHub托管 `macos-15` 和 `macos-15-intel`、Xcode16.4。macOS14、其他系统主版本及公开Developer ID/公证发行留后续版本；不能写成已经支持。最低部署版本设为15.0，产物为同一份Universal App/DMG。此范围变化来自用户明确决定，不删除任何功能场景。

交付生产Bundle `org.tokenmeter.TokenMeter`，默认API `http://127.0.0.1:49176`，默认feed `http://127.0.0.1:49177/appcast.xml`，配置页可修改。内部包不带UITESTING条件、测试路径、测试环境读取或认证旁路。生产SQLite保留 `database/production/production.db`，首建admin/123456且强制改密，不覆盖已有库。服务端源码/锁定依赖与启动说明作为独立发布资产；App连接服务后使用。

## 构建、签名与安装

1. 从默认分支固定完整SHA构建一次Universal生产App，构建号100、显示版本0.1.0；同一源码另构建101作为首版升级测试包。构建固定Sparkle2.10.0、macOS15.0最低系统、Release优化，内部使用明确记录的稳定自签代码签名与EdDSA公钥；不声称Developer ID或已公证。此内部构建明确传入 `ENABLE_HARDENED_RUNTIME=NO`；验包须拒绝带runtime/library-validation标志、ad-hoc签名、错误证书或不稳定签名要求的App。公开构建仍保留Developer ID、hardened runtime与公证要求。
2. 稳定代码签名P12、其密码及EdDSA seed保存在只允许master部署的 `release-validation` 环境secret。私钥不提交Git、不打包、不进入日志或测试工件。只在托管Mac的专用临时钥匙串导入代码签名，finally恢复原列表并删除；不改变系统信任。本地可生成密钥并设置环境secret，不在用户钥匙串导入身份。
3. 打包前后均核对生产Bundle、版本、无TMTest字段、内置默认、固定公钥、解压前验签、架构、代码签名及完整App摘要。DMG只包含最终App、Applications链接和安装说明。挂载最终DMG重新核对内容摘要；之后不重建或替换已测试包。
4. 内部自签包不具备Apple公网信任。记录 `spctl` 的实际退出和拒绝类别，不能把拒绝改写为Gatekeeper通过；安装说明明确首次系统许可路径。在隔离CI仅对已核对摘要的本次App处理隔离标记/许可，不关闭全局Gatekeeper、不添加系统信任；保存操作前后证据和真实启动结果。生产用户按系统“仍要打开”完成首次许可，或按安装说明对确定的内部包操作。

内部关闭hardened runtime的依据：Apple说明该模式默认要求加载的库由Apple或同一Team ID签名；Sparkle也说明无Apple开发签名的本地构建可能因此无法加载框架。稳定自签没有Apple Team ID，据此判断沿用公开Release的runtime设置存在加载冲突，选择只在内部打包命令中关闭；这属于预先兼容性决定，尚未获得本候选的实际启动结果。固定证书、代码完整性、EdDSA及最终DMG两平台六例仍全部必需。参考：[Apple library validation](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation)、[Sparkle setup](https://sparkle-project.org/documentation/)。

## 最终包测试路径

每个平台下载同一份原始DMG、高版本zip和构建清单，核对摘要/来源后从DMG安装到测试拥有的安装位置。真实App与API/更新源均在该runner上。每例使用新的真实SQLite和固定默认API端口49176；第006例另开隔离第二服务，经配置UI切换。生产App使用runner自身标准Application Support和UserDefaults，不注入测试路径；程序须先证明专用托管runner及目标目录/设置不存在，创建所有权记录后方可使用和清理。绝不在用户本机调用该生产位置测试路径。

XCUITest使用 `XCUIApplication(url: installedAppURL)` 精确指定从DMG复制的App，核对实际运行路径；独立构建的测试bundle不能替代被测包。测试账户、控制URL和断言数据仅交给测试runner；创建App对象后从其launchEnvironment移除全部测试/签名变量并断言清零，不交给生产App。每台Mac顺序执行六例，App结束后清理本次已取得所有权的标准凭据目录与UserDefaults，并读回核对；不增加十二台VM或复用另一例状态。修改测试runner的installed模式以适配真实凭据位置，完整保留六个原生测试方法与所有业务断言。第006例的“未配置公钥、更新按钮禁用”只适用于无公钥开发包；生产包改为核对固定公钥不可编辑、合法配置持久化，测试过程不触发合成公网地址。两种模式都保留非法URL拒绝与恢复默认。

第004例使用同机49177和构建阶段签名的高版本包：非法HTTP下载URL、跨域明文重定向、坏EdDSA签名均拒绝，正确包真实安装并自主重启到101，经 `/v1/me` 确认同一会话。安装前核对最终100包，测试后核对高101来源与摘要；高版本不能冒充最终候选。每例结束保留原始xcresult、截图、服务/请求日志及包/数据摘要，finally清理拥有的服务、设置与凭据。备份恢复在生产首建同构副本执行sqlite backup/恢复，并以独立原始数据和真实API验证，用户生产库不受影响。父门禁仅可读取CI程序新建、带隔离归属的合成生产schema备份及恢复副本；初始副本无会话，测试后的导出不得含可用token或明文口令。真实用户库永不导出，测试库证据不分发为产品数据库。

## 门禁与发布链路

`internal-release.yml` 仅允许默认master的workflow_dispatch，并要求candidate_sha等于该次GITHUB_SHA。master required checks和环境master部署策略必须由GitHub API读回确认。

构建job → 两平台最终包六例和SQLite恢复 → Mac上的父门禁重解析两套原始xcresult → 通行证 → Git发布。任何前序失败/缺失/跳过都不得签发通行证或创建Tag。父门禁检查精确case集合、源SHA、清单摘要、同一DMG/生产App、高版包、数据程序、安装路径、平台、签名、清理与本次run/attempt。完整bundle在解析前后重算，不排除SQLite。不能接受人工提供的PASS JSON或另一次运行的产物。

通行证在候选源码之外由受保护流程生成，绑定release_id、internal、candidate_sha、全部产物SHA256、测试/数据/SOP清单、实际两平台、签名类型、GitHub repository/workflow/run/attempt和时间。发布job重新检查本次所有依赖job真实结论、通行证和资产摘要，以同名annotated Tag与Release发布原始DMG、服务端资产、校验和、说明和通行证，并长期保留两平台原始E2E证据归档及门禁报告；发布前从归档重算报告和xcresult摘要，不只依赖90天Actions存储。若Tag/Release已存在则停止，不移动Tag或覆盖资产；失败保留已发生事实。

本机分发从已发布资产下载核对后使用。更新源只在127.0.0.1上提供已发布同一版本appcast/签名zip，不自动覆盖其他服务；后续升级使用同一固定公钥。首次无上一稳定版，上述100→受控101用于证明更新器，发布源仍提供真实100，不能把101测试包装进稳定渠道。

## 实施顺序与程序合同

下表为本轮程序合同，源码完成后登记manifest和测试绑定；存在文件不表示最终包或实际执行已通过。

| 步骤 | 程序/文件 | 验证 |
| --- | --- | --- |
| 固定平台与签名公开配置 | `releases/v0.1.0-20260929T074814Z/internal-release.json` | 精确两平台、最低15、生产Bundle、固定公钥；拒绝缺项 |
| 生产包构建与打包 | `scripts/internal_package.py` | 无测试路径、同源码100/101、Universal、签名、镜像和摘要负测 |
| 已安装App六例与恢复 | `scripts/internal_package_e2e.py`、原生测试installed模式 | 完整六例、同机源、生产路径所有权、备份恢复、清理、真实xcresult |
| 父级验收与通行证 | `scripts/internal_release_gate.py` | 拒绝少平台/错SHA/错包/漏例/过期或变动原始证据 |
| CI与自动Git分发 | `.github/workflows/internal-release.yml` | 受保护master候选、真实远端配置、依赖全绿后发布 |
| 本机部署说明/服务入口 | `docs/releases/02-installation.md`、`scripts/bootstrap_sqlite.py`、`scripts/local_distribution.py` | 不覆盖生产库或未知端口，绑定原始发布资产 |

先补规范和全部设计/用例文档并通过基线，再分别建立程序及失败回归、基础检查、提交新候选、完整PR迭代、合并、默认分支最终包运行、机器发布。每一阶段在版本06记录实际命令与结果；开发迭代旧PASS保留，不复用为新最终包PASS。
