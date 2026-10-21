"""
Director Analytics & Statistics Dashboard.
Direktor uchun keng qamrovli tahlil:
- Haftalik (7 kun)
- Oylik (30 kun)
- 3 oylik / Kvartal (90 kun)
- Yarim yillik (180 kun)
- 1 yillik (365 kun)
Har bir davr avvalgi teng davr bilan to'liq solishtiriladi (Comparison & Trends).
"""
import json
from datetime import timedelta, date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, Avg
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.finance.models import Transaction, Account, TransactionCategory, CashSubmission
from apps.users.models import User
from apps.education.models import Course, Group, GroupStudent
from apps.operations.models import Attendance, Lesson


def _calc_change(current, previous):
    """
    Hozirgi va oldingi qiymat o'rtasidagi farq va foiz o'zgarishini hisoblash.
    """
    diff = current - previous
    if previous and previous != 0:
        pct = (float(diff) / float(previous)) * 100.0
    elif current and current != 0:
        pct = 100.0
    else:
        pct = 0.0

    return {
        'current': current,
        'previous': previous,
        'diff': diff,
        'pct': round(pct, 1),
        'is_positive': diff > 0,
        'is_neutral': diff == 0,
        'direction': 'up' if diff > 0 else ('down' if diff < 0 else 'flat')
    }


@login_required
def director_analytics_view(request):
    """
    Direktor Analitika va Statistika Dashboardi.
    Faqat direktor (is_director) uchun ruxsat etiladi.
    """
    if not request.user.is_director:
        messages.error(request, "Direktor Analitikasi faqat rahbar uchun mo'ljallangan!")
        return redirect('dashboard')

    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    today = timezone.localdate()

    # Tanlangan davrni aniqlash
    period = request.GET.get('period', 'monthly')
    valid_periods = {
        'weekly': {'name': 'Haftalik (7 kun)', 'days': 7, 'granularity': 'daily'},
        'monthly': {'name': 'Oylik (30 kun)', 'days': 30, 'granularity': 'daily'},
        'quarterly': {'name': '3 Oylik (Kvartal)', 'days': 90, 'granularity': 'weekly'},
        'half_yearly': {'name': 'Yarim yillik (6 oy)', 'days': 180, 'granularity': 'monthly'},
        'yearly': {'name': '1 Yillik (365 kun)', 'days': 365, 'granularity': 'monthly'},
    }
    if period not in valid_periods:
        period = 'monthly'

    period_info = valid_periods[period]
    days_count = period_info['days']

    # 1. Joriy davr sanalari
    end_date = today
    start_date = today - timedelta(days=days_count - 1)

    # 2. Taqqoslash uchun avvalgi davr sanalari (xuddi shuncha kun orqaga)
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=days_count - 1)

    # Tranzaksiyalar bazaviy filtri
    tx_base = Transaction.objects.filter(is_deleted=False)
    if org:
        tx_base = tx_base.filter(organization=org)

    confirmed_tx = tx_base.filter(status='confirmed')

    # A) MOLIYAVIY KO'RSATKICHLAR (Joriy vs Oldingi)
    # Joriy davr
    cur_tx = confirmed_tx.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    cur_stats = cur_tx.aggregate(
        income=Sum('amount', filter=Q(transaction_type='income')),
        expense=Sum('amount', filter=Q(transaction_type='expense')),
        tx_count=Count('id'),
        paying_students=Count('student', distinct=True, filter=Q(transaction_type='income', student__isnull=False)),
    )
    cur_income = cur_stats['income'] or Decimal('0')
    cur_expense = cur_stats['expense'] or Decimal('0')
    cur_profit = cur_income - cur_expense
    cur_tx_count = cur_stats['tx_count'] or 0
    cur_paying_students = cur_stats['paying_students'] or 0
    cur_avg_ticket = (cur_income / cur_paying_students) if cur_paying_students > 0 else Decimal('0')
    cur_margin = (float(cur_profit) / float(cur_income) * 100) if cur_income > 0 else 0.0

    # Oldingi davr
    prev_tx = confirmed_tx.filter(created_at__date__gte=prev_start_date, created_at__date__lte=prev_end_date)
    prev_stats = prev_tx.aggregate(
        income=Sum('amount', filter=Q(transaction_type='income')),
        expense=Sum('amount', filter=Q(transaction_type='expense')),
        tx_count=Count('id'),
        paying_students=Count('student', distinct=True, filter=Q(transaction_type='income', student__isnull=False)),
    )
    prev_income = prev_stats['income'] or Decimal('0')
    prev_expense = prev_stats['expense'] or Decimal('0')
    prev_profit = prev_income - prev_expense
    prev_tx_count = prev_stats['tx_count'] or 0
    prev_paying_students = prev_stats['paying_students'] or 0
    prev_avg_ticket = (prev_income / prev_paying_students) if prev_paying_students > 0 else Decimal('0')
    prev_margin = (float(prev_profit) / float(prev_income) * 100) if prev_income > 0 else 0.0

    # Taqqoslashlar (Changes)
    income_change = _calc_change(cur_income, prev_income)
    expense_change = _calc_change(cur_expense, prev_expense)
    profit_change = _calc_change(cur_profit, prev_profit)
    tx_count_change = _calc_change(cur_tx_count, prev_tx_count)
    paying_students_change = _calc_change(cur_paying_students, prev_paying_students)
    avg_ticket_change = _calc_change(cur_avg_ticket, prev_avg_ticket)
    margin_change = _calc_change(round(cur_margin, 1), round(prev_margin, 1))

    # B) O'QUVCHILAR DINAMIKASI
    student_base = User.objects.filter(role='student', is_deleted=False)
    if org:
        student_base = student_base.filter(organization=org)

    cur_new_students = student_base.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    ).count()

    prev_new_students = student_base.filter(
        created_at__date__gte=prev_start_date, created_at__date__lte=prev_end_date
    ).count()

    new_students_change = _calc_change(cur_new_students, prev_new_students)
    total_active_students = student_base.filter(is_active=True).count()

    # C) DAVOMAT KO'RSATKICHI
    att_base = Attendance.objects.filter(is_deleted=False)
    if org:
        att_base = att_base.filter(organization=org)

    cur_att = att_base.filter(lesson__date__gte=start_date, lesson__date__lte=end_date)
    cur_att_total = cur_att.count()
    cur_att_present = cur_att.filter(status='present').count()
    cur_att_rate = round((cur_att_present / cur_att_total * 100), 1) if cur_att_total > 0 else 0.0

    prev_att = att_base.filter(lesson__date__gte=prev_start_date, lesson__date__lte=prev_end_date)
    prev_att_total = prev_att.count()
    prev_att_present = prev_att.filter(status='present').count()
    prev_att_rate = round((prev_att_present / prev_att_total * 100), 1) if prev_att_total > 0 else 0.0

    att_change = _calc_change(cur_att_rate, prev_att_rate)

    # D) TO'LOV USULLARI TAQSIMOTI (Donut Chart)
    payment_methods_data = cur_tx.filter(transaction_type='income').values('payment_method').annotate(
        total=Sum('amount'), count=Count('id')
    ).order_by('-total')

    method_map = {
        'cash': 'Naqd pul',
        'card': 'Plastik karta',
        'terminal': 'Terminal / Online',
        'transfer': 'Bank o\'tkazmasi',
        'online': 'Online (Click/Payme)',
    }
    method_labels = []
    method_sums = []
    for item in payment_methods_data:
        label = method_map.get(item['payment_method'], item['payment_method'])
        method_labels.append(label)
        method_sums.append(float(item['total'] or 0))

    if not method_labels:
        method_labels = ['Naqd pul', 'Plastik karta', 'Online']
        method_sums = [0, 0, 0]

    # E) ENG DAROMADLI KURSLAR
    top_courses_qs = cur_tx.filter(
        transaction_type='income',
        student__isnull=False
    ).values('student__enrolled_groups__group__course__name').annotate(
        revenue=Sum('amount'),
        student_count=Count('student', distinct=True)
    ).order_by('-revenue')

    top_courses = []
    for item in top_courses_qs:
        c_name = item.get('student__enrolled_groups__group__course__name')
        if c_name and c_name not in [c['name'] for c in top_courses]:
            top_courses.append({
                'name': c_name,
                'revenue': item['revenue'] or 0,
                'students': item['student_count'] or 0,
            })
        if len(top_courses) >= 6:
            break

    # F) XARAJATLAR STRUKTURASI
    expense_categories_qs = cur_tx.filter(
        transaction_type='expense',
        category__isnull=False
    ).values('category__name').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')[:6]

    expense_categories = []
    for cat in expense_categories_qs:
        total_val = cat['total'] or 0
        pct = (float(total_val) / float(cur_expense) * 100) if cur_expense > 0 else 0
        expense_categories.append({
            'name': cat['category__name'],
            'total': total_val,
            'pct': round(pct, 1),
            'count': cat['count'],
        })

    # G) TAQQOSLASH GRAFIKASI UCHUN VAQT DINAMIKASI (Timeline Comparison Chart)
    # Joriy davr va oldingi davrni interval nuqtalariga bo'lamiz
    granularity = period_info['granularity']
    chart_labels = []
    cur_income_series = []
    prev_income_series = []
    cur_expense_series = []
    prev_expense_series = []

    if granularity == 'daily' and days_count <= 7:
        # 7 kunlik (Dushanba -> Yakshanba)
        weekday_names = ["Dush", "Sesh", "Chor", "Pay", "Juma", "Shan", "Yak"]
        for i in range(days_count):
            c_day = start_date + timedelta(days=i)
            p_day = prev_start_date + timedelta(days=i)
            chart_labels.append(f"{weekday_names[c_day.weekday()]} ({c_day.strftime('%d.%m')})")

            c_inc = cur_tx.filter(transaction_type='income', created_at__date=c_day).aggregate(s=Sum('amount'))['s'] or 0
            p_inc = prev_tx.filter(transaction_type='income', created_at__date=p_day).aggregate(s=Sum('amount'))['s'] or 0
            c_exp = cur_tx.filter(transaction_type='expense', created_at__date=c_day).aggregate(s=Sum('amount'))['s'] or 0
            p_exp = prev_tx.filter(transaction_type='expense', created_at__date=p_day).aggregate(s=Sum('amount'))['s'] or 0

            cur_income_series.append(float(c_inc))
            prev_income_series.append(float(p_inc))
            cur_expense_series.append(float(c_exp))
            prev_expense_series.append(float(p_exp))

    elif granularity == 'daily' and days_count <= 30:
        # 30 kunlik (6 ta 5-kunlik blok yoki har 3-kunda 10 ta nuqta)
        step = 3
        points = days_count // step
        for i in range(points):
            offset_start = i * step
            offset_end = offset_start + step - 1

            c_sub_start = start_date + timedelta(days=offset_start)
            c_sub_end = start_date + timedelta(days=offset_end)
            p_sub_start = prev_start_date + timedelta(days=offset_start)
            p_sub_end = prev_start_date + timedelta(days=offset_end)

            chart_labels.append(f"{c_sub_start.strftime('%d.%m')} - {c_sub_end.strftime('%d.%m')}")

            c_inc = cur_tx.filter(transaction_type='income', created_at__date__gte=c_sub_start, created_at__date__lte=c_sub_end).aggregate(s=Sum('amount'))['s'] or 0
            p_inc = prev_tx.filter(transaction_type='income', created_at__date__gte=p_sub_start, created_at__date__lte=p_sub_end).aggregate(s=Sum('amount'))['s'] or 0
            c_exp = cur_tx.filter(transaction_type='expense', created_at__date__gte=c_sub_start, created_at__date__lte=c_sub_end).aggregate(s=Sum('amount'))['s'] or 0
            p_exp = prev_tx.filter(transaction_type='expense', created_at__date__gte=p_sub_start, created_at__date__lte=p_sub_end).aggregate(s=Sum('amount'))['s'] or 0

            cur_income_series.append(float(c_inc))
            prev_income_series.append(float(p_inc))
            cur_expense_series.append(float(c_exp))
            prev_expense_series.append(float(p_exp))

    elif granularity == 'weekly':
        # 90 kun (Kvartal) = 12 hafta
        num_weeks = 12
        for w in range(num_weeks):
            c_w_start = start_date + timedelta(days=w * 7)
            c_w_end = min(end_date, c_w_start + timedelta(days=6))
            p_w_start = prev_start_date + timedelta(days=w * 7)
            p_w_end = min(prev_end_date, p_w_start + timedelta(days=6))

            chart_labels.append(f"{w + 1}-hafta")

            c_inc = cur_tx.filter(transaction_type='income', created_at__date__gte=c_w_start, created_at__date__lte=c_w_end).aggregate(s=Sum('amount'))['s'] or 0
            p_inc = prev_tx.filter(transaction_type='income', created_at__date__gte=p_w_start, created_at__date__lte=p_w_end).aggregate(s=Sum('amount'))['s'] or 0
            c_exp = cur_tx.filter(transaction_type='expense', created_at__date__gte=c_w_start, created_at__date__lte=c_w_end).aggregate(s=Sum('amount'))['s'] or 0
            p_exp = prev_tx.filter(transaction_type='expense', created_at__date__gte=p_w_start, created_at__date__lte=p_w_end).aggregate(s=Sum('amount'))['s'] or 0

            cur_income_series.append(float(c_inc))
            prev_income_series.append(float(p_inc))
            cur_expense_series.append(float(c_exp))
            prev_expense_series.append(float(p_exp))

    else:
        # Yarim yillik (6 oy) yoki 1 Yillik (12 oy)
        num_months = 6 if days_count <= 180 else 12
        month_names = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
        days_per_chunk = days_count // num_months
        for m in range(num_months):
            c_m_start = start_date + timedelta(days=m * days_per_chunk)
            c_m_end = min(end_date, c_m_start + timedelta(days=days_per_chunk - 1))
            p_m_start = prev_start_date + timedelta(days=m * days_per_chunk)
            p_m_end = min(prev_end_date, p_m_start + timedelta(days=days_per_chunk - 1))

            chart_labels.append(f"{month_names[c_m_start.month - 1]} '{str(c_m_start.year)[-2:]}")

            c_inc = cur_tx.filter(transaction_type='income', created_at__date__gte=c_m_start, created_at__date__lte=c_m_end).aggregate(s=Sum('amount'))['s'] or 0
            p_inc = prev_tx.filter(transaction_type='income', created_at__date__gte=p_m_start, created_at__date__lte=p_m_end).aggregate(s=Sum('amount'))['s'] or 0
            c_exp = cur_tx.filter(transaction_type='expense', created_at__date__gte=c_m_start, created_at__date__lte=c_m_end).aggregate(s=Sum('amount'))['s'] or 0
            p_exp = prev_tx.filter(transaction_type='expense', created_at__date__gte=p_m_start, created_at__date__lte=p_m_end).aggregate(s=Sum('amount'))['s'] or 0

            cur_income_series.append(float(c_inc))
            prev_income_series.append(float(p_inc))
            cur_expense_series.append(float(c_exp))
            prev_expense_series.append(float(p_exp))

    # H) KASSA VA TASDIQLANMAGAN PULLAR (Hozirgi holat)
    accounts = Account.objects.filter(is_deleted=False)
    if org:
        accounts = accounts.filter(organization=org)
    total_cash_balance = accounts.aggregate(s=Sum('balance'))['s'] or 0

    pending_txs = tx_base.filter(status='pending')
    pending_total_amount = pending_txs.aggregate(s=Sum('amount'))['s'] or 0
    pending_total_count = pending_txs.count()

    context = {
        'period': period,
        'period_name': period_info['name'],
        'start_date': start_date,
        'end_date': end_date,
        'prev_start_date': prev_start_date,
        'prev_end_date': prev_end_date,

        # Asosiy ko'rsatkichlar & solishtirish
        'cur_income': cur_income,
        'prev_income': prev_income,
        'income_change': income_change,

        'cur_expense': cur_expense,
        'prev_expense': prev_expense,
        'expense_change': expense_change,

        'cur_profit': cur_profit,
        'prev_profit': prev_profit,
        'profit_change': profit_change,

        'cur_margin': round(cur_margin, 1),
        'prev_margin': round(prev_margin, 1),
        'margin_change': margin_change,

        'cur_new_students': cur_new_students,
        'prev_new_students': prev_new_students,
        'new_students_change': new_students_change,
        'total_active_students': total_active_students,

        'cur_paying_students': cur_paying_students,
        'prev_paying_students': prev_paying_students,
        'paying_students_change': paying_students_change,

        'cur_avg_ticket': cur_avg_ticket,
        'prev_avg_ticket': prev_avg_ticket,
        'avg_ticket_change': avg_ticket_change,

        'cur_att_rate': cur_att_rate,
        'prev_att_rate': prev_att_rate,
        'att_change': att_change,

        'total_cash_balance': total_cash_balance,
        'pending_total_amount': pending_total_amount,
        'pending_total_count': pending_total_count,

        # Chart ma'lumotlari (JSON ko'rinishida)
        'chart_labels_json': json.dumps(chart_labels),
        'cur_income_series_json': json.dumps(cur_income_series),
        'prev_income_series_json': json.dumps(prev_income_series),
        'cur_expense_series_json': json.dumps(cur_expense_series),
        'prev_expense_series_json': json.dumps(prev_expense_series),
        'method_labels_json': json.dumps(method_labels),
        'method_sums_json': json.dumps(method_sums),

        # Jadvallar
        'top_courses': top_courses,
        'expense_categories': expense_categories,
        'accounts': accounts,
    }

    return render(request, 'dashboards/director_analytics.html', context)
