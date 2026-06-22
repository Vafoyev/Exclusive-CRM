from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from .models import Lesson, Attendance
from .services import finish_lesson_logic


class AttendanceInline(TabularInline):
    model = Attendance
    extra = 0
    autocomplete_fields = ['student']


@admin.register(Lesson)
class LessonAdmin(ModelAdmin):
    list_display = ('group', 'date', 'start_time', 'teacher', 'status_badge')
    list_filter = ('status', 'date', 'group')
    inlines = [AttendanceInline]
    list_filter_submit = True
    search_fields = ('group__name', 'teacher__first_name')

    @admin.display(description="Holat")
    def status_badge(self, obj):
        status_colors = {
            'scheduled': '#3b82f6',
            'ongoing': '#f59e0b',
            'finished': '#10b981',
            'cancelled': '#ef4444',
        }
        color = status_colors.get(obj.status, '#6b7280')
        status_text = obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        return mark_safe(
            f'<span style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{status_text}</span>'
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:lesson_id>/finish/', self.admin_site.admin_view(self.finish_lesson_view), name='lesson-finish'),
        ]
        return custom_urls + urls

    def finish_lesson_view(self, request, lesson_id):
        try:
            msg = finish_lesson_logic(lesson_id, request.user)
            self.message_user(request, msg, level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Xatolik: {e}", level=messages.ERROR)

        return redirect('admin:operations_lesson_changelist')


@admin.register(Attendance)
class AttendanceAdmin(ModelAdmin):
    list_display = ('lesson', 'student', 'status_badge', 'grade')
    list_filter = ('status', 'lesson__date')
    search_fields = ('student__first_name', 'student__phone')
    list_filter_submit = True

    @admin.display(description="Holat")
    def status_badge(self, obj):
        status_colors = {
            'present': '#10b981',
            'absent': '#ef4444',
            'late': '#f59e0b',
            'excused': '#6b7280',
        }
        color = status_colors.get(obj.status, '#6b7280')
        status_text = obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        return mark_safe(
            f'<span style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{status_text}</span>'
        )
