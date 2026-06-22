"""
Bildirishnoma signallari - avtomatik xabar yuborish
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


# ============================================
# YANGI FOYDALANUVCHI QO'SHILGANDA
# ============================================
@receiver(post_save, sender='users.User')
def user_created_notification(sender, instance, created, **kwargs):
    """
    Yangi foydalanuvchi yaratilganda bildirishnoma.
    """
    if not created:
        return

    try:
        from apps.automation.services import create_system_notification

        # Foydalanuvchiga xush kelibsiz xabari
        create_system_notification(
            recipient=instance,
            title="Xush kelibsiz!",
            message=f"Hurmatli {instance.first_name or 'Foydalanuvchi'}, tizimga muvaffaqiyatli ro'yxatdan o'tdingiz!",
            notification_type='system'
        )

        # Super admin va adminlarga xabar
        from apps.users.models import User
        admins = User.objects.filter(
            role__in=['super_admin', 'admin', 'owner'],
            is_active=True,
            organization=instance.organization
        ).exclude(pk=instance.pk)

        for admin in admins[:5]:  # Faqat 5 tagacha
            create_system_notification(
                recipient=admin,
                title="Yangi foydalanuvchi",
                message=f"Yangi {instance.get_role_display()}: {instance.first_name} {instance.last_name} ({instance.phone})",
                notification_type='system'
            )

        logger.debug(f"User created notification sent for: {instance.phone}")

    except Exception as e:
        logger.error(f"Error in user_created_notification: {e}")


# ============================================
# DAVOMAT O'ZGARGANDA
# ============================================
@receiver(post_save, sender='operations.Attendance')
def attendance_notification(sender, instance, created, **kwargs):
    """
    Davomat o'zgarganda (agar 'absent' bo'lsa) ota-onaga xabar yuborish.
    """
    if instance.status != 'absent':
        return

    try:
        from apps.automation.services import send_template_notification

        student = instance.student
        
        # O'quvchining ota-onalariga xabar
        if hasattr(student, 'parent_relations'):
            parents = student.parent_relations.all()

            for relation in parents:
                send_template_notification(
                    user=relation.parent,
                    template_code='ATTENDANCE_ABSENT',
                    context={
                        'parent_name': relation.parent.first_name,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'date': str(instance.lesson.date) if instance.lesson else '',
                        'group': instance.lesson.group.name if instance.lesson and instance.lesson.group else ''
                    }
                )

        logger.debug(f"Attendance notification sent for student: {student.phone}")

    except Exception as e:
        logger.error(f"Error in attendance_notification: {e}")


# ============================================
# TO'LOV TASDIQLANGANDA
# ============================================
@receiver(post_save, sender='finance.Transaction')
def payment_notification(sender, instance, created, **kwargs):
    """
    To'lov tasdiqlanganda o'quvchi va ota-onaga xabar yuborish.
    Kirim/chiqim qo'shilganda administratorlarga xabar yuborish.
    """
    try:
        from apps.automation.services import send_template_notification, create_system_notification
        from apps.users.models import User

        # Yangi tranzaksiya yaratilganda administratorlarga bildirishnoma
        if created and instance.transaction_type in ('income', 'expense'):
            org = instance.organization
            admins = User.objects.filter(
                role__in=['super_admin', 'admin', 'owner'],
                is_active=True,
            )
            if org:
                admins = admins.filter(organization=org)
            # Yaratgan odamning o'ziga xabar yubormaslik
            admins = admins.exclude(pk=instance.created_by_id)

            type_display = 'Kirim' if instance.transaction_type == 'income' else 'Chiqim'
            amount_formatted = f"{instance.amount:,.0f}"
            creator_name = instance.created_by.get_full_name() if instance.created_by else 'Noma\'lum'

            for admin in admins[:10]:
                create_system_notification(
                    recipient=admin,
                    title=f"Yangi {type_display}",
                    message=f"{creator_name} tomonidan {amount_formatted} so'm {type_display.lower()} qo'shildi.",
                    notification_type='system'
                )

        # Faqat tasdiqlangan kirim
        if instance.transaction_type != 'income' or instance.status != 'confirmed':
            return

        if not instance.student:
            return

        student = instance.student
        amount_formatted = f"{instance.amount:,.0f}"

        # O'quvchiga xabar
        send_template_notification(
            user=student,
            template_code='PAYMENT_RECEIVED',
            context={
                'name': student.first_name,
                'amount': amount_formatted,
                'date': instance.created_at.strftime('%d.%m.%Y') if instance.created_at else '',
                'balance': f"{student.balance:,.0f}" if student.balance else '0'
            }
        )
        
        # Tizim bildirishnomasi ham
        create_system_notification(
            recipient=student,
            title="To'lov qabul qilindi",
            message=f"{amount_formatted} so'm to'lov muvaffaqiyatli qabul qilindi. Joriy balans: {student.balance:,.0f} so'm",
            notification_type='system'
        )

        # Ota-onalariga ham xabar
        if hasattr(student, 'parent_relations'):
            for relation in student.parent_relations.all():
                send_template_notification(
                    user=relation.parent,
                    template_code='PAYMENT_RECEIVED_PARENT',
                    context={
                        'parent_name': relation.parent.first_name,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'amount': amount_formatted,
                        'date': instance.created_at.strftime('%d.%m.%Y') if instance.created_at else '',
                        'balance': f"{student.balance:,.0f}" if student.balance else '0'
                    }
                )

        logger.debug(f"Payment notification sent for: {student.phone}, amount: {instance.amount}")

    except Exception as e:
        logger.error(f"Error in payment_notification: {e}")


# ============================================
# LID YARATILGANDA
# ============================================
@receiver(post_save, sender='crm.Lead')
def lead_created_notification(sender, instance, created, **kwargs):
    """
    Yangi lid qo'shilganda mas'ul shaxsga xabar.
    """
    if not created:
        return

    try:
        from apps.automation.services import create_system_notification

        # Mas'ul shaxsga xabar
        if instance.assigned_to:
            create_system_notification(
                recipient=instance.assigned_to,
                title="Yangi lid tayinlandi",
                message=f"Sizga yangi lid tayinlandi: {instance.full_name} ({instance.phone})",
                notification_type='system'
            )

        logger.debug(f"Lead notification sent for: {instance.full_name}")

    except Exception as e:
        logger.error(f"Error in lead_created_notification: {e}")
