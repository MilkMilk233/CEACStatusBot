import requests

from .handle import NotificationHandle


class EmailNotificationHandle(NotificationHandle):
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
        body = self._build_body(notification)

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
                print(f"Email sent to {recipient}")
            else:
                print(f"Failed to send email to {recipient}: {resp.status_code} {resp.text}")

    def _build_body(self, notification: dict) -> str:
        lines = [
            "Visa status has changed.\n",
            f"Previous status: {notification['from_status']}",
            f"Current status:  {notification['to_status']}",
            f"Last updated:    {notification['case_last_updated']}",
            f"Case created:    {notification['case_created']}",
        ]

        if notification["history"]:
            lines.append("\n--- Status Timeline ---")
            for entry in notification["history"]:
                lines.append(f"  {entry['from']} -> {entry['to']}  ({entry['at']})")

        lines.append(f"\n--- Details ---")
        lines.append(f"Visa type:    {notification['visa_type']}")
        lines.append(f"Description:  {notification['description']}")

        return "\n".join(lines)
