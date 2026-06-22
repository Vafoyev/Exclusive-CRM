import os
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.utils import timezone

from apps.core.backup_utils import cleanup_old_backups, create_backup_file
from apps.core.models import BackupConfiguration, BackupRunLog


def get_backup_configuration():
    return BackupConfiguration.objects.order_by('id').first() or BackupConfiguration.objects.create()


def mask_token(token):
    if not token:
        return ''
    if len(token) <= 8:
        return '*' * len(token)
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def calculate_next_run_at(configuration, base_time=None):
    base_time = base_time or timezone.localtime()
    if not configuration.is_enabled:
        return None

    if configuration.schedule_type == 'manual':
        return None

    if configuration.schedule_type == 'interval':
        interval_hours = max(configuration.interval_hours or 1, 1)
        anchor = configuration.last_run_at or base_time
        anchor = timezone.localtime(anchor)
        return anchor + timedelta(hours=interval_hours)

    target_time = configuration.daily_time or datetime.strptime('23:59', '%H:%M').time()
    next_run = timezone.make_aware(
        datetime.combine(base_time.date(), target_time),
        timezone.get_current_timezone(),
    )
    if next_run <= base_time:
        next_run += timedelta(days=1)
    return next_run


def save_backup_configuration(configuration, updated_by=None):
    configuration.updated_by = updated_by
    configuration.next_run_at = calculate_next_run_at(configuration)
    configuration.save()
    return configuration


def detect_latest_telegram_chat_id(bot_token):
    response = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getUpdates",
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get('ok'):
        raise RuntimeError(payload.get('description') or "Telegram getUpdates xatosi.")

    for item in reversed(payload.get('result', [])):
        for key in ('message', 'channel_post', 'edited_message'):
            chat = item.get(key, {}).get('chat')
            if chat and chat.get('id'):
                return str(chat['id'])
    raise RuntimeError("Bot bilan hali chat ochilmagan. Botga avval /start yuboring.")


def _parse_telegram_response(response, default_message):
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.ok and payload and payload.get('ok'):
        return payload

    description = ''
    if payload:
        description = payload.get('description') or ''
    if not description:
        description = (response.text or '').strip()
    if not description:
        description = default_message

    lowered = description.lower()
    if 'chat not found' in lowered:
        description = (
            "Telegram chat topilmadi. Botga avval /start yuboring yoki to'g'ri chat ID kiriting."
        )
    elif 'bot was blocked by the user' in lowered:
        description = "Bot foydalanuvchi tomonidan bloklangan. Telegramda botni unblock qiling."
    elif 'user is deactivated' in lowered:
        description = "Telegram user deaktiv qilingan yoki yaroqsiz chat ID berilgan."
    elif 'message caption is too long' in lowered:
        description = "Telegram caption juda uzun. Qisqaroq xabar bilan qayta urinib ko'ring."
    elif 'entity too large' in lowered or 'request entity too large' in lowered or 'file is too big' in lowered:
        description = "Backup fayl juda katta. Fayl hajmini kamaytiring yoki boshqa kanalga yuboring."

    raise RuntimeError(description)


def send_backup_to_telegram(file_path, bot_token, chat_id='', auto_detect_chat=True):
    if not bot_token:
        return {
            'sent': False,
            'chat_id': chat_id,
            'message': "Telegram bot token kiritilmagan.",
        }

    resolved_chat_id = chat_id.strip() if chat_id else ''
    if not resolved_chat_id and auto_detect_chat:
        resolved_chat_id = detect_latest_telegram_chat_id(bot_token)

    if not resolved_chat_id:
        return {
            'sent': False,
            'chat_id': '',
            'message': "Telegram chat ID topilmadi.",
        }

    file_size = os.path.getsize(file_path)
    caption = (
        "Database backup\n"
        f"Sana: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}\n"
        f"Fayl: {os.path.basename(file_path)}\n"
        f"Hajm: {format_file_size(file_size)}"
    )
    with open(file_path, 'rb') as backup_file:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendDocument",
            data={
                'chat_id': resolved_chat_id,
                'caption': caption,
            },
            files={'document': backup_file},
            timeout=60,
        )
    _parse_telegram_response(response, "Telegram sendDocument xatosi.")

    return {
        'sent': True,
        'chat_id': resolved_chat_id,
        'message': "Backup Telegramga yuborildi.",
    }


def trigger_backup_now(configuration=None, triggered_by=None, trigger_source='manual'):
    configuration = configuration or get_backup_configuration()
    run_log = BackupRunLog.objects.create(
        configuration=configuration,
        triggered_by=triggered_by,
        trigger_source=trigger_source,
        status='failed',
        started_at=timezone.now(),
    )

    try:
        backup_file = create_backup_file()
        file_size = os.path.getsize(backup_file)
        telegram_result = send_backup_to_telegram(
            backup_file,
            configuration.telegram_bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', ''),
            configuration.telegram_chat_id or getattr(settings, 'TELEGRAM_BACKUP_CHAT_ID', ''),
            auto_detect_chat=configuration.auto_detect_chat,
        )
        if telegram_result.get('chat_id') and configuration.telegram_chat_id != telegram_result['chat_id']:
            configuration.telegram_chat_id = telegram_result['chat_id']

        removed_count = cleanup_old_backups(days=max(configuration.retention_days or 1, 1))
        message = (
            f"Backup tayyor: {os.path.basename(backup_file)} ({format_file_size(file_size)}). "
            f"{telegram_result['message']} Eski tozalangan backup: {removed_count} ta."
        )

        configuration.last_run_at = timezone.now()
        configuration.last_status = 'success'
        configuration.last_message = message
        configuration.next_run_at = calculate_next_run_at(configuration, base_time=timezone.localtime(configuration.last_run_at))
        configuration.save()

        run_log.status = 'success'
        run_log.backup_file_name = os.path.basename(backup_file)
        run_log.file_size_bytes = file_size
        run_log.sent_to_telegram = telegram_result['sent']
        run_log.message = message
        run_log.completed_at = timezone.now()
        run_log.save()

        return {
            'success': True,
            'message': message,
            'run_log': run_log,
        }
    except Exception as exc:
        configuration.last_run_at = timezone.now()
        configuration.last_status = 'failed'
        configuration.last_message = str(exc)
        configuration.next_run_at = calculate_next_run_at(configuration, base_time=timezone.localtime(configuration.last_run_at))
        configuration.save()

        run_log.message = str(exc)
        run_log.completed_at = timezone.now()
        run_log.save()
        return {
            'success': False,
            'message': str(exc),
            'run_log': run_log,
        }


def run_due_backups():
    now = timezone.localtime()
    processed = []
    for configuration in BackupConfiguration.objects.filter(is_enabled=True).exclude(next_run_at__isnull=True):
        next_run = configuration.next_run_at
        if next_run and timezone.localtime(next_run) <= now:
            processed.append(trigger_backup_now(configuration=configuration, trigger_source='schedule'))
    return processed
