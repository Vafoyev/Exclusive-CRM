from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import User, ParentStudent


@admin.register(User)
class CustomUserAdmin(UserAdmin, ModelAdmin):
    # Username maydonini admin paneldan olib tashlaymiz
    ordering = ('phone',)
    list_display = ('phone', 'full_name_display', 'role_badge', 'organization', 'balance_display', 'status_badge')
    list_filter = ('role', 'organization', 'is_active')
    search_fields = ('phone', 'first_name', 'last_name')
    list_filter_submit = True

    # Fieldsetlarni (formani) to'g'irlash
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Shaxsiy ma\'lumotlar', {'fields': ('first_name', 'last_name', 'middle_name', 'avatar')}),
        ('Tizim', {'fields': ('role', 'organization', 'branch', 'is_active')}),
        ('Moliya & HR', {'fields': ('balance', 'nfc_card_id', 'profile_data')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'first_name', 'last_name', 'role', 'password'),
        }),
    )

    @admin.display(description="F.I.O")
    def full_name_display(self, obj):
        return f"{obj.first_name} {obj.last_name}" if obj.first_name else "-"

    @admin.display(description="Rol")
    def role_badge(self, obj):
        role_colors = {
            'super_admin': '#7c3aed',
            'owner': '#dc2626',
            'admin': '#2563eb',
            'teacher': '#059669',
            'student': '#0891b2',
            'staff': '#6b7280',
        }
        color = role_colors.get(obj.role, '#6b7280')
        role_name = obj.get_role_display() if hasattr(obj, 'get_role_display') else obj.role
        return mark_safe(
            f'<span style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{role_name}</span>'
        )

    @admin.display(description="Balans")
    def balance_display(self, obj):
        formatted = "{:,.0f}".format(obj.balance) if obj.balance else "0"
        color = "#10b981" if obj.balance and obj.balance >= 0 else "#ef4444"
        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{formatted} so\'m</span>'
        )

    @admin.display(description="Holat")
    def status_badge(self, obj):
        if obj.is_active:
            return mark_safe(
                '<span style="background-color: #10b981; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Faol</span>'
            )
        return mark_safe(
            '<span style="background-color: #ef4444; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Nofaol</span>'
        )


@admin.register(ParentStudent)
class ParentStudentAdmin(ModelAdmin):
    list_display = ('parent', 'student', 'relation_type', 'main_contact_badge')
    list_filter = ('relation_type', 'is_main_contact')
    search_fields = ('parent__phone', 'student__phone', 'parent__first_name', 'student__first_name')
    list_filter_submit = True

    @admin.display(description="Asosiy kontakt")
    def main_contact_badge(self, obj):
        if obj.is_main_contact:
            return mark_safe(
                '<span style="background-color: #3b82f6; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Ha</span>'
            )
        return mark_safe(
            '<span style="background-color: #6b7280; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Yo\'q</span>'
        )
