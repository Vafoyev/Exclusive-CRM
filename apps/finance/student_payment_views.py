"""
Student Payment Views - O'quvchi va Ota-ona uchun to'lov qilish.
Chek yuklash va admin tomonidan tasdiqlash.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum

from .models import Transaction, TransactionCategory, Account
from apps.users.models import User, ParentStudent
from apps.core.audit import log_user_action


@login_required
def student_payment_page(request):
    """
    O'quvchi yoki Ota-ona uchun to'lov sahifasi.
    O'z balansini ko'rish va to'lov qilish.
    """
    user = request.user
    org = request.organization

    # Agar ota-ona bo'lsa, farzandlarini olish
    if user.role == 'parent':
        children_relations = ParentStudent.objects.filter(parent=user).select_related('student')
        children = [rel.student for rel in children_relations]

        if not children:
            messages.error(request, "Sizga biriktirilgan o'quvchi topilmadi!")
            return redirect('dashboard')

        # Birinchi farzandni default qilish yoki tanlangan
        selected_student_id = request.GET.get('student')
        if selected_student_id:
            selected_student = get_object_or_404(User, pk=selected_student_id, role='student')
            # Tekshirish - bu farzandmi
            if selected_student not in children:
                messages.error(request, "Bu o'quvchi sizning farzandingiz emas!")
                return redirect('dashboard')
        else:
            selected_student = children[0]

    elif user.role == 'student':
        selected_student = user
        children = None
    else:
        messages.error(request, "Bu sahifa faqat o'quvchi va ota-onalar uchun!")
        return redirect('dashboard')

    # To'lov tarixi (base queryset)
    all_payments = Transaction.objects.filter(
        student=selected_student,
        transaction_type='income'
    ).order_by('-created_at')

    # Kutilayotgan to'lovlar (pending)
    pending_payments = all_payments.filter(status='pending')

    # Tasdiqlangan to'lovlar
    confirmed_payments = all_payments.filter(status='confirmed')

    # Statistika
    total_paid = confirmed_payments.aggregate(t=Sum('amount'))['t'] or 0

    # Oxirgi 20 ta to'lov (template uchun)
    payments = all_payments[:20]

    # To'lov kategoriyalari
    categories = TransactionCategory.objects.filter(
        organization=org,
        transaction_type='income',
        is_deleted=False
    )

    # Kassalar (faqat online/transfer)
    accounts = Account.objects.filter(
        organization=org,
        is_deleted=False,
        account_type__in=['wallet', 'bank', 'card']
    )

    context = {
        'student': selected_student,
        'children': children,
        'payments': payments,
        'pending_payments': pending_payments,
        'confirmed_payments': confirmed_payments,
        'total_paid': total_paid,
        'categories': categories,
        'accounts': accounts,
    }

    return render(request, 'finance/student_payment_page.html', context)


@login_required
def submit_payment(request):
    """
    O'quvchi/Ota-ona to'lov yuboradi (chek bilan).
    Admin tasdiqlagunga qadar 'pending' holatda bo'ladi.
    """
    if request.method != 'POST':
        return redirect('finance:student_payment_page')

    user = request.user
    org = request.organization

    # Form ma'lumotlari
    student_id = request.POST.get('student_id')
    amount = request.POST.get('amount')
    payment_method = request.POST.get('payment_method', 'transfer')
    payment_month = request.POST.get('payment_month', '')
    description = request.POST.get('description', '')
    receipt_image = request.FILES.get('receipt_image')

    # Validatsiya
    if not student_id or not amount:
        messages.error(request, "Summa va o'quvchini tanlang!")
        return redirect('finance:student_payment_page')

    try:
        amount = float(amount.replace(',', '').replace(' ', ''))
        if amount <= 0:
            raise ValueError()
    except:
        messages.error(request, "Noto'g'ri summa!")
        return redirect('finance:student_payment_page')

    # O'quvchini olish
    student = get_object_or_404(User, pk=student_id, role='student')

    # Agar ota-ona bo'lsa, o'z farzandimi tekshirish
    if user.role == 'parent':
        is_child = ParentStudent.objects.filter(parent=user, student=student).exists()
        if not is_child:
            messages.error(request, "Bu sizning farzandingiz emas!")
            return redirect('finance:student_payment_page')
    elif user.role == 'student' and user != student:
        messages.error(request, "Faqat o'zingiz uchun to'lov qilishingiz mumkin!")
        return redirect('finance:student_payment_page')

    # Kategoriya (O'quvchi to'lovi)
    category = TransactionCategory.objects.filter(
        organization=org,
        transaction_type='income',
        name__icontains="o'quvchi"
    ).first()

    if not category:
        category = TransactionCategory.objects.filter(
            organization=org,
            transaction_type='income'
        ).first()

    # Kassa (birinchi online/bank)
    account = Account.objects.filter(
        organization=org,
        is_deleted=False,
        account_type__in=['wallet', 'bank', 'card']
    ).first()

    if not account:
        account = Account.objects.filter(organization=org, is_deleted=False).first()

    if not account:
        messages.error(request, "Kassa topilmadi! Admin bilan bog'laning.")
        return redirect('finance:student_payment_page')

    # Oylik nomi
    month_names = {
        '1': 'Yanvar', '2': 'Fevral', '3': 'Mart', '4': 'Aprel',
        '5': 'May', '6': 'Iyun', '7': 'Iyul', '8': 'Avgust',
        '9': 'Sentabr', '10': 'Oktabr', '11': 'Noyabr', '12': 'Dekabr',
    }
    month_name = month_names.get(payment_month, '')
    if month_name and not description:
        description = f"{month_name} oyi uchun kurs to'lovi"
    elif month_name:
        description = f"{month_name} oyi: {description}"

    # Tranzaksiya yaratish
    transaction = Transaction.objects.create(
        organization=org,
        account=account,
        category=category,
        student=student,
        amount=amount,
        transaction_type='income',
        payment_method=payment_method,
        description=description or f"{user.first_name} tomonidan to'lov",
        receipt_image=receipt_image,
        status='pending',
        receipt_verified=False,
        created_by=user
    )

    log_user_action(user, 'CREATE', 'Transaction', transaction.id,
                   f"To'lov yuborildi: {amount:,.0f} so'm", request=request)

    messages.success(request, f"To'lov yuborildi! Summa: {amount:,.0f} so'm. Admin tasdiqlashini kuting.")
    return redirect('finance:student_payment_page')


@login_required
def my_payments(request):
    """
    O'quvchi yoki ota-ona o'z to'lovlari tarixini ko'radi.
    """
    user = request.user

    if user.role == 'student':
        students = [user]
    elif user.role == 'parent':
        children_relations = ParentStudent.objects.filter(parent=user).select_related('student')
        students = [rel.student for rel in children_relations]
    else:
        messages.error(request, "Bu sahifa faqat o'quvchi va ota-onalar uchun!")
        return redirect('dashboard')

    # Barcha to'lovlar
    payments = Transaction.objects.filter(
        student__in=students,
        transaction_type='income'
    ).select_related('student', 'account', 'category', 'confirmed_by').order_by('-created_at')

    context = {
        'payments': payments,
        'students': students,
    }

    return render(request, 'finance/my_payments.html', context)
