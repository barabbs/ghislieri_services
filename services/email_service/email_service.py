from modules.base_service import BaseService
from . import var
from modules import utility as utl
import smtplib, imaplib, email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import logging, os


log = logging.getLogger(__name__)


def get_email_credentials():
    with open(var.CREDENTIALS_FILE, 'r') as cred_file:
        return cred_file.readline().split(",")


class EmailService(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(EmailService, self).__init__(*args, **kwargs)
        self.credentials = get_email_credentials()

    def _send_email(self, sender, receivers, message):
        try:
            smtp_server = smtplib.SMTP_SSL(host=var.SMTP_HOST)
            smtp_server.login(*self.credentials)
            smtp_server.sendmail(sender, receivers, message.as_string())
            log.info(f"Email to {message['To']} sent!")
        except Exception as err:
            log.error(f"Exception while sending email: {err}")
            utl.log_error(err)
        finally:
            smtp_server.quit()

    def _request_send_email(self, sender, receivers, subject, text, attachments=None):
        message = MIMEMultipart()
        message["From"] = sender
        message["To"] = ",".join(receivers)
        message["Subject"] = subject
        message.attach(MIMEText(text, "plain"))
        if attachments is not None:
            for filepath in attachments:
                with open(filepath, "rb") as attachment:
                    p = MIMEApplication(attachment.read(), _subtype=filepath.split('.')[-1])
                    p.add_header('Content-Disposition', "attachment; filename={name}".format(name=filepath.split('/')[-1]))
                    message.attach(p)

        self._send_email(sender, receivers, message)

    def _request_download_attachments(self, mailbox="INBOX"):
        files = list()
        try:
            imap_server = imaplib.IMAP4_SSL(host=var.IMAP_HOST)
            imap_server.login(*self.credentials)
            imap_server.select(mailbox)

            res, msg_numbers = imap_server.search(None, '(UNSEEN)')
            for message_number in msg_numbers[0].split()[::-1]:
                res, data = imap_server.fetch(message_number, '(RFC822)')
                email_message = email.message_from_bytes(data[0][1])
                for part in email_message.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    file_name = part.get_filename()
                    if bool(file_name):
                        files.append(utl.get_unused_filepath(os.path.join(var.ATTACHMENT_DIR, file_name)))
                        with open(files[-1], 'wb') as f:
                            f.write(part.get_payload(decode=True))

        except Exception as err:
            log.error(f"Exception while sending email: {err}")
            utl.log_error(err)
        finally:
            imap_server.close()
            imap_server.logout()
        return files


SERVICE_CLASS = EmailService
