import requests

from .handle import NotificationHandle
from .body import build_email_body


class SendgridNotificationHandle(NotificationHandle):
    def __init__(self, fromEmail: str, toEmail: str, apiKey: str) -> None:
        super().__init__()
        self.__fromEmail = fromEmail
        self.__toEmail = toEmail.split("|")
        self.__apiKey = apiKey
        self.__api_url = "https://api.sendgrid.com/v3/mail/send"

    def send(self, notification: dict) -> None:
        subject = "[CEACStatusBot] {} -> {}".format(
            notification["from_status"], notification["to_status"]
        )
        body = build_email_body(notification)

        for recipient in self.__toEmail:
            resp = requests.post(
                self.__api_url,
                headers={
                    "Authorization": f"Bearer {self.__apiKey}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": recipient}]}],
                    "from": {"email": self.__fromEmail},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
            )
            if resp.status_code in (200, 201, 202):
                print(f"SendGrid: email sent to ***@{recipient.split('@')[1]}")
            else:
                print(f"SendGrid: failed to send to ***@{recipient.split('@')[1]}: HTTP {resp.status_code}")
