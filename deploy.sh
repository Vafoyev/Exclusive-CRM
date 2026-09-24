#!/bin/bash
set -e

# Loyiha papkasini aniqlash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "==========================================="
echo "  Exclusive CRM - Yangilanish (Deploy)     "
echo "==========================================="

echo ">>> 1. Git orqali oxirgi o'zgarishlarni tortib olish..."
git pull origin main

echo ">>> 2. Virtual muhitni faollashtirish..."
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "XATO: Virtual muhit (venv/.venv) topilmadi!"
    exit 1
fi

echo ">>> 3. Kutubxonalarni yangilash..."
pip install --upgrade pip
pip install -r requirements/production.txt

echo ">>> 4. Ma'lumotlar bazasi migratsiyalarini qo'llash..."
python manage.py migrate --settings=config.settings.production

echo ">>> 5. Statik fayllarni yig'ish..."
python manage.py collectstatic --noinput --settings=config.settings.production

echo ">>> 6. Xizmatlarni qayta ishga tushirish (Restart)..."
sudo systemctl restart gunicorn

# Agar celery xizmatlari mavjud bo'lsa ularni ham restart qilamiz
if systemctl list-unit-files | grep -q "celery.service"; then
    sudo systemctl restart celery
fi

if systemctl list-unit-files | grep -q "celery-beat.service"; then
    sudo systemctl restart celery-beat
fi

sudo systemctl restart nginx

echo "==========================================="
echo "  Muvaffaqiyatli yangilandi va ishga tushdi! "
echo "==========================================="
