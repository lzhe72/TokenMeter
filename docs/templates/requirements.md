# 本轮需求

**release_id：** `<release_id>`　**doc_id：** `<doc_id>`　**文档状态：** `draft`

**适用 SOP：** [SOP-002 需求定义](../../sop/SOP-002-requirements.md)；版本立项先执行 [SOP-001](../../sop/SOP-001-version-start.md)，文档变更执行 [SOP-024](../../sop/SOP-024-document-change.md)。

## 输入引用

- 本轮版本 manifest、基线 release_id（首次为 `null`）：`<实际引用>`。
- 用户要求、反馈或缺陷的可定位记录：`<实际引用>`。
- 长期约定：[产品设计](../../docs/product/README.md)、[版本规范](../../docs/standards/versioning.md)、[文档规范](../../docs/standards/documentation.md)。
- 当前实现和上一轮未完成项：`<实际状态/证据引用>`。

## 用户目标与范围

- 用户、使用场景及要解决的问题：
- 本轮目标和明确不纳入的内容：
- 已有行为、本轮变化及依赖：
- 支持的客户端、工具日志版本、部署方式和数据范围：

## 可观察验收条件

| source_requirement / 验收条件 ID | 用户操作及前置状态 | 正常结果 | 失败、边界和缺失数据结果 | 权限与数据约束 |
| --- | --- | --- | --- | --- |
| `<需求 ID / AC ID>` | `<实际场景>` | `<可观察结果>` | `<明确预期>` | `<允许/禁止的数据与操作>` |

为每项验收条件指定可自动验证的结果，登记独立 `tests/acceptance.json` 的 id、requirement_id、feature_id、spec、criterion 与 data_requirements；从已确定需求维护该清单，不能从用例反推删减。未知值和错误不能以零或成功掩盖。性能要求需写数据规模、环境和阈值。

## 决定与未决项

| 事项 | 已确认决定及依据 | 未决内容与解决动作 | 影响的验收条件 |
| --- | --- | --- | --- |
| `<事项>` | `<依据引用>` | `<无则写无>` | `<AC ID>` |

## 输出、验收与证据

- 输出：本轮 `01-requirements.md`、稳定需求/验收 ID，以及 manifest 中对应索引。
- 文档验收：范围可判断，每项行为可验收；影响范围或设计的未决项已解决；输入与 release_id 可追踪。
- 证据：在本轮 `06-iteration-record.md` 记录决定、依据和实际文档检查结果；未执行检查不得写通过。
- 下一步：[SOP-003 功能拆解](../../sop/SOP-003-feature-breakdown.md)，采用[拆解模板](breakdown.md)。
