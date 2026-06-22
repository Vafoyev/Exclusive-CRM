from django.urls import path
from . import views
from . import htmx_views

app_name = 'crm'

urlpatterns = [
    # Pipeline
    path('pipeline/', views.pipeline_view, name='pipeline'),
    
    # Leads
    path('leads/add/', views.lead_create, name='lead_create'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('leads/<int:pk>/edit/', views.lead_edit, name='lead_edit'),
    path('leads/<int:pk>/delete/', views.lead_delete, name='lead_delete'),
    path('leads/<int:pk>/convert/', views.lead_convert, name='lead_convert'),
    path('leads/<int:pk>/activity/', views.add_lead_activity, name='add_lead_activity'),
    
    # API
    path('api/leads/<int:lead_id>/move/', views.update_lead_stage, name='update_lead_stage'),
    
    # Stages
    path('stages/', views.stage_list, name='stage_list'),
    path('stages/add/', views.stage_create, name='stage_create'),
    path('stages/<int:pk>/edit/', views.stage_edit, name='stage_edit'),
    path('stages/<int:pk>/delete/', views.stage_delete, name='stage_delete'),
    
    # Sources
    path('sources/', views.source_list, name='source_list'),
    path('sources/add/', views.source_create, name='source_create'),
    path('sources/<int:pk>/edit/', views.source_edit, name='source_edit'),
    path('sources/<int:pk>/delete/', views.source_delete, name='source_delete'),

    # HTMX Endpoints - Tez partial rendering
    path('htmx/lead/<int:pk>/', htmx_views.htmx_lead_card, name='htmx_lead_card'),
    path('htmx/stage/<int:stage_id>/leads/', htmx_views.htmx_stage_leads, name='htmx_stage_leads'),
    path('htmx/lead/<int:pk>/move/<int:stage_id>/', htmx_views.htmx_move_lead, name='htmx_move_lead'),
    path('htmx/search/', htmx_views.htmx_search_leads, name='htmx_search_leads'),
    path('htmx/lead/<int:pk>/delete/', htmx_views.htmx_delete_lead, name='htmx_delete_lead'),
]