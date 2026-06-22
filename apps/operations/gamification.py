"""
Gamification modellari.
XP, Level, Badge tizimi.
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User


class Level(TenantAwareModel):
    """
    O'quvchi darajalari.
    XP asosida avtomatik belgilanadi.
    """
    name = models.CharField(max_length=50, verbose_name="Daraja nomi")  # Beginner, Intermediate, Advanced
    name_uz = models.CharField(max_length=50, verbose_name="O'zbekcha nomi")  # Boshlang'ich, O'rta, Yuqori
    min_xp = models.PositiveIntegerField(verbose_name="Minimal XP")
    max_xp = models.PositiveIntegerField(verbose_name="Maksimal XP")
    icon = models.CharField(max_length=50, default='⭐', verbose_name="Ikonka")
    color = models.CharField(max_length=20, default='blue', verbose_name="Rang")  # Tailwind class
    
    class Meta:
        db_table = 'gamification_levels'
        ordering = ['min_xp']
        verbose_name = "Daraja"
        verbose_name_plural = "Darajalar"

    def __str__(self):
        return f"{self.name} ({self.min_xp}-{self.max_xp} XP)"


class Badge(TenantAwareModel):
    """
    Yutuq nishonlari.
    Masalan: "Eng tirishqoq", "30 kun ketma-ket"
    """
    name = models.CharField(max_length=100, verbose_name="Nishon nomi")
    description = models.CharField(max_length=255, verbose_name="Tavsif")
    icon = models.CharField(max_length=50, default='🏆', verbose_name="Ikonka")
    color = models.CharField(max_length=20, default='yellow', verbose_name="Rang")
    
    # Qanday olinadi
    TRIGGER_CHOICES = (
        ('attendance_streak', 'Ketma-ket davomat'),
        ('grade_average', "O'rtacha baho"),
        ('xp_milestone', 'XP chegara'),
        ('lessons_count', 'Darslar soni'),
        ('manual', 'Qo\'lda beriladi'),
    )
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_CHOICES, default='manual', verbose_name="Trigger turi")
    trigger_value = models.PositiveIntegerField(default=0, verbose_name="Trigger qiymati")
    
    # Mukofot
    xp_reward = models.PositiveIntegerField(default=0, verbose_name="XP mukofoti")
    
    class Meta:
        db_table = 'gamification_badges'
        verbose_name = "Nishon"
        verbose_name_plural = "Nishonlar"

    def __str__(self):
        return f"{self.icon} {self.name}"


class StudentBadge(TenantAwareModel):
    """O'quvchiga berilgan nishonlar"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges',
                               limit_choices_to={'role': 'student'})
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awarded_to')
    awarded_at = models.DateTimeField(auto_now_add=True)
    awarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='awarded_badges')
    notes = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'student_badges'
        ordering = ['-awarded_at']
        verbose_name = "O'quvchi nishoni"
        verbose_name_plural = "O'quvchi nishonlari"
        unique_together = ('student', 'badge')

    def __str__(self):
        return f"{self.student.full_name} - {self.badge.name}"


class XPTransaction(TenantAwareModel):
    """XP harakatlari tarixi"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='xp_transactions',
                               limit_choices_to={'role': 'student'})
    
    SOURCE_CHOICES = (
        ('attendance', 'Davomat'),
        ('grade', 'Baho'),
        ('badge', 'Nishon'),
        ('bonus', 'Bonus'),
        ('penalty', 'Jarima'),
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, verbose_name="Manba")
    amount = models.IntegerField(verbose_name="XP miqdori")  # + yoki -
    description = models.CharField(max_length=255, blank=True)
    
    # Bog'liq ob'ekt (ixtiyoriy)
    related_lesson = models.ForeignKey('operations.Lesson', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'xp_transactions'
        ordering = ['-created_at']
        verbose_name = "XP harakati"
        verbose_name_plural = "XP harakatlari"

    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.student.full_name}: {sign}{self.amount} XP ({self.source})"

    def save(self, *args, **kwargs):
        # O'quvchi XP ni yangilash
        if self._state.adding:
            from apps.users.models import User
            # User modelida balance maydonini XP sifatida ishlatamiz yoki alohida maydon qo'shamiz
            # Hozircha profile_data ichida saqlaymiz
            xp_data = self.student.profile_data.get('xp', 0)
            self.student.profile_data['xp'] = max(0, xp_data + self.amount)
            self.student.save(update_fields=['profile_data'])
        super().save(*args, **kwargs)


class Streak(TenantAwareModel):
    """O'quvchi streak (ketma-ketlik) hisobi"""
    student = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak',
                                   limit_choices_to={'role': 'student'})
    
    current_streak = models.PositiveIntegerField(default=0, verbose_name="Joriy streak")
    longest_streak = models.PositiveIntegerField(default=0, verbose_name="Eng uzun streak")
    last_attendance_date = models.DateField(null=True, blank=True, verbose_name="Oxirgi davomat")
    
    class Meta:
        db_table = 'student_streaks'
        verbose_name = "O'quvchi streak"
        verbose_name_plural = "O'quvchi streaklari"

    def __str__(self):
        return f"{self.student.full_name}: {self.current_streak} kun"

    def update_streak(self, attendance_date):
        """Streakni yangilash"""
        from datetime import timedelta
        
        if self.last_attendance_date:
            diff = (attendance_date - self.last_attendance_date).days
            
            if diff == 1:
                # Ketma-ket kun
                self.current_streak += 1
            elif diff > 1:
                # Uzilish bo'lgan
                self.current_streak = 1
            # diff == 0 bo'lsa, bir kunda ikki marta davomatga kelgan
        else:
            self.current_streak = 1
        
        self.longest_streak = max(self.longest_streak, self.current_streak)
        self.last_attendance_date = attendance_date
        self.save()
