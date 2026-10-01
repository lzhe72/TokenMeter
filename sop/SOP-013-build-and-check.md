# SOP-013 构建与检查

**修订：** 7　**状态：** baselined　**适用：** all

## 目的与范围

在本机运行文档、基础工具、服务与Electron构建检查。

## 触发条件

实现/依赖变化后、进入完整E2E前。

## 前置条件

012实现、009本机运行时和锁文件就绪。

## 输入

候选源码、依赖和真实命令。

## 执行步骤

1. 运行python3 scripts/check_docs.py --mode baseline及python3 scripts/quality_gate.py check，核对文档与完整追踪。
2. 执行python3 -m unittest discover -s tests/governance -p test_*.py，使用隔离Python执行.local/venv-tm001/bin/python -m pytest tests/server -q；保留原始数量/退出码。
3. 在apps/desktop按009锁文件安装依赖/运行时，再执行npm run build和npm test。图标SVG改变时在根目录执行node scripts/build_desktop_icon.mjs，检查PNG/ICNS；正式包检查嵌入图标摘要。
4. 锁定Electron/Playwright与构建工具，核对CSP、IPC、凭据、配置URL、更新验证层基础负测。遗留Swift工具可用于历史回归，不是新客户端验收入口。
5. 图形界面按当前设计在真实App检查默认/最小尺寸、深浅色、焦点与表单状态并保存截图；执行`.local/venv-tm001/bin/python apps/desktop/tests/visual_fixture.py`生成隔离SQL/服务与10张截图，12项辅助检查由`apps/desktop/tests/hig.visual.cjs`断言，截图审查后自主修复。`scripts/quality_gate.py check`只检查文档和追踪；基础检查通过后按 SOP-014 执行真实桌面全量E2E，正式候选由 SOP-018 使用`scripts/local_gate.py`核验。打包检查使用同一候选源码/依赖，不得以基础检查代替产品PASS。

## 输出

构建物和基础原始结果或精确缺项。

## 成功与失败判据

所有适用基础检查真实通过；失败、零测试、缺构建物都不能放行。

## 异常恢复

保留首个失败并修根因，然后受影响基础检查与完整E2E。

## 证据位置

本机.local/ci日志与版本06。

## 下一步

014完整E2E。

具体合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。旧云端/Swift路径仅用于历史查询，不能覆盖用户本机优先规则。
