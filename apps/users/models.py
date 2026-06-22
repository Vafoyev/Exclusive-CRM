from django.db import models
from django.contrib.auth.models import AbstractUser
from django.templatetags.static import static
from apps.core.models import TenantAwareModel
from .managers import CustomUserManager


class User(AbstractUser, TenantAwareModel):
    """
    Global User Modeli.
    Hamma (Direktor, O'qituvchi, O'quvchi) shu jadvalda.
    """
    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),  # Platforma egasi
        ('owner', 'Direktor'),  # Markaz egasi
        ('admin', 'Administrator'),  # Filial boshqaruvchisi
        ('teacher', 'O\'qituvchi'),
        ('student', 'O\'quvchi'),
        ('parent', 'Ota-ona'),
        ('staff', 'Xodim'),  # Boshqa xodimlar
    )

    # 1. LOGINITSIYA
    username = None  # Usernameni o'chiramiz
    phone = models.CharField(max_length=20, unique=True, verbose_name="Telefon raqam")
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True, verbose_name="Telegram ID")

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    # 2. TIZIMDAGI O'RNI
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', verbose_name="Roli")
    branch = models.ForeignKey('organizations.Branch', on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name="Filial")

    # 3. SHAXSIY MA'LUMOTLAR
    middle_name = models.CharField(max_length=50, blank=True, verbose_name="Otasining ismi")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    avatar = models.ImageField(upload_to='avatars/%Y/%m/', blank=True, null=True, verbose_name="Rasm")

    # 4. HR (Xodimlar uchun)
    nfc_card_id = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name="NFC ID (Turniket)")

    # 5. ELASTIKLIK (Qo'shimcha ma'lumotlar)
    profile_data = models.JSONField(default=dict, blank=True, verbose_name="Qo'shimcha Info")
    # Misol: {"passport": "AA...", "shirt_size": "XL", "instagram": "@..."}

    # 6. RUXSATLAR (Xodimlar uchun bo'limlar va huquqlar)
    permissions = models.JSONField(default=dict, blank=True, verbose_name="Ruxsatlar")
    # Misol: {"users": {"view": true, "create": false}, "finance": {"view": true, "create": true}}

    # 7. MOLIYA (O'quvchilar uchun)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Hisob (Balans)")
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Tasdiqlangan Bonus summasi")
    bonus_percentage = models.PositiveIntegerField(default=0, verbose_name="Bonus foizi (%)")

    # 8. Organization Override (TenantAwareModeldan keladi, lekin SuperAdmin uchun bo'sh bo'lishi mumkin)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}"
        return f"{full_name.strip()} ({self.phone})" if full_name.strip() else self.phone

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self):
        initials = f"{(self.first_name or '')[:1]}{(self.last_name or '')[:1]}".strip().upper()
        if initials:
            return initials
        if self.phone:
            return self.phone[:1]
        return "?"

    @property
    def avatar_url(self):
        if self.avatar and getattr(self.avatar, 'url', None):
            return self.avatar.url
        return static('img/default-avatar.svg')

    def has_module_permission(self, module: str, action: str = 'view') -> bool:
        """
        Foydalanuvchi berilgan modulga ruxsati borligini tekshirish.

        Args:
            module: Modul nomi (users, finance, education, crm, operations)
            action: Amal turi (view, create, edit, delete)

        Returns:
            True/False
        """
        # Super admin va owner hammasiga ruxsat
        if self.role in ['super_admin', 'owner']:
            return True

        # Admin ko'pgiga ruxsat
        if self.role == 'admin':
            return True

        # Permissions dan tekshirish
        if not self.permissions:
            return False

        module_perms = self.permissions.get(module, {})
        return module_perms.get(action, False)

    def get_allowed_modules(self) -> list:
        """
        Foydalanuvchi kirishi mumkin bo'lgan modullar ro'yxati.
        """
        if self.role in ['super_admin', 'owner', 'admin']:
            return ['dashboard', 'users', 'education', 'finance', 'crm', 'operations', 'reports', 'settings']

        allowed = ['dashboard']  # Hammaga dashboard

        if self.permissions:
            for module, perms in self.permissions.items():
                if perms.get('view', False):
                    allowed.append(module)

        return allowed

    class Meta:
        db_table = 'users'
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        permissions = [
            # Users module - granular actions
            ('can_export_users_excel', "Foydalanuvchilar ro'yxatini Excel eksport qilish"),
            ('can_export_users_pdf', "Foydalanuvchilar ro'yxatini PDF eksport qilish"),
            # Finance module - granular actions
            ('can_view_salary', "Xodim oyligini ko'rish"),
            ('can_export_finance_excel', "Moliya hisobotini Excel eksport qilish"),
            # CRM module - granular actions
            ('can_export_crm_excel', "CRM ma'lumotlarini Excel eksport qilish"),
            # Reports module - granular actions
            ('can_export_reports_excel', "Hisobotlarni Excel eksport qilish"),
            ('can_export_reports_pdf', "Hisobotlarni PDF eksport qilish"),
        ]
        indexes = [
            models.Index(fields=['organization', 'role']),
            models.Index(fields=['organization', 'branch']),
            models.Index(fields=['phone']),
            models.Index(fields=['telegram_id']),
        ]


class ParentStudent(TenantAwareModel):
    """
    Ota-ona va O'quvchi o'rtasidagi bog'liqlik.
    """
    RELATION_TYPES = (
        ('father', 'Otasi'),
        ('mother', 'Onasi'),
        ('guardian', 'Vasiysi'),
        ('relative', 'Qarindoshi'),
    )

    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='children_relations',
                               limit_choices_to={'role': 'parent'})
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parent_relations',
                                limit_choices_to={'role': 'student'})
    relation_type = models.CharField(max_length=20, choices=RELATION_TYPES, default='mother',
                                     verbose_name="Qarindoshligi")

    is_main_contact = models.BooleanField(default=False, verbose_name="Asosiy aloqa uchunmi?")

    class Meta:
        db_table = 'parent_student_relations'
        unique_together = ('parent', 'student')
        verbose_name = "Ota-ona bog'liqligi"
        verbose_name_plural = "Ota-ona bog'liqliklari"
