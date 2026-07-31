from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db import transaction
from django.http import Http404, JsonResponse
from .models import User, ParentStudent
from .forms import UserForm, StudentForm, TeacherForm, StaffForm
from apps.core.permissions import permission_required, check_permission
from apps.hardware.services import build_student_presence_map


@login_required
@permission_required('users', 'view')
def user_list(request, role=None):
    """Foydalanuvchilar ro'yxati"""
    users = User.objects.filter(is_deleted=False).select_related('organization', 'branch').order_by('-date_joined')

    if request.user.role != 'super_admin' and request.user.organization:
        users = users.filter(organization=request.user.organization)

    # Role from URL kwargs or GET parameter
    if not role:
        role = request.GET.get('role')
    if role:
        users = users.filter(role=role)

    filter_type = request.GET.get('filter')
    if filter_type == 'debtors':
        users = users.filter(role='student', balance__lt=0)

    search = request.GET.get('q')
    if search:
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search)
        )

    base_qs = User.objects.filter(is_deleted=False)
    if request.user.role != 'super_admin' and request.user.organization:
        base_qs = base_qs.filter(organization=request.user.organization)

    user_stats = base_qs.aggregate(
        total_students=Count('id', filter=Q(role='student', is_active=True)),
        debtors_count=Count('id', filter=Q(role='student', balance__lt=0)),
        total_debt=Sum('balance', filter=Q(role='student', balance__lt=0)),
    )
    total_students = user_stats['total_students'] or 0
    debtors_count = user_stats['debtors_count'] or 0
    total_debt = abs(user_stats['total_debt'] or 0)

    paginator = Paginator(users, 25)
    page = request.GET.get('page', 1)
    users_page = paginator.get_page(page)

    context = {
        'users': users_page,
        'total_students': total_students,
        'debtors_count': debtors_count,
        'total_debt': total_debt,
        'current_role': role,
        'current_filter': filter_type,
        'current_search': search,
        'role_choices': User.ROLE_CHOICES,
    }
    return render(request, 'users/user_list.html', context)


@login_required
@permission_required('users', 'create')
def user_create(request):
    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)

            # Tashkilotni biriktirish
            if not user.organization and request.user.organization:
                user.organization = request.user.organization

            user.save()
            messages.success(request, f"{user.first_name} muvaffaqiyatli qo'shildi!")
            return redirect('users:user_list')
    else:
        form = UserForm()
    return render(request, 'users/user_form.html', {'form': form, 'title': "Yangi foydalanuvchi"})


@login_required
def admin_set_student_bonus(request):
    """
    Super Admin tomonidan o'quvchiga oylik to'lovdan chegirma/bonus belgilash.
    """
    if request.user.role != 'super_admin':
        messages.error(request, "Bu amal uchun sizda huquq yo'q (Faqat Super Admin).")
        return redirect('users:user_list')
        
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        bonus_amount_str = request.POST.get('bonus_amount', '0')
        bonus_percentage_str = request.POST.get('bonus_percentage', '0')
        
        try:
            student = User.objects.get(id=student_id, role='student', is_deleted=False)
            
            bonus_amount = float(bonus_amount_str)
            bonus_percentage = int(bonus_percentage_str)
            
            # Chegaralarni tekshirish
            if bonus_percentage > 100 or bonus_percentage < 0:
                messages.error(request, "Bonus foizi 0 va 100 orasida bo'lishi kerak!")
                return redirect('users:user_list')
                
            student.bonus_amount = bonus_amount
            student.bonus_percentage = bonus_percentage
            student.save(update_fields=['bonus_amount', 'bonus_percentage'])
            
            messages.success(request, f"{student.first_name} {student.last_name} uchun bonus saqlandi!")
            
        except User.DoesNotExist:
            messages.error(request, "O'quvchi topilmadi.")
        except ValueError:
            messages.error(request, "Noto'g'ri raqam kiritildi.")
            
    return redirect('users:user_list')


# ============================================
# OTA-ONA QIDIRISH (AJAX)
# ============================================
@login_required
def parent_search(request):
    """AJAX orqali ota-onalarni qidirish"""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    if not request.user.organization:
        return JsonResponse({'results': []})

    parents = User.objects.filter(
        role='parent',
        is_deleted=False,
        organization=request.user.organization,
    ).filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(phone__icontains=q)
    )

    results = [
        {
            'id': p.id,
            'first_name': p.first_name,
            'last_name': p.last_name,
            'phone': p.phone,
            'full_name': f"{p.first_name} {p.last_name} ({p.phone})",
        }
        for p in parents[:10]
    ]
    return JsonResponse({'results': results})


# ============================================
# O'QUVCHI QO'SHISH (Majburiy Ota-Ona bilan)
# ============================================
@login_required
@permission_required('users', 'create')
@transaction.atomic
def student_create(request):
    """O'quvchi qo'shish - bir yoki bir nechta ota-ona ma'lumotlari"""
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            # 1. Ota-ona ma'lumotlarini POST dan yig'ish
            parents_data = []
            idx = 0
            while True:
                phone = request.POST.get(f'parent_phone_{idx}', '').strip()
                if not phone:
                    break
                existing_id = request.POST.get(f'existing_parent_id_{idx}', '').strip()
                parents_data.append({
                    'existing_id': existing_id if existing_id else None,
                    'first_name': request.POST.get(f'parent_first_name_{idx}', '').strip(),
                    'last_name': request.POST.get(f'parent_last_name_{idx}', '').strip(),
                    'phone': phone,
                    'relation_type': request.POST.get(f'relation_type_{idx}', 'mother'),
                })
                idx += 1

            # Kamida bitta ota-ona bo'lishi kerak
            if not parents_data:
                form.add_error(None, "Kamida bitta ota-ona ma'lumotlari kiritilishi kerak!")
                return render(request, 'users/student_form.html', {
                    'form': form,
                    'title': "Yangi O'quvchi Qo'shish",
                    'relation_types': ParentStudent.RELATION_TYPES,
                })

            # 2. O'quvchini saqlash
            student = form.save(commit=False, organization=request.user.organization)
            student.save()

            # 3. Har bir ota-onani yaratish yoki topish va bog'lash
            parent_names = []
            for i, pd in enumerate(parents_data):
                if pd['existing_id']:
                    # Mavjud ota-onani tanlash
                    try:
                        parent = User.objects.get(
                            id=pd['existing_id'],
                            role='parent',
                            is_deleted=False,
                        )
                    except User.DoesNotExist:
                        continue
                else:
                    # Yangi ota-ona yaratish yoki telefon bo'yicha topish
                    parent, created = User.objects.get_or_create(
                        phone=pd['phone'],
                        defaults={
                            'first_name': pd['first_name'],
                            'last_name': pd['last_name'],
                            'role': 'parent',
                            'organization': request.user.organization,
                            'is_active': True,
                        }
                    )
                    if created:
                        parent.set_password(pd['phone'][-4:])
                        parent.save()

                # Bog'liqlik yaratish
                ParentStudent.objects.get_or_create(
                    parent=parent,
                    student=student,
                    defaults={
                        'relation_type': pd['relation_type'],
                        'is_main_contact': (i == 0),
                        'organization': request.user.organization,
                    }
                )
                parent_names.append(parent.full_name)

            names_str = ", ".join(parent_names)
            messages.success(request, f"✅ {student.full_name} muvaffaqiyatli qo'shildi! Ota-ona: {names_str}")
            return redirect('users:user_list')
    else:
        form = StudentForm()

    return render(request, 'users/student_form.html', {
        'form': form,
        'title': "Yangi O'quvchi Qo'shish",
        'relation_types': ParentStudent.RELATION_TYPES,
    })


# ============================================
# O'QITUVCHI QO'SHISH (NFC Card bilan)
# ============================================
@login_required
@permission_required('users', 'create')
def teacher_create(request):
    """O'qituvchi qo'shish - NFC karta va to'liq ma'lumotlar"""
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES)
        if form.is_valid():
            teacher = form.save(commit=False, organization=request.user.organization)
            teacher.save()
            
            messages.success(request, f"✅ O'qituvchi {teacher.full_name} muvaffaqiyatli qo'shildi!")
            return redirect('users:user_list')
    else:
        form = TeacherForm()
    
    return render(request, 'users/teacher_form.html', {
        'form': form, 
        'title': "Yangi O'qituvchi Qo'shish"
    })


# ============================================
# XODIM QO'SHISH (Rol va Ruxsatlar bilan)
# ============================================
@login_required
@permission_required('users', 'create')
def staff_create(request):
    """Xodim qo'shish - ruxsatlar bilan"""

    from apps.users.forms import AVAILABLE_ACTIONS, MODULE_EXTRA_ACTIONS

    if request.method == 'POST':
        form = StaffForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            # Ruxsatlarni yig'ish (faqat creator ega bo'lgan ruxsatlar)
            permissions = {}
            filtered_modules = form.get_filtered_modules()

            for module_code, module_name, icon in filtered_modules:
                module_perms = {}
                # Standard CRUD amallar
                for action_code, action_name in AVAILABLE_ACTIONS:
                    if form.creator_has_permission(module_code, action_code):
                        field_name = f"perm_{module_code}_{action_code}"
                        module_perms[action_code] = field_name in request.POST

                # Qo'shimcha granular amallar
                for action_code, action_name in MODULE_EXTRA_ACTIONS.get(module_code, []):
                    if form.creator_has_permission(module_code, action_code):
                        field_name = f"perm_{module_code}_{action_code}"
                        module_perms[action_code] = field_name in request.POST

                permissions[module_code] = module_perms

            staff = form.save(
                commit=False,
                organization=request.user.organization,
                permissions=permissions
            )
            staff.save()
            
            messages.success(request, f"✅ Xodim {staff.full_name} muvaffaqiyatli qo'shildi!")
            return redirect('users:user_list')
    else:
        form = StaffForm(user=request.user)
    
    return render(request, 'users/staff_form.html', {
        'form': form, 
        'title': "Yangi Xodim Qo'shish",
        'modules': form.get_filtered_modules(),
        'actions': AVAILABLE_ACTIONS,
        'extra_actions': form.get_filtered_extra_actions(),
    })


@login_required
@permission_required('users', 'view')
def user_detail(request, pk):
    """Foydalanuvchi to'liq ma'lumotlari"""
    user = get_object_or_404(User, pk=pk, is_deleted=False)

    # Tashkilot tekshiruvi
    if request.user.role != 'super_admin' and request.user.organization:
        if user.organization != request.user.organization:
            raise Http404

    # Ota-ona ma'lumotlari (o'quvchi uchun)
    parent_relations = []
    student_presence = None
    if user.role == 'student':
        parent_relations = ParentStudent.objects.filter(
            student=user
        ).select_related('parent')
        student_presence = build_student_presence_map([user.id]).get(user.id)

    # Farzandlar (ota-ona uchun)
    children_relations = []
    if user.role == 'parent':
        children_relations = ParentStudent.objects.filter(
            parent=user
        ).select_related('student')

    context = {
        'detail_user': user,
        'parent_relations': parent_relations,
        'children_relations': children_relations,
        'student_presence': student_presence,
    }
    return render(request, 'users/user_detail.html', context)


@login_required
@permission_required('users', 'edit')
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)

    # Tashkilot tekshiruvi — admin boshqa tashkilot userini tahrirlay olmaydi
    if request.user.role != 'super_admin' and request.user.organization:
        if user.organization and user.organization != request.user.organization:
            raise Http404

    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Ma'lumotlar yangilandi.")
            return redirect('users:user_list')
    else:
        form = UserForm(instance=user)
    return render(request, 'users/user_form.html', {'form': form, 'title': "Tahrirlash"})


@login_required
@permission_required('users', 'delete')
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)

    # Tashkilot tekshiruvi
    if request.user.role != 'super_admin' and request.user.organization:
        if user.organization and user.organization != request.user.organization:
            raise Http404

    if request.method == 'POST':
        user.delete()
        messages.warning(request, "Foydalanuvchi o'chirildi.")
        return redirect('users:user_list')
    return render(request, 'users/user_confirm_delete.html', {'user': user})


