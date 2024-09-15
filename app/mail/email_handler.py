# app/email_handler.py

import imaplib
import email
from email.header import decode_header
from app.models import MailUser, Email
from app.database import db
from datetime import datetime
from flask import current_app
import logging

class EmailHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def sync_emails(self, agency_id):
        mail_users = MailUser.query.filter_by(agency_id=agency_id).all()
        for mail_user in mail_users:
            try:
                self._fetch_emails(mail_user)
            except Exception as e:
                self.logger.error(f"Error syncing emails for user {mail_user.id}: {str(e)}")

    def _fetch_emails(self, mail_user):
        imap_server = self._get_imap_server(mail_user.domain)
        if not imap_server:
            self.logger.error(f"Unsupported email domain for user: {mail_user.email}")
            return

        try:
            with imaplib.IMAP4_SSL(imap_server) as imap:
                imap.login(mail_user.email, mail_user.password)
                imap.select(mail_user.folder)
                _, message_numbers = imap.search(None, 'ALL')
                
                for num in message_numbers[0].split():
                    _, msg_data = imap.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)

                    subject = self._decode_header(email_message['subject'])
                    sender = self._decode_header(email_message['from'])
                    recipient = self._decode_header(email_message['to'])
                    date = self._parse_date(email_message['date'])
                    content = self._get_email_content(email_message)

                    existing_email = Email.query.filter_by(
                        subject=subject,
                        sender=sender,
                        recipient=recipient,
                        date=date,
                        mail_user_id=mail_user.id
                    ).first()

                    if not existing_email:
                        new_email = Email(
                            subject=subject,
                            sender=sender,
                            recipient=recipient,
                            date=date,
                            content=content,
                            mail_user_id=mail_user.id
                        )
                        db.session.add(new_email)

                db.session.commit()

        except Exception as e:
            self.logger.error(f"Error fetching emails for {mail_user.email}: {str(e)}")
            raise

    def _get_imap_server(self, domain):
        imap_servers = {
            "gmail.com": "imap.gmail.com",
            "outlook.com": "imap-mail.outlook.com",
            "t-online.de": "secureimap.t-online.de"
        }
        return imap_servers.get(domain)

    def _decode_header(self, header):
        decoded_header, encoding = decode_header(header)[0]
        if isinstance(decoded_header, bytes):
            return decoded_header.decode(encoding or 'utf-8')
        return decoded_header

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            self.logger.warning(f"Unable to parse date: {date_str}")
            return datetime.now()

    def _get_email_content(self, email_message):
        content = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        content += part.get_payload(decode=True).decode()
                    except Exception as e:
                        self.logger.error(f"Error decoding email content: {str(e)}")
        else:
            try:
                content = email_message.get_payload(decode=True).decode()
            except Exception as e:
                self.logger.error(f"Error decoding email content: {str(e)}")
        return content

    def check_email_connection(self, email, password, server):
        imap_server = self._get_imap_server(server)
        if not imap_server:
            return False, "Unsupported email server"

        try:
            with imaplib.IMAP4_SSL(imap_server) as imap:
                imap.login(email, password)
                return True, "Connection successful"
        except imaplib.IMAP4.error as e:
            self.logger.error(f"IMAP error for {email}: {str(e)}")
            return False, "Invalid email or password"
        except Exception as e:
            self.logger.error(f"Error checking email connection for {email}: {str(e)}")
            return False, "Unable to connect to email server"

    def get_email_attachments(self, mail_user_id, email_id):
        mail_user = MailUser.query.get(mail_user_id)
        if not mail_user:
            return None

        try:
            with imaplib.IMAP4_SSL(self._get_imap_server(mail_user.domain)) as imap:
                imap.login(mail_user.email, mail_user.password)
                imap.select(mail_user.folder)
                _, msg_data = imap.fetch(str(email_id), '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)

                attachments = []
                for part in email_message.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            'filename': filename,
                            'content': part.get_payload(decode=True)
                        })
                return attachments
        except Exception as e:
            self.logger.error(f"Error fetching email attachments for user {mail_user_id}, email {email_id}: {str(e)}")
            return None
