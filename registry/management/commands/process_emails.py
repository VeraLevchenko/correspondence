# registry/management/commands/process_emails.py
import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
from registry.models import Incoming
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process unread emails from Gmail INBOX, create Incoming records, and mark emails as read'

    def decode_email_subject(self, subject):
        """Декодирование заголовка письма или имени отправителя."""
        decoded_subject = decode_header(subject)[0][0]
        if isinstance(decoded_subject, bytes):
            try:
                return decoded_subject.decode()
            except:
                return decoded_subject.decode('utf-8', errors='ignore')
        return decoded_subject or subject

    def decode_email_from(self, from_header):
        """Извлечение имени отправителя или email-адреса."""
        name, email_addr = parseaddr(from_header)
        if name:
            decoded_name = self.decode_email_subject(name)
            return decoded_name if decoded_name else email_addr
        return email_addr

    def handle(self, *args, **kwargs):
        """Обработка только непрочитанных писем из папки Входящие."""
        logger.info('Starting email processing for unread messages in INBOX...')
        self.stdout.write('Starting email processing for unread messages in INBOX...')

        # Подключение к Gmail через IMAP
        imap_server = imaplib.IMAP4_SSL('imap.gmail.com')
        try:
            imap_server.login(settings.GMAIL_EMAIL, settings.GMAIL_APP_PASSWORD)
            imap_server.select('INBOX')

            # Поиск только непрочитанных писем
            _, message_numbers = imap_server.search(None, 'UNSEEN')
            if not message_numbers[0]:
                logger.info('No unread emails found in INBOX.')
                self.stdout.write('No unread emails found in INBOX.')
                return

            for num in message_numbers[0].split():
                # Получение письма
                _, msg_data = imap_server.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                msg = email.message_from_bytes(email_body)

                # Извлечение данных
                from_header = msg.get('From', 'Unknown')
                from_email = self.decode_email_from(from_header)  # Декодированное имя или email
                subject = self.decode_email_subject(msg.get('Subject', 'No Subject'))
                date_str = msg.get('Date')
                try:
                    email_date = email.utils.parsedate_to_datetime(date_str)
                    incoming_date = email_date.date()
                except Exception as e:
                    logger.warning(f'Failed to parse email date: {e}')
                    incoming_date = datetime.now().date()

                response_deadline = incoming_date + timedelta(days=10)

                # Извлечение текста письма
                summary = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            try:
                                summary = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except Exception as e:
                                logger.warning(f'Failed to decode text/plain part: {e}')
                            break
                else:
                    try:
                        summary = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except Exception as e:
                        logger.warning(f'Failed to decode single-part payload: {e}')

                # Проверка дубликатов
                if not Incoming.objects.filter(summary=summary, incoming_date=incoming_date, applicant=from_email).exists():
                    incoming = Incoming(
                        incoming_date=incoming_date,
                        applicant=from_email,  # Сохраняем декодированное имя или email
                        summary=summary or subject,
                        responsible="Default Responsible",
                        response_deadline=response_deadline
                    )

                    # Обработка вложений
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_maintype() == 'multipart':
                                continue
                            if part.get('Content-Disposition') is None:
                                continue
                            filename = part.get_filename()
                            if filename:
                                try:
                                    decoded_filename = self.decode_email_subject(filename)
                                    file_data = part.get_payload(decode=True)
                                    incoming.attachment.save(decoded_filename, ContentFile(file_data), save=False)
                                except Exception as e:
                                    logger.error(f'Failed to process attachment {filename}: {e}')

                    # Сохранение записи
                    incoming.save()
                    logger.info(f'Created Incoming record for email from {from_email}')
                    self.stdout.write(self.style.SUCCESS(f'Created Incoming record for email from {from_email}'))

                    # Пометка письма как прочитанного
                    imap_server.store(num, '+FLAGS', '\\Seen')
                    logger.info(f'Marked email {num} as read.')
                    self.stdout.write(f'Marked email {num} as read.')

        except Exception as e:
            logger.error(f'Error processing emails: {e}')
            self.stdout.write(self.style.ERROR(f'Error processing emails: {e}'))
            raise

        finally:
            try:
                imap_server.logout()
            except:
                pass
            logger.info('Finished email processing.')
            self.stdout.write('Finished email processing.')