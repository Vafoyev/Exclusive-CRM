"""
Async utilities - Django 4.1+ async view'lar uchun yordamchi funksiyalar.
sync_to_async wrapper'lar bilan ORM operatsiyalarini async qilish.
"""
from asgiref.sync import sync_to_async
from django.core.paginator import Paginator
from django.db.models import QuerySet
from typing import Any, Optional, Type
from django.db import models


# ============================================
# GENERIC ASYNC ORM OPERATIONS
# ============================================

@sync_to_async
def aget_object_or_none(model: Type[models.Model], **kwargs) -> Optional[models.Model]:
    """
    Async versiyasi get_object_or_404 - lekin None qaytaradi.
    """
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        return None


@sync_to_async
def aget_object(model: Type[models.Model], **kwargs) -> models.Model:
    """
    Async versiyasi model.objects.get()
    """
    return model.objects.get(**kwargs)


@sync_to_async
def afilter(model: Type[models.Model], limit: int = 100, **kwargs) -> list:
    """
    Async filter - list qaytaradi.
    """
    return list(model.objects.filter(**kwargs)[:limit])


@sync_to_async
def acount(model: Type[models.Model], **kwargs) -> int:
    """
    Async count.
    """
    return model.objects.filter(**kwargs).count()


@sync_to_async
def acreate(model: Type[models.Model], **kwargs) -> models.Model:
    """
    Async create.
    """
    return model.objects.create(**kwargs)


@sync_to_async
def aupdate(queryset: QuerySet, **kwargs) -> int:
    """
    Async bulk update.
    """
    return queryset.update(**kwargs)


@sync_to_async
def asave(obj: models.Model, update_fields: list = None):
    """
    Async save.
    """
    obj.save(update_fields=update_fields)


@sync_to_async
def adelete(obj: models.Model):
    """
    Async delete.
    """
    obj.delete()


@sync_to_async
def apaginate(queryset: QuerySet, page: int, per_page: int = 20):
    """
    Async pagination.
    """
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page)


@sync_to_async
def aexists(model: Type[models.Model], **kwargs) -> bool:
    """
    Async exists check.
    """
    return model.objects.filter(**kwargs).exists()


@sync_to_async
def afirst(model: Type[models.Model], **kwargs) -> Optional[models.Model]:
    """
    Async first.
    """
    return model.objects.filter(**kwargs).first()


@sync_to_async
def alist(queryset: QuerySet) -> list:
    """
    QuerySet ni list ga o'zgartirish.
    """
    return list(queryset)


# ============================================
# TRANSACTION ASYNC HELPERS
# ============================================

@sync_to_async
def aget_with_related(model: Type[models.Model], related: list, **kwargs) -> models.Model:
    """
    select_related bilan async get.
    """
    return model.objects.select_related(*related).get(**kwargs)


@sync_to_async
def afilter_with_related(model: Type[models.Model], related: list, limit: int = 100, **kwargs) -> list:
    """
    select_related bilan async filter.
    """
    return list(model.objects.select_related(*related).filter(**kwargs)[:limit])


# ============================================
# CACHE ASYNC HELPERS
# ============================================

@sync_to_async
def acache_get(key: str, default: Any = None) -> Any:
    """
    Async cache get.
    """
    from django.core.cache import cache
    return cache.get(key, default)


@sync_to_async
def acache_set(key: str, value: Any, timeout: int = 300):
    """
    Async cache set.
    """
    from django.core.cache import cache
    cache.set(key, value, timeout)


@sync_to_async
def acache_delete(key: str):
    """
    Async cache delete.
    """
    from django.core.cache import cache
    cache.delete(key)
