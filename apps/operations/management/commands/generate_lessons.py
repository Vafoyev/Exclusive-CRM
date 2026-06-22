"""
Haftalik darslarni avtomatik yaratish uchun management command.
Har hafta boshlanganda yoki jadval o'zgarganda ishga tushadi.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.education.models import Group
from apps.operations.models import Lesson


class Command(BaseCommand):
    help = 'Aktiv guruhlar uchun haftalik darslarni avtomatik yaratadi'

    def add_arguments(self, parser):
        parser.add_argument(
            '--weeks',
            type=int,
            default=1,
            help='Necha hafta oldindan dars yaratish (default: 1)'
        )
        parser.add_argument(
            '--group',
            type=int,
            help='Faqat bitta guruh uchun dars yaratish (group_id)'
        )

    def handle(self, *args, **options):
        weeks = options['weeks']
        group_id = options.get('group')
        
        today = timezone.now().date()
        
        # Guruhlarni olish
        groups = Group.objects.filter(
            status='active',
            is_deleted=False,
            schedule_days__isnull=False
        ).exclude(schedule_days=[])
        
        if group_id:
            groups = groups.filter(id=group_id)
        
        total_created = 0
        
        for group in groups:
            if not group.schedule_days or not group.start_time or not group.end_time:
                self.stdout.write(f"⏭️ {group.name} - jadval to'liq emas, o'tkazib yuborildi")
                continue
            
            # Hafta kunlari uchun darslar yaratish
            for week_offset in range(weeks):
                start_of_week = today + timedelta(weeks=week_offset)
                
                for day_num in group.schedule_days:
                    # day_num: 1=Dush, 2=Sesh, 3=Chor, 4=Pay, 5=Jum, 6=Shan, 7=Yak
                    # Python weekday: 0=Dush, 1=Sesh...
                    days_until = (day_num - 1 - start_of_week.weekday()) % 7
                    lesson_date = start_of_week + timedelta(days=days_until)
                    
                    # Agar o'tgan sana bo'lsa, keyingi haftaga o'tkazish
                    if lesson_date < today:
                        lesson_date += timedelta(weeks=1)
                    
                    # Guruhning boshlanish/tugash sanalarini tekshirish
                    if group.start_date and lesson_date < group.start_date:
                        continue
                    if group.end_date and lesson_date > group.end_date:
                        continue
                    
                    # Mavjud dars bormi tekshirish
                    lesson, created = Lesson.objects.get_or_create(
                        organization=group.organization,
                        group=group,
                        date=lesson_date,
                        start_time=group.start_time,
                        defaults={
                            'teacher': group.teacher,
                            'end_time': group.end_time,
                            'room': group.room,
                            'status': 'scheduled',
                        }
                    )
                    
                    if created:
                        total_created += 1
                        self.stdout.write(f"✅ {group.name} - {lesson_date} dars yaratildi")
        
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Jami {total_created} ta yangi dars yaratildi!"))
