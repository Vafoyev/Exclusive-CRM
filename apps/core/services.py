"""
Business logic services.
Markazlashtirilgan hisob-kitob va boshqa operatsiyalar.
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone


def calculate_student_stats(student):
    """
    O'quvchining to'liq statistikasini hisoblash.
    """
    from apps.operations.models import Attendance, Lesson
    from apps.finance.models import Transaction
    from apps.education.models import GroupStudent
    
    # Davomat
    attendances = Attendance.objects.filter(student=student)
    attendance_stats = attendances.aggregate(
        total_lessons=Count('id'),
        present_count=Count('id', filter=Q(status='present')),
        late_count=Count('id', filter=Q(status='late')),
        absent_count=Count('id', filter=Q(status='absent')),
        avg_grade=Avg('grade'),
    )
    total_lessons = attendance_stats['total_lessons'] or 0
    present_count = attendance_stats['present_count'] or 0
    late_count = attendance_stats['late_count'] or 0
    absent_count = attendance_stats['absent_count'] or 0
    
    attendance_rate = (present_count / total_lessons * 100) if total_lessons > 0 else 0
    
    # Baholar
    avg_grade = attendance_stats['avg_grade'] or 0
    
    # XP
    xp = student.profile_data.get('xp', 0)
    
    # Guruhlar
    active_groups = GroupStudent.objects.filter(student=student, status='active').count()
    
    # To'lovlar
    payments = Transaction.objects.filter(
        student=student,
        transaction_type='income',
        status='confirmed'
    )
    total_paid = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    return {
        'total_lessons': total_lessons,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'attendance_rate': round(attendance_rate, 1),
        'avg_grade': round(avg_grade, 1),
        'xp': xp,
        'active_groups': active_groups,
        'total_paid': total_paid,
        'balance': student.balance,
    }


def calculate_teacher_stats(teacher, month=None):
    """
    O'qituvchining statistikasi.
    """
    from apps.operations.models import Lesson, Attendance
    from apps.education.models import Group, GroupStudent
    
    if month is None:
        month = date.today().replace(day=1)
    
    next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    # Guruhlar
    groups = Group.objects.filter(teacher=teacher, status='active')
    
    # Darslar
    lessons = Lesson.objects.filter(
        teacher=teacher,
        date__gte=month,
        date__lt=next_month
    )
    completed_lessons = lessons.filter(status='finished').count()
    scheduled_lessons = lessons.filter(status='scheduled').count()
    
    # O'quvchilar
    students_count = GroupStudent.objects.filter(
        group__teacher=teacher,
        group__status='active',
        status='active'
    ).values('student').distinct().count()
    
    # Davomat
    attendances = Attendance.objects.filter(
        lesson__teacher=teacher,
        lesson__date__gte=month,
        lesson__date__lt=next_month
    )
    attendance_stats = attendances.aggregate(
        total_records=Count('id'),
        present=Count('id', filter=Q(status='present')),
        avg_grade=Avg('grade'),
    )
    total_records = attendance_stats['total_records'] or 0
    present = attendance_stats['present'] or 0
    attendance_rate = (present / total_records) * 100 if total_records > 0 else 0

    # O'rtacha baho
    avg_grade = attendance_stats['avg_grade'] or 0
    
    return {
        'groups_count': groups.count(),
        'students_count': students_count,
        'completed_lessons': completed_lessons,
        'scheduled_lessons': scheduled_lessons,
        'attendance_rate': round(attendance_rate, 1),
        'avg_grade': round(avg_grade, 1),
    }


def calculate_organization_stats(organization, period='month'):
    """
    Tashkilot umumiy statistikasi.
    Dashboard uchun.
    """
    from apps.users.models import User
    from apps.crm.models import Lead
    from apps.education.models import Group, GroupStudent
    from apps.operations.models import Lesson
    from apps.finance.models import Transaction
    
    today = date.today()
    
    if period == 'today':
        start_date = today
    elif period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today.replace(day=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
    else:
        start_date = today - timedelta(days=30)
    
    # Foydalanuvchilar
    students = User.objects.filter(organization=organization, role='student', is_active=True)
    teachers = User.objects.filter(organization=organization, role='teacher', is_active=True)
    
    # Guruhlar
    active_groups = Group.objects.filter(organization=organization, status='active')
    
    # Lidlar
    leads = Lead.objects.filter(organization=organization, created_at__date__gte=start_date)
    lead_counts = leads.aggregate(
        leads_count=Count('id'),
        won_leads=Count('id', filter=Q(stage__stage_type='won')),
    )
    leads_count = lead_counts['leads_count'] or 0
    won_leads_count = lead_counts['won_leads'] or 0
    
    # Moliya
    transactions = Transaction.objects.filter(
        organization=organization,
        created_at__date__gte=start_date,
        status='confirmed'
    )
    income = transactions.filter(transaction_type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    expense = transactions.filter(transaction_type__in=['expense', 'salary']).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Darslar
    lessons_today = Lesson.objects.filter(
        organization=organization,
        date=today
    )
    
    return {
        'students_count': students.count(),
        'teachers_count': teachers.count(),
        'active_groups': active_groups.count(),
        'leads_count': leads_count,
        'won_leads': won_leads_count,
        'conversion_rate': round((won_leads_count / leads_count * 100) if leads_count > 0 else 0, 1),
        'total_income': income,
        'total_expense': expense,
        'net_profit': income - expense,
        'lessons_today': lessons_today.count(),
        'lessons_scheduled': lessons_today.filter(status='scheduled').count(),
        'lessons_finished': lessons_today.filter(status='finished').count(),
    }


def get_financial_chart_data(organization, days=30):
    """
    Moliyaviy grafik uchun ma'lumotlar.
    Chart.js formatida.
    """
    from apps.finance.models import Transaction
    from django.db.models.functions import TruncDate
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    transactions = Transaction.objects.filter(
        organization=organization,
        created_at__date__gte=start_date,
        status='confirmed'
    ).annotate(
        date_only=TruncDate('created_at')
    ).values('date_only', 'transaction_type').annotate(
        total=Sum('amount')
    ).order_by('date_only')
    
    # Ma'lumotlarni qayta ishlash
    dates = []
    income_data = []
    expense_data = []
    
    current = start_date
    while current <= end_date:
        dates.append(current.strftime('%d.%m'))
        
        day_income = sum(
            float(t['total']) for t in transactions 
            if t['date_only'] == current and t['transaction_type'] == 'income'
        )
        day_expense = sum(
            float(t['total']) for t in transactions 
            if t['date_only'] == current and t['transaction_type'] in ['expense', 'salary']
        )
        
        income_data.append(day_income)
        expense_data.append(day_expense)
        
        current += timedelta(days=1)
    
    return {
        'labels': dates,
        'income': income_data,
        'expense': expense_data,
    }


def get_lead_sources_chart(organization, days=30):
    """
    Lead manbalari diagrammasi.
    """
    from apps.crm.models import Lead
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    leads = Lead.objects.filter(
        organization=organization,
        created_at__date__gte=start_date
    ).values('source__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return {
        'labels': [l['source__name'] or "Noma'lum" for l in leads],
        'data': [l['count'] for l in leads],
    }


def export_transactions_csv(organization, start_date, end_date):
    """
    Tranzaksiyalarni CSV formatda eksport qilish.
    """
    import csv
    from io import StringIO
    from apps.finance.models import Transaction
    
    transactions = Transaction.objects.filter(
        organization=organization,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).select_related('account', 'category', 'student', 'staff', 'created_by').order_by('created_at')
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Sana', 'Vaqt', 'Turi', 'Kategoriya', 'Summa', 'Kassa',
        "O'quvchi", 'Xodim', 'Izoh', 'Holat', 'Kiritdi'
    ])
    
    for t in transactions:
        writer.writerow([
            t.created_at.strftime('%d.%m.%Y'),
            t.created_at.strftime('%H:%M'),
            t.get_transaction_type_display(),
            t.category.name if t.category else '',
            float(t.amount),
            t.account.name,
            t.student.full_name if t.student else '',
            t.staff.full_name if t.staff else '',
            t.description,
            t.get_status_display(),
            t.created_by.full_name if t.created_by else '',
        ])
    
    return output.getvalue()


def check_low_stock_supplies(organization):
    """
    Kam qolgan sarf materiallarni tekshirish.
    """
    from apps.finance.inventory import Supply
    
    low_stock = Supply.objects.filter(
        organization=organization,
        quantity__lte=F('min_quantity')
    )
    
    return list(low_stock.values('id', 'name', 'quantity', 'min_quantity', 'unit'))


def calculate_group_profitability(group):
    """
    Guruh daromadliligini hisoblash.
    """
    from apps.education.models import GroupStudent
    from apps.finance.models import Transaction
    from apps.operations.models import Lesson
    
    # O'quvchilardan kelgan pul
    students = GroupStudent.objects.filter(group=group).values_list('student_id', flat=True)
    income = Transaction.objects.filter(
        student_id__in=students,
        transaction_type='income',
        status='confirmed'
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Darslar soni va o'qituvchi xarajati
    lessons = Lesson.objects.filter(group=group, status='finished').count()
    per_lesson_rate = 50000
    if group.teacher and group.teacher.profile_data:
        per_lesson_rate = group.teacher.profile_data.get('per_lesson_rate', 50000)
    teacher_cost = lessons * per_lesson_rate
    
    # Sof foyda
    profit = float(income) - teacher_cost
    
    return {
        'total_income': income,
        'teacher_cost': teacher_cost,
        'lessons_count': lessons,
        'profit': profit,
        'profit_per_lesson': profit / lessons if lessons > 0 else 0,
    }
