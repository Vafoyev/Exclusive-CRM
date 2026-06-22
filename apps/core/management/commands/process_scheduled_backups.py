from django.core.management.base import BaseCommand

from apps.core.backup_services import run_due_backups


class Command(BaseCommand):
    help = "Backup sozlamalari bo'yicha vaqti kelgan backuplarni ishga tushiradi"

    def handle(self, *args, **options):
        processed = run_due_backups()
        self.stdout.write(self.style.SUCCESS(f"{len(processed)} ta scheduled backup tekshirildi va bajarildi"))
