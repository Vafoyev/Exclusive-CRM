#!/usr/bin/env bash
echo "=== 1. MockAI qaysi papkada joylashgan? ==="
find /home/ubuntu -maxdepth 3 -name "docker-compose*.yml" 2>/dev/null || true

echo -e "\n=== 2. MockAI Frontend Docker ma'lumotlari: ==="
docker inspect mockai-frontend --format '{{json .HostConfig.PortBindings}}' 2>/dev/null || true

echo -e "\n=== 3. MockAI konteyner ichidagi Nginx konfiguratsiyasi: ==="
docker exec mockai-frontend cat /etc/nginx/conf.d/default.conf 2>/dev/null || \
docker exec mockai-frontend cat /etc/nginx/nginx.conf 2>/dev/null || true
