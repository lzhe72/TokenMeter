# 本地安装与服务说明

适用：v0.1.0-20260929T074814Z。Electron本地内部发行，当前macOS15 Intel；现有DMG仅为开发包，本页是正式安装预案，不代表版本已获发布资格。实际结果见[状态页](../status.md)及[设计](../architecture/01-electron-local.md)。

## 安装包位置

当前可见的开发包位于仓库根`dmg/v0.1.0-20260929T074814Z/`，文件名含`DEVELOPMENT-NOT-RELEASED`，不能作为正式版本分发。门禁PASS后，最终DMG原名放在该版本目录，`release-archive/`保存摘要、原始证据与通行证。GitHub只存源码文档，不提供Release安装包。测试用101高版单独标记，用户稳定版为0.1.0/build100。

打开DMG后安装TokenMeter.app；旧App正在使用时先退出并保留备份，再替换。Codex测试不会自动覆盖用户已有App。内部自签包不代表Apple公证，如系统阻止按macOS正常允许打开流程处理；不关闭系统保护。

## 服务与账号

App内置API为`http://127.0.0.1:49176`，更新清单为`http://127.0.0.1:49177/version.json`，均指运行App的此电脑。配置管理可修改并持久保存；非回环必须HTTPS。服务端继续使用FastAPI和SQLite，具体初始化/运行命令以已交付程序的--help和本机发行README为准。不得接管不属于本次运行的端口进程。

用户数据库为`database/production/production.db`，首次新建只预置`admin / 123456`并强制改密；已有库不覆盖密码或成员。Codex回归库为`database/test/test.db`和私有临时副本，造数SQL只导入测试库。服务升级前备份并验证恢复。

登录页默认在此设备自动登录，保存token、不保存密码；重启经真实服务验证，关闭选项后只保留内存。配置更新源不更换固定签名公钥。更新失败保留旧版；正式更新必须来自通过本机门禁的本地稳定包，不使用受控101测试包。

完整Xcode不是安装、运行或Electron E2E前提；其他系统/arm64未经实测不承诺兼容。
