# SOP-001 版本立项

**修订：** 2　**状态：** baselined　**适用：** all

## 目的与范围

建立唯一 release_id 和可查询版本档案，确定本次产品、修复或基础建设工作的边界。

## 触发条件

收到新版本目标，或 SOP-023 已将反馈整理为下一轮工作。

## 前置条件

读取 [版本规范](../docs/standards/versioning.md)、releases/current.json 和已有档案；确定是否续作当前未发布版本。不要为同一迭代重复分配编号。

## 输入

用户目标、上版 release_id、当前 Git 状态、语义版本规则、[版本模板](../docs/templates/lifecycle-bundle.md)。

## 执行步骤

1. 执行 python3 scripts/release_registry.py show 核对当前档案和发布状态；已发布版本不可继续覆盖，修复分配新版本。
2. 按变更性质选择 MAJOR/MINOR/PATCH，在立项时以 UTC 秒时间分配 vMAJOR.MINOR.PATCH-YYYYMMDDTHHMMSSZ；此后固定不变。
3. 按版本规范建立 releases/<release_id>/00-manifest.json 及 01–06 编号文档；技术设计在开发计划中记录或链接附件，记录基线及本轮目标。
4. 更新 releases/current.json、文档目录、Changelog 的精确版本标题；使用版本规范中的分支和提交命名，先保留现有未提交工作。
5. 明确档案为未发布；本轮基础建设继续使用 v0.0.1-20260929T060944Z，不创建产品 tag。

## 输出

唯一版本编号、当前版本指针、完整档案骨架、版本范围与基线。

## 成功与失败判据

编号格式合法、索引唯一、基线可定位、产品版本与 release_id 一致才可继续需求设计。空档案不是文档基线，通过结构检查也不是发布资格。

## 异常恢复

若发现重复编号或覆盖已发布版本，停止分配并核对历史；保留错误记录，修正未发布档案及引用，不改旧 tag。

## 证据位置

版本 manifest 与 06-iteration-record.md 记录编号来源、基线、范围和建立时间；Git 状态仅引用必要结果。

## 下一步

执行 [SOP-002 需求定义](SOP-002-requirements.md)。
