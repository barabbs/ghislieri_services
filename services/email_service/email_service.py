from modules.base_service import BaseService
from modules.service_pipe import Request
from . import var
from modules import utility as utl
import smtplib, imaplib, email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import decode_header
from email import utils

import logging, os

# ---- DEPRECATED - Dropped OAuth2 support ----
# import base64
# from google.auth.transport.requests import Request as GRequest
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# ---------------------------------------------

log = logging.getLogger(__name__)


def get_email_credentials():
    with open(var.CREDENTIALS_FILE, 'r') as cred_file:
        return cred_file.readline().split(",")


def _create_message(sender, receivers, subject, text, attachments=None):
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
    return message


class EmailService(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(EmailService, self).__init__(*args, **kwargs)
        self.credentials = get_email_credentials()

    def _send_email(self, sender, receivers, **kwargs):
        message = _create_message(sender, receivers, **kwargs)
        try:
            smtp_server = smtplib.SMTP_SSL(host=var.SMTP_HOST)
            smtp_server.login(*self.credentials)
            smtp_server.sendmail(sender, receivers, message.as_string())
            log.info(f"Email to {message['To']} sent!")
        except Exception as err:
            log.error(f"Exception while sending email: {err}")
            utl.log_error(err)
        finally:
            try:
                smtp_server.quit()
            except UnboundLocalError:
                pass

    def _download_attachments(self, mailbox):
        files = list()
        try:
            imap_server = imaplib.IMAP4_SSL(host=var.IMAP_HOST)
            imap_server.login(*self.credentials)
            imap_server.select(mailbox)

            res, msg_numbers = imap_server.search(None, '(UNSEEN)')
            for message_number in msg_numbers[0].split()[::-1]:
                res, data = imap_server.fetch(message_number, '(RFC822)')
                email_message = email.message_from_bytes(data[0][1])
                metadata = {"date": utl.get_str_from_time(utils.parsedate_to_datetime(email_message['date']))}
                for part in email_message.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    file_name = part.get_filename()
                    if bool(file_name):
                        if decode_header(file_name)[0][1] is not None:
                            file_name = decode_header(file_name)[0][0].decode(decode_header(file_name)[0][1])
                        file_metadata = metadata.copy()
                        filepath = utl.get_unused_filepath(os.path.join(var.ATTACHMENT_DIR, file_name))
                        file_metadata["filepath"] = filepath
                        with open(filepath, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        files.append(file_metadata)
        except Exception as err:
            log.error(f"Exception while downloading attachments: {err}")
            utl.log_error(err)
        finally:
            try:
                imap_server.close()
                imap_server.logout()
            except UnboundLocalError:
                pass
        return files

    # Requests

    def _request_send_email(self, sender, receivers=None, groups=None, **kwargs):
        if groups is not None:
            receivers = sum((list(filter(lambda x: x is not None, (c['student_infos']['email'] for c in self.send_request(Request("student_databaser", "get_chats", group=g))))) for g in groups),
                            start=list() if receivers is None else list(receivers))
        self._send_email(sender, receivers, **kwargs)

    def _request_download_attachments(self, mailbox="INBOX"):
        return self._download_attachments(mailbox)


# ---- DEPRECATED - Dropped OAuth2 support ----
# class EmailServiceOAuth2(BaseService):
#     SERVICE_NAME = var.SERVICE_NAME
#
#     def __init__(self, *args, **kwargs):
#         super(EmailServiceOAuth2, self).__init__(*args, **kwargs)
#         self.credentials, self.service = None, None
#
#     def _update_credentials(self):
#         if os.path.exists(var.GOOGLE_TOKEN_FILE):
#             self.credentials = Credentials.from_authorized_user_file(var.GOOGLE_TOKEN_FILE, var.GOOGLE_SCOPES)
#         else:
#             self.credentials = None
#
#         if self.credentials is None or not self.credentials.valid:
#             if self.credentials is not None and self.credentials.expired and self.credentials.refresh_token:
#                 log.info("Google credentials expired")
#                 self.credentials.refresh(GRequest())
#             else:
#                 log.warning("Log in required for google credentials!")
#                 self.send_request(Request('ghislieri_bot', 'add_notification', **var.GOOGLE_CREDENTIALS_NOTIFICATION_DATA.copy()))
#                 flow = InstalledAppFlow.from_client_secrets_file(var.GOOGLE_CREDENTIALS_FILE, var.GOOGLE_SCOPES)
#                 log.info(flow.authorization_url())
#                 # auth_url, _ = flow.authorization_url()  # TODO: Pass authorization link to telegram notification ????
#                 self.credentials = flow.run_local_server(port=0)
#             with open(var.GOOGLE_TOKEN_FILE, 'w') as token:
#                 token.write(self.credentials.to_json())
#         self.service = build('gmail', 'v1', credentials=self.credentials)
#
#     def _send_email(self, sender, receivers, **kwargs):
#         try:
#             message = _create_message(sender, receivers, **kwargs)
#             encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
#
#             create_message = {'raw': encoded_message}
#             send_message = (self.service.users().messages().send(userId="me", body=create_message).execute())
#             log.info(f"Email to {message['To']} with Id: {send_message['id']} sent!")
#         except Exception as err:
#             log.error(f"Exception while sending email: {err}")
#             utl.log_error(err)
#
#     def _download_attachments(self, msg_id):
#         files = list()
#         message = self.service.users().messages().get(userId='me', id=msg_id).execute()
#         for part in message['payload']['parts']:
#             if part['filename']:
#                 if 'data' in part['body']:
#                     data = part['body']['data']
#                 else:
#                     att_id = part['body']['attachmentId']
#                     att = self.service.users().messages().attachments().get(userId='me', messageId=msg_id, id=att_id).execute()
#                     data = att['data']
#                 file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
#
#                 files.append(utl.get_unused_filepath(os.path.join(var.ATTACHMENT_DIR, part['filename'])))
#
#                 with open(files[-1], 'wb') as f:
#                     f.write(file_data)
#         return files
#
#     # Requests
#
#     def _request_send_email(self, sender, receivers=None, groups=None, **kwargs):
#         if groups is not None:
#             receivers = sum((list(filter(lambda x: x is not None, (c['student_infos']['email'] for c in self.send_request(Request("student_databaser", "get_chats", group=g))))) for g in groups),
#                             start=list() if receivers is None else list(receivers))
#         self._update_credentials()
#         self._send_email(sender, receivers, **kwargs)
#
#     def _request_download_attachments(self, mailbox="INBOX"):
#         self._update_credentials()
#         files = list()
#         try:
#             msgs = self.service.users().messages().list(userId='me', q=f'in:{mailbox} is:unread').execute()
#
#             if "messages" in msgs:
#                 for m in msgs['messages']:  # TODO: Should check if 'nextPageToken' in msgs.keys() ????????
#                     files += self._download_attachments(m['id'])
#                     self.service.users().messages().modify(userId='me', id=m['id'], body={'removeLabelIds': ['UNREAD']}).execute()
#             else:
#                 log.info(f"No unread messages found in mailbox {mailbox}")
#         except Exception as err:
#             log.error(f"Exception while downloading attachments: {err}")
#             utl.log_error(err)
#         return files
# ---------------------------------------------

SERVICE_CLASS = EmailService
