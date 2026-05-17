# CEACStatusBot

[中文文档](README.Chinese.md)

Automatically check your U.S. visa application status on [CEAC](https://ceac.state.gov/CEACStatTracker/Status.aspx?App=NIV) and notify you **only when the status changes**. No spam, no personal data in notifications, no password stored in plain sight.

---

## How It Works

```
┌──────────────────────────────────────────────────────────┐
│                    GitHub Actions                         │
│                    (runs hourly)                          │
│                                                          │
│  1. Scrape CEAC → solve CAPTCHA with ONNX model          │
│                        │                                 │
│  2. Compare status vs. previous (status_record.json)     │
│           │                          │                   │
│      Changed                     Unchanged               │
│           │                          │                   │
│  3. Record transition           Do nothing               │
│     ↓                                                    │
│  4. Send email ──┬── SendGrid (REST API)                 │
│                  └── SMTP     (QQ / Gmail / ...)         │
│     ↓                                                    │
│  5. git commit & push status_record.json                 │
└──────────────────────────────────────────────────────────┘
```

1. **Query** — The bot requests the CEAC status page, downloads a CAPTCHA, and solves it with an ONNX deep-learning model. It submits your application details (injected from GitHub Secrets at runtime, never written to disk) and parses the result.

2. **State machine** — The status is compared against the last known state in `status_record.json`. If identical, the run exits silently: no email, no git commit.

3. **Classify Refused** — Since March 2020, CEAC uses `Refused` for both final denials and temporary 221(g) administrative-processing holds. The bot inspects the description text to split them into `Refused (AP)` and `Refused (Final)` — two distinct states.

4. **Notify** — If the status changed, an email is sent through whichever provider(s) you configured. The email contains the old→new transition, a full timeline of every past transition, and the CEAC description. **No passport number, application ID, or surname is included.**

5. **Persist** — The updated `status_record.json` is committed back to the repo so the next run has the correct baseline. The file contains only status names and timestamps — zero PII.

### Example email

```
Subject: [CEACStatusBot] Application Received -> Administrative Processing

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

## Quick Start (GitHub Actions)

### 1. Fork this repo

Fork [github.com/machsix/CEACStatusBot](https://github.com/machsix/CEACStatusBot).

### 2. Pick an email provider

You need at least one. You can enable both at the same time — they are independent.

| | SendGrid | SMTP (QQ Mail) |
|---|---|---|
| Best for | Gmail / international recipients | QQ Mail recipients (higher deliverability) |
| Setup time | ~5 min | ~2 min |
| Credential type | API key (token) | Authorization code (token) |
| Requires account | Yes (free tier) | No (your existing mailbox) |

**SendGrid setup:**

1. Sign up at [sendgrid.com](https://sendgrid.com) (free tier, 100 emails/day).
2. Go to **Settings → Sender Authentication → Verify a Single Sender** and verify your email.
3. Go to **Settings → API Keys → Create API Key**, choose "Restricted Access" with **Mail Send** only. Copy the key (starts with `SG.`).

**QQ Mail SMTP setup:**

1. Log in to QQ Mail. Go to **Settings → Account → POP3/SMTP Service** and turn on SMTP.
2. Generate an **authorization code** — this is a dedicated token, not your QQ password. Copy it.

### 3. Set up GitHub Secrets

Go to your fork: **Settings → Secrets and variables → Actions → New repository secret**.

**Required** (for querying CEAC):

| Secret | Description | Example |
|---|---|---|
| `LOCATION` | Embassy / consulate | `CHINA, BEIJING` |
| `NUMBER` | Application ID or Case Number | `AA0020AKAX` |
| `PASSPORT_NUMBER` | Passport number | `E12345678` |
| `SURNAME` | First 5 letters of surname | `SMITH` |

**At least one** of these email groups:

| Secret | For | Description |
|---|---|---|
| `FROM` | SendGrid | Verified sender email |
| `TO` | SendGrid | Recipient(s), `\|`-separated |
| `SENDGRID_API_KEY` | SendGrid | API key from step 2 |
| `SMTP_FROM` | SMTP | Sender email address |
| `SMTP_TO` | SMTP | Recipient(s), `\|`-separated |
| `SMTP_PASSWORD` | SMTP | Authorization code from step 2 |
| `SMTP_SERVER` | SMTP | Optional; auto-detected from domain |

**Optional:**

| Secret | Description | Example |
|---|---|---|
| `TIMEZONE` | Timezone (IANA) for active-hours | `Asia/Shanghai` |
| `ACTIVE_HOURS` | Notification window for Refused status | `08:00-22:00` |

Valid location codes: [LOCATION.md](LOCATION.md).

### 4. Enable Actions

Go to the **Actions** tab in your fork and enable workflows (disabled by default on forks).

### 5. Test it

Go to **Actions → run main.py → Run workflow** → **Run workflow**.

The first run transitions from `UNKNOWN` → `<your real status>`, so you'll get a notification. After that, only actual status changes will trigger email.

---

## Local Usage

```bash
git clone https://github.com/YOUR_USERNAME/CEACStatusBot.git
cd CEACStatusBot
cp .env.example .env
# edit .env with your real values
uv sync
uv run trigger.py
```

For periodic checking, add a cron job:

```bash
17 * * * * cd /path/to/CEACStatusBot && /path/to/uv run trigger.py
```

---

## Status Record

`status_record.json` is committed to the repo and contains **zero PII** — only status names and ISO-8601 timestamps.

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

### Notification rules

| Trigger | Action |
|---|---|
| Status changed | Record transition, send email |
| Status unchanged | Silent |
| Status → `Refused (AP)` or `Refused (Final)`, within active hours | Send email |
| Status → `Refused (AP)` or `Refused (Final)`, outside active hours | Record transition, suppress email |
| `case_last_updated` changed, status same | Silent |

### Short Refused vs. Long Refused

CEAC uses `Refused` for two very different outcomes. The bot tells them apart:

| | Long Refused | Short Refused |
|---|---|---|
| **CEAC display** | "Refused" + a long paragraph | "Refused" + 2–3 short lines |
| **Meaning** | 221(g) administrative processing; case is still alive | Final refusal (e.g. §214(b)) |
| **Recorded as** | `Refused (AP)` | `Refused (Final)` |
| **What to expect** | Usually resolves to `Issued` after weeks/months | Will not change; re-application needed |

These are tracked as two separate states. Whichever path your case is on, the bot notifies you once and then stays quiet.

---

## Troubleshooting

### "Query status failed"

CEAC could not be scraped after 5 retries. Possible causes:
- CEAC is temporarily down — try again later.
- Your `LOCATION` doesn't match the CEAC dropdown. Double-check against [LOCATION.md](LOCATION.md).

### No email received

- Check spam/trash first.
- **SendGrid**: Go to the SendGrid dashboard → **Activity → Search**. Look for "Delivered", "Bounced", or "Dropped" + a reason. Make sure your sender email is verified.
- **SMTP / QQ**: Check that SMTP is actually enabled and the authorization code is correct. QQ Mail's SMTP sometimes gets silently turned off after password changes.
- QQ Mail recipients: emails from overseas IPs (SendGrid) may land in spam. Mark them as "not spam" once to train the filter. SMTP from QQ itself usually avoids this.

### "No notification handles configured"

You didn't set up either SendGrid or SMTP secrets (or both are incomplete). At least one full set is required.

### Workflow not running

- Forks disable Actions by default. Go to the **Actions** tab and enable them.
- The cron schedule only fires on the **default branch** (`main`). Use `workflow_dispatch` on other branches.

### git push fails

The workflow needs `contents: write` (already configured). If you have branch protection requiring PR reviews on `main`, exempt `github-actions[bot]` or remove the protection.

### Is my data safe in a public repo?

Yes. Your passport number, application ID, and surname live **only** in GitHub Secrets (encrypted at rest). They are injected as environment variables at runtime and never written to any file. `status_record.json` contains only status strings and dates.

---

## Credits

- [h4x3rotab](https://github.com/h4x3rotab): Telegram bot, CEAC interface adaptation
- [Andision](https://github.com/Andision): Original project
- [ceac_tracker](https://github.com/lixin-wei/ceac_tracker) · [CEACStatTracker](https://github.com/yuzeming/CEACStatTracker)
