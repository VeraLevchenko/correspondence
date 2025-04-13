# registry/tasks.py
from celery import shared_task
from django.core.management import call_command

@shared_task
def process_emails_task():
    call_command('process_emails')