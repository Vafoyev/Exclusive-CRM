from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.education.models import Group, Room

# Import additional models from submodules
from apps.operations.gamification import Level, Badge, StudentBadge, XPTransaction, Streak
from apps.operations.schedule import SchedulePattern, LessonGenerationLog
from apps.operations.shop import ShopCategory, ShopItem, Purchase


class Lesson(TenantAwareModel):
    """
    Har bir o'tiladigan dars (Unit).
    Masalan: "IELTS-A guruhi, 14-Yanvar, 14:00".
    """
    STATUS_CHOICES = (
        ('scheduled', 'Rejalashtirilgan'),
        ('started', 'Dars ketmoqda'),
        ('finished', 'Yakunlangan'),  # Pul yechilgan holat
        ('cancelled', 'Bekor qilingan'),
    )

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='lessons', verbose_name="Guruh")
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="O'qituvchi")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, verbose_name="Xona")

    date = models.DateField(verbose_name="Sana")
    start_time = models.TimeField(verbose_name="Boshlanish vaqti")
    end_time = models.TimeField(verbose_name="Tugash vaqti")

    topic = models.CharField(max_length=255, blank=True, verbose_name="Mavzu")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name="Holati")

    # Audit uchun
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.group.name} ({self.date})"

    class Meta:
        db_table = 'lessons'
        ordering = ['-date', '-start_time']
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        indexes = [
            models.Index(fields=['organization', 'date']),
            models.Index(fields=['teacher', 'date']),
            models.Index(fields=['group', 'date']),
        ]


class Attendance(TenantAwareModel):
    """
    O'quvchining darsdagi ishtiroki.
    Bu jadval Moliya bilan to'g'ridan-to'g'ri bog'lanadi.
    """
    STATUS_CHOICES = (
        ('present', 'Bor'),
        ('absent', 'Yo\'q (Sababsiz)'),
        ('excused', 'Sababli'),
        ('late', 'Kechikdi'),
    )

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_attendances')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')

    # Baholash va Gamification
    grade = models.PositiveIntegerField(null=True, blank=True, verbose_name="Baho (0-100)")
    xp_points = models.PositiveIntegerField(default=0, verbose_name="XP Ochko")

    comment = models.CharField(max_length=255, blank=True, verbose_name="Izoh")

    class Meta:
        db_table = 'attendance'
        unique_together = ('lesson', 'student')  # Bir darsda ikki marta belgilab bo'lmaydi
        verbose_name = "Davomat"
        verbose_name_plural = "Davomatlar"


class TeacherWeeklyRating(TenantAwareModel):
    """
    O'qituvchiga haftalik baho.
    Super admin yoki owner tomonidan haftada bir marta qo'yiladi.
    """
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='weekly_ratings')
    rated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='given_teacher_ratings')

    # Hafta
    week_start = models.DateField(verbose_name="Hafta boshlanishi")
    week_end = models.DateField(verbose_name="Hafta tugashi")

    # Baholash mezonlari (1-5 ball)
    preparation = models.PositiveSmallIntegerField(default=5, verbose_name="Tayyorgarlik")
    delivery = models.PositiveSmallIntegerField(default=5, verbose_name="Tushuntirish")
    engagement = models.PositiveSmallIntegerField(default=5, verbose_name="Faollik")
    punctuality = models.PositiveSmallIntegerField(default=5, verbose_name="Vaqtga rioya")
    overall = models.PositiveSmallIntegerField(default=5, verbose_name="Umumiy baho")

    comment = models.TextField(blank=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def average_score(self):
        """O'rtacha ball"""
        return round((self.preparation + self.delivery + self.engagement + self.punctuality + self.overall) / 5, 1)

    class Meta:
        db_table = 'teacher_weekly_ratings'
        unique_together = ('teacher', 'week_start')  # Har hafta faqat 1 ta baho
        verbose_name = "O'qituvchi haftalik bahosi"
        verbose_name_plural = "O'qituvchi haftalik baholari"
        ordering = ['-week_start']
