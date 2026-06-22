"""
Rol asosli Dashboard viewlari.
Har bir rol uchun alohida ma'lumotlar va statistikalar.
Cache bilan optimizatsiya qilingan.
"""
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection
from django.db.models import Avg, F, Q, Sum, Count, Window
from django.db.models.functions import RowNumber
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from apps.users.models import User, ParentStudent
from apps.organizations.models import Organization, Branch
from apps.crm.models import Lead, Stage
from apps.education.models import Course, Group, GroupStudent
from apps.operations.models import Lesson, Attendance
from apps.finance.models import Transaction, Account, MonthlyFeeCharge, MonthlyFeeRun
from apps.hardware.services import build_student_presence_map

DASHBOARD_CACHE_TIMEOUT = 60


def get_date_range(days=30):
    """So'nggi N kun uchun sana oralig'ini qaytaradi."""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def get_cached_or_compute(cache_key, compute_func, timeout=300):
    """
    Cache dan olish yoki hisoblash.
    Args:
        cache_key: Cache kaliti
        compute_func: Cache topilmasa chaqiriladigan funksiya
        timeout: Cache muddati (soniyalarda)
    """
    result = cache.get(cache_key)
    if result is None:
        result = compute_func()
        cache.set(cache_key, result, timeout)
    return result


def _dashboard_response(request, template_name, context):
    """
    Testlarda yengil mock request yuborilganda render o'rniga context qaytaradi.
    Real HTTP request uchun odatdagi template render ishlaydi.
    """
    if not hasattr(request, 'META'):
        return context
    return render(request, template_name, context)


def _dashboard_cache_key(name, *parts):
    normalized = [str(part if part is not None else 'none') for part in parts]
    return f"dashboard:{name}:{':'.join(normalized)}"


def _monthly_fee_tables_exist():
    cache_key = 'dashboard:monthly_fee_tables_exist'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        table_names = connection.introspection.table_names()
        exists = (
            MonthlyFeeCharge._meta.db_table in table_names
            and MonthlyFeeRun._meta.db_table in table_names
        )
    except DatabaseError:
        exists = False

    cache.set(cache_key, exists, 300 if exists else 5)
    return exists


def _build_student_leaderboard(organization, student_id=None):
    if not organization:
        return [], 0

    ranked_students = User.objects.filter(
        role='student',
        organization=organization,
        is_active=True,
        is_deleted=False,
    ).annotate(
        xp_total=Sum('lesson_attendances__xp_points'),
    ).exclude(
        xp_total__isnull=True,
    ).annotate(
        rank=Window(
            expression=RowNumber(),
            order_by=[F('xp_total').desc(), F('id').asc()],
        )
    ).order_by('rank')

    leaderboard = list(ranked_students[:10])
    if not student_id:
        return leaderboard, 0

    student_rank = ranked_students.filter(id=student_id).values_list('rank', flat=True).first() or 0
    return leaderboard, student_rank


def _build_parent_dashboard_data(parent):
    children_relations = list(
        ParentStudent.objects.filter(parent=parent).select_related('student')
    )
    if not children_relations:
        return []

    child_ids = [relation.student_id for relation in children_relations]
    student_presence_map = build_student_presence_map(child_ids)

    enrollments_map = {child_id: [] for child_id in child_ids}
    for enrollment in GroupStudent.objects.filter(
        student_id__in=child_ids,
        status='active'
    ).select_related('group', 'group__course', 'group__teacher'):
        enrollments_map.setdefault(enrollment.student_id, []).append(enrollment)

    stats_map = {
        row['student_id']: row
        for row in Attendance.objects.filter(
            student_id__in=child_ids
        ).values('student_id').annotate(
            total_att=Count('id'),
            present=Count('id', filter=Q(status='present')),
            avg_grade=Avg('grade'),
            total_xp=Sum('xp_points'),
        )
    }

    recent_attendance_map = {child_id: [] for child_id in child_ids}
    recent_attendance_qs = Attendance.objects.filter(
        student_id__in=child_ids
    ).annotate(
        row_number=Window(
            expression=RowNumber(),
            partition_by=[F('student_id')],
            order_by=[F('lesson__date').desc(), F('id').desc()],
        )
    ).filter(
        row_number__lte=5
    ).select_related(
        'lesson', 'lesson__group'
    ).order_by(
        'student_id', '-lesson__date', '-id'
    )
    for attendance in recent_attendance_qs:
        recent_attendance_map.setdefault(attendance.student_id, []).append(attendance)

    children_data = []
    for relation in children_relations:
        child = relation.student
        stats = stats_map.get(child.id, {})
        total_att = stats.get('total_att') or 0
        present = stats.get('present') or 0
        attendance_rate = (present / total_att * 100) if total_att > 0 else 0
        avg_grade = stats.get('avg_grade') or 0
        total_xp = stats.get('total_xp') or 0
        student_presence = student_presence_map.get(child.id, {})

        children_data.append({
            'child': child,
            'relation_type': relation.get_relation_type_display(),
            'enrollments': enrollments_map.get(child.id, []),
            'attendance_rate': round(attendance_rate, 1),
            'avg_grade': round(avg_grade, 1),
            'balance': child.balance,
            'has_debt': child.balance < 0,
            'xp': total_xp,
            'recent_attendance': recent_attendance_map.get(child.id, []),
            'missed_lessons_count': student_presence.get('missed_lessons_count', 0),
            'today_presence': student_presence.get('today_presence'),
            'recent_face_logs': student_presence.get('recent_face_logs', []),
        })

    return children_data


@login_required
def role_based_dashboard(request):
    """
    Foydalanuvchi roliga qarab tegishli dashboardga yo'naltiradi.
    """
    user = request.user
    role = user.role
    
    if role == 'super_admin':
        return super_admin_dashboard(request)
    elif role in ['owner', 'admin']:
        return admin_dashboard(request)
    elif role == 'teacher':
        return teacher_dashboard(request)
    elif role == 'student':
        return student_dashboard(request)
    elif role == 'parent':
        return parent_dashboard(request)
    else:
        return staff_dashboard(request)


@login_required
def super_admin_dashboard(request):
    """
    Super Admin uchun - butun tizim statistikasi.
    Moliya, O'quvchilar, Qarzdorlik, Bildirishnomalar - barcha muhim ma'lumotlar.
    """
    from apps.finance.inventory import Supply
    from apps.finance.payroll import StaffAttendance
    
    period = request.GET.get('period', 'monthly')
    cache_key = _dashboard_cache_key('super_admin', request.user.pk, period)
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return _dashboard_response(request, 'dashboards/super_admin.html', cached_context)

    today = timezone.now().date()
    
    # ====== HAFTALIK/OYLIK TOGGLE ======
    if period == 'weekly':
        start_date, end_date = get_date_range(7)
        period_label = "Haftalik"
    else:
        start_date, end_date = get_date_range(30)
        period_label = "Oylik"
    
    # ====== TASHKILOTLAR ======
    organization_stats = Organization.objects.filter(is_deleted=False).aggregate(
        total_orgs=Count('id'),
        active_orgs=Count('id', filter=Q(is_active=True)),
    )
    total_orgs = organization_stats['total_orgs'] or 0
    active_orgs = organization_stats['active_orgs'] or 0
    
    # ====== FOYDALANUVCHILAR ======
    total_users = User.objects.filter(is_active=True).count()
    users_by_role = User.objects.filter(is_active=True).values('role').annotate(count=Count('id'))
    users_by_role_dict = {item['role']: item['count'] for item in users_by_role}
    
    # O'quvchilar statistikasi
    total_students = users_by_role_dict.get('student', 0)
    active_students = User.objects.filter(role='student', is_active=True, is_deleted=False).count()
    frozen_students = GroupStudent.objects.filter(status='frozen').values('student').distinct().count()
    
    # ====== BUGUNGI STATISTIKA ======
    new_users_today = User.objects.filter(date_joined__date=today).count()
    new_leads_today = Lead.objects.filter(created_at__date=today).count()
    
    # ====== MOLIYA (BARCHA TASHKILOTLAR BO'YICHA) ======
    today_transaction_stats = Transaction.objects.filter(
        status='confirmed',
        created_at__date=today
    ).aggregate(
        today_income=Sum('amount', filter=Q(transaction_type='income')),
        today_expense=Sum('amount', filter=Q(transaction_type='expense')),
    )
    today_income = today_transaction_stats['today_income'] or 0
    today_expense = today_transaction_stats['today_expense'] or 0
    
    # Davr bo'yicha (haftalik/oylik)
    period_transaction_stats = Transaction.objects.filter(
        status='confirmed',
        created_at__range=[start_date, end_date]
    ).aggregate(
        period_income=Sum('amount', filter=Q(transaction_type='income')),
        period_expense=Sum('amount', filter=Q(transaction_type='expense')),
    )
    period_income = period_transaction_stats['period_income'] or 0
    period_expense = period_transaction_stats['period_expense'] or 0
    
    net_profit = period_income - period_expense
    
    # Umumiy asosiy (main) kassalar qoldig'i
    accounts_qs = Account.objects.filter(is_deleted=False)
    organization = getattr(request, 'organization', None)
    if organization:
        accounts_qs = accounts_qs.filter(organization=organization)
    account_balance_stats = accounts_qs.aggregate(
        total=Sum('balance'),
        main_cash_balance=Sum('balance', filter=~Q(name__startswith='Admin Kassa')),
        admin_cash_balance=Sum('balance', filter=Q(name__startswith='Admin Kassa')),
    )
    main_kassa_balance = account_balance_stats['total'] or 0
    main_cash_balance = account_balance_stats['main_cash_balance'] or 0
    admin_cash_balance = account_balance_stats['admin_cash_balance'] or 0

    billing_month = today.replace(day=1)
    current_month_fee_amount = 0
    current_month_fee_students = 0
    current_month_fee_charges = 0
    recent_monthly_fee_runs = []
    if _monthly_fee_tables_exist():
        try:
            monthly_fee_stats = MonthlyFeeCharge.objects.filter(
                billing_month=billing_month
            ).aggregate(
                total_amount=Sum('amount'),
                total_students=Count('student', distinct=True),
                total_charges=Count('id'),
            )
            current_month_fee_amount = monthly_fee_stats['total_amount'] or 0
            current_month_fee_students = monthly_fee_stats['total_students'] or 0
            current_month_fee_charges = monthly_fee_stats['total_charges'] or 0
            recent_monthly_fee_runs = list(
                MonthlyFeeRun.objects.select_related('triggered_by', 'target_student').order_by('-triggered_at')[:6]
            )
        except DatabaseError:
            cache.delete('dashboard:monthly_fee_tables_exist')
    
    # ====== KUNLIK XARAJATLAR TAQSIMOTI ======
    daily_expenses = Transaction.objects.filter(
        transaction_type='expense',
        status='confirmed',
        created_at__date=today
    ).values('category').annotate(
        total=Sum('amount')
    ).order_by('-total')[:5]
    
    # ====== QARZDORLIK ======
    debtors = User.objects.filter(role='student', balance__lt=0, is_active=True)
    debt_stats = debtors.aggregate(
        total_debt=Sum('balance'),
        debtors_count=Count('id'),
    )
    total_debt = abs(debt_stats['total_debt'] or 0)
    debtors_count = debt_stats['debtors_count'] or 0
    
    # ====== TUG'ILGAN KUNLAR ======
    today_birthdays = User.objects.filter(
        is_active=True,
        birth_date__month=today.month,
        birth_date__day=today.day
    ).select_related('organization')[:10]
    
    # ====== DAVOMAT (BUGUNGI) ======
    today_lessons = Lesson.objects.filter(date=today)
    lesson_stats = today_lessons.aggregate(
        total_today_lessons=Count('id'),
        finished_lessons=Count('id', filter=Q(status='finished')),
        attendance_taken_lessons=Count('id', filter=Q(attendances__isnull=False), distinct=True),
    )
    total_today_lessons = lesson_stats['total_today_lessons'] or 0
    finished_lessons = lesson_stats['finished_lessons'] or 0
    attendance_taken_lessons = lesson_stats['attendance_taken_lessons'] or 0

    # O'quvchilar davomati foizi
    attendance_stats = Attendance.objects.filter(lesson__date=today).aggregate(
        total_attendances=Count('id'),
        present_count=Count('id', filter=Q(status='present')),
    )
    total_attendances = attendance_stats['total_attendances'] or 0
    present_count = attendance_stats['present_count'] or 0
    attendance_rate = (present_count / total_attendances * 100) if total_attendances > 0 else 0
    
    # ====== GURUHLAR ======
    group_stats = Group.objects.filter(is_deleted=False).aggregate(
        total_groups=Count('id'),
        active_groups=Count('id', filter=Q(status='active')),
    )
    total_groups = group_stats['total_groups'] or 0
    active_groups = group_stats['active_groups'] or 0
    
    # ====== OXIRGI HARAKATLAR ======
    recent_orgs = Organization.objects.filter(is_deleted=False).order_by('-created_at')[:5]
    recent_users = User.objects.filter(is_active=True).order_by('-date_joined')[:10]
    recent_transactions = Transaction.objects.filter(status='confirmed').order_by('-created_at')[:5]
    
    # ====== KUTILAYOTGAN TO'LOVLAR (Tasdiqlanmagan) ======
    pending_payments = Transaction.objects.filter(
        status='pending',
        transaction_type='income'
    ).count()
    
    # ====== TASDIQLANMAGAN CHEKLAR ======
    pending_receipts_qs = Transaction.objects.filter(
        status='pending',
        receipt_verified=False,
        payment_method__in=Transaction.non_cash_payment_values()
    )
    pending_receipts_stats = pending_receipts_qs.aggregate(
        pending_receipts=Count('id'),
        pending_receipts_sum=Sum('amount'),
    )
    pending_receipts = pending_receipts_stats['pending_receipts'] or 0
    pending_receipts_sum = pending_receipts_stats['pending_receipts_sum'] or 0
    pending_receipts_list = pending_receipts_qs.select_related('student', 'created_by').order_by('-created_at')[:5]
    
    # ====== KAM QOLGAN MAHSULOTLAR (SKLAD) ======
    low_stock_qs = Supply.objects.filter(
        is_deleted=False,
        quantity__lte=F('min_quantity')
    )
    low_stock_items = low_stock_qs[:10]
    low_stock_count = low_stock_qs.count()
    
    # Quick Payment uchun o'quvchilar ro'yxati
    students_for_payment = list(
        User.objects.filter(
            role='student', is_active=True, is_deleted=False
        ).values('id', 'first_name', 'last_name', 'phone').order_by('first_name', 'last_name')
    )
    
    # Kassalar ro'yxati (Quick Payment uchun)
    accounts = Account.objects.filter(is_deleted=False)
    
    # ====== O'Z DAVOMATI (Super Admin) ======
    my_attendance = None
    try:
        my_attendance = StaffAttendance.objects.get(
            staff=request.user,
            date=today
        )
    except StaffAttendance.DoesNotExist:
        pass
    
    context = {
        # Tashkilotlar
        'total_orgs': total_orgs,
        'active_orgs': active_orgs,
        
        # Foydalanuvchilar
        'total_users': total_users,
        'users_by_role': users_by_role_dict,
        'total_students': total_students,
        'active_students': active_students,
        'frozen_students': frozen_students,
        
        # Bugungi
        'new_users_today': new_users_today,
        'new_leads_today': new_leads_today,
        
        # Moliya (haftalik/oylik toggle)
        'period': period,
        'period_label': period_label,
        'today_income': today_income,
        'today_expense': today_expense,
        'period_income': period_income,
        'period_expense': period_expense,
        'net_profit': net_profit,
        'main_kassa_balance': main_kassa_balance,
        'main_cash_balance': main_cash_balance,
        'admin_cash_balance': admin_cash_balance,
        'daily_expenses': daily_expenses,
        'monthly_fee_default_month': billing_month.strftime('%Y-%m'),
        'current_month_fee_amount': current_month_fee_amount,
        'current_month_fee_students': current_month_fee_students,
        'current_month_fee_charges': current_month_fee_charges,
        'recent_monthly_fee_runs': recent_monthly_fee_runs,
        
        # Qarzdorlik
        'total_debt': total_debt,
        'debtors_count': debtors_count,
        
        # Tug'ilgan kunlar
        'today_birthdays': today_birthdays,
        
        # Davomat
        'total_today_lessons': total_today_lessons,
        'finished_lessons': finished_lessons,
        'attendance_taken_lessons': attendance_taken_lessons,
        'attendance_rate': round(attendance_rate, 1),
        
        # Guruhlar
        'total_groups': total_groups,
        'active_groups': active_groups,
        
        # Oxirgi harakatlar
        'recent_orgs': recent_orgs,
        'recent_users': recent_users,
        'recent_transactions': recent_transactions,
        
        # Bildirishnomalar
        'pending_payments': pending_payments,
        'pending_receipts': pending_receipts,
        'pending_receipts_sum': pending_receipts_sum,
        'pending_receipts_list': pending_receipts_list,
        'low_stock_items': low_stock_items,
        'low_stock_count': low_stock_count,
        'today': today,
        
        # Quick Payment
        'students_for_payment': students_for_payment,
        'accounts': accounts,
        
        # O'z davomati
        'my_attendance': my_attendance,
    }
    
    cache.set(cache_key, context, DASHBOARD_CACHE_TIMEOUT)
    return _dashboard_response(request, 'dashboards/super_admin.html', context)


@login_required
def admin_dashboard(request):
    """
    Admin/Owner uchun - o'z tashkiloti statistikasi.
    """
    org = request.user.organization
    today = timezone.now().date()
    cache_key = _dashboard_cache_key('admin', request.user.pk, getattr(org, 'pk', None), today.isoformat())
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return _dashboard_response(request, 'dashboards/admin.html', cached_context)
    
    user_stats = User.objects.filter(organization=org).aggregate(
        total_students=Count('id', filter=Q(role='student', is_active=True, is_deleted=False)),
        total_teachers=Count('id', filter=Q(role='teacher', is_active=True, is_deleted=False)),
        total_debt=Sum('balance', filter=Q(role='student', balance__lt=0)),
    )
    total_students = user_stats['total_students'] or 0
    total_teachers = user_stats['total_teachers'] or 0
    total_debt = user_stats['total_debt'] or 0
    
    # Guruhlar
    active_groups = Group.objects.filter(
        organization=org, status='active', is_deleted=False
    ).count()
    
    # Lidlar
    leads_qs = Lead.objects.filter(organization=org, is_deleted=False)
    lead_stats = leads_qs.aggregate(
        total_leads=Count('id'),
        new_leads=Count('id', filter=Q(created_at__date=today)),
    )
    total_leads = lead_stats['total_leads'] or 0
    new_leads = lead_stats['new_leads'] or 0
    
    # Moliya
    start_date, end_date = get_date_range(30)
    monthly_income = Transaction.objects.filter(
        organization=org,
        transaction_type='income',
        status='confirmed',
        created_at__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Qarzdorlik
    # Bugungi darslar
    today_lessons = Lesson.objects.filter(
        organization=org,
        date=today
    ).select_related('group', 'teacher', 'room').order_by('start_time')[:10]
    
    # So'nggi lidlar
    recent_leads = Lead.objects.filter(
        organization=org, is_deleted=False
    ).select_related('source', 'stage').order_by('-created_at')[:5]
    
    # Voronka bosqichlari
    stages = Stage.objects.filter(organization=org).annotate(
        lead_count=Count('leads', filter=Q(leads__is_deleted=False))
    ).order_by('order')
    
    # Quick Payment uchun o'quvchilar ro'yxati
    students_for_payment = json.dumps(list(
        User.objects.filter(
            organization=org, role='student', is_active=True, is_deleted=False
        ).values('id', 'first_name', 'last_name', 'phone').order_by('first_name', 'last_name')
    ))
    
    # Kassalar ro'yxati (Quick Payment uchun)
    accounts = Account.objects.filter(organization=org, is_deleted=False)
    
    # ====== KUTILAYOTGAN TO'LOVLAR (Tasdiqlanmagan) ======
    pending_payments = Transaction.objects.filter(
        organization=org,
        status='pending',
        transaction_type='income'
    ).count()
    
    # ====== TASDIQLANMAGAN CHEKLAR ======
    pending_receipts_qs = Transaction.objects.filter(
        organization=org,
        status='pending',
        receipt_verified=False,
        payment_method__in=Transaction.non_cash_payment_values()
    )
    pending_receipts_stats = pending_receipts_qs.aggregate(
        pending_receipts=Count('id'),
        pending_receipts_sum=Sum('amount'),
    )
    pending_receipts = pending_receipts_stats['pending_receipts'] or 0
    pending_receipts_sum = pending_receipts_stats['pending_receipts_sum'] or 0
    pending_receipts_list = pending_receipts_qs.select_related('student', 'created_by').order_by('-created_at')[:5]
    
    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'active_groups': active_groups,
        'total_leads': total_leads,
        'new_leads': new_leads,
        'monthly_income': monthly_income,
        'total_debt': abs(total_debt),
        'today_lessons': today_lessons,
        'recent_leads': recent_leads,
        'stages': stages,
        'students_for_payment': students_for_payment,
        'accounts': accounts,
        'pending_payments': pending_payments,
        'pending_receipts': pending_receipts,
        'pending_receipts_sum': pending_receipts_sum,
        'pending_receipts_list': pending_receipts_list,
    }
    
    cache.set(cache_key, context, DASHBOARD_CACHE_TIMEOUT)
    return _dashboard_response(request, 'dashboards/admin.html', context)


@login_required
def teacher_dashboard(request):
    """
    O'qituvchi uchun - o'z guruhlari va darslari.
    KPI statistikasi va reyting bilan.
    """
    from apps.finance.payroll import StaffAttendance
    
    teacher = request.user
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    cache_key = _dashboard_cache_key('teacher', teacher.pk, today.isoformat())
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return _dashboard_response(request, 'dashboards/teacher.html', cached_context)
    
    # Mening guruhlarim
    my_groups = Group.objects.filter(
        teacher=teacher, 
        status__in=['active', 'pending'],
        is_deleted=False
    ).select_related('course', 'room').annotate(
        student_count=Count('students', filter=Q(students__status='active'))
    )
    
    # Bugungi darslarim
    today_lessons = Lesson.objects.filter(
        teacher=teacher,
        date=today
    ).select_related('group', 'room').order_by('start_time')
    
    # Keyingi darslarim (5 kun)
    upcoming_lessons = Lesson.objects.filter(
        teacher=teacher,
        date__gt=today,
        date__lte=today + timedelta(days=5)
    ).select_related('group', 'room').order_by('date', 'start_time')[:10]
    
    # O'tkazilmagan darslar (davomat belgilanmagan)
    pending_attendance = Lesson.objects.filter(
        teacher=teacher,
        date__lte=today,
        status='scheduled'
    ).select_related('group').order_by('-date')[:5]
    
    # Umumiy statistika
    total_students = GroupStudent.objects.filter(
        group__teacher=teacher,
        group__status='active',
        status='active'
    ).count()
    
    # ====== KPI STATISTIKASI ======
    # Oylik darslar
    monthly_lessons = Lesson.objects.filter(
        teacher=teacher,
        date__gte=start_of_month,
        date__lte=today
    )
    monthly_lesson_stats = monthly_lessons.aggregate(
        total_monthly_lessons=Count('id'),
        completed_lessons=Count('id', filter=Q(status='finished')),
    )
    total_monthly_lessons = monthly_lesson_stats['total_monthly_lessons'] or 0
    completed_lessons = monthly_lesson_stats['completed_lessons'] or 0
    lesson_completion_rate = (completed_lessons / total_monthly_lessons * 100) if total_monthly_lessons > 0 else 0
    
    # O'quvchilar davomati (mening darslarimda)
    monthly_attendance_stats = Attendance.objects.filter(
        lesson__teacher=teacher,
        lesson__date__gte=start_of_month,
        lesson__date__lte=today
    ).aggregate(
        total_attendance_records=Count('id'),
        present_records=Count('id', filter=Q(status='present')),
        avg_grade_given=Avg('grade'),
        total_xp_given=Sum('xp_points'),
    )
    total_attendance_records = monthly_attendance_stats['total_attendance_records'] or 0
    present_records = monthly_attendance_stats['present_records'] or 0
    student_attendance_rate = (present_records / total_attendance_records * 100) if total_attendance_records > 0 else 0
    
    # O'rtacha baho (bergan baholarim)
    avg_grade_given = monthly_attendance_stats['avg_grade_given'] or 0
    
    # XP berilgani
    total_xp_given = monthly_attendance_stats['total_xp_given'] or 0
    
    # ====== O'Z DAVOMATI (Teacher) ======
    my_attendance = None
    try:
        my_attendance = StaffAttendance.objects.get(
            staff=teacher,
            date=today
        )
    except StaffAttendance.DoesNotExist:
        pass
    
    context = {
        'my_groups': my_groups,
        'today_lessons': today_lessons,
        'upcoming_lessons': upcoming_lessons,
        'pending_attendance': pending_attendance,
        'total_students': total_students,
        'today': today,
        # KPI
        'total_monthly_lessons': total_monthly_lessons,
        'completed_lessons': completed_lessons,
        'lesson_completion_rate': round(lesson_completion_rate, 1),
        'student_attendance_rate': round(student_attendance_rate, 1),
        'avg_grade_given': round(avg_grade_given, 1),
        'total_xp_given': total_xp_given,
        # O'z davomati
        'my_attendance': my_attendance,
    }
    
    cache.set(cache_key, context, DASHBOARD_CACHE_TIMEOUT)
    return _dashboard_response(request, 'dashboards/teacher.html', context)


@login_required
def student_dashboard(request):
    """
    O'quvchi uchun - dars jadvali, baholar, to'lovlar.
    Leaderboard va gamifikatsiya bilan.
    """
    from apps.operations.shop import ShopItem
    
    student = request.user
    today = timezone.now().date()
    cache_key = _dashboard_cache_key('student', student.pk, today.isoformat())
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return _dashboard_response(request, 'dashboards/student.html', cached_context)
    
    # Mening guruhlarim
    my_enrollments = list(GroupStudent.objects.filter(
        student=student,
        status='active'
    ).select_related('group', 'group__course', 'group__teacher', 'group__room'))
    group_ids = [enrollment.group_id for enrollment in my_enrollments]
    
    # Bugungi darslarim
    today_lessons = Lesson.objects.filter(
        group_id__in=group_ids,
        date=today
    ).select_related('group', 'teacher', 'room').order_by('start_time')
    
    # Keyingi darslar
    upcoming_lessons = Lesson.objects.filter(
        group_id__in=group_ids,
        date__gt=today
    ).select_related('group', 'teacher', 'room').order_by('date', 'start_time')[:10]
    
    # Davomatim
    attendance_qs = Attendance.objects.filter(student=student)
    my_attendance = attendance_qs.select_related(
        'lesson', 'lesson__group'
    ).order_by('-lesson__date')[:20]
    presence_summary = build_student_presence_map([student.id]).get(student.id, {})
    
    # Statistikalar
    attendance_stats = attendance_qs.aggregate(
        total_lessons=Count('id'),
        present_count=Count('id', filter=Q(status='present')),
        avg_grade=Avg('grade'),
        total_xp=Sum('xp_points'),
    )
    total_lessons = attendance_stats['total_lessons'] or 0
    present_count = attendance_stats['present_count'] or 0
    attendance_rate = (present_count / total_lessons * 100) if total_lessons > 0 else 0
    avg_grade = attendance_stats['avg_grade'] or 0
    total_xp = attendance_stats['total_xp'] or 0
    
    # Coin (profile_data dan yoki XP dan)
    coin_balance = student.profile_data.get('xp', total_xp) if hasattr(student, 'profile_data') and student.profile_data else total_xp
    
    # Balans
    balance = student.balance
    
    # To'lovlar tarixi
    payments = Transaction.objects.filter(
        student=student
    ).select_related('account', 'category', 'confirmed_by').order_by('-created_at')[:10]

    # Chart Data (So'nggi 10 ta baho)
    grade_history = list(
        attendance_qs.filter(
            grade__isnull=False
        ).select_related('lesson').order_by('-lesson__date')[:10]
    )
    grade_history.reverse()
    
    chart_labels = [att.lesson.date.strftime('%d.%m') for att in grade_history]
    chart_data = [att.grade for att in grade_history]
    
    # ====== LEADERBOARD (Top 10 XP bo'yicha) ======
    # O'quvchining tashkilotidagi eng ko'p XP yig'ganlar
    org = student.organization
    leaderboard, student_rank = _build_student_leaderboard(org, student.id)
    
    # ====== SHOP ======
    shop_items_count = ShopItem.objects.filter(
        organization=org,
        is_active=True,
        is_deleted=False
    ).count() if org else 0
    
    context = {
        'my_enrollments': my_enrollments,
        'today_lessons': today_lessons,
        'upcoming_lessons': upcoming_lessons,
        'my_attendance': my_attendance,
        'attendance_rate': round(attendance_rate, 1),
        'avg_grade': round(avg_grade, 1),
        'total_xp': total_xp,
        'coin_balance': coin_balance,
        'balance': balance,
        'payments': payments,
        'today': today,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'missed_lessons_count': presence_summary.get('missed_lessons_count', 0),
        'late_lessons_count': presence_summary.get('late_lessons_count', 0),
        'today_presence': presence_summary.get('today_presence'),
        'recent_face_logs': presence_summary.get('recent_face_logs', []),
        # Leaderboard
        'leaderboard': leaderboard,
        'student_rank': student_rank,
        # Shop
        'shop_items_count': shop_items_count,
    }
    
    cache.set(cache_key, context, DASHBOARD_CACHE_TIMEOUT)
    return _dashboard_response(request, 'dashboards/student.html', context)


@login_required
def parent_dashboard(request):
    """
    Ota-ona uchun - farzandlari haqida ma'lumot.
    """
    parent = request.user
    today = timezone.now().date()
    cache_key = _dashboard_cache_key('parent', parent.pk, today.isoformat())
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return _dashboard_response(request, 'dashboards/parent.html', cached_context)
    
    children_data = _build_parent_dashboard_data(parent)
    
    # Umumiy qarzdorlik
    total_debt = sum(abs(d['balance']) for d in children_data if d['has_debt'])
    has_any_debt = any(d['has_debt'] for d in children_data)
    
    context = {
        'children_data': children_data,
        'today': today,
        'total_debt': total_debt,
        'has_any_debt': has_any_debt,
    }
    
    cache.set(cache_key, context, DASHBOARD_CACHE_TIMEOUT)
    return _dashboard_response(request, 'dashboards/parent.html', context)


@login_required
def staff_dashboard(request):
    """
    Oddiy xodim uchun - umumiy ma'lumotlar.
    """
    user = request.user
    today = timezone.now().date()
    org = user.organization
    cache_key = _dashboard_cache_key('staff', user.pk, getattr(org, 'pk', None), today.isoformat())
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return _dashboard_response(request, 'dashboards/staff.html', cached_context)
    
    # Bugungi darslar (tashkilot bo'yicha)
    today_lessons_count = 0
    total_students_count = 0
    active_groups_count = 0
    
    if org:
        today_lessons_count = Lesson.objects.filter(
            organization=org, date=today
        ).count()
        total_students_count = User.objects.filter(
            organization=org, role='student', is_active=True, is_deleted=False
        ).count()
        active_groups_count = Group.objects.filter(
            organization=org, status='active', is_deleted=False
        ).count()
    
    context = {
        'user': user,
        'today': today,
        'today_lessons_count': today_lessons_count,
        'total_students_count': total_students_count,
        'active_groups_count': active_groups_count,
    }
    cache.set(cache_key, context, DASHBOARD_CACHE_TIMEOUT)
    return _dashboard_response(request, 'dashboards/staff.html', context)
