from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User

# LMS imports at bottom to avoid circular imports


class Room(TenantAwareModel):
    """
    O'quv markazidagi xonalar.
    """
    name = models.CharField(max_length=50, verbose_name="Xona nomi")
    capacity = models.PositiveIntegerField(default=10, verbose_name="Sig'imi")
    has_projector = models.BooleanField(default=False, verbose_name="Proyektor bormi?")

    def __str__(self):
        return f"{self.name} ({self.capacity} kishilik)"

    class Meta:
        db_table = 'rooms'
        verbose_name = "Xona"
        verbose_name_plural = "Xonalar"


class Course(TenantAwareModel):
    """
    Kurs shablonlari (Yo'nalishlar).
    """
    name = models.CharField(max_length=100, verbose_name="Kurs nomi")
    description = models.TextField(blank=True, verbose_name="Ta'rif")

    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Narxi (Oylik)")
    duration_months = models.PositiveIntegerField(default=3, verbose_name="Davomiyligi (oy)")

    is_active = models.BooleanField(default=True, verbose_name="Aktivmi?")

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'courses'
        verbose_name = "Kurs"
        verbose_name_plural = "Kurslar"


class Group(TenantAwareModel):
    """
    Haqiqiy o'quv guruhi.
    """
    STATUS_CHOICES = (
        ('pending', 'Yig\'ilmoqda'),
        ('active', 'Dars ketmoqda'),
        ('finished', 'Tugatilgan'),
        ('cancelled', 'Bekor qilingan'),
    )

    name = models.CharField(max_length=100, verbose_name="Guruh nomi")  # M: IELTS-A
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='groups', verbose_name="Kurs")

    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'role': 'teacher'},
        related_name='teaching_groups',
        verbose_name="O'qituvchi"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Holati")

    start_date = models.DateField(null=True, blank=True, verbose_name="Boshlanish sanasi")
    end_date = models.DateField(null=True, blank=True, verbose_name="Tugash sanasi")

    # JADVAL SOZLAMALARI
    # Dars kunlari (Masalan: [1, 3, 5] - Dush/Chor/Juma)
    schedule_days = models.JSONField(default=list, verbose_name="Dars kunlari (1=Dush...7=Yak)")

    start_time = models.TimeField(null=True, blank=True, verbose_name="Boshlanish vaqti")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Tugash vaqti")

    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, related_name='groups', verbose_name="Xona")

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'groups'
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"


class GroupStudent(TenantAwareModel):
    """
    O'quvchi va Guruh o'rtasidagi bog'liqlik.
    """
    STATUS_CHOICES = (
        ('active', 'O\'qiyapti'),
        ('frozen', 'Muzlatilgan'),
        ('left', 'Chiqib ketgan'),
    )

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='students')
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enrolled_groups',
        limit_choices_to={'role': 'student'},
        verbose_name="O'quvchi"
    )

    joined_at = models.DateField(auto_now_add=True, verbose_name="Qo'shilgan sana")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")

    contract_file = models.FileField(upload_to='contracts/', null=True, blank=True, verbose_name="Shartnoma")

    class Meta:
        db_table = 'group_students'
        unique_together = ('group', 'student')
        verbose_name = "Guruh a'zosi"
        verbose_name_plural = "Guruh a'zolari"
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['group', 'status']),
        ]


# LMS Materials - added at bottom to avoid circular imports
from apps.education.materials import MaterialCategory, Material, MaterialView, Syllabus, SyllabusItem
