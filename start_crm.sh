#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM - Ishga Tushirish va Bog'lash Skripti (Port 8001)
# ==============================================================================

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

ACTUAL_USER="${SUDO_USER:-ubuntu}"

echo "=========================================================="
echo "  1. Papka huquqlarini sozlash (/home/ubuntu)...          "
echo "=========================================================="
# status=200/CHDIR xatosini yo'qotish uchun /home/ubuntu ruxsatini ochish
chmod 755 "$(dirname "$APP_DIR")" || true
chmod -R 775 "$APP_DIR" || true
chown -R "$ACTUAL_USER:www-data" "$APP_DIR" || true

mkdir -p /var/log/gunicorn /var/log/celery "$APP_DIR/media" "$APP_DIR/staticfiles"
chown -R "$ACTUAL_USER:www-data" /var/log/gunicorn /var/log/celery "$APP_DIR/media" "$APP_DIR/staticfiles"
chmod -R 775 /var/log/gunicorn /var/log/celery "$APP_DIR/media" "$APP_DIR/staticfiles"

echo "=========================================================="
echo "  2. Exclusive CRM Systemd servisini yaratish (Port 8001) "
echo "=========================================================="

cat <<EOF > /etc/systemd/system/exclusive_crm.service
[Unit]
Description=Exclusive CRM Gunicorn daemon
After=network.target

[Service]
User=${ACTUAL_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn --config ${APP_DIR}/gunicorn_config.py config.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF > /etc/systemd/system/exclusive_celery.service
[Unit]
Description=Exclusive CRM Celery Worker
After=network.target redis-server.service redis.service

[Service]
Type=simple
User=${ACTUAL_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/celery -A config worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF > /etc/systemd/system/exclusive_celery_beat.service
[Unit]
Description=Exclusive CRM Celery Beat
After=network.target redis-server.service redis.service

[Service]
Type=simple
User=${ACTUAL_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/celery -A config beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable exclusive_crm exclusive_celery exclusive_celery_beat
systemctl restart exclusive_crm
systemctl restart exclusive_celery 2>/dev/null || true
systemctl restart exclusive_celery_beat 2>/dev/null || true
sleep 2

echo ">>> Port 8001 (Exclusive CRM) tekshiruvi:"
if curl -s -I http://127.0.0.1:8001 | grep -q "HTTP"; then
    echo "[OK] Exclusive CRM Port 8001 da muvaffaqiyatli ishlamoqda!"
else
    echo "[LOG] Exclusive CRM status:"
    systemctl status exclusive_crm --no-pager | head -n 15 || true
fi

echo "=========================================================="
echo "  3. Nginx-da crm.e-exclusive.uz ni ulash                 "
echo "=========================================================="

cat <<EOF > /etc/nginx/sites-available/exclusive_crm
server {
    listen 80;
    server_name crm.e-exclusive.uz;

    client_max_body_size 100M;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;

    location /static/ {
        alias ${APP_DIR}/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias ${APP_DIR}/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

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

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF

ln -sf /etc/nginx/sites-available/exclusive_crm /etc/nginx/sites-enabled/
nginx -t

# Nginx ni xavfsiz yangilash
systemctl reload nginx || systemctl restart nginx || true

echo "=========================================================="
echo "  4. SSL (HTTPS) Sertifikatini ulash (Certbot)            "
echo "=========================================================="
if ! command -v certbot >/dev/null 2>&1; then
    apt update -y && apt install -y certbot python3-certbot-nginx 2>/dev/null || true
fi

if command -v certbot >/dev/null 2>&1; then
    echo ">>> SSL sertifikati ulanmoqda..."
    certbot --nginx -d crm.e-exclusive.uz --non-interactive --agree-tos -m info@e-exclusive.uz --redirect 2>/dev/null || true
    systemctl reload nginx 2>/dev/null || true
fi

echo "=========================================================="
echo "  5. Yakuniy tekshiruv                                    "
echo "=========================================================="
echo "Exclusive CRM javobi (Port 8001):"
curl -s -I http://127.0.0.1:8001 | head -n 4 || echo "Port 8001"

echo "Nginx orqali crm.e-exclusive.uz javobi:"
curl -s -I -H "Host: crm.e-exclusive.uz" http://127.0.0.1 | head -n 5 || echo "Nginx"

echo -e "\n=========================================================="
echo "  HAMMASI TAYYOR!                                         "
echo "  Mock AI: Port 8000 da ishlamoqda.                       "
echo "  Exclusive CRM: https://crm.e-exclusive.uz (Port 8001) da!"
echo "==========================================================\n"
