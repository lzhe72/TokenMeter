# TM-004 隔离 Claude 探针派生数据

本目录的六份 JSONL 是 Claude Code 2.1.126 在隔离 `CLAUDE_CONFIG_DIR`、假 key、受限回环合成 API 下生成的原件的**字段投影**。投影删除了正文、完整本机路径及无关字段；原件 SHA、投影 SHA、行数和事先固定的独立预期见 [`provenance-and-expected.json`](native-2.1.126-projection/provenance-and-expected.json)。本机原始证据保留在 `.local/ci/tm004-claude-2.1.126-research/`，不进入 Git。

可重复执行：

```sh
python3 scripts/tm004_fixture.py verify-projection
python3 scripts/tm004_fixture.py verify-origin --research-root .local/ci/tm004-claude-2.1.126-research
python3 scripts/tm004_fixture.py generate --run-id demo
python3 scripts/tm004_fixture.py verify-run --run-id demo
python3 scripts/tm004_fixture.py reset --run-id demo
```

`verify-origin` 只读取显式指定的隔离研究目录；没有该本机原件时可独立使用已提交投影。`generate` 仅在仓库 `.local/test-runs/tm004-<run-id>/` 新建0700私有目录，写0600文件和所有权标记；`reset` 核对标记、文件集合、摘要及当前用户所有权后才删除这一批，不清理其他目录。重复 run-id 拒绝覆盖。

生成器另从 `raw-main` 投影确定性地产生四份**合成故障注入**：`fault-partial-before/after.jsonl` 分别是半行与补全行（独立预期0→一次20）；`fault-conflict.jsonl` 用同一调用 ID 但14/7制造冲突（可信仍20，诊断1）；`fault-missing-field.jsonl` 真正删去 usage（可信0，缺字段诊断1）。这些文件不属于 Claude CLI 输出，不能作为供应商格式或有效零的证据。确切预期固定在同一 JSON 中，生成程序不从产品统计结果推算预期。

| 投影场景 | 独立预期 | 证据边界 |
| --- | --- | --- |
| `raw-main` | 一次调用13/7，total20 | 隔离 CLI 原生用量字段的脱敏投影 |
| `raw-main` + `raw-fork` | 复制历史只计一次，再计新调用：2次、26/14、total40 | 此次 fork 保留原 UUID/`message.id`，没有 `forkedFrom` |
| `raw-agent-parent` + `raw-agent-sub` | 父两次17/5、23/7与子一次19/6：3次、59/18、total77 | 父工具结果中的子代理汇总不另计 |
| `raw-multiblock` | 两条 assistant 行共用调用 ID 和31/9：1次、total40 | 逐行相加80为错误 |
| `raw-missing-usage` | **不把0/0当已知有效零** | 畸形合成 SSE 缺usage，CLI仍写出0/0 |

这些投影可用于固定数据与解析/去重基础测试，**不能单独证明对原始 JSONL 的兼容，更不能代替安装后 App E2E**。M/S/N/P规划数字、改写 UUID、`fork-context-ref`、嵌套 Agent、真实有效零、半行恢复、TM-002 授权与 TM-003 SQLite 仍待独立 fixture 和固定产品测试；`claude_raw` 数据集继续 planned。不得从本目录样本向用户生产库、真实日志或默认凭据读写。
