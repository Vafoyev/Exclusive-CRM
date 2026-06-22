"""
HR va Oylik modellari.
StaffKPI - Xodim KPI hisobi
PayrollRecord - Oylik hisob-kitobi
StaffAttendance - Xodim davomati (NFC)
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User


class StaffKPI(TenantAwareModel):
    """
    Xodim KPI (Key Performance Indicator) hisobi.
    Oylik bonus hisoblash uchun ishlatiladi.
    """
    staff = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='kpi_records',
        limit_choices_to={'role__in': ['teacher', 'staff', 'admin']}
    )
    
    # Davr
    period_start = models.DateField(verbose_name="Davr boshi")
    period_end = models.DateField(verbose_name="Davr oxiri")
    
    # O'qituvchilar uchun
    lessons_completed = models.PositiveIntegerField(default=0, verbose_name="O'tilgan darslar")
    students_count = models.PositiveIntegerField(default=0, verbose_name="O'quvchilar soni")
    students_retained = models.PositiveIntegerField(default=0, verbose_name="Saqlab qolingan o'quvchilar")
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Davomat foizi")
    average_grade = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="O'rtacha baho")
    
    # Umumiy
    tasks_completed = models.PositiveIntegerField(default=0, verbose_name="Bajarilgan vazifalar")
    late_count = models.PositiveIntegerField(default=0, verbose_name="Kechikishlar soni")
    absent_count = models.PositiveIntegerField(default=0, verbose_name="Yo'qlamalar soni")
    
    # Hisoblangan natija
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Umumiy ball")
    
    # Izoh
    notes = models.TextField(blank=True, verbose_name="Izoh")
    
    class Meta:
        db_table = 'staff_kpi'
        ordering = ['-period_end']
        verbose_name = "Xodim KPI"
        verbose_name_plural = "Xodimlar KPI"
        unique_together = ('staff', 'period_start', 'period_end')

    def __str__(self):
        return f"{self.staff.full_name} - {self.period_start} to {self.period_end}"

    def calculate_score(self):
        """KPI ballini hisoblash"""
        score = 0
        
        # Darslar uchun (har bir dars = 1 ball)
        score += self.lessons_completed * 1
        
        # Davomat foizi (90%+ = 10 ball, 80%+ = 5 ball)
        if self.attendance_rate >= 90:
            score += 10
        elif self.attendance_rate >= 80:
            score += 5
        
        # O'rtacha baho (80+ = 10 ball)
        if self.average_grade >= 80:
            score += 10
        elif self.average_grade >= 70:
            score += 5
        
        # Kechikishlar uchun jarima (har biri -2 ball)
        score -= self.late_count * 2
        
        # Yo'qlamalar uchun jarima (har biri -5 ball)
        score -= self.absent_count * 5
        
        self.total_score = max(0, score)
        return self.total_score


class PayrollRecord(TenantAwareModel):
    """
    Xodim oylik hisob-kitobi.
    Formula: (Asosiy + Bonus) - (Jarima + Kechikish) = Qo'lga tegadigan
    """
    STATUS_CHOICES = (
        ('draft', 'Qoralama'),
        ('pending', 'Kutilmoqda'),
        ('approved', 'Tasdiqlangan'),
        ('paid', 'To\'langan'),
        ('cancelled', 'Bekor qilingan'),
    )
    
    staff = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='payroll_records',
        limit_choices_to={'role__in': ['teacher', 'staff', 'admin']}
    )
    
    # Davr
    month = models.DateField(verbose_name="Oy (1-sana)")  # Har doim oyning 1-sanasi
    
    # Hisob-kitob
    base_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Asosiy oylik")
    per_lesson_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Darslik stavka")
    lessons_count = models.PositiveIntegerField(default=0, verbose_name="Darslar soni")
    lesson_earnings = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Dars daromadi")
    
    kpi_bonus = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="KPI bonus")
    other_bonus = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Boshqa bonuslar")
    
    late_penalty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Kechikish jarimasi")
    absent_penalty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Yo'qlama jarimasi")
    other_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Boshqa ushlab qolishlar")
    
    # Yakuniy
    gross_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Yalpi summa")
    total_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Jami ushlab qolish")
    net_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Qo'lga tegadigan")
    
    # Status va audit
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Holat")
    notes = models.TextField(blank=True, verbose_name="Izoh")
    
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='approved_payrolls', verbose_name="Tasdiqladi"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payroll_records'
        ordering = ['-month', 'staff__first_name']
        verbose_name = "Oylik hisob"
        verbose_name_plural = "Oylik hisoblar"
        unique_together = ('staff', 'month')

    def __str__(self):
        return f"{self.staff.full_name} - {self.month.strftime('%B %Y')}"

    def calculate(self):
        """Oylikni hisoblash"""
        # Dars daromadi
        self.lesson_earnings = self.per_lesson_rate * self.lessons_count
        
        # Yalpi summa
        self.gross_salary = (
            self.base_salary + 
            self.lesson_earnings + 
            self.kpi_bonus + 
            self.other_bonus
        )
        
        # Jami ushlab qolish
        self.total_deductions = (
            self.late_penalty + 
            self.absent_penalty + 
            self.other_deductions
        )
        
        # Qo'lga tegadigan
        self.net_salary = self.gross_salary - self.total_deductions
        
        return self.net_salary


class StaffAttendance(TenantAwareModel):
    """
    Xodim davomati (HR).
    NFC yoki manual kiritiladi.
    """
    staff = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='staff_attendances',
        limit_choices_to={'role__in': ['teacher', 'staff', 'admin']}
    )
    
    date = models.DateField(verbose_name="Sana")
    check_in = models.TimeField(null=True, blank=True, verbose_name="Keldi")
    check_out = models.TimeField(null=True, blank=True, verbose_name="Ketdi")
    
    # Kechikish
    expected_time = models.TimeField(default='09:00', verbose_name="Kutilgan vaqt")
    late_minutes = models.PositiveIntegerField(default=0, verbose_name="Kechikish (daqiqa)")
    
    # Status
    STATUS_CHOICES = (
        ('present', 'Keldi'),
        ('absent', 'Kelmadi'),
        ('late', 'Kechikdi'),
        ('half_day', 'Yarim kun'),
        ('leave', 'Ta\'til'),
        ('sick', 'Kasallik'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present', verbose_name="Holat")
    
    # NFC
    nfc_check_in = models.BooleanField(default=False, verbose_name="NFC orqali keldimi?")
    nfc_check_out = models.BooleanField(default=False, verbose_name="NFC orqali ketdimi?")
    
    notes = models.CharField(max_length=255, blank=True, verbose_name="Izoh")
    
    class Meta:
        db_table = 'staff_attendance'
        ordering = ['-date', 'staff__first_name']
        verbose_name = "Xodim davomati"
        verbose_name_plural = "Xodimlar davomati"
        unique_together = ('staff', 'date')

    def __str__(self):
        return f"{self.staff.full_name} - {self.date}"

    def calculate_late_minutes(self):
        """Kechikish daqiqalarini hisoblash"""
        if self.check_in and self.expected_time:
            from datetime import datetime, time, timedelta

            expected = self.expected_time
            if isinstance(expected, str):
                try:
                    parts = expected.split(':')
                    expected = time(int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    return self.late_minutes

            check_in = self.check_in
            if isinstance(check_in, str):
                try:
                    parts = check_in.split(':')
                    check_in = time(int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    return self.late_minutes

            check_in_dt = datetime.combine(self.date, check_in)
            expected_dt = datetime.combine(self.date, expected)
            
            if check_in_dt > expected_dt:
                diff = check_in_dt - expected_dt
                self.late_minutes = int(diff.total_seconds() / 60)
                self.status = 'late'
            else:
                self.late_minutes = 0
                self.status = 'present'
        
        return self.late_minutes
