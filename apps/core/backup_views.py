from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.core.backup_services import (
    calculate_next_run_at,
    format_file_size,
    get_backup_configuration,
    mask_token,
    save_backup_configuration,
    trigger_backup_now,
)


BACKUP_REAUTH_SESSION_KEY = 'backup_center_verified_until'


def _is_backup_access_confirmed(request):
    expires_at = request.session.get(BACKUP_REAUTH_SESSION_KEY)
    if not expires_at:
        return False
    return timezone.now().timestamp() < expires_at


def _require_super_admin(request):
    if request.user.role != 'super_admin':
        messages.error(request, "Bu bo'lim faqat Super Admin uchun.")
        return False
    return True


@login_required
def backup_center(request):
    if not _require_super_admin(request):
        return redirect('dashboard')

    config = get_backup_configuration()

    if request.method == 'POST' and request.POST.get('action') == 'unlock':
        password = request.POST.get('password', '')
        if request.user.check_password(password):
            minutes = getattr(settings, 'BACKUP_CENTER_REAUTH_MINUTES', 15)
            request.session[BACKUP_REAUTH_SESSION_KEY] = timezone.now().timestamp() + minutes * 60
            messages.success(request, "Backup bo'limiga kirish tasdiqlandi.")
            return redirect('core:backup_center')
        messages.error(request, "Parol noto'g'ri.")
        return redirect('core:backup_center')

    if request.method == 'POST' and request.POST.get('action') == 'lock_access':
        request.session.pop(BACKUP_REAUTH_SESSION_KEY, None)
        messages.success(request, "Backup bo'limi qulflandi.")
        return redirect('core:backup_center')

    access_confirmed = _is_backup_access_confirmed(request)
    if not access_confirmed:
        return render(request, 'core/backup_center.html', {
            'access_confirmed': False,
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_settings':
            config.telegram_bot_token = request.POST.get('telegram_bot_token', '').strip()
            config.telegram_chat_id = request.POST.get('telegram_chat_id', '').strip()
            config.auto_detect_chat = 'auto_detect_chat' in request.POST
            config.is_enabled = 'is_enabled' in request.POST
            schedule_type = request.POST.get('schedule_type', 'manual')
            if schedule_type not in {'manual', 'interval', 'daily'}:
                messages.error(request, "Backup rejimi noto'g'ri tanlandi.")
                return redirect('core:backup_center')

            try:
                interval_hours = max(int(request.POST.get('interval_hours') or 24), 1)
                retention_days = max(int(request.POST.get('retention_days') or 30), 1)
            except (TypeError, ValueError):
                messages.error(request, "Interval va saqlash muddati son bo'lishi kerak.")
                return redirect('core:backup_center')

            daily_time = request.POST.get('daily_time', '').strip()
            try:
                parsed_daily_time = datetime.strptime(daily_time, '%H:%M').time() if daily_time else None
            except ValueError:
                messages.error(request, "Kunlik vaqt HH:MM formatida bo'lishi kerak.")
                return redirect('core:backup_center')

            config.schedule_type = schedule_type
            config.interval_hours = interval_hours
            config.retention_days = retention_days
            config.daily_time = parsed_daily_time
            save_backup_configuration(config, updated_by=request.user)
            messages.success(request, "Backup sozlamalari saqlandi.")
            return redirect('core:backup_center')

        if action == 'run_backup_now':
            result = trigger_backup_now(configuration=config, triggered_by=request.user, trigger_source='manual')
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['message'])
            return redirect('core:backup_center')

    recent_logs = list(config.run_logs.select_related('triggered_by')[:10])
    for log in recent_logs:
        log.file_size_display = format_file_size(log.file_size_bytes or 0)

    context = {
        'access_confirmed': True,
        'backup_config': config,
        'masked_bot_token': mask_token(config.telegram_bot_token),
        'recent_logs': recent_logs,
        'next_run_preview': calculate_next_run_at(config),
        'scheduler_command': 'python manage.py process_scheduled_backups',
        'reauth_minutes': getattr(settings, 'BACKUP_CENTER_REAUTH_MINUTES', 15),
    }
    return render(request, 'core/backup_center.html', context)
