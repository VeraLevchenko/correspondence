# registry/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max  # Добавлен импорт
from .models import Incoming

class IncomingForm(forms.ModelForm):
    class Meta:
        model = Incoming
        fields = [
            'incoming_number',
            'applicant',
            'incoming_date',
            'summary',
            'attachment',
            'responsible',
            'response_deadline',
        ]
        widgets = {
            'incoming_number': forms.NumberInput(attrs={'min': 1}),
            'incoming_date': forms.DateInput(attrs={'type': 'date'}),
            'response_deadline': forms.DateInput(attrs={'type': 'date'}),
            'summary': forms.Textarea(attrs={'rows': 4}),
            'attachment': forms.ClearableFileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Установка начального значения для incoming_number
        if not self.instance.pk:  # Только для новых записей
            max_number = Incoming.objects.aggregate(Max('incoming_number'))['incoming_number__max']
            self.initial['incoming_number'] = (max_number or 0) + 1

    def clean_incoming_number(self):
        incoming_number = self.cleaned_data.get('incoming_number')
        if incoming_number is not None:
            # Проверка уникальности
            if Incoming.objects.filter(incoming_number=incoming_number).exclude(pk=self.instance.pk).exists():
                raise ValidationError('Запись с таким номером уже существует.')
            # Проверка, что номер положительный
            if incoming_number <= 0:
                raise ValidationError('Номер должен быть положительным числом.')
        return incoming_number