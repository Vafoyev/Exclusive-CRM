"""
Do'kon uchun test ma'lumotlar yaratish.
"""
from django.core.management.base import BaseCommand
from apps.operations.shop import ShopCategory, ShopItem
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Do'kon uchun test ma'lumotlar yaratadi"

    def handle(self, *args, **options):
        org = Organization.objects.first()
        if not org:
            self.stdout.write(self.style.ERROR("Organization topilmadi!"))
            return

        # Kategoriyalar
        cat1, _ = ShopCategory.objects.get_or_create(
            organization=org, name='Gadgetlar',
            defaults={'icon': '📱', 'order': 1}
        )
        cat2, _ = ShopCategory.objects.get_or_create(
            organization=org, name='Kitoblar',
            defaults={'icon': '📚', 'order': 2}
        )
        cat3, _ = ShopCategory.objects.get_or_create(
            organization=org, name='Sovgalar',
            defaults={'icon': '🎁', 'order': 3}
        )
        cat4, _ = ShopCategory.objects.get_or_create(
            organization=org, name='Chegirmalar',
            defaults={'icon': '💸', 'order': 4}
        )
        self.stdout.write(f"Kategoriyalar yaratildi: {ShopCategory.objects.filter(organization=org).count()}")

        # Mahsulotlar
        items_data = [
            {'name': 'AirPods Pro', 'category': cat1, 'coin_price': 5000, 'stock': 5, 'is_active': True, 'is_featured': True, 'description': 'Apple AirPods Pro simsiz naushniklar'},
            {'name': 'Smart Watch', 'category': cat1, 'coin_price': 3000, 'stock': 3, 'is_active': True, 'is_featured': True, 'description': 'Samsung Galaxy Watch'},
            {'name': 'Power Bank', 'category': cat1, 'coin_price': 1500, 'stock': 8, 'is_active': True, 'description': '10000mAh quvvat manbai'},
            {'name': 'English Grammar Book', 'category': cat2, 'coin_price': 500, 'stock': 10, 'is_active': True, 'description': 'Ingliz tili grammatikasi kitobi'},
            {'name': 'IELTS Preparation', 'category': cat2, 'coin_price': 800, 'stock': 8, 'is_active': True, 'description': 'IELTS tayyorlanish uchun kitob'},
            {'name': 'Oxford Dictionary', 'category': cat2, 'coin_price': 600, 'stock': 6, 'is_active': True, 'description': 'Oxford inglizcha-o\'zbekcha lug\'at'},
            {'name': 'Premium Ruchka Set', 'category': cat3, 'coin_price': 100, 'stock': 20, 'is_active': True, 'description': '5 ta premium ruchka to\'plami'},
            {'name': 'Smart Edu Futbolka', 'category': cat3, 'coin_price': 1500, 'stock': 10, 'is_active': True, 'is_featured': True, 'description': 'Smart Edu logotipli futbolka'},
            {'name': 'Kepka', 'category': cat3, 'coin_price': 800, 'stock': 15, 'is_active': True, 'description': 'Smart Edu kepkasi'},
            {'name': 'Daftar + Qalam', 'category': cat3, 'coin_price': 200, 'stock': 30, 'is_active': True, 'description': 'A4 daftar va 3 ta qalam'},
            {'name': '10% Chegirma', 'category': cat4, 'coin_price': 2000, 'stock': 99, 'is_active': True, 'is_featured': True, 'description': 'Keyingi oy uchun 10% chegirma kuponi'},
            {'name': '1 hafta bepul', 'category': cat4, 'coin_price': 3500, 'stock': 5, 'is_active': True, 'description': '1 hafta bepul dars kuponi'},
        ]

        for item_data in items_data:
            ShopItem.objects.get_or_create(
                organization=org,
                name=item_data['name'],
                defaults=item_data
            )

        self.stdout.write(f"Mahsulotlar yaratildi: {ShopItem.objects.filter(organization=org).count()}")
        self.stdout.write(self.style.SUCCESS("Do'kon ma'lumotlari muvaffaqiyatli yaratildi!"))
