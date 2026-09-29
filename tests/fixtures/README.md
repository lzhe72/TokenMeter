# 可复现测试数据

运行 `python3 scripts/test_data.py generate --run-id demo --seed 42`，在当前仓库的 `.local/test-runs/demo/` 生成以下文件。运行 `python3 scripts/test_data.py reset --run-id demo` 清理这一批数据。

**这些是人工定义的、标准化的测试规格，不是经过验证的 Codex / Claude Code 原始日志格式，不证明解析器支持任何工具或模型，也不是产品 E2E 通过证据。** `source` 和 `model` 字段仅用于未来统计模块的输入测试。正式解析器必须另行提供来自支持版本、完成脱敏的原始日志样本与对应解析测试。

| 文件 | 内容 |
| --- | --- |
| `.tokenmeter-fixture.json` | 工具归属、run-id、文件清单，用于限制清理范围 |
| `users.json` | 合成管理员、两名成员、停用账号及明显标注的测试密码 |
| `usage.jsonl` | 13 行、12 个独立事件，含重复事件、多个模型、三个设备、两个成员、日期边界和未知价格 |
| `prices.json` | 虚构 USD 单价，不能用于实际计费 |
| `expected.json` | 独立写明的预期总量、日期区间、成员统计及费用结果 |
| `manifest.json` | 格式版本、随机种子、固定时钟、时区、数据集映射和其他文件 SHA-256 |

固定时钟为 `2026-09-29T04:00:00Z`，时区为 `Asia/Shanghai`。近 N 天包含今天；日期范围左闭右开。输入 Token 包含缓存读取量，输出 Token 包含推理量，不能重复相加。费用结果区分已知价格部分与价格缺失事件；价格缺失不表示免费。

数据集标识为 `identity`、`usage_normalized`、`pricing`、`date_ranges` 和 `duplicates`。相同 run-id 和种子在不同工作目录生成完全相同的文件。种子改变记录顺序和测试密码，不改变预期汇总。seed 为 42 时，用户名为 `test-admin` / `test-alice` / `test-bob` / `test-disabled`，密码格式为 `TEST-ONLY-<名称>-42!`，例如 `TEST-ONLY-alice-42!`。

本程序只生成文件，**尚未创建应用账号、初始化业务数据库或执行 E2E**。产品实现时必须新增隔离测试环境的账号/数据库初始化程序和 SOP，并由真实 E2E 消费这些输入和预期结果。禁止将测试密码或价格写入生产环境。

清理操作不接受自定义路径或数据库连接，只允许合法 run-id；拒绝符号链接、缺失或不匹配的归属标记，以及额外文件或目录。已存在的目录不会被重新生成覆盖。清理拒绝时应先确认文件归属，不要用宽泛的递归删除绕过保护。

工具自测：`python3 -m unittest discover -s tests/governance -p 'test_test_data.py' -v`。完整使用与故障处理步骤见 [测试 SOP](../../docs/testing/execution.md)。
