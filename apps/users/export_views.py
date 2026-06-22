"""
Users Export Views - Foydalanuvchilar ma'lumotlarini PDF va Excel formatida eksport qilish.
"""
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from reportlab.lib.units import cm

from .models import User
from apps.core.export_utils import export_to_excel, export_to_pdf


@login_required
def export_users_excel(request):
    """Foydalanuvchilar ro'yxatini Excel formatida eksport qilish"""
    org = request.organization
    role = request.GET.get('role', '')

    users = User.objects.filter(is_deleted=False)
    if org:
        users = users.filter(organization=org)
    if role:
        users = users.filter(role=role)

    users = users.select_related('organization', 'branch').order_by('role', 'first_name')

    data = []
    for user in users:
        data.append({
            'id': user.id,
            'name': f"{user.first_name} {user.last_name}",
            'phone': user.phone or '',
            'role': user.get_role_display() if hasattr(user, 'get_role_display') else user.role,
            'branch': user.branch.name if user.branch else '-',
            'balance': float(user.balance) if user.balance else 0,
            'status': 'Faol' if user.is_active else 'Nofaol',
            'joined': user.date_joined.strftime('%Y-%m-%d') if user.date_joined else '',
        })

    columns = [
        {'key': 'id', 'header': 'ID', 'width': 8},
        {'key': 'name', 'header': 'F.I.O', 'width': 28},
        {'key': 'phone', 'header': 'Telefon', 'width': 18},
        {'key': 'role', 'header': 'Rol', 'width': 15},
        {'key': 'branch', 'header': 'Filial', 'width': 18},
        {'key': 'balance', 'header': 'Balans', 'width': 15, 'money': True},
        {'key': 'status', 'header': 'Holat', 'width': 10},
        {'key': 'joined', 'header': "Qo'shilgan", 'width': 12},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"foydalanuvchilar_{today}"

    role_name = dict(User.ROLE_CHOICES).get(role, 'Barcha') if role else 'Barcha'
    title = f"FOYDALANUVCHILAR RO'YXATI - {role_name}"

    return export_to_excel(data, columns, filename, title=title)


@login_required
def export_users_pdf(request):
    """Foydalanuvchilar ro'yxatini PDF formatida eksport qilish"""
    org = request.organization
    role = request.GET.get('role', '')

    users = User.objects.filter(is_deleted=False)
    if org:
        users = users.filter(organization=org)
    if role:
        users = users.filter(role=role)

    users = users.order_by('role', 'first_name')[:100]

    data = []
    for i, user in enumerate(users, 1):
        data.append({
            'num': i,
            'name': f"{user.first_name} {user.last_name}",
            'phone': user.phone or '',
            'role': user.get_role_display() if hasattr(user, 'get_role_display') else user.role,
            'status': 'Faol' if user.is_active else 'Nofaol',
        })

    columns = [
        {'key': 'num', 'header': '#', 'width': 1*cm},
        {'key': 'name', 'header': 'F.I.O', 'width': 6*cm},
        {'key': 'phone', 'header': 'Telefon', 'width': 4*cm},
        {'key': 'role', 'header': 'Rol', 'width': 3*cm},
        {'key': 'status', 'header': 'Holat', 'width': 2*cm},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"foydalanuvchilar_{today}"

    role_name = dict(User.ROLE_CHOICES).get(role, 'Barcha') if role else 'Barcha'
    title = f"FOYDALANUVCHILAR RO'YXATI"
    subtitle = f"Turi: {role_name} | Jami: {len(data)} ta"

    return export_to_pdf(data, columns, filename, title=title, subtitle=subtitle)


@login_required
def export_students_excel(request):
    """O'quvchilar ro'yxatini Excel formatida eksport qilish"""
    org = request.organization

    students = User.objects.filter(role='student', is_deleted=False)
    if org:
        students = students.filter(organization=org)

    students = students.select_related('branch').order_by('first_name')

    data = []
    for student in students:
        # Guruhlar
        from apps.education.models import GroupStudent
        groups = GroupStudent.objects.filter(student=student, status='active').select_related('group')
        group_names = ', '.join([gs.group.name for gs in groups]) if groups else '-'

        data.append({
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}",
            'phone': student.phone or '',
            'groups': group_names,
            'balance': float(student.balance) if student.balance else 0,
            'status': 'Faol' if student.is_active else 'Nofaol',
        })

    columns = [
        {'key': 'id', 'header': 'ID', 'width': 8},
        {'key': 'name', 'header': 'F.I.O', 'width': 28},
        {'key': 'phone', 'header': 'Telefon', 'width': 18},
        {'key': 'groups', 'header': 'Guruhlar', 'width': 25},
        {'key': 'balance', 'header': 'Balans', 'width': 15, 'money': True},
        {'key': 'status', 'header': 'Holat', 'width': 10},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"oqhuvchilar_{today}"
    title = f"O'QUVCHILAR RO'YXATI - {today}"

    return export_to_excel(data, columns, filename, title=title, sheet_name="O'quvchilar")


@login_required
def export_teachers_excel(request):
    """O'qituvchilar ro'yxatini Excel formatida eksport qilish"""
    org = request.organization

    teachers = User.objects.filter(role='teacher', is_deleted=False)
    if org:
        teachers = teachers.filter(organization=org)

    teachers = teachers.order_by('first_name')

    data = []
    for teacher in teachers:
        # Guruhlar soni
        from apps.education.models import Group
        groups_count = Group.objects.filter(teacher=teacher, is_deleted=False).count()

        data.append({
            'id': teacher.id,
            'name': f"{teacher.first_name} {teacher.last_name}",
            'phone': teacher.phone or '',
            'groups_count': groups_count,
            'salary': float(teacher.profile_data.get('salary', 0)) if teacher.profile_data else 0,
            'status': 'Faol' if teacher.is_active else 'Nofaol',
        })

    columns = [
        {'key': 'id', 'header': 'ID', 'width': 8},
        {'key': 'name', 'header': 'F.I.O', 'width': 28},
        {'key': 'phone', 'header': 'Telefon', 'width': 18},
        {'key': 'groups_count', 'header': 'Guruhlar soni', 'width': 15},
        {'key': 'salary', 'header': 'Oylik', 'width': 15, 'money': True},
        {'key': 'status', 'header': 'Holat', 'width': 10},
    ]

    today = timezone.now().strftime('%Y-%m-%d')
    filename = f"oqituvchilar_{today}"
    title = f"O'QITUVCHILAR RO'YXATI - {today}"

    return export_to_excel(data, columns, filename, title=title, sheet_name="O'qituvchilar")
