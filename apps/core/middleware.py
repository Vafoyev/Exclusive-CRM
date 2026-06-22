import asyncio
import logging
import threading

from asgiref.sync import sync_to_async, iscoroutinefunction
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

_thread_locals = threading.local()
_MISSING = '__tenant_missing__'
logger = logging.getLogger(__name__)


def get_current_organization():
    return getattr(_thread_locals, 'organization', None)


def _get_organization_sync(subdomain):
    """Sinxron tarzda tashkilotni olish."""
    Organization = apps.get_model('organizations', 'Organization')

    if settings.DEBUG and (subdomain == 'localhost' or subdomain == '127'):
        if Organization.objects.exists():
            return Organization.objects.first()

        try:
            from apps.users.models import User

            owner = User.objects.filter(role='super_admin').first()
            if not owner and User.objects.exists():
                owner = User.objects.first()

            org = Organization.objects.create(
                name="Smart Edu Test",
                subdomain="test",
                owner=owner,
            )
            logger.warning("TEST UCHUN TASHKILOT AVTOMATIK YARATILDI")
            return org
        except Exception:
            return None

    try:
        return Organization.objects.get(subdomain=subdomain, is_active=True)
    except Organization.DoesNotExist:
        return None


def _get_cached_organization(subdomain):
    cache_key = f"tenant:organization:{subdomain}"
    cached = cache.get(cache_key, _MISSING)
    if cached == _MISSING:
        organization = _get_organization_sync(subdomain)
        cache.set(cache_key, organization if organization is not None else None, 300)
        return organization
    return cached


class TenantMiddleware:
    """
    Multi-tenant middleware - WSGI va ASGI uchun mos.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)

    def __call__(self, request):
        if self.async_mode:
            return self.__acall__(request)
        return self._process_sync(request)

    async def __acall__(self, request):
        """Async versiya."""
        host = request.get_host().split(':')[0]
        subdomain = host.split('.')[0]

        request.organization = await sync_to_async(_get_cached_organization)(subdomain)
        _thread_locals.organization = request.organization

        response = await self.get_response(request)
        return response

    def _process_sync(self, request):
        """Sync versiya."""
        host = request.get_host().split(':')[0]
        subdomain = host.split('.')[0]

        request.organization = _get_cached_organization(subdomain)
        _thread_locals.organization = request.organization

        response = self.get_response(request)
        return response


class HTMXMiddleware:
    """
    HTMX middleware - so'rovlarni optimallashtirish uchun.
    HTMX so'rovi bo'lsa, faqat content qismini qaytaradi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.htmx = request.headers.get('HX-Request') == 'true'
        request.htmx_target = request.headers.get('HX-Target', '')
        request.htmx_trigger = request.headers.get('HX-Trigger', '')

        response = self.get_response(request)

        if request.htmx:
            response['HX-Trigger-After-Swap'] = 'updateSidebar'

            if response.status_code in (301, 302):
                redirect_url = response.get('Location', '')
                login_url = getattr(settings, 'LOGIN_URL', '/login/')
                try:
                    from django.urls import reverse

                    login_path = reverse(login_url)
                except Exception:
                    login_path = login_url
                if login_path and login_path in redirect_url:
                    response['HX-Redirect'] = redirect_url

        return response
