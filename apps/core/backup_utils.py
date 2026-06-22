import gzip
import glob
import os
import shutil
import subprocess

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone


def resolve_pg_dump_path():
    """
    pg_dump executable yo'lini topadi.
    Avval env/settings override, keyin PATH, keyin keng tarqalgan Linux yo'llari tekshiriladi.
    """
    configured_path = getattr(settings, 'PG_DUMP_PATH', '') or os.getenv('PG_DUMP_PATH', '')
    if configured_path:
        if os.path.isfile(configured_path):
            return configured_path
        resolved_from_path = shutil.which(configured_path)
        if resolved_from_path:
            return resolved_from_path

    resolved = shutil.which('pg_dump')
    if resolved:
        return resolved

    common_candidates = [
        '/usr/bin/pg_dump',
        '/usr/local/bin/pg_dump',
        '/bin/pg_dump',
    ]
    for pattern in (
        '/usr/lib/postgresql/*/bin/pg_dump',
        '/opt/homebrew/opt/libpq/bin/pg_dump',
        '/opt/local/lib/postgresql*/bin/pg_dump',
    ):
        common_candidates.extend(glob.glob(pattern))

    for candidate in common_candidates:
        if os.path.isfile(candidate):
            return candidate

    raise RuntimeError(
        "pg_dump topilmadi. Serverga PostgreSQL client o'rnating yoki .env ga "
        "PG_DUMP_PATH=/pg_dump/to'liq/yo'li qiymatini yozing."
    )


def create_backup_file():
    """
    Database backup faylini yaratadi va siqilgan .gz fayl yo'lini qaytaradi.
    PostgreSQL uchun pg_dump, SQLite uchun dumpdata ishlatiladi.
    """
    timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir = getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    db_settings = settings.DATABASES['default']
    engine = db_settings.get('ENGINE', '')

    if 'postgresql' in engine:
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")
        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings.get('PASSWORD', '')
        pg_dump_path = resolve_pg_dump_path()
        command = [
            pg_dump_path,
            '-h', db_settings.get('HOST', 'localhost'),
            '-p', str(db_settings.get('PORT', '5432')),
            '-U', db_settings.get('USER', 'postgres'),
            '-d', db_settings.get('NAME', 'crmtizim_db'),
            '-F', 'p',
            '--no-owner',
            '--no-acl',
            '-f', backup_file,
        ]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "pg_dump ishlamadi.")
    else:
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.json")
        with open(backup_file, 'w', encoding='utf-8') as output_file:
            call_command(
                'dumpdata',
                '--exclude=contenttypes',
                '--exclude=auth.permission',
                '--indent=2',
                stdout=output_file,
            )

    compressed_file = backup_file + '.gz'
    with open(backup_file, 'rb') as source_file:
        with gzip.open(compressed_file, 'wb') as compressed_output:
            shutil.copyfileobj(source_file, compressed_output)

    os.remove(backup_file)
    return compressed_file


def cleanup_old_backups(days=30):
    """
    Belgilangan kundan eski backup fayllarni o'chiradi.
    """
    backup_dir = getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups')
    if not os.path.exists(backup_dir):
        return 0

    threshold = timezone.now().timestamp() - (max(days, 1) * 86400)
    removed_count = 0

    for file_name in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, file_name)
        if os.path.isfile(file_path) and os.path.getmtime(file_path) < threshold:
            os.remove(file_path)
            removed_count += 1

    return removed_count
