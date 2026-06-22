from django.urls import path
from . import views
from . import export_views

app_name = 'users'

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('add/', views.user_create, name='user_create'),
    path('students/', views.user_list, {'role': 'student'}, name='student_list'),
    path('students/add/', views.student_create, name='student_create'),
    path('students/set-bonus/', views.admin_set_student_bonus, name='admin_set_student_bonus'),
    path('parents/search/', views.parent_search, name='parent_search'),
    path('teachers/', views.user_list, {'role': 'teacher'}, name='teacher_list'),
    path('teachers/add/', views.teacher_create, name='teacher_create'),
    path('staff/', views.user_list, {'role': 'staff'}, name='staff_list'),
    path('staff/add/', views.staff_create, name='staff_create'),
    path('<int:pk>/', views.user_detail, name='user_detail'),
    path('<int:pk>/edit/', views.user_update, name='user_update'),
    path('<int:pk>/delete/', views.user_delete, name='user_delete'),

    # Export (PDF/Excel)
    path('export/excel/', export_views.export_users_excel, name='export_users_excel'),
    path('export/pdf/', export_views.export_users_pdf, name='export_users_pdf'),
    path('students/export/excel/', export_views.export_students_excel, name='export_students_excel'),
    path('teachers/export/excel/', export_views.export_teachers_excel, name='export_teachers_excel'),
]