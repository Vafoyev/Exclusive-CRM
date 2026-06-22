"""
Materials views - LMS Materiallar.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from apps.education.materials import MaterialCategory, Material, MaterialView
from apps.education.models import Group
from apps.core.audit import log_user_action


@login_required
def material_list(request):
    """
    Materiallar ro'yxati.
    Kirish huquqiga qarab filtrlanadi.
    """
    org = request.organization
    user = request.user
    
    # Kategoriyalar
    categories = MaterialCategory.objects.filter(organization=org, is_deleted=False)
    
    # Filtr
    category_id = request.GET.get('category', '')
    material_type = request.GET.get('type', '')
    search = request.GET.get('q', '')
    
    materials = Material.objects.filter(
        organization=org,
        is_deleted=False,
        is_published=True
    ).select_related('category', 'uploaded_by')
    
    # Kirish huquqi filtri (studentlar uchun)
    if user.role == 'student':
        # O'quvchi qaysi guruhlarda?
        student_groups = Group.objects.filter(students__student=user)
        
        materials = materials.filter(
            Q(access_type='all') |
            Q(access_type='group', groups__in=student_groups) |
            Q(access_type='private', allowed_students=user)
        ).distinct()
    
    # Filter qo'llash
    if category_id:
        materials = materials.filter(category_id=category_id)
    if material_type:
        materials = materials.filter(material_type=material_type)
    if search:
        materials = materials.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    
    # Featured
    featured = materials.filter(is_featured=True)[:4]
    
    context = {
        'materials': materials[:50],
        'categories': categories,
        'featured': featured,
        'category_id': category_id,
        'material_type': material_type,
        'search': search,
    }
    
    return render(request, 'education/materials.html', context)


@login_required
def material_view(request, pk):
    """
    Materialni ko'rish va yuklab olish.
    Ko'rish statistikasi saqlanadi.
    """
    org = request.organization
    material = get_object_or_404(Material, pk=pk, organization=org)
    
    # Kirish huquqini tekshirish
    if not material.can_access(request.user):
        messages.error(request, "Bu materialga kirish huquqingiz yo'q!")
        return redirect('material_list')
    
    # Ko'rishni qayd qilish
    MaterialView.objects.create(
        organization=org,
        material=material,
        user=request.user
    )
    material.view_count += 1
    material.save(update_fields=['view_count'])
    
    context = {
        'material': material,
    }
    
    return render(request, 'education/material_detail.html', context)


@login_required
def material_download(request, pk):
    """
    Materialni yuklab olish.
    """
    from django.http import FileResponse
    
    org = request.organization
    material = get_object_or_404(Material, pk=pk, organization=org)
    
    # Kirish huquqini tekshirish
    if not material.can_access(request.user):
        messages.error(request, "Bu materialga kirish huquqingiz yo'q!")
        return redirect('material_list')
    
    if not material.file:
        messages.error(request, "Fayl topilmadi!")
        return redirect('material_list')
    
    # Yuklab olishni qayd qilish
    material.download_count += 1
    material.save(update_fields=['download_count'])
    
    return FileResponse(material.file.open(), as_attachment=True, filename=material.file.name.split('/')[-1])


# ===========================================
# ADMIN / TEACHER VIEWS
# ===========================================

@login_required
def material_upload(request):
    """
    Yangi material yuklash (Admin/Teacher).
    """
    from .forms import MaterialForm
    org = request.organization
    
    if request.user.role not in ['super_admin', 'owner', 'admin', 'teacher']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('material_list')
    
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES, organization=org)
        if form.is_valid():
            material = form.save(commit=False)
            material.organization = org
            material.uploaded_by = request.user
            material.save()
            form.save_m2m()  # ManyToMany maydonlarni saqlash
            
            log_user_action(request.user, 'CREATE', 'Material', material.id,
                           f"Material yukladi: {material.title}", request=request)
            messages.success(request, f"'{material.title}' muvaffaqiyatli yuklandi!")
            return redirect('material_list')
    else:
        form = MaterialForm(organization=org)
    
    context = {
        'form': form,
        'title': "Yangi Material Yuklash",
    }
    
    return render(request, 'education/material_form.html', context)


@login_required
def material_edit(request, pk):
    """
    Materialni tahrirlash.
    """
    from .forms import MaterialForm
    org = request.organization
    material = get_object_or_404(Material, pk=pk, organization=org)
    
    if request.user.role not in ['super_admin', 'owner', 'admin', 'teacher']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('material_list')
    
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES, instance=material, organization=org)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'Material', material.id,
                           f"Material tahrirladi: {material.title}", request=request)
            messages.success(request, "Material yangilandi!")
            return redirect('material_list')
    else:
        form = MaterialForm(instance=material, organization=org)
    
    context = {
        'form': form,
        'material': material,
        'title': "Materialni Tahrirlash",
    }
    
    return render(request, 'education/material_form.html', context)


@login_required
def material_delete(request, pk):
    """
    Materialni o'chirish.
    """
    org = request.organization
    material = get_object_or_404(Material, pk=pk, organization=org)
    
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('material_list')
    
    material.is_deleted = True
    material.save()
    
    log_user_action(request.user, 'DELETE', 'Material', material.id,
                   f"Material o'chirdi: {material.title}", request=request)
    messages.success(request, "Material o'chirildi!")
    
    return redirect('material_list')


# ===========================================
# CATEGORY MANAGEMENT
# ===========================================

@login_required
def category_list(request):
    """Kategoriyalar ro'yxati"""
    org = request.organization
    
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('material_list')
    
    categories = MaterialCategory.objects.filter(organization=org, is_deleted=False)
    
    return render(request, 'education/category_list.html', {
        'categories': categories
    })


@login_required
def category_create(request):
    """Yangi kategoriya qo'shish"""
    from django import forms
    
    org = request.organization
    
    if request.user.role not in ['super_admin', 'owner', 'admin']:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('material_list')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        icon = request.POST.get('icon', '📁').strip()
        
        if name:
            MaterialCategory.objects.create(
                organization=org,
                name=name,
                icon=icon if icon else '📁'
            )
            messages.success(request, f"'{name}' kategoriyasi qo'shildi!")
            return redirect('material_category_list')
        else:
            messages.error(request, "Kategoriya nomini kiriting!")
    
    return render(request, 'education/category_form.html', {
        'title': "Yangi Kategoriya"
    })
