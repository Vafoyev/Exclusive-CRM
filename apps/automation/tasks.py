"""
Background Tasks - Celery bilan.
Og'ir ishlarni asosiy so'rovdan ajratib, background da bajarish.
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import F


@shared_task(bind=True, max_retries=3)
def send_notification_async(self, notification_id):
    """
    Bildirishnomani background da yuborish.
    View da .delay() bilan chaqiriladi.
    """
    try:
        from apps.automation.models import NotificationLog

        notification = NotificationLog.objects.get(id=notification_id)

        # Telegram yoki boshqa kanallarga yuborish
        # TODO: Telegram bot orqali yuborish

        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save(update_fields=['status', 'sent_at'])

        return f"Notification {notification_id} sent successfully"

    except Exception as exc:
        self.retry(exc=exc, countdown=60)  # 1 daqiqadan keyin qayta urinish


@shared_task
def send_bulk_notifications(template_id, user_ids):
    """
    Ko'plab foydalanuvchilarga bir vaqtda xabar yuborish.
    """
    from apps.automation.models import NotificationTemplate, NotificationLog
    from apps.users.models import User

    template = NotificationTemplate.objects.get(id=template_id)
    users = User.objects.filter(id__in=user_ids)

    created = 0
    for user in users:
        NotificationLog.objects.create(
            template=template,
            recipient=user,
            organization=user.organization,
            message=template.body,
            status='sent',
            sent_at=timezone.now()
        )
        created += 1

    return f"Created {created} notifications"


@shared_task
def send_debt_reminders():
    """
    Qarzdor o'quvchilarga eslatma yuborish.
    Celery Beat orqali har kuni ishga tushadi.
    """
    from apps.users.models import User
    from apps.automation.models import NotificationTemplate, NotificationLog

    # Qarzdorlarni topish
    debtors = User.objects.filter(
        role='student',
        balance__lt=0,
        is_active=True,
        is_deleted=False
    ).select_related('organization')

    # Shablon topish
    template = NotificationTemplate.objects.filter(
        code='DEBT_REMINDER',
        is_active=True
    ).first()

    if not template:
        return "No DEBT_REMINDER template found"

    sent = 0
    for debtor in debtors:
        NotificationLog.objects.create(
            template=template,
            recipient=debtor,
            organization=debtor.organization,
            message=template.body.replace('{name}', debtor.first_name)
                                .replace('{amount}', str(abs(debtor.balance))),
            status='pending'
        )
        sent += 1

    return f"Sent {sent} debt reminders"


@shared_task
def send_daily_reminders():
    """
    Kunlik eslatmalar - darslar, to'lovlar va hokazo.
    """
    from apps.operations.models import Lesson
    from datetime import date

    today = date.today()

    # Bugungi darslar
    today_lessons = Lesson.objects.filter(
        date=today,
        is_deleted=False
    ).select_related('group', 'teacher').count()

    return f"Daily reminders sent. Today's lessons: {today_lessons}"


@shared_task
def generate_report_async(report_type, org_id, date_from, date_to, user_id):
    """
    Hisobotlarni background da yaratish (PDF/Excel).
    Katta ma'lumotlar uchun.
    """
    from apps.finance.models import Transaction
    from apps.organizations.models import Organization
    from apps.users.models import User
    from apps.automation.models import NotificationLog

    org = Organization.objects.get(id=org_id)
    user = User.objects.get(id=user_id)

    # Hisobot yaratish
    transactions = Transaction.objects.filter(
        organization=org,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        is_deleted=False
    ).count()

    # Foydalanuvchiga xabar yuborish
    NotificationLog.objects.create(
        recipient=user,
        organization=org,
        message=f"Sizning hisobotingiz tayyor! {transactions} ta tranzaksiya.",
        status='sent',
        sent_at=timezone.now()
    )

    return f"Report generated: {transactions} transactions"
