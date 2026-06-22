# 🎓 SMART EDU CRM - O'quv Markazlari uchun CRM & LMS Tizimi

[![Django](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-success.svg)](https://github.com/xudoyor1225/Crmtizim)

> **🌟 Production'da ishlamoqda!** - http://13.39.83.160

## 📖 Loyiha Haqida

**SMART EDU CRM** - O'zbekiston o'quv markazlari uchun maxsus ishlab chiqilgan to'liq funksional SaaS (Software as a Service) platformasi. Mijozlar boshqaruvi, ta'lim jarayoni, moliya va xodimlar boshqaruvini bir platformada birlashtiradi.

### 🎯 Maqsad
O'quv markazlarining barcha jarayonlarini avtomatlashtirish va markaziy boshqarish tizimini yaratish. Lidlardan tortib, to'lovlargacha barcha jarayonlarni bir tizimda boshqarish.

---

## ✨ Asosiy Imkoniyatlar

### 🎯 CRM (Customer Relationship Management)
- 📞 **Lid Boshqaruvi** - Potentsial mijozlarni kuzatish
- 🔄 **Sotuv Voronkasi** - Lead → Contact → Enrolled jarayoni
- 📊 **Kanban Board** - Vizual boshqaruv
- 📱 **SMS & Telegram** - Avtomatik xabarnomalar
- 📈 **Analitika** - Konversiya va hisobotlar

### 📚 LMS (Learning Management System)
- 👨‍🎓 **O'quvchilar Bazasi** - To'liq profil va tarixi
- 👨‍🏫 **O'qituvchilar** - Malaka, tajriba, KPI
- 📅 **Guruhlar & Jadval** - Dars jadvali boshqaruvi
- ✅ **Davomat Tizimi** - Avtomatik qayd etish
- 📝 **Baholash** - Baholar, imtihonlar, sertifikatlar
- 📖 **O'quv Materiallari** - Video, PDF, Audio, Kitoblar
- 📋 **Syllabus** - Kurs rejasi va mavzular
- 🎓 **Xonalar** - O'quv xonalari boshqaruvi

### 💰 Moliya va Kassa
- 💵 **To'lovlar** - Naqd, plastik, bank o'tkazmasi
- 📊 **Tranzaksiyalar** - To'liq moliyaviy tarix
- 🏦 **Kassa Boshqaruvi** - Kirish/Chiqish nazorati
- 📈 **Moliyaviy Hisobotlar** - Kunlik, oylik, yillik
- 🧾 **Chek Tasdiqlash** - Rasm yuklash va verifikatsiya
- 💳 **Student Payment** - O'quvchilar to'lov portali
- 🏪 **Do'kon** - Kitob va materiallar sotish
- 📦 **Sklad** - Inventarizatsiya boshqaruvi

### 👥 HR va Xodimlar
- 📋 **Xodimlar Bazasi** - To'liq ma'lumot
- ⏰ **Davomat** - Kirish/Chiqish, kechikishlar
- 💼 **Oylik Hisob-kitob** - Maosh, bonuslar, jarimalar
- 📈 **KPI Sistema** - Samaradorlik baholash
- 📊 **Hisobotlar** - Xodimlar statistikasi

### 🎮 Gamification (O'yin Elementlari)
- ⭐ **XP Tizimi** - Tajriba ballari
- 🏆 **Badge & Achievements** - Yutuqlar va nishonlar
- 🔥 **Streak System** - Ketma-ketlik mukofotlari
- 🎯 **Level Sistema** - Darajalar
- 🏅 **Leaderboard** - Reyting jadvali

### 🤖 Avtomatlashtirish
- 📨 **SMS Xabarnomalar** - To'lovlar, darslar haqida
- 💬 **Telegram Bot** - Bildirishnomalar va boshqaruv
- ⏰ **Eslatmalar** - Dars boshlanishidan oldin
- 📊 **Kunlik Hisobotlar** - Avtomatik yuboriladi
- 🔔 **Webhook Events** - Tizim hodisalari

### 🔒 Xavfsizlik va Nazorat
- 🔐 **Role-based Access Control** - Rol asosida ruxsatlar
- 📝 **Audit Log** - Barcha o'zgarishlar tarixi
- 🏢 **Multi-tenant SaaS** - Ko'p tashkilotli arxitektura
- 🔑 **Authentication** - Session va API autentifikatsiya
- 🛡️ **File Validation** - Fayl xavfsizligi

---

## 🚀 Tez Boshlash (Quick Start)

### Talablar
- **Python 3.10+** (tavsiya: 3.12)
- **PostgreSQL 13+** (majburiy, SQLite ishlatilmaydi)
- **Git**
- **Redis 6+** (Celery uchun, ixtiyoriy)

---

### 1️⃣ Loyihani Klonlash

```bash
git clone https://github.com/yourusername/Crmtizim.git
cd Crmtizim
```

---

### 2️⃣ Virtual Environment

**Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3️⃣ Kutubxonalarni O'rnatish

```bash
pip install -r requirements/base.txt
```

**Asosiy kutubxonalar:**
- Django 6.0
- djangorestframework
- psycopg2-binary (PostgreSQL)
- whitenoise (Static files)
- reportlab (PDF)
- python-decouple (Environment)
- Pillow (Images)

---

### 4️⃣ PostgreSQL Bazasini Yaratish

**PostgreSQL ga kirish:**
```bash
psql -U postgres
```

**SQL buyruqlar:**
```sql
-- Foydalanuvchi yaratish
CREATE USER crmtizim_user WITH PASSWORD 'your_secure_password';

-- Baza yaratish
CREATE DATABASE crmtizim_db OWNER crmtizim_user;

-- Sozlamalar
ALTER ROLE crmtizim_user SET client_encoding TO 'utf8';
ALTER ROLE crmtizim_user SET timezone TO 'Asia/Tashkent';

-- Huquqlar
GRANT ALL PRIVILEGES ON DATABASE crmtizim_db TO crmtizim_user;

-- PostgreSQL 15+ uchun
\c crmtizim_db
GRANT ALL ON SCHEMA public TO crmtizim_user;

-- Chiqish
\q
```

---

### 5️⃣ Environment Sozlash

**`.env` fayl yaratish:**
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

**`.env` faylni tahrirlang:**
```env
# Django
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL (MAJBURIY)
USE_POSTGRES=True
DB_NAME=crmtizim_db
DB_USER=crmtizim_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Telegram Bot (Ixtiyoriy)
TELEGRAM_BOT_TOKEN=your_bot_token

# SMS (Ixtiyoriy)
SMS_API_URL=https://notify.eskiz.uz/api
SMS_EMAIL=your_email
SMS_PASSWORD=your_password
```

---

### 6️⃣ Ma'lumotlar Bazasini Tayyorlash

```bash
# Migratsiyalarni qo'llash
python manage.py migrate

# Superuser yaratish
python manage.py createsuperuser
```

**Kirish ma'lumotlari:**
- Phone: `998901234567`
- Password: `admin123` (yoki o'zingizni)

---

### 7️⃣ Serverni Ishga Tushirish

```bash
python manage.py runserver
```

**Brauzerda ochish:**
- 🌐 Frontend: http://127.0.0.1:8000
- 👨‍💼 Admin Panel: http://127.0.0.1:8000/admin

---

### 8️⃣ Test Ma'lumotlar (Ixtiyoriy)

Agar test uchun ma'lumotlar kerak bo'lsa:

```bash
# Django shell ochish
python manage.py shell
```

```python
# Shell ichida
from apps.organizations.models import Organization, Branch
from apps.users.models import User

# Tashkilot yaratish
org = Organization.objects.create(
    name="Test O'quv Markazi",
    phone="998901234567",
    legal_name="Test O'quv Markazi MCHJ"
)

# Filial yaratish
branch = Branch.objects.create(
    organization=org,
    name="Markaziy Filial",
    address="Toshkent, Chilonzor"
)

print("✅ Test ma'lumotlar yaratildi!")
```

---

## 📂 Loyiha Strukturasi

```
Crmtizim/
├── 📁 apps/                          # Django aplikatsiyalari
│   ├── 🔧 core/                      # Asosiy funksiyalar
│   │   ├── models.py                # BaseModel, TenantAwareModel
│   │   ├── middleware.py            # TenantMiddleware (SaaS)
│   │   ├── permissions.py           # Role-based permissions
│   │   ├── validators.py            # File validation
│   │   ├── audit.py                 # Audit logging
│   │   └── utils.py                 # Utility functions
│   │
│   ├── 👤 users/                     # Foydalanuvchilar
│   │   ├── models.py                # User, Profile
│   │   ├── views.py                 # CRUD views
│   │   ├── forms.py                 # Forms
│   │   └── urls.py                  # URL patterns
│   │
│   ├── 🏢 organizations/             # Tashkilotlar
│   │   ├── models.py                # Organization, Branch
│   │   └── views.py                 # Multi-tenant views
│   │
│   ├── 📚 education/                 # LMS (Ta'lim)
│   │   ├── models.py                # Course, Group, Student
│   │   ├── lms_models.py            # LMS-specific models
│   │   ├── lms_views.py             # LMS views
│   │   ├── materials.py             # Study materials
│   │   ├── materials_views.py       # Materials CRUD
│   │   └── services.py              # Business logic
│   │
│   ├── 🎯 crm/                       # CRM (Mijozlar)
│   │   ├── models.py                # Lead, Contact, Deal
│   │   ├── views.py                 # Sales funnel
│   │   ├── forms.py                 # CRM forms
│   │   └── services.py              # CRM services
│   │
│   ├── 💰 finance/                   # Moliya
│   │   ├── models.py                # Transaction, Payment
│   │   ├── views.py                 # Finance views
│   │   ├── student_payment_views.py # Student payments
│   │   ├── inventory_views.py       # Inventory (sklad)
│   │   ├── export_views.py          # PDF/Excel export
│   │   └── services.py              # Payment logic
│   │
│   ├── 🎮 operations/                # Operatsiyalar
│   │   ├── models.py                # Lesson, Attendance
│   │   ├── views.py                 # Operations views
│   │   ├── gamification.py          # XP, Badges, Levels
│   │   ├── shop_views.py            # Online shop
│   │   └── services.py              # Operations logic
│   │
│   ├── 🤖 automation/                # Avtomatlashtirish
│   │   ├── models.py                # Notification, Template
│   │   ├── tasks.py                 # Celery tasks
│   │   ├── signals.py               # Django signals
│   │   └── services.py              # SMS, Telegram bot
│   │
│   └── 🔌 api/                       # REST API
│       ├── serializers.py           # DRF serializers
│       ├── views.py                 # API endpoints
│       └── urls.py                  # API routes
│
├── 📁 config/                        # Django sozlamalar
│   ├── settings/
│   │   ├── base.py                  # Asosiy sozlamalar
│   │   ├── local.py                 # Development
│   │   └── production.py            # Production
│   ├── urls.py                      # Root URL patterns
│   ├── wsgi.py                      # WSGI application
│   └── celery.py                    # Celery config
│
├── 📁 templates/                     # HTML shablonlar
│   ├── base.html                    # Base template
│   ├── dashboard.html               # Dashboard
│   ├── education/                   # LMS templates
│   ├── finance/                     # Finance templates
│   ├── crm/                         # CRM templates
│   └── users/                       # User templates
│
├── 📁 static/                        # Static files
│   ├── css/                         # CSS fayllar
│   ├── js/                          # JavaScript
│   └── img/                         # Images
│
├── 📁 media/                         # User uploads
│   ├── avatars/                     # Profile pictures
│   ├── receipts/                    # Payment receipts
│   └── materials/                   # Study materials
│
├── 📁 requirements/                  # Python dependencies
│   ├── base.txt                     # Base requirements
│   └── production.txt               # Production packages
│
├── 📁 logs/                          # Log files
│   ├── django.log                   # Application logs
│   └── errors.log                   # Error logs
│
├── 📄 manage.py                      # Django CLI
├── 📄 .env                           # Environment variables (local)
├── 📄 .env.example                   # Example env file
├── 📄 .gitignore                     # Git ignore rules
├── 📄 README.md                      # Bu fayl
├── 📄 QUICKSTART.md                  # Tez boshlash
├── 📄 POSTGRESQL_MIGRATION.md        # PostgreSQL qo'llanma
├── 📄 docker-compose.yml             # Docker compose
└── 📄 Dockerfile                     # Docker image
```

---

## 🔐 Xavfsizlik

### Environment Variables
Muhim ma'lumotlarni `.env` faylida saqlang:
```env
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
```

### CORS Sozlamalari
Production'da faqat o'z domenlaringizni ruxsat bering:
```python
CORS_ALLOWED_ORIGINS = [
    'https://app.smartedu.uz',
    'https://admin.smartedu.uz',
]
```

### File Upload Xavfsizligi
Barcha fayllar validatsiyadan o'tadi:
- Fayl turi tekshiriladi
- Maksimal hajm cheklangan (5MB cheklar uchun, 100MB materiallar uchun)

---

## 👥 Rollar va Ruxsatlar

| Rol | Tavsif | Ruxsatlar |
|-----|--------|-----------|
| **🔑 Super Admin** | Platforma egalari | Barcha tashkilotlarga kirish, tizim sozlamalari |
| **👑 Owner (Direktor)** | Markaz egasi | To'liq ruxsat, barcha modullar |
| **⚙️ Admin** | Filial boshqaruvchisi | Ma'muriy ruxsatlar, xodimlar boshqaruvi |
| **👨‍🏫 Teacher** | O'qituvchi | Guruhlar, darslar, baholash |
| **👨‍💼 Staff** | Xodim | Cheklangan ruxsatlar, CRM |
| **👨‍🎓 Student** | O'quvchi | O'z ma'lumotlari, materiallar |
| **👪 Parent** | Ota-ona | Farzand ma'lumotlari, to'lovlar |

### Ruxsatlar Tizimi
```python
# Har bir foydalanuvchi bir yoki bir nechta rolga ega
user.roles = ['admin', 'teacher']

# Permission tekshirish
@permission_required('education.view_group')
def group_list(request):
    # ...
```

---

## 📊 API Endpoints

### Authentication
```http
POST /api/auth/login/          # Login
POST /api/auth/logout/         # Logout
GET  /api/auth/user/           # Current user
```

### Students (O'quvchilar)
```http
GET    /api/students/          # Ro'yxat
POST   /api/students/          # Yangi o'quvchi
GET    /api/students/{id}/     # Bitta o'quvchi
PUT    /api/students/{id}/     # Yangilash
DELETE /api/students/{id}/     # O'chirish
```

### Groups (Guruhlar)
```http
GET    /api/groups/            # Ro'yxat
POST   /api/groups/            # Yangi guruh
GET    /api/groups/{id}/       # Bitta guruh
PUT    /api/groups/{id}/       # Yangilash
```

### Payments (To'lovlar)
```http
GET    /api/transactions/      # To'lovlar ro'yxati
POST   /api/transactions/      # Yangi to'lov
GET    /api/transactions/{id}/ # To'lov ma'lumoti
```

### Attendance (Davomat)
```http
GET    /api/attendance/        # Davomat ro'yxati
POST   /api/attendance/mark/   # Davomatni belgilash
```

### Authentication Methods
- **Session Authentication** - Web interface uchun
- **Basic Authentication** - API uchun
- **Token Authentication** - Mobile apps uchun (qo'shimcha)

---

## 🔒 Xavfsizlik

### Environment Variables
Muhim ma'lumotlarni `.env` faylida saqlang va hech qachon Git ga yuklamang:
```env
SECRET_KEY=your-very-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### CORS Sozlamalari
Production'da faqat o'z domenlaringizni ruxsat bering:
```python
# config/settings/production.py
CORS_ALLOWED_ORIGINS = [
    'https://app.smartedu.uz',
    'https://admin.smartedu.uz',
]
```

### File Upload Xavfsizligi
Barcha fayllar validatsiyadan o'tadi:
- ✅ Fayl turi tekshiriladi (faqat ruxsat etilgan formatlar)
- ✅ Maksimal hajm cheklangan (5MB cheklar, 100MB materiallar)
- ✅ Fayl nomi sanitize qilinadi
- ✅ Virus skanerlash (qo'shimcha)

---

## 🔄 Background Tasks (Celery)

### Redis ni Ishga Tushirish
```bash
# Windows (Memurai yoki WSL)
redis-server

# Linux/Mac
sudo systemctl start redis
```

### Celery Worker
```bash
# Development
celery -A config worker -l info

# Production (Windows)
celery -A config worker -l info --pool=solo

# Production (Linux)
celery -A config worker -l info --concurrency=4
```

### Celery Beat (Scheduled Tasks)
```bash
celery -A config beat -l info
```

---

## 🧪 Testlar

### Testlarni Ishga Tushirish
```bash
# Barcha testlar
python manage.py test

# Bitta app testi
python manage.py test apps.education

# Verbose output
python manage.py test --verbosity=2
```

### Test Qamrovi (Coverage)
```bash
# Coverage o'rnatish
pip install coverage

# Testlarni coverage bilan ishga tushirish
coverage run --source='apps' manage.py test

# Hisobot ko'rish
coverage report

# HTML hisobot
coverage html
# htmlcov/index.html ni brauzerda oching
```

---

## 🚢 Production'ga Chiqarish

### 1️⃣ Environment Sozlash
```env
# .env (Production)
DEBUG=False
SECRET_KEY=<very-strong-secret-key-at-least-50-characters>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

USE_POSTGRES=True
DB_NAME=crmtizim_prod
DB_USER=crmtizim_user
DB_PASSWORD=<strong-database-password>
DB_HOST=localhost
DB_PORT=5432
```

### 2️⃣ Static Fayllarni Yig'ish
```bash
python manage.py collectstatic --noinput
```

### 3️⃣ Gunicorn bilan Ishga Tushirish
```bash
# Gunicorn o'rnatish
pip install gunicorn

# Ishga tushirish
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

### 4️⃣ Nginx Konfiguratsiyasi
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location /static/ {
        alias /var/www/crmtizim/staticfiles/;
    }

    location /media/ {
        alias /var/www/crmtizim/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5️⃣ Systemd Service (Linux)
```ini
# /etc/systemd/system/crmtizim.service
[Unit]
Description=SMART EDU CRM
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/crmtizim
ExecStart=/var/www/crmtizim/.venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3

[Install]
WantedBy=multi-user.target
```

```bash
# Service ni ishga tushirish
sudo systemctl start crmtizim
sudo systemctl enable crmtizim
```

### 6️⃣ Docker (Ixtiyoriy)
```bash
# Docker image yaratish
docker build -t crmtizim:latest .

# Docker Compose bilan ishga tushirish
docker-compose up -d
```

---

## 🐛 Muammolar va Yechimlar

### ❌ Muammo: ModuleNotFoundError
```bash
# Yechim: Requirements o'rnatish
pip install -r requirements/base.txt
```

### ❌ Muammo: Migration xatolari
```bash
# Yechim: Migratsiyalarni qayta yaratish
python manage.py makemigrations
python manage.py migrate
```

### ❌ Muammo: Static fayllar yuklanmayapti
```bash
# Yechim: Collectstatic
python manage.py collectstatic --clear --noinput
```

### ❌ Muammo: PostgreSQL ulanmayapti
```bash
# 1. PostgreSQL ishlab turganini tekshirish
psql -U postgres -c "SELECT version();"

# 2. .env fayldagi sozlamalarni tekshirish
USE_POSTGRES=True
DB_HOST=localhost
DB_PORT=5432

# 3. Foydalanuvchi huquqlarini tekshirish
psql -U postgres
GRANT ALL PRIVILEGES ON DATABASE crmtizim_db TO crmtizim_user;
```

### ❌ Muammo: "Cannot filter a query once a slice has been taken"
```python
# Noto'g'ri:
queryset = Model.objects.all()[:10].filter(...)

# To'g'ri:
queryset = Model.objects.filter(...).all()[:10]
```

### ❌ Muammo: UnicodeDecodeError
```bash
# Windows uchun yechim
$env:PYTHONIOENCODING = "utf-8"
python manage.py runserver
```

---

## 🚀 Deployment va Yangilash

### Server Yangilash
Server'da yangilanishlarni qo'llash uchun: [SERVER_UPDATE_GUIDE.md](SERVER_UPDATE_GUIDE.md)

### Tezkor Yangilash
```bash
cd /var/www/Crmtizim && \
source venv/bin/activate && \
git pull origin main && \
python manage.py collectstatic --noinput && \
sudo systemctl restart gunicorn && \
sudo systemctl reload nginx
```

### Monitoring
```bash
# Service statuslari
sudo systemctl status gunicorn nginx

# Loglarni kuzatish
sudo journalctl -u gunicorn -f
```

---

## 🤝 Hissa Qo'shish

1. Fork qiling
2. Feature branch yarating (`git checkout -b feature/AmazingFeature`)
3. Commit qiling (`git commit -m 'Add some AmazingFeature'`)
4. Push qiling (`git push origin feature/AmazingFeature`)
5. Pull Request oching

---

## 📞 Aloqa

- **GitHub:** [xudoyor1225](https://github.com/xudoyor1225)
- **Repository:** [Crmtizim](https://github.com/xudoyor1225/Crmtizim)
- **Production:** http://13.39.83.160

---

## 📄 Litsenziya

Bu loyiha MIT litsenziyasi ostida tarqatiladi.

---

## 🙏 Minnatdorchilik

- Django Framework
- Django REST Framework
- PostgreSQL
- Gunicorn & Nginx
- AWS EC2

---

**Oxirgi yangilanish:** 2026-02-09  
**Versiya:** 2.0.0 (Production)
- Va boshqa open-source kutubxonalarga!

---

**© 2024-2026 SMART EDU CRM. Barcha huquqlar himoyalangan.**
