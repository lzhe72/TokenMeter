# 05 · TM-005 用量统计：详细测试用例

新增 `TC-TM005-CORE-01/02/03` 的独立纯统计辅助切片详见[04a逐步用例](../../../releases/v0.5.0-20261001T034729Z/04a-test-cases.md#无原生日志依赖的纯统计辅助tc)及[合成fixture](../../../tests/fixtures/tm005-core-slice.json)。它只测试可信事件的双来源汇总、unknown与声明式coverage代数；本页原产品场景、32条产品TC及6变体仍待真实采集/App绑定，不从模块检查获取PASS。

需求：`REQ-TM005`。规划版本：`0.5.0`。功能与全部用例为 **planned**，未执行产品 E2E，无 PASS 证据和发布资格。以下是待实现用例规格；步骤具体描述目标行为，缺少的程序和环境逐项列明。不能把文档完整误报为用例可执行。

本轮双来源范围已确定：Codex 与 Claude Code 均必须从受支持原生日志经安装后的 App 采集。目标版本的任务拆解、[统计读取合同](../../../releases/v0.5.0-20261001T034729Z/03a-statistics-contract.md)、逐 TC 草案和规范化语义 oracle 分别见[02 拆解](../../../releases/v0.5.0-20261001T034729Z/02-breakdown.md)、[04a 逐 TC 草案](../../../releases/v0.5.0-20261001T034729Z/04a-test-cases.md)和[语义 oracle](../../../tests/fixtures/tm005-semantic-expected.json)。这些文件仍为 draft；现有 `date_ranges` 不具备原生数据或三态覆盖能力。

32 条父 TC 和 6 个稳定变体已逐行进入 `tests/test_cases.json` 与项目总表，均为 `baseline_pending` / `unexecuted`，产品绑定为空。固定预检 `python3 scripts/check_tm005_bindings.py` 报告 38 项绑定缺口；这是目录负测和阻断证据，不是产品 E2E。

## 共用前置与执行规则

依赖功能：`TM-003`、`TM-004`。进入实现前按 [SOP-006](../../../sop/SOP-006-test-plan.md) 确定当轮版本/平台矩阵，按 [SOP-010](../../../sop/SOP-010-test-data.md) 建立数据、SQL、独立 expected 及重置程序，再按 [SOP-011](../../../sop/SOP-011-test-implementation.md) 绑定真实测试；执行遵循 [SOP-014](../../../sop/SOP-014-e2e.md)。账号只用合成测试用户，所有数据库、日志、授权和设置均隔离；不得用用户生产库造数。

下面给出的规划数字用于约束独立预期，并不声称已经生成对应厂商日志。原始格式、UI标识、测试函数和SQL尚未确定的部分，必须在该功能开发前补齐；不得发明当前不存在的执行命令。未来版本的测试平台以当轮设计为准，当前v0.1.0只声明macOS15 arm64/Intel。

### 已有基础数据程序

在仓库根可运行 `python3 scripts/test_data.py generate --run-id case-spec-<唯一标识> --seed 42`，产物在 `.local/test-runs/<同一run-id>/`；完成检查后运行 `python3 scripts/test_data.py reset --run-id <同一run-id>`。使用符合程序规则的唯一小写run-id并替换占位符。仅生成标准化JSON/JSONL及独立expected，既不导入产品库也不建立原生测试。账号的真实初始化与SQL见[数据库说明](../../../database/README.md)。

## E2E-TM005-001 · 日期筛选、趋势和明细

**验收：** `AC-TM005-001`，每个 UI 指标、趋势和明细与独立 expected 对应范围一致。

**前置/数据：** 目标数据集 `tm005_raw_both` 为 planned，生成程序为 null；已有 `date_ranges` 仅由 scripts/test_data.py 提供标准化语义样例，固定2026-09-29T04:00:00Z、Asia/Shanghai、seed42，13行含1重复、12唯一。需两个来源各自已验证版本的 raw 映射和真实App导入流程，当前未实现。

**步骤：**

1. 使用隔离账号与对应raw事件从App真实采集，确认参考时钟和团队时区；不能直接改系统时钟。
2. 依次点击今天、昨天、近7天、近15天、近30天，逐一核对卡片、趋势各点和明细包含的event集合。
3. 选择自定义本地2026-09-20至2026-09-21（结束上界09-22 00:00），核对边界包含/排除。
4. 重复刷新并重启，恢复筛选后再核对所有值及重复事件处理。

**独立预期：** 独立expected中的total依次16500、110、17380、27830、31130；custom=2200。today共5条、input15000、output1500、cache1700、reasoning170，cache/reasoning不再相加；custom-start包含、custom-end排除。趋势点及明细按expected事件时间逐条核对。

**绑定/证据/状态：** `planned`；`automated_test=null`，未有原生函数绑定和执行证据。按 SOP-010/011 补齐后由 SOP-014 执行；缺项：现有生成命令和清理见本文件数据说明；缺raw映射、真实统计UI和自动化绑定、可复现时钟入口及用量库SQL/schema。只生成expected不代表App测试通过。 预期证据包括当前release_id/候选SHA、输入与expected摘要、原始原生结果、逐步断言/必要截图、数据/故障恢复与清理记录；当前这些产品证据尚不存在。

## E2E-TM005-002 · 时区、月边界与缺失值

**验收：** `AC-TM005-002`，自然日边界正确；无覆盖/未知数据与真实零值区别显示。

**前置/数据：** 目标数据集 `tm005_raw_both` 为 planned，生成程序为 null；语义设计复用date_ranges中的2026-09-28T15:59:59Z与16:00:00Z、2026-08-30T15:59:59Z与16:00:00Z边界。还需补充两个来源可证明的覆盖缺口、已覆盖零调用日、unknown字段三类原生状态；当前生成器未覆盖后面三类。

**步骤：**

1. 团队时区Asia/Shanghai时查看今天及近30天，检查边界前后事件分日。
2. 把团队时区改为UTC，保持事件时间不变，重新选择日期范围并观察按新本地日分桶。
3. 分别切换到无日志覆盖的日期、已确认完整但0调用的日期、存在unknown字段的日期。
4. 重启后重复相同筛选，核对时区配置和三类缺失状态持久一致。

**独立预期：** Shanghai下15:59:59Z仍属前日、16:00:00Z属次日；UTC下二者同属UTC日期。无覆盖显示缺失，真实零可显示0，unknown字段显示未知；不得互相代替。各范围expected须独立按当地日期边界列出，不调用产品查询生成。

**绑定/证据/状态：** `planned`；`automated_test=null`，未有原生函数绑定和执行证据。按 SOP-010/011 补齐后由 SOP-014 执行；缺项：已有date_ranges不足覆盖全部AC；需补缺失/零/unknown数据、UTC独立expected、时区设置UI和原生绑定；SQL导入方案待schema和raw链路设计。 预期证据包括当前release_id/候选SHA、输入与expected摘要、原始原生结果、逐步断言/必要截图、数据/故障恢复与清理记录；当前这些产品证据尚不存在。

## 追踪与退出条件

与[用例总索引](README.md)、[验收清单](../../../tests/acceptance.json)、[功能矩阵](../../../tests/feature_matrix.json)和[数据清单](../../../tests/datasets.json)使用相同稳定ID。各例列出的缺项全部落实为程序/数据/自动化绑定后才能进入完整实现；实际运行结果另存机器报告。一个子场景失败或未执行，不能把所在整例记PASS。
