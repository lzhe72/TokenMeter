# SQLite 数据库

服务端使用两个独立文件。当前仓库的实际位置是：

| 用途 | SQLite 文件 | 账号 |
| --- | --- | --- |
| 应用回归 | `/Users/Shared/Previously Relocated Items/Security/work/git/TokenMeter/database/test/test.db` | `test-admin`、`test-alice`、`test-bob`、`test-disabled`，来自现有回归 fixture |
| 生产使用 | `/Users/Shared/Previously Relocated Items/Security/work/git/TokenMeter/database/production/production.db` | 首次初始化仅有 `admin` |

数据库文件、生成的 SQL 和所有权标记是本机数据，已加入 `.gitignore`。目录里的 `.gitkeep` 保证新检出后能找到位置。移动仓库后，以新位置的绝对路径为准。客户端本机数据与这里的服务端账号库属于不同存储。

## 首次初始化

在仓库根目录使用已按 [SOP-009](../sop/SOP-009-environment.md) 安装依赖的 Python 环境：

```sh
.local/venv-tm001/bin/python scripts/bootstrap_sqlite.py init-test --run-id local-20260929
.local/venv-tm001/bin/python scripts/bootstrap_sqlite.py init-production
.local/venv-tm001/bin/python scripts/bootstrap_sqlite.py verify
```

`init-test` 对照 [`tests/server/fixtures.py`](../tests/server/fixtures.py) 生成四个回归账号；`init-production` 在**空生产库**中写入一个管理员，用户名 `admin`、初始密码 `123456`，登录后必须先改成至少 12 位的新密码。脚本先在私有临时目录完成迁移、SQL 和账号校验，全部通过后才公布数据库文件；失败时清除临时文件。启动服务不会重新执行建表或造数，也不会重置密码。初始化发现已有数据库或 SQL 文件会拒绝覆盖，因此生产库只能首次初始化一次。密码在两个数据库中均保存为每次生成的新随机盐 Argon2 散列；生成的 SQL 不含明文密码。

固定的 `database/test/test.db` 只供 Codex 在本机检查账号数据和做应用回归，不供用户使用。自动原生 E2E runner 按每个用例在临时目录创建测试 SQLite，使用同一账号 fixture，以免上一例改密或停用污染下一例；它不会读写固定测试库。第005例另用临时生产库验证正式初始化逻辑，绝不连接用户的生产文件。

脚本同时生成并执行可查看的 SQLite SQL：

- `database/test/seed.sql`：四个回归账号及创建审计记录。
- `database/production/seed.sql`：首次生产管理员及创建审计记录。

SQL 在执行时检查库内环境标记和 `users` 空表。再次执行会失败，指向另一套数据库也不会写入账号。需要手工执行时，先确认目标是相应的**已迁移空库**，再使用 `sqlite3 -bail <数据库文件> < <对应的 seed.sql>`；通常直接运行初始化脚本即可。不要把生成的数据库或 SQL 提交到 Git。

## 启动生产服务

在仓库根目录运行：

```sh
.local/venv-tm001/bin/python scripts/bootstrap_sqlite.py serve-production --host 127.0.0.1 --port 49176
```

该入口从脚本所在仓库动态定位数据库，将 `TOKENMETER_DATABASE_URL` 明确设为 `sqlite:////Users/Shared/Previously Relocated Items/Security/work/git/TokenMeter/database/production/production.db`（当前路径），再启动真实 FastAPI 服务。移动或重克隆仓库后无需修改命令；可用 `printf '%s/database/production/production.db\n' "$(pwd -P)"` 查看新绝对路径。启动前只读核对 schema、库内环境标记和活动管理员，不导入测试账号。此预览入口仅允许绑定 `127.0.0.1` 或 `::1`，拒绝公网地址；当前已安装的 `.UITesting` 预览 App 默认接受 `http://127.0.0.1:49176` 本机服务。正式生产 App 要求 HTTPS 服务地址。首次登录 `admin` / `123456` 后按界面要求修改密码；修改前管理员接口会拒绝使用。正式对外访问的 TLS 和部署配置仍按发布预案执行。

## 用 SQL 查看数据

SQLite 可以直接执行 SQL。下列命令只读，不会创建或修改文件：

```sh
sqlite3 -readonly database/production/production.db \
  'SELECT username, role, is_active, must_change_password FROM users ORDER BY username;'
sqlite3 -readonly database/test/test.db \
  'SELECT username, role, is_active, must_change_password FROM users ORDER BY username;'
sqlite3 -readonly database/test/test.db \
  "SELECT action, datetime(occurred_at, 'unixepoch') AS utc_time FROM audit ORDER BY occurred_at;"
```

`is_active` 和 `must_change_password` 分别以 `1`/`0` 表示是/否。不要查询或复制 `password_hash`、会话 token 摘要到共享报告。

## 重建测试库

先停止正在使用 `test.db` 的服务和测试进程。读取 `database/test/.tokenmeter-test-database.json` 中的 `run_id`，再运行：

```sh
.local/venv-tm001/bin/python scripts/bootstrap_sqlite.py rebuild-test \
  --current-run-id local-20260929 --run-id local-20260929-r2
.local/venv-tm001/bin/python scripts/bootstrap_sqlite.py verify
```

脚本核对文件和库内所有权、拒绝 SQLite sidecar 文件，先建立并验证新的测试库，在 `.local/sqlite-db-backups/<旧 run_id>/` 备份旧文件，然后原子替换单个 `test.db`，再更新 SQL 和标记。新 run ID 必须不同；归档目录已存在时拒绝覆盖。若进程在数据库替换后意外中断，先停止测试服务，执行 `.local/venv-tm001/bin/python scripts/bootstrap_sqlite.py repair-test-material`，它依据新数据库的内部所有权重新生成标记和 SQL；再运行 `verify`。生产库无重建命令。生产数据的备份和恢复按 [SOP-016](../sop/SOP-016-database-migration.md) 与发布预案执行。
