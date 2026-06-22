from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, ProgrammingError, connection
from django.db.models import Count, Max, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from types import SimpleNamespace

from apps.core.permissions import permission_required
from apps.hardware.models import FaceIDEvent, FaceIDIntegration, FaceIDUserBinding, generate_device_token
from apps.hardware.services import get_event_type_label
from apps.organizations.models import Organization
from apps.users.models import User


FACE_ID_TABS = {'overview', 'users', 'api', 'events'}


def _get_organization_from_request(request):
    organization = getattr(request, 'organization', None) or getattr(request.user, 'organization', None)
    if organization is not None:
        return organization

    owned_organization = getattr(request.user, 'owned_organization', None)
    if owned_organization is not None:
        request.organization = owned_organization
        return owned_organization

    if request.user.role == 'super_admin':
        requested_org_id = request.GET.get('org', '').strip()
        active_orgs = Organization.objects.filter(is_active=True, is_deleted=False).order_by('id')
        if requested_org_id.isdigit():
            selected_org = active_orgs.filter(id=int(requested_org_id)).first()
            if selected_org is not None:
                request.organization = selected_org
                return selected_org

        fallback_org = active_orgs.first()
        if fallback_org is not None:
            request.organization = fallback_org
            return fallback_org

    return None


def _get_or_create_integration(organization):
    return FaceIDIntegration.objects.get_or_create(organization=organization)


def _face_id_schema_ready():
    required_tables = {
        FaceIDIntegration._meta.db_table,
        FaceIDUserBinding._meta.db_table,
        FaceIDEvent._meta.db_table,
    }
    try:
        existing_tables = set(connection.introspection.table_names())
    except (ProgrammingError, OperationalError):
        return False
    return required_tables.issubset(existing_tables)


def _build_endpoints(request):
    return {
        'users_list': request.build_absolute_uri(reverse('hardware:api_users_list')),
        'event': request.build_absolute_uri(reverse('hardware:api_event')),
        'history': request.build_absolute_uri(reverse('hardware:api_history_sync')),
        'last_time': request.build_absolute_uri(reverse('hardware:api_last_sync_time')),
    }


def _sanitize_tab(tab_name, default='overview'):
    return tab_name if tab_name in FACE_ID_TABS else default


def _redirect_with_tab(request, default_tab='overview'):
    tab_name = _sanitize_tab(request.POST.get('next_tab') or request.GET.get('tab'), default_tab)
    return redirect(f"{reverse('hardware:face_id_settings')}?tab={tab_name}")


def _render_schema_unavailable(request, organization, endpoints, current_tab, search=''):
    context = {
        'organization': organization,
        'integration': SimpleNamespace(
            agent_enabled=False,
            device_token='Migration kutilmoqda',
            last_event_received_at=None,
        ),
        'user_rows': [],
        'stats': {
            'bound_users': 0,
            'active_users': 0,
            'users_with_avatar': 0,
            'last_sync': None,
            'last_event': None,
        },
        'recent_events': [],
        'search': search,
        'endpoints': endpoints,
        'now': timezone.now(),
        'schema_ready': False,
        'migration_command': 'python manage.py migrate',
        'current_tab': current_tab,
    }
    return render(request, 'hardware/face_id_settings.html', context)


@login_required
@permission_required('settings', 'view')
def face_id_settings(request):
    organization = _get_organization_from_request(request)
    if organization is None:
        messages.error(request, "Face ID sozlamalari uchun tashkilot topilmadi.")
        return redirect('core:settings')

    search = request.GET.get('q', '').strip()
    current_tab = _sanitize_tab(request.GET.get('tab'), 'overview')
    endpoints = _build_endpoints(request)
    if not _face_id_schema_ready():
        if request.method == 'POST':
            messages.error(request, "Face ID bo'limi hali tayyor emas. Avval `python manage.py migrate` ni ishga tushiring.")
            return _redirect_with_tab(request, default_tab=current_tab)
        return _render_schema_unavailable(request, organization, endpoints, current_tab, search=search)

    try:
        integration, _ = _get_or_create_integration(organization)
    except (ProgrammingError, OperationalError):
        if request.method == 'POST':
            messages.error(request, "Face ID jadvallari topilmadi. Avval `python manage.py migrate` ni ishga tushiring.")
            return _redirect_with_tab(request, default_tab=current_tab)
        return _render_schema_unavailable(request, organization, endpoints, current_tab, search=search)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_settings':
            integration.agent_enabled = 'agent_enabled' in request.POST
            if 'regenerate_token' in request.POST:
                integration.device_token = generate_device_token()
                messages.success(request, "Face ID token yangilandi.")
            else:
                messages.success(request, "Face ID sozlamalari saqlandi.")
            integration.save()
            return _redirect_with_tab(request, default_tab='overview')

        if action == 'save_bindings':
            user_ids = [int(user_id) for user_id in request.POST.getlist('user_ids') if user_id.isdigit()]
            users = User.objects.filter(
                id__in=user_ids,
                organization=organization,
                is_deleted=False,
            )
            user_map = {user.id: user for user in users}
            existing_bindings = {
                binding.user_id: binding
                for binding in FaceIDUserBinding.objects.filter(user_id__in=user_ids).select_related('user')
            }

            used_codes = {}
            for user_id in user_ids:
                user = user_map.get(user_id)
                if user is None:
                    continue
                code = request.POST.get(f'face_id_code_{user_id}', '').strip()
                enabled = f'sync_enabled_{user_id}' in request.POST
                if enabled and not code:
                    code = str(user.id)
                if not code:
                    continue
                existing_binding = existing_bindings.get(user_id)
                existing_owner = FaceIDUserBinding.objects.select_related('user').filter(
                    organization=organization,
                    face_id_code=code,
                ).exclude(user_id=user_id).first()
                if existing_owner:
                    owner_name = existing_owner.user.full_name or existing_owner.user.phone
                    messages.error(request, f"{code} kodi allaqachon {owner_name} ga biriktirilgan.")
                    return _redirect_with_tab(request, default_tab='users')
                if code in used_codes and used_codes[code] != user_id:
                    messages.error(request, f"{code} kodi form ichida ikki marta takrorlangan.")
                    return _redirect_with_tab(request, default_tab='users')
                used_codes[code] = user_id
                if existing_binding is None:
                    FaceIDUserBinding.objects.create(
                        user=user,
                        organization=organization,
                        face_id_code=code,
                        sync_enabled=enabled,
                    )
                else:
                    existing_binding.face_id_code = code
                    existing_binding.sync_enabled = enabled
                    existing_binding.organization = organization
                    existing_binding.save()

            messages.success(request, "Face ID bog'lanishlari saqlandi.")
            return _redirect_with_tab(request, default_tab='users')

    users = User.objects.filter(
        organization=organization,
        is_deleted=False,
        is_active=True,
    ).order_by('role', 'first_name', 'last_name', 'id')
    if search:
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search)
        )

    users = list(users)
    bindings = {
        binding.user_id: binding
        for binding in FaceIDUserBinding.objects.filter(user__organization=organization).select_related('user')
    }
    user_rows = []
    for user in users:
        binding = bindings.get(user.id)
        user_rows.append({
            'user': user,
            'binding': binding,
            'face_id_code': binding.face_id_code if binding else str(user.id),
            'sync_enabled': binding.sync_enabled if binding else False,
            'has_avatar': bool(user.avatar),
            'last_event_label': get_event_type_label(binding.last_event_type) if binding and binding.last_event_type else '',
        })

    stats = FaceIDUserBinding.objects.filter(organization=organization).aggregate(
        bound_users=Count('id'),
        active_users=Count('id', filter=Q(sync_enabled=True)),
        users_with_avatar=Count('id', filter=Q(sync_enabled=True, user__avatar__isnull=False)),
        last_sync=Max('last_synced_at'),
        last_event=Max('last_event_at'),
    )
    recent_events = list(FaceIDEvent.objects.filter(
        organization=organization
    ).select_related('user').order_by('-occurred_at')[:20])
    for event in recent_events:
        event.event_label = get_event_type_label(event.event_type)

    context = {
        'organization': organization,
        'integration': integration,
        'user_rows': user_rows,
        'stats': stats,
        'recent_events': recent_events,
        'search': search,
        'endpoints': endpoints,
        'now': timezone.now(),
        'schema_ready': True,
        'migration_command': 'python manage.py migrate',
        'current_tab': current_tab,
    }
    return render(request, 'hardware/face_id_settings.html', context)
