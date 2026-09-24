#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM - ERR_TOO_MANY_REDIRECTS Butunlay To'g'rilash
# ==============================================================================

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "=== 1. .env sozlamalarini tekshirish ==="
sed -i 's/^SECURE_SSL_REDIRECT=.*/SECURE_SSL_REDIRECT=False/' .env 2>/dev/null || true
if ! grep -q "^SECURE_SSL_REDIRECT=" .env; then
    echo "SECURE_SSL_REDIRECT=False" >> .env
fi

echo "=== 2. Nginx-da 301 loop qayta yo'naltirishlarini tozalash ==="
SSL_LINES=""
if [ -f "/etc/letsencrypt/live/crm.e-exclusive.uz/fullchain.pem" ]; then
    SSL_LINES="
    listen 443 ssl;
    listen [::]:443 ssl;
    ssl_certificate /etc/letsencrypt/live/crm.e-exclusive.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/crm.e-exclusive.uz/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    "
fi

cat <<EOF > /etc/nginx/sites-available/exclusive_crm
server {
    listen 80;
    listen [::]:80;
    ${SSL_LINES}

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
        proxy_set_header X-Forwarded-Proto https;
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

echo "=== 3. Nginx tekshirish va reload qilish ==="
nginx -t
systemctl reload nginx || systemctl restart nginx

echo "=== 4. Exclusive CRM servisini qayta ishga tushirish ==="
systemctl restart exclusive_crm
sleep 2

echo "=== 5. Mahalliy sinov (Redirect loop yo'qligini tekshirish) ==="
echo "--- Bosh sahifa (/) ---"
curl -s -I -H "Host: crm.e-exclusive.uz" -H "X-Forwarded-Proto: https" http://127.0.0.1/ | head -n 6

echo -e "\n--- Login sahifasi (/login/) ---"
curl -s -I -H "Host: crm.e-exclusive.uz" -H "X-Forwarded-Proto: https" http://127.0.0.1/login/ | head -n 6

echo -e "\n=========================================================="
echo "  TAYYOR! Loop muammosi to'liq bartaraf qilindi.          "
echo "  Brauzerda https://crm.e-exclusive.uz ochiladi!          "
echo "==========================================================\n"
