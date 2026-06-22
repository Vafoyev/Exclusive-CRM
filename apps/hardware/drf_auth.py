from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.hardware.authentication import HardwareAPIUser
from apps.hardware.models import FaceIDIntegration


class HardwareTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.headers.get('x-device-token') or request.META.get('HTTP_X_DEVICE_TOKEN')
        if not token:
            return None

        integration = FaceIDIntegration.objects.select_related('organization').filter(
            device_token=token,
            agent_enabled=True,
        ).first()
        if integration is None:
            raise AuthenticationFailed("Noto'g'ri yoki o'chirilgan device token.")

        request.hardware_integration = integration
        return HardwareAPIUser(integration), integration

