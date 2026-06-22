from django.contrib import admin
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta


def dashboard_callback(request, context):
    """
    Admin dashboard uchun statistika ma'lumotlarini qaytaradi.
    Bu funksiya Unfold admin panel index sahifasida ko'rsatiladi.
    """
    from apps.users.models import User
    from apps.education.models import Group, Course, GroupStudent
    from apps.finance.models import Transaction
    from apps.crm.models import Lead, Stage
    from apps.operations.models import Lesson, Attendance
    from apps.organizations.models import Organization, Branch

    today = timezone.now().date()
    month_start = today.replace(day=1)
    week_ago = today - timedelta(days=7)

    # ========== FOYDALANUVCHILAR STATISTIKASI ==========
    total_users = User.objects.count()
    students = User.objects.filter(role='student').count()
    teachers = User.objects.filter(role='teacher').count()
    active_users = User.objects.filter(is_active=True).count()
    new_users_week = User.objects.filter(date_joined__gte=week_ago).count()

    # ========== TA'LIM STATISTIKASI ==========
    total_groups = Group.objects.count()
    active_groups = Group.objects.filter(status='active').count()
    total_courses = Course.objects.filter(is_active=True).count()
    total_enrollments = GroupStudent.objects.filter(status='active').count()

    # ========== MOLIYA STATISTIKASI ==========
    monthly_income = Transaction.objects.filter(
        transaction_type='income',
        status='confirmed',
        created_at__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0

    monthly_expense = Transaction.objects.filter(
        transaction_type='expense',
        status='confirmed',
        created_at__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0

    pending_transactions = Transaction.objects.filter(status='pending').count()

    # ========== CRM STATISTIKASI ==========
    total_leads = Lead.objects.filter(is_deleted=False).count()
    new_leads_week = Lead.objects.filter(
        is_deleted=False,
        created_at__gte=week_ago
    ).count()
    won_leads = Lead.objects.filter(
        is_deleted=False,
        stage__is_won=True
    ).count()

    # ========== DARSLAR STATISTIKASI ==========
    today_lessons = Lesson.objects.filter(date=today).count()
    finished_lessons_month = Lesson.objects.filter(
        status='finished',
        date__gte=month_start
    ).count()

    # ========== TASHKILOTLAR ==========
    total_organizations = Organization.objects.filter(is_active=True).count()
    total_branches = Branch.objects.count()

    # ========== XATOLAR VA OGOHLANTIRISHLAR ==========
    warnings = []
    errors = []
    info_alerts = []

    # Qarzdor o'quvchilar
    debt_students = User.objects.filter(role='student', balance__lt=0).count()
    if debt_students > 0:
        total_debt = User.objects.filter(role='student', balance__lt=0).aggregate(
            total=Sum('balance')
        )['total'] or 0
        warnings.append({
            'type': 'warning',
            'icon': 'warning',
            'title': f"{debt_students} ta qarzdor o'quvchi",
            'description': f"Jami qarz: {abs(total_debt):,.0f} so'm",
            'link': '/admin/users/user/?balance__lt=0&role__exact=student'
        })

    # Kutilayotgan tranzaksiyalar
    if pending_transactions > 0:
        pending_amount = Transaction.objects.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or 0
        alert_type = 'error' if pending_transactions > 10 else 'warning'
        (errors if alert_type == 'error' else warnings).append({
            'type': alert_type,
            'icon': 'pending_actions',
            'title': f"{pending_transactions} ta kutilayotgan tranzaksiya",
            'description': f"Jami summa: {pending_amount:,.0f} so'm",
            'link': '/admin/finance/transaction/?status__exact=pending'
        })

    # Bo'sh guruhlar
    empty_groups = Group.objects.filter(status='active').annotate(
        student_count=Count('students')
    ).filter(student_count=0).count()
    if empty_groups > 0:
        info_alerts.append({
            'type': 'info',
            'icon': 'group_off',
            'title': f"{empty_groups} ta bo'sh guruh",
            'description': "O'quvchisi yo'q faol guruhlar",
            'link': '/admin/education/group/?status__exact=active'
        })

    # Nofaol o'qituvchilar
    inactive_teachers = User.objects.filter(role='teacher', is_active=False).count()
    if inactive_teachers > 0:
        errors.append({
            'type': 'error',
            'icon': 'person_off',
            'title': f"{inactive_teachers} ta nofaol o'qituvchi",
            'description': "Nofaol holatdagi o'qituvchilar",
            'link': '/admin/users/user/?role__exact=teacher&is_active__exact=0'
        })

    # Bugungi darslar
    if today_lessons == 0:
        info_alerts.append({
            'type': 'info',
            'icon': 'event_busy',
            'title': "Bugun dars yo'q",
            'description': "Bugungi kunga dars rejalashtirilmagan",
            'link': '/admin/operations/lesson/'
        })

    # Yopilayotgan guruhlar (pending statusida uzoq vaqt turgan)
    old_forming_groups = Group.objects.filter(
        status='pending',
        created_at__lte=timezone.now() - timedelta(days=30)
    ).count()
    if old_forming_groups > 0:
        warnings.append({
            'type': 'warning',
            'icon': 'groups',
            'title': f"{old_forming_groups} ta eski 'yig'ilmoqda' guruh",
            'description': "30 kundan ko'p yig'ilmoqda holatida turgan guruhlar",
            'link': '/admin/education/group/?status__exact=pending'
        })

    # Yopiq lidlar (uzoq vaqt yangilanmagan)
    stale_leads = Lead.objects.filter(
        is_deleted=False,
        updated_at__lte=timezone.now() - timedelta(days=14)
    ).exclude(stage__is_won=True).count()
    if stale_leads > 0:
        warnings.append({
            'type': 'warning',
            'icon': 'hourglass_empty',
            'title': f"{stale_leads} ta eskirgan lid",
            'description': "14 kundan ko'p yangilanmagan lidlar",
            'link': '/admin/crm/lead/'
        })

    # Nofaol foydalanuvchilar (30 kundan ko'p login qilmagan)
    # inactive_logins = User.objects.filter(
    #     is_active=True,
    #     last_login__lte=timezone.now() - timedelta(days=30)
    # ).count()
    # if inactive_logins > 10:
    #     info_alerts.append({
    #         'type': 'info',
    #         'icon': 'person_off',
    #         'title': f"{inactive_logins} ta nofaol foydalanuvchi",
    #         'description': "30 kundan ko'p tizimga kirmagan",
    #         'link': '/admin/users/user/'
    #     })

    # ========== CONTEXT GA QO'SHISH ==========
    context.update({
        # Statistika kartochkalari
        "stats": [
            {
                "title": "Jami foydalanuvchilar",
                "value": total_users,
                "icon": "people",
                "color": "primary",
                "footer": f"+{new_users_week} bu hafta"
            },
            {
                "title": "O'quvchilar",
                "value": students,
                "icon": "school",
                "color": "success",
                "footer": f"{total_enrollments} faol yozilgan"
            },
            {
                "title": "O'qituvchilar",
                "value": teachers,
                "icon": "person",
                "color": "info",
                "footer": f"{active_groups} faol guruh"
            },
            {
                "title": "Oylik daromad",
                "value": f"{monthly_income:,.0f}",
                "icon": "payments",
                "color": "success",
                "footer": f"Xarajat: {monthly_expense:,.0f}"
            },
        ],

        # Ikkinchi qator statistika
        "stats_row2": [
            {
                "title": "Faol guruhlar",
                "value": active_groups,
                "total": total_groups,
                "icon": "groups",
                "color": "primary"
            },
            {
                "title": "Kurslar",
                "value": total_courses,
                "icon": "book",
                "color": "info"
            },
            {
                "title": "Lidlar",
                "value": total_leads,
                "icon": "funnel",
                "color": "warning",
                "footer": f"+{new_leads_week} yangi, {won_leads} yutilgan"
            },
            {
                "title": "Bugungi darslar",
                "value": today_lessons,
                "icon": "event",
                "color": "primary",
                "footer": f"{finished_lessons_month} oylik yakunlangan"
            },
        ],

        # Ogohlantirishlar va xatolar
        "warnings": warnings,
        "errors": errors,
        "info_alerts": info_alerts,
        "all_alerts": errors + warnings + info_alerts,

        # Qo'shimcha ma'lumotlar
        "organizations_count": total_organizations,
        "branches_count": total_branches,
        "pending_transactions": pending_transactions,
    })

    return context


def environment_callback(request):
    """
    Environment badge uchun callback.
    Development yoki Production ko'rsatadi.
    """
    from django.conf import settings
    if settings.DEBUG:
        return ["Development", "warning"]
    return ["Production", "success"]


def badge_callback(request):
    """
    Sidebar badge uchun - kutilayotgan ishlar sonini ko'rsatadi.
    """
    from apps.finance.models import Transaction
    pending = Transaction.objects.filter(status='pending').count()
    if pending > 0:
        return pending
    return None
