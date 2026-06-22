from decimal import Decimal

from django.db import models
from django.utils import timezone
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.core.validators import validate_receipt_file, FileSizeValidator

# Import additional models from submodules
from apps.finance.payroll import StaffKPI, PayrollRecord, StaffAttendance
from apps.finance.inventory import AssetCategory, Asset, SupplyCategory, Supply, SupplyTransaction


class Account(TenantAwareModel):
    """
    Hisob raqamlar / Kassalar.
    M: 'Asosiy Kassa (Naqd)', 'Click Hamyon', 'Bank Hisob raqam'.
    """
    TYPE_CHOICES = (
        ('cash', 'Naqd pul'),
        ('bank', 'Bank hisobi'),
        ('card', 'Korporativ karta'),
        ('wallet', 'Elektron hamyon'),
    )

    name = models.CharField(max_length=100, verbose_name="Kassa nomi")
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='cash', verbose_name="Turi")
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Joriy Balans")

    def __str__(self):
        return f"{self.name} ({self.balance:,.0f})"

    class Meta:
        db_table = 'finance_accounts'
        verbose_name = "Kassa / Hisob"
        verbose_name_plural = "Kassalar"


class TransactionCategory(TenantAwareModel):
    """
    Kirim va Chiqim turlari (Statistika uchun).
    M: 'Kurs to\'lovi', 'Arenda', 'Xodimlar oyligi', 'Marketing'.
    """
    TYPE_CHOICES = (
        ('income', 'Kirim'),
        ('expense', 'Chiqim'),
    )

    name = models.CharField(max_length=100, verbose_name="Kategoriya nomi")
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Turi")

    def __str__(self):
        return f"{self.name} ({self.get_transaction_type_display()})"

    class Meta:
        db_table = 'finance_categories'
        verbose_name = "Tranzaksiya Kategoriyasi"
        verbose_name_plural = "Tranzaksiya Kategoriyalari"


class Transaction(TenantAwareModel):
    """
    ENG MUHIM JADVAL.
    Har bir pul harakati shu yerda saqlanadi.
    """
    TYPE_CHOICES = (
        ('income', 'Kirim (To\'lov)'),
        ('expense', 'Chiqim (Xarajat)'),
        ('transfer', 'O\'tkazma'),
        ('salary', 'Oylik to\'lov'),
        ('refund', 'Pul qaytarish'),
        ('monthly_fee', 'Oylik kurs to\'lovi (Abonent)'),
    )

    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),  # Kassir kiritdi, hali tasdiqlanmadi
        ('confirmed', 'Tasdiqlandi'),  # Direktor tasdiqladi (Balans o'zgaradi)
        ('rejected', 'Rad etildi'),
    )

    # 1. Pul qayerga tushdi/chiqdi?
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transactions', verbose_name="Kassa")
    category = models.ForeignKey(TransactionCategory, on_delete=models.SET_NULL, null=True, verbose_name="Kategoriya")

    # 2. Kim bilan bog'liq?
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments',
                                limit_choices_to={'role': 'student'}, verbose_name="O'quvchi")
    staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='salaries',
                              limit_choices_to={'role__in': ['teacher', 'staff', 'admin']}, verbose_name="Xodim")

    # 3. Summa va Tafsilotlar
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Summa")
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='income', verbose_name="Turi")
    description = models.TextField(blank=True, verbose_name="Izoh")
    
    # To'lov usuli (faqat 3 ta tur)
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Naqd pul'),
        ('card', 'Plastik karta'),
        ('terminal', 'Terminal'),
    )
    PAYMENT_METHOD_ALIASES = {
        'transfer': 'terminal',
        'online': 'terminal',
    }
    PAYMENT_METHOD_GROUPS = {
        'cash': ('cash',),
        'card': ('card',),
        'terminal': ('terminal', 'transfer', 'online'),
    }
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash', 
                                      verbose_name="To'lov usuli")

    # Kassa topshirish bilan bog'lash (topshirilganlik holati)
    cash_submission = models.ForeignKey(
        'CashSubmission', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions', verbose_name="Kassa topshirish"
    )
    
    # Chek/Kvitansiya (rasm yoki PDF)
    receipt_image = models.ImageField(
        upload_to='receipts/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Chek rasmi",
        validators=[FileSizeValidator(max_size_mb=5)]
    )
    receipt_file = models.FileField(
        upload_to='receipts/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Chek fayli (PDF)",
        validators=[validate_receipt_file, FileSizeValidator(max_size_mb=5)]
    )

    # Chekni tasdiqlash (plastik to'lovlari uchun)
    receipt_verified = models.BooleanField(default=False, verbose_name="Chek tasdiqlandi")
    receipt_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='verified_receipts', verbose_name="Chekni tasdiqladi")
    receipt_verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Tasdiqlash vaqti")
    receipt_notes = models.TextField(blank=True, verbose_name="Chek izohi")

    # 4. XAVFSIZLIK (Audit)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Holati")

    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_transactions',
                                   verbose_name="Kiritdi")
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='confirmed_transactions', verbose_name="Tasdiqladi")
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount:,.0f}"

    @classmethod
    def normalize_payment_method(cls, payment_method):
        if not payment_method:
            return 'cash'
        return cls.PAYMENT_METHOD_ALIASES.get(payment_method, payment_method)

    @classmethod
    def payment_method_values(cls, payment_method):
        normalized = cls.normalize_payment_method(payment_method)
        return cls.PAYMENT_METHOD_GROUPS.get(normalized, (normalized,))

    @classmethod
    def non_cash_payment_values(cls):
        values = []
        for method in ('card', 'terminal'):
            values.extend(cls.payment_method_values(method))
        return tuple(dict.fromkeys(values))

    def save(self, *args, **kwargs):
        self.payment_method = self.normalize_payment_method(self.payment_method)
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'finance_transactions'
        ordering = ['-created_at']
        verbose_name = "Tranzaksiya"
        verbose_name_plural = "Tranzaksiyalar"
        indexes = [
            models.Index(fields=['organization', 'status', 'transaction_type']),
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['student', 'transaction_type', 'status']),
            models.Index(fields=['account', 'status', 'cash_submission']),
            models.Index(fields=['organization', 'receipt_verified', 'status', 'payment_method']),
        ]


class CashSubmission(TenantAwareModel):
    """
    Administrator kassasini asosiy kassaga topshirish.
    Admin haftalik yoki oylik hisobotni topshiradi,
    super admin tasdiqlaydi va pul asosiy kassaga o'tadi.
    """
    PERIOD_CHOICES = (
        ('daily', 'Kunlik'),
        ('weekly', 'Haftalik'),
        ('monthly', 'Oylik'),
    )

    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    )

    # Qaysi admin topshirmoqda
    admin_user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='cash_submissions',
        verbose_name="Administrator"
    )

    # Admin kassasi (pul qayerdan)
    admin_account = models.ForeignKey(
        Account, on_delete=models.PROTECT,
        related_name='outgoing_submissions',
        verbose_name="Admin kassasi"
    )

    # Asosiy kassa (pul qayerga)
    main_account = models.ForeignKey(
        Account, on_delete=models.PROTECT,
        related_name='incoming_submissions',
        verbose_name="Asosiy kassa"
    )

    # Summalar
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Jami kirim")
    total_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Jami chiqim")
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Sof summa")
    
    # To'lov usuli bo'yicha tafsilotlar
    amount_cash = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Naqd pul")
    amount_card = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Plastik karta")
    amount_terminal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Terminal")

    # Davr
    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES, verbose_name="Davr turi")
    period_start = models.DateField(verbose_name="Davr boshlanishi")
    period_end = models.DateField(verbose_name="Davr tugashi")

    # Status va tasdiqlash
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Holati")
    notes = models.TextField(blank=True, verbose_name="Izoh")

    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_submissions',
        verbose_name="Tasdiqladi"
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Tasdiqlash vaqti")
    rejection_reason = models.TextField(blank=True, verbose_name="Rad etish sababi")

    def __init__(self, *args, **kwargs):
        self._legacy_amount_other = Decimal(str(kwargs.pop('amount_other', 0) or 0))
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.admin_user} - {self.get_period_type_display()} ({self.period_start} - {self.period_end})"

    @property
    def amount_other(self):
        return self._legacy_amount_other

    class Meta:
        db_table = 'finance_cash_submissions'
        ordering = ['-created_at']
        verbose_name = "Kassa topshirish"
        verbose_name_plural = "Kassa topshirishlar"
        indexes = [
            models.Index(fields=['admin_user', 'status', 'created_at']),
            models.Index(fields=['organization', 'status', 'period_end']),
        ]


class MonthlyFeeRun(TenantAwareModel):
    """
    Super admin yoki avtomatika tomonidan ishga tushirilgan kurs puli yechish jarayoni logi.
    """
    RUN_TYPE_CHOICES = (
        ('single', "Bitta o'quvchi"),
        ('bulk', "Barcha o'quvchilar"),
    )
    STATUS_CHOICES = (
        ('completed', 'Bajarildi'),
        ('partial', 'Qisman bajarildi'),
        ('skipped', "Yangi yechish topilmadi"),
        ('failed', 'Xatolik'),
    )

    billing_month = models.DateField(verbose_name="Hisob-kitob oyi (Y-M-01)")
    run_type = models.CharField(max_length=20, choices=RUN_TYPE_CHOICES, verbose_name="Ishga tushirish turi")
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_monthly_fee_runs',
        verbose_name="Kim ishga tushirdi",
    )
    target_student = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='targeted_monthly_fee_runs',
        limit_choices_to={'role': 'student'},
        verbose_name="Tanlangan o'quvchi",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed', verbose_name="Holati")
    total_students_processed = models.PositiveIntegerField(default=0, verbose_name="Qamrab olingan o'quvchilar")
    total_charges_created = models.PositiveIntegerField(default=0, verbose_name="Yangi yechilgan kurslar")
    skipped_existing_count = models.PositiveIntegerField(default=0, verbose_name="Oldin yechilgan kurslar")
    total_amount_deducted = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Jami yechilgan summa")
    password_verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Parol tasdiqlangan vaqt")
    triggered_at = models.DateTimeField(default=timezone.now, verbose_name="Bosilgan vaqt")
    notes = models.TextField(blank=True, verbose_name="Izoh")
    summary = models.JSONField(default=dict, blank=True, verbose_name="Qo'shimcha xulosa")

    def __str__(self):
        return f"{self.get_run_type_display()} - {self.billing_month:%Y-%m} - {self.get_status_display()}"

    class Meta:
        db_table = 'finance_monthly_fee_runs'
        ordering = ['-triggered_at', '-created_at']
        verbose_name = "Kurs puli yechish jurnali"
        verbose_name_plural = "Kurs puli yechish jurnallari"
        indexes = [
            models.Index(fields=['organization', 'billing_month', 'run_type']),
            models.Index(fields=['triggered_by', 'triggered_at']),
            models.Index(fields=['status', 'triggered_at']),
        ]


class MonthlyFeeCharge(TenantAwareModel):
    """
    Har bir student-guruh-oy kesimidagi kurs puli yechishning yagona yozuvi.
    Shu jadval takroriy yechib yuborishni oldini oladi.
    """
    SOURCE_CHOICES = (
        ('manual_single', "Qo'lda - bitta o'quvchi"),
        ('manual_bulk', "Qo'lda - barcha o'quvchilar"),
        ('auto_month_start', 'Avtomatik - oy boshida'),
        ('auto_mid_month', "Avtomatik - oy o'rtasida"),
    )

    billing_month = models.DateField(verbose_name="Hisob-kitob oyi (Y-M-01)")
    run = models.ForeignKey(
        'MonthlyFeeRun',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='charges',
        verbose_name="Jarayon logi",
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='monthly_fee_charges',
        limit_choices_to={'role': 'student'},
        verbose_name="O'quvchi",
    )
    group = models.ForeignKey(
        'education.Group',
        on_delete=models.CASCADE,
        related_name='monthly_fee_charges',
        verbose_name="Guruh",
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='monthly_fee_charges',
        verbose_name="Yaratilgan tranzaksiya",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Yechilgan summa")
    charge_source = models.CharField(max_length=30, choices=SOURCE_CHOICES, verbose_name="Manba")
    charged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_monthly_fee_charges',
        verbose_name="Kim yechdi",
    )
    charged_at = models.DateTimeField(default=timezone.now, verbose_name="Yechilgan vaqt")
    description = models.TextField(blank=True, verbose_name="Izoh")

    def __str__(self):
        return f"{self.student} - {self.group} - {self.billing_month:%Y-%m}"

    class Meta:
        db_table = 'finance_monthly_fee_charges'
        verbose_name = "Kurs puli yechish yozuvi"
        verbose_name_plural = "Kurs puli yechish yozuvlari"
        unique_together = ('organization', 'billing_month', 'student', 'group')
        indexes = [
            models.Index(fields=['organization', 'billing_month']),
            models.Index(fields=['student', 'billing_month']),
            models.Index(fields=['run', 'charged_at']),
        ]


class MonthlyFeeLog(TenantAwareModel):
    """
    Har oyda avtomatik to'lov yechish jarayoni logi.
    Har bir tashkilot uchun har oyda bitta log yaratiladi.
    """
    billing_month = models.DateField(verbose_name="Hisob kitob oyi (Y-M-01)")
    is_processed = models.BooleanField(default=False, verbose_name="Yechildimi?")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Qachon yechildi")
    total_students_billed = models.PositiveIntegerField(default=0, verbose_name="Qancha o'quvchidan yechildi")
    total_amount_billed = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Umumiy summa")

    def __str__(self):
        return f"{self.organization} - {self.billing_month} ({'Bajarildi' if self.is_processed else 'Kutilmoqda'})"

    class Meta:
        db_table = 'finance_monthly_fee_logs'
        unique_together = ('organization', 'billing_month')
        verbose_name = "Oylik to'lov hisoboti"
        verbose_name_plural = "Oylik to'lov hisobotlari"
