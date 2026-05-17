# CEACStatusBot

自动从 [CEAC](https://ceac.state.gov/CEACStatTracker/Status.aspx?App=NIV) 查询你的美国签证申请状态，**只在状态变化时**发送邮件通知。不轰炸，不泄露个人信息，不存明文密码。

---

## 工作原理

```
┌──────────────────────────────────────────────────────────┐
│                    GitHub Actions                         │
│                    (每小时执行)                            │
│                                                          │
│  1. 抓取 CEAC → ONNX 模型识别验证码                        │
│                        │                                 │
│  2. 对比上次状态 (status_record.json)                     │
│           │                          │                   │
│         变了                       没变                   │
│           │                          │                   │
│  3. 记录状态转移                  什么都不做               │
│     ↓                                                    │
│  4. 发送邮件 ──┬── SendGrid (REST API)                   │
│               └── SMTP     (QQ / Gmail / ...)            │
│     ↓                                                    │
│  5. git commit & push status_record.json                 │
└──────────────────────────────────────────────────────────┘
```

1. **查询** — 程序请求 CEAC 签证状态页面，下载验证码，用 ONNX 深度学习模型自动识别。然后用你的申请信息（运行时从 GitHub Secrets 注入，不写入文件）提交表单，解析返回结果。

2. **状态机判断** — 对比 `status_record.json` 中记录的上一次状态。如果完全一样，程序直接退出：不发邮件，不改文件。

3. **区分 Refused 类型** — 2020 年 3 月起，CEAC 把最终拒签和 221(g) 行政审查都显示为 `Refused`。Bot 通过分析描述文字自动区分为 `Refused (AP)`（行政审查）和 `Refused (Final)`（最终拒签），视为两个不同状态。

4. **发送通知** — 状态变化时，通过你配置的邮件方式发送。邮件内容只有旧→新状态转移 + 完整历史时间线 + CEAC 描述文字。**不包含护照号、申请号、姓氏。**

5. **持久化** — 更新后的 `status_record.json` 被提交回仓库，作为下次运行的基线。该文件仅含状态名称和时间戳，零个人数据。

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

### 第 1 步：Fork 仓库

Fork [github.com/machsix/CEACStatusBot](https://github.com/machsix/CEACStatusBot)。

### 第 2 步：选择邮件发送方式

至少需要配置一种。两种可以同时启用，互不影响。

| | SendGrid | SMTP（QQ 邮箱） |
|---|---|---|
| 适合 | Gmail / 境外收件人 | QQ 邮箱收件人（送达率高） |
| 配置耗时 | ~5 分钟 | ~2 分钟 |
| 凭证类型 | API key（token） | 授权码（token） |
| 需要注册 | 是（免费额度） | 否（用现有邮箱） |

**SendGrid 配置：**

1. 在 [sendgrid.com](https://sendgrid.com) 注册（免费额度，100 封/天）。
2. 进入 **Settings → Sender Authentication → Verify a Single Sender**，验证你的发件邮箱。
3. 进入 **Settings → API Keys → Create API Key**，选择 "Restricted Access" 并仅开启 **Mail Send**。复制 key（以 `SG.` 开头）。

**QQ 邮箱 SMTP 配置：**

1. 登录 QQ 邮箱。进入 **设置 → 账户 → POP3/SMTP 服务**，开启 SMTP。
2. 生成**授权码**——这是一个独立 token，不是你 QQ 密码。复制下来。

### 第 3 步：配置 GitHub Secrets

进入你 fork 的仓库：**Settings → Secrets and variables → Actions → New repository secret**。

**必填**（查询 CEAC 用）：

| Secret | 说明 | 示例 |
|---|---|---|
| `LOCATION` | 使领馆地点 | `CHINA, BEIJING` |
| `NUMBER` | Application ID 或 Case Number | `AA0020AKAX` |
| `PASSPORT_NUMBER` | 护照号码 | `E12345678` |
| `SURNAME` | 姓的前 5 个英文字母 | `SMITH` |

**至少选一组**邮件配置：

| Secret | 方式 | 说明 |
|---|---|---|
| `FROM` | SendGrid | 已验证的发件邮箱 |
| `TO` | SendGrid | 收件人，`\|` 分隔 |
| `SENDGRID_API_KEY` | SendGrid | 第 2 步创建的 API key |
| `SMTP_FROM` | SMTP | 发件邮箱 |
| `SMTP_TO` | SMTP | 收件人，`\|` 分隔 |
| `SMTP_PASSWORD` | SMTP | 第 2 步生成的授权码 |
| `SMTP_SERVER` | SMTP | 可选；不填则从邮箱域名自动推断 |

**可选**：

| Secret | 说明 | 示例 |
|---|---|---|
| `TIMEZONE` | IANA 时区格式，用于活跃时段判断 | `Asia/Shanghai` |
| `ACTIVE_HOURS` | Refused 状态的通知时间窗口 | `08:00-22:00` |

有效的地点代码见 [LOCATION.md](LOCATION.md)。**注意**：请先在 CEAC 网站手动确认能查到你的签证状态。

### 第 4 步：启用 Actions

进入你 fork 仓库的 **Actions** 标签页，启用 workflows（fork 仓库默认禁用）。

### 第 5 步：手动测试

进入 **Actions → run main.py → Run workflow** → **Run workflow**。

首次运行从 `UNKNOWN` → `<你的实际状态>`，所以一定会收到通知。之后只有状态真正变化时才会再收到邮件。

---

## 本地使用

```bash
git clone https://github.com/YOUR_USERNAME/CEACStatusBot.git
cd CEACStatusBot
cp .env.example .env
# 编辑 .env 填入你的真实信息
uv sync
uv run trigger.py
```

想定时运行，加 cron：

```bash
17 * * * * cd /path/to/CEACStatusBot && /path/to/uv run trigger.py
```

---

## 状态记录

`status_record.json` 存储在仓库中，**不含任何个人信息**，只有状态名称和 ISO-8601 时间戳。

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

| 触发条件 | 行为 |
|---|---|
| 状态变化 | 记录转移，发送邮件 |
| 状态不变 | 静默 |
| 状态变为 `Refused (AP)` 或 `Refused (Final)`，在活跃时间内 | 发送邮件 |
| 状态变为 `Refused (AP)` 或 `Refused (Final)`，不在活跃时间内 | 记录转移，不发送 |
| `case_last_updated` 变了但状态没变 | 静默 |

### 短 Refused 与长 Refused

CEAC 用一个 `Refused` 表示两种完全不同的情况。Bot 自动区分：

| | 长 Refused | 短 Refused |
|---|---|---|
| **CEAC 显示** | "Refused" + 一长段文字 | "Refused" + 2-3 行短文字 |
| **含义** | 221(g) 行政审查，案子还在处理 | 最终拒签（如 §214(b)） |
| **记录为** | `Refused (AP)` | `Refused (Final)` |
| **后续** | 通常数周/数月后变为 `Issued` | 不会自己变，需重新申请 |

两者在状态机中被视为不同状态。无论你的案子走哪条路径，Bot 都只会通知一次然后保持静默，直到状态再次变化。

---

## 常见问题

### "Query status failed"

抓取 CEAC 失败（重试 5 次后放弃）。可能原因：
- CEAC 网站暂时不可用（稍后重试）。
- `LOCATION` 值与 CEAC 下拉菜单不匹配。检查 [LOCATION.md](LOCATION.md)。

### 运行成功但没收到邮件

- 先检查垃圾邮件/垃圾箱。
- **SendGrid**：去 SendGrid 后台 → **Activity → Search**。查看邮件状态："Delivered"（已送达）、"Bounced"（退信）或 "Dropped"（丢弃），附原因。确认发件邮箱已验证。
- **SMTP / QQ**：确认 SMTP 服务已开启且授权码正确。QQ 邮箱的 SMTP 在改密码后有时会被静默关闭。
- QQ 邮箱收件：境外 IP 发的邮件（SendGrid）偶尔进垃圾箱，标记一次「这不是垃圾邮件」即可训练过滤规则。QQ 自己发出的 SMTP 邮件通常不会。

### "No notification handles configured"

SendGrid 和 SMTP 都没配，或配置不完整。至少需要完整配置一组。

### Workflow 不运行

- Fork 仓库的 Actions 默认禁用。进入 **Actions** 标签页启用。
- 定时任务仅在**默认分支**（`main`）上触发。在其他分支上使用 `workflow_dispatch` 手动触发。

### git push 失败

Workflow 需要 `contents: write` 权限（已在配置中）。如果你在 `main` 分支上设置了需要 PR review 的分支保护规则，请在规则中放行 `github-actions[bot]`，或移除分支保护。

### 我的仓库是 public 的，安全吗？

安全。你的护照号、申请号、姓氏**仅存储在 GitHub Secrets**（静态加密）中，运行时注入环境变量，从未写入任何文件。`status_record.json` 中只有签证状态名称和时间戳，不含任何个人信息。

---

## 致谢

- [h4x3rotab](https://github.com/h4x3rotab): Telegram bot，CEAC 接口适配
- [Andision](https://github.com/Andision): 原始项目
- [ceac_tracker](https://github.com/lixin-wei/ceac_tracker) · [CEACStatTracker](https://github.com/yuzeming/CEACStatTracker)
