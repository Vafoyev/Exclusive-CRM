import mimetypes

from django.http import FileResponse, Http404
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hardware.drf_auth import HardwareTokenAuthentication
from apps.hardware.models import FaceIDUserBinding
from apps.hardware.serializers import (
    FaceIDEventResponseSerializer,
    FaceIDHistorySyncResponseSerializer,
    FaceIDLastSyncResponseSerializer,
    FaceIDUsersListResponseSerializer,
    HardwareEventPayloadSerializer,
    HardwareHistoryPayloadSerializer,
)
from apps.hardware.services import (
    get_event_type_label,
    last_event_time_as_utc_string,
    parse_event_timestamp,
    register_face_event,
)


class HardwareBaseAPIView(APIView):
    authentication_classes = [HardwareTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @property
    def integration(self):
        return self.request.auth


class FaceIDUsersListAPIView(HardwareBaseAPIView):
    @extend_schema(
        tags=['Hikvision Face ID'],
        summary="Sync bo'ladigan foydalanuvchilar ro'yxati",
        description=(
            "Desktop agent Hikvision qurilmaga yuborishi kerak bo'lgan foydalanuvchilar ro'yxatini oladi. "
            "Har bir user uchun Face ID kodi, to'liq ism va rasm URL qaytariladi."
        ),
        responses=FaceIDUsersListResponseSerializer,
        examples=[
            OpenApiExample(
                'Users List Response',
                value={
                    'success': True,
                    'data': {
                        'users': [
                            {
                                'user_id': 25,
                                'face_id_code': '1001',
                                'full_name': 'Teacher Hardware',
                                'phone': '998930000002',
                                'role': 'teacher',
                                'face_image_url': '/api/v1/hardware/users/25/face-image',
                            }
                        ],
                        'count': 1,
                    }
                },
                response_only=True,
            )
        ],
    )
    def get(self, request):
        bindings = list(
            FaceIDUserBinding.objects.filter(
                organization=self.integration.organization,
                sync_enabled=True,
                user__is_deleted=False,
                user__is_active=True,
            ).select_related('user').order_by('user__first_name', 'user__last_name', 'user__id')
        )

        now = timezone.now()
        if bindings:
            FaceIDUserBinding.objects.filter(id__in=[binding.id for binding in bindings]).update(last_synced_at=now)

        users = []
        for binding in bindings:
            user = binding.user
            users.append({
                'user_id': user.id,
                'face_id_code': binding.face_id_code,
                'full_name': user.full_name or user.phone,
                'phone': user.phone,
                'role': user.role,
                'face_image_url': reverse('hardware:api_face_image', kwargs={'user_id': user.id}) if user.avatar else None,
            })

        return Response({
            'success': True,
            'data': {
                'users': users,
                'count': len(users),
            }
        })


class FaceIDLastSyncTimeAPIView(HardwareBaseAPIView):
    @extend_schema(
        tags=['Hikvision Face ID'],
        summary="Oxirgi sync vaqtini olish",
        description=(
            "Desktop agent history sync boshlashdan oldin backend oxirgi qaysi Face ID eventni qabul qilganini oladi."
        ),
        responses=FaceIDLastSyncResponseSerializer,
        examples=[
            OpenApiExample(
                'Last Sync Response',
                value={
                    'success': True,
                    'data': {
                        'last_synced_at': '2026-04-14T18:03:42Z',
                    }
                },
                response_only=True,
            )
        ],
    )
    def get(self, request):
        return Response({
            'success': True,
            'data': {
                'last_synced_at': last_event_time_as_utc_string(self.integration.organization),
            }
        })


class FaceIDHistorySyncAPIView(HardwareBaseAPIView):
    @extend_schema(
        tags=['Hikvision Face ID'],
        summary="History loglarni bulk yuborish",
        description=(
            "Agent qurilmadagi eski kelish-ketish loglarini partiya ko'rinishida backendga yuboradi. "
            "Loglar vaqt bo'yicha tartiblanadi, kunning birinchi o'tishi `keldi`, keyingisi `ketdi` sifatida saqlanadi. "
            "Staff user bo'lsa HR davomatga ham tushadi."
        ),
        request=HardwareHistoryPayloadSerializer,
        responses=FaceIDHistorySyncResponseSerializer,
        examples=[
            OpenApiExample(
                'History Sync Request',
                value={
                    'logs': [
                        {
                            'face_id_code': '1001',
                            'event_type': 'CHECK_IN',
                            'timestamp': '2026-04-13T08:55:00+05:00',
                            'device_ip': '192.168.1.200',
                        },
                        {
                            'face_id_code': '1001',
                            'event_type': 'CHECK_OUT',
                            'timestamp': '2026-04-13T18:02:00+05:00',
                            'device_ip': '192.168.1.201',
                        }
                    ]
                },
                request_only=True,
            ),
            OpenApiExample(
                'History Sync Response',
                value={
                    'success': True,
                    'data': {
                        'processed': 2,
                        'created': 2,
                    }
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = HardwareHistoryPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        created_count = 0
        ordered_logs = sorted(
            serializer.validated_data['logs'],
            key=lambda item: parse_event_timestamp(item['timestamp']),
        )
        for item in ordered_logs:
            _, created = register_face_event(
                integration=self.integration,
                face_id_code=item['face_id_code'],
                event_type=item['event_type'],
                timestamp=item['timestamp'],
                device_ip=item.get('device_ip'),
                raw_payload=item,
            )
            if created:
                created_count += 1

        return Response({
            'success': True,
            'data': {
                'processed': len(serializer.validated_data['logs']),
                'created': created_count,
            }
        })


class FaceIDEventAPIView(HardwareBaseAPIView):
    @extend_schema(
        tags=['Hikvision Face ID'],
        summary="Live Face ID event qabul qilish",
        description=(
            "Qurilmadan kelgan real-time eventni qabul qiladi. Kunning birinchi o'tishi `keldi`, "
            "keyingisi `ketdi` sifatida avtomatik aniqlanadi. Agar Face ID kodi staff userga "
            "bog'langan bo'lsa, HR davomat jadvali ham yangilanadi."
        ),
        request=HardwareEventPayloadSerializer,
        responses=FaceIDEventResponseSerializer,
        examples=[
            OpenApiExample(
                'Live Event Request',
                value={
                    'face_id_code': '1001',
                    'event_type': 'CHECK_IN',
                    'timestamp': '2026-04-14T09:05:00+05:00',
                    'device_ip': '192.168.1.200',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Live Event Response',
                value={
                    'success': True,
                    'data': {
                        'created': True,
                        'user_id': 25,
                        'event_type': 'CHECK_IN',
                        'event_label': 'Markazga keldi',
                        'occurred_at': '2026-04-14T09:05:00+05:00',
                    }
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = HardwareEventPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        event, created = register_face_event(
            integration=self.integration,
            face_id_code=payload['face_id_code'],
            event_type=payload['event_type'],
            timestamp=payload['timestamp'],
            device_ip=payload.get('device_ip'),
            raw_payload=payload,
        )

        return Response({
            'success': True,
            'data': {
                'created': created,
                'user_id': event.user_id,
                'event_type': event.event_type,
                'event_label': get_event_type_label(event.event_type),
                'occurred_at': event.occurred_at.isoformat(),
            }
        })


class FaceIDUserImageAPIView(HardwareBaseAPIView):
    @extend_schema(
        tags=['Hikvision Face ID'],
        summary="Foydalanuvchi rasmi",
        description="Agent Hikvision qurilmaga upload qilish uchun user avatar rasmini shu endpointdan oladi.",
        responses={
            200: OpenApiResponse(response=OpenApiTypes.BINARY, description='User avatar image'),
            404: OpenApiResponse(description='Rasm topilmadi'),
        },
    )
    def get(self, request, user_id):
        binding = FaceIDUserBinding.objects.select_related('user').filter(
            organization=self.integration.organization,
            user_id=user_id,
            sync_enabled=True,
            user__is_deleted=False,
            user__is_active=True,
        ).first()
        if binding is None or not binding.user.avatar:
            raise Http404("Rasm topilmadi.")

        file_handle = binding.user.avatar.open('rb')
        content_type = mimetypes.guess_type(binding.user.avatar.name)[0] or 'application/octet-stream'
        response = FileResponse(file_handle, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="face-{binding.user_id}.jpg"'
        return response
