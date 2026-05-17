from smtplib import SMTP_SSL
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from .handle import NotificationHandle
from .body import build_email_body


class SmtpNotificationHandle(NotificationHandle):
    def __init__(self, fromEmail: str, toEmail: str, password: str, host: str = "") -> None:
        super().__init__()
        self.__fromEmail = fromEmail
        self.__toEmail = toEmail.split("|")
        self.__password = password

        if ":" in host:
            addr, port = host.split(":")
            self.__host = addr
            self.__port = int(port)
        else:
            self.__host = host or f"smtp.{fromEmail.split('@')[1]}"
            self.__port = 0

    def send(self, notification: dict) -> None:
        subject = "[CEACStatusBot] {} -> {}".format(
            notification["from_status"], notification["to_status"]
        )
        body = build_email_body(notification)

        msg = MIMEMultipart()
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = self.__fromEmail
        msg["To"] = ";".join(self.__toEmail)
        msg.attach(MIMEText(body, "plain", "utf-8"))

        smtp = SMTP_SSL(self.__host, self.__port)
        smtp.login(self.__fromEmail, self.__password)
        smtp.sendmail(self.__fromEmail, self.__toEmail, msg.as_string())
        smtp.quit()
        print(f"SMTP: email sent to {self.__toEmail}")
