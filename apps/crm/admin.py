from django.contrib import admin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from .models import LeadSource, Stage, Lead, Activity


@admin.register(LeadSource)
class LeadSourceAdmin(ModelAdmin):
    list_display = ('name', 'utm_source')
    search_fields = ('name', 'utm_source')
    list_filter_submit = True


@admin.register(Stage)
class StageAdmin(ModelAdmin):
    list_display = ('name', 'order', 'won_badge', 'color_preview')
    list_editable = ('order',)
    list_filter_submit = True

    @admin.display(description="Yutildi")
    def won_badge(self, obj):
        if obj.is_won:
            return mark_safe(
                '<span style="background-color: #10b981; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">✓ Yutildi</span>'
            )
        return mark_safe(
            '<span style="background-color: #6b7280; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Jarayonda</span>'
        )

    @admin.display(description="Rang")
    def color_preview(self, obj):
        color = obj.color or '#6b7280'
        color_text = obj.color or 'Yo\'q'
        return mark_safe(
            f'<span style="background-color: {color}; color: white; padding: 4px 12px; border-radius: 6px; font-size: 12px;">{color_text}</span>'
        )


class ActivityInline(TabularInline):
    model = Activity
    extra = 1
    readonly_fields = ('created_at',)


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    list_display = ('full_name', 'phone', 'source', 'stage_badge', 'assigned_to', 'created_at')
    list_filter = ('stage', 'source', 'assigned_to')
    search_fields = ('full_name', 'phone')
    inlines = [ActivityInline]
    list_filter_submit = True

    @admin.display(description="Bosqich")
    def stage_badge(self, obj):
        if obj.stage:
            color = obj.stage.color or '#6b7280'
            return mark_safe(
                f'<span style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{obj.stage.name}</span>'
            )
        return "-"
