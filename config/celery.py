"""
Celery configuration for Smart Edu CRM.
Background tasks va scheduled jobs uchun.

Ishga tushirish:
    Worker: celery -A config worker -l info
    Beat: celery -A config beat -l info
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('config')

# Django settings dan konfiguratsiyani olish
app.config_from_object('django.conf:settings', namespace='CELERY')

# Barcha apps dan tasks.py ni avtomatik topish
app.autodiscover_tasks()

# Davriy vazifalar jadvali
app.conf.beat_schedule = {
    # Har kuni soat 23:59 da backup
    'daily-database-backup': {
        'task': 'apps.core.tasks.backup_and_report',
        'schedule': crontab(hour=23, minute=59),
    },
    # Har kuni soat 9:00 da qarzdorlarga eslatma
    'daily-debt-reminders': {
        'task': 'apps.automation.tasks.send_debt_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
    # Har 5 daqiqada cache tozalash (o'chirilgan obyektlar)
    'cleanup-deleted-objects': {
        'task': 'apps.core.tasks.cleanup_deleted_objects',
        'schedule': 300,  # 5 daqiqa
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Test task"""
    print(f'Request: {self.request!r}')

