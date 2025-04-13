# correspondence/urls.py
from django.urls import path, re_path
from django.shortcuts import redirect
from django.views.static import serve
from registry import views
from django.conf import settings
from django.conf.urls.static import static

def redirect_to_incoming(request):
    return redirect('incoming_list')

def redirect_to_create(request):
    return redirect('incoming_create')

urlpatterns = [
    path('incoming/', views.incoming_list, name='incoming_list'),
    path('incoming/<int:pk>/', views.incoming_detail, name='incoming_detail'),
    path('incoming/create/', views.incoming_create, name='incoming_create'),
    path('create/', redirect_to_create),
    path('incoming/<int:pk>/update/', views.incoming_update, name='incoming_update'),
    path('incoming/<int:pk>/delete/', views.incoming_delete, name='incoming_delete'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', redirect_to_incoming),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)