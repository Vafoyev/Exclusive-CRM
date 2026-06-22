import logging
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.education.models import GroupStudent
from apps.finance.models import Transaction, TransactionCategory, Account, MonthlyFeeCharge, MonthlyFeeLog
from apps.finance.services import (
    _collect_legacy_monthly_fee_rows,
    _get_legacy_monthly_fee_amount,
    build_monthly_fee_description,
)
from apps.users.models import User
from apps.organizations.models import Organization
from apps.education.signals import calculate_price_with_bonus

class Command(BaseCommand):
    help = "Barcha faol o'quvchilardan TO'LIQ OYLIK to'lovni aniq yechib olish. Agar oldinroq proporsional yechilgan bo'lsa, yetmagan qismini yechadi."

    @transaction.atomic
    def handle(self, *args, **options):
        today = date.today()
        billing_month = date(today.year, today.month, 1)

        self.stdout.write(self.style.WARNING(f"\n=== TO'LIQ OY UCHUN MAJBURIY YECHISH ({billing_month.strftime('%Y-%m')}) ==="))

        for org in Organization.objects.all():
            self._process_organization(org, billing_month, today)

        self.stdout.write(self.style.SUCCESS("\nBarcha tashkilotlar uchun to'liq oylik yechish yakunlandi."))

    def _process_organization(self, org, billing_month, today):
        """Bitta tashkilot uchun oylik to'lovlarni yetmagan qismini yechish."""

        # Faol guruh-studentlar
        active_gs = GroupStudent.objects.filter(
            group__organization=org,
            status='active',
            student__role='student'
        ).select_related('group__course', 'student')

        if not active_gs.exists():
            return

        category, _ = TransactionCategory.objects.get_or_create(
            organization=org,
            name="Kurs to'lovi (Oylik avtomat)",
            defaults={'transaction_type': 'income'}
        )

        virtual_account = Account.objects.filter(organization=org).first()
        if not virtual_account:
            self.stdout.write(self.style.ERROR(f"[{org.name}] Kassa topilmadi. O'tkazib yuborildi."))
            return

        system_user = (
            User.objects.filter(role='super_admin', organization=org).first()
            or User.objects.filter(role='super_admin').first()
        )

        total_amount = Decimal('0')
        billed_count = 0
        existing_charge_map = {
            (charge.organization_id, charge.student_id, charge.group_id): charge
            for charge in MonthlyFeeCharge.objects.filter(
                organization=org,
                billing_month=billing_month,
            )
        }
        legacy_rows = _collect_legacy_monthly_fee_rows(
            billing_month,
            list(active_gs.values_list('student_id', flat=True)),
        )

        self.stdout.write(f"\n[{org.name}] tekshirilmoqda...")

        for gs in active_gs:
            student = gs.student
            group = gs.group
            course = group.course

            base_price = course.price if course.price > 0 else Decimal('0')
            if base_price == 0:
                continue

            # Bonusni chegirib TO'LIQ oylik narxni hisoblaymiz
            full_price = calculate_price_with_bonus(base_price, student)
            if full_price <= 0:
                continue

            # Shu oyni uchun shu guruhdan jami qancha yechilganini summasini hisoblaymiz
            existing_charge = existing_charge_map.get((org.id, student.id, group.id))
            legacy_amount = _get_legacy_monthly_fee_amount(legacy_rows, student.id, group, billing_month)
            billed_sum = existing_charge.amount if existing_charge else legacy_amount

            # Yetisheyotgan qismini hisoblaymiz (masalan proporsional yechilgan bo'lsa)
            remaining_price = full_price - billed_sum

            if remaining_price <= Decimal('0'):
                # Allaqachon to'liq oylik narx yechilgan bo'lsa teginmaymiz
                continue

            # Tranzaksiya yaratamiz (monthly_fee - faqat student balansidan kamayadi)
            new_trans = Transaction(
                organization=org,
                account=virtual_account,
                category=category,
                student=student,
                amount=remaining_price,
                transaction_type='monthly_fee',
                status='confirmed',
                created_by=system_user or student,
                confirmed_by=system_user or student,
                confirmed_at=timezone.now(),
                description=build_monthly_fee_description(
                    gs.group,
                    billing_month,
                    remaining_price,
                    suffix="to'liq to'lovgacha qolgan qismi",
                ),
            )
            new_trans.is_auto_billing = True
            new_trans.save()
            if existing_charge:
                existing_charge.transaction = new_trans
                existing_charge.amount = billed_sum + remaining_price
                existing_charge.charge_source = 'auto_month_start'
                existing_charge.charged_by = system_user or student
                existing_charge.charged_at = timezone.now()
                existing_charge.description = new_trans.description
                existing_charge.save(
                    update_fields=['transaction', 'amount', 'charge_source', 'charged_by', 'charged_at', 'description']
                )
            else:
                MonthlyFeeCharge.objects.create(
                    organization=org,
                    billing_month=billing_month,
                    student=student,
                    group=group,
                    transaction=new_trans,
                    amount=billed_sum + remaining_price,
                    charge_source='auto_month_start',
                    charged_by=system_user or student,
                    charged_at=timezone.now(),
                    description=new_trans.description,
                )

            total_amount += remaining_price
            billed_count += 1

            self.stdout.write(
                f"  -> {student.first_name} {student.last_name} ({group.name}): "
                f"-{remaining_price:,.0f} UZS qo'shimcha yechildi (To'liq qilingan narx: {full_price:,.0f})."
            )

        if billed_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f"[{org.name}] {billed_count} ta o'quvchidan jami {total_amount:,.0f} UZS yechildi."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"[{org.name}] Hamma o'quvchilardan to'liq oylik yechib olingan ekan."))

        # Log yozamiz
        log, _ = MonthlyFeeLog.objects.get_or_create(
            organization=org,
            billing_month=billing_month,
            defaults={'is_processed': True, 'total_students_billed': billed_count, 'total_amount_billed': total_amount}
        )
        if not getattr(log, 'is_new', False):
            log.is_processed = True
            log.processed_at = timezone.now()
            # Billed va amount ustiga qo'shib qo'yamiz
            log.total_students_billed = (log.total_students_billed or 0) + billed_count
            log.total_amount_billed = (log.total_amount_billed or Decimal('0')) + total_amount
            log.save(update_fields=['is_processed', 'processed_at', 'total_students_billed', 'total_amount_billed'])
