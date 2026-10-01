# v0.1.0-20260929T074814Z — 功能与任务拆解

## 历史工作分组与依赖

输入：[需求](01-requirements.md)，全部任务归属 TM-001 / REQ-TM001。以下原七项保留作历史工作分组，不再作为可直接实施的最小任务。新的具体任务在下一节，每项须先具备对应TC设计。

| 任务 | 产出与完成标准 | 前序 | 对应用例 |
| --- | --- | --- | --- |
| TASK-TM001-PLAN | 六文档、完整追踪、SOP 修正、基线通过 | 需求 | TEST-TM001-GOVERNANCE |
| TASK-TM001-SERVER | FastAPI/SQLAlchemy/Alembic 工程、真实认证/权限/审计 API；随机可撤销 token 固定30天到期、不滑动，改密/重置/停用撤销旧会话 | 计划、数据/测试 | E2E-TM001-001、E2E-TM001-002、E2E-TM001-003 |
| TASK-TM001-DATA | 独立测试/生产 SQLite 文件、可执行造数 SQL、生产首建管理员、回归账号/独立预期及安全重置；已有生产密码不可被重建覆盖 | 计划、工程骨架 | TEST-TM001-SERVER、E2E-TM001-001、E2E-TM001-005 |
| TASK-TM001-MAC | Electron React/TypeScript 登录/改密/主页/管理、默认本机 API/更新源地址与配置管理页的用户覆盖持久化；默认开启可关闭的设备自动登录、按规范化 origin 隔离的受保护凭据文件与内存会话、稳定 UI 标识、Playwright Electron工程 | API 合同、工程骨架 | E2E-TM001-001、E2E-TM001-002、E2E-TM001-003、E2E-TM001-004、E2E-TM001-005、E2E-TM001-006 |
| TASK-TM001-UPDATE | 固定 Ed25519 公钥、同机回环更新源/签名测试包/失败包及真实更新用例；默认49177配置、URL安全校验与升级时锁定更新设置；两构建沿用经校验的同一隔离profile，升级后服务验证自动登录 | Mac 工程 | E2E-TM001-004 |
| TASK-TM001-RUNNER | 本机Playwright从最终DMG安装App执行全部六例，原始JSON/trace/fixtureSQL/包摘要、父门禁复核；默认值与动态独占端口隔离测试；真实Squirrel自重启及profile、身份恢复 | 数据/桌面工程 | E2E-TM001-001、E2E-TM001-002、E2E-TM001-003、E2E-TM001-004、E2E-TM001-005、E2E-TM001-006 |
| TASK-TM001-REVIEW | 完整回归、流程复盘、PR 与合并判定、发布阻塞记录 | 全部实现任务 | TEST-TM001-GOVERNANCE |

工程骨架可在业务红测前建立；可独立验证的服务 API/数据/源码任务并行推进，缺 native 运行不宣称业务 E2E 已完成。文件所有权在开发计划中固定。

## 当前未发布版本的架构迁移

沿用原任务ID和全部验收范围。PLAN同步本机Electron基线；MAC重建界面/IPC与token隔离；UPDATE生成固定签名100候选和101受控包；RUNNER真实安装后六例与父门禁；REVIEW本地归档和源码PR自动合并。Git不保存DMG/报告/通行证，Actions默认不触发。文件边界见[当前设计](../../docs/architecture/01-electron-local.md)。旧Swift代码与CI结果属于历史，不能代表新执行器就绪。

## 需求阶段的具体开发任务

功能点见[功能列表](01a-feature-points.md)。以下TASK全称为 `TASK-TM001-` 加任务列，FP全称为 `FP-TM001-`，AC全称为 `AC-TM001-`。依赖列同样使用任务尾名。已存在代码标作待对照用例核验，不以源码存在宣布完成。

| 任务 | 功能点 | AC | 输入 | 具体产出及完成标准 | 依赖 |
| --- | --- | --- | --- | --- | --- |
| TASK-TM001-LOGIN-VALIDATION | FP-TM001-01 | 001、002 | 用户输入与格式/长度规则 | 登录表单输入验证、错误显示和无会话副作用；对应用例全部有真实记录 | PLAN |
| TASK-TM001-LOGIN-AUTH | FP-TM001-01 | 001、002 | 隔离用户表、哈希认证合同 | 按用户名定位并校验密码哈希，未知/错误统一拒绝，停用拒绝；对应用例全部有真实记录 | LOGIN-VALIDATION |
| TASK-TM001-LOGIN-SESSION | FP-TM001-01 | 001、002 | 有效认证与账号初态 | 首次进入强制改密；正常进入正确身份/角色；服务故障不冒充成功；对应用例全部有真实记录 | LOGIN-AUTH |
| TASK-TM001-LOGIN-RATE | FP-TM001-01 | 002 | 5分钟5次失败、账号或来源限流 | 实现5分钟内连续5次失败后限制账号或来源，窗口结束恢复；对应用例全部有真实记录 | LOGIN-AUTH |
| TASK-TM001-CHANGE-PASSWORD | FP-TM001-02 | 001、003 | 当前/新密码、确认输入和会话 | 验证长度/不同密码/确认；原子改密并撤销旧会话；对应用例全部有真实记录 | LOGIN-SESSION |
| TASK-TM001-SESSION-PERSIST | FP-TM001-03 | 001 | 自动登录选项和合成token | 0700/0600同UID凭据存储、拒绝symlink和失败回滚；对应用例全部有真实记录 | LOGIN-SESSION |
| TASK-TM001-SESSION-RESTORE | FP-TM001-03 | 001 | 已存token与真实服务 | 恢复前调用/me；失效/离线显示正确状态而非缓存成功；对应用例全部有真实记录 | SESSION-PERSIST |
| TASK-TM001-SESSION-MEMORY | FP-TM001-03 | 001 | 关闭自动登录的选项 | 仅内存会话、不读取旧文件、重启回登录；对应用例全部有真实记录 | SESSION-PERSIST |
| TASK-TM001-SESSION-EXPIRY | FP-TM001-03 | 001 | 固定参考时间、30天会话 | 到期拒绝、不滑动续期，边界可验证；对应用例全部有真实记录 | SESSION-RESTORE |
| TASK-TM001-SESSION-LOGOUT | FP-TM001-03 | 001 | 有效会话、在线及离线状态 | 先清本地再撤销服务token；离线待撤销明确显示；对应用例全部有真实记录 | SESSION-RESTORE |
| TASK-TM001-ADMIN-RESET | FP-TM001-04 | 003 | 管理员身份、目标账号、新临时密码 | 重置密码/强制改密并撤销该账号所有会话；对应用例全部有真实记录 | CHANGE-PASSWORD |
| TASK-TM001-ADMIN-STATUS | FP-TM001-04 | 003 | 管理员、活动或停用账号 | 停用即时撤销会话；启用恢复可登录性；对应用例全部有真实记录 | ADMIN-RESET |
| TASK-TM001-ADMIN-GUARD | FP-TM001-04 | 002、003 | 成员/管理员/最后活动管理员 | 成员管理接口拒绝；自停用/最后管理员保护及并发不破坏约束；对应用例全部有真实记录 | ADMIN-STATUS |
| TASK-TM001-ADMIN-AUDIT | FP-TM001-04 | 003 | 管理操作及actor/target | 审计记录动作、操作者/目标、时间，不含密码/token；对应用例全部有真实记录 | ADMIN-RESET、ADMIN-STATUS |
| TASK-TM001-BOOTSTRAP-INIT | FP-TM001-05 | 005 | 全新隔离生产副本 | 只建admin/123456且强制改密，不混入回归用户；对应用例全部有真实记录 | DATA |
| TASK-TM001-BOOTSTRAP-PRESERVE | FP-TM001-05 | 005 | 已改密/已存在隔离库 | 再次初始化或服务重启不覆盖账号与密码；对应用例全部有真实记录 | BOOTSTRAP-INIT |
| TASK-TM001-BOOTSTRAP-RESTORE | FP-TM001-05 | 005 | 已知隔离备份和空恢复目标 | 恢复后schema/行一致且真实App能用恢复库；对应用例全部有真实记录 | BOOTSTRAP-PRESERVE |
| TASK-TM001-CONFIG-API | FP-TM001-06 | 006 | 默认/自定义API origin | 真实设置UI保存、重启保留、凭据按规范origin隔离；对应用例全部有真实记录 | LOGIN-SESSION |
| TASK-TM001-CONFIG-UPDATE | FP-TM001-06 | 006 | 默认/自定义version.json URL | 校验回环HTTP与HTTPS边界、原子保存、取消和恢复默认；对应用例全部有真实记录 | CONFIG-API |
| TASK-TM001-CONFIG-LOCKS | FP-TM001-06 | 006 | 登录/待退出/升级中状态 | 按状态锁定API、重置或更新源，避免半状态修改；对应用例全部有真实记录 | CONFIG-UPDATE |
| TASK-TM001-UPDATE-DISCOVER | FP-TM001-07 | 004 | 真实同机更新源与有效身份 | 自动/手动检查版本、当前版本与失败状态；对应用例全部有真实记录 | CONFIG-UPDATE |
| TASK-TM001-UPDATE-VERIFY | FP-TM001-07 | 004 | 合法/非法元数据及ZIP和信任锚 | URL/长度/SHA/Ed25519/App签名与版本核对；拒绝不交安装器；对应用例全部有真实记录 | UPDATE-DISCOVER |
| TASK-TM001-UPDATE-INSTALL | FP-TM001-07 | 004 | 已验证包及旧版私有安装 | 原生Squirrel安装并自主重启，版本/profile/真实身份恢复；对应用例全部有真实记录 | UPDATE-VERIFY、SESSION-RESTORE |
| TASK-TM001-UPDATE-ISOLATION | FP-TM001-07 | 004 | 进程/profile/ShipIt归属状态 | 拒绝未知资源，采集所有权并只清理本次资源；对应用例全部有真实记录 | UPDATE-INSTALL |
| TASK-TM001-UI-CONSISTENCY | FP-TM001-08 | 001–006 | HIG视觉设计、真实表单与系统状态 | 布局/主题/焦点/键盘和图标一致；保留实际截图与断言；对应用例全部有真实记录 | MAC |
| TASK-TM001-CASE-CATALOG | FP-TM001-09 | 001–006 | 任务、逐条TC、数据合同 | 建立root全量用例集合与双向引用，重复/漏项有检查；对应用例全部有真实记录 | PLAN |
| TASK-TM001-CASE-RECORDS | FP-TM001-09 | 001–006 | 已基线TC及真实runner | 每TC/变体、每步记录输入/预期/实测/证据；每次实际运行独立输出结果Excel，失败/阻塞也归档，总表仅汇总；不借旧PASS；对应用例全部有真实记录 | CASE-CATALOG、RUNNER |
| TASK-TM001-CASE-GATE | FP-TM001-09 | 001–006 | 逐条记录和候选清单 | 精确TC集合与逐步证据校验；漏例/缺记录必须阻断；对应用例全部有真实记录 | CASE-RECORDS |

## 任务到用例的完整列表

逐条映射由[本轮测试计划](04-test-plan.md)和[根目录用例集合](../../TEST_CASES.md)登记，详细输入、动作与独立预期在[登录/改密](../../docs/testing/cases/01a-TM-001-login-scenarios.md)和[会话/管理/配置/升级](../../docs/testing/cases/01b-TM-001-session-admin-release-scenarios.md)。技术辅助任务使用治理/视觉用例并明确层级，不能当作App端到端通过。

逐TC自动化与父门禁程序已接入，执行绑定状态和实际开发包证据见[测试计划](04-test-plan.md)及[实际结果](07-test-results.md)。任务仍须由干净最终候选的完整本机门禁验收；未决产品行为先修订需求，不能靠程序绑定状态宣称发布通过。
