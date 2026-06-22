"""
LMS - O'quv Materiallari view'lari.
Materiallarni ko'rish, yuklab olish, va progress tracking.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q

from apps.education.models import Course
from apps.education.lms_models import CourseMaterial, MaterialProgress
from apps.core.audit import log_user_action


@login_required
def material_list(request):
    """
    Kurslar bo'yicha materiallar ro'yxati.
    """
    org = request.user.organization
    
    # O'qituvchi yoki admin bo'lsa, barcha materiallarni ko'radi
    if request.user.role in ['super_admin', 'owner', 'admin', 'teacher']:
        courses = Course.objects.filter(organization=org, is_deleted=False, is_active=True)
    else:
        # O'quvchi faqat o'zi yozilgan kurslarga tegishli materiallarni ko'radi
        from apps.education.models import GroupStudent
        enrolled_courses = GroupStudent.objects.filter(
            student=request.user,
            status='active'
        ).values_list('group__course_id', flat=True).distinct()
        courses = Course.objects.filter(id__in=enrolled_courses, is_deleted=False)
    
    courses = courses.annotate(material_count=Count('materials'))
    
    # Kurs tanlash
    course_id = request.GET.get('course')
    materials = CourseMaterial.objects.filter(organization=org, is_deleted=False)
    
    if course_id:
        materials = materials.filter(course_id=course_id)
    elif courses.exists():
        materials = materials.filter(course__in=courses)
    
    materials = materials.select_related('course', 'uploaded_by').order_by('order', '-created_at')
    
    # Turi bo'yicha filter
    material_type = request.GET.get('type')
    if material_type:
        materials = materials.filter(material_type=material_type)
    
    # Statistika
    total_materials = materials.count()
    
    context = {
        'courses': courses,
        'materials': materials,
        'total_materials': total_materials,
        'current_course': course_id,
        'current_type': material_type,
        'type_choices': CourseMaterial.TYPE_CHOICES,
    }
    
    return render(request, 'education/material_list.html', context)


@login_required
def material_detail(request, pk):
    """
    Material tafsiloti va ko'rish.
    """
    org = request.user.organization
    material = get_object_or_404(CourseMaterial, pk=pk, organization=org)
    
    # Ko'rish sonini oshirish
    material.view_count += 1
    material.save(update_fields=['view_count'])
    
    # Progress yangilash (O'quvchi uchun)
    if request.user.role == 'student':
        progress, created = MaterialProgress.objects.get_or_create(
            student=request.user,
            material=material,
            defaults={'organization': org}
        )
        if created:
            log_user_action(request.user, 'CREATE', 'MaterialProgress', 
                           progress.id, f"Started: {material.title}", request=request)
    
    # Bog'liq materiallar
    related_materials = CourseMaterial.objects.filter(
        course=material.course,
        is_deleted=False
    ).exclude(id=material.id).order_by('order')[:5]
    
    context = {
        'material': material,
        'related_materials': related_materials,
    }
    
    return render(request, 'education/material_detail.html', context)


@login_required
def material_upload(request, course_id):
    """
    Yangi material yuklash (O'qituvchi/Admin uchun).
    """
    org = request.user.organization
    course = get_object_or_404(Course, pk=course_id, organization=org)
    
    # Ruxsatni tekshirish
    if request.user.role not in ['super_admin', 'owner', 'admin', 'teacher']:
        messages.error(request, "Sizda material yuklash huquqi yo'q!")
        return redirect('education:material_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        material_type = request.POST.get('material_type', 'document')
        file = request.FILES.get('file')
        external_url = request.POST.get('external_url', '')
        is_public = request.POST.get('is_public') == 'on'
        
        material = CourseMaterial.objects.create(
            organization=org,
            course=course,
            title=title,
            description=description,
            material_type=material_type,
            file=file,
            external_url=external_url,
            is_public=is_public,
            uploaded_by=request.user,
            file_size=file.size if file else 0,
        )
        
        log_user_action(request.user, 'CREATE', 'CourseMaterial', 
                       material.id, title, request=request)
        messages.success(request, f"'{title}' materiali muvaffaqiyatli yuklandi!")
        return redirect('education:material_list')
    
    context = {
        'course': course,
        'type_choices': CourseMaterial.TYPE_CHOICES,
    }
    
    return render(request, 'education/material_upload.html', context)


@login_required
def mark_material_complete(request, pk):
    """
    Materialni tugallangan deb belgilash (AJAX).
    """
    if request.method == 'POST' and request.user.role == 'student':
        org = request.user.organization
        material = get_object_or_404(CourseMaterial, pk=pk, organization=org)
        
        progress, created = MaterialProgress.objects.get_or_create(
            student=request.user,
            material=material,
            defaults={'organization': org}
        )
        
        progress.is_completed = True
        progress.progress_percent = 100
        progress.completed_at = timezone.now()
        progress.save()
        
        return JsonResponse({'status': 'success', 'message': "Material tugallandi!"})
    
    return JsonResponse({'status': 'error', 'message': "Noto'g'ri so'rov"}, status=400)
