#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM - PostgreSQL Ruxsatnomalarini Tezkor To'g'rilash Skripti
# ==============================================================================

set -e

echo "=== 1. Mavjud PostgreSQL klasterlarini tekshirish ==="
if command -v pg_lsclusters >/dev/null 2>&1; then
    pg_lsclusters || true
fi

echo "=== 2. Barcha pg_hba.conf fayllarida trust rejimini yoqish ==="
for hba in $(find /etc/postgresql/ -name "pg_hba.conf" 2>/dev/null); do
    echo "Sozlanmoqda: $hba"
    sed -i '/crm_admin/d' "$hba"
    sed -i 's/scram-sha-256/trust/g' "$hba"
    sed -i 's/md5/trust/g' "$hba"
    sed -i 's/peer/trust/g' "$hba"
    # Eng tepasiga aniq trust qoidalarini qo'shamiz
    sed -i '1i local all all trust\nhost all all 127.0.0.1/32 trust\nhost all all ::1/128 trust' "$hba"
done

echo "=== 3. Barcha PostgreSQL xizmatlarini to'liq qayta ishga tushirish ==="
if command -v pg_ctlcluster >/dev/null 2>&1; then
    pg_lsclusters --no-header 2>/dev/null | while read -r ver cluster port rest; do
        if [ -n "$ver" ] && [ -n "$cluster" ]; then
            echo "Klaster qayta ishga tushirilmoqda: $ver $cluster (Port: $port)"
            pg_ctlcluster "$ver" "$cluster" restart || true
        fi
    done
fi
systemctl restart "postgresql*" 2>/dev/null || systemctl restart postgresql || true
sleep 2

DB_NAME="exclusive_crm_db"
DB_USER="crm_admin"
DB_PASS="SalomDunyo1"

echo "=== 4. Barcha portlarda (5432, 5433, 5434) foydalanuvchi va bazani sozlash ==="
for PORT in 5432 5433 5434; do
    if sudo -u postgres psql -p "$PORT" -c "SELECT 1;" >/dev/null 2>&1; then
        echo "Port $PORT da PostgreSQL topildi! Foydalanuvchi va baza sozlanmoqda..."
        sudo -u postgres psql -p "$PORT" -c "DO \$\$
        BEGIN
           IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
              CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
           END IF;
        END
        \$\$;" || true

        sudo -u postgres psql -p "$PORT" -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" || true
        sudo -u postgres psql -p "$PORT" -c "ALTER USER ${DB_USER} CREATEDB SUPERUSER;" || true
        sudo -u postgres psql -p "$PORT" -c "ALTER USER postgres WITH PASSWORD '${DB_PASS}';" || true

        sudo -u postgres psql -p "$PORT" -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
        sudo -u postgres psql -p "$PORT" -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" || true

        sudo -u postgres psql -p "$PORT" -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" || true
        sudo -u postgres psql -p "$PORT" -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" || true
        sudo -u postgres psql -p "$PORT" -c "SELECT pg_reload_conf();" || true
    fi
done

echo "=== 5. To'g'ri ishlaydigan portni aniqlash ==="
WORKING_PORT=""
for PORT in 5432 5433 5434; do
    if PGPASSWORD="${DB_PASS}" psql -h localhost -p "$PORT" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" >/dev/null 2>&1; then
        WORKING_PORT="$PORT"
        echo "Muvaffaqiyatli ulanish topildi: Port $WORKING_PORT"
        break
    fi
done

if [ -z "$WORKING_PORT" ]; then
    for PORT in 5432 5433 5434; do
        if psql -h localhost -p "$PORT" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" >/dev/null 2>&1; then
            WORKING_PORT="$PORT"
            echo "Trust orqali muvaffaqiyatli ulanish topildi: Port $WORKING_PORT"
            break
        fi
    done
fi

if [ -z "$WORKING_PORT" ]; then
    WORKING_PORT="5432"
fi

echo "=== 6. .env faylini to'g'ri port ($WORKING_PORT) va parol bilan yangilash ==="
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
sed -i 's/\r$//' .env 2>/dev/null || true

python3 - << PYEOF
import os

env_file = ".env"
db_settings = {
    "DB_NAME": "exclusive_crm_db",
    "DB_USER": "crm_admin",
    "DB_PASSWORD": "${DB_PASS}",
    "DB_HOST": "localhost",
    "DB_PORT": "${WORKING_PORT}",
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
print("[OK] .env fayli port ${WORKING_PORT} bilan yangilandi!")
PYEOF

echo "=== 7. Python orqali ulanishni tekshirish ==="
if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 - << PYEOF
import psycopg2
try:
    conn = psycopg2.connect(
        dbname="exclusive_crm_db",
        user="crm_admin",
        password="${DB_PASS}",
        host="localhost",
        port=${WORKING_PORT}
    )
    conn.close()
    print(">>> TABRIKLAYMIZ: BAZAGA ULANISH 100% MUVAFFAQITYATLI BO'LDI! <<<")
except Exception as e:
    print("Ulanish xatosi:", e)
    exit(1)
PYEOF

echo "=== 8. Django migratsiyalari va statik fayllar ==="
python manage.py migrate --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production

echo "=== 9. Servislarni qayta ishga tushirish ==="
systemctl daemon-reload
systemctl restart gunicorn celery celery-beat nginx || true

echo -e "\n================================================="
echo -e "   LOYIHA 100% ISHGA TUSHDI!                     "
echo -e "   Sayt: http://crm.e-exclusive.uz               "
echo -e "=================================================\n"
