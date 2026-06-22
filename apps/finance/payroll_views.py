"""
Payroll (Oylik) boshqaruvi viewlari.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from datetime import date, timedelta
import calendar

from apps.finance.payroll import StaffKPI, PayrollRecord, StaffAttendance
from apps.finance.models import Account, Transaction, TransactionCategory
from apps.users.models import User
from apps.operations.models import Lesson, Attendance
from apps.core.audit import log_user_action


def add_months(source_date, months):
    """Standard library replacement for relativedelta months"""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@login_required
def payroll_list(request):
    """Xodimlar oyliklari ro'yxati"""
    org = request.user.organization

    # Default: joriy oy
    month_str = request.GET.get('month')
    if month_str:
        year, month = map(int, month_str.split('-'))
        selected_month = date(year, month, 1)
    else:
        selected_month = date.today().replace(day=1)
    
    # Barcha payroll yozuvlari
    payrolls = PayrollRecord.objects.filter(
        month=selected_month
    ).select_related('staff', 'approved_by')
    
    if org:
        payrolls = payrolls.filter(organization=org)

    # Hali payroll yaratilmagan xodimlar
    staff_with_payroll = payrolls.values_list('staff_id', flat=True)

    staff_query = User.objects.filter(
        role__in=['teacher', 'staff', 'admin']
    )

    if org:
        staff_query = staff_query.filter(organization=org)

    staff_without_payroll = staff_query.exclude(id__in=staff_with_payroll)

    # Statistika
    stats = {
        'total_gross': payrolls.aggregate(Sum('gross_salary'))['gross_salary__sum'] or 0,
        'total_net': payrolls.aggregate(Sum('net_salary'))['net_salary__sum'] or 0,
        'approved_count': payrolls.filter(status='approved').count(),
        'pending_count': payrolls.filter(status__in=['draft', 'pending']).count(),
    }
    
    # Oylar (oxirgi 12 oy)
    months = []
    current = date.today().replace(day=1)
    for i in range(12):
        months.append(add_months(current, -i))
    
    context = {
        'payrolls': payrolls,
        'staff_without_payroll': staff_without_payroll,
        'selected_month': selected_month,
        'months': months,
        'stats': stats,
    }
    return render(request, 'finance/payroll_list.html', context)


@login_required
def calculate_payroll(request, staff_id):
    """Xodim uchun oylikni hisoblash"""
    org = request.user.organization

    staff_query = User.objects.filter(pk=staff_id)
    if org:
        staff_query = staff_query.filter(organization=org)

    staff = get_object_or_404(staff_query)

    # Oyni olish
    month_str = request.GET.get('month')
    if month_str:
        year, month = map(int, month_str.split('-'))
        selected_month = date(year, month, 1)
    else:
        selected_month = date.today().replace(day=1)
    
    # Mavjud payroll bormi?
    defaults = {
        'base_salary': staff.profile_data.get('base_salary', 0) if hasattr(staff, 'profile_data') and staff.profile_data else 0,
        'per_lesson_rate': staff.profile_data.get('per_lesson_rate', 50000) if hasattr(staff, 'profile_data') and staff.profile_data else 50000,
    }

    if org:
        defaults['organization'] = org

    payroll, created = PayrollRecord.objects.get_or_create(
        staff=staff,
        month=selected_month,
        defaults=defaults
    )
    
    if request.method == 'POST':
        # Formadan ma'lumotlarni olish
        payroll.base_salary = float(request.POST.get('base_salary', 0))
        payroll.per_lesson_rate = float(request.POST.get('per_lesson_rate', 0))
        payroll.kpi_bonus = float(request.POST.get('kpi_bonus', 0))
        payroll.other_bonus = float(request.POST.get('other_bonus', 0))
        payroll.late_penalty = float(request.POST.get('late_penalty', 0))
        payroll.absent_penalty = float(request.POST.get('absent_penalty', 0))
        payroll.other_deductions = float(request.POST.get('other_deductions', 0))
        payroll.notes = request.POST.get('notes', '')
        
        # Darslar sonini hisoblash
        month_end = add_months(selected_month, 1) - timedelta(days=1)
        lessons_count = Lesson.objects.filter(
            teacher=staff,
            date__gte=selected_month,
            date__lte=month_end,
            status='finished'
        ).count()
        payroll.lessons_count = lessons_count
        
        # Hisoblash va saqlash
        payroll.calculate()
        payroll.status = 'pending'
        payroll.save()
        
        log_user_action(request.user, 'payroll_calculate', payroll)
        messages.success(request, f"{staff.full_name} uchun oylik hisoblandi")
        return redirect('finance:payroll_list')

    # Statistika
    month_end = add_months(selected_month, 1) - timedelta(days=1)
    
    # O'tilgan darslar
    lessons_count = Lesson.objects.filter(
        teacher=staff,
        date__gte=selected_month,
        date__lte=month_end,
        status='finished'
    ).count()
    
    # Kechikishlar
    late_count = StaffAttendance.objects.filter(
        staff=staff,
        date__gte=selected_month,
        date__lte=month_end,
        status='late'
    ).count()
    
    # Yo'qlamalar
    absent_count = StaffAttendance.objects.filter(
        staff=staff,
        date__gte=selected_month,
        date__lte=month_end,
        status='absent'
    ).count()
    
    context = {
        'staff': staff,
        'payroll': payroll,
        'selected_month': selected_month,
        'lessons_count': lessons_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'created': created,
    }
    return render(request, 'finance/payroll_calculate.html', context)


@login_required
def approve_payroll(request, pk):
    """Oylikni tasdiqlash"""
    org = request.user.organization

    payroll_query = PayrollRecord.objects.filter(pk=pk)
    if org:
        payroll_query = payroll_query.filter(organization=org)

    payroll = get_object_or_404(payroll_query)

    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Sizda tasdiqlash huquqi yo'q")
        return redirect('finance:payroll_list')

    payroll.status = 'approved'
    payroll.approved_by = request.user
    payroll.approved_at = timezone.now()
    payroll.save()
    
    log_user_action(request.user, 'payroll_approve', payroll)
    messages.success(request, f"{payroll.staff.full_name} oyligi tasdiqlandi")
    return redirect('finance:payroll_list')


@login_required
def pay_salary(request, pk):
    """Oylikni to'lash (Tranzaksiya yaratish)"""
    org = request.user.organization

    payroll_query = PayrollRecord.objects.filter(pk=pk)
    if org:
        payroll_query = payroll_query.filter(organization=org)

    payroll = get_object_or_404(payroll_query)

    if payroll.status != 'approved':
        messages.error(request, "Avval oylikni tasdiqlang")
        return redirect('finance:payroll_list')

    if request.method == 'POST':
        account_id = request.POST.get('account')

        account_query = Account.objects.filter(pk=account_id)
        if org:
            account_query = account_query.filter(organization=org)
        account = get_object_or_404(account_query)

        # Kassada pul yetarlimi?
        if account.balance < payroll.net_salary:
            messages.error(request, f"Kassada yetarli mablag' yo'q ({account.balance:,.0f} / {payroll.net_salary:,.0f})")
            return redirect('finance:payroll_list')

        # Oylik kategoriyasini olish yoki yaratish
        category_defaults = {'transaction_type': 'expense'}
        if org:
            category_defaults['organization'] = org

        category, _ = TransactionCategory.objects.get_or_create(
            name="Xodimlar oyligi",
            defaults=category_defaults
        )
        
        # Tranzaksiya yaratish
        transaction_data = {
            'account': account,
            'category': category,
            'staff': payroll.staff,
            'amount': payroll.net_salary,
            'transaction_type': 'expense',
            'description': f"{payroll.staff.full_name} - {payroll.month.strftime('%B %Y')} oyligi",
            'status': 'confirmed',
            'created_by': request.user,
            'confirmed_by': request.user,
            'confirmed_at': timezone.now()
        }

        if org:
            transaction_data['organization'] = org

        Transaction.objects.create(**transaction_data)

        # Kassadan pul yechish
        account.balance -= payroll.net_salary
        account.save()
        
        # Payroll statusini yangilash
        payroll.status = 'paid'
        payroll.paid_at = timezone.now()
        payroll.save()
        
        log_user_action(request.user, 'salary_paid', payroll)
        messages.success(request, f"{payroll.staff.full_name}ga {payroll.net_salary:,.0f} so'm oylik to'landi")
        return redirect('finance:payroll_list')

    accounts = Account.objects.filter(is_deleted=False)
    if org:
        accounts = accounts.filter(organization=org)

    context = {
        'payroll': payroll,
        'accounts': accounts,
    }
    return render(request, 'finance/payroll_pay.html', context)


