
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import logging

logger = logging.getLogger(__name__)

class Email:
    def __init__(self, to, subject, content):
        self.to = to if isinstance(to, list) else [to]
        self.subject = subject
        self.content = content

    def send(self):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.subject
        msg['From'] = "jaffar@hsbc.com"
        msg['To'] = ", ".join(self.to)
        html_part = MIMEText(self.content, 'html')
        msg.attach(html_part)
        try:
            with smtplib.SMTP('localhost') as server:
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
