"""
History (Audit Log) sahifasi uchun view'lar.
Tizimda sodir bo'lgan barcha amallarni kuzatish.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse

from apps.core.models import AuditLog
from apps.users.models import User


@login_required
def history_list(request):
    """
    Tizim tarixi - barcha amallar ro'yxati.
    Filter va pagination bilan.
    """
    logs = AuditLog.objects.select_related('user', 'organization').order_by('-created_at')
    
    # Tashkilot bo'yicha filter (Super Admin bo'lmasa)
    if request.user.role != 'super_admin' and request.user.organization:
        logs = logs.filter(organization=request.user.organization)
    
    # === FILTERLAR ===
    
    # Sana bo'yicha
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)
    
    # Foydalanuvchi bo'yicha
    user_id = request.GET.get('user')
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    # Model (Bo'lim) bo'yicha
    model_name = request.GET.get('model')
    if model_name:
        logs = logs.filter(model_name__icontains=model_name)
    
    # Qidiruv
    search = request.GET.get('q')
    if search:
        logs = logs.filter(
            Q(object_repr__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(model_name__icontains=search)
        )
    
    # === STATISTIKA ===
    # Statistikani action filtersiz hisoblash kerak,
    # shunda har doim to'g'ri umumiy sonlarni ko'rsatadi
    action_stats = logs.order_by().values('action').annotate(count=Count('id'))
    stats = {item['action']: item['count'] for item in action_stats}
    total_count = sum(stats.values())
    
    # Amal turi bo'yicha (statistikadan keyin qo'llanadi)
    action = request.GET.get('action')
    if action:
        logs = logs.filter(action=action)
    
    # === PAGINATION ===
    paginator = Paginator(logs, 50)  # 50 ta har sahifada
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)
    
    # Filter uchun ma'lumotlar
    users_with_logs = User.objects.filter(
        audit_logs__isnull=False
    ).distinct().order_by('first_name')
    
    # Model nomlari ro'yxati
    model_names = AuditLog.objects.values_list('model_name', flat=True).distinct()
    
    context = {
        'logs': logs_page,
        'users': users_with_logs,
        'model_names': set(model_names),
        'action_choices': AuditLog.ACTION_CHOICES,
        # Statistika
        'stats': stats,
        'total_count': total_count,
        # Current filters
        'current_action': action,
        'current_user': user_id,
        'current_model': model_name,
        'current_search': search,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'core/history.html', context)


@login_required
def history_detail(request, log_id):
    """
    Bitta log yozuvi tafsiloti.
    """
    log = get_object_or_404(AuditLog, id=log_id)
    
    # Ruxsatni tekshirish
    if request.user.role != 'super_admin':
        if log.organization != request.user.organization:
            return JsonResponse({'error': 'Ruxsat yo\'q'}, status=403)
    
    return render(request, 'core/history_detail.html', {'log': log})
