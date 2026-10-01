# 本机产品测试执行规范

先读[SOP索引](../../sop/README.md)，再按任务完整读取SOP-009至014；最终包与门禁另读SOP-017/018。详细执行合同见[Electron本机设计](../architecture/01-electron-local.md)，逐项设计见[用例索引](cases/README.md)和`tests/test_cases.json`。旧Swift/CI结果只属历史。

## 当前执行事实

dev07开发包曾执行六个聚合场景组：五组PASS、升级004 FAIL，汇总缺升级资产。首轮精细全量`local-7feea03dd72e4eddba0651cede8fd23d`已BLOCKED（109条预期、16条PASS、93条BLOCKED），原始结果及独立Excel保留。新版全量`local-343e54113b0b442383e80f137013014b`已结束为FAIL；独立代码复核后78父用例62 PASS/9 FAIL/7 BLOCKED、38变体31 PASS/7 FAIL。定向验证及UI01新单例另存，不覆盖原始失败。各轮状态及独立Excel路径见[本版结果](../../releases/v0.1.0-20260929T074814Z/07-test-results.md)。六个聚合场景组的历史PASS不能转成精细TC的PASS。

## 固定代码入口

测试输入、动作、预期与断言必须事先写在仓库版本化程序中。Codex只调用程序和分析原始结果，不能临场操作App、目测截图或手填通过。每个TC可单独用新run_id重现；父TC的全部已声明变体由固定程序逐项运行，不能只选容易通过的一种。

```sh
python3 scripts/run_test_case.py --case-id TC-TM001-LOGIN-01 --package-manifest <本轮包清单> --development
python3 scripts/run_test_case.py --all --package-manifest <本轮包清单> --development
```

以上`--development`只用于明确标识的开发包。正式候选用相同入口和最终包清单，去掉该参数；具体参数以程序`--help`和SOP-014为准。单例用于定位和复现，迭代及发布仍须运行本次目标和全部此前已交付功能。

## 准备与执行

1. 检查文档基线、macOS15 Intel、Node/npm、已登录桌面和本机工具链；Electron/Playwright无需完整Xcode。隔离Python环境按`server/requirements-dev.txt`准备，Electron依lockfile安装。
2. 按SOP-010为每例生成独立合成账号、SQL、预期值、隔离SQLite、profile和拥有的回环端口。不得读取用户生产库、默认凭据、真实日志或终止已有App/49176服务。
3. 按已批准的TC与变体核对固定Playwright绑定。真实App必须从本轮DMG安装，经过UI、preload、主进程、真实FastAPI及SQLite，保存每个设计步骤的动作、预期、实测和断言；mock/API/组件检查不能代替。
4. 按SOP-013完成构建和基础检查，再按SOP-014运行固定单例或全量程序。更新用例使用本例拥有的回环更新源，验证拒绝路径和由App自主交接、重启的成功路径；不能手动启动高版替代升级。
5. 保存原始Playwright JSON、事件、trace、截图、SQL/fixture摘要、DB与服务审计、包和进程证据及清理结果。每次运行单独生成`TokenMeter测试结果-<run_id>.xlsx`，不覆盖历史；最终包另按SOP-017安装验证。

已知覆盖缺口由固定代码写`coverage-blocked.json`：CONFIG-01/05尚缺默认服务启动前网络观察，CONFIG-06尚缺验证与原生安装忙态观察，UPDATE-04尚缺零原生交接观察。其余断言通过时机器判BLOCKED；有确定性失败则FAIL优先。不得以局部通过宣称完整TC通过。

## 结果与发布

PASS/FAIL/BLOCKED取自原始机器结果；文档基线和编译成功不表示产品通过。缺程序、环境、步骤或证据为BLOCKED，确定性断言失败为FAIL；失败、跳过、重试取绿、清理失败或候选/包摘要不符均不放行。父门禁独立复核固定候选SHA、最终包、平台、完整TC集合和原始结果，只有全部通过才签发本地通行证。默认在本机运行，Actions仅在用户明确要求多环境时启用；DMG和执行原件只在本机按版本保存。
