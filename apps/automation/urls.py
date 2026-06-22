from django.urls import path
from . import views

app_name = 'automation'

urlpatterns = [
    path('templates/', views.template_list, name='template_list'),
    path('templates/add/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/test/', views.template_test, name='template_test'),
    path('send-notification/', views.send_custom_notification, name='send_notification'),
]
