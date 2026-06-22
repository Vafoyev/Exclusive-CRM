"""
Administrator kassa kirim-chiqim va kassa topshirish viewlari.
Admin o'z kassasida kirim-chiqim qiladi, keyin super adminga topshiradi.
"""
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.db import transaction, DatabaseError
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from .models import Account, Transaction, TransactionCategory, CashSubmission
from .services import confirm_transaction as confirm_service
from apps.users.models import User
from apps.core.permissions import permission_required, check_permission
from apps.core.audit import log_user_action

logger = logging.getLogger(__name__)


def _get_or_create_admin_account(user, org):
    """Admin uchun shaxsiy kassani olish yoki yaratish."""
    account = Account.objects.filter(
        organization=org,
        name=f"Admin Kassa - {user.get_full_name()}",
        is_deleted=False,
    ).first()
    if not account:
        account = Account.objects.create(
            organization=org,
            name=f"Admin Kassa - {user.get_full_name()}",
            account_type='cash',
            balance=Decimal('0.00'),
        )
    return account


def _payment_method_queryset(queryset, method):
    return queryset.filter(payment_method__in=Transaction.payment_method_values(method))


def _payment_method_net_amount(queryset, method):
    method_qs = _payment_method_queryset(queryset, method)
    income = method_qs.filter(transaction_type='income').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    expense = method_qs.filter(transaction_type='expense').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    return income - expense


@login_required
@permission_required('admin_finance', 'view')
def admin_cash_dashboard(request):
    """Administrator kassasi - kirim chiqim dashboard."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    # Admin kassasidagi joriy sessiya tranzaksiyalari (topshirilmagan)
    transactions = Transaction.objects.filter(
        account=admin_account,
        is_deleted=False,
        cash_submission__isnull=True,
    ).select_related('category', 'student', 'created_by', 'confirmed_by', 'cash_submission').order_by('-created_at')[:50]

    # Statistika
    confirmed_txs = Transaction.objects.filter(
        account=admin_account,
        is_deleted=False,
        status='confirmed'
    )
    
    # Kassa topshirilgandan keyin barchasi 0 ga tushishi uchun
    # faqat topshirilmagan tranzaksiyalarni hisobga olamiz
    unsubmitted_txs = confirmed_txs.filter(cash_submission__isnull=True)
    
    total_income = unsubmitted_txs.filter(transaction_type='income').aggregate(t=Sum('amount'))['t'] or 0
    total_expense = unsubmitted_txs.filter(transaction_type='expense').aggregate(t=Sum('amount'))['t'] or 0

    # To'lov usuli bo'yicha balanslar (topshirilmagan tranzaksiyalar)
    balance_cash = _payment_method_net_amount(unsubmitted_txs, 'cash')
    balance_card = _payment_method_net_amount(unsubmitted_txs, 'card')
    balance_terminal = _payment_method_net_amount(unsubmitted_txs, 'terminal')

    # Kutilayotgan o'quvchi to'lovlari (barcha pending student payments)
    pending_qs = Transaction.objects.filter(
        is_deleted=False,
        status='pending',
        transaction_type='income',
        student__isnull=False,
    )
    if org:
        pending_qs = pending_qs.filter(organization=org)
    pending_student_payments = pending_qs.select_related(
        'student', 'account', 'category', 'created_by'
    ).order_by('-created_at')[:20]

    # Oxirgi topshirishlar
    try:
        submissions = list(CashSubmission.objects.filter(
            admin_user=user,
            is_deleted=False,
        ).order_by('-created_at')[:10])
    except DatabaseError as e:
        logger.error(f"CashSubmission so'rovida xatolik (dashboard): {e}")
        submissions = []

    # Joriy (topshirilmagan) umumiy balans
    net_balance = balance_cash + balance_card + balance_terminal

    context = {
        'admin_account': admin_account,
        'transactions': transactions,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': admin_account.balance,
        'net_balance': net_balance,
        'balance_cash': balance_cash,
        'balance_card': balance_card,
        'balance_terminal': balance_terminal,
        'submissions': submissions,
        'pending_student_payments': pending_student_payments,
        'pending_count': pending_student_payments.count(),
    }
    return render(request, 'finance/admin_cash/dashboard.html', context)


@login_required
@permission_required('admin_finance', 'create')
def admin_add_income(request):
    """Admin kassasiga kirim qo'shish."""
    from .forms import AdminCashTransactionForm
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    if request.method == 'POST':
        form = AdminCashTransactionForm(request.POST, organization=org, transaction_type='income')
        if form.is_valid():
            try:
                with transaction.atomic():
                    t = form.save(commit=False)
                    t.organization = org
                    t.account = admin_account
                    t.transaction_type = 'income'
                    t.created_by = user
                    t.status = 'pending'
                    t.save()
                    confirm_service(t.id, user)

                log_user_action(user, 'CREATE', 'Transaction', t.id, str(t), request=request)
                messages.success(request, "Kirim qo'shildi va darhol tasdiqlandi.")
                return redirect('finance:admin_cash_dashboard')
            except ValidationError as exc:
                form.add_error(None, exc.message)
    else:
        form = AdminCashTransactionForm(organization=org, transaction_type='income')

    return render(request, 'finance/admin_cash/transaction_form.html', {
        'form': form, 'title': 'Kirim', 'type': 'income'
    })


@login_required
@permission_required('admin_finance', 'create')
def admin_add_expense(request):
    """Admin kassasidan chiqim qo'shish."""
    from .forms import AdminCashTransactionForm
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    if request.method == 'POST':
        form = AdminCashTransactionForm(request.POST, organization=org, transaction_type='expense')
        if form.is_valid():
            try:
                with transaction.atomic():
                    t = form.save(commit=False)
                    t.organization = org
                    t.account = admin_account
                    t.transaction_type = 'expense'
                    t.created_by = user
                    t.status = 'pending'
                    t.save()
                    confirm_service(t.id, user)

                log_user_action(user, 'CREATE', 'Transaction', t.id, str(t), request=request)
                messages.success(request, "Chiqim qo'shildi va darhol tasdiqlandi.")
                return redirect('finance:admin_cash_dashboard')
            except ValidationError as exc:
                form.add_error(None, exc.message)
    else:
        form = AdminCashTransactionForm(organization=org, transaction_type='expense')

    return render(request, 'finance/admin_cash/transaction_form.html', {
        'form': form, 'title': 'Chiqim', 'type': 'expense'
    })


@login_required
@permission_required('admin_finance', 'view')
def admin_cash_history(request):
    """Admin kassasi tarixi."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    # Filters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    trans_type = request.GET.get('type', '')

    transactions = Transaction.objects.filter(
        account=admin_account,
        is_deleted=False,
    ).select_related('category', 'created_by', 'confirmed_by')

    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)
    if trans_type:
        transactions = transactions.filter(transaction_type=trans_type)

    transactions = transactions.order_by('-created_at')[:100]

    context = {
        'transactions': transactions,
        'admin_account': admin_account,
        'date_from': date_from,
        'date_to': date_to,
        'trans_type': trans_type,
    }
    return render(request, 'finance/admin_cash/history.html', context)


@login_required
@permission_required('admin_finance', 'create')
def admin_submit_cash(request):
    """Admin kassasini asosiy kassaga topshirish."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    # Asosiy kassani topish (admin kassasi bo'lmagan birinchi kassa)
    main_accounts = Account.objects.filter(
        organization=org,
        is_deleted=False,
    ).exclude(pk=admin_account.pk)

    if request.method == 'POST':
        main_account_id = request.POST.get('main_account')
        notes = request.POST.get('notes', '')
        payment_methods = request.POST.getlist('payment_methods')

        if not main_account_id:
            messages.error(request, "❌ Asosiy kassani tanlang!")
            return redirect('finance:admin_cash_dashboard')

        if not payment_methods:
            messages.error(request, "❌ Kamida bitta to'lov usulini tanlang!")
            return redirect('finance:admin_cash_dashboard')

        main_account = get_object_or_404(Account, pk=main_account_id, organization=org)
        normalized_methods = {Transaction.normalize_payment_method(method) for method in payment_methods}
        selected_method_values = []
        for method in normalized_methods:
            selected_method_values.extend(Transaction.payment_method_values(method))

        # Faqat bugungi kun uchun
        today = timezone.now().date()
        period_start = today
        period_end = today

        # TOPSHIRILMAGAN tranzaksiyalar (cash_submission yo'q bo'lganlar) - faqat tanlangan usullar bo'yicha
        unsubmitted_txs = Transaction.objects.filter(
            account=admin_account,
            is_deleted=False,
            status='confirmed',
            cash_submission__isnull=True,
            payment_method__in=tuple(dict.fromkeys(selected_method_values)),
        )

        total_income = unsubmitted_txs.filter(transaction_type='income').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_expense = unsubmitted_txs.filter(transaction_type='expense').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        
        # To'lov usuli bo'yicha tafsilotlarni hisoblash (faqat 3 ta tur)
        # Kirim - Chiqim hisoblash har bir usul uchun
        amount_cash = _payment_method_net_amount(unsubmitted_txs, 'cash') if 'cash' in normalized_methods else Decimal('0')
        amount_card = _payment_method_net_amount(unsubmitted_txs, 'card') if 'card' in normalized_methods else Decimal('0')
        amount_terminal = _payment_method_net_amount(unsubmitted_txs, 'terminal') if 'terminal' in normalized_methods else Decimal('0')

        # Tanlangan tranzaksiyalar yig'indisi
        net_amount = amount_cash + amount_card + amount_terminal

        if unsubmitted_txs.count() == 0 and net_amount <= 0:
            messages.warning(request, "⚠️ Tanlangan usullar bo'yicha topshirish uchun tranzaksiyalar yoki mablag' yo'q!")
            return redirect('finance:admin_cash_dashboard')

        try:
            with transaction.atomic():
                submission = CashSubmission.objects.create(
                    organization=org,
                    admin_user=user,
                    admin_account=admin_account,
                    main_account=main_account,
                    total_income=total_income,
                    total_expense=total_expense,
                    net_amount=net_amount,
                    amount_cash=amount_cash,
                    amount_card=amount_card,
                    amount_terminal=amount_terminal,
                    period_type='daily',
                    period_start=period_start,
                    period_end=period_end,
                    notes=notes,
                    status='pending',
                )

                # Barcha topshirilmagan tranzaksiyalarga cash_submission FK ni biriktirish
                unsubmitted_txs.update(cash_submission=submission)

                # Admin kassasi balansidan ayriladi
                admin_account.refresh_from_db()
                admin_account.balance -= net_amount
                admin_account.save(update_fields=['balance'])
        except DatabaseError as e:
            logger.error(f"Kassa topshirishda xatolik: {e}")
            messages.error(
                request,
                "❌ Kassa topshirishda xatolik yuz berdi. "
                "Ma'lumotlar bazasi migratsiyalarini tekshiring (python manage.py migrate)."
            )
            return redirect('finance:admin_cash_dashboard')

        log_user_action(user, 'CREATE', 'CashSubmission', submission.id, str(submission), request=request)

        # Super admin / owner larga bildirishnoma yuborish
        try:
            from apps.automation.services import create_system_notification
            admins = User.objects.filter(
                role__in=['super_admin', 'owner'],
                is_active=True,
            )
            if org:
                admins = admins.filter(organization=org)
            admins = admins.exclude(pk=user.pk)

            for admin in admins[:10]:
                create_system_notification(
                    recipient=admin,
                    title="Yangi kassa topshirish",
                    message=(
                        f"{user.get_full_name()} kassa topshirish so'rovini yubordi. "
                        f"Sana: {submission.period_start.strftime('%d.%m.%Y')}. "
                        f"Sof summa: {net_amount:,.0f} so'm"
                    ),
                    notification_type='system'
                )
        except Exception as e:
            logger.error(f"Kassa topshirish bildirishnomalarini yuborishda xatolik: {e}")

        messages.success(request, f"✅ Kassa topshirildi! Sof summa: {net_amount:,.0f} UZS.")
        return redirect('finance:admin_cash_dashboard')

    # Barcha topshirilmagan tranzaksiyalarni olish (balanslarni alohida ko'rsatish uchun)
    all_unsubmitted_txs = Transaction.objects.filter(
        account=admin_account,
        is_deleted=False,
        status='confirmed',
        cash_submission__isnull=True,
    )
    
    balance_cash = _payment_method_net_amount(all_unsubmitted_txs, 'cash')
    balance_card = _payment_method_net_amount(all_unsubmitted_txs, 'card')
    balance_terminal = _payment_method_net_amount(all_unsubmitted_txs, 'terminal')

    net_balance = balance_cash + balance_card + balance_terminal

    context = {
        'admin_account': admin_account,
        'main_accounts': main_accounts,
        'balance': net_balance,
        'balance_cash': balance_cash,
        'balance_card': balance_card,
        'balance_terminal': balance_terminal,
        'now': timezone.now().date(),
    }
    return render(request, 'finance/admin_cash/submit_cash.html', context)


# ============================================
# SUPER ADMIN / OWNER - Kassa topshirishlarni boshqarish
# ============================================

@login_required
def cash_submission_list(request):
    """Kassa topshirishlar ro'yxati (super admin / owner / admin)."""
    user = request.user
    # finance yoki admin_finance ruxsati bo'lishi kerak
    if not (check_permission(user, 'finance', 'view') or check_permission(user, 'admin_finance', 'view')):
        messages.error(request, "⛔ Sizda bu amalni bajarish huquqi yo'q!")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('dashboard')

    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    status_filter = request.GET.get('status', '')

    try:
        submissions = CashSubmission.objects.filter(is_deleted=False)
        if org:
            submissions = submissions.filter(organization=org)

        # Admin faqat o'z topshirishlarini ko'radi
        if user.role == 'admin' and not check_permission(user, 'finance', 'view'):
            submissions = submissions.filter(admin_user=user)

        if status_filter:
            submissions = submissions.filter(status=status_filter)

        submissions = list(submissions.select_related(
            'admin_user', 'admin_account', 'main_account', 'approved_by'
        ).order_by('-created_at')[:50])
    except DatabaseError as e:
        logger.error(f"CashSubmission so'rovida xatolik (list): {e}")
        submissions = []

    context = {
        'submissions': submissions,
        'status_filter': status_filter,
    }
    return render(request, 'finance/admin_cash/submission_list.html', context)


@login_required
@permission_required('finance', 'edit')
@require_POST
def approve_cash_submission(request, pk):
    """Kassa topshirishni tasdiqlash - pul asosiy kassaga o'tadi."""
    from .services import approve_cash_submission as approve_service
    try:
        approve_service(pk, request.user)
        messages.success(request, "Kassa topshirish tasdiqlandi. Pul asosiy kassaga o'tkazildi.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('finance:cash_submission_list')


@login_required
@permission_required('finance', 'edit')
@require_POST
def reject_cash_submission(request, pk):
    """Kassa topshirishni rad etish."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    qs = CashSubmission.objects.filter(is_deleted=False)
    if org:
        qs = qs.filter(organization=org)
    submission = get_object_or_404(qs, pk=pk)
    if submission.status != 'pending':
        messages.error(request, "Bu topshirish allaqachon ko'rib chiqilgan.")
        return redirect('finance:cash_submission_list')

    rejection_reason = request.POST.get('reason', '')

    with transaction.atomic():
        submission.status = 'rejected'
        submission.rejection_reason = rejection_reason
        submission.approved_by = request.user
        submission.approved_at = timezone.now()
        submission.save()

        # Admin kassasi balansini qaytarish (topshirish vaqtida 0 ga tushirilgan edi)
        if submission.net_amount != 0:
            admin_account = submission.admin_account
            admin_account.refresh_from_db()
            admin_account.balance += submission.net_amount
            admin_account.save(update_fields=['balance'])

    log_user_action(request.user, 'UPDATE', 'CashSubmission', submission.id,
                    f"Rad etildi: {submission}", request=request)

    # Admin ga bildirishnoma yuborish
    try:
        from apps.automation.services import create_system_notification
        reason_text = rejection_reason or "Ko\u2018rsatilmagan"
        create_system_notification(
            recipient=submission.admin_user,
            title="Kassa topshirish rad etildi ❌",
            message=(
                f"Sizning {submission.period_start.strftime('%d.%m.%Y')} - "
                f"{submission.period_end.strftime('%d.%m.%Y')} oralig'idagi "
                f"kassa topshirishingiz rad etildi. "
                f"Sabab: {reason_text}. "
                f"Rad etgan: {request.user.get_full_name()}"
            ),
            notification_type='system'
        )
    except Exception as e:
        logger.error(f"Kassa rad etish bildirishnomalarini yuborishda xatolik: {e}")

    messages.warning(request, "Kassa topshirish rad etildi.")
    return redirect('finance:cash_submission_list')


# ============================================
# ADMIN - O'quvchi to'lovlarini boshqarish
# ============================================

@login_required
@permission_required('admin_finance', 'view')
def admin_student_payments(request):
    """Admin uchun o'quvchi to'lovlari ro'yxati - tasdiqlash/rad etish."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    status_filter = request.GET.get('status', 'pending')
    search = request.GET.get('search', '')

    payments = Transaction.objects.filter(
        is_deleted=False,
        transaction_type='income',
        student__isnull=False,
    )
    if org:
        payments = payments.filter(organization=org)
    payments = payments.select_related('student', 'account', 'category', 'created_by', 'confirmed_by')

    if status_filter:
        payments = payments.filter(status=status_filter)
    if search:
        payments = payments.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__phone__icontains=search)
        )

    payments = payments.order_by('-created_at')[:100]

    # Statistika
    pending_qs = Transaction.objects.filter(
        is_deleted=False, status='pending',
        transaction_type='income', student__isnull=False,
    )
    if org:
        pending_qs = pending_qs.filter(organization=org)
    pending_count = pending_qs.count()

    context = {
        'payments': payments,
        'status_filter': status_filter,
        'search': search,
        'pending_count': pending_count,
    }
    return render(request, 'finance/admin_cash/student_payments.html', context)


@login_required
@permission_required('admin_finance', 'edit')
@require_POST
def admin_confirm_student_payment(request, pk):
    """O'quvchi to'lovini tasdiqlash va admin kassasiga o'tkazish."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user

    qs = Transaction.objects.filter(pk=pk)
    if org:
        qs = qs.filter(organization=org)
    tx = get_object_or_404(qs)

    if tx.status != 'pending':
        messages.error(request, "Bu to'lov allaqachon ko'rib chiqilgan.")
        return redirect('finance:admin_student_payments')

    # To'lovni admin kassasiga bog'lash
    admin_account = _get_or_create_admin_account(user, org)
    tx.account = admin_account
    tx.save(update_fields=['account'])

    try:
        confirm_service(tx.id, user)
        messages.success(request,
            f"✅ {tx.student.get_full_name()} to'lovi tasdiqlandi: {tx.amount:,.0f} UZS. "
            f"Admin kassasiga tushdi.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect('finance:admin_student_payments')


@login_required
@permission_required('admin_finance', 'edit')
@require_POST
def admin_reject_student_payment(request, pk):
    """O'quvchi to'lovini rad etish."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)

    qs = Transaction.objects.filter(pk=pk)
    if org:
        qs = qs.filter(organization=org)
    tx = get_object_or_404(qs)

    if tx.status != 'pending':
        messages.error(request, "Bu to'lov allaqachon ko'rib chiqilgan.")
        return redirect('finance:admin_student_payments')

    reason = request.POST.get('reason', '')
    tx.status = 'rejected'
    tx.receipt_notes = reason or "Admin tomonidan rad etildi"
    tx.confirmed_by = request.user
    tx.confirmed_at = timezone.now()
    tx.save()

    log_user_action(request.user, 'UPDATE', 'Transaction', tx.id,
                    f"O'quvchi to'lovi rad etildi: {tx}", request=request)
    messages.warning(request, f"{tx.student.get_full_name()} to'lovi rad etildi.")
    return redirect('finance:admin_student_payments')


# ============================================
# ADMIN - O'quvchi kurs to'lovini qo'shish
# ============================================

@login_required
@permission_required('admin_finance', 'create')
def admin_add_course_payment(request):
    """Admin o'quvchi uchun kurs to'lovini qo'shish (admin kassasiga tushadi)."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    # O'quvchilar ro'yxati
    students = User.objects.filter(role='student', is_active=True)
    if org:
        students = students.filter(organization=org)

    # Kategoriyalar
    categories = TransactionCategory.objects.filter(
        transaction_type='income', is_deleted=False
    )
    if org:
        categories = categories.filter(organization=org)

    if request.method == 'POST':
        student_id = request.POST.get('student')
        amount = request.POST.get('amount')
        category_id = request.POST.get('category')
        payment_method = request.POST.get('payment_method', 'cash')
        description = request.POST.get('description', '')

        # Validatsiya
        if not student_id or not amount:
            messages.error(request, "O'quvchi va summa maydonlarini to'ldiring!")
            return render(request, 'finance/admin_cash/course_payment_form.html', {
                'students': students, 'categories': categories,
                'admin_account': admin_account,
            })

        try:
            amount_decimal = Decimal(amount.replace(',', '').replace(' ', ''))
            if amount_decimal <= 0:
                raise ValueError()
        except (ValueError, ArithmeticError):
            messages.error(request, "Noto'g'ri summa formati!")
            return render(request, 'finance/admin_cash/course_payment_form.html', {
                'students': students, 'categories': categories,
                'admin_account': admin_account,
            })

        student = get_object_or_404(User, pk=student_id, role='student')
        category = None
        if category_id:
            category = TransactionCategory.objects.filter(pk=category_id).first()

        # Tranzaksiya yaratish - admin kassasiga tushadi
        tx_data = {
            'organization': org,
            'account': admin_account,
            'category': category,
            'student': student,
            'amount': amount_decimal,
            'transaction_type': 'income',
            'payment_method': payment_method,
            'description': description or f"Kurs to'lovi: {student.get_full_name()}",
            'status': 'pending',
            'created_by': user,
        }

        # Chek fayllarini qo'shish
        receipt_image = request.FILES.get('receipt_image')
        receipt_file = request.FILES.get('receipt_file')
        if receipt_image:
            tx_data['receipt_image'] = receipt_image
        if receipt_file:
            tx_data['receipt_file'] = receipt_file

        tx = Transaction.objects.create(**tx_data)

        # Admin o'zi yaratgani uchun avtomatik tasdiqlash
        try:
            confirm_service(tx.id, user)
            messages.success(request,
                f"✅ {student.get_full_name()} uchun {amount_decimal:,.0f} UZS kurs to'lovi qabul qilindi. "
                f"Admin kassasiga tushdi.")
        except Exception as e:
            messages.error(request, str(e))

        log_user_action(user, 'CREATE', 'Transaction', tx.id,
                        f"Kurs to'lovi: {student.get_full_name()} - {amount_decimal:,.0f}", request=request)
        return redirect('finance:admin_cash_dashboard')

    context = {
        'students': students,
        'categories': categories,
        'admin_account': admin_account,
    }
    return render(request, 'finance/admin_cash/course_payment_form.html', context)


@login_required
@permission_required('finance', 'view')
def cash_submission_detail(request, pk):
    """Kassa topshirish tafsilotlari - to'lov usuli bo'yicha tafsilotlar va tranzaksiya tarixi."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    
    # Faqat o'z topshirishlarini ko'rish yoki ruxsat bo'lsa
    qs = CashSubmission.objects.filter(is_deleted=False)
    if org:
        qs = qs.filter(organization=org)
    
    if user.role == 'admin' and not check_permission(user, 'finance', 'view'):
        qs = qs.filter(admin_user=user)
    
    submission = get_object_or_404(qs.select_related(
        'admin_user', 'admin_account', 'main_account', 'approved_by', 'organization'
    ), pk=pk)
    
    # FK orqali shu topshirishga bog'langan tranzaksiyalarni olish
    period_transactions = Transaction.objects.filter(
        is_deleted=False,
        cash_submission=submission,
    ).select_related(
        'category', 'student', 'staff', 'created_by', 'confirmed_by'
    ).order_by('-created_at')
    
    # Agar FK bo'yicha hech narsa topilmasa — eski usul bilan (backwards compat)
    if not period_transactions.exists():
        period_transactions = Transaction.objects.filter(
            is_deleted=False,
            created_at__date__gte=submission.period_start,
            created_at__date__lte=submission.period_end,
            account=submission.admin_account
        ).select_related(
            'category', 'student', 'staff', 'created_by', 'confirmed_by'
        ).order_by('-created_at')
    
    # Kirim va chiqimlarni ajratish
    income_transactions = period_transactions.filter(transaction_type='income')
    expense_transactions = period_transactions.filter(transaction_type='expense')
    
    # To'lov usuli bo'yicha statistika (faqat 3 ta tur)
    payment_method_stats = {}
    for method in ['cash', 'card', 'terminal']:
        method_transactions = _payment_method_queryset(period_transactions, method)
        total = method_transactions.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        payment_method_stats[method] = {
            'total': total,
            'count': method_transactions.count(),
            'transactions': method_transactions
        }
    
    context = {
        'submission': submission,
        'period_transactions': period_transactions,
        'income_transactions': income_transactions,
        'expense_transactions': expense_transactions,
        'payment_method_stats': payment_method_stats,
        'can_approve_reject': check_permission(user, 'finance', 'edit'),
    }
    return render(request, 'finance/admin_cash/submission_detail.html', context)


# ============================================
# ADMIN - Tranzaksiyalarni tahrirlash va o'chirish
# ============================================

@login_required
@permission_required('admin_finance', 'edit')
def admin_edit_transaction(request, pk):
    """Admin kassasidagi tranzaksiyani tahrirlash.
    Faqat kassa topshirilmagan bo'lsa ishlaydi."""
    from .forms import AdminCashTransactionForm
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    tx = get_object_or_404(Transaction, pk=pk, account=admin_account, is_deleted=False)

    # Kassa topshirilganmi?
    if tx.cash_submission is not None:
        messages.error(request, "❌ Bu tranzaksiya kassa topshirilgandan keyin o'zgartirib bo'lmaydi!")
        return redirect('finance:admin_cash_dashboard')

    old_amount = tx.amount
    old_type = tx.transaction_type

    if request.method == 'POST':
        new_amount = request.POST.get('amount')
        new_category_id = request.POST.get('category')
        new_payment_method = request.POST.get('payment_method', tx.payment_method)
        new_description = request.POST.get('description', tx.description)

        try:
            new_amount = Decimal(str(new_amount).replace(',', '').replace(' ', ''))
            if new_amount <= 0:
                raise ValueError()
        except (ValueError, ArithmeticError, TypeError):
            messages.error(request, "Noto'g'ri summa!")
            return redirect('finance:admin_edit_transaction', pk=pk)

        with transaction.atomic():
            # Agar tasdiqlangan bo'lsa — balansni teskari yurgizib, qayta hisoblash
            if tx.status == 'confirmed':
                is_supply_sale = getattr(tx.category, 'name', '') == 'Mahsulot sotish'
                
                # Eski summani qaytarish
                if old_type == 'income':
                    admin_account.balance -= old_amount
                    if tx.student and not is_supply_sale:
                        tx.student.balance -= old_amount
                        tx.student.save(update_fields=['balance'])
                elif old_type == 'expense':
                    admin_account.balance += old_amount

                # Yangi kategoriya tekshiriladi
                new_cat = TransactionCategory.objects.filter(pk=new_category_id).first() if new_category_id else tx.category
                is_new_supply_sale = getattr(new_cat, 'name', '') == 'Mahsulot sotish'

                # Yangi summani qo'shish
                if old_type == 'income':
                    admin_account.balance += new_amount
                    if tx.student and not is_new_supply_sale:
                        tx.student.balance += new_amount
                        tx.student.save(update_fields=['balance'])
                elif old_type == 'expense':
                    admin_account.balance -= new_amount

                admin_account.save(update_fields=['balance'])

            # Tranzaksiyani yangilash (signal ni bypass qilish uchun update_fields)
            tx.amount = new_amount
            tx.payment_method = new_payment_method
            tx.description = new_description
            if new_category_id:
                tx.category_id = new_category_id
            tx._bypass_confirmed_edit_lock = True
            tx.save(update_fields=['amount', 'payment_method', 'description', 'category_id', 'updated_at'])

        log_user_action(user, 'UPDATE', 'Transaction', tx.id,
                        f"Tranzaksiya tahrirlandi: {old_amount} → {new_amount}", request=request)
        messages.success(request, f"✅ Tranzaksiya yangilandi: {new_amount:,.0f} UZS")
        return redirect('finance:admin_cash_dashboard')

    # GET — tahrirlash formasi
    categories = TransactionCategory.objects.filter(
        is_deleted=False, transaction_type=tx.transaction_type
    )
    if org:
        categories = categories.filter(organization=org)

    context = {
        'tx': tx,
        'categories': categories,
        'payment_methods': Transaction.PAYMENT_METHOD_CHOICES,
    }
    return render(request, 'finance/admin_cash/transaction_edit.html', context)


@login_required
@permission_required('admin_finance', 'edit')
@require_POST
def admin_delete_transaction(request, pk):
    """Admin kassasidagi tranzaksiyani o'chirish (soft delete).
    Faqat kassa topshirilmagan bo'lsa ishlaydi."""
    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    user = request.user
    admin_account = _get_or_create_admin_account(user, org)

    tx = get_object_or_404(Transaction, pk=pk, account=admin_account, is_deleted=False)

    # Kassa topshirilganmi?
    if tx.cash_submission is not None:
        messages.error(request, "❌ Bu tranzaksiya kassa topshirilgandan keyin o'chirib bo'lmaydi!")
        return redirect('finance:admin_cash_dashboard')

    with transaction.atomic():
        # Agar tasdiqlangan bo'lsa — balanslarni teskari yurgizish
        if tx.status == 'confirmed':
            if tx.transaction_type == 'income':
                admin_account.balance -= tx.amount
                is_supply_sale = getattr(tx.category, 'name', '') == 'Mahsulot sotish'
                if tx.student and not is_supply_sale:
                    tx.student.balance -= tx.amount
                    tx.student.save(update_fields=['balance'])
            elif tx.transaction_type == 'expense':
                admin_account.balance += tx.amount
            elif tx.transaction_type == 'refund':
                admin_account.balance += tx.amount
                if tx.student:
                    tx.student.balance += tx.amount
                    tx.student.save(update_fields=['balance'])
            admin_account.save(update_fields=['balance'])

        # Soft delete
        tx.is_deleted = True
        tx.deleted_at = timezone.now()
        tx.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    log_user_action(user, 'DELETE', 'Transaction', tx.id,
                    f"Tranzaksiya o'chirildi: {tx.amount:,.0f} ({tx.get_transaction_type_display()})",
                    request=request)
    messages.success(request, f"🗑️ Tranzaksiya o'chirildi va balanslar yangilandi.")
    return redirect('finance:admin_cash_dashboard')
