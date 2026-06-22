from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q

from .models import Course, Room, Group, GroupStudent
from .forms import CourseForm, RoomForm, GroupForm
from apps.users.models import User
from apps.core.audit import log_user_action
from apps.core.permissions import permission_required


# --- KURSLAR ---
@login_required
@permission_required('education', 'view')
def course_list(request):
    """Kurslar ro'yxati"""
    org = request.organization
    courses = Course.objects.filter(organization=org, is_deleted=False)
    courses = courses.annotate(
        group_count=Count('groups', filter=Q(groups__is_deleted=False))
    )
    return render(request, 'education/course_list.html', {'courses': courses})


@login_required
@permission_required('education', 'create')
def course_create(request):
    org = request.organization
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.organization = org
            course.save()
            log_user_action(request.user, 'CREATE', 'Course', course.id, str(course), request=request)
            messages.success(request, "Kurs yaratildi!")
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'education/form.html', {'form': form, 'title': 'Yangi Kurs'})


@login_required
@permission_required('education', 'edit')
def course_edit(request, pk):
    org = request.organization
    course = get_object_or_404(Course, pk=pk, organization=org)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'Course', course.id, str(course), request=request)
            messages.success(request, "Kurs yangilandi!")
            return redirect('course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'education/form.html', {'form': form, 'title': 'Kursni tahrirlash'})


# --- XONALAR ---
@login_required
@permission_required('education', 'view')
def room_list(request):
    org = request.organization
    rooms = Room.objects.filter(organization=org, is_deleted=False)
    return render(request, 'education/room_list.html', {'rooms': rooms})


@login_required
@permission_required('education', 'create')
def room_create(request):
    org = request.organization
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.organization = org
            room.save()
            log_user_action(request.user, 'CREATE', 'Room', room.id, str(room), request=request)
            messages.success(request, "Xona qo'shildi!")
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'education/form.html', {'form': form, 'title': 'Yangi Xona'})


# --- GURUHLAR ---
@login_required
@permission_required('education', 'view')
def group_list(request):
    org = request.organization
    groups = Group.objects.filter(organization=org, is_deleted=False).select_related('course', 'teacher', 'room')
    
    # O'qituvchi faqat o'z guruhlari
    if request.user.role == 'teacher':
        groups = groups.filter(teacher=request.user)
    
    groups = groups.annotate(
        student_count=Count('students', filter=Q(students__status='active', students__is_deleted=False))
    )
    return render(request, 'education/group_list.html', {'groups': groups})


@login_required
@permission_required('education', 'create')
def group_create(request):
    org = request.organization
    if request.method == 'POST':
        form = GroupForm(request.POST, organization=org)
        if form.is_valid():
            group = form.save(commit=False)
            group.organization = org
            group.save()
            log_user_action(request.user, 'CREATE', 'Group', group.id, str(group), request=request)
            messages.success(request, "Guruh muvaffaqiyatli yaratildi!")
            return redirect('group_list')
        else:
            messages.error(request, "Xatolik! Jadvalda to'qnashuv bo'lishi mumkin.")
    else:
        form = GroupForm(organization=org)

    return render(request, 'education/group_form.html', {'form': form, 'title': 'Yangi Guruh'})


@login_required
@permission_required('education', 'view')
def group_detail(request, pk):
    """Guruh tafsilotlari va o'quvchilar"""
    org = request.organization
    group = get_object_or_404(Group, pk=pk, organization=org, is_deleted=False)
    
    # Guruhdagi o'quvchilar
    enrollments = GroupStudent.objects.filter(group=group, is_deleted=False).select_related('student')
    
    # Qo'shish mumkin bo'lgan o'quvchilar
    enrolled_ids = enrollments.values_list('student_id', flat=True)
    available_students = User.objects.filter(
        organization=org,
        role='student',
        is_active=True,
        is_deleted=False
    ).exclude(id__in=enrolled_ids)
    
    context = {
        'group': group,
        'enrollments': enrollments,
        'available_students': available_students,
    }
    return render(request, 'education/group_detail.html', context)


@login_required
@permission_required('education', 'edit')
def add_student_to_group(request, pk):
    """O'quvchini guruhga qo'shish"""
    org = request.organization
    group = get_object_or_404(Group, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        if student_id:
            student = get_object_or_404(User, pk=student_id, organization=org, role='student')
            
            # Tekshirish - allaqachon a'zo emasmi, yoki o'chirilganmi
            existing = GroupStudent.objects.filter(group=group, student=student).first()
            if existing:
                if getattr(existing, 'is_deleted', False):
                    existing.is_deleted = False
                    existing.status = 'active'
                    existing.save()
                    log_user_action(request.user, 'RESTORE', 'GroupStudent', group.id, 
                                   f"{student.first_name} -> {group.name}", request=request)
                    messages.success(request, f"{student.first_name} guruhga qayta qo'shildi!")
                else:
                    messages.warning(request, "Bu o'quvchi allaqachon guruhda!")
            else:
                GroupStudent.objects.create(
                    organization=org,
                    group=group,
                    student=student,
                    status='active'
                )
                log_user_action(request.user, 'CREATE', 'GroupStudent', group.id, 
                               f"{student.first_name} -> {group.name}", request=request)
                messages.success(request, f"{student.first_name} guruhga qo'shildi!")
    
    return redirect('group_detail', pk=pk)


@login_required
@permission_required('education', 'edit')
def remove_student_from_group(request, pk, student_id):
    """O'quvchini guruhdan chiqarish"""
    org = request.organization
    group = get_object_or_404(Group, pk=pk, organization=org, is_deleted=False)
    
    enrollment = get_object_or_404(GroupStudent, group=group, student_id=student_id, is_deleted=False)
    
    if request.method == 'POST':
        student_name = enrollment.student.first_name
        enrollment.delete()
        log_user_action(request.user, 'DELETE', 'GroupStudent', group.id, 
                       f"{student_name} guruhdan o'chirildi", request=request)
        messages.warning(request, "O'quvchi guruhdan o'chirildi.")
    
    return redirect('group_detail', pk=pk)


@login_required
@permission_required('education', 'edit')
def group_edit(request, pk):
    """Guruhni tahrirlash"""
    org = request.organization
    group = get_object_or_404(Group, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group, organization=org)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'Group', group.id, str(group), request=request)
            messages.success(request, "Guruh yangilandi!")
            return redirect('group_detail', pk=pk)
    else:
        form = GroupForm(instance=group, organization=org)
    
    return render(request, 'education/group_form.html', {'form': form, 'title': 'Guruhni tahrirlash', 'group': group})


@login_required
@permission_required('education', 'delete')
def group_delete(request, pk):
    """Guruhni o'chirish (soft delete)"""
    org = request.organization
    group = get_object_or_404(Group, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        group.is_deleted = True
        group.save()
        log_user_action(request.user, 'DELETE', 'Group', group.id, str(group), request=request)
        messages.success(request, "Guruh o'chirildi!")
    
    return redirect('group_list')


@login_required
@permission_required('education', 'delete')
def course_delete(request, pk):
    """Kursni o'chirish (soft delete)"""
    org = request.organization
    course = get_object_or_404(Course, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        course.is_deleted = True
        course.save()
        log_user_action(request.user, 'DELETE', 'Course', course.id, str(course), request=request)
        messages.success(request, "Kurs o'chirildi!")
    
    return redirect('course_list')


@login_required
@permission_required('education', 'edit')
def room_edit(request, pk):
    """Xonani tahrirlash"""
    org = request.organization
    room = get_object_or_404(Room, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'Room', room.id, str(room), request=request)
            messages.success(request, "Xona yangilandi!")
            return redirect('room_list')
    else:
        form = RoomForm(instance=room)
    
    return render(request, 'education/form.html', {'form': form, 'title': 'Xonani tahrirlash'})


@login_required
@permission_required('education', 'delete')
def room_delete(request, pk):
    """Xonani o'chirish (soft delete)"""
    org = request.organization
    room = get_object_or_404(Room, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        room.is_deleted = True
        room.save()
        log_user_action(request.user, 'DELETE', 'Room', room.id, str(room), request=request)
        messages.success(request, "Xona o'chirildi!")
    
    return redirect('room_list')


# --- O'quvchi qidirish API ---
@login_required
def search_students_api(request):
    """AJAX orqali o'quvchilarni qidirish"""
    from django.http import JsonResponse
    
    org = request.organization
    query = request.GET.get('q', '').strip()
    group_id = request.GET.get('group_id')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    students = User.objects.filter(
        organization=org,
        role='student',
        is_active=True,
        is_deleted=False
    ).filter(
        Q(first_name__icontains=query) | 
        Q(last_name__icontains=query) | 
        Q(phone__icontains=query)
    )
    
    # Agar group_id berilgan bo'lsa, guruhda yo'q o'quvchilarni ko'rsatamiz
    if group_id:
        enrolled_ids = GroupStudent.objects.filter(group_id=group_id).values_list('student_id', flat=True)
        students = students.exclude(id__in=enrolled_ids)
    
    students = students[:10]  # Limit
    
    results = [{
        'id': s.id,
        'name': f"{s.first_name} {s.last_name}",
        'phone': s.phone,
    } for s in students]
    
    return JsonResponse({'results': results})