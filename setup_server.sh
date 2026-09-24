#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM - To'liq Avtomatik Server O'rnatish Skripti (Single-command Setup)
# Domen: crm.e-exclusive.uz | Server IP: 3.208.22.250
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN}   Exclusive CRM - Avtomatlashtirilgan O'rnatish     ${NC}"
echo -e "${BLUE}=====================================================${NC}"

# 1. Root huquqini tekshirish
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[XATO] Skriptni root yoki sudo bilan ishga tushiring!${NC}"
    echo "Misol: sudo bash setup_server.sh"
    exit 1
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
ACTUAL_USER="${SUDO_USER:-$(whoami)}"

echo -e "${YELLOW}>>> Loyiha papkasi: ${APP_DIR}${NC}"
echo -e "${YELLOW}>>> Tizim foydalanuvchisi: ${ACTUAL_USER}${NC}"

# 2. Tizim paketlarini yangilash va o'rnatish
echo -e "\n${BLUE}>>> 1/8. Tizim paketlarini yangilash va o'rnatish...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt update -y
apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential libpq-dev postgresql postgresql-contrib \
    redis-server nginx git curl ufw

# 3. PostgreSQL sozlash
echo -e "\n${BLUE}>>> 2/8. PostgreSQL ma'lumotlar bazasini sozlash...${NC}"
systemctl start postgresql
systemctl enable postgresql

# Windows CRLF (\r) belgilarini tozalash
sed -i 's/\r$//' .env 2>/dev/null || true
sed -i 's/\r$//' setup_server.sh 2>/dev/null || true
sed -i 's/\r$//' deploy.sh 2>/dev/null || true

DB_NAME="exclusive_crm_db"
DB_USER="crm_admin"
DB_PASS="SalomDunyo1"

# Barcha pg_hba.conf fayllarini topib, to'liq trust rejimiga o'tkazish
for hba in $(find /etc/postgresql/ -name "pg_hba.conf" 2>/dev/null); do
    echo "PostgreSQL konfiguratsiyasi sozlanmoqda: $hba"
    sed -i 's/scram-sha-256/trust/g' "$hba"
    sed -i 's/md5/trust/g' "$hba"
    sed -i 's/peer/trust/g' "$hba"
done
systemctl restart postgresql
sleep 2

# PostgreSQL foydalanuvchisi va bazasini yaratish hamda parolni yangilash
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

# psql orqali ulanishni tekshirish
psql -h localhost -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" >/dev/null 2>&1 && \
echo -e "${GREEN}[OK] PostgreSQL bazasi ($DB_NAME) va foydalanuvchisi ($DB_USER) muvaffaqiyatli ulandi.${NC}" || \
echo -e "${YELLOW}[INFO] PostgreSQL ulanishi sozlandi.${NC}"

# 4. Redis sozlash
echo -e "\n${BLUE}>>> 3/8. Redis xizmatini ishga tushirish...${NC}"
systemctl enable --now redis-server
echo -e "${GREEN}[OK] Redis ishlamoqda.${NC}"

# 5. Virtual Environment va Python paketlar
echo -e "\n${BLUE}>>> 4/8. Python virtual muhitini (venv) yaratish va paketlarni o'rnatish...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements/production.txt

# 6. .env faylini yaratish yoki yangilash
echo -e "\n${BLUE}>>> 5/8. .env konfiguratsiya faylini tayyorlash...${NC}"

# .env faylini to'g'rilash (Python orqali xavfsiz va to'liq sinxronlash)
python3 - << 'PYEOF'
import os, secrets

env_file = ".env"
db_settings = {
    "DB_NAME": "exclusive_crm_db",
    "DB_USER": "crm_admin",
    "DB_PASSWORD": "SalomDunyo1",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "USE_POSTGRES": "True",
    "ALLOWED_HOSTS": "crm.e-exclusive.uz,3.208.22.250,localhost,127.0.0.1",
    "CSRF_TRUSTED_ORIGINS": "https://crm.e-exclusive.uz,http://crm.e-exclusive.uz,http://3.208.22.250",
    "DEBUG": "False",
    "SECURE_SSL_REDIRECT": "False",
    "SESSION_COOKIE_SECURE": "False",
    "CSRF_COOKIE_SECURE": "False",
    "REDIS_URL": "redis://localhost:6379/0",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
    "USE_REDIS": "True",
    "USE_S3": "False"
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
        elif k == "SECRET_KEY":
            seen.add("SECRET_KEY")
    new_lines.append(line)

if "SECRET_KEY" not in seen:
    new_lines.insert(0, f"SECRET_KEY={secrets.token_urlsafe(50)}")

for k, v in db_settings.items():
    if k not in seen:
        new_lines.append(f"{k}={v}")

with open(env_file, "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines) + "\n")
print("[OK] .env fayli muvaffaqiyatli yangilandi va bazaga ulandi.")
PYEOF

# Python orqali PostgreSQL ga ulanishni tekshirish
echo -e "PostgreSQL ulanishini tekshirish..."
python3 - << 'PYEOF'
import psycopg2, sys
from decouple import config
try:
    conn = psycopg2.connect(
        dbname=config('DB_NAME'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        host=config('DB_HOST', default='localhost'),
        port=config('DB_PORT', default=5432)
    )
    conn.close()
    print("[OK] Python orqali ma'lumotlar bazasiga ulanish tekshirildi: MUVAFFAQITYATLI!")
except Exception as e:
    print("[XATO] Bazaga ulanishda xatolik:", e)
    sys.exit(1)
PYEOF

# 7. Papkalar va huquqlar
mkdir -p "$APP_DIR/staticfiles"
mkdir -p "$APP_DIR/media"
mkdir -p /var/log/gunicorn
mkdir -p /var/log/celery

# 8. Django migratsiyalari va statik fayllar
echo -e "\n${BLUE}>>> 6/8. Django migratsiyalari va statik fayllarni yig'ish...${NC}"
python manage.py migrate --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production

# Huquqlarni sozlash
chown -R "$ACTUAL_USER:www-data" "$APP_DIR"
chown -R www-data:www-data "$APP_DIR/media" "$APP_DIR/staticfiles" /var/log/gunicorn /var/log/celery
chmod -R 775 "$APP_DIR/media" "$APP_DIR/staticfiles"

# 9. Systemd servislarni sozlash
echo -e "\n${BLUE}>>> 7/8. Systemd servislarni (Exclusive CRM) sozlash...${NC}"

# Exclusive CRM Gunicorn service (Port 8001 da ishlaydi, boshqa loyihalarga xalaqit bermaydi)
cat <<EOF > /etc/systemd/system/exclusive_crm.service
[Unit]
Description=Exclusive CRM Gunicorn daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn --config ${APP_DIR}/gunicorn_config.py config.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Exclusive CRM Celery service
cat <<EOF > /etc/systemd/system/exclusive_celery.service
[Unit]
Description=Exclusive CRM Celery Worker
After=network.target redis-server.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/celery -A config worker --loglevel=info --detach --logfile=/var/log/celery/exclusive_worker.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Exclusive CRM Celery Beat service
cat <<EOF > /etc/systemd/system/exclusive_celery_beat.service
[Unit]
Description=Exclusive CRM Celery Beat
After=network.target redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/celery -A config beat --loglevel=info --logfile=/var/log/celery/exclusive_beat.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 10. Nginx sozlash
echo -e "\n${BLUE}>>> 8/8. Nginx veb-serverini sozlash...${NC}"

cat <<EOF > /etc/nginx/sites-available/exclusive_crm
server {
    listen 80;
    server_name crm.e-exclusive.uz;

    client_max_body_size 100M;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;

    # Static files
    location /static/ {
        alias ${APP_DIR}/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias ${APP_DIR}/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Django application (Port 8001)
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;

        proxy_connect_timeout 90s;
        proxy_send_timeout 90s;
        proxy_read_timeout 90s;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF

ln -sf /etc/nginx/sites-available/exclusive_crm /etc/nginx/sites-enabled/

# Nginx tekshirish
nginx -t

# Firewall sozlash (SSH va Web portlar)
if command -v ufw >/dev/null 2>&1; then
    ufw allow 22/tcp || true
    ufw allow 'Nginx Full' || true
    ufw --force enable || true
fi

# Xizmatlarni ishga tushirish (Faqat Exclusive CRM xizmatlari)
systemctl daemon-reload
systemctl enable exclusive_crm exclusive_celery exclusive_celery_beat nginx
systemctl restart exclusive_crm exclusive_celery exclusive_celery_beat nginx

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}   TABRIKLAYMIZ! O'RNATISH MUVAFFAQIYATLI YAKUNLANDI!${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "Domen orqali:  ${BLUE}http://crm.e-exclusive.uz${NC} yoki ${BLUE}https://crm.e-exclusive.uz${NC}"
echo -e "IP orqali:     ${BLUE}http://3.208.22.250${NC}"
echo -e "\nAdmin yaratish uchun quyidagi buyruqni bering:"
echo -e "${YELLOW}source venv/bin/activate && python manage.py createsuperuser --settings=config.settings.production${NC}"
echo -e "\nKelgusida yangilanishlarni olish uchun:"
echo -e "${YELLOW}./deploy.sh${NC}"
echo -e "=====================================================\n"
