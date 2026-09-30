# 06 · TM-006 费用估算：详细测试用例

需求：`REQ-TM006`。规划版本：`0.6.0`。功能与全部用例为 **planned**，未执行产品 E2E，无 PASS 证据和发布资格。以下是待实现用例规格；步骤具体描述目标行为，缺少的程序和环境逐项列明。不能把文档完整误报为用例可执行。

## 共用前置与执行规则

依赖功能：`TM-005`。进入实现前按 [SOP-006](../../../sop/SOP-006-test-plan.md) 确定当轮版本/平台矩阵，按 [SOP-010](../../../sop/SOP-010-test-data.md) 建立数据、SQL、独立 expected 及重置程序，再按 [SOP-011](../../../sop/SOP-011-test-implementation.md) 绑定真实测试；执行遵循 [SOP-014](../../../sop/SOP-014-e2e.md)。账号只用合成测试用户，所有数据库、日志、授权和设置均隔离；不得用用户生产库造数。

下面给出的规划数字用于约束独立预期，并不声称已经生成对应厂商日志。原始格式、UI标识、测试函数和SQL尚未确定的部分，必须在该功能开发前补齐；不得发明当前不存在的执行命令。未来版本的测试平台以当轮设计为准，当前v0.1.0只声明macOS15 arm64/Intel。

### 已有基础数据程序

在仓库根可运行 `python3 scripts/test_data.py generate --run-id case-spec-<唯一标识> --seed 42`，产物在 `.local/test-runs/<同一run-id>/`；完成检查后运行 `python3 scripts/test_data.py reset --run-id <同一run-id>`。使用符合程序规则的唯一小写run-id并替换占位符。仅生成标准化JSON/JSONL及独立expected，既不导入产品库也不建立原生测试。账号的真实初始化与SQL见[数据库说明](../../../database/README.md)。

## E2E-TM006-001 · Token子项与基础费用

**验收：** `AC-TM006-001`，计费子项不重复，金额与独立预期一致。

**前置/数据：** 数据集 `pricing`；pricing由scripts/test_data.py生成合成非计费价格。gpt-5每百万input/cache/output为USD2/0.2/8；today-gpt input1000含cache200、output100含reasoning20。价格不是厂商现价。

**步骤：**

1. 将对应raw调用经App采集并应用fixture价格版本，显示该模型明细。
2. 查看该调用input、cache、output、reasoning、total与费用。
3. 查看today范围和成员alice汇总，核对价格版本及估算标签。
4. 重复扫描和重启，确认费用不随重复记录增长且价格版本不变。

**独立预期：** 单调用total=1100；费用=(800×2+200×0.2+100×8)/1000000=USD0.002440，reasoning20不另加价。today已知费用USD0.015190且有1条无价格，alice今日USD0.010090。使用Decimal/十进制独立oracle，不以界面舍入反推底层精度。

**绑定/证据/状态：** `planned`；`automated_test=null`，未有原生函数绑定和执行证据。按 SOP-010/011 补齐后由 SOP-014 执行；缺项：pricing基础数据available，但缺真实raw映射、价格管理/费用UI、原生绑定；无已实现用量与价格表SQL导入器。 预期证据包括当前release_id/候选SHA、输入与expected摘要、原始原生结果、逐步断言/必要截图、数据/故障恢复与清理记录；当前这些产品证据尚不存在。

## E2E-TM006-002 · 历史价格、多币种和未知费用

**验收：** `AC-TM006-002`，未知费用不填零，历史保留价格版本，分币种汇总且标明估算。

**前置/数据：** 数据集 `pricing_extended`；pricing_extended planned：同模型在生效时点T前后各一调用，两个独立价格版本；另有USD/CNY各一模型、无价模型和订阅估算模型。必须提供价格/订阅分摊规则及手算expected后才能实现。

**步骤：**

1. 在T前写入调用并统计，保存其价格版本和费用；再添加T生效的新价格和T后调用。
2. 重新查询旧期间，核对历史调用仍引用原价格版本；查看跨T范围的逐条金额。
3. 加入不同币种与无价格记录，从App查看总览/明细。
4. 加入订阅估算样例并检查说明，再重启核对价格版本、币种分组和unknown持久一致。

**独立预期：** T前后依各自生效版本计算，历史结果不会悄悄换价；USD与CNY分组，未约定汇率不得相加；无价格显示未知而非0；订阅必须明确估算口径。具体金额oracle依待定义订阅/价格合同生成，当前不得手填PASS。

**绑定/证据/状态：** `planned`；`automated_test=null`，未有原生函数绑定和执行证据。按 SOP-010/011 补齐后由 SOP-014 执行；缺项：缺pricing_extended生成/清理、历史价格及多币种SQL、订阅口径/独立数值expected、原生UI；基础pricing不能代替扩展集。 预期证据包括当前release_id/候选SHA、输入与expected摘要、原始原生结果、逐步断言/必要截图、数据/故障恢复与清理记录；当前这些产品证据尚不存在。

## 追踪与退出条件

与[用例总索引](README.md)、[验收清单](../../../tests/acceptance.json)、[功能矩阵](../../../tests/feature_matrix.json)和[数据清单](../../../tests/datasets.json)使用相同稳定ID。各例列出的缺项全部落实为程序/数据/自动化绑定后才能进入完整实现；实际运行结果另存机器报告。一个子场景失败或未执行，不能把所在整例记PASS。
