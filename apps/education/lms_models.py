"""
LMS - O'quv Materiallari modellari.
Video, PDF, prezentatsiya va boshqa fayllarni saqlash va ulashish.
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User


class MaterialCategory(TenantAwareModel):
    """Material kategoriyalari (Video, PDF, Presentation, etc.)"""
    name = models.CharField(max_length=100, verbose_name="Kategoriya nomi")
    icon = models.CharField(max_length=50, default='ph-file', verbose_name="Ikonka")
    color = models.CharField(max_length=20, default='blue', verbose_name="Rang")
    
    class Meta:
        db_table = 'material_categories'
        verbose_name = "Material kategoriyasi"
        verbose_name_plural = "Material kategoriyalari"
    
    def __str__(self):
        return self.name


class CourseMaterial(TenantAwareModel):
    """
    Kurs materiallari.
    Video darslar, PDF kitoblar, prezentatsiyalar.
    """
    TYPE_CHOICES = (
        ('video', 'Video'),
        ('pdf', 'PDF'),
        ('document', 'Hujjat'),
        ('presentation', 'Prezentatsiya'),
        ('audio', 'Audio'),
        ('link', 'Havola'),
        ('other', 'Boshqa'),
    )
    
    course = models.ForeignKey(
        'education.Course', 
        on_delete=models.CASCADE, 
        related_name='materials',
        verbose_name="Kurs"
    )
    
    # Asosiy ma'lumotlar
    title = models.CharField(max_length=200, verbose_name="Sarlavha")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    material_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='document', verbose_name="Turi")
    
    # Fayl yoki havola
    file = models.FileField(upload_to='materials/%Y/%m/', null=True, blank=True, verbose_name="Fayl")
    external_url = models.URLField(blank=True, verbose_name="Tashqi havola")
    
    # Tartib va kirish
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")
    is_public = models.BooleanField(default=False, verbose_name="Hammaga ochiqmi?")
    is_featured = models.BooleanField(default=False, verbose_name="Tavsiya qilingan")
    
    # Fayl ma'lumotlari
    file_size = models.PositiveIntegerField(default=0, verbose_name="Fayl hajmi (bytes)")
    duration_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="Davomiyligi (soniya)")
    
    # Statlar
    view_count = models.PositiveIntegerField(default=0, verbose_name="Ko'rildi")
    download_count = models.PositiveIntegerField(default=0, verbose_name="Yuklab olindi")
    
    # Audit
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_materials')
    
    class Meta:
        db_table = 'course_materials'
        ordering = ['order', 'created_at']
        verbose_name = "Kurs materiali"
        verbose_name_plural = "Kurs materiallari"
    
    def __str__(self):
        return f"{self.course.name} - {self.title}"
    
    @property
    def file_size_display(self):
        """Fayl hajmini o'qish uchun qulay formatda qaytarish"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
    
    @property
    def duration_display(self):
        """Video davomiyligini o'qish uchun qulay formatda"""
        if not self.duration_seconds:
            return None
        mins, secs = divmod(self.duration_seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"


class MaterialProgress(TenantAwareModel):
    """O'quvchi material o'qish progressi"""
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='material_progress',
        limit_choices_to={'role': 'student'}
    )
    material = models.ForeignKey(CourseMaterial, on_delete=models.CASCADE, related_name='progress')
    
    # Progress
    is_completed = models.BooleanField(default=False, verbose_name="Tugallandimi?")
    progress_percent = models.PositiveIntegerField(default=0, verbose_name="Progress (%)")
    last_position = models.PositiveIntegerField(default=0, verbose_name="Oxirgi pozitsiya (sekund)")
    
    # Vaqt
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'material_progress'
        unique_together = ('student', 'material')
        verbose_name = "Material progressi"
        verbose_name_plural = "Material progresslari"
    
    def __str__(self):
        return f"{self.student.first_name} - {self.material.title}: {self.progress_percent}%"
