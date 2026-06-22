from django.core.management.base import BaseCommand
from apps.automation.models import NotificationTemplate


class Command(BaseCommand):
    help = 'Create default notification templates'

    def handle(self, *args, **options):
        templates_data = [
            {
                'title': "Darsga kelmaganlik",
                'code': "ATTENDANCE_ABSENT",
                'message_type': "system",
                'body': "Hurmatli {parent_name}, farzandingiz {student_name} bugungi {date} sanadagi {group} darsiga qatnashmadi."
            },
            {
                'title': "To'lov qabul qilindi",
                'code': "PAYMENT_RECEIVED",
                'message_type': "system",
                'body': "Assalomu alaykum {name}! Sizning {amount} so'm miqdoridagi to'lovingiz qabul qilindi. Sana: {date}. Hozirgi balans: {balance} so'm"
            },
            {
                'title': "To'lov qabul qilindi (Ota-ona)",
                'code': "PAYMENT_RECEIVED_PARENT",
                'message_type': "system",
                'body': "Hurmatli {parent_name}, farzandingiz {student_name} uchun {amount} so'm to'lov qabul qilindi. Sana: {date}. Balans: {balance} so'm"
            },
            {
                'title': "Qarz eslatmasi",
                'code': "DEBT_REMINDER",
                'message_type': "system",
                'body': "Hurmatli {first_name}, sizning hisobingizda {balance} so'm qarz mavjud. Iltimos, to'lovni amalga oshiring."
            },
            {
                'title': "Yangi dars qo'shildi",
                'code': "NEW_LESSON",
                'message_type': "system",
                'body': "Hurmatli {first_name}, {date} sanasida {group} guruhida yangi dars qo'shildi."
            }
        ]

        created_count = 0
        for data in templates_data:
            obj, created = NotificationTemplate.objects.update_or_create(
                code=data['code'],
                defaults={
                    'title': data['title'],
                    'message_type': data['message_type'],
                    'body': data['body'],
                    'organization': None  # Global template
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created: {data['code']}"))
            else:
                self.stdout.write(f"Updated: {data['code']}")

        self.stdout.write(self.style.SUCCESS(f"\nTotal: {created_count} created, {len(templates_data) - created_count} updated"))
