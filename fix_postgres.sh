#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM - PostgreSQL Ruxsatnomalarini Tezkor To'g'rilash Skripti
# ==============================================================================

set -euo pipefail

echo ">>> PostgreSQL xavfsizlik qoidalarini (pg_hba.conf) yangilash..."
for hba in $(find /etc/postgresql/ -name "pg_hba.conf" 2>/dev/null); do
    echo "Fayl tozalanmoqda: $hba"
    sed -i 's/scram-sha-256/trust/g' "$hba"
    sed -i 's/md5/trust/g' "$hba"
    sed -i 's/peer/trust/g' "$hba"
done

echo ">>> PostgreSQL ni qayta ishga tushirish..."
systemctl restart postgresql
sleep 1

DB_NAME="exclusive_crm_db"
DB_USER="crm_admin"
DB_PASS="SalomDunyo1"

echo ">>> Foydalanuvchi ($DB_USER) va bazani sozlash..."
sudo -u postgres psql -c "DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
      CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
   END IF;
END
\$\$;"

sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"
sudo -u postgres psql -c "ALTER USER ${DB_USER} CREATEDB SUPERUSER;"
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD '${DB_PASS}';" || true

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" || true

echo ">>> .env faylidagi parolni yangilash..."
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
sed -i 's/\r$//' .env 2>/dev/null || true

python3 - << 'PYEOF'
import os

env_file = ".env"
db_settings = {
    "DB_NAME": "exclusive_crm_db",
    "DB_USER": "crm_admin",
    "DB_PASSWORD": "SalomDunyo1",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "USE_POSTGRES": "True"
}

lines = []
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip("\r\n") for line in f]

new_lines = []
seen = set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=")[0].strip()
        if k in db_settings:
            new_lines.append(f"{k}={db_settings[k]}")
            seen.add(k)
            continue
    new_lines.append(line)

for k, v in db_settings.items():
    if k not in seen:
        new_lines.append(f"{k}={v}")

with open(env_file, "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines) + "\n")
print("[OK] .env yangilandi!")
PYEOF

echo ">>> PostgreSQL ulanishini tekshirish..."
if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 - << 'PYEOF'
import psycopg2
try:
    conn = psycopg2.connect(
        dbname="exclusive_crm_db",
        user="crm_admin",
        password="SalomDunyo1",
        host="localhost",
        port=5432
    )
    conn.close()
    print(">>> TABRIKLAYMIZ: BAZAGA ULANISH 100% MUVAFFAQITYATLI BO'LDI! <<<")
except Exception as e:
    print("Xatolik:", e)
    exit(1)
PYEOF

echo ">>> Django migratsiyalarini qo'llash..."
python manage.py migrate --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production

echo ">>> Servislarni qayta ishga tushirish..."
systemctl restart gunicorn celery celery-beat nginx || true

echo ">>> HAMMASI TAYYOR! <<<"
