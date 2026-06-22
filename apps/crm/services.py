from django.db import transaction
from apps.users.models import User
from apps.crm.models import Lead, Activity


def convert_lead_to_student(lead_id, user_id=None):
    """
    Agar Lid "To'lov qildi" (Won) bosqichiga o'tsa,
    uni avtomatik ravishda User (Student) jadvaliga ko'chiramiz.
    """
    lead = Lead.objects.get(id=lead_id)

    # 1. Tekshiramiz: Bu raqam bilan User bormi?
    if User.objects.filter(phone=lead.phone).exists():
        return None, "Bu raqamli foydalanuvchi allaqachon mavjud."

    with transaction.atomic():
        # 2. Yangi User yaratamiz
        new_student = User.objects.create_user(
            phone=lead.phone,
            password='student123',  # Vaqtincha parol (SMS qilib yuborish kerak aslida)
            first_name=lead.full_name.split()[0],
            last_name=lead.full_name.split()[-1] if len(lead.full_name.split()) > 1 else "",
            role='student',
            organization=lead.organization
        )

        # 3. Tarixga yozib qo'yamiz
        Activity.objects.create(
            organization=lead.organization,
            lead=lead,
            user_id=user_id,
            activity_type='status_change',
            comment="Lid muvaffaqiyatli O'quvchiga aylantirildi!"
        )

        return new_student, "Muvaffaqiyatli o'tkazildi"


def move_lead_to_stage(lead_id, new_stage_id, user_id):
    """
    Kanban doskada Lidni bir joydan ikkinchi joyga surish.
    """
    lead = Lead.objects.get(id=lead_id)
    old_stage = lead.stage.name

    lead.stage_id = new_stage_id
    lead.save()

    # Log yozamiz
    Activity.objects.create(
        organization=lead.organization,
        lead=lead,
        user_id=user_id,
        activity_type='status_change',
        comment=f"Status o'zgardi: {old_stage} -> {lead.stage.name}"
    )

    return lead