from django.core.cache import cache


NOTIFICATIONS_CACHE_TIMEOUT = 60
PERMISSIONS_CACHE_TIMEOUT = 300


def get_notifications_cache_key(user_id):
    return f"core:notifications:{user_id}"


def invalidate_user_notifications_cache(user_id):
    if user_id:
        cache.delete(get_notifications_cache_key(user_id))


def tenant_context(request):
    """
    Barcha shablonlarga 'organization' o'zgaruvchisini qo'shadi.
    """
    return {
        'organization': request.organization
    }


def user_permissions_context(request):
    """
    Foydalanuvchi ruxsatlarini shablonlarga qo'shadi.
    """
    if not request.user.is_authenticated:
        return {
            'user_modules': [],
            'full_access': False,
        }

    user = request.user
    user_updated_at = getattr(user, 'updated_at', None)
    cache_version = int(user_updated_at.timestamp()) if user_updated_at else 'static'
    cache_key = f"core:user_permissions:{user.pk}:{cache_version}"
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return cached_context

    # Super admin va owner - hamma narsaga to'liq ruxsat (Direktor)
    if user.role in ['super_admin', 'owner'] or user.is_superuser:
        allowed_modules = ['dashboard', 'users', 'education', 'finance', 'crm', 'operations', 'reports', 'settings', 'automation', 'admin_finance']
        context = {
            'user_modules': allowed_modules,
            'full_access': True,
            'is_director': True,
        }
        cache.set(cache_key, context, PERMISSIONS_CACHE_TIMEOUT)
        return context

    # Admin, staff va boshqa rollar uchun permissions dan tekshirish
    allowed_modules = ['dashboard']  # Hammaga dashboard

    # Agar admin bo'lsa - barcha boshqaruv modullariga ruxsat, lekin full_access=False (Direktor cheklovlari bor)
    if user.role == 'admin':
        allowed_modules = ['dashboard', 'users', 'education', 'finance', 'crm', 'operations', 'reports', 'settings', 'automation', 'admin_finance']
        if user.permissions:
            for module, perms in user.permissions.items():
                if isinstance(perms, dict) and perms.get('view', False) and module not in allowed_modules:
                    allowed_modules.append(module)
        context = {
            'user_modules': allowed_modules,
            'full_access': False,
            'is_director': False,
        }
        cache.set(cache_key, context, PERMISSIONS_CACHE_TIMEOUT)
        return context

    # O'qituvchi - default modullar
    if user.role == 'teacher' and not user.permissions:
        allowed_modules = ['dashboard', 'operations', 'education']
        context = {
            'user_modules': allowed_modules,
            'full_access': False,
        }
        cache.set(cache_key, context, PERMISSIONS_CACHE_TIMEOUT)
        return context

    # Permissions dan tekshirish
    if user.permissions:
        for module, perms in user.permissions.items():
            if isinstance(perms, dict) and perms.get('view', False):
                allowed_modules.append(module)

    # Admin uchun admin_finance har doim qo'shiladi
    if user.role == 'admin' and 'admin_finance' not in allowed_modules:
        allowed_modules.append('admin_finance')

    context = {
        'user_modules': allowed_modules,
        'full_access': False,
    }
    cache.set(cache_key, context, PERMISSIONS_CACHE_TIMEOUT)
    return context


def notifications_context(request):
    """
    Barcha shablonlarga bildirishnomalarni qo'shadi.
    """
    if not request.user.is_authenticated:
        return {
            'notifications': [],
            'unread_notifications_count': 0
        }

    try:
        from apps.automation.models import NotificationLog

        cache_key = get_notifications_cache_key(request.user.pk)
        cached_context = cache.get(cache_key)
        if cached_context is not None:
            return cached_context

        notifications_qs = NotificationLog.objects.filter(
            recipient=request.user,
            is_deleted=False
        )

        notifications = list(
            notifications_qs.select_related('template').order_by('-created_at')[:10]
        )
        unread_count = notifications_qs.filter(status='sent').count()

        context = {
            'notifications': notifications,
            'unread_notifications_count': unread_count
        }
        cache.set(cache_key, context, NOTIFICATIONS_CACHE_TIMEOUT)

        return context
    except Exception:
        return {
            'notifications': [],
            'unread_notifications_count': 0
        }


def sidebar_stats_context(request):
    """
    Sidebar menyusi uchun dinamik real statistik ko'rsatkichlar.
    """
    if not request.user.is_authenticated:
        return {}

    org = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    org_id = org.pk if org else 'all'
    cache_key = f"core:sidebar_stats:{org_id}"
    cached_stats = cache.get(cache_key)
    if cached_stats is not None:
        return cached_stats

    try:
        from apps.users.models import User
        from apps.crm.models import Lead
        from apps.education.models import Group

        users_qs = User.objects.filter(is_deleted=False)
        leads_qs = Lead.objects.filter(is_deleted=False)
        groups_qs = Group.objects.filter(is_deleted=False)
        debtors_qs = User.objects.filter(role='student', balance__lt=0, is_deleted=False)

        from apps.finance.models import Transaction, CashSubmission
        from django.db.models import Sum

        tx_pending_qs = Transaction.objects.filter(status='pending', is_deleted=False, transaction_type='income')
        sub_pending_qs = CashSubmission.objects.filter(status='pending', is_deleted=False)

        if org:
            users_qs = users_qs.filter(organization=org)
            leads_qs = leads_qs.filter(organization=org)
            groups_qs = groups_qs.filter(organization=org)
            debtors_qs = debtors_qs.filter(organization=org)
            tx_pending_qs = tx_pending_qs.filter(organization=org)
            sub_pending_qs = sub_pending_qs.filter(organization=org)

        tx_pending_stats = tx_pending_qs.aggregate(count=Count('id'), total=Sum('amount'))
        sub_pending_stats = sub_pending_qs.aggregate(count=Count('id'), total=Sum('net_amount'))

        tx_pending_count = tx_pending_stats['count'] or 0
        tx_pending_amount = tx_pending_stats['total'] or 0
        sub_pending_count = sub_pending_stats['count'] or 0
        sub_pending_amount = sub_pending_stats['total'] or 0

        total_pending_count = tx_pending_count + sub_pending_count
        total_pending_amount = tx_pending_amount + sub_pending_amount

        stats = {
            'sidebar_users_count': users_qs.count(),
            'sidebar_leads_count': leads_qs.count(),
            'sidebar_groups_count': groups_qs.count(),
            'sidebar_debtors_count': debtors_qs.count(),
            'director_pending_total_amount': total_pending_amount,
            'director_pending_total_count': total_pending_count,
            'director_pending_tx_amount': tx_pending_amount,
            'director_pending_tx_count': tx_pending_count,
            'director_pending_sub_amount': sub_pending_amount,
            'director_pending_sub_count': sub_pending_count,
        }
        cache.set(cache_key, stats, 60)
        return stats
    except Exception:
        return {
            'sidebar_users_count': 0,
            'sidebar_leads_count': 0,
            'sidebar_groups_count': 0,
            'sidebar_debtors_count': 0,
            'director_pending_total_amount': 0,
            'director_pending_total_count': 0,
            'director_pending_tx_amount': 0,
            'director_pending_tx_count': 0,
            'director_pending_sub_amount': 0,
            'director_pending_sub_count': 0,
        }
