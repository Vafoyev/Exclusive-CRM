"""
Resurslar (Inventory) uchun view'lar.
Sarf materiallar va aktivlarni boshqarish.
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, F

from apps.finance.inventory import Supply, SupplyCategory, SupplyTransaction, Asset, AssetCategory
from apps.core.audit import log_user_action

logger = logging.getLogger(__name__)


@login_required
def supply_list(request):
    """
    Sarf materiallar ro'yxati.
    Low stock alert bilan.
    """
    org = request.user.organization
    
    supplies = Supply.objects.filter(organization=org, is_deleted=False).select_related('category')
    
    # Low stock filter
    show_low_stock = request.GET.get('low_stock')
    if show_low_stock:
        supplies = supplies.filter(quantity__lte=F('min_quantity'))
    
    # Kategoriya filter
    category_id = request.GET.get('category')
    if category_id:
        supplies = supplies.filter(category_id=category_id)
    
    # Qidiruv
    search = request.GET.get('q')
    if search:
        supplies = supplies.filter(name__icontains=search)
    
    # Statistika
    total_items = supplies.count()
    low_stock_count = supplies.filter(quantity__lte=F('min_quantity')).count()
    total_value = supplies.aggregate(
        total=Sum(F('quantity') * F('unit_price'))
    )['total'] or 0
    
    categories = SupplyCategory.objects.filter(organization=org, is_deleted=False)
    
    # Kutilayotgan/Muddati o'tgan qarzlar
    from django.utils import timezone
    unpaid_debts = SupplyTransaction.objects.filter(
        organization=org,
        payment_method='qarz',
        is_debt_paid=False
    ).select_related('student', 'supply').order_by('due_date')
    
    today = timezone.now().date()
    
    # O'quvchilar ro'yxati (chiqim modalida tanlash uchun)
    from apps.users.models import User as UserModel
    students = UserModel.objects.filter(
        role='student', is_active=True
    ).order_by('first_name', 'last_name')
    if org:
        students = students.filter(organization=org)

    context = {
        'supplies': supplies,
        'categories': categories,
        'students': students,
        'unpaid_debts': unpaid_debts,
        'today': today,
        'total_items': total_items,
        'low_stock_count': low_stock_count,
        'total_value': total_value,
        'current_category': category_id,
        'current_search': search,
        'show_low_stock': show_low_stock,
    }
    
    return render(request, 'finance/supply_list.html', context)


@login_required
def supply_add_stock(request, supply_id):
    """Sklad: Material qo'shish (kirim)"""
    if request.user.role not in ['super_admin', 'owner']:
        messages.error(request, "Ruxsat yo'q! Faqat material chiqimi mumkin.")
        return redirect('finance:supply_list')
    
    org = request.user.organization
    supply = get_object_or_404(Supply, pk=supply_id, organization=org)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))
        notes = request.POST.get('notes', '')
        
        if quantity > 0:
            SupplyTransaction.objects.create(
                supply=supply,
                transaction_type='in',
                quantity=quantity,
                performed_by=request.user,
                notes=notes,
                organization=org,
            )
            log_user_action(request.user, 'CREATE', 'SupplyTransaction', 
                           None, f"{supply.name}: +{quantity}", request=request)
            messages.success(request, f"{quantity} {supply.unit} qo'shildi!")
        
    return redirect('finance:supply_list')


@login_required  
def supply_remove_stock(request, supply_id):
    """Sklad: Material yechish (chiqim) - o'quvchiga biriktirish yoki oddiy chiqim."""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')
    
    org = request.user.organization
    supply = get_object_or_404(Supply, pk=supply_id, organization=org)
    
    if request.method == 'POST':
        from decimal import Decimal
        from .models import Transaction, TransactionCategory, Account
        from .admin_cash_views import _get_or_create_admin_account
        from .services import confirm_transaction as confirm_service

        try:
            quantity = int(request.POST.get('quantity', 0))
            notes = request.POST.get('notes', '')
            action_type = request.POST.get('action_type', 'simple')  # 'simple' yoki 'student'
            student_id = request.POST.get('student_id')
            payment_method = request.POST.get('payment_method', 'cash')

            if quantity > 0 and quantity <= supply.quantity:
                student = None
                financial_tx = None
                due_date_val = None

                if action_type in ['student', 'student_debt']:
                    if not student_id:
                        messages.error(request, "Iltimos, o'quvchini tanlang!")
                        return redirect('finance:supply_list')
                        
                    # O'quvchiga biriktirish - moliyaviy tranzaksiya yaratish
                    from apps.users.models import User as UserModel
                    try:
                        student = UserModel.objects.get(pk=student_id, role='student')
                    except UserModel.DoesNotExist:
                        messages.error(request, "O'quvchi topilmadi!")
                        return redirect('finance:supply_list')

                    # Mahsulot narxini hisoblash
                    total_price = supply.unit_price * Decimal(str(quantity))

                    if total_price > 0:
                        if payment_method == 'qarz':
                            # Qarzga berilganda
                            due_date_str = request.POST.get('due_date')
                            if not due_date_str:
                                messages.error(request, "Qarzga berish uchun qaytarish sanasini kiriting!")
                                return redirect('finance:supply_list')
                            due_date_val = due_date_str
                            
                            # O'quvchining balansidan ayiramiz (qarzga botadi)
                            student.balance -= total_price
                            student.save(update_fields=['balance'])
                            notes = notes or f"{supply.name} x{quantity} → {student.get_full_name()} (Qarzga, {due_date_str})"
                        else:
                            # Admin kassasini olish
                            admin_account = _get_or_create_admin_account(request.user, org)

                            # Kirim tranzaksiyasi yaratish (mahsulot sotish)
                            cat, _ = TransactionCategory.objects.get_or_create(
                                organization=org,
                                name='Mahsulot sotish',
                                transaction_type='income',
                                defaults={'organization': org}
                            )

                            financial_tx = Transaction.objects.create(
                                organization=org,
                                account=admin_account,
                                category=cat,
                                student=student,
                                amount=total_price,
                                transaction_type='income',
                                payment_method=payment_method,
                                description=f"Mahsulot sotish: {supply.name} x{quantity} → {student.get_full_name()}",
                                status='pending',
                                created_by=request.user,
                            )

                            # Avtomatik tasdiqlash
                            try:
                                confirm_service(financial_tx.id, request.user)
                            except Exception as e:
                                messages.warning(request, f"Tranzaksiya yaratildi, lekin tasdiqlanmadi: {e}")

                            notes = notes or f"{supply.name} x{quantity} → {student.get_full_name()} ({payment_method})"

                # Ombordan chiqim
                supply_tx = SupplyTransaction.objects.create(
                    supply=supply,
                    transaction_type='out',
                    quantity=quantity,
                    performed_by=request.user,
                    notes=notes or f"{supply.name} dan {quantity} ta chiqim",
                    organization=org,
                    student=student,
                    payment_method=payment_method if student else None,
                    due_date=due_date_val if action_type in ['student', 'student_debt'] else None,
                    financial_transaction=financial_tx,
                )
                
                log_user_action(request.user, 'CREATE', 'SupplyTransaction', 
                               None, f"{supply.name}: -{quantity}", request=request)

                if student:
                    messages.success(request, 
                        f"✅ {quantity} {supply.unit} '{supply.name}' {student.get_full_name()} ga berildi. "
                        f"Kassa balansiga {supply.unit_price * Decimal(str(quantity)):,.0f} UZS kirim bo'ldi.")
                else:
                    messages.success(request, f"✅ {quantity} {supply.unit} '{supply.name}' ombordan yechildi!")
            elif quantity <= 0:
                messages.error(request, "Miqdor noto'g'ri! Kamida 1 bo'lishi kerak.")
            else:
                messages.error(request, f"Yetarli miqdor yo'q! Omborda faqat {supply.quantity} {supply.unit} bor.")
        except Exception as e:
            logger.exception("Ombor chiqimida xatolik yuz berdi")
            messages.error(request, f"❌ Xatolik yuz berdi: {e}")
        
    return redirect('finance:supply_list')


@login_required
def asset_list(request):
    """Aktivlar ro'yxati"""
    org = request.user.organization
    
    assets = Asset.objects.filter(organization=org, is_deleted=False).select_related('category', 'room', 'responsible_person')
    
    # Status filter
    status = request.GET.get('status')
    if status:
        assets = assets.filter(status=status)
    
    # Kategoriya filter  
    category_id = request.GET.get('category')
    if category_id:
        assets = assets.filter(category_id=category_id)
    
    # Statistika
    total_assets = assets.count()
    active_assets = assets.filter(status='active').count()
    total_value = assets.aggregate(total=Sum('purchase_price'))['total'] or 0
    
    categories = AssetCategory.objects.filter(organization=org, is_deleted=False)
    
    context = {
        'assets': assets,
        'categories': categories,
        'total_assets': total_assets,
        'active_assets': active_assets,
        'total_value': total_value,
        'current_status': status,
        'current_category': category_id,
    }
    
    return render(request, 'finance/asset_list.html', context)


# =============================================
# SUPPLY CRUD (Sklad materiallari)
# =============================================

@login_required
def supply_pay_debt(request, pk):
    """Qarzga berilgan material pulini to'lash (qarzni uzish)"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')
        
    org = request.user.organization
    tx = get_object_or_404(SupplyTransaction, pk=pk, organization=org, payment_method='qarz', is_debt_paid=False)
    
    if request.method == 'POST':
        from .models import Transaction, TransactionCategory, Account
        from .admin_cash_views import _get_or_create_admin_account
        from .services import confirm_transaction as confirm_service
        from decimal import Decimal
        
        payment_method = request.POST.get('payment_method', 'cash')
        
        # Admin kassasini olish
        admin_account = _get_or_create_admin_account(request.user, org)

        # Mahsulot narxini hisoblash
        total_price = tx.supply.unit_price * Decimal(str(tx.quantity))
        
        # O'quvchining balansini tiklaymiz (qarz to'landi)
        student = tx.student
        student.balance += total_price
        student.save(update_fields=['balance'])
        
        # Kassaga kirim qilamiz
        cat, _ = TransactionCategory.objects.get_or_create(
            organization=org,
            name='Qarzni qaytarish (Material)',
            transaction_type='income',
            defaults={'organization': org}
        )

        financial_tx = Transaction.objects.create(
            organization=org,
            account=admin_account,
            category=cat,
            student=student,
            amount=total_price,
            transaction_type='income',
            payment_method=payment_method,
            description=f"Qarz to'landi (M: {tx.supply.name} x{tx.quantity}): {student.get_full_name()}",
            status='pending',
            created_by=request.user,
        )

        # Avtomatik tasdiqlash
        try:
            confirm_service(financial_tx.id, request.user)
        except Exception as e:
            messages.warning(request, f"Tranzaksiya yaratildi, lekin tasdiqlanmadi: {e}")
            
        # Qarz to'landi deb belgilash
        tx.is_debt_paid = True
        tx.financial_transaction = financial_tx
        tx.save(update_fields=['is_debt_paid', 'financial_transaction'])
        
        messages.success(request, f"✅ Qarz to'landi: {total_price:,.0f} UZS kassaga kirim qilindi!")
        
    return redirect('finance:supply_list')


@login_required
def supply_detail(request, pk):
    """Bitta material tafsilotlari va uning barcha tranzaksiya tarixi"""
    org = request.user.organization
    supply = get_object_or_404(Supply, pk=pk, organization=org)
    
    # Materialga tegishli barch tranzaksiyalarni olish
    transactions = SupplyTransaction.objects.filter(supply=supply).select_related(
        'performed_by', 'student', 'financial_transaction'
    ).order_by('-created_at')

    # Umumiy sklad qiymati
    total_worth = supply.quantity * supply.unit_price

    context = {
        'supply': supply,
        'transactions': transactions,
        'total_worth': total_worth,
    }
    return render(request, 'finance/supply_detail.html', context)


@login_required
def supply_create(request):
    """Yangi material qo'shish"""
    if request.user.role not in ['super_admin', 'owner']:
        messages.error(request, "Ruxsat yo'q! Faqat super admin/owner material qo'sha oladi.")
        return redirect('finance:supply_list')

    org = request.user.organization
    categories = SupplyCategory.objects.filter(organization=org, is_deleted=False)

    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        unit = request.POST.get('unit', 'dona')
        quantity = int(request.POST.get('quantity', 0) or 0)
        min_quantity = int(request.POST.get('min_quantity', 5) or 5)
        unit_price = float(request.POST.get('unit_price', 0) or 0)
        description = request.POST.get('description', '')

        if name:
            supply = Supply.objects.create(
                organization=org,
                name=name,
                category_id=category_id if category_id else None,
                unit=unit,
                quantity=quantity,
                min_quantity=min_quantity,
                unit_price=unit_price,
                description=description
            )
            log_user_action(request.user, 'CREATE', 'Supply', supply.id,
                           f"Material yaratildi: {name}", request=request)
            messages.success(request, f"'{name}' muvaffaqiyatli qo'shildi!")
            return redirect('finance:supply_list')

    return render(request, 'finance/supply_form.html', {
        'title': 'Yangi material',
        'categories': categories
    })


@login_required
def supply_edit(request, pk):
    """Materialni tahrirlash"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')

    org = request.user.organization
    supply = get_object_or_404(Supply, pk=pk, organization=org)
    categories = SupplyCategory.objects.filter(organization=org, is_deleted=False)

    if request.method == 'POST':
        supply.name = request.POST.get('name', supply.name)
        category_id = request.POST.get('category')
        supply.category_id = category_id if category_id else None
        supply.unit = request.POST.get('unit', supply.unit)
        supply.quantity = int(request.POST.get('quantity', 0) or 0)
        supply.min_quantity = int(request.POST.get('min_quantity', 5) or 5)
        supply.unit_price = float(request.POST.get('unit_price', 0) or 0)
        supply.description = request.POST.get('description', '')
        supply.save()

        log_user_action(request.user, 'UPDATE', 'Supply', supply.id,
                       f"Material yangilandi: {supply.name}", request=request)
        messages.success(request, "Material yangilandi!")
        return redirect('finance:supply_list')

    return render(request, 'finance/supply_form.html', {
        'title': 'Materialni tahrirlash',
        'supply': supply,
        'categories': categories
    })


@login_required
def supply_delete(request, pk):
    """Materialni o'chirish"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')

    org = request.user.organization
    supply = get_object_or_404(Supply, pk=pk, organization=org)

    log_user_action(request.user, 'DELETE', 'Supply', supply.id,
                   f"Material o'chirildi: {supply.name}", request=request)
    supply.is_deleted = True
    supply.save()
    messages.warning(request, f"'{supply.name}' o'chirildi!")
    return redirect('finance:supply_list')


# =============================================
# SUPPLY CATEGORY CRUD
# =============================================

@login_required
def supply_category_list(request):
    """Sklad kategoriyalari"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')

    org = request.user.organization
    categories = SupplyCategory.objects.filter(organization=org, is_deleted=False)

    return render(request, 'finance/supply_category_list.html', {'categories': categories})


@login_required
def supply_category_create(request):
    """Yangi kategoriya"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')

    org = request.user.organization

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            SupplyCategory.objects.create(organization=org, name=name)
            messages.success(request, f"'{name}' kategoriyasi yaratildi!")
            return redirect('finance:supply_category_list')

    return render(request, 'finance/supply_category_form.html', {'title': 'Yangi kategoriya'})


@login_required
def supply_category_edit(request, pk):
    """Kategoriyani tahrirlash"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')

    org = request.user.organization
    category = get_object_or_404(SupplyCategory, pk=pk, organization=org)

    if request.method == 'POST':
        category.name = request.POST.get('name', category.name)
        category.save()
        messages.success(request, "Kategoriya yangilandi!")
        return redirect('finance:supply_category_list')

    return render(request, 'finance/supply_category_form.html', {
        'title': 'Kategoriyani tahrirlash',
        'category': category
    })


@login_required
def supply_category_delete(request, pk):
    """Kategoriyani o'chirish"""
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('finance:supply_list')

    org = request.user.organization
    category = get_object_or_404(SupplyCategory, pk=pk, organization=org)
    category.is_deleted = True
    category.save()
    messages.warning(request, f"'{category.name}' o'chirildi!")
    return redirect('finance:supply_category_list')

