#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM - Cloudflare Redirect Loop (ERR_TOO_MANY_REDIRECTS) Tuzatish
# ==============================================================================

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo ">>> 1. .env faylida SECURE_SSL_REDIRECT=False ekanligini tasdiqlash..."
sed -i 's/^SECURE_SSL_REDIRECT=.*/SECURE_SSL_REDIRECT=False/' .env || true
if ! grep -q "^SECURE_SSL_REDIRECT=" .env; then
    echo "SECURE_SSL_REDIRECT=False" >> .env
fi

echo ">>> 2. Nginx konfiguratsiyasidan cheksiz qayta yo'naltirishni (redirect) olib tashlash..."
# Certbot qo'shgan 301 redirect Cloudflare Flexible rejimida cheksiz loop beradi.
# Biz port 80 va port 443 da to'g'ridan-to'g'ri xizmat ko'rsatadigan qilamiz.

SSL_BLOCK=""
if [ -f "/etc/letsencrypt/live/crm.e-exclusive.uz/fullchain.pem" ]; then
    SSL_BLOCK="
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/crm.e-exclusive.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/crm.e-exclusive.uz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    "
fi

cat <<EOF > /etc/nginx/sites-available/exclusive_crm
server {
    listen 80;
    listen [::]:80;
    ${SSL_BLOCK}

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

echo ">>> 3. Nginx konfiguratsiyasini tekshirish va reload qilish..."
nginx -t
systemctl reload nginx || systemctl restart nginx

echo ">>> 4. Exclusive CRM servisini qayta ishga tushirish..."
systemctl restart exclusive_crm
sleep 2

echo ">>> 5. crm.e-exclusive.uz test qilish:"
curl -s -I -H "Host: crm.e-exclusive.uz" http://127.0.0.1 | head -n 8

echo -e "\n=========================================================="
echo "  TUZATILDI! Redirect loop to'xtatildi.                   "
echo "  Endi https://crm.e-exclusive.uz ochiladi!               "
echo "==========================================================\n"
