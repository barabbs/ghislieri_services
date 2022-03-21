from modules.base_service import BaseService
from . import var
from modules import utility as utl
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import logging

log = logging.getLogger(__name__)


def get_email_credentials():
    with open(var.CREDENTIALS_FILE, 'r') as cred_file:
        return cred_file.readline().split(",")


class EmailService(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def _request_send_email(self, metadata, text, attachments=None):
        # context = ssl.create_default_context()
        try:
            server = smtplib.SMTP(*var.SMTP_SERVER)
            server.starttls() # Secure the connection
            server.login(*get_email_credentials())

            message = MIMEMultipart()
            for k, v in metadata.items():
                message[k] = v

            message.attach(MIMEText(text, "plain"))

            if attachments is not None:
                for filepath in attachments:
                    with open(filepath, "rb") as attachment:
                        p = MIMEApplication(attachment.read(), _subtype=filepath.split('.')[-1])
                        p.add_header('Content-Disposition', "attachment; filename={name}".format(name=filepath.split('\\')[-1]))
                        message.attach(p)

            server.sendmail(metadata["From"], metadata["To"], message.as_string())
            log.info(f"Email to {message['To']} sent!")
        except Exception as err:
            log.error(f"Exception while sending email: {err}")
            utl.log_error(err)
        finally:
            server.quit()
