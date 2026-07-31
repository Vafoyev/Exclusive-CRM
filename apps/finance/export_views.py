"""
Finance Export Views - Moliyaviy ma'lumotlarni PDF va Excel formatida eksport qilish.
"""
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum

from reportlab.lib.units import cm

from .models import Transaction, Account
from apps.core.export_utils import export_to_excel, export_to_pdf, format_money
from apps.core.permissions import permission_required


# ========================================
# TRANSACTIONS EXPORT
# ========================================

@login_required
@permission_required('finance', 'view')
def export_transactions_excel(request):
    """Tranzaksiyalarni Excel formatida eksport qilish"""
    org = request.organization

    # Filter parametrlari (GET dan)
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    trans_type = request.GET.get('type', '')
    status = request.GET.get('status', '')

    # QuerySet
    transactions = Transaction.objects.filter(is_deleted=False)
    if org:
        transactions = transactions.filter(organization=org)

    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)
    if trans_type:
        transactions = transactions.filter(transaction_type=trans_type)
    if status:
        transactions = transactions.filter(status=status)

    transactions = transactions.select_related(
        'account', 'category', 'student', 'staff', 'created_by'
    ).order_by('-created_at')

    # Ma'lumotlarni tayyorlash
    data = []
    for t in transactions:
        data.append({
            'id': t.id,
            'date': t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
            'type': 'Kirim' if t.transaction_type == 'income' else 'Chiqim',
            'category': t.category.name if t.category else '-',
            'account': t.account.name if t.account else '-',
            'student': f"{t.student.first_name} {t.student.last_name}" if t.student else '-',
            'staff': f"{t.staff.first_name} {t.staff.last_name}" if t.staff else '-',
            'amount': float(t.amount) if t.amount else 0,
            'status': t.get_status_display() if hasattr(t, 'get_status_display') else t.status,
            'description': t.description or '',
            'created_by': f"{t.created_by.first_name}" if t.created_by else '-',
        })

    # Ustunlar
    columns = [
        {'key': 'id', 'header': 'ID', 'width': 8},
        {'key': 'date', 'header': 'Sana', 'width': 18},
        {'key': 'type', 'header': 'Turi', 'width': 10},
        {'key': 'category', 'header': 'Kategoriya', 'width': 18},
        {'key': 'account', 'header': 'Kassa', 'width': 15},
        {'key': 'student', 'header': "O'quvchi", 'width': 20},
        {'key': 'amount', 'header': 'Summa', 'width': 15, 'money': True},
        {'key': 'status', 'header': 'Holat', 'width': 12},
        {'key': 'description', 'header': 'Izoh', 'width': 25},
    ]

    # Fayl nomi
    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"tranzaksiyalar_{today}"

    # Sarlavha
    title = "TRANZAKSIYALAR RO'YXATI"
    if date_from and date_to:
        title += f" ({date_from} - {date_to})"

    return export_to_excel(data, columns, filename, title=title)


@login_required
@permission_required('finance', 'view')
def export_transactions_pdf(request):
    """Tranzaksiyalarni PDF formatida eksport qilish"""
    org = request.organization

    # Filter parametrlari
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    trans_type = request.GET.get('type', '')
    status = request.GET.get('status', '')

    # QuerySet
    transactions = Transaction.objects.filter(is_deleted=False)
    if org:
        transactions = transactions.filter(organization=org)

    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)
    if trans_type:
        transactions = transactions.filter(transaction_type=trans_type)
    if status:
        transactions = transactions.filter(status=status)

    # Statistika (slice olmadan oldin)
    income = transactions.filter(transaction_type='income', status='confirmed').aggregate(t=Sum('amount'))['t'] or 0
    expense = transactions.filter(transaction_type='expense', status='confirmed').aggregate(t=Sum('amount'))['t'] or 0

    # Endi slice qilamiz
    transactions = transactions.select_related(
        'account', 'category', 'student', 'created_by'
    ).order_by('-created_at')[:100]  # PDF uchun cheklash


    # Ma'lumotlarni tayyorlash
    data = []
    for t in transactions:
        data.append({
            'date': t.created_at.strftime('%d.%m.%Y') if t.created_at else '',
            'type': 'Kirim' if t.transaction_type == 'income' else 'Chiqim',
            'category': t.category.name if t.category else '-',
            'student': f"{t.student.first_name} {t.student.last_name[:1]}." if t.student else '-',
            'amount': float(t.amount) if t.amount else 0,
            'status': 'Tasdiqlangan' if t.status == 'confirmed' else 'Kutilmoqda',
        })

    # Ustunlar (PDF uchun kengliklar cm da)
    columns = [
        {'key': 'date', 'header': 'Sana', 'width': 2.5*cm},
        {'key': 'type', 'header': 'Turi', 'width': 2*cm},
        {'key': 'category', 'header': 'Kategoriya', 'width': 4*cm},
        {'key': 'student', 'header': "O'quvchi", 'width': 4*cm},
        {'key': 'amount', 'header': 'Summa', 'width': 3*cm, 'money': True},
        {'key': 'status', 'header': 'Holat', 'width': 2.5*cm},
    ]

    # Fayl nomi
    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"tranzaksiyalar_{today}"

    # Sarlavha va subtitle
    title = "TRANZAKSIYALAR RO'YXATI"
    subtitle = f"Kirim: {format_money(income)} so'm | Chiqim: {format_money(expense)} so'm | Balans: {format_money(income - expense)} so'm"

    return export_to_pdf(data, columns, filename, title=title, subtitle=subtitle, landscape_mode=True)


# ========================================
# FINANCE REPORT EXPORT
# ========================================

@login_required
@permission_required('finance', 'view')
def export_finance_report_excel(request):
    """Moliyaviy hisobotni Excel formatida eksport qilish"""
    org = request.organization
    today = timezone.now().date()

    # Kassalar
    accounts = Account.objects.filter(is_deleted=False)
    if org:
        accounts = accounts.filter(organization=org)

    data = []
    total_balance = 0

    for acc in accounts:
        # Kassa bo'yicha kirim/chiqim
        income = Transaction.objects.filter(
            account=acc, transaction_type='income', status='confirmed'
        ).aggregate(t=Sum('amount'))['t'] or 0

        expense = Transaction.objects.filter(
            account=acc, transaction_type='expense', status='confirmed'
        ).aggregate(t=Sum('amount'))['t'] or 0

        data.append({
            'name': acc.name,
            'type': acc.get_account_type_display() if hasattr(acc, 'get_account_type_display') else acc.account_type,
            'income': float(income),
            'expense': float(expense),
            'balance': float(acc.balance or 0),
        })
        total_balance += float(acc.balance or 0)

    # Jami qator
    data.append({
        'name': 'JAMI',
        'type': '',
        'income': sum(d['income'] for d in data[:-1]) if len(data) > 1 else 0,
        'expense': sum(d['expense'] for d in data[:-1]) if len(data) > 1 else 0,
        'balance': total_balance,
    })

    columns = [
        {'key': 'name', 'header': 'Kassa nomi', 'width': 25},
        {'key': 'type', 'header': 'Turi', 'width': 15},
        {'key': 'income', 'header': 'Jami kirim', 'width': 18, 'money': True},
        {'key': 'expense', 'header': 'Jami chiqim', 'width': 18, 'money': True},
        {'key': 'balance', 'header': 'Balans', 'width': 18, 'money': True},
    ]

    filename = f"moliya_hisobot_{today}"
    title = f"MOLIYAVIY HISOBOT - {today}"

    return export_to_excel(data, columns, filename, title=title, sheet_name="Kassalar")


@login_required
@permission_required('finance', 'view')
def export_finance_report_pdf(request):
    """Moliyaviy hisobotni PDF formatida eksport qilish"""
    org = request.organization
    today = timezone.now().date()

    accounts = Account.objects.filter(is_deleted=False)
    if org:
        accounts = accounts.filter(organization=org)

    data = []
    total_income = 0
    total_expense = 0
    total_balance = 0

    for acc in accounts:
        income = Transaction.objects.filter(
            account=acc, transaction_type='income', status='confirmed'
        ).aggregate(t=Sum('amount'))['t'] or 0

        expense = Transaction.objects.filter(
            account=acc, transaction_type='expense', status='confirmed'
        ).aggregate(t=Sum('amount'))['t'] or 0

        data.append({
            'name': acc.name,
            'income': float(income),
            'expense': float(expense),
            'balance': float(acc.balance or 0),
        })
        total_income += float(income)
        total_expense += float(expense)
        total_balance += float(acc.balance or 0)

    columns = [
        {'key': 'name', 'header': 'Kassa', 'width': 5*cm},
        {'key': 'income', 'header': 'Kirim', 'width': 4*cm, 'money': True},
        {'key': 'expense', 'header': 'Chiqim', 'width': 4*cm, 'money': True},
        {'key': 'balance', 'header': 'Balans', 'width': 4*cm, 'money': True},
    ]

    filename = f"moliya_hisobot_{today}"
    title = "MOLIYAVIY HISOBOT"
    subtitle = f"Jami: Kirim {format_money(total_income)} | Chiqim {format_money(total_expense)} | Balans {format_money(total_balance)} so'm"

    return export_to_pdf(data, columns, filename, title=title, subtitle=subtitle)


# ========================================
# STUDENTS DEBT EXPORT
# ========================================

@login_required
@permission_required('finance', 'view')
def export_debtors_excel(request):
    """Qarzdorlar ro'yxatini Excel formatida eksport qilish"""
    from apps.users.models import User

    org = request.organization

    debtors = User.objects.filter(role='student', balance__lt=0, is_deleted=False)
    if org:
        debtors = debtors.filter(organization=org)

    debtors = debtors.order_by('balance')  # Eng katta qarzdordan

    data = []
    for student in debtors:
        data.append({
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}",
            'phone': student.phone or '',
            'balance': float(student.balance),
            'debt': abs(float(student.balance)),
        })

    columns = [
        {'key': 'id', 'header': 'ID', 'width': 8},
        {'key': 'name', 'header': 'F.I.O', 'width': 30},
        {'key': 'phone', 'header': 'Telefon', 'width': 18},
        {'key': 'debt', 'header': 'Qarz summasi', 'width': 18, 'money': True},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"qarzdorlar_{today}"
    title = f"QARZDORLAR RO'YXATI - {today}"

    return export_to_excel(data, columns, filename, title=title, sheet_name="Qarzdorlar")


@login_required
@permission_required('finance', 'view')
def export_debtors_pdf(request):
    """Qarzdorlar ro'yxatini PDF formatida eksport qilish"""
    from apps.users.models import User

    org = request.organization

    debtors = User.objects.filter(role='student', balance__lt=0, is_deleted=False)
    if org:
        debtors = debtors.filter(organization=org)

    debtors = debtors.order_by('balance')

    total_debt = abs(sum(d.balance for d in debtors))

    data = []
    for i, student in enumerate(debtors, 1):
        data.append({
            'num': i,
            'name': f"{student.first_name} {student.last_name}",
            'phone': student.phone or '',
            'debt': abs(float(student.balance)),
        })

    columns = [
        {'key': 'num', 'header': '#', 'width': 1*cm},
        {'key': 'name', 'header': 'F.I.O', 'width': 6*cm},
        {'key': 'phone', 'header': 'Telefon', 'width': 4*cm},
        {'key': 'debt', 'header': 'Qarz', 'width': 4*cm, 'money': True},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"qarzdorlar_{today}"
    title = "QARZDORLAR RO'YXATI"
    subtitle = f"Jami qarzdorlar: {len(data)} ta | Umumiy qarz: {format_money(total_debt)} so'm"

    return export_to_pdf(data, columns, filename, title=title, subtitle=subtitle)
