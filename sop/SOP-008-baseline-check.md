# SOP-008 基线检查

**修订：** 5　**状态：** baselined　**适用：** all

## 目的与范围

在产品实现前确认文档、编号/引用及需求到测试一致。整版基线与用户2026-10-01允许的独立开发切片基线分别判定，后者不授予整版基线或发行资格。

## 触发条件

SOP-001–007的版本计划全部完成、文档/SOP迁移整合后，或已建基线发生影响实现的变化；也可在整版仍draft时，为不依赖未决条件的明确TASK/TC子集建立开发切片。单份草稿编制按SOP-024检查后返回原步骤。

## 前置条件

整版基线要求SOP-001–007档案和内容齐全，必要元数据和SOP已登记；draft内容先解决实际缺项，不能提前改成baselined。开发切片要求具体TASK/TC的需求、设计、数据、步骤、逐步预期、依赖和非目标均已固定且可独立验证；任何`baseline_pending`决定若可能改变该切片的预期、身份/权限、安全边界、接口或数据口径，该切片仍BLOCKED。切片不改变整版draft与其他TC的pending状态。

## 输入

docs/catalog.json、当前manifest、需求/拆解/设计/开发/测试/发布文档、Changelog和功能矩阵；切片另列明确TASK ID、TC ID、固定版本文件/提交及其依赖、未决项隔离说明。

## 执行步骤

1. 整版检查每个功能点→具体TASK→TC的双向关系；每条用例须有具体输入、步骤、预期、DB操作、类型、数据/重置方案与结果入口。切片只对列明的TASK/TC逐项做同等内容检查，记录它们与其他目标及未决决定的依赖边界；模块级任务或汇总E2E ID不算齐全。切片内关键预期仍为`baseline_pending`即阻断该TC及其依赖开发；切片外目标保持原draft/pending，不删除、不降级为未来项以求通过。未实现的自动化允许如实为空并安排SOP-011任务，不预填PASS。

2. 对照索引确认必需文档、十章节 SOP、release_id、基线和引用一致。检查完整需求→任务→测试计划追踪；待在 SOP-009–011 建立的程序登记 `program_bindings_status=planned`，可用 `test_programs=[]`、`test_data_program=null`，但 `test_sop` 必须真实，已填程序路径必须存在，补齐任务可追踪。不能要求计划中的工程与测试预先实现，也不能虚构程序绑定通过本步骤。
3. 整版执行`python3 scripts/check_docs.py --mode baseline`及`python3 scripts/quality_gate.py check`，保存完整结果并修错；`--mode structure`不能替代整版严格基线。切片只执行已有`python3 scripts/check_docs.py --mode structure`及`python3 -m unittest discover -s tests/governance -p 'test_*.py'`，记录退出码、数量和提交SHA；再核对固定TC ID及关联文件摘要。当前工具没有局部baseline模式，不虚构切片机器PASS：把整版`baseline`和`quality_gate check`真实结果记为NOT_RUN或FAIL/BLOCKED，切片内容核对结论单列为`development_slice_ready`或BLOCKED，不写`documentation_baseline PASS`。
4. 做内容核对：整版检查全部目标，切片检查列明TASK/TC的每个验收条件、数据/重置、程序准备任务及依赖；核对需求定义表、`tests/acceptance.json`、用例矩阵和版本计划对这些ID的双向一致性。逐项写明整版剩余目标/`baseline_pending`及为何不影响此切片，不允许删除目标或改成planned来绕过检查。
5. 在版本06和状态页记录切片ID集合、输入文件及SHA/提交、结构/治理命令与结果、逐TC语义核对、未决依赖、`development_slice_ready`判定、整版仍draft及正式发行NOT_RUN。若相关设计或未决项变化，撤销受影响切片就绪结论并重新检查；只有整版条件齐全后才跑本SOP整版baseline/quality及登记文档baselined。

## 输出

结构校验结果、语义一致性记录、整版文档基线或明确未决清单；可选的独立开发切片就绪记录，仍保留整版draft与未决TC。

## 成功与失败判据

整版须baseline与quality两项命令成功且全部目标内容无关键冲突才记文档baselined。开发切片须步骤1–5所列固定ID、依赖隔离、结构/治理检查和语义核对全部成立，才可仅对该切片进入009–014；其他TASK/TC和整版发行仍BLOCKED。结构通过但切片行为不明确时不能开发依赖工作。两种结论均不生成产品PASS。

## 异常恢复

按错误回到对应SOP修复并重新检查；不要删除必需功能、伪造文件或改成planned来绕过检查。切片因未决项受影响则暂停该切片，其他真正独立切片可继续。

## 证据位置

06-iteration-record.md 引用命令、退出码和修正项；候选提交保存文档基线，后续运行记录绑定该提交。

## 下一步

整版基线或已核准的独立开发切片进入[SOP-009 环境准备](SOP-009-environment.md)及其依赖任务；完整发行仍须整版基线、最终候选全量门禁和用户正式发布指令。无产品行为的文档工作转[SOP-022](SOP-022-archive-handoff.md)。
