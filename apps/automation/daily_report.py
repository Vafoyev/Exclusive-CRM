import logging
import requests
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum, Count, Q
from django.utils import timezone

from apps.users.models import User
from apps.finance.models import Transaction, Account
from apps.education.models import Group
from apps.operations.models import Lesson
from apps.crm.models import Lead

logger = logging.getLogger(__name__)


def generate_daily_report_text(organization=None) -> str:
    """
    Kunlik hisobot matnini chiroyli Telegram HTML formatida tayyorlaydi.
    """
    now = timezone.localtime()
    today = now.date()

    # 1. MOLIYA (Bugungi to'lovlar)
    tx_qs = Transaction.objects.filter(
        transaction_type='income',
        status='confirmed',
        created_at__date=today,
        is_deleted=False,
    )
    if organization:
        tx_qs = tx_qs.filter(organization=organization)

    today_income_count = tx_qs.count()
    today_income_sum = tx_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # To'lov turlari bo'yicha
    cash_sum = tx_qs.filter(payment_method='cash').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    card_sum = tx_qs.filter(payment_method='card').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    terminal_sum = tx_qs.filter(payment_method__in=['terminal', 'transfer', 'online']).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Tasdiqlash kutilayotgan to'lovlar (pending)
    pending_qs = Transaction.objects.filter(
        transaction_type='income',
        status='pending',
        created_at__date=today,
        is_deleted=False,
    )
    if organization:
        pending_qs = pending_qs.filter(organization=organization)
    pending_count = pending_qs.count()
    pending_sum = pending_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # 2. O'QUVCHILAR
    student_qs = User.objects.filter(role='student', is_active=True, is_deleted=False)
    if organization:
        student_qs = student_qs.filter(organization=organization)

    total_students = student_qs.count()
    new_students_today = student_qs.filter(created_at__date=today).count()

    # Qarzdorlik
    debtors_qs = student_qs.filter(balance__lt=0)
    debtors_count = debtors_qs.count()
    total_debt = abs(debtors_qs.aggregate(total=Sum('balance'))['total'] or Decimal('0'))

    # 3. KASSALAR BALANSI
    accounts_qs = Account.objects.filter(is_deleted=False)
    if organization:
        accounts_qs = accounts_qs.filter(organization=organization)
    total_kassa_balance = accounts_qs.aggregate(total=Sum('balance'))['total'] or Decimal('0')

    # 4. TA'LIM VA GURUHLAR
    groups_qs = Group.objects.filter(is_deleted=False)
    if organization:
        groups_qs = groups_qs.filter(organization=organization)
    total_groups = groups_qs.count()

    lessons_qs = Lesson.objects.filter(date=today, is_deleted=False)
    if organization:
        lessons_qs = lessons_qs.filter(group__organization=organization)
    today_lessons = lessons_qs.count()
    finished_lessons = lessons_qs.filter(status='finished').count()

    # 5. CRM / LIDLAR
    leads_qs = Lead.objects.filter(is_deleted=False)
    if organization:
        leads_qs = leads_qs.filter(organization=organization)
    new_leads_today = leads_qs.filter(created_at__date=today).count()

    # Matnni shakllantirish
    text = (
        f"📊 <b>EXCLUSIVE CRM — KUNLIK HISOBOT</b>\n"
        f"📅 Sana: <b>{now.strftime('%d.%m.%Y')}</b> | ⏰ <b>{now.strftime('%H:%M')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>MOLIYA VA TUSHUMLAR:</b>\n"
        f"• To'lov qilgan o'quvchilar: <b>{today_income_count} ta</b>\n"
        f"• Bugungi jami tushum: <b>{today_income_sum:,.0f} UZS</b>\n"
    )

    if today_income_count > 0:
        if cash_sum > 0:
            text += f"   💵 Naqd pul: {cash_sum:,.0f} UZS\n"
        if card_sum > 0:
            text += f"   💳 Plastik karta: {card_sum:,.0f} UZS\n"
        if terminal_sum > 0:
            text += f"   🏦 Terminal/Bank: {terminal_sum:,.0f} UZS\n"

        # To'lov qilgan o'quvchilar ro'yxati
        payments = list(tx_qs.select_related('student', 'account').order_by('created_at'))
        text += f"\n🧾 <b>Bugungi to'lovlar ro'yxati:</b>\n"
        method_icons = {
            'cash': '💵 Naqd',
            'card': '💳 Karta',
            'terminal': '🏦 Terminal',
            'transfer': '🏛 O\'tkazma',
            'online': '📱 Onlayn',
        }
        limit = 30
        for idx, p in enumerate(payments[:limit], 1):
            if p.student:
                s_name = p.student.get_full_name() or p.student.username
                s_phone = f" ({p.student.phone})" if getattr(p.student, 'phone', None) else ""
            else:
                s_name = p.description or "Noma'lum to'lovchi"
                s_phone = ""
            m_str = method_icons.get(p.payment_method, p.payment_method or '')
            p_time = timezone.localtime(p.created_at).strftime('%H:%M')
            text += f"{idx}. <b>{s_name}</b>{s_phone}\n   └ 💰 <b>{p.amount:,.0f} UZS</b> | {m_str} | ⏰ {p_time}\n"

        if len(payments) > limit:
            text += f"   <i>...va yana {len(payments) - limit} ta to'lov</i>\n"

    if pending_count > 0:
        text += f"\n⏳ <b>Tasdiqlash kutilayotgan to'lovlar:</b> <b>{pending_count} ta</b> ({pending_sum:,.0f} UZS)\n"

    text += (
        f"\n• Jami kassa qoldig'i: <b>{total_kassa_balance:,.0f} UZS</b>\n\n"
        f"👥 <b>O'QUVCHILAR STATISTIKASI:</b>\n"
        f"• Bugun qo'shilgan yangi o'quvchilar: <b>+{new_students_today} ta</b>\n"
        f"• Jami faol o'quvchilar: <b>{total_students} nafar</b>\n"
        f"• Qarzdor o'quvchilar: <b>{debtors_count} ta</b> (jami: <b>-{total_debt:,.0f} UZS</b>)\n\n"
        f"📚 <b>DARSLAR VA GURUHLAR:</b>\n"
        f"• Faol guruhlar: <b>{total_groups} ta</b>\n"
        f"• Bugungi darslar: <b>{today_lessons} ta</b> (yakunlandi: <b>{finished_lessons} ta</b>)\n"
    )

    if new_leads_today > 0:
        text += f"\n🎯 <b>CRM (LIDLAR):</b>\n• Bugungi yangi lidlar: <b>+{new_leads_today} ta</b>\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <i>Exclusive CRM avtomatik hisobot tizimi</i>"
    )

    return text


def send_daily_report(chat_id=None, bot_token=None, organization=None) -> dict:
    """
    Kunlik hisobotni Telegram bot orqali ko'rsatilgan chatga yuboradi.
    """
    token = (
        bot_token
        or getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        or ''
    )
    if not token:
        try:
            from apps.core.models import BackupConfiguration
            conf = BackupConfiguration.objects.first()
            if conf and conf.telegram_bot_token:
                token = conf.telegram_bot_token
        except Exception:
            pass

    if not token:
        logger.warning("Telegram bot token sozlanmagan!")
        return {'success': False, 'error': "Bot token topilmadi."}

    target_chats = set()
    if chat_id:
        if isinstance(chat_id, (list, tuple)):
            target_chats.update(str(cid).strip() for cid in chat_id if str(cid).strip())
        else:
            for cid in str(chat_id).split(','):
                if cid.strip():
                    target_chats.add(cid.strip())

    configured_chats = getattr(settings, 'TELEGRAM_REPORT_CHAT_ID', '') or getattr(settings, 'TELEGRAM_BACKUP_CHAT_ID', '') or ''
    for cid in str(configured_chats).split(','):
        if cid.strip():
            target_chats.add(cid.strip())

    try:
        from apps.core.models import BackupConfiguration
        conf = BackupConfiguration.objects.first()
        if conf and conf.telegram_chat_id:
            for cid in str(conf.telegram_chat_id).split(','):
                if cid.strip():
                    target_chats.add(cid.strip())
    except Exception:
        pass

    try:
        from apps.users.models import User
        admin_tids = User.objects.filter(
            role__in=['super_admin', 'owner'],
            telegram_id__isnull=False,
            is_active=True
        ).values_list('telegram_id', flat=True)
        for tid in admin_tids:
            if tid:
                target_chats.add(str(tid).strip())
    except Exception:
        pass

    if not target_chats:
        return {'success': False, 'error': "Qabul qiluvchi Chat ID topilmadi."}

    text = generate_daily_report_text(organization=organization)
    sent_count = 0
    errors = []

    for target_chat in target_chats:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': str(target_chat),
                'text': text,
                'parse_mode': 'HTML',
            }, timeout=15)
            res_data = response.json()
            if res_data.get('ok'):
                sent_count += 1
            else:
                logger.error("Telegram sendMessage xatosi (chat %s): %s", target_chat, res_data)
                errors.append(f"{target_chat}: {res_data.get('description')}")
        except Exception as e:
            logger.exception("Telegram report yuborishda xatolik:")
            errors.append(f"{target_chat}: {e}")

    return {
        'success': sent_count > 0,
        'sent_count': sent_count,
        'total_targets': len(target_chats),
        'errors': errors
    }


def send_payment_notification(transaction) -> bool:
    """
    Yangi to'lov tasdiqlanganda Telegram guruh va adminlarga darhol bildirishnoma yuborish.
    """
    if not transaction or transaction.transaction_type != 'income' or transaction.status != 'confirmed':
        return False

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return False

    target_chats = set()
    configured_chats = getattr(settings, 'TELEGRAM_REPORT_CHAT_ID', '') or getattr(settings, 'TELEGRAM_BACKUP_CHAT_ID', '') or ''
    for cid in str(configured_chats).split(','):
        if cid.strip():
            target_chats.add(cid.strip())

    if not target_chats:
        return False

    s_name = transaction.student.get_full_name() if transaction.student else (transaction.description or "Noma'lum to'lovchi")
    s_phone = f"\n📞 <b>Telefon:</b> +{transaction.student.phone}" if (transaction.student and getattr(transaction.student, 'phone', None)) else ""
    acc_name = transaction.account.name if transaction.account else "Kassa"
    method_icons = {
        'cash': '💵 Naqd',
        'card': '💳 Karta',
        'terminal': '🏦 Terminal',
        'transfer': '🏛 O\'tkazma',
        'online': '📱 Onlayn',
    }
    method_str = method_icons.get(transaction.payment_method, transaction.payment_method or 'Boshqa')
    p_time = timezone.localtime(transaction.created_at).strftime('%d.%m.%Y %H:%M')
    conf_by = f"\n👨‍💼 <b>Qabul qildi:</b> {transaction.confirmed_by.get_full_name() or transaction.confirmed_by.username}" if transaction.confirmed_by else ""
    desc = f"\n📝 <b>Izoh:</b> {transaction.description}" if transaction.description and transaction.description != f"Tezkor to'lov: {s_name}" else ""

    text = (
        f"🟢 <b>YANGI TO'LOV QABUL QILINDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>O'quvchi:</b> <b>{s_name}</b>{s_phone}\n"
        f"💰 <b>Summa:</b> <b>{transaction.amount:,.0f} UZS</b>\n"
        f"💳 <b>To'lov turi:</b> {method_str}\n"
        f"🏦 <b>Kassa:</b> {acc_name}{desc}{conf_by}\n"
        f"⏰ <b>Vaqt:</b> {p_time}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <i>Exclusive CRM</i>"
    )

    sent = False
    for target_chat in target_chats:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = requests.post(url, json={
                'chat_id': str(target_chat),
                'text': text,
                'parse_mode': 'HTML',
            }, timeout=8)
            if resp.status_code == 200:
                sent = True
        except Exception as e:
            logger.error("Failed to send payment alert to %s: %s", target_chat, e)

    return sent

