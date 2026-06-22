from django.contrib import admin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import Organization, Branch


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ('name', 'subdomain', 'owner', 'status_badge', 'created_at')
    search_fields = ('name', 'subdomain')
    list_filter = ('is_active',)
    list_filter_submit = True

    @admin.display(description="Holat")
    def status_badge(self, obj):
        if obj.is_active:
            return mark_safe(
                '<span style="background-color: #10b981; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Faol</span>'
            )
        return mark_safe(
            '<span style="background-color: #ef4444; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Nofaol</span>'
        )


@admin.register(Branch)
class BranchAdmin(ModelAdmin):
    list_display = ('name', 'organization', 'phone', 'main_badge')
    list_filter = ('organization', 'is_main')
    search_fields = ('name', 'phone')
    list_filter_submit = True

    @admin.display(description="Asosiy")
    def main_badge(self, obj):
        if obj.is_main:
            return mark_safe(
                '<span style="background-color: #3b82f6; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Asosiy</span>'
            )
        return mark_safe(
            '<span style="background-color: #6b7280; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Filial</span>'
        )
