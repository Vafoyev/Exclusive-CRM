import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.organizations.models import Organization, Branch
from apps.users.models import User

print("==========================================================")
print("  Exclusive CRM - 3 ta hisobni yaratish va sozlash        ")
print("==========================================================")

# 1. Tashkilot va filialni tekshirish / yaratish
org, created = Organization.objects.get_or_create(
    subdomain='crm',
    defaults={'name': 'Exclusive Education', 'is_active': True}
)
if not created:
    org.is_active = True
    org.save()

branch, _ = Branch.objects.get_or_create(
    organization=org,
    is_main=True,
    defaults={
        'name': 'Bosh filial',
        'address': 'Toshkent shahri',
        'phone': '+998900000000',
    }
)

# 2. Uchta foydalanuvchini yaratish / parolini o'rnatish

# 1) exclusive_admin (SalomDunyo1)
u1, _ = User.objects.get_or_create(
    phone='exclusive_admin',
    defaults={
        'first_name': 'Exclusive',
        'last_name': 'Admin',
        'role': 'super_admin',
        'is_staff': True,
        'is_superuser': True,
        'organization': org,
        'branch': branch,
    }
)
u1.set_password('SalomDunyo1')
u1.is_staff = True
u1.is_superuser = True
u1.is_active = True
u1.role = 'super_admin'
u1.organization = org
u1.branch = branch
u1.save()
print("1. [OK] exclusive_admin -> Parol: SalomDunyo1 (Super Admin)")

# 2) director (ExclusiveAim)
u2, _ = User.objects.get_or_create(
    phone='director',
    defaults={
        'first_name': 'Markaz',
        'last_name': 'Direktori',
        'role': 'owner',
        'is_staff': True,
        'is_superuser': False,
        'organization': org,
        'branch': branch,
    }
)
u2.set_password('ExclusiveAim')
u2.is_staff = True
u2.is_active = True
u2.role = 'owner'
u2.organization = org
u2.branch = branch
u2.save()
org.owner = u2
org.save()
print("2. [OK] director -> Parol: ExclusiveAim (Direktor / Owner)")

# 3) isobek (01020304)
u3, _ = User.objects.get_or_create(
    phone='isobek',
    defaults={
        'first_name': 'Isobek',
        'last_name': 'Admin',
        'role': 'super_admin',
        'is_staff': True,
        'is_superuser': True,
        'organization': org,
        'branch': branch,
    }
)
u3.set_password('01020304')
u3.is_staff = True
u3.is_superuser = True
u3.is_active = True
u3.role = 'super_admin'
u3.organization = org
u3.branch = branch
u3.save()
print("3. [OK] isobek -> Parol: 01020304 (Super Admin)")

print("==========================================================")
print("  Barcha 3 ta hisob muvaffaqiyatli saqlandi!              ")
print("==========================================================")
