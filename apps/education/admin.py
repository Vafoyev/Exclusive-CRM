from django.contrib import admin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from .models import Room, Course, Group, GroupStudent
from .forms import GroupForm


@admin.register(Room)
class RoomAdmin(ModelAdmin):
    list_display = ('name', 'capacity', 'projector_badge')
    list_filter = ('has_projector',)
    search_fields = ('name',)
    list_filter_submit = True

    @admin.display(description="Proektor")
    def projector_badge(self, obj):
        if obj.has_projector:
            return mark_safe(
                '<span style="background-color: #10b981; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Bor</span>'
            )
        return mark_safe(
            '<span style="background-color: #6b7280; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">Yo\'q</span>'
        )


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ('name', 'price_display', 'duration_months', 'status_badge')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_filter_submit = True

    @admin.display(description="Narx")
    def price_display(self, obj):
        formatted = "{:,.0f}".format(obj.price) if obj.price else "0"
        return mark_safe(
            f'<span style="color: #059669; font-weight: bold;">{formatted} so\'m</span>'
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


class StudentInline(TabularInline):
    model = GroupStudent
    extra = 1
    autocomplete_fields = ['student']


@admin.register(Group)
class GroupAdmin(ModelAdmin):
    form = GroupForm
    list_display = ('name', 'course', 'teacher', 'room', 'start_time', 'status_badge')
    list_filter = ('status', 'course', 'teacher')
    inlines = [StudentInline]
    search_fields = ('name',)
    list_filter_submit = True

    @admin.display(description="Holat")
    def status_badge(self, obj):
        status_colors = {
            'pending': '#f59e0b',
            'active': '#10b981',
            'finished': '#6b7280',
            'cancelled': '#ef4444',
        }
        color = status_colors.get(obj.status, '#6b7280')
        status_text = obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        return mark_safe(
            f'<span style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{status_text}</span>'
        )


@admin.register(GroupStudent)
class GroupStudentAdmin(ModelAdmin):
    list_display = ('student', 'group', 'status_badge', 'joined_at')
    list_filter = ('status', 'group')
    search_fields = ('student__phone', 'student__first_name')
    list_filter_submit = True

    @admin.display(description="Holat")
    def status_badge(self, obj):
        status_colors = {
            'active': '#10b981',
            'paused': '#f59e0b',
            'finished': '#6b7280',
            'expelled': '#ef4444',
        }
        color = status_colors.get(obj.status, '#6b7280')
        status_text = obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        return mark_safe(
            f'<span style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{status_text}</span>'
        )
