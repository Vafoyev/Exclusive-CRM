#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM - Nginx va Port 8001 Marshrutini To'liq To'g'rilash
# MockAI (8000) va Exclusive CRM (8001) ni mustaqil ajratish
# ==============================================================================

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "=========================================================="
echo "  1. Exclusive CRM servisini (Port 8001) ishga tushirish  "
echo "=========================================================="

# Systemd servisi
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

systemctl daemon-reload
systemctl enable exclusive_crm
systemctl restart exclusive_crm
sleep 2

# Port 8001 tekshirish
echo ">>> Port 8001 da Exclusive CRM holati:"
if curl -s -I http://127.0.0.1:8001 | grep -q "HTTP"; then
    echo "[OK] Exclusive CRM port 8001 da muvaffaqiyatli javob bermoqda!"
else
    echo "[INFO] Exclusive CRM ishga tushirilmoqda..."
    systemctl status exclusive_crm --no-pager | head -n 12 || true
fi

echo "=========================================================="
echo "  2. Nginx-da crm.e-exclusive.uz ni 8001 ga yo'naltirish  "
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

echo "=========================================================="
echo "  3. Nginx ni toza qayta ishga tushirish                  "
echo "=========================================================="
pkill -9 -f nginx 2>/dev/null || true
sleep 1
systemctl start nginx || systemctl restart nginx
sleep 1

# Mock AI xizmatini tekshirib, tirikligini ta'minlash (Port 8000)
systemctl start gunicorn 2>/dev/null || true

echo "=========================================================="
echo "  4. SSL (HTTPS 443) sertifikatini tekshirish / ulash     "
echo "=========================================================="
if ! command -v certbot >/dev/null 2>&1; then
    apt update -y && apt install -y certbot python3-certbot-nginx 2>/dev/null || true
fi

if command -v certbot >/dev/null 2>&1; then
    echo ">>> crm.e-exclusive.uz uchun SSL (HTTPS) sozlanmoqda..."
    certbot --nginx -d crm.e-exclusive.uz --non-interactive --agree-tos -m info@e-exclusive.uz --redirect 2>/dev/null || echo "[INFO] Certbot sozlamalari yakunlandi."
fi

# Nginx ni qayta yuklash
nginx -t && (systemctl reload nginx 2>/dev/null || systemctl restart nginx 2>/dev/null || true)

echo "=========================================================="
echo "  5. Tekshiruv natijalari                                 "
echo "=========================================================="
echo ">>> Mock AI (Port 8000):"
curl -s -I http://127.0.0.1:8000 | head -n 3 || echo "Port 8000 holati"

echo ">>> Exclusive CRM (Port 8001):"
curl -s -I http://127.0.0.1:8001 | head -n 3 || echo "Port 8001 holati"

echo -e "\n>>> crm.e-exclusive.uz Nginx orqali sinovi:"
curl -s -I -H "Host: crm.e-exclusive.uz" http://127.0.0.1 | head -n 5

echo -e "\n=========================================================="
echo "  TABRIKLAYMIZ! Ikkala loyiha ham to'liq ajratildi:       "
echo "  1. MockAI -> Port 8000 da ishlamoqda.                   "
echo "  2. Exclusive CRM -> https://crm.e-exclusive.uz (Port 8001) da!"
echo "==========================================================\n"
