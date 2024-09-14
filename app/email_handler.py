# app/email_handler.py

import imaplib
import email
from app.models import MailUser, Email
from app.database import db
from datetime import datetime

class EmailHandler:
    def sync_emails(self, agency_id):
        mail_users = MailUser.query.filter_by(agency_id=agency_id).all()
        for mail_user in mail_users:
            self._fetch_emails(mail_user)

    def _fetch_emails(self, mail_user):
        if mail_user.domain == "imap.gmail.com":
            imap_server = "imap.gmail.com"
        elif mail_user.domain == "imap-mail.outlook.com":
            imap_server = "imap-mail.outlook.com"
        elif mail_user.domain == "secureimap.t-online.de":
            imap_server = "secureimap.t-online.de"
        else:
            print(f"Unsupported email domain for user: {mail_user.email}")
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

                    subject = email_message['subject']
                    sender = email_message['from']
                    recipient = email_message['to']
                    date = datetime.strptime(email_message['date'], "%a, %d %b %Y %H:%M:%S %z")
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
            print(f"Error fetching emails for {mail_user.email}: {str(e)}")

    def _get_email_content(self, email_message):
        content = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    content += part.get_payload(decode=True).decode()
        else:
            content = email_message.get_payload(decode=True).decode()
        return content
