"""
Permission decorators va utility funksiyalar.
Role-based access control uchun.
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse


def role_required(*roles):
    """
    Faqat ma'lum rollarga ruxsat beruvchi decorator.

    Foydalanish:
        @role_required('owner', 'admin')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role in roles:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "Sizda bu sahifaga kirish huquqi yo'q!")
                raise PermissionDenied("Bu sahifa faqat admin va owner uchun!")
        return wrapper
    return decorator


def admin_required(view_func):
    """Faqat admin va owner uchun"""
    return role_required('owner', 'admin', 'super_admin')(view_func)


def teacher_required(view_func):
    """O'qituvchi yoki yuqori"""
    return role_required('owner', 'admin', 'teacher')(view_func)


def staff_required(view_func):
    """Har qanday xodim"""
    return role_required('owner', 'admin', 'teacher', 'staff')(view_func)


# ============================================
# MODUL ASOSIDAGI RUXSATLAR (Yangi)
# ============================================

def check_permission(user, module: str, action: str = 'view') -> bool:
    """
    Foydalanuvchining ruxsatini tekshirish.

    Args:
        user: User object
        module: Modul nomi (users, finance, education, crm, operations, settings)
        action: Amal turi (view, create, edit, delete)

    Returns:
        True/False
    """
    if not user.is_authenticated:
        return False

    # Super admin va owner - hamma narsaga ruxsat
    if user.role in ['super_admin', 'owner']:
        return True

    # Admin - agar permissions bo'sh bo'lsa, ruxsat bor
    if user.role == 'admin' and not user.permissions:
        return True

    # O'qituvchi - operations va education modullariga default ruxsat
    if user.role == 'teacher' and not user.permissions:
        teacher_defaults = {
            'operations': ['view', 'create', 'edit'],
            'education': ['view'],
        }
        if module in teacher_defaults and action in teacher_defaults[module]:
            return True

    # Admin uchun admin_finance default ruxsat (o'z kassasi)
    if user.role == 'admin' and module == 'admin_finance':
        if action in ['view', 'create', 'edit']:
            return True

    # Permissions tekshirish
    if user.permissions:
        module_perms = user.permissions.get(module, {})
        if isinstance(module_perms, dict):
            return module_perms.get(action, False)

    return False


def permission_required(module: str, action: str = 'view'):
    """
    View uchun modul va amal bo'yicha ruxsatni tekshiruvchi decorator.

    Ishlatish:
        @permission_required('finance', 'create')
        def transaction_create(request):
            ...

    Args:
        module: Modul nomi (users, finance, education, crm, operations, settings)
        action: Amal turi (view, create, edit, delete)
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user

            if check_permission(user, module, action):
                return view_func(request, *args, **kwargs)

            # Ruxsat yo'q
            messages.error(request, f"⛔ Sizda bu amalni bajarish huquqi yo'q!")

            # AJAX so'rov bo'lsa JSON qaytarish
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Sizda bu amalni bajarish huquqi yo\'q!'
                }, status=403)

            # Oldingi sahifaga qaytarish
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            return redirect('dashboard')

        return wrapper
    return decorator


class PermissionRequiredMixin:
    """
    Class-based view uchun ruxsatlarni tekshiruvchi mixin.

    Ishlatish:
        class TransactionCreateView(PermissionRequiredMixin, CreateView):
            permission_module = 'finance'
            permission_action = 'create'
            ...
    """
    permission_module = None
    permission_action = 'view'

    def dispatch(self, request, *args, **kwargs):
        if not self.permission_module:
            return super().dispatch(request, *args, **kwargs)

        if not check_permission(request.user, self.permission_module, self.permission_action):
            messages.error(request, f"⛔ Sizda bu amalni bajarish huquqi yo'q!")
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)


# REST Framework uchun
from rest_framework.permissions import BasePermission


class IsOwnerOrAdmin(BasePermission):
    """REST API: Faqat Owner yoki Admin"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['owner', 'admin', 'super_admin']


class IsTeacher(BasePermission):
    """REST API: O'qituvchi yoki yuqori"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['owner', 'admin', 'teacher']


class IsStaff(BasePermission):
    """REST API: Har qanday xodim"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['owner', 'admin', 'teacher', 'staff']


class IsSameOrganization(BasePermission):
    """REST API: Bir xil tashkilotdan bo'lishi kerak"""
    def has_object_permission(self, request, view, obj):
        if not hasattr(obj, 'organization'):
            return True
        return request.user.organization == obj.organization
