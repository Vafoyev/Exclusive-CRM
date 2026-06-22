from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.operations.models import Lesson, Attendance
from apps.finance.models import Transaction, Account, TransactionCategory
from apps.users.models import User


@transaction.atomic
def finish_lesson_logic(lesson_id, user):
    """
    O'qituvchi "Darsni tugatish" tugmasini bosganda ishlaydi.
    1. Statusni 'finished' qiladi.
    2. Kelgan o'quvchilardan pul yechadi.
    3. O'qituvchiga KPI yozadi (keyinchalik).
    """
    try:
        lesson = Lesson.objects.select_for_update().get(id=lesson_id)
    except Lesson.DoesNotExist:
        raise ValidationError("Dars topilmadi")

    if lesson.status == 'finished':
        raise ValidationError("Bu dars allaqachon yakunlangan va pullar yechilgan.")

    # 1. Dars narxini aniqlaymiz (Kurs narxidan kelib chiqib yoki bitta dars narxi)
    # (Bu qism student darajasiga tushirildi, sababi bonus har xil bo'lishi mumkin)

    # 2. Kategoriyani topamiz (Kurs to'lovi)
    category, _ = TransactionCategory.objects.get_or_create(
        organization=lesson.organization,
        transaction_type='income',
        defaults={'name': 'Kurs to\'lovi avtomat'}
    )

    # 3. Davomatni tekshiramiz
    attendances = Attendance.objects.filter(lesson=lesson).select_related('student')

    if not attendances.exists():
        raise ValidationError("Davomat qilinmagan! Avval o'quvchilarni belgilang.")

    # Asosiy kurs narxi (Butun oy uchun)
    base_course_price = 50000 * 12
    if lesson.group.course.price > 0:
        base_course_price = lesson.group.course.price

    for att in attendances:
        # Agar o'quvchi BOR bo'lsa yoki SABABSIZ yo'q bo'lsa -> Pul yechamiz
        if att.status in ['present', 'late', 'absent']:
            # Dars narxini hisoblash, bonuslarni inobatga olgan holda
            from decimal import Decimal
            student_course_price = base_course_price
            
            # Foizli bonus
            if att.student.bonus_percentage > 0:
                student_course_price = student_course_price * (1 - (Decimal(att.student.bonus_percentage) / Decimal(100)))
            
            # Summa bonus
            if att.student.bonus_amount > 0:
                student_course_price = max(Decimal('0'), student_course_price - att.student.bonus_amount)
                
            lesson_price = student_course_price / 12

            # Tranzaksiya yaratamiz (Avtomatik tasdiqlangan holda)
            # Chunki bu real balansdan yechilyapti

            Transaction.objects.create(
                organization=lesson.organization,
                branch=lesson.group.room.organization.branches.first() if lesson.room else None,  # Vaqtincha logic
                account=Account.objects.filter(organization=lesson.organization).first(),  # Virtual hisob
                category=category,
                student=att.student,
                amount=lesson_price,
                transaction_type='income',  # Aslida bu "Realizatsiya", balansdan kamayishi kerak.
                # DIQQAT: Bu yerda logika shunday:
                # Student balansidan pul kamayadi -> Markaz foydasiga yoziladi.
                # Sodda bo'lishi uchun: Biz shunchaki student balansini kamaytiramiz.
                status='confirmed',
                created_by=user,
                confirmed_by=user,
                confirmed_at=timezone.now(),
                description=f"{lesson.group.name} - {lesson.date} darsi uchun to'lov"
            )

            # O'quvchi balansini kamaytiramiz
            att.student.balance -= lesson_price
            att.student.save()

    # 4. Darsni yopamiz
    lesson.status = 'finished'
    lesson.finished_at = timezone.now()
    lesson.save()

    return "Dars yakunlandi va hisob-kitob qilindi."