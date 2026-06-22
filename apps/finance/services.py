from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_UP

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.education.models import GroupStudent
from apps.finance.models import (
    Account,
    CashSubmission,
    MonthlyFeeCharge,
    MonthlyFeeLog,
    MonthlyFeeRun,
    Transaction,
    TransactionCategory,
)
from apps.users.models import User

MONTHLY_FEE_CATEGORY_NAME = "Kurs to'lovi (Oylik avtomat)"
MONTHLY_FEE_RUN_STATUS_FIELDS = [
    'status',
    'total_students_processed',
    'total_charges_created',
    'skipped_existing_count',
    'total_amount_deducted',
    'notes',
    'summary',
]


def calculate_price_with_bonus(base_price, student):
    """
    Kurs narxidan bonusni ayirib, yakuniy narxni qaytaradi.
    Avval foiz bonus, keyin summa bonus chegiriladi.
    """
    final_price = base_price

    if student.bonus_percentage > 0:
        final_price = final_price * (1 - (Decimal(student.bonus_percentage) / Decimal(100)))

    if student.bonus_amount > 0:
        final_price = max(Decimal('0'), final_price - student.bonus_amount)

    return final_price.quantize(Decimal('1'), rounding=ROUND_UP)


def normalize_billing_month(value=None):
    """
    Billing oyni har doim YYYY-MM-01 ko'rinishiga olib keladi.
    """
    if value is None:
        value = timezone.localdate()

    if isinstance(value, datetime):
        value = value.date()

    if isinstance(value, str):
        cleaned = value.strip()
        if len(cleaned) == 7:
            cleaned = f"{cleaned}-01"
        value = date.fromisoformat(cleaned)

    if not isinstance(value, date):
        raise ValidationError("Billing oy noto'g'ri formatda yuborildi.")

    return value.replace(day=1)


def verify_user_password(user, password, request=None):
    """
    Muhim amal oldidan foydalanuvchining parolini qayta tasdiqlaydi.
    """
    if not password:
        return False

    authenticated_user = authenticate(request, username=user.phone, password=password)
    if authenticated_user and authenticated_user.pk == user.pk:
        return True

    authenticated_user = authenticate(request, phone=user.phone, password=password)
    if authenticated_user and authenticated_user.pk == user.pk:
        return True

    return user.check_password(password)


def build_monthly_fee_description(group, billing_month, amount, suffix='kurs to\'lovi'):
    return (
        f"[MF {billing_month:%Y-%m} G{group.id}] "
        f"{group.name} - {billing_month:%Y-%m} oyi uchun {suffix} "
        f"({amount:,.0f} UZS)"
    )


def _get_monthly_fee_category(org):
    return TransactionCategory.objects.get_or_create(
        organization=org,
        name=MONTHLY_FEE_CATEGORY_NAME,
        defaults={'transaction_type': 'income'},
    )[0]


def _get_fee_account(org):
    return Account.objects.filter(organization=org, is_deleted=False).order_by('id').first()


def _get_system_user(org, fallback_user=None):
    return (
        User.objects.filter(role='super_admin', organization=org).first()
        or User.objects.filter(role='super_admin').first()
        or fallback_user
    )


def _collect_legacy_monthly_fee_rows(billing_month, student_ids):
    """
    Yangi charge jurnali hali bo'lmagan eski yozuvlarni ham takroriy yechishdan himoya qiladi.
    """
    if not student_ids:
        return {}

    rows_map = defaultdict(list)
    tx_rows = Transaction.objects.filter(
        student_id__in=student_ids,
        transaction_type='monthly_fee',
        status='confirmed',
        created_at__year=billing_month.year,
        created_at__month=billing_month.month,
    ).values_list('student_id', 'description', 'amount')

    for student_id, description, amount in tx_rows:
        rows_map[student_id].append((description or '', amount or Decimal('0')))

    return rows_map


def _get_legacy_monthly_fee_amount(legacy_rows, student_id, group, billing_month):
    prefix = f"{group.name} - {billing_month:%Y-%m} oyi uchun"
    marker = f"[MF {billing_month:%Y-%m} G{group.id}]"
    total = Decimal('0')
    for description, amount in legacy_rows.get(student_id, []):
        if description.startswith(marker) or description.startswith(prefix):
            total += amount
    return total


def _ensure_monthly_log_state(org, billing_month, processed_at=None):
    charge_stats = MonthlyFeeCharge.objects.filter(
        organization=org,
        billing_month=billing_month,
    ).aggregate(
        total_students=Count('student', distinct=True),
        total_amount=Sum('amount'),
    )

    log, _ = MonthlyFeeLog.objects.get_or_create(
        organization=org,
        billing_month=billing_month,
        defaults={'is_processed': False},
    )
    log.is_processed = True
    log.processed_at = processed_at or timezone.now()
    log.total_students_billed = charge_stats['total_students'] or 0
    log.total_amount_billed = charge_stats['total_amount'] or Decimal('0')
    log.save(update_fields=['is_processed', 'processed_at', 'total_students_billed', 'total_amount_billed'])


def invalidate_dashboard_cache():
    for user_id in User.objects.filter(role='super_admin', is_active=True).values_list('id', flat=True):
        cache.delete(f"dashboard:super_admin:{user_id}:weekly")
        cache.delete(f"dashboard:super_admin:{user_id}:monthly")


def _build_monthly_fee_transaction(*, org, account, category, student, group, amount, actor, description):
    return Transaction(
        organization=org,
        account=account,
        category=category,
        student=student,
        amount=amount,
        transaction_type='monthly_fee',
        status='confirmed',
        created_by=actor or student,
        confirmed_by=actor or student,
        confirmed_at=timezone.now(),
        description=description,
    )


def _finalize_run(run, result):
    run.status = result['status']
    run.total_students_processed = result['total_students_processed']
    run.total_charges_created = result['total_charges_created']
    run.skipped_existing_count = result['skipped_existing_count']
    run.total_amount_deducted = result['total_amount_deducted']
    run.notes = result.get('notes', '')
    run.summary = result.get('summary', {})
    run.save(update_fields=MONTHLY_FEE_RUN_STATUS_FIELDS)
    return run


@transaction.atomic
def reset_all_student_balances(*, triggered_by, password, request=None):
    """
    Super admin barcha o'quvchilar balansini 0 ga tushirishi uchun xavfsiz bulk amal.
    """
    if triggered_by.role != 'super_admin':
        raise ValidationError("Bu amal faqat super admin uchun.")

    if not verify_user_password(triggered_by, password, request=request):
        raise ValidationError("Parol noto'g'ri. Qayta urinib ko'ring.")

    student_qs = User.objects.filter(role='student', is_deleted=False)
    total_students = student_qs.count()
    balances_qs = student_qs.exclude(balance=0)
    stats = balances_qs.aggregate(
        students_with_balance=Count('id'),
        debt_amount=Sum('balance', filter=Q(balance__lt=0)),
        credit_amount=Sum('balance', filter=Q(balance__gt=0)),
        net_balance=Sum('balance'),
    )

    reset_at = timezone.now()
    updated_count = balances_qs.update(balance=Decimal('0'), updated_at=reset_at)
    result = {
        'total_students': total_students,
        'updated_count': updated_count,
        'students_with_balance': stats['students_with_balance'] or 0,
        'debt_amount': abs(stats['debt_amount'] or Decimal('0')),
        'credit_amount': stats['credit_amount'] or Decimal('0'),
        'net_balance': stats['net_balance'] or Decimal('0'),
        'reset_at': reset_at,
    }

    try:
        from apps.core.audit import log_user_action

        log_user_action(
            triggered_by,
            'UPDATE',
            'StudentBalanceReset',
            object_repr="Barcha o'quvchilar balansini 0 qilish",
            changes={
                'total_students': result['total_students'],
                'updated_count': result['updated_count'],
                'debt_amount': str(result['debt_amount']),
                'credit_amount': str(result['credit_amount']),
                'net_balance': str(result['net_balance']),
                'reset_at': result['reset_at'].isoformat(),
            },
            request=request,
        )
    except Exception:
        pass

    invalidate_dashboard_cache()
    return result


@transaction.atomic
def confirm_transaction(transaction_id, user):
    """
    Tranzaksiyani xavfsiz tasdiqlash.
    Bazaviy qoidalar:
    1. Tranzaksiya qulflanadi (select_for_update) - bir vaqtda ikki marta bosilmasligi uchun.
    2. Status 'pending' bo'lsagina ishlaydi.
    3. Balanslar signal orqali atomik tarzda yangilanadi (signals.py).
    """
    try:
        tx = Transaction.objects.select_for_update().get(id=transaction_id)
    except Transaction.DoesNotExist:
        raise ValidationError("Tranzaksiya topilmadi.")

    if tx.status == 'confirmed':
        return tx

    if tx.transaction_type in ['expense', 'salary', 'refund']:
        tx.account.refresh_from_db()
        if tx.account.balance < tx.amount:
            raise ValidationError(f"Kassada mablag' yetarli emas! Mavjud: {tx.account.balance}")

    tx.status = 'confirmed'
    tx.confirmed_by = user
    tx.confirmed_at = timezone.now()
    tx.receipt_verified = True
    tx.receipt_verified_by = user
    tx.receipt_verified_at = timezone.now()
    tx.save()

    return tx


@transaction.atomic
def approve_cash_submission(submission_id, user):
    """
    Kassa topshirishni tasdiqlash.
    Admin kassasidan asosiy kassaga pul o'tkazish.
    """
    try:
        submission = CashSubmission.objects.select_for_update().get(id=submission_id)
    except CashSubmission.DoesNotExist:
        raise ValidationError("Topshirish topilmadi.")

    if submission.status != 'pending':
        raise ValidationError("Bu topshirish allaqachon ko'rib chiqilgan.")

    net_amount = submission.net_amount
    transfer_amount = net_amount

    if transfer_amount > 0:
        Transaction.objects.create(
            organization=submission.organization,
            account=submission.main_account,
            amount=transfer_amount,
            transaction_type='transfer',
            description=(
                f"Kassa topshirish: {submission.admin_user.get_full_name()} "
                f"({submission.get_period_type_display()}: {submission.period_start} - {submission.period_end})"
            ),
            status='confirmed',
            created_by=submission.admin_user,
            confirmed_by=user,
            confirmed_at=timezone.now(),
            payment_method='cash',
        )

    submission.status = 'approved'
    submission.approved_by = user
    submission.approved_at = timezone.now()
    submission.save()

    try:
        from apps.automation.services import create_system_notification

        create_system_notification(
            recipient=submission.admin_user,
            title="Kassa topshirish tasdiqlandi",
            message=(
                f"Sizning {submission.period_start.strftime('%d.%m.%Y')} - "
                f"{submission.period_end.strftime('%d.%m.%Y')} oralig'idagi "
                f"kassa topshirishingiz tasdiqlandi. "
                f"Sof summa: {net_amount:,.0f} so'm. "
                f"Tasdiqlagan: {user.get_full_name()}"
            ),
            notification_type='system',
        )
    except Exception:
        pass

    return submission


def execute_manual_monthly_fee_run(*, triggered_by, billing_month, run_type, password, target_student=None, request=None):
    """
    Super admin uchun qo'lda kurs puli yechish jarayonini ishga tushiradi.
    """
    if triggered_by.role != 'super_admin':
        raise ValidationError("Bu amal faqat super admin uchun.")

    if run_type not in {'single', 'bulk'}:
        raise ValidationError("Yechish turi noto'g'ri tanlandi.")

    if run_type == 'single' and target_student is None:
        raise ValidationError("Bitta yechish uchun o'quvchini tanlang.")

    billing_month = normalize_billing_month(billing_month)
    if not verify_user_password(triggered_by, password, request=request):
        raise ValidationError("Parol noto'g'ri. Qayta urinib ko'ring.")

    run = MonthlyFeeRun.objects.create(
        organization=triggered_by.organization or getattr(target_student, 'organization', None),
        billing_month=billing_month,
        run_type=run_type,
        triggered_by=triggered_by,
        target_student=target_student,
        password_verified_at=timezone.now(),
        triggered_at=timezone.now(),
        status='completed',
    )

    try:
        if run_type == 'single':
            result = deduct_monthly_fees_for_student(
                student=target_student,
                billing_month=billing_month,
                triggered_by=triggered_by,
                run=run,
            )
        else:
            result = deduct_monthly_fees_bulk(
                billing_month=billing_month,
                triggered_by=triggered_by,
                run=run,
            )
    except Exception as exc:
        run.status = 'failed'
        run.notes = str(exc)
        run.summary = {'error': str(exc)}
        run.save(update_fields=['status', 'notes', 'summary'])
        raise

    _finalize_run(run, result)

    try:
        from apps.core.audit import log_user_action

        log_user_action(
            triggered_by,
            'CREATE',
            'MonthlyFeeRun',
            run.id,
            str(run),
            changes={
                'billing_month': billing_month.isoformat(),
                'run_type': run_type,
                'status': run.status,
                'charges_created': run.total_charges_created,
                'amount': float(run.total_amount_deducted),
            },
            request=request,
        )
    except Exception:
        pass

    invalidate_dashboard_cache()
    return run


@transaction.atomic
def deduct_monthly_fees_for_student(*, student, billing_month, triggered_by, run=None):
    enrollments = list(
        GroupStudent.objects.filter(
            student=student,
            status='active',
            group__status='active',
            group__is_deleted=False,
        ).select_related('student', 'group', 'group__course', 'group__organization')
    )

    if not enrollments:
        return {
            'status': 'skipped',
            'total_students_processed': 1,
            'total_charges_created': 0,
            'skipped_existing_count': 0,
            'total_amount_deducted': Decimal('0'),
            'notes': "Tanlangan o'quvchida faol guruh topilmadi.",
            'summary': {'student_id': student.id, 'charges': []},
        }

    existing_charge_map = {
        (charge.organization_id, charge.student_id, charge.group_id): charge
        for charge in MonthlyFeeCharge.objects.filter(
            billing_month=billing_month,
            student=student,
            group_id__in=[enrollment.group_id for enrollment in enrollments],
        )
    }
    legacy_rows = _collect_legacy_monthly_fee_rows(billing_month, [student.id])

    total_amount = Decimal('0')
    created_count = 0
    skipped_existing = 0
    missing_configuration = []
    created_details = []

    for enrollment in enrollments:
        group = enrollment.group
        org = group.organization or student.organization
        if not org:
            missing_configuration.append(f"{group.name}: tashkilot topilmadi")
            continue

        base_price = group.course.price if group.course and group.course.price > 0 else Decimal('0')
        if base_price <= 0:
            continue

        full_amount = calculate_price_with_bonus(base_price, student)
        if full_amount <= 0:
            continue

        charge_key = (org.id, student.id, group.id)
        existing_charge = existing_charge_map.get(charge_key)
        legacy_amount = _get_legacy_monthly_fee_amount(legacy_rows, student.id, group, billing_month)
        already_billed_amount = existing_charge.amount if existing_charge else legacy_amount
        amount = full_amount - already_billed_amount
        if amount <= 0:
            skipped_existing += 1
            continue

        account = _get_fee_account(org)
        if not account:
            missing_configuration.append(f"{group.name}: kassa topilmadi")
            continue

        category = _get_monthly_fee_category(org)
        actor = _get_system_user(org, fallback_user=triggered_by)
        description = build_monthly_fee_description(group, billing_month, amount)

        new_transaction = _build_monthly_fee_transaction(
            org=org,
            account=account,
            category=category,
            student=student,
            group=group,
            amount=amount,
            actor=actor,
            description=description,
        )
        new_transaction.is_auto_billing = True
        new_transaction.save()

        if existing_charge:
            existing_charge.run = run or existing_charge.run
            existing_charge.transaction = new_transaction
            existing_charge.amount = already_billed_amount + amount
            existing_charge.charge_source = 'manual_single'
            existing_charge.charged_by = triggered_by
            existing_charge.charged_at = timezone.now()
            existing_charge.description = description
            existing_charge.save(
                update_fields=[
                    'run',
                    'transaction',
                    'amount',
                    'charge_source',
                    'charged_by',
                    'charged_at',
                    'description',
                ]
            )
        else:
            MonthlyFeeCharge.objects.create(
                organization=org,
                billing_month=billing_month,
                run=run,
                student=student,
                group=group,
                transaction=new_transaction,
                amount=already_billed_amount + amount,
                charge_source='manual_single',
                charged_by=triggered_by,
                charged_at=timezone.now(),
                description=description,
            )

        total_amount += amount
        created_count += 1
        created_details.append({
            'student_id': student.id,
            'group_id': group.id,
            'group_name': group.name,
            'amount': float(amount),
            'organization_id': org.id,
        })

    status = 'completed'
    if created_count == 0 and skipped_existing > 0 and not missing_configuration:
        status = 'skipped'
    elif missing_configuration and created_count > 0:
        status = 'partial'
    elif missing_configuration and created_count == 0:
        status = 'failed'

    notes = f"{student.get_full_name()} uchun {created_count} ta kursdan yechildi."
    if skipped_existing:
        notes += f" {skipped_existing} tasi oldin yechilgan."
    if missing_configuration:
        notes += " Ayrim guruhlar o'tkazib yuborildi."

    return {
        'status': status,
        'total_students_processed': 1,
        'total_charges_created': created_count,
        'skipped_existing_count': skipped_existing,
        'total_amount_deducted': total_amount,
        'notes': notes,
        'summary': {
            'student_id': student.id,
            'student_name': student.get_full_name(),
            'charges': created_details,
            'missing_configuration': missing_configuration,
        },
    }


@transaction.atomic
def deduct_monthly_fees_bulk(*, billing_month, triggered_by, run=None):
    enrollments = list(
        GroupStudent.objects.filter(
            status='active',
            group__status='active',
            group__is_deleted=False,
            student__role='student',
            student__is_active=True,
            student__is_deleted=False,
        ).select_related('student', 'group', 'group__course', 'group__organization')
    )

    if not enrollments:
        return {
            'status': 'skipped',
            'total_students_processed': 0,
            'total_charges_created': 0,
            'skipped_existing_count': 0,
            'total_amount_deducted': Decimal('0'),
            'notes': "Faol o'quvchilar topilmadi.",
            'summary': {'organizations': []},
        }

    student_ids = sorted({enrollment.student_id for enrollment in enrollments})
    group_ids = sorted({enrollment.group_id for enrollment in enrollments})
    existing_charge_map = {
        (charge.organization_id, charge.student_id, charge.group_id): charge
        for charge in MonthlyFeeCharge.objects.filter(
            billing_month=billing_month,
            student_id__in=student_ids,
            group_id__in=group_ids,
        )
    }
    legacy_rows = _collect_legacy_monthly_fee_rows(billing_month, student_ids)

    fee_context = {}
    now = timezone.now()
    transactions_to_create = []
    charges_payload = []
    students_to_update = {}
    processed_students = set()
    skipped_existing = 0
    total_amount = Decimal('0')
    per_org_summary = defaultdict(lambda: {
        'organization_id': None,
        'organization_name': '',
        'org': None,
        'created': 0,
        'skipped_existing': 0,
        'amount': Decimal('0'),
        'issues': [],
    })

    for enrollment in enrollments:
        student = enrollment.student
        group = enrollment.group
        org = group.organization or student.organization
        processed_students.add(student.id)

        if not org:
            continue

        org_summary = per_org_summary[org.id]
        org_summary['organization_id'] = org.id
        org_summary['organization_name'] = org.name
        org_summary['org'] = org

        base_price = group.course.price if group.course and group.course.price > 0 else Decimal('0')
        if base_price <= 0:
            continue

        full_amount = calculate_price_with_bonus(base_price, student)
        if full_amount <= 0:
            continue

        charge_key = (org.id, student.id, group.id)
        existing_charge = existing_charge_map.get(charge_key)
        legacy_amount = _get_legacy_monthly_fee_amount(legacy_rows, student.id, group, billing_month)
        already_billed_amount = existing_charge.amount if existing_charge else legacy_amount
        amount = full_amount - already_billed_amount
        if amount <= 0:
            skipped_existing += 1
            org_summary['skipped_existing'] += 1
            continue

        if org.id not in fee_context:
            fee_context[org.id] = {
                'account': _get_fee_account(org),
                'category': _get_monthly_fee_category(org),
                'actor': _get_system_user(org, fallback_user=triggered_by),
                'org': org,
            }

        context = fee_context[org.id]
        if not context['account']:
            org_summary['issues'].append("Kassa topilmadi")
            continue

        description = build_monthly_fee_description(group, billing_month, amount)
        transaction_obj = _build_monthly_fee_transaction(
            org=org,
            account=context['account'],
            category=context['category'],
            student=student,
            group=group,
            amount=amount,
            actor=context['actor'],
            description=description,
        )
        transaction_obj.is_auto_billing = True
        transactions_to_create.append(transaction_obj)
        charges_payload.append({
            'organization': org,
            'student': student,
            'group': group,
            'amount': amount,
            'new_total_amount': already_billed_amount + amount,
            'existing_charge': existing_charge,
            'description': description,
        })

        if student.id not in students_to_update:
            students_to_update[student.id] = student
        students_to_update[student.id].balance -= amount

        total_amount += amount
        org_summary['created'] += 1
        org_summary['amount'] += amount

    if transactions_to_create:
        created_transactions = Transaction.objects.bulk_create(transactions_to_create, batch_size=500)
        if students_to_update:
            User.objects.bulk_update(list(students_to_update.values()), ['balance'], batch_size=500)

        charges_to_create = []
        charges_to_update = []
        for index, payload in enumerate(charges_payload):
            created_transaction = created_transactions[index] if index < len(created_transactions) else None
            if payload['existing_charge']:
                charge = payload['existing_charge']
                charge.run = run or charge.run
                charge.transaction = created_transaction if getattr(created_transaction, 'pk', None) else charge.transaction
                charge.amount = payload['new_total_amount']
                charge.charge_source = 'manual_bulk'
                charge.charged_by = triggered_by
                charge.charged_at = now
                charge.description = payload['description']
                charges_to_update.append(charge)
            else:
                charges_to_create.append(
                    MonthlyFeeCharge(
                        organization=payload['organization'],
                        billing_month=billing_month,
                        run=run,
                        student=payload['student'],
                        group=payload['group'],
                        transaction=created_transaction if getattr(created_transaction, 'pk', None) else None,
                        amount=payload['new_total_amount'],
                        charge_source='manual_bulk',
                        charged_by=triggered_by,
                        charged_at=now,
                        description=payload['description'],
                    )
                )

        if charges_to_create:
            MonthlyFeeCharge.objects.bulk_create(charges_to_create, batch_size=500)
        if charges_to_update:
            MonthlyFeeCharge.objects.bulk_update(
                charges_to_update,
                ['run', 'transaction', 'amount', 'charge_source', 'charged_by', 'charged_at', 'description'],
                batch_size=500,
            )

        for org_data in per_org_summary.values():
            if org_data['org'] and (org_data['created'] > 0 or org_data['skipped_existing'] > 0):
                _ensure_monthly_log_state(org_data['org'], billing_month, processed_at=now)

    failed_orgs = [data for data in per_org_summary.values() if data['issues'] and data['created'] == 0]
    partial_orgs = [data for data in per_org_summary.values() if data['issues'] and data['created'] > 0]

    status = 'completed'
    if not transactions_to_create and skipped_existing > 0 and not failed_orgs:
        status = 'skipped'
    elif failed_orgs and transactions_to_create:
        status = 'partial'
    elif failed_orgs and not transactions_to_create:
        status = 'failed'
    elif partial_orgs:
        status = 'partial'

    organization_rows = []
    for data in per_org_summary.values():
        organization_rows.append({
            'organization_id': data['organization_id'],
            'organization_name': data['organization_name'],
            'created': data['created'],
            'skipped_existing': data['skipped_existing'],
            'amount': float(data['amount']),
            'issues': data['issues'],
        })

    notes = (
        f"{len(processed_students)} ta o'quvchi tekshirildi, "
        f"{len(transactions_to_create)} ta kurs uchun yechish yaratildi."
    )
    if skipped_existing:
        notes += f" {skipped_existing} ta kurs oldin yechilgan."

    return {
        'status': status,
        'total_students_processed': len(processed_students),
        'total_charges_created': len(transactions_to_create),
        'skipped_existing_count': skipped_existing,
        'total_amount_deducted': total_amount,
        'notes': notes,
        'summary': {
            'organizations': organization_rows,
            'billing_month': billing_month.isoformat(),
        },
    }
