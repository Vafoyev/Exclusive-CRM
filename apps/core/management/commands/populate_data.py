"""
Test ma'lumotlarini yaratish management command.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta
from decimal import Decimal

from apps.users.models import User
from apps.organizations.models import Organization, Branch
from apps.education.models import Course, Room, Group, GroupStudent
from apps.finance.models import Account, TransactionCategory, Transaction
from apps.crm.models import Stage, LeadSource, Lead


class Command(BaseCommand):
    help = 'Bazani test ma\'lumotlar bilan to\'ldirish'

    def handle(self, *args, **kwargs):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS('TEST MA\'LUMOTLARINI YARATISH BOSHLANDI'))
        self.stdout.write("=" * 60)

        # 1. ORGANIZATSIYA
        self.stdout.write("\n[1] Tashkilot yaratilmoqda...")
        org, created = Organization.objects.get_or_create(
            name="Smart Edu Test Center",
            defaults={
                'subdomain': 'smartedu',
                'config': {
                    'currency': 'UZS',
                    'timezone': 'Asia/Tashkent',
                    'working_days': [1, 2, 3, 4, 5, 6]
                },
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f"   ✅ Tashkilot yaratildi: {org.name}")
        else:
            self.stdout.write(f"   ℹ️  Tashkilot mavjud: {org.name}")

        # 2. FILIAL
        self.stdout.write("\n2️⃣ Filial yaratilmoqda...")
        branch, created = Branch.objects.get_or_create(
            organization=org,
            name="Asosiy filial",
            defaults={
                'address': 'Toshkent, Chilonzor',
                'phone': '+998901234567',
                'is_main': True,
            }
        )
        if created:
            self.stdout.write(f"   ✅ Filial yaratildi: {branch.name}")

        # 3. FOYDALANUVCHILAR
        self.stdout.write("\n3️⃣ Foydalanuvchilar yaratilmoqda...")

        # Admin
        admin, created = User.objects.get_or_create(
            phone='+998901111111',
            defaults={
                'first_name': 'Admin',
                'last_name': 'Adminov',
                'role': 'admin',
                'organization': org,
                'branch': branch,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(f"   ✅ Admin yaratildi: {admin.full_name}")

        # O'qituvchilar
        teachers = []
        teacher_names = [
            ('Jasur', 'Karimov'),
            ('Dilnoza', 'Rahimova'),
            ('Aziz', 'Tursunov'),
        ]

        for first, last in teacher_names:
            teacher, created = User.objects.get_or_create(
                phone=f'+99890{first[:4].lower()}',
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'role': 'teacher',
                    'organization': org,
                    'branch': branch,
                }
            )
            if created:
                teacher.set_password('teacher123')
                teacher.save()
                self.stdout.write(f"   ✅ O'qituvchi yaratildi: {teacher.full_name}")
            teachers.append(teacher)

        # O'quvchilar
        students = []
        student_names = [
            ('Ali', 'Valiyev'),
            ('Zarina', 'Mahmudova'),
            ('Bobur', 'Usmonov'),
            ('Madina', 'Aliyeva'),
            ('Sardor', 'Ismoilov'),
            ('Nilufar', 'Rahmonova'),
        ]

        for idx, (first, last) in enumerate(student_names):
            student, created = User.objects.get_or_create(
                phone=f'+998911{idx+1:03d}000',
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'role': 'student',
                    'organization': org,
                    'branch': branch,
                    'balance': Decimal('1000000'),
                }
            )
            if created:
                student.set_password('student123')
                student.save()
                self.stdout.write(f"   ✅ O'quvchi yaratildi: {student.full_name}")
            students.append(student)

        # 4. KURSLAR
        self.stdout.write("\n4️⃣ Kurslar yaratilmoqda...")
        courses = []
        course_data = [
            ('IELTS', 3000000, 'IELTS tayyorlov kursi', 3),
            ('English Elementary', 1500000, 'Boshlang\'ich ingliz tili', 4),
            ('Python Programming', 2000000, 'Python dasturlash asoslari', 6),
        ]

        for name, price, desc, duration in course_data:
            course, created = Course.objects.get_or_create(
                organization=org,
                name=name,
                defaults={
                    'price': price,
                    'description': desc,
                    'duration_months': duration,
                }
            )
            if created:
                self.stdout.write(f"   ✅ Kurs yaratildi: {course.name} - {price:,} so'm")
            courses.append(course)

        # 5. XONALAR
        self.stdout.write("\n5️⃣ Xonalar yaratilmoqda...")
        rooms = []
        room_names = ['101-xona', '102-xona', '201-xona', 'Katta zal']

        for room_name in room_names:
            room, created = Room.objects.get_or_create(
                organization=org,
                name=room_name,
                defaults={
                    'capacity': 15,
                    'has_projector': True,
                }
            )
            if created:
                self.stdout.write(f"   ✅ Xona yaratildi: {room.name}")
            rooms.append(room)

        # 6. GURUHLAR
        self.stdout.write("\n6️⃣ Guruhlar yaratilmoqda...")
        groups = []
        group_data = [
            ('IELTS-A', courses[0], teachers[0], [1, 2, 3, 4], time(9, 0), time(11, 0)),
            ('Elementary-B', courses[1], teachers[1], [1, 3, 5], time(14, 0), time(16, 0)),
            ('Python-C', courses[2], teachers[2], [2, 4], time(18, 0), time(20, 0)),
        ]

        today = timezone.now().date()

        for name, course, teacher, days, start, end in group_data:
            group, created = Group.objects.get_or_create(
                organization=org,
                name=name,
                defaults={
                    'course': course,
                    'teacher': teacher,
                    'room': rooms[0],
                    'start_date': today,
                    'end_date': today + timedelta(days=90),
                    'schedule_days': days,
                    'start_time': start,
                    'end_time': end,
                    'status': 'active',
                }
            )
            if created:
                self.stdout.write(f"   ✅ Guruh yaratildi: {group.name}")
            groups.append(group)

        # 7. GURUHLARGA O'QUVCHILAR QO'SHISH
        self.stdout.write("\n7️⃣ O'quvchilarni guruhlarga biriktirish...")
        for i, group in enumerate(groups):
            group_students = students[i*2:(i+1)*2]
            for student in group_students:
                gs, created = GroupStudent.objects.get_or_create(
                    group=group,
                    student=student,
                    defaults={
                        'joined_at': today,
                        'status': 'active',
                    }
                )
                if created:
                    self.stdout.write(f"   ✅ {student.full_name} → {group.name}")

        # 8. MOLIYA - KASSALAR
        self.stdout.write("\n8️⃣ Kassalar yaratilmoqda...")
        accounts = []
        account_names = ['Asosiy kassa', 'Payme kassa', 'Click kassa']

        for acc_name in account_names:
            account, created = Account.objects.get_or_create(
                organization=org,
                name=acc_name,
                defaults={
                    'balance': Decimal('10000000'),
                    'account_type': 'cash',
                }
            )
            if created:
                self.stdout.write(f"   ✅ Kassa yaratildi: {account.name} - {account.balance:,} so'm")
            accounts.append(account)

        # 9. MOLIYA - KATEGORIYALAR
        self.stdout.write("\n[9] Kategoriyalar yaratilmoqda...")
        categories = []
        category_data = [
            ('O\'quvchi to\'lovi', 'income'),
            ('O\'qituvchi oylik', 'expense'),
            ('Ijara', 'expense'),
            ('Kommunal xizmatlar', 'expense'),
            ('Reklama', 'expense'),
            ('Boshqa kirim', 'income'),
            ('Boshqa chiqim', 'expense'),
        ]

        for name, trans_type in category_data:
            category, created = TransactionCategory.objects.get_or_create(
                organization=org,
                name=name,
                defaults={
                    'transaction_type': trans_type,
                }
            )
            if created:
                self.stdout.write(f"   + Kategoriya yaratildi: {category.name}")
            categories.append(category)

        # 10. TRANZAKSIYALAR
        self.stdout.write("\n[10] Tranzaksiyalar yaratilmoqda...")
        for student in students[:3]:
            transaction = Transaction.objects.create(
                organization=org,
                account=accounts[0],
                amount=Decimal('1500000'),
                transaction_type='income',
                category=categories[0],
                description=f"{student.full_name} - Kurs to'lovi",
                student=student,
                created_by=admin,
            )
            self.stdout.write(f"   + To'lov: {student.full_name} - 1,500,000 so'm")

        # 11. CRM - BOSQICHLAR VA MANBALAR
        self.stdout.write("\n1️⃣1️⃣ CRM ma'lumotlari yaratilmoqda...")
        stages = []
        stage_names = ['Yangi', 'Qo\'ng\'iroq qilindi', 'Uchrashuv', 'Yozildi', 'Rad etdi']

        for i, stage_name in enumerate(stage_names):
            stage, created = Stage.objects.get_or_create(
                organization=org,
                name=stage_name,
                defaults={
                    'order': i,
                    'color': ['#3B82F6', '#EAB308', '#10B981', '#8B5CF6', '#EF4444'][i],
                }
            )
            if created:
                self.stdout.write(f"   ✅ Bosqich yaratildi: {stage.name}")
            stages.append(stage)

        # Manbalar
        sources = []
        source_names = ['Instagram', 'Telegram', 'Do\'st tavsiyasi', 'Ko\'chadan', 'Boshqa']

        for source_name in source_names:
            source, created = LeadSource.objects.get_or_create(
                organization=org,
                name=source_name,
                defaults={}
            )
            if created:
                self.stdout.write(f"   ✅ Manba yaratildi: {source.name}")
            sources.append(source)

        # Leadlar
        lead_data = [
            ('Akmal Yusupov', '+998901112233', sources[0], stages[0]),
            ('Dilshod Normatov', '+998902223344', sources[1], stages[1]),
            ('Feruza Karimova', '+998903334455', sources[2], stages[2]),
        ]

        for full_name, phone, source, stage in lead_data:
            lead, created = Lead.objects.get_or_create(
                organization=org,
                phone=phone,
                defaults={
                    'full_name': full_name,
                    'source': source,
                    'stage': stage,
                    'assigned_to': admin,
                }
            )
            if created:
                self.stdout.write(f"   ✅ Lead yaratildi: {lead.full_name} ({stage.name})")

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS('🎉 BARCHA MA\'LUMOTLAR MUVAFFAQIYATLI YARATILDI!'))
        self.stdout.write("=" * 60)
        self.stdout.write(f"""
📊 YARATILGAN MA'LUMOTLAR:
   • Tashkilot: {Organization.objects.count()}
   • Filial: {Branch.objects.count()}
   • Foydalanuvchilar: {User.objects.count()}
   • Kurslar: {Course.objects.count()}
   • Xonalar: {Room.objects.count()}
   • Guruhlar: {Group.objects.count()}
   • Kassalar: {Account.objects.count()}
   • Kategoriyalar: {TransactionCategory.objects.count()}
   • Tranzaksiyalar: {Transaction.objects.count()}
   • CRM Bosqichlar: {Stage.objects.count()}
   • CRM Manbalar: {LeadSource.objects.count()}
   • Leadlar: {Lead.objects.count()}
        """)

        self.stdout.write("\n🔑 LOGIN MA'LUMOTLARI:")
        self.stdout.write("   Admin: +998901111111 / admin123")
        self.stdout.write("   O'qituvchi: +99890jasu / teacher123")
        self.stdout.write("   O'quvchi: +998911001000 / student123")
