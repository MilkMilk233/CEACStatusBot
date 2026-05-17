# CEACStatusBot

[中文文档](README.Chinese.md)

Automatically check your U.S. visa application status on [CEAC](https://ceac.state.gov/CEACStatTracker/Status.aspx?App=NIV) and notify you **only when the status changes** — no spam, no personal data in transit.

## Table of Contents

- [How It Works](#how-it-works)
- [Quick Start (GitHub Actions)](#quick-start-github-actions)
- [Local Usage](#local-usage)
- [Environment Variables](#environment-variables)
- [Email Notifications (SendGrid)](#email-notifications-sendgrid)
- [Status Record & State Machine](#status-record--state-machine)
- [Troubleshooting](#troubleshooting)
- [Credits](#credits)

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────┐
│                  GitHub Actions                  │
│  ┌──────────┐    ┌──────────┐    ┌───────────┐  │
│  │  Cron    │───▶│  Query   │───▶│  State    │  │
│  │ (hourly) │    │  CEAC    │    │  Machine  │  │
│  └──────────┘    └────┬─────┘    └─────┬─────┘  │
│                       │                │         │
│                  Captcha OCR     Status changed? │
│                  (ONNX model)         │          │
│                                  ┌───┴──────┐   │
│                                  │ Yes      │   │
│                                  ▼          │   │
│                           ┌──────────┐      │   │
│                           │ SendGrid │      │   │
│                           │  Email   │      │   │
│                           └──────────┘      │   │
│                                  │          │   │
│                           ┌──────▼──────┐   │   │
│                           │ git commit  │   │   │
│                           │ & push JSON │   │   │
│                           └─────────────┘   │   │
│                                  │          │   │
│                      ┌───────────▼──────┐   │   │
│                      │  No (same state) │   │   │
│                      │  → Do nothing    │   │   │
│                      └──────────────────┘   │   │
└─────────────────────────────────────────────────┘
```

### Step by Step

1. **Cron trigger** — GitHub Actions fires once per hour (at minute 17 of each hour).

2. **Scrape CEAC** — The bot requests the CEAC status page, downloads a CAPTCHA image, and uses an ONNX deep-learning model to solve it automatically. It then submits your application details (from GitHub Secrets) and parses the result: status, last-updated date, description, etc.

3. **State machine** — The result is compared against the last known status stored in `status_record.json`. If the status string is **unchanged**, the run exits silently. No email, no git commit.

4. **Notification** — If the status **has changed**, an email is sent via SendGrid. The email contains:
   - The transition: *"Previous status → Current status"*
   - The full timeline of all past status transitions
   - CEAC description text and dates

   **No passport number, application ID, or surname is included in the email.**

5. **Persist state** — The updated `status_record.json` is committed back to the repository by the workflow, so the next run has the correct baseline.

### What the Email Looks Like

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

### 1. Fork this repository

Click the **Fork** button at [github.com/machsix/CEACStatusBot](https://github.com/machsix/CEACStatusBot).

### 2. Create a SendGrid account

See [Email Notifications (SendGrid)](#email-notifications-sendgrid) below. You'll need:
- A verified sender email
- An API key

### 3. Set up GitHub Secrets

Go to your fork: **Settings → Secrets and variables → Actions → New repository secret**.

Add these **required** secrets one by one:

| Secret | Description | Example |
|---|---|---|
| `LOCATION` | Embassy/consulate location | `CHINA, BEIJING` |
| `NUMBER` | Application ID or Case Number | `AA0020AKAX` |
| `PASSPORT_NUMBER` | Passport number | `E12345678` |
| `SURNAME` | First 5 letters of surname | `SMITH` |
| `FROM` | SendGrid verified sender email | `noreply@example.com` |
| `TO` | Recipient email(s), `\|`-separated | `you@gmail.com\|you@qq.com` |
| `SENDGRID_API_KEY` | SendGrid API key | `SG.xxxxxxxx` |

**Optional** secrets:

| Secret | Description | Example |
|---|---|---|
| `TIMEZONE` | Your timezone (IANA format) | `Asia/Shanghai` |
| `ACTIVE_HOURS` | Mute "Refused" notifications outside this window | `08:00-22:00` |

> You can find valid location codes in [LOCATION.md](LOCATION.md).

### 4. Enable Actions

Go to the **Actions** tab in your fork and enable workflows (they may be disabled by default on forks).

### 5. Trigger a test run

Go to **Actions → run main.py → Run workflow** and click the green **Run workflow** button.

The first run will be from `UNKNOWN` → `<your actual status>`, so you'll receive a notification email. After that, you'll only hear from the bot when your status actually changes.

---

## Local Usage

If you prefer running locally instead of GitHub Actions:

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/CEACStatusBot.git
cd CEACStatusBot

# Create .env from template
cp .env.example .env
# Edit .env with your real values
nano .env

# Install dependencies
uv sync

# Run once
uv run trigger.py
```

Run it manually whenever you want to check. Or set up a cron job:

```bash
# In crontab: run every hour at minute 17
17 * * * * cd /path/to/CEACStatusBot && /path/to/uv run trigger.py
```

---

## Environment Variables

### Required

| Variable | Description |
|---|---|
| `LOCATION` | Embassy/consulate where you applied. See [LOCATION.md](LOCATION.md). |
| `NUMBER` | Your CEAC Application ID or Case Number. |
| `PASSPORT_NUMBER` | Your passport number, exactly as entered on CEAC. |
| `SURNAME` | First 5 letters of your surname. Must match CEAC exactly. |

### Notification (Required for email)

| Variable | Description |
|---|---|
| `FROM` | SendGrid verified sender email address. |
| `TO` | Recipient(s). Use `\|` to separate multiple: `a@x.com\|b@x.com` |
| `SENDGRID_API_KEY` | SendGrid API key with "Mail Send" permission. |

### Timing (Optional)

| Variable | Description |
|---|---|
| `TIMEZONE` | IANA timezone string, e.g. `Asia/Shanghai`, `America/New_York`. Controls active-hours calculation for "Refused" gating. |
| `ACTIVE_HOURS` | Window during which "Refused" notifications are sent, 24h format. Example: `08:00-22:00`. Default: `00:00-23:59`. |

---

## Email Notifications (SendGrid)

### Why SendGrid?

- **Free tier**: 100 emails/day — far more than needed.
- **Token, not password**: The API key can only send email. If leaked, you revoke it and create a new one. It does not grant access to your personal email account.
- **No PII in transit**: Emails contain only status names and dates. Even if SendGrid's servers were compromised, your passport number and application ID are not in the emails.

### Setup (5 minutes)

1. Go to [sendgrid.com](https://sendgrid.com) and click **Start for Free**.
2. Verify your email: **Settings → Sender Authentication → Verify a Single Sender**. Enter an email address you own. Check your inbox and click the verification link.
3. Create an API key: **Settings → API Keys → Create API Key**. Choose "Restricted Access" and enable only **Mail Send**. Copy the key (it starts with `SG.`).
4. Add these to your GitHub Secrets (or `.env` file):
   - `FROM`: the email you verified in step 2
   - `TO`: your recipient email(s)
   - `SENDGRID_API_KEY`: the key from step 3

### Multiple Recipients

Separate email addresses with `|` (no spaces):

```
you@gmail.com|you@qq.com|partner@outlook.com
```

Each recipient receives a separate email. The bot does not use CC/BCC — each address gets its own individual send.

---

## Status Record & State Machine

### File Format

`status_record.json` is the bot's memory. It lives in the repository and contains **zero PII** — only status names and ISO-8601 timestamps.

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

### Notification Rules

| Condition | Action |
|---|---|
| Status **changed** (e.g. `UNKNOWN` → `Application Received`) | Record transition, send email |
| Status **unchanged** (e.g. `Issued` → `Issued`) | **Silent** — no email, no file change |
| Status → `Refused` during active hours | Send email |
| Status → `Refused` outside active hours | Record transition, **suppress** email |

The `case_last_updated` date changing does **not** trigger a notification by itself. Only the actual status string matters.

### Active Hours for "Refused"

If you get a "Refused" result (common for administrative processing cases), the bot can suppress that notification during sleeping hours. Set `TIMEZONE` and `ACTIVE_HOURS`:

```
TIMEZONE=Asia/Shanghai
ACTIVE_HOURS=08:00-22:00
```

With this config, a "Refused" result at 3 AM will be recorded in `status_record.json` but no email will be sent. Other status transitions (like "Issued") are always sent regardless of time.

---

## Troubleshooting

### "Query status failed, no notification sent"

The bot could not scrape CEAC after 5 retries. Possible causes:
- CEAC website is temporarily down (retry later).
- Your `LOCATION` value doesn't match any option on the CEAC dropdown. Check [LOCATION.md](LOCATION.md) and double-check that the name matches exactly.

### "Email notification config missing or incomplete"

One of `FROM`, `TO`, or `SENDGRID_API_KEY` is missing or empty. If running on GitHub Actions, check your repository secrets. If running locally, check your `.env` file.

### No email received, but the run succeeded

- Check your spam/trash folder.
- If using SendGrid, go to **Activity → Search** in the SendGrid dashboard. Look for the email — it will show "Delivered", "Bounced", or "Dropped" with a reason.
- Verify your sender email is verified in SendGrid (**Settings → Sender Authentication**).
- For QQ mail recipients: SendGrid emails from overseas IPs may occasionally land in spam. Mark them as "not spam" to train the filter.

### Workflow not running

- Forks have workflows **disabled by default**. Go to the **Actions** tab and click "I understand my workflows, go ahead and enable them".
- The cron schedule (`17 * * * *`) only triggers on the **default branch** (`main`). If you're working on another branch, use `workflow_dispatch` to trigger manually.

### git push fails in Actions

The workflow needs `contents: write` permission (already configured in the workflow file). If you've set up branch protection rules on `main` that require PR reviews, the `github-actions[bot]` user will be blocked. To fix: either exempt `github-actions[bot]` from the branch protection rule, or remove branch protection.

---

## Credits

### Contributors

- [h4x3rotab](https://github.com/h4x3rotab): Telegram bot integration, CEAC interface adaptation
- [Andision](https://github.com/Andision): Original project

### Related Projects

- [ceac_tracker](https://github.com/lixin-wei/ceac_tracker)
- [CEACStatTracker](https://github.com/yuzeming/CEACStatTracker)
