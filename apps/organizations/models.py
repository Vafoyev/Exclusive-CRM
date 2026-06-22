from django.db import models
from apps.core.models import BaseModel, SoftDeleteModel


class Organization(SoftDeleteModel):
    """
    Har bir O'quv Markazi - bu bitta Organization.
    """
    name = models.CharField(max_length=255, verbose_name="Markaz nomi")
    subdomain = models.CharField(max_length=50, unique=True, verbose_name="Subdomain")
    # Misol: 'najot' -> najot.smartedu.uz

    # Egasi (User modeli hali yuklanmagani uchun string bilan beramiz)
    owner = models.OneToOneField(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_organization',
        verbose_name="Markaz Egasi (Direktor)"
    )

    # Global Sozlamalar (Elastiklik)
    config = models.JSONField(default=dict, blank=True, verbose_name="Tizim Sozlamalari")
    # Misol: {"currency": "UZS", "sms_provider": "eskiz", "working_days": [1,2,3,4,5,6]}

    is_active = models.BooleanField(default=True, verbose_name="Aktivmi?")

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'organizations'
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"


class Branch(SoftDeleteModel):
    """
    Filiallar (Masalan: Chilonzor filiali, Yunusobod filiali).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255, verbose_name="Filial nomi")
    address = models.TextField(blank=True, verbose_name="Manzil")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")

    # Filialga xos sozlamalar
    settings = models.JSONField(default=dict, blank=True, verbose_name="Filial Sozlamalari")
    # Misol: {"late_penalty": 5000, "check_in_start": "08:00"}

    is_main = models.BooleanField(default=False, verbose_name="Bosh filialmi?")

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    class Meta:
        db_table = 'branches'
        verbose_name = "Filial"
        verbose_name_plural = "Filiallar"