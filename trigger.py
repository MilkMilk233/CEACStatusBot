import json
import os
import subprocess

from dotenv import load_dotenv

from CEACStatusBot import NotificationManager, SendgridNotificationHandle, SmtpNotificationHandle

if os.path.exists(".env"):
    load_dotenv(dotenv_path=".env")
else:
    print(".env not found, using system environment only")


def download_artifact():
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts"],
            capture_output=True,
            text=True,
        )
        artifacts = json.loads(result.stdout)
        artifact_exists = any(artifact["name"] == "status-artifact" for artifact in artifacts["artifacts"])

        if artifact_exists:
            subprocess.run(["gh", "run", "download", "--name", "status-artifact"], check=True)
        else:
            with open("status_record.json", "w") as file:
                json.dump({"current": "UNKNOWN", "history": []}, file)
    except Exception as e:
        print(f"Error downloading artifact: {e}")


if not os.path.exists("status_record.json"):
    download_artifact()

try:
    LOCATION = os.environ["LOCATION"]
    NUMBER = os.environ["NUMBER"]
    PASSPORT_NUMBER = os.environ["PASSPORT_NUMBER"]
    SURNAME = os.environ["SURNAME"]
    notificationManager = NotificationManager(LOCATION, NUMBER, PASSPORT_NUMBER, SURNAME)
except KeyError as e:
    raise RuntimeError(f"Missing required env var: {e}") from e

# --- SendGrid ---
FROM = os.getenv("FROM")
TO = os.getenv("TO")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

if FROM and TO and SENDGRID_API_KEY:
    notificationManager.addHandle(SendgridNotificationHandle(FROM, TO, SENDGRID_API_KEY))
else:
    print("SendGrid config missing or incomplete — skipped.")

# --- SMTP (e.g. QQ mail) ---
SMTP_FROM = os.getenv("SMTP_FROM")
SMTP_TO = os.getenv("SMTP_TO")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "")

if SMTP_FROM and SMTP_TO and SMTP_PASSWORD:
    notificationManager.addHandle(SmtpNotificationHandle(SMTP_FROM, SMTP_TO, SMTP_PASSWORD, SMTP_SERVER))
else:
    print("SMTP config missing or incomplete — skipped.")

if not notificationManager.hasHandles():
    raise RuntimeError("No notification handles configured. Set up SendGrid or SMTP.")

notificationManager.send()
