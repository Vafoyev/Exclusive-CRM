from django.core.management.base import BaseCommand
from apps.automation.daily_report import send_daily_report


class Command(BaseCommand):
    help = "Kunlik hisobotni Telegram bot orqali yuborish"

    def add_arguments(self, parser):
        parser.add_argument(
            '--chat-id',
            type=str,
            help="Qabul qiluvchi Telegram chat ID (ixtiyoriy, berilmasa avtomatik olinadi)",
        )

    def handle(self, *args, **options):
        chat_id = options.get('chat_id')
        self.stdout.write("Kunlik hisobot Telegramga yuborilmoqda...")
        result = send_daily_report(chat_id=chat_id)
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"✅ Hisobot muvaffaqiyatli yuborildi! Yuborilgan chatlar: {result.get('sent_count')}/{result.get('total_targets')}"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Xatolik yuz berdi: {result.get('error')}"))
