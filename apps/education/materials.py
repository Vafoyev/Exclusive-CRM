"""
Materials - LMS Ta'lim Materiallari.
Video, PDF, Audio va boshqa o'quv materiallarini boshqarish.
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.education.models import Group


class MaterialCategory(TenantAwareModel):
    """Material kategoriyalari"""
    name = models.CharField(max_length=100, verbose_name="Kategoriya nomi")
    icon = models.CharField(max_length=50, default='📁', verbose_name="Ikonka")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    
    class Meta:
        db_table = 'material_categories'
        ordering = ['order', 'name']
        verbose_name = "Material kategoriyasi"
        verbose_name_plural = "Material kategoriyalari"

    def __str__(self):
        return f"{self.icon} {self.name}"


class Material(TenantAwareModel):
    """
    O'quv materiallari.
    Video darslar, PDF kitoblar, Audio materiallar.
    """
    TYPE_CHOICES = (
        ('video', '🎬 Video'),
        ('pdf', '📄 PDF'),
        ('audio', '🎧 Audio'),
        ('doc', '📝 Hujjat'),
        ('link', '🔗 Havola'),
        ('other', '📦 Boshqa'),
    )
    
    category = models.ForeignKey(MaterialCategory, on_delete=models.SET_NULL, null=True,
                                 related_name='materials', verbose_name="Kategoriya")
    
    title = models.CharField(max_length=255, verbose_name="Sarlavha")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    material_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='pdf',
                                     verbose_name="Turi")
    
    # Fayl yoki havola
    file = models.FileField(upload_to='materials/%Y/%m/', null=True, blank=True,
                           verbose_name="Fayl")
    external_url = models.URLField(null=True, blank=True, verbose_name="Tashqi havola")
    
    # Thumbnail (video uchun)
    thumbnail = models.ImageField(upload_to='materials/thumbnails/', null=True, blank=True,
                                  verbose_name="Muqova rasmi")
    
    # Kirish huquqlari
    ACCESS_CHOICES = (
        ('all', 'Hamma uchun'),
        ('group', 'Faqat guruh a\'zolari'),
        ('private', 'Tanlangan o\'quvchilar'),
    )
    access_type = models.CharField(max_length=20, choices=ACCESS_CHOICES, default='all',
                                   verbose_name="Kirish huquqi")
    
    # Qaysi guruhlar uchun (agar access_type = 'group')
    groups = models.ManyToManyField(Group, blank=True, related_name='materials',
                                    verbose_name="Guruhlar")
    
    # Qaysi o'quvchilar uchun (agar access_type = 'private')
    allowed_students = models.ManyToManyField(User, blank=True, related_name='private_materials',
                                              limit_choices_to={'role': 'student'},
                                              verbose_name="Ruxsat berilgan o'quvchilar")
    
    # Yukladi
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='uploaded_materials', verbose_name="Yukladi")
    
    # Statistika
    view_count = models.PositiveIntegerField(default=0, verbose_name="Ko'rishlar soni")
    download_count = models.PositiveIntegerField(default=0, verbose_name="Yuklab olishlar")
    
    # Holat
    is_published = models.BooleanField(default=True, verbose_name="Chop etilgan")
    is_featured = models.BooleanField(default=False, verbose_name="Tavsiya etilgan")
    
    class Meta:
        db_table = 'materials'
        ordering = ['-created_at']
        verbose_name = "Material"
        verbose_name_plural = "Materiallar"

    def __str__(self):
        return f"{self.get_material_type_display()} {self.title}"
    
    @property
    def file_size(self):
        """Fayl hajmi (MB)"""
        if self.file and hasattr(self.file, 'size'):
            return round(self.file.size / (1024 * 1024), 2)
        return 0
    
    def can_access(self, user):
        """Foydalanuvchi ko'rishi mumkinmi?"""
        if user.role in ['super_admin', 'owner', 'admin', 'teacher']:
            return True
        
        if self.access_type == 'all':
            return True
        
        if self.access_type == 'group':
            return self.groups.filter(students=user).exists()
        
        if self.access_type == 'private':
            return self.allowed_students.filter(pk=user.pk).exists()
        
        return False


class MaterialView(TenantAwareModel):
    """Material ko'rishlar tarixi"""
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='material_views')
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    # Qancha vaqt ko'rdi (video uchun)
    watch_duration = models.PositiveIntegerField(default=0, verbose_name="Ko'rish davomiyligi (soniya)")
    
    class Meta:
        db_table = 'material_views'
        ordering = ['-viewed_at']
        verbose_name = "Material ko'rish"
        verbose_name_plural = "Material ko'rishlar"

    def __str__(self):
        return f"{self.user.first_name} - {self.material.title}"


class Syllabus(TenantAwareModel):
    """
    O'quv rejasi (Syllabus).
    Kurs yoki guruh uchun dars rejasi.
    """
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='syllabus',
                                  verbose_name="Guruh")
    title = models.CharField(max_length=255, verbose_name="Reja nomi")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    
    # PDF yoki fayl
    file = models.FileField(upload_to='syllabi/%Y/', null=True, blank=True,
                           verbose_name="Reja fayli")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='created_syllabi')
    
    class Meta:
        db_table = 'syllabi'
        verbose_name = "O'quv rejasi"
        verbose_name_plural = "O'quv rejalari"

    def __str__(self):
        return f"{self.group.name} - {self.title}"


class SyllabusItem(TenantAwareModel):
    """O'quv rejasi bandlari"""
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='items')
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    
    title = models.CharField(max_length=255, verbose_name="Mavzu")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, default=1,
                                         verbose_name="Davomiylik (soat)")
    
    # Bog'liq materiallar
    materials = models.ManyToManyField(Material, blank=True, related_name='syllabus_items',
                                       verbose_name="Materiallar")
    
    is_completed = models.BooleanField(default=False, verbose_name="Yakunlandi")
    completed_at = models.DateField(null=True, blank=True, verbose_name="Yakunlangan sana")
    
    class Meta:
        db_table = 'syllabus_items'
        ordering = ['syllabus', 'order']
        verbose_name = "O'quv rejasi bandi"
        verbose_name_plural = "O'quv rejasi bandlari"

    def __str__(self):
        return f"{self.order}. {self.title}"
