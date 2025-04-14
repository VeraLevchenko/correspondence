# registry/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .models import Incoming
from .forms import IncomingForm
from django.core.paginator import Paginator
import unicodedata

@login_required
def incoming_list(request):
    query = unicodedata.normalize('NFKC', request.GET.get('q', '').strip())
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    responsible_filter = unicodedata.normalize('NFKC', request.GET.get('responsible_filter', '').strip())
    number_filter = request.GET.get('number_filter', '')
    summary_filter = unicodedata.normalize('NFKC', request.GET.get('summary_filter', '').strip())
    deadline_from = request.GET.get('deadline_from', '')
    deadline_to = request.GET.get('deadline_to', '')
    attachment_filter = request.GET.get('attachment_filter', '')

    incoming = Incoming.objects.all().order_by('-incoming_number')

    if query:
        incoming = incoming.filter(applicant__icontains=query)
    if date_from:
        incoming = incoming.filter(incoming_date__gte=date_from)
    if date_to:
        incoming = incoming.filter(incoming_date__lte=date_to)
    if responsible_filter:
        incoming = incoming.filter(responsible__icontains=responsible_filter)
    if number_filter:
        incoming = incoming.filter(incoming_number=number_filter)
    if summary_filter:
        incoming = incoming.filter(summary__icontains=summary_filter)
    if deadline_from:
        incoming = incoming.filter(response_deadline__gte=deadline_from)
    if deadline_to:
        incoming = incoming.filter(response_deadline__lte=deadline_to)
    if attachment_filter == 'yes':
        incoming = incoming.filter(attachments__isnull=False).distinct()
    elif attachment_filter == 'no':
        incoming = incoming.filter(attachments__isnull=True)

    paginator = Paginator(incoming, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'registry/incoming_list.html', {
        'page_obj': page_obj,
        'query': query,
        'date_from': date_from,
        'date_to': date_to,
        'responsible_filter': responsible_filter,
        'number_filter': number_filter,
        'summary_filter': summary_filter,
        'deadline_from': deadline_from,
        'deadline_to': deadline_to,
        'attachment_filter': attachment_filter,
    })

@login_required
def incoming_detail(request, pk):
    incoming = get_object_or_404(Incoming, pk=pk)
    return render(request, 'registry/incoming_detail.html', {'incoming': incoming})

@login_required
def incoming_create(request):
    if request.method == 'POST':
        form = IncomingForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('incoming_list')
    else:
        form = IncomingForm()
    return render(request, 'registry/incoming_form.html', {'form': form})

@login_required
def incoming_update(request, pk):
    incoming = get_object_or_404(Incoming, pk=pk)
    if request.method == 'POST':
        form = IncomingForm(request.POST, request.FILES, instance=incoming)
        if form.is_valid():
            form.save()
            return redirect('incoming_list')
    else:
        form = IncomingForm(instance=incoming)
    return render(request, 'registry/incoming_form.html', {'form': form})

@login_required
def incoming_delete(request, pk):
    incoming = get_object_or_404(Incoming, pk=pk)
    if request.method == 'POST':
        incoming.delete()
        return redirect('incoming_list')
    return render(request, 'registry/incoming_delete.html', {'incoming': incoming})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('incoming_list')
    else:
        form = AuthenticationForm()
    return render(request, 'registry/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')