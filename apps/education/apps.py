from django.apps import AppConfig

class EducationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.education'
    verbose_name = "Ta'lim Bo'limi"

    def ready(self):
        import apps.education.signals  # noqa: F401