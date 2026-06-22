from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import dashboard_view, logout_view
from apps.core.export_views import export_transactions, api_chart_data, global_search
from django.contrib.auth.views import LoginView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth (Kirish/Chiqish)
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', logout_view, name='logout'),

    # Dashboard (Bosh sahifa)
    path('', dashboard_view, name='dashboard'),
    
    # API Hujjatlari (Swagger/OpenAPI)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API & Export
    path('api/', include('apps.api.urls')),
    path('api/chart-data/', api_chart_data, name='api_chart_data'),
    path('api/search/', global_search, name='global_search'),
    path('export/transactions/', export_transactions, name='export_transactions'),
    
    # Modullar
    path('users/', include('apps.users.urls')),
    path('', include('apps.education.urls')),  # courses/, groups/, rooms/, edu/materials/
    path('crm/', include('apps.crm.urls')),
    path('operations/', include('apps.operations.urls')),
    path('finance/', include('apps.finance.urls')),
    path('automation/', include('apps.automation.urls')),
    path('core/', include('apps.core.urls')),
    path('', include('apps.hardware.urls')),
]

# Media fayllar uchun
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
