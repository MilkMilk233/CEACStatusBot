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
        subject = self._make_subject(notification)
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

    @staticmethod
    def _make_subject(notification: dict) -> str:
        if notification.get("is_status_change", True):
            return "[CEACStatusBot] {} -> {}".format(
                notification["from_status"], notification["to_status"]
            )
        return "[CEACStatusBot] {} — Case updated".format(
            notification["to_status"]
        )
