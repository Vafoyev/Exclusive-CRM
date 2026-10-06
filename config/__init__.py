# Enable Celery
from .celery import app as celery_app

__all__ = ('celery_app',)

# Python 3.14 compatibility patch for Django template Context copy
try:
    from django.template.context import BaseContext
    def _safe_context_copy(self):
        dup = self.__class__.__new__(self.__class__)
        dup.__dict__.update(self.__dict__)
        dup.dicts = self.dicts[:]
        return dup
    BaseContext.__copy__ = _safe_context_copy
except Exception:
    pass

