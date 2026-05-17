# CEACStatusBot

自动从 [CEAC](https://ceac.state.gov/CEACStatTracker/Status.aspx?App=NIV) 查询您的美国签证申请状态，**仅在状态变化时**才发送通知 — 不轰炸，不泄露个人信息。

## 目录

- [工作原理](#工作原理)
- [快速开始 (GitHub Actions)](#快速开始-github-actions)
- [本地使用](#本地使用)
- [环境变量](#环境变量)
- [邮件通知 (SendGrid)](#邮件通知-sendgrid)
- [状态记录与状态机](#状态记录与状态机)
- [常见问题](#常见问题)
- [致谢](#致谢)

---

## 工作原理

### 架构图

```
┌─────────────────────────────────────────────────┐
│                  GitHub Actions                  │
│  ┌──────────┐    ┌──────────┐    ┌───────────┐  │
│  │  定时任务 │───▶│  查询    │───▶│  状态机   │  │
│  │ (每小时)  │    │  CEAC    │    │           │  │
│  └──────────┘    └────┬─────┘    └─────┬─────┘  │
│                       │                │         │
│                 验证码识别       status 变了? │
│                (ONNX 模型)          │          │
│                                  ┌───┴──────┐   │
│                                  │ 是       │   │
│                                  ▼          │   │
│                           ┌──────────┐      │   │
│                           │ SendGrid │      │   │
│                           │   发邮件  │      │   │
│                           └──────────┘      │   │
│                                  │          │   │
│                           ┌──────▼──────┐   │   │
│                           │ git commit  │   │   │
│                           │ & push JSON │   │   │
│                           └─────────────┘   │   │
│                                  │          │   │
│                      ┌───────────▼──────┐   │   │
│                      │ 否 (状态不变)     │   │   │
│                      │  → 什么都不做    │   │   │
│                      └──────────────────┘   │   │
└─────────────────────────────────────────────────┘
```

### 执行流程

1. **定时触发** — GitHub Actions 每小时第 17 分钟执行一次。

2. **抓取 CEAC 页面** — 程序请求 CEAC 签证状态查询页面，下载验证码图片，使用 ONNX 深度学习模型自动识别验证码，然后提交您的申请信息（从 GitHub Secrets 中注入，不写入文件），解析返回结果：状态、最后更新日期、描述等。

3. **状态机判断** — 将本次查询到的状态与 `status_record.json` 中记录的上一次状态对比。如果状态字符串**完全相同**，程序直接退出。不发邮件，不改文件。

4. **发送通知** — 如果状态**发生变化**，通过 SendGrid API 发送邮件。邮件内容包含：
   - 状态转移：*"旧状态 → 新状态"*
   - 完整的状态转移时间线（所有历史记录）
   - CEAC 返回的描述文字和日期

   **邮件中不包含护照号、申请号、姓氏等任何个人信息。**

5. **持久化状态** — 更新后的 `status_record.json` 由 workflow 自动提交回仓库，作为下次运行的基线。

### 邮件示例

```
主题: [CEACStatusBot] Application Received -> Administrative Processing

Visa status has changed.

Previous status: Application Received
Current status:  Administrative Processing
Last updated:    28-May-2024
Case created:    15-May-2024

--- Status Timeline ---
  UNKNOWN -> Application Received  (2024-05-15T08:00:00)
  Application Received -> Administrative Processing  (2024-05-28T14:30:00)

--- Details ---
Visa type:    NONIMMIGRANT VISA APPLICATION
Description:  Your visa case is currently undergoing necessary administrative processing...
```

---

## 快速开始 (GitHub Actions)

### 第一步：Fork 仓库

点击 [github.com/machsix/CEACStatusBot](https://github.com/machsix/CEACStatusBot) 页面右上角的 **Fork** 按钮。

### 第二步：注册 SendGrid

详见下方 [邮件通知 (SendGrid)](#邮件通知-sendgrid) 章节。你需要准备：
- 一个已验证的发件邮箱
- 一个 API key

### 第三步：配置 GitHub Secrets

进入你 fork 的仓库：**Settings → Secrets and variables → Actions → New repository secret**。

逐一添加以下**必填** secrets：

| Secret | 说明 | 示例 |
|---|---|---|
| `LOCATION` | 使领馆地点 | `CHINA, BEIJING` |
| `NUMBER` | Application ID 或 Case Number | `AA0020AKAX` |
| `PASSPORT_NUMBER` | 护照号码 | `E12345678` |
| `SURNAME` | 姓的前 5 个英文字母 | `SMITH` |
| `FROM` | SendGrid 已验证的发件邮箱 | `noreply@example.com` |
| `TO` | 收件邮箱，多个用 `\|` 分隔 | `you@gmail.com\|you@qq.com` |
| `SENDGRID_API_KEY` | SendGrid API key | `SG.xxxxxxxx` |

**可选** secrets：

| Secret | 说明 | 示例 |
|---|---|---|
| `TIMEZONE` | IANA 时区格式 | `Asia/Shanghai` |
| `ACTIVE_HOURS` | 活跃时间段（仅对 Refused 状态生效） | `08:00-22:00` |

> 有效的地点代码请参见 [LOCATION.md](LOCATION.md)。请先在 CEAC 网站手动确认能查到你的签证状态。

### 第四步：启用 Actions

进入你 fork 仓库的 **Actions** 标签页，启用 workflows（fork 仓库默认禁用）。

### 第五步：手动触发测试

进入 **Actions → run main.py → Run workflow**，点击绿色 **Run workflow** 按钮。

首次运行的状态转移是 `UNKNOWN` → `<你的实际状态>`，因此你会收到一封通知邮件。之后，只有当状态实际变化时才会再次收到邮件。

---

## 本地使用

如果你想在本地机器上运行（不使用 GitHub Actions）：

### 前提条件

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)（`pip install uv`）

### 安装步骤

```bash
git clone https://github.com/YOUR_USERNAME/CEACStatusBot.git
cd CEACStatusBot

# 从模板创建 .env 文件
cp .env.example .env
# 编辑 .env 填入真实值
nano .env

# 安装依赖
uv sync

# 运行一次
uv run trigger.py
```

想定时运行？用 cron：

```bash
# crontab：每小时第 17 分钟执行一次
17 * * * * cd /path/to/CEACStatusBot && /path/to/uv run trigger.py
```

---

## 环境变量

### 必填

| 变量 | 说明 |
|---|---|
| `LOCATION` | 申请签证的使领馆。详见 [LOCATION.md](LOCATION.md)。 |
| `NUMBER` | CEAC 网站的 Application ID 或 Case Number。 |
| `PASSPORT_NUMBER` | 护照号码，需与 CEAC 表格中填写的一致。 |
| `SURNAME` | 姓的前 5 个英文字母，需与 CEAC 表格中填写的一致。 |

### 通知（发邮件必填）

| 变量 | 说明 |
|---|---|
| `FROM` | SendGrid 已验证的发件邮箱。 |
| `TO` | 收件邮箱。多个用 `\|` 分隔：`a@x.com\|b@x.com` |
| `SENDGRID_API_KEY` | SendGrid API key，需有 "Mail Send" 权限。 |

### 时间设置（可选）

| 变量 | 说明 |
|---|---|
| `TIMEZONE` | IANA 时区格式，如 `Asia/Shanghai`、`America/New_York`。用于判断是否在活跃时间段内。注意：北京时间应写 `Asia/Shanghai`，而非 ~~`Asia/Beijing`~~。 |
| `ACTIVE_HOURS` | 接收 "Refused" 状态通知的时间窗口，24 小时格式。示例：`08:00-22:00`。默认值：`00:00-23:59`（全天）。 |

---

## 邮件通知 (SendGrid)

### 为什么用 SendGrid？

- **免费**：100 封/天，远超实际需要。
- **Token 而非密码**：API key 只有发邮件的能力。即使泄露，你可以在 SendGrid 后台撤销并新建一个。它无法登录你的个人邮箱。
- **无个人数据**：邮件内容只有状态名称和日期。即使 SendGrid 的服务器被攻击，你的护照号和申请号也不在邮件中。

### 设置步骤（约 5 分钟）

1. 访问 [sendgrid.com](https://sendgrid.com)，点击 **Start for Free** 注册。
2. 验证邮箱：**Settings → Sender Authentication → Verify a Single Sender**。输入一个你拥有的邮箱地址，去收件箱点击验证链接。
3. 创建 API key：**Settings → API Keys → Create API Key**。选择 "Restricted Access"，仅开启 **Mail Send** 权限。复制 key（以 `SG.` 开头）。
4. 将以下信息添加到 GitHub Secrets（或本地 `.env` 文件）：
   - `FROM`：你在第 2 步验证的邮箱
   - `TO`：收件邮箱
   - `SENDGRID_API_KEY`：第 3 步创建的 key

### 多个收件人

用 `|` 分隔多个邮箱地址（不要加空格）：

```
you@gmail.com|you@qq.com|partner@outlook.com
```

每个收件人独立发送一封邮件。不使用 CC/BCC。

---

## 状态记录与状态机

### 文件格式

`status_record.json` 是 Bot 的「记忆」。它存储在仓库中，**不含任何个人信息** — 只有状态名称和 ISO-8601 时间戳。

```json
{
  "current": "Issued",
  "history": [
    {"from": "UNKNOWN", "to": "Application Received", "at": "2024-05-15T08:00:00"},
    {"from": "Application Received", "to": "Administrative Processing", "at": "2024-05-28T14:30:00"},
    {"from": "Administrative Processing", "to": "Issued", "at": "2024-06-15T10:00:00"}
  ]
}
```

### 通知规则

| 情况 | 行为 |
|---|---|
| 状态**变化**（如 `UNKNOWN` → `Application Received`） | 记录转移，发送邮件 |
| 状态**不变**（如 `Issued` → `Issued`） | **静默**——不发邮件，不改文件 |
| 状态变为 `Refused` 且在活跃时间 | 发送邮件 |
| 状态变为 `Refused` 且不在活跃时间 | 记录转移，**不发送**邮件 |

注意：`case_last_updated` 日期变化**不会**触发通知。只有 status 字符串本身的变化才触发。

### Refused 状态的活跃时间

签证被拒（Refused）的原因之一是行政审查（Administrative Processing 有时也会显示为 Refused）。如果你不希望半夜被通知吵醒，可以设置 `TIMEZONE` 和 `ACTIVE_HOURS`：

```
TIMEZONE=Asia/Shanghai
ACTIVE_HOURS=08:00-22:00
```

这样，凌晨 3 点的 Refused 通知不会发送，但仍会记录到 `status_record.json` 中。其他状态（如 Issued）不受此限制，随时发送。

---

## 常见问题

### "Query status failed, no notification sent"

程序在重试 5 次后仍未能从 CEAC 获取状态。可能原因：
- CEAC 网站暂时不可用（稍后重试即可）。
- `LOCATION` 值与 CEAC 下拉菜单中的选项不匹配。请检查 [LOCATION.md](LOCATION.md)，确保名称完全一致。

### "Email notification config missing or incomplete"

`FROM`、`TO` 或 `SENDGRID_API_KEY` 有缺失。如果使用 GitHub Actions，检查 repository secrets。如果本地运行，检查 `.env` 文件。

### 运行成功但没收到邮件

- 检查垃圾邮件/垃圾箱。
- 登录 SendGrid 后台，进入 **Activity → Search**。查找邮件状态——会显示 "Delivered"（已送达）、"Bounced"（退信）或 "Dropped"（丢弃），并附原因。
- 确认你的发件邮箱在 SendGrid 已验证（**Settings → Sender Authentication**）。
- QQ 邮箱用户：SendGrid 从境外 IP 发送的邮件偶尔会被 QQ 邮箱归入垃圾邮件。将发件人标记为「这不是垃圾邮件」来训练过滤规则。

### Workflow 不运行

- Fork 仓库的 Actions 默认禁用。进入 **Actions** 标签页，点击启用。
- 定时任务（`17 * * * *`）仅在**默认分支**（`main`）上触发。如果在其他分支上开发，请使用 `workflow_dispatch` 手动触发。

### Actions 中 git push 失败

Workflow 需要 `contents: write` 权限（已在 workflow 文件中配置）。如果你在 `main` 分支上设置了需要 PR review 的分支保护规则，`github-actions[bot]` 的推送会被阻止。解决方法：在分支保护规则中放行 `github-actions[bot]`，或移除分支保护。

### 我 fork 的仓库是 public 的，安全吗？

安全。你的个人信息（护照号、申请号、姓氏）仅存储在 GitHub **Secrets** 中，程序运行时注入内存，永远不会写入文件或提交到仓库。`status_record.json` 中只包含签证状态名称和时间戳，不含任何个人数据。

---

## 致谢

### 开发者

- [h4x3rotab](https://github.com/h4x3rotab): Telegram bot 集成，适配新版 CEAC 接口
- [Andision](https://github.com/Andision): 原始项目

### 相关项目

- [ceac_tracker](https://github.com/lixin-wei/ceac_tracker)
- [CEACStatTracker](https://github.com/yuzeming/CEACStatTracker)
