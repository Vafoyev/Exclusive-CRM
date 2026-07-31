"""
Settings (Sozlamalar) sahifalari.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import OperationalError, ProgrammingError
from django.core.cache import cache

from apps.finance.models import TransactionCategory, Account
from apps.hardware.models import FaceIDEvent, FaceIDUserBinding
from apps.users.models import User
from apps.organizations.models import Organization
from apps.core.permissions import permission_required

SETTINGS_STATS_CACHE_TIMEOUT = 300


def _get_face_id_stats(org):
    default_stats = {
        'face_id_users_count': 0,
        'face_id_events_count': 0,
        'face_id_ready': False,
    }
    if not org:
        return default_stats

    try:
        return {
            'face_id_users_count': FaceIDUserBinding.objects.filter(
                organization=org,
                sync_enabled=True,
            ).count(),
            'face_id_events_count': FaceIDEvent.objects.filter(organization=org).count(),
            'face_id_ready': True,
        }
    except (ProgrammingError, OperationalError):
        return default_stats


@login_required
@permission_required('settings', 'view')
def settings_index(request):
    """Asosiy sozlamalar sahifasi"""
    org = request.user.organization
    user = request.user
    cache_key = f"core:settings_stats:{org.id if org else 'none'}"
    stats = cache.get(cache_key)
    if stats is None:
        face_id_stats = _get_face_id_stats(org)
        stats = {
            'categories_count': TransactionCategory.objects.filter(organization=org).count() if org else 0,
            'accounts_count': Account.objects.filter(organization=org, is_deleted=False).count() if org else 0,
            'users_count': User.objects.filter(organization=org, is_deleted=False).count() if org else 0,
        }
        stats.update(face_id_stats)
        cache.set(cache_key, stats, SETTINGS_STATS_CACHE_TIMEOUT)

    context = {
        'stats': stats,
    }

    return render(request, 'core/settings.html', context)
