"""
LMS (Learning Management System) modellari.
Elektron kutubxona - kitoblar, videolar, resurslar.
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.education.models import Course, Group


class ResourceCategory(TenantAwareModel):
    """Resurs kategoriyalari"""
    name = models.CharField(max_length=100, verbose_name="Kategoriya nomi")
    icon = models.CharField(max_length=50, default='ph-folder', verbose_name="Ikonka")
    
    class Meta:
        db_table = 'lms_categories'
        verbose_name = "Resurs kategoriyasi"
        verbose_name_plural = "Resurs kategoriyalari"

    def __str__(self):
        return self.name


class Resource(TenantAwareModel):
    """
    O'quv resurslari.
    Kitob, video, audio, hujjat.
    """
    TYPE_CHOICES = (
        ('pdf', 'PDF Hujjat'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('link', 'Havola'),
        ('document', 'Boshqa hujjat'),
    )
    
    ACCESS_CHOICES = (
        ('public', 'Hammaga ochiq'),
        ('course', 'Faqat kursga'),
        ('group', 'Faqat guruhga'),
        ('paid', 'Pullik'),
    )
    
    category = models.ForeignKey(ResourceCategory, on_delete=models.SET_NULL, null=True, related_name='resources')
    
    title = models.CharField(max_length=255, verbose_name="Sarlavha")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='pdf', verbose_name="Turi")
    
    # Fayl yoki havola
    file = models.FileField(upload_to='resources/%Y/%m/', null=True, blank=True, verbose_name="Fayl")
    external_url = models.URLField(blank=True, verbose_name="Tashqi havola")
    thumbnail = models.ImageField(upload_to='resources/thumbnails/', null=True, blank=True, verbose_name="Rasm")
    
    # Kirish huquqi
    access_type = models.CharField(max_length=20, choices=ACCESS_CHOICES, default='course', verbose_name="Kirish turi")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, 
                              related_name='resources', verbose_name="Kurs")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='resources', verbose_name="Guruh")
    
    # Meta
    file_size = models.PositiveIntegerField(default=0, verbose_name="Fayl hajmi (KB)")
    duration_minutes = models.PositiveIntegerField(default=0, verbose_name="Davomiyligi (daqiqa)")
    
    # Statistika
    view_count = models.PositiveIntegerField(default=0, verbose_name="Ko'rishlar soni")
    download_count = models.PositiveIntegerField(default=0, verbose_name="Yuklab olishlar")
    
    # O'qituvchi yukladi
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_resources')
    
    class Meta:
        db_table = 'lms_resources'
        ordering = ['-created_at']
        verbose_name = "Resurs"
        verbose_name_plural = "Resurslar"

    def __str__(self):
        return self.title

    def can_access(self, user):
        """Foydalanuvchi resurga kira oladimi?"""
        if self.access_type == 'public':
            return True
        
        if user.role in ['super_admin', 'owner', 'admin']:
            return True
        
        if self.access_type == 'course' and self.course:
            # O'quvchi shu kursga yozilganmi?
            from apps.education.models import GroupEnrollment
            return GroupEnrollment.objects.filter(
                student=user,
                group__course=self.course,
                status='active'
            ).exists()
        
        if self.access_type == 'group' and self.group:
            from apps.education.models import GroupEnrollment
            return GroupEnrollment.objects.filter(
                student=user,
                group=self.group,
                status='active'
            ).exists()
        
        # Pullik resurslar uchun alohida tekshiruv kerak
        if self.access_type == 'paid':
            return ResourceAccess.objects.filter(
                student=user,
                resource=self,
                is_active=True
            ).exists()
        
        return False


class ResourceAccess(TenantAwareModel):
    """Resursga individual kirish huquqi (pullik resurslar uchun)"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resource_accesses')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='accesses')
    
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Muddati tugaydi")
    
    # To'lov
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        db_table = 'lms_resource_access'
        verbose_name = "Resurs kirish huquqi"
        verbose_name_plural = "Resurs kirish huquqlari"
        unique_together = ('student', 'resource')


class ResourceView(TenantAwareModel):
    """Resurs ko'rishlar tarixi"""
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resource_views')
    
    # Progress (video uchun)
    progress_percent = models.PositiveIntegerField(default=0, verbose_name="Progress (%)")
    last_position = models.PositiveIntegerField(default=0, verbose_name="Oxirgi pozitsiya (soniya)")
    completed = models.BooleanField(default=False, verbose_name="Tugallandi")
    
    class Meta:
        db_table = 'lms_resource_views'
        ordering = ['-updated_at']
        verbose_name = "Resurs ko'rish"
        verbose_name_plural = "Resurs ko'rishlar"

    def __str__(self):
        return f"{self.user.full_name} - {self.resource.title}"
