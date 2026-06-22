"""
Audit Mixins va Decorators.
CRUD operatsiyalarini avtomatik log qilish uchun.
"""
from functools import wraps
from .models import AuditLog


class AuditMixin:
    """
    View uchun mixin. CRUD operatsiyalarini avtomatik log qiladi.
    Class-based viewlar uchun ishlatiladi.
    """
    
    def get_audit_object_repr(self, obj):
        """Obyektni string ko'rinishida qaytaradi."""
        return str(obj)
    
    def log_create(self, obj, request=None):
        """Yaratish logini yozadi."""
        AuditLog.log(
            user=request.user if request else None,
            action='CREATE',
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=self.get_audit_object_repr(obj),
            request=request
        )
    
    def log_update(self, obj, changes, request=None):
        """O'zgartirish logini yozadi."""
        AuditLog.log(
            user=request.user if request else None,
            action='UPDATE',
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=self.get_audit_object_repr(obj),
            changes=changes,
            request=request
        )
    
    def log_delete(self, obj, request=None):
        """O'chirish logini yozadi."""
        AuditLog.log(
            user=request.user if request else None,
            action='DELETE',
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=self.get_audit_object_repr(obj),
            request=request
        )


def get_model_changes(instance, old_instance):
    """
    Ikki obyekt o'rtasidagi farqlarni topadi.
    Returns: {field_name: {'old': old_value, 'new': new_value}}
    """
    changes = {}
    
    for field in instance._meta.fields:
        field_name = field.name
        
        # Parol va secret maydonlarni o'tkazib yuboramiz
        if 'password' in field_name.lower() or 'secret' in field_name.lower():
            continue
            
        old_value = getattr(old_instance, field_name, None)
        new_value = getattr(instance, field_name, None)
        
        # Serialize qilish mumkin bo'lmagan obyektlarni stringga o'giramiz
        try:
            if old_value != new_value:
                changes[field_name] = {
                    'old': str(old_value) if old_value else None,
                    'new': str(new_value) if new_value else None
                }
        except Exception:
            pass
    
    return changes


def audit_action(action_type):
    """
    Function-based viewlar uchun decorator.
    
    Usage:
        @audit_action('CREATE')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            
            # View ishladi, endi log yozamiz
            # (Bu yerda qo'shimcha logic qo'shish mumkin)
            
            return response
        return wrapper
    return decorator


def log_user_action(user, action, model_name, object_id=None, object_repr='', changes=None, request=None):
    """
    Oddiy helper funksiya - istalgan joydan log yozish uchun.
    
    Usage:
        log_user_action(request.user, 'CREATE', 'Lead', lead.id, str(lead), request=request)
    """
    return AuditLog.log(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr,
        changes=changes,
        request=request
    )
