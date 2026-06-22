"""
Database backup management command.
Qo'lda backup yaratish va Telegramga yuborish.

Foydalanish:
    python manage.py backup_db                # Backup + Telegramga yuborish
    python manage.py backup_db --no-telegram  # Faqat lokal backup
"""
from django.core.management.base import BaseCommand
from apps.core.tasks import _create_backup, _send_to_telegram, _cleanup_old_backups
import os


class Command(BaseCommand):
    help = "Database backup yaratish va Telegram botga yuborish"

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-telegram',
            action='store_true',
            default=False,
            help="Telegramga yubormay, faqat lokal backup yaratish",
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            default=False,
            help="30 kundan eski backuplarni tozalash",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Backup yaratilmoqda..."))

        try:
            # 1. Backup yaratish
            backup_file = _create_backup()
            if not backup_file:
                self.stdout.write(self.style.ERROR("Backup yaratilmadi!"))
                return

            file_size = os.path.getsize(backup_file)
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"

            self.stdout.write(
                self.style.SUCCESS(f"✅ Backup yaratildi: {backup_file} ({size_str})")
            )

            # 2. Telegramga yuborish
            if not options['no_telegram']:
                self.stdout.write(self.style.NOTICE("Telegramga yuborilmoqda..."))
                try:
                    sent = _send_to_telegram(backup_file)
                    if sent:
                        self.stdout.write(
                            self.style.SUCCESS("✅ Telegramga muvaffaqiyatli yuborildi!")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                "⚠️ Telegramga yuborilmadi. "
                                "TELEGRAM_BOT_TOKEN va TELEGRAM_BACKUP_CHAT_ID ni tekshiring."
                            )
                        )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ Telegram xatosi: {e}"))
            else:
                self.stdout.write(self.style.NOTICE("Telegramga yuborish o'tkazib yuborildi (--no-telegram)"))

            # 3. Eski backuplarni tozalash
            if options['cleanup']:
                removed = _cleanup_old_backups(days=30)
                self.stdout.write(
                    self.style.SUCCESS(f"🧹 {removed} ta eski backup o'chirildi")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Xatolik: {e}"))
