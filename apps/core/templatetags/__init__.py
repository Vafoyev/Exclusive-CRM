"""
Custom template tags for role checking.
"""
from django import template

register = template.Library()


@register.filter(name='has_role')
def has_role(user, roles):
    """
    Foydalanuvchining roli berilgan rollar ichida borligini tekshirish.

    Foydalanish:
        {% if request.user|has_role:"admin,owner,teacher" %}
            ...
        {% endif %}
    """
    if not user or not user.is_authenticated:
        return False

    role_list = [r.strip() for r in roles.split(',')]
    return user.role in role_list


@register.simple_tag(takes_context=True)
def user_can(context, *roles):
    """
    Foydalanuvchining roli berilgan rollardan biriga mos kelishini tekshirish.

    Foydalanish:
        {% user_can 'admin' 'owner' as can_manage %}
        {% if can_manage %}
            ...
        {% endif %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False

    return request.user.role in roles


@register.filter(name='is_admin')
def is_admin(user):
    """Admin yoki yuqori rolni tekshirish"""
    return user.is_authenticated and user.role in ['super_admin', 'owner', 'admin']


@register.filter(name='is_teacher_or_admin')
def is_teacher_or_admin(user):
    """O'qituvchi yoki admin rolni tekshirish"""
    return user.is_authenticated and user.role in ['super_admin', 'owner', 'admin', 'teacher']


@register.filter(name='is_staff_member')
def is_staff_member(user):
    """Xodim rolini tekshirish"""
    return user.is_authenticated and user.role in ['super_admin', 'owner', 'admin', 'teacher', 'staff']
