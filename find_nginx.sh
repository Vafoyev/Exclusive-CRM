#!/usr/bin/env bash
echo "=== 1. Port 80 va 443 ni qaysi dastur band qilib turibdi? ==="
ss -tlpn | grep -E ':(80|443)\s' || netstat -tlpn | grep -E ':(80|443)\s' || lsof -i :80 || true

echo -e "\n=== 2. Nginx jarayonlari qayerdan ishlamoqda? ==="
ps aux | grep -i nginx | grep -v grep || true

echo -e "\n=== 3. Docker konteynerlari bormi? ==="
docker ps 2>/dev/null || echo "Docker ishlamayapti yoki o'rnatilmagan"

echo -e "\n=== 4. Nginx konfiguratsiya fayllari qayerda? ==="
which nginx || true
nginx -V 2>&1 | tr ' ' '\n' | grep -E 'conf-path|prefix' || true

echo -e "\n=== 5. Nginx holati (systemctl) ==="
systemctl status nginx --no-pager | head -n 12 || true
