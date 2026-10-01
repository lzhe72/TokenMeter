# 发布门禁与本地发行规范

当前范围由用户2026-09-30确认：本机开发、完整测试、打包及发行；Git只保存源码、文档、版本追踪。最终DMG、更新ZIP、原始报告和通行证保存在本机，不创建GitHub Release或上传资产。详见[当前设计](../architecture/01-electron-local.md)。

## 不可跳过的门禁

1. release_id贯穿需求、任务、计划、用例、数据/SOP、候选SHA、Changelog、通行证与Git Tag；文档基线完整一致。
2. 固定干净候选源码/tree与依赖，electron-builder构建目录App，固定自签身份验证嵌套签名，生成原DMG和更新ZIP。当前本地内部路线不要求Apple Developer账号或公证；系统实际结果如实记录，不关闭保护或声称Apple信任。
3. 从同一最终DMG安装正式App，macOS15 Intel按候选机器用例清单执行目标版本及此前已交付功能的全部父TC、固定变体、辅助、各来源场景组与独立审计，真实UI/IPC/API/SQLite；TM001六组只属于其来源版本，不限制后续版本的场景数。最终gate自身派生TC按SOP-018在其他原件及真实升级验真后计算。arm64与其他系统未验证，不宣称支持。
4. 首版无稳定包：候选100完整验收后，使用受控同源101证明真实更新、失败保护及自主重启/身份恢复；受控高版不能当用户稳定包。每版先在本地`master`固定不可变SHA/tree里程碑；后续版本从上一版按SOP-018/020通过门禁并归档的实际本机稳定原包真实升级。
5. 父门禁读取原始结果、用例/数据/SQL与产物摘要、签名和运行身份，核对精确集合、时间、本次nonce/候选/包与清理。零例、跳过、重试取绿、失败、旧证据、哈希不符均不放行。
6. 只有PASS产生候选源码之外的本地passport；FAIL/BLOCKED不签发。证据同uid可写，不能宣称第三方不可篡改证明。源码/依赖/产物变化需重新完整验证。

## Git与归档

总控按版本依赖顺序将需求分支集成本地`master`，逐版固定里程碑SHA/tree，对该版同一最终DMG执行完整产品E2E与本机机器门禁。PASS后先按SOP-020本机归档并提供正式稳定原包，下一版以该原包作为真实升级源。全部目标版本完成后，总控按当前强制PR保护统一登记远端源码；PR合并链必须保留每版里程碑祖先，逐版读回来源SHA/tree与Tag映射，内容或来源不符时阻断远端登记并按适用门禁重新验证。原包始终绑定实际被测里程碑；本机稳定发行、远端源码登记与Git Tag分别记录，Tag不独立授予发行资格。

远端集成前只读核对分支保护、实际required checks和工作流触发。用户2026-10-01重申本机测试、Git仅做源码版本管理后，已从远端`master`移除三项旧Actions required checks；前后原始快照及读回核对保存在`.local/git-sync/20261001T055756Z-local-only-protection/`。PR、管理员执行、对话解决、禁止强推/删除均保留。旧检查不再作为本机候选的远端验收条件；完整产品E2E、最终包和本机机器门禁仍必须在最终候选上真实PASS。后续实际保护变化按[SOP-019](../../sop/SOP-019-git-release.md)核对与处理。

按SOP-020执行`scripts/local_release.py verify`或`archive`，均传入`--milestone-sha <被测提交> --milestone-tree <被测tree>`，在干净且HEAD精确等于被测提交的里程碑检出中核对该提交为本地`master`祖先，原包、通行证与里程碑同源；再将原包、原始结果与passport复制至仓库根`dmg/<release_id>/release-archive/`，逐项读回摘要。schema 2归档索引保存里程碑SHA/tree、master tip、DMG/manifest/passport摘要及`remote_source_state=PENDING`；正式原包只有同一里程碑门禁PASS后才独占复制到`dmg/<release_id>/`供用户安装，并再次核对摘要。开发/候选便捷副本标记`NOT-RELEASED`；不重建包借报告，不覆盖已有档案。本地归档索引记录远端源码登记待办；最终远端读回收据另行追加，不改原包或通行证。测试不覆盖用户旧App、生产数据库或占用服务；后续部署前备份并验证恢复，失败按SOP-021停止推广。

默认不运行GitHub Actions完整测试，仅用户明确要求多环境时设计矩阵后运行；旧CI签发/Release上传程序属于历史，不能作为当前发行入口。
