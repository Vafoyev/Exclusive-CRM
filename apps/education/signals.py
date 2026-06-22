from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import date
from decimal import Decimal, ROUND_UP
import calendar

from apps.education.models import GroupStudent
from apps.finance.models import MonthlyFeeCharge, MonthlyFeeLog, TransactionCategory, Account, Transaction
from apps.finance.services import build_monthly_fee_description, calculate_price_with_bonus
from apps.users.models import User


def calculate_proportional_price(full_price, join_day, total_days_in_month):
    """
    Oy o'rtasida qo'shilgan student uchun proporsional narxni hisoblab beradi.
    
    Misol: Narx = 300,000 UZS, Oy = 31 kun, Qo'shilgan sana = 15-mart
    Qolgan kunlar: 31 - 15 + 1 = 17 kun
    Proporsional narx: 300,000 * 17 / 31 = 164,517 UZS
    """
    remaining_days = total_days_in_month - join_day + 1
    if remaining_days <= 0:
        return Decimal('0')
    
    proportional = full_price * Decimal(remaining_days) / Decimal(total_days_in_month)
    return proportional.quantize(Decimal('1'), rounding=ROUND_UP)


def get_system_user_and_account(org):
    """
    Tashkilot uchun system user va virtual accountni topib beradi.
    """
    virtual_account = Account.objects.filter(organization=org).first()
    if not virtual_account:
        return None, None

    system_user = User.objects.filter(role='super_admin', organization=org).first()
    if not system_user:
        system_user = User.objects.filter(role='super_admin').first()

    return system_user, virtual_account


@receiver(post_save, sender=GroupStudent)
def bill_mid_month_enrollment(sender, instance, created, **kwargs):
    """
    Agar o'quvchi guruhga yangi qo'shilsa va shu oy uchun hisob-kitob allaqachon bajarilgan bo'lsa,
    qolgan kunlar uchun proporsional to'lov yechiladi.
    
    Misol: Oy boshida hisob-kitob bo'lgan. 15-martda yangi student qo'shildi.
    Kurs narxi: 300,000 UZS. Mart = 31 kun.
    Qolgan kunlar: 31 - 15 + 1 = 17
    Proporsional narx: 300,000 * 17 / 31 ≈ 164,517 UZS yechiladi.
    """
    # Faqat aktiv holatda qo'shilganda
    if instance.status != 'active':
        return

    student = instance.student
    group = instance.group
    org = group.organization

    if not org:
        return

    today = date.today()
    billing_month = date(today.year, today.month, 1)

    # 1. Shu oy uchun yechish allaqachon bajarilganligini tekshiramiz
    log = MonthlyFeeLog.objects.filter(
        organization=org,
        billing_month=billing_month,
        is_processed=True
    ).first()

    # Agar hali hisob-kitob bo'lmagan bo'lsa, keyinroq skript o'zi yechadi
    if not log:
        return

    # Takroriy yechib olmaslik uchun tekshiruv
    already_billed = MonthlyFeeCharge.objects.filter(
        organization=org,
        billing_month=billing_month,
        student=student,
        group=group,
    ).exists()

    if already_billed:
        return

    # 2. Kurs narxini olish
    base_price = group.course.price if group.course.price > 0 else Decimal('0')
    if base_price == 0:
        return

    # 3. Bonus chegirib, yakuniy to'liq oylik narxni hisoblaymiz
    full_monthly_price = calculate_price_with_bonus(base_price, student)
    if full_monthly_price <= 0:
        return

    # 4. Proporsional narxni hisoblaymiz (qolgan kunlar uchun)
    total_days = calendar.monthrange(today.year, today.month)[1]
    final_price = calculate_proportional_price(full_monthly_price, today.day, total_days)

    if final_price <= 0:
        return

    # 5. Kategoriya va Kassa
    category, _ = TransactionCategory.objects.get_or_create(
        organization=org,
        name="Kurs to'lovi (Oylik avtomat)",
        defaults={'transaction_type': 'income'}
    )

    system_user, virtual_account = get_system_user_and_account(org)
    if not virtual_account:
        return

    # 6. Tranzaksiya yaratamiz (monthly_fee - kassaga ta'sir qilmaydi)
    remaining_days = total_days - today.day + 1
    description = build_monthly_fee_description(
        group,
        billing_month,
        final_price,
        suffix=(
            f"to'lov (Oy o'rtasida qo'shildi: {remaining_days}/{total_days} kun, "
            f"to'liq narx: {full_monthly_price:,.0f} UZS)"
        ),
    )

    new_trans = Transaction(
        organization=org,
        account=virtual_account,
        category=category,
        student=student,
        amount=final_price,
        transaction_type='monthly_fee',
        status='confirmed',
        created_by=system_user or student,
        confirmed_by=system_user or student,
        confirmed_at=timezone.now(),
        description=description,
    )
    new_trans.is_auto_billing = True
    new_trans.save()

    MonthlyFeeCharge.objects.create(
        organization=org,
        billing_month=billing_month,
        student=student,
        group=group,
        transaction=new_trans,
        amount=final_price,
        charge_source='auto_mid_month',
        charged_by=system_user or student,
        charged_at=timezone.now(),
        description=description,
    )
    # Balans signal orqali avtomatik kamayadi
