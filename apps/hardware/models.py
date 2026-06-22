import secrets
from datetime import timezone as dt_timezone

from django.db import models

from apps.core.models import BaseModel, TenantAwareModel


def generate_device_token():
    return secrets.token_hex(24)


class FaceIDIntegration(BaseModel):
    organization = models.OneToOneField(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='face_id_integration',
    )
    agent_enabled = models.BooleanField(default=False, verbose_name="Agent yoqilgan")
    device_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_device_token,
        verbose_name="Qurilma tokeni",
    )
    last_event_received_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi event vaqti")

    class Meta:
        db_table = 'hardware_face_id_integrations'
        verbose_name = "Face ID integratsiya"
        verbose_name_plural = "Face ID integratsiyalar"

    def __str__(self):
        return f"{self.organization} Face ID"


class FaceIDUserBinding(TenantAwareModel):
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='face_id_binding',
        verbose_name="Foydalanuvchi",
    )
    face_id_code = models.CharField(max_length=64, verbose_name="Face ID kodi")
    sync_enabled = models.BooleanField(default=True, verbose_name="Sync yoqilgan")
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi sync")
    last_event_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi event")
    last_event_type = models.CharField(max_length=20, blank=True, verbose_name="Oxirgi event turi")
    last_device_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="Oxirgi qurilma IP")

    class Meta:
        db_table = 'hardware_face_id_bindings'
        verbose_name = "Face ID bog'lanish"
        verbose_name_plural = "Face ID bog'lanishlar"
        unique_together = ('organization', 'face_id_code')
        indexes = [
            models.Index(fields=['organization', 'sync_enabled']),
            models.Index(fields=['organization', 'face_id_code']),
        ]

    def __str__(self):
        return f"{self.user.full_name or self.user.phone} [{self.face_id_code}]"

    def save(self, *args, **kwargs):
        if self.user and self.user.organization_id:
            self.organization = self.user.organization
        super().save(*args, **kwargs)


class FaceIDEvent(TenantAwareModel):
    EVENT_CHOICES = (
        ('CHECK_IN', 'Keldi'),
        ('CHECK_OUT', 'Ketdi'),
    )

    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='face_id_events',
        verbose_name="Foydalanuvchi",
    )
    face_id_code = models.CharField(max_length=64, verbose_name="Face ID kodi")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, verbose_name="Event turi")
    occurred_at = models.DateTimeField(verbose_name="Qachon bo'lgan")
    device_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="Qurilma IP")
    raw_payload = models.JSONField(default=dict, blank=True, verbose_name="Xom payload")

    class Meta:
        db_table = 'hardware_face_id_events'
        verbose_name = "Face ID event"
        verbose_name_plural = "Face ID eventlar"
        ordering = ['-occurred_at']
        unique_together = ('organization', 'face_id_code', 'event_type', 'occurred_at')
        indexes = [
            models.Index(fields=['organization', 'occurred_at']),
            models.Index(fields=['organization', 'face_id_code', 'occurred_at']),
        ]

    def __str__(self):
        return f"{self.face_id_code} {self.event_type} {self.occurred_at.astimezone(dt_timezone.utc).isoformat()}"

