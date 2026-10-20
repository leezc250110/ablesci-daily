# AbleSci 每日签到

通过 GitHub Actions 为 [AbleSci 科研通](https://www.ablesci.com) 账号定时签到，支持最多 **20 个账号**、结果汇总和可选邮件通知，无需服务器。

[配置账号](https://github.com/leezc250110/ablesci-daily/settings/secrets/actions) · [查看运行结果](https://github.com/leezc250110/ablesci-daily/actions/workflows/ablesci-signin.yaml) · [详细配置](docs/configuration.md) · [故障排查](docs/troubleshooting.md)

## 快速开始

### 1. 准备你自己的仓库

如果你就是本仓库的所有者，直接进入下一步。其他使用者先 Fork 到自己的 GitHub 账号，在自己的仓库中操作。下文快捷链接指向 `leezc250110/ablesci-daily`；Fork 后请切换到自己的仓库。

在仓库顶部打开 **Settings → Secrets and variables → Actions → Secrets**。如果没有 Settings，确认当前登录的账号有仓库管理员权限。

### 2. 添加签到账号

点击 **New repository secret**，分别添加：

| Name | Secret 值 |
| --- | --- |
| `ABLESCI_1_EMAIL` | AbleSci 登录邮箱 |
| `ABLESCI_1_PASSWORD` | AbleSci 登录密码 |

Secret 名称必须完全一致，值不要附带引号或多余换行。密码填在 GitHub Secrets 中，不要写进代码、Issue 或公开日志。保存后的 Secret 无法查看，只能更新。

前 **5 个账号**可以直接按编号增加 `ABLESCI_2_EMAIL` / `ABLESCI_2_PASSWORD` 等，无需修改代码。更多账号建议使用下面的 JSON 配置。

### 3. 手动验证一次

打开 **Actions → AbleSci 每日签到 → Run workflow**，选择默认分支 `master`，再点击绿色按钮。

如果 Fork 后提示工作流未启用，先点击启用工作流的按钮。进入本次运行，在 **Summary** 查看账号、状态、说明、积分和连续签到天数。

| 状态 | 含义 |
| --- | --- |
| ✅ 签到成功 | 本次完成签到 |
| ℹ️ 今日已签到 | 今天已完成，属于成功 |
| ❌ 失败 | 网站拒绝登录或签到，检查账号配置 |
| 🤖 被要求验证码 | 先用浏览器完成验证，再手动重跑 |
| ⚠️ 异常 | 网络或网站响应异常，查看步骤日志 |

任一账号失败，任务退出码为 `1`；全部签到成功或今日已签到，退出码为 `0`。配置缺失或不完整也会明确失败，不会悄悄跳过。

### 4. 等待每天自动运行

默认每天 **北京时间 08:00** 触发。GitHub 调度可能延迟；工作流另外保留 **0～25 分钟随机等待**，手动运行不等待。账号之间间隔 4～15 秒。

如需关闭额外等待，在 **Settings → Secrets and variables → Actions → Variables** 新建 Repository variable：`ABLESCI_JITTER_MAX`，值填 `0`。可设置范围为 `0`～`1500` 秒。等待会占用 runner 运行时间。

定时任务从默认分支运行。公开仓库连续 60 天无活动时，GitHub 可能停用定时工作流；需要到 Actions 重新启用。调度规则见 [GitHub 官方说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 多账号：一个 Secret 管理

新建名为 **`ABLESCI_ACCOUNTS_JSON`** 的 Repository secret，值为 JSON 数组：

```json
[
  {"name": "账号一", "email": "one@example.com", "password": "替换为真实密码"},
  {"name": "账号二", "email": "two@example.com", "password": "替换为真实密码"}
]
```

`name` 可省略。数组内添加账号即可，最多 20 个，不需要修改 workflow。JSON 使用双引号；密码中如果含双引号或反斜杠，需要按 JSON 规则转义，例如 `\"` 和 `\\`。

JSON 与现有编号式 Secrets 可以共存；同邮箱、同密码合并，同邮箱、不同密码会报错。改用 JSON 后建议删除已替代的编号式 Secrets，避免以后只更新其中一处。[完整规则与配置表](docs/configuration.md)

## 可选：邮件通知

不配置邮件也能签到。需要邮件时，在同一 Secrets 页面添加：

| Secret | 示例 / 作用 |
| --- | --- |
| `SMTP_HOST` | QQ 邮箱填 `smtp.qq.com` |
| `SMTP_PORT` | `465`（SSL，默认）或 `587`（STARTTLS） |
| `SMTP_USER` | 发件邮箱，例如 `your-account@qq.com` |
| `SMTP_PASS` | 邮箱服务商提供的 SMTP 授权码或应用专用密码 |
| `MAIL_TO` | 收件邮箱；多个用英文逗号分隔；省略则发给自己 |
| `MAIL_WHEN` | `failure` 只在账号签到失败时发送；`always` 每次发送（默认）；`never` 关闭 |

QQ 邮箱需先在邮箱设置中开启 SMTP 并获取授权码，`SMTP_PASS` 不填邮箱登录密码。其他服务商需要支持用户名和密码方式的 SMTP 认证。

邮件提供纯文本与 HTML 表格。SMTP 配置或发送失败会输出警告，不改变签到任务的退出码。账号配置检查失败发生在签到前，不会发送这封签到结果邮件。只支持 465 / 587，连接会验证服务器证书。

## 本地运行与检查

需要 **Python 3.10+**，在项目根目录执行：

```sh
python -m pip install -r requirements.txt

# 联网检查登录页与 CSRF，不需要账号，不登录
python ablesci_signin.py --check

# 离线检查账号和随机等待配置，不签到、不发邮件
python ablesci_signin.py --check-config
```

实际签到前，需先在当前终端配置环境变量，例如 Windows PowerShell：

```powershell
$env:ABLESCI_1_EMAIL = 'one@example.com'
$securePassword = Read-Host 'AbleSci 密码' -AsSecureString
$env:ABLESCI_1_PASSWORD = [System.Net.NetworkCredential]::new('', $securePassword).Password
python ablesci_signin.py --check-config
python ablesci_signin.py
Remove-Item Env:ABLESCI_1_PASSWORD
```

`python -m ablesci` 是等效入口。项目不会自动读取 `.env` 文件；环境变量由终端或 GitHub Actions 注入。不要在共享终端中留下凭据。

## 从旧版升级 / 仓库迁移后

- 继续使用原来的 `ABLESCI_1_*`～`ABLESCI_5_*` 或 `ABLESCI_EMAIL` / `ABLESCI_PASSWORD`，无需重填。
- 原命令 `python ablesci_signin.py` 和原定时触发时刻保留。
- 以前填写了一半的账号会被跳过；现在会让配置检查失败，请补全或删除该账号的两个 Secret。
- `ABLESCI_JITTER_MAX` 现在通过 Repository variable 配置，范围 0～1500 秒。
- 转移仓库后，请在新仓库确认 Secrets、Actions 启用状态，并手动运行一次。更新 README、收藏和本地 Git 远程地址里的旧账号链接。

## 开发与维护

```text
ablesci_signin.py             兼容的启动入口
ablesci/
  config.py                  环境变量、JSON、校验和去重
  models.py                  账号与结果模型
  client.py                  HTTP 会话、CSRF 和站点响应解析
  runner.py                  单账号流程与有限重试
  reports.py                 控制台、Actions 摘要和邮件正文
  notifications.py           SMTP 通知
  cli.py                     命令行及多账号调度
.github/workflows/
  ablesci-signin.yaml         每日签到
  ci.yaml                    Python 3.10 / 3.12 / 3.14 离线测试
tests/                       配置、网络分支、报告和通知回归测试
```

```sh
python -m unittest discover -s tests -v
```

测试使用模拟网络与 SMTP，不需要真实密码，也不会签到或发送邮件。每次登录尝试新建会话并抓取 CSRF，登录网络失败最多尝试两次；密码错误、验证码、响应结构异常不自动重试。签到请求发生网络错误时，可能已在网站生效，本次报告异常，下一次运行再确认。[排查与维护说明](docs/troubleshooting.md)

日志会打码显示账号邮箱，网站消息会过滤当前账号的邮箱和密码；不会输出完整响应正文或 CSRF token。公开仓库的代码和运行日志可被他人查看，账号备注也会显示，请只使用不敏感的备注。请使用你有权管理的账号，并遵守网站规则；网站接口、验证码和调度环境发生变化时，需要相应维护，项目无法保证永久可用。
