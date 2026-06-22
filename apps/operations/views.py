"""
Operations views - Darslar va Davomat tizimi (ASYNC optimized).
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import timedelta
from asgiref.sync import sync_to_async

from .models import Lesson, Attendance
from apps.education.models import Group, GroupStudent
from apps.users.models import User
from apps.core.audit import log_user_action
from apps.core.permissions import permission_required, check_permission


# Shablon izohlar - davomat olishda tez tanlash uchun
ATTENDANCE_NOTES = [
    "Darsga tayyor",
    "Uy vazifasini bajargan",
    "Faol qatnashdi",
    "Diqqat bilan tingladi",
    "Savollar berdi",
    "Uy vazifasini bajarmagan",
    "Darsga kech keldi",
    "Telefonni ko'p ishlatdi",
    "Sababli kelmadi - kasal",
    "Sababli kelmadi - oilaviy",
]


# Async helper functions
@sync_to_async
def get_lessons_data(user, org, date_filter, group_filter, status_filter):
    """Darslar ma'lumotlarini async olish"""
    # Super admin barcha darslarni ko'radi
    if user.role == 'super_admin' or not org:
        lessons = Lesson.objects.filter(is_deleted=False)
    else:
        lessons = Lesson.objects.filter(organization=org, is_deleted=False)

    # Agar o'qituvchi bo'lsa, faqat o'z darslari
    if user.role == 'teacher':
        lessons = lessons.filter(teacher=user)
    
    if date_filter:
        lessons = lessons.filter(date=date_filter)
    if group_filter:
        lessons = lessons.filter(group_id=group_filter)
    if status_filter:
        lessons = lessons.filter(status=status_filter)
    
    lessons = lessons.select_related('group', 'teacher', 'room').annotate(
        attendance_count=Count('attendances', distinct=True),
        present_count=Count('attendances', filter=Q(attendances__status='present'), distinct=True),
    ).order_by('start_time')
    
    # Davomat olinganligini tekshirish
    lessons_data = []
    for lesson in lessons:
        attendance_count = lesson.attendance_count
        lessons_data.append({
            'lesson': lesson,
            'attendance_taken': attendance_count > 0,
            'attendance_count': attendance_count,
            'present_count': lesson.present_count,
        })
    
    return lessons_data, list(lessons)


@sync_to_async
def get_groups_for_filter(user, org):
    """Guruhlarni filter uchun olish"""
    if user.role == 'teacher':
        groups = Group.objects.filter(teacher=user, is_deleted=False)
    elif user.role == 'super_admin' or not org:
        groups = Group.objects.filter(is_deleted=False)
    else:
        groups = Group.objects.filter(organization=org, is_deleted=False)
    return list(groups)


# ===========================================
# LESSONS (DARSLAR)
# ===========================================

@login_required
@permission_required('operations', 'view')
def lesson_list(request):
    """Darslar va Jadval - birlashtirilgan dashboard"""
    org = request.user.organization
    user = request.user
    today = timezone.now().date()

    # Filter parametrlari
    date_filter = request.GET.get('date', str(today))
    group_filter = request.GET.get('group', '')
    status_filter = request.GET.get('status', '')

    # Super admin barcha darslarni ko'radi
    if user.role == 'super_admin' or not org:
        lessons = Lesson.objects.filter(is_deleted=False)
    else:
        lessons = Lesson.objects.filter(organization=org, is_deleted=False)

    # Agar o'qituvchi bo'lsa, faqat o'z darslari
    if user.role == 'teacher':
        lessons = lessons.filter(teacher=user)

    if date_filter:
        lessons = lessons.filter(date=date_filter)
    if group_filter:
        lessons = lessons.filter(group_id=group_filter)
    if status_filter:
        lessons = lessons.filter(status=status_filter)

    lessons = lessons.select_related('group', 'teacher', 'room').annotate(
        attendance_count=Count('attendances', distinct=True),
        present_count=Count('attendances', filter=Q(attendances__status='present'), distinct=True),
    ).order_by('start_time')

    # Davomat olinganligini tekshirish
    lessons_data = []
    attendance_taken_count = 0
    ongoing_count = 0
    for lesson in lessons:
        attendance_count = lesson.attendance_count
        if attendance_count > 0:
            attendance_taken_count += 1
        if lesson.status == 'started':
            ongoing_count += 1
        lessons_data.append({
            'lesson': lesson,
            'attendance_taken': attendance_count > 0,
            'attendance_count': attendance_count,
            'present_count': lesson.present_count,
        })

    # Guruhlar filter uchun
    if user.role == 'teacher':
        groups = Group.objects.filter(teacher=user, is_deleted=False)
    elif user.role == 'super_admin' or not org:
        groups = Group.objects.filter(is_deleted=False)
    else:
        groups = Group.objects.filter(organization=org, is_deleted=False)

    # ========== HAFTALIK JADVAL ==========
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    week_offset = int(request.GET.get('week', 0))
    start_of_week += timedelta(weeks=week_offset)
    end_of_week += timedelta(weeks=week_offset)

    # Faol guruhlar
    if user.role == 'super_admin' or not org:
        schedule_groups = Group.objects.filter(
            is_deleted=False, status__in=['active', 'pending']
        ).select_related('teacher', 'room', 'course')
    else:
        schedule_groups = Group.objects.filter(
            organization=org, is_deleted=False, status__in=['active', 'pending']
        ).select_related('teacher', 'room', 'course')

    if user.role == 'teacher':
        schedule_groups = schedule_groups.filter(teacher=user)
    elif user.role == 'student':
        my_groups = GroupStudent.objects.filter(student=user, status='active').values_list('group_id', flat=True)
        schedule_groups = schedule_groups.filter(id__in=my_groups)

    # Hafta kunlari
    day_names = ['', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
    week_days = []
    weekly_lessons_count = 0

    for i in range(7):
        day_number = i + 1
        day_date = start_of_week + timedelta(days=i)
        day_groups = []

        for group in schedule_groups:
            if group.schedule_days and day_number in group.schedule_days:
                weekly_lessons_count += 1
                day_groups.append({
                    'group': group,
                    'name': group.name,
                    'start_time': group.start_time,
                    'end_time': group.end_time,
                    'room': group.room,
                    'teacher': group.teacher,
                })

        day_groups.sort(key=lambda x: x['start_time'] if x['start_time'] else timezone.now().time())

        week_days.append({
            'day_number': day_number,
            'day_name': day_names[day_number],
            'date': day_date,
            'is_today': day_date == today,
            'groups': day_groups,
        })

    context = {
        # Bugungi darslar
        'lessons_data': lessons_data,
        'lessons': lessons,
        'groups': groups,
        'today': today,
        'date_filter': date_filter,
        'group_filter': group_filter,
        'status_filter': status_filter,
        # Statistika
        'today_lessons_count': len(lessons_data),
        'attendance_taken_count': attendance_taken_count,
        'ongoing_count': ongoing_count,
        'weekly_lessons_count': weekly_lessons_count,
        # Haftalik jadval
        'week_days': week_days,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'week_offset': week_offset,
    }
    
    return render(request, 'operations/lessons_dashboard.html', context)


@login_required
@permission_required('operations', 'create')
def lesson_add(request):
    """Yangi dars qo'shish"""
    org = request.user.organization
    user = request.user
    
    # Guruhlar va xonalar
    if user.role == 'teacher':
        groups = Group.objects.filter(teacher=user, is_deleted=False, status='active')
    elif user.role == 'super_admin' or not org:
        groups = Group.objects.filter(is_deleted=False, status='active')
    else:
        groups = Group.objects.filter(organization=org, is_deleted=False, status='active')
    
    from apps.education.models import Room
    if user.role == 'super_admin' or not org:
        rooms = Room.objects.filter(is_deleted=False)
    else:
        rooms = Room.objects.filter(organization=org, is_deleted=False)

    if request.method == 'POST':
        group_id = request.POST.get('group')
        date = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        room_id = request.POST.get('room') or None
        topic = request.POST.get('topic', '')
        
        if group_id and date and start_time and end_time:
            group = get_object_or_404(Group, pk=group_id)
            
            lesson = Lesson.objects.create(
                organization=org or group.organization,
                group=group,
                teacher=group.teacher or user,
                date=date,
                start_time=start_time,
                end_time=end_time,
                room_id=room_id,
                topic=topic,
                status='scheduled'
            )
            
            log_user_action(user, 'CREATE', 'Lesson', lesson.id, str(lesson), request=request)
            messages.success(request, "Dars muvaffaqiyatli qo'shildi!")
            return redirect('operations:lesson_list')
        else:
            messages.error(request, "Barcha maydonlarni to'ldiring!")
    
    context = {
        'groups': groups,
        'rooms': rooms,
        'today': timezone.now().date(),
    }
    
    return render(request, 'operations/lesson_form.html', context)


@login_required
@permission_required('operations', 'view')
def lesson_detail(request, pk):
    """Dars tafsilotlari"""
    org = request.user.organization
    user = request.user

    # Super admin barcha darslarni ko'radi
    if user.role == 'super_admin' or not org:
        lesson = get_object_or_404(Lesson, pk=pk, is_deleted=False)
    else:
        lesson = get_object_or_404(Lesson, pk=pk, organization=org, is_deleted=False)

    # Ushbu darsdagi davomatlar
    attendances = Attendance.objects.filter(lesson=lesson).select_related('student')
    
    # O'qituvchining umumiy reytingi
    teacher_avg_rating = None
    total_ratings_count = 0
    if lesson.teacher:
        from apps.operations.models import TeacherWeeklyRating
        ratings = TeacherWeeklyRating.objects.filter(teacher=lesson.teacher)
        total_ratings_count = ratings.count()
        if total_ratings_count > 0:
            avg_data = ratings.aggregate(
                avg_prep=Avg('preparation'),
                avg_del=Avg('delivery'),
                avg_eng=Avg('engagement'),
                avg_punc=Avg('punctuality'),
                avg_overall=Avg('overall')
            )
            teacher_avg_rating = round((
                (avg_data['avg_prep'] or 0) +
                (avg_data['avg_del'] or 0) +
                (avg_data['avg_eng'] or 0) +
                (avg_data['avg_punc'] or 0) +
                (avg_data['avg_overall'] or 0)
            ) / 5, 1)

    # Davomat statistikasi
    attendance_stats = attendances.aggregate(
        present_count=Count('id', filter=Q(status='present')),
        total_students=Count('id'),
    )
    present_count = attendance_stats['present_count'] or 0
    total_students = attendance_stats['total_students'] or 0

    context = {
        'lesson': lesson,
        'attendances': attendances,
        'teacher_avg_rating': teacher_avg_rating,
        'total_ratings_count': total_ratings_count,
        'present_count': present_count,
        'total_students': total_students,
    }
    
    return render(request, 'operations/lesson_detail.html', context)


@login_required
@permission_required('operations', 'edit')
def start_lesson(request, pk):
    """Darsni boshlash"""
    org = request.user.organization
    user = request.user

    # Super admin barcha darslarni boshlashi mumkin
    if user.role == 'super_admin' or not org:
        lesson = get_object_or_404(Lesson, pk=pk, is_deleted=False)
    else:
        lesson = get_object_or_404(Lesson, pk=pk, organization=org, is_deleted=False)

    if lesson.status == 'scheduled':
        lesson.status = 'started'
        lesson.started_at = timezone.now()
        lesson.save()
        log_user_action(request.user, 'UPDATE', 'Lesson', lesson.id, str(lesson), 
                       changes={'status': 'started'}, request=request)
        messages.success(request, "Dars boshlandi!")
    
    return redirect('operations:take_attendance', pk=lesson.pk)


@login_required
@permission_required('operations', 'edit')
def finish_lesson(request, pk):
    """Darsni yakunlash"""
    org = request.user.organization
    user = request.user

    # Super admin barcha darslarni yakunlashi mumkin
    if user.role == 'super_admin' or not org:
        lesson = get_object_or_404(Lesson, pk=pk, is_deleted=False)
    else:
        lesson = get_object_or_404(Lesson, pk=pk, organization=org, is_deleted=False)

    if lesson.status in ['scheduled', 'started']:
        lesson.status = 'finished'
        lesson.finished_at = timezone.now()
        lesson.save()
        log_user_action(request.user, 'UPDATE', 'Lesson', lesson.id, str(lesson), 
                       changes={'status': 'finished'}, request=request)
        messages.success(request, "Dars yakunlandi!")
    
    return redirect('operations:lesson_list')


@login_required
@permission_required('operations', 'edit')
def lesson_edit(request, pk):
    """Darsni tahrirlash"""
    org = request.user.organization
    user = request.user

    if user.role == 'super_admin' or not org:
        lesson = get_object_or_404(Lesson, pk=pk, is_deleted=False)
    else:
        lesson = get_object_or_404(Lesson, pk=pk, organization=org, is_deleted=False)

    # Guruhlar va xonalar
    if user.role == 'teacher':
        groups = Group.objects.filter(teacher=user, is_deleted=False, status='active')
    elif user.role == 'super_admin' or not org:
        groups = Group.objects.filter(is_deleted=False, status='active')
    else:
        groups = Group.objects.filter(organization=org, is_deleted=False, status='active')

    from apps.education.models import Room
    if user.role == 'super_admin' or not org:
        rooms = Room.objects.filter(is_deleted=False)
    else:
        rooms = Room.objects.filter(organization=org, is_deleted=False)

    if request.method == 'POST':
        group_id = request.POST.get('group')
        date = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        room_id = request.POST.get('room') or None
        topic = request.POST.get('topic', '')

        if group_id and date and start_time and end_time:
            lesson.group_id = group_id
            lesson.date = date
            lesson.start_time = start_time
            lesson.end_time = end_time
            lesson.room_id = room_id
            lesson.topic = topic
            lesson.save()

            log_user_action(user, 'UPDATE', 'Lesson', lesson.id, str(lesson), request=request)
            messages.success(request, "Dars muvaffaqiyatli yangilandi!")
            return redirect('operations:lesson_list')
        else:
            messages.error(request, "Barcha maydonlarni to'ldiring!")

    context = {
        'groups': groups,
        'rooms': rooms,
        'today': timezone.now().date(),
        'lesson': lesson,
        'is_edit': True,
    }

    return render(request, 'operations/lesson_form.html', context)


@login_required
@permission_required('operations', 'delete')
def lesson_delete(request, pk):
    """Darsni o'chirish (soft delete)"""
    org = request.user.organization
    user = request.user

    if user.role == 'super_admin' or not org:
        lesson = get_object_or_404(Lesson, pk=pk, is_deleted=False)
    else:
        lesson = get_object_or_404(Lesson, pk=pk, organization=org, is_deleted=False)

    if request.method == 'POST':
        lesson.is_deleted = True
        lesson.save()
        log_user_action(user, 'DELETE', 'Lesson', lesson.id, str(lesson), request=request)
        messages.success(request, "Dars o'chirildi!")

    return redirect('operations:lesson_list')


# ===========================================
# ATTENDANCE (DAVOMAT)
# ===========================================

@login_required
@permission_required('operations', 'edit')
def take_attendance(request, pk):
    """Davomat olish sahifasi"""
    org = request.user.organization
    user = request.user

    # Super admin barcha darslarni ko'radi
    if user.role == 'super_admin' or not org:
        lesson = get_object_or_404(Lesson, pk=pk, is_deleted=False)
    else:
        lesson = get_object_or_404(Lesson, pk=pk, organization=org, is_deleted=False)

    # Guruhdagi o'quvchilar
    group_students = GroupStudent.objects.filter(
        group=lesson.group,
        status='active'
    ).select_related('student')
    
    # Mavjud davomatlar
    existing_attendances = {
        att.student_id: att 
        for att in Attendance.objects.filter(lesson=lesson)
    }
    
    if request.method == 'POST':
        for gs in group_students:
            student = gs.student
            status = request.POST.get(f'status_{student.id}', 'absent')
            grade = request.POST.get(f'grade_{student.id}', '')
            comment = request.POST.get(f'comment_{student.id}', '')
            
            # XP hisoblash
            xp = 0
            if status == 'present':
                xp = 10
            elif status == 'late':
                xp = 5
            elif status == 'excused':
                xp = 3
            
            # Mavjud davomatni yangilash yoki yangi yaratish
            if student.id in existing_attendances:
                att = existing_attendances[student.id]
                att.status = status
                att.grade = int(grade) if grade else None
                att.comment = comment
                att.xp_points = xp
                att.save()
            else:
                Attendance.objects.create(
                    organization=org or lesson.organization,
                    lesson=lesson,
                    student=student,
                    status=status,
                    grade=int(grade) if grade else None,
                    comment=comment,
                    xp_points=xp,
                )
        
        log_user_action(request.user, 'UPDATE', 'Attendance', lesson.id, 
                       f"Davomat - {lesson.group.name}", request=request)
        messages.success(request, "Davomat saqlandi!")
        return redirect('operations:lesson_list')

    # O'quvchilar ro'yxatini tayyorlash
    students_data = []
    for gs in group_students:
        existing = existing_attendances.get(gs.student_id)
        students_data.append({
            'student': gs.student,
            'status': existing.status if existing else 'present',
            'grade': existing.grade if existing else None,
            'comment': existing.comment if existing else '',
        })
    
    context = {
        'lesson': lesson,
        'students_data': students_data,
        'attendance_notes': ATTENDANCE_NOTES,
    }
    
    return render(request, 'operations/take_attendance.html', context)


# ===========================================
# SCHEDULE (JADVAL)
# ===========================================

@login_required
@permission_required('operations', 'view')
def schedule_view(request):
    """Haftalik jadval - lesson_list ga redirect"""
    return redirect('operations:lesson_list')


# ===========================================
# RATINGS (REYTINGLAR)
# ===========================================

@login_required
@permission_required('operations', 'view')
def teacher_ratings(request):
    """O'qituvchilar reytingi va haftalik baho qo'yish"""
    org = request.user.organization
    user = request.user
    today = timezone.now().date()

    # Joriy hafta
    current_week_start = today - timedelta(days=today.weekday())
    current_week_end = current_week_start + timedelta(days=6)

    # Baho qo'yish (faqat super_admin va owner)
    if request.method == 'POST' and user.role in ['super_admin', 'owner']:
        teacher_id = request.POST.get('teacher_id')
        preparation = int(request.POST.get('preparation', 5))
        delivery = int(request.POST.get('delivery', 5))
        engagement = int(request.POST.get('engagement', 5))
        punctuality = int(request.POST.get('punctuality', 5))
        overall = int(request.POST.get('overall', 5))
        comment = request.POST.get('rating_comment', '')

        teacher = get_object_or_404(User, pk=teacher_id, role='teacher')

        from apps.operations.models import TeacherWeeklyRating
        rating, created = TeacherWeeklyRating.objects.update_or_create(
            teacher=teacher,
            week_start=current_week_start,
            defaults={
                'organization': org or teacher.organization,
                'rated_by': user,
                'week_end': current_week_end,
                'preparation': min(5, max(1, preparation)),
                'delivery': min(5, max(1, delivery)),
                'engagement': min(5, max(1, engagement)),
                'punctuality': min(5, max(1, punctuality)),
                'overall': min(5, max(1, overall)),
                'comment': comment,
            }
        )

        action = "yangilandi" if not created else "qo'yildi"
        messages.success(request, f"{teacher.first_name} uchun haftalik baho {action}!")
        return redirect('operations:teacher_ratings')

    # O'qituvchilar ro'yxati
    if user.role == 'super_admin' or not org:
        teachers = User.objects.filter(role='teacher', is_deleted=False)
    else:
        teachers = User.objects.filter(organization=org, role='teacher', is_deleted=False)

    teachers = teachers.annotate(
        group_count=Count('teaching_groups', filter=Q(teaching_groups__status='active'), distinct=True),
        student_count=Count(
            'teaching_groups__students__student',
            filter=Q(teaching_groups__status='active', teaching_groups__students__status='active'),
            distinct=True
        ),
        lesson_count=Count('lesson', filter=Q(lesson__status='finished'), distinct=True),
    ).order_by('-student_count')
    
    # O'qituvchilar ma'lumotlarini to'plash
    from apps.operations.models import TeacherWeeklyRating
    teachers_data = []

    for teacher in teachers:
        # Joriy hafta bahosi
        current_rating = TeacherWeeklyRating.objects.filter(
            teacher=teacher,
            week_start=current_week_start
        ).first()

        # Umumiy o'rtacha reyting
        all_ratings = TeacherWeeklyRating.objects.filter(teacher=teacher)
        total_ratings = all_ratings.count()
        avg_rating = None
        if total_ratings > 0:
            avg_data = all_ratings.aggregate(
                avg_prep=Avg('preparation'),
                avg_del=Avg('delivery'),
                avg_eng=Avg('engagement'),
                avg_punc=Avg('punctuality'),
                avg_overall=Avg('overall')
            )
            avg_rating = round((
                (avg_data['avg_prep'] or 0) +
                (avg_data['avg_del'] or 0) +
                (avg_data['avg_eng'] or 0) +
                (avg_data['avg_punc'] or 0) +
                (avg_data['avg_overall'] or 0)
            ) / 5, 1)

        # O'rtacha davomat foizi
        total_att = Attendance.objects.filter(
            lesson__teacher=teacher,
            lesson__status='finished'
        ).count()
        present_att = Attendance.objects.filter(
            lesson__teacher=teacher,
            lesson__status='finished',
            status='present'
        ).count()
        att_rate = (present_att / total_att * 100) if total_att > 0 else 0
        
        teachers_data.append({
            'teacher': teacher,
            'group_count': teacher.group_count,
            'student_count': teacher.student_count,
            'lesson_count': teacher.lesson_count,
            'attendance_rate': round(att_rate, 1),
            'current_rating': current_rating,
            'avg_rating': avg_rating,
            'total_ratings': total_ratings,
        })
    
    context = {
        'teachers_data': teachers_data,
        'current_week_start': current_week_start,
        'current_week_end': current_week_end,
        'can_rate': user.role in ['super_admin', 'owner'],
    }

    # ========== O'QUVCHILAR ==========
    if user.role == 'super_admin' or not org:
        students = User.objects.filter(role='student', is_deleted=False)
    else:
        students = User.objects.filter(organization=org, role='student', is_deleted=False)

    students_data = []
    for student in students[:50]:  # Top 50
        # Guruh
        gs = GroupStudent.objects.filter(student=student, status='active').select_related('group').first()
        group_name = gs.group.name if gs else None

        # XP
        xp = getattr(student, 'xp_points', 0) or 0

        # Davomat
        total_att = Attendance.objects.filter(student=student).count()
        present_att = Attendance.objects.filter(student=student, status='present').count()
        att_rate = (present_att / total_att * 100) if total_att > 0 else 0

        # O'rtacha baho
        avg_grade = Attendance.objects.filter(student=student, grade__isnull=False).aggregate(avg=Avg('grade'))['avg']

        students_data.append({
            'student': student,
            'group_name': group_name,
            'xp': xp,
            'attendance_rate': round(att_rate, 1),
            'avg_grade': round(avg_grade, 1) if avg_grade else None,
        })

    # XP bo'yicha tartiblash
    students_data.sort(key=lambda x: x['xp'], reverse=True)
    context['students_data'] = students_data

    return render(request, 'operations/ratings_dashboard.html', context)


@login_required
def student_ratings(request):
    """O'quvchilar reytingi - Reytinglar sahifasiga redirect (tab=students)"""
    return redirect('operations:teacher_ratings')
