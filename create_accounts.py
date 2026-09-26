import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.organizations.models import Organization, Branch
from apps.users.models import User
from django.contrib.auth.models import Permission

print("==========================================================")
print("  Exclusive CRM - 3 ta hisobni yaratish va to'liq sozlash ")
print("==========================================================")

# 1. Tashkilot va filialni tekshirish / yaratish
org, created = Organization.objects.get_or_create(
    subdomain='crm',
    defaults={'name': 'Exclusive Education', 'is_active': True}
)
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

# Administrator uchun barcha operatsion ruxsatlar (permissions)
ADMIN_PERMISSIONS = {
    'users': {'view': True, 'create': True, 'edit': True, 'delete': True},
    'crm': {'view': True, 'create': True, 'edit': True, 'delete': True, 'leads': True},
    'education': {'view': True, 'create': True, 'edit': True, 'delete': True},
    'operations': {'view': True, 'create': True, 'edit': True, 'delete': True, 'attendance': True},
    'finance': {'view': True, 'create': True, 'edit': True, 'delete': True, 'payments': True},
    'admin_finance': {'view': True, 'create': True, 'edit': True, 'delete': True},
    'automation': {'view': True, 'create': True, 'edit': True, 'delete': False},
    'reports': {'view': True, 'create': True, 'edit': True, 'delete': False},
    'settings': {'view': True, 'create': True, 'edit': True, 'delete': False},
}

# 1) isobek (01020304) -> Super Admin (Tizim egasi)
u_isobek, _ = User.objects.get_or_create(
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
u_isobek.set_password('01020304')
u_isobek.first_name = 'Isobek'
u_isobek.last_name = 'Admin'
u_isobek.role = 'super_admin'
u_isobek.is_staff = True
u_isobek.is_superuser = True
u_isobek.is_active = True
u_isobek.organization = org
u_isobek.branch = branch
u_isobek.save()
print("1. [OK] isobek -> Parol: 01020304 (Super Admin / Isobek)")

# 2) director (ExclusiveAim) -> Direktor / Owner
u_dir, _ = User.objects.get_or_create(
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
u_dir.set_password('ExclusiveAim')
u_dir.first_name = 'Markaz'
u_dir.last_name = 'Direktori'
u_dir.role = 'owner'
u_dir.is_staff = True
u_dir.is_superuser = False
u_dir.is_active = True
u_dir.organization = org
u_dir.branch = branch
u_dir.save()
org.owner = u_dir
org.save()
print("2. [OK] director -> Parol: ExclusiveAim (Direktor / Owner)")

# 3) admin va exclusive_admin -> Administrator (Administrator vazifalari bilan)
for admin_username in ['admin', 'exclusive_admin']:
    u_admin, _ = User.objects.get_or_create(
        phone=admin_username,
        defaults={
            'first_name': 'Markaz',
            'last_name': 'Administratori',
            'role': 'admin',
            'is_staff': True,
            'is_superuser': False,
            'organization': org,
            'branch': branch,
        }
    )
    u_admin.set_password('SalomDunyo1')
    u_admin.first_name = 'Markaz'
    u_admin.last_name = 'Administratori'
    u_admin.role = 'admin'
    u_admin.is_staff = True
    u_admin.is_superuser = False
    u_admin.is_active = True
    u_admin.organization = org
    u_admin.branch = branch
    u_admin.permissions = ADMIN_PERMISSIONS
    u_admin.save()

    # Django ruxsatlarini ham to'liq biriktiramiz
    all_perms = Permission.objects.filter(
        content_type__app_label__in=[
            'users', 'crm', 'education', 'operations',
            'finance', 'automation', 'organizations'
        ]
    )
    u_admin.user_permissions.set(all_perms)
    print(f"3. [OK] {admin_username} -> Parol: SalomDunyo1 (Administrator - Barcha vazifalar va ruxsatlar bilan)")

# 4. Standart Kassalar va Kategoriyalarni yaratish
from apps.finance.services import ensure_default_finance_data
ensure_default_finance_data(org)
print("4. [OK] Standart kassalar (Asosiy kassa, Bank, Karta) va kategoriyalar (Kurs to'lovi...) yaratildi!")

print("==========================================================")
print("  Barcha hisoblar, kassalar va ruxsatlar 100% tayyor!      ")
print("==========================================================")
