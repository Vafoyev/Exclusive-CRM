"""
Omborxona (Inventory) modellari.
Aktivlar va sarf materiallarini boshqarish.
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User


class AssetCategory(TenantAwareModel):
    """Aktiv kategoriyalari (Mebel, Texnika, Kanchelyariya)"""
    name = models.CharField(max_length=100, verbose_name="Kategoriya nomi")
    icon = models.CharField(max_length=50, default='ph-cube', verbose_name="Ikonka")
    
    class Meta:
        db_table = 'asset_categories'
        verbose_name = "Aktiv kategoriyasi"
        verbose_name_plural = "Aktiv kategoriyalari"

    def __str__(self):
        return self.name


class Asset(TenantAwareModel):
    """
    Aktivlar (uzoq muddatli mulklar).
    Masalan: Parta, stul, kompyuter, proyektor.
    """
    STATUS_CHOICES = (
        ('active', 'Faol'),
        ('repair', 'Ta\'mirda'),
        ('broken', 'Buzuq'),
        ('disposed', 'Yo\'q qilingan'),
    )
    
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, related_name='assets')
    name = models.CharField(max_length=200, verbose_name="Nomi")
    inventory_number = models.CharField(max_length=50, unique=True, verbose_name="Inventar raqami")
    
    # Joylashuvi
    room = models.ForeignKey('education.Room', on_delete=models.SET_NULL, null=True, blank=True, 
                            related_name='assets', verbose_name="Xona")
    
    # Qiymati
    purchase_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Sotib olish narxi")
    purchase_date = models.DateField(null=True, blank=True, verbose_name="Sotib olingan sana")
    
    # Holat
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Holat")
    condition_notes = models.TextField(blank=True, verbose_name="Holat izohi")
    
    # Mas'ul
    responsible_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='responsible_assets', verbose_name="Mas'ul shaxs")
    
    class Meta:
        db_table = 'assets'
        ordering = ['category', 'name']
        verbose_name = "Aktiv"
        verbose_name_plural = "Aktivlar"

    def __str__(self):
        return f"{self.name} ({self.inventory_number})"


class SupplyCategory(TenantAwareModel):
    """Sarf material kategoriyalari"""
    name = models.CharField(max_length=100, verbose_name="Kategoriya nomi")
    
    class Meta:
        db_table = 'supply_categories'
        verbose_name = "Sarf material kategoriyasi"
        verbose_name_plural = "Sarf material kategoriyalari"

    def __str__(self):
        return self.name


class Supply(TenantAwareModel):
    """
    Sarf materiallar.
    Masalan: Marker, qog'oz, suv, choy.
    """
    category = models.ForeignKey(SupplyCategory, on_delete=models.SET_NULL, null=True, related_name='supplies')
    name = models.CharField(max_length=200, verbose_name="Nomi")
    unit = models.CharField(max_length=20, default='dona', verbose_name="O'lchov birligi")
    description = models.TextField(blank=True, default='', verbose_name="Tavsif")

    # Miqdor
    quantity = models.PositiveIntegerField(default=0, verbose_name="Joriy miqdor")
    min_quantity = models.PositiveIntegerField(default=5, verbose_name="Minimal miqdor")
    
    # Narx
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Birlik narxi")
    
    class Meta:
        db_table = 'supplies'
        ordering = ['category', 'name']
        verbose_name = "Sarf material"
        verbose_name_plural = "Sarf materiallar"

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def is_low_stock(self):
        """Tugab qolmoqdami?"""
        return self.quantity <= self.min_quantity

    @property
    def total_value(self):
        """Umumiy qiymati"""
        return self.quantity * self.unit_price


class SupplyTransaction(TenantAwareModel):
    """Sarf material harakatlari (Kirim/Chiqim)"""
    TYPE_CHOICES = (
        ('in', 'Kirim'),
        ('out', 'Chiqim'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Naqd pul'),
        ('card', 'Plastik karta'),
        ('terminal', 'Terminal'),
        ('qarz', 'Qarzga'),
    )
    
    supply = models.ForeignKey(Supply, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="Turi")
    quantity = models.PositiveIntegerField(verbose_name="Miqdor")
    
    # O'quvchiga biriktirish (sotuv/berish)
    student = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'role': 'student'},
        related_name='supply_received', verbose_name="O'quvchi"
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES,
        null=True, blank=True, verbose_name="To'lov usuli"
    )
    # Moliyaviy tranzaksiyaga bog'lash
    financial_transaction = models.ForeignKey(
        'finance.Transaction', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='supply_transactions', verbose_name="Moliyaviy tranzaksiya"
    )
    
    # Audit
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='supply_transactions')
    notes = models.CharField(max_length=255, blank=True, verbose_name="Izoh")
    
    # Qarzga sotish (Credit Sales)
    due_date = models.DateField(null=True, blank=True, verbose_name="Qaytarish sanasi")
    is_debt_paid = models.BooleanField(default=False, verbose_name="Qarz to'landimi?")
    
    class Meta:
        db_table = 'supply_transactions'
        ordering = ['-created_at']
        verbose_name = "Sarf material harakati"
        verbose_name_plural = "Sarf material harakatlari"

    def save(self, *args, **kwargs):
        # Avtomatik miqdorni yangilash
        if self._state.adding:  # Yangi yozuv
            if self.transaction_type == 'in':
                self.supply.quantity += self.quantity
            else:
                self.supply.quantity = max(0, self.supply.quantity - self.quantity)
            self.supply.save()
        super().save(*args, **kwargs)
