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

DB_NAME="exclusive_crm_db"
DB_USER="crm_admin"
DB_PASS="CrmExclusivePass2026Secure"

# Agar .env fayli allaqachon mavjud bo'lsa, undagi parolni olamiz
if [ -f ".env" ]; then
    ENV_USER=$(grep -E '^DB_USER=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d ' ' || true)
    ENV_PASS=$(grep -E '^DB_PASSWORD=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d ' ' || true)
    ENV_NAME=$(grep -E '^DB_NAME=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d ' ' || true)
    [ -n "$ENV_USER" ] && DB_USER="$ENV_USER"
    [ -n "$ENV_PASS" ] && DB_PASS="$ENV_PASS"
    [ -n "$ENV_NAME" ] && DB_NAME="$ENV_NAME"
fi

# Foydalanuvchi va bazani yaratish / parolini majburiy yangilash
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER'" | grep -q 1 || \
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

# Parolni har doim yangilash (authentication failed xatosi bo'lmasligi uchun)
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -c "ALTER USER $DB_USER CREATEDB SUPERUSER;"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;" || true

echo -e "${GREEN}[OK] PostgreSQL bazasi ($DB_NAME) va foydalanuvchisi ($DB_USER) tayyor.${NC}"

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
if [ ! -f ".env" ]; then
    RANDOM_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    cat <<EOF > .env
# ========================================
# EXCLUSIVE CRM - PRODUCTION ENVIRONMENT
# ========================================
SECRET_KEY=${RANDOM_SECRET}
DEBUG=False
ALLOWED_HOSTS=crm.e-exclusive.uz,3.208.22.250,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://crm.e-exclusive.uz,http://crm.e-exclusive.uz,http://3.208.22.250

# HTTPS (Cloudflare orqali SSL yoqilganda True qiling)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Database
USE_POSTGRES=True
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}
DB_HOST=localhost
DB_PORT=5432
PG_DUMP_PATH=/usr/bin/pg_dump

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
USE_REDIS=True

# Static & Media
USE_S3=False
EOF
    echo -e "${GREEN}[OK] Yangi .env fayli yaratildi.${NC}"
else
    echo -e "${YELLOW}[INFO] Mavjud .env fayli tekshirildi va bazaga ulandi.${NC}"
fi

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
echo -e "\n${BLUE}>>> 7/8. Systemd servislarni (Gunicorn, Celery) sozlash...${NC}"

# Gunicorn service
cat <<EOF > /etc/systemd/system/gunicorn.service
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

# Celery service
cat <<EOF > /etc/systemd/system/celery.service
[Unit]
Description=Exclusive CRM Celery Worker
After=network.target redis-server.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/celery -A config worker --loglevel=info --detach --logfile=/var/log/celery/worker.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat service
cat <<EOF > /etc/systemd/system/celery-beat.service
[Unit]
Description=Exclusive CRM Celery Beat
After=network.target redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/celery -A config beat --loglevel=info --logfile=/var/log/celery/beat.log
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
    server_name crm.e-exclusive.uz 3.208.22.250;

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

    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
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
rm -f /etc/nginx/sites-enabled/default

# Nginx tekshirish
nginx -t

# Firewall sozlash (SSH va Web portlar)
if command -v ufw >/dev/null 2>&1; then
    ufw allow 22/tcp || true
    ufw allow 'Nginx Full' || true
    ufw --force enable || true
fi

# Xizmatlarni ishga tushirish
systemctl daemon-reload
systemctl enable gunicorn celery celery-beat nginx
systemctl restart gunicorn celery celery-beat nginx

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
