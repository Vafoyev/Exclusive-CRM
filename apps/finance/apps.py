from django.apps import AppConfig

class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = "Moliya va Kassa"

    def ready(self):
        """Signal'larni yuklash"""
        import apps.finance.signals
