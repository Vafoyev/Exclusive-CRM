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