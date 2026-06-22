from drf_spectacular.extensions import OpenApiAuthenticationExtension


class HardwareTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'apps.hardware.drf_auth.HardwareTokenAuthentication'
    name = 'HardwareDeviceTokenAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'x-device-token',
            'description': "Hikvision desktop agent uchun device token. `/face-id/` sahifasidan olinadi.",
        }
