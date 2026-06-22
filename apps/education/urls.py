from django.urls import path
from . import views
from . import materials_views

# app_name = 'education'  # Removed to avoid namespace issues

urlpatterns = [
    # Kurslar
    path('courses/', views.course_list, name='course_list'),
    path('courses/add/', views.course_create, name='course_create'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),

    # Xonalar
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/add/', views.room_create, name='room_create'),
    path('rooms/<int:pk>/edit/', views.room_edit, name='room_edit'),
    path('rooms/<int:pk>/delete/', views.room_delete, name='room_delete'),

    # Guruhlar
    path('groups/', views.group_list, name='group_list'),
    path('groups/add/', views.group_create, name='group_create'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
    path('groups/<int:pk>/add-student/', views.add_student_to_group, name='add_student_to_group'),
    path('groups/<int:pk>/remove-student/<int:student_id>/', views.remove_student_from_group, name='remove_student_from_group'),
    
    # API - O'quvchi qidirish
    path('api/search-students/', views.search_students_api, name='search_students_api'),
    
    # Materials LMS (edu/materials/ prefix)
    path('edu/materials/', materials_views.material_list, name='material_list'),
    path('edu/materials/<int:pk>/', materials_views.material_view, name='material_view'),
    path('edu/materials/<int:pk>/download/', materials_views.material_download, name='material_download'),
    path('edu/materials/upload/', materials_views.material_upload, name='material_upload'),
    path('edu/materials/<int:pk>/edit/', materials_views.material_edit, name='material_edit'),
    path('edu/materials/<int:pk>/delete/', materials_views.material_delete, name='material_delete'),

    # Material kategoriyalari
    path('edu/materials/categories/', materials_views.category_list, name='material_category_list'),
    path('edu/materials/categories/add/', materials_views.category_create, name='material_category_create'),
]