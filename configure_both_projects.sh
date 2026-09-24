#!/usr/bin/env bash
# ==============================================================================
# Exclusive CRM & MockAI - Ikkala loyihani bir vaqtda to'liq sozlash skripti
# ==============================================================================

set -e

CRM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOCKAI_COMPOSE="/home/ubuntu/MockAi/mockai_platform/docker-compose.yml"

echo "=========================================================="
echo "  1. MockAI portini 8080 ga o'tkazish (80-portni bo'shatish)..."
echo "=========================================================="

if [ -f "$MOCKAI_COMPOSE" ]; then
    cp "$MOCKAI_COMPOSE" "${MOCKAI_COMPOSE}.bak"
    # Port 80:80 ni 8080:80 ga almashtirish
    sed -i -E 's/["'\'']?80:80["'\'']?/"8080:80"/g' "$MOCKAI_COMPOSE"
    sed -i -E 's/["'\'']?0\.0\.0\.0:80:80["'\'']?/"8080:80"/g' "$MOCKAI_COMPOSE"
    
    echo "[OK] docker-compose.yml yangilandi (Port: 8080)."
    cd "$(dirname "$MOCKAI_COMPOSE")"
    
    if docker compose version >/dev/null 2>&1; then
        docker compose up -d --force-recreate
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose up -d --force-recreate
    fi
    echo "[OK] MockAI konteynerlari qayta ishga tushirildi (Port: 8080)."
else
    echo "[OGOHLANTIRISH] $MOCKAI_COMPOSE topilmadi, mavjud konteyner tekshirilmoqda..."
fi

cd "$CRM_DIR"
sleep 2

echo "=========================================================="
echo "  2. Exclusive CRM servisini (Port 8001) ishga tushirish  "
echo "=========================================================="

chmod 755 /home/ubuntu || true
chmod -R 775 "$CRM_DIR" || true
chown -R ubuntu:www-data "$CRM_DIR" || true

systemctl daemon-reload
systemctl enable exclusive_crm
systemctl restart exclusive_crm
sleep 2

echo ">>> Exclusive CRM (Port 8001) tekshiruvi:"
curl -s -I http://127.0.0.1:8001 | head -n 3 || echo "Port 8001"

echo "=========================================================="
echo "  3. Asosiy Nginx konfiguratsiyasini sozlash (Master Proxy)"
echo "=========================================================="

rm -f /etc/nginx/sites-enabled/default

# A) Mock AI konfiguratsiyasi (Boshqa barcha so'rovlar uchun default server)
cat << 'EOF' > /etc/nginx/sites-available/mockai
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/mockai /etc/nginx/sites-enabled/

# B) Exclusive CRM konfiguratsiyasi (crm.e-exclusive.uz uchun)
cat << EOF > /etc/nginx/sites-available/exclusive_crm
server {
    listen 80;
    listen [::]:80;
    server_name crm.e-exclusive.uz;

    client_max_body_size 100M;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;

    location /static/ {
        alias ${CRM_DIR}/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias ${CRM_DIR}/media/;
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

echo ">>> Nginx sintaksisini tekshirish:"
nginx -t

echo "=========================================================="
echo "  4. Nginx xizmatini ishga tushirish                      "
echo "=========================================================="
systemctl daemon-reload
systemctl enable nginx
systemctl restart nginx
sleep 1

echo "=========================================================="
echo "  5. SSL Sertifikatini ulash (crm.e-exclusive.uz)         "
echo "=========================================================="
if command -v certbot >/dev/null 2>&1; then
    certbot --nginx -d crm.e-exclusive.uz --non-interactive --agree-tos -m info@e-exclusive.uz --redirect 2>/dev/null || true
    systemctl reload nginx 2>/dev/null || true
fi

echo "=========================================================="
echo "  6. Yakuniy tekshiruv va natijalar                       "
echo "=========================================================="
echo ">>> 1) MockAI (Port 8080):"
curl -s -I http://127.0.0.1:8080 | head -n 3 || echo "MockAI tekshiruvi"

echo -e "\n>>> 2) Exclusive CRM (Port 8001):"
curl -s -I http://127.0.0.1:8001 | head -n 3 || echo "Exclusive CRM tekshiruvi"

echo -e "\n>>> 3) crm.e-exclusive.uz Nginx javobi:"
curl -s -I -H "Host: crm.e-exclusive.uz" http://127.0.0.1 | head -n 5 || echo "Domen tekshiruvi"

echo -e "\n=========================================================="
echo "  MUVAFFAQITYATLI YAKUNLANDI!                             "
echo "  1. MockAI -> Port 8080 da ishlamoqda (Master Nginx orqali) "
echo "  2. Exclusive CRM -> https://crm.e-exclusive.uz (Port 8001)!"
echo "==========================================================\n"
