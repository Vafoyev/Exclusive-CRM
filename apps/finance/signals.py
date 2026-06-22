"""
Finance moduli uchun signal'lar.
Transaction tasdiqlanganda balansni avtomatik yangilash.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from apps.finance.models import Transaction


@receiver(pre_save, sender=Transaction)
def prevent_edit_confirmed_transaction(sender, instance, **kwargs):
    """
    Tasdiqlangan yoki topshirilgan tranzaksiyani o'zgartirishni oldini olish.
    Bu moliyaviy xatolarning oldini oladi.
    """
    if instance.pk:  # Mavjud obyekt (yangi emas)
        try:
            old_transaction = Transaction.objects.get(pk=instance.pk)
            instance._previous_transaction = old_transaction

            # Agar kassa topshirilgan bo'lsa, hech qanday muhim o'zgarish mumkin emas
            if old_transaction.cash_submission_id is not None:
                critical_fields = ['amount', 'transaction_type', 'account', 'student', 'staff', 'payment_method']
                for field in critical_fields:
                    old_value = getattr(old_transaction, field)
                    new_value = getattr(instance, field)
                    if old_value != new_value:
                        raise ValidationError(
                            f"Kassa topshirilgan tranzaksiyaning '{field}' maydonini o'zgartirib bo'lmaydi!"
                        )

            # Agar status confirmed bo'lsa, muhim maydonlarni o'zgartirish mumkin emas
            # (faqat admin_edit_transaction orqali balanslarni qayta hisoblash bilan)
            if old_transaction.status == 'confirmed':
                if getattr(instance, '_bypass_confirmed_edit_lock', False):
                    return

                critical_fields = [
                    'amount', 'transaction_type', 'account', 'student',
                    'staff', 'payment_method', 'category',
                ]

                for field in critical_fields:
                    old_value = getattr(old_transaction, field)
                    new_value = getattr(instance, field)

                    if old_value != new_value:
                        raise ValidationError(
                            f"Tasdiqlangan tranzaksiyaning '{field}' maydonini o'zgartirib bo'lmaydi! "
                            f"Agar xato bo'lsa, uni bekor qiling va yangisini yarating."
                        )
        except Transaction.DoesNotExist:
            pass  # Yangi obyekt


@receiver(post_save, sender=Transaction)
def update_balances_on_transaction(sender, instance, created, **kwargs):
    """
    Transaction tasdiqlanganda balanslarni avtomatik yangilash.

    Qoidalar:
    1. Faqat status='confirmed' bo'lganda balanslarga ta'sir qiladi
    2. O'quvchi to'lovi (income) -> student.balance OSHADI
    3. O'quvchi to'lovdan qaytarish (refund) -> student.balance KAMAYADI
    4. Xodim oyligi (salary) -> staff.balance (agar kerak bo'lsa)
    5. Kassa balance ham o'zgaradi
    """
    # Faqat tasdiqlangan va o'chirilmagan tranzaksiyalar
    if instance.status != 'confirmed' or instance.is_deleted:
        return

    previous_transaction = getattr(instance, '_previous_transaction', None)
    if not created:
        if previous_transaction is None:
            try:
                previous_transaction = Transaction.objects.get(pk=instance.pk)
            except Transaction.DoesNotExist:
                previous_transaction = None

        # Faqat pending -> confirmed o'tishida balanslar signal orqali yangilanadi.
        if previous_transaction and previous_transaction.status == 'confirmed':
            return
        if previous_transaction and previous_transaction.status != 'confirmed' and instance.status != 'confirmed':
            return

    # Kassa balansini yangilash
    account = instance.account

    if instance.transaction_type == 'income':
        # Kirim - kassaga qo'shiladi
        account.balance += instance.amount

        # O'quvchi to'lovi bo'lsa, uning balansiga ham qo'shiladi
        # (Mahsulot sotishdan tashqari, chunki tovar evaziga to'langan naqd pul)
        is_supply_sale = getattr(instance.category, 'name', '') == 'Mahsulot sotish'
        if instance.student and not is_supply_sale:
            instance.student.balance += instance.amount
            instance.student.save(update_fields=['balance'])

    elif instance.transaction_type == 'expense':
        # Chiqim - kassadan ayiriladi
        account.balance -= instance.amount

    elif instance.transaction_type == 'refund':
        # Pul qaytarish - kassadan chiqib ketadi
        account.balance -= instance.amount

        # O'quvchidan balans ayiriladi
        if instance.student:
            instance.student.balance -= instance.amount
            instance.student.save(update_fields=['balance'])

    elif instance.transaction_type == 'salary':
        # Xodim oyligi - kassadan chiqadi
        account.balance -= instance.amount

    elif instance.transaction_type == 'monthly_fee':
        # Oylik abonent to'lovi yechish - kassaga ta'sir qilmaydi, faqat o'quvchidan yechiladi
        if instance.student:
            instance.student.balance -= instance.amount
            instance.student.save(update_fields=['balance'])

    elif instance.transaction_type == 'transfer':
        # Internal transfer log'lari destination account balansini oshiradi.
        account.balance += instance.amount

    account.save(update_fields=['balance'])


@receiver(post_save, sender=Transaction)
def log_transaction_confirmation(sender, instance, created, **kwargs):
    """
    Transaction tasdiqlanishini audit log'ga yozish.
    """
    if not created and instance.status == 'confirmed':
        from apps.core.models import AuditLog

        AuditLog.log(
            user=instance.confirmed_by,
            action='UPDATE',
            model_name='Transaction',
            object_id=instance.id,
            object_repr=str(instance),
            changes={
                'status': 'confirmed',
                'amount': float(instance.amount),
                'type': instance.transaction_type
            }
        )
