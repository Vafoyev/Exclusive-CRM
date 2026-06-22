from django.apps import AppConfig


class HardwareConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hardware'
    verbose_name = 'Hardware Integrations'

    def ready(self):
        from apps.hardware import schema  # noqa: F401
