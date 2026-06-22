"""
Kassa Yopish (Cash Register Closing / Z-Report).
Kunlik kassa hisobi va tasdiqlash.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.finance.models import Account, Transaction


class CashRegisterSession(TenantAwareModel):
    """
    Kassa smena/sessiyasi.
    Kun boshida ochiladi, kun oxirida yopiladi.
    """
    STATUS_CHOICES = (
        ('open', 'Ochiq'),
        ('pending', 'Yopilmoqda'),
        ('closed', 'Yopilgan'),
    )
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='sessions', verbose_name="Kassa")
    
    # Sessiya davri
    opened_at = models.DateTimeField(default=timezone.now, verbose_name="Ochildi")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Yopildi")
    
    # Ochilish balansii
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Boshlang'ich balans")
    
    # Kun davomida
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Jami kirim")
    total_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Jami chiqim")
    
    # Yopish
    expected_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Kutilgan balans")
    actual_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Haqiqiy balans")
    difference = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Farq")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name="Holat")
    notes = models.TextField(blank=True, verbose_name="Izoh")
    
    # Audit
    opened_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='opened_sessions')
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_sessions')
    
    class Meta:
        db_table = 'cash_register_sessions'
        ordering = ['-opened_at']
        verbose_name = "Kassa sessiyasi"
        verbose_name_plural = "Kassa sessiyalari"

    def __str__(self):
        return f"{self.account.name} - {self.opened_at.strftime('%d.%m.%Y')}"

    def calculate_totals(self):
        """Kun davomidagi kirim-chiqimni hisoblash"""
        transactions = Transaction.objects.filter(
            account=self.account,
            created_at__gte=self.opened_at,
            status='confirmed'
        )
        
        if self.closed_at:
            transactions = transactions.filter(created_at__lte=self.closed_at)
        
        totals = transactions.aggregate(
            total_income=models.Sum('amount', filter=models.Q(transaction_type='income')),
            total_expense=models.Sum('amount', filter=models.Q(transaction_type__in=['expense', 'salary', 'refund'])),
        )
        self.total_income = totals['total_income'] or 0
        self.total_expense = totals['total_expense'] or 0
        
        self.expected_balance = self.opening_balance + self.total_income - self.total_expense
        return self.expected_balance

    def close_session(self, actual_balance, closed_by, notes=''):
        """Sessiyani yopish"""
        self.calculate_totals()
        self.actual_balance = actual_balance
        self.difference = actual_balance - self.expected_balance
        self.closed_at = timezone.now()
        self.closed_by = closed_by
        self.notes = notes
        self.status = 'closed'
        self.save()
        
        # Keyingi sessiya uchun balansni yangilash
        self.account.balance = actual_balance
        self.account.save()
        
        return self.difference


class DailyReport(TenantAwareModel):
    """Kunlik moliyaviy hisobot (Z-Report)"""
    date = models.DateField(unique=True, verbose_name="Sana")
    
    # Umumiy ko'rsatkichlar
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Tranzaksiyalar soni
    income_count = models.PositiveIntegerField(default=0)
    expense_count = models.PositiveIntegerField(default=0)
    
    # O'quvchilar
    new_students = models.PositiveIntegerField(default=0, verbose_name="Yangi o'quvchilar")
    payments_received = models.PositiveIntegerField(default=0, verbose_name="To'lovlar soni")
    
    # Darslar
    lessons_completed = models.PositiveIntegerField(default=0, verbose_name="O'tilgan darslar")
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Davomat foizi")
    
    # Avtomatik yaratildi
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'daily_reports'
        ordering = ['-date']
        verbose_name = "Kunlik hisobot"
        verbose_name_plural = "Kunlik hisobotlar"

    def __str__(self):
        return f"Hisobot - {self.date}"

    @classmethod
    def generate_for_date(cls, organization, date):
        """Ma'lum sana uchun hisobot yaratish"""
        from django.db.models import Sum, Count, Avg
        from datetime import datetime, timedelta
        from apps.operations.models import Lesson, Attendance
        from apps.users.models import User
        
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())
        
        # Tranzaksiyalar
        transactions = Transaction.objects.filter(
            organization=organization,
            created_at__range=(start, end),
            status='confirmed'
        )
        
        income = transactions.filter(transaction_type='income').aggregate(
            total=Sum('amount'), count=Count('id')
        )
        expense = transactions.filter(transaction_type__in=['expense', 'salary']).aggregate(
            total=Sum('amount'), count=Count('id')
        )
        
        # Darslar
        lessons = Lesson.objects.filter(
            organization=organization,
            date=date,
            status='finished'
        )
        
        attendances = Attendance.objects.filter(
            lesson__in=lessons
        )
        attendance_stats = attendances.aggregate(
            total=Count('id'),
            present=Count('id', filter=models.Q(status='present')),
        )
        total_attendances = attendance_stats['total'] or 0
        present = attendance_stats['present'] or 0
        attendance_rate = (present / total_attendances) * 100 if total_attendances > 0 else 0
        
        # Yangi o'quvchilar
        new_students = User.objects.filter(
            organization=organization,
            role='student',
            date_joined__date=date
        ).count()
        
        report, created = cls.objects.update_or_create(
            organization=organization,
            date=date,
            defaults={
                'total_income': income['total'] or 0,
                'income_count': income['count'] or 0,
                'total_expense': expense['total'] or 0,
                'expense_count': expense['count'] or 0,
                'net_profit': (income['total'] or 0) - (expense['total'] or 0),
                'lessons_completed': lessons.count(),
                'attendance_rate': attendance_rate,
                'new_students': new_students,
                'payments_received': income['count'] or 0,
            }
        )
        
        return report
