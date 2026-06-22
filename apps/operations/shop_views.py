"""
Shop views - Do'kon va Xaridlar.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum

from apps.operations.shop import ShopCategory, ShopItem, Purchase
from apps.users.models import User
from apps.core.audit import log_user_action


@login_required
def shop_list(request):
    """
    Do'kon sahifasi - O'quvchilar uchun.
    Barcha faol mahsulotlarni ko'rsatadi.
    """
    org = request.organization
    
    # Kategoriyalar bilan mahsulotlar
    categories = ShopCategory.objects.filter(organization=org, is_deleted=False)
    items = ShopItem.objects.filter(
        organization=org, 
        is_deleted=False, 
        is_active=True
    ).select_related('category', 'supply')
    
    # Featured items
    featured = items.filter(is_featured=True)[:4]
    
    # O'quvchi coin balansi
    user_coins = request.user.profile_data.get('xp', 0)
    
    context = {
        'categories': categories,
        'items': items,
        'featured': featured,
        'user_coins': user_coins,
    }
    
    return render(request, 'operations/shop.html', context)


@login_required
def purchase_item(request, item_id):
    """
    Mahsulot sotib olish.
    O'quvchi balansidan coin yechiladi, skladdan mahsulot kamayadi.
    """
    org = request.organization
    item = get_object_or_404(ShopItem, pk=item_id, organization=org, is_active=True)
    
    # Faqat studentlar sotib olishi mumkin
    if request.user.role != 'student':
        messages.error(request, "Faqat o'quvchilar sotib olishi mumkin!")
        return redirect('operations:shop')
    
    # Coin tekshirish
    user_coins = request.user.profile_data.get('xp', 0)
    if user_coins < item.coin_price:
        messages.error(request, f"Yetarli coin yo'q! Sizda: {user_coins} 💰, Kerak: {item.coin_price} 💰")
        return redirect('operations:shop')
    
    # Stock tekshirish
    if not item.is_in_stock:
        messages.error(request, "Bu mahsulot tugagan!")
        return redirect('operations:shop')
    
    # Xarid yaratish
    purchase = Purchase.objects.create(
        organization=org,
        student=request.user,
        item=item,
        quantity=1,
        coin_spent=item.coin_price,
        status='pending'
    )
    
    log_user_action(request.user, 'CREATE', 'Purchase', purchase.id, 
                   f"Do'kondan sotib oldi: {item.name}", request=request)
    
    messages.success(request, f"✅ {item.name} muvaffaqiyatli sotib olindi! Admindan olib keting.")
    return redirect('operations:shop')


@login_required  
def purchase_history(request):
    """
    O'quvchining xaridlar tarixi.
    """
    org = request.organization
    
    if request.user.role == 'student':
        purchases = Purchase.objects.filter(
            organization=org,
            student=request.user,
            is_deleted=False
        ).select_related('item')
    else:
        # Admin / Teacher barcha xaridlarni ko'radi
        purchases = Purchase.objects.filter(
            organization=org,
            is_deleted=False
        ).select_related('item', 'student')
    
    # Statistika
    total_spent = purchases.filter(status__in=['pending', 'delivered']).aggregate(
        total=Sum('coin_spent')
    )['total'] or 0
    
    context = {
        'purchases': purchases[:50],
        'total_spent': total_spent,
    }
    
    return render(request, 'operations/purchase_history.html', context)


# ===========================================
# ADMIN VIEWS
# ===========================================

@login_required
def shop_admin(request):
    """
    Admin uchun do'kon boshqaruvi.
    """
    org = request.organization
    
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')
    
    items = ShopItem.objects.filter(organization=org, is_deleted=False).select_related('category', 'supply')
    categories = ShopCategory.objects.filter(organization=org, is_deleted=False)
    
    # Kutilayotgan xaridlar
    pending_purchases = Purchase.objects.filter(
        organization=org,
        status='pending',
        is_deleted=False
    ).select_related('student', 'item')
    
    context = {
        'items': items,
        'categories': categories,
        'pending_purchases': pending_purchases,
        'pending_count': pending_purchases.count(),
    }
    
    return render(request, 'operations/shop_admin.html', context)


@login_required
def deliver_purchase(request, pk):
    """
    Xaridni topshirish (Admin).
    """
    org = request.organization
    purchase = get_object_or_404(Purchase, pk=pk, organization=org)
    
    if purchase.status == 'pending':
        purchase.status = 'delivered'
        purchase.delivered_by = request.user
        purchase.delivered_at = timezone.now()
        purchase.save()
        
        log_user_action(request.user, 'UPDATE', 'Purchase', purchase.id, 
                       f"Topshirildi: {purchase.item.name}", request=request)
        messages.success(request, f"✅ {purchase.item.name} topshirildi!")
    
    return redirect('operations:shop_admin')


@login_required
def cancel_purchase(request, pk):
    """
    Xaridni bekor qilish va coinni qaytarish.
    """
    org = request.organization
    purchase = get_object_or_404(Purchase, pk=pk, organization=org)
    
    if purchase.status == 'pending':
        # Coinni qaytarish (agar coin bilan to'langan bo'lsa)
        if purchase.payment_type == 'coin' and purchase.coin_spent > 0:
            xp_data = purchase.student.profile_data.get('xp', 0)
            purchase.student.profile_data['xp'] = xp_data + purchase.coin_spent
            purchase.student.save(update_fields=['profile_data'])

        # Stockni qaytarish
        if purchase.item.supply:
            purchase.item.supply.quantity += purchase.quantity
            purchase.item.supply.save()
        else:
            purchase.item.stock += purchase.quantity
            purchase.item.save()
        
        purchase.status = 'cancelled'
        purchase.save()
        
        log_user_action(request.user, 'UPDATE', 'Purchase', purchase.id, 
                       f"Bekor qilindi: {purchase.item.name}", request=request)
        messages.warning(request, f"Xarid bekor qilindi.")

    return redirect('operations:shop_admin')


# =============================================
# ADMIN - KATEGORIYA CRUD
# =============================================

@login_required
def category_list(request):
    """Kategoriyalar ro'yxati (Admin)"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization
    categories = ShopCategory.objects.filter(organization=org, is_deleted=False).order_by('order')

    return render(request, 'operations/shop_category_list.html', {'categories': categories})


@login_required
def category_create(request):
    """Yangi kategoriya qo'shish"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization

    if request.method == 'POST':
        name = request.POST.get('name')
        icon = request.POST.get('icon', '📦')
        order = request.POST.get('order', 0)

        if name:
            ShopCategory.objects.create(
                organization=org,
                name=name,
                icon=icon,
                order=int(order) if order else 0
            )
            messages.success(request, f"✅ '{name}' kategoriyasi yaratildi!")
            return redirect('operations:shop_category_list')

    return render(request, 'operations/shop_category_form.html', {'title': 'Yangi kategoriya'})


@login_required
def category_edit(request, pk):
    """Kategoriyani tahrirlash"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization
    category = get_object_or_404(ShopCategory, pk=pk, organization=org)

    if request.method == 'POST':
        category.name = request.POST.get('name', category.name)
        category.icon = request.POST.get('icon', category.icon)
        category.order = int(request.POST.get('order', 0))
        category.save()
        messages.success(request, "Kategoriya yangilandi!")
        return redirect('operations:shop_category_list')

    return render(request, 'operations/shop_category_form.html', {
        'title': 'Kategoriyani tahrirlash',
        'category': category
    })


@login_required
def category_delete(request, pk):
    """Kategoriyani o'chirish"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization
    category = get_object_or_404(ShopCategory, pk=pk, organization=org)
    category.is_deleted = True
    category.save()
    messages.warning(request, f"'{category.name}' o'chirildi!")
    return redirect('operations:shop_category_list')


# =============================================
# ADMIN - MAHSULOT CRUD
# =============================================

@login_required
def item_list(request):
    """Mahsulotlar ro'yxati (Admin)"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization
    items = ShopItem.objects.filter(organization=org, is_deleted=False).select_related('category')
    categories = ShopCategory.objects.filter(organization=org, is_deleted=False)

    # Filter
    cat_filter = request.GET.get('category')
    if cat_filter:
        items = items.filter(category_id=cat_filter)

    return render(request, 'operations/shop_item_list.html', {
        'items': items,
        'categories': categories,
        'cat_filter': cat_filter
    })


@login_required
def item_create(request):
    """Yangi mahsulot qo'shish"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization
    categories = ShopCategory.objects.filter(organization=org, is_deleted=False)

    if request.method == 'POST':
        item = ShopItem(organization=org)
        item.name = request.POST.get('name')
        item.description = request.POST.get('description', '')
        item.item_type = request.POST.get('item_type', 'physical')
        item.coin_price = int(request.POST.get('coin_price', 0) or 0)
        item.cash_price = float(request.POST.get('cash_price', 0) or 0)
        item.allow_coin_purchase = request.POST.get('allow_coin_purchase') == 'on'
        item.allow_cash_purchase = request.POST.get('allow_cash_purchase') == 'on'
        item.stock = int(request.POST.get('stock', 0) or 0)
        item.is_active = request.POST.get('is_active') == 'on'
        item.is_featured = request.POST.get('is_featured') == 'on'

        cat_id = request.POST.get('category')
        if cat_id:
            item.category_id = int(cat_id)

        if request.FILES.get('image'):
            item.image = request.FILES['image']

        if request.FILES.get('digital_file'):
            item.digital_file = request.FILES['digital_file']

        item.digital_link = request.POST.get('digital_link', '')

        item.save()

        log_user_action(request.user, 'CREATE', 'ShopItem', item.id,
                       f"Mahsulot yaratildi: {item.name}", request=request)
        messages.success(request, f"✅ '{item.name}' mahsuloti yaratildi!")
        return redirect('operations:shop_item_list')

    return render(request, 'operations/shop_item_form.html', {
        'title': 'Yangi mahsulot',
        'categories': categories,
        'item_types': ShopItem.TYPE_CHOICES
    })


@login_required
def item_edit(request, pk):
    """Mahsulotni tahrirlash"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization
    item = get_object_or_404(ShopItem, pk=pk, organization=org)
    categories = ShopCategory.objects.filter(organization=org, is_deleted=False)

    if request.method == 'POST':
        item.name = request.POST.get('name', item.name)
        item.description = request.POST.get('description', '')
        item.item_type = request.POST.get('item_type', item.item_type)
        item.coin_price = int(request.POST.get('coin_price', 0) or 0)
        item.cash_price = float(request.POST.get('cash_price', 0) or 0)
        item.allow_coin_purchase = request.POST.get('allow_coin_purchase') == 'on'
        item.allow_cash_purchase = request.POST.get('allow_cash_purchase') == 'on'
        item.stock = int(request.POST.get('stock', 0) or 0)
        item.is_active = request.POST.get('is_active') == 'on'
        item.is_featured = request.POST.get('is_featured') == 'on'

        cat_id = request.POST.get('category')
        if cat_id:
            item.category_id = int(cat_id)

        if request.FILES.get('image'):
            item.image = request.FILES['image']

        if request.FILES.get('digital_file'):
            item.digital_file = request.FILES['digital_file']

        item.digital_link = request.POST.get('digital_link', '')

        item.save()

        log_user_action(request.user, 'UPDATE', 'ShopItem', item.id,
                       f"Mahsulot yangilandi: {item.name}", request=request)
        messages.success(request, "Mahsulot yangilandi!")
        return redirect('operations:shop_item_list')

    return render(request, 'operations/shop_item_form.html', {
        'title': 'Mahsulotni tahrirlash',
        'item': item,
        'categories': categories,
        'item_types': ShopItem.TYPE_CHOICES
    })


@login_required
def item_delete(request, pk):
    """Mahsulotni o'chirish"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop')

    org = request.organization
    item = get_object_or_404(ShopItem, pk=pk, organization=org)
    item.is_deleted = True
    item.save()
    messages.warning(request, f"'{item.name}' o'chirildi!")
    return redirect('operations:shop_item_list')


# =============================================
# XARID - PUL BILAN
# =============================================

@login_required
def purchase_with_cash(request, item_id):
    """Pul bilan sotib olish (chek yuklash)"""
    org = request.organization
    item = get_object_or_404(ShopItem, pk=item_id, organization=org, is_active=True)

    if not item.allow_cash_purchase or item.cash_price <= 0:
        messages.error(request, "Bu mahsulotni pul bilan sotib olish mumkin emas!")
        return redirect('operations:shop')

    if request.method == 'POST':
        receipt = request.FILES.get('receipt_image')

        if not receipt:
            messages.error(request, "Chek rasmini yuklang!")
            return redirect('operations:shop')

        # Xarid yaratish
        purchase = Purchase.objects.create(
            organization=org,
            student=request.user,
            item=item,
            quantity=1,
            payment_type='cash',
            cash_spent=item.cash_price,
            receipt_image=receipt,
            status='paid'  # Tasdiq kutilmoqda
        )

        # Stockni kamaytirish (sklad)
        if item.supply:
            item.supply.quantity = max(0, item.supply.quantity - 1)
            item.supply.save()
        else:
            item.stock = max(0, item.stock - 1)
            item.save()

        log_user_action(request.user, 'CREATE', 'Purchase', purchase.id,
                       f"Pul bilan sotib oldi: {item.name}", request=request)

        messages.success(request, f"✅ Xarid yuborildi! Admin tasdiqlashini kuting.")
        return redirect('operations:purchase_history')

    return render(request, 'operations/purchase_cash_form.html', {'item': item})


@login_required
def verify_purchase(request, pk):
    """Admin - Pul bilan xaridni tasdiqlash"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('operations:shop_admin')

    org = request.organization
    purchase = get_object_or_404(Purchase, pk=pk, organization=org)

    if purchase.status == 'paid' and purchase.payment_type == 'cash':
        purchase.receipt_verified = True
        purchase.status = 'delivered'
        purchase.delivered_by = request.user
        purchase.delivered_at = timezone.now()
        purchase.save()

        messages.success(request, f"✅ Xarid tasdiqlandi va topshirildi!")

    return redirect('operations:shop_admin')
