# 配置参考

[返回使用说明](../README.md)

## 账号来源及顺序

程序依次读取 JSON 数组、编号 1～20、旧版单账号变量。不同来源可以混用，同邮箱按大小写不敏感方式去重；密码必须一致，否则拒绝运行。

| 配置 | 必填性 | 说明 |
| --- | --- | --- |
| `ABLESCI_ACCOUNTS_JSON` | 可选 | 非空 JSON 数组，每项为对象；`email` 和 `password` 是非空字符串，`name` 是可选字符串 |
| `ABLESCI_N_EMAIL` | 与同编号密码成对 | `N` 为 1～20，邮箱首尾空白会清理 |
| `ABLESCI_N_PASSWORD` | 与同编号邮箱成对 | 密码保留首尾空格，清理 BOM 和首尾 CR/LF |
| `ABLESCI_N_NAME` | 可选 | 显示备注；不要包含敏感信息 |
| `ABLESCI_EMAIL` / `ABLESCI_PASSWORD` | 可选，成对 | 兼容旧版单账号配置 |

任何配置不完整、JSON 无效、冲突密码或总账号数超过 20，都会在访问网站前失败。邮箱仅做基本格式检查，不代表账号存在或密码正确。

GitHub workflow 默认注入编号 1～5 的邮箱与密码，以及 JSON 和旧版变量。第 6～20 个账号推荐放到 JSON 中；如果坚持使用编号式 Secrets，需要在 workflow 的 `jobs.signin.env` 中逐对增加引用，例如：

```yaml
ABLESCI_6_EMAIL: ${{ secrets.ABLESCI_6_EMAIL }}
ABLESCI_6_PASSWORD: ${{ secrets.ABLESCI_6_PASSWORD }}
```

编号式备注同样需要显式注入，直接添加 Secret 并不会自动进入运行环境：

```yaml
ABLESCI_1_NAME: ${{ secrets.ABLESCI_1_NAME }}
```

JSON 的 `name` 无需额外修改 workflow。

## 调度

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| workflow `schedule` | `0 0 * * *` | UTC，每天北京时间 08:00 触发 |
| Repository variable `ABLESCI_JITTER_MAX` | `1500` | GitHub 工作流最大随机等待秒数，允许 0～1500；设置 `0` 关闭 |
| 本地环境变量 `ABLESCI_JITTER_MAX` | `0` | 本地默认不等待，且只有 `GITHUB_EVENT_NAME=schedule` 才会实际等待 |
| `TZ` | workflow 设为 `Asia/Shanghai` | 日志和邮件主题使用运行环境本地时间 |

账号之间随机间隔 4～15 秒，单次 HTTP 请求超时参数为 25 秒。整个 job 最长运行 90 分钟，并发组保证手动与定时签到不会同时执行。实际开始时间由 GitHub 调度决定，随机等待只增加延迟，不保证准点或全天随机。

## 邮件

账号配置与邮件配置相互独立。不配置 `SMTP_HOST`、`SMTP_USER`、`SMTP_PASS` 时直接跳过；只配置部分项时会告警并跳过。

`SMTP_PORT` 省略为 465；非整数会告警并回退 465；其他整数端口会告警并停用本次通知。`MAIL_WHEN` 省略或无效时使用 `always`，希望只收失败邮件时应明确设为 `failure`。

`MAIL_TO` 支持英文逗号和分号分隔，省略时使用 `SMTP_USER`。SMTP 支持 465 上的 SSL 和 587 上的 STARTTLS，两者都会校验服务器证书。认证方式是 SMTP 用户名和密码，不支持 OAuth 专用登录流程。

## 命令与退出码

| 命令 | 行为 |
| --- | --- |
| `python ablesci_signin.py` | 校验配置 → 按需等待 → 逐账号签到 → 摘要与可选邮件 |
| `python ablesci_signin.py --check-config` | 离线校验账号、去重和延迟配置；不验证真实密码与 SMTP 可用性 |
| `python ablesci_signin.py --check` | 获取登录页并提取 CSRF；不需要账号，不登录 |
| `python -m ablesci --help` | 查看模块入口帮助 |

正常签到全部成功或已签到返回 0，任一失败或配置无效返回 1。自检成功返回 0，失败返回 1。命令行参数用错时由 argparse 返回 2。
