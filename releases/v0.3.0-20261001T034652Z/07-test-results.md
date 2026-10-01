# v0.3.0-20261001T034652Z · 测试结果

**产品状态：** 安装App的TM-003产品TC仍未执行/BLOCKED；尚无其SOP-010固定产品数据、完整逐TC程序、最终DMG或产品原始结果，不能引用TM-001历史PASS。以下均为SOP-013 `source_check`独立辅助模块；每次原报告与`TokenMeter测试结果-<run_id>.xlsx`在本机按run不可覆盖，根总表只保存摘要。模块PASS不转为产品E2E或发行资格。

| run_id | 被测候选 | 固定范围与实际结果 | 独立结果Excel |
| --- | --- | --- | --- |
| `tm003-core-20261001T163807Z` | 见版本06/原报告 | CORE01/02/03 3/3 PASS，九步 | `.local/test-results/tm003-core-20261001T163807Z/` |
| `tm003-core-20261001T165439Z` | 见版本06/原报告 | CORE01/02/03 新run 3/3 PASS，旧run仍保留 | `.local/test-results/tm003-core-20261001T165439Z/` |
| `tm003-core45-20261001T175000Z` | `9efc6fa9` | CORE04/05 2/2 PASS，九步 | `.local/test-results/tm003-core45-20261001T175000Z/` |
| `tm003-core06-20261001T182500Z` | `eef956b8` | CORE06 1/1 PASS，四步；先前红测FAIL保留 | `.local/test-results/tm003-core06-20261001T182500Z/` |
| `tm003-core07-20261001T200438Z` | `33b1ee1636fc8e92ecba834856769df9f112c509`，tree`3ad0cc5b5a054a8f1f011dbb2496f2d33babf77b` | CORE07 1/1 PASS，五步、清理PASS；此前`collector_not_implemented`红测FAIL保留 | `.local/test-results/tm003-core07-20261001T200438Z/`；Excel SHA-256 `d96b274d2caa2991cca8ba8a11b6c6205aea4b80b6bfe00285de2aa4c1bb0f29` |

最新CORE07原报告`.local/source-check-runs/tm003-core07-20261001T200438Z/report.json` SHA-256 `7c717f0e2a09937f93f2b09e973ee7aa032bdc17c3751cf99c456879b05b5398`，verification回读PASS；被测用例目录SHA-256 `58634134d220097666d8251e7fd3d5d277b69f779be6508a2e4ec6e21da9f177`，等于文档冻结输入`a3e99da`中的目录。开发树基础检查结构PASS、治理511/511、桌面构建PASS；结构首次因本地SOP-008收据未复制而失败，复制核对后通过。其程序尚未进入本文档树，机器`binding`仍null；真实TM-002授权、Keychain、App/IPC、任意大文件和产品E2E仍待独立验证。
