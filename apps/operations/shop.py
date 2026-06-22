"""
Internal Shop - Gamifikatsiya Do'koni.
O'quvchilar coin yig'ib, sovg'alar sotib olishi mumkin.
"""
from django.db import models
from apps.core.models import TenantAwareModel
from apps.users.models import User
from apps.finance.inventory import Supply


class ShopCategory(TenantAwareModel):
    """Do'kon kategoriyalari"""
    name = models.CharField(max_length=100, verbose_name="Kategoriya nomi")
    icon = models.CharField(max_length=50, default='🎁', verbose_name="Ikonka")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    
    class Meta:
        db_table = 'shop_categories'
        ordering = ['order', 'name']
        verbose_name = "Do'kon kategoriyasi"
        verbose_name_plural = "Do'kon kategoriyalari"

    def __str__(self):
        return f"{self.icon} {self.name}"


class ShopItem(TenantAwareModel):
    """
    Do'kondagi mahsulotlar.
    Sklad bilan bog'langan yoki virtual sovg'alar (vaucher, chegirma).
    """
    TYPE_CHOICES = (
        ('physical', 'Jismoniy mahsulot'),
        ('digital', 'Elektron mahsulot'),
        ('book_physical', 'Kitob (Qog\'oz)'),
        ('book_digital', 'Kitob (Elektron)'),
        ('voucher', 'Chegirma kuponi'),
        ('service', 'Xizmat'),
    )

    category = models.ForeignKey(ShopCategory, on_delete=models.SET_NULL, null=True,
                                 related_name='items', verbose_name="Kategoriya")
    name = models.CharField(max_length=200, verbose_name="Nomi")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    
    # Mahsulot turi
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='physical',
                                 verbose_name="Mahsulot turi")

    # Narxlar (Coin YOKI Pul bilan)
    coin_price = models.PositiveIntegerField(default=0, verbose_name="Coin narxi")
    cash_price = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     verbose_name="Pul narxi (so'm)")

    # Coin bilan yoki pul bilan sotib olish mumkinmi
    allow_coin_purchase = models.BooleanField(default=True, verbose_name="Coin bilan olish")
    allow_cash_purchase = models.BooleanField(default=True, verbose_name="Pul bilan olish")

    # Skladdan olinadimi?
    supply = models.ForeignKey(Supply, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='shop_items', verbose_name="Sklad mahsuloti")
    
    # Virtual mahsulot uchun (agar supply yo'q bo'lsa)
    stock = models.PositiveIntegerField(default=0, verbose_name="Mavjud soni")
    
    # Elektron mahsulot uchun (PDF, link)
    digital_file = models.FileField(upload_to='shop/digital/%Y/%m/', null=True, blank=True,
                                    verbose_name="Elektron fayl (PDF)")
    digital_link = models.URLField(blank=True, verbose_name="Tashqi havola")

    # Media
    image = models.ImageField(upload_to='shop/%Y/%m/', null=True, blank=True, verbose_name="Rasm")
    
    # Holat
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    is_featured = models.BooleanField(default=False, verbose_name="Tavsiya etilgan")
    
    class Meta:
        db_table = 'shop_items'
        ordering = ['-is_featured', 'category', 'name']
        verbose_name = "Do'kon mahsuloti"
        verbose_name_plural = "Do'kon mahsulotlari"

    def __str__(self):
        return f"{self.name} ({self.coin_price} 💰)"
    
    @property
    def available_stock(self):
        """Mavjud mahsulot sonini qaytaradi"""
        if self.supply:
            return self.supply.quantity
        return self.stock
    
    @property
    def is_in_stock(self):
        """Sotib olish mumkinmi?"""
        return self.available_stock > 0 and self.is_active


class Purchase(TenantAwareModel):
    """
    Xaridlar tarixi.
    O'quvchi coin yoki pul sarflab mahsulot sotib oladi.
    """
    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('paid', 'To\'langan (tasdiq kutilmoqda)'),
        ('delivered', 'Topshirildi'),
        ('cancelled', 'Bekor qilindi'),
    )
    
    PAYMENT_TYPE_CHOICES = (
        ('coin', 'Coin bilan'),
        ('cash', 'Pul bilan'),
    )

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases',
                                limit_choices_to={'role': 'student'}, verbose_name="O'quvchi")
    item = models.ForeignKey(ShopItem, on_delete=models.CASCADE, related_name='purchases',
                             verbose_name="Mahsulot")
    
    quantity = models.PositiveIntegerField(default=1, verbose_name="Soni")

    # To'lov turi
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default='coin',
                                    verbose_name="To'lov turi")
    coin_spent = models.PositiveIntegerField(default=0, verbose_name="Sarflangan coin")
    cash_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     verbose_name="To'langan summa")

    # Chek (pul bilan to'lovda)
    receipt_image = models.ImageField(upload_to='shop/receipts/%Y/%m/', null=True, blank=True,
                                      verbose_name="Chek rasmi")
    receipt_verified = models.BooleanField(default=False, verbose_name="Chek tasdiqlandi")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending',
                              verbose_name="Holati")
    
    # Topshirish
    delivered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='delivered_purchases', verbose_name="Topshirdi")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Topshirilgan vaqt")
    notes = models.TextField(blank=True, verbose_name="Izoh")
    
    class Meta:
        db_table = 'shop_purchases'
        ordering = ['-created_at']
        verbose_name = "Xarid"
        verbose_name_plural = "Xaridlar"

    def __str__(self):
        return f"{self.student.first_name} - {self.item.name}"
    
    def save(self, *args, **kwargs):
        if self._state.adding:  # Yangi xarid
            # Coin ni hisoblash (agar belgilanmagan bo'lsa)
            if not self.coin_spent:
                self.coin_spent = self.item.coin_price * self.quantity
            
            # O'quvchi balansidan coin yechish
            xp_data = self.student.profile_data.get('xp', 0)
            if xp_data >= self.coin_spent:
                self.student.profile_data['xp'] = xp_data - self.coin_spent
                self.student.save(update_fields=['profile_data'])
            
            # Skladdan yechish
            if self.item.supply:
                self.item.supply.quantity = max(0, self.item.supply.quantity - self.quantity)
                self.item.supply.save()
            else:
                self.item.stock = max(0, self.item.stock - self.quantity)
                self.item.save()
        
        super().save(*args, **kwargs)
