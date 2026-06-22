"""
Custom API permissions.
Rol asosida API endpointlarga kirishni cheklash.
"""
from rest_framework.permissions import BasePermission


class IsParent(BasePermission):
    """Faqat ota-ona rolidagi foydalanuvchilarga ruxsat."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'parent'
        )


class IsStudent(BasePermission):
    """Faqat o'quvchi rolidagi foydalanuvchilarga ruxsat."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'student'
        )
