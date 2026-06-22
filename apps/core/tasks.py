"""
Core background tasks.
"""
from datetime import timedelta
import logging
import os

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.core.backup_utils import cleanup_old_backups, create_backup_file

try:
    from celery import shared_task
except ImportError:
    def shared_task(*task_args, **task_kwargs):
        def decorator(func):
            return func

        if task_args and callable(task_args[0]) and len(task_args) == 1 and not task_kwargs:
            return task_args[0]
        return decorator


logger = logging.getLogger('apps')


def _create_backup():
    """
    Database backup faylini yaratadi.
    """
    backup_file = create_backup_file()
    logger.info("Backup yaratildi: %s", backup_file)
    return backup_file


def _send_to_telegram(file_path):
    """
    Backup faylni Telegram chatga yuboradi.
    """
    import telegram

    bot_token = settings.TELEGRAM_BOT_TOKEN
    chat_id = getattr(settings, 'TELEGRAM_BACKUP_CHAT_ID', '')

    if not bot_token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN yoki TELEGRAM_BACKUP_CHAT_ID sozlanmagan.")
        return False

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    if file_size < 1024:
        size_str = f"{file_size} B"
    elif file_size < 1024 * 1024:
        size_str = f"{file_size / 1024:.1f} KB"
    else:
        size_str = f"{file_size / (1024 * 1024):.1f} MB"

    now = timezone.now()
    db_name = settings.DATABASES['default'].get('NAME', 'unknown')
    caption = (
        "*Database Backup*\n"
        f"Sana: `{now.strftime('%Y-%m-%d %H:%M')}`\n"
        f"Baza: `{db_name}`\n"
        f"Hajm: `{size_str}`\n"
        "Status: Muvaffaqiyatli"
    )

    if file_size > 50 * 1024 * 1024:
        logger.error("Backup fayl juda katta (%s), Telegram limitidan oshdi.", size_str)
        import asyncio

        async def _send_warning():
            async with telegram.Bot(token=bot_token) as async_bot:
                await async_bot.send_message(
                    chat_id=chat_id,
                    text=f"Backup fayl juda katta ({size_str}). Telegram limitidan oshdi.",
                )

        asyncio.run(_send_warning())
        return False

    import asyncio

    async def _send():
        async with telegram.Bot(token=bot_token) as async_bot:
            with open(file_path, 'rb') as file_obj:
                await async_bot.send_document(
                    chat_id=chat_id,
                    document=file_obj,
                    filename=file_name,
                    caption=caption,
                    parse_mode='Markdown',
                )

    asyncio.run(_send())
    logger.info("Backup Telegramga yuborildi: %s", file_name)
    return True


def _cleanup_old_backups(days=30):
    """
    Eski backup fayllarni o'chiradi.
    """
    removed = cleanup_old_backups(days=days)
    logger.info("Eski backup tozalandi: %s ta", removed)
    return removed


@shared_task
def backup_and_report():
    """
    Backup yaratadi va imkon bo'lsa Telegramga yuboradi.
    """
    try:
        backup_file = _create_backup()
        if not backup_file:
            return "Backup yaratilmadi"

        telegram_sent = False
        try:
            telegram_sent = _send_to_telegram(backup_file)
        except Exception as exc:
            logger.error("Telegram yuborishda xato: %s", exc)

        removed = _cleanup_old_backups(days=30)
        status = "Telegramga yuborildi" if telegram_sent else "Faqat lokal saqlandi"
        return f"Backup tayyor: {os.path.basename(backup_file)} | {status} | {removed} ta eski backup o'chirildi"
    except Exception as exc:
        logger.error("Backup xatosi: %s", exc)
        return f"Backup failed: {exc}"


@shared_task
def process_scheduled_backups():
    """
    Backup sozlamalariga qarab kerakli paytda backup ishga tushiradi.
    """
    from apps.core.backup_services import run_due_backups

    processed = run_due_backups()
    return f"{len(processed)} ta scheduled backup ishlatildi"


@shared_task
def cleanup_deleted_objects():
    """
    30 kundan eski soft-deleted obyektlarni tozalaydi.
    """
    from apps.crm.models import Lead
    from apps.finance.models import Transaction
    from apps.users.models import User

    threshold = timezone.now() - timedelta(days=30)
    deleted_count = {
        'users': User.objects.filter(is_deleted=True, updated_at__lt=threshold).delete()[0],
        'leads': Lead.objects.filter(is_deleted=True, updated_at__lt=threshold).delete()[0],
        'transactions': Transaction.objects.filter(is_deleted=True, updated_at__lt=threshold).delete()[0],
    }
    return f"Cleaned up: {deleted_count}"


@shared_task
def clear_expired_cache():
    """
    Cache ni tozalaydi.
    """
    try:
        cache.clear()
        return "Cache cleared successfully"
    except Exception as exc:
        return f"Cache clear failed: {exc}"


@shared_task
def send_email_async(to_email, subject, body):
    """
    Email yuborishni backgroundda bajaradi.
    """
    from django.core.mail import send_mail

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return f"Email sent to {to_email}"
    except Exception as exc:
        return f"Email failed: {exc}"


@shared_task
def update_statistics_cache():
    """
    Dashboard statistikalarini cache ga yozadi.
    """
    from django.db.models import Sum

    from apps.education.models import Group
    from apps.finance.models import Transaction
    from apps.users.models import User

    stats = {
        'total_students': User.objects.filter(role='student', is_deleted=False).count(),
        'total_teachers': User.objects.filter(role='teacher', is_deleted=False).count(),
        'total_groups': Group.objects.filter(is_deleted=False).count(),
        'total_income': Transaction.objects.filter(
            transaction_type='income',
            status='confirmed',
            is_deleted=False,
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    cache.set('dashboard_stats', stats, 3600)
    return f"Statistics cached: {stats}"
