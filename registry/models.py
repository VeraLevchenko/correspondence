# registry/models.py
from django.db import models
from django.db.models import Max
from django.utils import timezone

class Incoming(models.Model):
    incoming_number = models.IntegerField(unique=True)
    incoming_date = models.DateField(default=timezone.now)
    applicant = models.CharField(max_length=255)
    summary = models.TextField()
    responsible = models.CharField(max_length=100)
    response_deadline = models.DateField()

    def save(self, *args, **kwargs):
        if not self.incoming_number:
            max_number = Incoming.objects.aggregate(Max('incoming_number'))['incoming_number__max']
            self.incoming_number = (max_number or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"№{self.incoming_number} от {self.incoming_date}"

    class Meta:
        ordering = ['-incoming_date', '-incoming_number']

class Attachment(models.Model):
    incoming = models.ForeignKey(Incoming, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    filename = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.filename or self.file.name