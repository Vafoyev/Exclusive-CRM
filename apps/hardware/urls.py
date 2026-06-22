from django.urls import path

from apps.hardware import views
from apps.hardware.api_views import (
    FaceIDEventAPIView,
    FaceIDHistorySyncAPIView,
    FaceIDLastSyncTimeAPIView,
    FaceIDUserImageAPIView,
    FaceIDUsersListAPIView,
)

app_name = 'hardware'

urlpatterns = [
    path('face-id/', views.face_id_settings, name='face_id_settings'),

    # API v1 (agent compatibility)
    path('api/v1/hardware/sync/users-list', FaceIDUsersListAPIView.as_view(), name='api_users_list'),
    path('api/v1/hardware/sync/last-time', FaceIDLastSyncTimeAPIView.as_view(), name='api_last_sync_time'),
    path('api/v1/hardware/sync/history', FaceIDHistorySyncAPIView.as_view(), name='api_history_sync'),
    path('api/v1/hardware/event', FaceIDEventAPIView.as_view(), name='api_event'),
    path('api/v1/hardware/users/<int:user_id>/face-image', FaceIDUserImageAPIView.as_view(), name='api_face_image'),
]
