from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User

class NotificationTemplate(TenantAwareModel):
    """
    SMS va Telegram xabarlar shabloni.
    """
    TYPE_CHOICES = (
        ('sms', 'SMS'),
        ('telegram', 'Telegram'),
        ('system', 'Tizim Xabari'),
    )

    title = models.CharField(max_length=100, verbose_name="Shablon nomi")
    body = models.TextField(verbose_name="Xabar matni")
    # M: "Hurmatli {name}, siz darsga kelmadingiz."
    
    code = models.CharField(max_length=50, unique=True, verbose_name="Kod (Foydalanish uchun)")
    # M: "attendance_absent", "payment_received"

    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system')

    def __str__(self):
        return f"{self.title} ({self.code})"

    class Meta:
        db_table = 'notification_templates'
        verbose_name = "Xabar Shabloni"
        verbose_name_plural = "Xabar Shablonlari"


class NotificationLog(TenantAwareModel):
    """
    Yuborilgan xabarlar tarixi.
    """
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Qabul qiluvchi")
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(verbose_name="Yuborilgan xabar")
    message_type = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='sent', choices=(
        ('sent', 'Yuborildi'),
        ('failed', 'Xatolik'),
        ('read', 'O\'qildi')
    ))
    
    def __str__(self):
        return f"{self.recipient} - {self.message[:30]}"
    
    class Meta:
        db_table = 'notification_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'created_at']),
            models.Index(fields=['recipient', 'status', 'created_at']),
        ]
