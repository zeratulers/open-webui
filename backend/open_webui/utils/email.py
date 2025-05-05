import smtplib
import ssl
from email.mime.text import MIMEText
import os
def send_verification_email(to_email, code):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    message = MIMEText(f"您正在注册Sera Web UI，你的验证码是 {code}，5分钟过期", "plain", "utf-8")
    message["Subject"] = "Sera Web UI 邮箱验证"
    message["From"] = smtp_user
    message["To"] = to_email

    context = ssl.create_default_context()

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, message.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, message.as_string())
