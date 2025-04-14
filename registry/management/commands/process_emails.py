# registry/management/commands/process_emails.py
import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
from registry.models import Incoming, Attachment
import logging
import g4f
import asyncio
import aiohttp

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

	async def async_summarize(self, prompt):
		"""Асинхронный вызов g4f с таймаутом для модели gpt-4o-mini."""
		try:
			# Проверка доступности модели
			model = g4f.models.gpt_4o_mini
			if not model.best_provider:
				logger.error("No provider available for model: gpt-4o-mini")
				return None

			async with aiohttp.ClientSession() as session:
				logger.info("Attempting to summarize with model: gpt-4o-mini")
				response = await asyncio.wait_for(
					g4f.ChatCompletion.create_async(
						model="gpt-4o-mini",
						messages=[{"role": "user", "content": prompt}],
						max_tokens=200,
						session=session
					),
					timeout=20.0  # Таймаут 20 секунд
				)
				# Обработка ответа
				if isinstance(response, str):
					logger.warning("g4f returned a string instead of an object.")
					return response.strip()
				elif hasattr(response, 'choices') and response.choices:
					return response.choices[0].message.content.strip()
				else:
					logger.warning("Invalid response format from g4f.")
					return None
		except asyncio.TimeoutError:
			logger.warning("g4f summarization timed out after 20 seconds.")
			return None
		except Exception as e:
			logger.error(f"Failed to summarize email with g4f: {e}")
			return None

	def summarize_email_content(self, text, subject):
		"""Получение краткого содержания с помощью g4f с таймаутом."""
		if not text:
			logger.warning("Empty email content, using subject as summary.")
			return subject[:200]

		prompt = f"Перескажи краткое содержание этого письма на русском языке в пределах 200 символов:\n\n{text[:10000]}"  # Ограничиваем текст до 10,000 символов
		# Запускаем асинхронный цикл для выполнения запроса
		loop = asyncio.new_event_loop()
		asyncio.set_event_loop(loop)
		try:
			summary = loop.run_until_complete(self.async_summarize(prompt))
			if summary:
				logger.info("Successfully generated summary with g4f.")
				return summary[:200]
			else:
				logger.warning("Empty summary returned by g4f.")
				return text[:200] or subject
		finally:
			loop.close()

	def handle(self, *args, **kwargs):
		"""Обработка только непрочитанных писем из папки Входящие."""
		logger.info('Starting email processing for unread messages in INBOX...')
		self.stdout.write('Starting email processing for unread messages in INBOX...')

		imap_server = imaplib.IMAP4_SSL('imap.gmail.com')
		try:
			imap_server.login(settings.GMAIL_EMAIL, settings.GMAIL_APP_PASSWORD)
			imap_server.select('INBOX')

			_, message_numbers = imap_server.search(None, 'UNSEEN')
			if not message_numbers[0]:
				logger.info('No unread emails found in INBOX.')
				self.stdout.write('No unread emails found in INBOX.')
				return

			for num in message_numbers[0].split():
				_, msg_data = imap_server.fetch(num, '(RFC822)')
				email_body = msg_data[0][1]
				msg = email.message_from_bytes(email_body)

				from_header = msg.get('From', 'Unknown')
				from_email = self.decode_email_from(from_header)
				subject = self.decode_email_subject(msg.get('Subject', 'No Subject'))
				date_str = msg.get('Date')
				try:
					email_date = email.utils.parsedate_to_datetime(date_str)
					incoming_date = email_date.date()
				except Exception as e:
					logger.warning(f'Failed to parse email date: {e}')
					incoming_date = datetime.now().date()

				response_deadline = incoming_date + timedelta(days=10)

				raw_summary = ""
				if msg.is_multipart():
					for part in msg.walk():
						if part.get_content_type() == 'text/plain':
							try:
								raw_summary = part.get_payload(decode=True).decode('utf-8', errors='ignore')
							except Exception as e:
								logger.warning(f'Failed to decode text/plain part: {e}')
							break
				else:
					try:
						raw_summary = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
					except Exception as e:
						logger.warning(f'Failed to decode single-part payload: {e}')

				summary = self.summarize_email_content(raw_summary, subject)

				if not Incoming.objects.filter(summary=summary, incoming_date=incoming_date,
											   applicant=from_email).exists():
					incoming = Incoming(
						incoming_date=incoming_date,
						applicant=from_email,
						summary=summary,
						responsible="Default Responsible",
						response_deadline=response_deadline
					)
					incoming.save()

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
									attachment = Attachment(
										incoming=incoming,
										filename=decoded_filename
									)
									attachment.file.save(decoded_filename, ContentFile(file_data), save=True)
									logger.info(f'Saved attachment: {decoded_filename}')
								except Exception as e:
									logger.error(f'Failed to process attachment {filename}: {e}')

					logger.info(f'Created Incoming record for email from {from_email} with summary: {summary[:50]}...')
					self.stdout.write(self.style.SUCCESS(f'Created Incoming record for email from {from_email}'))

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