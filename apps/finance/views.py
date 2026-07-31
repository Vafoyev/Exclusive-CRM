from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from decimal import Decimal, InvalidOperation
from datetime import timedelta
import logging
from .models import Account, Transaction, TransactionCategory
from apps.users.models import User
from apps.core.audit import log_user_action
from apps.core.permissions import permission_required, check_permission, role_required
from .services import execute_manual_monthly_fee_run, normalize_billing_month, reset_all_student_balances

logger = logging.getLogger(__name__)


@login_required
def kassa_dashboard(request):
    """Moliya / Kassa Dashboard View"""
    return render(request, 'finance/kassa.html')



@login_required
@permission_required('finance', 'view')
def transaction_list(request):
    """Tranzaksiyalar ro'yxati"""
    org = request.organization

    # Filter parametrlari
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    trans_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    account_id = request.GET.get('account', '')

    # Asosiy QuerySet
    transactions = Transaction.objects.filter(is_deleted=False)
    if org:
        transactions = transactions.filter(organization=org)

    # Admin faqat o'z kirim-chiqimlarini ko'radi (umumiy emas)
    if request.user.role == 'admin':
        transactions = transactions.filter(created_by=request.user)

    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)
    if trans_type:
        transactions = transactions.filter(transaction_type=trans_type)
    if status:
        transactions = transactions.filter(status=status)
    if account_id:
        transactions = transactions.filter(account_id=account_id)

    # Statistika
    stats_qs = transactions.filter(status='confirmed')
    stats = stats_qs.aggregate(
        income=Sum('amount', filter=Q(transaction_type='income')),
        expense=Sum('amount', filter=Q(transaction_type='expense')),
    )
    income = stats['income'] or 0
    expense = stats['expense'] or 0

    # Optimallashtirilgan load
    transactions = transactions.select_related(
        'account', 'category', 'student', 'staff', 'created_by', 'confirmed_by'
    ).order_by('-created_at')[:100]

    accounts = Account.objects.filter(is_deleted=False)
    if org:
        accounts = accounts.filter(organization=org)

    context = {
        'transactions': transactions,
        'accounts': accounts,
        'income': income,
        'expense': expense,
        'balance': income - expense,
        'date_from': date_from,
        'date_to': date_to,
        'trans_type': trans_type,
        'status': status,
        'account_id': account_id,
    }
    return render(request, 'finance/transaction_list.html', context)

# Boshqa viewlar o'zgarishsiz qolishi mumkin, chunki asosiy xato List view da edi
# (Qisqartirish uchun faqat listni yozdim, qolganlari import qilingan joyda turibdi deb faraz qilamiz
# Lekin faylni to'liq yozayotganimiz uchun ularni ham qo'shish kerak)

@login_required
@permission_required('finance', 'view')
def account_list(request):
    org = request.organization
    accounts = Account.objects.filter(is_deleted=False)
    if org:
        accounts = accounts.filter(organization=org)

    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or 0

    return render(request, 'finance/account_list.html', {'accounts': accounts, 'total_balance': total_balance})

@login_required
@permission_required('finance', 'create')
def account_create(request):
    from .forms import AccountForm
    org = request.organization
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            acc = form.save(commit=False)
            acc.organization = org
            acc.save()
            messages.success(request, "Kassa yaratildi")
            return redirect('finance:account_list')
    else:
        form = AccountForm()
    return render(request, 'finance/account_form.html', {'form': form, 'title': 'Yangi Kassa'})

@login_required
@permission_required('finance', 'edit')
def account_edit(request, pk):
    from .forms import AccountForm
    org = request.organization
    account = get_object_or_404(Account, pk=pk, organization=org)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, "Kassa yangilandi")
            return redirect('finance:account_list')
    else:
        form = AccountForm(instance=account)
    return render(request, 'finance/account_form.html', {'form': form, 'title': 'Kassani tahrirlash'})

@login_required
@permission_required('finance', 'delete')
@require_POST
def account_delete(request, pk):
    org = request.organization
    account = get_object_or_404(Account, pk=pk, organization=org)
    account.is_deleted = True
    account.save()
    messages.success(request, "Kassa o'chirildi")
    return redirect('finance:account_list')

# ===========================================
# KATEGORIYALAR (Transaction Categories)
# ===========================================

@login_required
@permission_required('finance', 'view')
def category_list(request):
    """Kirim va chiqim kategoriyalari ro'yxati"""
    org = request.organization
    categories = TransactionCategory.objects.filter(is_deleted=False)
    if org:
        categories = categories.filter(organization=org)

    income_categories = categories.filter(transaction_type='income')
    expense_categories = categories.filter(transaction_type='expense')

    return render(request, 'finance/category_list.html', {
        'income_categories': income_categories,
        'expense_categories': expense_categories,
    })

@login_required
@permission_required('finance', 'create')
def category_create(request):
    """Yangi kategoriya yaratish"""
    from .forms import CategoryForm
    org = request.organization
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.organization = org
            cat.save()
            messages.success(request, "Kategoriya yaratildi")
            return redirect('finance:category_list')
    else:
        form = CategoryForm()
    return render(request, 'finance/category_form.html', {'form': form, 'title': 'Yangi Kategoriya'})

@login_required
@permission_required('finance', 'edit')
def category_edit(request, pk):
    """Kategoriyani tahrirlash"""
    from .forms import CategoryForm
    org = request.organization
    category = get_object_or_404(TransactionCategory, pk=pk, organization=org)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Kategoriya yangilandi")
            return redirect('finance:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'finance/category_form.html', {'form': form, 'title': 'Kategoriyani tahrirlash'})

@login_required
@permission_required('finance', 'create')
def add_income(request):
    from .forms import TransactionForm
    org = request.organization
    if request.method == 'POST':
        form = TransactionForm(request.POST, organization=org, transaction_type='income')
        if form.is_valid():
            t = form.save(commit=False)
            t.organization = org
            t.transaction_type = 'income'
            t.created_by = request.user
            t.status = 'pending'
            t.save()
            messages.success(request, "Kirim qo'shildi")
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm(organization=org, transaction_type='income')
    return render(request, 'finance/transaction_form.html', {'form': form, 'title': 'Kirim', 'type': 'income'})

@login_required
@permission_required('finance', 'create')
def add_expense(request):
    from .forms import TransactionForm
    org = request.organization
    if request.method == 'POST':
        form = TransactionForm(request.POST, organization=org, transaction_type='expense')
        if form.is_valid():
            t = form.save(commit=False)
            t.organization = org
            t.transaction_type = 'expense'
            t.created_by = request.user
            t.status = 'pending'
            t.save()
            messages.success(request, "Chiqim qo'shildi")
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm(organization=org, transaction_type='expense')
    return render(request, 'finance/transaction_form.html', {'form': form, 'title': 'Chiqim', 'type': 'expense'})

@login_required
@permission_required('finance', 'edit')
def confirm_transaction(request, pk):
    # Bu view endi services.py orqali ishlaydi (avvalgi fixda to'g'irlangan)
    from .services import confirm_transaction as confirm_service
    try:
        confirm_service(pk, request.user)
        messages.success(request, "Tasdiqlandi")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('finance:transaction_list')

@login_required
@permission_required('finance', 'edit')
def reject_transaction(request, pk):
    t = get_object_or_404(Transaction, pk=pk)
    if t.status == 'pending':
        t.status = 'rejected'
        t.save()
        messages.warning(request, "Rad etildi")
    return redirect('finance:transaction_list')

# Student payments view (Placeholder - needs existing imports)
@login_required
@permission_required('finance', 'view')
def student_payments(request, student_id):
    student = get_object_or_404(User, pk=student_id)
    payments = Transaction.objects.filter(student=student).select_related(
        'account', 'category', 'created_by', 'confirmed_by'
    ).order_by('-created_at')
    total = payments.filter(transaction_type='income', status='confirmed').aggregate(s=Sum('amount'))['s'] or 0
    return render(request, 'finance/student_payments.html', {'student': student, 'payments': payments, 'total_paid': total})

@login_required
@permission_required('finance', 'create')
def add_student_payment(request, student_id):
    from .forms import StudentPaymentForm
    student = get_object_or_404(User, pk=student_id)
    if request.method == 'POST':
        form = StudentPaymentForm(request.POST, request.FILES, organization=request.organization)
        if form.is_valid():
            t = form.save(commit=False)
            t.organization = request.organization
            t.student = student
            t.transaction_type = 'income'
            t.created_by = request.user
            t.status = 'pending'
            t.save()
            messages.success(request, "To'lov qabul qilindi")
            return redirect('finance:student_payments', student_id=student.id)
    else:
        form = StudentPaymentForm(organization=request.organization)
    return render(request, 'finance/student_payment_form.html', {'form': form, 'student': student})

@login_required
@permission_required('finance', 'view')
def finance_report(request):
    """Moliyaviy hisobot - kirim, chiqim, foyda statistikasi"""

    org = request.organization
    today = timezone.now().date()

    # Davr tanlash (default: 30 kun)
    try:
        days = max(1, int(request.GET.get('days', 30)))
    except (TypeError, ValueError):
        days = 30
    start_date = today - timedelta(days=days)
    end_date = today

    # Base queryset
    transactions = Transaction.objects.filter(
        is_deleted=False,
        status='confirmed',
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    if org:
        transactions = transactions.filter(organization=org)

    # Umumiy statistika
    totals = transactions.aggregate(
        total_income=Sum('amount', filter=Q(transaction_type='income')),
        total_expense=Sum('amount', filter=Q(transaction_type='expense')),
    )
    total_income = totals['total_income'] or 0
    total_expense = totals['total_expense'] or 0
    net_profit = total_income - total_expense

    # Kunlik statistika (grafik uchun)
    daily_totals = {
        row['day']: row
        for row in transactions.annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            income=Sum('amount', filter=Q(transaction_type='income')),
            expense=Sum('amount', filter=Q(transaction_type='expense')),
        )
    }
    daily_stats = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        row = daily_totals.get(day, {})
        income = row.get('income') or 0
        expense = row.get('expense') or 0
        daily_stats.append({
            'date': day,
            'income': income,
            'expense': expense,
        })

    # Maksimal qiymat (grafik scale uchun)
    max_amount = max([max(d['income'], d['expense']) for d in daily_stats] or [1])
    for d in daily_stats:
        d['income_height'] = int((d['income'] / max_amount) * 100) if max_amount > 0 else 0
        d['expense_height'] = int((d['expense'] / max_amount) * 100) if max_amount > 0 else 0

    # Kategoriya bo'yicha (pie chart uchun)
    income_by_category = transactions.filter(
        transaction_type='income',
        category__isnull=False
    ).values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]

    expense_by_category = transactions.filter(
        transaction_type='expense',
        category__isnull=False
    ).values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]

    # Kassalar balansi
    accounts = Account.objects.filter(is_deleted=False)
    if org:
        accounts = accounts.filter(organization=org)
    total_balance = accounts.aggregate(t=Sum('balance'))['t'] or 0

    # Oxirgi tranzaksiyalar
    recent_transactions = transactions.select_related(
        'category', 'student', 'account'
    ).order_by('-created_at')[:10]

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'days': days,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'daily_stats': daily_stats,
        'income_by_category': income_by_category,
        'expense_by_category': expense_by_category,
        'accounts': accounts,
        'total_balance': total_balance,
        'recent_transactions': recent_transactions,
    }

    return render(request, 'finance/report.html', context)


@login_required
@permission_required('finance', 'view')
def pending_receipts(request):
    org = request.organization
    txs = Transaction.objects.filter(receipt_verified=False, status='pending', is_deleted=False)
    if org:
        txs = txs.filter(organization=org)
    txs = txs.select_related('student', 'created_by', 'category', 'account')

    pending_stats = txs.aggregate(
        pending_count=Count('id'),
        pending_sum=Sum('amount'),
    )
    pending_count = pending_stats['pending_count'] or 0
    pending_sum = pending_stats['pending_sum'] or 0

    return render(request, 'finance/pending_receipts.html', {
        'pending_receipts': txs,
        'pending_count': pending_count,
        'pending_sum': pending_sum,
    })

@login_required
@permission_required('finance', 'edit')
def verify_receipt(request, pk):
    return confirm_transaction(request, pk)

@login_required
@permission_required('finance', 'edit')
def reject_receipt(request, pk):
    return reject_transaction(request, pk)


@login_required
@permission_required('finance', 'create')
@require_POST
def quick_payment(request):
    """Quick Payment modal dan kelgan AJAX so'rovni qayta ishlash."""
    try:
        org = request.user.organization

        student_id = request.POST.get('student_id')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method', 'cash')
        account_id = request.POST.get('account_id')
        receipt_image = request.FILES.get('receipt_image')

        if not student_id or not amount or not account_id:
            return JsonResponse({'success': False, 'error': "Barcha maydonlarni to'ldiring."}, status=400)

        try:
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                return JsonResponse({'success': False, 'error': "Summa musbat bo'lishi kerak."}, status=400)
        except (InvalidOperation, ValueError):
            return JsonResponse({'success': False, 'error': "Noto'g'ri summa formati."}, status=400)

        # Super admin uchun organization bo'lmasligi mumkin
        if org:
            student = User.objects.filter(pk=student_id, organization=org, role='student').first()
            account = Account.objects.filter(pk=account_id, organization=org).first()
        else:
            student = User.objects.filter(pk=student_id, role='student').first()
            account = Account.objects.filter(pk=account_id).first()

        if not student:
            return JsonResponse({'success': False, 'error': "O'quvchi topilmadi."}, status=400)
        if not account:
            return JsonResponse({'success': False, 'error': "Kassa topilmadi."}, status=400)

        # Tranzaksiya uchun tashkilotni aniqlash
        transaction_org = org or student.organization

        # Kurs to'lovi kategoriyasini topish yoki None
        category = TransactionCategory.objects.filter(
            organization=transaction_org, transaction_type='income'
        ).first()

        transaction = Transaction.objects.create(
            organization=transaction_org,
            account=account,
            category=category,
            student=student,
            amount=amount_decimal,
            transaction_type='income',
            payment_method=payment_method,
            description=f"Tezkor to'lov: {student.get_full_name()}",
            status='pending',
            created_by=request.user,
            receipt_image=receipt_image,
        )

        return JsonResponse({
            'success': True,
            'message': f"{student.get_full_name()} uchun {amount_decimal:,.0f} UZS to'lov qabul qilindi.",
            'transaction_id': transaction.id,
        })
    except Exception:
        logger.exception("Quick payment da kutilmagan xatolik")
        return JsonResponse({'success': False, 'error': "Xatolik yuz berdi. Iltimos qayta urinib ko'ring."}, status=500)


@login_required
@role_required('super_admin')
@require_POST
def monthly_fee_run(request):
    """
    Super admin uchun qo'lda kurs puli yechish.
    """
    run_type = request.POST.get('run_type', 'bulk')
    student_id = request.POST.get('student_id')
    password = request.POST.get('password', '')

    try:
        billing_month = normalize_billing_month(request.POST.get('billing_month'))
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    target_student = None
    if run_type == 'single':
        if not student_id:
            return JsonResponse({'success': False, 'error': "O'quvchini tanlang."}, status=400)
        target_student = User.objects.filter(
            pk=student_id,
            role='student',
            is_active=True,
            is_deleted=False,
        ).first()
        if not target_student:
            return JsonResponse({'success': False, 'error': "O'quvchi topilmadi."}, status=404)

    try:
        run = execute_manual_monthly_fee_run(
            triggered_by=request.user,
            billing_month=billing_month,
            run_type=run_type,
            password=password,
            target_student=target_student,
            request=request,
        )
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    return JsonResponse({
        'success': True,
        'message': run.notes or "Kurs puli yechish yakunlandi.",
        'run': {
            'id': run.id,
            'status': run.status,
            'billing_month': run.billing_month.strftime('%Y-%m'),
            'run_type': run.run_type,
            'total_students_processed': run.total_students_processed,
            'total_charges_created': run.total_charges_created,
            'skipped_existing_count': run.skipped_existing_count,
            'total_amount_deducted': float(run.total_amount_deducted),
            'triggered_at': timezone.localtime(run.triggered_at).strftime('%d.%m.%Y %H:%M'),
            'summary': run.summary,
        },
    })


@login_required
@role_required('super_admin')
@require_POST
def reset_student_balances(request):
    """
    Super admin barcha student balanslarini 0 ga tushiradi.
    """
    password = request.POST.get('password', '')

    try:
        result = reset_all_student_balances(
            triggered_by=request.user,
            password=password,
            request=request,
        )
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    return JsonResponse({
        'success': True,
        'message': f"{result['updated_count']} ta student balansi 0 ga tushirildi.",
        'result': {
            'total_students': result['total_students'],
            'updated_count': result['updated_count'],
            'students_with_balance': result['students_with_balance'],
            'debt_amount': float(result['debt_amount']),
            'credit_amount': float(result['credit_amount']),
            'net_balance': float(result['net_balance']),
            'reset_at': timezone.localtime(result['reset_at']).strftime('%d.%m.%Y %H:%M'),
        },
    })
