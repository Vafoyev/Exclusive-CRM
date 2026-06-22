import uuid
from django.db import models
from django.utils import timezone
from apps.core.middleware import get_current_organization

class BaseModel(models.Model):
    """
    Barcha modellar uchun umumiy maydonlar:
    - ID o'rniga UUID (Xavfsizlik uchun)
    - Yaratilgan vaqt
    - O'zgarish vaqti
    """
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="O'zgartirilgan vaqt")

    class Meta:
        abstract = True


class SoftDeleteModel(BaseModel):
    """
    Ma'lumotni o'chirmasdan 'yashirish' (Trash can) funksiyasi.
    ERP tizimda hech narsa butunlay o'chmasligi kerak.
    """
    is_deleted = models.BooleanField(default=False, verbose_name="O'chirilganmi?")
    deleted_at = models.DateTimeField(null=True, blank=True)

    def delete(self, using=None, keep_parents=False):
        # Haqiqiy o'chirish o'rniga, bayroqchani ko'tarib qo'yamiz
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        # Qayta tiklash
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    class Meta:
        abstract = True


class TenantAwareModel(SoftDeleteModel):
    """
    SaaS arxitekturasining yuragi.
    Ma'lumotni avtomatik ravishda tegishli O'quv Markazga bog'laydi.
    """
    # String reference ishlatamiz ('apps.organizations.Organization'),
    # chunki Organization hali yuklanmagan bo'lishi mumkin.
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name="%(class)s_related",
        verbose_name="Tashkilot",
        null=True, blank=True # SuperAdmin ma'lumotlari uchun bo'sh qolishi mumkin
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Agar tashkilot biriktirilmagan bo'lsa, uni avtomatik topamiz
        if not self.organization_id:
            org = get_current_organization()
            if org:
                self.organization = org
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    """
    Barcha o'zgarishlarni kuzatish uchun log.
    Kim, qachon, nimani o'zgartirdi - hammasini saqlaymiz.
    """
    ACTION_CHOICES = (
        ('CREATE', 'Yaratildi'),
        ('UPDATE', 'O\'zgartirildi'),
        ('DELETE', 'O\'chirildi'),
        ('LOGIN', 'Tizimga kirdi'),
        ('LOGOUT', 'Tizimdan chiqdi'),
    )

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='audit_logs'
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        verbose_name="Kim bajardi"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Amal")
    model_name = models.CharField(max_length=100, verbose_name="Model nomi")
    object_id = models.IntegerField(null=True, blank=True, verbose_name="Obyekt ID")
    object_repr = models.CharField(max_length=255, blank=True, verbose_name="Obyekt nomi")
    changes = models.JSONField(default=dict, blank=True, verbose_name="O'zgarishlar")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Manzil")
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="Brauzer")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Vaqt")

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Loglar"

    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name}"

    @classmethod
    def log(cls, user, action, model_name, object_id=None, object_repr='', changes=None, request=None):
        """
        Log yozish uchun helper method.
        """
        log_entry = cls(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr[:255] if object_repr else '',
            changes=changes or {},
        )
        
        if user and hasattr(user, 'organization'):
            log_entry.organization = user.organization
            
        if request and hasattr(request, 'organization') and request.organization:
            log_entry.organization = request.organization
            
        if request:
            log_entry.ip_address = cls.get_client_ip(request)
            log_entry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        log_entry.save()
        return log_entry

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class BackupConfiguration(BaseModel):
    SCHEDULE_TYPE_CHOICES = (
        ('manual', "Faqat qo'lda"),
        ('interval', 'Har N soatda'),
        ('daily', 'Har kuni aniq vaqtda'),
    )
    LAST_STATUS_CHOICES = (
        ('never', 'Hali ishga tushmagan'),
        ('success', 'Muvaffaqiyatli'),
        ('failed', 'Xatolik bilan tugagan'),
    )

    name = models.CharField(max_length=100, default='Asosiy backup sozlamasi', verbose_name='Nomi')
    is_enabled = models.BooleanField(default=False, verbose_name='Avtomatik backup yoqilgan')
    telegram_bot_token = models.CharField(max_length=255, blank=True, verbose_name='Telegram bot token')
    telegram_chat_id = models.CharField(max_length=64, blank=True, verbose_name='Telegram chat ID')
    auto_detect_chat = models.BooleanField(default=True, verbose_name='Chat ID ni avtomatik topish')
    schedule_type = models.CharField(
        max_length=20,
        choices=SCHEDULE_TYPE_CHOICES,
        default='manual',
        verbose_name='Backup rejimi',
    )
    interval_hours = models.PositiveIntegerField(default=24, verbose_name='Interval (soat)')
    daily_time = models.TimeField(null=True, blank=True, verbose_name='Kunlik backup vaqti')
    retention_days = models.PositiveIntegerField(default=30, verbose_name='Backup saqlash kunlari')
    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name='Oxirgi ishga tushgan vaqt')
    next_run_at = models.DateTimeField(null=True, blank=True, verbose_name='Keyingi backup vaqti')
    last_status = models.CharField(
        max_length=20,
        choices=LAST_STATUS_CHOICES,
        default='never',
        verbose_name='Oxirgi holat',
    )
    last_message = models.TextField(blank=True, verbose_name='Oxirgi xabar')
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backup_config_updates',
        verbose_name='Kim yangiladi',
    )

    class Meta:
        db_table = 'backup_configurations'
        verbose_name = 'Backup sozlamasi'
        verbose_name_plural = 'Backup sozlamalari'

    def __str__(self):
        return self.name


class BackupRunLog(BaseModel):
    STATUS_CHOICES = (
        ('success', 'Muvaffaqiyatli'),
        ('failed', 'Xatolik'),
    )
    TRIGGER_SOURCE_CHOICES = (
        ('manual', "Qo'lda"),
        ('schedule', 'Jadval bo`yicha'),
    )

    configuration = models.ForeignKey(
        BackupConfiguration,
        on_delete=models.CASCADE,
        related_name='run_logs',
        verbose_name='Sozlama',
    )
    triggered_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backup_runs',
        verbose_name='Kim ishga tushirdi',
    )
    trigger_source = models.CharField(
        max_length=20,
        choices=TRIGGER_SOURCE_CHOICES,
        default='manual',
        verbose_name='Ishga tushish turi',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='Holati')
    backup_file_name = models.CharField(max_length=255, blank=True, verbose_name='Backup fayl nomi')
    file_size_bytes = models.BigIntegerField(default=0, verbose_name='Fayl hajmi')
    sent_to_telegram = models.BooleanField(default=False, verbose_name='Telegramga yuborildimi')
    message = models.TextField(blank=True, verbose_name='Natija xabari')
    started_at = models.DateTimeField(default=timezone.now, verbose_name='Boshlangan vaqt')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Tugagan vaqt')

    class Meta:
        db_table = 'backup_run_logs'
        verbose_name = 'Backup log'
        verbose_name_plural = 'Backup loglari'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.get_status_display()} - {self.started_at:%Y-%m-%d %H:%M}"
