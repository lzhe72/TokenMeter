# 02 · 内部安装与本机服务

适用 `v0.1.0-20260929T074814Z`，按[SOP-020](../../sop/SOP-020-deployment.md)执行。安装输入必须来自同名Git Release，并与该版本通行证及SHA256清单一致；最终包门禁未通过时不执行分发。支持macOS15的Apple Silicon和Intel。发布是否完成以远端Release及其通行证为准。

## 安装App

1. 下载该版本的DMG、服务器zip、候选更新zip、`package-manifest.json`、`<release_id>.passport.json`和SHA256清单，保存在同一独立目录。先用 `shasum -a 256 <文件>` 比较发布清单，包不同则停止。
2. 打开DMG，把TokenMeter拖到Applications；已有安装时先保留旧App和服务数据库的备份，确认版本后再替换。此包为团队内部自签包，没有Developer ID/Apple公证。首次打开如被系统拦截，在“系统设置→隐私与安全性”中对刚下载并核对的TokenMeter选择“仍要打开”；不关闭全局Gatekeeper或修改系统信任。
3. 启动下面两个本机服务，再打开App。默认API为 `http://127.0.0.1:49176`，更新源为 `http://127.0.0.1:49177/appcast.xml`，均指运行App的电脑。设置页可以修改；其他机器的地址使用HTTPS。

## 服务与数据库

解压服务器zip到持久目录，例如用户自行选择的 `TokenMeter-service`。以下命令在该目录执行，Python3.10+：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r server/requirements.txt
```

首次没有库时执行一次：

```sh
.venv/bin/python scripts/bootstrap_sqlite.py init-production
```

生产库在 `database/production/production.db`，初始管理员 `admin / 123456`，首次登录改密。初始化程序拒绝覆盖已有库；服务启动不重新造数。用户已有生产库时保留其账号和密码，不再次初始化，也不从测试库复制账号。测试库仅用于Codex隔离回归，不随发布包分发。

启动API（该终端保持运行）：

```sh
.venv/bin/python scripts/bootstrap_sqlite.py serve-production --host 127.0.0.1 --port 49176
```

另开终端启动更新源，把 `<发布资产目录绝对路径>` 替换为下载目录；其中必须包含原始清单、候选更新zip和通行证：

```sh
python3 scripts/local_distribution.py --release-dir '<发布资产目录绝对路径>'
```

更新源程序只监听127.0.0.1:49177，启动前核对通行证、清单及候选zip摘要，只提供健康探针、appcast和已验证的候选zip。它不发布101受控测试包，不接受手写通过报告代替受保护Release来源核验。部署者须先核对Git Release/通行证来源。端口占用直接失败，不终止或接管未知进程。按Ctrl-C停止自己启动的服务；生产数据库与App设置保留。

## 健康、备份与回退

- API启动后用 `curl --fail http://127.0.0.1:49176/v1/health` 核对健康；更新源用 `curl --fail http://127.0.0.1:49177/healthz` 核对实际版本。首次无更新时界面应显示当前已是最新版本。
- 在服务停止后用SQLite `.backup` 或Python `sqlite3.Connection.backup` 创建带时间戳的新备份；先在隔离副本执行 `PRAGMA integrity_check`，核对schema与账号再尝试恢复。不要直接复制正在写入的单个db文件而丢掉WAL。
- 安装或发布后检查失败时停止推广，按[SOP-021](../../sop/SOP-021-rollback.md)恢复已保存旧App/旧服务，数据库先验证备份兼容再恢复。首次内部版本没有上一稳定版，保留诊断并修复新候选，不将101测试包当回退或稳定发布。
- 本版服务采用前台启动以便明确进程归属。开机守护进程、远程团队服务器和其他系统版本留后续迭代，不预装未经测试的系统服务。
