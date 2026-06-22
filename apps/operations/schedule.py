"""
Dars jadvali modellari.
Haftalik pattern va conflict detection.
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.education.models import Group, Room


class SchedulePattern(TenantAwareModel):
    """
    Haftalik dars jadvali patterni.
    Guruhning haftalik takrorlanuvchi darslari.
    """
    DAYS_OF_WEEK = (
        (0, 'Dushanba'),
        (1, 'Seshanba'),
        (2, 'Chorshanba'),
        (3, 'Payshanba'),
        (4, 'Juma'),
        (5, 'Shanba'),
        (6, 'Yakshanba'),
    )
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='schedule_patterns', verbose_name="Guruh")
    day_of_week = models.PositiveIntegerField(choices=DAYS_OF_WEEK, verbose_name="Hafta kuni")
    start_time = models.TimeField(verbose_name="Boshlanish vaqti")
    end_time = models.TimeField(verbose_name="Tugash vaqti")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, 
                            related_name='schedule_patterns', verbose_name="Xona")
    
    is_active = models.BooleanField(default=True, verbose_name="Faolmi?")
    
    class Meta:
        db_table = 'schedule_patterns'
        ordering = ['day_of_week', 'start_time']
        verbose_name = "Jadval patterni"
        verbose_name_plural = "Jadval patternlari"

    def __str__(self):
        return f"{self.group.name} - {self.get_day_of_week_display()} {self.start_time}"

    @classmethod
    def check_room_conflict(cls, room, day_of_week, start_time, end_time, exclude_id=None):
        """
        Xona band emasligini tekshirish.
        Returns: (is_conflict, conflicting_pattern)
        """
        if not room:
            return False, None
            
        conflicts = cls.objects.filter(
            room=room,
            day_of_week=day_of_week,
            is_active=True
        )
        
        if exclude_id:
            conflicts = conflicts.exclude(id=exclude_id)
        
        for pattern in conflicts:
            # Vaqt kesishishini tekshirish
            if (start_time < pattern.end_time and end_time > pattern.start_time):
                return True, pattern
        
        return False, None

    @classmethod
    def check_teacher_conflict(cls, teacher, day_of_week, start_time, end_time, exclude_id=None):
        """
        O'qituvchi band emasligini tekshirish.
        """
        conflicts = cls.objects.filter(
            group__teacher=teacher,
            day_of_week=day_of_week,
            is_active=True
        )
        
        if exclude_id:
            conflicts = conflicts.exclude(id=exclude_id)
        
        for pattern in conflicts:
            if (start_time < pattern.end_time and end_time > pattern.start_time):
                return True, pattern
        
        return False, None


class LessonGenerationLog(TenantAwareModel):
    """Dars yaratish logi"""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='generation_logs')
    
    date_from = models.DateField(verbose_name="Boshlang'ich sana")
    date_to = models.DateField(verbose_name="Tugash sanasi")
    lessons_created = models.PositiveIntegerField(default=0, verbose_name="Yaratilgan darslar")
    
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'lesson_generation_logs'
        ordering = ['-created_at']
        verbose_name = "Dars yaratish logi"
        verbose_name_plural = "Dars yaratish loglari"


def generate_lessons_for_group(group, date_from, date_to, created_by=None):
    """
    Guruh uchun patternlar asosida darslarni avtomatik yaratish.
    """
    from datetime import timedelta
    from apps.operations.models import Lesson
    
    patterns = SchedulePattern.objects.filter(group=group, is_active=True)
    
    if not patterns.exists():
        return 0
    
    lessons_created = 0
    current_date = date_from
    
    while current_date <= date_to:
        day_of_week = current_date.weekday()
        
        for pattern in patterns.filter(day_of_week=day_of_week):
            # Mavjudligini tekshirish
            exists = Lesson.objects.filter(
                group=group,
                date=current_date,
                start_time=pattern.start_time
            ).exists()
            
            if not exists:
                Lesson.objects.create(
                    organization=group.organization,
                    group=group,
                    teacher=group.teacher,
                    room=pattern.room,
                    date=current_date,
                    start_time=pattern.start_time,
                    end_time=pattern.end_time,
                    status='scheduled'
                )
                lessons_created += 1
        
        current_date += timedelta(days=1)
    
    # Log yozish
    if lessons_created > 0:
        LessonGenerationLog.objects.create(
            organization=group.organization,
            group=group,
            date_from=date_from,
            date_to=date_to,
            lessons_created=lessons_created,
            generated_by=created_by
        )
    
    return lessons_created
