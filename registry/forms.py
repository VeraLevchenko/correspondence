# registry/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from .models import Incoming, Attachment

class IncomingForm(forms.ModelForm):
    attachments = forms.FileField(
        widget=forms.FileInput(),  # Убираем multiple=True
        required=False,
        label='Вложения',
        allow_empty_file=True
    )

    class Meta:
        model = Incoming
        fields = [
            'incoming_number',
            'applicant',
            'incoming_date',
            'summary',
            'responsible',
            'response_deadline',
        ]
        widgets = {
            'incoming_number': forms.NumberInput(attrs={'min': 1}),
            'incoming_date': forms.DateInput(attrs={'type': 'date'}),
            'response_deadline': forms.DateInput(attrs={'type': 'date'}),
            'summary': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            max_number = Incoming.objects.aggregate(Max('incoming_number'))['incoming_number__max']
            self.initial['incoming_number'] = (max_number or 0) + 1

    def clean_incoming_number(self):
        incoming_number = self.cleaned_data.get('incoming_number')
        if incoming_number is not None:
            if Incoming.objects.filter(incoming_number=incoming_number).exclude(pk=self.instance.pk).exists():
                raise ValidationError('Запись с таким номером уже существует.')
            if incoming_number <= 0:
                raise ValidationError('Номер должен быть положительным числом.')
        return incoming_number

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            # Обработка загруженных файлов
            files = self.files.getlist('attachments')  # Получаем список файлов
            for file in files:
                if file:  # Проверяем, что файл не пустой
                    Attachment.objects.create(
                        incoming=instance,
                        file=file,
                        filename=file.name
                    )
        return instance