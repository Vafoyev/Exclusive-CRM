"""
Operations Export Views - Darslar va davomat ma'lumotlarini PDF va Excel formatida eksport qilish.
"""
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q

from reportlab.lib.units import cm

from .models import Lesson, Attendance
from apps.education.models import Group
from apps.core.export_utils import export_to_excel, export_to_pdf


@login_required
def export_lessons_excel(request):
    """Darslar ro'yxatini Excel formatida eksport qilish"""
    org = request.organization
    user = request.user

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    group_id = request.GET.get('group', '')

    lessons = Lesson.objects.filter(is_deleted=False)
    if org:
        lessons = lessons.filter(organization=org)
    if user.role == 'teacher':
        lessons = lessons.filter(teacher=user)
    if date_from:
        lessons = lessons.filter(date__gte=date_from)
    if date_to:
        lessons = lessons.filter(date__lte=date_to)
    if group_id:
        lessons = lessons.filter(group_id=group_id)

    lessons = lessons.select_related('group', 'teacher', 'room').order_by('-date', 'start_time')

    data = []
    for lesson in lessons:
        # Davomat statistikasi
        attendance = Attendance.objects.filter(lesson=lesson)
        total = attendance.count()
        present = attendance.filter(status='present').count()

        data.append({
            'id': lesson.id,
            'date': lesson.date.strftime('%Y-%m-%d') if lesson.date else '',
            'time': f"{lesson.start_time.strftime('%H:%M')}-{lesson.end_time.strftime('%H:%M')}" if lesson.start_time else '',
            'group': lesson.group.name if lesson.group else '-',
            'teacher': f"{lesson.teacher.first_name} {lesson.teacher.last_name}" if lesson.teacher else '-',
            'room': lesson.room.name if lesson.room else '-',
            'topic': lesson.topic or '-',
            'attendance': f"{present}/{total}" if total > 0 else '-',
            'status': lesson.get_status_display() if hasattr(lesson, 'get_status_display') else lesson.status,
        })

    columns = [
        {'key': 'id', 'header': 'ID', 'width': 8},
        {'key': 'date', 'header': 'Sana', 'width': 12},
        {'key': 'time', 'header': 'Vaqt', 'width': 14},
        {'key': 'group', 'header': 'Guruh', 'width': 18},
        {'key': 'teacher', 'header': "O'qituvchi", 'width': 20},
        {'key': 'room', 'header': 'Xona', 'width': 12},
        {'key': 'topic', 'header': 'Mavzu', 'width': 25},
        {'key': 'attendance', 'header': 'Davomat', 'width': 10},
        {'key': 'status', 'header': 'Holat', 'width': 12},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"darslar_{today}"
    title = f"DARSLAR RO'YXATI"

    return export_to_excel(data, columns, filename, title=title, sheet_name="Darslar")


@login_required
def export_lessons_pdf(request):
    """Darslar ro'yxatini PDF formatida eksport qilish"""
    org = request.organization
    user = request.user

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    lessons = Lesson.objects.filter(is_deleted=False)
    if org:
        lessons = lessons.filter(organization=org)
    if user.role == 'teacher':
        lessons = lessons.filter(teacher=user)
    if date_from:
        lessons = lessons.filter(date__gte=date_from)
    if date_to:
        lessons = lessons.filter(date__lte=date_to)

    lessons = lessons.select_related('group', 'teacher').order_by('-date')[:100]

    data = []
    for lesson in lessons:
        data.append({
            'date': lesson.date.strftime('%d.%m.%Y') if lesson.date else '',
            'time': lesson.start_time.strftime('%H:%M') if lesson.start_time else '',
            'group': lesson.group.name if lesson.group else '-',
            'teacher': f"{lesson.teacher.first_name}" if lesson.teacher else '-',
            'status': lesson.get_status_display() if hasattr(lesson, 'get_status_display') else lesson.status,
        })

    columns = [
        {'key': 'date', 'header': 'Sana', 'width': 2.5*cm},
        {'key': 'time', 'header': 'Vaqt', 'width': 2*cm},
        {'key': 'group', 'header': 'Guruh', 'width': 4*cm},
        {'key': 'teacher', 'header': "O'qituvchi", 'width': 4*cm},
        {'key': 'status', 'header': 'Holat', 'width': 3*cm},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"darslar_{today}"
    title = "DARSLAR RO'YXATI"
    subtitle = f"Jami: {len(data)} ta dars"

    return export_to_pdf(data, columns, filename, title=title, subtitle=subtitle)


@login_required
def export_attendance_excel(request):
    """Davomat hisobotini Excel formatida eksport qilish"""
    org = request.organization
    group_id = request.GET.get('group', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    attendance = Attendance.objects.filter(lesson__is_deleted=False)
    if org:
        attendance = attendance.filter(organization=org)
    if group_id:
        attendance = attendance.filter(lesson__group_id=group_id)
    if date_from:
        attendance = attendance.filter(lesson__date__gte=date_from)
    if date_to:
        attendance = attendance.filter(lesson__date__lte=date_to)

    attendance = attendance.select_related('student', 'lesson', 'lesson__group').order_by('-lesson__date')

    data = []
    for att in attendance:
        data.append({
            'date': att.lesson.date.strftime('%Y-%m-%d') if att.lesson and att.lesson.date else '',
            'group': att.lesson.group.name if att.lesson and att.lesson.group else '-',
            'student': f"{att.student.first_name} {att.student.last_name}" if att.student else '-',
            'status': att.get_status_display() if hasattr(att, 'get_status_display') else att.status,
            'grade': att.grade if att.grade else '-',
            'xp': att.xp_points if att.xp_points else 0,
            'comment': att.comment or '',
        })

    columns = [
        {'key': 'date', 'header': 'Sana', 'width': 12},
        {'key': 'group', 'header': 'Guruh', 'width': 18},
        {'key': 'student', 'header': "O'quvchi", 'width': 25},
        {'key': 'status', 'header': 'Holat', 'width': 12},
        {'key': 'grade', 'header': 'Baho', 'width': 8},
        {'key': 'xp', 'header': 'XP', 'width': 8},
        {'key': 'comment', 'header': 'Izoh', 'width': 25},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"davomat_{today}"
    title = f"DAVOMAT HISOBOTI"

    return export_to_excel(data, columns, filename, title=title, sheet_name="Davomat")


@login_required
def export_group_attendance_excel(request, group_id):
    """Guruh bo'yicha davomat hisobotini Excel formatida eksport qilish"""
    group = Group.objects.get(pk=group_id)

    from apps.education.models import GroupStudent
    students = GroupStudent.objects.filter(group=group, status='active').select_related('student')

    # Darslar (oxirgi 30 kun)
    from datetime import timedelta
    today = timezone.now().date()
    start_date = today - timedelta(days=30)

    lessons = Lesson.objects.filter(
        group=group,
        date__gte=start_date,
        is_deleted=False
    ).order_by('date')

    # Ma'lumotlarni tayyorlash
    data = []
    for gs in students:
        student = gs.student
        row = {
            'name': f"{student.first_name} {student.last_name}",
        }

        total = 0
        present = 0
        for lesson in lessons:
            att = Attendance.objects.filter(lesson=lesson, student=student).first()
            key = f"d_{lesson.date.strftime('%d.%m')}"
            if att:
                row[key] = '✓' if att.status == 'present' else ('○' if att.status == 'late' else '✗')
                total += 1
                if att.status in ['present', 'late']:
                    present += 1
            else:
                row[key] = '-'

        row['attendance_rate'] = f"{present}/{total}" if total > 0 else '-'
        data.append(row)

    # Ustunlar
    columns = [{'key': 'name', 'header': "O'quvchi", 'width': 25}]
    for lesson in lessons:
        columns.append({
            'key': f"d_{lesson.date.strftime('%d.%m')}",
            'header': lesson.date.strftime('%d.%m'),
            'width': 6
        })
    columns.append({'key': 'attendance_rate', 'header': 'Jami', 'width': 10})

    filename = f"davomat_{group.name}_{today}"
    title = f"DAVOMAT - {group.name}"

    return export_to_excel(data, columns, filename, title=title, sheet_name="Davomat")
