import logging
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.education.models import GroupStudent
from apps.finance.models import Transaction, TransactionCategory, Account, MonthlyFeeCharge, MonthlyFeeLog
from apps.finance.services import (
    _collect_legacy_monthly_fee_rows,
    _get_legacy_monthly_fee_amount,
    build_monthly_fee_description,
    calculate_price_with_bonus,
)
from apps.users.models import User
from apps.organizations.models import Organization

class Command(BaseCommand):
    help = "Barcha faol o'quvchilardan joriy oy uchun TO'LIQ OYLIK to'lovni OPTIMAL (bulk) shaklda yechish."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help="Oy boshida bo'lmasa ham majburlab ishga tushirish (test maqsadida)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        today = date.today()
        billing_month = date(today.year, today.month, 1)
        is_force = options['force']

        if today.day != 1 and not is_force:
            self.stdout.write(self.style.WARNING(
                "Bugun oyning boshi emas. Skript to'xtatildi. (--force qo'shing)"
            ))
            return

        self.stdout.write(self.style.WARNING(f"\n=== OPTIMAL OYLIK TO'LOV YECHISH (BULK) ({billing_month.strftime('%Y-%m')}) ==="))

        for org in Organization.objects.all():
            self._process_organization(org, billing_month, today, is_force)

        self.stdout.write(self.style.SUCCESS("\nBarcha tashkilotlar uchun jarayon yakunlandi."))

    def _process_organization(self, org, billing_month, today, is_force):
        # Tashkilot uchun log olamiz
        log, _ = MonthlyFeeLog.objects.get_or_create(
            organization=org,
            billing_month=billing_month,
            defaults={'is_processed': False}
        )

        if log.is_processed and not is_force:
            self.stdout.write(self.style.SUCCESS(
                f"[{org.name}] {billing_month} oyi uchun allaqachon yechildi."
            ))
            return

        # Faol o'quvchilarni guruh-student bog'lamasi orqali topamiz
        active_gs = list(GroupStudent.objects.filter(
            group__organization=org,
            status='active',
            student__role='student'
        ).select_related('group__course', 'student'))

        if not active_gs:
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

        transactions_to_create = []
        charges_payload = []
        students_to_update = {}
        total_amount = Decimal('0')
        billed_students = set()
        existing_charge_map = {
            (charge.organization_id, charge.student_id, charge.group_id): charge
            for charge in MonthlyFeeCharge.objects.filter(
                organization=org,
                billing_month=billing_month,
            )
        }
        legacy_rows = _collect_legacy_monthly_fee_rows(
            billing_month,
            [gs.student_id for gs in active_gs],
        )

        self.stdout.write(f"\n[{org.name}] hisoblanmoqda...")

        for gs in active_gs:
            student = gs.student
            group = gs.group
            course = group.course

            base_price = course.price if course.price > 0 else Decimal('0')
            if base_price == 0:
                continue

            # Bonusni hisobga olgan holda to'liq narxni hisoblaymiz
            full_price = calculate_price_with_bonus(base_price, student)
            if full_price <= 0:
                continue

            existing_charge = existing_charge_map.get((org.id, student.id, group.id))
            legacy_amount = _get_legacy_monthly_fee_amount(legacy_rows, student.id, group, billing_month)
            already_billed_amount = existing_charge.amount if existing_charge else legacy_amount
            amount_to_deduct = full_price - already_billed_amount
            if amount_to_deduct <= 0:
                continue

            desc = build_monthly_fee_description(group, billing_month, amount_to_deduct, suffix="avtomatik to'lov")

            # Tranzaksiyani tayyorlaymiz lekin bazaga SAQLAMAYMIZ (save() qilinmaydi)
            new_trans = Transaction(
                organization=org,
                account=virtual_account,
                category=category,
                student=student,
                amount=amount_to_deduct,
                transaction_type='monthly_fee',
                status='confirmed',
                created_by=system_user or student,
                confirmed_by=system_user or student,
                confirmed_at=timezone.now(),
                description=desc,
            )
            new_trans.is_auto_billing = True
            
            transactions_to_create.append(new_trans)
            charges_payload.append({
                'student': student,
                'group': group,
                'amount': amount_to_deduct,
                'existing_charge': existing_charge,
                'new_total_amount': already_billed_amount + amount_to_deduct,
                'description': desc,
            })
            
            # Student oldin ham darsga qatnashayotgan bo'lsa (yana bir xil student bir necha guruhda bo'lishi mumkin)
            if student.id not in students_to_update:
                students_to_update[student.id] = student
                
            # Xotirada student balansidan summani ayiramiz
            students_to_update[student.id].balance -= amount_to_deduct
            
            total_amount += amount_to_deduct
            billed_students.add(student.id)

        # Bulk amalga oshirish: bu signals larni trigger qilmaydi, demak balansni ham ikki martalab manfiy tushirmaydi.
        if transactions_to_create:
            # Barcha tranzaksiyalar bitta so'rovda saqlanadi
            created_transactions = Transaction.objects.bulk_create(transactions_to_create, batch_size=500)
            
            # Xotiradagi (yangilangan balansli) hamma userlarni bitta so'rovda saqlaymiz
            users_list = list(students_to_update.values())
            User.objects.bulk_update(users_list, ['balance'], batch_size=500)
            charges_to_create = []
            charges_to_update = []
            for index, payload in enumerate(charges_payload):
                created_transaction = created_transactions[index] if getattr(created_transactions[index], 'pk', None) else None
                if payload['existing_charge']:
                    charge = payload['existing_charge']
                    charge.transaction = created_transaction or charge.transaction
                    charge.amount = payload['new_total_amount']
                    charge.charge_source = 'auto_month_start'
                    charge.charged_by = system_user or payload['student']
                    charge.charged_at = timezone.now()
                    charge.description = payload['description']
                    charges_to_update.append(charge)
                else:
                    charges_to_create.append(
                        MonthlyFeeCharge(
                            organization=org,
                            billing_month=billing_month,
                            student=payload['student'],
                            group=payload['group'],
                            transaction=created_transaction,
                            amount=payload['new_total_amount'],
                            charge_source='auto_month_start',
                            charged_by=system_user or payload['student'],
                            charged_at=timezone.now(),
                            description=payload['description'],
                        )
                    )
            if charges_to_create:
                MonthlyFeeCharge.objects.bulk_create(charges_to_create, batch_size=500)
            if charges_to_update:
                MonthlyFeeCharge.objects.bulk_update(
                    charges_to_update,
                    ['transaction', 'amount', 'charge_source', 'charged_by', 'charged_at', 'description'],
                    batch_size=500,
                )

            self.stdout.write(self.style.SUCCESS(
                f"  -> {len(billed_students)} ta o'quvchidan (jami {len(transactions_to_create)} marta) {total_amount:,.0f} UZS bittada yechildi."
            ))
            
            # Log jadvalida ma'lumotlarni yangilab qo'yamiz
            log.is_processed = True
            log.processed_at = timezone.now()
            log.total_students_billed = (log.total_students_billed or 0) + len(billed_students)
            log.total_amount_billed = (log.total_amount_billed or Decimal('0')) + total_amount
            log.save(update_fields=['is_processed', 'processed_at', 'total_students_billed', 'total_amount_billed'])

        else:
            self.stdout.write(self.style.WARNING(f"[{org.name}] Yechish uchun qarzdorliklar topilmadi."))
