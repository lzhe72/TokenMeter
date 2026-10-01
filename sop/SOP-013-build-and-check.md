# SOP-013 构建与检查

**修订：** 9　**状态：** baselined　**适用：** all

## 目的与范围

在本机运行文档、基础工具、服务与Electron构建检查。

## 触发条件

实现/依赖变化后、开发功能回归前；正式发布完整E2E前再次针对最终候选执行。

## 前置条件

012实现、009本机运行时和锁文件就绪。

## 输入

候选源码、依赖和真实命令。

## 执行步骤

1. 整版已基线或正式发布时运行`python3 scripts/check_docs.py --mode baseline`及`python3 scripts/quality_gate.py check`，核对文档与完整追踪。仅按SOP-008独立开发切片推进且整版仍draft时，运行`python3 scripts/check_docs.py --mode structure`和治理测试，核对切片ID/依赖/输入摘要与SOP-008就绪记录；整版baseline/quality保留原NOT_RUN或FAIL/BLOCKED，不因其未通过阻断已核准的独立切片，但绝不称整版文档PASS。
2. 执行python3 -m unittest discover -s tests/governance -p test_*.py，使用隔离Python执行.local/venv-tm001/bin/python -m pytest tests/server -q；保留原始数量/退出码。已基线的固定模块TC按SOP-011绑定的独立命令逐项运行，保存预先冻结的TC清单、测试代码/输入摘要、commit/tree、run_id、执行环境、原始输出、退出码、实际断言与清理证据。一个命令包含多个TC时须由固定程序输出逐TC结果和可追溯的失败归属；聚合计数不能凭名称分配PASS。模块检查的执行类型固定为`source_check`，产品E2E状态另记`NOT_RUN`或引用SOP-014同候选的真实批次。零例、跳过、重试取绿或缺逐TC判据按真实状态记FAIL/BLOCKED，不得推断通过。
3. 在apps/desktop按009锁文件安装依赖/运行时，再执行npm run build和npm test。图标SVG改变时在根目录执行node scripts/build_desktop_icon.mjs，检查PNG/ICNS；正式包检查嵌入图标摘要。
4. 锁定Electron/Playwright与构建工具，核对CSP、IPC、凭据、配置URL、更新验证层基础负测。遗留Swift工具可用于历史回归，不是新客户端验收入口。
5. 图形界面变动按当前设计在真实App检查默认/最小尺寸、深浅色、焦点与表单状态并保存截图；适用时执行`.local/venv-tm001/bin/python apps/desktop/tests/visual_fixture.py`生成隔离SQL/服务与10张截图，由`apps/desktop/tests/hig.visual.cjs`断言并审查截图。`scripts/quality_gate.py check`只检查文档和追踪；开发阶段按SOP-014执行本功能已基线固定TC的真实产品回归。用户另行启动正式发布后，在最终候选重新执行适用基础检查、完整跨需求E2E，并由SOP-018使用`scripts/local_gate.py`核验。打包检查使用同一候选源码/依赖，不得以基础检查代替产品PASS。
6. 对每次固定模块TC的实际运行，由仓库中固化的`source_check`导出程序读取本次不可覆盖的原始报告/日志与摘要，生成`TokenMeter测试结果-<run_id>.xlsx`及独立导出收据，保留FAIL/BLOCKED和缺失项。Excel至少含批次身份、执行类型、候选SHA/tree、环境、逐TC预期与实际断言/步骤、结果、证据路径及摘要、数据/重置和清理状态；不能从设计文档或人工判断生成实测值。程序必须拒绝错误类型、不同run/候选/输入、日志摘要不符、缺证据、重复ID或覆盖历史文件；导出后回读行数、ID和状态，并保留负测原始输出。当前仓库若只有产品E2E导出程序，不能把模块结果包装成其`result.json`或`E2E-TM...`行；在真实模块导出程序和所需逐TC原始字段接通前，保留模块测试原始PASS/FAIL，但将Excel导出与批次索引记BLOCKED，缺字段须新run补采而非修改旧原件。按SOP-024交文档会话同步总表规范与模板。

## 输出

构建物、基础及固定模块TC原始结果、独立批次Excel和导出收据，或精确缺项。

## 成功与失败判据

所有本阶段适用基础检查真实通过；失败、零测试、缺构建物不能称本阶段通过。固定模块TC原始执行结论与报告导出结论分开：测试可据原件记真实PASS，导出缺失时本阶段结果归档/总表登记仍为BLOCKED。模块PASS不证明产品E2E通过或功能产品验收。未执行的正式门禁记NOT_RUN，不阻断源码版本登记。

## 异常恢复

保留首个失败并修根因，然后重做受影响基础检查及本功能固定TC；正式发布时对最终候选执行完整E2E。

## 证据位置

本机.local/ci日志与版本06。

## 下一步

014本功能固定TC回归；收到正式发布指令时在最终候选进入014完整E2E。

具体合同见[Electron本机设计](../docs/architecture/01-electron-local.md)。旧云端/Swift路径仅用于历史查询，不能覆盖用户本机优先规则。
