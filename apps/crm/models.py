from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.education.models import Course


class LeadSource(TenantAwareModel):
    """
    Mijoz qayerdan keldi? (Marketing analitikasi uchun).
    """
    name = models.CharField(max_length=100, verbose_name="Manba nomi")  # M: Instagram, Telegram
    utm_source = models.CharField(max_length=100, blank=True, verbose_name="UTM Kodo")  # M: ig_ads_summer

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'lead_sources'
        verbose_name = "Lid Manbasi"
        verbose_name_plural = "Lid Manbalari"


class Stage(TenantAwareModel):
    """
    Sotuv Voronkasi bosqichlari (Kanban ustunlari).
    Mijoz xohlagancha bosqich yaratishi mumkin.
    """
    name = models.CharField(max_length=100, verbose_name="Bosqich nomi")  # M: Yangi, Qo'ng'iroq qilindi
    order = models.PositiveIntegerField(default=1, verbose_name="Ketma-ketlik")  # 1, 2, 3...
    color = models.CharField(max_length=20, default="#3B82F6", verbose_name="Rangi (HEX)")

    is_won = models.BooleanField(default=False,
                                 verbose_name="Yutuq bosqichimi?")  # Agar shu bosqichga o'tsa, o'quvchiga aylanadi

    class Meta:
        db_table = 'crm_stages'
        ordering = ['order']
        verbose_name = "Voronka Bosqichi"
        verbose_name_plural = "Voronka Bosqichlari"

    def __str__(self):
        return self.name


class Lead(TenantAwareModel):
    """
    Potensial mijoz (Lid).
    """
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi", db_index=True)
    phone = models.CharField(max_length=20, verbose_name="Telefon", db_index=True)

    source = models.ForeignKey(LeadSource, on_delete=models.SET_NULL, null=True, verbose_name="Manba")
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name='leads', verbose_name="Bosqich")

    interested_course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, verbose_name="Qiziqqan kursi")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    limit_choices_to={'role__in': ['admin', 'owner', 'manager']},
                                    verbose_name="Mas'ul xodim")

    # Marketing ma'lumotlari (JSON)
    extra_data = models.JSONField(default=dict, blank=True, verbose_name="Qo'shimcha Info")

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    class Meta:
        db_table = 'leads'
        verbose_name = "Lid"
        verbose_name_plural = "Lidlar"
        indexes = [
            models.Index(fields=['organization', 'stage']),
            models.Index(fields=['created_at']),
        ]


class Activity(TenantAwareModel):
    """
    Lid bilan qilingan harakatlar tarixi (Log).
    Kim qachon telefon qildi, nima dedi?
    """
    TYPE_CHOICES = (
        ('call', 'Qo\'ng\'iroq'),
        ('sms', 'SMS'),
        ('meeting', 'Uchrashuv'),
        ('note', 'Izoh'),
        ('status_change', 'Status o\'zgardi'),
    )

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Bajardi")

    activity_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='note')
    comment = models.TextField(verbose_name="Izoh/Natija")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lead_activities'
        ordering = ['-created_at']
        verbose_name = "Harakat"
        verbose_name_plural = "Harakatlar"