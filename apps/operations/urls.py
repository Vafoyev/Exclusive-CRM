from django.urls import path
from . import views
from . import shop_views
from . import export_views

app_name = 'operations'

urlpatterns = [
    # Lessons
    path('lessons/', views.lesson_list, name='lesson_list'),
    path('lessons/add/', views.lesson_add, name='lesson_add'),
    path('lessons/<int:pk>/', views.lesson_detail, name='lesson_detail'),
    path('lessons/<int:pk>/edit/', views.lesson_edit, name='lesson_edit'),
    path('lessons/<int:pk>/delete/', views.lesson_delete, name='lesson_delete'),
    path('lessons/<int:pk>/start/', views.start_lesson, name='start_lesson'),
    path('lessons/<int:pk>/finish/', views.finish_lesson, name='finish_lesson'),
    path('lessons/<int:pk>/attendance/', views.take_attendance, name='take_attendance'),
    
    # Schedule
    path('schedule/', views.schedule_view, name='schedule'),
    
    # Ratings
    path('ratings/teachers/', views.teacher_ratings, name='teacher_ratings'),
    path('ratings/students/', views.student_ratings, name='student_ratings'),
    
    # Export (PDF/Excel)
    path('lessons/export/excel/', export_views.export_lessons_excel, name='export_lessons_excel'),
    path('lessons/export/pdf/', export_views.export_lessons_pdf, name='export_lessons_pdf'),
    path('attendance/export/excel/', export_views.export_attendance_excel, name='export_attendance_excel'),
    path('groups/<int:group_id>/attendance/export/', export_views.export_group_attendance_excel, name='export_group_attendance'),

    # Shop (Do'kon)
    path('shop/', shop_views.shop_list, name='shop'),
    path('shop/buy/<int:item_id>/', shop_views.purchase_item, name='purchase_item'),
    path('shop/buy-cash/<int:item_id>/', shop_views.purchase_with_cash, name='purchase_with_cash'),
    path('shop/history/', shop_views.purchase_history, name='purchase_history'),

    # Shop Admin
    path('shop/admin/', shop_views.shop_admin, name='shop_admin'),
    path('shop/deliver/<int:pk>/', shop_views.deliver_purchase, name='deliver_purchase'),
    path('shop/cancel/<int:pk>/', shop_views.cancel_purchase, name='cancel_purchase'),
    path('shop/verify/<int:pk>/', shop_views.verify_purchase, name='verify_purchase'),

    # Shop Categories (Admin)
    path('shop/categories/', shop_views.category_list, name='shop_category_list'),
    path('shop/categories/add/', shop_views.category_create, name='shop_category_create'),
    path('shop/categories/<int:pk>/edit/', shop_views.category_edit, name='shop_category_edit'),
    path('shop/categories/<int:pk>/delete/', shop_views.category_delete, name='shop_category_delete'),

    # Shop Items (Admin)
    path('shop/items/', shop_views.item_list, name='shop_item_list'),
    path('shop/items/add/', shop_views.item_create, name='shop_item_create'),
    path('shop/items/<int:pk>/edit/', shop_views.item_edit, name='shop_item_edit'),
    path('shop/items/<int:pk>/delete/', shop_views.item_delete, name='shop_item_delete'),
]
