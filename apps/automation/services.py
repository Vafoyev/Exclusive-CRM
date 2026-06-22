"""
Bildirishnoma xizmatlari - xabar yuborish va log qilish
"""
from django.conf import settings
from .models import NotificationTemplate, NotificationLog
import logging

logger = logging.getLogger(__name__)


def create_system_notification(recipient, title: str, message: str, notification_type: str = 'system'):
    """
    Tizim ichida bildirishnoma yaratish (navbar da ko'rinadi).

    Args:
        recipient: Qabul qiluvchi user
        title: Xabar sarlavhasi
        message: Xabar matni
        notification_type: 'system', 'sms', 'telegram'

    Returns:
        NotificationLog yoki None
    """
    try:
        notification = NotificationLog.objects.create(
            organization=recipient.organization if hasattr(recipient, 'organization') else None,
            recipient=recipient,
            template=None,  # Template ishlatilmaydi
            message=f"<strong>{title}</strong><br>{message}",
            message_type=notification_type,
            status='sent'
        )

        logger.debug(f"System notification created for {recipient}: {title}")
        return notification

    except Exception as e:
        logger.error(f"Error creating system notification: {e}")
        return None


def send_template_notification(user, template_code: str, context: dict = None):
    """
    Shablon orqali bildirishnoma yuborish.

    Args:
        user: Qabul qiluvchi user
        template_code: Shablon kodi (masalan: 'PAYMENT_RECEIVED')
        context: Xabar ichidagi o'zgaruvchilar (masalan: {'amount': '1,000'})

    Returns:
        True/False
    """
    if context is None:
        context = {}

    # User haqida ma'lumotlarni contextga qo'shamiz
    context.update({
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'phone': user.phone or '',
    })

    try:
        # Shablonni topish
        template = NotificationTemplate.objects.filter(
            code=template_code,
            is_deleted=False
        ).first()

        if not template:
            # Shablon topilmasa, default xabar bilan tizim bildirishnomasi
            logger.warning(f"Notification template not found: {template_code}")
            create_system_notification(
                recipient=user,
                title="Yangi xabar",
                message=f"Template: {template_code}",
                notification_type='system'
            )
            return False

        # Xabarni shakllantirish
        try:
            message_body = template.body.format(**context)
        except KeyError as e:
            logger.error(f"Missing context key for template {template_code}: {e}")
            message_body = template.body  # Formatlashsiz qaytaramiz

        status = 'sent'

        # Telegram yuborish
        if template.message_type == 'telegram':
            status = _send_telegram(user, message_body)

        # SMS yuborish
        elif template.message_type == 'sms':
            status = _send_sms(user, message_body)

        # Log yozish
        NotificationLog.objects.create(
            organization=user.organization if hasattr(user, 'organization') else None,
            recipient=user,
            template=template,
            message=message_body,
            message_type=template.message_type,
            status=status
        )
        
        logger.debug(f"Notification sent [{template.message_type}] to {user.phone}: {message_body[:50]}...")
        return True

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False


def _send_telegram(user, message: str) -> str:
    """
    Telegram orqali xabar yuborish.
    """
    try:
        telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)

        if not telegram_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured")
            return 'sent'  # Log uchun sent deb belgilaymiz

        telegram_id = getattr(user, 'telegram_id', None)

        if not telegram_id:
            logger.warning(f"User {user} has no telegram_id")
            return 'sent'  # Tizimda ko'rinishi uchun sent

        import telebot
        bot = telebot.TeleBot(telegram_token)
        bot.send_message(telegram_id, message, parse_mode='HTML')

        return 'sent'

    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return 'failed'


def _send_sms(user, message: str) -> str:
    """
    SMS yuborish (Mock - hozircha faqat log).
    Keyinchalik Eskiz yoki boshqa SMS provider bilan integratsiya qilish mumkin.
    """
    try:
        # SMS provider integratsiyasi
        # Masalan: Eskiz, PlayMobile va h.k.

        sms_enabled = getattr(settings, 'SMS_ENABLED', False)

        if not sms_enabled:
            logger.debug(f"SMS disabled. Would send to {user.phone}: {message[:50]}...")
            return 'sent'

        # TODO: SMS provider API chaqirish
        # response = sms_provider.send(user.phone, message)

        return 'sent'

    except Exception as e:
        logger.error(f"SMS error: {e}")
        return 'failed'


# Eski funksiya nomi bilan moslik uchun
def send_notification(user, template_code: str, context: dict = None):
    """
    Eski funksiya nomi - yangi funksiyaga yo'naltirish.
    """
    return send_template_notification(user, template_code, context)

