from apps.education.models import Group


def check_schedule_conflict(organization, room, teacher, days, start_time, end_time, exclude_group_id=None):
    """
    Dars vaqtlari to'qnashuvini tekshiradi.

    Args:
        organization: Qaysi markazligi
        room: Tanlangan xona
        teacher: Tanlangan o'qituvchi
        days: Dars kunlari ro'yxati [1, 3, 5]
        start_time, end_time: Vaqtlar
        exclude_group_id: Tahrirlanayotganda o'zini tekshirmaslik uchun

    Returns:
        Xatolik matni (str) yoki None
    """

    # 1. Faqat shu tashkilotning aktiv guruhlarini olamiz
    existing_groups = Group.objects.filter(
        organization=organization,
        status__in=['active', 'pending']
    )

    # Tahrirlash paytida o'zini hisobga olmaymiz
    if exclude_group_id:
        existing_groups = existing_groups.exclude(id=exclude_group_id)

    # 2. Har bir guruh bilan solishtiramiz
    for group in existing_groups:
        # Kunlari kesishadimi?
        # M: group_days=[1,3,5], new_days=[2,4,6] -> Kesishmaydi.
        common_days = set(group.schedule_days) & set(map(int, days))

        if not common_days:
            continue  # Kunlar har xil, muammo yo'q.

        # Vaqtlar kesishadimi?
        # Mantiq: (YangiBosh < EskiTugash) VA (YangiTugash > EskiBosh)
        if start_time < group.end_time and end_time > group.start_time:
            # TO'QNASHUV BOR! Sababini aytamiz.

            # Xona bandmi?
            if room and group.room == room:
                return f"Xato! {room.name} xonasi '{group.name}' guruhi tomonidan band ({group.start_time} - {group.end_time})."

            # O'qituvchi bandmi?
            if teacher and group.teacher == teacher:
                return f"Xato! O'qituvchi {teacher.first_name} bu vaqtda '{group.name}' guruhida darsda."

    return None  # Hammasi toza


DAY_NAMES = {
    1: 'Dushanba',
    2: 'Seshanba',
    3: 'Chorshanba',
    4: 'Payshanba',
    5: 'Juma',
    6: 'Shanba',
    7: 'Yakshanba',
}


def check_student_schedule_conflict(student, target_group):
    """
    O'quvchining boshqa guruhlaridagi dars vaqtlari bilan to'qnashuvini tekshiradi.
    Masalan: rus tili va ingliz tili bir xil kun va soatda bo'lsa, o'quvchi ikkalasiga bir vaqtda qatnasha olmaydi.

    Args:
        student: User modeli (role='student')
        target_group: Group modeli (qo'shilayotgan guruh)

    Returns:
        Xatolik xabari (str) yoki None
    """
    from apps.education.models import GroupStudent

    # Guruhning dars kunlari yoki vaqtlari kiritilmagan bo'lsa tekshirib bo'lmaydi
    if not target_group.schedule_days or not target_group.start_time or not target_group.end_time:
        return None

    try:
        target_days = set(int(d) for d in target_group.schedule_days)
    except (ValueError, TypeError):
        target_days = set(target_group.schedule_days)

    if not target_days:
        return None

    # O'quvchining faol a'zo bo'lgan boshqa guruhlari
    active_enrollments = GroupStudent.objects.filter(
        student=student,
        status='active',
        is_deleted=False,
        group__is_deleted=False,
        group__status__in=['active', 'pending']
    ).exclude(group_id=target_group.id).select_related('group', 'group__course')

    for enrollment in active_enrollments:
        other_group = enrollment.group
        if not other_group.schedule_days or not other_group.start_time or not other_group.end_time:
            continue

        try:
            other_days = set(int(d) for d in other_group.schedule_days)
        except (ValueError, TypeError):
            other_days = set(other_group.schedule_days)

        common_days = target_days & other_days
        if not common_days:
            # Dars kunlari kesishmaydi
            continue

        # Vaqtlar kesishadimi?
        # Mantiq: (YangiBosh < EskiTugash) VA (YangiTugash > EskiBosh)
        if target_group.start_time < other_group.end_time and target_group.end_time > other_group.start_time:
            days_str = ", ".join(DAY_NAMES.get(d, str(d)) for d in sorted(common_days))
            course_name = other_group.course.name if other_group.course else "boshqa kurs"
            other_time = f"{other_group.start_time.strftime('%H:%M')} - {other_group.end_time.strftime('%H:%M')}"
            target_time = f"{target_group.start_time.strftime('%H:%M')} - {target_group.end_time.strftime('%H:%M')}"
            student_name = student.get_full_name() or student.phone

            return (
                f"Vaqt to'qnashuvi! {student_name} bir vaqtda ikkita darsga qatnasha olmaydi. "
                f"U ayni shu vaqtda '{other_group.name}' ({course_name}) guruhida darsda bo'ladi ({days_str}: {other_time}). "
                f"Ushbu guruh darsi esa: {target_time}."
            )

    return None